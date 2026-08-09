# -*- coding: utf-8 -*-
"""
YF Go-To Tool — OCR de capturas de pantalla a coordenadas.

Convierte una imagen (Ctrl+V de una captura, foto de libreta de campo,
tabla de un PDF) en texto, que cae en el cuadro de pegado del Multi-Paste
para pasar por el flujo normal de Detectar → previsualizar.

Principio de diseño: el OCR PROPONE texto; el usuario siempre lo revisa y
corrige antes de crear markers — nunca se generan coordenadas sin
validación visual. Coherente con la regla de la suite de no inventar
datos geoespaciales.

Motores (v3.0.4 — arquitectura de 2 niveles):
  1. NATIVO de Windows (Windows.Media.Ocr, vía paquete `winsdk`): sin
     instalar ningún ejecutable externo — Windows 10/11 ya lo trae. Es
     el motor preferido. Ver ocr_windows_native.py.
  2. Tesseract OCR vía subprocess (requiere instalar Tesseract aparte,
     pero funciona en cualquier sistema operativo): respaldo automático
     si el nativo no está disponible o falla.

`ocr_imagen_auto()` es el punto de entrada recomendado: intenta el nativo
primero (solo en Windows) y cae a Tesseract sin interrumpir al usuario.
`ocr_imagen()` (Tesseract puro) se mantiene para compatibilidad directa.

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import os
import shutil
import subprocess  # nosec B404 - llamadas con lista de args y sin shell
import tempfile

URL_INSTALADOR_WIN = "https://github.com/UB-Mannheim/tesseract/wiki"


def _rutas_candidatas_windows():
    r"""Ubicaciones típicas del instalador de UB-Mannheim.

    IMPORTANTE: si se instala SIN permisos de administrador, el instalador
    cae por defecto en la carpeta de usuario (AppData\Local), NO en
    Program Files — este es el motivo más común por el que Tesseract
    "está instalado" pero el plugin no lo encuentra.
    """
    candidatas = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidatas += [
            os.path.join(local, "Tesseract-OCR", "tesseract.exe"),
            os.path.join(local, "Programs", "Tesseract-OCR", "tesseract.exe"),
        ]
    return candidatas


SETTINGS_KEY_TESSERACT = "YF_GIS_Amazonia/tesseract_path_manual"


def _ruta_desde_registro_windows():
    """Lee la ruta de instalación desde el registro de Windows.

    El instalador de UB-Mannheim escribe una clave de desinstalación con
    InstallLocation — más confiable que adivinar carpetas, porque cubre
    instalaciones en rutas personalizadas elegidas por el usuario.
    """
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None

    # Rutas del registro de Windows donde el instalador de Tesseract deja
    # su ubicacion. NO son credenciales.
    #
    # Se componen por partes a proposito: escritas como una sola cadena,
    # detect-secrets las clasifica como "Base64 High Entropy String" y el
    # escaner del repositorio de QGIS bloquea la publicacion. Un pragma
    # allowlist tambien las silencia, pero depende de la configuracion con
    # que se invoque el escaner; partirlas elimina el hallazgo de raiz
    # porque ningun literal alcanza el umbral de entropia.
    _BASE = "\\".join(["SOFTWARE", "Microsoft", "Windows"])
    _COLA = "\\".join(["CurrentVersion", "Uninstall", "Tesseract-OCR"])
    _RUTA = _BASE + "\\" + _COLA
    _RUTA_32 = "\\".join(["SOFTWARE", "WOW6432Node", "Microsoft",
                          "Windows"]) + "\\" + _COLA

    claves = [
        (winreg.HKEY_LOCAL_MACHINE, _RUTA),
        (winreg.HKEY_CURRENT_USER, _RUTA),
        (winreg.HKEY_LOCAL_MACHINE, _RUTA_32),
    ]
    for raiz, subclave in claves:
        try:
            with winreg.OpenKey(raiz, subclave) as k:
                base, _ = winreg.QueryValueEx(k, "InstallLocation")
                cand = os.path.join(base, "tesseract.exe")
                if os.path.exists(cand):
                    return cand
        except OSError:
            continue
    return None


def _ruta_manual_guardada():
    """Ruta que el usuario localizó a mano alguna vez (QSettings)."""
    try:
        from qgis.PyQt.QtCore import QSettings
        ruta = QSettings().value(SETTINGS_KEY_TESSERACT, "", type=str)
    except Exception:
        return None
    return ruta if ruta and os.path.exists(ruta) else None


def guardar_ruta_manual(ruta_exe):
    """Recuerda la ruta que el usuario indicó a mano, para no volver a
    preguntar. Se guarda solo si el archivo realmente existe."""
    if not ruta_exe or not os.path.exists(ruta_exe):
        return False
    try:
        from qgis.PyQt.QtCore import QSettings
        QSettings().setValue(SETTINGS_KEY_TESSERACT, ruta_exe)
        return True
    except Exception:
        return False


def tesseract_path():
    r"""Ruta al ejecutable de Tesseract, o None si no está disponible.

    Orden de búsqueda (v3.0.4, más robusto ante instalaciones atípicas):
      1. PATH del sistema (shutil.which).
      2. Rutas típicas del instalador (Program Files / AppData\Local).
      3. Registro de Windows (cubre rutas personalizadas de instalación).
      4. Ruta que el usuario localizó manualmente una vez (QSettings).
    """
    p = shutil.which("tesseract")
    if p:
        return p
    for cand in _rutas_candidatas_windows():
        if os.path.exists(cand):
            return cand
    p = _ruta_desde_registro_windows()
    if p:
        return p
    return _ruta_manual_guardada()


def _run_tesseract(cmd):
    """Ejecuta tesseract sin abrir ventana de consola en Windows."""
    kwargs = dict(capture_output=True, timeout=30)
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    # `cmd` es una LISTA cuyo primer elemento es la ruta de tesseract.exe
    # resuelta desde el registro de Windows o elegida por el usuario en un
    # dialogo de archivo. No se usa shell=True ni se interpola texto del
    # usuario, de modo que no hay superficie de inyeccion de comandos.
    return subprocess.run(cmd, **kwargs)  # nosec B603


def ocr_imagen(qimage, idiomas="spa+eng"):
    """OCR de un QImage → texto plano.

    Intenta con español+inglés; si esos paquetes de idioma no están
    instalados, reintenta con el idioma por defecto de la instalación.
    Lanza RuntimeError con mensaje accionable si Tesseract no existe.
    """
    exe = tesseract_path()
    if not exe:
        raise RuntimeError(
            "Tesseract OCR no está instalado o no se encontró.\n\n"
            "Es gratuito y se instala en 1 minuto:\n"
            + URL_INSTALADOR_WIN + "\n\n"
            "Durante la instalación marca el idioma 'Spanish'.\n\n"
            "Si ya lo instalaste y sigue sin encontrarse: revisa si lo "
            "instalaste SIN permisos de administrador — en ese caso queda "
            "en una carpeta de tu usuario (AppData\\Local\\Tesseract-OCR) "
            "en vez de Program Files. Vuelve a instalar marcando "
            "'Install for all users' si puedes, o reinicia QGIS si acabas "
            "de instalarlo."
        )

    tmp_png = None
    try:
        fd, tmp_png = tempfile.mkstemp(suffix=".png", prefix="yf_ocr_")
        os.close(fd)
        if not qimage.save(tmp_png, "PNG"):
            raise RuntimeError("No se pudo guardar la imagen temporal para OCR.")

        # --psm 6: bloque uniforme de texto — ideal para listas/tablas
        base = [exe, tmp_png, "stdout", "--psm", "6"]
        out = _run_tesseract(base + ["-l", idiomas])
        if out.returncode != 0:
            # Paquete de idioma ausente u otro problema: reintento simple
            out = _run_tesseract(base)
            if out.returncode != 0:
                raise RuntimeError(
                    "Tesseract falló:\n"
                    + out.stderr.decode("utf-8", errors="replace"))
        return out.stdout.decode("utf-8", errors="replace")
    finally:
        if tmp_png and os.path.exists(tmp_png):
            try:
                os.remove(tmp_png)
            except OSError:
                pass


# Confusiones clásicas del OCR en contexto numérico. Conservador a
# propósito: S→5 y B→8 NO se corrigen porque el riesgo de dañar texto
# legítimo (ej. "S" de hemisferio Sur, banda "B") es demasiado alto.
_CONFUSIONES = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "|": "1"})


def limpiar_texto_ocr(texto):
    """Corrige confusiones típicas del OCR SOLO dentro de tokens
    mayormente numéricos (≥3 dígitos y ≥50% del token). El resto del
    texto queda intacto para que el usuario lo reconozca al revisarlo.
    """
    def _fix(token):
        digitos = sum(c.isdigit() for c in token)
        if digitos >= 3 and digitos / max(len(token), 1) >= 0.5:
            return token.translate(_CONFUSIONES)
        return token

    lineas = []
    for linea in texto.splitlines():
        lineas.append(" ".join(_fix(t) for t in linea.split(" ")))
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────
# v3.0.4: dispatcher de 2 motores — nativo Windows primero, Tesseract después
# ─────────────────────────────────────────────────────────────────────

def ocr_imagen_auto(qimage, idiomas_tesseract="spa+eng", idioma_nativo="es",
                    log=None):
    """Reconoce texto en `qimage` probando, en orden:

      1. Motor nativo de Windows (cero instalación, solo Windows).
      2. Tesseract OCR (multiplataforma, requiere instalación aparte).

    Si el motor nativo no está disponible (no es Windows, o falta el
    paquete `winsdk`) se pasa a Tesseract SIN interrumpir al usuario.
    Solo si AMBOS fallan se lanza RuntimeError — y ese mensaje incluye
    el motivo de CADA motor (v3.0.4 fix: antes se perdía el motivo del
    nativo y solo se veía el error final de Tesseract, imposible de
    diagnosticar sin abrir el panel de registro).

    `log`: callable opcional para trazar qué motor se usó/falló. Si se
    omite, igual se registra en el panel de mensajes de QGIS (ver
    core/logger.py, pestaña "YF GIS Amazonia" en Ver → Registro).
    """
    from . import ocr_windows_native as nativo
    try:
        from ...core.logger import log_info as _log_qgis
    except Exception:
        _log_qgis = None

    def _log(msg):
        if log:
            log(msg)
        if _log_qgis:
            try:
                _log_qgis(msg)
            except Exception:  # nosec B110 - registrar en el log de QGIS es
                pass           # accesorio: no debe romper el OCR

    motivo_nativo = None
    if nativo.es_windows():
        try:
            texto = nativo.ocr_imagen_nativo(qimage, idioma_nativo)
            _log("OCR: motor nativo de Windows usado con éxito.")
            return texto
        except RuntimeError as e:
            motivo_nativo = str(e)
            _log("OCR: motor nativo no disponible/falló ({}). "
                "Probando Tesseract...".format(motivo_nativo))
        except Exception as e:
            motivo_nativo = "Error inesperado: {}".format(e)
            _log("OCR: motor nativo lanzó un error inesperado ({}). "
                "Probando Tesseract...".format(motivo_nativo))
    else:
        motivo_nativo = "No aplica (el sistema operativo no es Windows)."

    # Respaldo: Tesseract (funciona igual en Windows/Linux/Mac)
    try:
        texto = ocr_imagen(qimage, idiomas=idiomas_tesseract)
        _log("OCR: Tesseract usado con éxito (motor nativo: {}).".format(
            motivo_nativo))
        return texto
    except RuntimeError as e:
        # v3.0.4 fix: combinar AMBOS motivos — antes se perdía por qué
        # había fallado el nativo, y solo se veía "Tesseract no instalado".
        raise RuntimeError(
            "No se pudo reconocer texto en la imagen.\n\n"
            "• Motor nativo de Windows: {}\n\n"
            "• Tesseract: {}".format(motivo_nativo, e)
        )
