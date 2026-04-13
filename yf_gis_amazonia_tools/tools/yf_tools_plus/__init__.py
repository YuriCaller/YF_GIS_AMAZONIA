# -*- coding: utf-8 -*-
"""
YF Tools Plus v2.3 — Integrado en YF GIS Amazonia Tools.

Herramientas de topografía catastral:
- Tab 0: Convertir Excel a CSV
- Tab 1: Crear polígonos desde CSV
- Tab 2: Segmentar polígonos (líneas + vértices con azimut)
- Tab 3: Exportar tablas a Excel
"""

from ...core.base_tool import BaseTool
from ...core.logger import log_info


class Tool(BaseTool):
    """YF Tools Plus tool entry point."""

    TOOL_NAME = "YF Tools Plus"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._dialog = None

    def _ensure_dialog(self):
        """Lazy-create the dialog."""
        if self._dialog is None:
            from .yf_tools_plus_dialog import YF_Tools_PlusDialog
            self._dialog = YF_Tools_PlusDialog(self.iface)

    def run(self, tab_index=None):
        """Open the YF Tools Plus dialog, optionally at a specific tab."""
        log_info("Abriendo YF Tools Plus")
        self._ensure_dialog()

        if tab_index is not None:
            self._dialog.tabWidget.setCurrentIndex(tab_index)

        self._dialog.show()

    def run_segmentador(self):
        """Shortcut to open directly on the Segmentator tab."""
        self.run(tab_index=2)

    def unload(self):
        if self._dialog:
            self._dialog.close()
            self._dialog = None
