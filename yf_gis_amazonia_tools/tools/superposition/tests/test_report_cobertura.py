# -*- coding: utf-8 -*-
"""
Pruebas de la conclusión sugerida del informe.

El foco NO es la redacción sino una garantía de fondo: que el párrafo que
se transcribe al expediente nunca afirme cobertura que el análisis no
tuvo. Una capa caída no puede leerse como capa limpia.

Se ejecutan sin QGIS: report_engine solo depende de la stdlib.
"""

import importlib.util
import os
import sys
import types
import unittest

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SUP = os.path.abspath(os.path.join(_AQUI, ".."))

_PKG = "yf_rep_test"
if _PKG not in sys.modules:
    _paquete = types.ModuleType(_PKG)
    _paquete.__path__ = [_SUP]
    sys.modules[_PKG] = _paquete


def _cargar(nombre):
    completo = "{}.{}".format(_PKG, nombre)
    if completo in sys.modules:
        return sys.modules[completo]
    spec = importlib.util.spec_from_file_location(
        completo, os.path.join(_SUP, nombre + ".py"))
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[completo] = modulo
    spec.loader.exec_module(modulo)
    return modulo


re_ = _cargar("report_engine")


def contexto(evaluadas=3, hay_sup=False, errores=(), nivel="critico",
             con_sup=1):
    return {
        "errores": [{"capa": c, "motivo": m} for c, m in errores],
        "superposiciones": ([{
            "capa": "SERFOR — Concesiones Forestales",
            "archivo": "SERFOR · Concesiones Forestales",
            "titular": "LOBOYOC II",
            "codigo": "17-TAM/C-CON-RI-002-06",
            "tipo": "Concesión forestal",
            "area_ha": 4.0566, "porcentaje": 9.19,
            "nivel": nivel, "nivel_legible": nivel.capitalize(),
            "atributos": {},
        }] if hay_sup else []),
        "trazabilidad": {"archivos": [], "log": []},
        "analisis": {
            "fecha_legible": "31/07/2026 10:00",
            "plugin_version": "3.0.4",
            "nivel_global_legible": nivel.capitalize(),
            "hay_errores": bool(errores),
            "sin_superposicion": not hay_sup,
            "metodo_area": "Elipsoidal",
            "carpeta_capas": "",
            "umbral_critico_pct": 5.0,
            "umbral_observable_pct": 1.0,
            "predio": {"nombre": "Benedicta Anccoccallo", "area_ha": 44.1044,
                       "perimetro_m": 3021.44, "crs": "EPSG:32719",
                       "n_partes": 1},
            "capas_evaluadas": evaluadas,
            "capas_no_evaluadas": len(errores),
            "capas_totales": evaluadas + len(errores),
            "capas_con_superposicion": con_sup if hay_sup else 0,
            "hay_superposicion": hay_sup,
            "nivel_global": nivel,
            "umbral_ha": 0.05,
            "area_superpuesta_total_ha": 4.0566,
            "porcentaje_superpuesto_total": 9.19,
            "area_afectada_unica_ha": 4.0566,
            "porcentaje_afectado_unico": 9.19,
        },
    }


class TestCoberturaCompleta(unittest.TestCase):

    def test_sin_superposicion_y_sin_fallos_no_pone_reservas(self):
        txt = re_.conclusion_sugerida(contexto())
        self.assertIn("NO se ha identificado superposición", txt)
        self.assertNotIn("NO agota", txt)

    def test_con_superposicion_y_sin_fallos(self):
        txt = re_.conclusion_sugerida(contexto(hay_sup=True))
        self.assertIn("se ha identificado superposición", txt)
        self.assertNotIn("NO agota", txt)


class TestCoberturaIncompleta(unittest.TestCase):
    """Lo esencial: una capa caída jamás puede leerse como capa limpia."""

    ERRORES = (("SERNANP — ANP", "El servicio no respondió"),
               ("MIDAGRI — Predio Rural", "Error de acceso (403)"))

    def test_limpio_con_fallos_advierte_en_la_conclusion(self):
        txt = re_.conclusion_sugerida(
            contexto(evaluadas=3, errores=self.ERRORES))
        self.assertIn("2 capa(s) no pudieron ser evaluadas", txt)
        self.assertIn("NO agota", txt)

    def test_con_superposicion_y_fallos_tambien_advierte(self):
        txt = re_.conclusion_sugerida(
            contexto(evaluadas=3, hay_sup=True, errores=self.ERRORES))
        self.assertIn("se ha identificado superposición", txt)
        self.assertIn("NO agota", txt)

    def test_no_afirma_estar_libre_sin_matizar(self):
        """Regresión: antes decía 'se encuentra libre' sin reserva alguna."""
        txt = re_.conclusion_sugerida(
            contexto(evaluadas=3, errores=self.ERRORES))
        i_libre = txt.find("libre")
        i_reserva = txt.find("constancia")
        self.assertGreater(i_libre, -1)
        self.assertGreater(i_reserva, i_libre,
                           "la salvedad debe acompañar a la afirmación")

    def test_nivel_no_significativo_conserva_la_reserva(self):
        txt = re_.conclusion_sugerida(
            contexto(evaluadas=2, hay_sup=True, nivel="no_significativo",
                     errores=self.ERRORES))
        self.assertIn("umbral de significancia", txt)
        self.assertIn("NO agota", txt)


class TestCoberturaNula(unittest.TestCase):
    """Si no se evaluó nada, el informe no puede concluir nada."""

    ERRORES = (("SERFOR — Concesiones", "timeout"),
               ("SERNANP — ANP", "timeout"),
               ("MIDAGRI — Predio Rural", "timeout"))

    def test_no_concluye_ausencia(self):
        txt = re_.conclusion_sugerida(
            contexto(evaluadas=0, errores=self.ERRORES))
        self.assertIn("No fue posible efectuar el análisis", txt)
        self.assertIn("NO acredita", txt)

    def test_no_dice_que_esta_libre(self):
        txt = re_.conclusion_sugerida(
            contexto(evaluadas=0, errores=self.ERRORES))
        self.assertNotIn("se encuentra libre", txt)

    def test_desaconseja_su_uso_como_sustento(self):
        txt = re_.conclusion_sugerida(
            contexto(evaluadas=0, errores=self.ERRORES))
        self.assertIn("no debe ser empleado como sustento", txt)


class TestHtmlAdvertencia(unittest.TestCase):

    def test_seccion_no_evaluadas_es_visualmente_advertencia(self):
        ctx = contexto(evaluadas=1,
                       errores=(("SERNANP — ANP", "sin respuesta"),))
        html = re_.generar_html(ctx, conclusion="x")
        self.assertIn("ADVERTENCIA", html)
        self.assertIn("no implica ausencia de", html)

    def test_sin_errores_no_hay_bloque_de_advertencia(self):
        html = re_.generar_html(contexto(), conclusion="x")
        self.assertNotIn("cobertura\nincompleta", html)
        self.assertNotIn("Capas no evaluadas", html)


class TestRecuentoHonesto(unittest.TestCase):
    """El recuento de la conclusión debe distinguir previstas de evaluadas."""

    def test_declara_n_de_t(self):
        txt = re_.conclusion_sugerida(
            contexto(evaluadas=3,
                     errores=(("A", "x"), ("B", "y"), ("C", "z"))))
        self.assertIn("contrastada contra 3 de 6 capa(s)", txt)

    def test_sin_fallos_n_igual_t(self):
        txt = re_.conclusion_sugerida(contexto(evaluadas=4))
        self.assertIn("contrastada contra 4 de 4 capa(s)", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
