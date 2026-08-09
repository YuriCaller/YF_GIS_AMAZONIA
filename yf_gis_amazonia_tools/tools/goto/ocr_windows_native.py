# -*- coding: utf-8 -*-
"""
YF Go-To Tool — OCR nativo de Windows (Windows.Media.Ocr).

Motor PREFERIDO en Windows 10/11: viene integrado en el sistema operativo,
sin instalar ningún ejecutable externo (a diferencia de Tesseract). Solo
requiere el paquete Python `winsdk` (puro Python, sin binarios compilados,
instala en segundos) para poder llamar a la API desde QGIS.

Advertencia de plataforma: SOLO funciona en Windows. En Linux/macOS esta
función lanza RuntimeError de inmediato — el llamador (ocr_coords.py)
debe capturarlo y usar Tesseract como respaldo.

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import sys

WINSDK_PIP_SPEC = "winsdk"


def es_windows():
    """True si el sistema operativo es Windows (10/11 con el motor nativo)."""
    return sys.platform.startswith("win")


def winsdk_disponible():
    """True si el paquete `winsdk` ya está importable."""
    try:
        import winsdk.windows.media.ocr  # noqa: F401
        return True
    except Exception:
        return False


def _localizar_python():
    """Delega en core.dependencies para no duplicar la lógica.

    v3.0.6: esta función existía por triplicado en el plugin. Ahora hay
    una sola implementación compartida.
    """
    from ...core.dependencies import localizar_python
    return localizar_python()


def instalar_winsdk(log=None):
    """Instala el paquete `winsdk` con pip. Devuelve (ok, salida_texto).

    Paquete pequeño y puro Python (bindings PyWinRT oficiales de Microsoft)
    — sin compilación, instala en segundos incluso sin conexión rápida.
    """
    import subprocess  # nosec B404 — lista fija de args, sin shell
    py = _localizar_python()

    def _run(cmd):
        if log:
            log(" ".join(cmd))
        p = subprocess.run(cmd, stdout=subprocess.PIPE,  # nosec B603
                           stderr=subprocess.STDOUT, text=True)
        return p.returncode, p.stdout

    base = [py, "-m", "pip", "install", "--disable-pip-version-check"]
    out_all = ""
    for cmd in (base + ["--user", WINSDK_PIP_SPEC], base + [WINSDK_PIP_SPEC]):
        rc, out = _run(cmd)
        out_all += out + "\n"
        if rc == 0:
            return True, out_all
    return False, out_all


async def _reconocer_async(png_bytes, idioma_bcp47):
    """Corrutina winrt: bytes PNG -> texto reconocido.

    Requiere ejecutarse dentro de un loop de asyncio (ver ocr_imagen_nativo).
    """
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import (
        InMemoryRandomAccessStream, DataWriter,
    )

    engine = None
    if idioma_bcp47:
        try:
            lang = Language(idioma_bcp47)
            if OcrEngine.is_language_supported(lang):
                engine = OcrEngine.try_create_from_language(lang)
        except Exception:
            engine = None
    if engine is None:
        engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError(
            "Windows no tiene ningún paquete de idioma de OCR instalado.\n\n"
            "Actívalo en: Configuración → Hora e idioma → Idioma y región → "
            "Agregar un idioma (marca 'Reconocimiento óptico de caracteres')."
        )

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    # v3.0.4 fix: write_bytes() espera un objeto bytes-like (bytes/
    # bytearray), NO una lista de enteros. list(png_bytes) causaba
    # "a bytes-like object is required, not 'list'" — bug real detectado
    # en campo (no se puede probar WinRT fuera de Windows).
    writer.write_bytes(png_bytes)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    resultado = await engine.recognize_async(bitmap)
    return resultado.text


SETTINGS_KEY_NATIVO = "YF_GIS_Amazonia/ocr_motor_nativo_activo"
TIMEOUT_SEGUNDOS = 20


def nativo_habilitado():
    """False si el motor nativo se deshabilitó tras colgarse una vez."""
    try:
        from qgis.PyQt.QtCore import QSettings
        return QSettings().value(SETTINGS_KEY_NATIVO, True, type=bool)
    except Exception:
        return True


def set_nativo_habilitado(activo):
    """Recuerda si el motor nativo debe intentarse en el futuro."""
    try:
        from qgis.PyQt.QtCore import QSettings
        QSettings().setValue(SETTINGS_KEY_NATIVO, bool(activo))
    except Exception:  # nosec B110 - fuera de QGIS no hay QSettings; la
        pass           # preferencia simplemente no se persiste


def _qimage_a_png(qimage):
    """QImage -> bytes PNG en memoria."""
    from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice
    buf = QByteArray()
    dispositivo = QBuffer(buf)
    modo = getattr(QIODevice, "OpenModeFlag", QIODevice).WriteOnly
    dispositivo.open(modo)
    ok = qimage.save(dispositivo, "PNG")
    dispositivo.close()
    if not ok:
        raise RuntimeError("No se pudo convertir la imagen a PNG en memoria.")
    return bytes(buf)


def ocr_imagen_nativo(qimage, idioma_bcp47="es", timeout=TIMEOUT_SEGUNDOS):
    """OCR de un QImage usando el motor nativo de Windows.

    CRÍTICO — por qué esto corre en un hilo aparte:

    Las operaciones asíncronas de WinRT entregan su resultado a través
    del bucle de mensajes del hilo que las inicia. Si se llaman desde el
    hilo principal de Qt y se espera ahí mismo (asyncio.run bloquea ese
    hilo), Windows espera a que Qt bombee mensajes y Qt espera a que
    Windows responda: DEADLOCK, QGIS "(No responde)" para siempre.
    Bug real reportado en campo el 2026-07-23.

    Ejecutarlo en un hilo trabajador (apartamento MTA, sin bucle de
    mensajes) rompe el ciclo. El timeout es la red de seguridad: si algo
    se traba igual, se aborta y QGIS sigue vivo.
    """
    if not es_windows():
        raise RuntimeError(
            "El motor nativo de Windows solo funciona en Windows."
        )
    if not nativo_habilitado():
        raise RuntimeError(
            "El motor nativo está desactivado (se colgó en un intento "
            "anterior). Se usará Tesseract."
        )
    if not winsdk_disponible():
        raise RuntimeError(
            "El paquete 'winsdk' no está instalado todavía."
        )

    import asyncio
    import concurrent.futures

    png_bytes = _qimage_a_png(qimage)

    def _trabajador():
        # Bucle propio de este hilo: no toca el bucle de Qt.
        return asyncio.run(_reconocer_async(png_bytes, idioma_bcp47))

    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="yf_ocr_nativo")
    futuro = executor.submit(_trabajador)
    try:
        return futuro.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        # Auto-desactivar: mejor perder la comodidad del motor nativo que
        # volver a congelar QGIS en cada intento.
        set_nativo_habilitado(False)
        raise RuntimeError(
            "El motor nativo de Windows no respondió en {} segundos y se "
            "desactivó para evitar que QGIS se congele. Se usará Tesseract "
            "de ahora en adelante.".format(timeout)
        )
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            "El motor OCR nativo de Windows falló:\n{}".format(e)
        )
    finally:
        # wait=False: si el hilo quedó trabado, no arrastramos a QGIS con él.
        executor.shutdown(wait=False)
