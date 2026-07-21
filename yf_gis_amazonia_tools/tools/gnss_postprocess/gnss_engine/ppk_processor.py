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
        """Construye el comando para rnx2rtkp.

        Sintaxis de rnx2rtkp para PPK (modo relativo/diferencial):
            rnx2rtkp -k config.conf -o output.pos rover.obs base.obs nav.nav [gnav]

        IMPORTANTE:
        - El archivo RINEX base va como SEGUNDO archivo posicional (después del rover),
          NO con el flag -r (que es para coordenadas ECEF manuales).
        - El orden de archivos posicionales es: rover_obs, base_obs, nav_file [, gnav_file]
        """
        p = self.params
        # Archivos posicionales: rover, base, nav (en ese orden)
        cmd = [binary, '-k', conf, '-o', out_pos]

        # 1) Rover observation file (obligatorio)
        cmd.append(p.rinex_rover)

        # 2) Base observation file (obligatorio en PPK - va como 2do posicional)
        if p.rinex_base and os.path.isfile(p.rinex_base):
            cmd.append(p.rinex_base)

        # 3) Navigation file(s)
        cmd.append(p.nav_file)

        if p.gnav_file and os.path.isfile(p.gnav_file):
            cmd.append(p.gnav_file)

        # 4) Efemérides precisas (CRÍTICO si sateph=1 en el .conf):
        #    rnx2rtkp acepta .sp3/.clk/.ionex como posicionales adicionales.
        #    Si el .conf pide 'precise' pero el SP3 no se pasa, RTKLIB
        #    no tiene órbitas y TODO el procesamiento se degrada.
        if p.sp3_file and os.path.isfile(p.sp3_file):
            cmd.append(p.sp3_file)
        if p.clk_file and os.path.isfile(p.clk_file):
            cmd.append(p.clk_file)
        if p.ionex_file and os.path.isfile(p.ionex_file):
            cmd.append(p.ionex_file)

        # CRÍTICO: normalizar rutas — RTKLIB falla con barras mixtas / y \
        cmd = [os.path.normpath(c) if (os.sep in c or '/' in c) else c for c in cmd]
        return cmd

    def _execute(self, cmd: list) -> bool:
        """Ejecuta rnx2rtkp.

        Usa subprocess.run con la lista directamente (shell desactivado, default seguro).
        Python en Windows cita automáticamente argumentos con espacios cuando
        recibe una lista. Esto evita el patron Bandit B602 (subprocess con shell habilitado).

        Para logging, usamos subprocess.list2cmdline() que muestra cómo Windows
        verá el comando sin necesidad de invocar un shell.
        """
        try:
            # Log del comando de forma segura (no requiere invocar un shell)
            cmd_display = subprocess.list2cmdline(cmd)
            self.log.emit(f'  [CMD] {cmd_display}', 'info')

            # subprocess.run con lista + shell=False (default) es:
            #  - Seguro (sin inyección de shell)
            #  - Compatible con rutas con espacios (Python cita automáticamente)
            #  - Multiplataforma (Windows y Linux funcionan idéntico)
            # Guardar trazabilidad para el informe (estilo TBC).
            # cmd = [binary, '-k', conf, '-o', out_pos, rover, base, ...]
            self.last_cmd = ' '.join(f'"{a}"' if ' ' in a else a for a in cmd)
            self.last_binary = cmd[0] if cmd else ''
            try:
                self.last_conf = cmd[cmd.index('-k') + 1] if '-k' in cmd else ''
                self.last_pos = cmd[cmd.index('-o') + 1] if '-o' in cmd else ''
            except (ValueError, IndexError):
                self.last_conf = ''
                self.last_pos = ''
            result = subprocess.run(  # nosec B603 - RTKLIB, lista sin shell, ruta validada
                cmd,
                capture_output=True,
                text=True, encoding='utf-8', errors='replace',
                timeout=600
            )

            # Log output (stderr contiene el progreso de RTKLIB)
            output = (result.stdout or '') + (result.stderr or '')
            output_lines = output.strip().split('\n') if output.strip() else []

            for line in output_lines:
                line = line.strip()
                if not line:
                    continue
                # Solo loguear líneas importantes, no cada época
                if line.startswith('processing'):
                    continue  # Saltar líneas de progreso (hay miles)
                level = 'error' if 'error' in line.lower() else 'info'
                self.log.emit(f'  {line}', level)

            # Resumen de procesamiento
            proc_count = sum(1 for l in output_lines if l.strip().startswith('processing'))  # noqa: E741
            if proc_count > 0:
                self.log.emit(f'  ⏱ {proc_count} épocas procesadas por RTKLIB', 'info')

            # Detectar si RTKLIB imprimió el help en vez de procesar
            if any('usage: rnx2rtkp' in l for l in output_lines):  # noqa: E741
                self.log.emit(
                    '❌ RTKLIB mostró la ayuda en vez de procesar. '
                    'Problema con los argumentos del comando.',
                    'error'
                )
                return False

            # Detectar "no obs data"
            if any('no obs data' in l.lower() for l in output_lines):  # noqa: E741
                self.log.emit(
                    '❌ RTKLIB no pudo leer datos de observación. '
                    'Verifique que las rutas de archivos no tengan caracteres especiales.',
                    'error'
                )
                return False

            if result.returncode != 0:
                self.log.emit(f'❌ rnx2rtkp retornó código {result.returncode}', 'error')
                return False

            return True

        except subprocess.TimeoutExpired:
            self.log.emit('❌ RTKLIB excedió el tiempo límite (10 min)', 'error')
            return False
        except Exception as ex:
            self.log.emit(f'❌ Error ejecutando RTKLIB: {ex}', 'error')
            return False

    def _resolve_binary(self) -> str:
        exe = 'rnx2rtkp.exe' if platform.system() == 'Windows' else 'rnx2rtkp'

        # Buscar en múltiples ubicaciones:
        # 1. plugin_dir/rtklib_bin/ (raíz del plugin)
        # 2. plugin_dir/tools/gnss_postprocess/rtklib_bin/ (subdirectorio del módulo GNSS)
        # 3. Junto a este archivo (gnss_engine/../rtklib_bin/)
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
