# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición de Derechos.

Evalúa un predio contra una carpeta de capas de derechos preexistentes
(concesiones forestales, BPP, predios, lotes de hidrocarburos, ANP,
comunidades nativas...) y produce:

  · Tabla de superposiciones con titular, código, área y % del predio
  · GeoPackage con las geometrías de intersección para el plano
  · Trazabilidad verificable: hash SHA-256 por archivo + log JSON

Reemplaza el flujo "iterador + Model Builder" de ArcGIS por un recorrido
recursivo de carpeta, con índice espacial y reparación de geometrías.

Módulos:
  data_contract.py  — contrato de datos único
  layer_scanner.py  — recorrido recursivo (incluye sub-capas de GeoPackage)
  overlap_engine.py — motor de intersección
  traceability.py   — hashes y log reproducible
  output_export.py  — GeoPackage / CSV / anexo de verificación
  dialog.py         — interfaz

Pendiente (v3.4): plantillas de informe docxtpl por institución.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Análisis de superposición de derechos preexistentes."""

    TOOL_NAME = "Análisis de Superposición"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._dialogo = None

    def _on_dialogo_destruido(self):
        """La referencia Python queda colgando cuando Qt destruye el widget
        (WA_DeleteOnClose); limpiarla evita usar un objeto C++ ya borrado."""
        self._dialogo = None

    def unload(self):
        if self._dialogo is not None:
            try:
                self._dialogo.close()
                self._dialogo.deleteLater()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self._dialogo = None

    def _version(self):
        """Versión declarada en metadata.txt (va al informe y al log)."""
        import os
        ruta = os.path.join(self.plugin_dir, "metadata.txt")
        try:
            with open(ruta, encoding="utf-8") as f:
                for linea in f:
                    if linea.startswith("version="):
                        return linea.split("=", 1)[1].strip()
        except OSError:
            pass
        return ""

    def run(self):
        from .dialog import SuperposicionDialog
        try:
            # v3.0.4 fix: recrear el diálogo en cada apertura en vez de
            # reutilizar uno persistente. Un diálogo reutilizado arrastra
            # estado (resultado previo, capas escaneadas) que hacía que
            # abrir la herramienta se volviera más lento con el uso.
            if self._dialogo is not None:
                try:
                    self._dialogo.close()
                    self._dialogo.deleteLater()
                except Exception:
                    logging.getLogger(__name__).debug("suppressed",
                                                      exc_info=True)
                self._dialogo = None

            self._dialogo = SuperposicionDialog(
                self.iface, plugin_version=self._version(),
                parent=self.iface.mainWindow())
            # No-modal: no bloquea QGIS, pero se destruye al cerrar para
            # no dejar residuos entre sesiones.
            try:
                from qgis.PyQt.QtCore import Qt
                self._dialogo.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            try:
                self._dialogo.destroyed.connect(self._on_dialogo_destruido)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self._dialogo.show()
            self._dialogo.raise_()
            self._dialogo.activateWindow()
            log_info("Análisis de Superposición abierto")
        except Exception as e:
            log_error("Error al abrir Análisis de Superposición: {}".format(e))
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.iface.mainWindow(), "Análisis de Superposición",
                "No se pudo abrir la herramienta:\n{}".format(e))
