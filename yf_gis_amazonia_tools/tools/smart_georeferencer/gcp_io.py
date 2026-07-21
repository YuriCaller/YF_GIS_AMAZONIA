"""
gcp_io.py — Lectura de GCPs desde CSV/Excel.

Columnas esperadas (encabezado, insensible a may/min, espacios y guiones bajos):
    pixelX, pixelY, mapX, mapY
Acepta sinónimos comunes (px/py/col/row, x/y/este/norte, etc.). Si no hay
encabezado reconocible pero hay 4 columnas numéricas, asume ese orden.

Devuelve (src_px Nx2, map_xy Nx2) en coordenadas de PÍXEL ORIGINAL de la imagen
y coordenadas de MAPA. La conversión a espacio del item (si la imagen se
reescaló) la hace quien llama, usando item.src_scale.
"""
import csv
import numpy as np

_PX = ["pixelx", "px", "col", "column", "columna", "imgx", "xpixel", "xpix"]
_PY = ["pixely", "py", "row", "line", "fila", "imgy", "ypixel", "ypix"]
_MX = ["mapx", "x", "este", "easting", "xmap", "e", "coordx", "x_map"]
_MY = ["mapy", "y", "norte", "northing", "ymap", "n", "coordy", "y_map"]


def _norm(s):
    return s.strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _find(headers, keys):
    for i, h in enumerate(headers):
        if h in keys:
            return i
    return None


def read_gcps_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = [r for r in csv.reader(f, dialect) if any(c.strip() for c in r)]
    return _rows_to_gcps(rows)


def read_gcps_xlsx(path):
    try:
        import openpyxl
    except ImportError:
        raise ValueError("Para leer Excel falta 'openpyxl'. "
                         "Exporta a CSV o instala openpyxl.")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = [[("" if c is None else str(c)) for c in row]
            for row in ws.iter_rows(values_only=True)]
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    return _rows_to_gcps(rows)


def read_gcps(path):
    p = path.lower()
    if p.endswith((".xlsx", ".xlsm")):
        return read_gcps_xlsx(path)
    return read_gcps_csv(path)


def _rows_to_gcps(rows):
    if not rows:
        raise ValueError("El archivo está vacío.")
    headers = [_norm(c) for c in rows[0]]
    ipx, ipy = _find(headers, _PX), _find(headers, _PY)
    imx, imy = _find(headers, _MX), _find(headers, _MY)
    start = 1
    if None in (ipx, ipy, imx, imy):
        # sin encabezado reconocible: ¿4 columnas numéricas en orden?
        try:
            [float(x) for x in rows[0][:4]]
            ipx, ipy, imx, imy, start = 0, 1, 2, 3, 0
        except (ValueError, IndexError):
            raise ValueError(
                "No reconozco las columnas. Usa encabezados: "
                "pixelX, pixelY, mapX, mapY.")
    src, mp = [], []
    for r in rows[start:]:
        try:
            src.append([float(r[ipx]), float(r[ipy])])
            mp.append([float(r[imx]), float(r[imy])])
        except (ValueError, IndexError):
            continue  # nosec B112 - entrada malformada: se omite a proposito
    if len(src) < 1:
        raise ValueError("No se leyeron filas numéricas válidas.")
    return np.asarray(src, float), np.asarray(mp, float)
