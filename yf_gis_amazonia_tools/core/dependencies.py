# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Gestión de dependencias opcionales.

Centraliza la localización del intérprete Python real y la instalación
con pip de paquetes opcionales (python-docx, winsdk, ...), con un
diálogo de consentimiento.

POR QUÉ NO SE INSTALA EN SILENCIO
---------------------------------
Buena parte de los usuarios de este plugin trabaja en entidades públicas
(gobiernos regionales, direcciones agrarias, SERFOR) donde las máquinas
tienen la instalación de paquetes restringida por política, proxy o
firewall. Una instalación automática en esos equipos congela la interfaz
sin explicación, falla con un error de pip que no dice nada al usuario
final y modifica el entorno Python sin que nadie lo haya pedido.

DÓNDE SE INSTALA (cambio de fondo en v3.0.7)
--------------------------------------------
Hasta v3.0.6 se intentaba `pip install --user`. En OSGeo4W eso falla a
menudo por dos motivos distintos que el usuario no puede distinguir:

  1. pip rechaza --user cuando detecta un entorno tipo virtualenv
     ("User site-packages are not visible in this virtualenv"), que es
     como se presenta la instalación empaquetada de QGIS en Windows.
  2. Cuando sí instala, lo hace en %APPDATA%\\Python\\PythonXX\\site-packages,
     un directorio que la instalación de QGIS puede no leer (PYTHONNOUSERSITE
     o un `site` recortado), de modo que la instalación "funciona" y el
     import sigue fallando. Ese es el caso que más confunde: pip dice
     "Successfully installed" y la herramienta sigue bloqueada.

Ahora se instala por defecto con `--target` en una carpeta propia dentro
del perfil de QGIS:

    <perfil>/python/dependencies

Ventajas: siempre es escribible (QGIS ya escribe ahí), no necesita
permisos de administrador, no toca la instalación de QGIS ni el Python
del sistema, sobrevive a reinstalaciones del plugin y —lo importante—
nosotros controlamos su presencia en sys.path, así que si pip termina
bien el import funciona sin reiniciar.

`--user` y la instalación normal quedan como respaldo por si `--target`
no fuera viable.

NOTA SOBRE pip.main()
---------------------
No se usa `pip.main()`: el propio equipo de pip lo desaconseja porque no
es reentrante y contamina el proceso anfitrión. Se invoca pip como
subproceso del intérprete correcto, que en OSGeo4W no siempre coincide
con el del proceso de QGIS.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import glob
import importlib
import os
import sys

TIMEOUT_PIP = 300  # s. Una red institucional lenta puede tardar bastante.

MANUAL_URL = "https://yuricaller.github.io/YF_GIS_AMAZONIA/instalacion/dependencias/"


# ──────────────────────────────────────────────────────────────────────
# Carpeta propia de paquetes
# ──────────────────────────────────────────────────────────────────────

def directorio_paquetes(crear=False):
    """Carpeta donde el plugin instala sus dependencias opcionales.

    Vive dentro del perfil de QGIS, no dentro del plugin: así no se
    borra al actualizar o reinstalar el plugin, y no obliga a volver a
    descargar todo en equipos sin internet.
    """
    try:
        from qgis.core import QgsApplication
        base = QgsApplication.qgisSettingsDirPath()
    except Exception:
        base = os.path.expanduser("~/.qgis3")

    destino = os.path.join(base, "python", "dependencies")
    if crear:
        try:
            os.makedirs(destino, exist_ok=True)
        except OSError:
            return None
    return destino


def asegurar_sys_path():
    """Añade la carpeta de dependencias a sys.path.

    Debe llamarse UNA VEZ al arrancar el plugin, antes de que cualquier
    herramienta intente importar un paquete opcional. Se antepone
    (insert 0) para que una versión instalada por el usuario tenga
    prioridad sobre una copia antigua que pudiera venir en el sistema.
    """
    destino = directorio_paquetes()
    if destino and os.path.isdir(destino) and destino not in sys.path:
        sys.path.insert(0, destino)
        return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Localización del intérprete
# ──────────────────────────────────────────────────────────────────────

