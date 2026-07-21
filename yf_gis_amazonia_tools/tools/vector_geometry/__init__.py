# -*- coding: utf-8 -*-
"""
Vector Geometry — Módulo principal.

Calcula atributos geométricos (área, perímetro, centroide, longitud,
azimut, coordenadas) directamente sobre la misma capa, sin crear
capas nuevas. Accesible desde clic derecho en el panel de capas.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

try:
    from qgis.PyQt.QtGui import QAction        # Qt6: QAction vive en QtGui
except ImportError:
    from qgis.PyQt.QtWidgets import QAction    # Qt5: QAction vive en QtWidgets
import logging
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsWkbTypes, QgsProject

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Vector Geometry — calcula atributos geométricos en la misma capa."""

    TOOL_NAME = "Calcular Geometría Vectorial"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._context_action = None
        self._setup_context_menu()

    # ─────────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────────

    def _setup_context_menu(self):
        """Registra la acción en el menú contextual del panel de capas."""
        try:
            import os
            icon_path = os.path.join(self.plugin_dir, "icons", "vector_geometry.png")
            icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

            self._context_action = QAction(
                icon,
                "YF · Calcular Geometría Vectorial",
                self.iface.mainWindow()
            )
            self._context_action.triggered.connect(self._run_from_context)
            self.iface.addCustomActionForLayerType(
                self._context_action,
                "",          # grupo (vacío = sin grupo extra)
                0,           # QgsMapLayerType.VectorLayer
                True         # allLayers
            )
            log_info("Vector Geometry: acción de contexto registrada en panel de capas")
        except Exception as e:
            log_error(f"Vector Geometry: error registrando contexto: {e}")

    def unload(self):
        """Limpia la acción del menú contextual."""
        if self._context_action:
            try:
                self.iface.removeCustomActionForLayerType(self._context_action)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self._context_action = None

    # ─────────────────────────────────────────────────────────────────
    # Entry points
    # ─────────────────────────────────────────────────────────────────

    def run(self):
        """Llamado desde el menú principal — usa la capa activa."""
        layer = self.iface.activeLayer()
        if not self._validar_capa(layer):
            return
        self._abrir_dialogo(layer)

    def _run_from_context(self):
        """Llamado desde clic derecho en panel de capas."""
        layer = self.iface.activeLayer()
        if not self._validar_capa(layer):
            return
        self._abrir_dialogo(layer)

    # ─────────────────────────────────────────────────────────────────
    # Lógica principal
    # ─────────────────────────────────────────────────────────────────

    def _abrir_dialogo(self, layer):
        import traceback
        try:
            from .dialog import VectorGeometryDialog
        except Exception as e:
            log_error(f"Vector Geometry: error importando diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Calcular Geometría",
                f"No se pudo cargar el diálogo:\n\n{e}"
            )
            return

        try:
            dlg = VectorGeometryDialog(layer, self.iface.mainWindow())
        except Exception as e:
            log_error(f"Vector Geometry: error construyendo diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Calcular Geometría",
                f"Error al construir el diálogo:\n\n{e}"
            )
            return

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            from .geometry_calculator import (
                calcular_poligono, calcular_linea, calcular_punto
            )
            opciones = dlg.get_opciones()
            target_crs = dlg.get_crs()
            solo_sel = dlg.get_solo_seleccion()
            geom_type = QgsWkbTypes.geometryType(layer.wkbType())

            if geom_type == 2:
                count = calcular_poligono(layer, opciones, target_crs, solo_sel,
                                          metodo=dlg.get_metodo())
            elif geom_type == 1:
                count = calcular_linea(layer, opciones, target_crs, solo_sel,
                                       metodo=dlg.get_metodo())
            else:
                count = calcular_punto(layer, opciones, target_crs, solo_sel)

            layer.triggerRepaint()
            campos_activos = list(opciones.values())
            self.iface.messageBar().pushSuccess(
                "YF · Geometría calculada",
                f"{count} features actualizadas · Campos: {', '.join(campos_activos)}"
            )
            log_info(f"Vector Geometry: {count} features procesadas en '{layer.name()}'")

        except Exception as e:
            log_error(f"Vector Geometry error al calcular: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Calcular Geometría",
                f"Ocurrió un error al calcular:\n\n{e}"
            )

    # ─────────────────────────────────────────────────────────────────
    # Validación
    # ─────────────────────────────────────────────────────────────────

    def _validar_capa(self, layer):
        from qgis.core import QgsVectorLayer
        if layer is None:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Calcular Geometría",
                "No hay ninguna capa activa.\n\n"
                "Selecciona una capa vectorial en el panel de capas."
            )
            return False

        if not isinstance(layer, QgsVectorLayer):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Calcular Geometría",
                f"La capa '{layer.name()}' no es una capa vectorial."
            )
            return False

        if not layer.isEditable() and not layer.dataProvider().capabilities():
            QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Calcular Geometría",
                "La capa no tiene permisos de escritura."
            )
            return False

        return True
