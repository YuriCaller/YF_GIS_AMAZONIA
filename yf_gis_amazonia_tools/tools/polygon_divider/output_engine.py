# -*- coding: utf-8 -*-
"""
Polygon Divider — Motor de salida (capas resultantes + etiquetado).

Responsable de:
- Crear la capa resultado (GeoPackage en memoria → archivo, o capa de
  memoria si el usuario elige no guardar a disco todavía).
- Heredar todos los campos del polígono padre en cada fragmento.
- Añadir campos de control: fraccion, area_ha, porcentaje, fecha_division,
  poligono_padre_id.
- Generar el nombre de archivo según el campo base elegido por el
  usuario (Opción A acordada), con fallback seguro a ID+timestamp.
- Aplicar etiquetado automático por expresión QGIS (no como texto fijo).

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os
import re
import unicodedata
from datetime import datetime

from qgis.core import (
    QgsField,
    QgsFields,
    QgsFeature,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsProject,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

from ...core.logger import log_info, log_warning, log_error
from ...core.qt_compat import QVariant_Int, QVariant_Double, QVariant_String


# ─────────────────────────────────────────────────────────────────────
# Nombre de archivo / capa
# ─────────────────────────────────────────────────────────────────────

def _slugificar(texto: str) -> str:
    """Convierte un valor de campo en un nombre de archivo seguro."""
    if texto is None:
        return ""
    texto = str(texto).strip()
    # Quitar tildes
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Reemplazar espacios y caracteres no seguros
    texto = re.sub(r"[^\w\-]+", "_", texto, flags=re.UNICODE)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto.upper()


def generar_nombre_capa(feature, campo_base, sufijo_modo, fid_referencia):
    """
    Genera el nombre de la capa resultado según el campo base elegido
    por el usuario (Opción A). Si el campo no existe, está vacío o es
    nulo, cae a un nombre de respaldo con el ID de la feature + timestamp,
    para nunca fallar silenciosamente.
    """
    valor_base = None
    if campo_base and feature.fields().indexFromName(campo_base) != -1:
        valor_base = feature.attribute(campo_base)

    slug = _slugificar(valor_base) if valor_base not in (None, "") else ""

    if not slug:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        slug = f"POLIGONO_{fid_referencia}_{timestamp}"
        log_warning(
            f"Polygon Divider: el campo '{campo_base}' está vacío o no "
            f"existe en la feature {fid_referencia}. Usando nombre de "
            f"respaldo: {slug}"
        )

    return f"{slug}_{sufijo_modo}"


def sufijo_para_modo(modo, valor):
    """
    Construye el sufijo del nombre de capa según el modo de división.
    modo: 'area' | 'partes' | 'porcentaje'
    """
    if modo == "partes":
        return f"div_{int(valor)}p"
    if modo == "area":
        return f"div_area_{str(valor).replace('.', '_')}ha"
    if modo == "porcentaje":
        return "div_pct"
    return "div"


# ─────────────────────────────────────────────────────────────────────
# Construcción de capa resultado
# ─────────────────────────────────────────────────────────────────────

def construir_campos_resultado(campos_originales: QgsFields) -> QgsFields:
    """
    Construye el esquema de campos de la capa resultado: todos los
    campos originales heredados + los campos de control nuevos.

    Excluye explícitamente 'fid' (y variantes de nombre equivalentes):
    es el identificador de fila que GDAL/OGR trata como clave primaria
    en GeoPackage. Si se hereda el mismo valor de fid en múltiples
    fragmentos (todos provienen del mismo polígono padre), la escritura
    a GeoPackage falla con "UNIQUE constraint failed" y solo se guarda
    1 de N fragmentos. GeoPackage genera su propio fid autoincremental
    al insertar, así que no hay pérdida real de información.
    """
    CAMPOS_EXCLUIDOS = {"fid", "ogc_fid", "objectid"}

    nuevos = QgsFields()
    for campo in campos_originales:
        if campo.name().lower() not in CAMPOS_EXCLUIDOS:
            nuevos.append(campo)

    extras = [
        ("fraccion",       QVariant_Int),
        ("area_ha",        QVariant_Double),
        ("porcentaje",     QVariant_Double),
        ("area_padre_ha",  QVariant_Double),   # área planar del polígono padre al momento de dividir
        ("fecha_division", QVariant_String),
        ("poligono_padre_id", QVariant_String),
    ]

    for nombre, tipo in extras:
        if nuevos.indexFromName(nombre) == -1:
            nuevos.append(QgsField(nombre, tipo))

    return nuevos


def crear_capa_resultado(nombre_capa, crs, campos_resultado, geom_type_wkb=QgsWkbTypes.Type.Polygon):
    """
    Crea una QgsVectorLayer de memoria con el esquema dado. La capa de
    memoria luego puede guardarse a GeoPackage explícitamente con
    guardar_a_geopackage(), o dejarse como capa temporal si el usuario
    así lo prefiere.
    """
    uri = f"Polygon?crs={crs.authid()}"
    capa = QgsVectorLayer(uri, nombre_capa, "memory")
    capa.dataProvider().addAttributes(campos_resultado)
    capa.updateFields()
    return capa


def poblar_fragmentos(capa_resultado, fragmentos, feature_original, area_total_padre,
                       padre_id, etiquetar=True):
    """
    Inserta cada fragmento como una feature en la capa resultado,
    heredando todos los atributos originales y añadiendo los campos
    de control. Opcionalmente activa el etiquetado por expresión.
    """
    provider = capa_resultado.dataProvider()
    nuevas_features = []
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    n = len(fragmentos)
    for i, frag_geom in enumerate(fragmentos, start=1):
        feat = QgsFeature(capa_resultado.fields())
        feat.setGeometry(frag_geom)

        # Heredar atributos originales (por nombre, robusto a orden de
        # campos). 'fid' se excluye explícitamente: ver nota en
        # construir_campos_resultado sobre el conflicto con la clave
        # primaria de GeoPackage.
        for campo in feature_original.fields().names():
            if campo.lower() in ("fid", "ogc_fid", "objectid"):
                continue
            idx_destino = feat.fields().indexFromName(campo)
            if idx_destino != -1:
                feat.setAttribute(idx_destino, feature_original.attribute(campo))

        area_ha = frag_geom.area() / 10000.0
        porcentaje = (frag_geom.area() / area_total_padre * 100.0) if area_total_padre else 0.0
        area_padre_ha = area_total_padre / 10000.0 if area_total_padre else 0.0

        feat.setAttribute("fraccion", i)
        feat.setAttribute("area_ha", round(area_ha, 4))
        feat.setAttribute("porcentaje", round(porcentaje, 4))   # 4 decimales para no perder precisión
        feat.setAttribute("area_padre_ha", round(area_padre_ha, 4))
        feat.setAttribute("fecha_division", fecha_hoy)
        feat.setAttribute("poligono_padre_id", str(padre_id))

        nuevas_features.append(feat)

    provider.addFeatures(nuevas_features)
    capa_resultado.updateExtents()

    if etiquetar:
        aplicar_etiquetado_automatico(capa_resultado)

    log_info(
        f"Polygon Divider: {n} fragmentos insertados en capa "
        f"'{capa_resultado.name()}'."
    )
    return nuevas_features


# ─────────────────────────────────────────────────────────────────────
# Etiquetado automático por expresión
# ─────────────────────────────────────────────────────────────────────

def _resolver_placement_overpoint():
    """
    Resuelve QgsPalLayerSettings.PredefinedPointPosition.OverPoint de forma robusta
    entre versiones de PyQGIS.

    En algunas versiones recientes (PyQt6), QgsPalLayerSettings tiene
    DOS enums distintos que comparten nombres de miembro parecidos
    (Placement.OverPoint para posicionamiento de etiqueta, y un enum no
    relacionado LabelPredefinedPointPosition). El atributo "plano"
    QgsPalLayerSettings.PredefinedPointPosition.OverPoint puede resolver ambiguamente al enum
    incorrecto y lanzar:
        "a member of enum 'LabelPlacement' is expected not
         'LabelPredefinedPointPosition'"
    La forma con namespace explícito Placement.OverPoint es la única
    consistente en todas las versiones soportadas (QGIS ≥ 3.22).
    """
    placement_enum = getattr(QgsPalLayerSettings, "Placement", None)
    if placement_enum is not None and hasattr(placement_enum, "OverPoint"):
        return placement_enum.OverPoint
    # Fallback para versiones muy antiguas sin el enum anidado
    return QgsPalLayerSettings.PredefinedPointPosition.OverPoint


def aplicar_etiquetado_automatico(capa):
    """
    Activa etiquetado de capa usando una expresión QGIS dinámica, NO un
    campo de texto fijo. Esto permite que el usuario edite el estilo de
    etiqueta libremente después, sin tocar datos.

    Formato de etiqueta:
        FRACCIÓN 1
        2.55 ha (33.3%)
    """
    settings = QgsPalLayerSettings()
    settings.fieldName = (
        "'FRACCIÓN ' || \"fraccion\" || '\\n' || "
        "round(\"area_ha\", 4) || ' ha (' || round(\"porcentaje\", 2) || '%)'"
    )
    settings.isExpression = True
    settings.placement = _resolver_placement_overpoint()

    text_format = QgsTextFormat()
    text_format.setSize(9)
    settings.setFormat(text_format)

    labeling = QgsVectorLayerSimpleLabeling(settings)
    capa.setLabeling(labeling)
    capa.setLabelsEnabled(True)
    capa.triggerRepaint()

    log_info(f"Polygon Divider: etiquetado automático activado en '{capa.name()}'.")


# ─────────────────────────────────────────────────────────────────────
# Persistencia a GeoPackage
# ─────────────────────────────────────────────────────────────────────

def guardar_a_geopackage(capa_memoria, carpeta_destino, nombre_archivo):
    """
    Escribe la capa de memoria a un archivo .gpkg en `carpeta_destino`.
    Si el archivo ya existe, agrega un sufijo numérico para no sobrescribir
    trabajo previo silenciosamente.

    Retorna: (ruta_completa, capa_cargada_desde_disco) o (None, None) si falla.
    """
    if not nombre_archivo.lower().endswith(".gpkg"):
        nombre_archivo += ".gpkg"

    ruta = os.path.join(carpeta_destino, nombre_archivo)

    contador = 1
    base, ext = os.path.splitext(ruta)
    while os.path.exists(ruta):
        ruta = f"{base}_{contador}{ext}"
        contador += 1

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.fileEncoding = "UTF-8"

    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        capa_memoria,
        ruta,
        QgsProject.instance().transformContext(),
        options,
    )

    # writeAsVectorFormatV3 retorna una tupla (QgsVectorFileWriter.WriterError, str)
    error_code = error[0] if isinstance(error, tuple) else error

    if error_code != QgsVectorFileWriter.WriterError.NoError:
        log_error(f"Polygon Divider: error al guardar GeoPackage en '{ruta}': {error}")
        return None, None

    nombre_capa = os.path.splitext(os.path.basename(ruta))[0]
    capa_disco = QgsVectorLayer(f"{ruta}|layername={nombre_capa}", nombre_capa, "ogr")

    if not capa_disco.isValid():
        # Fallback: intentar cargar sin layername explícito
        capa_disco = QgsVectorLayer(ruta, nombre_capa, "ogr")

    log_info(f"Polygon Divider: GeoPackage guardado en '{ruta}'.")
    return ruta, capa_disco
