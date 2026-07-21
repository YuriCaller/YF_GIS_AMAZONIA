# -*- coding: utf-8 -*-
"""
Layout Tools — Table Style Manager.
Aplica, copia, pega y guarda estilos de tablas en el compositor de QGIS.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os
from qgis.PyQt.QtWidgets import QMessageBox, QApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsPrintLayout

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Layout Tools — Table Style Manager."""

    TOOL_NAME = "Table Style Manager"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)

    def run(self):
        import traceback
        try:
            layout = self._get_active_layout()
            if layout is None:
                return
            self._abrir_dialogo(layout)
        except Exception as e:
            log_error(f"Layout Tools: error: {e}")
            traceback.print_exc()

    # ─────────────────────────────────────────────────────────────────
    # Diálogo
    # ─────────────────────────────────────────────────────────────────

    def _abrir_dialogo(self, layout):
        import traceback
        try:
            from .dialog import TableStyleDialog
            dlg = TableStyleDialog(layout, self.iface.mainWindow())
        except Exception as e:
            log_error(f"Layout Tools: error construyendo diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Table Style Manager",
                f"No se pudo abrir el diálogo:\n\n{e}"
            )
            return

        # El diálogo aplica el estilo directamente con su botón "Aplicar"
        # Solo abrimos el diálogo — no aplicamos al cerrar
        dlg.exec()

    # ─────────────────────────────────────────────────────────────────
    # Selector de layout
    # ─────────────────────────────────────────────────────────────────

    def _get_active_layout(self):
        """Retorna el layout activo o pide al usuario que elija uno."""
        from qgis.core import QgsProject
        from qgis.PyQt.QtWidgets import QInputDialog

        project = QgsProject.instance()
        layouts = [
            l for l in project.layoutManager().layouts()  # noqa: E741
            if isinstance(l, QgsPrintLayout)
        ]
        if not layouts:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Table Style Manager",
                "No hay ningún Layout de Impresión en el proyecto."
            )
            return None
        if len(layouts) == 1:
            return layouts[0]

        nombres = [l.name() for l in layouts]  # noqa: E741
        nombre, ok = QInputDialog.getItem(
            self.iface.mainWindow(),
            "YF · Table Style Manager",
            "Selecciona el layout:",
            nombres, 0, False
        )
        if not ok:
            return None
        return next(l for l in layouts if l.name() == nombre)  # noqa: E741
