# -*- coding: utf-8 -*-
"""
Layout Designer Integration — inyecta toolbar YF en el compositor de mapas.
Cada toolbar guarda su propia referencia al window y al layout.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os
try:
    from qgis.PyQt.QtGui import QAction        # Qt6: QAction vive en QtGui
except ImportError:
    from qgis.PyQt.QtWidgets import QAction    # Qt5: QAction vive en QtWidgets
from qgis.PyQt.QtWidgets import QToolBar, QApplication, QMainWindow
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsPrintLayout

from ..core.logger import log_info, log_error


class LayoutDesignerIntegration:
    """Inyecta toolbar YF en el compositor de mapas."""

    def __init__(self, iface, plugin_dir):
        self.iface      = iface
        self.plugin_dir = plugin_dir
        self._toolbars  = []  # lista de toolbars creadas

        try:
            self.iface.layoutDesignerOpened.connect(self._on_designer_opened)
            log_info("Layout Designer Integration: señal conectada")
        except Exception as e:
            log_error(f"Layout Designer Integration: {e}")

        # Inyectar en designers ya abiertos
        self._inject_open_designers()

    def unload(self):
        try:
            self.iface.layoutDesignerOpened.disconnect(self._on_designer_opened)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        for tb in self._toolbars:
            try:
                tb.setVisible(False)
                tb.setParent(None)
                tb.deleteLater()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
        self._toolbars.clear()

    # ─────────────────────────────────────────────────────────────────
    # Detección y señales
    # ─────────────────────────────────────────────────────────────────

    def _on_designer_opened(self, designer):
        """Señal: nuevo compositor abierto — designer es QgsLayoutDesignerInterface."""
        log_info("Layout Designer Integration: compositor abierto via señal")
        # Obtener la ventana real del designer
        win = None
        try:
            win = designer.window()
            if not isinstance(win, QMainWindow):
                win = None
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

        if win is None:
            # Buscar en topLevel
            for w in QApplication.topLevelWidgets():
                if isinstance(w, QMainWindow):
                    cn = type(w).__name__
                    if "LayoutDesigner" in cn or "PrintComposer" in cn:
                        win = w
                        break

        if win:
            # Obtener layout desde el designer interface
            layout = None
            for method in ["layout", "currentLayout"]:
                if hasattr(designer, method):
                    try:
                        lay = getattr(designer, method)()
                        if isinstance(lay, QgsPrintLayout):
                            layout = lay
                            break
                    except Exception:
                        logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self._inject_toolbar(win, layout)

    def _inject_open_designers(self):
        """Inyecta en compositors ya abiertos al cargar el plugin."""
        try:
            for widget in QApplication.topLevelWidgets():
                if not isinstance(widget, QMainWindow):
                    continue
                cn = type(widget).__name__
                if "LayoutDesigner" in cn or "PrintComposer" in cn:
                    log_info(f"Designer ya abierto: {cn}")
                    # Obtener layout desde la ventana
                    layout = None
                    for method in ["layout", "currentLayout"]:
                        if hasattr(widget, method):
                            try:
                                lay = getattr(widget, method)()
                                if isinstance(lay, QgsPrintLayout):
                                    layout = lay
                                    break
                            except Exception:
                                logging.getLogger(__name__).debug("suppressed", exc_info=True)
                    self._inject_toolbar(widget, layout)
        except Exception as e:
            log_error(f"inject_open_designers: {e}")

    # ─────────────────────────────────────────────────────────────────
    # Toolbar — guarda referencia al window y layout
    # ─────────────────────────────────────────────────────────────────

    def _inject_toolbar(self, window, layout):
        """Agrega toolbar YF al compositor guardando referencias locales."""
        try:
            # No inyectar dos veces
            for tb in window.findChildren(QToolBar):
                if tb.objectName() == "yf_layout_toolbar":
                    log_info("Toolbar YF ya existe en este compositor")
                    return

            toolbar = QToolBar("YF — Layout Tools", window)
            toolbar.setObjectName("yf_layout_toolbar")

            # Crear un handler específico para este window+layout
            handler = _LayoutToolsHandler(
                self.iface, self.plugin_dir, window, layout
            )
            # Guardar handler como atributo del toolbar para que no sea GC'd
            toolbar._yf_handler = handler

            # ── Table Style ──────────────────────────────────────────
            act1 = QAction(
                self._icon("layout_tools.png"),
                "YF · Table Style Manager", window
            )
            act1.setToolTip("Aplicar, copiar y pegar estilos de tablas")
            act1.triggered.connect(handler.run_table_style)
            toolbar.addAction(act1)

            # ── Cajetín ──────────────────────────────────────────────
            act2 = QAction(
                self._icon("title_block.png"),
                "YF · Generar Cajetín", window
            )
            act2.setToolTip("Generar cajetín de rotulación automático")
            act2.triggered.connect(handler.run_title_block)
            toolbar.addAction(act2)

            # ── Rescaler ─────────────────────────────────────────────
            act3 = QAction(
                self._icon("layout_rescaler.png"),
                "YF · Redimensionar Layout", window
            )
            act3.setToolTip("Redimensionar layout escalando todos los elementos")
            act3.triggered.connect(handler.run_rescaler)
            toolbar.addAction(act3)

            window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
            toolbar.show()
            self._toolbars.append(toolbar)
            log_info("✅ Toolbar YF inyectada en compositor")

        except Exception as e:
            log_error(f"_inject_toolbar: {e}")
            import traceback; traceback.print_exc()

    def _icon(self, filename):
        path = os.path.join(self.plugin_dir, "icons", filename)
        return QIcon(path) if os.path.exists(path) else QIcon()


# ─────────────────────────────────────────────────────────────────────────────
# Handler — clase dedicada por compositor con referencias propias
# ─────────────────────────────────────────────────────────────────────────────

class _LayoutToolsHandler:
    """
    Maneja las acciones YF para un compositor específico.
    Guarda referencia al window (padre de diálogos) y al layout.
    """

    def __init__(self, iface, plugin_dir, window, layout):
        self.iface      = iface
        self.plugin_dir = plugin_dir
        self.window     = window    # QMainWindow del compositor — padre de diálogos
        self._layout    = layout    # puede actualizarse si cambia

    def _get_layout(self):
        """Obtiene el layout — desde referencia guardada o desde el proyecto."""
        # Intentar desde la ventana del compositor directamente
        for method in ["layout", "currentLayout"]:
            if hasattr(self.window, method):
                try:
                    lay = getattr(self.window, method)()
                    if isinstance(lay, QgsPrintLayout):
                        return lay
                except Exception:
                    logging.getLogger(__name__).debug("suppressed", exc_info=True)

        # Fallback: layout guardado en el momento de inyección
        if self._layout and isinstance(self._layout, QgsPrintLayout):
            return self._layout

        # Último recurso: primer layout del proyecto
        from qgis.core import QgsProject
        layouts = [
            l for l in QgsProject.instance().layoutManager().layouts()  # noqa: E741
            if isinstance(l, QgsPrintLayout)
        ]
        return layouts[0] if layouts else None

    def run_table_style(self):
        import traceback
        try:
            from .layout_tools.dialog import TableStyleDialog
            from .layout_tools.table_style_engine import aplicar_estilo
            from qgis.PyQt.QtWidgets import QMessageBox

            # Usar SOLO el layout activo del compositor
            layout = self._get_layout()
            if not layout:
                QMessageBox.warning(
                    self.window, "YF · Table Style Manager",
                    "No se encontró el layout activo."
                )
                return

            # El diálogo tiene botón "Aplicar" que aplica directo
            # exec() solo abre el diálogo — el estilo ya se aplicó dentro
            dlg = TableStyleDialog(layout, self.window)
            dlg.exec()
        except Exception as e:
            log_error(f"run_table_style: {e}")
            traceback.print_exc()

    def run_title_block(self):
        import traceback
        try:
            layout = self._get_layout()
            if not layout:
                return
            from .layout_tools.title_block_dialog import TitleBlockDialog
            from .layout_tools.title_block_engine import generar_cajetin
            dlg = TitleBlockDialog(layout, self.window)
            if dlg.exec():
                destino = dlg.get_layout()   # elegido en el combo
                pos_x, pos_y = dlg.get_posicion()
                generar_cajetin(
                    destino, dlg.get_plantilla(),
                    pos_x, pos_y,
                    dlg.get_datos(),
                    logo_path=dlg.get_logo(),
                )
                self.iface.messageBar().pushSuccess(
                    "YF · Cajetín",
                    "Cajetín generado en '{}'".format(destino.name())
                )
        except Exception as e:
            log_error(f"run_title_block: {e}")
            traceback.print_exc()

    def run_rescaler(self):
        import traceback
        try:
            layout = self._get_layout()
            if not layout:
                return
            from .layout_rescaler.dialog import LayoutRescalerDialog
            from .layout_rescaler.rescaler_engine import rescale_layout
            from qgis.core import QgsLayoutSize, QgsUnitTypes
            dlg = LayoutRescalerDialog(layout, self.window)
            if dlg.exec():
                new_w, new_h = dlg.get_new_size()
                if dlg.get_scale_elements():
                    rescale_layout(layout, new_w, new_h, dlg.get_scale_fonts())
                else:
                    page = layout.pageCollection().page(0)
                    page.setPageSize(QgsLayoutSize(
                        new_w, new_h, QgsUnitTypes.LayoutUnit.LayoutMillimeters
                    ))
                    layout.refresh()
                self.iface.messageBar().pushSuccess(
                    "YF · Layout Rescaler",
                    f"Layout redimensionado a {new_w:.0f}×{new_h:.0f} mm"
                )
        except Exception as e:
            log_error(f"run_rescaler: {e}")
            traceback.print_exc()
