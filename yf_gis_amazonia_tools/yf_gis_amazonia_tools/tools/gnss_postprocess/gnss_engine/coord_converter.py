# -*- coding: utf-8 -*-
"""
coord_converter.py
Conversiones geodésicas precisas usando pyproj.
Soporta: UTM ↔ Geográficas ↔ Cartesianas ECEF
Sistema de referencia: WGS84 / SIRGAS 2000 (compatibles a efectos prácticos)

DECISIÓN DE DISEÑO: Se usa pyproj >= 2.6 (incluido en QGIS 3.16+).
SIRGAS 2000 se trata como WGS84 (diferencia < 1mm, aceptable en campo).
"""
from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class BaseCoords:
    """Coordenadas de la base con metadata de trazabilidad."""
    lat_dd: float           # Latitud decimal (°), negativo = Sur
    lon_dd: float           # Longitud decimal (°), negativo = Oeste
    h_elip: float           # Altura elipsoidal (m)
    datum: str = 'WGS84'
    fuente: str = 'manual'  # 'manual', 'rinex_header', 'archivo'
    zona_utm: Optional[str] = None
    este_utm: Optional[float] = None
    norte_utm: Optional[float] = None
    # Trazabilidad: coords originales del RINEX header
    rinex_lat: Optional[float] = None
    rinex_lon: Optional[float] = None
    rinex_h: Optional[float] = None

    @property
    def fue_corregida(self) -> bool:
        """True si las coords difieren del header RINEX."""
        if self.rinex_lat is None:
            return False
        tol = 1e-7  # ~1 cm en latitud
        return (abs(self.lat_dd - self.rinex_lat) > tol or
                abs(self.lon_dd - self.rinex_lon) > tol or
                abs(self.h_elip - self.rinex_h) > 0.001)

    @property
    def delta_horizontal_m(self) -> Optional[float]:
        """Diferencia horizontal entre coords IGN y RINEX header (metros)."""
        if self.rinex_lat is None:
            return None
        dlat = math.radians(self.lat_dd - self.rinex_lat) * 6371000
        dlon = (math.radians(self.lon_dd - self.rinex_lon) *
                6371000 * math.cos(math.radians(self.lat_dd)))
        return math.sqrt(dlat**2 + dlon**2)

    @property
    def delta_vertical_m(self) -> Optional[float]:
        if self.rinex_h is None:
            return None
        return abs(self.h_elip - self.rinex_h)


