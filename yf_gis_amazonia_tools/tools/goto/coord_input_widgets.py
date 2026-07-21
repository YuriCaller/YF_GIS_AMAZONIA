# -*- coding: utf-8 -*-
"""
YF Go-To Tool - Coordinate Input Widgets
Widgets con campos separados para cada formato de coordenada.

Cada widget hereda de CoordInputBase y debe implementar:
- get_coordinates() -> (lat, lon, label) o None
- set_coordinates(lat, lon) para inicializar con valores

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import logging
from qgis.PyQt.QtCore import Qt, pyqtSignal, QRegularExpression
from qgis.PyQt.QtGui import QFont, QDoubleValidator, QIntValidator, QRegularExpressionValidator
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QFormLayout
)

from ...core.coord_parser import (
    latlon_to_utm, utm_to_latlon, parse_dms, format_dms,
    MGRS_E_LETTERS, MGRS_N_LETTERS
)
from ...core.smart_widgets import SmartDoubleSpinBox, SmartSpinBox, SmartLineEdit
from ...core.paste_helpers import guess_coordinate_type


# Banda UTM válidas (sur a norte)
UTM_BANDS = list('CDEFGHJKLMNPQRSTUVWX')

# Mapeo banda → hemisferio
def band_to_hemisphere(band):
    return 'S' if band in 'CDEFGHJKLM' else 'N'


# ============================================================
# Base
# ============================================================

class CoordInputBase(QWidget):
    """Base para todos los widgets de entrada."""

    coordinatesChanged = pyqtSignal()  # se emite cuando los campos cambian
    submitRequested = pyqtSignal()     # Enter presionado

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mono_font = QFont()
        self._mono_font.setFamilies(["Consolas", "Monaco", "monospace"])
        self._mono_font.setPointSize(10)

    def get_coordinates(self):
        """Retorna (lat, lon, label) o None si los campos no son válidos."""
        raise NotImplementedError

    def set_coordinates(self, lat, lon):
        """Inicializa los campos con (lat, lon) en grados decimales."""
        raise NotImplementedError

    def clear(self):
        """Limpia los campos."""
        raise NotImplementedError


# ============================================================
# Decimal Degrees
# ============================================================

class DDInputWidget(CoordInputBase):
    """Dos campos: latitud y longitud en decimales."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        self.lat_edit = SmartDoubleSpinBox()
        self.lat_edit.setDecimals(8)
        self.lat_edit.setRange(-90.0, 90.0)
        self.lat_edit.setSingleStep(0.0001)
        self.lat_edit.setFont(self._mono_font)
        self.lat_edit.setMinimumHeight(28)
        self.lat_edit.setSpecialValueText(" ")
        self.lat_edit.setValue(-12.5934)
        layout.addRow("Latitud (°):", self.lat_edit)

        self.lon_edit = SmartDoubleSpinBox()
        self.lon_edit.setDecimals(8)
        self.lon_edit.setRange(-180.0, 180.0)
        self.lon_edit.setSingleStep(0.0001)
        self.lon_edit.setFont(self._mono_font)
        self.lon_edit.setMinimumHeight(28)
        self.lon_edit.setValue(-69.1894)
        layout.addRow("Longitud (°):", self.lon_edit)

        hint = QLabel(
            "<small><i>Pega <code>lat lon</code> en cualquier campo y se distribuirán automáticamente.</i></small>"
        )
        hint.setStyleSheet("color: #888;")
        hint.setWordWrap(True)
        layout.addRow("", hint)

        self.lat_edit.valueChanged.connect(self.coordinatesChanged.emit)
        self.lon_edit.valueChanged.connect(self.coordinatesChanged.emit)

        # Manejar paste de pares en cualquier campo
        self.lat_edit.pairPasted.connect(self._on_pair_pasted)
        self.lon_edit.pairPasted.connect(self._on_pair_pasted)

    def _on_pair_pasted(self, val1, val2):
        """
        Recibe el par pegado y lo distribuye:
        - Si los valores parecen lat/lon (rango decimal), val1=lat val2=lon
        - Lo mismo independientemente del campo donde se pegó
        """
        # Validar rangos lat/lon
        if -90 <= val1 <= 90 and -180 <= val2 <= 180:
            self.lat_edit.blockSignals(True)
            self.lon_edit.blockSignals(True)
            try:
                self.lat_edit.setValue(val1)
                self.lon_edit.setValue(val2)
            finally:
                self.lat_edit.blockSignals(False)
                self.lon_edit.blockSignals(False)
            self.coordinatesChanged.emit()

    def get_coordinates(self):
        try:
            lat = self.lat_edit.value()
            lon = self.lon_edit.value()
            label = f"{lat:.6f}, {lon:.6f}"
            return (lat, lon, label)
        except Exception:
            return None

    def set_coordinates(self, lat, lon):
        self.lat_edit.blockSignals(True)
        self.lon_edit.blockSignals(True)
        self.lat_edit.setValue(lat)
        self.lon_edit.setValue(lon)
        self.lat_edit.blockSignals(False)
        self.lon_edit.blockSignals(False)

    def clear(self):
        self.lat_edit.setValue(0.0)
        self.lon_edit.setValue(0.0)


