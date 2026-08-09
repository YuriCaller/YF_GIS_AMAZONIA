# -*- coding: utf-8 -*-
"""
Comprueba que el catálogo de herramientas no se desfase del menú.

MOTIVO
------
En v3.0.6 el diálogo «Acerca de» anunciaba 8 herramientas cuando la
suite tenía 17: la lista estaba escrita a mano y nadie la actualizaba al
añadir un módulo. Este test convierte ese olvido en un fallo de pruebas.

No importa QGIS: lee plugin_manager.py como texto y extrae los tool_id
registrados. Así corre en cualquier entorno, incluido el CI.
"""

import os
import re
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(AQUI)


def _ids_del_menu():
    ruta = os.path.join(CORE, "plugin_manager.py")
    with open(ruta, encoding="utf-8") as fh:
        contenido = fh.read()
    return set(re.findall(r'tool_id\s*=\s*["\']([^"\']+)["\']', contenido))


def _catalogo():
    import importlib.util
    ruta = os.path.join(CORE, "tools_catalog.py")
    spec = importlib.util.spec_from_file_location("tools_catalog", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class TestCatalogo(unittest.TestCase):

    def setUp(self):
        self.cat = _catalogo()
        self.claves = {h.clave for h in self.cat.HERRAMIENTAS}
        self.ids = _ids_del_menu()

    def test_toda_herramienta_del_menu_esta_documentada(self):
        faltan = self.ids - self.claves
        self.assertFalse(
            faltan,
            "Herramientas registradas en el menú pero ausentes del "
            "catálogo (no saldrán en «Acerca de» ni tendrán manual): "
            "{}".format(sorted(faltan)))

    def test_no_hay_herramientas_fantasma(self):
        sobran = self.claves - self.ids
        self.assertFalse(
            sobran,
            "Herramientas en el catálogo que ya no se registran en el "
            "menú: {}".format(sorted(sobran)))

    def test_claves_unicas(self):
        claves = [h.clave for h in self.cat.HERRAMIENTAS]
        self.assertEqual(len(claves), len(set(claves)),
                         "Hay claves duplicadas en el catálogo")

    def test_campos_obligatorios(self):
        for h in self.cat.HERRAMIENTAS:
            self.assertTrue(h.nombre.strip(), h.clave)
            self.assertTrue(h.resumen.strip(), h.clave)
            self.assertIn(h.categoria, self.cat.ORDEN_CATEGORIAS,
                          "Categoría no declarada en ORDEN_CATEGORIAS: "
                          "{} ({})".format(h.categoria, h.clave))

    def test_iconos_existen(self):
        iconos = os.path.join(os.path.dirname(CORE), "icons")
        for h in self.cat.HERRAMIENTAS:
            self.assertTrue(
                os.path.exists(os.path.join(iconos, h.icono)),
                "Icono ausente para {}: {}".format(h.clave, h.icono))

    def test_existe_pagina_de_manual(self):
        """Cada herramienta debe tener su .md en docs/herramientas/."""
        docs = os.path.join(
            os.path.dirname(os.path.dirname(CORE)), "docs", "herramientas")
        if not os.path.isdir(docs):
            self.skipTest("docs/ no está en este paquete")
        for h in self.cat.HERRAMIENTAS:
            self.assertTrue(
                os.path.exists(os.path.join(docs, h.clave + ".md")),
                "Falta la página del manual: docs/herramientas/{}.md"
                .format(h.clave))


if __name__ == "__main__":
    unittest.main()