class CoordConverter:
    """Conversiones geodésicas. Requiere pyproj >= 2.6."""

    # Zona UTM por defecto para Perú (18S y 19S cubren Madre de Dios)
    PERU_ZONES = {
        '17S': 32717, '18S': 32718, '19S': 32719,
        '17N': 32617, '18N': 32618, '19N': 32619,
    }

    def __init__(self):
        try:
            from pyproj import Transformer, CRS
            self._Transformer = Transformer
            self._CRS = CRS
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    # ──────────────────────────────────────────────
    # UTM → Geográficas WGS84
    # ──────────────────────────────────────────────
    def utm_to_geo(self, este: float, norte: float, zona: str,
                   h_elip: float = 0.0) -> tuple:
        """
        Convierte UTM a lat/lon WGS84 decimal.
        zona: '18S', '19S', '18N', etc.
        Retorna: (lat_dd, lon_dd, h_elip)
        """
        if not self._available:
            raise RuntimeError('pyproj no disponible en este entorno.')

        epsg = self.PERU_ZONES.get(zona.upper())
        if epsg is None:
            raise ValueError(f'Zona UTM no reconocida: {zona}. '
                             f'Válidas: {list(self.PERU_ZONES.keys())}')

        t = self._Transformer.from_crs(
            f'EPSG:{epsg}', 'EPSG:4326', always_xy=True
        )
        lon, lat = t.transform(este, norte)
        return float(lat), float(lon), float(h_elip)

    # ──────────────────────────────────────────────
    # Geográficas → UTM
    # ──────────────────────────────────────────────
    def geo_to_utm(self, lat_dd: float, lon_dd: float,
                   zona: Optional[str] = None) -> tuple:
        """
        Convierte lat/lon WGS84 a UTM.
        Si zona=None, calcula automáticamente.
        Retorna: (este, norte, zona_str)
        """
        if not self._available:
            raise RuntimeError('pyproj no disponible en este entorno.')

        if zona is None:
            zona = self._auto_zona(lat_dd, lon_dd)

        epsg = self.PERU_ZONES.get(zona.upper())
        if epsg is None:
            # Calcular EPSG genérico
            band = int((lon_dd + 180) / 6) + 1
            epsg = 32600 + band if lat_dd >= 0 else 32700 + band

        t = self._Transformer.from_crs(
            'EPSG:4326', f'EPSG:{epsg}', always_xy=True
        )
        este, norte = t.transform(lon_dd, lat_dd)
        return float(este), float(norte), zona

    # ──────────────────────────────────────────────
    # Geográficas → ECEF (Cartesianas)
    # ──────────────────────────────────────────────
    def geo_to_ecef(self, lat_dd: float, lon_dd: float,
                    h_elip: float) -> tuple:
        """Retorna (X, Y, Z) en metros ECEF WGS84."""
        if not self._available:
            # Fórmula manual como fallback
            return self._manual_geo_to_ecef(lat_dd, lon_dd, h_elip)
        t = self._Transformer.from_crs(
            'EPSG:4326',
            self._CRS.from_proj4('+proj=geocent +datum=WGS84'),
            always_xy=True
        )
        X, Y, Z = t.transform(lon_dd, lat_dd, h_elip)
        return float(X), float(Y), float(Z)

    # ──────────────────────────────────────────────
    # ECEF → Geográficas
    # ──────────────────────────────────────────────
    def ecef_to_geo(self, X: float, Y: float, Z: float) -> tuple:
        """Retorna (lat_dd, lon_dd, h_elip)."""
        if not self._available:
            return self._manual_ecef_to_geo(X, Y, Z)
        t = self._Transformer.from_crs(
            self._CRS.from_proj4('+proj=geocent +datum=WGS84'),
            'EPSG:4326',
            always_xy=True
        )
        lon, lat, h = t.transform(X, Y, Z)
        return float(lat), float(lon), float(h)

    # ──────────────────────────────────────────────
    # DMS → Decimal
    # ──────────────────────────────────────────────
    @staticmethod
    def dms_to_dd(degrees: int, minutes: int, seconds: float,
                  hemisphere: str) -> float:
        """Convierte Grados°Minutos'Segundos" a decimal."""
        dd = abs(int(degrees)) + int(minutes) / 60.0 + float(seconds) / 3600.0
        if str(hemisphere).upper() in ('S', 'W'):
            dd = -dd
        return dd

    # ──────────────────────────────────────────────
    # INTERNOS
    # ──────────────────────────────────────────────
    @staticmethod
    def _auto_zona(lat_dd: float, lon_dd: float) -> str:
        band = int((lon_dd + 180) / 6) + 1
        hem = 'N' if lat_dd >= 0 else 'S'
        return f'{band}{hem}'

    @staticmethod
    def _manual_geo_to_ecef(lat, lon, h):
        """Fórmula directa WGS84 sin pyproj."""
        a = 6378137.0
        f = 1 / 298.257223563
        e2 = 2 * f - f**2
        lat_r = math.radians(lat)
        lon_r = math.radians(lon)
        N = a / math.sqrt(1 - e2 * math.sin(lat_r)**2)
        X = (N + h) * math.cos(lat_r) * math.cos(lon_r)
        Y = (N + h) * math.cos(lat_r) * math.sin(lon_r)
        Z = (N * (1 - e2) + h) * math.sin(lat_r)
        return X, Y, Z

    @staticmethod
    def _manual_ecef_to_geo(X, Y, Z):
        """Algoritmo iterativo de Bowring."""
        a = 6378137.0
        f = 1 / 298.257223563
        e2 = 2 * f - f**2
        lon = math.atan2(Y, X)
        p   = math.sqrt(X**2 + Y**2)
        lat = math.atan2(Z, p * (1 - e2))
        for _ in range(10):
            N   = a / math.sqrt(1 - e2 * math.sin(lat)**2)
            lat = math.atan2(Z + e2 * N * math.sin(lat), p)
        N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
        h = p / math.cos(lat) - N if abs(math.cos(lat)) > 1e-10 else abs(Z) / math.sin(lat) - N * (1 - e2)
        return math.degrees(lat), math.degrees(lon), h
