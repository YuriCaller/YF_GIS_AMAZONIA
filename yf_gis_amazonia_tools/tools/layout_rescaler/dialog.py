# -*- coding: utf-8 -*-
"""
Diálogo de Redimensionar Layout — estilo ArcMap.
Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QLabel, QCheckBox, QDoubleSpinBox,
    QDialogButtonBox, QMessageBox, QRadioButton,
    QSizePolicy, QFrame, QGridLayout, QButtonGroup
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont

from .rescaler_engine import PAPER_SIZES, get_layout_size_mm


class LayoutRescalerDialog(QDialog):
    """Diálogo para redimensionar layout proporcionalmente."""

    def __init__(self, layout, parent=None):
        super().__init__(parent)
        self.layout = layout
        self._old_w, self._old_h = get_layout_size_mm(layout)
        self._build_ui()
        self._detect_current_orientation()
        self._update_preview()

    # ─────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("YF · Redimensionar Layout")
        self.setMinimumWidth(440)

        main = QVBoxLayout(self)
        main.setSpacing(10)

        # ── Selector de layout (funcional) + tamaño actual ──
        grp_lay = QGroupBox("Layout a redimensionar")
        gl = QGridLayout(grp_lay)
        gl.addWidget(QLabel("Aplicar en:"), 0, 0)
        self.combo_layout = QComboBox()
        self.combo_layout.setToolTip(
            "<b>Layout de destino</b><br>Todos los cálculos y el "
            "redimensionado se aplican al layout elegido aquí.")
        self._cargar_layouts()
        self.combo_layout.currentIndexChanged.connect(self._on_layout_cambiado)
        gl.addWidget(self.combo_layout, 0, 1)
        main.addWidget(grp_lay)

        self.lbl_header = QLabel()
        self.lbl_header.setFrameStyle(QFrame.Shape.StyledPanel)
        self.lbl_header.setContentsMargins(8, 6, 8, 6)
        self._actualizar_header()
        main.addWidget(self.lbl_header)

        # ── Tamaño destino ──
        grp_size = QGroupBox("Nuevo tamaño de papel")
        grid = QGridLayout(grp_size)

        # Combo de tamaños predefinidos
        grid.addWidget(QLabel("Tamaño:"), 0, 0)
        self.combo_size = QComboBox()
        self.combo_size.addItem("── Personalizado ──", None)
        for name, (w, h) in PAPER_SIZES.items():
            self.combo_size.addItem(name, (w, h))
        self.combo_size.currentIndexChanged.connect(self._on_size_selected)
        grid.addWidget(self.combo_size, 0, 1, 1, 2)

        # Orientación
        grid.addWidget(QLabel("Orientación:"), 1, 0)
        orient_layout = QHBoxLayout()
        self.radio_landscape = QRadioButton("Apaisado")
        self.radio_portrait  = QRadioButton("Vertical")
        self.radio_landscape.setChecked(True)
        self.radio_landscape.toggled.connect(self._on_orientation_changed)
        orient_layout.addWidget(self.radio_landscape)
        orient_layout.addWidget(self.radio_portrait)
        orient_layout.addStretch()
        grid.addLayout(orient_layout, 1, 1, 1, 2)

        # Ancho / Alto personalizados
        grid.addWidget(QLabel("Ancho (mm):"), 2, 0)
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(50, 5000)
        self.spin_w.setDecimals(1)
        self.spin_w.setValue(self._old_w)
        self.spin_w.valueChanged.connect(self._update_preview)
        grid.addWidget(self.spin_w, 2, 1)

        grid.addWidget(QLabel("Alto (mm):"), 3, 0)
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(50, 5000)
        self.spin_h.setDecimals(1)
        self.spin_h.setValue(self._old_h)
        self.spin_h.valueChanged.connect(self._update_preview)
        grid.addWidget(self.spin_h, 3, 1)

        main.addWidget(grp_size)

        # ── Opciones de escalado ──
        grp_opts = QGroupBox("Opciones")
        opts_layout = QVBoxLayout(grp_opts)

        self.chk_scale_elements = QCheckBox(
            "Escalar los elementos del mapa proporcionalmente al nuevo tamaño"
        )
        self.chk_scale_elements.setChecked(True)
        self.chk_scale_elements.setStyleSheet("font-weight: bold;")
        opts_layout.addWidget(self.chk_scale_elements)

        self.chk_scale_fonts = QCheckBox(
            "Escalar también el tamaño de fuentes (etiquetas, leyenda, barra de escala)"
        )
        self.chk_scale_fonts.setChecked(True)
        opts_layout.addWidget(self.chk_scale_fonts)

        # Vincular: si no escala elementos, deshabilitar fuentes
        self.chk_scale_elements.toggled.connect(
            self.chk_scale_fonts.setEnabled
        )

        main.addWidget(grp_opts)

        # ── Preview de factores ──
        grp_preview = QGroupBox("Vista previa del cambio")
        preview_layout = QVBoxLayout(grp_preview)
        self.lbl_preview = QLabel()
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lbl_preview.setStyleSheet("font-family: monospace; font-size: 11px;")
        preview_layout.addWidget(self.lbl_preview)
        main.addWidget(grp_preview)

        # ── Botones ──
        btn_box = QDialogButtonBox()
        btn_box.addButton("✅  Aplicar", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton("Cancelar",   QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        main.addWidget(btn_box)

    # ─────────────────────────────────────────────────────────────────
    # Eventos
    # ─────────────────────────────────────────────────────────────────

    def _cargar_layouts(self):
        from qgis.core import QgsProject, QgsPrintLayout
        self.combo_layout.clear()
        layouts = [l for l in  # noqa: E741
                   QgsProject.instance().layoutManager().layouts()
                   if isinstance(l, QgsPrintLayout)]
        # Guardar el NOMBRE (sip degrada el objeto a QGraphicsScene)
        for l in sorted(layouts, key=lambda x: x.name().lower()):  # noqa: E741
            self.combo_layout.addItem(l.name(), l.name())
        if self.layout is not None:
            idx = self.combo_layout.findText(self.layout.name())
            if idx >= 0:
                self.combo_layout.setCurrentIndex(idx)

    def _on_layout_cambiado(self, idx):
        from qgis.core import QgsProject
        nombre = self.combo_layout.currentData()
        lay = (QgsProject.instance().layoutManager().layoutByName(nombre)
               if nombre else None)
        if lay is None:
            return
        self.layout = lay
        self._old_w, self._old_h = get_layout_size_mm(lay)
        self._detect_current_orientation()
        self._update_preview()
        self._actualizar_header()

    def _actualizar_header(self):
        self.lbl_header.setText(
            "<b>Tamaño actual:</b> {:.1f} × {:.1f} mm".format(
                self._old_w, self._old_h))

    def get_layout(self):
        """Layout elegido en el combo (resuelto por nombre)."""
        from qgis.core import QgsProject
        nombre = self.combo_layout.currentData()
        if nombre:
            lay = QgsProject.instance().layoutManager().layoutByName(nombre)
            if lay is not None:
                return lay
        return self.layout

    def _detect_current_orientation(self):
        """Detecta orientación actual del layout."""
        if self._old_w >= self._old_h:
            self.radio_landscape.setChecked(True)
        else:
            self.radio_portrait.setChecked(True)

    def _on_size_selected(self, idx):
        """Rellena los spinboxes al elegir un tamaño predefinido."""
        data = self.combo_size.currentData()
        if data is None:
            return
        w_land, h_land = data
        if self.radio_landscape.isChecked():
            self.spin_w.setValue(w_land)
            self.spin_h.setValue(h_land)
        else:
            self.spin_w.setValue(h_land)
            self.spin_h.setValue(w_land)
        self._update_preview()

    def _on_orientation_changed(self):
        """Intercambia ancho/alto al cambiar orientación."""
        w = self.spin_w.value()
        h = self.spin_h.value()
        if self.radio_landscape.isChecked() and h > w:
            self.spin_w.setValue(h)
            self.spin_h.setValue(w)
        elif self.radio_portrait.isChecked() and w > h:
            self.spin_w.setValue(h)
            self.spin_h.setValue(w)
        self._update_preview()

    def _update_preview(self):
        """Actualiza el panel de vista previa con factores de escala."""
        nw = self.spin_w.value()
        nh = self.spin_h.value()
        if self._old_w and self._old_h:
            fx = nw / self._old_w
            fy = nh / self._old_h
            f_avg = (fx + fy) / 2
            arrow = "▲" if fx > 1 else ("▼" if fx < 1 else "=")
            self.lbl_preview.setText(
                f"  Tamaño actual  :  {self._old_w:.1f} × {self._old_h:.1f} mm\n"
                f"  Tamaño nuevo   :  {nw:.1f} × {nh:.1f} mm\n"
                f"  Factor ancho   :  {fx:.4f}  {arrow}\n"
                f"  Factor alto    :  {fy:.4f}  {arrow}\n"
                f"  Factor fuentes :  {f_avg:.4f}"
            )

    # ─────────────────────────────────────────────────────────────────
    # Getters
    # ─────────────────────────────────────────────────────────────────

    def get_new_size(self):
        return self.spin_w.value(), self.spin_h.value()

    def get_scale_elements(self):
        return self.chk_scale_elements.isChecked()

    def get_scale_fonts(self):
        return self.chk_scale_fonts.isChecked()

    def validate(self):
        nw, nh = self.get_new_size()
        if abs(nw - self._old_w) < 0.1 and abs(nh - self._old_h) < 0.1:
            QMessageBox.warning(
                self, "Sin cambio",
                "El tamaño nuevo es igual al actual.\nModifica las dimensiones."
            )
            return False
        return True

    def accept(self):
        if self.validate():
            super().accept()
