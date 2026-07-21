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

    # ── Alturas de antena ─────────────────────────
    ant_height_rover: float = 0.0    # Altura VERTICAL al ARP (jalón = medida directa;
                                     # si se midió SLANT en trípode, convertir antes:
                                     # v = sqrt(slant² − R_antena²) + offset_ARP
    ant_height_base:  float = 0.0    # Altura de antena base (si es base propia)

    # ── Calibración de antena (ANTEX) ─────────────
    # Archivo .atx (IGS maestro, o fusionado con ANTEX del fabricante,
    # ej. METX5/Mettatec). Si está presente Y 'antena' coincide con un
    # nombre normalizado IGS, RTKLIB aplica PCO/PCV reales (como TBC).
    antex_file: Optional[str] = None
    antena_base: str = ''            # Tipo de antena de la base (header RINEX)
    # NOTA: para CORS IGN (MD01/MD04) la altura de antena
    # está en el RINEX header — RTKLIB la lee automáticamente
    # si se usa ant2-postype=rinexhead. Para coords manuales
    # se debe ingresar ant2-antdelu aquí.

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
    # Referencia: RTKLIB manual 2.4.2 sección 5.2
    # 0=single, 1=dgps, 2=kinematic, 3=static, 4=movbase,
    # 5=fixed, 6=ppp-kinematic, 7=ppp-static
    _POSMODE = {
        'static':        3,
        'kinematic':     2,
        'movbase':       4,
        'fixed':         5,
        'dgps-static':   1,   # DGPS código diferencial (submétrico, sin falsos fix)
        'dgps-kinematic': 1,  # DGPS cinemático
        'ppp-static':    7,
        'ppp-kinematic': 6,
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
            self._out_section(params),
            self._stats_section(),
            self._ant_section(params),
            self._files_section(params),
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

        # NOTA (verificado con datos reales de MDD bajo dosel): forzar
        # 'combined' empeora datos con cycle slips severos (el backward
        # propaga sus propios errores). Se respeta la elección del usuario;
        # default forward, que demostró ser el más robusto en estos datos.

        # Modelo ionosférico: IONEX si hay archivo VÁLIDO, broadcast si no
        _ionex_ok = bool(p.ionex_file and os.path.isfile(p.ionex_file))
        ionoopt = 8 if _ionex_ok else 1   # 8=IONEX, 1=broadcast

        # Efemérides: SP3 solo si el archivo EXISTE (si se pide precise
        # sin pasar el archivo, RTKLIB se queda sin órbitas y todo falla)
        _sp3_ok = bool(p.sp3_file and os.path.isfile(p.sp3_file))
        sateph  = 1 if _sp3_ok else 0     # 1=precise, 0=broadcast

        # Troposfera: si hay efemérides precisas (línea base larga),
        # estimar troposfera (tropopt=3) en vez de solo Saastamoinen (=2).
        # Esto mejora notablemente la resolución de ambigüedades >20km.
        tropopt = 3 if _sp3_ok else 2     # 3=estimate ZTD, 2=Saastamoinen

        # Navsys: suma de bits (GPS=0x01, SBAS=0x02, GLO=0x04, GAL=0x08, BDS=0x20)
        navsys = p.navsys

        # Calibración de antena (ANTEX):
        #   posopt1 = PCV de antena de SATÉLITE → solo tiene sentido con
        #             efemérides precisas (SP3); en broadcast se ignora.
        #   posopt2 = PCV de antena de RECEPTOR → requiere .atx cargado
        #             y que ant1-anttype coincida con un nombre IGS.
        _atx_ok = bool(p.antex_file and os.path.isfile(p.antex_file))
        posopt1 = 1 if (_atx_ok and _sp3_ok) else 0
        posopt2 = 1 if (_atx_ok and p.antena.strip()) else 0

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
            f'pos1-tropopt       ={tropopt}',
            f'pos1-sateph        ={sateph}',
            f'pos1-posopt1       ={posopt1}',
            f'pos1-posopt2       ={posopt2}',
            f'pos1-posopt3       =0',
            f'pos1-posopt4       =0',
            f'pos1-posopt5       =0',
            f'pos1-posopt6       =0',
            f'pos1-exclsats      =',
            f'pos1-navsys        ={navsys}',
        ]
        return '\n'.join(lines)

    def _pos2_section(self, p: ProcessingParams) -> str:
        # Sin resolución de ambigüedad en PPP ni DGPS:
        # DGPS usa pseudodistancia (código), no fase → no hay ambigüedad
        # que fijar → IMPOSIBLE generar falsos fix. Precisión honesta
        # submétrica (0.3-1 m típico contra base cercana).
        _sin_ar = ('ppp' in p.solution_type) or ('dgps' in p.solution_type)
        armode  = 0 if _sin_ar else 3   # 3=fix-and-hold
        gloar   = 0 if _sin_ar else 1

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

    def _out_section(self, p: ProcessingParams = None) -> str:
        # NOTA (verificado con datos reales MDD): solstatic=single puede
        # producir UN falso fix con sigmas centimétricas engañosas y sin
        # posibilidad de validar consistencia. Se mantiene 'all' SIEMPRE:
        # el layer_builder valida la dispersión entre épocas (anti-falso-fix).
        solstatic = 'all'
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
            f'out-solstatic      ={solstatic}',
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
        # ant1-antdelu = altura vertical de antena sobre el punto
        # antdelu espera altura VERTICAL al ARP (no slant). En jalón la medida
        # de campo ya es vertical; en trípode con cinta (slant) hay que convertir.
        lines += [
            'ant1-postype       =llh',
            'ant1-pos1          =0.0',
            'ant1-pos2          =0.0',
            'ant1-pos3          =0.0',
            f'ant1-anttype       ={p.antena}',
            'ant1-antdele       =0.0',
            'ant1-antdeln       =0.0',
            f'ant1-antdelu       ={p.ant_height_rover:.4f}',
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
                f'ant2-anttype       ={p.antena_base}',
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

    def _files_section(self, p: ProcessingParams) -> str:
        """
        Archivos de calibración de antena (ANTEX).
        RTKLIB usa el MISMO .atx para PCV de receptor y de satélite:
          file-rcvantfile → corrige la antena del rover (y base si
                            ant2-anttype está definido)
          file-satantfile → corrige antenas de los satélites (útil con SP3)
        Referencia: RTKLIB manual 2.4.2 §3.5.
        """
        if not (p.antex_file and os.path.isfile(p.antex_file)):
            return '\n# ── Archivos ANTEX: no configurados ─────────────'
        lines = [
            '',
            '# ── Calibración de antena (ANTEX) ───────────────',
            f'# Modelo aplicado: {p.antena or "(sin nombre — PCV rover inactivo)"}',
            f'file-rcvantfile    ={p.antex_file}',
            f'file-satantfile    ={p.antex_file}',
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
