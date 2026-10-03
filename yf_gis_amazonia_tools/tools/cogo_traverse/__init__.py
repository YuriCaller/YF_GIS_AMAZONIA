# -*- coding: utf-8 -*-
"""
COGO — Poligonal en Vivo

Digitalización de una poligonal por azimut y distancia, lado a lado,
con dibujo en vivo en el canvas — estilo "Traverse" de ArcGIS Pro.

Es un segundo frontend para el motor de core/poligonal.py: el primero
es la tabla pegada de "Reconstruir predio" (Memoria Descriptiva, modo
batch); este es interactivo, para cuando no se tiene la tabla completa
a mano y conviene ir metiendo los lados mientras se los lee del plano.

Autor: Yuri F. Caller Cordova — TUCSA / gis-amazonia.pe
"""

import logging

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error
from ...core.crs_utils import is_projected


class Tool(BaseTool):
    """COGO — Poligonal en Vivo — punto de entrada de la herramienta."""

    TOOL_NAME = "COGO — Poligonal en Vivo"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self.canvas = iface.mapCanvas()
        self.map_tool = None
        self.panel = None

    def run(self):
        from qgis.core import QgsProject
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtWidgets import QMessageBox

        crs = QgsProject.instance().crs()
        if not is_projected(crs):
            QMessageBox.warning(
                self.iface.mainWindow(), "COGO — Poligonal en Vivo",
                "El proyecto está en un CRS geográfico (grados). El COGO "
                "necesita un CRS proyectado (metros) para que azimut y "
                "distancia tengan sentido. Cambia el CRS del proyecto a "
                "una zona UTM antes de continuar.")
            return

        if self.panel is not None:
            # Ya estaba abierto: solo lo traemos al frente.
            self.panel.show()
            self.panel.raise_()
            return

        try:
            from .map_tool import CogoMapTool
            from .panel import CogoPanel

            self.map_tool = CogoMapTool(self.canvas)
            self.panel = CogoPanel(self.iface, self.map_tool,
                                   parent=self.iface.mainWindow())
            self.panel.visibilityChanged.connect(self._on_visibilidad)
            self.iface.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.panel)
            self.panel.show()
            log_info("COGO — Poligonal en Vivo: panel abierto")
        except Exception as e:
            import traceback
            log_error(f"COGO — Poligonal en Vivo: error al abrir: {e}\n"
                      f"{traceback.format_exc()}")

    def _on_visibilidad(self, visible):
        if not visible and self.map_tool is not None:
            self.map_tool.limpiar()

    def unload(self):
        if self.panel is not None:
            try:
                self.iface.removeDockWidget(self.panel)
                self.panel.deleteLater()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.panel = None
        if self.map_tool is not None:
            try:
                self.map_tool.limpiar()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.map_tool = None
