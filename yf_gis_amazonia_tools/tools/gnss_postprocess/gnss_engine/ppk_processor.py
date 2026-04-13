# -*- coding: utf-8 -*-
"""
ppk_processor.py
Motor de post-procesamiento PPK (Post Processed Kinematic).
Responsabilidad única: ejecutar rnx2rtkp para modo diferencial.
"""
import os
import subprocess
import platform
import stat
import shutil
from qgis.PyQt.QtCore import QThread, pyqtSignal

from .config_builder import ConfigBuilder, ProcessingParams
from ..validators.ppk_validator import PPKValidator


class PPKProcessor(QThread):
    """
    Ejecuta el procesamiento PPK en un hilo separado.
    Señales Qt para comunicar progreso a la UI.
    """
    progress = pyqtSignal(int)          # 0-100
    log      = pyqtSignal(str, str)     # (mensaje, nivel: info|ok|warn|error)
    finished = pyqtSignal(bool, str, dict)  # (éxito, pos_file, stats)

    def __init__(self, params: ProcessingParams, plugin_dir: str):
        super().__init__()
        self.params     = params
        self.plugin_dir = plugin_dir
        self._builder   = ConfigBuilder()

    def run(self):
        p = self.params
        try:
            # 1. Validar parámetros PPK
            self.log.emit('🔍 Validando parámetros PPK...', 'info')
            validator = PPKValidator()
            ok, errors = validator.validate(p)
            if not ok:
                for e in errors:
                    self.log.emit(f'❌ {e}', 'error')
                self.finished.emit(False, '', {})
                return
            self.progress.emit(10)

            # 2. Generar .conf dinámico
            self.log.emit('📝 Generando configuración RTKLIB...', 'info')
            conf_path = self._builder.write(p)
            self.log.emit(f'   → {conf_path}', 'info')
            self.progress.emit(20)

            # 3. Log de trazabilidad de base
            self._log_base_traceability()
            self.progress.emit(25)

            # 4. Resolver binario
            binary = self._resolve_binary()
            if not binary:
                self.log.emit('❌ No se encontró rnx2rtkp. Ejecuta install_rtklib.py', 'error')
                self.finished.emit(False, '', {})
                return
            self.log.emit(f'🔧 Motor: {binary}', 'info')
            self.progress.emit(30)

            # 5. Construir y ejecutar comando
            out_pos = os.path.join(p.out_dir, p.out_prefix + '.pos')
            cmd = self._build_command(binary, conf_path, out_pos)
            self.log.emit(f'▶ {" ".join(cmd)}', 'info')
            self.progress.emit(35)

            success = self._execute(cmd)
            self.progress.emit(85)

            if not success:
                self.finished.emit(False, '', {})
                return

            # 6. Parsear resultado
            self.log.emit('📊 Analizando resultados...', 'info')
            from ..results.pos_parser import PosParser
            stats = PosParser().parse(out_pos)
            self.progress.emit(95)

            self.log.emit(
                f'✅ PPK completado | Fix: {stats.get("fix_pct",0):.1f}% '
                f'Float: {stats.get("float_pct",0):.1f}%',
                'ok'
            )
            self.finished.emit(True, out_pos, stats)

        except Exception as ex:
            self.log.emit(f'❌ Excepción PPK: {ex}', 'error')
            self.finished.emit(False, '', {})

    # ──────────────────────────────────────────────
    # TRAZABILIDAD
    # ──────────────────────────────────────────────
    def _log_base_traceability(self):
        bc = self.params.base_coords
        if bc is None:
            return
        self.log.emit(
            f'📌 Base [{bc.fuente}]: '
            f'Lat={bc.lat_dd:.8f}° Lon={bc.lon_dd:.8f}° h={bc.h_elip:.4f}m',
            'info'
        )
        if bc.fue_corregida:
            dh = bc.delta_horizontal_m
            dv = bc.delta_vertical_m
            self.log.emit(
                f'⚠️  Coordenadas CORREGIDAS respecto al RINEX header: '
                f'ΔH={dh:.4f}m  ΔV={dv:.4f}m',
                'warn'
            )
            self.log.emit(
                f'   RINEX original: '
                f'Lat={bc.rinex_lat:.8f}° Lon={bc.rinex_lon:.8f}° h={bc.rinex_h:.4f}m',
                'warn'
            )
        else:
            self.log.emit('✅ Coordenadas de base coinciden con RINEX header.', 'ok')

    # ──────────────────────────────────────────────
    # COMANDO
    # ──────────────────────────────────────────────
    def _build_command(self, binary: str, conf: str, out_pos: str) -> list:
        p = self.params
        cmd = [binary, '-k', conf, '-o', out_pos, p.rinex_rover, p.nav_file]

        if p.gnav_file and os.path.isfile(p.gnav_file):
            cmd.append(p.gnav_file)

        # Base RINEX
        if p.rinex_base and os.path.isfile(p.rinex_base):
            cmd += ['-r', p.rinex_base]

        return cmd

    def _execute(self, cmd: list) -> bool:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace'
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    level = 'error' if 'error' in line.lower() else 'info'
                    self.log.emit(f'  {line}', level)
            proc.wait()
            if proc.returncode != 0:
                self.log.emit(f'❌ rnx2rtkp retornó código {proc.returncode}', 'error')
                return False
            return True
        except Exception as ex:
            self.log.emit(f'❌ Error ejecutando RTKLIB: {ex}', 'error')
            return False

    def _resolve_binary(self) -> str:
        exe = 'rnx2rtkp.exe' if platform.system() == 'Windows' else 'rnx2rtkp'
        bundled = os.path.join(self.plugin_dir, 'rtklib_bin', exe)
        if os.path.isfile(bundled):
            if platform.system() != 'Windows':
                os.chmod(bundled, os.stat(bundled).st_mode | stat.S_IEXEC)
            return bundled
        return shutil.which('rnx2rtkp') or ''
