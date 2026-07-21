"""
georef_layer.py — Genera la georreferenciación de la imagen para cargarla como
una capa ráster real en la tabla de contenidos.

  - 0–2 GCPs (transformación afín): VRT con geotransform (rápido, sin warp).
  - 3+  GCPs: se WARPEA a un GeoTIFF real (no VRT). Motivo: el VRT warpeado lee
    el origen de forma perezosa por tiles, y con orígenes JPEG/JFIF eso falla
    ("Pointer 'hBand' is NULL in GDALRasterIOEx") y/o no extiende la deformación
    fuera del marco original. El GeoTIFF decodifica el origen una vez, es
    autocontenido, renderiza confiable y contiene toda la deformación.

Para 3 GCPs se usa polinomial orden 1 (afín exacto, evita el TPS degenerado);
TPS solo con 4+ GCPs. Validado con GDAL 3.8.
"""
import logging
import os
import numpy as np
from osgeo import gdal, osr


def decode_to_gtiff(src_path, out_tif):
    """Decodifica el origen (JPEG/JFIF/PNG/etc.) a un GeoTIFF SIN georreferenciar.
    Se hace UNA vez por sesión: warpear directo desde un JPEG/JFIF falla
    ('hBand is NULL') porque el JPEG no permite lectura aleatoria por tiles.
    El GeoTIFF resultante sí, y todo el pipeline de warp opera sobre él."""
    ds = gdal.Translate(out_tif, src_path, format="GTiff",
                        creationOptions=["TILED=YES"])
    ok = ds is not None
    ds = None
    return out_tif if ok else src_path


def _wkt(authid):
    srs = osr.SpatialReference()
    srs.SetFromUserInput(authid)            # p.ej. 'EPSG:32719'
    return srs.ExportToWkt()


def _geotransform_from(fwd, step=1.0):
    """Geotransform GDAL (6 coef) de una transformación afín fwd (px ITEM -> mapa),
    muestreando con paso `step` para expresarlo en píxeles ORIGINALES.
    step = src_scale (px_item por px_original)."""
    p = fwd.map(np.array([[0, 0], [step, 0], [0, step]], float))
    x0, y0 = p[0]; x1, y1 = p[1]; x2, y2 = p[2]
    return [x0, x1 - x0, x2 - x0, y0, y1 - y0, y2 - y0]


def build_placement(src_path, fwd, src_px, map_xy, authid, out_base,
                    method="tps", src_scale=1.0):
    """Georreferencia `src_path` (imagen ORIGINAL). Devuelve la RUTA del archivo
    creado (.vrt para <3 GCPs, .tif para >=3).
      fwd       : transformación afín actual (px item -> mapa), caso <3 GCPs.
      src_px    : GCPs en px ORIGINAL (usa item.gcps_original_px()).
      map_xy    : GCPs en coords de mapa.
      out_base  : ruta SIN extensión; la función agrega .vrt o .tif.
      src_scale : px_item por px_original (deshace el reescalado del preview)."""
    wkt = _wkt(authid)
    n = len(src_px)

    if n < 3:
        out = out_base + ".vrt"
        gt = _geotransform_from(fwd, step=src_scale)
        ds = gdal.Translate(out, src_path, format="VRT")
        ds.SetGeoTransform(gt)
        ds.SetProjection(wkt)
        ds = None
        return out

    # --- 3+ GCPs: warp a GeoTIFF real ---
    gcps = [gdal.GCP(float(mx), float(my), 0.0, float(px), float(py))
            for (px, py), (mx, my) in zip(src_px, map_xy)]
    gcp_vrt = out_base + ".gcp.vrt"
    g = gdal.Translate(gcp_vrt, src_path, format="VRT", outputSRS=wkt, GCPs=gcps)
    g = None

    out = out_base + ".tif"
    kw = dict(dstSRS=wkt, resampleAlg="cubic", dstNodata=0,
              creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
    if method == "tps" and n >= 4:
        kw["tps"] = True                 # TPS solo con 4+ (evita degenerado)
    else:
        kw["polynomialOrder"] = 1 if n < 6 else 2
    gdal.Warp(out, gcp_vrt, **kw)

    # el .tif es autocontenido; el VRT intermedio ya no hace falta
    try:
        os.remove(gcp_vrt)
    except OSError:
        logging.getLogger(__name__).debug("suppressed", exc_info=True)
    return out
