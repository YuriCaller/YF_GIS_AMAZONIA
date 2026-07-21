# -*- coding: utf-8 -*-
"""
Layout Rescaler — Redimensiona el layout de QGIS escalando todos
los elementos proporcionalmente, como el checkbox de ArcMap.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os
try:
    from qgis.PyQt.QtGui import QAction        # Qt6: QAction vive en QtGui
except ImportError:
    from qgis.PyQt.QtWidgets import QAction    # Qt5: QAction vive en QtWidgets
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtWidgets import QMessageBox, QApplication, QToolBar
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsPrintLayout

from ...core.base_tool import BaseTool

from qgis.core import QgsUnitTypes as _QUT
_MM_COMPAT = getattr(getattr(_QUT, 'LayoutUnit', _QUT),
                     'LayoutMillimeters',
                     getattr(_QUT, 'LayoutMillimeters', None))
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Layout Rescaler — escala proporcional al cambiar tamaño de hoja."""

    TOOL_NAME = "Redimensionar Layout"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._injected_toolbars = []  # (toolbar, separator, action)

        # Señal para futuros designers
        try:
            self.iface.layoutDesignerOpened.connect(self._on_designer_opened)
            log_info("Layout Rescaler: señal layoutDesignerOpened conectada")
        except Exception as e:
            log_error(f"Layout Rescaler: señal no disponible: {e}")

        # Inyectar en designers YA abiertos
        self._inject_into_open_designers()

    def unload(self):
        try:
            self.iface.layoutDesignerOpened.disconnect(self._on_designer_opened)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        # Limpiar acciones inyectadas
        for toolbar, sep, action in self._injected_toolbars:
            try:
                toolbar.removeAction(action)
                toolbar.removeAction(sep)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
        self._injected_toolbars.clear()

    # ─────────────────────────────────────────────────────────────────
    # Inyección en el compositor
    # ─────────────────────────────────────────────────────────────────

    def _on_designer_opened(self, designer):
        """Señal: nuevo compositor abierto."""
        log_info("Layout Rescaler: compositor abierto detectado via señal")
        self._inject_into_designer(designer)

    def _inject_into_open_designers(self):
        """
        Busca designers ya abiertos usando QApplication.topLevelWidgets()
        ya que son ventanas independientes, no hijos de mainWindow().
        """
        try:
            for widget in QApplication.topLevelWidgets():
                class_name = type(widget).__name__
                # Detectar por nombre de clase O por presencia del método layout()
                es_designer = (
                    "LayoutDesigner" in class_name or
                    "PrintComposer" in class_name or
                    "LayoutDesignerDialog" in class_name
                )
                # Verificación adicional: tiene método layout() que retorna QgsPrintLayout
                if not es_designer and hasattr(widget, "layout") and callable(widget.layout):
                    try:
                        from qgis.core import QgsPrintLayout
                        lay = widget.layout()
                        if isinstance(lay, QgsPrintLayout):
                            es_designer = True
                    except Exception:
                        logging.getLogger(__name__).debug("suppressed", exc_info=True)
                if es_designer:
                    log_info(f"Layout Rescaler: designer detectado: {class_name}")
                    self._inject_into_designer(widget)
        except Exception as e:
            log_error(f"Layout Rescaler: error buscando designers abiertos: {e}")

    def _inject_into_designer(self, designer):
        """Agrega el botón YF a la toolbar del compositor."""
        try:
            icon_path = os.path.join(self.plugin_dir, "icons", "layout_rescaler.png")
            icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

            action = QAction(icon, "YF · Redimensionar Layout", designer)
            action.setToolTip("YF · Redimensionar layout proporcionalmente")
            action.triggered.connect(
                lambda checked=False, d=designer: self._run_for_designer(d)
            )

            # Buscar toolbar — probar métodos conocidos de QgsLayoutDesignerInterface
            toolbar = None
            for method_name in ["actionsToolbar", "layoutToolbar",
                                 "navigationToolbar", "atlasToolbar"]:
                if hasattr(designer, method_name):
                    try:
                        tb = getattr(designer, method_name)()
                        if tb is not None:
                            toolbar = tb
                            log_info(f"Layout Rescaler: toolbar encontrada via {method_name}()")
                            break
                    except Exception:
                        logging.getLogger(__name__).debug("suppressed", exc_info=True)

            # Fallback: primera QToolBar hija del designer
            if toolbar is None:
                toolbars = designer.findChildren(QToolBar)
                if toolbars:
                    toolbar = toolbars[0]
                    log_info("Layout Rescaler: usando primera QToolBar del compositor")

            if toolbar is not None:
                sep = toolbar.addSeparator()
                toolbar.addAction(action)
                self._injected_toolbars.append((toolbar, sep, action))
                log_info("Layout Rescaler: ✅ botón inyectado en toolbar del compositor")
            else:
                log_error("Layout Rescaler: no se encontró ninguna toolbar en el compositor")

        except Exception as e:
            log_error(f"Layout Rescaler: error inyectando botón: {e}")
            import traceback
            traceback.print_exc()

    def _run_for_designer(self, designer):
        """Ejecuta el rescaler desde el compositor."""
        try:
            # QgsLayoutDesignerInterface.layout() o .currentLayout()
            layout = None
            for method in ["layout", "currentLayout"]:
                if hasattr(designer, method):
                    try:
                        layout = getattr(designer, method)()
                        if layout is not None:
                            break
                    except Exception:
                        logging.getLogger(__name__).debug("suppressed", exc_info=True)

            if layout is None:
                QMessageBox.warning(
                    designer, "YF · Layout Rescaler",
                    "No se pudo obtener el layout activo del compositor."
                )
                return
            self._abrir_dialogo(layout)
        except Exception as e:
            log_error(f"Layout Rescaler: error desde compositor: {e}")

    # ─────────────────────────────────────────────────────────────────
    # Entry point desde menú/toolbar QGIS principal
    # ─────────────────────────────────────────────────────────────────

    def run(self):
        import traceback
        try:
            layout = self._get_active_layout()
            if layout is None:
                return
            self._abrir_dialogo(layout)
        except Exception as e:
            log_error(f"Layout Rescaler error: {e}")
            traceback.print_exc()

    # ─────────────────────────────────────────────────────────────────
    # Diálogo y cálculo
    # ─────────────────────────────────────────────────────────────────

    def _abrir_dialogo(self, layout):
        import traceback
        try:
            from .dialog import LayoutRescalerDialog
            dlg = LayoutRescalerDialog(layout, self.iface.mainWindow())
        except Exception as e:
            log_error(f"Layout Rescaler: error abriendo diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(), "Error — YF Layout Rescaler",
                f"No se pudo abrir el diálogo:\n\n{e}"
            )
            return

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        layout = dlg.get_layout()   # elegido en el combo del diálogo
        new_w, new_h   = dlg.get_new_size()
        scale_elements = dlg.get_scale_elements()
        scale_fonts    = dlg.get_scale_fonts()

        try:
            if scale_elements:
                from .rescaler_engine import rescale_layout
                stats, old_w, old_h = rescale_layout(layout, new_w, new_h, scale_fonts)
                msg = "Layout redimensionado correctamente"
                if stats["errores"]:
                    log_error("Advertencias: " + "; ".join(stats["detalles"]))
            else:
                from qgis.core import QgsLayoutSize, QgsUnitTypes
                page = layout.pageCollection().page(0)
                page.setPageSize(QgsLayoutSize(new_w, new_h,
                                               _MM_COMPAT))
                layout.refresh()
                msg = f"Página actualizada a {new_w:.0f}×{new_h:.0f} mm"

            self.iface.messageBar().pushSuccess("YF · Layout Rescaler", msg)

        except Exception as e:
            log_error(f"Layout Rescaler error al aplicar: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(), "Error — YF Layout Rescaler",
                f"Error al redimensionar:\n\n{e}"
            )

    # ─────────────────────────────────────────────────────────────────
    # Selector de layout activo
    # ─────────────────────────────────────────────────────────────────

    def _get_active_layout(self):
        from qgis.core import QgsProject
        from qgis.PyQt.QtWidgets import QInputDialog
        layouts = [
            l for l in QgsProject.instance().layoutManager().layouts()  # noqa: E741
            if isinstance(l, QgsPrintLayout)
        ]
        if not layouts:
            QMessageBox.warning(
                self.iface.mainWindow(), "YF · Layout Rescaler",
                "No hay ningún Layout de Impresión en el proyecto."
            )
            return None
        if len(layouts) == 1:
            return layouts[0]
        nombres = [l.name() for l in layouts]  # noqa: E741
        nombre, ok = QInputDialog.getItem(
            self.iface.mainWindow(), "YF · Layout Rescaler",
            "Selecciona el layout:", nombres, 0, False
        )
        if not ok:
            return None
        return next(l for l in layouts if l.name() == nombre)  # noqa: E741
