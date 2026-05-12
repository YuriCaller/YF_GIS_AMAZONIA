# -*- coding: utf-8 -*-
"""
SAF Generator - Generador Profesional de Sistemas Agroforestales.

Generates planting points for agroforestry systems with:
- Unique plant identification (column letter + row number)
- Multiple spatial distribution methods
- Custom row orientation
- Automatic grid lines and symbology
"""

from ...core.base_tool import BaseTool
from ...core.logger import log_info


class Tool(BaseTool):
    """SAF Generator tool entry point."""

    TOOL_NAME = "SAF Generator"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._dialog = None

    def run(self):
        """Open the SAF Generator dialog."""
        log_info("Abriendo SAF Generator")
        from .dialog import GeneradorPlantacionDialog

        self._dialog = GeneradorPlantacionDialog(self.iface)
        self._dialog.exec_()

    def unload(self):
        """Clean up."""
        if self._dialog:
            self._dialog.close()
            self._dialog = None