# ============================================================
# DMS (Degrees, Minutes, Seconds)
# ============================================================

class DMSInputWidget(CoordInputBase):
    """Campos sexagesimales: grados, minutos, segundos, hemisferio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ---- Latitud ----
        lat_box = QHBoxLayout()
        lat_box.setSpacing(4)
        lat_box.addWidget(QLabel("Lat:"))

        self.lat_deg = SmartSpinBox()
        self.lat_deg.setRange(0, 90)
        self.lat_deg.setSuffix("°")
        self.lat_deg.setMinimumHeight(28)
        self.lat_deg.setFixedWidth(60)
        self.lat_deg.setFont(self._mono_font)
        self.lat_deg.setValue(12)
        lat_box.addWidget(self.lat_deg)

        self.lat_min = QSpinBox()
        self.lat_min.setRange(0, 59)
        self.lat_min.setSuffix("'")
        self.lat_min.setMinimumHeight(28)
        self.lat_min.setFixedWidth(54)
        self.lat_min.setFont(self._mono_font)
        self.lat_min.setValue(35)
        lat_box.addWidget(self.lat_min)

        self.lat_sec = QDoubleSpinBox()
        self.lat_sec.setRange(0.0, 59.999999)
        self.lat_sec.setDecimals(3)
        self.lat_sec.setSuffix('"')
        self.lat_sec.setMinimumHeight(28)
        self.lat_sec.setFixedWidth(78)
        self.lat_sec.setFont(self._mono_font)
        self.lat_sec.setValue(36.240)
        lat_box.addWidget(self.lat_sec)

        self.lat_hemi = QComboBox()
        self.lat_hemi.addItems(["N", "S"])
        self.lat_hemi.setCurrentText("S")
        self.lat_hemi.setMinimumHeight(28)
        self.lat_hemi.setFixedWidth(48)
        lat_box.addWidget(self.lat_hemi)
        lat_box.addStretch()
        layout.addLayout(lat_box)

        # ---- Longitud ----
        lon_box = QHBoxLayout()
        lon_box.setSpacing(4)
        lon_box.addWidget(QLabel("Lon:"))

        self.lon_deg = QSpinBox()
        self.lon_deg.setRange(0, 180)
        self.lon_deg.setSuffix("°")
        self.lon_deg.setMinimumHeight(28)
        self.lon_deg.setFixedWidth(60)
        self.lon_deg.setFont(self._mono_font)
        self.lon_deg.setValue(69)
        lon_box.addWidget(self.lon_deg)

        self.lon_min = QSpinBox()
        self.lon_min.setRange(0, 59)
        self.lon_min.setSuffix("'")
        self.lon_min.setMinimumHeight(28)
        self.lon_min.setFixedWidth(54)
        self.lon_min.setFont(self._mono_font)
        self.lon_min.setValue(11)
        lon_box.addWidget(self.lon_min)

        self.lon_sec = QDoubleSpinBox()
        self.lon_sec.setRange(0.0, 59.999999)
        self.lon_sec.setDecimals(3)
        self.lon_sec.setSuffix('"')
        self.lon_sec.setMinimumHeight(28)
        self.lon_sec.setFixedWidth(78)
        self.lon_sec.setFont(self._mono_font)
        self.lon_sec.setValue(21.840)
        lon_box.addWidget(self.lon_sec)

        self.lon_hemi = QComboBox()
        self.lon_hemi.addItems(["E", "W"])
        self.lon_hemi.setCurrentText("W")
        self.lon_hemi.setMinimumHeight(28)
        self.lon_hemi.setFixedWidth(48)
        lon_box.addWidget(self.lon_hemi)
        lon_box.addStretch()
        layout.addLayout(lon_box)

        # Hint
        hint = QLabel("<small><i>Formato: grados, minutos, segundos, hemisferio</i></small>")
        hint.setStyleSheet("color: #888;")
        layout.addWidget(hint)

        # Conectar señales
        for w in [self.lat_deg, self.lat_min, self.lat_sec,
                  self.lon_deg, self.lon_min, self.lon_sec]:
            w.valueChanged.connect(self.coordinatesChanged.emit)
        self.lat_hemi.currentTextChanged.connect(self.coordinatesChanged.emit)
        self.lon_hemi.currentTextChanged.connect(self.coordinatesChanged.emit)

        # Paste inteligente en lat_deg (único que es SmartSpinBox)
        # Si pegan un par decimal, convertirlo a DMS
        self.lat_deg.pairPasted.connect(self._on_pair_pasted)

    def _on_pair_pasted(self, val1, val2):
        """Si pegan lat/lon decimal, convertir a DMS."""
        if abs(val1) <= 90 and abs(val2) <= 180:
            self.set_coordinates(val1, val2)
            self.coordinatesChanged.emit()

    def get_coordinates(self):
        try:
            lat = (self.lat_deg.value()
                   + self.lat_min.value() / 60
                   + self.lat_sec.value() / 3600)
            if self.lat_hemi.currentText() == "S":
                lat = -lat

            lon = (self.lon_deg.value()
                   + self.lon_min.value() / 60
                   + self.lon_sec.value() / 3600)
            if self.lon_hemi.currentText() == "W":
                lon = -lon

            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return None
            label = format_dms(lat, lon)
            return (lat, lon, label)
        except Exception:
            return None

    def set_coordinates(self, lat, lon):
        # Bloquear señales mientras llenamos
        all_widgets = [self.lat_deg, self.lat_min, self.lat_sec,
                       self.lon_deg, self.lon_min, self.lon_sec,
                       self.lat_hemi, self.lon_hemi]
        for w in all_widgets:
            w.blockSignals(True)

        try:
            # Latitud
            self.lat_hemi.setCurrentText("N" if lat >= 0 else "S")
            v = abs(lat)
            d = int(v)
            m_full = (v - d) * 60
            m = int(m_full)
            s = (m_full - m) * 60
            self.lat_deg.setValue(d)
            self.lat_min.setValue(m)
            self.lat_sec.setValue(s)

            # Longitud
            self.lon_hemi.setCurrentText("E" if lon >= 0 else "W")
            v = abs(lon)
            d = int(v)
            m_full = (v - d) * 60
            m = int(m_full)
            s = (m_full - m) * 60
            self.lon_deg.setValue(d)
            self.lon_min.setValue(m)
            self.lon_sec.setValue(s)
        finally:
            for w in all_widgets:
                w.blockSignals(False)

    def clear(self):
        for w in [self.lat_deg, self.lat_min, self.lat_sec,
                  self.lon_deg, self.lon_min, self.lon_sec]:
            w.setValue(0)


# ============================================================
# UTM
# ============================================================

class UTMInputWidget(CoordInputBase):
    """
    Campos UTM: zona (número), banda (letra), easting, northing.
    Zona y banda detectadas auto desde el CRS del proyecto.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ---- Zona y banda ----
        zone_box = QHBoxLayout()
        zone_box.setSpacing(6)

        zone_box.addWidget(QLabel("Zona:"))
        self.zone_spin = QSpinBox()
        self.zone_spin.setRange(1, 60)
        self.zone_spin.setMinimumHeight(28)
        self.zone_spin.setFixedWidth(60)
        self.zone_spin.setFont(self._mono_font)
        self.zone_spin.setValue(19)  # default Madre de Dios
        zone_box.addWidget(self.zone_spin)

        zone_box.addWidget(QLabel("Banda:"))
        self.band_combo = QComboBox()
        for b in UTM_BANDS:
            hemi = band_to_hemisphere(b)
            self.band_combo.addItem(f"{b}  ({hemi})", b)
        self.band_combo.setCurrentText("L  (S)")
        # Set por valor real
        idx = self.band_combo.findData("L")
        if idx >= 0:
            self.band_combo.setCurrentIndex(idx)
        self.band_combo.setMinimumHeight(28)
        self.band_combo.setMinimumWidth(80)
        zone_box.addWidget(self.band_combo)

        zone_box.addStretch()
        layout.addLayout(zone_box)

        # Indicador de detección
        self.detection_label = QLabel("")
        self.detection_label.setWordWrap(True)
        self.detection_label.setStyleSheet("color: #27ae60; font-size: 10pt;")
        layout.addWidget(self.detection_label)

        # ---- Easting y Northing ----
        form = QFormLayout()
        form.setSpacing(6)

        self.easting_spin = SmartDoubleSpinBox()
        self.easting_spin.setRange(100000, 999999.999)
        self.easting_spin.setDecimals(2)
        self.easting_spin.setMinimumHeight(28)
        self.easting_spin.setFont(self._mono_font)
        self.easting_spin.setSuffix(" m")
        self.easting_spin.setValue(479428.0)
        form.addRow("Easting (X):", self.easting_spin)

        self.northing_spin = SmartDoubleSpinBox()
        self.northing_spin.setRange(0, 10000000.0)
        self.northing_spin.setDecimals(2)
        self.northing_spin.setMinimumHeight(28)
        self.northing_spin.setFont(self._mono_font)
        self.northing_spin.setSuffix(" m")
        self.northing_spin.setValue(8607821.0)
        form.addRow("Northing (Y):", self.northing_spin)

        layout.addLayout(form)

        # Hint mejorado para v1.2
        hint = QLabel(
            "<small><i>💡 <b>Pega desde Excel</b> (este, norte separados por tab/coma/espacio) "
            "en cualquier campo. Se distribuirán automáticamente.</i></small>"
        )
        hint.setStyleSheet("color: #888;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Conectar
        self.zone_spin.valueChanged.connect(self.coordinatesChanged.emit)
        self.band_combo.currentIndexChanged.connect(self.coordinatesChanged.emit)
        self.easting_spin.valueChanged.connect(self.coordinatesChanged.emit)
        self.northing_spin.valueChanged.connect(self.coordinatesChanged.emit)

        # Paste inteligente: distribuir par pegado entre Easting y Northing
        self.easting_spin.pairPasted.connect(self._on_pair_pasted)
        self.northing_spin.pairPasted.connect(self._on_pair_pasted)

    def _on_pair_pasted(self, val1, val2):
        """
        Distribuye un par pegado entre Easting y Northing.

        Heurística:
        - Si val1 es claramente Northing (>1,000,000) y val2 es Easting (<1,000,000),
          intercambiar (manejar orden inverso)
        - Si los valores parecen lat/lon decimal, convertir a UTM usando zona actual
        - En el caso normal: val1=Easting, val2=Northing
        """
        # Caso 1: ambos son rangos UTM válidos
        if 10000 < abs(val1) < 10000000 and 10000 < abs(val2) < 10000000:
            # Detectar si están en orden inverso (Norte primero, Este después)
            # Norte de UTM en zona sur va de ~1,000,000 a 10,000,000
            # Este de UTM va de 100,000 a 999,999
            if val1 > 1000000 and val2 < 1000000:
                # Orden inverso detectado
                easting, northing = val2, val1
            else:
                easting, northing = val1, val2

            self.easting_spin.blockSignals(True)
            self.northing_spin.blockSignals(True)
            try:
                self.easting_spin.setValue(easting)
                self.northing_spin.setValue(northing)
            finally:
                self.easting_spin.blockSignals(False)
                self.northing_spin.blockSignals(False)
            self.coordinatesChanged.emit()
            return

        # Caso 2: parecen lat/lon decimal → convertir a UTM
        if abs(val1) <= 90 and abs(val2) <= 180:
            try:
                z, b, e, n = latlon_to_utm(val1, val2)
                self.zone_spin.blockSignals(True)
                self.band_combo.blockSignals(True)
                self.easting_spin.blockSignals(True)
                self.northing_spin.blockSignals(True)
                try:
                    self.zone_spin.setValue(z)
                    idx = self.band_combo.findData(b)
                    if idx >= 0:
                        self.band_combo.setCurrentIndex(idx)
                    self.easting_spin.setValue(e)
                    self.northing_spin.setValue(n)
                finally:
                    self.zone_spin.blockSignals(False)
                    self.band_combo.blockSignals(False)
                    self.easting_spin.blockSignals(False)
                    self.northing_spin.blockSignals(False)
                self.coordinatesChanged.emit()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def set_detection_info(self, text):
        """Muestra mensaje sobre la detección auto del CRS."""
        self.detection_label.setText(text)

    def apply_crs_detection(self, zone, band):
        """Aplica zona/banda detectada desde CRS sin emitir señales."""
        if zone is None:
            return
        self.zone_spin.blockSignals(True)
        self.band_combo.blockSignals(True)
        try:
            self.zone_spin.setValue(zone)
            if band:
                idx = self.band_combo.findData(band)
                if idx >= 0:
                    self.band_combo.setCurrentIndex(idx)
        finally:
            self.zone_spin.blockSignals(False)
            self.band_combo.blockSignals(False)

    def get_coordinates(self):
        try:
            zone = self.zone_spin.value()
            band = self.band_combo.currentData() or 'L'
            easting = self.easting_spin.value()
            northing = self.northing_spin.value()
            is_south = band in 'CDEFGHJKLM'
            lat, lon = utm_to_latlon(easting, northing, zone, is_south)
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return None
            label = f"{zone}{band} {easting:.0f} {northing:.0f}"
            return (lat, lon, label)
        except Exception:
            return None

    def set_coordinates(self, lat, lon):
        """Convierte lat/lon a UTM y llena los campos."""
        try:
            zone, band, easting, northing = latlon_to_utm(lat, lon)
            self.zone_spin.blockSignals(True)
            self.band_combo.blockSignals(True)
            self.easting_spin.blockSignals(True)
            self.northing_spin.blockSignals(True)
            try:
                self.zone_spin.setValue(zone)
                idx = self.band_combo.findData(band)
                if idx >= 0:
                    self.band_combo.setCurrentIndex(idx)
                self.easting_spin.setValue(easting)
                self.northing_spin.setValue(northing)
            finally:
                self.zone_spin.blockSignals(False)
                self.band_combo.blockSignals(False)
                self.easting_spin.blockSignals(False)
                self.northing_spin.blockSignals(False)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def clear(self):
        self.easting_spin.setValue(500000)
        self.northing_spin.setValue(0)


# ============================================================
# MGRS
# ============================================================

class MGRSInputWidget(CoordInputBase):
    """
    Campos MGRS: zona (número + banda) + 2 letras de cuadrícula + dígitos.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ---- Grid Zone Designator (GZD) ----
        gzd_box = QHBoxLayout()
        gzd_box.setSpacing(4)
        gzd_box.addWidget(QLabel("Zona:"))

        self.zone_spin = QSpinBox()
        self.zone_spin.setRange(1, 60)
        self.zone_spin.setMinimumHeight(28)
        self.zone_spin.setFixedWidth(60)
        self.zone_spin.setFont(self._mono_font)
        self.zone_spin.setValue(19)
        gzd_box.addWidget(self.zone_spin)

        self.band_combo = QComboBox()
        for b in UTM_BANDS:
            self.band_combo.addItem(b, b)
        idx = self.band_combo.findData("L")
        if idx >= 0:
            self.band_combo.setCurrentIndex(idx)
        self.band_combo.setMinimumHeight(28)
        self.band_combo.setFixedWidth(60)
        self.band_combo.setFont(self._mono_font)
        gzd_box.addWidget(self.band_combo)

        gzd_box.addWidget(QLabel("Cuadr:"))

        # Letras del cuadrante (100km grid square)
        self.grid_e = QComboBox()
        for c in MGRS_E_LETTERS:
            self.grid_e.addItem(c, c)
        self.grid_e.setMinimumHeight(28)
        self.grid_e.setFixedWidth(54)
        self.grid_e.setFont(self._mono_font)
        gzd_box.addWidget(self.grid_e)

        self.grid_n = QComboBox()
        for c in MGRS_N_LETTERS:
            self.grid_n.addItem(c, c)
        self.grid_n.setMinimumHeight(28)
        self.grid_n.setFixedWidth(54)
        self.grid_n.setFont(self._mono_font)
        gzd_box.addWidget(self.grid_n)

        gzd_box.addStretch()
        layout.addLayout(gzd_box)

        # ---- Coordenadas numéricas ----
        coords_box = QHBoxLayout()
        coords_box.setSpacing(6)

        coords_box.addWidget(QLabel("Easting:"))
        self.east_edit = QLineEdit()
        self.east_edit.setMinimumHeight(28)
        self.east_edit.setMaximumWidth(120)
        self.east_edit.setFont(self._mono_font)
        # Solo dígitos, hasta 5
        val = QRegularExpressionValidator(QRegularExpression(r'\d{0,5}'), self)
        self.east_edit.setValidator(val)
        self.east_edit.setText("79428")
        self.east_edit.setPlaceholderText("0-99999")
        coords_box.addWidget(self.east_edit)

        coords_box.addWidget(QLabel("Northing:"))
        self.north_edit = QLineEdit()
        self.north_edit.setMinimumHeight(28)
        self.north_edit.setMaximumWidth(120)
        self.north_edit.setFont(self._mono_font)
        val2 = QRegularExpressionValidator(QRegularExpression(r'\d{0,5}'), self)
        self.north_edit.setValidator(val2)
        self.north_edit.setText("07821")
        self.north_edit.setPlaceholderText("0-99999")
        coords_box.addWidget(self.north_edit)
        coords_box.addStretch()

        layout.addLayout(coords_box)

        # Hint
        hint = QLabel(
            "<small><i>Precisión metro (5 dígitos). Ej: 19L DE 79428 07821</i></small>"
        )
        hint.setStyleSheet("color: #888;")
        layout.addWidget(hint)

        # Conexiones
        self.zone_spin.valueChanged.connect(self.coordinatesChanged.emit)
        self.band_combo.currentIndexChanged.connect(self.coordinatesChanged.emit)
        self.grid_e.currentIndexChanged.connect(self.coordinatesChanged.emit)
        self.grid_n.currentIndexChanged.connect(self.coordinatesChanged.emit)
        self.east_edit.textChanged.connect(self.coordinatesChanged.emit)
        self.north_edit.textChanged.connect(self.coordinatesChanged.emit)
        self.east_edit.returnPressed.connect(self.submitRequested.emit)
        self.north_edit.returnPressed.connect(self.submitRequested.emit)

    def get_coordinates(self):
        from ...core.coord_parser import parse_mgrs
        try:
            zone = self.zone_spin.value()
            band = self.band_combo.currentData()
            ge = self.grid_e.currentData()
            gn = self.grid_n.currentData()
            east = self.east_edit.text().zfill(5) if self.east_edit.text() else "00000"
            north = self.north_edit.text().zfill(5) if self.north_edit.text() else "00000"

            mgrs_str = f"{zone}{band}{ge}{gn}{east}{north}"
            result = parse_mgrs(mgrs_str)
            if result is None:
                return None
            lat, lon = result
            label = f"{zone}{band} {ge}{gn} {east} {north}"
            return (lat, lon, label)
        except Exception:
            return None

    def set_coordinates(self, lat, lon):
        """Aproximación: convertir a UTM, mostrar como MGRS."""
        # Esto requiere un converter latlon->mgrs completo, simplificamos
        # mostrando solo la zona/banda correcta
        try:
            zone, band, _, _ = latlon_to_utm(lat, lon)
            self.zone_spin.blockSignals(True)
            self.band_combo.blockSignals(True)
            try:
                self.zone_spin.setValue(zone)
                idx = self.band_combo.findData(band)
                if idx >= 0:
                    self.band_combo.setCurrentIndex(idx)
            finally:
                self.zone_spin.blockSignals(False)
                self.band_combo.blockSignals(False)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def clear(self):
        self.east_edit.clear()
        self.north_edit.clear()
