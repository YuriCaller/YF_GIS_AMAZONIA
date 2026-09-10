# -*- coding: utf-8 -*-
"""
Diálogo de Calcular Geometría Vectorial.
Detecta tipo de geometría y permite al usuario definir
el nombre de cada campo de salida — nuevo o existente.
Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QCheckBox, QComboBox, QLineEdit,
    QLabel, QDialogButtonBox, QMessageBox,
    QSizePolicy, QFrame, QWidget, QPushButton, QDateEdit,
    QRadioButton, QDoubleSpinBox
)
from qgis.PyQt.QtCore import Qt, QDate
from qgis.core import QgsWkbTypes

# EPSG favoritos para Madre de Dios / Peru
EPSG_FAVORITOS = [
    ("WGS 84 / UTM zona 19S  (EPSG:32719)", "EPSG:32719"),
    ("WGS 84 / UTM zona 18S  (EPSG:32718)", "EPSG:32718"),
    ("WGS 84 Geográfico       (EPSG:4326)",  "EPSG:4326"),
    ("SIRGAS 2000 / UTM 19S   (EPSG:31979)", "EPSG:31979"),
    ("Misma CRS de la capa",                  None),
]

# Nombres de campo sugeridos por defecto para cada cálculo
DEFAULTS_NOMBRE = {
    # polígono
    "area_ha":     "area_ha",
    "area_m2":     "area_m2",
    "perimetro_m": "perim_m",
    "centroide_x": "cent_x",
    "centroide_y": "cent_y",
    # línea
    "longitud_m":  "longitud_m",
    "azimut_dec":  "azimut_dec",
    "azimut_gms":  "azimut_gms",
    "inicio_x":    "ini_x",
    "inicio_y":    "ini_y",
    "fin_x":       "fin_x",
    "fin_y":       "fin_y",
    "az_mag":       "az_mag",
    "az_mag_campo": "az_mag_campo",
    "contra_mag":   "contra_mag",
    "declinacion":  "decl_mag",
    "conv_merid":   "conv_merid",
    "fecha_decl":   "fecha_decl",
    # punto
    "coord_x":     "coord_x",
    "coord_y":     "coord_y",
    "elevacion_z": "elev_z",
}


class FieldRow(QWidget):
    """
    Fila compacta: [✓ CheckBox etiqueta]  [ComboBox/LineEdit nombre campo]
    El combo mezcla campos existentes + opción 'Nuevo campo...'
    Al elegir 'Nuevo campo...' aparece un QLineEdit editable.
    """

    NUEVO_CAMPO = "── Nuevo campo ──"

    def __init__(self, key, label, default_name, existing_fields, checked, parent=None):
        super().__init__(parent)
        self.key = key
        self._existing = existing_fields

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

        # Checkbox con etiqueta descriptiva
        self.chk = QCheckBox(label)
        self.chk.setChecked(checked)
        self.chk.setMinimumWidth(220)
        row.addWidget(self.chk, stretch=2)

        # Flecha decorativa
        arrow = QLabel("→")
        arrow.setStyleSheet("color: #888;")
        row.addWidget(arrow)

        # Combo con campos existentes + "Nuevo campo"
        self.combo = QComboBox()
        self.combo.setMinimumWidth(130)
        self.combo.setEditable(False)

        # Primero los campos existentes que podrían recibir este valor
        for f in existing_fields:
            self.combo.addItem(f)
        self.combo.addItem(self.NUEVO_CAMPO)

        # LineEdit para nombre personalizado (visible solo cuando "Nuevo campo")
        self.line = QLineEdit()
        self.line.setMaxLength(20)
        self.line.setPlaceholderText("nombre_campo")
        self.line.setMinimumWidth(120)

        # Selección inicial: si ya existe el campo sugerido, úsalo
        if default_name in existing_fields:
            idx = self.combo.findText(default_name)
            self.combo.setCurrentIndex(idx)
            self.line.setVisible(False)
        else:
            # No existe — seleccionar "Nuevo campo" y prellenar el LineEdit
            self.combo.setCurrentText(self.NUEVO_CAMPO)
            self.line.setText(default_name)
            self.line.setVisible(True)

        row.addWidget(self.combo, stretch=2)
        row.addWidget(self.line, stretch=2)

        # Conectar señales
        self.combo.currentTextChanged.connect(self._on_combo_changed)
        self.chk.toggled.connect(self._on_check_toggled)
        self._on_check_toggled(self.chk.isChecked())

    def _on_combo_changed(self, text):
        self.line.setVisible(text == self.NUEVO_CAMPO)

    def _on_check_toggled(self, checked):
        self.combo.setEnabled(checked)
        self.line.setEnabled(checked)

    def is_checked(self):
        return self.chk.isChecked()

    def get_field_name(self):
        """Retorna el nombre final del campo (existente o nuevo)."""
        if self.combo.currentText() == self.NUEVO_CAMPO:
            return self.line.text().strip()
        return self.combo.currentText()


class VectorGeometryDialog(QDialog):
    """Diálogo principal para calcular geometría vectorial."""

    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.geom_type = QgsWkbTypes.geometryType(layer.wkbType())
        # Campos existentes en la capa (solo numéricos + string para azimut)
        self._existing_fields = [f.name() for f in layer.fields()]
        self._rows = {}   # key → FieldRow
        self._build_ui()
        self._populate_for_geometry()

    # ─────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("YF · Calcular Geometría Vectorial")
        self.setMinimumWidth(520)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Cabecera
        header = QLabel(
            f"<b>Capa:</b> {self.layer.name()}<br>"
            f"<b>Tipo:</b> {self._geom_type_label()} &nbsp;|&nbsp; "
            f"<b>CRS:</b> {self.layer.crs().authid()}"
        )
        header.setFrameStyle(QFrame.Shape.StyledPanel)
        header.setContentsMargins(8, 6, 8, 6)
        main_layout.addWidget(header)

        # Encabezado de columnas
        col_header = QHBoxLayout()
        col_header.setContentsMargins(0, 0, 0, 0)
        lbl_campo = QLabel("<b>Campo a calcular</b>")
        lbl_campo.setMinimumWidth(220)
        lbl_destino = QLabel("<b>Nombre en la capa</b>")
        lbl_destino.setStyleSheet("color: #555;")
        col_header.addWidget(lbl_campo, stretch=2)
        col_header.addSpacing(20)
        col_header.addWidget(lbl_destino, stretch=4)
        main_layout.addLayout(col_header)

        # Grupo de filas de campos
        self.group_campos = QGroupBox()
        self.campos_layout = QVBoxLayout(self.group_campos)
        self.campos_layout.setSpacing(2)
        main_layout.addWidget(self.group_campos)

        # Método de cálculo: elipsoidal vs planar
        group_met = QGroupBox("Método de cálculo de área/longitud")
        met_layout = QVBoxLayout(group_met)
        from qgis.PyQt.QtWidgets import QRadioButton
        self.rb_elipsoidal = QRadioButton(
            "🌍 Elipsoidal ($area) — mundo real, considera curvatura")
        self.rb_elipsoidal.setToolTip(
            "Equivale a la expresión $area de QGIS.\n"
            "Considera la curvatura de la Tierra (elipsoide).\n"
            "Ideal para: áreas extensas, análisis geoespaciales,\n"
            "imágenes satelitales, estudios regionales.")
        self.rb_planar = QRadioButton(
            "📐 Planar (area($geometry)) — plano legal / catastro")
        self.rb_planar.setToolTip(
            "Equivale a la expresión area($geometry) de QGIS.\n"
            "Cálculo cartesiano en el plano del CRS proyectado.\n"
            "Ideal para: planos legales, catastro, predios,\n"
            "levantamientos topográficos. Requiere CRS proyectado (UTM).")
        self.rb_elipsoidal.setChecked(True)
        met_layout.addWidget(self.rb_elipsoidal)
        met_layout.addWidget(self.rb_planar)
        lbl_met = QLabel(
            "Catastro/predios → Planar  |  Análisis regional → Elipsoidal")
        lbl_met.setStyleSheet("color:#666;font-size:10px;")
        met_layout.addWidget(lbl_met)
        main_layout.addWidget(group_met)

        # CRS destino
        group_crs = QGroupBox("Sistema de referencia para el cálculo")
        crs_layout = QVBoxLayout(group_crs)
        self.combo_crs = QComboBox()
        for label, authid in EPSG_FAVORITOS:
            self.combo_crs.addItem(label, authid)
        crs_actual = self.layer.crs().authid()
        for i, (_, authid) in enumerate(EPSG_FAVORITOS):
            if authid == crs_actual:
                self.combo_crs.setCurrentIndex(i)
                break
        crs_layout.addWidget(self.combo_crs)
        main_layout.addWidget(group_crs)

        # Solo selección
        self.chk_solo_seleccion = QCheckBox("Calcular solo en features seleccionadas")
        n_sel = self.layer.selectedFeatureCount()
        self.chk_solo_seleccion.setEnabled(n_sel > 0)
        if n_sel > 0:
            self.chk_solo_seleccion.setText(
                f"Calcular solo en features seleccionadas  ({n_sel} seleccionadas)"
            )
        main_layout.addWidget(self.chk_solo_seleccion)

        # Aviso
        lbl_aviso = QLabel("⚠️  Si el campo ya existe, sus valores serán sobreescritos.")
        lbl_aviso.setStyleSheet("color: #b05000; font-size: 11px;")
        main_layout.addWidget(lbl_aviso)

        # Botón "Calcular todo"
        btn_todo = QPushButton("⚡  Calcular TODO automáticamente")
        btn_todo.setToolTip(
            "Marca y calcula todos los campos útiles para este tipo de geometría"
        )
        btn_todo.setStyleSheet(
            "QPushButton { background-color: #1a6e2e; color: white; "
            "font-weight: bold; padding: 5px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #228b3a; }"
        )
        btn_todo.clicked.connect(self._calcular_todo)
        main_layout.addWidget(btn_todo)

        # Botones normales
        btn_box = QDialogButtonBox()
        btn_box.addButton("✅  Calcular selección", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)

    def _populate_for_geometry(self):
        """Agrega filas según tipo de geometría."""
        if self.geom_type == 2:   # Polígono
            campos = [
                ("area_ha",     "Área en hectáreas"),
                ("area_m2",     "Área en m²"),
                ("perimetro_m", "Perímetro en metros"),
                ("centroide_x", "Centroide X"),
                ("centroide_y", "Centroide Y"),
            ]
            defaults_on = {"area_ha", "perimetro_m"}

        elif self.geom_type == 1:  # Línea
            campos = [
                ("longitud_m",  "Longitud en metros"),
                ("azimut_dec",  "Azimut decimal (°)"),
                ("azimut_gms",  "Azimut GMS (°′″)"),
                ("az_mag",       "Azimut magnético (°)"),
                ("az_mag_campo", "Azimut magnético de campo (0.5°)"),
                ("contra_mag",   "Contrarrumbo magnético (°)"),
                ("declinacion",  "Declinación aplicada (°)"),
                ("conv_merid",   "Convergencia de meridianos (°)"),
                ("fecha_decl",   "Fecha y modelo del cálculo"),
            ]
            defaults_on = {"longitud_m", "azimut_gms"}

        else:                      # Punto
            campos = [
                ("coord_x",     "Coordenada X"),
                ("coord_y",     "Coordenada Y"),
                ("elevacion_z", "Elevación Z (si tiene 3D)"),
            ]
            defaults_on = {"coord_x", "coord_y"}

        for key, label in campos:
            row = FieldRow(
                key=key,
                label=label,
                default_name=DEFAULTS_NOMBRE[key],
                existing_fields=self._existing_fields,
                checked=(key in defaults_on),
                parent=self,
            )
            self._rows[key] = row
            self.campos_layout.addWidget(row)

        if self.geom_type == 1:
            self.campos_layout.addWidget(self._bloque_declinacion())

    def _bloque_declinacion(self):
        """Fecha del cálculo magnético + advertencia de uso."""
        caja = QGroupBox("Declinación magnética")
        lay = QVBoxLayout(caja)

        # ── Modo automático (WMM) ───────────────────────────────────
        self.rb_decl_auto = QRadioButton(
            "Calcular automáticamente (modelo WMM según la ubicación)")
        self.rb_decl_auto.setChecked(True)
        lay.addWidget(self.rb_decl_auto)

        fila_f = QHBoxLayout()
        fila_f.addSpacing(22)
        fila_f.addWidget(QLabel("Fecha del cálculo:"))
        self.date_decl = QDateEdit()
        self.date_decl.setCalendarPopup(True)
        self.date_decl.setDisplayFormat("dd/MM/yyyy")
        self.date_decl.setDate(QDate.currentDate())
        fila_f.addWidget(self.date_decl)
        fila_f.addStretch()
        lay.addLayout(fila_f)

        # ── Modo manual ─────────────────────────────────────────────
        self.rb_decl_manual = QRadioButton(
            "Ingresar declinación medida en campo")
        lay.addWidget(self.rb_decl_manual)

        fila_m = QHBoxLayout()
        fila_m.addSpacing(22)
        fila_m.addWidget(QLabel("Declinación:"))
        self.spin_decl = QDoubleSpinBox()
        self.spin_decl.setRange(0.0, 45.0)
        self.spin_decl.setDecimals(2)
        self.spin_decl.setSingleStep(0.25)
        self.spin_decl.setSuffix(" °")
        fila_m.addWidget(self.spin_decl)
        self.combo_decl_sentido = QComboBox()
        self.combo_decl_sentido.addItem("Oeste (W)", -1)
        self.combo_decl_sentido.addItem("Este (E)", 1)
        fila_m.addWidget(self.combo_decl_sentido)
        fila_m.addStretch()
        lay.addLayout(fila_m)

        def _sync():
            auto = self.rb_decl_auto.isChecked()
            self.date_decl.setEnabled(auto)
            self.spin_decl.setEnabled(not auto)
            self.combo_decl_sentido.setEnabled(not auto)

        self.rb_decl_auto.toggled.connect(lambda _: _sync())
        _sync()

        aviso = QLabel(
            "El azimut magnético es de USO EXCLUSIVO DE CAMPO. El azimut de "
            "cuadrícula es el que rige el replanteo oficial y la reproducción "
            "de coordenadas. La declinación cambia con los años: por eso se "
            "guarda junto con la fecha y el modelo empleado. Usa el modo "
            "manual solo si mediste la declinación en terreno; en Perú es "
            "Oeste, y un valor tomado de un GPS antiguo puede estar varios "
            "grados desactualizado."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet("color: #8a6d00;")
        lay.addWidget(aviso)
        return caja

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _geom_type_label(self):
        return {0: "Punto", 1: "Línea", 2: "Polígono"}.get(self.geom_type, "?")

    def get_opciones(self):
        """
        Retorna dict: key → nombre_campo_destino  (solo los marcados)
        Ej: {"area_ha": "area_ha", "perimetro_m": "mi_perimetro"}
        """
        result = {}
        for key, row in self._rows.items():
            if row.is_checked():
                result[key] = row.get_field_name()
        return result

    def get_crs(self):
        return self.combo_crs.currentData()

    def get_fecha(self):
        """Fecha ISO para el cálculo magnético (None si no aplica)."""
        w = getattr(self, "date_decl", None)
        return w.date().toString("yyyy-MM-dd") if w is not None else None

    def get_declinacion_manual(self):
        """Declinación en grados con signo (Este +, Oeste -).

        Devuelve None cuando el modo automático está activo, que es lo que
        el calculador interpreta como "usar el modelo WMM".
        """
        rb = getattr(self, "rb_decl_manual", None)
        if rb is None or not rb.isChecked():
            return None
        signo = self.combo_decl_sentido.currentData()
        return float(self.spin_decl.value()) * float(signo)

    def get_metodo(self):
        """Retorna 'planar' o 'elipsoidal' según la selección."""
        return "planar" if self.rb_planar.isChecked() else "elipsoidal"

    def get_solo_seleccion(self):
        return self.chk_solo_seleccion.isChecked()

    def validate(self):
        opciones = self.get_opciones()
        if not opciones:
            QMessageBox.warning(self, "Sin campos",
                "Selecciona al menos un campo para calcular.")
            return False
        # Verificar que ningún nombre de campo esté vacío
        for key, fname in opciones.items():
            if not fname:
                QMessageBox.warning(self, "Nombre vacío",
                    f"El campo '{key}' no tiene un nombre de destino.\n"
                    f"Escribe un nombre o desmarca la opción.")
                return False
            if len(fname) > 20:
                QMessageBox.warning(self, "Nombre muy largo",
                    f"'{fname}' supera 20 caracteres.\n"
                    f"Los nombres de campo tienen un límite de 20 caracteres.")
                return False
        return True

    def _calcular_todo(self):
        """Marca todos los campos, usa nombres por defecto y ejecuta."""
        # Marcar todos los checkboxes
        for row in self._rows.values():
            row.chk.setChecked(True)
        # Validar y ejecutar directamente
        if self.validate():
            super().accept()

    def accept(self):
        if self.validate():
            super().accept()
