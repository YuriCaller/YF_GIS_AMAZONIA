# -*- coding: utf-8 -*-
"""
Memoria Descriptiva v3.2 — Integrado en YF GIS Amazonia Tools.

Genera memorias descriptivas técnicas (.docx) a partir de capas vectoriales.
Tres modos de trabajo:
  - ÚNICO:           1 memoria para el polígono seleccionado
  - ATLAS COMPLETO:  1 memoria por CADA polígono de la capa
  - ATLAS SELECCIÓN: 1 memoria por cada polígono SELECCIONADO en QGIS
"""

import os
import sys
import traceback

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error, log_warning

# Check for python-docx
try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# Load processing modules
_TOOL_DIR = os.path.dirname(__file__)
try:
    from .deteccion_capas_adyacentes import detectar_capas_adyacentes
    from .identificacion_colindantes import identificar_colindantes_completo
    from .procesamiento_coordenadas import (
        obtener_vertices_de_poligono,
        calcular_area_perimetro_feature,
        generar_descripcion_linderos,
        obtener_info_sistema_coordenadas,
        _detectar_campo,
    )
    from .generacion_documento_word import generar_documento_word
    _MODS_OK = True
    _MODS_ERR = ""
except ImportError as e:
    _MODS_OK = False
    _MODS_ERR = str(e)


