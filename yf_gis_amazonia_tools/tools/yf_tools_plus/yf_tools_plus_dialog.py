# -*- coding: utf-8 -*-
"""
/***************************************************************************
 YF_Tools_PlusDialog
                                 A QGIS plugin
 Diálogo principal del plugin.
                             -------------------
        begin                : 2025-04-21
        copyright            : (C) 2025 by Yuri Caller
        email                : yuricaller@gmail.com
 ****************************************************************************/
"""

import logging
import os
import json
# Compatibilidad PyQt5 / PyQt6 (QGIS 3.x y 4.x)
try:
    from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QSize
    from qgis.PyQt.QtWidgets import QDialog, QMessageBox, QFileDialog, QApplication
    from qgis.PyQt import uic
except ImportError:
    from PyQt6.QtCore import QSettings, QTranslator, QCoreApplication, QSize
    from PyQt6.QtWidgets import QDialog, QMessageBox, QFileDialog, QApplication
    from PyQt6 import uic
from qgis.core import (
    QgsMessageLog, Qgis, QgsProject, QgsMapLayerProxyModel, 
    QgsVectorLayer, QgsCoordinateReferenceSystem
)
from qgis.utils import iface

# Importar las clases de módulos
from .modules.excel_to_csv import ExcelToCsv
from .modules.table_to_polygon import TableToPolygon
from .modules.polygon_creator import PolygonCreator
from .modules.segmentator import Segmentator
from .modules.excel_exporter import ExcelExporter

# Cargar el archivo .ui
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'yf_tools_plus_dialog_base.ui'))

