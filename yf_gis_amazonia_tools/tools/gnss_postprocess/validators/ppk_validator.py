# -*- coding: utf-8 -*-
"""
ppk_validator.py
Valida todos los requisitos para ejecutar PPK.
Si falla → bloquea el procesamiento (no warnings, son errores duros).
"""
import os
from typing import Tuple, List
from ..gnss_engine.config_builder import ProcessingParams


class PPKValidator:
    """Validación estricta para modo PPK."""

    def validate(self, p: ProcessingParams) -> Tuple[bool, List[str]]:
        errors = []

        # ── Archivos obligatorios ──────────────────
        self._check_file(p.rinex_rover, 'RINEX Rover', errors)
        self._check_file(p.nav_file,    'Archivo de navegación', errors)
        self._check_file(p.rinex_base,  'RINEX Base', errors)

        # ── BASE: coordenadas IGN obligatorias ─────
        if p.base_coords is None:
            errors.append(
                'CRÍTICO: No se ingresaron coordenadas de la base. '
                'En modo PPK es OBLIGATORIO ingresar las coordenadas '
                'oficiales (ficha IGN o equivalente). '
                'El plugin NO usa las coordenadas del RINEX header.'
            )
        else:
            bc = p.base_coords
            # Validar rango geográfico (Perú: lat -18 a 0, lon -82 a -68)
            if not (-20.0 <= bc.lat_dd <= 2.0):
                errors.append(
                    f'Latitud de base fuera de rango Perú: {bc.lat_dd:.6f}° '
                    f'(esperado -20° a +2°)'
                )
            if not (-82.0 <= bc.lon_dd <= -68.0):
                errors.append(
                    f'Longitud de base fuera de rango Perú: {bc.lon_dd:.6f}° '
                    f'(esperado -82° a -68°)'
                )
            if not (-100.0 <= bc.h_elip <= 6000.0):
                errors.append(
                    f'Altura elipsoidal inusual: {bc.h_elip:.4f} m '
                    f'(rango esperado -100 a 6000 m)'
                )

        # ── Directorio de salida ───────────────────
        if not p.out_dir or not os.path.isdir(p.out_dir):
            errors.append(f'Directorio de salida no válido: {p.out_dir!r}')

        # ── Modo solución ──────────────────────────
        valid_modes = {'static', 'kinematic', 'movbase'}
        if p.solution_type not in valid_modes:
            errors.append(
                f'Modo {p.solution_type!r} no es válido para PPK. '
                f'Válidos: {valid_modes}'
            )

        return len(errors) == 0, errors

    @staticmethod
    def _check_file(path, name: str, errors: list):
        if not path:
            errors.append(f'{name}: no se seleccionó archivo.')
        elif not os.path.isfile(path):
            errors.append(f'{name}: archivo no encontrado → {path}')
