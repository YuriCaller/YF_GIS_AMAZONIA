# -*- coding: utf-8 -*-
"""
Descargador automático de efemérides precisas (SP3/CLK/IONEX).

Lee la fecha del RINEX rover, calcula semana GPS y día del año,
y descarga de fuentes públicas en orden de preferencia:
  1. ESA Navigation Office (sin login)
  2. GSSC ESA (sin login)
  3. IGS BKG (sin login)

Prioriza: Final (FIN) → Rapid (RAP) → Ultra-rapid (ULT).

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os
import re
import gzip
import shutil
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timedelta, date


GPS_EPOCH = date(1980, 1, 6)


def _http_get(url, timeout=60):
    """
    Descarga HTTP(S) segura. Retorna bytes o None.
    1) Valida el esquema (solo http/https) — nunca file:// ni custom.
    2) Usa QgsBlockingNetworkRequest (API QGIS: respeta proxy/SSL del perfil).
    3) Fallback a urllib SOLO con esquema ya validado.
    """
    from urllib.parse import urlparse  # noqa: F811
    scheme = urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Esquema de URL no permitido: {scheme}")

    # Vía preferida: red nativa de QGIS
    try:
        from qgis.core import QgsBlockingNetworkRequest
        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtNetwork import QNetworkRequest
        qreq = QNetworkRequest(QUrl(url))
        try:
            qreq.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                              QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        except (AttributeError, TypeError):
            # Qt < 5.15 sin RedirectPolicyAttribute: los redirects
            # los maneja QgsBlockingNetworkRequest por defecto.
            QNetworkRequest  # no-op explícito
        qreq.setRawHeader(b"User-Agent", b"Mozilla/5.0 (YF-GIS-Amazonia)")
        blocking = QgsBlockingNetworkRequest()
        if blocking.get(qreq) == QgsBlockingNetworkRequest.ErrorCode.NoError:
            return bytes(blocking.reply().content())
        return None
    except ImportError:
        logging.getLogger(__name__).debug("suppressed", exc_info=True)  # fuera de QGIS (tests) → fallback

    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (YF-GIS-Amazonia)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 — esquema validado arriba (solo http/https)
        return resp.read()



def leer_fecha_rinex(rinex_path):
    """Lee TIME OF FIRST OBS del header de un RINEX obs.
    Retorna datetime o None."""
    try:
        with open(rinex_path, 'r', errors='replace') as f:
            for i, line in enumerate(f):
                if 'TIME OF FIRST OBS' in line:
                    parts = line.split()
                    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                    return datetime(y, m, d)
                if i > 100:  # el header no pasa de ~60 líneas
                    break
    except (OSError, ValueError, IndexError) as exc:
        # Archivo ilegible o header malformado: se reporta None y el
        # llamador muestra el mensaje al usuario.
        _ = exc
    return None


def calcular_semana_gps(fecha):
    """Retorna (semana_gps, dia_semana, dia_del_año)."""
    d = fecha.date() if isinstance(fecha, datetime) else fecha
    delta = (d - GPS_EPOCH).days
    semana = delta // 7
    dia_semana = delta % 7
    doy = d.timetuple().tm_yday
    return semana, dia_semana, doy


def construir_urls(fecha):
    """Construye URLs candidatas para SP3 y CLK, en orden de preferencia.
    Retorna dict {'sp3': [urls], 'clk': [urls]}."""
    semana, dow, doy = calcular_semana_gps(fecha)
    yyyy = fecha.year
    ddd = f"{doy:03d}"

    # Centros y tipos en orden de preferencia
    # FIN=final (mejor, ~12-18 días), RAP=rapid (~1 día)
    productos = []
    for centro, tipo, orb_int, clk_int in [
        ('ESA0OPSFIN', 'final', '05M', '30S'),
        ('IGS0OPSFIN', 'final', '15M', '30S'),
        ('ESA0OPSRAP', 'rapid', '15M', '30S'),
        ('IGS0OPSRAP', 'rapid', '15M', '05M'),
    ]:
        sp3_name = f"{centro}_{yyyy}{ddd}0000_01D_{orb_int}_ORB.SP3.gz"
        clk_name = f"{centro}_{yyyy}{ddd}0000_01D_{clk_int}_CLK.CLK.gz"
        productos.append((centro, tipo, sp3_name, clk_name))

    # Fuentes (sin login primero)
    bases = [
        f"http://navigation-office.esa.int/products/gnss-products/{semana}",
        f"https://gssc.esa.int/gnss/products/{semana}",
        f"https://igs.bkg.bund.de/root_ftp/IGS/products/{semana}",
    ]

    urls = {'sp3': [], 'clk': []}
    for base in bases:
        for centro, tipo, sp3n, clkn in productos:
            urls['sp3'].append((f"{base}/{sp3n}", tipo, centro))
            urls['clk'].append((f"{base}/{clkn}", tipo, centro))
    return urls


def descargar_archivo(url, destino, timeout=60, log=None):
    """Descarga un archivo. Retorna True si tuvo éxito."""
    try:
        data = _http_get(url, timeout=timeout)
        if not data or len(data) < 1000:  # vacío o error html
            return False
        with open(destino, 'wb') as f:
            f.write(data)
        return True
    except Exception as e:
        if log:
            log(f"   {type(e).__name__}: {url.split('/')[-1]}")
        return False


def descomprimir_gz(path_gz):
    """Descomprime .gz y retorna la ruta del archivo descomprimido."""
    destino = path_gz[:-3]  # quitar .gz
    with gzip.open(path_gz, 'rb') as f_in, open(destino, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(path_gz)
    return destino


def descargar_efemerides(rinex_rover_path, out_dir=None, log=None,
                          incluir_clk=True):
    """
    Función principal: lee fecha del RINEX, descarga SP3 (y CLK).
    Retorna dict {'sp3': path|None, 'clk': path|None, 'tipo': str, 'msg': str}
    """
    def _log(msg):
        if log:
            log(msg)

    resultado = {'sp3': None, 'clk': None, 'tipo': None, 'msg': ''}

    # 1. Leer fecha
    fecha = leer_fecha_rinex(rinex_rover_path)
    if not fecha:
        resultado['msg'] = 'No se pudo leer la fecha del RINEX rover'
        return resultado

    semana, dow, doy = calcular_semana_gps(fecha)
    _log(f"📅 Fecha RINEX: {fecha.date()} | Semana GPS {semana} día {dow} | DOY {doy}")

    # 2. Carpeta de destino
    if not out_dir:
        out_dir = os.path.dirname(rinex_rover_path)
    os.makedirs(out_dir, exist_ok=True)

    # 3. Intentar descargas en orden de preferencia
    urls = construir_urls(fecha)

    _log("⬇ Buscando órbitas precisas (SP3)...")
    for url, tipo, centro in urls['sp3']:
        nombre = url.split('/')[-1]
        destino_gz = os.path.join(out_dir, nombre)
        if descargar_archivo(url, destino_gz, log=None):
            sp3_path = descomprimir_gz(destino_gz)
            resultado['sp3'] = sp3_path
            resultado['tipo'] = tipo
            _log(f"✅ SP3 {tipo} ({centro}): {os.path.basename(sp3_path)}")
            break
    if not resultado['sp3']:
        resultado['msg'] = ('No se encontraron órbitas SP3 en fuentes públicas. '
                            'Puede que aún no estén publicadas para esta fecha.')
        _log(f"❌ {resultado['msg']}")
        return resultado

    # 4. Relojes CLK (opcional)
    if incluir_clk:
        _log("⬇ Buscando relojes precisos (CLK)...")
        for url, tipo, centro in urls['clk']:
            nombre = url.split('/')[-1]
            destino_gz = os.path.join(out_dir, nombre)
            if descargar_archivo(url, destino_gz, log=None):
                clk_path = descomprimir_gz(destino_gz)
                resultado['clk'] = clk_path
                _log(f"✅ CLK {tipo} ({centro}): {os.path.basename(clk_path)}")
                break
        if not resultado['clk']:
            _log("⚠ No se encontró CLK — RTKLIB usará relojes del SP3 (suficiente)")

    resultado['msg'] = f"Efemérides {resultado['tipo']} descargadas correctamente"
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# Auto-instalación del binario RTKLIB
# (cada reinstalación del plugin borra rtklib_bin/, así que el binario
#  debe poder recuperarse automáticamente)
# ─────────────────────────────────────────────────────────────────────────────

RTKLIB_URL = ('https://github.com/rtklibexplorer/RTKLIB/releases/'
              'download/b34k/demo5_b34k.zip')


def instalar_rtklib(bin_dir, log=None):
    """
    Descarga e instala rnx2rtkp.exe en bin_dir.
    Retorna la ruta del ejecutable o None si falla.
    """
    import zipfile
    import platform

    def _log(msg):
        if log:
            log(msg)

    exe_name = 'rnx2rtkp.exe' if platform.system() == 'Windows' else 'rnx2rtkp'
    os.makedirs(bin_dir, exist_ok=True)
    dest_exe = os.path.join(bin_dir, exe_name)

    if os.path.isfile(dest_exe):
        return dest_exe

    _log('⬇ Descargando RTKLIB demo5 b34k (~33 MB)...')
    zip_dest = os.path.join(bin_dir, '_rtklib_tmp.zip')
    try:
        data = _http_get(RTKLIB_URL, timeout=300)
        if not data or len(data) < 1_000_000:
            _log('❌ Descarga incompleta')
            return None
        with open(zip_dest, 'wb') as f:
            f.write(data)
        _log(f'✅ Descargado: {len(data):,} bytes')

        with zipfile.ZipFile(zip_dest) as z:
            for n in z.namelist():
                if n.lower().endswith(exe_name.lower()):
                    with z.open(n) as src, open(dest_exe, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    break
        os.remove(zip_dest)

        if os.path.isfile(dest_exe):
            if platform.system() != 'Windows':
                import stat
                os.chmod(dest_exe, os.stat(dest_exe).st_mode | stat.S_IEXEC)
            _log(f'✅ rnx2rtkp instalado: {os.path.getsize(dest_exe):,} bytes')
            return dest_exe
    except Exception as e:
        _log(f'❌ Error instalando RTKLIB: {e}')
        try:
            if os.path.exists(zip_dest):
                os.remove(zip_dest)
        except OSError as exc:
            _log(f'No se pudo eliminar temporal: {exc}')
    return None
