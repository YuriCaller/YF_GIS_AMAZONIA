# -*- coding: utf-8 -*-
"""
YF Go-To Tool v1.1 - Panel principal
Panel dock con pestañas y entrada por campos separados por formato.

Cambios v1.1:
- Tab "Coords" rediseñada: selector de formato + widgets dinámicos
- Auto-detección de zona UTM desde CRS del proyecto
- Modo "Pegar y detectar" alternativo
- Sincronización en vivo entre formatos al cambiar de tab

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QComboBox, QSlider,
    QGroupBox, QToolButton, QSizePolicy, QFrame, QTabWidget,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
    QFileDialog, QStackedWidget, QButtonGroup, QFormLayout,
    QDialog, QDialogButtonBox
)

from ...core.coord_parser import (
    parse_coordinates, format_dd, format_dms, format_utm,
    FORMAT_DD, FORMAT_DMS, FORMAT_UTM, FORMAT_MGRS
)
from .coord_input_widgets import (
    DDInputWidget, DMSInputWidget, UTMInputWidget, MGRSInputWidget
)
from ...core.crs_utils import get_project_utm_info
from .multi_paste_dialog import MultiPasteDialog


# Indices de los formatos en el stack/selector
FMT_DD = 0
FMT_DMS = 1
FMT_UTM = 2
FMT_MGRS = 3


class PasteDialog(QDialog):
    """Diálogo modal para pegar coordenadas en una sola línea."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pegar y detectar")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        info = QLabel(
            "<b>Pega una coordenada</b> en cualquier formato.<br>"
            "<small>El plugin detectará automáticamente DD, DMS, UTM o MGRS.</small>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.input = QLineEdit()
        f = QFont()
        f.setFamilies(["Consolas", "Monaco", "monospace"])
        f.setPointSize(11)
        self.input.setFont(f)
        self.input.setMinimumHeight(36)
        self.input.setPlaceholderText(
            "Ej: -12.5934, -69.1894  ·  19L 479428 8607821"
        )
        layout.addWidget(self.input)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #555; font-size: 10pt;")
        self.status.setMinimumHeight(24)
        layout.addWidget(self.status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.ok_btn = buttons.button(QDialogButtonBox.Ok)
        self.ok_btn.setText("Usar coordenada")
        self.ok_btn.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.input.textChanged.connect(self._on_text_changed)
        self.input.returnPressed.connect(self._on_return)
        self.parsed = None

    def _on_text_changed(self, text):
        if not text.strip():
            self.status.setText("")
            self.ok_btn.setEnabled(False)
            self.parsed = None
            return

        result = parse_coordinates(text)
        if result is None:
            self.status.setText(
                "<span style='color: #c0392b;'>⚠ Formato no reconocido</span>"
            )
            self.ok_btn.setEnabled(False)
            self.parsed = None
        else:
            fmt_names = {
                FORMAT_DD: "Decimal", FORMAT_DMS: "DMS",
                FORMAT_UTM: "UTM", FORMAT_MGRS: "MGRS"
            }
            fmt = fmt_names.get(result['format'], 'desconocido')
            self.status.setText(
                f"<span style='color: #27ae60;'>✓ Detectado: <b>{fmt}</b> · "
                f"{format_dd(result['lat'], result['lon'])}</span>"
            )
            self.ok_btn.setEnabled(True)
            self.parsed = result

    def _on_return(self):
        if self.ok_btn.isEnabled():
            self.accept()


class GoToPanel(QDockWidget):
    """Panel dock principal v1.1."""

    goToRequested = pyqtSignal(float, float, str)
    multiCoordsRequested = pyqtSignal(list)  # lista de (lat, lon, label)
    searchRequested = pyqtSignal(str)
    bookmarkGoTo = pyqtSignal(int)
    bookmarkAdd = pyqtSignal(str, float, float, str)
    bookmarkRemove = pyqtSignal(int)
    markerGoTo = pyqtSignal(int)
    markerRemove = pyqtSignal(int)
    markersClearAll = pyqtSignal()
    markersToLayer = pyqtSignal(bool, str)

    def __init__(self, iface, parent=None):
        super().__init__("YF Go-To Tool", parent)
        self.iface = iface
        self.setObjectName("YFGoToPanel")
        self._current_format = FMT_DD

        self._build_ui()
        self._refresh_utm_detection()

    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_coords_tab(), "📍  Coords")
        self.tabs.addTab(self._build_search_tab(), "🔍  Buscar")
        self.tabs.addTab(self._build_bookmarks_tab(), "⭐  Bookmarks")
        self.tabs.addTab(self._build_markers_tab(), "📌  Markers")
        layout.addWidget(self.tabs)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)

        footer = QLabel(
            "<small>YF Go-To Tool v1.1<br>"
            "Yuri Caller · TUCSA · gis-amazonia.pe<br>"
            "<b>Atajos:</b> Ctrl+G abrir · Enter ir · Esc limpiar</small>"
        )
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #888;")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        self.setWidget(container)

    # ----------------------------------------------------------------
    # Tab: Coordenadas (REDISEÑADA v1.1)
    # ----------------------------------------------------------------

    def _build_coords_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # ---- Cabecera con título y botón "Pegar y detectar" ----
        header_row = QHBoxLayout()
        title = QLabel("<b>Ingrese coordenadas</b>")
        header_row.addWidget(title)
        header_row.addStretch()

        self.paste_btn = QToolButton()
        self.paste_btn.setText("📋  Pegar y detectar")
        self.paste_btn.setToolTip(
            "Pegar coordenada en una sola línea con detección automática"
        )
        self.paste_btn.setStyleSheet("""
            QToolButton {
                background-color: #95a5a6; color: white;
                border: none; border-radius: 3px;
                padding: 4px 10px; font-size: 9pt;
            }
            QToolButton:hover { background-color: #7f8c8d; }
        """)
        header_row.addWidget(self.paste_btn)
        layout.addLayout(header_row)

        # ---- Selector de formato ----
        format_row = QHBoxLayout()
        format_row.setSpacing(4)

        self.format_buttons = []
        self.format_group = QButtonGroup(self)
        self.format_group.setExclusive(True)

        for i, (text, tooltip) in enumerate([
            ("DD",   "Decimal (latitud, longitud)"),
            ("DMS",  "Grados, minutos, segundos"),
            ("UTM",  "Universal Transverse Mercator"),
            ("MGRS", "Military Grid Reference System"),
        ]):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setMinimumHeight(30)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet("""
                QToolButton {
                    background-color: #ecf0f1; border: 1px solid #bdc3c7;
                    border-radius: 3px; padding: 4px 8px; font-weight: bold;
                }
                QToolButton:hover { background-color: #d5dbdb; }
                QToolButton:checked {
                    background-color: #2980b9; color: white;
                    border: 1px solid #1f6391;
                }
            """)
            if i == 0:
                btn.setChecked(True)
            self.format_buttons.append(btn)
            self.format_group.addButton(btn, i)
            format_row.addWidget(btn)

        layout.addLayout(format_row)

        # ---- Stack con los widgets de entrada ----
        self.input_stack = QStackedWidget()

        self.dd_widget = DDInputWidget()
        self.dms_widget = DMSInputWidget()
        self.utm_widget = UTMInputWidget()
        self.mgrs_widget = MGRSInputWidget()

        self.input_stack.addWidget(self.dd_widget)
        self.input_stack.addWidget(self.dms_widget)
        self.input_stack.addWidget(self.utm_widget)
        self.input_stack.addWidget(self.mgrs_widget)

        # Envolver en QGroupBox para visual consistency
        input_group = QGroupBox()
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(self.input_stack)
        layout.addWidget(input_group)

        # ---- Status / validación ----
        self.coord_status = QLabel("")
        self.coord_status.setWordWrap(True)
        self.coord_status.setStyleSheet("color: #555; font-size: 10pt;")
        self.coord_status.setMinimumHeight(28)
        layout.addWidget(self.coord_status)

        # ---- Botones de acción ----
        action_row = QHBoxLayout()
        self.go_btn = QPushButton("▶  Ir al punto")
        self.go_btn.setMinimumHeight(36)
        self.go_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 6px 12px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        action_row.addWidget(self.go_btn)

        self.bookmark_current_btn = QPushButton("⭐")
        self.bookmark_current_btn.setToolTip("Guardar como bookmark")
        self.bookmark_current_btn.setMinimumHeight(36)
        self.bookmark_current_btn.setMaximumWidth(40)
        self.bookmark_current_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12; color: white;
                border: none; border-radius: 4px; font-size: 14pt;
            }
            QPushButton:hover { background-color: #e67e22; }
        """)
        action_row.addWidget(self.bookmark_current_btn)
        layout.addLayout(action_row)

        # ---- Equivalencias en otros formatos ----
        formats_group = QGroupBox("Equivalencias")
        formats_layout = QFormLayout(formats_group)
        formats_layout.setSpacing(4)

        mono = QFont()
        mono.setFamilies(["Consolas", "Monaco", "monospace"])
        mono.setPointSize(9)

        self.lbl_dd = QLineEdit()
        self.lbl_dd.setReadOnly(True)
        self.lbl_dd.setStyleSheet("background: #f8f8f8;")
        self.lbl_dd.setFont(mono)
        formats_layout.addRow("Decimal:", self.lbl_dd)

        self.lbl_dms = QLineEdit()
        self.lbl_dms.setReadOnly(True)
        self.lbl_dms.setStyleSheet("background: #f8f8f8;")
        self.lbl_dms.setFont(mono)
        formats_layout.addRow("DMS:", self.lbl_dms)

        self.lbl_utm = QLineEdit()
        self.lbl_utm.setReadOnly(True)
        self.lbl_utm.setStyleSheet("background: #f8f8f8;")
        self.lbl_utm.setFont(mono)
        formats_layout.addRow("UTM:", self.lbl_utm)

        layout.addWidget(formats_group)

        # ---- Zoom al llegar ----
        zoom_group = QGroupBox("Zoom al llegar")
        zoom_layout = QHBoxLayout(zoom_group)
        zoom_layout.addWidget(QLabel("Escala:"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems([
            "Sin zoom (solo centrar)",
            "1:500", "1:1,000", "1:2,500",
            "1:5,000", "1:10,000", "1:25,000", "1:50,000",
        ])
        self.zoom_combo.setCurrentIndex(4)
        zoom_layout.addWidget(self.zoom_combo, 1)
        layout.addWidget(zoom_group)

        layout.addStretch()

        # ---- Conexiones ----
        self.paste_btn.clicked.connect(self._open_paste_dialog)
        self.format_group.idClicked.connect(self._on_format_changed)
        self.go_btn.clicked.connect(self._on_go_clicked)
        self.bookmark_current_btn.clicked.connect(self._on_bookmark_current)

        # Conectar cambios en cada widget de entrada
        for widget in [self.dd_widget, self.dms_widget,
                       self.utm_widget, self.mgrs_widget]:
            widget.coordinatesChanged.connect(self._on_coord_changed)
            widget.submitRequested.connect(self._on_go_clicked)

        # Trigger inicial
        QTimer.singleShot(100, self._on_coord_changed)

        return w

    def _on_format_changed(self, format_id):
        """Cambio de formato: convertir el valor actual al nuevo widget."""
        old_format = self._current_format
        self._current_format = format_id

        # Tomar coordenadas del formato anterior
        old_widget = self.input_stack.widget(old_format)
        coords = old_widget.get_coordinates()

        # Cambiar al nuevo
        self.input_stack.setCurrentIndex(format_id)

        # Si las coordenadas eran válidas, transferirlas
        if coords:
            lat, lon, _ = coords
            new_widget = self.input_stack.widget(format_id)
            new_widget.blockSignals(True)
            try:
                new_widget.set_coordinates(lat, lon)
            finally:
                new_widget.blockSignals(False)

        self._on_coord_changed()

    def _on_coord_changed(self):
        """Actualiza status y equivalencias."""
        current = self.input_stack.currentWidget()
        coords = current.get_coordinates() if current else None

        if coords is None:
            self.coord_status.setText(
                "<span style='color: #c0392b;'>⚠ Coordenadas inválidas</span>"
            )
            self.lbl_dd.setText("")
            self.lbl_dms.setText("")
            self.lbl_utm.setText("")
            self.go_btn.setEnabled(False)
            return

        lat, lon, label = coords
        self.coord_status.setText(
            f"<span style='color: #27ae60;'>✓ Coordenada válida</span>"
        )
        self.lbl_dd.setText(format_dd(lat, lon))
        self.lbl_dms.setText(format_dms(lat, lon))
        try:
            self.lbl_utm.setText(format_utm(lat, lon))
        except Exception:
            self.lbl_utm.setText("(fuera de rango)")
        self.go_btn.setEnabled(True)

    def _on_go_clicked(self):
        current = self.input_stack.currentWidget()
        coords = current.get_coordinates() if current else None
        if coords:
            lat, lon, label = coords
            self.goToRequested.emit(lat, lon, label)

    def _on_bookmark_current(self):
        current = self.input_stack.currentWidget()
        coords = current.get_coordinates() if current else None
        if not coords:
            QMessageBox.information(
                self, "Sin coordenada",
                "Ingresa una coordenada válida antes de guardar."
            )
            return
        lat, lon, label = coords
        name, ok = QInputDialog.getText(
            self, "Nuevo bookmark", "Nombre del lugar:"
        )
        if ok and name.strip():
            self.bookmarkAdd.emit(name.strip(), lat, lon, label)

    def _open_paste_dialog(self):
        """Abre el diálogo modal de 'Pegar y detectar'."""
        dlg = PasteDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.parsed is not None:
            lat = dlg.parsed['lat']
            lon = dlg.parsed['lon']
            fmt = dlg.parsed['format']

            # Detectar el formato detectado y seleccionar el tab correspondiente
            format_map = {
                FORMAT_DD: FMT_DD,
                FORMAT_DMS: FMT_DMS,
                FORMAT_UTM: FMT_UTM,
                FORMAT_MGRS: FMT_MGRS,
            }
            target_fmt = format_map.get(fmt, FMT_DD)

            # Activar el botón del formato detectado
            self.format_buttons[target_fmt].setChecked(True)
            self._current_format = target_fmt
            self.input_stack.setCurrentIndex(target_fmt)

            # Llenar el widget correspondiente
            target_widget = self.input_stack.widget(target_fmt)
            target_widget.set_coordinates(lat, lon)

            self._on_coord_changed()

    def _refresh_utm_detection(self):
        """Detecta zona UTM del proyecto y actualiza el widget UTM."""
        try:
            zone, band, desc = get_project_utm_info()
            if zone is not None:
                self.utm_widget.apply_crs_detection(zone, band)
                self.utm_widget.set_detection_info(
                    f"<small><b>Auto-detectado:</b> Zona {zone}{band} "
                    f"<i>(desde CRS del proyecto)</i></small>"
                )
                # También para MGRS
                self.mgrs_widget.zone_spin.setValue(zone)
                if band:
                    idx = self.mgrs_widget.band_combo.findData(band)
                    if idx >= 0:
                        self.mgrs_widget.band_combo.setCurrentIndex(idx)
            else:
                self.utm_widget.set_detection_info(
                    f"<small><i>{desc}. Usando default Zona 19L (Madre de Dios).</i></small>"
                )
        except Exception as e:
            self.utm_widget.set_detection_info(
                f"<small><i>No se pudo detectar CRS: {e}</i></small>"
            )

    def get_zoom_scale(self):
        scales = [None, 500, 1000, 2500, 5000, 10000, 25000, 50000]
        idx = self.zoom_combo.currentIndex()
        if 0 <= idx < len(scales):
            return scales[idx]
        return None

    def focus_coord_input(self):
        self.tabs.setCurrentIndex(0)
        # Enfocar el primer campo del widget activo
        current = self.input_stack.currentWidget()
        if current:
            # Buscar el primer QLineEdit/QDoubleSpinBox y enfocarlo
            for attr_name in ['lat_edit', 'lat_deg', 'easting_spin', 'east_edit']:
                if hasattr(current, attr_name):
                    w = getattr(current, attr_name)
                    w.setFocus()
                    if hasattr(w, 'selectAll'):
                        w.selectAll()
                    break

    def notify_crs_changed(self):
        """Llamado desde el plugin principal cuando cambia el CRS del proyecto."""
        self._refresh_utm_detection()

    # ----------------------------------------------------------------
    # Tab: Buscar (sin cambios desde v1.0)
    # ----------------------------------------------------------------

    def _build_search_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 6, 6, 6)

        info = QLabel(
            "<b>Búsqueda por nombre</b> (vía OpenStreetMap)<br>"
            "<small>Ej: 'Puerto Maldonado', 'Reserva Tambopata'</small>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nombre del lugar a buscar...")
        self.search_input.setMinimumHeight(32)
        search_row.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("🔍")
        self.search_btn.setMinimumHeight(32)
        self.search_btn.setMaximumWidth(44)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white;
                border: none; border-radius: 4px; font-size: 14pt;
            }
            QPushButton:hover { background-color: #3498db; }
        """)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        country_row = QHBoxLayout()
        country_row.addWidget(QLabel("País:"))
        self.country_combo = QComboBox()
        self.country_combo.addItem("Perú", "pe")
        self.country_combo.addItem("Bolivia", "bo")
        self.country_combo.addItem("Brasil", "br")
        self.country_combo.addItem("Colombia", "co")
        self.country_combo.addItem("Ecuador", "ec")
        self.country_combo.addItem("Chile", "cl")
        self.country_combo.addItem("Todo el mundo", "")
        country_row.addWidget(self.country_combo, 1)
        layout.addLayout(country_row)

        self.search_status = QLabel("")
        self.search_status.setStyleSheet("color: #555; font-size: 10pt;")
        layout.addWidget(self.search_status)

        self.search_results = QListWidget()
        self.search_results.setMinimumHeight(200)
        self.search_results.setStyleSheet("""
            QListWidget::item { padding: 6px; }
            QListWidget::item:hover { background-color: #ecf0f1; }
        """)
        layout.addWidget(self.search_results, 1)

        action_row = QHBoxLayout()
        self.search_goto_btn = QPushButton("▶  Ir al resultado seleccionado")
        self.search_goto_btn.setMinimumHeight(32)
        self.search_goto_btn.setEnabled(False)
        self.search_goto_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 4px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        action_row.addWidget(self.search_goto_btn)

        self.search_bookmark_btn = QPushButton("⭐")
        self.search_bookmark_btn.setToolTip("Guardar como bookmark")
        self.search_bookmark_btn.setMinimumHeight(32)
        self.search_bookmark_btn.setMaximumWidth(40)
        self.search_bookmark_btn.setEnabled(False)
        self.search_bookmark_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12; color: white;
                border: none; border-radius: 4px; font-size: 14pt;
            }
            QPushButton:hover { background-color: #e67e22; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        action_row.addWidget(self.search_bookmark_btn)
        layout.addLayout(action_row)

        self.search_btn.clicked.connect(self._on_search_clicked)
        self.search_input.returnPressed.connect(self._on_search_clicked)
        self.search_results.itemSelectionChanged.connect(self._on_search_selection_changed)
        self.search_results.itemDoubleClicked.connect(lambda _: self._on_search_goto())
        self.search_goto_btn.clicked.connect(self._on_search_goto)
        self.search_bookmark_btn.clicked.connect(self._on_search_bookmark)

        return w

    def _on_search_clicked(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self.search_status.setText("<i>Buscando...</i>")
        self.search_results.clear()
        self.searchRequested.emit(query)

    def set_search_results(self, results):
        self.search_results.clear()
        if not results:
            self.search_status.setText(
                "<span style='color: #c0392b;'>Sin resultados</span>"
            )
            return
        self.search_status.setText(
            f"<span style='color: #27ae60;'>{len(results)} resultado(s)</span>"
        )
        for r in results:
            item = QListWidgetItem()
            text = r['name']
            if len(text) > 80:
                text = text[:77] + "..."
            type_str = r.get('type', '')
            if type_str:
                text = f"[{type_str}] {text}"
            item.setText(text)
            item.setData(Qt.UserRole, r)
            item.setToolTip(r['name'])
            self.search_results.addItem(item)

    def set_search_error(self, msg):
        self.search_status.setText(
            f"<span style='color: #c0392b;'>⚠ {msg}</span>"
        )

    def _on_search_selection_changed(self):
        has_sel = self.search_results.currentItem() is not None
        self.search_goto_btn.setEnabled(has_sel)
        self.search_bookmark_btn.setEnabled(has_sel)

    def _on_search_goto(self):
        item = self.search_results.currentItem()
        if item is None:
            return
        r = item.data(Qt.UserRole)
        self.goToRequested.emit(r['lat'], r['lon'], r['name'][:100])

    def _on_search_bookmark(self):
        item = self.search_results.currentItem()
        if item is None:
            return
        r = item.data(Qt.UserRole)
        suggested = r['name'].split(',')[0]
        name, ok = QInputDialog.getText(
            self, "Nuevo bookmark", "Nombre:", text=suggested
        )
        if ok and name.strip():
            self.bookmarkAdd.emit(name.strip(), r['lat'], r['lon'], r['name'][:200])

    def get_country_code(self):
        return self.country_combo.currentData()

    # ----------------------------------------------------------------
    # Tab: Bookmarks (sin cambios desde v1.0)
    # ----------------------------------------------------------------

    def _build_bookmarks_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 6, 6, 6)

        info = QLabel(
            "<b>Puntos frecuentes</b> guardados.<br>"
            "<small>Persisten entre sesiones de QGIS.</small>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.bookmarks_list = QListWidget()
        self.bookmarks_list.setStyleSheet("""
            QListWidget::item { padding: 8px; border-bottom: 1px solid #eee; }
            QListWidget::item:hover { background-color: #ecf0f1; }
        """)
        layout.addWidget(self.bookmarks_list, 1)

        btn_row = QHBoxLayout()
        self.bookmark_goto_btn = QPushButton("▶  Ir")
        self.bookmark_goto_btn.setMinimumHeight(32)
        self.bookmark_goto_btn.setEnabled(False)
        self.bookmark_goto_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white; font-weight: bold;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)

        self.bookmark_remove_btn = QPushButton("🗑  Eliminar")
        self.bookmark_remove_btn.setMinimumHeight(32)
        self.bookmark_remove_btn.setEnabled(False)
        self.bookmark_remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b; color: white;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)

        btn_row.addWidget(self.bookmark_goto_btn)
        btn_row.addWidget(self.bookmark_remove_btn)
        layout.addLayout(btn_row)

        self.bookmarks_list.itemSelectionChanged.connect(self._on_bookmark_selection)
        self.bookmarks_list.itemDoubleClicked.connect(lambda _: self._on_bookmark_goto())
        self.bookmark_goto_btn.clicked.connect(self._on_bookmark_goto)
        self.bookmark_remove_btn.clicked.connect(self._on_bookmark_remove)

        return w

    def set_bookmarks(self, bookmarks):
        self.bookmarks_list.clear()
        for i, b in enumerate(bookmarks):
            item = QListWidgetItem()
            text = f"⭐  {b['name']}\n     {format_dd(b['lat'], b['lon'])}"
            if b.get('note'):
                text += f"\n     {b['note'][:60]}"
            item.setText(text)
            item.setData(Qt.UserRole, i)
            self.bookmarks_list.addItem(item)

    def _on_bookmark_selection(self):
        has_sel = self.bookmarks_list.currentItem() is not None
        self.bookmark_goto_btn.setEnabled(has_sel)
        self.bookmark_remove_btn.setEnabled(has_sel)

    def _on_bookmark_goto(self):
        item = self.bookmarks_list.currentItem()
        if item is None:
            return
        self.bookmarkGoTo.emit(item.data(Qt.UserRole))

    def _on_bookmark_remove(self):
        item = self.bookmarks_list.currentItem()
        if item is None:
            return
        reply = QMessageBox.question(
            self, "Confirmar", "¿Eliminar este bookmark?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.bookmarkRemove.emit(item.data(Qt.UserRole))

    # ----------------------------------------------------------------
    # Tab: Markers (sin cambios desde v1.0)
    # ----------------------------------------------------------------

    def _build_markers_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 6, 6, 6)

        info = QLabel(
            "<b>Markers visitados</b> en esta sesión.<br>"
            "<small>Son gráficos efímeros (no aparecen en la TOC).</small>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Botón "Pegar múltiples" destacado
        self.multi_paste_btn = QPushButton("📋  Pegar múltiples coordenadas (Excel/WhatsApp)")
        self.multi_paste_btn.setMinimumHeight(34)
        self.multi_paste_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad; color: white; font-weight: bold;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #9b59b6; }
        """)
        self.multi_paste_btn.setToolTip(
            "Pegue varios vértices desde Excel, WhatsApp o texto libre para crear "
            "múltiples markers de una sola vez"
        )
        layout.addWidget(self.multi_paste_btn)

        self.markers_list = QListWidget()
        self.markers_list.setStyleSheet("""
            QListWidget::item { padding: 6px; border-bottom: 1px solid #eee; }
            QListWidget::item:hover { background-color: #ecf0f1; }
        """)
        layout.addWidget(self.markers_list, 1)

        btn_row1 = QHBoxLayout()
        self.marker_goto_btn = QPushButton("▶  Re-navegar")
        self.marker_goto_btn.setMinimumHeight(32)
        self.marker_goto_btn.setEnabled(False)
        self.marker_goto_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white; font-weight: bold;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        btn_row1.addWidget(self.marker_goto_btn)

        self.marker_remove_btn = QPushButton("🗑")
        self.marker_remove_btn.setToolTip("Eliminar marker seleccionado")
        self.marker_remove_btn.setMinimumHeight(32)
        self.marker_remove_btn.setMaximumWidth(40)
        self.marker_remove_btn.setEnabled(False)
        self.marker_remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b; color: white;
                border: none; border-radius: 4px; font-size: 13pt;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        btn_row1.addWidget(self.marker_remove_btn)
        layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self.clear_all_btn = QPushButton("🧹  Limpiar todos")
        self.clear_all_btn.setMinimumHeight(30)
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        btn_row2.addWidget(self.clear_all_btn)

        self.to_layer_btn = QPushButton("📁  Convertir a capa…")
        self.to_layer_btn.setMinimumHeight(30)
        self.to_layer_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; font-weight: bold;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        btn_row2.addWidget(self.to_layer_btn)
        layout.addLayout(btn_row2)

        self.markers_list.itemSelectionChanged.connect(self._on_marker_selection)
        self.markers_list.itemDoubleClicked.connect(lambda _: self._on_marker_goto())
        self.marker_goto_btn.clicked.connect(self._on_marker_goto)
        self.marker_remove_btn.clicked.connect(self._on_marker_remove)
        self.clear_all_btn.clicked.connect(self._on_clear_all)
        self.to_layer_btn.clicked.connect(self._on_to_layer)
        self.multi_paste_btn.clicked.connect(self._open_multi_paste)

        return w

    def _open_multi_paste(self):
        """Abre el diálogo de pegado múltiple."""
        # Obtener zona/banda detectada para defaults
        zone, band, _ = get_project_utm_info()
        if zone is None:
            zone = 19
            band = 'L'

        dlg = MultiPasteDialog(
            default_utm_zone=zone,
            default_utm_band=band,
            parent=self
        )
        if dlg.exec_() == QDialog.Accepted:
            results = dlg.get_results()
            if results:
                self.multiCoordsRequested.emit(results)

    def set_markers(self, markers):
        self.markers_list.clear()
        for i, m in enumerate(markers):
            item = QListWidgetItem()
            label = m.get('label', '') or m.get('original', '') or 'Sin etiqueta'
            text = f"#{m['number']}  {label[:50]}"
            text += f"\n    {format_dd(m['lat'], m['lon'])}"
            item.setText(text)
            item.setData(Qt.UserRole, i)
            self.markers_list.addItem(item)

    def _on_marker_selection(self):
        has_sel = self.markers_list.currentItem() is not None
        self.marker_goto_btn.setEnabled(has_sel)
        self.marker_remove_btn.setEnabled(has_sel)

    def _on_marker_goto(self):
        item = self.markers_list.currentItem()
        if item is None:
            return
        self.markerGoTo.emit(item.data(Qt.UserRole))

    def _on_marker_remove(self):
        item = self.markers_list.currentItem()
        if item is None:
            return
        self.markerRemove.emit(item.data(Qt.UserRole))

    def _on_clear_all(self):
        if self.markers_list.count() == 0:
            return
        reply = QMessageBox.question(
            self, "Confirmar",
            f"¿Eliminar los {self.markers_list.count()} markers?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.markersClearAll.emit()

    def _on_to_layer(self):
        if self.markers_list.count() == 0:
            QMessageBox.information(
                self, "Sin markers",
                "Aún no hay markers para convertir a capa."
            )
            return
        reply = QMessageBox.question(
            self, "Convertir a capa",
            "<b>¿Qué tipo de capa quieres crear?</b><br><br>"
            "<b>Sí</b> = Capa temporal en memoria<br>"
            "<b>No</b> = GeoPackage permanente (recomendado)",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        if reply == QMessageBox.Cancel:
            return
        if reply == QMessageBox.Yes:
            self.markersToLayer.emit(True, "")
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Guardar markers como GeoPackage",
                "goto_markers.gpkg",
                "GeoPackage (*.gpkg)"
            )
            if file_path:
                if not file_path.lower().endswith('.gpkg'):
                    file_path += '.gpkg'
                self.markersToLayer.emit(False, file_path)
