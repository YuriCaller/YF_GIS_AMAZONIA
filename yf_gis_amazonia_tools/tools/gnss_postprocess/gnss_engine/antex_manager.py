# -*- coding: utf-8 -*-
"""
antex_manager.py
Gestión de archivos ANTEX (calibración de antenas GNSS) para el
módulo de post-proceso.

Funciones:
  1. Descargar el ANTEX maestro del IGS (igs20.atx) — cubre Trimble,
     CHCNAV, Leica, Topcon, South, Emlid, Septentrio y miles más.
  2. Parsear cualquier .atx y listar las antenas de RECEPTOR
     (nombre normalizado IGS de 20 caracteres, ej. 'TRMR10          NONE').
  3. Fusionar el ANTEX maestro con ANTEX personalizados del usuario
     (ej. METX5 de Mettatec, calibrado por el NGS) en un único archivo
     que RTKLIB pueda consumir vía file-rcvantfile.
  4. Leer el tipo de antena del header de un RINEX de base
     (línea 'ANT # / TYPE') para aplicar PCV también en la base.

Formato ANTEX 1.4: https://files.igs.org/pub/data/format/antex14.txt
RTKLIB manual 2.4.2 §3.5: file-rcvantfile / file-satantfile.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os
import re
import shutil

# Reutiliza el descargador seguro ya validado del módulo de efemérides
from .ephemeris_downloader import _http_get


# ── Fuentes públicas del ANTEX maestro (orden de preferencia) ──
IGS_ANTEX_URLS = [
    'https://files.igs.org/pub/station/general/igs20.atx',
    'https://files.igs.org/pub/station/general/pcv_archive/igs20.atx',
]

MASTER_FILENAME = 'igs20.atx'
MERGED_FILENAME = 'yf_merged.atx'


def data_dir():
    """Carpeta de datos persistente del módulo (junto al código)."""
    d = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(d, exist_ok=True)
    return d


def master_path():
    return os.path.join(data_dir(), MASTER_FILENAME)


def merged_path():
    return os.path.join(data_dir(), MERGED_FILENAME)


# ══════════════════════════════════════════════
# DESCARGA
# ══════════════════════════════════════════════

def download_master(force=False, log=None):
    """
    Descarga igs20.atx a la carpeta de datos. Retorna la ruta o None.
    Si ya existe y force=False, retorna la copia local sin descargar.
    """
    dest = master_path()
    if os.path.isfile(dest) and os.path.getsize(dest) > 1_000_000 and not force:
        return dest

    for url in IGS_ANTEX_URLS:
        try:
            if log:
                log(f'Descargando ANTEX maestro: {url}')
            raw = _http_get(url, timeout=120)
            # El igs20.atx pesa varios MB; un archivo diminuto = error HTML
            if raw and len(raw) > 1_000_000 and b'ANTEX VERSION' in raw[:200]:
                with open(dest, 'wb') as f:
                    f.write(raw)
                return dest
        except Exception as exc:          # red caída, DNS, timeout…
            if log:
                log(f'  fallo: {exc}')
            continue
    return None


# ══════════════════════════════════════════════
# PARSER
# ══════════════════════════════════════════════

def _iter_antenna_blocks(path):
    """
    Itera los bloques START OF ANTENNA … END OF ANTENNA de un .atx.
    Yields: (antenna_type_20char, serial_20char, [líneas del bloque]).
    """
    block, in_block = [], False
    atype, serial = '', ''
    with open(path, 'r', errors='replace') as f:
        for line in f:
            label = line[60:80].strip() if len(line) > 60 else ''
            if label == 'START OF ANTENNA':
                in_block, block = True, [line]
                atype, serial = '', ''
                continue
            if not in_block:
                continue
            block.append(line)
            if label == 'TYPE / SERIAL NO':
                atype = line[0:20].rstrip()
                serial = line[20:40].strip()
            elif label == 'END OF ANTENNA':
                in_block = False
                yield atype, serial, block


def list_receiver_antennas(path):
    """
    Lista los nombres de antenas de RECEPTOR de un .atx (serial vacío).
    Las antenas de satélite (BLOCK IIR, GALILEO-2…) traen serial G01/E12…
    y se excluyen. Retorna lista ordenada sin duplicados.
    """
    names = set()
    if not path or not os.path.isfile(path):
        return []
    for atype, serial, _blk in _iter_antenna_blocks(path):
        if atype and not serial:          # receptor: campo serial en blanco
            names.add(atype)
    return sorted(names)


def read_rinex_antenna(rinex_path):
    """
    Lee el tipo de antena del header RINEX (obs) — línea 'ANT # / TYPE'.
    Columnas 20-40 = tipo de antena (formato IGS). Retorna str o ''.
    Necesario para aplicar PCV también en la BASE (CORS IGN / base propia).
    """
    try:
        with open(rinex_path, 'r', errors='replace') as f:
            for i, line in enumerate(f):
                if 'ANT # / TYPE' in line:
                    return line[20:40].rstrip()
                if 'END OF HEADER' in line or i > 120:
                    break
    except OSError:
        logging.getLogger(__name__).debug("suppressed", exc_info=True)
    return ''


# ══════════════════════════════════════════════
# FUSIÓN (maestro IGS + ANTEX del usuario)
# ══════════════════════════════════════════════

def merge_antex(master, extras, out_path=None, log=None):
    """
    Fusiona el ANTEX maestro con archivos extra (ej. METX5 de Mettatec).
    Estrategia: se copia el maestro completo y se insertan, antes del
    final, los bloques de antenas de receptor de cada extra cuyo nombre
    NO exista ya en el maestro (el maestro tiene prioridad por ser IGS).

    Retorna la ruta del archivo fusionado, o el maestro si no hay extras.
    """
    extras = [e for e in (extras or []) if e and os.path.isfile(e)]
    if not extras:
        return master

    out_path = out_path or merged_path()
    existing = set(list_receiver_antennas(master))

    shutil.copyfile(master, out_path)
    added = 0
    with open(out_path, 'a', errors='replace') as out:
        for extra in extras:
            for atype, serial, blk in _iter_antenna_blocks(extra):
                if serial or not atype:      # solo antenas de receptor
                    continue
                if atype in existing:
                    if log:
                        log(f'  {atype}: ya está en el maestro — se omite')
                    continue
                out.writelines(blk)
                existing.add(atype)
                added += 1
                if log:
                    log(f'  + {atype} (desde {os.path.basename(extra)})')
    if log:
        log(f'ANTEX fusionado: {added} antena(s) agregada(s) → {out_path}')
    return out_path


def resolve_antex(custom_files=None, log=None):
    """
    Punto de entrada de alto nivel para la UI:
      1. Asegura el maestro (descarga si falta).
      2. Fusiona con los ANTEX personalizados del usuario.
    Retorna (ruta_atx_final, lista_nombres_antenas) o (None, []).
    """
    master = download_master(log=log)
    if not master:
        # Sin internet y sin copia local: si hay un custom, usarlo solo
        customs = [c for c in (custom_files or []) if c and os.path.isfile(c)]
        if customs:
            if log:
                log('Sin ANTEX maestro — usando solo ANTEX personalizado.')
            return customs[0], list_receiver_antennas(customs[0])
        return None, []

    final = merge_antex(master, custom_files, log=log)
    return final, list_receiver_antennas(final)
