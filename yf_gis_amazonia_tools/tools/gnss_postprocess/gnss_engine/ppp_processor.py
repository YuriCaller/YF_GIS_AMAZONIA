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
import subprocess  # nosec B404 - llamadas con lista de args y sin shell
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

        # CRÍTICO: normalizar rutas — RTKLIB falla con barras mixtas / y \
        cmd = [os.path.normpath(c) if (os.sep in c or '/' in c) else c for c in cmd]
        return cmd

    def _execute(self, cmd: list) -> bool:
        try:
            # Log seguro del comando (sin invocar shell). list2cmdline muestra
            # cómo Windows verá el comando con sus argumentos citados.
            cmd_display = subprocess.list2cmdline(cmd)
            self.log.emit(f'  [CMD] {cmd_display}', 'info')

            # subprocess.run con lista + shell=False (default) es seguro
            # y maneja correctamente rutas con espacios en Windows y Linux.
            # Esto evita Bandit B602 (subprocess_popen_with_shell_equals_true).
            result = subprocess.run(  # nosec B603 - RTKLIB, lista sin shell, ruta validada
                cmd, capture_output=True,
                text=True, encoding='utf-8', errors='replace',
                timeout=600
            )

            output = (result.stdout or '') + (result.stderr or '')
            output_lines = output.strip().split('\n') if output.strip() else []

            for line in output_lines:
                line = line.strip()
                if not line or line.startswith('processing'):
                    continue
                self.log.emit(f'  {line}', 'info')

            proc_count = sum(1 for l in output_lines if l.strip().startswith('processing'))  # noqa: E741
            if proc_count > 0:
                self.log.emit(f'  ⏱ {proc_count} épocas procesadas', 'info')

            if any('usage: rnx2rtkp' in l for l in output_lines):  # noqa: E741
                self.log.emit('❌ RTKLIB mostró la ayuda. Revise argumentos.', 'error')
                return False

            if any('no obs data' in l.lower() for l in output_lines):  # noqa: E741
                self.log.emit('❌ RTKLIB no pudo leer datos de observación.', 'error')
                return False

            if result.returncode != 0:
                self.log.emit(f'❌ rnx2rtkp (PPP) código {result.returncode}', 'error')
                return False
            return True
        except subprocess.TimeoutExpired:
            self.log.emit('❌ Tiempo límite excedido (10 min)', 'error')
            return False
        except Exception as ex:
            self.log.emit(f'❌ {ex}', 'error')
            return False

    def _resolve_binary(self) -> str:
        exe = 'rnx2rtkp.exe' if platform.system() == 'Windows' else 'rnx2rtkp'
        search_paths = [
            os.path.join(self.plugin_dir, 'rtklib_bin', exe),
            os.path.join(self.plugin_dir, 'tools', 'gnss_postprocess', 'rtklib_bin', exe),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rtklib_bin', exe),
        ]
        for path in search_paths:
            if os.path.isfile(path):
                if platform.system() != 'Windows':
                    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
                return path
        return shutil.which('rnx2rtkp') or ''
