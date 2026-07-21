# -*- coding: utf-8 -*-
"""
Layout Rescaler Engine — escala todos los elementos del layout
proporcionalmente al nuevo tamaño de hoja, como ArcMap.

Mejoras v2:
- Snapshot del estado original antes de escalar
- Cálculo basado en posición relativa (ratio) para mayor precisión
- Soporta escala en cualquier dirección sin pérdida de posición

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
from qgis.core import (
    QgsLayoutItemLabel,
    QgsLayoutItemScaleBar,
    QgsLayoutItemLegend,
    QgsLayoutSize,
    QgsLayoutPoint,
    QgsUnitTypes,
)


def get_layout_size_mm(layout):
    """Retorna (ancho_mm, alto_mm) del layout actual."""
    page = layout.pageCollection().page(0)
    if page is None:
        return None, None
    size = page.pageSize()
    return size.width(), size.height()


def _to_mm(value, units):
    """Convierte un valor de unidades de layout a mm."""
    mm = QgsUnitTypes.LayoutUnit.LayoutMillimeters
    if units == mm:
        return value
    conversions = {
        QgsUnitTypes.LayoutUnit.LayoutCentimeters: 10.0,
        QgsUnitTypes.LayoutUnit.LayoutMeters:      1000.0,
        QgsUnitTypes.LayoutUnit.LayoutInches:      25.4,
        QgsUnitTypes.LayoutUnit.LayoutPoints:      0.352778,
        QgsUnitTypes.LayoutUnit.LayoutPicas:       4.23333,
        QgsUnitTypes.LayoutUnit.LayoutPixels:      0.264583,
    }
    return value * conversions.get(units, 1.0)


def _snapshot_items(layout, old_w, old_h):
    """
    Captura el estado de cada ítem como proporciones relativas al tamaño
    de la página. Esto permite escalar correctamente en cualquier dirección.
    """
    mm = QgsUnitTypes.LayoutUnit.LayoutMillimeters
    page = layout.pageCollection().page(0)
    snapshots = []

    for item in layout.items():
        if item == page or not hasattr(item, 'positionWithUnits'):
            continue
        try:
            pos = item.positionWithUnits()
            sz  = item.sizeWithUnits()
            x_mm = _to_mm(pos.x(), pos.units())
            y_mm = _to_mm(pos.y(), pos.units())
            w_mm = _to_mm(sz.width(),  sz.units())
            h_mm = _to_mm(sz.height(), sz.units())

            # Fuente actual si es etiqueta
            font_size = None
            if isinstance(item, QgsLayoutItemLabel):
                try:
                    font_size = item.textFormat().size()
                except Exception:
                    logging.getLogger(__name__).debug("suppressed", exc_info=True)
            elif isinstance(item, QgsLayoutItemScaleBar):
                try:
                    font_size = item.textFormat().size()
                except Exception:
                    logging.getLogger(__name__).debug("suppressed", exc_info=True)
            elif isinstance(item, QgsLayoutItemLegend):
                try:
                    font_size = item.titleTextFormat().size()
                except Exception:
                    logging.getLogger(__name__).debug("suppressed", exc_info=True)

            snapshots.append({
                "item":      item,
                # Proporciones relativas al tamaño de página
                "rx":        x_mm / old_w,
                "ry":        y_mm / old_h,
                "rw":        w_mm / old_w,
                "rh":        h_mm / old_h,
                "font_size": font_size,
            })
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    return snapshots


def rescale_layout(layout, new_width_mm, new_height_mm, scale_fonts=True):
    """
    Reescala todos los elementos del layout proporcionalmente.
    Usa proporciones relativas para máxima precisión en cualquier dirección.
    """
    old_w, old_h = get_layout_size_mm(layout)
    if old_w is None or old_w == 0 or old_h == 0:
        raise ValueError("No se pudo leer el tamaño actual del layout.")

    mm = QgsUnitTypes.LayoutUnit.LayoutMillimeters
    f_avg = ((new_width_mm / old_w) + (new_height_mm / old_h)) / 2.0

    stats = {"items_procesados": 0, "errores": 0, "detalles": []}

    # ── 1. Capturar snapshot ANTES de cambiar la página ──────────────
    snapshots = _snapshot_items(layout, old_w, old_h)

    # ── 2. Cambiar tamaño de la página ───────────────────────────────
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(new_width_mm, new_height_mm, mm))

    # ── 3. Aplicar posiciones/tamaños desde el snapshot ──────────────
    for snap in snapshots:
        item = snap["item"]
        try:
            new_x = snap["rx"] * new_width_mm
            new_y = snap["ry"] * new_height_mm
            new_w = snap["rw"] * new_width_mm
            new_h = snap["rh"] * new_height_mm

            # Mínimo de 1mm para no perder elementos
            new_w = max(1.0, new_w)
            new_h = max(1.0, new_h)

            item.attemptMove(QgsLayoutPoint(new_x, new_y, mm))
            item.attemptResize(QgsLayoutSize(new_w, new_h, mm))

            # Escalar fuente
            if scale_fonts and snap["font_size"] and snap["font_size"] > 0:
                new_font_size = max(4.0, round(snap["font_size"] * f_avg, 2))
                _apply_font_size(item, new_font_size)

            stats["items_procesados"] += 1

        except Exception as e:
            stats["errores"] += 1
            stats["detalles"].append(f"{type(item).__name__}: {e}")

    # ── 4. Refrescar ─────────────────────────────────────────────────
    layout.refresh()

    return stats, old_w, old_h


def _apply_font_size(item, size):
    """Aplica el tamaño de fuente según el tipo de ítem."""
    try:
        if isinstance(item, (QgsLayoutItemLabel, QgsLayoutItemScaleBar)):
            tf = item.textFormat()
            tf.setSize(size)
            item.setTextFormat(tf)
        elif isinstance(item, QgsLayoutItemLegend):
            tf = item.titleTextFormat()
            tf.setSize(size)
            item.setTitleTextFormat(tf)
    except Exception:
        logging.getLogger(__name__).debug("suppressed", exc_info=True)


# ── Tamaños estándar predefinidos ────────────────────────────────────────────
PAPER_SIZES = {
    "A0": (1189, 841),
    "A1": (841,  594),
    "A2": (594,  420),
    "A3": (420,  297),
    "A4": (297,  210),
    "A5": (210,  148),
    "Carta / Letter": (279.4, 215.9),
    "Legal":          (355.6, 215.9),
    "Tabloide / B":   (431.8, 279.4),
}
