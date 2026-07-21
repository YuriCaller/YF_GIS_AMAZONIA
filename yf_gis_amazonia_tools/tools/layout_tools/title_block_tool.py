# -*- coding: utf-8 -*-
"""
Title Block Tool — entry point del generador de cajetín Predio Agrícola.
El layout de destino se elige dentro del diálogo (combo desplegable).
Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsProject, QgsPrintLayout

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Generador de cajetín — modelo único Predio Agrícola."""

    TOOL_NAME = "Generar Cajetín"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)

    def run(self):
        import traceback
        try:
            layouts = [l for l in  # noqa: E741
                       QgsProject.instance().layoutManager().layouts()
                       if isinstance(l, QgsPrintLayout)]
            if not layouts:
                QMessageBox.warning(
                    self.iface.mainWindow(), "YF · Cajetín",
                    "No hay ningún Layout de Impresión en el proyecto.\n"
                    "Crea uno en Proyecto → Diseñador de Impresión.")
                return
            # El layout definitivo se elige en el combo del diálogo;
            # el primero solo preselecciona.
            self._abrir_dialogo(layouts[0])
        except Exception as e:
            log_error(f"Title Block: error: {e}")
            traceback.print_exc()

    def _abrir_dialogo(self, layout_inicial):
        import traceback
        try:
            from .title_block_dialog import TitleBlockDialog
            dlg = TitleBlockDialog(layout_inicial, self.iface.mainWindow())
        except Exception as e:
            log_error(f"Title Block: error construyendo diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(), "Error — YF Cajetín",
                f"No se pudo abrir el diálogo:\n\n{e}")
            return

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            from .title_block_engine import generar_cajetin
            layout = dlg.get_layout()          # ← elegido en el combo
            datos = dlg.get_datos()
            pos_x, pos_y = dlg.get_posicion()

            items = generar_cajetin(
                layout, dlg.get_plantilla(), pos_x, pos_y,
                datos, logo_path=dlg.get_logo())

            self.iface.messageBar().pushSuccess(
                "YF · Cajetín",
                f"Cajetín generado con {len(items)} elementos "
                f"en '{layout.name()}'")
            log_info(
                f"Title Block: cajetín generado en '{layout.name()}' "
                f"({pos_x:.1f}, {pos_y:.1f}) mm")

            self.iface.openLayoutDesigner(layout)

        except Exception as e:
            log_error(f"Title Block: error generando: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(), "Error — YF Cajetín",
                f"Error al generar el cajetín:\n\n{e}")
