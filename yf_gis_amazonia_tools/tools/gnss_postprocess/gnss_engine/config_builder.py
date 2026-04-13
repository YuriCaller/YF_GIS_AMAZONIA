# -*- coding: utf-8 -*-
"""
config_builder.py
Genera archivos .conf de RTKLIB de forma completamente dinámica.
NO usa plantillas estáticas. Cada parámetro se justifica.

RTKLIB rnx2rtkp parámetros de referencia:
  https://www.rtklib.com/prog/manual_2.4.2.pdf (sección 5.2)
"""
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from ..gnss_engine.coord_converter import BaseCoords


@dataclass
class ProcessingParams:
    """Parámetros completos de procesamiento. Sin valores críticos por defecto."""

    # ── Modo ──────────────────────────────────────
    mode: str                        # 'ppk' | 'ppp'
    solution_type: str               # 'static' | 'kinematic' | 'movbase' | 'ppp-static' | 'ppp-kinematic'
    kalman_filter: str               # 'forward' | 'backward' | 'combined'

    # ── Archivos rover ────────────────────────────
    rinex_rover: str
    nav_file: str

    # ── Archivos base (PPK) ───────────────────────
    rinex_base: Optional[str] = None
    base_coords: Optional[BaseCoords] = None  # OBLIGATORIO en PPK

    # ── Archivos precisos (PPP) ───────────────────
    sp3_file: Optional[str] = None
    clk_file: Optional[str] = None
    ionex_file: Optional[str] = None
    gnav_file: Optional[str] = None

    # ── Parámetros geodésicos ──────────────────────
    freq: int = 2                    # 1=L1, 2=L1+L2, 3=L1+L2+L5
    elev_mask_deg: float = 10.0
    snr_mask_dbhz: int = 0
    navsys: int = 0x07               # GPS+GLONASS+Galileo por defecto

    # ── Salida ────────────────────────────────────
    out_dir: str = ''
    out_prefix: str = 'gnss_result'

    # ── Metadata del proyecto ─────────────────────
    project_name: str = ''
    operator: str = ''
    receptor: str = ''
    antena: str = ''
    serial_receptor: str = ''
    notas: str = ''


