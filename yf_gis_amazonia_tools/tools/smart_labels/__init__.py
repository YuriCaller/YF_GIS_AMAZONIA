# -*- coding: utf-8 -*-
"""
Smart Labels — Etiquetado inteligente desde clic derecho en el canvas.
Detecta el tipo de geometría y aplica estilos técnicos predefinidos.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os
try:
    from qgis.PyQt.QtGui import QAction        # Qt6: QAction vive en QtGui
except ImportError:
    from qgis.PyQt.QtWidgets import QAction    # Qt5: QAction vive en QtWidgets
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtWidgets import QMessageBox, QMenu
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsWkbTypes, QgsVectorLayer

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Smart Labels — etiquetado inteligente por tipo de geometría."""

    TOOL_NAME = "Smart Labels"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self._context_action = None
        self._setup_context_menu()
        # Registrar funciones de expresion elipsoidales al cargar el plugin,
        # para que proyectos guardados con etiquetas yf_* rendericen bien.
        try:
            from .label_engine import registrar_funciones_expresion
            registrar_funciones_expresion()
        except Exception as e:
            log_error(f"Smart Labels: registro de funciones fallido: {e}")

    def _setup_context_menu(self):
        """Registra acción en el menú contextual del canvas."""
        try:
            icon_path = os.path.join(self.plugin_dir, "icons", "smart_labels.png")
            icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

            self._context_action = QAction(
                icon,
                "YF · Smart Labels — Etiquetar capa",
                self.iface.mainWindow()
            )
            self._context_action.triggered.connect(self._run_from_context)

            # Registrar en clic derecho del canvas
            self.iface.mapCanvas().contextMenuAboutToShow.connect(
                self._add_to_canvas_menu
            )
            log_info("Smart Labels: context menu registrado en canvas")
        except Exception as e:
            log_error(f"Smart Labels: error registrando context menu: {e}")

    def _add_to_canvas_menu(self, menu):
        """Agrega la acción al menú contextual del canvas si hay capa vectorial activa."""
        try:
            layer = self.iface.activeLayer()
            if layer and isinstance(layer, QgsVectorLayer):
                menu.addSeparator()
                # Submenú YF
                yf_menu = menu.addMenu("🏷️  YF · Smart Labels")
                geom_type = QgsWkbTypes.geometryType(layer.wkbType())

                # Estilos según tipo de geometría
                if geom_type == 2:   # Polígono
                    estilos = [
                        ("tecnico",      "Técnico — Área + Perímetro"),
                        ("simple_area",  "Simple — Solo área"),
                        ("catastral",    "Catastral — Nombre + Área + Perímetro"),
                        ("forestal",     "Forestal — Área de estudio"),
                    ]
                elif geom_type == 1:  # Línea
                    estilos = [
                        ("distancia_azimut", "Distancia + Azimut"),
                        ("solo_distancia",   "Solo distancia (m)"),
                        ("solo_azimut",      "Solo azimut (°)"),
                    ]
                else:                 # Punto
                    estilos = [
                        ("vertice",      "Vértice — V-01, V-02..."),
                        ("coordenadas",  "Coordenadas X, Y"),
                        ("nombre_campo", "Campo de nombre"),
                    ]

                for key, label in estilos:
                    act = QAction(label, menu)
                    act.triggered.connect(
                        lambda checked=False, k=key, lyr=layer:
                        self._aplicar_directo(lyr, k)
                    )
                    yf_menu.addAction(act)

                yf_menu.addSeparator()
                act_dialogo = QAction("⚙️  Más opciones...", menu)
                act_dialogo.triggered.connect(
                    lambda: self._abrir_dialogo(layer)
                )
                yf_menu.addAction(act_dialogo)

                act_quitar = QAction("🚫  Quitar etiquetas", menu)
                act_quitar.triggered.connect(
                    lambda checked=False, lyr=layer:
                    self._quitar_etiquetas(lyr)
                )
                yf_menu.addAction(act_quitar)

        except Exception as e:
            log_error(f"Smart Labels: error en context menu: {e}")

    def unload(self):
        try:
            self.iface.mapCanvas().contextMenuAboutToShow.disconnect(
                self._add_to_canvas_menu
            )
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    # ─────────────────────────────────────────────────────────────────
    # Entry points
    # ─────────────────────────────────────────────────────────────────

    def run(self):
        """Desde menú/toolbar — abre diálogo completo."""
        layer = self.iface.activeLayer()
        if not self._validar_capa(layer):
            return
        self._abrir_dialogo(layer)

    def _run_from_context(self):
        layer = self.iface.activeLayer()
        if not self._validar_capa(layer):
            return
        self._abrir_dialogo(layer)

    # ─────────────────────────────────────────────────────────────────
    # Lógica
    # ─────────────────────────────────────────────────────────────────

    def _aplicar_directo(self, layer, estilo_key):
        """Aplica un estilo directo desde el submenú del canvas."""
        try:
            from .label_engine import (
                aplicar_etiqueta_poligono,
                aplicar_etiqueta_linea,
                aplicar_etiqueta_punto,
            )
            geom_type = QgsWkbTypes.geometryType(layer.wkbType())

            if geom_type == 2:
                aplicar_etiqueta_poligono(layer, estilo_key)
            elif geom_type == 1:
                aplicar_etiqueta_linea(layer, estilo_key)
            else:
                aplicar_etiqueta_punto(layer, estilo_key)

            self.iface.messageBar().pushSuccess(
                "YF · Smart Labels",
                f"Etiqueta '{estilo_key}' aplicada a '{layer.name()}'"
            )
            log_info(f"Smart Labels: estilo '{estilo_key}' → '{layer.name()}'")

        except Exception as e:
            log_error(f"Smart Labels: error aplicando estilo: {e}")
            import traceback
            traceback.print_exc()

    def _abrir_dialogo(self, layer):
        """Abre el diálogo completo de selección de estilo."""
        import traceback
        try:
            from .dialog import SmartLabelsDialog
            from .label_engine import (
                aplicar_etiqueta_poligono,
                aplicar_etiqueta_linea,
                aplicar_etiqueta_punto,
            )

            dlg = SmartLabelsDialog(layer, self.iface.mainWindow())
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            estilo_key  = dlg.get_estilo_key()
            campo_nombre = dlg.get_campo_nombre()
            geom_type   = QgsWkbTypes.geometryType(layer.wkbType())

            if geom_type == 2:
                aplicar_etiqueta_poligono(
                    layer, estilo_key, campo_nombre,
                    unidad_area=dlg.get_unidad_area(),
                    unidad_perim=dlg.get_unidad_longitud(),
                    metodo=dlg.get_metodo(),
                )
            elif geom_type == 1:
                aplicar_etiqueta_linea(
                    layer, estilo_key,
                    unidad_long=dlg.get_unidad_longitud(),
                    metodo=dlg.get_metodo(),
                )
            else:
                aplicar_etiqueta_punto(layer, estilo_key, campo_nombre)

            self.iface.messageBar().pushSuccess(
                "YF · Smart Labels",
                f"Etiqueta aplicada a '{layer.name()}'"
            )

        except Exception as e:
            log_error(f"Smart Labels: error en diálogo: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error — YF Smart Labels",
                f"Error al aplicar etiqueta:\n\n{e}"
            )

    def _quitar_etiquetas(self, layer):
        from .label_engine import quitar_etiquetas
        quitar_etiquetas(layer)
        self.iface.messageBar().pushInfo(
            "YF · Smart Labels",
            f"Etiquetas quitadas de '{layer.name()}'"
        )

    def _validar_capa(self, layer):
        if not layer or not isinstance(layer, QgsVectorLayer):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "YF · Smart Labels",
                "Selecciona una capa vectorial activa en el panel de capas."
            )
            return False
        return True
