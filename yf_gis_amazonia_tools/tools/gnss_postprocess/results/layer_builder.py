# -*- coding: utf-8 -*-
"""
layer_builder.py
Crea la capa vectorial QGIS con los atributos definidos en el prompt:
  nombre, este, norte, altura, precision, metodo, base_nombre, base_corregida
Aplica simbología categorizada por Q.
"""
import os
import math
from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
    QgsPointXY, QgsProject, QgsSymbol,
    QgsRendererCategory, QgsCategorizedSymbolRenderer,
    QgsLineSymbol, QgsMarkerSymbol,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter, QgsCoordinateTransformContext
)
from qgis.PyQt.QtCore import QVariant
from ..results.pos_parser import PosStats, Q_LABELS, Q_COLORS_HEX
from ..gnss_engine.coord_converter import BaseCoords, CoordConverter


class LayerBuilder:
    """Construye capas QGIS a partir de PosStats."""

    def __init__(self, iface, params):
        self.iface  = iface
        self.params = params
        self._conv  = CoordConverter()

    # ══════════════════════════════════════════════
    # CAPA PRINCIPAL DE PUNTOS
    # ══════════════════════════════════════════════
    def build_points_layer(self, stats: PosStats,
                           project_name: str = '',
                           load_q: set = None) -> QgsVectorLayer:
        """
        Crea capa de puntos con todos los atributos del prompt.
        load_q: set de valores Q a incluir (None = todos)
        """
        p = self.params
        bc: BaseCoords = p.base_coords

        layer = QgsVectorLayer('Point?crs=EPSG:4326',
                               f'{project_name}_GNSS_puntos', 'memory')
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField('idx',             QVariant.Int),
            QgsField('timestamp',       QVariant.String),
            QgsField('nombre',          QVariant.String),   # Requerido prompt
            QgsField('lat_dd',          QVariant.Double),
            QgsField('lon_dd',          QVariant.Double),
            QgsField('este',            QVariant.Double),   # Requerido prompt
            QgsField('norte',           QVariant.Double),   # Requerido prompt
            QgsField('altura',          QVariant.Double),   # Requerido prompt (elipsoidal)
            QgsField('precision_h',     QVariant.Double),   # Requerido prompt (SDH m)
            QgsField('precision_v',     QVariant.Double),
            QgsField('q',               QVariant.Int),
            QgsField('q_label',         QVariant.String),
            QgsField('metodo',          QVariant.String),   # Requerido prompt
            QgsField('ns',              QVariant.Int),
            QgsField('sdn_m',           QVariant.Double),
            QgsField('sde_m',           QVariant.Double),
            QgsField('sdu_m',           QVariant.Double),
            QgsField('base_nombre',     QVariant.String),   # Requerido prompt
            QgsField('base_corregida',  QVariant.String),   # Requerido prompt
            QgsField('base_delta_h',    QVariant.Double),   # Trazabilidad
            QgsField('base_delta_v',    QVariant.Double),
        ])
        layer.updateFields()

        # Datos de base para atributos
        base_nombre    = getattr(bc, 'fuente', 'N/A') if bc else 'N/A'
        base_corregida = 'SI' if (bc and bc.fue_corregida) else 'NO'
        delta_h = (bc.delta_horizontal_m or 0.0) if bc else 0.0
        delta_v = (bc.delta_vertical_m or 0.0) if bc else 0.0
        metodo  = p.mode.upper()

        features = []
        for i, ep in enumerate(stats.epochs):
            if load_q and ep.q not in load_q:
                continue

            # Calcular UTM
            try:
                este, norte, _ = self._conv.geo_to_utm(ep.lat, ep.lon)
            except Exception:
                este, norte = 0.0, 0.0

            sdh = math.sqrt(ep.sdn**2 + ep.sde**2)

            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(ep.lon, ep.lat)))
            f.setAttributes([
                i + 1,
                ep.timestamp,
                f'{project_name}_{i+1:04d}',
                round(ep.lat, 10),
                round(ep.lon, 10),
                round(este, 3),
                round(norte, 3),
                round(ep.h, 4),
                round(sdh, 5),
                round(ep.sdu, 5),
                ep.q,
                ep.q_label,
                metodo,
                ep.ns,
                round(ep.sdn, 5),
                round(ep.sde, 5),
                round(ep.sdu, 5),
                base_nombre,
                base_corregida,
                round(delta_h, 4),
                round(delta_v, 4),
            ])
            features.append(f)

        pr.addFeatures(features)
        layer.updateExtents()
        self._apply_symbology(layer)
        return layer

    # ══════════════════════════════════════════════
    # CAPA DE TRAYECTORIA
    # ══════════════════════════════════════════════
    def build_trajectory_layer(self, stats: PosStats,
                                project_name: str = '') -> QgsVectorLayer:
        layer = QgsVectorLayer('LineString?crs=EPSG:4326',
                               f'{project_name}_GNSS_trayectoria', 'memory')
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField('epocas',  QVariant.Int),
            QgsField('metodo',  QVariant.String),
        ])
        layer.updateFields()

        if len(stats.epochs) > 1:
            pts = [QgsPointXY(e.lon, e.lat) for e in stats.epochs]
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPolylineXY(pts))
            f.setAttributes([len(pts), self.params.mode.upper()])
            pr.addFeatures([f])
            layer.updateExtents()

        sym = QgsLineSymbol.createSimple({'color': '#2196f3', 'width': '0.6'})
        layer.renderer().setSymbol(sym)
        return layer

    # ══════════════════════════════════════════════
    # SIMBOLOGÍA
    # ══════════════════════════════════════════════
    def _apply_symbology(self, layer: QgsVectorLayer):
        cats = []
        for q, color in Q_COLORS_HEX.items():
            sym = QgsMarkerSymbol.createSimple({
                'name': 'circle', 'color': color,
                'size': '2.5',
                'outline_color': '#333', 'outline_width': '0.3'
            })
            cats.append(QgsRendererCategory(q, sym, Q_LABELS.get(q, str(q))))
        renderer = QgsCategorizedSymbolRenderer('q', cats)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    # ══════════════════════════════════════════════
    # EXPORTACIÓN
    # ══════════════════════════════════════════════
    def export_layer(self, layer: QgsVectorLayer,
                     out_dir: str, prefix: str,
                     formats: list):
        """
        formats: lista de 'gpkg', 'shp', 'kml', 'geojson'
        """
        driver_map = {
            'gpkg':    ('GPKG',    '.gpkg'),
            'shp':     ('ESRI Shapefile', '.shp'),
            'kml':     ('KML',     '.kml'),
            'geojson': ('GeoJSON', '.geojson'),
        }
        results = {}
        for fmt in formats:
            if fmt not in driver_map:
                continue
            driver, ext = driver_map[fmt]
            path = os.path.join(out_dir, prefix + ext)

            opts = QgsVectorFileWriter.SaveVectorOptions()
            opts.driverName = driver
            opts.layerName  = prefix
            if os.path.isfile(path) and fmt == 'gpkg':
                opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            else:
                opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

            err, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer, path,
                QgsCoordinateTransformContext(), opts
            )
            results[fmt] = path if err == QgsVectorFileWriter.NoError else f'ERROR: {msg}'

        return results
