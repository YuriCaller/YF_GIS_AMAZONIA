# -*- coding: utf-8 -*-
"""
Polygon Divider — Diálogo principal.

Implementa la interfaz validada en el mockup: selección de modo
(por área / N partes iguales / por porcentajes), control de ángulo de
corte (spinbox + trazado en canvas), configuración de capa resultado
(campo base para el nombre, toggle de etiquetado), vista previa y
aplicación de la división.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import os
import math

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox,
    QTabWidget, QWidget, QCheckBox, QMessageBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QFileDialog, QAbstractSpinBox,
)
from qgis.PyQt.QtGui import QFont

from qgis.core import (
    QgsProject, QgsWkbTypes, QgsField, QgsVectorLayer,
)

from ...core.logger import log_info, log_warning, log_error
from . import division_engine as engine
from . import output_engine as outengine
from .map_tool import PolygonDividerMapTool


MODO_AREA = "area"
MODO_PARTES = "partes"
MODO_PORCENTAJE = "porcentaje"


class PolygonDividerDialog(QDialog):
    """Diálogo principal de la herramienta Polygon Divider."""

    def __init__(self, iface, layer, feature, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.layer = layer
        self.feature = feature
        self.canvas = iface.mapCanvas()

        self._geom_original = feature.geometry()
        self._angulo_actual_rad = 0.0
        self._fragmentos_calculados = None  # último resultado calculado
        self._indices_multiparte = []  # fracciones con geometría no contigua

        self._map_tool = None
        self._tool_anterior = None

        self.setWindowTitle("YF · Polygon Divider")
        self.setMinimumWidth(420)

        self._build_ui()
        self._conectar_senales()
        self._poblar_combo_campos()
        self._actualizar_resumen_area()

    # ------------------------------------------------------------------
    # Construcción UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Resumen de capa / polígono ──
        grp_resumen = QGroupBox("Polígono seleccionado")
        f_resumen = QFormLayout()
        self.lbl_capa = QLabel(self.layer.name())
        self.lbl_area_total = QLabel("—")
        f_resumen.addRow("Capa activa:", self.lbl_capa)
        f_resumen.addRow("Área total:", self.lbl_area_total)
        grp_resumen.setLayout(f_resumen)
        layout.addWidget(grp_resumen)

        # ── Modo de división (tabs) ──
        grp_modo = QGroupBox("Modo de división")
        v_modo = QVBoxLayout()

        self.tabs_modo = QTabWidget()
        self.tabs_modo.addTab(self._tab_por_area(), "Por área exacta")
        self.tabs_modo.addTab(self._tab_n_partes(), "N partes iguales")
        self.tabs_modo.addTab(self._tab_porcentajes(), "Por porcentajes")
        v_modo.addWidget(self.tabs_modo)

        grp_modo.setLayout(v_modo)
        layout.addWidget(grp_modo)

        # ── Ángulo de corte ──
        grp_angulo = QGroupBox("Ángulo de la línea de corte")
        h_angulo = QHBoxLayout()

        self.spin_angulo = QDoubleSpinBox()
        self.spin_angulo.setRange(0.0, 179.99)
        self.spin_angulo.setDecimals(1)
        self.spin_angulo.setSuffix(" °")
        self.spin_angulo.setSingleStep(1.0)
        self.spin_angulo.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)

        self.btn_trazar = QPushButton("✂  Trazar línea en canvas")
        self.btn_trazar.setCheckable(True)

        h_angulo.addWidget(QLabel("Ángulo:"))
        h_angulo.addWidget(self.spin_angulo)
        h_angulo.addWidget(self.btn_trazar)
        grp_angulo.setLayout(h_angulo)
        layout.addWidget(grp_angulo)

        self.lbl_estado_linea = QLabel("Sin línea definida — usa el spinbox o traza en canvas.")
        self.lbl_estado_linea.setStyleSheet("color: #8a6d00;")
        layout.addWidget(self.lbl_estado_linea)

        # ── Capa resultado ──
        grp_salida = QGroupBox("Capa resultado")
        v_salida = QVBoxLayout()

        self.chk_capa_separada = QCheckBox("Guardar resultado en GeoPackage (recomendado para catastro)")
        self.chk_capa_separada.setChecked(True)
        v_salida.addWidget(self.chk_capa_separada)
        nota_toggle = QLabel("Sin marcar: los fragmentos se añaden como capa temporal en memoria (no se guarda a disco).")
        nota_toggle.setWordWrap(True)
        nota_toggle.setStyleSheet("color: #666; font-size: 10px;")
        v_salida.addWidget(nota_toggle)

        f_salida = QFormLayout()
        self.combo_campo_base = QComboBox()
        f_salida.addRow("Campo nombre base:", self.combo_campo_base)

        self.lbl_preview_nombre = QLabel("—")
        self.lbl_preview_nombre.setStyleSheet("color: #3a7a3a; font-family: monospace;")
        f_salida.addRow("Nombre resultante:", self.lbl_preview_nombre)

        v_salida.addLayout(f_salida)

        self.chk_etiquetar = QCheckBox("Etiquetar fracciones automáticamente")
        self.chk_etiquetar.setChecked(True)
        v_salida.addWidget(self.chk_etiquetar)

        h_carpeta = QHBoxLayout()
        self.txt_carpeta = QLineEdit()
        self.txt_carpeta.setReadOnly(True)
        self.btn_carpeta = QPushButton("Elegir carpeta…")
        h_carpeta.addWidget(QLabel("Guardar en:"))
        h_carpeta.addWidget(self.txt_carpeta)
        h_carpeta.addWidget(self.btn_carpeta)
        v_salida.addLayout(h_carpeta)

        grp_salida.setLayout(v_salida)
        layout.addWidget(grp_salida)

        # ── Acciones ──
        h_acciones = QHBoxLayout()
        self.btn_preview = QPushButton("👁  Vista previa")
        self.btn_aplicar = QPushButton("✂  Aplicar división")
        self.btn_aplicar.setEnabled(False)
        self.btn_cerrar = QPushButton("Cerrar")

        h_acciones.addWidget(self.btn_preview)
        h_acciones.addWidget(self.btn_aplicar)
        h_acciones.addWidget(self.btn_cerrar)
        layout.addLayout(h_acciones)

        self._toggle_modo_salida()

    def _tab_por_area(self):
        w = QWidget()
        f = QFormLayout(w)
        self.spin_area_objetivo = QDoubleSpinBox()
        self.spin_area_objetivo.setRange(0.0001, 1_000_000.0)
        self.spin_area_objetivo.setDecimals(4)
        self.spin_area_objetivo.setSuffix(" ha")
        self.spin_area_objetivo.setValue(1.0)
        f.addRow("Área del primer fragmento:", self.spin_area_objetivo)
        nota = QLabel(
            "El primer fragmento (lado izquierdo de la línea, según su "
            "dirección) tendrá exactamente esta área. El resto queda en "
            "el segundo fragmento."
        )
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #666; font-size: 10px;")
        f.addRow(nota)
        return w

    def _tab_n_partes(self):
        w = QWidget()
        f = QFormLayout(w)
        self.spin_n_partes = QSpinBox()
        self.spin_n_partes.setRange(2, 50)
        self.spin_n_partes.setValue(2)
        f.addRow("Número de partes:", self.spin_n_partes)
        nota = QLabel(
            "Genera N fragmentos de área igual, todos cortados con líneas "
            "paralelas en la dirección definida."
        )
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #666; font-size: 10px;")
        f.addRow(nota)
        return w

    def _tab_porcentajes(self):
        w = QWidget()
        v = QVBoxLayout(w)

        h_n = QHBoxLayout()
        self.spin_n_porcentajes = QSpinBox()
        self.spin_n_porcentajes.setRange(2, 10)
        self.spin_n_porcentajes.setValue(2)
        h_n.addWidget(QLabel("Número de fracciones:"))
        h_n.addWidget(self.spin_n_porcentajes)
        v.addLayout(h_n)

        self.tabla_porcentajes = QTableWidget(2, 1)
        self.tabla_porcentajes.setHorizontalHeaderLabels(["Porcentaje (%)"])
        self.tabla_porcentajes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_porcentajes.setItem(0, 0, QTableWidgetItem("50"))
        self.tabla_porcentajes.setItem(1, 0, QTableWidgetItem("50"))
        v.addWidget(self.tabla_porcentajes)

        self.lbl_suma_porcentajes = QLabel("Suma: 100.0 %")
        v.addWidget(self.lbl_suma_porcentajes)

        nota = QLabel("Los porcentajes deben sumar exactamente 100%.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #666; font-size: 10px;")
        v.addWidget(nota)

        return w

    # ------------------------------------------------------------------
    # Señales
    # ------------------------------------------------------------------

    def _conectar_senales(self):
        self.spin_angulo.valueChanged.connect(self._on_angulo_spinbox_cambiado)
        self.btn_trazar.toggled.connect(self._on_trazar_toggled)
        self.chk_capa_separada.toggled.connect(self._toggle_modo_salida)
        self.combo_campo_base.currentTextChanged.connect(self._actualizar_preview_nombre)
        self.btn_carpeta.clicked.connect(self._elegir_carpeta)
        self.btn_preview.clicked.connect(self._on_preview_clicked)
        self.btn_aplicar.clicked.connect(self._on_aplicar_clicked)
        self.btn_cerrar.clicked.connect(self._on_cerrar)

        self.tabs_modo.currentChanged.connect(lambda _i: self._invalidar_resultado())
        self.spin_area_objetivo.valueChanged.connect(self._invalidar_resultado)
        self.spin_n_partes.valueChanged.connect(self._invalidar_resultado)
        self.spin_n_porcentajes.valueChanged.connect(self._on_n_porcentajes_cambiado)
        self.tabla_porcentajes.itemChanged.connect(self._actualizar_suma_porcentajes)

    # ------------------------------------------------------------------
    # Helpers de estado
    # ------------------------------------------------------------------

    def _modo_actual(self):
        idx = self.tabs_modo.currentIndex()
        return [MODO_AREA, MODO_PARTES, MODO_PORCENTAJE][idx]

    def _actualizar_resumen_area(self):
        area_m2 = self._geom_original.area()
        area_ha = area_m2 / 10000.0
        self.lbl_area_total.setText(f"{area_ha:.4f} ha  ({area_m2:.2f} m²)")
        # Limitar el spinbox de área objetivo al área total disponible
        self.spin_area_objetivo.setMaximum(max(area_ha - 0.0001, 0.0001))

    def _poblar_combo_campos(self):
        self.combo_campo_base.clear()
        CAMPOS_EXCLUIDOS = {"fid", "ogc_fid", "objectid"}

        campos_texto = [
            f.name() for f in self.layer.fields()
            if f.type() in (10,) and f.name().lower() not in CAMPOS_EXCLUIDOS
        ]
        if not campos_texto:
            campos_texto = [
                f.name() for f in self.layer.fields()
                if f.name().lower() not in CAMPOS_EXCLUIDOS
            ]
        if not campos_texto:
            # Caso extremo: la capa solo tiene 'fid'. Se permite igual,
            # generar_nombre_capa cae a su fallback con ID + timestamp.
            campos_texto = [f.name() for f in self.layer.fields()]
        self.combo_campo_base.addItems(campos_texto)
        self._actualizar_preview_nombre()

    def _toggle_modo_salida(self):
        habilitado = self.chk_capa_separada.isChecked()
        self.combo_campo_base.setEnabled(habilitado)
        self.chk_etiquetar.setEnabled(habilitado)
        self.txt_carpeta.setEnabled(habilitado)
        self.btn_carpeta.setEnabled(habilitado)
        self.lbl_preview_nombre.setEnabled(habilitado)
        if not habilitado:
            self.lbl_preview_nombre.setText("→ Se añadirá como capa temporal en memoria")

    def _invalidar_resultado(self):
        self._fragmentos_calculados = None
        self._indices_multiparte = []
        self.btn_aplicar.setEnabled(False)

    # ------------------------------------------------------------------
    # Ángulo / trazado en canvas
    # ------------------------------------------------------------------

    def _on_angulo_spinbox_cambiado(self, valor_grados):
        self._angulo_actual_rad = math.radians(valor_grados)
        self._invalidar_resultado()
        if self.btn_trazar.isChecked():
            # Sincronizar la línea dibujada en canvas con el spinbox
            self._redibujar_linea_desde_angulo()

    def _on_trazar_toggled(self, activo):
        if activo:
            self._activar_map_tool()
            self.lbl_estado_linea.setText(
                "Modo trazado activo: haz clic en el mapa para el punto inicial, "
                "luego otro clic para el punto final. Esc o clic derecho cancela."
            )
            self.lbl_estado_linea.setStyleSheet("color: #b35c00;")
        else:
            self._desactivar_map_tool()

    def _activar_map_tool(self):
        self._tool_anterior = self.canvas.mapTool()
        self._map_tool = PolygonDividerMapTool(self.canvas, self._geom_original)

        if self._modo_actual() == MODO_AREA:
            area_objetivo_m2 = self.spin_area_objetivo.value() * 10000.0
            self._map_tool.set_area_objetivo_preview(area_objetivo_m2)

        self._map_tool.lineaActualizada.connect(self._on_linea_actualizada_canvas)
        self._map_tool.lineaCompletada.connect(self._on_linea_completada_canvas)
        self._map_tool.trazadoCancelado.connect(self._on_trazado_cancelado_canvas)

        self.canvas.setMapTool(self._map_tool)

    def _desactivar_map_tool(self):
        if self._map_tool is not None:
            self._map_tool.limpiar()
            try:
                self._map_tool.lineaActualizada.disconnect()
                self._map_tool.lineaCompletada.disconnect()
                self._map_tool.trazadoCancelado.disconnect()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            if self.canvas.mapTool() is self._map_tool:
                if self._tool_anterior is not None:
                    self.canvas.setMapTool(self._tool_anterior)
                else:
                    self.canvas.unsetMapTool(self._map_tool)
            self._map_tool = None

    def _on_linea_actualizada_canvas(self, angulo_rad):
        self._angulo_actual_rad = angulo_rad
        self.spin_angulo.blockSignals(True)
        self.spin_angulo.setValue(math.degrees(angulo_rad) % 180)
        self.spin_angulo.blockSignals(False)

    def _on_linea_completada_canvas(self, angulo_rad):
        self._angulo_actual_rad = angulo_rad
        self.spin_angulo.blockSignals(True)
        self.spin_angulo.setValue(math.degrees(angulo_rad) % 180)
        self.spin_angulo.blockSignals(False)
        self.lbl_estado_linea.setText("✓ Línea definida correctamente.")
        self.lbl_estado_linea.setStyleSheet("color: #2e7d32;")
        self.btn_trazar.setChecked(False)

    def _on_trazado_cancelado_canvas(self):
        self.lbl_estado_linea.setText("Trazado cancelado.")
        self.lbl_estado_linea.setStyleSheet("color: #8a6d00;")

    def _redibujar_linea_desde_angulo(self):
        if self._map_tool is None:
            return
        # Sin geometría de puntos clicados, solo se sincroniza el ángulo
        # interno; la línea visual se actualizará en el próximo movimiento
        # del mouse. Esto evita lógica duplicada de dibujo.
        self._map_tool._angulo_rad = self._angulo_actual_rad

    # ------------------------------------------------------------------
    # Tabla de porcentajes
    # ------------------------------------------------------------------

    def _on_n_porcentajes_cambiado(self, n):
        actual = self.tabla_porcentajes.rowCount()
        self.tabla_porcentajes.blockSignals(True)
        if n > actual:
            valor_default = round(100.0 / n, 1)
            for i in range(actual, n):
                self.tabla_porcentajes.insertRow(i)
                self.tabla_porcentajes.setItem(i, 0, QTableWidgetItem(str(valor_default)))
        elif n < actual:
            for i in range(actual - 1, n - 1, -1):
                self.tabla_porcentajes.removeRow(i)
        self.tabla_porcentajes.blockSignals(False)
        self._actualizar_suma_porcentajes()
        self._invalidar_resultado()

    def _leer_porcentajes(self):
        valores = []
        for i in range(self.tabla_porcentajes.rowCount()):
            item = self.tabla_porcentajes.item(i, 0)
            texto = item.text().strip() if item else ""
            try:
                valores.append(float(texto.replace(",", ".")))
            except ValueError:
                valores.append(0.0)
        return valores

    def _actualizar_suma_porcentajes(self, *_args):
        valores = self._leer_porcentajes()
        suma = sum(valores)
        self.lbl_suma_porcentajes.setText(f"Suma: {suma:.1f} %")
        if abs(suma - 100.0) > 0.01:
            self.lbl_suma_porcentajes.setStyleSheet("color: #c62828; font-weight: bold;")
        else:
            self.lbl_suma_porcentajes.setStyleSheet("color: #2e7d32;")
        self._invalidar_resultado()

    # ------------------------------------------------------------------
    # Nombre de capa resultado
    # ------------------------------------------------------------------

    def _sufijo_actual(self):
        modo = self._modo_actual()
        if modo == MODO_AREA:
            return outengine.sufijo_para_modo(MODO_AREA, self.spin_area_objetivo.value())
        if modo == MODO_PARTES:
            return outengine.sufijo_para_modo(MODO_PARTES, self.spin_n_partes.value())
        return outengine.sufijo_para_modo(MODO_PORCENTAJE, None)

    def _actualizar_preview_nombre(self, *_args):
        campo = self.combo_campo_base.currentText()
        sufijo = self._sufijo_actual()
        nombre = outengine.generar_nombre_capa(
            self.feature, campo, sufijo, self.feature.id()
        )
        self.lbl_preview_nombre.setText(f"{nombre}.gpkg")

    def _elegir_carpeta(self):
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta de destino", self.txt_carpeta.text() or os.path.expanduser("~")
        )
        if carpeta:
            self.txt_carpeta.setText(carpeta)

    # ------------------------------------------------------------------
    # Cálculo (compartido por Preview y Aplicar)
    # ------------------------------------------------------------------

    def _calcular_fragmentos(self):
        """
        Ejecuta el motor de división según el modo activo.
        Retorna (lista_de_QgsGeometry, lista_indices_multiparte).
        Lanza DivisionError (mostrado al usuario) si algo falla.
        """
        modo = self._modo_actual()
        angulo = self._angulo_actual_rad

        if modo == MODO_AREA:
            area_objetivo_m2 = self.spin_area_objetivo.value() * 10000.0
            frag_a, frag_b, _, _, es_multiparte = engine.calcular_corte_por_area(
                self._geom_original, angulo, area_objetivo_m2
            )
            indices = []
            if frag_a.isMultipart():
                indices.append(1)
            if frag_b.isMultipart():
                indices.append(2)
            return [frag_a, frag_b], indices

        if modo == MODO_PARTES:
            n = self.spin_n_partes.value()
            return engine.dividir_n_partes_iguales(self._geom_original, angulo, n)

        if modo == MODO_PORCENTAJE:
            porcentajes = self._leer_porcentajes()
            if abs(sum(porcentajes) - 100.0) > 0.01:
                raise engine.DivisionError(
                    f"Los porcentajes deben sumar 100%. Suma actual: "
                    f"{sum(porcentajes):.1f}%."
                )
            return engine.dividir_por_porcentajes(self._geom_original, angulo, porcentajes)

        raise engine.DivisionError("Modo de división no reconocido.")

    # ------------------------------------------------------------------
    # Vista previa
    # ------------------------------------------------------------------

    def _on_preview_clicked(self):
        try:
            fragmentos, indices_multiparte = self._calcular_fragmentos()
        except engine.DivisionError as e:
            QMessageBox.warning(self, "YF · Polygon Divider", str(e))
            return
        except Exception as e:
            log_error(f"Polygon Divider: error inesperado en preview: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, "YF · Polygon Divider",
                f"Error inesperado al calcular la vista previa:\n\n{e}"
            )
            return

        self._fragmentos_calculados = fragmentos
        self._indices_multiparte = indices_multiparte
        self._mostrar_preview_canvas(fragmentos)
        self.btn_aplicar.setEnabled(True)

        resumen = "\n".join(
            f"  Fracción {i+1}: {f.area()/10000.0:.4f} ha "
            f"({f.area()/self._geom_original.area()*100:.1f}%)"
            + (" ⚠ NO CONTIGUA" if (i + 1) in indices_multiparte else "")
            for i, f in enumerate(fragmentos)
        )

        if indices_multiparte:
            fracciones_txt = ", ".join(str(i) for i in indices_multiparte)
            self.lbl_estado_linea.setText(
                f"⚠ Vista previa calculada — {len(fragmentos)} fragmentos. "
                f"La(s) fracción(es) {fracciones_txt} quedaron como ISLAS "
                f"SEPARADAS (el polígono no es convexo en esta dirección)."
            )
            self.lbl_estado_linea.setStyleSheet("color: #c62828; font-weight: bold;")
            QMessageBox.warning(
                self,
                "YF · Polygon Divider — Geometría no contigua",
                f"Con este ángulo de corte, la(s) fracción(es) "
                f"{fracciones_txt} resultaron formadas por varias piezas "
                f"separadas (islas) en lugar de un solo polígono continuo.\n\n"
                f"El área total sigue siendo exacta, pero cada una de esas "
                f"fracciones quedará como un multipolígono. Esto ocurre "
                f"porque el polígono original tiene concavidades y la línea "
                f"de corte las atraviesa.\n\n"
                f"Puedes continuar y aplicar la división así (el resultado "
                f"es geométricamente válido), o cerrar este aviso y probar "
                f"con otro ángulo de línea para obtener fracciones contiguas."
            )
        else:
            self.lbl_estado_linea.setText(
                f"✓ Vista previa calculada — {len(fragmentos)} fragmentos."
            )
            self.lbl_estado_linea.setStyleSheet("color: #2e7d32;")

        log_info(f"Polygon Divider: vista previa generada.\n{resumen}")

    def _mostrar_preview_canvas(self, fragmentos):
        """Dibuja los fragmentos resultantes en rubber bands amarillos temporales."""
        from qgis.gui import QgsRubberBand
        from qgis.PyQt.QtGui import QColor

        # Limpiar previews anteriores
        if hasattr(self, "_rbs_preview_dialogo"):
            for rb in self._rbs_preview_dialogo:
                self.canvas.scene().removeItem(rb)
        self._rbs_preview_dialogo = []

        colores = [
            QColor(74, 158, 202, 70), QColor(61, 184, 122, 70),
            QColor(155, 111, 212, 70), QColor(224, 92, 42, 70),
            QColor(240, 192, 64, 70),
        ]

        for i, frag in enumerate(fragmentos):
            rb = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
            color = colores[i % len(colores)]
            rb.setColor(color)
            rb.setFillColor(color)
            rb.setWidth(2)
            rb.setToGeometry(frag, None)
            self._rbs_preview_dialogo.append(rb)

        self.canvas.refresh()

    def _limpiar_preview_canvas(self):
        if hasattr(self, "_rbs_preview_dialogo"):
            for rb in self._rbs_preview_dialogo:
                self.canvas.scene().removeItem(rb)
            self._rbs_preview_dialogo = []
            self.canvas.refresh()

    # ------------------------------------------------------------------
    # Aplicar división
    # ------------------------------------------------------------------

    def _on_aplicar_clicked(self):
        if not self._fragmentos_calculados:
            QMessageBox.information(
                self, "YF · Polygon Divider",
                "Primero genera la vista previa para confirmar el resultado."
            )
            return

        crear_capa_separada = self.chk_capa_separada.isChecked()

        if crear_capa_separada and not self.txt_carpeta.text():
            QMessageBox.warning(
                self, "YF · Polygon Divider",
                "Elige una carpeta de destino para guardar la capa resultado."
            )
            return

        aviso_multiparte = ""
        if self._indices_multiparte:
            fracciones_txt = ", ".join(str(i) for i in self._indices_multiparte)
            aviso_multiparte = (
                f"\n\n⚠ ATENCIÓN: la(s) fracción(es) {fracciones_txt} quedarán "
                f"como geometría MULTIPARTE (varias islas separadas que suman "
                f"el área correcta, no un polígono continuo)."
            )

        if crear_capa_separada:
            texto_confirmacion = (
                f"Se generarán {len(self._fragmentos_calculados)} fragmentos.\n\n"
                f"Se creará una nueva capa GeoPackage en disco; el polígono "
                f"original permanecerá intacto."
                + aviso_multiparte
            )
        else:
            texto_confirmacion = (
                f"Se generarán {len(self._fragmentos_calculados)} fragmentos.\n\n"
                f"Los fragmentos se añadirán al proyecto como capa temporal "
                f"en memoria (no se guardará a disco). El polígono original "
                f"permanecerá intacto."
                + aviso_multiparte
            )

        respuesta = QMessageBox.question(
            self, "Confirmar división",
            texto_confirmacion,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            if crear_capa_separada:
                self._aplicar_capa_separada()
            else:
                self._aplicar_capa_memoria()
        except Exception as e:
            log_error(f"Polygon Divider: error al aplicar división: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, "YF · Polygon Divider",
                f"Ocurrió un error al aplicar la división:\n\n{e}"
            )

    def _aplicar_capa_separada(self):
        campos_resultado = outengine.construir_campos_resultado(self.layer.fields())
        nombre_base = self.lbl_preview_nombre.text().replace(".gpkg", "")

        capa_memoria = outengine.crear_capa_resultado(
            nombre_base, self.layer.crs(), campos_resultado
        )

        outengine.poblar_fragmentos(
            capa_memoria,
            self._fragmentos_calculados,
            self.feature,
            self._geom_original.area(),
            padre_id=self.feature.id(),
            etiquetar=self.chk_etiquetar.isChecked(),
        )

        ruta, capa_disco = outengine.guardar_a_geopackage(
            capa_memoria, self.txt_carpeta.text(), nombre_base
        )

        if ruta is None or capa_disco is None or not capa_disco.isValid():
            QMessageBox.critical(
                self, "YF · Polygon Divider",
                "No se pudo guardar la capa resultado en disco. "
                "Revisa permisos de la carpeta elegida."
            )
            return

        if self.chk_etiquetar.isChecked():
            outengine.aplicar_etiquetado_automatico(capa_disco)

        QgsProject.instance().addMapLayer(capa_disco)
        self._limpiar_preview_canvas()

        self.iface.messageBar().pushSuccess(
            "YF · Polygon Divider",
            f"{len(self._fragmentos_calculados)} fragmentos creados en "
            f"'{os.path.basename(ruta)}'. Polígono original intacto."
        )
        log_info(f"Polygon Divider: división aplicada — capa separada en {ruta}")
        self.close()

    def _aplicar_capa_memoria(self):
        """
        Crea los fragmentos como capa temporal en memoria y la añade al
        proyecto. No guarda nada a disco. El polígono original permanece
        intacto. El usuario puede guardar la capa manualmente después
        desde el panel de capas de QGIS (clic derecho → Exportar).
        """
        campos_resultado = outengine.construir_campos_resultado(self.layer.fields())
        nombre_base = self.lbl_preview_nombre.text().replace(".gpkg", "") + "_temp"

        capa_memoria = outengine.crear_capa_resultado(
            nombre_base, self.layer.crs(), campos_resultado
        )

        outengine.poblar_fragmentos(
            capa_memoria,
            self._fragmentos_calculados,
            self.feature,
            self._geom_original.area(),
            padre_id=self.feature.id(),
            etiquetar=self.chk_etiquetar.isChecked(),
        )

        if not capa_memoria.isValid() or capa_memoria.featureCount() == 0:
            QMessageBox.critical(
                self, "YF · Polygon Divider",
                "No se pudo crear la capa temporal en memoria."
            )
            return

        QgsProject.instance().addMapLayer(capa_memoria)
        self._limpiar_preview_canvas()

        self.iface.messageBar().pushSuccess(
            "YF · Polygon Divider",
            f"{len(self._fragmentos_calculados)} fragmentos creados como capa "
            f"temporal '{nombre_base}'. Polígono original intacto. "
            f"Guarda la capa manualmente si deseas persistirla."
        )
        log_info(
            f"Polygon Divider: división aplicada — capa temporal en memoria "
            f"'{nombre_base}' ({len(self._fragmentos_calculados)} fragmentos)."
        )
        self.close()

    def _aplicar_edicion_directa(self):
        if not self.layer.isEditable():
            self.layer.startEditing()

        campos = self.layer.fields()
        idx_fraccion = campos.indexFromName("fraccion")
        tiene_campos_control = idx_fraccion != -1

        if not tiene_campos_control:
            # Añadir campos de control mínimos si no existen, para no
            # perder trazabilidad incluso en edición directa.
            nuevos = outengine.construir_campos_resultado(campos)
            campos_a_agregar = [
                nuevos.field(i) for i in range(campos.count(), nuevos.count())
            ]
            self.layer.dataProvider().addAttributes(campos_a_agregar)
            self.layer.updateFields()

        area_total = self._geom_original.area()
        fecha_hoy = __import__("datetime").datetime.now().strftime("%Y-%m-%d")

        nuevas_features = []
        for i, frag in enumerate(self._fragmentos_calculados, start=1):
            from qgis.core import QgsFeature
            feat = QgsFeature(self.layer.fields())
            feat.setGeometry(frag)
            for campo in self.feature.fields().names():
                if campo.lower() in ("fid", "ogc_fid", "objectid"):
                    continue
                idx = feat.fields().indexFromName(campo)
                if idx != -1:
                    feat.setAttribute(idx, self.feature.attribute(campo))

            if self.layer.fields().indexFromName("fraccion") != -1:
                feat.setAttribute("fraccion", i)
                feat.setAttribute("area_ha", round(frag.area() / 10000.0, 4))
                feat.setAttribute("porcentaje", round(frag.area() / area_total * 100.0, 2))
                feat.setAttribute("fecha_division", fecha_hoy)
                feat.setAttribute("poligono_padre_id", str(self.feature.id()))

            nuevas_features.append(feat)

        self.layer.deleteFeature(self.feature.id())
        self.layer.addFeatures(nuevas_features)
        self.layer.commitChanges()
        self.layer.triggerRepaint()

        if self.chk_etiquetar.isChecked():
            outengine.aplicar_etiquetado_automatico(self.layer)

        self._limpiar_preview_canvas()

        self.iface.messageBar().pushSuccess(
            "YF · Polygon Divider",
            f"Polígono original reemplazado por {len(nuevas_features)} "
            f"fragmentos en '{self.layer.name()}'."
        )
        log_info("Polygon Divider: división aplicada — edición directa de capa.")
        self.close()

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------

    def _on_cerrar(self):
        self.close()

    def closeEvent(self, event):
        self._desactivar_map_tool()
        self._limpiar_preview_canvas()
        super().closeEvent(event)