class ConfigBuilder:
    """
    Genera el archivo .conf de RTKLIB de forma dinámica.
    Cada sección es un método separado para facilitar overrides.
    """

    # Mapeo interno modo → código RTKLIB pos1-posmode
    _POSMODE = {
        'static':        0,
        'kinematic':     1,
        'movbase':       2,
        'fixed':         3,
        'ppp-static':    4,
        'ppp-kinematic': 5,
    }
    _SOLTYPE = {
        'forward':  0,
        'backward': 1,
        'combined': 2,
    }

    def build(self, params: ProcessingParams) -> str:
        """
        Genera el contenido completo del .conf como string.
        Llama a secciones ordenadas.
        """
        sections = [
            self._header_comment(params),
            self._pos1_section(params),
            self._pos2_section(params),
            self._out_section(),
            self._stats_section(),
            self._ant_section(params),
            self._misc_section(),
        ]
        return '\n'.join(sections)

    def write(self, params: ProcessingParams) -> str:
        """Escribe el .conf en disco y retorna la ruta."""
        content = self.build(params)
        path = os.path.join(
            params.out_dir,
            params.out_prefix + '_rtklib.conf'
        )
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    # ══════════════════════════════════════════════
    # SECCIONES
    # ══════════════════════════════════════════════

    def _header_comment(self, p: ProcessingParams) -> str:
        import datetime
        return (
            f'# GNSS Post-Process Plugin v2.0 — Configuración dinámica\n'
            f'# Modo: {p.mode.upper()} | Solución: {p.solution_type}\n'
            f'# Proyecto: {p.project_name}\n'
            f'# Generado: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'# Operador: {p.operator}\n'
        )

    def _pos1_section(self, p: ProcessingParams) -> str:
        posmode = self._POSMODE.get(p.solution_type, 0)
        soltype = self._SOLTYPE.get(p.kalman_filter, 0)

        # Modelo ionosférico: IONEX si hay archivo, broadcast si no
        ionoopt = 8 if p.ionex_file else 1   # 8=IONEX, 1=broadcast

        # Efemérides: SP3 si hay archivo
        sateph  = 1 if p.sp3_file else 0     # 1=precise, 0=broadcast

        # Navsys: suma de bits (GPS=0x01, SBAS=0x02, GLO=0x04, GAL=0x08, BDS=0x20)
        navsys = p.navsys

        lines = [
            '',
            '# ── Posicionamiento ─────────────────────────────',
            f'pos1-posmode       ={posmode}',
            f'pos1-frequency     ={p.freq}',
            f'pos1-soltype       ={soltype}',
            f'pos1-elmask        ={p.elev_mask_deg:.1f}',
            f'pos1-snrmask_r     ={p.snr_mask_dbhz}',
            f'pos1-snrmask_b     ={p.snr_mask_dbhz}',
            f'pos1-dynamics      =0',
            f'pos1-tidecorr      =0',
            f'pos1-ionoopt       ={ionoopt}',
            f'pos1-tropopt       =2',    # Saastamoinen (estándar catastral)
            f'pos1-sateph        ={sateph}',
            f'pos1-posopt1       =0',
            f'pos1-posopt2       =0',
            f'pos1-posopt3       =0',
            f'pos1-posopt4       =0',
            f'pos1-posopt5       =0',
            f'pos1-posopt6       =0',
            f'pos1-exclsats      =',
            f'pos1-navsys        ={navsys}',
        ]
        return '\n'.join(lines)

    def _pos2_section(self, p: ProcessingParams) -> str:
        # Modo AR diferente para PPP (no aplica fix de ambigüedad)
        armode  = 0 if 'ppp' in p.solution_type else 3   # 3=fix-and-hold
        gloar   = 0 if 'ppp' in p.solution_type else 1

        lines = [
            '',
            '# ── Resolución de ambigüedad ────────────────────',
            f'pos2-armode        ={armode}',
            f'pos2-gloarmode     ={gloar}',
            f'pos2-bdsarmode     =1',
            f'pos2-arthres       =3.0',
            f'pos2-arlockcnt     =0',
            f'pos2-arminfix      =10',
            f'pos2-armaxiter     =1',
            f'pos2-elmaskhold    =0.0',
            f'pos2-aroutcnt      =5',
            f'pos2-maxage        =30.0',
            f'pos2-syncsol       =0',
            f'pos2-slipthres     =0.05',
            f'pos2-rejionno      =30.0',
            f'pos2-rejgdop       =30.0',
            f'pos2-niter         =1',
            f'pos2-baselen       =0.0',
            f'pos2-basesig       =0.0',
        ]
        return '\n'.join(lines)

    def _out_section(self) -> str:
        lines = [
            '',
            '# ── Formato de salida ───────────────────────────',
            'out-solformat      =llh',       # lat/lon/h para parseo posterior
            'out-outhead        =on',
            'out-outopt         =on',
            'out-outvel         =off',
            'out-timesys        =gpst',
            'out-timeform       =tow',
            'out-timendec       =3',
            'out-degform        =deg',
            'out-fieldsep       = ',
            'out-outsingle      =off',
            'out-maxsolstd      =0.0',
            'out-height         =ellipsoidal',
            'out-geoid          =internal',
            'out-solstatic      =all',
            'out-nmeaintv1      =0.0',
            'out-nmeaintv2      =0.0',
            'out-outstat        =1',         # Generar archivo de estadísticas
        ]
        return '\n'.join(lines)

    def _stats_section(self) -> str:
        lines = [
            '',
            '# ── Estadísticas y ruido ────────────────────────',
            'stats-eratio1      =100.0',
            'stats-eratio2      =100.0',
            'stats-errphase     =0.003',
            'stats-errphaseel   =0.003',
            'stats-errphasebl   =0.0',
            'stats-errdoppler   =1.0',
            'stats-stdbias      =30.0',
            'stats-stdiono      =0.03',
            'stats-stdtrop      =0.3',
            'stats-prnaccelh    =1.0',
            'stats-prnaccelv    =0.1',
            'stats-prnbias      =0.0001',
            'stats-prniono      =0.001',
            'stats-prntrop      =0.0001',
            'stats-clkstab      =5e-12',
        ]
        return '\n'.join(lines)

    def _ant_section(self, p: ProcessingParams) -> str:
        lines = [
            '',
            '# ── Antenas ─────────────────────────────────────',
        ]

        # ROVER (ant1) — posición calculada por RTKLIB
        lines += [
            'ant1-postype       =llh',
            'ant1-pos1          =0.0',
            'ant1-pos2          =0.0',
            'ant1-pos3          =0.0',
            'ant1-anttype       =',
            'ant1-antdele       =0.0',
            'ant1-antdeln       =0.0',
            'ant1-antdelu       =0.0',
        ]

        # BASE (ant2) — CRÍTICO: usar coords IGN si están disponibles
        if p.base_coords is not None:
            bc = p.base_coords
            lines += [
                '',
                f'# BASE: {bc.fuente} | Corregida: {bc.fue_corregida}',
                f'# Datum: {bc.datum}',
                'ant2-postype       =llh',
                f'ant2-pos1          ={bc.lat_dd:.10f}',
                f'ant2-pos2          ={bc.lon_dd:.10f}',
                f'ant2-pos3          ={bc.h_elip:.4f}',
                'ant2-anttype       =',
                'ant2-antdele       =0.0',
                'ant2-antdeln       =0.0',
                'ant2-antdelu       =0.0',
            ]
            if bc.fue_corregida and bc.delta_horizontal_m is not None:
                lines.append(
                    f'# TRAZABILIDAD: Delta_H={bc.delta_horizontal_m:.4f}m '
                    f'Delta_V={bc.delta_vertical_m:.4f}m vs RINEX header'
                )
        else:
            # Solo permitido si el modo es PPP
            lines += [
                'ant2-postype       =rinexhead',
                'ant2-pos1          =0.0',
                'ant2-pos2          =0.0',
                'ant2-pos3          =0.0',
                'ant2-anttype       =',
                'ant2-antdele       =0.0',
                'ant2-antdeln       =0.0',
                'ant2-antdelu       =0.0',
            ]

        return '\n'.join(lines)

    def _misc_section(self) -> str:
        lines = [
            '',
            '# ── Misceláneos ─────────────────────────────────',
            'misc-timeinterp    =on',
            'misc-sbasatsel     =0',
            'misc-rnxopt1       =',
            'misc-rnxopt2       =',
            'misc-pppopt        =',
        ]
        return '\n'.join(lines)
