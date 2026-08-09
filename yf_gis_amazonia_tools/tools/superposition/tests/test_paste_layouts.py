# -*- coding: utf-8 -*-
"""
Pruebas de core/paste_helpers — disposiciones de pegado.

Regresión de un fallo real reportado en campo: al pegar desde Excel, los
pares Este/Norte se emparejaban mal y producían coordenadas imposibles
(una latitud de -86 en un predio de Madre de Dios).

Dos causas concurrentes:
  1. El portapapeles de Excel trae texto E imagen; el diálogo priorizaba
     la imagen y hacía OCR sobre datos que ya eran perfectos.
  2. Ante una línea con muchos números, se tomaban los dos primeros como
     par — dando (Este, Este) cuando el texto venía por columnas.

Corren sin QGIS: paste_helpers es Python puro.
"""

import importlib.util
import os
import sys
import types
import unittest

_AQUI = os.path.dirname(os.path.abspath(__file__))
_CORE = os.path.abspath(os.path.join(_AQUI, "..", "..", "..", "core"))

_PKG = "yf_paste_test"
if _PKG not in sys.modules:
    m = types.ModuleType(_PKG)
    m.__path__ = [_CORE]
    sys.modules[_PKG] = m

spec = importlib.util.spec_from_file_location(
    _PKG + ".paste_helpers", os.path.join(_CORE, "paste_helpers.py"))
ph = importlib.util.module_from_spec(spec)
sys.modules[_PKG + ".paste_helpers"] = ph
spec.loader.exec_module(ph)


class TestDisposicionNormal(unittest.TestCase):
    """Lo que ya funcionaba debe seguir funcionando."""

    def test_excel_tabulado(self):
        r = ph.extract_multiple_pairs(
            "351005\t8570306\n350976\t8570325\n350977\t8570312")
        self.assertEqual(r, [(351005, 8570306), (350976, 8570325),
                             (350977, 8570312)])

    def test_con_identificadores(self):
        r = ph.extract_multiple_pairs(
            "V1: 351005 8570306\nV2: 350976 8570325")
        self.assertEqual(r, [(351005, 8570306), (350976, 8570325)])

    def test_latlon(self):
        r = ph.extract_multiple_pairs(
            "-12.486013 -69.167694\n-12.478781 -69.156370")
        self.assertEqual(r, [(-12.486013, -69.167694),
                             (-12.478781, -69.156370)])

    def test_un_solo_par(self):
        self.assertEqual(ph.extract_multiple_pairs("351005 8570306"),
                         [(351005, 8570306)])

    def test_columna_de_id_se_descarta(self):
        r = ph.extract_multiple_pairs(
            "1\t351005\t8570306\n2\t350976\t8570325")
        self.assertEqual(r, [(351005, 8570306), (350976, 8570325)])


class TestDisposicionPorColumnas(unittest.TestCase):
    """El fallo reportado: todos los Estes y luego todos los Nortes."""

    def test_dos_renglones_una_columna_cada_uno(self):
        r = ph.extract_multiple_pairs(
            "351005 350976 350977 350988\n"
            "8570306 8570325 8570312 8570289")
        self.assertEqual(r, [(351005, 8570306), (350976, 8570325),
                             (350977, 8570312), (350988, 8570289)])

    def test_todo_aplanado_en_una_fila(self):
        r = ph.extract_multiple_pairs(
            "351005 350976 350977 8570306 8570325 8570312")
        self.assertEqual(r, [(351005, 8570306), (350976, 8570325),
                             (350977, 8570312)])

    def test_no_produce_latitudes_imposibles(self):
        """Regresión directa del caso reportado."""
        r = ph.extract_multiple_pairs(
            "351005 350976 350977 350988\n"
            "8570306 8570325 8570312 8570289")
        for este, norte in r:
            self.assertLess(este, 1000000, "el Este no puede ser un Norte")
            self.assertGreater(norte, 1000000, "el Norte debe ser mayor")

    def test_pares_consecutivos_en_una_linea(self):
        r = ph.extract_multiple_pairs("351005 8570306 350976 8570325")
        self.assertEqual(r, [(351005, 8570306), (350976, 8570325)])


class TestTextoDeOcrCorrupto(unittest.TestCase):
    """Un OCR imperfecto no debe desarmar la detección por columnas.

    Caso real: al pegar una captura, el reconocimiento leyó 351CNJO por
    351000 y 856916 por 8569916. La versión anterior partía la lista por
    la mitad, de modo que un solo valor mal leído descolocaba el corte y
    todos los pares salían (Este, Este).
    """

    OCR = ("351005 350976 350977 350988 350945 351CNJO 351021 350910 "
           "350942 350518 350293\n"
           "351393 351725 351047 8570306 8570325 8570312 8570289 8570171 "
           "8570330 8570321\n"
           "8570300 8570150 8570131 856916 8570711 8570680 857CHJ46")

    def test_ningun_par_es_incoherente(self):
        for este, norte in ph.extract_multiple_pairs(self.OCR):
            self.assertLess(abs(este), 1000000)
            self.assertGreaterEqual(abs(norte), 1000000)

    def test_recupera_la_mayoria_de_los_puntos(self):
        r = ph.extract_multiple_pairs(self.OCR)
        self.assertGreaterEqual(len(r), 10)

    def test_descarta_el_valor_corrompido(self):
        """856916 es un Norte al que el OCR comió un dígito: no es un Este."""
        r = ph.extract_multiple_pairs(self.OCR)
        self.assertNotIn(856916, [e for e, _ in r])


class TestEmparejarPorColumnas(unittest.TestCase):
    """La heurística debe ser conservadora: ante la duda, no reordenar."""

    def test_detecta_separacion_nitida(self):
        r = ph._emparejar_por_columnas(
            [351005, 350976, 8570306, 8570325])
        self.assertEqual(r, [(351005, 8570306), (350976, 8570325)])

    def test_rechaza_magnitudes_parecidas(self):
        # Ya vienen como pares: no debe reordenarlos.
        self.assertEqual(
            ph._emparejar_por_columnas([100, 110, 120, 130]), [])

    def test_rechaza_muy_pocos_valores(self):
        self.assertEqual(ph._emparejar_por_columnas([351005, 8570306]), [])

    def test_separa_por_magnitud_no_por_posicion(self):
        """Aunque vengan entremezclados, agrupa Estes y Nortes."""
        r = ph._emparejar_por_columnas(
            [351005, 350976, 350977, 8570306, 8570325, 8570312])
        self.assertEqual(r, [(351005, 8570306), (350976, 8570325),
                             (350977, 8570312)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
