# -*- coding: utf-8 -*-
"""
layer_builder.py
Crea la capa vectorial QGIS con los atributos definidos en el prompt:
  nombre, este, norte, altura, precision, metodo, base_nombre, base_corregida
Aplica simbología categorizada por Q.
"""
import logging
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
from ....core.qt_compat import QVariant_Int, QVariant_Double, QVariant_String
from ..results.pos_parser import PosStats, Q_LABELS, Q_COLORS_HEX
from ..gnss_engine.coord_converter import BaseCoords, CoordConverter


class LayerBuilder:
    """Construye capas QGIS a partir de PosStats."""

    def __init__(self, iface, params):
        self.iface  = iface
        self.params = params
        self._conv  = CoordConverter()

    # ══════════════════════════════════════════════
    # ZONA UTM FIJA
    # ══════════════════════════════════════════════
    def _zona_utm_proyecto(self, stats):
        """
        Determina la zona UTM única para todo el levantamiento.
        Prioridad:
          1. CRS del proyecto QGIS si es UTM
          2. Zona calculada del primer punto (centroide)
        Retorna string tipo '19S'.
        """
        # 1. Intentar desde CRS del proyecto
        try:
            from qgis.core import QgsProject  # noqa: F811
            crs = QgsProject.instance().crs()
            authid = crs.authid()  # ej. 'EPSG:32719'
            if authid.startswith('EPSG:'):
                epsg = int(authid.split(':')[1])
                # UTM Sur: 327xx, UTM Norte: 326xx
                if 32701 <= epsg <= 32760:
                    band = epsg - 32700
                    return f'{band}S'
                elif 32601 <= epsg <= 32660:
                    band = epsg - 32600
                    return f'{band}N'
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

        # 2. Calcular desde el centroide del levantamiento
        if stats.epochs:
            lat_c = sum(e.lat for e in stats.epochs) / len(stats.epochs)
            lon_c = sum(e.lon for e in stats.epochs) / len(stats.epochs)
            band = int((lon_c + 180) / 6) + 1
            hem = 'N' if lat_c >= 0 else 'S'
            return f'{band}{hem}'

        # 3. Default Madre de Dios
        return '19S'

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
            QgsField('idx',             QVariant_Int),
            QgsField('timestamp',       QVariant_String),
            QgsField('nombre',          QVariant_String),   # Requerido prompt
            QgsField('lat_dd',          QVariant_Double),
            QgsField('lon_dd',          QVariant_Double),
            QgsField('este',            QVariant_Double),   # Requerido prompt
            QgsField('norte',           QVariant_Double),   # Requerido prompt
            QgsField('altura',          QVariant_Double),   # Requerido prompt (elipsoidal)
            QgsField('precision_h',     QVariant_Double),   # Requerido prompt (SDH m)
            QgsField('precision_v',     QVariant_Double),
            QgsField('q',               QVariant_Int),
            QgsField('q_label',         QVariant_String),
            QgsField('metodo',          QVariant_String),   # Requerido prompt
            QgsField('ns',              QVariant_Int),
            QgsField('sdn_m',           QVariant_Double),
            QgsField('sde_m',           QVariant_Double),
            QgsField('sdu_m',           QVariant_Double),
            QgsField('base_nombre',     QVariant_String),   # Requerido prompt
            QgsField('base_corregida',  QVariant_String),   # Requerido prompt
            QgsField('base_delta_h',    QVariant_Double),   # Trazabilidad
            QgsField('base_delta_v',    QVariant_Double),
        ])
        layer.updateFields()

        # Datos de base para atributos
        base_nombre    = getattr(bc, 'fuente', 'N/A') if bc else 'N/A'
        base_corregida = 'SI' if (bc and bc.fue_corregida) else 'NO'
        delta_h = (bc.delta_horizontal_m or 0.0) if bc else 0.0
        delta_v = (bc.delta_vertical_m or 0.0) if bc else 0.0
        metodo  = p.mode.upper()

        # Determinar zona UTM ÚNICA para todo el levantamiento
        # desde el CRS del proyecto — NUNCA auto-detectar por punto
        # (un levantamiento que cruza meridiano de zona daría saltos)
        zona_fija = self._zona_utm_proyecto(stats)

        features = []
        for i, ep in enumerate(stats.epochs):
            if load_q and ep.q not in load_q:
                continue

            # Calcular UTM con la zona fija del proyecto
            try:
                este, norte, _ = self._conv.geo_to_utm(ep.lat, ep.lon, zona_fija)
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
        """Genera UN solo punto: la coordenada corregida.

        Estrategia de selección (prioriza calidad geodésica):
        - Si hay AL MENOS 1 época FIX → usar SOLO las FIX (centimétrico).
          Una sola FIX es geodésicamente superior a miles de FLOAT.
        - Si no hay FIX pero hay FLOAT → usar FLOAT (submétrico).
        - Si no hay ninguna → SINGLE (métrico).

        El promedio es PONDERADO por 1/sigma^2 (igual que TBC).
        """
        p = self.params
        bc = p.base_coords
        fix_ep = [e for e in stats.epochs if e.q == 1]
        flt_ep = [e for e in stats.epochs if e.q == 2]
        dgps_ep = [e for e in stats.epochs if e.q == 4]

        # ¿El usuario eligió modo DGPS submétrico?
        modo_dgps = 'dgps' in str(getattr(p, 'solution_type', ''))

        def _dispersion_m(eps):
            """Dispersión horizontal máxima (m) de un grupo de épocas."""
            if len(eps) < 2:
                return 0.0
            lats = [e.lat for e in eps]
            lons = [e.lon for e in eps]
            dlat = (max(lats) - min(lats)) * 111320.0
            dlon = ((max(lons) - min(lons)) * 111320.0
                    * math.cos(math.radians(sum(lats) / len(lats))))
            return math.sqrt(dlat**2 + dlon**2)

        def _filtrar_outliers(eps, umbral_m=0.5):
            """Filtra falsos fix puntuales por distancia a la MEDIANA.
            Evita que unos pocos outliers contaminen el promedio de
            cientos de épocas buenas (misma lógica que el modo ocupaciones)."""
            import statistics as _st
            if len(eps) < 3:
                return eps
            lat_med = _st.median(e.lat for e in eps)
            lon_med = _st.median(e.lon for e in eps)
            cos_lat = math.cos(math.radians(lat_med))
            buenas = [e for e in eps
                      if math.sqrt(((e.lat - lat_med) * 111320.0) ** 2
                                   + ((e.lon - lon_med) * 111320.0 * cos_lat) ** 2)
                      <= umbral_m]
            if len(buenas) < max(3, len(eps) * 0.3):
                return eps
            return buenas

        # VALIDACIÓN ANTI-FALSO-FIX: en estático, épocas FIX verdaderas
        # son consistentes a nivel cm. Si se dispersan >0.5 m, son
        # falsos fix (línea base larga / multipath) y NO deben usarse
        # como si fueran centimétricas.
        UMBRAL_FIX_M = 0.5
        confiable = True
        advertencia = ''

        # Filtrar falsos fix puntuales por mediana ANTES de evaluar.
        # Evita que outliers inflen la dispersión y arruinen el promedio.
        fix_filt = _filtrar_outliers(fix_ep, UMBRAL_FIX_M) if fix_ep else []

        if modo_dgps and dgps_ep:
            # Modo submétrico: la solución DGPS (código) es la esperada.
            # No hay ambigüedad → no hay falsos fix posibles.
            best, q_used, q_label = _filtrar_outliers(dgps_ep, 2.0), 4, 'SUBMÉTRICO DGPS'
        elif len(fix_filt) >= 4 and _dispersion_m(fix_filt) <= UMBRAL_FIX_M:
            best, q_used, q_label = fix_filt, 1, 'FIX'
        elif flt_ep:
            best, q_used, q_label = _filtrar_outliers(flt_ep, 1.0), 2, 'FLOAT'
            if fix_ep:
                advertencia = (f'{len(fix_ep)} épocas FIX descartadas por '
                               f'inconsistencia ({_dispersion_m(fix_ep):.1f} m '
                               f'de dispersión) — posibles falsos fix')
        elif dgps_ep:
            best, q_used, q_label = dgps_ep, 4, 'SUBMÉTRICO DGPS'
        elif stats.epochs:
            best, q_used, q_label = stats.epochs, 5, 'SINGLE'
        else:
            return None

        # Evaluar confiabilidad del grupo elegido
        disp_best = _dispersion_m(best)
        if q_label == 'FIX' and disp_best > UMBRAL_FIX_M:
            confiable = False
        elif q_label == 'FLOAT' and disp_best > 2.0:
            confiable = False
            advertencia = (advertencia + ' | ' if advertencia else '') + (
                f'FLOAT sin converger (dispersión {disp_best:.1f} m) — '
                f'resultado NO submétrico, revisar calidad de datos')
        elif q_label == 'SUBMÉTRICO DGPS' and disp_best > 3.0:
            # DGPS honesto puede llegar a ~1m; >3m indica datos muy ruidosos
            confiable = False
            advertencia = (advertencia + ' | ' if advertencia else '') + (
                f'DGPS con dispersión alta ({disp_best:.1f} m) — '
                f'precisión peor que submétrica, revisar datos')
        elif q_label == 'SINGLE':
            confiable = False

        if not confiable:
            q_label = q_label + ' (NO CONFIABLE)'
        try:
            from ...core.logger import log_warning
            if advertencia:
                log_warning(f'GNSS: {advertencia}')
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        n = len(best)

        # Promedio PONDERADO por 1/sigma^2 (TBC-style)
        def _wmean(vals_sigmas):
            pares = [(v, max(s, 0.001)) for v, s in vals_sigmas]
            pesos = [1.0/(s*s) for _, s in pares]
            sw = sum(pesos)
            if sw <= 0:
                return sum(v for v, _ in pares)/len(pares), None
            media = sum(v*w for (v, _), w in zip(pares, pesos))/sw
            return media, math.sqrt(1.0/sw)

        lat_avg, sig_lat = _wmean([(e.lat, e.sdn) for e in best])
        lon_avg, sig_lon = _wmean([(e.lon, e.sde) for e in best])
        h_avg,   sig_h   = _wmean([(e.h,   e.sdu) for e in best])

        # Dispersión real (desviación estándar de las épocas usadas)
        lat_std_m = math.sqrt(sum((e.lat - lat_avg)**2 for e in best) / n) * 111320
        lon_std_m = math.sqrt(sum((e.lon - lon_avg)**2 for e in best) / n) * 111320 * math.cos(math.radians(lat_avg))
        h_std     = math.sqrt(sum((e.h - h_avg)**2 for e in best) / n)
        # Sigmas de la media ponderada (en metros)
        sdn_avg = sig_lat if sig_lat else sum(e.sdn for e in best)/n
        sde_avg = sig_lon if sig_lon else sum(e.sde for e in best)/n
        sdu_avg = sig_h   if sig_h   else sum(e.sdu for e in best)/n
        ns_avg  = sum(e.ns for e in best) / n

        # Zona UTM fija desde CRS del proyecto (no auto por punto)
        try:
            zona = self._zona_utm_proyecto(stats)
            este, norte, _ = self._conv.geo_to_utm(lat_avg, lon_avg, zona)
        except Exception:
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
            QgsField('nombre',          QVariant_String),
            QgsField('lat_dd',          QVariant_Double),
            QgsField('lon_dd',          QVariant_Double),
            QgsField('este',            QVariant_Double),
            QgsField('norte',           QVariant_Double),
            QgsField('altura_elip',     QVariant_Double),
            QgsField('precision_h',     QVariant_Double),
            QgsField('precision_v',     QVariant_Double),
            QgsField('sigma_norte_m',   QVariant_Double),
            QgsField('sigma_este_m',    QVariant_Double),
            QgsField('sigma_altura_m',  QVariant_Double),
            QgsField('rtklib_sdn',      QVariant_Double),
            QgsField('rtklib_sde',      QVariant_Double),
            QgsField('rtklib_sdu',      QVariant_Double),
            QgsField('calidad',         QVariant_String),
            QgsField('q',               QVariant_Int),
            QgsField('n_epocas_total',  QVariant_Int),
            QgsField('n_epocas_usadas', QVariant_Int),
            QgsField('n_fix',           QVariant_Int),
            QgsField('n_float',         QVariant_Int),
            QgsField('pct_fix',         QVariant_Double),
            QgsField('sat_promedio',    QVariant_Double),
            QgsField('metodo',          QVariant_String),
            QgsField('base_nombre',     QVariant_String),
            QgsField('base_corregida',  QVariant_String),
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
            QgsField('epocas',  QVariant_Int),
            QgsField('metodo',  QVariant_String),
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
                opts.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
            else:
                opts.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile

            err, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer, path,
                QgsCoordinateTransformContext(), opts
            )
            results[fmt] = path if err == QgsVectorFileWriter.WriterError.NoError else f'ERROR: {msg}'

        return results
