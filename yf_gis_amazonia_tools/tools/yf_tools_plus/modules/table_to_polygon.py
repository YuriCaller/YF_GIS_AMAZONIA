# -*- coding: utf-8 -*-
"""
TableToPolygon — Tabla (Excel/CSV) a polígono(s) en un solo paso.
Reemplaza el flujo Excel→CSV→Polígono de versiones anteriores.

Capacidades:
  - Lee .xlsx / .xls / .csv directamente (pandas), con selector de hoja.
  - Un polígono por tabla, o VARIOS agrupando por un campo ID.
  - Orden de vértices por campo opcional (evita polígonos "estrella").
  - Validación honesta: nunca inventa geometría; los grupos inválidos
    se omiten y se reportan con detalle.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os
import pandas as pd

from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY,
    QgsProject, QgsFillSymbol, QgsSingleSymbolRenderer,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling, QgsDistanceArea,
    QgsCoordinateReferenceSystem, QgsMessageLog, Qgis,
)
from qgis.PyQt.QtGui import QColor, QFont
from ....core.qt_compat import QVariant_Int, QVariant_Double, QVariant_String

TAG = "YF Tools Plus"

EXT_EXCEL = ('.xlsx', '.xls')
EXT_CSV = ('.csv',)

# Candidatos para auto-detección de campos
CAND_X = ('este', 'x', 'east', 'coord_x', 'utm_e', 'e')
CAND_Y = ('norte', 'y', 'north', 'coord_y', 'utm_n', 'n')
CAND_ID = ('id_poligono', 'poligono', 'fraccion', 'predio', 'parcela',
           'id_pol', 'grupo', 'zona')
CAND_ORDEN = ('id_vertice', 'orden', 'vertice', 'order', 'secuencia', 'nro')


def _log(msg, nivel=Qgis.MessageLevel.Info):
    QgsMessageLog.logMessage(str(msg), TAG, nivel)


class TableToPolygon:
    """Crea polígonos a partir de una tabla Excel o CSV."""

    # ------------------------------------------------------------------
    # Lectura de tabla
    # ------------------------------------------------------------------

    @staticmethod
    def es_excel(path):
        return str(path).lower().endswith(EXT_EXCEL)

    @staticmethod
    def get_sheets(path):
        """Hojas de un Excel (lista vacía para CSV o error)."""
        try:
            if TableToPolygon.es_excel(path):
                return list(pd.ExcelFile(path).sheet_names)
        except Exception as e:
            _log("No se pudieron leer las hojas: {}".format(e), Qgis.MessageLevel.Warning)
        return []

    @staticmethod
    def read_table(path, sheet=None):
        """DataFrame desde xlsx/xls/csv. Lanza excepción con mensaje claro."""
        if not os.path.exists(path):
            raise FileNotFoundError("El archivo no existe: {}".format(path))
        if TableToPolygon.es_excel(path):
            return pd.read_excel(path, sheet_name=sheet if sheet else 0)
        # CSV: intentar utf-8 y caer a latin-1 (tablas de campo antiguas)
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding='latin-1')

    @classmethod
    def get_fields(cls, path, sheet=None):
        """Nombres de columnas de la tabla."""
        try:
            df = cls.read_table(path, sheet)
            return [str(c) for c in df.columns]
        except Exception as e:
            _log("Error leyendo campos: {}".format(e), Qgis.MessageLevel.Warning)
            return []

    @staticmethod
    def autodetectar(campos):
        """Sugiere campos X, Y, ID de polígono y orden a partir de nombres."""
        res = {'x': '', 'y': '', 'id': '', 'orden': ''}
        bajos = {c.lower().strip(): c for c in campos}

        def busca(cands):
            for cand in cands:
                if cand in bajos:
                    return bajos[cand]
            for cand in cands:
                for lc, orig in bajos.items():
                    if lc.startswith(cand):
                        return orig
            return ''

        res['x'] = busca(CAND_X)
        res['y'] = busca(CAND_Y)
        res['id'] = busca(CAND_ID)
        res['orden'] = busca(CAND_ORDEN)
        return res

    # ------------------------------------------------------------------
    # Creación de polígonos
    # ------------------------------------------------------------------

    @classmethod
    def create_polygons(cls, path, field_x, field_y, crs_authid,
                        sheet=None, field_id=None, field_orden=None,
                        style_params=None, nombre_capa=None):
        """Crea la capa de polígonos.

        field_id:    columna que agrupa filas en polígonos (None = uno solo)
        field_orden: columna que ordena los vértices dentro de cada grupo
                     (None = orden de filas de la tabla)

        Devuelve (QgsVectorLayer | None, resumen: str).
        La capa se agrega al proyecto solo si hay al menos 1 polígono válido.
        """
        df = cls.read_table(path, sheet)
        total_filas = len(df)
        _log("Tabla '{}'{}: {} filas".format(
            os.path.basename(path),
            " hoja '{}'".format(sheet) if sheet else "", total_filas))

        for col in (field_x, field_y):
            if col not in df.columns:
                raise ValueError("La columna '{}' no existe en la tabla".format(col))

        # Coordenadas numéricas; reportar filas inválidas (1-based + encabezado)
        df = df.copy()
        df['_X'] = pd.to_numeric(df[field_x], errors='coerce')
        df['_Y'] = pd.to_numeric(df[field_y], errors='coerce')
        invalidas = df[df['_X'].isna() | df['_Y'].isna()]
        filas_malas = [int(i) + 2 for i in invalidas.index.tolist()]
        df_ok = df.dropna(subset=['_X', '_Y'])

        nombre = nombre_capa or os.path.splitext(os.path.basename(path))[0]
        return cls._construir_poligonos(df_ok, filas_malas, field_id,
                                        field_orden, crs_authid,
                                        style_params, nombre)

    # ------------------------------------------------------------------
    # Constructor común (tabla o capa de puntos)
    # ------------------------------------------------------------------

    @classmethod
    def _construir_poligonos(cls, df_ok, filas_malas, field_id,
                             field_orden, crs_authid, style_params,
                             nombre_base):
        """Núcleo compartido: agrupa, ordena, valida y construye la capa.

        df_ok: DataFrame con columnas _X, _Y (numéricas) y los campos
        de atributos. Usado tanto por la ruta de archivo (Excel/CSV)
        como por la ruta de capa de puntos (v3.0.4).
        """
        # Agrupación
        if field_id and field_id in df_ok.columns:
            grupos = list(df_ok.groupby(field_id, sort=True))
        else:
            grupos = [(1, df_ok)]

        # Construcción de features
        feats, omitidos, detalles = [], [], []
        for gid, g in grupos:
            if field_orden and field_orden in g.columns:
                g = g.copy()
                g['_ORD'] = pd.to_numeric(g[field_orden], errors='coerce')
                g = g.sort_values('_ORD', na_position='last')
            pts = [QgsPointXY(float(x), float(y))
                   for x, y in zip(g['_X'], g['_Y'])]
            # Cierre implícito: si el último punto repite el primero, quitarlo
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) < 3:
                omitidos.append("{} ({} vértices)".format(gid, len(pts)))
                continue
            geom = QgsGeometry.fromPolygonXY([pts])
            if geom.isNull() or not geom.isGeosValid():
                # Se conserva (el usuario decide repararla), pero se avisa
                _log("Polígono '{}' con geometría no válida (auto-intersección?)"
                     .format(gid), Qgis.MessageLevel.Warning)
            feats.append((gid, pts, geom))
            detalles.append("{}: {} vértices".format(gid, len(pts)))

        if not feats:
            resumen = ("No se creó ningún polígono. Grupos con menos de 3 "
                       "vértices: {}.".format(", ".join(omitidos) or "—"))
            if filas_malas:
                resumen += " Filas con coordenadas no numéricas: {}.".format(
                    filas_malas[:15])
            _log(resumen, Qgis.MessageLevel.Critical)
            return None, resumen

        # Capa en memoria
        crs = QgsCoordinateReferenceSystem(crs_authid)
        nombre = nombre_base
        layer = QgsVectorLayer("Polygon?crs={}".format(crs_authid),
                               nombre, "memory")
        prov = layer.dataProvider()
        prov.addAttributes([
            QgsField("ID", QVariant_String),
            QgsField("VERTICES", QVariant_Int),
            QgsField("AREA_HA", QVariant_Double),
            QgsField("PERIMETRO", QVariant_Double),
        ])
        layer.updateFields()

        # Área/perímetro elipsoidales (WGS84) — mismos criterios que la suite
        da = QgsDistanceArea()
        da.setSourceCrs(crs, QgsProject.instance().transformContext())
        da.setEllipsoid("WGS84")

        for gid, pts, geom in feats:
            f = QgsFeature(layer.fields())
            f.setGeometry(geom)
            try:
                area_ha = round(da.measureArea(geom) / 10000.0, 4)
                perim = round(da.measurePerimeter(geom), 2)
            except Exception:
                area_ha, perim = None, None
            f.setAttributes([str(gid), len(pts), area_ha, perim])
            prov.addFeature(f)
        layer.updateExtents()

        cls._aplicar_estilo(layer, style_params or {})
        QgsProject.instance().addMapLayer(layer)

        resumen = "{} polígono(s) creados: {}.".format(
            len(feats), "; ".join(detalles))
        if omitidos:
            resumen += "\nOmitidos por tener menos de 3 vértices: {}.".format(
                ", ".join(omitidos))
        if filas_malas:
            resumen += "\nFilas con coordenadas no numéricas (ignoradas): {}{}".format(
                filas_malas[:15], "…" if len(filas_malas) > 15 else "")
        _log(resumen)
        return layer, resumen

    # ------------------------------------------------------------------
    # v3.0.4: capa de puntos del proyecto como fuente
    # ------------------------------------------------------------------

    @classmethod
    def create_polygons_from_layer(cls, layer, field_id=None,
                                   field_orden=None, style_params=None,
                                   nombre_capa=None, solo_seleccion=False):
        """Crea polígono(s) desde una capa de puntos ya cargada en QGIS.

        Las coordenadas salen de la GEOMETRÍA (no de campos) y el CRS de
        salida es el de la capa — sin riesgo de elegir mal la zona UTM.
        solo_seleccion=True usa únicamente las entidades seleccionadas.
        """
        from qgis.core import QgsWkbTypes
        feats = (layer.selectedFeatures() if solo_seleccion
                 else list(layer.getFeatures()))
        _log("Capa '{}': {} punto(s){}".format(
            layer.name(), len(feats),
            " (solo selección)" if solo_seleccion else ""))
        if not feats:
            return None, ("No hay entidades seleccionadas en la capa."
                          if solo_seleccion
                          else "La capa no tiene entidades.")

        nombres_campos = [f.name() for f in layer.fields()]
        filas, vacias = [], 0
        for f in feats:
            g = f.geometry()
            if g is None or g.isEmpty():
                vacias += 1
                continue
            if QgsWkbTypes.isMultiType(g.wkbType()):
                pts = g.asMultiPoint()
                if not pts:
                    vacias += 1
                    continue
                p = pts[0]
            else:
                p = g.asPoint()
            fila = {n: f[n] for n in nombres_campos}
            fila['_X'] = float(p.x())
            fila['_Y'] = float(p.y())
            filas.append(fila)

        if vacias:
            _log("{} entidad(es) sin geometría de punto — omitidas".format(
                vacias), Qgis.MessageLevel.Warning)
        if not filas:
            return None, "Ninguna entidad tiene geometría de punto válida."

        df_ok = pd.DataFrame(filas)
        nombre = nombre_capa or "{}_poligono".format(layer.name())
        return cls._construir_poligonos(df_ok, [], field_id, field_orden,
                                        layer.crs().authid(),
                                        style_params, nombre)


    # ------------------------------------------------------------------
    # Estilo (mismo look de la suite: borde rojo, relleno claro, etiqueta ID)
    # ------------------------------------------------------------------

    @staticmethod
    def _aplicar_estilo(layer, p):
        try:
            sym = QgsFillSymbol.createSimple({
                'color': p.get('polygon_color', '255,255,255,60'),
                'outline_color': p.get('border_color', '#ff340b'),
                'outline_width': p.get('border_width', '0.26'),
            })
            layer.setRenderer(QgsSingleSymbolRenderer(sym))

            settings = QgsPalLayerSettings()
            settings.fieldName = "ID"
            fmt = QgsTextFormat()
            fmt.setFont(QFont(p.get('label_font', 'Arial')))
            fmt.setSize(float(p.get('label_size', '9')))
            fmt.setColor(QColor(p.get('label_color', '#ff340b')))
            buf = QgsTextBufferSettings()
            buf.setEnabled(True)
            buf.setSize(0.8)
            buf.setColor(QColor('#ffffff'))
            fmt.setBuffer(buf)
            settings.setFormat(fmt)
            layer.setLabelsEnabled(True)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.triggerRepaint()
        except Exception as e:
            _log("No se pudo aplicar el estilo: {}".format(e), Qgis.MessageLevel.Warning)
