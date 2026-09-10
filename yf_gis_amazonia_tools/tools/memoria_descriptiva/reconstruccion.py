# -*- coding: utf-8 -*-
"""
reconstruccion.py — Pestaña «Reconstruir predio» de Memoria Descriptiva
YF GIS Amazonia Tools

La operacion inversa de la herramienta: en vez de generar la memoria a
partir del poligono, reconstruye el poligono a partir de la memoria.
Para cuando llega el expediente con el cuadro de vertices pero sin
shapefile.

No es una herramienta nueva de la suite: no se registra en
core/tools_catalog.py ni en core/plugin_manager.py. Es una pestaña mas
del dialogo que ya existe.

Toda la logica vive en core/poligonal.py y core/pegado_poligonal.py.
Este modulo es solo la cascara: recoge origen, fecha y declinacion,
llama, y crea la capa.

Autor: Yuri F. Caller Cordova — TUCSA / gis-amazonia.pe
"""

import datetime

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QDate
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsFeature, QgsField, QgsGeometry, QgsPointXY,
                       QgsProject, QgsVectorLayer)

from ...core.pegado_poligonal import TablaPegadoWidget
from ...core.poligonal import (TOLERANCIA_CIERRE_DEFECTO, compensar_bowditch,
                               poligonal_a_poligono)

from ...core.qt_compat import QVariant_Double, QVariant_String, RichText

try:
    from ...core.yf_declinacion import convergencia_punto, declinacion_punto
    _DECL_OK = True
except ImportError as _e:                              # pragma: no cover
    _DECL_OK = False
    _DECL_ERR = str(_e)


