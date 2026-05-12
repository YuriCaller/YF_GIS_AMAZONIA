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


    # ══════════════════════════════════════════════════
    # PUNTO PROMEDIADO (COORDENADA CORREGIDA FINAL)
    # ══════════════════════════════════════════════════
    def build_averaged_layer(self, stats: PosStats,
                              project_name: str = '') -> QgsVectorLayer:
        """Genera UN solo punto: la coordenada corregida promediada."""
        p = self.params
        bc = p.base_coords
        fix_ep = [e for e in stats.epochs if e.q == 1]
        flt_ep = [e for e in stats.epochs if e.q == 2]
        if len(fix_ep) >= 5:
            best, q_used, q_label = fix_ep, 1, 'FIX'
        elif flt_ep:
            best, q_used, q_label = flt_ep, 2, 'FLOAT'
        elif stats.epochs:
            best, q_used, q_label = stats.epochs, 5, 'SINGLE'
        else:
            return None
        n = len(best)
        lat_avg = sum(e.lat for e in best) / n
        lon_avg = sum(e.lon for e in best) / n
        h_avg   = sum(e.h for e in best) / n
        lat_std_m = math.sqrt(sum((e.lat - lat_avg)**2 for e in best) / n) * 111320
        lon_std_m = math.sqrt(sum((e.lon - lon_avg)**2 for e in best) / n) * 111320 * math.cos(math.radians(lat_avg))
        h_std     = math.sqrt(sum((e.h - h_avg)**2 for e in best) / n)
        sdn_avg = sum(e.sdn for e in best) / n
        sde_avg = sum(e.sde for e in best) / n
        sdu_avg = sum(e.sdu for e in best) / n
        ns_avg  = sum(e.ns for e in best) / n
        try:
            este, norte, _ = self._conv.geo_to_utm(lat_avg, lon_avg)
        except Exception:
            este, norte = 0.0, 0.0
        base_nombre = getattr(bc, 'fuente', 'N/A') if bc else 'N/A'
        base_corregida = 'SI' if (bc and bc.fue_corregida) else 'NO'
        layer = QgsVectorLayer('Point?crs=EPSG:4326',
                               f'{project_name}_GNSS_corregido', 'memory')
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField('nombre',          QVariant.String),
            QgsField('lat_dd',          QVariant.Double),
            QgsField('lon_dd',          QVariant.Double),
            QgsField('este',            QVariant.Double),
            QgsField('norte',           QVariant.Double),
            QgsField('altura_elip',     QVariant.Double),
            QgsField('precision_h',     QVariant.Double),
            QgsField('precision_v',     QVariant.Double),
            QgsField('sigma_norte_m',   QVariant.Double),
            QgsField('sigma_este_m',    QVariant.Double),
            QgsField('sigma_altura_m',  QVariant.Double),
            QgsField('rtklib_sdn',      QVariant.Double),
            QgsField('rtklib_sde',      QVariant.Double),
            QgsField('rtklib_sdu',      QVariant.Double),
            QgsField('calidad',         QVariant.String),
            QgsField('q',               QVariant.Int),
            QgsField('n_epocas_total',  QVariant.Int),
            QgsField('n_epocas_usadas', QVariant.Int),
            QgsField('n_fix',           QVariant.Int),
            QgsField('n_float',         QVariant.Int),
            QgsField('pct_fix',         QVariant.Double),
            QgsField('sat_promedio',    QVariant.Double),
            QgsField('metodo',          QVariant.String),
            QgsField('base_nombre',     QVariant.String),
            QgsField('base_corregida',  QVariant.String),
        ])
        layer.updateFields()
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon_avg, lat_avg)))
        feat.setAttributes([
            project_name,
            round(lat_avg, 10), round(lon_avg, 10),
            round(este, 3), round(norte, 3), round(h_avg, 4),
            round(math.sqrt(sdn_avg**2 + sde_avg**2), 4), round(sdu_avg, 4),
            round(lat_std_m, 4), round(lon_std_m, 4), round(h_std, 4),
            round(sdn_avg, 5), round(sde_avg, 5), round(sdu_avg, 5),
            q_label, q_used,
            len(stats.epochs), n, len(fix_ep), len(flt_ep),
            round(len(fix_ep) / len(stats.epochs) * 100, 1) if stats.epochs else 0.0,
            round(ns_avg, 1), p.mode.upper(), base_nombre, base_corregida,
        ])
        pr.addFeatures([feat])
        layer.updateExtents()
        color = '#4CAF50' if q_used == 1 else '#FF9800' if q_used == 2 else '#F44336'
        sym = QgsMarkerSymbol.createSimple({
            'name': 'circle', 'color': color,
            'size': '5', 'outline_color': '#333', 'outline_width': '0.5'
        })
        layer.renderer().setSymbol(sym)
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