class YF_Tools_PlusDialog(QDialog, FORM_CLASS):
    """Diálogo principal del plugin YF Tools Plus."""

    def __init__(self, iface, parent=None):  # noqa: F811
        """Constructor."""
        super(YF_Tools_PlusDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.config_path = os.path.join(self.plugin_dir, 'config.json')
        
        # Inicializar clases de módulos
        self.excel_to_csv = ExcelToCsv()
        self.polygon_creator = PolygonCreator()
        self.segmentator = Segmentator()
        self.excel_exporter = ExcelExporter()
        
        # Conectar señales
        self.pushButton_convert_csv.clicked.connect(self.run_excel_to_csv)
        self.pushButton_create_polygon.clicked.connect(self.run_create_polygon)
        self.pushButton_segment_polygon.clicked.connect(self.run_segmentator)
        self.pushButton_export_excel.clicked.connect(self.run_export_excel)
        self.pushButton_save_config.clicked.connect(self.save_config)
        self.pushButton_refresh_layers.clicked.connect(self.refresh_layer_comboboxes)
        
        # Conectar botón Recalcular Atributos (v2.2)
        self.pushButton_recalcular.clicked.connect(self.run_recalcular)
        
        # Conectar cambio de archivo CSV para actualizar campos
        self.mFileWidget_csv_polygon.fileChanged.connect(self.update_csv_fields)
        
        # Configuración inicial de widgets
        try:
            # Configurar CRS selector
            self.mCrsSelector_polygon.setCrs(QgsProject.instance().crs())
            
            # Configurar filtros de capas
            self.mLayerComboBox_polygon.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
            self.mLayerComboBox_export.setFilters(QgsMapLayerProxyModel.Filter.VectorLayer)
            # Filtros para combos de recalculo (v2.2)
            self.mLayerComboBox_recalc_lineas.setFilters(QgsMapLayerProxyModel.Filter.LineLayer)
            self.mLayerComboBox_recalc_puntos.setFilters(QgsMapLayerProxyModel.Filter.PointLayer)
            self.mLayerComboBox_recalc_lineas.setAllowEmptyLayer(True)
            self.mLayerComboBox_recalc_puntos.setAllowEmptyLayer(True)
            # Nombres por defecto para capas de salida (v2.3)
            self.lineEdit_nombre_lineas.setPlaceholderText("Segmentos")
            self.lineEdit_nombre_puntos.setPlaceholderText("Vertices")
            # Ocultar barra de progreso al inicio
            self.progressBar_segmento.setVisible(False)
            self.progressBar_segmento.setValue(0)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error al configurar widgets: {str(e)}", 
                "YF Tools Plus", 
                Qgis.MessageLevel.Warning
            )
        
        self.table_to_polygon = TableToPolygon()

        # ── v3.0: pestaña unificada Tabla → Polígono ──
        self._configurar_v3()

        # Cargar configuración guardada
        self.load_config()

    def tr(self, message):
        """Obtiene la cadena traducida de QGIS."""
        return QCoreApplication.translate('YF_Tools_PlusDialog', message)

    def _configurar_v3(self):
        """v3.0: elimina la pestaña Excel a CSV y convierte Crear Polígono
        en Tabla → Polígono (Excel/CSV directo, multi-polígono por campo ID,
        orden de vértices opcional)."""
        from qgis.PyQt.QtWidgets import (QGroupBox, QFormLayout, QComboBox,
                                          QLabel)
        # 1. Quitar pestañas redundantes (por texto, robusto a índices):
        #    - "Excel a CSV": absorbida por Tabla → Polígono
        #    - "Segmentador": duplicaba el Segmentador de Parcelas standalone
        #      de la suite, que es el mantenido (fix fid GeoPackage, etc.)
        for texto in ('Excel a CSV',):
            for i in range(self.tabWidget.count()):
                if texto in self.tabWidget.tabText(i):
                    self.tabWidget.removeTab(i)
                    break

        # 2. Retitular y localizar la pestaña de polígono
        idx_pol = -1
        for i in range(self.tabWidget.count()):
            if 'Pol\u00edgono' in self.tabWidget.tabText(i) or 'Poligono' in self.tabWidget.tabText(i):
                idx_pol = i
                self.tabWidget.setTabText(i, "Tabla \u2192 Pol\u00edgono")
                break

        # 3. Filtro de archivo: Excel + CSV en el mismo selector
        try:
            self.mFileWidget_csv_polygon.setFilter(
                "Tablas (*.xlsx *.xls *.csv);;Excel (*.xlsx *.xls);;CSV (*.csv)")
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

        # 3b. Textos heredados del flujo CSV -> ahora tabla universal
        from qgis.PyQt.QtWidgets import QGroupBox as _QGB, QLabel as _QLB
        if idx_pol >= 0:
            page0 = self.tabWidget.widget(idx_pol)
            for g in page0.findChildren(_QGB):
                if 'CSV' in g.title():
                    g.setTitle("Archivo de tabla (Excel o CSV)")
            for l in page0.findChildren(_QLB):  # noqa: E741
                t = l.text()
                if 'Seleccione el archivo CSV' in t:
                    l.setText("Seleccione la tabla (.xlsx, .xls, .csv):")
                elif 'al seleccionar un CSV' in t:
                    l.setText(t.replace('al seleccionar un CSV',
                                        'al seleccionar la tabla'))

        # 4. Grupo nuevo: hoja + agrupación + orden
        grp = QGroupBox("Hoja y agrupaci\u00f3n")
        form = QFormLayout(grp)

        self.cboHojaExcel = QComboBox()
        self.cboHojaExcel.setToolTip(
            "<b>Hoja</b><br>Solo para Excel con varias hojas: elige cu\u00e1l "
            "contiene las coordenadas.")
        self.lblHojaExcel = QLabel("Hoja del Excel:")
        form.addRow(self.lblHojaExcel, self.cboHojaExcel)
        self.lblHojaExcel.setVisible(False)
        self.cboHojaExcel.setVisible(False)

        self.cboCampoIDPol = QComboBox()
        self.cboCampoIDPol.setToolTip(
            "<b>Campo ID de pol\u00edgono</b><br>Si la tabla trae los v\u00e9rtices de "
            "VARIOS pol\u00edgonos (fracciones, predios), elige la columna que los "
            "distingue: se dibuja un pol\u00edgono por cada valor. "
            "D\u00e9jalo en \u2014 Un solo pol\u00edgono \u2014 para el caso simple.")
        form.addRow("Campo ID de pol\u00edgono:", self.cboCampoIDPol)

        self.cboCampoOrdenPol = QComboBox()
        self.cboCampoOrdenPol.setToolTip(
            "<b>Campo de orden</b><br>Columna que define el recorrido de los "
            "v\u00e9rtices (ID_Vertice, orden). Sin \u00e9l se respeta el orden de "
            "filas \u2014 si la tabla viene desordenada, el pol\u00edgono saldr\u00e1 "
            "en estrella.")
        form.addRow("Campo de orden:", self.cboCampoOrdenPol)

        # Insertar el grupo en la página, después del grupo de coordenadas
        if idx_pol >= 0:
            page = self.tabWidget.widget(idx_pol)
            lay = page.layout()
            if lay is not None:
                pos = min(2, lay.count())
                try:
                    lay.insertWidget(pos, grp)
                except Exception:
                    lay.addWidget(grp)

        # 5. Cambio de hoja recarga los campos
        self.cboHojaExcel.currentIndexChanged.connect(
            lambda _i: self.update_csv_fields(
                self.mFileWidget_csv_polygon.filePath()))

        # 3c. Ventana y traducciones del Segmentador (v3.0 pulido)
        self.setMinimumSize(700, 780)
        self.resize(720, 840)
        from qgis.PyQt.QtWidgets import (QLabel as _L3, QGroupBox as _G3,
                                          QPushButton as _B3)
        TRAD = {
            'Recalculate Attributes of Existing Layers':
                'Recalcular atributos de capas existentes',
            'Use after manually editing vertices or segments.':
                'Usar despu\u00e9s de editar manualmente v\u00e9rtices o segmentos.',
            'Inherited fields from the source polygon are NOT modified.':
                'Los campos heredados del pol\u00edgono origen NO se modifican.',
            'Both layers automatically inherit all fields from the source '
            'polygon (useful for atlas and map series).':
                'Ambas capas heredan autom\u00e1ticamente todos los campos del '
                'pol\u00edgono origen (\u00fatil para atlas y series de mapas).',
            'Segments layer (lines) to recalculate:':
                'Capa de segmentos (l\u00edneas) a recalcular:',
            'Vertices layer (points) to recalculate:':
                'Capa de v\u00e9rtices (puntos) a recalcular:',
            'Recalculate Attributes': 'Recalcular atributos',
        }
        for w in (self.findChildren(_L3) + self.findChildren(_G3)
                  + self.findChildren(_B3)):
            try:
                t = w.title() if isinstance(w, _G3) else w.text()
                for en, es in TRAD.items():
                    if en in t:
                        t = t.replace(en, es)
                if isinstance(w, _G3):
                    w.setTitle(t)
                else:
                    w.setText(t)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)

        # 6. v3.0.4: selector de fuente (archivo vs capa de puntos)
        self._configurar_fuente_puntos(idx_pol)

    # ------------------------------------------------------------------
    # v3.0.4: fuente alternativa — capa de puntos del proyecto
    # ------------------------------------------------------------------

    def _configurar_fuente_puntos(self, idx_pol):
        """Agrega el selector Archivo (Excel/CSV) vs Capa de puntos."""
        from qgis.PyQt.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout,
                                          QRadioButton, QCheckBox, QLabel)
        from qgis.gui import QgsMapLayerComboBox
        try:
            from qgis.core import QgsMapLayerProxyModel
            _FILTRO_PUNTOS = getattr(
                QgsMapLayerProxyModel, "Filter",
                QgsMapLayerProxyModel).PointLayer
        except (ImportError, AttributeError):
            from qgis.core import Qgis as _Q
            _FILTRO_PUNTOS = _Q.LayerFilter.PointLayer  # QGIS 4 / Qt6

        if idx_pol < 0:
            return
        page = self.tabWidget.widget(idx_pol)
        lay = page.layout()
        if lay is None:
            return

        grp = QGroupBox("Fuente de puntos")
        v = QVBoxLayout(grp)
        fila = QHBoxLayout()
        self.rbFuenteArchivo = QRadioButton("Archivo (Excel/CSV)")
        self.rbFuenteCapa = QRadioButton("Capa de puntos del proyecto")
        self.rbFuenteArchivo.setChecked(True)
        fila.addWidget(self.rbFuenteArchivo)
        fila.addWidget(self.rbFuenteCapa)
        v.addLayout(fila)

        self.cboCapaPuntos = QgsMapLayerComboBox()
        try:
            self.cboCapaPuntos.setFilters(_FILTRO_PUNTOS)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        self.cboCapaPuntos.setToolTip(
            "<b>Capa de puntos</b><br>Vértices ya cargados en el proyecto "
            "(QField, PPK, shapefiles de terceros). Las coordenadas salen de "
            "la GEOMETRÍA y el CRS es el de la capa — sin riesgo de elegir "
            "mal la zona UTM.")
        v.addWidget(self.cboCapaPuntos)

        fila2 = QHBoxLayout()
        self.chkSoloSeleccion = QCheckBox("Solo entidades seleccionadas")
        self.chkSoloSeleccion.setToolTip(
            "Construye el polígono únicamente con los puntos seleccionados "
            "en el canvas — útil para tomar 5-10 vértices de una capa grande.")
        self.lblCrsCapaPuntos = QLabel("")
        fila2.addWidget(self.chkSoloSeleccion)
        fila2.addStretch(1)
        fila2.addWidget(self.lblCrsCapaPuntos)
        v.addLayout(fila2)

        lay.insertWidget(0, grp)

        # Grupos que se ocultan en modo capa
        from qgis.PyQt.QtWidgets import QGroupBox as _G
        self._grpArchivoTabla = None
        self._grpCoords = None
        for g in page.findChildren(_G):
            t = g.title()
            if 'Archivo de tabla' in t:
                self._grpArchivoTabla = g
            elif 'Coordenadas' in t:
                self._grpCoords = g

        self.rbFuenteArchivo.toggled.connect(self._on_fuente_cambiada)
        self.cboCapaPuntos.layerChanged.connect(self._on_capa_puntos_cambiada)
        self._on_fuente_cambiada()

    def _on_fuente_cambiada(self, *_args):
        """Alterna visibilidad entre modo archivo y modo capa."""
        modo_capa = self.rbFuenteCapa.isChecked()
        self.cboCapaPuntos.setVisible(modo_capa)
        self.chkSoloSeleccion.setVisible(modo_capa)
        self.lblCrsCapaPuntos.setVisible(modo_capa)
        if self._grpArchivoTabla is not None:
            self._grpArchivoTabla.setVisible(not modo_capa)
        if self._grpCoords is not None:
            self._grpCoords.setVisible(not modo_capa)
        if modo_capa:
            self.lblHojaExcel.setVisible(False)
            self.cboHojaExcel.setVisible(False)
            self._on_capa_puntos_cambiada(self.cboCapaPuntos.currentLayer())
        else:
            fp = self.mFileWidget_csv_polygon.filePath()
            if fp:
                self.update_csv_fields(fp)

    def _on_capa_puntos_cambiada(self, layer):
        """Repuebla ID/orden con los campos de la capa y muestra su CRS."""
        if not self.rbFuenteCapa.isChecked():
            return
        if layer is None:
            self.lblCrsCapaPuntos.setText("")
            return
        self.lblCrsCapaPuntos.setText("CRS: {}".format(layer.crs().authid()))
        campos = [f.name() for f in layer.fields()]
        sug = self.table_to_polygon.autodetectar(campos)
        for combo, clave, vacio in (
                (self.cboCampoIDPol, 'id', "\u2014 Un solo pol\u00edgono \u2014"),
                (self.cboCampoOrdenPol, 'orden',
                 "\u2014 Orden de entidades \u2014")):
            actual = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(vacio, None)
            for c in campos:
                combo.addItem(c, c)
            objetivo = actual if actual in campos else sug[clave]
            if objetivo:
                i = combo.findText(objetivo)
                if i >= 0:
                    combo.setCurrentIndex(i)
            combo.blockSignals(False)

    def _run_create_polygon_desde_capa(self):
        """v3.0.4: crea polígono(s) desde la capa de puntos elegida."""
        try:
            layer = self.cboCapaPuntos.currentLayer()
            if layer is None:
                QMessageBox.warning(self, "Advertencia",
                                    "Seleccione una capa de puntos del "
                                    "proyecto.")
                return
            solo_sel = self.chkSoloSeleccion.isChecked()
            if solo_sel and layer.selectedFeatureCount() == 0:
                QMessageBox.warning(self, "Advertencia",
                                    "La capa no tiene entidades "
                                    "seleccionadas.")
                return

            field_id = self.cboCampoIDPol.currentData()
            field_orden = self.cboCampoOrdenPol.currentData()

            style_params = {
                'polygon_color': '255,255,255,60',
                'border_color': '#ff340b',
                'border_width': '0.26',
                'label_font': 'Arial',
                'label_size': '9',
                'label_color': '#ff340b',
            }

            layer_out, resumen = self.table_to_polygon.create_polygons_from_layer(
                layer, field_id=field_id, field_orden=field_orden,
                style_params=style_params, solo_seleccion=solo_sel)

            if layer_out is not None:
                QMessageBox.information(self, "Resultado", resumen)
                self.refresh_layer_comboboxes()
            else:
                QMessageBox.warning(self, "Sin resultados", resumen)

        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 "Error al crear pol\u00edgono(s) desde "
                                 "capa:\n{}".format(e))
            QgsMessageLog.logMessage(
                "Error en TableToPolygon (capa): {}".format(e),
                "YF Tools Plus", Qgis.MessageLevel.Critical)

    def _hoja_actual(self):
        if self.cboHojaExcel.isVisible() and self.cboHojaExcel.currentText():
            return self.cboHojaExcel.currentText()
        return None

    def update_csv_fields(self, filepath):
        """v3.0: detecta campos de CUALQUIER tabla (xlsx/xls/csv), maneja
        hojas de Excel y auto-selecciona X, Y, ID de polígono y orden."""
        try:
            if not filepath or not os.path.exists(filepath):
                return

            # Hojas: mostrar el combo solo si el Excel tiene más de una
            hojas = self.table_to_polygon.get_sheets(filepath)
            multi = len(hojas) > 1
            if multi and self.cboHojaExcel.count() == 0 or \
                    [self.cboHojaExcel.itemText(i)
                     for i in range(self.cboHojaExcel.count())] != hojas:
                self.cboHojaExcel.blockSignals(True)
                self.cboHojaExcel.clear()
                if multi:
                    self.cboHojaExcel.addItems(hojas)
                self.cboHojaExcel.blockSignals(False)
            self.lblHojaExcel.setVisible(multi)
            self.cboHojaExcel.setVisible(multi)

            fields = self.table_to_polygon.get_fields(
                filepath, self._hoja_actual())
            if not fields:
                QgsMessageLog.logMessage(
                    "No se pudieron detectar campos en la tabla",
                    "YF Tools Plus", Qgis.MessageLevel.Warning)
                return

            sug = self.table_to_polygon.autodetectar(fields)

            # X / Y
            for combo, clave in ((self.comboBox_x_field, 'x'),
                                 (self.comboBox_y_field, 'y')):
                actual = combo.currentText()
                combo.clear()
                combo.addItems(fields)
                objetivo = actual if actual in fields else sug[clave]
                if objetivo:
                    i = combo.findText(objetivo)
                    if i >= 0:
                        combo.setCurrentIndex(i)

            # ID de polígono (opcional) y orden (opcional)
            for combo, clave, vacio in (
                    (self.cboCampoIDPol, 'id', "\u2014 Un solo pol\u00edgono \u2014"),
                    (self.cboCampoOrdenPol, 'orden', "\u2014 Orden de filas \u2014")):
                actual = combo.currentText()
                combo.clear()
                combo.addItem(vacio, None)
                for f in fields:
                    combo.addItem(f, f)
                objetivo = actual if actual in fields else sug[clave]
                if objetivo:
                    i = combo.findText(objetivo)
                    if i >= 0:
                        combo.setCurrentIndex(i)

            QgsMessageLog.logMessage(
                "\u2713 Campos detectados: {}".format(", ".join(fields)),
                "YF Tools Plus", Qgis.MessageLevel.Success)

        except Exception as e:
            QgsMessageLog.logMessage(
                "Error al actualizar campos: {}".format(e),
                "YF Tools Plus", Qgis.MessageLevel.Warning)

    def refresh_layer_comboboxes(self):
        """Fuerza la actualización de los QgsMapLayerComboBox."""
        try:
            self.mLayerComboBox_polygon.setLayer(None)
            self.mLayerComboBox_polygon.setCurrentIndex(0)
            self.mLayerComboBox_export.setLayer(None)
            self.mLayerComboBox_export.setCurrentIndex(0)
            # Actualizar también combos de recalculo (v2.2)
            self.mLayerComboBox_recalc_lineas.setLayer(None)
            self.mLayerComboBox_recalc_lineas.setCurrentIndex(0)
            self.mLayerComboBox_recalc_puntos.setLayer(None)
            self.mLayerComboBox_recalc_puntos.setCurrentIndex(0)
            
            self.iface.messageBar().pushMessage(
                "YF Tools Plus",
                "✓ Listas de capas actualizadas",
                level=Qgis.MessageLevel.Success,
                duration=2
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error al actualizar listas: {str(e)}", 
                "YF Tools Plus", 
                Qgis.MessageLevel.Warning
            )

    def run_excel_to_csv(self):
        """Ejecuta la conversión de Excel a CSV."""
        try:
            input_file = self.mFileWidget_excel_input.filePath()
            output_file = self.mFileWidget_csv_output.filePath()
            
            if not input_file or not output_file:
                QMessageBox.warning(
                    self, 
                    "Advertencia", 
                    "Debe seleccionar un archivo de entrada y uno de salida."
                )
                return
            
            QgsMessageLog.logMessage(
                "Iniciando conversión de Excel a CSV...", 
                "YF Tools Plus", 
                Qgis.MessageLevel.Info
            )
            
            result = self.excel_to_csv.convert(input_file, output_file)
            
            if result:
                QMessageBox.information(
                    self, 
                    "Éxito", 
                    f"✓ Archivo convertido exitosamente a:\n{output_file}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo convertir el archivo. Revise el registro de mensajes."
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Error al convertir archivo:\n{str(e)}"
            )
            QgsMessageLog.logMessage(
                f"Error en ExcelToCsv: {str(e)}", 
                "YF Tools Plus", 
                Qgis.MessageLevel.Critical
            )

    def run_create_polygon(self):
        """v3.0: crea polígono(s) directo desde la tabla (Excel o CSV).
        v3.0.4: o desde una capa de puntos del proyecto."""
        if getattr(self, 'rbFuenteCapa', None) is not None \
                and self.rbFuenteCapa.isChecked():
            self._run_create_polygon_desde_capa()
            return
        try:
            tabla = self.mFileWidget_csv_polygon.filePath()
            x_field = self.comboBox_x_field.currentText().strip()
            y_field = self.comboBox_y_field.currentText().strip()
            crs = self.mCrsSelector_polygon.crs()

            if not tabla:
                QMessageBox.warning(self, "Advertencia",
                                    "Debe seleccionar un archivo de tabla "
                                    "(.xlsx, .xls o .csv).")
                return
            if not x_field or not y_field:
                QMessageBox.warning(self, "Advertencia",
                                    "Debe especificar los campos X e Y.")
                return
            if not crs.isValid():
                QMessageBox.warning(self, "Advertencia",
                                    "Seleccione un sistema de coordenadas "
                                    "v\u00e1lido (ej. EPSG:32719).")
                return

            field_id = self.cboCampoIDPol.currentData()
            field_orden = self.cboCampoOrdenPol.currentData()

            style_params = {
                'polygon_color': '255,255,255,60',
                'border_color': '#ff340b',
                'border_width': '0.26',
                'label_font': 'Arial',
                'label_size': '9',
                'label_color': '#ff340b',
            }

            layer, resumen = self.table_to_polygon.create_polygons(
                tabla, x_field, y_field, crs.authid(),
                sheet=self._hoja_actual(),
                field_id=field_id, field_orden=field_orden,
                style_params=style_params)

            if layer is not None:
                QMessageBox.information(self, "Resultado", resumen)
                self.refresh_layer_comboboxes()
            else:
                QMessageBox.warning(self, "Sin resultados", resumen)

        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 "Error al crear pol\u00edgono(s):\n{}".format(e))
            QgsMessageLog.logMessage(
                "Error en TableToPolygon: {}".format(e),
                "YF Tools Plus", Qgis.MessageLevel.Critical)

    def run_segmentator(self):
        """Ejecuta la segmentación de polígonos con todas las opciones (v2.3)."""
        try:
            layer = self.mLayerComboBox_polygon.currentLayer()

            if not layer or not layer.isValid():
                QMessageBox.warning(self, "Advertencia",
                    "Debe seleccionar una capa de polígono válida.")
                return

            # Leer opciones de la UI
            nombre_lin = self.lineEdit_nombre_lineas.text().strip() or "Segmentos"
            nombre_pnt = self.lineEdit_nombre_puntos.text().strip() or "Vertices"
            solo_sel   = self.checkBox_solo_seleccionados.isChecked()
            con_huecos = self.checkBox_anillos_interiores.isChecked()

            # Advertir si solo_seleccionados pero no hay selección
            if solo_sel and layer.selectedFeatureCount() == 0:
                resp = QMessageBox.question(
                    self, "Sin selección",
                    "No hay features seleccionadas.\n\n"
                    "¿Desea procesar todos los polígonos de la capa?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if resp == QMessageBox.StandardButton.No:
                    return
                solo_sel = False

            total_features = (layer.selectedFeatureCount()
                              if solo_sel and layer.selectedFeatureCount() > 0
                              else layer.featureCount())

            QgsMessageLog.logMessage(
                "Segmentando capa: " + layer.name() +
                " | capas: [" + nombre_lin + ", " + nombre_pnt + "]" +
                " | solo_sel=" + str(solo_sel) +
                " | huecos=" + str(con_huecos),
                "YF Tools Plus", Qgis.MessageLevel.Info)

            # Mostrar barra de progreso
            self.progressBar_segmento.setVisible(True)
            self.progressBar_segmento.setMaximum(max(total_features, 1))
            self.progressBar_segmento.setValue(0)
            self.pushButton_segment_polygon.setEnabled(False)
            QApplication.processEvents()

            def on_progress(procesados, total):
                self.progressBar_segmento.setValue(procesados)
                QApplication.processEvents()

            result = self.segmentator.segment_polygon(
                layer,
                nombre_lineas=nombre_lin,
                nombre_puntos=nombre_pnt,
                solo_seleccionados=solo_sel,
                incluir_anillos_interiores=con_huecos,
                feedback_cb=on_progress
            )

            self.progressBar_segmento.setVisible(False)
            self.pushButton_segment_polygon.setEnabled(True)

            if result:
                msg = ("\u2714 Segmentaci\u00f3n completada\n\n"
                       "Capas creadas:\n"
                       "\u2022 " + nombre_lin + "\n"
                       "\u2022 " + nombre_pnt)
                if solo_sel:
                    msg += "\n\n[Solo features seleccionadas]"
                if con_huecos:
                    msg += "\n[Incluye anillos interiores]"
                self.iface.messageBar().pushMessage(
                    "YF Tools Plus",
                    "\u2714 Segmentaci\u00f3n completada: " + nombre_lin + " / " + nombre_pnt,
                    level=Qgis.MessageLevel.Success, duration=4)
                QMessageBox.information(self, "\u00c9xito", msg)
            else:
                QMessageBox.warning(self, "Advertencia",
                    "La segmentaci\u00f3n no se complet\u00f3 correctamente.")

        except Exception as e:
            self.progressBar_segmento.setVisible(False)
            self.pushButton_segment_polygon.setEnabled(True)
            QMessageBox.critical(self, "Error",
                "Error al segmentar pol\u00edgono:\n" + str(e))
            QgsMessageLog.logMessage(
                "Error en Segmentator: " + str(e), "YF Tools Plus", Qgis.MessageLevel.Critical)

    def run_recalcular(self):
        """
        Copia longitud y azimut de la capa de segmentos a la de vertices y
        renumera los IDs de ambas en secuencia 1..n.

        Requiere AMBAS capas: el emparejamiento es entre ellas (cada punto
        con el segmento que arranca en el). No se modifica ninguna geometria.
        """
        try:
            capa_lin = self.mLayerComboBox_recalc_lineas.currentLayer()
            capa_pnt = self.mLayerComboBox_recalc_puntos.currentLayer()

            faltan = []
            if not capa_lin:
                faltan.append("\u2022 Capa de Segmentos (l\u00edneas)")
            if not capa_pnt:
                faltan.append("\u2022 Capa de V\u00e9rtices (puntos)")
            if faltan:
                QMessageBox.warning(
                    self, "Faltan capas",
                    "El recalculo necesita las dos capas: toma la longitud y el\n"
                    "azimut de los segmentos y los copia a los vertices.\n\n"
                    "Falta seleccionar:\n" + "\n".join(faltan))
                return

            if capa_lin.id() == capa_pnt.id():
                QMessageBox.warning(
                    self, "Capas repetidas",
                    "Seleccionaste la misma capa en los dos campos.")
                return

            if capa_lin.geometryType() != 1 or capa_pnt.geometryType() != 0:
                QMessageBox.warning(
                    self, "Tipo de geometria incorrecto",
                    "La capa de segmentos debe ser de lineas y la de vertices\n"
                    "de puntos. Revisa la seleccion.")
                return

            self.segmentator.recalcular_atributos(capa_lin, capa_pnt)
            rep = getattr(self.segmentator, "ultimo_reporte", None)

            if rep is None:
                QMessageBox.warning(
                    self, "Recalculo con errores",
                    "No se pudo completar. Revisa el Log de Mensajes de QGIS.")
                return

            # rep["ok"] es False cuando hay advertencias, aunque se haya
            # escrito: el usuario debe leerlas antes de dar por bueno el cuadro.
            if rep.get("avisos"):
                QMessageBox.warning(self, "Recalculo con advertencias",
                                    rep["mensaje"])
                self.iface.messageBar().pushMessage(
                    "YF Tools Plus",
                    "Recalculo terminado con advertencias",
                    level=Qgis.MessageLevel.Warning, duration=5)
            else:
                QMessageBox.information(self, "Recalculo completado",
                                        rep["mensaje"])
                self.iface.messageBar().pushMessage(
                    "YF Tools Plus",
                    "\u2714 Atributos recalculados correctamente",
                    level=Qgis.MessageLevel.Success, duration=3)


        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                "Error al recalcular atributos:\n" + str(e)
            )
            QgsMessageLog.logMessage(
                "Error en run_recalcular: " + str(e),
                "YF Tools Plus", Qgis.MessageLevel.Critical
            )

    def run_export_excel(self):
        """Ejecuta la exportación a Excel desde el diálogo."""
        try:
            layer = self.mLayerComboBox_export.currentLayer()
            output_path = self.mFileWidget_excel_output.filePath()
            open_file = self.checkBox_auto_open.isChecked()
            
            if not layer or not layer.isValid():
                QMessageBox.warning(
                    self, 
                    "Advertencia", 
                    "Debe seleccionar una capa vectorial válida para exportar."
                )
                return
            
            if not output_path:
                layer_name = layer.name().replace(" ", "_")
                output_dir = os.path.expanduser("~")
                output_path = os.path.join(output_dir, f"{layer_name}_atributos.xlsx")
            
            QgsMessageLog.logMessage(
                f"Exportando capa: {layer.name()}", 
                "YF Tools Plus", 
                Qgis.MessageLevel.Info
            )
            
            # Verificar si el destino está bloqueado (abierto en Excel)
            if os.path.exists(output_path):
                try:
                    with open(output_path, 'a'):
                        pass
                except (PermissionError, OSError):
                    QMessageBox.warning(
                        self, "Archivo en uso",
                        "El archivo de destino está abierto en Excel u otro "
                        "programa:\n\n{}\n\nCiérralo y vuelve a exportar."
                        .format(output_path))
                    return

            self.excel_exporter.export_to_excel(layer, output_path, open_file)

            # Verificar que el archivo se creó realmente y no quedó vacío
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                QMessageBox.critical(
                    self, "Error",
                    "La exportación no generó un archivo válido:\n{}\n\n"
                    "Revisa que la capa tenga entidades y que la ruta sea "
                    "escribible.".format(output_path))
                return

            kb = os.path.getsize(output_path) / 1024
            msg = ("Exportación completada.\n\n"
                   "Capa: {}\nArchivo: {}\nUbicación: {}\nTamaño: {:.1f} KB"
                   .format(layer.name(), os.path.basename(output_path),
                           os.path.dirname(output_path), kb))
            if open_file:
                msg += "\n\n(Se abrió automáticamente)"

            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle("Éxito")
            box.setText(msg)
            btn_carpeta = box.addButton("Abrir carpeta",
                                        QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() == btn_carpeta:
                from qgis.PyQt.QtGui import QDesktopServices
                from qgis.PyQt.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(
                    os.path.dirname(output_path)))
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Error al exportar a Excel:\n{str(e)}"
            )
            QgsMessageLog.logMessage(
                f"Error en ExcelExporter: {str(e)}", 
                "YF Tools Plus", 
                Qgis.MessageLevel.Critical
            )

    def save_config(self):
        """Guarda la configuración actual."""
        config = {
            "excel_input_path": self.mFileWidget_excel_input.filePath(),
            "csv_output_path": self.mFileWidget_csv_output.filePath(),
            "csv_polygon_path": self.mFileWidget_csv_polygon.filePath(),
            "x_field": self.comboBox_x_field.currentText(),
            "y_field": self.comboBox_y_field.currentText(),
            "crs_authid": self.mCrsSelector_polygon.crs().authid(),
            "excel_output_path": self.mFileWidget_excel_output.filePath(),
            "auto_open": self.checkBox_auto_open.isChecked(),
            "current_tab": self.tabWidget.currentIndex()
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            self.iface.messageBar().pushMessage(
                "YF Tools Plus",
                "✓ Configuración guardada",
                level=Qgis.MessageLevel.Success,
                duration=2
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error al guardar configuración: {str(e)}", 
                "YF Tools Plus", 
                Qgis.MessageLevel.Critical
            )

    def load_config(self):
        """Carga la configuración guardada."""
        if not os.path.exists(self.config_path):
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.mFileWidget_excel_input.setFilePath(config.get("excel_input_path", ""))
            self.mFileWidget_csv_output.setFilePath(config.get("csv_output_path", ""))
            
            csv_path = config.get("csv_polygon_path", "")
            if csv_path:
                self.mFileWidget_csv_polygon.setFilePath(csv_path)
                if os.path.exists(csv_path):
                    self.update_csv_fields(csv_path)
            
            # Establecer valores de campos
            x_field = config.get("x_field", "ESTE")
            y_field = config.get("y_field", "NORTE")
            
            self.comboBox_x_field.setEditText(x_field)
            self.comboBox_y_field.setEditText(y_field)
            
            crs_authid = config.get("crs_authid")
            if crs_authid:
                crs = QgsCoordinateReferenceSystem(crs_authid)
                if crs.isValid():
                    self.mCrsSelector_polygon.setCrs(crs)
            
            self.mFileWidget_excel_output.setFilePath(config.get("excel_output_path", ""))
            self.checkBox_auto_open.setChecked(config.get("auto_open", True))
            self.tabWidget.setCurrentIndex(config.get("current_tab", 0))
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error al cargar configuración: {str(e)}", 
                "YF Tools Plus", 
                Qgis.MessageLevel.Warning
            )