class Tool(BaseTool):
    """Memoria Descriptiva tool entry point."""

    TOOL_NAME = "Memoria Descriptiva"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self.dlg = None
        self.first_start = True

    def run(self):
        """Open the Memoria Descriptiva dialog."""
        from qgis.PyQt.QtWidgets import QMessageBox

        if not HAS_DOCX:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Dependencia faltante",
                "Requiere <b>python-docx</b>.<br>"
                "Instale: <code>pip install python-docx</code>",
            )
            return

        if not _MODS_OK:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error de módulos",
                f"Error al cargar módulos internos:<br>{_MODS_ERR}",
            )
            return

        log_info("Abriendo Memoria Descriptiva")

        if self.first_start:
            self.first_start = False
            from .memoria_descriptiva_dialog import MemoriaDescriptivaDialog
            self.dlg = MemoriaDescriptivaDialog()
            self.dlg.btnBrowse.clicked.connect(self._select_output)
            self.dlg.btnGenerar.clicked.connect(self._generar)

        self._cargar_capas()
        self._autodetectar_crs()
        self.dlg.show()
        self.dlg.exec_()

    def unload(self):
        if self.dlg:
            self.dlg.close()
            self.dlg = None

    # ------------------------------------------------------------------
    # Layer loading
    # ------------------------------------------------------------------

    def _cargar_capas(self):
        from qgis.core import QgsProject, QgsVectorLayer

        for cbo in [self.dlg.cboPoligonos, self.dlg.cboPuntos, self.dlg.cboLineas]:
            cbo.blockSignals(True)
            cbo.clear()

        self.dlg.cboPoligonos.addItem("-- Seleccione --", None)
        self.dlg.cboPuntos.addItem("-- Seleccione --", None)
        self.dlg.cboLineas.addItem("-- Opcional --", None)

        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                gt = layer.geometryType()
                if gt == 2:
                    self.dlg.cboPoligonos.addItem(layer.name(), layer.id())
                elif gt == 0:
                    self.dlg.cboPuntos.addItem(layer.name(), layer.id())
                elif gt == 1:
                    self.dlg.cboLineas.addItem(layer.name(), layer.id())

        for cbo in [self.dlg.cboPoligonos, self.dlg.cboPuntos, self.dlg.cboLineas]:
            cbo.blockSignals(False)

        self._autoselect(self.dlg.cboPoligonos, ["AREA_TOTAL", "area_total", "Parcelas", "parcelas"])
        self._autoselect(self.dlg.cboPuntos, ["Puntos", "puntos", "vertices", "Vertices"])

        if self.dlg.cboPoligonos.count() > 1:
            if self.dlg.cboPoligonos.currentIndex() == 0:
                self.dlg.cboPoligonos.setCurrentIndex(1)
            self.dlg.actualizar_campos_poligono()

        if self.dlg.cboPuntos.count() > 1:
            if self.dlg.cboPuntos.currentIndex() == 0:
                self.dlg.cboPuntos.setCurrentIndex(1)
            self.dlg.actualizar_campos_puntos()

    def _autoselect(self, combo, nombres):
        for i in range(1, combo.count()):
            if combo.itemText(i).lower() in [n.lower() for n in nombres]:
                combo.setCurrentIndex(i)
                return

    def _autodetectar_crs(self):
        lid = self.dlg.cboPoligonos.currentData()
        if not lid:
            return
        from qgis.core import QgsProject
        layer = QgsProject.instance().mapLayer(lid)
        if not layer:
            return
        try:
            info = obtener_info_sistema_coordenadas(layer)
            for attr, key in [
                ("txtSistema", "Sistema de coordenadas"),
                ("txtUnidades", "Unidades"),
                ("txtElipsoide", "Elipsoide"),
                ("txtGrillado", "Grillado"),
            ]:
                w = getattr(self.dlg, attr, None)
                if w and not w.text():
                    w.setText(info.get(key, ""))
        except Exception:
            pass

    def _select_output(self):
        from qgis.PyQt.QtWidgets import QFileDialog

        fn, _ = QFileDialog.getSaveFileName(
            self.dlg,
            "Guardar Memoria Descriptiva",
            os.path.expanduser("~"),
            "Documentos Word (*.docx)",
        )
        if fn:
            if not fn.lower().endswith(".docx"):
                fn += ".docx"
            self.dlg.txtOutputFile.setText(fn)

    # ------------------------------------------------------------------
    # Generation dispatcher
    # ------------------------------------------------------------------

    def _generar(self):
        from qgis.PyQt.QtWidgets import QMessageBox
        from qgis.core import QgsProject

        if not self.dlg.validar_formulario():
            return

        datos = self.dlg.obtener_datos_formulario()
        modo = datos["modo"]

        pol_layer = QgsProject.instance().mapLayer(datos["capas"]["poligono_id"])
        pnt_layer = QgsProject.instance().mapLayer(datos["capas"]["punto_id"])

        if modo == "unico":
            sel = list(pol_layer.selectedFeatures())
            feats = sel if sel else list(pol_layer.getFeatures())
            if not feats:
                QMessageBox.warning(self.dlg, "Sin datos", "La capa de polígonos está vacía.")
                return
            self._procesar_lista(datos, [feats[0]], pol_layer, pnt_layer, es_atlas=False)

        elif modo == "atlas_seleccion":
            feats = list(pol_layer.selectedFeatures())
            if not feats:
                QMessageBox.warning(
                    self.dlg, "Sin selección",
                    "No hay polígonos seleccionados.\nSelecciona al menos uno en QGIS.",
                )
                return
            self._procesar_lista(datos, feats, pol_layer, pnt_layer, es_atlas=True)

        else:  # atlas_completo
            feats = list(pol_layer.getFeatures())
            if not feats:
                QMessageBox.warning(self.dlg, "Sin datos", "La capa de polígonos está vacía.")
                return
            self._procesar_lista(datos, feats, pol_layer, pnt_layer, es_atlas=True)

    # ------------------------------------------------------------------
    # Process feature list
    # ------------------------------------------------------------------

    def _procesar_lista(self, datos, features, pol_layer, pnt_layer, es_atlas):
        from qgis.PyQt.QtWidgets import QProgressDialog, QMessageBox, QApplication
        from qgis.PyQt.QtCore import Qt

        total = len(features)
        prog = QProgressDialog("Generando memorias...", "Cancelar", 0, total, self.dlg)
        prog.setWindowTitle("Memoria Descriptiva")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        prog.show()
        QApplication.processEvents()

        generados = []
        errores = []

        for i, feature in enumerate(features):
            if prog.wasCanceled():
                break

            nombre_prop, dni_prop = self._extraer_nombre_dni(feature, datos)
            sufijo = nombre_prop.replace(" ", "_")[:40] if es_atlas else None

            prog.setLabelText("{}/{}: {}".format(i + 1, total, nombre_prop or "predio_{}".format(i + 1)))
            prog.setValue(i)
            QApplication.processEvents()

            try:
                id_pol = self._obtener_id_poligono(feature, pol_layer, datos)

                campos_puntos = {
                    "campo_id_poligono": datos["relacion"]["campo_rel_puntos"],
                    "campo_vertice": datos["campos"]["campo_vertice"],
                    "campo_lado": datos["campos"]["campo_lado"],
                    "campo_este": datos["campos"]["campo_este"],
                    "campo_norte": datos["campos"]["campo_norte"],
                    "campo_distancia": datos["campos"]["campo_distancia"],
                    "campo_azimut": datos["campos"]["campo_azimut"],
                }
                vertices = obtener_vertices_de_poligono(pnt_layer, id_pol, campos_puntos)

                campos_pol = {
                    "campo_area": datos["campos"]["campo_area"],
                    "campo_perimetro": datos["campos"]["campo_perimetro"],
                }
                ap = calcular_area_perimetro_feature(feature, pol_layer, campos_pol)

                if datos["colindantes"]["detectar_automatico"]:
                    capas_adj = detectar_capas_adyacentes(pol_layer)
                    colindantes = identificar_colindantes_completo(pol_layer, capas_adj)
                else:
                    m = datos["colindantes"]["manual"]
                    colindantes = {
                        d: {"nombre": m.get(d, "Terrenos del Estado"), "observacion": ""}
                        for d in ["NORTE", "SUR", "ESTE", "OESTE"]
                    }

                if not any(v for v in datos.get("info_mapa", {}).values()):
                    datos["info_mapa"] = obtener_info_sistema_coordenadas(pol_layer)

                dp = {
                    "vertices": vertices,
                    "area": ap["area"],
                    "perimetro": ap["perimetro"],
                    "fuente_area": ap["fuente_area"],
                    "colindantes": colindantes,
                    "descripcion_linderos": generar_descripcion_linderos(vertices),
                    "nombre_propietario": nombre_prop,
                }

                datos_doc = dict(datos)
                datos_doc["_nombre_propietario_actual"] = nombre_prop
                datos_doc["_dni_actual"] = dni_prop

                out = generar_documento_word(datos_doc, dp, sufijo_archivo=sufijo)
                generados.append((nombre_prop or "predio_{}".format(i + 1), out))
                log_info("Memoria generada: {} -> {}".format(nombre_prop, os.path.basename(out)))

            except Exception as e:
                errores.append((nombre_prop or "predio_{}".format(i + 1), str(e)))
                log_error("Error memoria {}: {}".format(nombre_prop, traceback.format_exc()))

        prog.setValue(total)
        prog.close()

        # Summary
        if generados:
            carpeta = os.path.dirname(generados[0][1])
            msg = "<b>{} memorias generadas correctamente</b><br>".format(len(generados))
            msg += "<b>Carpeta:</b> {}<br><br>".format(carpeta)
            for nombre, path in generados[:15]:
                msg += "• {} → <small>{}</small><br>".format(nombre, os.path.basename(path))
            if len(generados) > 15:
                msg += "<i>... y {} más</i><br>".format(len(generados) - 15)
            if errores:
                msg += "<br><b style='color:red'>Errores ({}):</b><br>".format(len(errores))
                for n, e in errores[:5]:
                    e_limpio = e.replace("KeyError(", "Campo no encontrado: ").rstrip(")")
                    msg += "• {}: <small>{}</small><br>".format(n, e_limpio[:150])
                if len(errores) > 5:
                    msg += "<i>... y {} errores más (ver consola de Python para detalles)</i><br>".format(len(errores) - 5)
            QMessageBox.information(self.dlg, "Completado", msg)
            if not es_atlas:
                self.dlg.accept()
        else:
            msg = "No se generó ningún documento."
            if errores:
                msg += "\n\nErrores:\n" + "\n".join("• {}: {}".format(n, e) for n, e in errores)
            QMessageBox.warning(self.dlg, "Sin resultados", msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _obtener_id_poligono(self, feature, pol_layer, datos):
        campo_id = datos["relacion"]["campo_id_poligono"]
        if not campo_id:
            campo_id = _detectar_campo(pol_layer,
                ["fid", "FID", "FID_", "fid_", "id", "ID",
                 "objectid", "OBJECTID", "ogc_fid", "gid"])
        if campo_id:
            fnames = [f.name() for f in feature.fields()]
            if campo_id in fnames:
                val = feature[campo_id]
                if val is not None:
                    try:
                        result = int(val)
                        print("  ID polígono: campo='{}' valor={}".format(campo_id, result))
                        return result
                    except (ValueError, TypeError):
                        print("  ID polígono (str): campo='{}' valor={}".format(campo_id, val))
                        return val
            else:
                print("  Advertencia: campo '{}' no encontrado en feature. Usando FID nativo.".format(campo_id))
        fid = feature.id()
        print("  ID polígono (FID nativo QGIS): {}".format(fid))
        return fid

    def _extraer_nombre_dni(self, feature, datos):
        fnames = [f.name() for f in feature.fields()]
        es_atlas = datos.get("modo", "unico") in ("atlas_completo", "atlas_seleccion")

        if es_atlas:
            campo_nombre = datos.get("atlas_solicitante", {}).get("campo_nombre")
            campo_dni = datos.get("atlas_solicitante", {}).get("campo_dni")
        else:
            sol = datos.get("solicitante", {})
            return sol.get("nombre", ""), sol.get("dni", "")

        nombre = ""
        if campo_nombre and campo_nombre in fnames:
            v = feature[campo_nombre]
            nombre = str(v).strip() if v else ""

        if not nombre:
            for c in ["NombresApellidos", "nombre", "nom_tit", "propietario", "titular", "name"]:
                if c in fnames:
                    v = feature[c]
                    if v:
                        nombre = str(v).strip()
                        break

        dni = ""
        if campo_dni and campo_dni in fnames:
            v = feature[campo_dni]
            dni = str(v).strip() if v else ""

        return nombre, dni
