# -*- coding: utf-8 -*-
"""
Diálogo de Smart Labels — selector de estilo por tipo de geometría.
Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QLabel, QDialogButtonBox, QPushButton,
    QFrame, QSizePolicy
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes

from .label_engine import (
    ESTILOS_POLIGONO, ESTILOS_LINEA, ESTILOS_PUNTO
)


class SmartLabelsDialog(QDialog):
    """Diálogo selector de estilos de etiqueta."""

    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.geom_type = QgsWkbTypes.geometryType(layer.wkbType())
        self._campos_texto = [
            f.name() for f in layer.fields()
            if f.typeName() in ("String", "string", "text", "Text")
        ]
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("YF · Smart Labels")
        self.setMinimumWidth(400)
        main = QVBoxLayout(self)
        main.setSpacing(10)

        # Cabecera
        header = QLabel(
            f"<b>Capa:</b> {self.layer.name()}<br>"
            f"<b>Tipo:</b> {self._geom_label()} &nbsp;|&nbsp; "
            f"<b>CRS:</b> {self.layer.crs().authid()}"
        )
        header.setFrameStyle(QFrame.Shape.StyledPanel)
        header.setContentsMargins(8, 6, 8, 6)
        main.addWidget(header)

        # Estilos disponibles según tipo
        grp = QGroupBox("Estilo de etiqueta")
        grp_layout = QVBoxLayout(grp)

        grp_layout.addWidget(QLabel("Estilo:"))
        self.combo_estilo = QComboBox()
        self._poblar_estilos()
        self.combo_estilo.currentIndexChanged.connect(self._on_estilo_changed)
        grp_layout.addWidget(self.combo_estilo)

        # Campo nombre (solo para polígono catastral y punto nombre)
        self.lbl_campo = QLabel("Campo de nombre:")
        self.combo_campo = QComboBox()
        self.combo_campo.addItem("── Sin campo ──", None)
        for c in self._campos_texto:
            self.combo_campo.addItem(c, c)
        self.lbl_campo.setVisible(False)
        self.combo_campo.setVisible(False)
        grp_layout.addWidget(self.lbl_campo)
        grp_layout.addWidget(self.combo_campo)

        # Preview de la expresión
        self.lbl_preview = QLabel()
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setStyleSheet(
            "background:#f5f5f5; border:1px solid #ccc; "
            "padding:6px; font-family:monospace; font-size:11px;"
        )
        grp_layout.addWidget(QLabel("Vista previa de etiqueta:"))
        grp_layout.addWidget(self.lbl_preview)
        main.addWidget(grp)

        # Botones
        btn_layout = QHBoxLayout()
        self.btn_quitar = QPushButton("🚫  Quitar etiquetas")
        self.btn_quitar.clicked.connect(self._quitar)
        btn_layout.addWidget(self.btn_quitar)

        btn_box = QDialogButtonBox()
        btn_box.addButton("✅  Aplicar", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton("Cancelar",   QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        btn_layout.addWidget(btn_box)
        main.addLayout(btn_layout)

        self._on_estilo_changed(0)

    def _poblar_estilos(self):
        if self.geom_type == 2:   # Polígono
            for key, meta in ESTILOS_POLIGONO.items():
                self.combo_estilo.addItem(meta["nombre"], key)
        elif self.geom_type == 1:  # Línea
            for key, meta in ESTILOS_LINEA.items():
                self.combo_estilo.addItem(meta["nombre"], key)
        else:                      # Punto
            for key, meta in ESTILOS_PUNTO.items():
                self.combo_estilo.addItem(meta["nombre"], key)

    def _on_estilo_changed(self, idx):
        key = self.combo_estilo.currentData()
        if not key:
            return

        # Mostrar campo nombre si aplica
        necesita_campo = key in ("catastral", "nombre_campo")
        self.lbl_campo.setVisible(necesita_campo)
        self.combo_campo.setVisible(necesita_campo)

        # Preview
        previews = {
            # Polígono
            "tecnico":        "ÁREA GEOREFERENCIADA\nÁrea: 2345.6547 ha.\nPerímetro: 23454.10 m.",
            "simple_area":    "Área: 2345.65 ha.",
            "catastral":      "PARCELA FLOR CALLER\nÁrea: 2345.65 ha.\nPerímetro: 23454.10 m.",
            "forestal":       "ÁREA DE ESTUDIO\n2345.65 ha.",
            # Línea
            "distancia_azimut": "L=145.67 m\nAz=324°15'22\"",
            "solo_distancia":   "145.67 m",
            "solo_azimut":      "324°15'22\"",
            # Punto
            "vertice":          "V-01  V-02  V-03",
            "coordenadas":      "353500.12\n8355500.34",
            "nombre_campo":     "[valor del campo seleccionado]",
        }
        self.lbl_preview.setText(previews.get(key, ""))

    def _quitar(self):
        from .label_engine import quitar_etiquetas
        quitar_etiquetas(self.layer)
        self.reject()

    def _geom_label(self):
        return {0: "Punto", 1: "Línea", 2: "Polígono"}.get(self.geom_type, "?")

    # Getters
    def get_estilo_key(self):
        return self.combo_estilo.currentData()

    def get_campo_nombre(self):
        return self.combo_campo.currentData()
