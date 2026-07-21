# -*- coding: utf-8 -*-
"""
Title Block Engine — Cajetín único "Predio Agrícola".
Modelo fiel al cajetín de producción de gis-amazonia.pe:

  ┌──────────────────────────────────────────────┬─────────┐
  │  MAPA PERIMETRICO DEL PREDIO AGRICOLA        │         │
  ├──────────────────────────────────────────────┤ MAPA 01 │
  │  PROPIETARIO : ...                           │         │
  ├──────────────────────────────┬───────────────┤ [Norte] │
  │ PROYECTO: ...                │ DNI: ...      │         │
  ├──────────────┬───────────────┴───────────────┤         │
  │ Datum/Proy/  │ Elaboración/Fecha/Parcela/    │         │
  │ Unid/Centr.  │ Código matriz/Partida/Área    │         │
  ├──────────────┴───────────────────────────────┴─────────┤
  │ Fuente : ...                                            │
  └─────────────────────────────────────────────────────────┘

Textos dinámicos con expresiones QGIS en etiquetas HTML
(fecha, datum, proyección, unidades, centroide del mapa).
Todos los elementos se agrupan al generarse.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsLayoutItemLabel, QgsLayoutItemShape, QgsLayoutItemPicture,
    QgsLayoutItemMap, QgsLayoutItemGroup,
    QgsLayoutSize, QgsLayoutPoint, QgsUnitTypes,
    QgsFillSymbol, QgsSimpleFillSymbolLayer, QgsProject,
)

# ── Compatibilidad Qt5/Qt6 y QGIS 3.x/4.x ───────────────────────────────────
MM = getattr(getattr(QgsUnitTypes, 'LayoutUnit', QgsUnitTypes),
             'LayoutMillimeters',
             getattr(QgsUnitTypes, 'LayoutMillimeters', None))

_MODE_HTML = getattr(getattr(QgsLayoutItemLabel, 'Mode', QgsLayoutItemLabel),
                     'ModeHtml', getattr(QgsLayoutItemLabel, 'ModeHtml', 1))
_MODE_FONT = getattr(getattr(QgsLayoutItemLabel, 'Mode', QgsLayoutItemLabel),
                     'ModeFont', getattr(QgsLayoutItemLabel, 'ModeFont', 0))
_ZOOM_RESIZE = getattr(getattr(QgsLayoutItemPicture, 'ResizeMode',
                               QgsLayoutItemPicture),
                       'ZoomResizeFrame',
                       getattr(QgsLayoutItemPicture, 'ZoomResizeFrame', 3))


# ── Plantilla única ──────────────────────────────────────────────────────────
# Se conserva el dict por compatibilidad con los llamadores existentes
# (combo del diálogo, get_plantilla), pero solo hay un modelo.

PLANTILLAS_CAJETIN = {
    "predio_agricola": {
        "nombre":      "Predio Agrícola",
        "descripcion": "Modelo oficial gis-amazonia.pe — medidas del plano real",
        # Medidas del cajetín de producción (FRACCIONAMIENTO.pdf, A3):
        "ancho": 121.5,
        "alto":  47.8,     # marco; la Fuente va fuera, debajo (+~5 mm)
        "C_HEADER": "#175339",   # verde exacto medido del PDF
        "C_BORDE":  "#1a1a1a",
        "C_TEXTO":  "#000000",
        "C_FONDO":  "#ffffff",
    },
}

GROSOR_BORDE = 0.35   # mm — borde de cada caja, como el modelo


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de dibujo
# ─────────────────────────────────────────────────────────────────────────────

def _rect(layout, x, y, w, h, fill, stroke=None, sw=GROSOR_BORDE):
    item = QgsLayoutItemShape(layout)
    layout.addLayoutItem(item)
    try:
        item.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
    except AttributeError:
        item.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
    item.attemptMove(QgsLayoutPoint(x, y, MM))
    item.attemptResize(QgsLayoutSize(w, h, MM))
    sym = QgsFillSymbol()
    sl = QgsSimpleFillSymbolLayer()
    sl.setFillColor(QColor(fill))
    sl.setStrokeColor(QColor(stroke or fill))
    sl.setStrokeWidth(sw if stroke else 0)
    sym.changeSymbolLayer(0, sl)
    item.setSymbol(sym)
    item.setFrameEnabled(False)
    item.setBackgroundEnabled(False)
    return item


def _lbl(layout, text, x, y, w, h, size=7, bold=False, italic=False,
         color="#000000", halign=Qt.AlignmentFlag.AlignLeft, html=True,
         valign=Qt.AlignmentFlag.AlignVCenter, familia="Arial"):
    item = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, MM))
    item.attemptResize(QgsLayoutSize(w, h, MM))
    font = QFont(familia, int(size))
    font.setBold(bold)
    font.setItalic(italic)
    item.setFont(font)
    item.setFontColor(QColor(color))
    try:
        item.setHAlign(halign)
        item.setVAlign(valign)
    except Exception:
        logging.getLogger(__name__).debug("suppressed", exc_info=True)
    item.setMarginX(1.2)
    item.setMarginY(0.3)
    item.setMode(_MODE_HTML if html else _MODE_FONT)
    item.setText(text)
    item.setBackgroundEnabled(False)
    item.setFrameEnabled(False)
    return item


def _norte(layout, x, y, w, h):
    item = QgsLayoutItemPicture(layout)
    layout.addLayoutItem(item)
    for path in [":/images/north_arrows/NorthArrow_11.svg",
                 ":/images/north_arrows/NorthArrow_02.svg",
                 ":/images/north_arrows/NorthArrow_01.svg"]:
        item.setPicturePath(path)
        if item.picturePath():
            break
    item.attemptMove(QgsLayoutPoint(x, y, MM))
    item.attemptResize(QgsLayoutSize(w, h, MM))
    item.setFrameEnabled(False)
    item.setBackgroundEnabled(False)
    item.setResizeMode(_ZOOM_RESIZE)
    return item


def _var(nombre, fallback=""):
    try:
        val = QgsProject.instance().variable(nombre)
        return val if val else fallback
    except Exception:
        return fallback


def _asegurar_mapa_referencia(layout):
    """Las expresiones @map_extent_center y @map_scale de las etiquetas
    necesitan un mapa de referencia. Si el layout no tiene uno, se asigna
    el QgsLayoutItemMap más grande. Devuelve True si hay mapa disponible."""
    try:
        if layout.referenceMap() is not None:
            return True
        mapas = [it for it in layout.items()
                 if isinstance(it, QgsLayoutItemMap)]
        if not mapas:
            return False
        principal = max(
            mapas, key=lambda m: m.sizeWithUnits().width() *
                                 m.sizeWithUnits().height())
        layout.setReferenceMap(principal)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Expresiones dinámicas (evaluadas en vivo por QGIS en la etiqueta)
# ─────────────────────────────────────────────────────────────────────────────

EXPR_FECHA      = "[% format_date(now(),'dd/MM/yyyy') %]"
EXPR_DATUM      = "[% trim(regexp_substr(@project_crs_description, '^([^/]+)')) %]"
EXPR_PROYECCION = "[% trim(regexp_substr(@project_crs_description, '/(.*)$')) %]"
EXPR_UNIDADES   = ("[% if(@project_distance_units = 'meters', 'Metros', "
                   "title(@project_distance_units)) %]")
EXPR_CENT_X     = "[% format_number(x(@map_extent_center), 4) %]"
EXPR_CENT_Y     = "[% format_number(y(@map_extent_center), 4) %]"


def _fila_html(etiqueta, valor):
    """Formato exacto del modelo real: <b>Etiqueta : </b> valor."""
    return "<b>{} : </b>{}".format(etiqueta, valor)


# ─────────────────────────────────────────────────────────────────────────────
# Generador del cajetín Predio Agrícola
# ─────────────────────────────────────────────────────────────────────────────

def _gen_predio_agricola(layout, x0, y0, datos, plt):
    """Anatomía medida del cajetín real (proporciones del PDF de producción):
      barra título 7.1/47.8 · propietario 11.8 (celda DNI 22% der.)
      proyecto 7.0 · info 18.5 en 2 columnas (43%/57% del área izq.)
      escudo/norte: columna derecha 22% ocupando proyecto+info
      Fuente: texto pequeño FUERA del marco, debajo."""
    W = float(datos.get("ancho_mm") or plt["ancho"])
    esc = W / 121.5                       # factor respecto al modelo real
    H  = 47.8 * esc
    CH, CB, CT, CF = plt["C_HEADER"], plt["C_BORDE"], plt["C_TEXTO"], plt["C_FONDO"]

    items = []

    def R(x, y, w, h, fill, stroke=CB):
        it = _rect(layout, x, y, w, h, fill, stroke)
        items.append(it); return it

    def L(text, x, y, w, h, **kw):
        it = _lbl(layout, text, x, y, w, h, **kw)
        items.append(it); return it

    hay_mapa = _asegurar_mapa_referencia(layout)

    # Alturas y anchos escalados (medidas reales en mm sobre 121.5)
    h_tit, h_pro, h_pd, h_inf = (7.1*esc, 11.8*esc, 7.0*esc, 18.5*esc)
    w_dni  = 26.6 * esc                   # celda DNI / columna escudo
    w_izq  = W - w_dni
    w_col1 = 39.7 * esc
    w_col2 = w_izq - w_col1
    f_txt  = max(5.0, 6.5 * esc)          # tamaño base de texto
    f_tit  = max(7.0, 9.0 * esc)

    # ── Marco general ──
    R(x0, y0, W, H, CF)

    # ── Barra de título (verde, ancho completo) ──
    R(x0, y0, W, h_tit, CH)
    titulo = datos.get("titulo") or "PLANO PERIMETRICO DEL PREDIO AGRICOLA"
    L(titulo, x0, y0, W, h_tit, size=f_tit, bold=True, italic=True,
      color="#ffffff", halign=Qt.AlignmentFlag.AlignCenter, html=False)

    # ── PROPIETARIO | DNI ──
    y = y0 + h_tit
    R(x0, y, w_izq, h_pro, CF)
    R(x0 + w_izq, y, w_dni, h_pro, CF)
    L("<i><b>PROPIETARIO : {}</b></i>".format(datos.get("propietario", "")),
      x0, y, w_izq, h_pro, size=f_txt + 1.5, color=CT,
      halign=Qt.AlignmentFlag.AlignCenter)
    L("<b>DNI:</b><br>{}".format(datos.get("dni", "")),
      x0 + w_izq, y, w_dni, h_pro, size=f_txt + 1, color=CT,
      halign=Qt.AlignmentFlag.AlignCenter)

    # ── PROYECTO (izq.) + escudo/norte (der., abarca proyecto+info) ──
    y += h_pro
    R(x0, y, w_izq, h_pd, CF)
    R(x0 + w_izq, y, w_dni, h_pd + h_inf, CF)
    L("<b>PROYECTO: {}</b>".format(datos.get("proyecto", "")),
      x0, y, w_izq, h_pd, size=f_txt + 0.5, color=CT)
    lado_n = min(w_dni, h_pd + h_inf) - 4.0 * esc
    nor = _norte(layout,
                 x0 + w_izq + (w_dni - lado_n) / 2.0,
                 y + (h_pd + h_inf - lado_n) / 2.0,
                 lado_n, lado_n)
    items.append(nor)

    # ── Bloque de información en dos columnas ──
    y += h_pd
    R(x0, y, w_col1, h_inf, CF)
    R(x0 + w_col1, y, w_col2, h_inf, CF)

    cent_x = EXPR_CENT_X if hay_mapa else "-----"
    cent_y = EXPR_CENT_Y if hay_mapa else "-----"
    col1 = "<br>".join([
        _fila_html("Datum",       datos.get("datum")      or EXPR_DATUM),
        _fila_html("Proyección",  datos.get("proyeccion") or EXPR_PROYECCION),
        _fila_html("Unidades",    datos.get("unidades")   or EXPR_UNIDADES),
        _fila_html("Centroide X", cent_x),
        _fila_html("Centroide Y", cent_y),
    ])
    L(col1, x0, y + 0.3, w_col1, h_inf - 0.6, size=f_txt, color=CT,
      valign=Qt.AlignmentFlag.AlignTop)

    col2 = "<br>".join([
        _fila_html("Elaboracion",
                   datos.get("elaborado")
                   or _var("tucsa_elaborado", "Ing. Yuri F. Caller Córdova")),
        _fila_html("Fecha", datos.get("fecha") or EXPR_FECHA),
        _fila_html("Nombre de la Parcela", datos.get("parcela", "")),
        _fila_html("Codigo catastral",
                   datos.get("codigo_matriz") or "------"),
        _fila_html("Partida registral",
                   datos.get("partida") or "no aplica"),
        _fila_html("Area del predio",
                   datos.get("area_matriz") or "ninguna"),
    ])
    L(col2, x0 + w_col1, y + 0.3, w_col2, h_inf - 0.6,
      size=f_txt, color=CT, valign=Qt.AlignmentFlag.AlignTop)

    # ── Fuente: FUERA del marco, texto pequeño ──
    fuente = datos.get("fuente", "")
    if fuente:
        L("<b>Fuente : </b>{}".format(fuente), x0, y0 + H + 0.5, W, 5.0 * esc,
          size=max(4.5, 5.0 * esc), color=CT,
          valign=Qt.AlignmentFlag.AlignTop)

    # ── Agrupar ──
    grupo = None
    try:
        grupo = QgsLayoutItemGroup(layout)
        layout.addLayoutItem(grupo)
        for it in items:
            grupo.addItem(it)
        try:
            grupo.setId("YF_Cajetin_PredioAgricola")
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
    except Exception:
        grupo = None

    layout.refresh()
    return items, grupo


# ─────────────────────────────────────────────────────────────────────────────

def generar_cajetin(layout, plantilla_key, pos_x, pos_y,
                    datos, logo_path=None, grupo_nombre="YF_Cajetin"):
    """Genera el cajetín Predio Agrícola en el layout.
    plantilla_key y logo_path se aceptan por compatibilidad; solo existe
    un modelo y no usa logo (lleva rosa náutica).
    Devuelve la lista de items generados (agrupados en el layout)."""
    plt = PLANTILLAS_CAJETIN["predio_agricola"]
    items, _grupo = _gen_predio_agricola(layout, pos_x, pos_y, datos or {}, plt)
    return items


def get_variables_proyecto():
    return {
        "elaborado": _var("tucsa_elaborado",
                          "Ing. Yuri F. Caller Córdova"),
        "empresa":   _var("tucsa_empresa",
                          "TUCSA — Training Universal Company SAC"),
        "fecha":     EXPR_FECHA,
        "datum":     EXPR_DATUM,
    }
