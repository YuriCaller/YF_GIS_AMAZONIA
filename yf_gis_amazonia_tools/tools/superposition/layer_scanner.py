# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Escáner recursivo de capas vectoriales en una carpeta.

Este es el reemplazo del "iterador + Model Builder" de ArcGIS: os.walk
recorre la carpeta de derechos preexistentes (concesiones, predios, BPP,
lotes de hidrocarburos, comunidades...) y devuelve cada capa lista para
analizar — incluidas las sub-capas dentro de un GeoPackage.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os

# Formatos vectoriales que OGR abre y que son habituales en expedientes
# peruanos. Se excluye .dbf suelto (tabla sin geometría) a propósito.
EXTENSIONES_VECTORIALES = (
    ".shp", ".gpkg", ".geojson", ".json", ".kml", ".kmz",
    ".gml", ".tab", ".mif", ".sqlite", ".gdb",
)

# Carpetas que nunca se recorren (ruido típico de directorios de trabajo).
CARPETAS_IGNORADAS = {
    ".git", "__pycache__", ".svn", "node_modules",
    "$RECYCLE.BIN", "System Volume Information",
}


class CapaEncontrada:
    """Una capa lista para analizar.

    v3.0.4: admite capas REMOTAS (geoservicios WFS / ArcGIS REST) además
    de archivos en disco. `provider` deja de estar implícito en "ogr"
    porque una capa WFS necesita el proveedor "WFS", y `archivo` pasa a
    contener la URL del servicio cuando `remota` es True — de ahí que la
    trazabilidad y las etiquetas usen `origen_corto()` en vez de
    os.path.basename(), que sobre una URL devuelve basura.
    """

    __slots__ = ("uri", "nombre", "archivo", "es_sublayer",
                 "provider", "remota", "origen_etiqueta")

    def __init__(self, uri, nombre, archivo, es_sublayer=False,
                 provider="ogr", remota=False, origen_etiqueta=""):
        self.uri = uri            # lo que recibe QgsVectorLayer()
        self.nombre = nombre      # nombre legible para el informe
        self.archivo = archivo    # ruta física, o URL si remota
        self.es_sublayer = es_sublayer
        self.provider = provider  # "ogr", "WFS", "arcgisfeatureserver"
        self.remota = remota
        self.origen_etiqueta = origen_etiqueta

    def origen_corto(self):
        """Etiqueta breve del origen, válida para archivo o servicio."""
        if self.remota:
            return self.origen_etiqueta or self.archivo
        return os.path.basename(self.archivo) if self.archivo else ""

    def __repr__(self):
        return "<CapaEncontrada {} ({})>".format(self.nombre,
                                                 self.origen_corto())


def _nombre_legible(ruta):
    """Nombre de capa a partir del archivo, sin extensión."""
    return os.path.splitext(os.path.basename(ruta))[0]


def listar_archivos_vectoriales(carpeta, recursivo=True,
                                extensiones=EXTENSIONES_VECTORIALES):
    """Rutas de archivos vectoriales bajo `carpeta`.

    Este es el "iterador" que en ArcGIS requería Model Builder: aquí es
    una función de 10 líneas que además puede filtrarse y testearse.
    """
    encontrados = []
    if not carpeta or not os.path.isdir(carpeta):
        return encontrados

    exts = tuple(e.lower() for e in extensiones)
    for raiz, dirs, archivos in os.walk(carpeta):
        dirs[:] = [d for d in dirs if d not in CARPETAS_IGNORADAS]
        for nombre in sorted(archivos):
            if nombre.lower().endswith(exts):
                encontrados.append(os.path.join(raiz, nombre))
        if not recursivo:
            break
    return encontrados


def _sublayers_gpkg(ruta):
    """Sub-capas de un GeoPackage/SQLite/GDB.

    Un .gpkg puede contener 20 capas (concesiones, BPP, predios...); si
    solo se abriera el archivo se analizaría una sola y el informe
    quedaría incompleto sin que nadie lo note. Esa omisión silenciosa es
    justamente el error que este módulo debe evitar.
    """
    from qgis.core import QgsVectorLayer, QgsProviderRegistry

    resultados = []
    # Vía preferida: metadatos del proveedor (no carga geometrías)
    try:
        meta = QgsProviderRegistry.instance().providerMetadata("ogr")
        if meta is not None:
            for sub in meta.querySublayers(ruta):
                if sub.name():
                    resultados.append((sub.uri(), sub.name()))
            if resultados:
                return resultados
    except Exception:
        resultados = []

    # Respaldo: abrir la capa y leer subLayers() del proveedor.
    # v3.0.4 fix: liberar la capa temporal (si no, cada .gpkg deja un
    # dataset OGR abierto y contribuye a la degradación de QGIS).
    capa = None
    try:
        capa = QgsVectorLayer(ruta, "tmp", "ogr")
        if not capa.isValid():
            return []
        for entrada in capa.dataProvider().subLayers():
            partes = entrada.split("!!::!!")
            if len(partes) >= 2:
                nombre = partes[1]
                resultados.append(
                    ("{}|layername={}".format(ruta, nombre), nombre))
    except Exception:
        return []
    finally:
        if capa is not None:
            try:
                capa.setDataSource("", "", "ogr")
            except Exception:  # nosec B110 - cierre best-effort del
                pass           # proveedor OGR para no filtrar handles
            del capa
    return resultados


def escanear_carpeta(carpeta, recursivo=True, log=None):
    """Devuelve [CapaEncontrada] para toda la carpeta.

    Expande automáticamente las sub-capas de GeoPackage: 1 archivo puede
    producir N capas analizables.
    """
    capas = []
    for ruta in listar_archivos_vectoriales(carpeta, recursivo):
        ext = os.path.splitext(ruta)[1].lower()
        if ext in (".gpkg", ".sqlite", ".gdb"):
            subs = _sublayers_gpkg(ruta)
            if subs:
                for uri, nombre in subs:
                    capas.append(CapaEncontrada(
                        uri=uri,
                        nombre="{} › {}".format(_nombre_legible(ruta), nombre),
                        archivo=ruta,
                        es_sublayer=True))
                if log:
                    log("{}: {} sub-capa(s)".format(
                        os.path.basename(ruta), len(subs)))
                continue
        capas.append(CapaEncontrada(
            uri=ruta, nombre=_nombre_legible(ruta), archivo=ruta))
    if log:
        log("Escaneo: {} capa(s) analizable(s) en {}".format(
            len(capas), carpeta))
    return capas
