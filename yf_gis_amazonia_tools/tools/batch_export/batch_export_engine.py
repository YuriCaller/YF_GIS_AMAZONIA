# -*- coding: utf-8 -*-
"""
Batch Export Engine — empaqueta expediente completo listo para entregar.
Exporta capas vectoriales, PDFs de layouts y tabla de coordenadas en un clic.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os
import shutil
import zipfile
from datetime import datetime

from qgis.core import (
    QgsProject,
    QgsVectorFileWriter,
    QgsPrintLayout,
    QgsLayoutExporter,
    QgsCoordinateTransformContext,
    QgsVectorLayer,
    QgsMessageLog,
    Qgis,
)


# ─────────────────────────────────────────────────────────────────────────────
# Plantillas de estructura de carpetas
# ─────────────────────────────────────────────────────────────────────────────

PLANTILLAS = {
    "goremad": {
        "nombre":      "GOREMAD — Titulación / Catastro",
        "descripcion": "Estructura estándar para expedientes de GOREMAD",
        "carpetas": [
            "01_SHAPES",
            "02_GEOPACKAGE",
            "03_MAPAS_PDF",
            "04_TABLAS",
            "05_METADATOS",
        ],
    },
    "serfor": {
        "nombre":      "SERFOR — POA / Plan de Manejo",
        "descripcion": "Estructura para expedientes forestales SERFOR",
        "carpetas": [
            "01_SHAPES",
            "02_GEOPACKAGE",
            "03_MAPAS_PDF",
            "04_TABLAS_INVENTARIO",
            "05_METADATOS",
        ],
    },
    "acca": {
        "nombre":      "ACCA — Monitoreo / Paisaje",
        "descripcion": "Estructura para entregables ACCA",
        "carpetas": [
            "01_VECTORIALES",
            "02_MAPAS_PDF",
            "03_TABLAS",
            "04_METADATOS",
        ],
    },
    "simple": {
        "nombre":      "Simple — Sin subcarpetas",
        "descripcion": "Todo en una sola carpeta",
        "carpetas": [],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Funciones principales
# ─────────────────────────────────────────────────────────────────────────────

def crear_estructura(base_dir, plantilla_key, nombre_expediente):
    """Crea la estructura de carpetas del expediente."""
    plantilla = PLANTILLAS.get(plantilla_key, PLANTILLAS["simple"])
    raiz = os.path.join(base_dir, nombre_expediente)
    os.makedirs(raiz, exist_ok=True)

    carpetas_creadas = {"raiz": raiz}
    for carpeta in plantilla["carpetas"]:
        path = os.path.join(raiz, carpeta)
        os.makedirs(path, exist_ok=True)
        # Clave simplificada para acceso
        key = carpeta.split("_", 1)[-1].lower() if "_" in carpeta else carpeta.lower()
        carpetas_creadas[key] = path

    return raiz, carpetas_creadas


def exportar_capa_shapefile(layer, destino_dir, nombre=None):
    """Exporta una capa vectorial a Shapefile."""
    nombre = nombre or _sanitizar(layer.name())
    path = os.path.join(destino_dir, nombre + ".shp")

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "ESRI Shapefile"
    options.fileEncoding = "UTF-8"

    error, msg = _exportar(layer, path, options)
    return path, error, msg


def exportar_capa_geopackage(layer, destino_dir, nombre=None):
    """Exporta una capa vectorial a GeoPackage."""
    nombre = nombre or _sanitizar(layer.name())
    path = os.path.join(destino_dir, nombre + ".gpkg")

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.fileEncoding = "UTF-8"
    options.layerName = nombre

    error, msg = _exportar(layer, path, options)
    return path, error, msg


def exportar_layout_pdf(layout, destino_dir, nombre=None, dpi=300):
    """Exporta un QgsPrintLayout a PDF."""
    nombre = nombre or _sanitizar(layout.name())
    path = os.path.join(destino_dir, nombre + ".pdf")

    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = dpi
    settings.forceVectorOutput = False

    result = exporter.exportToPdf(path, settings)
    if result == QgsLayoutExporter.ExportResult.Success:
        return path, True, "OK"
    else:
        return path, False, f"Error exportando PDF (código {result})"


def exportar_tabla_coordenadas(layer, destino_dir, nombre=None, formato="xlsx"):
    """
    Exporta tabla de atributos a XLSX o CSV.
    Ideal para tabla de coordenadas de vértices.
    """
    nombre = nombre or _sanitizar(layer.name()) + "_tabla"
    
    if formato == "xlsx":
        path = os.path.join(destino_dir, nombre + ".xlsx")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "XLSX"
        options.fileEncoding = "UTF-8"
    else:
        path = os.path.join(destino_dir, nombre + ".csv")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "CSV"
        options.fileEncoding = "UTF-8"

    error, msg = _exportar(layer, path, options)
    return path, error, msg


def generar_metadatos(raiz, nombre_expediente, capas_info, layouts_info,
                      autor, cliente, crs_authid):
    """Genera un archivo TXT de metadatos del expediente."""
    path = os.path.join(raiz, "METADATOS.txt")
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")

    lineas = [
        "=" * 60,
        f"  EXPEDIENTE: {nombre_expediente}",
        "=" * 60,
        f"  Fecha de generación : {ahora}",
        f"  Elaborado por       : {autor}",
        f"  Cliente / Entidad   : {cliente}",
        f"  Sistema de referencia: {crs_authid}",
        f"  Software            : QGIS + YF GIS Amazonia Tools",
        "",
        "─" * 60,
        "  CAPAS VECTORIALES INCLUIDAS",
        "─" * 60,
    ]
    for info in capas_info:
        lineas.append(f"  • {info['nombre']} — {info['tipo']} — {info['features']} features")

    lineas += [
        "",
        "─" * 60,
        "  MAPAS PDF INCLUIDOS",
        "─" * 60,
    ]
    for info in layouts_info:
        lineas.append(f"  • {info['nombre']} — DPI {info['dpi']}")

    lineas += [
        "",
        "─" * 60,
        "  TUCSA — Training Universal Company SAC",
        "  gis-amazonia.pe",
        "=" * 60,
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))

    return path


def comprimir_expediente(raiz, destino_zip=None):
    """Comprime toda la carpeta del expediente en un ZIP."""
    if destino_zip is None:
        destino_zip = raiz + ".zip"

    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(raiz):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, os.path.dirname(raiz))
                zf.write(filepath, arcname)

    return destino_zip


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _exportar(layer, path, options):
    """Wrapper para QgsVectorFileWriter.writeAsVectorFormatV3 con fallback."""
    try:
        context = QgsCoordinateTransformContext()
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, path, context, options
        )
        if result[0] == QgsVectorFileWriter.WriterError.NoError:
            return True, "OK"
        return False, result[1]
    except AttributeError:
        # Fallback para QGIS < 3.20
        try:
            error = QgsVectorFileWriter.writeAsVectorFormat(layer, path, options)
            if error[0] == QgsVectorFileWriter.WriterError.NoError:
                return True, "OK"
            return False, error[1]
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)


def _sanitizar(nombre):
    """Elimina caracteres no válidos para nombres de archivo."""
    import re
    nombre = nombre.replace(" ", "_")
    nombre = re.sub(r'[^\w\-]', '', nombre, flags=re.UNICODE)
    return nombre[:50]  # máximo 50 caracteres


def get_capas_vectoriales():
    """Retorna todas las capas vectoriales del proyecto."""
    return [
        layer for layer in QgsProject.instance().mapLayers().values()
        if isinstance(layer, QgsVectorLayer) and layer.isValid()
    ]


def get_layouts():
    """Retorna todos los layouts de impresión del proyecto."""
    return [
        layout for layout in QgsProject.instance().layoutManager().layouts()
        if isinstance(layout, QgsPrintLayout)
    ]
