# -*- coding: utf-8 -*-
"""
Polygon Divider — Punto de entrada del módulo.

Divide un polígono en partes por área exacta, N partes iguales o
porcentajes, mediante una línea de corte trazada por el usuario o
ajustada por ángulo. Opcionalmente crea una capa resultado separada
(GeoPackage) con atributos heredados y etiquetado automático, o edita
la capa original directamente (con confirmación explícita).

Inspirado en el comando "Divide" de ArcGIS Pro.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsWkbTypes, QgsVectorLayer

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Polygon Divider — divide el polígono activo con línea de corte."""

    TOOL_NAME = "Polygon Divider"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._dialogo_activo = None

    def unload(self):
        if self._dialogo_activo is not None:
            try:
                self._dialogo_activo.close()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self._dialogo_activo = None

    # ─────────────────────────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────────────────────────

    def run(self):
        layer = self.iface.activeLayer()
        if not self._validar_capa(layer):
            return

        feature = self._obtener_feature_objetivo(layer)
        if feature is None:
            return

        self._abrir_dialogo(layer, feature)

    # ─────────────────────────────────────────────────────────────────
    # Validación
    # ─────────────────────────────────────────────────────────────────

    def _validar_capa(self, layer):
        if layer is None:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Polygon Divider",
                "No hay ninguna capa activa.\n\n"
                "Selecciona una capa de polígonos en el panel de capas."
            )
            return False

        if not isinstance(layer, QgsVectorLayer):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Polygon Divider",
                f"La capa '{layer.name()}' no es una capa vectorial."
            )
            return False

        if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.GeometryType.PolygonGeometry:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Polygon Divider",
                f"La capa '{layer.name()}' no contiene polígonos.\n\n"
                "Esta herramienta solo divide geometrías de tipo polígono."
            )
            return False

        # Advertencia de CRS no proyectado: el cálculo de área es PLANAR
        # (cartesiano en el CRS de la capa). Con un CRS geográfico (grados),
        # las áreas serían en grados² — completamente inútiles para catastro.
        crs = layer.crs()
        if crs.isGeographic():
            respuesta = QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Polygon Divider — CRS no proyectado",
                f"La capa '{layer.name()}' usa un CRS geográfico "
                f"({crs.authid()} — {crs.description()}).\n\n"
                f"El cálculo de área de esta herramienta es PLANAR "
                f"(cartesiano), por lo que las áreas se medirían en grados² "
                f"en lugar de metros² o hectáreas. Los resultados de división "
                f"por área exacta o porcentajes serían incorrectos.\n\n"
                f"Se recomienda proyectar la capa a un CRS métrico antes de "
                f"dividir (ej. EPSG:32719 para zona 19S en Madre de Dios).\n\n"
                f"¿Deseas continuar de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return False

        return True

    def _obtener_feature_objetivo(self, layer):
        """
        Determina sobre qué feature trabajar:
        - Si hay exactamente 1 feature seleccionada → esa.
        - Si hay 0 o más de 1 seleccionadas → pide al usuario seleccionar
          exactamente un polígono (no se asume cuál).
        """
        seleccionadas = layer.selectedFeatures()

        if len(seleccionadas) == 1:
            return seleccionadas[0]

        if len(seleccionadas) == 0:
            QMessageBox.information(
                self.iface.mainWindow(),
                "YF · Polygon Divider",
                "Selecciona un polígono en la capa activa antes de "
                "ejecutar Polygon Divider.\n\n"
                "Usa la herramienta de selección de QGIS para elegir "
                "exactamente un polígono."
            )
            return None

        QMessageBox.information(
            self.iface.mainWindow(),
            "YF · Polygon Divider",
            f"Hay {len(seleccionadas)} polígonos seleccionados.\n\n"
            "Esta herramienta trabaja sobre un único polígono a la vez. "
            "Selecciona solo uno e inténtalo de nuevo."
        )
        return None

    # ─────────────────────────────────────────────────────────────────
    # Diálogo
    # ─────────────────────────────────────────────────────────────────

    def _abrir_dialogo(self, layer, feature):
        import traceback
        try:
            from .dialog import PolygonDividerDialog
        except Exception as e:
            log_error(f"Polygon Divider: error importando diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Polygon Divider",
                f"No se pudo cargar el diálogo:\n\n{e}"
            )
            return

        try:
            dlg = PolygonDividerDialog(
                self.iface, layer, feature, self.iface.mainWindow()
            )
        except Exception as e:
            log_error(f"Polygon Divider: error construyendo diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Polygon Divider",
                f"Error al construir el diálogo:\n\n{e}"
            )
            return

        self._dialogo_activo = dlg
        dlg.setModal(False)
        dlg.show()
        log_info(f"Polygon Divider: diálogo abierto para feature {feature.id()} en '{layer.name()}'.")
