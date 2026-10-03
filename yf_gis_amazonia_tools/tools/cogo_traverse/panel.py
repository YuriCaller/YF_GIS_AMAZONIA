# -*- coding: utf-8 -*-
"""
CogoPanel — panel flotante para digitalizar una poligonal en vivo por
azimut/distancia (COGO), estilo "Traverse" de ArcGIS Pro.

Es la capa de interacción: no calcula nada por su cuenta. Todo el
parseo, el recorrido de la poligonal, el error de cierre y la
compensación Bowditch se delegan a core/poligonal.py — el mismo motor
que ya usa "Reconstruir predio" en Memoria Descriptiva. Este panel es
simplemente una segunda puerta de entrada a ese motor: en vez de pegar
una tabla completa, se cargan los lados uno por uno y se ve la figura
crecer en el mapa.

Autor: Yuri F. Caller Cordova — TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox,
    QCheckBox, QGroupBox, QDoubleSpinBox,
)
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsField,
    QgsPointXY,
)

from ...core.qt_compat import QVariant_Double, QVariant_Int, PolygonGeometry
from ...core.logger import log_info, log_error
from ...core import poligonal as P


class CogoPanel(QDockWidget):
    """Panel flotante que orquesta el trazado COGO en vivo."""

    def __init__(self, iface, map_tool, parent=None):
        super().__init__("COGO — Poligonal en vivo", parent)
        self.iface = iface
        self.map_tool = map_tool
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)

        self._origen = None        # (E, N) o None
        self._segmentos = []       # lista de core.poligonal.Segmento
        self._pol_actual = None    # ultimo core.poligonal.Poligonal calculado
        self._cerrada = False

        self._construir_ui()
        self._conectar_senales()
        self._refrescar_estado()

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _construir_ui(self):
        cont = QWidget()
        layout = QVBoxLayout(cont)

        # ── Origen ────────────────────────────────────────────────
        grp_origen = QGroupBox("1. Origen")
        f_origen = QVBoxLayout(grp_origen)
        self.lblOrigen = QLabel("Sin fijar")
        self.lblOrigen.setStyleSheet("font-weight: bold;")
        self.btnOrigenClic = QPushButton("Fijar con clic en el mapa")
        fila_manual = QHBoxLayout()
        self.txtOrigenE = QLineEdit()
        self.txtOrigenE.setPlaceholderText("Este (E)")
        self.txtOrigenN = QLineEdit()
        self.txtOrigenN.setPlaceholderText("Norte (N)")
        self.btnOrigenManual = QPushButton("Usar")
        fila_manual.addWidget(self.txtOrigenE)
        fila_manual.addWidget(self.txtOrigenN)
        fila_manual.addWidget(self.btnOrigenManual)
        f_origen.addWidget(self.lblOrigen)
        f_origen.addWidget(self.btnOrigenClic)
        f_origen.addLayout(fila_manual)
        layout.addWidget(grp_origen)

        # ── Corrección de azimut ─────────────────────────────────
        grp_correccion = QGroupBox("Corrección (opcional)")
        f_corr = QFormLayout(grp_correccion)
        self.spnDeclinacion = QDoubleSpinBox()
        self.spnDeclinacion.setRange(-30.0, 30.0)
        self.spnDeclinacion.setDecimals(2)
        self.spnDeclinacion.setSuffix(" °")
        self.spnDeclinacion.setToolTip(
            "Declinación magnética. Con signo: Oeste es negativa en Perú.\n"
            "Déjala en 0 si ya trabajas en azimut verdadero/cuadrícula.")
        self.spnConvergencia = QDoubleSpinBox()
        self.spnConvergencia.setRange(-10.0, 10.0)
        self.spnConvergencia.setDecimals(2)
        self.spnConvergencia.setSuffix(" °")
        self.spnConvergencia.setToolTip(
            "Convergencia de meridiano. Déjala en 0 si trabajas en Norte "
            "verdadero.")
        f_corr.addRow("Declinación:", self.spnDeclinacion)
        f_corr.addRow("Convergencia:", self.spnConvergencia)
        layout.addWidget(grp_correccion)

        # ── Lado nuevo ────────────────────────────────────────────
        grp_lado = QGroupBox("2. Agregar lado")
        f_lado = QFormLayout(grp_lado)
        self.txtAzimut = QLineEdit()
        self.txtAzimut.setPlaceholderText("253°15'30\"  ó  N 4°44' W")
        self.txtDistancia = QLineEdit()
        self.txtDistancia.setPlaceholderText("metros, ej. 120.50")
        f_lado.addRow("Azimut / Rumbo:", self.txtAzimut)
        f_lado.addRow("Distancia:", self.txtDistancia)

        fila_botones_lado = QHBoxLayout()
        self.btnAgregar = QPushButton("Agregar lado")
        self.btnDeshacer = QPushButton("Deshacer último")
        fila_botones_lado.addWidget(self.btnAgregar)
        fila_botones_lado.addWidget(self.btnDeshacer)
        f_lado.addRow(fila_botones_lado)
        layout.addWidget(grp_lado)

        # ── Lista de lados ────────────────────────────────────────
        self.lista = QListWidget()
        self.lista.setMaximumHeight(140)
        layout.addWidget(self.lista)

        # ── Estado / cierre ───────────────────────────────────────
        self.lblEstado = QLabel("")
        self.lblEstado.setWordWrap(True)
        layout.addWidget(self.lblEstado)

        # ── Acciones finales ──────────────────────────────────────
        grp_final = QGroupBox("3. Cerrar y guardar")
        f_final = QVBoxLayout(grp_final)
        self.btnCerrar = QPushButton("Cerrar figura")
        self.chkCompensar = QCheckBox("Compensar cierre (Bowditch) al guardar")
        self.chkForzarCompensar = QCheckBox(
            "Forzar compensación aunque el cierre esté fuera de tolerancia")
        self.btnGuardar = QPushButton("Guardar geometría")
        self.btnCancelar = QPushButton("Cancelar / reiniciar")
        f_final.addWidget(self.btnCerrar)
        f_final.addWidget(self.chkCompensar)
        f_final.addWidget(self.chkForzarCompensar)
        f_final.addWidget(self.btnGuardar)
        f_final.addWidget(self.btnCancelar)
        layout.addWidget(grp_final)

        layout.addStretch()
        cont.setLayout(layout)
        self.setWidget(cont)

    def _conectar_senales(self):
        self.btnOrigenClic.clicked.connect(self.map_tool.pedir_origen_por_clic)
        self.btnOrigenManual.clicked.connect(self._usar_origen_manual)
        self.map_tool.origen_fijado.connect(self._on_origen_fijado)
        self.map_tool.herramienta_desactivada.connect(self._on_herramienta_desactivada)

        self.btnAgregar.clicked.connect(self._agregar_lado)
        self.txtDistancia.returnPressed.connect(self._agregar_lado)
        self.txtAzimut.returnPressed.connect(
            lambda: self.txtDistancia.setFocus())
        self.btnDeshacer.clicked.connect(self._deshacer_lado)

        self.btnCerrar.clicked.connect(self._cerrar_figura)
        self.btnGuardar.clicked.connect(self._guardar_geometria)
        self.btnCancelar.clicked.connect(self.reiniciar)

    # ------------------------------------------------------------------
    # Origen
    # ------------------------------------------------------------------

    def _on_origen_fijado(self, x, y):
        self._origen = (x, y)
        self.txtOrigenE.setText(f"{x:.3f}")
        self.txtOrigenN.setText(f"{y:.3f}")
        self._refrescar_estado()

    def _usar_origen_manual(self):
        try:
            x = float(self.txtOrigenE.text().replace(",", "."))
            y = float(self.txtOrigenN.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(
                self, "COGO", "Coordenadas de origen inválidas.")
            return
        self._origen = (x, y)
        self.map_tool.fijar_origen_programatico(x, y)
        self._refrescar_estado()

    def _on_herramienta_desactivada(self):
        # El usuario cambió a otra herramienta de QGIS mientras
        # esperábamos el clic de origen. No perdemos nada — solo
        # dejamos de esperar el clic.
        pass

    # ------------------------------------------------------------------
    # Lados
    # ------------------------------------------------------------------

    def _agregar_lado(self):
        if self._origen is None:
            QMessageBox.warning(
                self, "COGO",
                "Primero fija el origen (clic en el mapa o coordenadas "
                "manuales).")
            return
        if self._cerrada:
            QMessageBox.information(
                self, "COGO",
                "La figura ya está cerrada. Usa \"Cancelar / reiniciar\" "
                "para empezar una nueva.")
            return

        try:
            azimut = P.parse_azimut(self.txtAzimut.text())
            distancia = P.parse_distancia(self.txtDistancia.text())
        except ValueError as e:
            QMessageBox.warning(self, "COGO", str(e))
            return

        if azimut is None:
            QMessageBox.warning(
                self, "COGO",
                "El COGO en vivo necesita azimut en cada lado (no admite "
                "linderos naturales sin azimut).")
            return

        self._segmentos.append(P.Segmento(distancia=distancia, azimut=azimut))
        self.txtAzimut.clear()
        self.txtDistancia.clear()
        self.txtAzimut.setFocus()
        self._recalcular(cerrar=False)
        self._agregar_fila_lista(self._segmentos[-1])

    def _agregar_fila_lista(self, seg):
        self.lista.addItem(
            f"Lado {self.lista.count() + 1}:  {seg.gms}  ({seg.rumbo})  —  "
            f"{seg.distancia:.2f} m")

    def _deshacer_lado(self):
        if self._cerrada:
            # deshacer el "cierre" simplemente vuelve a estado abierto
            self._cerrada = False
            self._recalcular(cerrar=False)
            return
        if not self._segmentos:
            return
        self._segmentos.pop()
        item = self.lista.takeItem(self.lista.count() - 1)
        del item
        self._recalcular(cerrar=False)

    # ------------------------------------------------------------------
    # Cálculo / dibujo en vivo
    # ------------------------------------------------------------------

    def _declinacion(self):
        return self.spnDeclinacion.value()

    def _convergencia(self):
        return self.spnConvergencia.value()

    def _recalcular(self, cerrar):
        if self._origen is None or not self._segmentos:
            self._pol_actual = None
            self.map_tool.mostrar_vertices([], cerrado=True)
            self._refrescar_estado()
            return

        try:
            self._pol_actual = P.poligonal_a_poligono(
                self._origen, self._segmentos,
                declinacion=self._declinacion(),
                convergencia=self._convergencia(),
                cerrar=cerrar)
        except ValueError as e:
            QMessageBox.warning(self, "COGO", str(e))
            return

        self.map_tool.mostrar_vertices(self._pol_actual.vertices, cerrado=cerrar)
        self._cerrada = cerrar
        self._refrescar_estado()

    def _cerrar_figura(self):
        if self._origen is None or len(self._segmentos) < 3:
            QMessageBox.warning(
                self, "COGO",
                "Se necesitan al menos 3 lados para cerrar una figura.")
            return
        self._recalcular(cerrar=True)

    def _refrescar_estado(self):
        if self._origen is None:
            self.lblOrigen.setText("Sin fijar")
        else:
            self.lblOrigen.setText(
                f"E {self._origen[0]:.3f}   N {self._origen[1]:.3f}")

        if self._pol_actual is None:
            self.lblEstado.setText(
                "Agrega lados para ver el perímetro y, al cerrar la "
                "figura, el error de cierre y el área.")
            return

        pol = self._pol_actual
        texto = f"Perímetro: {pol.cierre.perimetro:.2f} m"
        if self._cerrada:
            texto += f"\nÁrea: {pol.area:.2f} m²  ({pol.area_ha:.4f} ha)"
            texto += f"\nCierre: {pol.cierre}"
            if pol.cierre.acepta():
                texto += "  ✔ dentro de tolerancia (1:1000)"
            else:
                texto += "  ⚠ fuera de tolerancia"
        else:
            texto += "\n(pendiente de cerrar — línea roja punteada = cierre)"
        if pol.avisos:
            texto += "\n\n" + "\n".join(pol.avisos)
        self.lblEstado.setText(texto)

    # ------------------------------------------------------------------
    # Guardar
    # ------------------------------------------------------------------

    def _guardar_geometria(self):
        if not self._cerrada or self._pol_actual is None:
            QMessageBox.warning(
                self, "COGO", "Cierra la figura antes de guardarla.")
            return

        pol = self._pol_actual
        if self.chkCompensar.isChecked():
            try:
                pol = P.compensar_bowditch(
                    pol, forzar=self.chkForzarCompensar.isChecked())
            except ValueError as e:
                QMessageBox.warning(self, "COGO", str(e))
                return

        vertices = pol.vertices
        geom = QgsGeometry.fromPolygonXY([[
            QgsPointXY(e, n) for e, n in vertices
        ]])
        if not geom.isGeosValid():
            log_error("COGO: geometría resultante inválida al guardar")
            QMessageBox.warning(
                self, "COGO",
                "La geometría resultante no es válida (¿lados cruzados?). "
                "Revisa los azimuts y distancias antes de guardar.")
            return

        capa = self._capa_destino()
        if capa is None:
            return

        feat = QgsFeature(capa.fields())
        feat.setGeometry(geom)
        for nombre, valor in (
            ("area_m2", pol.area),
            ("area_ha", pol.area_ha),
            ("perimetro", pol.cierre.perimetro),
            ("compensada", 1 if pol.compensada else 0),
        ):
            idx = capa.fields().indexFromName(nombre)
            if idx >= 0:
                feat.setAttribute(idx, valor)

        capa.startEditing()
        ok = capa.addFeature(feat)
        capa.commitChanges()
        if not ok:
            QMessageBox.warning(self, "COGO", "No se pudo agregar la geometría.")
            return

        capa.triggerRepaint()
        log_info("COGO: poligonal guardada en '{}'".format(capa.name()))
        QMessageBox.information(
            self, "COGO",
            f"Geometría guardada en la capa \"{capa.name()}\".")
        self.reiniciar()

    def _capa_destino(self):
        """Usa la capa activa si es un polígono editable; si no, crea una
        capa temporal nueva ('memoria') para no perder el trabajo."""
        activa = self.iface.activeLayer()
        if (isinstance(activa, QgsVectorLayer)
                and activa.geometryType() == PolygonGeometry
                and activa.crs() == QgsProject.instance().crs()):
            return activa

        crs = QgsProject.instance().crs()
        capa = QgsVectorLayer(
            f"Polygon?crs={crs.authid()}", "COGO_poligonal", "memory")
        capa.dataProvider().addAttributes([
            QgsField("area_m2", QVariant_Double),
            QgsField("area_ha", QVariant_Double),
            QgsField("perimetro", QVariant_Double),
            QgsField("compensada", QVariant_Int),
        ])
        capa.updateFields()
        QgsProject.instance().addMapLayer(capa)
        log_info("COGO: creada capa temporal 'COGO_poligonal' (memoria)")
        return capa

    # ------------------------------------------------------------------
    # Reinicio / cierre del panel
    # ------------------------------------------------------------------

    def reiniciar(self):
        self._origen = None
        self._segmentos = []
        self._pol_actual = None
        self._cerrada = False
        self.txtOrigenE.clear()
        self.txtOrigenN.clear()
        self.txtAzimut.clear()
        self.txtDistancia.clear()
        self.lista.clear()
        self.map_tool.limpiar()
        self._refrescar_estado()

    def closeEvent(self, event):
        self.map_tool.limpiar()
        super().closeEvent(event)
