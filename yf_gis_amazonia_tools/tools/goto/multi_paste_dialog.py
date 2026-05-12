# -*- coding: utf-8 -*-
"""
YF Go-To Tool - Multi-Paste Dialog
Diálogo para pegar múltiples coordenadas de texto libre.

Casos típicos:
- WhatsApp: lista de vértices descritos en lenguaje natural
- Excel: copy-paste de varias filas
- Reporte SERFOR: tabla pegada como texto

Detecta automáticamente y muestra preview antes de crear markers.

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QListWidget, QListWidgetItem, QComboBox,
    QSpinBox, QGroupBox, QFormLayout, QDialogButtonBox, QFrame
)

from ...core.paste_helpers import extract_multiple_pairs, guess_coordinate_type
from ...core.coord_parser import (
    utm_to_latlon, latlon_to_utm, format_dd, format_utm,
    MGRS_E_LETTERS, MGRS_N_LETTERS
)


UTM_BANDS = list('CDEFGHJKLMNPQRSTUVWX')


class MultiPasteDialog(QDialog):
    """Diálogo para pegar múltiples coordenadas y crear N markers."""

    # Emite lista de (lat, lon, label) cuando el usuario confirma
    coordinatesAccepted = pyqtSignal(list)

    def __init__(self, default_utm_zone=19, default_utm_band='L', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pegar múltiples coordenadas")
        self.setMinimumSize(600, 550)

        self.default_zone = default_utm_zone
        self.default_band = default_utm_band
        self.parsed_pairs = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ---- Instrucciones ----
        info = QLabel(
            "<b>Pegue las coordenadas</b> desde Excel, WhatsApp, correo, o cualquier fuente.<br>"
            "<small>El plugin detectará pares Este/Norte o Lat/Lon automáticamente.</small>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # ---- Área de pegado ----
        self.paste_text = QPlainTextEdit()
        mono = QFont()
        mono.setFamilies(["Consolas", "Monaco", "monospace"])
        mono.setPointSize(10)
        self.paste_text.setFont(mono)
        self.paste_text.setPlaceholderText(
            "Pegue aquí. Ejemplos:\n\n"
            "V1: 485185, 8625060\n"
            "V2: 485200, 8624800\n"
            "V3: 484950, 8624900\n\n"
            "o desde WhatsApp:\n"
            "Vertice 1 este 485185 norte 8625060\n"
            "Vertice 2 este 485200 norte 8624800"
        )
        self.paste_text.setMinimumHeight(160)
        layout.addWidget(self.paste_text)

        # ---- Configuración del tipo de coordenadas ----
        config_group = QGroupBox("Tipo de coordenadas pegadas")
        config_layout = QVBoxLayout(config_group)

        # Auto-detección
        self.type_label = QLabel(
            "<i>Pegue contenido arriba y presione <b>Detectar</b> para analizar.</i>"
        )
        self.type_label.setStyleSheet("color: #555; font-size: 10pt;")
        config_layout.addWidget(self.type_label)

        # Selector manual de tipo (si la auto-detección falla)
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Forzar tipo:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Auto-detectar", "auto")
        self.type_combo.addItem("UTM (Este, Norte)", "utm")
        self.type_combo.addItem("Decimal (Lat, Lon)", "latlon")
        self.type_combo.addItem("Decimal (Lon, Lat - invertido)", "lonlat")
        type_row.addWidget(self.type_combo, 1)
        config_layout.addLayout(type_row)

        # Para UTM: zona/banda
        utm_row = QHBoxLayout()
        utm_row.addWidget(QLabel("Si UTM, Zona:"))
        self.zone_spin = QSpinBox()
        self.zone_spin.setRange(1, 60)
        self.zone_spin.setValue(self.default_zone)
        self.zone_spin.setMaximumWidth(60)
        utm_row.addWidget(self.zone_spin)

        utm_row.addWidget(QLabel("Banda:"))
        self.band_combo = QComboBox()
        for b in UTM_BANDS:
            hemi = 'S' if b in 'CDEFGHJKLM' else 'N'
            self.band_combo.addItem(f"{b} ({hemi})", b)
        idx = self.band_combo.findData(self.default_band)
        if idx >= 0:
            self.band_combo.setCurrentIndex(idx)
        utm_row.addWidget(self.band_combo)
        utm_row.addStretch()
        config_layout.addLayout(utm_row)

        # Botón Detectar
        detect_row = QHBoxLayout()
        self.detect_btn = QPushButton("🔍  Detectar y previsualizar")
        self.detect_btn.setMinimumHeight(32)
        self.detect_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 6px 12px;
            }
            QPushButton:hover { background-color: #3498db; }
        """)
        detect_row.addWidget(self.detect_btn)
        config_layout.addLayout(detect_row)

        layout.addWidget(config_group)

        # ---- Preview ----
        preview_group = QGroupBox("Vista previa")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_list = QListWidget()
        self.preview_list.setMaximumHeight(150)
        self.preview_list.setStyleSheet("""
            QListWidget::item { padding: 4px; font-family: monospace; }
        """)
        preview_layout.addWidget(self.preview_list)

        self.preview_summary = QLabel("")
        self.preview_summary.setStyleSheet("color: #555; font-size: 10pt;")
        preview_layout.addWidget(self.preview_summary)

        layout.addWidget(preview_group)

        # ---- Botones ----
        button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.ok_btn = button_box.addButton(
            "✓  Crear markers", QDialogButtonBox.AcceptRole
        )
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.ok_btn.setEnabled(False)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Conexiones
        self.detect_btn.clicked.connect(self._detect_and_preview)
        self.paste_text.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self):
        # Limpiar preview cuando cambia el texto
        self.preview_list.clear()
        self.preview_summary.setText("<i>Texto modificado, presione Detectar.</i>")
        self.ok_btn.setEnabled(False)

    def _detect_and_preview(self):
        text = self.paste_text.toPlainText()
        if not text.strip():
            self.type_label.setText(
                "<span style='color: #c0392b;'>⚠ Sin contenido para analizar</span>"
            )
            return

        # Extraer pares
        pairs = extract_multiple_pairs(text)
        if not pairs:
            self.type_label.setText(
                "<span style='color: #c0392b;'>⚠ No se detectaron pares de coordenadas</span>"
            )
            self.preview_list.clear()
            self.preview_summary.setText("")
            self.ok_btn.setEnabled(False)
            return

        # Determinar tipo
        forced = self.type_combo.currentData()
        if forced == "auto":
            # Auto-detectar basado en magnitudes
            types_detected = [guess_coordinate_type(p[0], p[1]) for p in pairs]
            # Si la mayoría son UTM, usar UTM; idem latlon
            utm_count = types_detected.count('utm')
            ll_count = types_detected.count('latlon')
            if utm_count >= ll_count and utm_count > 0:
                detected_type = 'utm'
            elif ll_count > 0:
                detected_type = 'latlon'
            else:
                self.type_label.setText(
                    "<span style='color: #c0392b;'>⚠ No se pudo identificar el tipo. "
                    "Seleccione manualmente.</span>"
                )
                self.preview_list.clear()
                self.ok_btn.setEnabled(False)
                return
        else:
            detected_type = forced

        # Convertir todos los pares a (lat, lon, label)
        results = []
        zone = self.zone_spin.value()
        band = self.band_combo.currentData() or 'L'
        is_south = band in 'CDEFGHJKLM'

        for i, (v1, v2) in enumerate(pairs):
            try:
                if detected_type == 'utm':
                    easting, northing = v1, v2
                    # Si val1 > val2 considerablemente y v1 parece norte
                    if v1 > 1000000 and v2 < 1000000:
                        easting, northing = v2, v1
                    lat, lon = utm_to_latlon(easting, northing, zone, is_south)
                    label = f"V{i+1}: {zone}{band} {easting:.0f} {northing:.0f}"
                elif detected_type == 'latlon':
                    lat, lon = v1, v2
                    label = f"V{i+1}: {lat:.6f}, {lon:.6f}"
                elif detected_type == 'lonlat':
                    lat, lon = v2, v1
                    label = f"V{i+1}: {lat:.6f}, {lon:.6f}"
                else:
                    continue

                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    results.append((lat, lon, label))
            except Exception as e:
                continue

        if not results:
            self.type_label.setText(
                "<span style='color: #c0392b;'>⚠ No se pudieron convertir las coordenadas. "
                "Verifique el tipo seleccionado.</span>"
            )
            self.preview_list.clear()
            self.ok_btn.setEnabled(False)
            return

        # Mostrar preview
        type_name = {
            'utm': f'UTM Zona {zone}{band}',
            'latlon': 'Decimal Lat/Lon',
            'lonlat': 'Decimal Lon/Lat',
        }.get(detected_type, detected_type)

        self.type_label.setText(
            f"<span style='color: #27ae60;'>✓ Detectado: <b>{type_name}</b> · "
            f"{len(results)} punto(s)</span>"
        )

        self.preview_list.clear()
        for lat, lon, label in results:
            item = QListWidgetItem(f"{label}  →  {lat:.5f}, {lon:.5f}")
            self.preview_list.addItem(item)

        self.preview_summary.setText(
            f"<b>{len(results)} markers</b> listos para crear."
        )
        self.parsed_pairs = results
        self.ok_btn.setEnabled(True)

    def get_results(self):
        """Retorna la lista de (lat, lon, label) confirmados."""
        return self.parsed_pairs
