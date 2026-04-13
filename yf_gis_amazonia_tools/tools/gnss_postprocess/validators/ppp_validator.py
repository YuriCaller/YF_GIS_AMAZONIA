# -*- coding: utf-8 -*-
"""
ppp_validator.py
Validación estricta para modo PPP.
SP3 + CLK son obligatorios. Sin ellos la solución PPP no es posible.
"""
import os
from typing import Tuple, List
from ..gnss_engine.config_builder import ProcessingParams


class PPPValidator:
    def validate(self, p: ProcessingParams) -> Tuple[bool, List[str]]:
        errors = []

        # ── Archivos obligatorios PPP ──────────────
        self._check_file(p.rinex_rover, 'RINEX Rover', errors)
        self._check_file(p.nav_file,    'Archivo de navegación', errors)

        # SP3 y CLK son OBLIGATORIOS para PPP
        if not p.sp3_file:
            errors.append(
                'CRÍTICO PPP: Falta archivo de órbitas precisas (.sp3). '
                'Descarga desde: https://cddis.nasa.gov/archive/gnss/products/'
            )
        elif not os.path.isfile(p.sp3_file):
            errors.append(f'SP3 no encontrado: {p.sp3_file}')

        if not p.clk_file:
            errors.append(
                'CRÍTICO PPP: Falta archivo de relojes precisos (.clk). '
                'Descarga desde: https://cddis.nasa.gov/archive/gnss/products/'
            )
        elif not os.path.isfile(p.clk_file):
            errors.append(f'CLK no encontrado: {p.clk_file}')

        # ── Modo solución ──────────────────────────
        valid_modes = {'ppp-static', 'ppp-kinematic'}
        if p.solution_type not in valid_modes:
            errors.append(
                f'Modo {p.solution_type!r} no es válido para PPP. '
                f'Válidos: {valid_modes}'
            )

        # ── Salida ────────────────────────────────
        if not p.out_dir or not os.path.isdir(p.out_dir):
            errors.append(f'Directorio de salida no válido: {p.out_dir!r}')

        return len(errors) == 0, errors

    @staticmethod
    def _check_file(path, name: str, errors: list):
        if not path:
            errors.append(f'{name}: no se seleccionó archivo.')
        elif not os.path.isfile(path):
            errors.append(f'{name}: no encontrado → {path}')
