# -*- coding: utf-8 -*-
"""
Attribute Search v1.1 — Integrado en YF GIS Amazonia Tools.

Búsqueda avanzada de atributos multi-capa con:
- Búsqueda simple y avanzada (expresiones QGIS)
- Visualización de resultados con gráficos
- Generación de reportes
- Exportación a CSV/Excel
- Zoom, selección y resaltado de features

Correcciones v1.1 (integración):
- Fix inyección SQL en búsqueda (escape de comillas simples)
- Fix legendInterface() deprecado (QGIS 3.x)
- Fix wkbType().name() incompatible
- Imports condicionales para pandas/matplotlib/docx
"""

from ...core.base_tool import BaseTool
from ...core.logger import log_info


class Tool(BaseTool):
    """Attribute Search tool entry point."""

    TOOL_NAME = "Attribute Search"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._dock = None
        self._dialog = None

    def run(self):
        """Toggle the Attribute Search dock panel."""
        log_info("Abriendo Búsqueda Avanzada de Atributos")

        from qgis.PyQt.QtWidgets import QDockWidget
        from qgis.PyQt.QtCore import Qt

        if self._dock is None:
            from .ui.main_dialog import MainDialog

            self._dialog = MainDialog(self.iface)
            self._dialog.closingPlugin.connect(self._on_closed)

            self._dock = QDockWidget(
                "Búsqueda Avanzada de Atributos",
                self.iface.mainWindow(),
            )
            self._dock.setAllowedAreas(
                Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
            )
            self._dock.setMinimumSize(800, 600)
            self._dock.setWidget(self._dialog.widget())
            self.iface.mainWindow().addDockWidget(
                Qt.RightDockWidgetArea, self._dock
            )
        else:
            self._dock.setVisible(not self._dock.isVisible())

    def _on_closed(self):
        """Handle dialog close signal."""
        if self._dock:
            self._dock.setVisible(False)

    def unload(self):
        """Remove the dock widget."""
        if self._dock:
            self.iface.mainWindow().removeDockWidget(self._dock)
            self._dock = None
        if self._dialog:
            self._dialog.close()
            self._dialog = None
