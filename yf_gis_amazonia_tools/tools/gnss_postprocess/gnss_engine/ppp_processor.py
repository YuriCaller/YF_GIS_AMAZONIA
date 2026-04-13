# -*- coding: utf-8 -*-
"""
ppp_processor.py
Motor de post-procesamiento PPP (Precise Point Positioning).
Diferencias clave vs PPK:
  - No requiere base ni RINEX base
  - Requiere SP3 + CLK (obligatorio)
  - Usa posmode=4 (ppp-static) o 5 (ppp-kinematic)
  - Sin resolución de ambigüedad (armode=0)
"""
import os
import subprocess
import platform
import stat
import shutil
from qgis.PyQt.QtCore import QThread, pyqtSignal

from .config_builder import ConfigBuilder, ProcessingParams
from ..validators.ppp_validator import PPPValidator


class PPPProcessor(QThread):
    progress = pyqtSignal(int)
    log      = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str, dict)

    def __init__(self, params: ProcessingParams, plugin_dir: str):
        super().__init__()
        self.params     = params
        self.plugin_dir = plugin_dir
        self._builder   = ConfigBuilder()

    def run(self):
        p = self.params
        try:
            # 1. Validar PPP (SP3 + CLK obligatorios)
            self.log.emit('🔍 Validando parámetros PPP...', 'info')
            validator = PPPValidator()
            ok, errors = validator.validate(p)
            if not ok:
                for e in errors:
                    self.log.emit(f'❌ {e}', 'error')
                self.finished.emit(False, '', {})
                return
            self.progress.emit(10)

            # 2. Generar .conf
            self.log.emit('📝 Generando configuración RTKLIB (modo PPP)...', 'info')
            conf_path = self._builder.write(p)
            self.log.emit(f'   → {conf_path}', 'info')
            self.progress.emit(20)

            # 3. Binario
            binary = self._resolve_binary()
            if not binary:
                self.log.emit('❌ rnx2rtkp no encontrado.', 'error')
                self.finished.emit(False, '', {})
                return
            self.log.emit(f'🔧 Motor (PPP): {binary}', 'info')
            self.progress.emit(30)

            # 4. Comando PPP
            out_pos = os.path.join(p.out_dir, p.out_prefix + '.pos')
            cmd = self._build_ppp_command(binary, conf_path, out_pos)
            self.log.emit(f'▶ {" ".join(cmd)}', 'info')
            self.progress.emit(35)

            success = self._execute(cmd)
            self.progress.emit(85)

            if not success:
                self.finished.emit(False, '', {})
                return

            # 5. Parsear
            from ..results.pos_parser import PosParser
            stats = PosParser().parse(out_pos)
            self.progress.emit(95)

            self.log.emit(
                f'✅ PPP completado | Q=6(PPP): {stats.get("ppp_pct",0):.1f}% '
                f'Float: {stats.get("float_pct",0):.1f}%',
                'ok'
            )
            self.finished.emit(True, out_pos, stats)

        except Exception as ex:
            self.log.emit(f'❌ Excepción PPP: {ex}', 'error')
            self.finished.emit(False, '', {})

    def _build_ppp_command(self, binary: str, conf: str, out_pos: str) -> list:
        p = self.params
        cmd = [binary, '-k', conf, '-o', out_pos, p.rinex_rover, p.nav_file]

        if p.gnav_file and os.path.isfile(p.gnav_file):
            cmd.append(p.gnav_file)

        # SP3 y CLK son obligatorios en PPP
        if p.sp3_file and os.path.isfile(p.sp3_file):
            cmd += ['-s', p.sp3_file]
        if p.clk_file and os.path.isfile(p.clk_file):
            cmd += ['-c', p.clk_file]
        if p.ionex_file and os.path.isfile(p.ionex_file):
            cmd += ['-i', p.ionex_file]

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
                    self.log.emit(f'  {line}', 'info')
            proc.wait()
            if proc.returncode != 0:
                self.log.emit(f'❌ rnx2rtkp (PPP) código {proc.returncode}', 'error')
                return False
            return True
        except Exception as ex:
            self.log.emit(f'❌ {ex}', 'error')
            return False

    def _resolve_binary(self) -> str:
        exe = 'rnx2rtkp.exe' if platform.system() == 'Windows' else 'rnx2rtkp'
        bundled = os.path.join(self.plugin_dir, 'rtklib_bin', exe)
        if os.path.isfile(bundled):
            if platform.system() != 'Windows':
                os.chmod(bundled, os.stat(bundled).st_mode | stat.S_IEXEC)
            return bundled
        return shutil.which('rnx2rtkp') or ''