def localizar_python():
    """Devuelve la ruta del Python real detrás de qgis-bin.exe.

    En Windows/OSGeo4W, sys.executable apunta al ejecutable de QGIS, no
    al intérprete; instalar con él no siempre coloca el paquete donde
    QGIS lo va a importar.
    """
    exe = sys.executable or ""
    if "python" in os.path.basename(exe).lower():
        return exe

    nombres = ("python.exe", "python3.exe", "pythonw.exe", "python3", "python")
    candidatos = []
    for n in nombres:
        candidatos += [
            os.path.join(sys.prefix, n),
            os.path.join(os.path.dirname(exe), n),
            os.path.join(sys.prefix, "Scripts", n),
            os.path.join(sys.prefix, "bin", n),
        ]

    # Distribución OSGeo4W: el intérprete no está junto a qgis-bin.exe
    # sino en <raíz OSGeo4W>/apps/PythonXX/python.exe. La raíz está dos
    # o tres niveles por encima según la versión del instalador, así que
    # se prueban ambas en vez de fijar una.
    raiz_dir = os.path.dirname(exe)
    for saltos in (2, 3, 4):
        raiz = os.path.abspath(os.path.join(raiz_dir, *([".."] * saltos)))
        candidatos += sorted(
            glob.glob(os.path.join(raiz, "apps", "Python*", "python.exe")),
            reverse=True,  # la versión más alta primero
        )

    for c in candidatos:
        if c and os.path.exists(c):
            return c
    return exe


# ──────────────────────────────────────────────────────────────────────
# Proxy
# ──────────────────────────────────────────────────────────────────────

def _entorno_con_proxy():
    """Copia del entorno con el proxy que QGIS ya tiene configurado.

    En una dirección regional el usuario suele haber configurado el
    proxy en QGIS (Opciones → Red) porque sin eso no le cargan los WMS.
    pip, en cambio, no lee esa configuración: mira las variables de
    entorno. Trasladarla evita el fallo más frecuente en entidades
    públicas, donde el usuario no sabría construir la URL del proxy.
    """
    env = os.environ.copy()
    try:
        from qgis.PyQt.QtCore import QSettings
        s = QSettings()
        if s.value("proxy/proxyEnabled", False, type=bool):
            host = s.value("proxy/proxyHost", "", type=str)
            port = s.value("proxy/proxyPort", "", type=str)
            if host and port:
                usuario = s.value("proxy/proxyUser", "", type=str)
                clave = s.value("proxy/proxyPassword", "", type=str)
                cred = "{}:{}@".format(usuario, clave) if usuario else ""
                url = "http://{}{}:{}".format(cred, host, port)
                env.setdefault("HTTP_PROXY", url)
                env.setdefault("HTTPS_PROXY", url)
    except Exception:  # nosec B110 - sin proxy se intenta igual
        pass
    return env


# ──────────────────────────────────────────────────────────────────────
# Comprobación e instalación
# ──────────────────────────────────────────────────────────────────────

def esta_disponible(modulo):
    """True si el módulo puede importarse ahora mismo."""
    try:
        importlib.import_module(modulo)
        return True
    except ImportError:
        return False


def _ejecutar_pip(cmd, timeout, log=None):
    """Lanza pip como subproceso. Devuelve (returncode, salida)."""
    import subprocess  # nosec B404 - lista fija de args, sin shell

    if log:
        log(" ".join(cmd))

    kwargs = dict(
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=timeout, env=_entorno_con_proxy(),
    )
    # En Windows, evita el parpadeo de una consola negra sobre QGIS.
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    p = subprocess.run(cmd, **kwargs)  # nosec B603 - args fijos, sin shell
    return p.returncode, (p.stdout or "")


