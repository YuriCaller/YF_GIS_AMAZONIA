# -*- coding: utf-8 -*-
"""
Segmentador de Parcelas — Acceso directo al segmentador de YF Tools Plus.

Este módulo no tiene lógica propia: abre YF Tools Plus directamente
en la pestaña de Segmentación (tab 2). Esto evita duplicar código
y mantiene una sola implementación del segmentador.
"""

from ...core.base_tool import BaseTool
from ...core.logger import log_info


class Tool(BaseTool):
    """Segmentador — delegates to YF Tools Plus segmentator tab."""

    TOOL_NAME = "Segmentador"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._yf_tools = None

    def run(self):
        """Open YF Tools Plus at the Segmentator tab."""
        log_info("Abriendo Segmentador (via YF Tools Plus)")

        # Lazy-load the YF Tools Plus Tool instance
        if self._yf_tools is None:
            from ..yf_tools_plus import Tool as YFToolsPlusTool
            self._yf_tools = YFToolsPlusTool(self.iface, self.plugin_dir)

        self._yf_tools.run_segmentador()

    def unload(self):
        if self._yf_tools:
            self._yf_tools.unload()
            self._yf_tools = None
