# -*- coding: utf-8 -*-
"""
Smart Labels Engine — aplica estilos de etiqueta técnicos
a cualquier capa vectorial existente.

Reutiliza la lógica probada del segmentador y polygon_creator,
extendiéndola para cualquier capa (no solo las creadas por YF Tools).

v3.0.4-dev: unidades configurables (m²/ha/km², m/km) y método de
cálculo explícito (campo precalculado / planar / elipsoidal).

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


# ───────────────────────────────────────────────────────────────────────────
# Estilos predefinidos
# ───────────────────────────────────────────────────────────────────────────

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


# ───────────────────────────────────────────────────────────────────────────
# Unidades y métodos de cálculo (v3.0.4-dev)
# ───────────────────────────────────────────────────────────────────────────

UNIDADES_AREA = {
    "m2":  {"nombre": "m²",  "factor_m2": 1.0,      "dec": 2, "sufijo": " m²"},
    "ha":  {"nombre": "ha",  "factor_m2": 0.0001,   "dec": 4, "sufijo": " ha."},
    "km2": {"nombre": "km²", "factor_m2": 0.000001, "dec": 4, "sufijo": " km²"},
}

UNIDADES_LONGITUD = {
    "m":  {"nombre": "m",  "factor_m": 1.0,   "dec": 2, "sufijo": " m."},
    "km": {"nombre": "km", "factor_m": 0.001, "dec": 3, "sufijo": " km."},
}

METODOS_CALCULO = {
    "campo":      "Campo precalculado de la capa",
    "planar":     "Planar — plano de proyección (uso catastral)",
    "elipsoidal": "Elipsoidal — superficie del elipsoide (WGS84)",
}


def detectar_campos_medida(layer):
    """Detecta campos precalculados de área/perímetro/longitud (case-insensitive).

    Convención YF Tools: área en HECTÁREAS, perímetro/longitud en METROS.
    Retorna dict con los nombres reales de los campos o None.
    """
    reales = {f.name().lower(): f.name() for f in layer.fields()}

    def _busca(candidatos):
        return next((reales[c] for c in candidatos if c in reales), None)

    return {
        "area":  _busca(["area_ha", "area"]),
        "perim": _busca(["perim_m", "perimetro", "perim"]),
        "long":  _busca(["longitud_m", "longitud", "length", "long_m"]),
    }


def _resolver_metodo(metodo, tiene_campo):
    """'auto' → campo si existe, sino planar. Valida métodos explícitos."""
    if metodo == "auto":
        return "campo" if tiene_campo else "planar"
    if metodo == "campo" and not tiene_campo:
        return "planar"
    return metodo if metodo in METODOS_CALCULO else "planar"


def _medida_elipsoidal(crs_authid, feature, tipo):
    """Mide sobre el elipsoide WGS84 con QgsDistanceArea explícita.

    Retorna SIEMPRE metros / metros cuadrados. El CRS de la capa llega
    como argumento fijado en la expresión, sin depender del elipsoide
    ni de las unidades configuradas en el proyecto del usuario.
    """
    from qgis.core import (QgsDistanceArea, QgsProject,
                           QgsCoordinateReferenceSystem)
    if feature is None:
        return None
    geom = feature.geometry()
    if geom is None or geom.isEmpty():
        return None
    crs = None
    if crs_authid:
        crs = QgsCoordinateReferenceSystem(str(crs_authid))
    if crs is None or not crs.isValid():
        crs = QgsProject.instance().crs()
    da = QgsDistanceArea()
    da.setSourceCrs(crs, QgsProject.instance().transformContext())
    da.setEllipsoid("EPSG:7030")  # WGS 84
    if tipo == "area":
        return float(da.measureArea(geom))
    if tipo == "perimetro":
        return float(da.measurePerimeter(geom))
    return float(da.measureLength(geom))


def registrar_funciones_expresion():
    """Registra yf_area_elip / yf_perimetro_elip / yf_longitud_elip.

    Patrón seguro validado contra 3 crashes reales en QGIS 3.44 (Windows):

    1. NUNCA llamar QgsExpression.isFunctionName() ni unregisterFunction()
       desde código de plugin — segfault durante reloads de módulo
       (QgsExpression::functionIndex, ver stack trace 2026-07-22).
    2. Construir con register=False: en ese modo el decorador qgsfunction
       NO consulta isFunctionName internamente.
    3. CRÍTICO — mantener referencias Python vivas en qgis.utils:
       registerFunction() NO toma posesión del objeto; si el GC lo
       destruye, el registro C++ queda con punteros colgantes y cualquier
       operación posterior sobre expresiones produce access violation.
    4. Centinela en qgis.utils (sobrevive reloads): registro único por
       sesión de QGIS; los reloads del módulo saltan este bloque.
    """
    import qgis.utils as _qutils
    if getattr(_qutils, "_yf_expr_funcs_registered", False):
        return
    from qgis.core import QgsExpression, qgsfunction

    @qgsfunction(group="YF GIS Amazonia", usesgeometry=True, register=False)
    def yf_area_elip(crs_authid, feature, parent):
        """Área elipsoidal WGS84 en m². Uso: yf_area_elip('EPSG:32719')"""
        return _medida_elipsoidal(crs_authid, feature, "area")

    @qgsfunction(group="YF GIS Amazonia", usesgeometry=True, register=False)
    def yf_perimetro_elip(crs_authid, feature, parent):
        """Perímetro elipsoidal WGS84 en m. Uso: yf_perimetro_elip('EPSG:32719')"""
        return _medida_elipsoidal(crs_authid, feature, "perimetro")

    @qgsfunction(group="YF GIS Amazonia", usesgeometry=True, register=False)
    def yf_longitud_elip(crs_authid, feature, parent):
        """Longitud elipsoidal WGS84 en m. Uso: yf_longitud_elip('EPSG:32719')"""
        return _medida_elipsoidal(crs_authid, feature, "longitud")

    fobjs = (yf_area_elip, yf_perimetro_elip, yf_longitud_elip)
    for fobj in fobjs:
        QgsExpression.registerFunction(fobj)

    # Referencias persistentes: sin esto, el GC de Python destruye los
    # objetos y el registro C++ queda apuntando a memoria liberada.
    _qutils._yf_expr_funcs = fobjs
    _qutils._yf_expr_funcs_registered = True


try:
    registrar_funciones_expresion()
except Exception:
    logging.getLogger(__name__).warning(
        "Smart Labels: no se pudieron registrar funciones elipsoidales",
        exc_info=True,
    )


def expr_area(metodo, unidad, campo=None, crs_authid=None):
    """Construye (expresion_numerica, sufijo) para área en la unidad pedida.

    - campo:      campo precalculado, se asume en HECTÁREAS (convención YF).
    - planar:     area($geometry) — siempre sobre el plano del CRS de la capa.
    - elipsoidal: yf_area_elip('<crs>') — determinista, WGS84, en m².
    """
    u = UNIDADES_AREA.get(unidad, UNIDADES_AREA["ha"])
    if metodo == "campo" and campo:
        factor = 10000.0 * u["factor_m2"]  # ha → m² → unidad destino
        base = f'"{campo}"' if factor == 1.0 else f'("{campo}" * {factor:g})'
    else:
        if metodo == "elipsoidal":
            fn = f"yf_area_elip('{crs_authid or ''}')"
        else:
            fn = "area($geometry)"
        base = fn if u["factor_m2"] == 1.0 else f'({fn} * {u["factor_m2"]:g})'
    return f'round({base}, {u["dec"]})', u["sufijo"]


def expr_longitud(metodo, unidad, campo=None, es_perimetro=False,
                  crs_authid=None):
    """Construye (expresion_numerica, sufijo) para perímetro/longitud.

    Campo precalculado se asume en METROS (convención YF Tools).
    """
    u = UNIDADES_LONGITUD.get(unidad, UNIDADES_LONGITUD["m"])
    if metodo == "campo" and campo:
        base = (f'"{campo}"' if u["factor_m"] == 1.0
                else f'("{campo}" * {u["factor_m"]:g})')
    else:
        if metodo == "elipsoidal":
            nombre_fn = "yf_perimetro_elip" if es_perimetro else "yf_longitud_elip"
            fn = f"{nombre_fn}('{crs_authid or ''}')"
        else:
            fn = "perimeter($geometry)" if es_perimetro else "length($geometry)"
        base = fn if u["factor_m"] == 1.0 else f'({fn} * {u["factor_m"]:g})'
    return f'round({base}, {u["dec"]})', u["sufijo"]


# ───────────────────────────────────────────────────────────────────────────
# Funciones auxiliares
# ───────────────────────────────────────────────────────────────────────────

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


# ───────────────────────────────────────────────────────────────────────────
# Aplicadores por tipo de geometría
# ───────────────────────────────────────────────────────────────────────────

def aplicar_etiqueta_poligono(layer, estilo_key, campo_nombre=None,
                              unidad_area="ha", unidad_perim="m",
                              metodo="auto"):
    """
    Aplica etiqueta técnica a una capa de polígonos.

    estilo_key:   clave de ESTILOS_POLIGONO
    campo_nombre: campo para estilo 'catastral' (opcional)
    unidad_area:  'm2' | 'ha' | 'km2'
    unidad_perim: 'm' | 'km'
    metodo:       'auto' | 'campo' | 'planar' | 'elipsoidal'
                  auto = campo precalculado si existe, sino planar
    """
    estilo = ESTILOS_POLIGONO.get(estilo_key, ESTILOS_POLIGONO["tecnico"])
    pal = QgsPalLayerSettings()

    campos = detectar_campos_medida(layer)
    met = _resolver_metodo(metodo, bool(campos["area"]))

    crs_id = layer.crs().authid()
    a_num, a_suf = expr_area(met, unidad_area, campos["area"],
                             crs_authid=crs_id)
    p_num, p_suf = expr_longitud(met, unidad_perim, campos["perim"],
                                 es_perimetro=True, crs_authid=crs_id)

    if estilo_key == "tecnico":
        pal.fieldName = (
            f"'ÁREA GEOREFERENCIADA' || '\\n' || "
            f"'Área: ' || {a_num} || '{a_suf}' || '\\n' || "
            f"'Perímetro: ' || {p_num} || '{p_suf}'"
        )

    elif estilo_key == "simple_area":
        pal.fieldName = f"'Área: ' || {a_num} || '{a_suf}'"

    elif estilo_key == "catastral":
        nombre_expr = f'"{campo_nombre}"' if campo_nombre else "'SIN NOMBRE'"
        pal.fieldName = (
            f"{nombre_expr} || '\\n' || "
            f"'Área: ' || {a_num} || '{a_suf}' || '\\n' || "
            f"'Perímetro: ' || {p_num} || '{p_suf}'"
        )

    elif estilo_key == "forestal":
        pal.fieldName = (
            f"'ÁREA DE ESTUDIO' || '\\n' || "
            f"{a_num} || '{a_suf}'"
        )

    pal.isExpression = True
    pal.setFormat(_make_text_format(estilo["color"], estilo["size"], estilo["bold"]))
    _set_placement_poligono(pal)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def aplicar_etiqueta_linea(layer, estilo_key,
                           unidad_long="m", metodo="auto"):
    """Aplica etiqueta técnica a una capa de líneas.

    unidad_long: 'm' | 'km'
    metodo:      'auto' | 'campo' | 'planar' | 'elipsoidal'
    """
    estilo = ESTILOS_LINEA.get(estilo_key, ESTILOS_LINEA["distancia_azimut"])
    pal = QgsPalLayerSettings()

    campos = detectar_campos_medida(layer)
    campo_azim = next((c for c in ["azimut_gms", "azimut_dec", "azimut", "AZIMUT"]
                       if _campo_existe(layer, c)), None)

    met = _resolver_metodo(metodo, bool(campos["long"]))
    l_num, l_suf = expr_longitud(met, unidad_long, campos["long"],
                                 crs_authid=layer.crs().authid())
    l_suf_corto = l_suf.rstrip('.')  # estilo línea usa 'm' sin punto

    if estilo_key == "distancia_azimut":
        if campo_azim:
            pal.fieldName = (
                f"'L=' || {l_num} || '{l_suf_corto}' || '\\n' || "
                f"'Az=' || \"{campo_azim}\""
            )
        else:
            pal.fieldName = f"'L=' || {l_num} || '{l_suf_corto}'"

    elif estilo_key == "solo_distancia":
        pal.fieldName = f"{l_num} || '{l_suf_corto}'"

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
