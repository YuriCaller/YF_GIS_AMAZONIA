# -*- coding: utf-8 -*-
"""
Diálogo de Batch Export — exportación de expediente completo en un clic.
Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QComboBox, QLabel, QLineEdit,
    QDialogButtonBox, QPushButton, QFileDialog,
    QScrollArea, QWidget, QFrame, QProgressBar,
    QSizePolicy, QMessageBox, QSpinBox
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QFont

from .batch_export_engine import (
    PLANTILLAS, get_capas_vectoriales, get_layouts
)


class BatchExportDialog(QDialog):
    """Diálogo principal de exportación en lote."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._capas   = get_capas_vectoriales()
        self._layouts = get_layouts()
        self._chk_capas   = {}   # layer_id → QCheckBox
        self._chk_layouts = {}   # layout_name → QCheckBox
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("YF · Exportar Expediente")
        self.setMinimumWidth(520)
        self.setMinimumHeight(600)

        main = QVBoxLayout(self)
        main.setSpacing(8)

        # ── Nombre del expediente ──
        grp_info = QGroupBox("Información del expediente")
        info_layout = QVBoxLayout(grp_info)

        row_nombre = QHBoxLayout()
        row_nombre.addWidget(QLabel("Nombre:"))
        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Ej: EXPEDIENTE_FlорCaller_2026")
        # Prellenar con nombre del proyecto
        from qgis.core import QgsProject
        proj_name = QgsProject.instance().baseName()
        if proj_name:
            self.txt_nombre.setText(proj_name.replace(" ", "_").upper())
        row_nombre.addWidget(self.txt_nombre)
        info_layout.addLayout(row_nombre)

        row_autor = QHBoxLayout()
        row_autor.addWidget(QLabel("Elaborado por:"))
        self.txt_autor = QLineEdit("Ing. Yuri F. Caller Córdova — CIP N° 214377")
        row_autor.addWidget(self.txt_autor)
        info_layout.addLayout(row_autor)

        row_cliente = QHBoxLayout()
        row_cliente.addWidget(QLabel("Cliente / Entidad:"))
        self.txt_cliente = QLineEdit()
        self.txt_cliente.setPlaceholderText("Ej: GOREMAD, FENAMAD, ACCA...")
        row_cliente.addWidget(self.txt_cliente)
        info_layout.addLayout(row_cliente)

        main.addWidget(grp_info)

        # ── Carpeta destino ──
        grp_dir = QGroupBox("Carpeta de salida")
        dir_layout = QHBoxLayout(grp_dir)
        self.txt_dir = QLineEdit()
        self.txt_dir.setPlaceholderText("Selecciona la carpeta destino...")
        btn_dir = QPushButton("📁  Examinar")
        btn_dir.clicked.connect(self._elegir_directorio)
        dir_layout.addWidget(self.txt_dir)
        dir_layout.addWidget(btn_dir)
        main.addWidget(grp_dir)

        # ── Plantilla de estructura ──
        grp_plantilla = QGroupBox("Estructura de carpetas")
        plt_layout = QHBoxLayout(grp_plantilla)
        plt_layout.addWidget(QLabel("Plantilla:"))
        self.combo_plantilla = QComboBox()
        for key, meta in PLANTILLAS.items():
            self.combo_plantilla.addItem(meta["nombre"], key)
        plt_layout.addWidget(self.combo_plantilla)
        main.addWidget(grp_plantilla)

        # ── Capas vectoriales ──
        grp_capas = QGroupBox(f"Capas vectoriales ({len(self._capas)} disponibles)")
        capas_layout = QVBoxLayout(grp_capas)

        # Botones seleccionar/deseleccionar todo
        sel_row = QHBoxLayout()
        btn_sel_all = QPushButton("Seleccionar todo")
        btn_sel_all.clicked.connect(lambda: self._toggle_capas(True))
        btn_desel   = QPushButton("Deseleccionar todo")
        btn_desel.clicked.connect(lambda: self._toggle_capas(False))
        sel_row.addWidget(btn_sel_all)
        sel_row.addWidget(btn_desel)
        sel_row.addStretch()
        capas_layout.addLayout(sel_row)

        # Scroll con capas
        scroll_capas = QScrollArea()
        scroll_capas.setMaximumHeight(150)
        scroll_capas.setWidgetResizable(True)
        capas_widget = QWidget()
        capas_inner = QVBoxLayout(capas_widget)
        capas_inner.setSpacing(2)

        for layer in self._capas:
            row = QHBoxLayout()
            chk = QCheckBox(layer.name())
            chk.setChecked(True)
            self._chk_capas[layer.id()] = chk
            row.addWidget(chk)

            # Formato de exportación por capa
            combo = QComboBox()
            combo.addItem("SHP + GPKG", "both")
            combo.addItem("Solo SHP",   "shp")
            combo.addItem("Solo GPKG",  "gpkg")
            combo.addItem("Solo tabla (XLSX)", "xlsx")
            combo.setObjectName(f"fmt_{layer.id()}")
            combo.setMaximumWidth(160)
            row.addWidget(combo)
            capas_inner.addLayout(row)

        capas_widget.setLayout(capas_inner)
        scroll_capas.setWidget(capas_widget)
        capas_layout.addWidget(scroll_capas)
        main.addWidget(grp_capas)

        # ── Layouts PDF ──
        grp_layouts = QGroupBox(f"Layouts / Mapas PDF ({len(self._layouts)} disponibles)")
        layouts_layout = QVBoxLayout(grp_layouts)

        if self._layouts:
            for layout in self._layouts:
                row = QHBoxLayout()
                chk = QCheckBox(layout.name())
                chk.setChecked(True)
                self._chk_layouts[layout.name()] = chk
                row.addWidget(chk)
                # DPI
                lbl_dpi = QLabel("DPI:")
                spin_dpi = QSpinBox()
                spin_dpi.setRange(72, 600)
                spin_dpi.setValue(300)
                # Sanitizar nombre para ObjectName (sin espacios ni caracteres especiales)
                safe_name = layout.name().replace(" ", "_").replace("/", "_")
                spin_dpi.setObjectName(f"dpi_{safe_name}")
                spin_dpi.setMaximumWidth(70)
                row.addWidget(lbl_dpi)
                row.addWidget(spin_dpi)
                row.addStretch()
                layouts_layout.addLayout(row)
        else:
            layouts_layout.addWidget(QLabel("⚠️  No hay layouts en el proyecto."))

        main.addWidget(grp_layouts)

        # ── Opciones adicionales ──
        grp_opts = QGroupBox("Opciones adicionales")
        opts_layout = QVBoxLayout(grp_opts)
        self.chk_metadatos = QCheckBox("Generar archivo de metadatos (METADATOS.txt)")
        self.chk_metadatos.setChecked(True)
        self.chk_zip = QCheckBox("Comprimir todo en un ZIP al finalizar")
        self.chk_zip.setChecked(True)
        self.chk_abrir = QCheckBox("Abrir carpeta al finalizar")
        self.chk_abrir.setChecked(True)
        opts_layout.addWidget(self.chk_metadatos)
        opts_layout.addWidget(self.chk_zip)
        opts_layout.addWidget(self.chk_abrir)
        main.addWidget(grp_opts)

        # ── Barra de progreso ──
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        main.addWidget(self.progress)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet("color: #1a6e2e; font-size: 11px;")
        main.addWidget(self.lbl_estado)

        # ── Botones ──
        btn_box = QDialogButtonBox()
        self.btn_exportar = btn_box.addButton(
            "🚀  Exportar expediente", QDialogButtonBox.ButtonRole.AcceptRole
        )
        btn_box.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        main.addWidget(btn_box)

    # ─────────────────────────────────────────────────────────────────
    # Eventos
    # ─────────────────────────────────────────────────────────────────

    def _elegir_directorio(self):
        path = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de salida", os.path.expanduser("~")
        )
        if path:
            self.txt_dir.setText(path)

    def _toggle_capas(self, checked):
        for chk in self._chk_capas.values():
            chk.setChecked(checked)

    # ─────────────────────────────────────────────────────────────────
    # Getters
    # ─────────────────────────────────────────────────────────────────

    def get_nombre(self):
        nombre = self.txt_nombre.text().strip()
        return nombre or "EXPEDIENTE_YF"

    def get_directorio(self):
        return self.txt_dir.text().strip()

    def get_plantilla(self):
        return self.combo_plantilla.currentData()

    def get_autor(self):
        return self.txt_autor.text().strip()

    def get_cliente(self):
        return self.txt_cliente.text().strip()

    def get_capas_seleccionadas(self):
        """Retorna lista de (layer, formato) para capas marcadas."""
        result = []
        for layer in self._capas:
            chk = self._chk_capas.get(layer.id())
            if chk and chk.isChecked():
                combo = self.findChild(QComboBox, f"fmt_{layer.id()}")
                fmt = combo.currentData() if combo else "both"
                result.append((layer, fmt))
        return result

    def get_layouts_seleccionados(self):
        """Retorna lista de (layout, dpi) para layouts marcados."""
        result = []
        for layout in self._layouts:
            chk = self._chk_layouts.get(layout.name())
            if chk and chk.isChecked():
                safe_name = layout.name().replace(" ", "_").replace("/", "_")
                spin = self.findChild(QSpinBox, f"dpi_{safe_name}")
                dpi = spin.value() if spin else 300
                result.append((layout, dpi))
        return result

    def get_opciones(self):
        return {
            "metadatos": self.chk_metadatos.isChecked(),
            "zip":       self.chk_zip.isChecked(),
            "abrir":     self.chk_abrir.isChecked(),
        }

    def set_progreso(self, valor, mensaje=""):
        self.progress.setVisible(True)
        self.progress.setValue(valor)
        self.lbl_estado.setText(mensaje)

    def validate(self):
        if not self.get_directorio():
            QMessageBox.warning(self, "Sin carpeta",
                "Selecciona una carpeta de salida.")
            return False
        if not os.path.isdir(self.get_directorio()):
            QMessageBox.warning(self, "Carpeta inválida",
                "La carpeta seleccionada no existe.")
            return False
        if not self.get_capas_seleccionadas() and not self.get_layouts_seleccionados():
            QMessageBox.warning(self, "Sin elementos",
                "Selecciona al menos una capa o un layout para exportar.")
            return False
        return True

    def accept(self):
        if self.validate():
            super().accept()
