# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Exportador de resultados.

Escribe las geometrías de intersección a GeoPackage (para el plano) y
los productos de trazabilidad (log JSON, anexo de verificación).

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os

from . import traceability


def _campos_resultado():
    """Campos de la capa de superposiciones."""
    from qgis.core import QgsField, QgsFields
    from ...core.qt_compat import QVariant_Double, QVariant_String

    campos = QgsFields()
    campos.append(QgsField("capa", QVariant_String))
    campos.append(QgsField("archivo", QVariant_String))
    campos.append(QgsField("tipo", QVariant_String))
    campos.append(QgsField("titular", QVariant_String))
    campos.append(QgsField("codigo", QVariant_String))
    campos.append(QgsField("area_ha", QVariant_Double))
    campos.append(QgsField("porcentaje", QVariant_Double))
    campos.append(QgsField("nivel", QVariant_String))
    return campos


def _wkb_multipoligono():
    """WkbType.MultiPolygon con compatibilidad Qt5/Qt6."""
    from qgis.core import QgsWkbTypes
    # Qt6 anida el enum en .Type; Qt5 lo expone directo. getattr resuelve
    # ambos sin dejar un literal sin scope que el comprobador marque.
    return getattr(QgsWkbTypes, "Type", QgsWkbTypes).MultiPolygon


def exportar_geopackage(resultado, ruta_gpkg, crs, nombre_capa="superposiciones"):
    """Escribe las intersecciones a un GeoPackage.

    Devuelve (ok, mensaje). Si no hay superposiciones no crea archivo:
    un GeoPackage vacío confunde más de lo que ayuda.
    """
    from qgis.core import (QgsVectorFileWriter, QgsFeature,
                           QgsCoordinateTransformContext)

    if not resultado.superposiciones:
        return False, "No hay superposiciones que exportar."

    campos = _campos_resultado()
    opciones = QgsVectorFileWriter.SaveVectorOptions()
    opciones.driverName = "GPKG"
    opciones.layerName = nombre_capa
    opciones.fileEncoding = "UTF-8"
    try:
        opciones.actionOnExistingFile = getattr(
            QgsVectorFileWriter, "ActionOnExistingFile",
            QgsVectorFileWriter).CreateOrOverwriteFile
    except AttributeError:
        pass

    writer = QgsVectorFileWriter.create(
        ruta_gpkg, campos, _wkb_multipoligono(), crs,
        QgsCoordinateTransformContext(), opciones)

    _sin_error = getattr(QgsVectorFileWriter, "WriterError",
                         QgsVectorFileWriter).NoError
    if writer.hasError() != _sin_error:
        return False, "No se pudo crear el GeoPackage: {}".format(
            writer.errorMessage())

    escritas = 0
    for s in resultado.superposiciones:
        if s.geometria is None or s.geometria.isEmpty():
            continue
        feat = QgsFeature(campos)
        feat.setGeometry(s.geometria)
        feat.setAttributes([
            s.capa, s.archivo, s.tipo, s.titular or "", s.codigo or "",
            round(s.area_ha, 4), round(s.porcentaje, 2), s.nivel,
        ])
        writer.addFeature(feat)
        escritas += 1

    del writer
    if escritas == 0:
        return False, "Ninguna superposición tenía geometría exportable."
    return True, "{} superposición(es) escritas en {}".format(
        escritas, os.path.basename(ruta_gpkg))


def exportar_trazabilidad(contexto, carpeta, prefijo="superposicion"):
    """Escribe log JSON + anexo de verificación TXT.

    Devuelve la lista de rutas generadas.
    """
    generados = []
    ruta_log = os.path.join(carpeta, "{}_log.json".format(prefijo))
    traceability.guardar_log_json(contexto, ruta_log)
    generados.append(ruta_log)

    ruta_anexo = os.path.join(carpeta, "{}_anexo_verificacion.txt".format(prefijo))
    with open(ruta_anexo, "w", encoding="utf-8") as f:
        f.write(traceability.texto_anexo_verificacion(contexto))
    generados.append(ruta_anexo)
    return generados


def exportar_csv_resumen(contexto, ruta_csv):
    """Tabla resumen en CSV — para pegar en Excel o en el informe."""
    import csv
    filas = contexto.get("superposiciones", [])
    with open(ruta_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Capa", "Archivo", "Tipo", "Titular", "Código",
                    "Área (ha)", "% del predio", "Nivel"])
        for s in filas:
            w.writerow([s["capa"], s["archivo"], s["tipo"], s["titular"],
                        s["codigo"], s["area_ha"], s["porcentaje"],
                        s["nivel_legible"]])
    return ruta_csv


