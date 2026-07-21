# -*- coding: utf-8 -*-
"""
Diálogo del Generador de Cajetín — modelo único "Predio Agrícola".
Los campos vacíos se completan con expresiones dinámicas de QGIS
(fecha, datum, proyección, unidades, centroide del mapa).
Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QLabel, QLineEdit,
    QDialogButtonBox, QFrame, QGridLayout, QComboBox,
    QDoubleSpinBox, QPlainTextEdit
)

from .title_block_engine import PLANTILLAS_CAJETIN, get_variables_proyecto

FUENTE_DEFAULT = (
    "Datos de la Dirección Regional de Agricultura (predios 2021), "
    "información de IGN, MED, análisis histórico con imágenes de "
    "Google Earth Engine y Google Earth, GEOSERFOR (2026), GEOSERNANP."
)


class TitleBlockDialog(QDialog):
    """Configura y genera el cajetín Predio Agrícola."""

    def __init__(self, layout=None, parent=None):
        super().__init__(parent)
        self._layout_inicial = layout
        self._vars = get_variables_proyecto()
        self.setWindowTitle("YF · Generador de Cajetín — Predio Agrícola")
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(8)

        header = QLabel(
            "Cajetín modelo Predio Agrícola con textos dinámicos: los campos "
            "que dejes vacíos se completan automáticamente con datos del "
            "proyecto (fecha, datum, proyección, unidades, centroide)."
        )
        header.setWordWrap(True)
        header.setFrameStyle(QFrame.Shape.StyledPanel)
        header.setContentsMargins(8, 6, 8, 6)
        main.addWidget(header)

        # ── Layout de destino ──
        grp_lay = QGroupBox("Layout de destino")
        lay_grid = QGridLayout(grp_lay)
        lay_grid.addWidget(QLabel("Aplicar en:"), 0, 0)
        self.combo_layout = QComboBox()
        self.combo_layout.setToolTip(
            "<b>Layout de destino</b><br>Layout de impresión del proyecto "
            "donde se insertará el cajetín.")
        self._cargar_layouts()
        lay_grid.addWidget(self.combo_layout, 0, 1)
        main.addWidget(grp_lay)

        # ── Datos del cajetín ──
        grp = QGroupBox("Datos del cajetín")
        grid = QGridLayout(grp)
        grid.setSpacing(5)

        def field(row, label, placeholder, default="", tooltip=""):
            lab = QLabel(label)
            grid.addWidget(lab, row, 0)
            txt = QLineEdit()
            txt.setPlaceholderText(placeholder)
            if default:
                txt.setText(default)
            if tooltip:
                txt.setToolTip(tooltip)
                lab.setToolTip(tooltip)
            grid.addWidget(txt, row, 1)
            return txt

        self.txt_titulo = field(
            0, "Título del mapa:", "",
            "MAPA PERIMETRICO DEL PREDIO AGRICOLA",
            "<b>Título</b><br>Barra verde superior del cajetín.")
        self.txt_propietario = field(
            1, "Propietario:", "Ej: MARDONIO ATAO BENDEZU", "",
            "<b>Propietario</b><br>Nombres y apellidos del titular del predio.")
        self.txt_proyecto = field(
            2, "Proyecto:", "", "SANEAMIENTO FÍSICO",
            "<b>Proyecto</b><br>Tipo de trámite o proyecto "
            "(saneamiento físico, titulación, georreferenciación...).")
        self.txt_dni = field(
            3, "DNI:", "Ej: 44806432", "",
            "<b>DNI</b><br>Documento de identidad del propietario.")
        self.txt_parcela = field(
            4, "Nombre de la Parcela:", "Ej: FUNDO MATIAS", "",
            "<b>Parcela</b><br>Nombre del fundo o parcela.")
        self.txt_codigo = field(
            5, "Código del predio matriz:", "------", "",
            "<b>Código matriz</b><br>Vacío = '------' (sin código).")
        self.txt_partida = field(
            6, "Partida registral:", "no aplica", "",
            "<b>Partida</b><br>Vacío = 'no aplica'.")
        self.txt_area_matriz = field(
            7, "Área del predio matriz:", "ninguna", "",
            "<b>Área matriz</b><br>Vacío = 'ninguna'.")
        self.txt_elaborado = field(
            8, "Elaboración:", "", self._vars.get("elaborado", ""),
            "<b>Elaboración</b><br>Profesional responsable. Se toma de la "
            "variable de proyecto <i>tucsa_elaborado</i> si existe.")
        self.txt_mapa_num = field(
            9, "Mapa N°:", "01", "01",
            "<b>Mapa N°</b><br>Se muestra grande en el panel derecho: MAPA 01.")

        lab_f = QLabel("Fuente:")
        grid.addWidget(lab_f, 10, 0)
        self.txt_fuente = QPlainTextEdit()
        self.txt_fuente.setPlainText(FUENTE_DEFAULT)
        self.txt_fuente.setMaximumHeight(52)
        tt_f = ("<b>Fuente</b><br>Fila inferior a todo lo ancho. "
                "Cita las fuentes de datos del mapa.")
        self.txt_fuente.setToolTip(tt_f)
        lab_f.setToolTip(tt_f)
        grid.addWidget(self.txt_fuente, 10, 1)

        main.addWidget(grp)

        nota = QLabel(
            "Dinámicos automáticos: <b>Fecha</b> (hoy), <b>Datum</b>, "
            "<b>Proyección</b> y <b>Unidades</b> (CRS del proyecto), "
            "<b>Centroide X/Y</b> (centro del mapa principal). "
            "Se actualizan solos al mover el mapa o cambiar el CRS.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #666; font-size: 11px; padding: 2px 4px;")
        main.addWidget(nota)

        # ── Posición ──
        grp_pos = QGroupBox("Posición en el layout")
        pos = QGridLayout(grp_pos)

        pos.addWidget(QLabel("Posición:"), 0, 0)
        self.combo_pos = QComboBox()
        self.combo_pos.addItem("Inferior derecha — panel (como el plano)", "panel_br")
        self.combo_pos.addItem("Superior — ancho de página", "top_full")
        self.combo_pos.addItem("Inferior — ancho de página", "bottom_full")
        self.combo_pos.addItem("Personalizada (X, Y, ancho)", "custom")
        self.combo_pos.setToolTip(
            "<b>Posición</b><br>El modelo ocupa el ancho útil de la página "
            "(como cabecera o pie). En Personalizada defines X, Y y ancho.")
        self.combo_pos.currentIndexChanged.connect(self._on_pos_changed)
        pos.addWidget(self.combo_pos, 0, 1, 1, 3)

        pos.addWidget(QLabel("X (mm):"), 1, 0)
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setRange(0, 5000); self.spin_x.setEnabled(False)
        pos.addWidget(self.spin_x, 1, 1)

        pos.addWidget(QLabel("Y (mm):"), 1, 2)
        self.spin_y = QDoubleSpinBox()
        self.spin_y.setRange(0, 5000); self.spin_y.setEnabled(False)
        pos.addWidget(self.spin_y, 1, 3)

        pos.addWidget(QLabel("Ancho (mm):"), 2, 0)
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(80, 5000)
        self.spin_w.setValue(121.5)
        self.spin_w.setEnabled(False)
        pos.addWidget(self.spin_w, 2, 1)

        main.addWidget(grp_pos)

        # ── Botones ──
        btn_box = QDialogButtonBox()
        btn_box.addButton("Generar cajetín",
                          QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton("Cerrar",
                          QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        main.addWidget(btn_box)

    def _on_pos_changed(self, idx):
        custom = self.combo_pos.currentData() == "custom"
        self.spin_x.setEnabled(custom)
        self.spin_y.setEnabled(custom)
        self.spin_w.setEnabled(custom)

    # ─────────────────────────────────────────────────────────────────
    # Posición y ancho automáticos
    # ─────────────────────────────────────────────────────────────────

    MARGEN = 5.0

    def _cargar_layouts(self):
        from qgis.core import QgsProject, QgsPrintLayout
        self.combo_layout.clear()
        layouts = [l for l in  # noqa: E741
                   QgsProject.instance().layoutManager().layouts()
                   if isinstance(l, QgsPrintLayout)]
        for l in sorted(layouts, key=lambda x: x.name().lower()):  # noqa: E741
            self.combo_layout.addItem(l.name(), l.name())
        # Preseleccionar el layout con el que se abrió el diálogo
        if self._layout_inicial is not None:
            idx = self.combo_layout.findText(self._layout_inicial.name())
            if idx >= 0:
                self.combo_layout.setCurrentIndex(idx)

    def get_layout(self):
        """Layout elegido en el combo (autoritativo sobre el inicial).
        Se resuelve por NOMBRE via layoutManager: guardar el objeto como
        userData degrada QgsPrintLayout a QGraphicsScene (sip downcast)."""
        from qgis.core import QgsProject
        nombre = self.combo_layout.currentData()
        if nombre:
            lay = QgsProject.instance().layoutManager().layoutByName(nombre)
            if lay is not None:
                return lay
        return self._layout_inicial

    def _pagina(self):
        page = self.get_layout().pageCollection().page(0)
        return page.pageSize().width(), page.pageSize().height()

    def _calcular_geometria(self):
        plt = PLANTILLAS_CAJETIN["predio_agricola"]
        pw, ph = self._pagina()
        clave = self.combo_pos.currentData()
        if clave == "panel_br":
            # Panel derecho inferior, medidas del plano real (121.5 mm de
            # ancho + ~5 mm de Fuente debajo del marco)
            ancho = plt["ancho"]
            alto_total = plt["alto"] + 5.5
            return (pw - ancho - self.MARGEN,
                    ph - alto_total - self.MARGEN, ancho)
        alto = plt["alto"]
        if clave == "top_full":
            return self.MARGEN, self.MARGEN, pw - 2 * self.MARGEN
        if clave == "bottom_full":
            return self.MARGEN, ph - alto - self.MARGEN - 5.5, pw - 2 * self.MARGEN
        return self.spin_x.value(), self.spin_y.value(), self.spin_w.value()

    # ─────────────────────────────────────────────────────────────────
    # Getters (interfaz estable con los llamadores)
    # ─────────────────────────────────────────────────────────────────

    def get_plantilla(self):
        return "predio_agricola"

    def get_datos(self):
        _x, _y, ancho = self._calcular_geometria()
        return {
            "titulo":        self.txt_titulo.text().strip(),
            "propietario":   self.txt_propietario.text().strip(),
            "proyecto":      self.txt_proyecto.text().strip(),
            "dni":           self.txt_dni.text().strip(),
            "parcela":       self.txt_parcela.text().strip(),
            "codigo_matriz": self.txt_codigo.text().strip(),
            "partida":       self.txt_partida.text().strip(),
            "area_matriz":   self.txt_area_matriz.text().strip(),
            "elaborado":     self.txt_elaborado.text().strip(),
            "mapa_num":      self.txt_mapa_num.text().strip(),
            "fuente":        self.txt_fuente.toPlainText().strip(),
            "ancho_mm":      ancho,
        }

    def get_logo(self):
        return None   # el modelo lleva rosa náutica, no logo

    def get_posicion(self):
        x, y, _w = self._calcular_geometria()
        return x, y
