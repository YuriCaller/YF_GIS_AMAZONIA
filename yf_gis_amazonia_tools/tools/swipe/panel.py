# -*- coding: utf-8 -*-
"""
YF Swipe Panel v1.1
Panel de control flotante con todos los controles del plugin.

Secciones:
- Activación
- Modo (Swipe / Lupa)
- Selector de capa con botón intercambiar
- Dirección (solo en modo swipe)
- Posición del divisor (solo en modo swipe)
- Radio de lupa (solo en modo lupa)
- Transparencia
- Exportar

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import logging
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSlider, QGroupBox, QButtonGroup,
    QToolButton, QSizePolicy, QFrame, QStackedWidget
)

from qgis.core import QgsProject, QgsMapLayer


class SwipePanel(QDockWidget):
    """Panel dock para controlar el swipe tool v1.1."""

    layerChanged = pyqtSignal(object)
    modeChanged = pyqtSignal(str)        # 'swipe' / 'magnifier'
    directionChanged = pyqtSignal(str)
    activationToggled = pyqtSignal(bool)
    positionChanged = pyqtSignal(float)
    opacityChanged = pyqtSignal(float)   # 0.0 - 1.0
    radiusChanged = pyqtSignal(int)      # píxeles
    swapRequested = pyqtSignal()
    exportRequested = pyqtSignal()

    def __init__(self, iface, parent=None):
        super().__init__("YF Swipe Tool", parent)
        self.iface = iface
        self.setObjectName("YFSwipePanel")

        self._build_ui()
        self._connect_signals()
        self._populate_layers()

        QgsProject.instance().layersAdded.connect(self._populate_layers)
        QgsProject.instance().layersRemoved.connect(self._populate_layers)

    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ---- Activación ----
        self.toggle_btn = QPushButton("▶  Activar")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setMinimumHeight(36)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 6px 12px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:checked { background-color: #c0392b; }
            QPushButton:checked:hover { background-color: #e74c3c; }
        """)
        layout.addWidget(self.toggle_btn)

        # ---- Modo ----
        mode_group = QGroupBox("Modo")
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setSpacing(6)

        self.mode_swipe_btn = QToolButton()
        self.mode_swipe_btn.setText("▦  Swipe")
        self.mode_swipe_btn.setCheckable(True)
        self.mode_swipe_btn.setChecked(True)
        self.mode_swipe_btn.setMinimumHeight(30)
        self.mode_swipe_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mode_swipe_btn.setToolTip("Divisor arrastrable horizontal o vertical")

        self.mode_magnifier_btn = QToolButton()
        self.mode_magnifier_btn.setText("◯  Lupa")
        self.mode_magnifier_btn.setCheckable(True)
        self.mode_magnifier_btn.setMinimumHeight(30)
        self.mode_magnifier_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mode_magnifier_btn.setToolTip("Círculo que sigue al cursor (use +/- para ajustar tamaño)")

        mode_style = """
            QToolButton {
                background-color: #ecf0f1; border: 1px solid #bdc3c7;
                border-radius: 3px; padding: 4px 8px; font-weight: bold;
            }
            QToolButton:hover { background-color: #d5dbdb; }
            QToolButton:checked {
                background-color: #16a085; color: white;
                border: 1px solid #0e6b56;
            }
        """
        self.mode_swipe_btn.setStyleSheet(mode_style)
        self.mode_magnifier_btn.setStyleSheet(mode_style)

        self.mode_group_btn = QButtonGroup(self)
        self.mode_group_btn.setExclusive(True)
        self.mode_group_btn.addButton(self.mode_swipe_btn, 0)
        self.mode_group_btn.addButton(self.mode_magnifier_btn, 1)

        mode_layout.addWidget(self.mode_swipe_btn)
        mode_layout.addWidget(self.mode_magnifier_btn)
        layout.addWidget(mode_group)

        # ---- Capa ----
        layer_group = QGroupBox("Capa para Swipe")
        layer_layout = QVBoxLayout(layer_group)
        layer_layout.setSpacing(4)

        info_label = QLabel("<i>Esta capa se revelará al mover el divisor.</i>")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #555; font-size: 10pt;")
        layer_layout.addWidget(info_label)

        layer_row = QHBoxLayout()
        self.layer_combo = QComboBox()
        self.layer_combo.setMinimumHeight(28)
        layer_row.addWidget(self.layer_combo, 1)

        self.swap_btn = QToolButton()
        self.swap_btn.setText("⇄")
        self.swap_btn.setToolTip("Intercambiar: la capa actual se intercambia con la siguiente del proyecto")
        self.swap_btn.setMinimumSize(32, 28)
        self.swap_btn.setStyleSheet("""
            QToolButton {
                background-color: #f39c12; color: white; font-weight: bold;
                border: none; border-radius: 3px; font-size: 14pt;
            }
            QToolButton:hover { background-color: #e67e22; }
        """)
        layer_row.addWidget(self.swap_btn)
        layer_layout.addLayout(layer_row)
        layout.addWidget(layer_group)

        # ---- Stack: Dirección (swipe) / Radio (lupa) ----
        self.controls_stack = QStackedWidget()

        # Página 0: controles de swipe
        swipe_page = QWidget()
        swipe_page_layout = QVBoxLayout(swipe_page)
        swipe_page_layout.setContentsMargins(0, 0, 0, 0)
        swipe_page_layout.setSpacing(8)

        dir_group = QGroupBox("Dirección del Swipe")
        dir_layout = QHBoxLayout(dir_group)

        self.dir_horizontal_btn = QToolButton()
        self.dir_horizontal_btn.setText("⇄  Horizontal")
        self.dir_horizontal_btn.setCheckable(True)
        self.dir_horizontal_btn.setChecked(True)
        self.dir_horizontal_btn.setMinimumHeight(32)
        self.dir_horizontal_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.dir_vertical_btn = QToolButton()
        self.dir_vertical_btn.setText("⇅  Vertical")
        self.dir_vertical_btn.setCheckable(True)
        self.dir_vertical_btn.setMinimumHeight(32)
        self.dir_vertical_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        dir_btn_style = """
            QToolButton {
                background-color: #ecf0f1; border: 1px solid #bdc3c7;
                border-radius: 3px; padding: 4px 8px; font-weight: bold;
            }
            QToolButton:hover { background-color: #d5dbdb; }
            QToolButton:checked {
                background-color: #2980b9; color: white;
                border: 1px solid #1f6391;
            }
        """
        self.dir_horizontal_btn.setStyleSheet(dir_btn_style)
        self.dir_vertical_btn.setStyleSheet(dir_btn_style)

        self.dir_group_btn = QButtonGroup(self)
        self.dir_group_btn.setExclusive(True)
        self.dir_group_btn.addButton(self.dir_horizontal_btn, 0)
        self.dir_group_btn.addButton(self.dir_vertical_btn, 1)

        dir_layout.addWidget(self.dir_horizontal_btn)
        dir_layout.addWidget(self.dir_vertical_btn)
        swipe_page_layout.addWidget(dir_group)

        pos_group = QGroupBox("Posición del Divisor")
        pos_layout = QVBoxLayout(pos_group)

        self.pos_slider = QSlider(Qt.Orientation.Horizontal)
        self.pos_slider.setMinimum(0)
        self.pos_slider.setMaximum(1000)
        self.pos_slider.setValue(500)
        pos_layout.addWidget(self.pos_slider)

        self.pos_label = QLabel("50%")
        self.pos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pos_label.setStyleSheet("color: #2980b9; font-weight: bold;")
        pos_layout.addWidget(self.pos_label)

        quick_layout = QHBoxLayout()
        for label, val in [("0%", 0), ("25%", 250), ("50%", 500),
                           ("75%", 750), ("100%", 1000)]:
            btn = QPushButton(label)
            btn.setMaximumWidth(50)
            btn.clicked.connect(lambda checked, v=val: self.pos_slider.setValue(v))
            quick_layout.addWidget(btn)
        pos_layout.addLayout(quick_layout)
        swipe_page_layout.addWidget(pos_group)

        self.controls_stack.addWidget(swipe_page)

        # Página 1: controles de lupa
        magn_page = QWidget()
        magn_page_layout = QVBoxLayout(magn_page)
        magn_page_layout.setContentsMargins(0, 0, 0, 0)

        magn_group = QGroupBox("Radio de Lupa")
        magn_layout = QVBoxLayout(magn_group)

        hint_label = QLabel(
            "<i>Use + / - sobre el mapa para ajustar rápido.</i>"
        )
        hint_label.setStyleSheet("color: #555; font-size: 10pt;")
        magn_layout.addWidget(hint_label)

        self.radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_slider.setMinimum(30)
        self.radius_slider.setMaximum(500)
        self.radius_slider.setValue(150)
        magn_layout.addWidget(self.radius_slider)

        self.radius_label = QLabel("150 px")
        self.radius_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.radius_label.setStyleSheet("color: #16a085; font-weight: bold;")
        magn_layout.addWidget(self.radius_label)

        magn_page_layout.addWidget(magn_group)
        magn_page_layout.addStretch()

        self.controls_stack.addWidget(magn_page)
        layout.addWidget(self.controls_stack)

        # ---- Transparencia (siempre visible) ----
        opacity_group = QGroupBox("Transparencia de la Capa")
        opacity_layout = QVBoxLayout(opacity_group)

        opacity_hint = QLabel(
            "<i>0% = la capa de abajo se ve a través.</i>"
        )
        opacity_hint.setStyleSheet("color: #555; font-size: 10pt;")
        opacity_layout.addWidget(opacity_hint)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        opacity_layout.addWidget(self.opacity_slider)

        self.opacity_label = QLabel("Opacidad: 100%")
        self.opacity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.opacity_label.setStyleSheet("color: #8e44ad; font-weight: bold;")
        opacity_layout.addWidget(self.opacity_label)

        layout.addWidget(opacity_group)

        # ---- Exportar ----
        self.export_btn = QPushButton("📷  Exportar vista comparativa…")
        self.export_btn.setMinimumHeight(32)
        self.export_btn.setToolTip("Exportar la vista actual del canvas como PNG o PDF (Ctrl+S)")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 4px 12px;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        layout.addWidget(self.export_btn)

        # ---- Footer ----
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        footer = QLabel(
            "<small>YF Swipe Tool v1.1<br>"
            "Yuri Caller · TUCSA · gis-amazonia.pe<br>"
            "<b>Atajos:</b> ←→↑↓ mover · Shift acelera · +/- radio · Ctrl+S exportar</small>"
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #888;")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        layout.addStretch()
        self.setWidget(container)

    def _connect_signals(self):
        self.toggle_btn.toggled.connect(self._on_toggle)
        self.layer_combo.currentIndexChanged.connect(self._on_layer_changed)
        self.dir_horizontal_btn.toggled.connect(self._on_direction_changed)
        self.pos_slider.valueChanged.connect(self._on_position_changed)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.radius_slider.valueChanged.connect(self._on_radius_changed)
        self.mode_swipe_btn.toggled.connect(self._on_mode_changed)
        self.swap_btn.clicked.connect(self.swapRequested.emit)
        self.export_btn.clicked.connect(self.exportRequested.emit)

    def _populate_layers(self):
        current_id = self.layer_combo.currentData()
        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()

        layers = QgsProject.instance().mapLayers().values()
        layers = sorted(layers, key=lambda l: l.name().lower())  # noqa: E741

        for layer in layers:
            icon = self._icon_for_layer(layer)
            self.layer_combo.addItem(icon, layer.name(), layer.id())

        if current_id is not None:
            idx = self.layer_combo.findData(current_id)
            if idx >= 0:
                self.layer_combo.setCurrentIndex(idx)

        self.layer_combo.blockSignals(False)
        self._on_layer_changed()

    def _icon_for_layer(self, layer):
        try:
            if layer.type() == QgsMapLayer.LayerType.RasterLayer:
                return QIcon(":/images/themes/default/mIconRaster.svg")
            elif layer.type() == QgsMapLayer.LayerType.VectorLayer:
                from qgis.core import QgsWkbTypes
                gt = layer.geometryType()
                if gt == QgsWkbTypes.GeometryType.PointGeometry:
                    return QIcon(":/images/themes/default/mIconPointLayer.svg")
                elif gt == QgsWkbTypes.GeometryType.LineGeometry:
                    return QIcon(":/images/themes/default/mIconLineLayer.svg")
                elif gt == QgsWkbTypes.GeometryType.PolygonGeometry:
                    return QIcon(":/images/themes/default/mIconPolygonLayer.svg")
            elif layer.type() == QgsMapLayer.LayerType.MeshLayer:
                return QIcon(":/images/themes/default/mIconMeshLayer.svg")
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        return QIcon()

    def _on_toggle(self, checked):
        self.toggle_btn.setText("⏸  Desactivar" if checked else "▶  Activar")
        self.activationToggled.emit(checked)

    def _on_layer_changed(self):
        layer_id = self.layer_combo.currentData()
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            self.layerChanged.emit(layer)
        else:
            self.layerChanged.emit(None)

    def _on_direction_changed(self):
        direction = 'horizontal' if self.dir_horizontal_btn.isChecked() else 'vertical'
        self.directionChanged.emit(direction)

    def _on_position_changed(self, value):
        proportion = value / 1000.0
        self.pos_label.setText(f"{int(proportion * 100)}%")
        self.positionChanged.emit(proportion)

    def _on_opacity_changed(self, value):
        proportion = value / 100.0
        self.opacity_label.setText(f"Opacidad: {value}%")
        self.opacityChanged.emit(proportion)

    def _on_radius_changed(self, value):
        self.radius_label.setText(f"{value} px")
        self.radiusChanged.emit(value)

    def _on_mode_changed(self):
        if self.mode_swipe_btn.isChecked():
            self.controls_stack.setCurrentIndex(0)
            self.modeChanged.emit('swipe')
        else:
            self.controls_stack.setCurrentIndex(1)
            self.modeChanged.emit('magnifier')

    # ---- API pública ----
    def set_position_silent(self, proportion):
        self.pos_slider.blockSignals(True)
        self.pos_slider.setValue(int(proportion * 1000))
        self.pos_label.setText(f"{int(proportion * 100)}%")
        self.pos_slider.blockSignals(False)

    def set_radius_silent(self, radius):
        self.radius_slider.blockSignals(True)
        self.radius_slider.setValue(int(radius))
        self.radius_label.setText(f"{int(radius)} px")
        self.radius_slider.blockSignals(False)

    def get_selected_layer(self):
        layer_id = self.layer_combo.currentData()
        if layer_id:
            return QgsProject.instance().mapLayer(layer_id)
        return None

    def is_active(self):
        return self.toggle_btn.isChecked()

    def set_active(self, active):
        self.toggle_btn.setChecked(active)

    # ---- Persistencia ----
    def get_settings_dict(self):
        """Devuelve diccionario con configuración actual para guardar."""
        return {
            'mode': 'swipe' if self.mode_swipe_btn.isChecked() else 'magnifier',
            'direction': 'horizontal' if self.dir_horizontal_btn.isChecked() else 'vertical',
            'position': self.pos_slider.value(),
            'opacity': self.opacity_slider.value(),
            'radius': self.radius_slider.value(),
            'layer_id': self.layer_combo.currentData(),
        }

    def apply_settings_dict(self, settings):
        """Aplica configuración desde diccionario."""
        try:
            mode = settings.get('mode', 'swipe')
            if mode == 'magnifier':
                self.mode_magnifier_btn.setChecked(True)
            else:
                self.mode_swipe_btn.setChecked(True)

            direction = settings.get('direction', 'horizontal')
            if direction == 'vertical':
                self.dir_vertical_btn.setChecked(True)
            else:
                self.dir_horizontal_btn.setChecked(True)

            self.pos_slider.setValue(int(settings.get('position', 500)))
            self.opacity_slider.setValue(int(settings.get('opacity', 100)))
            self.radius_slider.setValue(int(settings.get('radius', 150)))

            layer_id = settings.get('layer_id')
            if layer_id:
                idx = self.layer_combo.findData(layer_id)
                if idx >= 0:
                    self.layer_combo.setCurrentIndex(idx)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def swap_to_next_layer(self):
        """Cambia al siguiente layer del combo (envoltorio)."""
        count = self.layer_combo.count()
        if count < 2:
            return
        current = self.layer_combo.currentIndex()
        next_idx = (current + 1) % count
        self.layer_combo.setCurrentIndex(next_idx)
