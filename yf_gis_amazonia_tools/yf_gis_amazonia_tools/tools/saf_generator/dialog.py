# -*- coding: utf-8 -*-
"""
SAF Generator Dialog - UI for the plantation generator.

Improvements over v2.1:
- Species and proportions tables are automatically synchronized
- Proper error messages with suggestions
- CRS validation before generation
"""

import math
import os
import re

from qgis.core import QgsVectorLayer, QgsWkbTypes, QgsProject
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QDoubleSpinBox, QGroupBox, QMessageBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
)

from .engine import SAFEngine
from ...core.crs_utils import layer_crs_is_valid_for_measurements
from ...core.logger import log_info, log_error


# ── Orientation Map Tool ────────────────────────────────────────────

class OrientacionMapTool(QgsMapTool):
    """Map tool to capture orientation angle from two clicks."""

    orientacion_definida = pyqtSignal(float)

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.puntos = []
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubberBand.setColor(QColor(255, 0, 0, 200))
        self.rubberBand.setWidth(4)
        self.first_click = True

    def canvasPressEvent(self, event):
        punto = self.toMapCoordinates(event.pos())
        self.puntos.append(punto)

        if len(self.puntos) == 1:
            self.rubberBand.reset(QgsWkbTypes.LineGeometry)
            self.rubberBand.addPoint(punto)
            if self.first_click:
                QMessageBox.information(
                    None,
                    "Punto 1 capturado",
                    "Primer punto capturado.\n\n"
                    "Haz clic en el segundo punto\n"
                    "para definir la dirección de las filas.",
                )
                self.first_click = False

        elif len(self.puntos) == 2:
            self.rubberBand.addPoint(punto)
            p1, p2 = self.puntos
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            angle = math.degrees(math.atan2(dy, dx))
            dist = math.sqrt(dx ** 2 + dy ** 2)

            QMessageBox.information(
                None,
                "Orientación definida",
                f"Ángulo: {angle:.2f}°\n"
                f"Distancia: {dist:.2f} m\n\n"
                f"Los puntos se generarán con esta orientación.",
            )
            self.orientacion_definida.emit(angle)
            self._reset()

    def _reset(self):
        self.puntos = []
        self.first_click = True

    def deactivate(self):
        self.rubberBand.reset(QgsWkbTypes.LineGeometry)
        super().deactivate()


# ── Main Dialog ─────────────────────────────────────────────────────

