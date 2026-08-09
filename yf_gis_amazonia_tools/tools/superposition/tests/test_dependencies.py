# -*- coding: utf-8 -*-
"""
Pruebas de core/dependencies.

El foco está en el diagnóstico de fallos: el valor de este módulo no es
instalar (eso lo hace pip), sino explicarle al usuario por qué NO pudo
instalarse cuando trabaja en una entidad con la red restringida.

Corren sin QGIS: solo se prueban las funciones que no tocan Qt.
"""

import importlib.util
import os
import sys
import types
import unittest

_AQUI = os.path.dirname(os.path.abspath(__file__))
_CORE = os.path.abspath(os.path.join(_AQUI, "..", "..", "..", "core"))

_PKG = "yf_dep_test"
if _PKG not in sys.modules:
    m = types.ModuleType(_PKG)
    m.__path__ = [_CORE]
    sys.modules[_PKG] = m

spec = importlib.util.spec_from_file_location(
    _PKG + ".dependencies", os.path.join(_CORE, "dependencies.py"))
dep = importlib.util.module_from_spec(spec)
sys.modules[_PKG + ".dependencies"] = dep
spec.loader.exec_module(dep)


class TestLocalizarPython(unittest.TestCase):

    def test_devuelve_una_ruta(self):
        self.assertTrue(dep.localizar_python())

    def test_reconoce_un_interprete_directo(self):
        # En este entorno sys.executable ES python, debe devolverlo tal cual.
        if "python" in os.path.basename(sys.executable).lower():
            self.assertEqual(dep.localizar_python(), sys.executable)


class TestDisponibilidad(unittest.TestCase):

    def test_modulo_existente(self):
        self.assertTrue(dep.esta_disponible("json"))

    def test_modulo_inexistente(self):
        self.assertFalse(dep.esta_disponible("modulo_que_no_existe_xyz"))


class TestDiagnostico(unittest.TestCase):
    """Cada fallo típico de una red institucional debe explicarse claro."""

    def test_proxy(self):
        d = dep._diagnosticar("ProxyError: Cannot connect to proxy")
        self.assertIn("proxy", d.lower())

    def test_certificado_ssl(self):
        d = dep._diagnosticar(
            "SSLError: CERTIFICATE_VERIFY_FAILED certificate verify failed")
        self.assertIn("certificado", d.lower())

    def test_permisos(self):
        d = dep._diagnosticar("ERROR: Could not install: Permission denied")
        self.assertIn("permisos", d.lower())

    def test_sin_internet(self):
        d = dep._diagnosticar(
            "Failed to establish a new connection: Temporary failure in "
            "name resolution")
        self.assertIn("internet", d.lower())

    def test_paquete_inexistente(self):
        d = dep._diagnosticar(
            "ERROR: Could not find a version that satisfies the requirement")
        self.assertIn("pypi", d.lower())

    def test_sin_pip(self):
        d = dep._diagnosticar("/usr/bin/python: No module named pip")
        self.assertIn("pip", d.lower())

    def test_fallo_desconocido_no_deja_al_usuario_sin_mensaje(self):
        d = dep._diagnosticar("algo raro ocurrio")
        self.assertTrue(d)
        self.assertIn("fall", d.lower())

    def test_salida_vacia_no_rompe(self):
        self.assertTrue(dep._diagnosticar(""))
        self.assertTrue(dep._diagnosticar(None))


class TestInstalacion(unittest.TestCase):
    """No se instala nada real: se comprueba el manejo de errores."""

    def test_paquete_inexistente_devuelve_diagnostico(self):
        ok, salida, diag = dep.instalar_paquete(
            "yf-paquete-que-no-existe-000", timeout=90)
        self.assertFalse(ok)
        self.assertTrue(diag, "debe explicar la causa, no quedarse mudo")

    def test_timeout_no_lanza_excepcion(self):
        ok, salida, diag = dep.instalar_paquete(
            "yf-paquete-que-no-existe-000", timeout=1)
        self.assertFalse(ok)
        self.assertTrue(diag)


class TestRecarga(unittest.TestCase):

    def test_modulo_ya_presente(self):
        self.assertTrue(dep.recargar("json"))

    def test_modulo_ausente_devuelve_false(self):
        self.assertFalse(dep.recargar("modulo_que_no_existe_xyz"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
