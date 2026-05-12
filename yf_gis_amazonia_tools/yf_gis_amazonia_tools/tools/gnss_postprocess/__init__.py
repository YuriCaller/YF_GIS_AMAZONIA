# -*- coding: utf-8 -*-
"""
GNSS Post-Process PPK/PPP v2.0 — Integrado en YF GIS Amazonia Tools.

Procesamiento GNSS diferencial con RTKLIB:
- PPK y PPP vía RTKLIB
- Validación geodésica estricta de bases
- Ficha técnica estilo IGN Perú (UTM, Geográficas, Cartesianas)
- Reportes PDF con reportlab
- Exportación a SHP, GPKG, KML, GeoJSON
- Archivos .cor para IGN Perú
"""

import os

from ...core.base_tool import BaseTool
from ...core.logger import log_info


class Tool(BaseTool):
    """GNSS Post-Process tool entry point."""

    TOOL_NAME = "GNSS Post-Process"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._dock = None
        self._widget = None
        # tool_dir points to this tool's directory (for icon, rtklib_bin, etc.)
        self._tool_dir = os.path.dirname(__file__)

    def run(self):
        """Toggle the GNSS dock panel."""
        log_info("Abriendo GNSS Post-Process PPK/PPP")

        from qgis.PyQt.QtWidgets import QDockWidget
        from qgis.PyQt.QtCore import Qt

        if self._dock is None:
            from .ui.main_dialog import GNSSMainDialog

            self._dock = QDockWidget(
                "GNSS Post-Process v2", self.iface.mainWindow()
            )
            self._dock.setAllowedAreas(
                Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
            )
            self._dock.setMinimumWidth(460)

            # Pass tool_dir so the dialog can find rtklib_bin, icons, etc.
            self._widget = GNSSMainDialog(self.iface, self._tool_dir)
            self._dock.setWidget(self._widget)
            self.iface.mainWindow().addDockWidget(
                Qt.RightDockWidgetArea, self._dock
            )
        else:
            self._dock.setVisible(not self._dock.isVisible())

    def unload(self):
        """Remove the dock widget."""
        if self._dock:
            self.iface.mainWindow().removeDockWidget(self._dock)
            self._dock = None
            self._widget = None
