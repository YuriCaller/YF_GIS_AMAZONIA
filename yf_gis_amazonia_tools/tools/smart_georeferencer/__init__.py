# -*- coding: utf-8 -*-
"""
Smart Georeferencer — Georreferenciación dinámica en vivo.

Módulo de la suite YF GIS Amazonia Tools. Coloca una imagen (plano escaneado,
ortofoto, etc.) como capa en la TOC y permite georreferenciarla en tiempo real:
captura de GCPs estilo ArcGIS (dos clics), autoensamblado a vértices, warp TPS,
detección automática de puntos (OpenCV), diagnóstico de calidad leave-one-out y
exportación a GeoTIFF full-res.

Expone la clase `Tool` que el ToolRegistry de la suite instancia y ejecuta.
"""
import logging
from qgis.PyQt.QtCore import Qt

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error

from .dock import GeorefDock


class Tool(BaseTool):
    TOOL_NAME = "Smart Georeferencer"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self.dock = None

    def run(self):
        """Muestra (o crea) el panel acoplado del georreferenciador."""
        if self.dock is None:
            try:
                self.dock = GeorefDock(self.iface)
            except Exception as e:
                log_error(f"No se pudo crear el panel de Smart Georeferencer: {e}")
                raise
            self.iface.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
            log_info("Smart Georeferencer abierto.")
        self.dock.setVisible(True)
        self.dock.raise_()

    def unload(self):
        """Cierra la sesión y quita el panel al descargar el plugin."""
        if self.dock is not None:
            try:
                self.dock._finish_session(remove_layer=False)
                self.iface.removeDockWidget(self.dock)
                self.dock.deleteLater()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.dock = None
