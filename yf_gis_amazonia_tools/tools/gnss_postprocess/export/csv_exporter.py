# -*- coding: utf-8 -*-
"""
csv_exporter.py
Exporta los resultados del post-proceso a CSV con todos los atributos
definidos en el prompt: nombre, este, norte, altura, precision,
metodo, base_nombre, base_corregida + trazabilidad.
"""
import os
import csv
import math
from ..results.pos_parser import PosStats, Q_LABELS
from ..gnss_engine.coord_converter import BaseCoords, CoordConverter


class CSVExporter:
    """Exporta PosStats a CSV con coordenadas UTM calculadas."""

    def __init__(self):
        self._conv = CoordConverter()

    def export(self, stats: PosStats, params,
               out_dir: str, prefix: str) -> str:
        """
        Genera CSV con todos los atributos requeridos.
        Retorna ruta del archivo generado.
        """
        bc: BaseCoords = params.base_coords
        metodo         = params.mode.upper()
        base_nombre    = getattr(bc, 'fuente', 'N/A') if bc else 'N/A'
        base_corregida = ('SI' if (bc and bc.fue_corregida) else 'NO')
        delta_h        = (bc.delta_horizontal_m or 0.0) if bc else 0.0
        delta_v        = (bc.delta_vertical_m   or 0.0) if bc else 0.0
        proyecto       = params.project_name or prefix

        path = os.path.join(out_dir, prefix + '_coords.csv')

        fieldnames = [
            'idx', 'nombre', 'timestamp',
            'lat_dd', 'lon_dd',
            'este', 'norte', 'zona_utm',
            'altura_elip_m',
            'precision_h_m', 'precision_v_m',
            'q', 'q_label',
            'metodo',
            'ns',
            'sdn_m', 'sde_m', 'sdu_m',
            'base_nombre', 'base_corregida',
            'base_delta_h_m', 'base_delta_v_m',
            'proyecto',
        ]

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for i, ep in enumerate(stats.epochs):
                # UTM
                try:
                    este, norte, zona = self._conv.geo_to_utm(ep.lat, ep.lon)
                except Exception:
                    este, norte, zona = 0.0, 0.0, 'N/A'

                sdh = math.sqrt(ep.sdn**2 + ep.sde**2)

                writer.writerow({
                    'idx':            i + 1,
                    'nombre':         f'{proyecto}_{i+1:04d}',
                    'timestamp':      ep.timestamp,
                    'lat_dd':         round(ep.lat, 10),
                    'lon_dd':         round(ep.lon, 10),
                    'este':           round(este, 3),
                    'norte':          round(norte, 3),
                    'zona_utm':       zona,
                    'altura_elip_m':  round(ep.h, 4),
                    'precision_h_m':  round(sdh, 5),
                    'precision_v_m':  round(ep.sdu, 5),
                    'q':              ep.q,
                    'q_label':        ep.q_label,
                    'metodo':         metodo,
                    'ns':             ep.ns,
                    'sdn_m':          round(ep.sdn, 5),
                    'sde_m':          round(ep.sde, 5),
                    'sdu_m':          round(ep.sdu, 5),
                    'base_nombre':    base_nombre,
                    'base_corregida': base_corregida,
                    'base_delta_h_m': round(delta_h, 4),
                    'base_delta_v_m': round(delta_v, 4),
                    'proyecto':       proyecto,
                })

        return path

    def export_summary(self, stats: PosStats, params,
                       out_dir: str, prefix: str) -> str:
        """
        CSV de resumen: una sola fila con la coordenada media
        (útil para puntos estáticos).
        """
        bc  = params.base_coords
        path = os.path.join(out_dir, prefix + '_resumen.csv')

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'nombre', 'lat_dd', 'lon_dd', 'altura_m',
                'precision_h_m', 'precision_v_m',
                'fix_pct', 'float_pct', 'epocas_total',
                'rms_n', 'rms_e', 'rms_u',
                'metodo', 'base_corregida',
            ])
            sdh = 0.0
            if stats.mean_sdn and stats.mean_sde:
                sdh = math.sqrt(stats.mean_sdn**2 + stats.mean_sde**2)

            writer.writerow([
                params.out_prefix,
                round(stats.mean_lat or 0, 10),
                round(stats.mean_lon or 0, 10),
                round(stats.mean_h   or 0, 4),
                round(sdh, 5),
                round(stats.mean_sdu or 0, 5),
                round(stats.fix_pct, 2),
                round(stats.float_pct, 2),
                stats.total,
                round(stats.rms_n, 5),
                round(stats.rms_e, 5),
                round(stats.rms_u, 5),
                params.mode.upper(),
                'SI' if (bc and bc.fue_corregida) else 'NO',
            ])

        return path
