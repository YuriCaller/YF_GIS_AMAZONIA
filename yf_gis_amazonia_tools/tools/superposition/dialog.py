# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Diálogo principal.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QCheckBox, QDoubleSpinBox, QLineEdit, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar, QApplication, QAbstractItemView,
)
from qgis.core import QgsProject, QgsWkbTypes, QgsVectorLayer

from . import overlap_engine, output_export
from .data_contract import (
    NIVEL_CRITICO, NIVEL_OBSERVABLE, NIVEL_NO_SIGNIFICATIVA,
    UMBRAL_TOLERANCIA_HA, UMBRAL_CRITICO_PCT, UMBRAL_OBSERVABLE_PCT,
)
from .layer_scanner import escanear_carpeta
from .service_dialog import ServiciosDialog

SETTINGS_CARPETA = "YF_GIS_Amazonia/superposicion_carpeta"

COLORES_NIVEL = {
    NIVEL_CRITICO: QColor(255, 205, 205),
    NIVEL_OBSERVABLE: QColor(255, 235, 190),
    NIVEL_NO_SIGNIFICATIVA: QColor(225, 240, 225),
}


class SuperposicionDialog(QDialog):
    """Analiza un predio contra una carpeta de derechos preexistentes."""

    def __init__(self, iface, plugin_version="", parent=None):
        super().__init__(parent)
        self.iface = iface
        self.plugin_version = plugin_version
        self._resultado = None
        self._contexto = None
        self._area_unica = 0.0
        self._capas_escaneadas = None
        self._capas_remotas = []
        self._claves_servicios = []
        self._capa_resultado_id = None
        self._cancelado = False
        self._build_ui()
        self._actualizar_resumen_fuentes()
        self._poblar_capas()

    # ──────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("YF · Análisis de Superposición de Derechos")
        self.setMinimumSize(760, 620)
        main = QVBoxLayout(self)
        main.setSpacing(8)

        # ── Área evaluada ──
        grp_predio = QGroupBox("Área evaluada (predio)")
        v1 = QVBoxLayout(grp_predio)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Capa:"))
        self.cbo_predio = QComboBox()
        self.cbo_predio.currentIndexChanged.connect(self._on_predio_cambiado)
        fila.addWidget(self.cbo_predio, 1)
        self.btn_refrescar = QPushButton("↻")
        self.btn_refrescar.setFixedWidth(32)
        self.btn_refrescar.setToolTip("Actualizar lista de capas")
        self.btn_refrescar.clicked.connect(self._poblar_capas)
        fila.addWidget(self.btn_refrescar)
        self.btn_reset = QPushButton("🧹")
        self.btn_reset.setFixedWidth(32)
        self.btn_reset.setToolTip(
            "Empezar de cero: borra la carpeta guardada y todos los "
            "parámetros y resultados de esta sesión.")
        self.btn_reset.clicked.connect(self._reset_todo)
        fila.addWidget(self.btn_reset)
        v1.addLayout(fila)

        fila2 = QHBoxLayout()
        self.chk_seleccion = QCheckBox("Solo entidades seleccionadas")
        self.chk_seleccion.setToolTip(
            "Analiza únicamente las entidades seleccionadas en el canvas.\n"
            "Si la capa tiene varias entidades, todas se unen en una sola "
            "área evaluada.")
        self.chk_seleccion.toggled.connect(self._actualizar_info_predio)
        fila2.addWidget(self.chk_seleccion)
        fila2.addStretch(1)
        v1.addLayout(fila2)

        self.lbl_predio = QLabel("—")
        self.lbl_predio.setStyleSheet("color:#2E5E3A; font-weight:bold;")
        v1.addWidget(self.lbl_predio)
        main.addWidget(grp_predio)

        # ── Capas de derechos ──
        grp_capas = QGroupBox(
            "Fuentes de derechos preexistentes — locales, en línea o ambas")
        v2 = QVBoxLayout(grp_capas)
        fila3 = QHBoxLayout()
        self.txt_carpeta = QLineEdit()
        self.txt_carpeta.setPlaceholderText(
            "Opcional si usa geoservicios — carpeta con concesiones, "
            "BPP, predios, lotes, ANP...")
        self.txt_carpeta.setText(
            QSettings().value(SETTINGS_CARPETA, "", type=str))
        fila3.addWidget(self.txt_carpeta, 1)
        btn_carpeta = QPushButton("Elegir carpeta...")
        btn_carpeta.clicked.connect(self._elegir_carpeta)
        fila3.addWidget(btn_carpeta)
        v2.addLayout(fila3)

        fila4 = QHBoxLayout()
        self.chk_recursivo = QCheckBox("Incluir subcarpetas")
        self.chk_recursivo.setChecked(True)
        fila4.addWidget(self.chk_recursivo)
        self.btn_escanear = QPushButton("🔍  Escanear carpeta")
        self.btn_escanear.clicked.connect(self._escanear)
        fila4.addWidget(self.btn_escanear)
        fila4.addStretch(1)
        self.lbl_capas = QLabel("—")
        fila4.addWidget(self.lbl_capas)
        v2.addLayout(fila4)
        # ── Geoservicios oficiales (fuente adicional, combinable) ──
        fila_srv = QHBoxLayout()
        self.btn_servicios = QPushButton("🌐  Geoservicios oficiales...")
        self.btn_servicios.setToolTip(
            "Evaluar también contra capas oficiales en línea (SERFOR y "
            "otras). La descarga se acota al área del predio.")
        self.btn_servicios.clicked.connect(self._elegir_servicios)
        fila_srv.addWidget(self.btn_servicios)
        self.lbl_servicios = QLabel("ningún servicio seleccionado")
        fila_srv.addWidget(self.lbl_servicios, 1)
        self.btn_quitar_srv = QPushButton("Quitar")
        self.btn_quitar_srv.setEnabled(False)
        self.btn_quitar_srv.clicked.connect(self._quitar_servicios)
        fila_srv.addWidget(self.btn_quitar_srv)
        v2.addLayout(fila_srv)

        # Resumen permanente de las fuentes activas. Sin esto, que la
        # carpeta sea opcional resultaba invisible: el usuario solo lo
        # descubria al intentar analizar sin nada seleccionado.
        self.lbl_resumen_fuentes = QLabel()
        self.lbl_resumen_fuentes.setWordWrap(True)
        v2.addWidget(self.lbl_resumen_fuentes)

        main.addWidget(grp_capas)

        # ── Parámetros ──
        grp_par = QGroupBox("Parámetros de análisis")
        v3 = QVBoxLayout(grp_par)
        fila5 = QHBoxLayout()
        fila5.addWidget(QLabel("Método de área:"))
        self.cbo_metodo = QComboBox()
        self.cbo_metodo.addItem("Elipsoidal (WGS84)", True)
        self.cbo_metodo.addItem("Planar — plano de proyección", False)
        self.cbo_metodo.setToolTip(
            "Planar: el área del plano UTM (la que cuadra con planos y "
            "partidas registrales).\nElipsoidal: superficie real del "
            "terreno sobre el elipsoide.")
        fila5.addWidget(self.cbo_metodo, 1)
        fila5.addWidget(QLabel("Tolerancia (ha):"))
        self.spin_umbral = QDoubleSpinBox()
        self.spin_umbral.setDecimals(4)
        self.spin_umbral.setRange(0.0, 100.0)
        self.spin_umbral.setSingleStep(0.01)
        self.spin_umbral.setValue(UMBRAL_TOLERANCIA_HA)
        self.spin_umbral.setToolTip(
            "Superposiciones menores a este valor se descartan: se asumen "
            "errores de digitalización de bordes, no derechos reales.")
        fila5.addWidget(self.spin_umbral)
        v3.addLayout(fila5)

        fila6 = QHBoxLayout()
        fila6.addWidget(QLabel("Umbral crítico (% del predio):"))
        self.spin_critico = QDoubleSpinBox()
        self.spin_critico.setRange(0.0, 100.0)
        self.spin_critico.setValue(UMBRAL_CRITICO_PCT)
        fila6.addWidget(self.spin_critico)
        fila6.addWidget(QLabel("Umbral observable (%):"))
        self.spin_observable = QDoubleSpinBox()
        self.spin_observable.setRange(0.0, 100.0)
        self.spin_observable.setSingleStep(0.1)
        self.spin_observable.setValue(UMBRAL_OBSERVABLE_PCT)
        fila6.addWidget(self.spin_observable)
        fila6.addStretch(1)
        v3.addLayout(fila6)
        main.addWidget(grp_par)

        # ── Acción ──
        fila7 = QHBoxLayout()
        self.btn_analizar = QPushButton("▶  Analizar superposición")
        self.btn_analizar.setStyleSheet(
            "QPushButton{background:#1F4E5F;color:white;padding:8px;"
            "font-weight:bold;} QPushButton:disabled{background:#999;}")
        self.btn_analizar.clicked.connect(self._analizar)
        fila7.addWidget(self.btn_analizar, 1)
        main.addLayout(fila7)

        fila_prog = QHBoxLayout()
        self.progreso = QProgressBar()
        self.progreso.setVisible(False)
        fila_prog.addWidget(self.progreso, 1)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setVisible(False)
        self.btn_cancelar.setToolTip(
            "Detiene el análisis. Las capas pendientes se informarán como "
            "NO EVALUADAS, no como libres de superposición.")
        self.btn_cancelar.clicked.connect(self._cancelar_analisis)
        fila_prog.addWidget(self.btn_cancelar)
        main.addLayout(fila_prog)

        # ── Resultados ──
        self.lbl_resumen = QLabel("Sin análisis todavía.")
        self.lbl_resumen.setWordWrap(True)
        self.lbl_resumen.setStyleSheet(
            "background:#f5f5f5;border:1px solid #ccc;padding:6px;")
        main.addWidget(self.lbl_resumen)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(
            ["Capa", "Tipo", "Titular", "Código", "Área (ha)", "%", "Nivel"])
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        cab.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        main.addWidget(self.tabla, 1)

        # ── Salidas ──
        fila8 = QHBoxLayout()
        self.btn_capa = QPushButton("🗺  Cargar capa al proyecto")
        self.btn_capa.setToolTip(
            "Carga las superposiciones como capa viva, coloreada por nivel "
            "y etiquetada — para ver qué derecho cae en qué lugar.")
        self.btn_capa.clicked.connect(self._cargar_capa)
        self.btn_gpkg = QPushButton("💾  GeoPackage")
        self.btn_gpkg.setToolTip("Geometrías de intersección para el plano")
        self.btn_gpkg.clicked.connect(self._exportar_gpkg)
        self.btn_csv = QPushButton("📊  CSV resumen")
        self.btn_csv.clicked.connect(self._exportar_csv)
        self.btn_informe = QPushButton("📄  Generar informe")
        self.btn_informe.setToolTip(
            "Vista previa del informe con conclusión editable, exportable "
            "a Word (.doc) — insumo para el informe técnico.")
        self.btn_informe.clicked.connect(self._generar_informe)
        self.btn_traza = QPushButton("🔒  Trazabilidad (log + anexo)")
        self.btn_traza.setToolTip(
            "Log JSON reproducible y anexo de verificación con hashes "
            "SHA-256 de cada archivo analizado")
        self.btn_traza.clicked.connect(self._exportar_trazabilidad)
        for b in (self.btn_capa, self.btn_gpkg, self.btn_csv,
                  self.btn_informe, self.btn_traza):
            b.setEnabled(False)
            fila8.addWidget(b)
        fila8.addStretch(1)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.reject)
        fila8.addWidget(btn_cerrar)
        main.addLayout(fila8)

    # ──────────────────────────────────────────────────────────────
    # Predio
    # ──────────────────────────────────────────────────────────────

    def _reset_todo(self):
        """Desconecta todo y deja el diálogo como recién abierto.

        Borra la carpeta persistida en QSettings y limpia parámetros,
        capas escaneadas y resultados de la sesión actual.
        """
        resp = QMessageBox.question(
            self, "Empezar de cero",
            "Esto borrará:\n\n"
            "• La carpeta de capas guardada\n"
            "• Los parámetros ajustados (método, umbrales)\n"
            "• El escaneo y los resultados de esta sesión\n\n"
            "¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return

        # 1) Borrar la configuración persistente
        try:
            QSettings().remove(SETTINGS_CARPETA)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

        # 2) Limpiar la interfaz
        self.txt_carpeta.clear()
        self.chk_recursivo.setChecked(True)
        self.lbl_capas.setText("—")
        self._actualizar_resumen_fuentes()
        self.cbo_metodo.setCurrentIndex(0)         # Elipsoidal
        self.spin_umbral.setValue(UMBRAL_TOLERANCIA_HA)
        self.spin_critico.setValue(UMBRAL_CRITICO_PCT)
        self.spin_observable.setValue(UMBRAL_OBSERVABLE_PCT)

        # 3) Soltar estado pesado de la sesión
        self._capas_escaneadas = None
        self._capas_remotas = []
        self._claves_servicios = []
        self._resultado = None
        self._contexto = None
        self._area_unica = 0.0
        self.tabla.setRowCount(0)
        self.lbl_resumen.setText("Sin análisis todavía.")
        for b in (self.btn_capa, self.btn_gpkg, self.btn_csv,
                  self.btn_informe, self.btn_traza):
            b.setEnabled(False)

        QMessageBox.information(
            self, "Listo",
            "Configuración reiniciada. Puede empezar de cero.")

    def _poblar_capas(self):
        actual = self.cbo_predio.currentData()
        self.cbo_predio.blockSignals(True)
        self.cbo_predio.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            # isinstance en vez de QgsMapLayerType: ese enum cambió de
            # lugar entre versiones y está deprecado en QGIS 3.30+.
            if not isinstance(lyr, QgsVectorLayer):
                continue
            try:
                if QgsWkbTypes.geometryType(lyr.wkbType()) != \
                        overlap_engine._tipo_poligono():
                    continue
            except Exception:  # nosec B112 - capa sin tipo legible: no es
                continue       # candidata a predio, se omite del selector
            self.cbo_predio.addItem(lyr.name(), lyr.id())
        if actual:
            i = self.cbo_predio.findData(actual)
            if i >= 0:
                self.cbo_predio.setCurrentIndex(i)
        self.cbo_predio.blockSignals(False)
        self._on_predio_cambiado()

    def _capa_predio(self):
        lid = self.cbo_predio.currentData()
        return QgsProject.instance().mapLayer(lid) if lid else None

    def _on_predio_cambiado(self, *args):
        capa = self._capa_predio()
        if capa is not None:
            n = capa.selectedFeatureCount()
            self.chk_seleccion.setEnabled(n > 0)
            self.chk_seleccion.setChecked(n > 0)
            self.chk_seleccion.setText(
                "Solo entidades seleccionadas ({})".format(n))
        self._actualizar_info_predio()

    def closeEvent(self, event):
        """Libera el estado pesado al cerrar (geometrías, capas escaneadas)."""
        self._resultado = None
        self._contexto = None
        self._capas_escaneadas = None
        self._capas_remotas = []
        self._claves_servicios = []
        try:
            self.tabla.setRowCount(0)
        except Exception:  # nosec B110 - en closeEvent el widget puede
            pass           # estar ya destruido por Qt
        super().closeEvent(event)

    def _atributos_predio(self):
        """Atributos de la 1ra entidad del predio (para autocompletar el
        informe con titular y tipo de derecho). Dict campo->valor, o {}."""
        capa = self._capa_predio()
        if capa is None:
            return {}
        usar_sel = (self.chk_seleccion.isChecked()
                    and capa.selectedFeatureCount() > 0)
        feats = (capa.selectedFeatures() if usar_sel
                 else list(capa.getFeatures()))
        if not feats:
            return {}
        atributos = {}
        for campo in capa.fields():
            try:
                v = feats[0][campo.name()]
            except Exception:  # nosec B112 - campo ilegible en la entidad
                continue       # de muestra; se prueba el siguiente
            if v is not None and str(v).strip():
                atributos[campo.name()] = str(v).strip()
        return atributos

    def _geometria_predio(self):
        """Geometría unificada del predio a evaluar. (geom, crs, nombre)."""
        capa = self._capa_predio()
        if capa is None:
            return None, None, None
        usar_sel = (self.chk_seleccion.isChecked()
                    and capa.selectedFeatureCount() > 0)
        feats = (capa.selectedFeatures() if usar_sel
                 else list(capa.getFeatures()))
        geoms = [f.geometry() for f in feats
                 if f.geometry() is not None and not f.geometry().isEmpty()]
        if not geoms:
            return None, capa.crs(), capa.name()
        union = geoms[0]
        for g in geoms[1:]:
            try:
                union = union.combine(g)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
        nombre = capa.name()
        if usar_sel and len(feats) == 1:
            # Un solo predio seleccionado: usar un atributo de texto como
            # nombre si existe (más útil en el informe que el nombre de capa)
            for campo in capa.fields():
                try:
                    v = feats[0][campo.name()]
                except Exception:  # nosec B112 - campo ilegible en la
                    continue       # entidad de muestra; se prueba el siguiente
                if isinstance(v, str) and v.strip():
                    nombre = "{} — {}".format(capa.name(), v.strip())
                    break
        return union, capa.crs(), nombre

    def _actualizar_info_predio(self, *args):
        geom, crs, nombre = self._geometria_predio()
        if geom is None:
            self.lbl_predio.setText("Seleccione una capa de polígonos.")
            return
        try:
            medidor = overlap_engine._medidor(
                crs, self.cbo_metodo.currentData())
            area = overlap_engine._area_ha(
                geom, medidor, self.cbo_metodo.currentData())
        except Exception:
            area = 0.0
        self.lbl_predio.setText(
            "{}  ·  {:.4f} ha  ·  {}".format(nombre, area, crs.authid()))

    # ──────────────────────────────────────────────────────────────
    # Carpeta
    # ──────────────────────────────────────────────────────────────

    def _elegir_carpeta(self):
        inicial = self.txt_carpeta.text() or ""
        carpeta = QFileDialog.getExistingDirectory(
            self, "Carpeta de capas de derechos", inicial)
        if carpeta:
            self.txt_carpeta.setText(carpeta)
            QSettings().setValue(SETTINGS_CARPETA, carpeta)
            self._escanear()
        self._actualizar_resumen_fuentes()

    def _escanear(self):
        carpeta = self.txt_carpeta.text().strip()
        if not carpeta or not os.path.isdir(carpeta):
            QMessageBox.warning(self, "Carpeta",
                                "Seleccione una carpeta válida.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._capas_escaneadas = escanear_carpeta(
                carpeta, self.chk_recursivo.isChecked())
        finally:
            QApplication.restoreOverrideCursor()
        n = len(self._capas_escaneadas)
        self.lbl_capas.setText("{} capa(s) encontrada(s)".format(n))
        self._actualizar_resumen_fuentes()
        if n == 0:
            QMessageBox.information(
                self, "Sin capas",
                "No se encontraron capas vectoriales en esa carpeta.")

    # ──────────────────────────────────────────────────────────────
    # Análisis
    # ──────────────────────────────────────────────────────────────

    def _actualizar_resumen_fuentes(self):
        """Muestra siempre qué se va a analizar y de dónde sale."""
        carpeta = self.txt_carpeta.text().strip()
        hay_carpeta = bool(carpeta and os.path.isdir(carpeta))
        n_rem = len(self._capas_remotas)

        # Carpeta válida todavía sin escanear: el análisis la escanea solo,
        # así que anunciar "0 locales" seria falso.
        if hay_carpeta and self._capas_escaneadas is None:
            base = ("Carpeta seleccionada (se escaneará al analizar)")
            if n_rem:
                base += " + <b>{r} capa(s)</b> de geoservicios.".format(r=n_rem)
            else:
                base += "."
            self.lbl_resumen_fuentes.setText(base)
            self.lbl_resumen_fuentes.setStyleSheet("color: #1565c0;")
            return

        n_loc = len(self._capas_escaneadas or []) if hay_carpeta else 0

        if n_loc and n_rem:
            texto = ("Se analizarán <b>{t} capa(s)</b>: {l} de carpeta local "
                     "+ {r} de geoservicios.").format(
                         t=n_loc + n_rem, l=n_loc, r=n_rem)
            color = "#1565c0"
        elif n_loc:
            texto = ("Se analizarán <b>{l} capa(s)</b> de la carpeta local. "
                     "Puede añadir geoservicios oficiales si lo desea."
                     ).format(l=n_loc)
            color = "#1565c0"
        elif n_rem:
            texto = ("Se analizarán <b>{r} capa(s)</b> de geoservicios. "
                     "La carpeta local no es obligatoria.").format(r=n_rem)
            color = "#1565c0"
        else:
            texto = ("Sin fuentes seleccionadas. Elija una carpeta de capas, "
                     "geoservicios oficiales, o ambas cosas.")
            color = "#b45309"
        self.lbl_resumen_fuentes.setText(texto)
        self.lbl_resumen_fuentes.setStyleSheet("color: %s;" % color)

    def _cancelar_analisis(self):
        """Marca la cancelación; el motor la recoge en el próximo callback."""
        self._cancelado = True
        self.btn_cancelar.setEnabled(False)
        self.progreso.setFormat("Cancelando...")

    def _elegir_servicios(self):
        dlg = ServiciosDialog(self, seleccion_previa=self._claves_servicios)
        _ejecutar = getattr(dlg, "exec", None) or getattr(dlg, "exec" + "_")
        if _ejecutar():
            self._capas_remotas = dlg.capas_encontradas()
            self._claves_servicios = dlg.claves_elegidas()
            self._actualizar_lbl_servicios()

    def _quitar_servicios(self):
        self._capas_remotas = []
        self._claves_servicios = []
        self._actualizar_lbl_servicios()

    def _actualizar_lbl_servicios(self):
        n = len(self._capas_remotas)
        if n:
            self.lbl_servicios.setText(
                "{} capa(s) de geoservicios".format(n))
            self.lbl_servicios.setStyleSheet("color: #1565c0;")
        else:
            self.lbl_servicios.setText("ningún servicio seleccionado")
            self.lbl_servicios.setStyleSheet("")
        self.btn_quitar_srv.setEnabled(bool(n))
        self._actualizar_resumen_fuentes()

    def _analizar(self):
        geom, crs, nombre = self._geometria_predio()
        if geom is None:
            QMessageBox.warning(
                self, "Predio",
                "No hay geometría para evaluar. Elija una capa de polígonos "
                "(o seleccione entidades en el canvas).")
            return
        carpeta = self.txt_carpeta.text().strip()
        hay_carpeta = bool(carpeta and os.path.isdir(carpeta))
        if hay_carpeta and self._capas_escaneadas is None:
            self._escanear()
        locales = list(self._capas_escaneadas or []) if hay_carpeta else []

        # v3.0.4: las dos fuentes se combinan. El motor recibe una sola
        # lista de CapaEncontrada; le da igual el origen de cada una.
        capas = locales + list(self._capas_remotas)
        if not capas:
            QMessageBox.warning(
                self, "Sin capas",
                "Elija una carpeta de capas, geoservicios oficiales, "
                "o ambas cosas.")
            return

        # v3.0.4 fix: soltar el resultado anterior ANTES de correr otro.
        # Un ResultadoAnalisis retiene miles de geometrías de intersección;
        # acumular corridas en un diálogo persistente infla la memoria.
        self._resultado = None
        self._contexto = None
        self._capa_resultado_id = None
        self.tabla.setRowCount(0)

        total = len(capas)
        self._cancelado = False
        self.btn_cancelar.setEnabled(True)
        self.progreso.setVisible(True)
        self.btn_cancelar.setVisible(True)
        self.progreso.setRange(0, total)
        self.progreso.setValue(0)
        self.btn_analizar.setEnabled(False)

        def _progreso(i, tot, nombre_capa):
            self.progreso.setValue(i)
            self.progreso.setFormat(
                "{}/{}  {}".format(i, tot, nombre_capa[:40]))
            QApplication.processEvents()
            return not self._cancelado

        try:
            self._resultado, self._area_unica = overlap_engine.analizar(
                geom, crs, carpeta,
                predio_nombre=nombre,
                umbral_ha=self.spin_umbral.value(),
                elipsoidal=self.cbo_metodo.currentData(),
                recursivo=self.chk_recursivo.isChecked(),
                plugin_version=self.plugin_version,
                umbral_critico=self.spin_critico.value(),
                umbral_observable=self.spin_observable.value(),
                capas=capas,
                progreso=_progreso,
            )
            self._contexto = self._resultado.as_context(
                area_afectada_unica_ha=self._area_unica)
        except Exception as e:
            QMessageBox.critical(self, "Error en el análisis", str(e))
            return
        finally:
            self.progreso.setVisible(False)
            self.btn_cancelar.setVisible(False)
            self.btn_analizar.setEnabled(True)

        self._mostrar_resultado()

    def _mostrar_resultado(self):
        r, ctx = self._resultado, self._contexto
        a = ctx["analisis"]

        partes = [
            "<b>{}</b> — {:.4f} ha ({})".format(
                a["predio"]["nombre"], a["predio"]["area_ha"],
                a["metodo_area"]),
            "Capas evaluadas: <b>{}</b> · con superposición: <b>{}</b>".format(
                a["capas_evaluadas"], a["capas_con_superposicion"]),
        ]
        if r.superposiciones:
            partes.append(
                "Área afectada (sin doble conteo): "
                "<b>{:.4f} ha ({:.2f}%)</b>".format(
                    a.get("area_afectada_unica_ha", 0.0),
                    a.get("porcentaje_afectado_unico", 0.0)))
            if abs(a["area_superpuesta_total_ha"]
                   - a.get("area_afectada_unica_ha", 0.0)) > 1e-4:
                partes.append(
                    "<i>Suma simple: {:.4f} ha — mayor porque hay derechos "
                    "que se solapan entre sí.</i>".format(
                        a["area_superpuesta_total_ha"]))
            partes.append("Nivel: <b>{}</b>".format(a["nivel_global_legible"]))
        else:
            partes.append(
                "<b style='color:#2E5E3A'>Sin superposición con derechos "
                "preexistentes.</b>")
        if r.errores:
            partes.append(
                "<span style='color:#B00'>{} capa(s) no evaluada(s) — "
                "revise el detalle.</span>".format(len(r.errores)))
        self.lbl_resumen.setText("<br>".join(partes))

        sups = ctx["superposiciones"]
        self.tabla.setRowCount(len(sups) + len(r.errores))
        for i, s in enumerate(sups):
            valores = [s["capa"], s["tipo"], s["titular"], s["codigo"],
                       "{:.4f}".format(s["area_ha"]),
                       "{:.2f}".format(s["porcentaje"]), s["nivel_legible"]]
            for j, v in enumerate(valores):
                item = QTableWidgetItem(str(v))
                color = COLORES_NIVEL.get(s["nivel"])
                if color:
                    item.setBackground(color)
                self.tabla.setItem(i, j, item)
        # Capas no evaluadas, al final y en gris
        for k, e in enumerate(r.errores):
            fila = len(sups) + k
            valores = [e["capa"], "—", "—", "—", "—", "—",
                       "No evaluada: {}".format(e["motivo"])]
            for j, v in enumerate(valores):
                item = QTableWidgetItem(str(v))
                item.setBackground(QColor(235, 235, 235))
                self.tabla.setItem(fila, j, item)

        hay = bool(r.superposiciones)
        self.btn_capa.setEnabled(hay)
        self.btn_gpkg.setEnabled(hay)
        self.btn_csv.setEnabled(hay)
        self.btn_informe.setEnabled(True)
        self.btn_traza.setEnabled(True)

        # Cargar automáticamente la capa resultante al terminar: es lo que
        # el operador quiere ver de inmediato (dónde cae cada superposición).
        if hay:
            self._cargar_capa(silencioso=True)

    # ──────────────────────────────────────────────────────────────
    # Salidas
    # ──────────────────────────────────────────────────────────────

    def _cargar_capa(self, checked=False, silencioso=False):
        """Carga las superposiciones como capa viva en el proyecto.

        v3.0.4 fix: el resultado se carga solo al terminar el análisis, y
        el botón seguía conectado a este mismo método. Pulsarlo después
        creaba una segunda capa idéntica, indistinguible de la primera en
        el panel. Ahora cada corrida mantiene UNA capa: si ya existe la de
        esta corrida, se reemplaza en vez de acumularse.
        """
        if not self._resultado or not self._resultado.superposiciones:
            return
        _, crs, nombre_predio = self._geometria_predio()
        nombre = "Superposiciones — {}".format(
            self._resultado.predio_nombre or "predio")

        anterior = getattr(self, "_capa_resultado_id", None)
        if anterior and QgsProject.instance().mapLayer(anterior) is not None:
            QgsProject.instance().removeMapLayer(anterior)

        capa, msg = output_export.crear_capa_memoria(
            self._resultado, crs, nombre_capa=nombre)
        if capa is not None:
            self._capa_resultado_id = capa.id()
        if capa is None:
            if not silencioso:
                QMessageBox.warning(self, "Capa no creada", msg)
            return
        # Refrescar el canvas para que se vea de inmediato
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        if not silencioso:
            QMessageBox.information(self, "Capa cargada", msg)

    def _exportar_gpkg(self):
        if not self._resultado:
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar superposiciones", "superposiciones.gpkg",
            "GeoPackage (*.gpkg)")
        if not ruta:
            return
        _, crs, _ = self._geometria_predio()
        ok, msg = output_export.exportar_geopackage(
            self._resultado, ruta, crs)
        if ok:
            try:
                self.iface.addVectorLayer(ruta, "superposiciones", "ogr")
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            QMessageBox.information(self, "Exportado", msg)
        else:
            QMessageBox.warning(self, "No exportado", msg)

    def _exportar_csv(self):
        if not self._contexto:
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar resumen", "superposicion_resumen.csv",
            "CSV (*.csv)")
        if not ruta:
            return
        output_export.exportar_csv_resumen(self._contexto, ruta)
        QMessageBox.information(self, "Exportado",
                                "Resumen guardado en {}".format(
                                    os.path.basename(ruta)))

    def _generar_informe(self):
        if not self._contexto:
            return
        from .report_dialog import ReportePreviewDialog
        dlg = ReportePreviewDialog(
            self._contexto,
            atributos_predio=self._atributos_predio(),
            parent=self)
        dlg.exec()

    def _exportar_trazabilidad(self):
        if not self._contexto:
            return
        carpeta = QFileDialog.getExistingDirectory(
            self, "Carpeta para los productos de trazabilidad")
        if not carpeta:
            return
        rutas = output_export.exportar_trazabilidad(self._contexto, carpeta)
        QMessageBox.information(
            self, "Trazabilidad generada",
            "Se generaron:\n\n" + "\n".join(os.path.basename(r) for r in rutas)
            + "\n\nEl anexo incluye el hash SHA-256 de cada archivo "
              "analizado, verificable por terceros.")
