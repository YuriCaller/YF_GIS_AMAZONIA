# -*- coding: utf-8 -*-
"""
Smart Labels Engine — aplica estilos de etiqueta técnicos
a cualquier capa vectorial existente.

Reutiliza la lógica probada del segmentador y polygon_creator,
extendiéndola para cualquier capa (no solo las creadas por YF Tools).

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
from qgis.PyQt.QtGui import QFont, QColor
from qgis.core import (
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
    Qgis,
)
from ...core.qt_compat import QVariant_Int, QVariant_Double, QVariant_String


# ─────────────────────────────────────────────────────────────────────────────
# Estilos predefinidos
# ─────────────────────────────────────────────────────────────────────────────

ESTILOS_POLIGONO = {
    "tecnico": {
        "nombre":      "Técnico — Área + Perímetro",
        "descripcion": "Área georeferenciada / Área: X ha / Perímetro: X m",
        "color":       QColor(255, 52, 11),   # rojo técnico YF
        "size":        9,
        "bold":        True,
    },
    "simple_area": {
        "nombre":      "Simple — Solo área",
        "descripcion": "Área: X ha",
        "color":       QColor(30, 100, 200),
        "size":        9,
        "bold":        False,
    },
    "catastral": {
        "nombre":      "Catastral — Área + Perímetro + Nombre",
        "descripcion": "Nombre del predio / Área: X ha / Perímetro: X m",
        "color":       QColor(0, 60, 130),
        "size":        8,
        "bold":        True,
    },
    "forestal": {
        "nombre":      "Forestal — Área en ha",
        "descripcion": "Área de estudio / X.XX ha",
        "color":       QColor(20, 120, 40),
        "size":        9,
        "bold":        True,
    },
}

ESTILOS_LINEA = {
    "distancia_azimut": {
        "nombre":      "Distancia + Azimut",
        "descripcion": "L=145.67 m / Az=324.15°",
        "color":       QColor(0, 0, 0),
        "size":        7,
        "bold":        False,
    },
    "solo_distancia": {
        "nombre":      "Solo distancia (m)",
        "descripcion": "145.67 m",
        "color":       QColor(0, 0, 180),
        "size":        8,
        "bold":        False,
    },
    "solo_azimut": {
        "nombre":      "Solo azimut (°)",
        "descripcion": "324.15°",
        "color":       QColor(150, 0, 0),
        "size":        7,
        "bold":        False,
    },
}

ESTILOS_PUNTO = {
    "vertice": {
        "nombre":      "Vértice — V01, V02...",
        "descripcion": "V-01, V-02, V-03...",
        "color":       QColor(0, 0, 255),
        "size":        9,
        "bold":        True,
    },
    "coordenadas": {
        "nombre":      "Coordenadas X, Y",
        "descripcion": "353500.12 / 8355500.34",
        "color":       QColor(0, 80, 160),
        "size":        7,
        "bold":        False,
    },
    "nombre_campo": {
        "nombre":      "Nombre del campo",
        "descripcion": "Muestra el primer campo de texto",
        "color":       QColor(60, 60, 60),
        "size":        9,
        "bold":        False,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Funciones auxiliares
# ─────────────────────────────────────────────────────────────────────────────

def _make_text_format(color, size, bold=False, buffer_size=0.8, 
                      scale_based=False, min_scale=1000, max_scale=50000):
    """
    Crea un QgsTextFormat con halo blanco.
    scale_based=True vincula el tamaño al rango de escala del mapa.
    """
    from qgis.core import QgsMapUnitScale, QgsUnitTypes
    fmt = QgsTextFormat()
    weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
    fmt.setFont(QFont("Arial", size, weight))
    fmt.setColor(color)
    fmt.setSize(size)
    # Unidades en puntos tipográficos (estable entre escalas)
    fmt.setSizeUnit(QgsUnitTypes.RenderUnit.RenderPoints)

    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(buffer_size)
    buf.setColor(QColor(255, 255, 255))
    fmt.setBuffer(buf)
    return fmt


def _set_placement_poligono(pal):
    """Placement centrado sobre el polígono."""
    try:
        pal.placement = Qgis.LabelPlacement.OverPoint
    except AttributeError:
        try:
            pal.placement = QgsPalLayerSettings.Placement.OverPoint
        except AttributeError:
            pal.placement = 0
    pal.centroidWhole = True


def _set_placement_linea(pal):
    """Placement sobre la línea con rotación automática."""
    try:
        pal.placement = QgsPalLayerSettings.Placement.Line
        pal.placementFlags = (
            QgsPalLayerSettings.OnLine | QgsPalLayerSettings.AboveLine
        )
    except AttributeError:
        pal.placement = 3
    # Rotación automática siguiendo la dirección del segmento
    try:
        pal.lineSettings().setPlacementFlags(
            Qgis.LabelLinePlacementFlags(
                Qgis.LabelLinePlacementFlag.AboveLine |
                Qgis.LabelLinePlacementFlag.OnLine
            )
        )
    except Exception:
        logging.getLogger(__name__).debug("suppressed", exc_info=True)


def _set_placement_punto(pal):
    """Placement arriba-derecha del punto."""
    try:
        pal.placement = QgsPalLayerSettings.Placement.AroundPoint
        pal.quadOffset = QgsPalLayerSettings.QuadrantPosition.QuadrantAboveRight
    except AttributeError:
        pal.placement = 1
    pal.dist = 1.0


def _primer_campo_texto(layer):
    """Retorna el nombre del primer campo de texto en la capa."""
    from qgis.PyQt.QtCore import QVariant
    for field in layer.fields():
        if field.type() in (QVariant_String,):
            return field.name()
    return None


def _campo_existe(layer, nombre):
    """Verifica si un campo existe en la capa."""
    return layer.fields().indexOf(nombre) >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Aplicadores por tipo de geometría
# ─────────────────────────────────────────────────────────────────────────────

def aplicar_etiqueta_poligono(layer, estilo_key, campo_nombre=None):
    """
    Aplica etiqueta técnica a una capa de polígonos.
    
    estilo_key: clave de ESTILOS_POLIGONO
    campo_nombre: nombre del campo para estilo 'catastral' (opcional)
    """
    estilo = ESTILOS_POLIGONO.get(estilo_key, ESTILOS_POLIGONO["tecnico"])
    pal = QgsPalLayerSettings()

    if estilo_key == "tecnico":
        # Detectar campos de área y perímetro disponibles
        campo_area  = next((c for c in ["area_ha", "AREA", "area", "Area"]
                           if _campo_existe(layer, c)), None)
        campo_perim = next((c for c in ["perim_m", "PERIMETRO", "perimetro", "Perimetro"]
                           if _campo_existe(layer, c)), None)

        if campo_area and campo_perim:
            pal.fieldName = (
                f"'ÁREA GEOREFERENCIADA' || '\\n' || "
                f"'Área: ' || round(\"{campo_area}\", 4) || ' ha.' || '\\n' || "
                f"'Perímetro: ' || round(\"{campo_perim}\", 2) || ' m.'"
            )
        elif campo_area:
            pal.fieldName = (
                f"'ÁREA GEOREFERENCIADA' || '\\n' || "
                f"'Área: ' || round(\"{campo_area}\", 4) || ' ha.'"
            )
        else:
            # Sin campos calculados — usar expresión geométrica directa
            pal.fieldName = (
                "'ÁREA GEOREFERENCIADA' || '\\n' || "
                "'Área: ' || round($area / 10000, 4) || ' ha.' || '\\n' || "
                "'Perímetro: ' || round($perimeter, 2) || ' m.'"
            )

    elif estilo_key == "simple_area":
        campo_area = next((c for c in ["area_ha", "AREA", "area", "Area"]
                          if _campo_existe(layer, c)), None)
        if campo_area:
            pal.fieldName = f"'Área: ' || round(\"{campo_area}\", 4) || ' ha.'"
        else:
            pal.fieldName = "'Área: ' || round($area / 10000, 4) || ' ha.'"

    elif estilo_key == "catastral":
        campo_area  = next((c for c in ["area_ha", "AREA", "area"]
                           if _campo_existe(layer, c)), None)
        campo_perim = next((c for c in ["perim_m", "PERIMETRO", "perimetro"]
                           if _campo_existe(layer, c)), None)
        nombre_expr = f'"{campo_nombre}"' if campo_nombre else "'SIN NOMBRE'"
        area_expr   = f'round("{campo_area}", 4)' if campo_area else "round($area/10000,4)"
        perim_expr  = f'round("{campo_perim}", 2)' if campo_perim else "round($perimeter,2)"
        pal.fieldName = (
            f"{nombre_expr} || '\\n' || "
            f"'Área: ' || {area_expr} || ' ha.' || '\\n' || "
            f"'Perímetro: ' || {perim_expr} || ' m.'"
        )

    elif estilo_key == "forestal":
        campo_area = next((c for c in ["area_ha", "AREA", "area"]
                          if _campo_existe(layer, c)), None)
        area_expr = f'round("{campo_area}", 2)' if campo_area else "round($area/10000,2)"
        pal.fieldName = (
            f"'ÁREA DE ESTUDIO' || '\\n' || "
            f"{area_expr} || ' ha.'"
        )

    pal.isExpression = True
    pal.setFormat(_make_text_format(estilo["color"], estilo["size"], estilo["bold"]))
    _set_placement_poligono(pal)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def aplicar_etiqueta_linea(layer, estilo_key):
    """Aplica etiqueta técnica a una capa de líneas."""
    estilo = ESTILOS_LINEA.get(estilo_key, ESTILOS_LINEA["distancia_azimut"])
    pal = QgsPalLayerSettings()

    # Detectar campos
    campo_long  = next((c for c in ["longitud_m", "longitud", "length", "LONGITUD"]
                       if _campo_existe(layer, c)), None)
    campo_azim  = next((c for c in ["azimut_gms", "azimut_dec", "azimut", "AZIMUT"]
                       if _campo_existe(layer, c)), None)

    if estilo_key == "distancia_azimut":
        if campo_long and campo_azim:
            pal.fieldName = (
                f"'L=' || round(\"{campo_long}\", 2) || ' m' || '\\n' || "
                f"'Az=' || \"{campo_azim}\""
            )
        elif campo_long:
            pal.fieldName = f"'L=' || round(\"{campo_long}\", 2) || ' m'"
        else:
            pal.fieldName = "'L=' || round($length, 2) || ' m'"

    elif estilo_key == "solo_distancia":
        if campo_long:
            pal.fieldName = f"round(\"{campo_long}\", 2) || ' m'"
        else:
            pal.fieldName = "round($length, 2) || ' m'"

    elif estilo_key == "solo_azimut":
        if campo_azim:
            pal.fieldName = f'"{campo_azim}"'
        else:
            pal.fieldName = "'Sin campo azimut'"

    pal.isExpression = True
    pal.setFormat(_make_text_format(estilo["color"], estilo["size"], estilo["bold"]))
    _set_placement_linea(pal)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def aplicar_etiqueta_punto(layer, estilo_key, campo_id=None):
    """Aplica etiqueta técnica a una capa de puntos."""
    estilo = ESTILOS_PUNTO.get(estilo_key, ESTILOS_PUNTO["vertice"])
    pal = QgsPalLayerSettings()

    if estilo_key == "vertice":
        # Detectar campo de ID de vértice
        campo = next((c for c in ["ID_Vertice", "id_vertice", "ID", "id", "nombre"]
                     if _campo_existe(layer, c)), None)
        if campo:
            pal.fieldName = f"'V-' || lpad(\"{campo}\", 2, '0')"
        else:
            pal.fieldName = "'V-' || lpad(@row_number, 2, '0')"

    elif estilo_key == "coordenadas":
        pal.fieldName = (
            "round($x, 2) || '\\n' || round($y, 2)"
        )

    elif estilo_key == "nombre_campo":
        campo_txt = campo_id or _primer_campo_texto(layer)
        if campo_txt:
            pal.fieldName = f'"{campo_txt}"'
        else:
            pal.fieldName = "'Sin campo texto'"

    pal.isExpression = True
    pal.setFormat(_make_text_format(estilo["color"], estilo["size"], estilo["bold"]))
    _set_placement_punto(pal)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def quitar_etiquetas(layer):
    """Desactiva las etiquetas de la capa."""
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()