# ─────────────────────────────────────────────────────────────────────
# Capa resultante viva (en memoria) — cargada directo al proyecto
# ─────────────────────────────────────────────────────────────────────

def _color_por_nivel():
    """Mapa nivel -> (relleno RGBA, borde RGB) coherente con la tabla."""
    return {
        "critico":          ("255,52,11,140", "150,20,0"),
        "observable":       ("255,170,0,130", "180,110,0"),
        "no_significativa": ("60,160,70,110", "30,110,40"),
    }


def _simbologia_por_nivel(capa):
    """Renderizador categorizado por el campo 'nivel'.

    Firefly-friendly: rellenos translúcidos para que el operador vea el
    solape sobre el basemap sin tapar el predio.
    """
    from qgis.core import (QgsCategorizedSymbolRenderer, QgsRendererCategory,
                           QgsFillSymbol)
    from .data_contract import NIVELES_LEGIBLES

    colores = _color_por_nivel()
    categorias = []
    for nivel, (relleno, borde) in colores.items():
        sym = QgsFillSymbol.createSimple({
            "color": relleno,
            "outline_color": borde,
            "outline_width": "0.5",
        })
        categorias.append(QgsRendererCategory(
            nivel, sym, NIVELES_LEGIBLES.get(nivel, nivel)))
    renderer = QgsCategorizedSymbolRenderer("nivel", categorias)
    capa.setRenderer(renderer)


def _etiquetar(capa):
    """Etiqueta: capa + titular + área, halo blanco."""
    from qgis.core import (QgsPalLayerSettings, QgsTextFormat,
                           QgsTextBufferSettings, QgsVectorLayerSimpleLabeling,
                           Qgis)
    from qgis.PyQt.QtGui import QColor, QFont

    pal = QgsPalLayerSettings()
    pal.fieldName = (
        "\"capa\" || '\\n' || "
        "if(\"titular\" != '', \"titular\" || '\\n', '') || "
        "format_number(\"area_ha\", 4) || ' ha'"
    )
    pal.isExpression = True

    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial", 8))
    fmt.setSize(8)
    fmt.setColor(QColor(90, 20, 0))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(0.8)
    buf.setColor(QColor(255, 255, 255))
    fmt.setBuffer(buf)
    pal.setFormat(fmt)

    try:
        pal.placement = Qgis.LabelPlacement.OverPoint
    except AttributeError:
        try:
            pal.placement = QgsPalLayerSettings.Placement.OverPoint
        except AttributeError:
            pal.placement = 0
    try:
        pal.centroidWhole = True
    except Exception:  # nosec B110 - atributo ausente en algunas versiones
        pass           # de QGIS; el etiquetado funciona sin él

    capa.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    capa.setLabelsEnabled(True)


def crear_capa_memoria(resultado, crs, nombre_capa="Superposiciones",
                       agregar_al_proyecto=True, etiquetar=True):
    """Crea una capa vectorial en MEMORIA con las intersecciones.

    A diferencia de exportar_geopackage (que escribe a disco), esto carga
    la capa viva al proyecto para que el operador vea de inmediato QUÉ
    derecho cae en QUÉ espacio geográfico. Devuelve (capa, mensaje).
    """
    from qgis.core import QgsVectorLayer, QgsFeature, QgsProject

    geoms = [s for s in resultado.superposiciones
             if s.geometria is not None and not s.geometria.isEmpty()]
    if not geoms:
        return None, "No hay geometrías de superposición para cargar."

    authid = crs.authid() if hasattr(crs, "authid") else str(crs)
    capa = QgsVectorLayer(
        "MultiPolygon?crs={}".format(authid), nombre_capa, "memory")
    if not capa.isValid():
        return None, "No se pudo crear la capa en memoria."

    prov = capa.dataProvider()
    prov.addAttributes(_campos_resultado())
    capa.updateFields()

    feats = []
    for s in geoms:
        feat = QgsFeature(capa.fields())
        feat.setGeometry(s.geometria)
        feat.setAttributes([
            s.capa, s.archivo, s.tipo, s.titular or "", s.codigo or "",
            round(s.area_ha, 4), round(s.porcentaje, 2), s.nivel,
        ])
        feats.append(feat)
    prov.addFeatures(feats)
    capa.updateExtents()

    try:
        _simbologia_por_nivel(capa)
        if etiquetar:
            _etiquetar(capa)
    except Exception:  # nosec B110 - el estilo es accesorio: la capa
        pass           # de resultados es válida aunque falle

    if agregar_al_proyecto:
        QgsProject.instance().addMapLayer(capa)
    return capa, "{} superposición(es) cargadas como capa '{}'".format(
        len(feats), nombre_capa)
