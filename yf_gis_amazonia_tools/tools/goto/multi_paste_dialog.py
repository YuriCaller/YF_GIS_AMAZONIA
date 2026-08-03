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
    QSpinBox, QGroupBox, QFormLayout, QDialogButtonBox, QFrame,
    QApplication, QMessageBox
)

from ...core.paste_helpers import extract_multiple_pairs, guess_coordinate_type
from ...core.coord_parser import (
    utm_to_latlon, latlon_to_utm, format_dd, format_utm,
    MGRS_E_LETTERS, MGRS_N_LETTERS
)


UTM_BANDS = list('CDEFGHJKLMNPQRSTUVWX')


class PasteTextEdit(QPlainTextEdit):
    """QPlainTextEdit que acepta pegar IMÁGENES (Ctrl+V de una captura de
    pantalla): en vez de ignorarlas, emite imagePasted para que el diálogo
    las procese con OCR. El pegado de texto funciona como siempre."""

    imagePasted = pyqtSignal(object)  # QImage

    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            self.imagePasted.emit(source.imageData())
            return
        super().insertFromMimeData(source)


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
            "<b>Pegue las coordenadas</b> desde Excel, WhatsApp, correo, o cualquier fuente "
            "— incluso una <b>captura de pantalla</b> (Ctrl+V) que se leerá con OCR.<br>"
            "<small>El plugin detectará pares Este/Norte o Lat/Lon automáticamente.</small>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # ---- Área de pegado ----
        self.paste_text = PasteTextEdit()
        self.paste_text.imagePasted.connect(self._on_imagen_pegada)
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

        # v3.0.4: OCR de capturas de pantalla
        fila_ocr = QHBoxLayout()
        self.btn_ocr = QPushButton("📷  Pegar captura de pantalla (OCR)")
        self.btn_ocr.setToolTip(
            "Lee la imagen del portapapeles (Win+Shift+S) y la convierte a "
            "texto con OCR.\nTambién puedes pegar la imagen directamente en "
            "el cuadro con Ctrl+V.\nEl texto reconocido SIEMPRE queda a la "
            "vista para que lo revises antes de Detectar.")
        fila_ocr.addWidget(self.btn_ocr)

        # v3.0.4: interruptor del motor nativo. Se auto-desactiva si el
        # motor se cuelga (ver ocr_windows_native.TIMEOUT_SEGUNDOS); este
        # checkbox es la forma de volver a activarlo cuando el usuario
        # quiera reintentar.
        from qgis.PyQt.QtWidgets import QCheckBox as _QCheckBox
        from . import ocr_windows_native as _ocr_nat
        self.chk_ocr_nativo = _QCheckBox("Motor nativo de Windows")
        self.chk_ocr_nativo.setToolTip(
            "Usa el reconocimiento de texto integrado en Windows 10/11 "
            "(más rápido y sin instalar nada aparte).\n"
            "Si se desmarca, se usará Tesseract.\n\n"
            "Se desmarca solo si el motor nativo llega a colgarse.")
        self.chk_ocr_nativo.setChecked(_ocr_nat.nativo_habilitado())
        self.chk_ocr_nativo.setVisible(_ocr_nat.es_windows())
        self.chk_ocr_nativo.toggled.connect(_ocr_nat.set_nativo_habilitado)
        fila_ocr.addWidget(self.chk_ocr_nativo)
        fila_ocr.addStretch(1)
        layout.addLayout(fila_ocr)
        self.btn_ocr.clicked.connect(self._pegar_imagen_portapapeles)

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
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.ok_btn = button_box.addButton(
            "✓  Crear markers", QDialogButtonBox.ButtonRole.AcceptRole
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

    # ------------------------------------------------------------------
    # v3.0.4: OCR de capturas de pantalla
    # ------------------------------------------------------------------

    def _pegar_imagen_portapapeles(self):
        img = QApplication.clipboard().image()
        if img is None or img.isNull():
            QMessageBox.information(
                self, "OCR",
                "No hay ninguna imagen en el portapapeles.\n"
                "Copia una captura (Win+Shift+S) y vuelve a intentar."
            )
            return
        self._on_imagen_pegada(img)

    def _on_imagen_pegada(self, qimage):
        from .ocr_coords import ocr_imagen_auto, limpiar_texto_ocr
        from . import ocr_windows_native as _ocr_native

        # v3.0.4: primera vez que hay imagen y estamos en Windows sin
        # winsdk instalado -> ofrecer instalarlo (paquete puro Python,
        # segundos). Si el usuario dice que no, se sigue igual con
        # Tesseract vía ocr_imagen_auto — nunca bloquea el flujo.
        if (_ocr_native.es_windows()
                and not _ocr_native.winsdk_disponible()
                and not getattr(self, '_winsdk_ya_preguntado', False)):
            self._winsdk_ya_preguntado = True
            resp = QMessageBox.question(
                self, "OCR — motor nativo de Windows",
                "Windows trae un motor de reconocimiento de texto "
                "integrado, más rápido y sin instalar nada aparte "
                "(a diferencia de Tesseract).\n\n"
                "Requiere un paquete Python pequeño ('winsdk', sin "
                "ejecutables, instala en segundos).\n\n"
                "¿Instalarlo ahora? (Puedes seguir usando Tesseract si "
                "eliges 'No'.)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp == QMessageBox.StandardButton.Yes:
                # getattr cubre Qt5 (enum plano) y Qt6 (enum con scope):
                # no hace falta try/except, y no deja literal sin scope.
                cursor_inst = getattr(Qt, "CursorShape", Qt).WaitCursor
                QApplication.setOverrideCursor(cursor_inst)
                try:
                    ok, salida = _ocr_native.instalar_winsdk()
                finally:
                    QApplication.restoreOverrideCursor()

                # v3.0.4 fix: pip puede devolver éxito (returncode 0) pero
                # haber instalado en el entorno de un python.exe DISTINTO
                # al que corre esta sesión de QGIS (típico en instalaciones
                # OSGeo4W con varios Python) — se verifica con un import
                # real antes de prometer que "ya funciona".
                if ok:
                    ok = _ocr_native.winsdk_disponible()

                if ok:
                    QMessageBox.information(
                        self, "Listo",
                        "Motor nativo instalado y verificado. Se usará "
                        "automáticamente desde ahora (no hace falta "
                        "reiniciar QGIS).")
                else:
                    QMessageBox.warning(
                        self, "No se pudo instalar",
                        "'winsdk' no quedó disponible en el Python de "
                        "QGIS (puede haberse instalado en un intérprete "
                        "distinto). Se seguirá usando Tesseract mientras "
                        "tanto.\n\nDetalle técnico:\n" + salida[-1500:])

        cursor_espera = getattr(Qt, "CursorShape", Qt).WaitCursor
        QApplication.setOverrideCursor(cursor_espera)
        try:
            texto = ocr_imagen_auto(qimage)
        except RuntimeError as e:
            QApplication.restoreOverrideCursor()
            # El motor nativo pudo auto-desactivarse por timeout: reflejarlo
            # en el checkbox para que el usuario vea qué pasó y pueda
            # reactivarlo cuando quiera.
            try:
                self.chk_ocr_nativo.blockSignals(True)
                self.chk_ocr_nativo.setChecked(
                    _ocr_native.nativo_habilitado())
                self.chk_ocr_nativo.blockSignals(False)
            except Exception:  # nosec B110 - reflejar el estado en el
                pass           # checkbox es cosmetico; el flujo sigue
            if self._ofrecer_buscar_tesseract_manual(str(e)):
                # El usuario localizó tesseract.exe a mano: reintentar
                # una vez, ahora que la ruta quedó guardada en QSettings.
                self._on_imagen_pegada(qimage)
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "OCR", "El OCR falló:\n{}".format(e))
            return
        QApplication.restoreOverrideCursor()

        texto = limpiar_texto_ocr(texto).strip()
        if not texto:
            QMessageBox.information(
                self, "OCR",
                "No se reconoció texto en la imagen.\n"
                "Prueba con una captura más nítida o con más zoom."
            )
            return

        actual = self.paste_text.toPlainText().rstrip()
        self.paste_text.setPlainText(
            (actual + "\n" if actual else "") + texto)
        self.type_label.setText(
            "<i>📷 Texto reconocido por OCR — <b>revísalo y corrígelo</b> "
            "antes de presionar Detectar.</i>")

    def _ofrecer_buscar_tesseract_manual(self, mensaje_error):
        """Muestra el error de OCR con un botón extra: localizar
        tesseract.exe a mano (cubre instalaciones en rutas atípicas que
        ni el registro de Windows ni las rutas típicas detectan).

        Devuelve True si el usuario localizó el ejecutable con éxito
        (para que el llamador reintente el OCR una sola vez).
        """
        from qgis.PyQt.QtWidgets import QFileDialog
        from .ocr_coords import guardar_ruta_manual

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("OCR no disponible")
        box.setText(mensaje_error)
        btn_buscar = box.addButton(
            "📂  Buscar tesseract.exe...", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()

        if box.clickedButton() is not btn_buscar:
            return False

        ruta, _ = QFileDialog.getOpenFileName(
            self, "Localizar tesseract.exe", "",
            "tesseract.exe (tesseract.exe);;Todos los archivos (*)")
        if not ruta:
            return False
        if guardar_ruta_manual(ruta):
            QMessageBox.information(
                self, "Listo",
                "Ruta guardada. Reintentando el reconocimiento...")
            return True
        QMessageBox.warning(
            self, "Ruta inválida",
            "El archivo seleccionado no parece válido.")
        return False

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
            except Exception:  # nosec B112 - fila malformada: se omite a proposito
                continue  # nosec B112 - entrada malformada: se omite a proposito

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