def instalar_paquete(paquete, log=None, timeout=TIMEOUT_PIP, destino=None):
    """Instala `paquete` con pip. Devuelve (ok, salida, diagnostico).

    Estrategia, en orden:
      1. --target <perfil>/python/dependencies  → siempre escribible,
         sin permisos de administrador, y bajo nuestro control en
         sys.path, de modo que el import funciona sin reiniciar QGIS.
      2. --user                                 → respaldo.
      3. instalación normal                     → último recurso.

    `paquete` puede ser un nombre de PyPI o la ruta a un archivo .whl,
    lo que permite instalar sin internet.
    """
    py = localizar_python()
    base = [py, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-input"]

    carpeta = destino or directorio_paquetes(crear=True)
    intentos = []
    if carpeta:
        # --upgrade evita que pip se salte la instalación si encuentra
        # una copia vieja en el propio --target.
        intentos.append(base + ["--target", carpeta, "--upgrade", paquete])
    intentos.append(base + ["--user", paquete])
    intentos.append(base + [paquete])

    salida = ""
    for cmd in intentos:
        try:
            rc, out = _ejecutar_pip(cmd, timeout, log=log)
        except Exception as e:  # incluye TimeoutExpired y OSError
            nombre = type(e).__name__
            if "Timeout" in nombre:
                return False, salida, (
                    "La instalación superó el tiempo límite ({} s). Suele "
                    "indicar una red muy lenta o un proxy que no responde."
                    .format(timeout))
            return False, salida, "No se pudo ejecutar pip: {}".format(e)

        salida += out + "\n"
        if rc == 0:
            return True, salida, ""

    return False, salida, _diagnosticar(salida)


def instalar_desde_wheel(ruta_whl, log=None, timeout=TIMEOUT_PIP):
    """Instala desde un .whl local, sin tocar la red.

    Vía para equipos sin salida a internet: se descarga el archivo en
    otra máquina y se trae por USB.
    """
    py = localizar_python()
    carpeta = directorio_paquetes(crear=True)
    cmd = [py, "-m", "pip", "install", "--disable-pip-version-check",
           "--no-input", "--no-index"]
    if carpeta:
        cmd += ["--target", carpeta, "--upgrade"]
    cmd.append(ruta_whl)

    try:
        rc, salida = _ejecutar_pip(cmd, timeout, log=log)
    except Exception as e:
        return False, "", "No se pudo ejecutar pip: {}".format(e)

    if rc == 0:
        return True, salida, ""
    return False, salida, _diagnosticar(salida)


def _diagnosticar(salida):
    """Traduce la salida de pip a una causa probable, en lenguaje claro."""
    s = (salida or "").lower()
    if "proxy" in s or "proxyerror" in s:
        return ("La conexión pasa por un proxy que bloqueó la descarga. "
                "Es habitual en redes institucionales. Si conoce los datos "
                "del proxy, configúrelo en QGIS (Configuración → Opciones → "
                "Red) y vuelva a intentarlo: el plugin los reutiliza.")
    if ("ssl" in s and "certificate" in s) or "certificate_verify_failed" in s:
        return ("El certificado SSL fue rechazado. Suele deberse a un "
                "filtrado de red corporativo que inspecciona el tráfico.")
    if ("permission denied" in s or "access is denied" in s
            or "winerror 5" in s):
        return ("Sin permisos de escritura. El equipo puede tener la "
                "instalación de paquetes restringida por política.")
    if "not visible in this virtualenv" in s:
        return ("Esta instalación de QGIS no admite la modalidad --user. "
                "Use la instalación desde archivo .whl.")
    if ("could not find a version" in s or "no matching distribution" in s
            or "temporary failure in name resolution" in s
            or "failed to establish a new connection" in s
            or "network is unreachable" in s):
        return ("No se pudo alcanzar el repositorio de paquetes (PyPI). "
                "Puede que el equipo no tenga salida a internet.")
    if "no module named pip" in s:
        return ("Esta instalación de Python no incluye pip. Ejecute "
                "primero: python -m ensurepip --upgrade")
    return ("La instalación falló. Revise el detalle técnico para más "
            "información.")


def recargar(modulo):
    """Hace visible un paquete recién instalado sin reiniciar QGIS."""
    asegurar_sys_path()
    try:
        import site
        d = site.getusersitepackages()
        if d and os.path.isdir(d) and d not in sys.path:
            sys.path.append(d)
    except Exception:  # nosec B110 - si site no coopera, se prueba igual
        pass

    importlib.invalidate_caches()

    # Si un intento anterior dejó el módulo a medias en sys.modules, un
    # import normal devolvería ese resto en vez de la instalación nueva.
    for nombre in [m for m in list(sys.modules) if m.split(".")[0] == modulo]:
        sys.modules.pop(nombre, None)

    try:
        importlib.import_module(modulo)
        return True
    except ImportError:
        return False


def diagnostico_entorno():
    """Texto de diagnóstico para pegar en un reporte de incidencia."""
    carpeta = directorio_paquetes()
    lineas = [
        "Python del proceso : {}".format(sys.executable),
        "Intérprete pip     : {}".format(localizar_python()),
        "Versión Python     : {}".format(sys.version.split()[0]),
        "Carpeta paquetes   : {}".format(carpeta),
        "  existe           : {}".format(os.path.isdir(carpeta) if carpeta else False),
        "  en sys.path      : {}".format(carpeta in sys.path if carpeta else False),
        "",
        "Paquetes opcionales:",
    ]
    for mod, paq in (("docx", "python-docx"), ("cv2", "opencv-python"),
                     ("winsdk", "winsdk"), ("pytesseract", "pytesseract"),
                     ("openpyxl", "openpyxl")):
        estado = "disponible" if esta_disponible(mod) else "NO instalado"
        lineas.append("  {:<16} {:<18} {}".format(mod, paq, estado))
    return "\n".join(lineas)


# ──────────────────────────────────────────────────────────────────────
# Diálogo de consentimiento
# ──────────────────────────────────────────────────────────────────────

def asegurar_dependencia(modulo, paquete, descripcion, parent=None,
                         tamano_aprox="", log=None):
    """Garantiza que `modulo` esté disponible, pidiendo permiso si falta.

    Devuelve True si el módulo puede usarse al terminar.
    """
    asegurar_sys_path()
    if esta_disponible(modulo):
        return True

    from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMessageBox
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QDesktopServices
    from qgis.PyQt.QtCore import QUrl

    detalle = (
        "<p>Esta herramienta necesita el componente "
        "<b>{paquete}</b>{tam}.</p>"
        "<p>{descripcion}</p>"
        "<p>Puede instalarse ahora desde QGIS, sin cerrar el programa. "
        "Se descargará desde el repositorio oficial de paquetes de "
        "Python (PyPI) y se guardará en su perfil de QGIS, sin modificar "
        "la instalación del programa ni requerir permisos de "
        "administrador.</p>"
        "<p><i>Si trabaja en una entidad con la red restringida y la "
        "descarga se bloquea, puede instalarlo desde un archivo .whl "
        "descargado en otro equipo.</i></p>"
    ).format(paquete=paquete,
             tam=" (~{})".format(tamano_aprox) if tamano_aprox else "",
             descripcion=descripcion)

    caja = QMessageBox(parent)
    caja.setWindowTitle("Componente necesario")
    caja.setIcon(QMessageBox.Icon.Question)
    caja.setTextFormat(Qt.TextFormat.RichText)
    caja.setText(detalle)
    btn_si = caja.addButton("Instalar ahora",
                            QMessageBox.ButtonRole.AcceptRole)
    btn_whl = caja.addButton("Instalar desde archivo .whl...",
                             QMessageBox.ButtonRole.ActionRole)
    caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    caja.exec()

    pulsado = caja.clickedButton()
    if pulsado is btn_whl:
        ruta, _ = QFileDialog.getOpenFileName(
            parent, "Seleccione el archivo .whl de {}".format(paquete),
            "", "Paquetes Python (*.whl)")
        if not ruta:
            return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, salida, diagnostico = instalar_desde_wheel(ruta, log=log)
        finally:
            QApplication.restoreOverrideCursor()
    elif pulsado is btn_si:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, salida, diagnostico = instalar_paquete(paquete, log=log)
        finally:
            QApplication.restoreOverrideCursor()
    else:
        return False

    if ok and recargar(modulo):
        QMessageBox.information(
            parent, "Componente instalado",
            "<b>{}</b> se instaló correctamente. Ya puede usar la "
            "herramienta.".format(paquete))
        return True

    if ok:
        QMessageBox.information(
            parent, "Reinicie QGIS",
            "<b>{}</b> se instaló, pero QGIS necesita reiniciarse para "
            "reconocerlo.<br><br>Cierre y vuelva a abrir QGIS, y luego "
            "use la herramienta de nuevo.".format(paquete))
        return False

    carpeta = directorio_paquetes()
    manual = QMessageBox(parent)
    manual.setWindowTitle("No se pudo instalar")
    manual.setIcon(QMessageBox.Icon.Warning)
    manual.setTextFormat(Qt.TextFormat.RichText)
    manual.setText(
        "<p>No se pudo instalar <b>{paquete}</b>.</p>"
        "<p><b>Causa probable:</b> {diag}</p>"
        "<p><b>Instalación manual.</b> Abra la consola de OSGeo4W (menú "
        "Inicio → QGIS → <i>OSGeo4W Shell</i>) y ejecute exactamente esta "
        "orden, con las comillas:</p>"
        "<p><code>\"{py}\" -m pip install --target \"{destino}\" "
        "{paquete}</code></p>"
        "<p>Use esa ruta de intérprete y no simplemente <code>python</code>: "
        "en OSGeo4W puede haber varios, y el paquete debe quedar donde "
        "QGIS lo busca.</p>"
        "<p><b>Sin internet:</b> descargue el archivo .whl de {paquete} "
        "desde pypi.org en un equipo con conexión, tráigalo por USB y use "
        "el botón «Instalar desde archivo .whl» de esta misma ventana.</p>"
        .format(paquete=paquete, diag=diagnostico, py=localizar_python(),
                destino=carpeta or ""))
    if salida:
        manual.setDetailedText(salida + "\n\n" + diagnostico_entorno())
    btn_ayuda = manual.addButton("Ver manual", QMessageBox.ButtonRole.HelpRole)
    manual.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
    manual.exec()
    if manual.clickedButton() is btn_ayuda:
        QDesktopServices.openUrl(QUrl(MANUAL_URL))
    return False
