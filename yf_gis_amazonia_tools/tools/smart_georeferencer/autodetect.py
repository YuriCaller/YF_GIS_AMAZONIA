"""
autodetect.py — Puente QGIS <-> OpenCV para auto-detección de GCPs.

Renderiza el ráster de referencia (una capa georreferenciada o el basemap visible)
sobre el extent actual, lo empareja con la imagen de dron vía gcp_matcher, y
escribe los GCPs resultantes en el GeorefCanvasItem.
"""
import numpy as np

from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QImage
from qgis.core import (QgsMapSettings, QgsMapRendererParallelJob,
                       QgsRectangle, QgsCoordinateReferenceSystem)

from . import gcp_matcher as gm


def qimage_to_cv(qimg):
    """QImage -> array BGR (uint8) para OpenCV."""
    img = qimg.convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    ptr = img.constBits(); ptr.setsize(h * w * 3)
    arr = np.frombuffer(ptr, np.uint8).reshape(h, w, 3).copy()  # RGB
    return arr[:, :, ::-1].copy()                               # -> BGR


def render_reference(canvas, layers, extent, size_px=1200):
    """Renderiza las capas dadas sobre `extent` a una QImage. Devuelve
    (qimage, geotransform_GDAL). El geotransform permite px-ref -> coords mapa."""
    ext = QgsRectangle(extent)
    ar = ext.height() / ext.width() if ext.width() else 1.0
    W = size_px
    H = max(1, int(round(size_px * ar)))

    ms = QgsMapSettings()
    ms.setLayers(layers)
    ms.setExtent(ext)
    ms.setOutputSize(QSize(W, H))
    ms.setDestinationCrs(canvas.mapSettings().destinationCrs())
    ms.setBackgroundColor(canvas.canvasColor())

    job = QgsMapRendererParallelJob(ms)
    job.start(); job.waitForFinished()
    qimg = job.renderedImage()

    # geotransform estilo GDAL a partir del extent renderizado
    gt = [ext.xMinimum(), ext.width() / W, 0.0,
          ext.yMaximum(), 0.0, -ext.height() / H]
    return qimg, gt


def auto_detect(item, canvas, ref_layers, detector="SIFT",
                max_gcps=40, size_px=1200):
    """Detecta GCPs entre la imagen del item y las capas de referencia.
    Devuelve el dict de diagnóstico de gcp_matcher (con .ok y .msg)."""
    drone_cv = qimage_to_cv(item.image)
    ref_qimg, gt = render_reference(canvas, ref_layers, canvas.extent(), size_px)
    ref_cv = qimage_to_cv(ref_qimg)

    res = gm.auto_detect_gcps(drone_cv, ref_cv, detector=detector,
                              max_gcps=max_gcps)
    if not res.get("ok"):
        return res

    map_coords = gm.ref_px_to_map(res["ref"], gt)   # px referencia -> coords mapa
    item.set_gcps(res["src"], map_coords)            # ETAPA 1: re-warp
    res["map_coords"] = map_coords
    return res
