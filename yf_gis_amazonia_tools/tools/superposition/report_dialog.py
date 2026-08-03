# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Vista previa del informe con conclusión editable.

Flujo definido con el usuario:
  1. Se genera el HTML con una conclusión BORRADOR graduada por nivel.
  2. El usuario revisa y EDITA la conclusión jurídica en un cuadro de
     texto (firma el profesional, no el software).
  3. Exporta a .doc (Word lo abre editable) o guarda el HTML.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QPlainTextEdit, QLineEdit, QFileDialog, QMessageBox, QSplitter,
    QGroupBox, QWidget, QCheckBox,
)

from . import report_engine

# Vista previa HTML: se usa QWebEngineView si está, si no QTextBrowser.
try:
    from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
    _TIENE_WEBENGINE = True
except Exception:
    _TIENE_WEBENGINE = False
    from qgis.PyQt.QtWidgets import QTextBrowser


class ReportePreviewDialog(QDialog):
    """Vista previa + conclusión editable + exportación."""

    def __init__(self, contexto, atributos_predio=None, parent=None):
        super().__init__(parent)
        self.contexto = contexto
        self.atributos_predio = atributos_predio or {}
        self._conclusion_editada = None
        self._build_ui()
        self._autocompletar_predio()
        # Subtítulo inicial: el del perfil por defecto
        perfil0 = report_engine.PERFILES.get(
            self._perfil(), report_engine.PERFILES["generico"])
        self.txt_subtitulo.setText(perfil0["subtitulo"])
        self._regenerar()

    # Heurísticas de autodetección (coherentes con overlap_engine)
    _CAMPOS_TITULAR = ("titular", "nombre", "propietario", "propietar",
                       "razon_social", "razon_soc", "beneficiario",
                       "concesionario", "comunidad", "denominacion")
    _CAMPOS_DERECHO = ("tipo", "tipo_derecho", "tipo_dere", "derecho",
                       "categoria", "clase", "modalidad", "uso")

    def _autodetectar(self, candidatos):
        """Primer atributo del predio que coincida con los candidatos."""
        reales = {k.lower(): v for k, v in self.atributos_predio.items()}
        for c in candidatos:
            if c in reales:
                return reales[c]
        for c in candidatos:
            for bajo, val in reales.items():
                if bajo.startswith(c):
                    return val
        return ""

    def _autocompletar_predio(self):
        """Rellena titular y tipo de derecho desde la capa (editable encima)."""
        self.txt_titular.setText(self._autodetectar(self._CAMPOS_TITULAR))
        self.txt_derecho.setText(self._autodetectar(self._CAMPOS_DERECHO))

    def _build_ui(self):
        self.setWindowTitle("YF · Informe de Superposición")
        self.setMinimumSize(900, 680)
        main = QVBoxLayout(self)

        # ── Barra superior: perfil + responsable ──
        barra = QHBoxLayout()
        barra.addWidget(QLabel("Perfil institucional:"))
        self.cbo_perfil = QComboBox()
        for clave, nombre in report_engine.perfiles_disponibles():
            self.cbo_perfil.addItem(nombre, clave)
        self.cbo_perfil.currentIndexChanged.connect(self._on_perfil_cambiado)
        barra.addWidget(self.cbo_perfil)
        barra.addWidget(QLabel("Responsable:"))
        self.txt_responsable = QLineEdit()
        self.txt_responsable.setPlaceholderText(
            "Ing. ... (aparece en la línea de firma)")
        self.txt_responsable.textChanged.connect(self._regenerar)
        barra.addWidget(self.txt_responsable, 1)
        self.chk_anexo = QCheckBox("Incluir anexo de verificación")
        self.chk_anexo.setChecked(True)
        self.chk_anexo.toggled.connect(self._regenerar)
        barra.addWidget(self.chk_anexo)
        main.addLayout(barra)

        # ── Identificación del informe (editable por el usuario) ──
        grp_id = QGroupBox("Identificación del informe")
        gid = QVBoxLayout(grp_id)
        fila_sub = QHBoxLayout()
        fila_sub.addWidget(QLabel("Subtítulo / institución:"))
        self.txt_subtitulo = QLineEdit()
        self.txt_subtitulo.setPlaceholderText(
            "Ej. Gerencia Regional Forestal y de Fauna Silvestre — GOREMAD")
        self.txt_subtitulo.setToolTip(
            "Texto libre bajo el título del informe. Al elegir un perfil se "
            "sugiere uno, pero puede editarlo para cada informe.")
        self.txt_subtitulo.textChanged.connect(self._regenerar)
        fila_sub.addWidget(self.txt_subtitulo, 1)
        gid.addLayout(fila_sub)

        fila_pred = QHBoxLayout()
        fila_pred.addWidget(QLabel("Titular / propietario:"))
        self.txt_titular = QLineEdit()
        self.txt_titular.setPlaceholderText(
            "Se autocompleta desde la capa — editable")
        self.txt_titular.textChanged.connect(self._regenerar)
        fila_pred.addWidget(self.txt_titular, 1)
        fila_pred.addWidget(QLabel("Tipo de derecho:"))
        self.txt_derecho = QLineEdit()
        self.txt_derecho.setPlaceholderText("Ej. Predio rural, concesión...")
        self.txt_derecho.textChanged.connect(self._regenerar)
        fila_pred.addWidget(self.txt_derecho, 1)
        gid.addLayout(fila_pred)
        main.addWidget(grp_id)

        # ── Splitter: conclusión editable | vista previa ──
        splitter = QSplitter(Qt.Orientation.Vertical)

        grp_concl = QGroupBox(
            "Conclusión (borrador editable — firma el profesional)")
        vc = QVBoxLayout(grp_concl)
        self.txt_conclusion = QPlainTextEdit()
        self.txt_conclusion.setPlaceholderText(
            "El motor propone una conclusión según el nivel del hallazgo. "
            "Revísela y edítela antes de exportar.")
        vc.addWidget(self.txt_conclusion)
        fila_c = QHBoxLayout()
        btn_regenerar = QPushButton("↻  Restaurar conclusión sugerida")
        btn_regenerar.setToolTip(
            "Vuelve a la redacción automática según el nivel del análisis.")
        btn_regenerar.clicked.connect(self._restaurar_conclusion)
        btn_aplicar = QPushButton("Aplicar a la vista previa")
        btn_aplicar.clicked.connect(self._aplicar_conclusion)
        fila_c.addWidget(btn_regenerar)
        fila_c.addStretch(1)
        fila_c.addWidget(btn_aplicar)
        vc.addLayout(fila_c)
        splitter.addWidget(grp_concl)

        cont_prev = QWidget()
        vp = QVBoxLayout(cont_prev)
        vp.setContentsMargins(0, 0, 0, 0)
        vp.addWidget(QLabel("Vista previa:"))
        if _TIENE_WEBENGINE:
            self.preview = QWebEngineView()
        else:
            self.preview = QTextBrowser()
        vp.addWidget(self.preview, 1)
        splitter.addWidget(cont_prev)
        splitter.setSizes([200, 480])
        main.addWidget(splitter, 1)

        # ── Botones de exportación ──
        fila_b = QHBoxLayout()
        btn_doc = QPushButton("📄  Exportar a Word (.doc)")
        btn_doc.setToolTip(
            "Genera un documento que Word abre editable — insumo para el "
            "informe técnico. Sin dependencias externas.")
        btn_doc.setStyleSheet(
            "QPushButton{background:#1F4E5F;color:white;padding:8px;"
            "font-weight:bold;}")
        btn_doc.clicked.connect(self._exportar_doc)
        btn_html = QPushButton("🌐  Guardar HTML")
        btn_html.clicked.connect(self._guardar_html)
        fila_b.addWidget(btn_doc, 1)
        fila_b.addWidget(btn_html)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.reject)
        fila_b.addWidget(btn_cerrar)
        main.addLayout(fila_b)

    # ──────────────────────────────────────────────────────────────

    def _perfil(self):
        return self.cbo_perfil.currentData() or "generico"

    def _on_perfil_cambiado(self, *args):
        # Sugerir el subtítulo del perfil, pero sin pisar lo que el usuario
        # ya haya escrito a mano.
        actual = self.txt_subtitulo.text().strip()
        sugeridos = {v["subtitulo"] for v in report_engine.PERFILES.values()}
        if not actual or actual in sugeridos:
            perfil = report_engine.PERFILES.get(
                self._perfil(), report_engine.PERFILES["generico"])
            self.txt_subtitulo.blockSignals(True)
            self.txt_subtitulo.setText(perfil["subtitulo"])
            self.txt_subtitulo.blockSignals(False)
        self._regenerar()

    def _restaurar_conclusion(self):
        self._conclusion_editada = None
        sugerida = report_engine.conclusion_sugerida(self.contexto)
        self.txt_conclusion.setPlainText(sugerida)
        self._regenerar()

    def _aplicar_conclusion(self):
        self._conclusion_editada = self.txt_conclusion.toPlainText().strip()
        self._regenerar()

    def _conclusion_actual(self):
        texto = self.txt_conclusion.toPlainText().strip()
        return texto if texto else None

    def _regenerar(self, *args):
        # Primera vez: sembrar el cuadro con la conclusión sugerida
        if not self.txt_conclusion.toPlainText().strip():
            self.txt_conclusion.setPlainText(
                report_engine.conclusion_sugerida(self.contexto))
        self._html = report_engine.generar_html(
            self.contexto,
            perfil_key=self._perfil(),
            conclusion=self._conclusion_actual(),
            responsable=self.txt_responsable.text().strip() or None,
            incluir_anexo=self.chk_anexo.isChecked(),
            subtitulo=self.txt_subtitulo.text().strip(),
            predio_titular=self.txt_titular.text().strip() or None,
            predio_derecho=self.txt_derecho.text().strip() or None,
        )
        try:
            if _TIENE_WEBENGINE:
                self.preview.setHtml(self._html)
            else:
                self.preview.setHtml(self._html)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def _nombre_base(self):
        nombre = self.contexto["analisis"]["predio"]["nombre"]
        limpio = "".join(c if c.isalnum() or c in " -_" else "_"
                         for c in nombre).strip().replace(" ", "_")
        return "Informe_superposicion_{}".format(limpio or "predio")

    def _exportar_doc(self):
        self._aplicar_conclusion()
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar informe a Word",
            self._nombre_base() + ".doc", "Documento Word (*.doc)")
        if not ruta:
            return
        try:
            ruta_final = report_engine.exportar_doc(self._html, ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", "No se pudo exportar:\n{}".format(e))
            return
        self._ofrecer_abrir(ruta_final,
                            "Documento Word generado:\n{}".format(
                                os.path.basename(ruta_final)))

    def _guardar_html(self):
        self._aplicar_conclusion()
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar informe HTML",
            self._nombre_base() + ".html", "HTML (*.html)")
        if not ruta:
            return
        try:
            ruta_final = report_engine.guardar_html(self._html, ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", "No se pudo guardar:\n{}".format(e))
            return
        self._ofrecer_abrir(ruta_final,
                            "HTML guardado:\n{}".format(
                                os.path.basename(ruta_final)))

    def _ofrecer_abrir(self, ruta, mensaje):
        resp = QMessageBox.question(
            self, "Listo", mensaje + "\n\n¿Abrir el archivo ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resp == QMessageBox.StandardButton.Yes:
            try:
                from qgis.PyQt.QtGui import QDesktopServices
                from qgis.PyQt.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
