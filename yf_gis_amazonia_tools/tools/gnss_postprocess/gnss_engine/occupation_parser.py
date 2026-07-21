# -*- coding: utf-8 -*-
"""
Parser de ocupaciones dentro de un RINEX continuo (estilo TBC/Pathfinder).

Los receptores Trimble (Geo7X, DA2) registran en modo continuo y marcan
cada punto ocupado con un EVENT FLAG en el RINEX:
  - Flag 2: inicio de tramo cinemático ("Start of Kinematic Data")
  - Flag 3: inicio de ocupación estática ("Start of Occupation"), seguido
    de metadatos: MARKER NAME, MARKER NUMBER, APPROX POSITION XYZ,
    ANTENNA: DELTA H/E/N.

Este parser extrae las ocupaciones (nombre, ventana de tiempo, altura de
antena) para que cada punto se resuelva por separado, SIN promediar entre
distintas ocupaciones — replicando el flujo de TBC/Pathfinder.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Occupation:
    name: str                       # MARKER NAME (H1, H-6, ...)
    number: str = ''                # MARKER NUMBER
    ant_height: float = 0.0         # ANTENNA DELTA H de esta ocupación
    t_start: Optional[datetime] = None
    t_end: Optional[datetime] = None
    n_epochs: int = 0
    approx_xyz: tuple = None

    @property
    def duration_s(self) -> float:
        if self.t_start and self.t_end:
            return (self.t_end - self.t_start).total_seconds()
        return 0.0


_EPOCH2 = re.compile(
    r'^>\s+(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+'
    r'([\d.]+)\s+(\d)\s+(\d+)')
_EVENT = re.compile(r'^>\s+(\d)\s+(\d+)\s*$')  # ">   3  5"  (flag, n_meta)


def _parse_epoch_time(line):
    m = _EPOCH2.match(line)
    if not m:
        return None, None, None
    y, mo, d, h, mi = (int(m.group(i)) for i in range(1, 6))
    s = float(m.group(6))
    flag = int(m.group(7))
    nsat = int(m.group(8))
    try:
        dt = datetime(y, mo, d, h, mi, int(s))
    except ValueError:
        return None, flag, nsat
    return dt, flag, nsat


def parse_occupations(rinex_path) -> List[Occupation]:
    """Lee un RINEX 3.x y devuelve la lista de ocupaciones detectadas.

    Si el archivo no tiene event flags de ocupación (flag 3), devuelve
    lista vacía — el archivo es de un solo punto o cinemático puro y se
    procesa por el flujo normal.
    """
    occs: List[Occupation] = []
    with open(rinex_path, 'r', encoding='ascii', errors='replace') as f:
        lines = f.readlines()

    # Saltar header
    start = 0
    for i, l in enumerate(lines):
        if 'END OF HEADER' in l:
            start = i + 1
            break

    current: Optional[Occupation] = None
    last_time = None
    i = start
    n = len(lines)
    while i < n:
        line = lines[i]

        # ¿Evento especial? ">  <flag>  <n_meta>"
        ev = _EVENT.match(line.rstrip())
        if ev:
            flag = int(ev.group(1))
            n_meta = int(ev.group(2))
            if flag == 3:
                # Inicio de ocupación — cerrar la anterior
                if current is not None:
                    current.t_end = last_time
                    occs.append(current)
                # Leer metadatos
                name, number, ant_h, axyz = '', '', 0.0, None
                for j in range(i + 1, min(i + 1 + n_meta + 1, n)):
                    lj = lines[j]
                    if 'MARKER NAME' in lj:
                        name = lj.split('MARKER NAME')[0].strip()
                    elif 'MARKER NUMBER' in lj:
                        number = lj.split('MARKER NUMBER')[0].strip()
                    elif 'ANTENNA: DELTA' in lj:
                        parts = lj.split()
                        if parts:
                            try:
                                ant_h = float(parts[0])
                            except ValueError:
                                logging.getLogger(__name__).debug("suppressed", exc_info=True)
                    elif 'APPROX POSITION XYZ' in lj:
                        parts = lj.split()
                        if len(parts) >= 3:
                            try:
                                axyz = tuple(float(parts[k]) for k in range(3))
                            except ValueError:
                                logging.getLogger(__name__).debug("suppressed", exc_info=True)
                current = Occupation(name=name or f'PT_{len(occs)+1}',
                                     number=number, ant_height=ant_h,
                                     approx_xyz=axyz)
                i += n_meta + 1
                continue
            elif flag == 2:
                # Inicio cinematico = receptor EMPIEZA A MOVERSE.
                # Cierra la ocupacion (el periodo estatico termino).
                # Sin esto la ventana incluiria la caminata al siguiente
                # punto y el promedio saldria desplazado (bug de los 144m).
                if current is not None:
                    current.t_end = last_time
                    occs.append(current)
                    current = None
                i += n_meta + 1
                continue
            else:
                i += n_meta + 1
                continue

        # ¿Época de datos normal?
        dt, flag, nsat = _parse_epoch_time(line)
        if dt is not None:
            last_time = dt
            if current is not None:
                if current.t_start is None:
                    current.t_start = dt
                current.n_epochs += 1
        i += 1

    # Cerrar la última ocupación
    if current is not None:
        current.t_end = last_time
        occs.append(current)

    return occs


def summary(occs: List[Occupation]) -> str:
    if not occs:
        return 'Sin ocupaciones marcadas (archivo de punto único o cinemático).'
    out = [f'{len(occs)} ocupaciones detectadas:']
    for o in occs:
        ts = o.t_start.strftime('%H:%M:%S') if o.t_start else '?'
        out.append(f'  {o.name:<8} inicio {ts}  '
                   f'{o.n_epochs} épocas  {o.duration_s:.0f}s  '
                   f'ant={o.ant_height:.3f}m')
    return '\n'.join(out)
