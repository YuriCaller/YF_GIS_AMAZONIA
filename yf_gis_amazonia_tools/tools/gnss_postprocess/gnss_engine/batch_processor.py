# -*- coding: utf-8 -*-
"""
Procesamiento GNSS por lotes (batch) — estilo TBC/Pathfinder.

Procesa N archivos rover contra UNA base en una sola corrida. Cada archivo
se resuelve con la MISMA logica robusta del modo ocupaciones: se procesa en
cinematico, se detectan las ocupaciones por event flags y se corta por
ventana de tiempo, con filtrado de outliers por mediana. Asi un archivo con
1 punto o con varias ocupaciones se maneja igual y sin promediar la caminata.

Autor: Yuri F. Caller Cordova — TUCSA / gis-amazonia.pe
"""

import os
import dataclasses

from qgis.PyQt.QtCore import QThread, pyqtSignal


def detect_nav_for_rover(rover_path):
    """Detecta archivos de navegacion junto a un rover (convencion RINEX)."""
    if not rover_path or not os.path.isfile(rover_path):
        return '', ''
    rover_dir = os.path.dirname(rover_path)
    rover_name, rover_ext = os.path.splitext(os.path.basename(rover_path))
    nav_candidates, gnav_candidates = [], []

    if len(rover_ext) >= 3 and rover_ext[-1].lower() == 'o':
        yp = rover_ext[:-1]
        for ch in ['n', 'N', 'p', 'P', 'l', 'L']:
            nav_candidates.append(rover_name + yp + ch)
        for ch in ['g', 'G']:
            gnav_candidates.append(rover_name + yp + ch)

    if rover_ext.lower() == '.o':
        import glob as _glob
        for ch in ['n', 'p', 'l']:
            for hit in sorted(_glob.glob(os.path.join(
                    rover_dir, rover_name + '.[0-9][0-9]' + ch))):
                nav_candidates.append(os.path.basename(hit))
        for hit in sorted(_glob.glob(os.path.join(
                rover_dir, rover_name + '.[0-9][0-9]g'))):
            gnav_candidates.append(os.path.basename(hit))

    if rover_ext.lower() == '.obs':
        nav_candidates += [rover_name + '.nav', rover_name + '.NAV']
        gnav_candidates += [rover_name + '.gnav', rover_name + '.GNAV']

    if rover_ext.lower() == '.rnx' and '_MO' in rover_name:
        for suf in ['_MN', '_GN', '_EN', '_CN', '_JN']:
            nav_candidates.append(rover_name.replace('_MO', suf) + '.rnx')
            nav_candidates.append(rover_name.replace('_MO', suf) + '.RNX')

    nav, gnav = '', ''
    for cand in nav_candidates:
        full = os.path.join(rover_dir, cand)
        if os.path.isfile(full):
            nav = full
            break
    for cand in gnav_candidates:
        full = os.path.join(rover_dir, cand)
        if os.path.isfile(full):
            gnav = full
            break
    return nav, gnav


class BatchProcessor(QThread):
    """Procesa multiples rovers; cada uno via logica de ocupaciones."""

    log            = pyqtSignal(str, str)
    progress       = pyqtSignal(int)
    file_progress  = pyqtSignal(int, int, str)
    batch_finished = pyqtSignal(list)   # [OccResult con campo .archivo, ...]

    def __init__(self, rover_files, params_template, plugin_dir):
        super().__init__()
        self.rover_files = list(rover_files)
        self.template = params_template
        self.plugin_dir = plugin_dir

    def run(self):
        from .occupation_processor import OccupationProcessor
        from .occupation_parser import parse_occupations

        todos = []
        n = len(self.rover_files)
        self.log.emit(f'LOTE: {n} archivos contra la misma base', 'info')

        for i, rover in enumerate(self.rover_files, 1):
            nombre = os.path.splitext(os.path.basename(rover))[0]
            self.file_progress.emit(i, n, nombre)
            self.log.emit(f'--- [{i}/{n}] {os.path.basename(rover)} ---', 'info')

            nav, gnav = detect_nav_for_rover(rover)
            if not nav:
                nav = self.template.nav_file
            if not gnav:
                gnav = self.template.gnav_file

            params = dataclasses.replace(
                self.template, rinex_rover=rover,
                nav_file=nav, gnav_file=gnav or None, out_prefix=nombre)

            # Procesar este archivo con la logica de ocupaciones (kinematic +
            # corte por ventana + filtrado). Funciona con 1 o varias ocupaciones.
            try:
                op = OccupationProcessor(params, self.plugin_dir, rover)
                op.log.connect(self.log)
                resultados = op.procesar_sincrono()  # devuelve List[OccResult]
                # Capturar trazabilidad del último archivo procesado (para informe)
                self.last_cmd = getattr(op, 'last_cmd', '')
                self.last_binary = getattr(op, 'last_binary', '')
                self.last_pos = getattr(op, 'last_pos', '')
                for res in resultados:
                    res.archivo = nombre
                    todos.append(res)
                if not resultados:
                    self.log.emit(f'   {nombre}: sin ocupaciones/solucion', 'warn')
            except Exception as ex:
                self.log.emit(f'   Excepcion en {nombre}: {ex}', 'error')

            self.progress.emit(int(i / n * 100))

        ok = sum(1 for r in todos if getattr(r, 'confiable', False))
        self.log.emit(f'LOTE COMPLETADO: {len(todos)} puntos '
                      f'({ok} confiables)', 'ok' if todos else 'error')
        self.batch_finished.emit(todos)