class TabReconstruccion(QtWidgets.QWidget):
    """Pestaña completa. Se inserta en el tabWidget del dialogo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pol = None
        self._construir_ui()

    # ------------------------------------------------------------ UI
    def _construir_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        cont = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(cont)
        scroll.setWidget(cont)
        outer.addWidget(scroll)

        ayuda = QtWidgets.QLabel(
            "Reconstruye el poligono a partir del cuadro de vertices de una "
            "memoria descriptiva. Util cuando el expediente llega sin "
            "shapefile. Si el plano esta acotado en azimut magnetico, indica "
            "la fecha del <b>trabajo de campo</b> — no la de aprobacion.")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color:#555; padding:4px;")
        lay.addWidget(ayuda)

        # ── Tabla pegada ────────────────────────────────────────────
        grp_tabla = QtWidgets.QGroupBox("Cuadro de vertices")
        grp_tabla.setStyleSheet("QGroupBox { font-weight: bold; }")
        vl = QtWidgets.QVBoxLayout()
        self.tabla = TablaPegadoWidget()
        vl.addWidget(self.tabla)
        grp_tabla.setLayout(vl)
        lay.addWidget(grp_tabla, 1)

        # ── Origen ──────────────────────────────────────────────────
        grp_org = QtWidgets.QGroupBox("Punto de arranque (primer vertice)")
        grp_org.setStyleSheet("QGroupBox { font-weight: bold; }")
        fl = QtWidgets.QFormLayout()

        self.spinE = QtWidgets.QDoubleSpinBox()
        self.spinE.setRange(-1e7, 1e7)
        self.spinE.setDecimals(3)
        self.spinE.setSuffix(" m E")
        self.spinN = QtWidgets.QDoubleSpinBox()
        self.spinN.setRange(-1e8, 1e8)
        self.spinN.setDecimals(3)
        self.spinN.setSuffix(" m N")
        fl.addRow("Este:", self.spinE)
        fl.addRow("Norte:", self.spinN)

        self.txtCrs = QtWidgets.QLineEdit("EPSG:32719")
        self.txtCrs.setToolTip(
            "Si el expediente es del PETT puede estar en PSAD56 zona 19S "
            "(EPSG:24879), no en WGS84. Confundirlos son ~350 m de "
            "traslacion en Peru.")
        fl.addRow("SRC:", self.txtCrs)

        self.btnDesdeSeleccion = QtWidgets.QPushButton(
            "Tomar del vertice seleccionado en el lienzo")
        self.btnDesdeSeleccion.clicked.connect(self._origen_desde_seleccion)
        fl.addRow("", self.btnDesdeSeleccion)
        grp_org.setLayout(fl)
        lay.addWidget(grp_org)

        # ── Norte ───────────────────────────────────────────────────
        grp_n = QtWidgets.QGroupBox("Correccion de norte")
        grp_n.setStyleSheet("QGroupBox { font-weight: bold; }")
        fl2 = QtWidgets.QFormLayout()

        self.cboNorte = QtWidgets.QComboBox()
        self.cboNorte.addItem("Magnetico (aplicar declinacion)", "magnetico")
        self.cboNorte.addItem("Verdadero (sin correccion)", "verdadero")
        self.cboNorte.addItem("De cuadricula (quitar convergencia)", "cuadricula")
        self.cboNorte.currentIndexChanged.connect(self._actualizar_norte)
        fl2.addRow("Los azimuts del plano son:", self.cboNorte)

        self.fecha = QtWidgets.QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setDate(QDate(1998, 7, 1))
        self.fecha.dateChanged.connect(self._calcular_declinacion)
        fl2.addRow("Fecha del levantamiento:", self.fecha)

        fila = QtWidgets.QHBoxLayout()
        self.spinDecl = QtWidgets.QDoubleSpinBox()
        self.spinDecl.setRange(-40.0, 40.0)
        self.spinDecl.setDecimals(3)
        self.spinDecl.setSuffix(" °")
        self.spinDecl.setToolTip("Negativa al Oeste, que es el caso en Peru.")
        self.btnCalcDecl = QtWidgets.QPushButton("Calcular (WMM)")
        self.btnCalcDecl.clicked.connect(self._calcular_declinacion)
        fila.addWidget(self.spinDecl)
        fila.addWidget(self.btnCalcDecl)
        fl2.addRow("Declinacion:", fila)

        self.spinConv = QtWidgets.QDoubleSpinBox()
        self.spinConv.setRange(-10.0, 10.0)
        self.spinConv.setDecimals(3)
        self.spinConv.setSuffix(" °")
        fl2.addRow("Convergencia:", self.spinConv)

        self.lblModelo = QtWidgets.QLabel()
        self.lblModelo.setStyleSheet("color:#666; font-size:8pt;")
        self.lblModelo.setWordWrap(True)
        fl2.addRow("", self.lblModelo)
        grp_n.setLayout(fl2)
        lay.addWidget(grp_n)

        # ── Acciones ────────────────────────────────────────────────
        acc = QtWidgets.QHBoxLayout()
        self.chkCompensar = QtWidgets.QCheckBox("Compensar cierre (Bowditch)")
        self.chkCompensar.setToolTip(
            "Reparte el error de cierre entre los lados. Se niega si el "
            "error es grande o si hay linderos naturales: compensar un "
            "cierre malo no lo arregla, lo esconde.")
        self.btnReconstruir = QtWidgets.QPushButton("Reconstruir predio")
        self.btnReconstruir.setStyleSheet(
            "padding: 8px 18px; font-weight: bold; font-size: 11pt;")
        self.btnReconstruir.clicked.connect(self._reconstruir)
        acc.addWidget(self.chkCompensar)
        acc.addStretch()
        acc.addWidget(self.btnReconstruir)
        lay.addLayout(acc)

        self.lblResultado = QtWidgets.QLabel()
        self.lblResultado.setWordWrap(True)
        self.lblResultado.setTextFormat(RichText)
        lay.addWidget(self.lblResultado)

        self.tabla.cambiado.connect(self.btnReconstruir.setEnabled)
        self.btnReconstruir.setEnabled(False)
        self._actualizar_norte()

    # -------------------------------------------------------- helpers
    def _actualizar_norte(self):
        modo = self.cboNorte.currentData()
        mag = (modo == "magnetico")
        self.fecha.setEnabled(mag)
        self.spinDecl.setEnabled(mag)
        self.btnCalcDecl.setEnabled(mag and _DECL_OK)
        self.spinConv.setEnabled(modo == "cuadricula")
        if not mag:
            self.spinDecl.setValue(0.0)
        if modo != "cuadricula":
            self.spinConv.setValue(0.0)
        if mag and not _DECL_OK:
            self.lblModelo.setText(
                "Modelo WMM no disponible: {}. Escribe la declinacion a mano."
                .format(_DECL_ERR))

    def _crs(self):
        crs = QgsCoordinateReferenceSystem(self.txtCrs.text().strip())
        return crs if crs.isValid() else None

    def _a_wgs84(self):
        crs = self._crs()
        if crs is None:
            return None
        destino = QgsCoordinateReferenceSystem("EPSG:4326")
        tr = QgsCoordinateTransform(crs, destino, QgsProject.instance())
        p = tr.transform(QgsPointXY(self.spinE.value(), self.spinN.value()))
        return p.y(), p.x()                       # lat, lon

    def _origen_desde_seleccion(self):
        for capa in QgsProject.instance().mapLayers().values():
            if not isinstance(capa, QgsVectorLayer):
                continue
            if capa.selectedFeatureCount() != 1:
                continue
            geom = next(capa.getSelectedFeatures()).geometry()
            if geom is None or geom.isEmpty():
                continue
            p = geom.centroid().asPoint()
            self.spinE.setValue(p.x())
            self.spinN.setValue(p.y())
            if capa.crs().isValid():
                self.txtCrs.setText(capa.crs().authid())
            self._avisar("Origen tomado de «{}».".format(capa.name()), True)
            return
        self._avisar("Selecciona exactamente un objeto en una capa vectorial.",
                     False)

    def _calcular_declinacion(self):
        if not _DECL_OK or self.cboNorte.currentData() != "magnetico":
            return
        latlon = self._a_wgs84()
        if latlon is None:
            self._avisar("SRC invalido: {}".format(self.txtCrs.text()), False)
            return
        if self.spinE.value() == 0 and self.spinN.value() == 0:
            return                                # aun sin origen
        qd = self.fecha.date()
        fecha = datetime.date(qd.year(), qd.month(), qd.day())
        try:
            d, var, info = declinacion_punto(latlon[0], latlon[1], fecha)
        except Exception as e:                    # modelo fuera de epoca
            self.lblModelo.setText("No se pudo calcular: {}".format(e))
            return
        self.spinDecl.setValue(d)
        self.lblModelo.setText(
            "{} · epoca {} · D = {:+.3f}° ({:.1f}° {}) · variacion {:+.3f}°/año"
            .format(info.get("modelo", "WMM"), info.get("epoca", "?"), d,
                    abs(d), "W" if d < 0 else "E", var))
        try:
            g = convergencia_punto(self.spinE.value(), self.spinN.value(),
                                   self.txtCrs.text().strip())
            if self.cboNorte.currentData() == "cuadricula":
                self.spinConv.setValue(g)
        except Exception:
            pass

    def _avisar(self, texto, ok):
        color = "#2e7d32" if ok else "#c62828"
        self.lblResultado.setText(
            '<span style="color:{}">{}</span>'.format(color, texto))

    # ---------------------------------------------------------- accion
    def _reconstruir(self):
        segs = self.tabla.segmentos()
        if not segs:
            self._avisar("No hay lados que reconstruir.", False)
            return
        crs = self._crs()
        if crs is None:
            self._avisar("SRC invalido: {}".format(self.txtCrs.text()), False)
            return

        origen = (self.spinE.value(), self.spinN.value())
        try:
            pol = poligonal_a_poligono(origen, segs,
                                       declinacion=self.spinDecl.value(),
                                       convergencia=self.spinConv.value())
        except ValueError as e:
            self._avisar("Error: {}".format(e), False)
            return

        if self.chkCompensar.isChecked():
            try:
                pol = compensar_bowditch(pol, TOLERANCIA_CIERRE_DEFECTO)
            except ValueError as e:
                self._avisar("No se compenso. {}".format(e), False)

        self._pol = pol
        capa = self._crear_capa(pol, crs)
        QgsProject.instance().addMapLayer(capa)

        lineas = ["<b>Predio reconstruido.</b>",
                  "Area: {:.4f} ha &nbsp;·&nbsp; Perimetro: {:.2f} m"
                  .format(pol.area_ha, pol.cierre.perimetro),
                  str(pol.cierre)]
        lineas += ["<span style='color:#b26a00'>· {}</span>".format(a)
                   for a in pol.avisos]
        self.lblResultado.setText("<br>".join(lineas))

    def _crear_capa(self, pol, crs):
        capa = QgsVectorLayer("Polygon?crs={}".format(crs.authid()),
                              "Predio reconstruido", "memory")
        dp = capa.dataProvider()
        dp.addAttributes([
            QgsField("area_ha", QVariant_Double),
            QgsField("perimetro", QVariant_Double),
            QgsField("declinacion", QVariant_Double),
            QgsField("convergencia", QVariant_Double),
            QgsField("cierre_m", QVariant_Double),
            QgsField("origen", QVariant_String),
        ])
        capa.updateFields()
        f = QgsFeature(capa.fields())
        f.setGeometry(QgsGeometry.fromPolygonXY(
            [[QgsPointXY(e, n) for e, n in pol.vertices]]))
        f.setAttributes([
            round(pol.area_ha, 4), round(pol.cierre.perimetro, 3),
            pol.declinacion, pol.convergencia, round(pol.cierre.lineal, 3),
            "Reconstruido desde memoria descriptiva "
            "(compensada)" if pol.compensada else
            "Reconstruido desde memoria descriptiva",
        ])
        dp.addFeature(f)
        capa.updateExtents()
        return capa


def instalar(dialogo, indice=3):
    """
    Inserta la pestaña en el dialogo de Memoria Descriptiva.

    Se llama desde MemoriaDescriptivaDialog.__init__, igual que
    _crear_tab_modo y _crear_tab_campos. Si algo falla, el dialogo debe
    seguir abriendo: esta pestaña es opcional, la generacion de memorias
    no depende de ella.
    """
    try:
        tab = TabReconstruccion(dialogo)
        dialogo.tabReconstruccion = tab
        dialogo.tabWidget.insertTab(indice, tab, "\U0001F4D0 Reconstruir predio")
        return tab
    except Exception as e:
        print("Aviso: no se pudo crear la pestaña Reconstruir predio: "
              "{}".format(e))
        return None