class GeneradorPlantacionDialog(QDialog):
    """Main dialog for the SAF Generator."""

    # Default species presets
    DEFAULT_SPECIES = [
        ("PLATANO", "0", "#FFD700"),
        ("CACAO", "1", "#8B4513"),
        ("", "2", "#00AA00"),
    ]

    DISTRIBUTION_METHODS = [
        ("Hash espacial (recomendado)", "HASH"),
        ("Tablero ajedrez (50%-50%)", "AJEDREZ"),
        ("Filas alternadas", "FILAS"),
        ("Bloques 3x3", "BLOQUES"),
        ("Aleatorio controlado", "ALEATORIO"),
        ("Secuencial (personalizado)", "SECUENCIAL"),
    ]

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.engine = SAFEngine()
        self.angulo_orientacion = 0.0
        self.usar_orientacion = False
        self.tool = None
        self.setWindowTitle("SAF Generator — Sistemas Agroforestales")
        self.setMinimumWidth(650)
        self.setMinimumHeight(700)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout()

        # ── Layer selection ──
        grp_layer = QGroupBox("1. Capa de parcelas")
        ly = QVBoxLayout()
        self.combo_capa = QComboBox()
        self._load_layers()
        ly.addWidget(self.combo_capa)
        grp_layer.setLayout(ly)
        layout.addWidget(grp_layer)

        # ── Distance ──
        grp_dist = QGroupBox("2. Distanciamiento")
        ld = QHBoxLayout()
        ld.addWidget(QLabel("Distancia (m):"))
        self.spin_distancia = QDoubleSpinBox()
        self.spin_distancia.setRange(0.5, 50.0)
        self.spin_distancia.setValue(2.29)
        self.spin_distancia.setDecimals(2)
        ld.addWidget(self.spin_distancia)
        ld.addStretch()
        grp_dist.setLayout(ld)
        layout.addWidget(grp_dist)

        # ── Orientation ──
        grp_orient = QGroupBox("3. Orientación de filas (opcional)")
        lo = QVBoxLayout()

        self.check_orientacion = QCheckBox("Usar orientación personalizada")
        self.check_orientacion.stateChanged.connect(self._toggle_orientation)
        lo.addWidget(self.check_orientacion)

        lo_btn = QHBoxLayout()
        self.btn_orientacion = QPushButton("Definir con cursor (2 clics en mapa)")
        self.btn_orientacion.clicked.connect(self._activate_orientation_tool)
        self.btn_orientacion.setEnabled(False)
        self.btn_orientacion.setStyleSheet(
            "background: #2196F3; color: white; padding: 8px; font-weight: bold;"
        )
        lo_btn.addWidget(self.btn_orientacion)
        lo.addLayout(lo_btn)

        lo_angle = QHBoxLayout()
        lo_angle.addWidget(QLabel("Ángulo:"))
        self.spin_angulo = QDoubleSpinBox()
        self.spin_angulo.setRange(-360, 360)
        self.spin_angulo.setValue(0)
        self.spin_angulo.setDecimals(2)
        self.spin_angulo.setSuffix("°")
        self.spin_angulo.setMinimumWidth(120)
        self.spin_angulo.setEnabled(False)
        self.spin_angulo.valueChanged.connect(
            lambda v: setattr(self, "angulo_orientacion", v)
        )
        lo_angle.addWidget(self.spin_angulo)
        lo_angle.addStretch()
        lo.addLayout(lo_angle)

        grp_orient.setLayout(lo)
        layout.addWidget(grp_orient)

        # ── Species ──
        grp_species = QGroupBox("4. Especies y distribución")
        ls = QVBoxLayout()

        # Species table
        self.tabla_especies = QTableWidget(3, 3)
        self.tabla_especies.setHorizontalHeaderLabels(
            ["Nombre", "Código", "Color"]
        )
        self.tabla_especies.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.tabla_especies.setMaximumHeight(120)

        for i, (name, code, color) in enumerate(self.DEFAULT_SPECIES):
            self.tabla_especies.setItem(i, 0, QTableWidgetItem(name))
            self.tabla_especies.setItem(i, 1, QTableWidgetItem(code))
            self.tabla_especies.setItem(i, 2, QTableWidgetItem(color))

        ls.addWidget(QLabel("Especies (deja vacías las que no uses):"))
        ls.addWidget(self.tabla_especies)

        # Species buttons
        lb = QHBoxLayout()
        btn_add = QPushButton("+ Agregar")
        btn_add.clicked.connect(self._add_species)
        btn_remove = QPushButton("- Eliminar")
        btn_remove.clicked.connect(self._remove_species)
        lb.addWidget(btn_add)
        lb.addWidget(btn_remove)
        lb.addStretch()
        ls.addLayout(lb)

        # Distribution method
        ls.addWidget(QLabel("Método de distribución:"))
        self.combo_metodo = QComboBox()
        for label, value in self.DISTRIBUTION_METHODS:
            self.combo_metodo.addItem(label, value)
        self.combo_metodo.currentIndexChanged.connect(self._on_method_changed)
        ls.addWidget(self.combo_metodo)

        # Proportions table
        ls.addWidget(QLabel("Proporción de cada especie (%):"))
        self.tabla_proporciones = QTableWidget(0, 2)
        self.tabla_proporciones.setHorizontalHeaderLabels(["Especie", "%"])
        self.tabla_proporciones.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.tabla_proporciones.setMaximumHeight(100)
        ls.addWidget(self.tabla_proporciones)

        # Sequential pattern (hidden by default)
        self.widget_secuencial = QWidget()
        lsec = QVBoxLayout()
        lsec.addWidget(QLabel("Patrón secuencial (códigos separados por coma):"))
        self.txt_patron = QLineEdit("0,1,1,0,1,1,0,0,0,1,1,0")
        lsec.addWidget(self.txt_patron)
        self.widget_secuencial.setLayout(lsec)
        self.widget_secuencial.setVisible(False)
        ls.addWidget(self.widget_secuencial)

        grp_species.setLayout(ls)
        layout.addWidget(grp_species)

        # Sync proportions table with species on edit
        self.tabla_especies.cellChanged.connect(self._sync_proportions)
        self._sync_proportions()

        # ── Output options ──
        grp_output = QGroupBox("5. Opciones de salida")
        lo2 = QVBoxLayout()
        ln = QHBoxLayout()
        ln.addWidget(QLabel("Nombre:"))
        self.txt_nombre = QLineEdit("Plantacion_SAF")
        ln.addWidget(self.txt_nombre)
        lo2.addLayout(ln)

        self.check_cuadricula = QCheckBox("Generar cuadrícula de líneas")
        self.check_cuadricula.setChecked(True)
        lo2.addWidget(self.check_cuadricula)

        grp_output.setLayout(lo2)
        layout.addWidget(grp_output)

        # ── Action buttons ──
        lb2 = QHBoxLayout()
        btn_gen = QPushButton("GENERAR PLANTACIÓN")
        btn_gen.clicked.connect(self._generate)
        btn_gen.setStyleSheet(
            "background: #4CAF50; color: white; padding: 12px; "
            "font-size: 14px; font-weight: bold;"
        )
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        lb2.addWidget(btn_gen)
        lb2.addWidget(btn_cancel)
        layout.addLayout(lb2)

        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Species / Proportions sync
    # ------------------------------------------------------------------

    def _sync_proportions(self):
        """Synchronize the proportions table with the species table."""
        species = self._get_species()
        n = len(species)

        self.tabla_proporciones.setRowCount(n)
        equal_pct = round(100 / n, 1) if n > 0 else 0

        for i, (code, info) in enumerate(species.items()):
            label = f"{info['nombre']} ({code})"
            self.tabla_proporciones.setItem(i, 0, QTableWidgetItem(label))
            # Keep existing percentage if row already existed
            existing = self.tabla_proporciones.item(i, 1)
            if existing is None or not existing.text().strip():
                self.tabla_proporciones.setItem(
                    i, 1, QTableWidgetItem(str(equal_pct))
                )

    def _get_species(self):
        """Read species from the species table."""
        species = {}
        for row in range(self.tabla_especies.rowCount()):
            name_item = self.tabla_especies.item(row, 0)
            code_item = self.tabla_especies.item(row, 1)
            color_item = self.tabla_especies.item(row, 2)

            if name_item and name_item.text().strip():
                try:
                    code = int(code_item.text()) if code_item else row
                except ValueError:
                    code = row
                color = color_item.text().strip() if color_item else "#999999"
                species[code] = {
                    "nombre": name_item.text().strip(),
                    "color": color,
                }
        return species

    def _get_proportions(self, species):
        """Read proportions from the proportions table."""
        proportions = {}
        for row in range(self.tabla_proporciones.rowCount()):
            item_name = self.tabla_proporciones.item(row, 0)
            item_pct = self.tabla_proporciones.item(row, 1)
            if item_name and item_pct:
                match = re.search(r"\((\d+)\)", item_name.text())
                if match:
                    code = int(match.group(1))
                    try:
                        pct = float(item_pct.text())
                    except ValueError:
                        pct = 0
                    proportions[code] = pct
        return proportions

    def _get_pattern(self):
        """Parse the sequential pattern string."""
        try:
            text = self.txt_patron.text().strip()
            return [int(x.strip()) for x in text.split(",") if x.strip()]
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Layer management
    # ------------------------------------------------------------------

    def _load_layers(self):
        """Populate the layer combo with polygon layers."""
        self.combo_capa.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if (isinstance(layer, QgsVectorLayer)
                    and layer.geometryType() == QgsWkbTypes.PolygonGeometry):
                self.combo_capa.addItem(layer.name(), layer)

    # ------------------------------------------------------------------
    # Orientation
    # ------------------------------------------------------------------

    def _toggle_orientation(self, state):
        enabled = state == Qt.Checked
        self.btn_orientacion.setEnabled(enabled)
        self.spin_angulo.setEnabled(enabled)
        self.usar_orientacion = enabled
        if not enabled:
            self.angulo_orientacion = 0
            self.spin_angulo.setValue(0)
            if self.tool:
                self.iface.mapCanvas().unsetMapTool(self.tool)

    def _activate_orientation_tool(self):
        try:
            canvas = self.iface.mapCanvas()
            self.tool = OrientacionMapTool(canvas)
            self.tool.orientacion_definida.connect(self._set_angle)
            canvas.setMapTool(self.tool)
            self.showMinimized()
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                f"Error al activar herramienta de orientación:\n{e}"
            )

    def _set_angle(self, angle):
        self.angulo_orientacion = angle
        self.spin_angulo.setValue(angle)
        self.showNormal()
        self.activateWindow()
        if self.tool:
            self.iface.mapCanvas().unsetMapTool(self.tool)

    # ------------------------------------------------------------------
    # UI callbacks
    # ------------------------------------------------------------------

    def _add_species(self):
        row = self.tabla_especies.rowCount()
        self.tabla_especies.insertRow(row)
        self.tabla_especies.setItem(row, 1, QTableWidgetItem(str(row)))
        self.tabla_especies.setItem(row, 2, QTableWidgetItem("#999999"))
        self._sync_proportions()

    def _remove_species(self):
        if self.tabla_especies.rowCount() > 2:
            self.tabla_especies.removeRow(self.tabla_especies.rowCount() - 1)
            self._sync_proportions()

    def _on_method_changed(self):
        method = self.combo_metodo.currentData()
        self.widget_secuencial.setVisible(method == "SECUENCIAL")
        self.tabla_proporciones.setVisible(method != "AJEDREZ")

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate(self):
        """Validate inputs and run the generation engine."""
        if self.combo_capa.currentIndex() == -1:
            QMessageBox.warning(self, "Error", "Selecciona una capa de parcelas.")
            return

        layer = self.combo_capa.currentData()

        # CRS validation
        valid, msg = layer_crs_is_valid_for_measurements(layer)
        if not valid:
            QMessageBox.warning(self, "CRS no válido", msg)
            return

        species = self._get_species()
        if not species:
            QMessageBox.warning(
                self, "Error",
                "Define al menos una especie con nombre.",
            )
            return

        method = self.combo_metodo.currentData()
        proportions = self._get_proportions(species)
        pattern = self._get_pattern() if method == "SECUENCIAL" else None

        if method == "SECUENCIAL" and not pattern:
            QMessageBox.warning(
                self, "Error",
                "El patrón secuencial no es válido.\n"
                "Usa números separados por comas, ej: 0,1,1,0,1,1",
            )
            return

        distance = self.spin_distancia.value()
        name = self.txt_nombre.text().strip() or "Plantacion_SAF"

        try:
            points, lines_h, lines_v = self.engine.generate(
                layer=layer,
                distance=distance,
                method=method,
                species=species,
                proportions=proportions,
                pattern=pattern,
                orientation_angle=self.angulo_orientacion,
                use_orientation=self.usar_orientacion,
            )

            if not points:
                QMessageBox.warning(
                    self, "Sin resultados",
                    "No se generaron puntos.\n\n"
                    "Posibles causas:\n"
                    "- La distancia es mayor que el tamaño de la parcela\n"
                    "- Los polígonos no son válidos\n"
                    "- El CRS no está en metros",
                )
                return

            # Add point layer
            point_layer = self.engine.create_point_layer(
                points, layer.crs(), name, species
            )
            QgsProject.instance().addMapLayer(point_layer)

            # Add grid layer if requested
            if self.check_cuadricula.isChecked():
                grid_layer = self.engine.create_grid_layer(
                    lines_h, lines_v, layer.crs(), f"{name}_Cuadricula"
                )
                QgsProject.instance().addMapLayer(grid_layer)

            # Build summary
            total = len(points)
            stats = {}
            for code, info in species.items():
                count = len([
                    p for p in points if p["especie_codigo"] == code
                ])
                stats[info["nombre"]] = count

            msg = f"Generación exitosa\n\n"
            msg += f"Método: {self.combo_metodo.currentText()}\n"
            msg += f"Total plantas: {total}\n\n"
            for sp_name, count in stats.items():
                pct = count / total * 100 if total > 0 else 0
                msg += f"{sp_name}: {count} ({pct:.1f}%)\n"
            msg += f"\nDistancia: {distance} m"
            if self.usar_orientacion:
                msg += f"\nOrientación: {self.angulo_orientacion:.2f}°"

            log_info(f"SAF generado: {total} puntos, {len(species)} especies")
            QMessageBox.information(self, "Éxito", msg)
            self.accept()

        except Exception as e:
            log_error(f"Error generando SAF: {e}")
            QMessageBox.critical(
                self, "Error", f"Error durante la generación:\n{e}"
            )
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self.tool:
            self.iface.mapCanvas().unsetMapTool(self.tool)
        super().closeEvent(event)
