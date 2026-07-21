# -*- coding: utf-8 -*-
"""
Diálogo de Table Style Manager.
Aplicar, copiar, pegar y guardar estilos de tablas en el compositor.
Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QLabel, QDialogButtonBox, QPushButton,
    QFrame, QMessageBox, QFileDialog, QSizePolicy,
    QTabWidget, QWidget, QColorDialog, QCheckBox,
    QDoubleSpinBox, QSpinBox, QGridLayout, QLineEdit
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont, QPalette

from .table_style_engine import (
    ESTILOS_PREDEFINIDOS, aplicar_estilo, capturar_estilo,
    guardar_estilo_json, cargar_estilo_json,
    get_tablas_en_layout, nombre_tabla,
)


class TableStyleDialog(QDialog):
    """Diálogo principal del Table Style Manager."""

    # Buffer de estilo copiado (clase compartida entre instancias)
    _estilo_copiado = None

    def __init__(self, layout, parent=None):
        super().__init__(parent)
        self.layout   = layout
        self._tablas  = get_tablas_en_layout(layout)
        self._estilo_personalizado = None  # siempre resetear al abrir
        self.setWindowTitle("YF · Table Style Manager")
        self.setMinimumWidth(480)
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(8)

        # ── Selector de layout (funcional) ──
        grp_lay = QGroupBox("Layout de destino")
        gl = QHBoxLayout(grp_lay)
        gl.addWidget(QLabel("Aplicar en:"))
        self.combo_layout = QComboBox()
        self.combo_layout.setToolTip(
            "<b>Layout de destino</b><br>Al cambiarlo se recargan sus "
            "tablas automáticamente.")
        self._cargar_layouts()
        gl.addWidget(self.combo_layout)
        main.addWidget(grp_lay)

        # Cabecera dinámica
        self.lbl_header = QLabel()
        self.lbl_header.setFrameStyle(QFrame.Shape.StyledPanel)
        self.lbl_header.setContentsMargins(8, 6, 8, 6)
        main.addWidget(self.lbl_header)

        # Selector de tabla destino (se puebla por _recargar_tablas)
        grp_tabla = QGroupBox("Tabla a estilizar")
        t_layout = QHBoxLayout(grp_tabla)
        t_layout.addWidget(QLabel("Tabla:"))
        self.combo_tabla = QComboBox()
        t_layout.addWidget(self.combo_tabla)
        main.addWidget(grp_tabla)

        self._recargar_tablas()
        self.combo_layout.currentIndexChanged.connect(self._on_layout_cambiado)

        # Tabs: Estilos predefinidos | Copiar/Pegar | Personalizar
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_predefinidos(), "⭐  Estilos predefinidos")
        self.tabs.addTab(self._tab_copiar_pegar(), "📋  Copiar / Pegar")
        self.tabs.addTab(self._tab_personalizar(), "🎨  Personalizar")
        main.addWidget(self.tabs)

        # Preview colores
        self.lbl_preview = QLabel()
        self.lbl_preview.setFixedHeight(32)
        self.lbl_preview.setFrameStyle(QFrame.Shape.StyledPanel)
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.lbl_preview)

        # Botones
        # Botón "Aplicar" que aplica el estilo directamente sin cerrar
        btn_row = QHBoxLayout()
        self.btn_aplicar = QPushButton("✅  Aplicar estilo")
        self.btn_aplicar.setStyleSheet(
            "QPushButton { background:#1a6e2e; color:white; "
            "font-weight:bold; padding:6px 12px; border-radius:4px; }"
            "QPushButton:hover { background:#228b3a; }"
        )
        self.btn_aplicar.clicked.connect(self._aplicar_ahora)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_aplicar)
        btn_row.addWidget(btn_cerrar)
        main.addLayout(btn_row)

        self._actualizar_preview()

    # ─────────────────────────────────────────────────────────────────
    # Tab 1 — Estilos predefinidos
    # ─────────────────────────────────────────────────────────────────

    def _cargar_layouts(self):
        from qgis.core import QgsProject, QgsPrintLayout
        self.combo_layout.clear()
        layouts = [l for l in  # noqa: E741
                   QgsProject.instance().layoutManager().layouts()
                   if isinstance(l, QgsPrintLayout)]
        # Guardar el NOMBRE: sip degrada QgsPrintLayout a QGraphicsScene
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
        self._recargar_tablas()

    def _recargar_tablas(self):
        """Recarga las tablas del layout activo. userData = ÍNDICE en
        self._tablas (guardar el objeto degrada el tipo vía sip)."""
        self._tablas = get_tablas_en_layout(self.layout)
        self.combo_tabla.clear()
        for i, tabla in enumerate(self._tablas):
            self.combo_tabla.addItem(nombre_tabla(tabla), i)
        hay = bool(self._tablas)
        self.combo_tabla.setEnabled(hay)
        if hasattr(self, 'btn_aplicar'):
            self.btn_aplicar.setEnabled(hay)
        self.lbl_header.setText(
            "<b>Layout:</b> {}<br><b>Tablas encontradas:</b> {}{}".format(
                self.layout.name(), len(self._tablas),
                "" if hay else " — ⚠ agrega una con "
                "Añadir elemento → Tabla de atributos"))

    def _tab_predefinidos(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("Selecciona un estilo predefinido:"))
        self.combo_estilo = QComboBox()
        for key, meta in ESTILOS_PREDEFINIDOS.items():
            self.combo_estilo.addItem(
                f"{meta['nombre']}  —  {meta['descripcion']}", key
            )
        self.combo_estilo.currentIndexChanged.connect(self._actualizar_preview)
        layout.addWidget(self.combo_estilo)

        # Botones de importar/exportar JSON
        row = QHBoxLayout()
        btn_export = QPushButton("💾  Exportar estilo como JSON")
        btn_export.clicked.connect(self._exportar_json)
        btn_import = QPushButton("📂  Importar estilo JSON")
        btn_import.clicked.connect(self._importar_json)
        row.addWidget(btn_export)
        row.addWidget(btn_import)
        layout.addLayout(row)
        layout.addStretch()
        return w

    # ─────────────────────────────────────────────────────────────────
    # Tab 2 — Copiar / Pegar
    # ─────────────────────────────────────────────────────────────────

    def _tab_copiar_pegar(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        # ── Copiar ────────────────────────────────────────────────────
        grp_copy = QGroupBox("1. Copiar estilo de una tabla")
        copy_layout = QVBoxLayout(grp_copy)
        copy_layout.addWidget(QLabel("Selecciona la tabla con el estilo que quieres copiar:"))
        self.combo_origen = QComboBox()
        for tabla in self._tablas:
            self.combo_origen.addItem(nombre_tabla(tabla), tabla)
        copy_layout.addWidget(self.combo_origen)

        btn_copiar = QPushButton("📋  Copiar estilo")
        btn_copiar.setStyleSheet(
            "QPushButton{background:#1565c0;color:white;font-weight:bold;"
            "padding:6px;border-radius:4px;}"
            "QPushButton:hover{background:#1976d2;}"
        )
        btn_copiar.clicked.connect(self._copiar_estilo)
        copy_layout.addWidget(btn_copiar)

        # Estado visual del portapapeles
        self.lbl_clipboard = QLabel("📋 Portapapeles: vacío")
        self.lbl_clipboard.setStyleSheet(
            "color:#888;font-size:11px;padding:4px;"
            "border:1px solid #ddd;border-radius:3px;"
        )
        copy_layout.addWidget(self.lbl_clipboard)
        if TableStyleDialog._estilo_copiado:
            self._actualizar_lbl_clipboard()
        layout.addWidget(grp_copy)

        # ── Pegar ─────────────────────────────────────────────────────
        grp_paste = QGroupBox("2. Pegar estilo en una tabla")
        paste_layout = QVBoxLayout(grp_paste)
        paste_layout.addWidget(QLabel("La tabla destino es la seleccionada en la parte superior."))

        btn_pegar = QPushButton("📌  Pegar estilo copiado")
        btn_pegar.setStyleSheet(
            "QPushButton{background:#2e7d32;color:white;font-weight:bold;"
            "padding:6px;border-radius:4px;}"
            "QPushButton:hover{background:#388e3c;}"
        )
        btn_pegar.clicked.connect(self._pegar_estilo)
        paste_layout.addWidget(btn_pegar)
        layout.addWidget(grp_paste)

        # ── Guardar como JSON ─────────────────────────────────────────
        grp_save = QGroupBox("3. Guardar estilo copiado como archivo")
        save_layout = QHBoxLayout(grp_save)
        btn_guardar = QPushButton("💾  Exportar como JSON")
        btn_guardar.clicked.connect(self._guardar_preset)
        save_layout.addWidget(btn_guardar)
        layout.addWidget(grp_save)

        layout.addStretch()
        return w

    def _actualizar_lbl_clipboard(self):
        """Actualiza el label de estado del portapapeles."""
        if TableStyleDialog._estilo_copiado:
            nombre = TableStyleDialog._estilo_copiado.get("nombre", "sin nombre")
            bg = TableStyleDialog._estilo_copiado.get("header_bg", "")
            self.lbl_clipboard.setText(f"✅ Portapapeles: '{nombre}'  {bg}")
            self.lbl_clipboard.setStyleSheet(
                "color:#1a6e2e;font-size:11px;padding:4px;"
                "border:1px solid #1a6e2e;border-radius:3px;font-weight:bold;"
            )
        else:
            self.lbl_clipboard.setText("📋 Portapapeles: vacío — copia primero un estilo")
            self.lbl_clipboard.setStyleSheet(
                "color:#888;font-size:11px;padding:4px;"
                "border:1px solid #ddd;border-radius:3px;"
            )

    # ─────────────────────────────────────────────────────────────────
    # Tab 3 — Personalizar
    # ─────────────────────────────────────────────────────────────────

    def _tab_personalizar(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        grid = QGridLayout()

        # Color encabezado
        grid.addWidget(QLabel("Color encabezado:"), 0, 0)
        self.btn_color_enc = QPushButton()
        self._set_btn_color(self.btn_color_enc, "#2c5f8a")
        self.btn_color_enc.clicked.connect(
            lambda: self._elegir_color(self.btn_color_enc))
        grid.addWidget(self.btn_color_enc, 0, 1)

        # Color texto encabezado
        grid.addWidget(QLabel("Texto encabezado:"), 1, 0)
        self.btn_color_enc_txt = QPushButton()
        self._set_btn_color(self.btn_color_enc_txt, "#ffffff")
        self.btn_color_enc_txt.clicked.connect(
            lambda: self._elegir_color(self.btn_color_enc_txt))
        grid.addWidget(self.btn_color_enc_txt, 1, 1)

        # Tamaño fuente encabezado
        grid.addWidget(QLabel("Tamaño fuente enc.:"), 2, 0)
        self.spin_size_enc = QSpinBox()
        self.spin_size_enc.setRange(4, 24)
        self.spin_size_enc.setValue(9)
        grid.addWidget(self.spin_size_enc, 2, 1)

        # Color celdas zebra
        grid.addWidget(QLabel("Color zebra (filas):"), 3, 0)
        self.btn_color_zebra = QPushButton()
        self._set_btn_color(self.btn_color_zebra, "#e8f0f7")
        self.btn_color_zebra.clicked.connect(
            lambda: self._elegir_color(self.btn_color_zebra))
        grid.addWidget(self.btn_color_zebra, 3, 1)

        # Zebra activo
        self.chk_zebra = QCheckBox("Activar filas zebra")
        self.chk_zebra.setChecked(True)
        grid.addWidget(self.chk_zebra, 4, 0, 1, 2)

        # Tamaño fuente celdas
        grid.addWidget(QLabel("Tamaño fuente celdas:"), 5, 0)
        self.spin_size_cel = QSpinBox()
        self.spin_size_cel.setRange(4, 24)
        self.spin_size_cel.setValue(8)
        grid.addWidget(self.spin_size_cel, 5, 1)

        # Margen celda
        grid.addWidget(QLabel("Margen celda (mm):"), 6, 0)
        self.spin_margen = QDoubleSpinBox()
        self.spin_margen.setRange(0, 10)
        self.spin_margen.setDecimals(1)
        self.spin_margen.setValue(1.0)
        grid.addWidget(self.spin_margen, 6, 1)

        layout.addLayout(grid)
        layout.addStretch()
        return w

    # ─────────────────────────────────────────────────────────────────
    # Helpers de UI
    # ─────────────────────────────────────────────────────────────────

    def _set_btn_color(self, btn, hex_color):
        btn.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #aaa;"
        )
        btn.setText(hex_color)
        btn.setProperty("color", hex_color)

    def _elegir_color(self, btn):
        color = QColorDialog.getColor(
            QColor(btn.property("color") or "#ffffff"),
            self, "Seleccionar color"
        )
        if color.isValid():
            self._set_btn_color(btn, color.name())
            self._actualizar_preview()

    def _actualizar_preview(self):
        """Actualiza la barra de preview con los colores del estilo activo."""
        estilo = self._get_estilo_activo()
        if not estilo:
            return
        # Estructura plana: header_bg, header_fg, odd_bg
        bg_enc = estilo.get("header_bg", "#333333")
        fg_enc = estilo.get("header_fg", "#ffffff")
        bg_cel = estilo.get("odd_bg", "#ffffff")
        self.lbl_preview.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {bg_enc}, stop:0.4 {bg_enc}, "
            f"stop:0.41 {bg_cel}, stop:1 {bg_cel});"
            f"color: {fg_enc}; font-weight: bold; font-size: 11px;"
        )
        self.lbl_preview.setText(
            f"Encabezado: {bg_enc}  |  Celda: {bg_cel}"
        )

    def _get_estilo_activo(self):
        """Retorna el estilo del tab activo — siempre la selección actual."""
        tab = self.tabs.currentIndex() if hasattr(self, 'tabs') else 0

        if tab == 0:  # Predefinidos
            key = self.combo_estilo.currentData()
            return ESTILOS_PREDEFINIDOS.get(key)

        elif tab == 1:  # Copiar/Pegar — usa el estilo copiado
            if TableStyleDialog._estilo_copiado:
                return TableStyleDialog._estilo_copiado
            # Si no hay nada copiado, avisar
            return None

        elif tab == 2:  # Personalizado — construir desde controles
            return self._build_estilo_personalizado()

        return None

    def _build_estilo_personalizado(self):
        """Construye un dict de estilo compatible con aplicar_estilo()."""
        color_enc     = self.btn_color_enc.property("color") or "#2c5f8a"
        color_enc_txt = self.btn_color_enc_txt.property("color") or "#ffffff"
        color_zebra   = self.btn_color_zebra.property("color") or "#e8f0f7"
        size_enc      = self.spin_size_enc.value()
        size_cel      = self.spin_size_cel.value()
        zebra_activo  = self.chk_zebra.isChecked()
        margen        = self.spin_margen.value()

        return {
            "nombre":       "Personalizado",
            "descripcion":  "Estilo personalizado",
            "header_bg":    color_enc,
            "header_fg":    color_enc_txt,
            "header_size":  size_enc,
            "header_bold":  True,
            "header_font":  "Arial",
            "content_fg":   "#000000",
            "content_size": size_cel,
            "content_bold": False,
            "content_font": "Arial",
            "even_bg":      color_zebra if zebra_activo else "#ffffff",
            "odd_bg":       "#ffffff",
            "grid_color":   "#666666",
            "grid_width":   0.3,
            "cell_margin":  margen,
        }

    # ─────────────────────────────────────────────────────────────────
    # Acciones
    # ─────────────────────────────────────────────────────────────────

    def _copiar_estilo(self):
        tabla = self.combo_origen.currentData()
        if tabla is None:
            return
        estilo = capturar_estilo(tabla)
        if estilo:
            TableStyleDialog._estilo_copiado = estilo
            self.lbl_clipboard.setText(
                f"✅ Portapapeles: '{estilo.get('nombre','copiado')}'"
            )
            self.lbl_clipboard.setStyleSheet("color: #1a6e2e; font-size: 11px;")
        else:
            QMessageBox.warning(self, "Error",
                "No se pudo capturar el estilo de la tabla.")

    def _pegar_estilo(self):
        if not TableStyleDialog._estilo_copiado:
            QMessageBox.warning(self, "YF · Pegar Estilo",
                "El portapapeles está vacío.\n\nPrimero copia el estilo de una tabla usando el botón Copiar estilo.")
            return
        tabla = self.combo_tabla.currentData()
        if tabla is None:
            QMessageBox.warning(self, "YF · Pegar Estilo",
                "Selecciona una tabla destino en la parte superior del diálogo.")
            return
        from .table_style_engine import aplicar_estilo  # noqa: F811
        aplicar_estilo(tabla, TableStyleDialog._estilo_copiado)
        self.layout.refresh()
        self.btn_aplicar.setText("✅  ¡Pegado!")
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_aplicar.setText("✅  Aplicar estilo"))

    def _guardar_preset(self):
        nombre = self.txt_nombre_estilo.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Sin nombre", "Escribe un nombre para el estilo.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar estilo", f"{nombre}.json",
            "JSON (*.json)"
        )
        if not path:
            return
        tabla = self.combo_origen.currentData()
        estilo = capturar_estilo(tabla) if tabla else self._build_estilo_personalizado()
        if estilo:
            estilo["nombre"] = nombre
            guardar_estilo_json(estilo, path)
            QMessageBox.information(self, "YF · Table Style",
                f"Estilo guardado en:\n{path}")

    def _exportar_json(self):
        key = self.combo_estilo.currentData()
        estilo = ESTILOS_PREDEFINIDOS.get(key)
        if not estilo:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar estilo", f"{key}.json", "JSON (*.json)"
        )
        if path:
            guardar_estilo_json(estilo, path)

    def _importar_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar estilo JSON", "", "JSON (*.json)"
        )
        if path:
            try:
                self._estilo_personalizado = cargar_estilo_json(path)
                QMessageBox.information(self, "YF · Table Style",
                    f"Estilo importado: '{self._estilo_personalizado.get('nombre','?')}'")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo leer el JSON:\n{e}")

    # ─────────────────────────────────────────────────────────────────

    def _aplicar_ahora(self):
        """Aplica el estilo directamente desde el botón."""
        print("=== YF Table Style: _aplicar_ahora EJECUTADO ===")
        try:
            from .table_style_engine import aplicar_estilo  # noqa: F811
            tabla  = self.get_tabla_destino()
            estilo = self.get_estilo_final()
            print(f"  tabla: {tabla}")
            print(f"  estilo: {estilo.get('nombre') if estilo else None}")

            if tabla is None:
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.warning(self, "YF · Table Style", "No hay tabla seleccionada.")
                return
            if estilo is None:
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.warning(self, "YF · Table Style", "No se pudo obtener el estilo.")
                return

            aplicar_estilo(tabla, estilo)
            # Refrescar layout
            try:
                self.layout.refresh()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)

            self.btn_aplicar.setText("✅  ¡Aplicado!")
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_aplicar.setText("✅  Aplicar estilo"))

        except Exception as e:
            from ...core.logger import log_error
            log_error(f"_aplicar_ahora: {e}")
            import traceback; traceback.print_exc()

    # Getters
    # ─────────────────────────────────────────────────────────────────

    def get_tabla_destino(self):
        idx = self.combo_tabla.currentData()
        if idx is None or not (0 <= int(idx) < len(self._tablas)):
            return None
        return self._tablas[int(idx)]

    def get_estilo_final(self):
        """Retorna el estilo del tab activo — siempre fresco, sin caché."""
        return self._get_estilo_activo()
