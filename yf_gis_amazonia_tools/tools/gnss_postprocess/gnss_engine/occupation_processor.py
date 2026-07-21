# -*- coding: utf-8 -*-
"""
Procesador de ocupaciones (estilo TBC / Pathfinder).

Estrategia (Opción A, la de TBC):
  1. Procesa el RINEX continuo UNA vez en modo KINEMATIC contra la base.
     Así RTKLIB mantiene la continuidad de ambigüedades entre puntos.
  2. Lee las ocupaciones del RINEX (occupation_parser).
  3. Corta el .pos por la ventana de tiempo de cada ocupación.
  4. Calcula la solución estática de cada punto SOLO con sus épocas,
     con validación anti-falso-fix POR PUNTO (sin promediar entre puntos).
  5. Reporta el error individual de cada toma (tipo solución, RMS,
     sigmas, % fix, dispersión) — el usuario decide cuáles aceptar.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os
import math
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from qgis.PyQt.QtCore import QThread, pyqtSignal

from .occupation_parser import parse_occupations, Occupation


@dataclass
class OccResult:
    name: str
    q_label: str          # FIX / FLOAT / SUBMÉTRICO / ... (NO CONFIABLE)
    q_code: int
    lat: float
    lon: float
    h: float
    este: float = 0.0
    norte: float = 0.0
    n_used: int = 0
    n_total: int = 0
    fix_pct: float = 0.0
    sigma_h: float = 0.0      # m
    sigma_v: float = 0.0      # m
    dispersion_h: float = 0.0  # m, entre épocas usadas
    pdop: float = 0.0
    ant_height: float = 0.0
    confiable: bool = True
    duration_s: float = 0.0
    archivo: str = ''


# --- Tolerancia para emparejar épocas .pos con ventanas de ocupación ---
_MARGIN_S = 2.0


def _gpst_to_dt(week, tow):
    """GPS week + time of week → datetime UTC (sin leap seconds, suficiente
    para emparejar ventanas porque el RINEX y el .pos usan el mismo GPST)."""
    epoch = datetime(1980, 1, 6)
    return epoch + timedelta(weeks=week, seconds=tow)


class OccupationProcessor(QThread):
    log            = pyqtSignal(str, str)
    progress       = pyqtSignal(int)
    finished_occ   = pyqtSignal(list)   # List[OccResult]

    def __init__(self, params, plugin_dir, rover_path):
        super().__init__()
        self.params = params
        self.plugin_dir = plugin_dir
        self.rover_path = rover_path

    # ---- utilidades de cálculo ----
    @staticmethod
    def _dispersion_m(epochs):
        if len(epochs) < 2:
            return 0.0
        lats = [e['lat'] for e in epochs]
        lons = [e['lon'] for e in epochs]
        latm = sum(lats) / len(lats)
        dlat = (max(lats) - min(lats)) * 111320.0
        dlon = (max(lons) - min(lons)) * 111320.0 * math.cos(math.radians(latm))
        return math.sqrt(dlat ** 2 + dlon ** 2)

    @staticmethod
    def _filtrar_outliers(epochs, umbral_m=0.5):
        """Filtra falsos fix puntuales por distancia a la MEDIANA.

        En estático, la mayoría de épocas buenas se agrupan; unos pocos
        falsos fix aparecen lejos. Usar la mediana (robusta) como centro
        y descartar lo que esté más lejos del umbral evita que 5-10
        outliers contaminen el promedio de cientos de épocas buenas.
        Devuelve (épocas_filtradas, n_descartadas).
        """
        import statistics
        if len(epochs) < 3:
            return epochs, 0
        lat_med = statistics.median(e['lat'] for e in epochs)
        lon_med = statistics.median(e['lon'] for e in epochs)
        cos_lat = math.cos(math.radians(lat_med))
        buenas = []
        for e in epochs:
            d = math.sqrt(((e['lat'] - lat_med) * 111320.0) ** 2
                          + ((e['lon'] - lon_med) * 111320.0 * cos_lat) ** 2)
            if d <= umbral_m:
                buenas.append(e)
        # Si el filtro deja muy pocas, no era ruido sino dispersión real
        if len(buenas) < max(3, len(epochs) * 0.3):
            return epochs, 0
        return buenas, len(epochs) - len(buenas)

    @staticmethod
    def _wmean(vals, sigmas):
        pares = [(v, max(s, 0.001)) for v, s in zip(vals, sigmas)]
        pesos = [1.0 / (s * s) for _, s in pares]
        sw = sum(pesos)
        if sw <= 0:
            return sum(v for v, _ in pares) / len(pares), None
        media = sum(v * w for (v, _), w in zip(pares, pesos)) / sw
        return media, math.sqrt(1.0 / sw)

    def run(self):
        try:
            self._run()
        except Exception as ex:
            import traceback
            self.log.emit(f'❌ Error en ocupaciones: {ex}', 'error')
            traceback.print_exc()
            self.finished_occ.emit([])

    def procesar_sincrono(self):
        """Ejecuta el procesamiento y DEVUELVE la lista de OccResult.
        Para uso desde el batch (sin hilo). No emite finished_occ."""
        return self._procesar()

    def _run(self):
        resultados = self._procesar()
        self.finished_occ.emit(resultados)

    def _procesar(self):
        import dataclasses
        from .ppk_processor import PPKProcessor
        from ..results.pos_parser import PosParser

        # 1. Detectar ocupaciones
        occs = parse_occupations(self.rover_path)
        if not occs:
            # Sin event flags: tratar todo el archivo como UNA ocupación
            # (archivo cinemático puro o estático de un punto)
            self.log.emit('Sin marcas de ocupación — procesando como punto único', 'info')
            return self._procesar_punto_unico()
        self.log.emit(f'📍 {len(occs)} ocupaciones detectadas en el archivo', 'info')

        # 2. Procesar TODO el archivo en KINEMATIC (continuidad de ambigüedades)
        kin_params = dataclasses.replace(
            self.params, solution_type='kinematic',
            out_prefix=self.params.out_prefix + '_kin')
        self.log.emit('⚙ Procesando archivo completo en modo cinemático...', 'info')
        proc = PPKProcessor(kin_params, self.plugin_dir)
        proc.log.connect(self.log)
        pos_path = os.path.join(kin_params.out_dir, kin_params.out_prefix + '.pos')
        proc.run()
        # Propagar trazabilidad para el informe (comando RTKLIB, binario, .pos)
        self.last_cmd = getattr(proc, 'last_cmd', '')
        self.last_binary = getattr(proc, 'last_binary', '')
        self.last_pos = pos_path

        if not os.path.isfile(pos_path):
            self.log.emit('❌ No se generó el .pos cinemático', 'error')
            self.finished_occ.emit([])
            return

        # 3. Leer todas las épocas del .pos con su tiempo
        epochs = self._read_pos_epochs(pos_path)
        self.log.emit(f'📊 {len(epochs)} épocas en la solución cinemática', 'info')

        # 4. Cortar por ventana de cada ocupación y resolver
        resultados = []
        modo_dgps = 'dgps' in str(getattr(self.params, 'solution_type', ''))
        for idx, occ in enumerate(occs, 1):
            self.progress.emit(int(idx / len(occs) * 100))
            res = self._solve_occupation(occ, epochs, modo_dgps)
            resultados.append(res)
            self.log.emit(
                f'  {occ.name:<8} → {res.q_label} | '
                f'{res.n_used}/{res.n_total} ép | σH={res.sigma_h*100:.1f}cm | '
                f'disp={res.dispersion_h*100:.1f}cm',
                'ok' if res.confiable else 'warn')

        return resultados

    def _procesar_punto_unico(self):
        """Procesa un archivo SIN ocupaciones como un solo punto.
        Usa modo estático y trata todas las épocas como una ocupación,
        con el mismo filtrado de outliers."""
        import dataclasses
        from .ppk_processor import PPKProcessor
        from .occupation_parser import Occupation

        est_params = dataclasses.replace(
            self.params, solution_type='static',
            out_prefix=self.params.out_prefix + '_pt')
        self.log.emit('Procesando archivo en estático...', 'info')
        proc = PPKProcessor(est_params, self.plugin_dir)
        proc.log.connect(self.log)
        pos_path = os.path.join(est_params.out_dir, est_params.out_prefix + '.pos')
        proc.run()
        self.last_cmd = getattr(proc, 'last_cmd', '')
        self.last_binary = getattr(proc, 'last_binary', '')
        self.last_pos = pos_path
        if not os.path.isfile(pos_path):
            return []
        epochs = self._read_pos_epochs(pos_path)
        if not epochs:
            return []
        # Una ocupación que abarca todas las épocas
        occ = Occupation(name=self.params.out_prefix)
        occ.t_start = epochs[0]['t']
        occ.t_end = epochs[-1]['t']
        modo_dgps = 'dgps' in str(getattr(self.params, 'solution_type', ''))
        res = self._solve_occupation(occ, epochs, modo_dgps)
        # Este archivo NO tiene event flags de ocupación: es un tramo
        # cinemático/tránsito, no un punto topográfico. Se marca para que
        # el usuario no lo confunda con un vértice válido.
        res.q_label = 'SIN OCUPACIÓN (tramo cinemático)'
        res.confiable = False
        self.log.emit(f'  ⚠ {occ.name}: archivo sin ocupación marcada — '
                      f'tramo cinemático, NO es un punto topográfico '
                      f'(disp={res.dispersion_h*100:.1f}cm)', 'warn')
        return [res]

    def _read_pos_epochs(self, pos_path):
        """Lee el .pos y devuelve lista de dicts con tiempo y posición."""
        epochs = []
        with open(pos_path, 'r', errors='replace') as f:
            for line in f:
                if line.startswith('%') or not line.strip():
                    continue
                p = line.split()
                if len(p) < 9:
                    continue
                try:
                    week = int(p[0]); tow = float(p[1])
                    dt = _gpst_to_dt(week, tow)
                    epochs.append({
                        't': dt,
                        'lat': float(p[2]), 'lon': float(p[3]), 'h': float(p[4]),
                        'q': int(p[5]),
                        'ns': int(float(p[6])),
                        'sdn': float(p[7]),
                        'sde': float(p[8]),
                        'sdu': float(p[9]),
                    })
                except (ValueError, IndexError):
                    continue  # nosec B112 - entrada malformada: se omite a proposito
        return epochs

    def _solve_occupation(self, occ: Occupation, all_epochs, modo_dgps):
        # Ventana temporal de la ocupación (con margen)
        t0 = occ.t_start - timedelta(seconds=_MARGIN_S) if occ.t_start else None
        t1 = occ.t_end + timedelta(seconds=_MARGIN_S) if occ.t_end else None
        win = [e for e in all_epochs
               if t0 and t1 and t0 <= e['t'] <= t1] if t0 else []

        res = OccResult(name=occ.name, q_label='SIN DATOS', q_code=5,
                        lat=0, lon=0, h=0, ant_height=occ.ant_height,
                        n_total=len(win), duration_s=occ.duration_s,
                        confiable=False)
        if not win:
            return res

        fix = [e for e in win if e['q'] == 1]
        flt = [e for e in win if e['q'] == 2]
        dgps = [e for e in win if e['q'] == 4]

        UMBRAL_FIX = 0.5
        MIN_FIX_EPOCHS = 4    # ocupaciones de ~7s: 4+ épocas FIX basta
        SIGMA_MAX_FIX = 0.10  # 10 cm: un FIX real no tiene sigma mayor

        # FIX válido = suficientes épocas Y consistentes tras filtrar outliers
        fix_filtrado, _ = self._filtrar_outliers(fix, UMBRAL_FIX) if fix else ([], 0)
        fix_valido = (len(fix_filtrado) >= MIN_FIX_EPOCHS
                      and self._dispersion_m(fix_filtrado) <= UMBRAL_FIX)

        if modo_dgps and dgps:
            best, code, label = dgps, 4, 'SUBMÉTRICO DGPS'
        elif fix_valido:
            best, code, label = fix, 1, 'FIX'
        elif flt:
            best, code, label = flt, 2, 'FLOAT'
        elif dgps:
            best, code, label = dgps, 4, 'SUBMÉTRICO DGPS'
        elif fix:
            best, code, label = fix, 1, 'FIX'
        else:
            best, code, label = win, 5, 'SINGLE'

        # Filtrar falsos fix puntuales (outliers vs mediana) antes de promediar.
        # Esto evita que unos pocos outliers contaminen cientos de épocas buenas.
        umbral_filtro = 0.5 if code == 1 else (2.0 if code == 4 else 1.0)
        best, n_outliers = self._filtrar_outliers(best, umbral_filtro)

        disp = self._dispersion_m(best)

        # Media ponderada SOLO de las épocas de esta ocupación
        lat, slat = self._wmean([e['lat'] for e in best], [e['sdn'] for e in best])
        lon, slon = self._wmean([e['lon'] for e in best], [e['sde'] for e in best])
        h, sh = self._wmean([e['h'] for e in best], [e['sdu'] for e in best])
        sigma_h = math.sqrt((slat or 0)**2 + (slon or 0)**2)

        # ── Evaluación de confiabilidad (multicriterio) ──
        confiable = True
        if label == 'FIX':
            if len(best) < MIN_FIX_EPOCHS:
                confiable = False   # muy pocas épocas FIX
            elif disp > UMBRAL_FIX:
                confiable = False   # FIX dispersos = falsos fix
            elif sigma_h > SIGMA_MAX_FIX:
                confiable = False   # sigma incompatible con un FIX real
        elif label == 'FLOAT':
            if disp > 2.0 or sigma_h > 1.0:
                confiable = False
        elif label == 'SUBMÉTRICO DGPS':
            if disp > 3.0 or sigma_h > 2.0:
                confiable = False
        elif label == 'SINGLE':
            confiable = False

        res.lat, res.lon, res.h = lat, lon, h
        res.q_code = code
        res.q_label = label + ('' if confiable else ' (NO CONFIABLE)')
        res.n_used = len(best)
        res.fix_pct = len(fix) / len(win) * 100 if win else 0
        res.sigma_h = sigma_h
        res.sigma_v = sh or 0
        res.dispersion_h = disp
        res.confiable = confiable

        # UTM
        try:
            from pyproj import Transformer
            crs = self.params.base_coords
            zona_epsg = 'EPSG:32719'  # UTM 19S por defecto (Madre de Dios)
            t = Transformer.from_crs('EPSG:4326', zona_epsg, always_xy=True)
            res.este, res.norte = t.transform(lon, lat)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        return res
