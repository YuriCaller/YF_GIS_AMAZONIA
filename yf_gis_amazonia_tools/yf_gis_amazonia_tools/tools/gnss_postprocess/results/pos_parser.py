# -*- coding: utf-8 -*-
"""
pos_parser.py
Parsea el archivo .pos generado por RTKLIB.
Clasifica épocas por calidad Q y calcula estadísticas.

Formato .pos (columnas):
  % (date) UTC/GPST, lat(deg), lon(deg), height(m), Q, ns,
    sdn(m), sde(m), sdu(m), sdne(m), sdeu(m), sdun(m), age(s), ratio
"""
import os
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Calidad RTKLIB
Q_LABELS = {
    1: 'FIX',
    2: 'FLOAT',
    3: 'SBAS',
    4: 'SINGLE',
    5: 'DGPS',
    6: 'PPP',
}
Q_COLORS_HEX = {
    1: '#00c853',   # verde Fix
    2: '#ffd600',   # amarillo Float
    3: '#ff6d00',   # naranja SBAS
    4: '#d50000',   # rojo Single
    5: '#e65100',   # naranja oscuro DGPS
    6: '#6200ea',   # morado PPP
}


@dataclass
class Epoch:
    """Una época del archivo .pos."""
    timestamp: str
    lat:   float
    lon:   float
    h:     float
    q:     int
    ns:    int
    sdn:   float
    sde:   float
    sdu:   float
    sdne:  float = 0.0
    sdeu:  float = 0.0
    sdun:  float = 0.0
    age:   float = 0.0
    ratio: float = 0.0

    @property
    def q_label(self) -> str:
        return Q_LABELS.get(self.q, f'Q={self.q}')

    @property
    def sdh(self) -> float:
        """Desviación estándar horizontal 2D."""
        return math.sqrt(self.sdn**2 + self.sde**2)

    @property
    def q_color(self) -> str:
        return Q_COLORS_HEX.get(self.q, '#999999')


@dataclass
class PosStats:
    """Estadísticas completas del .pos."""
    epochs: List[Epoch] = field(default_factory=list)
    total:  int = 0

    # Por calidad
    count_q: Dict[int, int] = field(default_factory=dict)

    # RMS globales
    rms_n: float = 0.0
    rms_e: float = 0.0
    rms_u: float = 0.0

    # Coordenada promedio de épocas Fix (para estático)
    mean_lat: Optional[float] = None
    mean_lon: Optional[float] = None
    mean_h:   Optional[float] = None
    mean_sdn: Optional[float] = None
    mean_sde: Optional[float] = None
    mean_sdu: Optional[float] = None

    @property
    def fix_count(self):   return self.count_q.get(1, 0)
    @property
    def float_count(self): return self.count_q.get(2, 0)
    @property
    def single_count(self):return self.count_q.get(4, 0)
    @property
    def ppp_count(self):   return self.count_q.get(6, 0)

    @property
    def fix_pct(self):
        return self.fix_count / max(self.total, 1) * 100
    @property
    def float_pct(self):
        return self.float_count / max(self.total, 1) * 100
    @property
    def ppp_pct(self):
        return self.ppp_count / max(self.total, 1) * 100

    def as_dict(self) -> dict:
        return {
            'total': self.total,
            'fix':   self.fix_count,
            'float': self.float_count,
            'single': self.single_count,
            'ppp':   self.ppp_count,
            'fix_pct':   self.fix_pct,
            'float_pct': self.float_pct,
            'ppp_pct':   self.ppp_pct,
            'rms_n': self.rms_n,
            'rms_e': self.rms_e,
            'rms_u': self.rms_u,
            'mean_lat': self.mean_lat,
            'mean_lon': self.mean_lon,
            'mean_h':   self.mean_h,
            'mean_sdn': self.mean_sdn,
            'mean_sde': self.mean_sde,
            'mean_sdu': self.mean_sdu,
            'epochs': [
                {'lat': ep.lat, 'lon': ep.lon, 'h': ep.h,
                 'q': ep.q, 'ns': ep.ns,
                 'sdn': ep.sdn, 'sde': ep.sde, 'sdu': ep.sdu,
                 'sdh': ep.sdh, 'timestamp': ep.timestamp}
                for ep in self.epochs
            ]
        }


class PosParser:
    """Parsea el archivo .pos y retorna PosStats + dict compatible."""

    def parse(self, pos_file: str) -> dict:
        """Parsea y retorna dict (compatible con código anterior)."""
        stats = self.parse_full(pos_file)
        return stats.as_dict()

    def parse_full(self, pos_file: str) -> PosStats:
        stats = PosStats()
        if not os.path.isfile(pos_file):
            return stats

        epochs = []
        count_q = {}

        with open(pos_file, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.startswith('%') or not line.strip():
                    continue
                ep = self._parse_line(line)
                if ep is None:
                    continue
                epochs.append(ep)
                count_q[ep.q] = count_q.get(ep.q, 0) + 1

        stats.epochs  = epochs
        stats.total   = len(epochs)
        stats.count_q = count_q

        if epochs:
            stats.rms_n = self._rms([e.sdn for e in epochs])
            stats.rms_e = self._rms([e.sde for e in epochs])
            stats.rms_u = self._rms([e.sdu for e in epochs])

            # Promedio de épocas FIX (para informe de punto estático)
            fix_epochs = [e for e in epochs if e.q == 1]
            if not fix_epochs:
                # PPP: usar q=6
                fix_epochs = [e for e in epochs if e.q == 6]
            if fix_epochs:
                stats.mean_lat = sum(e.lat for e in fix_epochs) / len(fix_epochs)
                stats.mean_lon = sum(e.lon for e in fix_epochs) / len(fix_epochs)
                stats.mean_h   = sum(e.h   for e in fix_epochs) / len(fix_epochs)
                stats.mean_sdn = self._rms([e.sdn for e in fix_epochs])
                stats.mean_sde = self._rms([e.sde for e in fix_epochs])
                stats.mean_sdu = self._rms([e.sdu for e in fix_epochs])

        return stats

    @staticmethod
    def _parse_line(line: str) -> Optional[Epoch]:
        parts = line.split()
        if len(parts) < 10:
            return None
        try:
            # Formato: date time lat lon h Q ns sdn sde sdu [sdne sdeu sdun age ratio]
            ts  = f'{parts[0]} {parts[1]}'
            lat = float(parts[2])
            lon = float(parts[3])
            h   = float(parts[4])
            q   = int(parts[5])
            ns  = int(parts[6])
            sdn = float(parts[7])
            sde = float(parts[8])
            sdu = float(parts[9])
            sdne = float(parts[10]) if len(parts) > 10 else 0.0
            sdeu = float(parts[11]) if len(parts) > 11 else 0.0
            sdun = float(parts[12]) if len(parts) > 12 else 0.0
            age  = float(parts[13]) if len(parts) > 13 else 0.0
            ratio= float(parts[14]) if len(parts) > 14 else 0.0
            return Epoch(ts, lat, lon, h, q, ns, sdn, sde, sdu, sdne, sdeu, sdun, age, ratio)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _rms(vals: list) -> float:
        if not vals:
            return 0.0
        return math.sqrt(sum(x**2 for x in vals) / len(vals))
