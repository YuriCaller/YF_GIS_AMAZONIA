"""
exporter.py — Export final a GeoTIFF georreferenciado.

El preview en pantalla usa la malla (rápido). El EXPORT usa GDAL a
resolución completa con los MISMOS GCPs (TPS o polinomial). Así el preview es
fluido y el resultado final tiene calidad cartográfica.
"""
from osgeo import gdal, osr


def _gcp_list(src_gcp, map_gcp):
    gcps = []
    for (px, py), (mx, my) in zip(src_gcp, map_gcp):
        # gdal.GCP(X, Y, Z, pixel/col, line/row)
        gcps.append(gdal.GCP(float(mx), float(my), 0.0, float(px), float(py)))
    return gcps


def export_geotiff(image_path, src_gcp, map_gcp, out_path, crs_authid,
                   method="tps", poly_order=2, resample="cubic"):
    """Warpa `image_path` a `out_path` (GeoTIFF) usando los GCPs.
    method: 'tps' (thin plate spline) o 'poly' (polinomial poly_order)."""
    src_ds = gdal.Open(image_path)
    if src_ds is None:
        raise IOError(f"GDAL no pudo abrir {image_path}")

    srs = osr.SpatialReference()
    srs.SetFromUserInput(crs_authid)            # p.ej. 'EPSG:32719' (UTM 19S)
    wkt = srs.ExportToWkt()

    gcps = _gcp_list(src_gcp, map_gcp)
    tmp = "/vsimem/_yf_gcp.vrt"
    gdal.Translate(tmp, src_ds, outputSRS=wkt, GCPs=gcps)

    warp_kw = dict(dstSRS=wkt, resampleAlg=resample,
                   dstNodata=0, multithread=True,
                   creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
    if method == "tps":
        warp_kw["tps"] = True
    else:
        warp_kw["polynomialOrder"] = int(poly_order)

    gdal.Warp(out_path, tmp, **warp_kw)
    gdal.Unlink(tmp)
    src_ds = None
    return out_path


def gcp_rms(src_gcp, map_gcp, method="tps", poly_order=1):
    """RMS de los residuales de los GCPs (control de calidad rápido).
    Para 'poly' orden 1 = afín; útil para detectar GCPs malos."""
    import numpy as np
    src = np.asarray(src_gcp, float); dst = np.asarray(map_gcp, float)
    if method != "tps" and len(src) >= 3:
        A = np.hstack([src, np.ones((len(src), 1))])
        M, *_ = np.linalg.lstsq(A, dst, rcond=None)
        pred = A @ M
        res = np.linalg.norm(pred - dst, axis=1)
        return float(np.sqrt((res ** 2).mean())), res
    return None, None
