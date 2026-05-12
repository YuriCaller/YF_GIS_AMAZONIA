# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Segmentator
                                 A QGIS plugin
 Herramientas para generar capas a partir de archivos Excel
                             -------------------
        begin                : 2025-04-21
        copyright            : (C) 2025 by Yuri Caller
        email                : yuricaller@gmail.com
 ****************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ****************************************************************************/
"""

from math import atan2, degrees
from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsProject,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings, QgsVectorLayerSimpleLabeling,
    QgsWkbTypes, QgsMessageLog, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor, QFont
import traceback

# Campos propios calculados — no se heredan del polígono
CAMPOS_PROPIOS_LINEAS = {"ID_Global", "ID_Poligono", "ID_Segmento", "longitud", "azimut"}
CAMPOS_PROPIOS_PUNTOS = {
    "ID_Global", "ID_Poligono", "ID_Vertice", "LADO",
    "Este", "Norte", "Distancia", "Azimut", "ang_int", "ang_extr"
}


class Segmentator:
    """Clase para segmentar polígonos en líneas y vértices"""

    def __init__(self):
        """Constructor."""
        pass

    # ──────────────────────────────────────────────────────────────────────
    # Cálculo geométrico
    # ──────────────────────────────────────────────────────────────────────

    def calcular_angulo_norte(self, punto_inicio, punto_fin):
        """Calcula el azimut respecto al norte [0, 360)."""
        dx = punto_fin.x() - punto_inicio.x()
        dy = punto_fin.y() - punto_inicio.y()
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return 0.0
        angulo = degrees(atan2(dx, dy))
        if angulo < 0:
            angulo += 360
        return angulo

    # ──────────────────────────────────────────────────────────────────────
    # Helpers herencia de campos
    # ──────────────────────────────────────────────────────────────────────

    def _campos_heredados(self, capa_poligonos, propios):
        return [f for f in capa_poligonos.fields() if f.name() not in propios]

    def _valores_heredados(self, feature, campos):
        return [feature[c.name()] for c in campos]

    # ──────────────────────────────────────────────────────────────────────
    # Procesar un anillo exterior → devuelve listas de features
    # ──────────────────────────────────────────────────────────────────────

    def _procesar_anillo(self, anillo, id_poligono, id_global_start,
                         fields_lin, fields_pnt, vals_lin, vals_pnt,
                         nombre_anillo, feedback=None):
        """
        Procesa un anillo (lista de QgsPointXY) y devuelve:
        (features_lineas, features_puntos, id_global_siguiente)
        """
        vertices_xy = [QgsPointXY(p) for p in anillo]

        if len(vertices_xy) < 3:
            QgsMessageLog.logMessage(
                "Anillo '" + nombre_anillo + "' con menos de 3 vertices. Omitiendo.",
                "YF Tools", Qgis.Warning)
            return [], [], id_global_start

        if vertices_xy[0].compare(vertices_xy[-1], 1e-9):
            vertices_xy.pop()

        if len(vertices_xy) < 3:
            return [], [], id_global_start

        # Reordenar desde el vértice más al norte
        vertice_norte = max(vertices_xy, key=lambda p: (p.y(), -p.x()))
        indice_norte = vertices_xy.index(vertice_norte)
        vertices_ordenados = vertices_xy[indice_norte:] + vertices_xy[:indice_norte]
        num_vertices = len(vertices_ordenados)

        id_global = id_global_start
        feats_lin = []
        feats_pnt = []

        for i in range(num_vertices):
            idx_next = (i + 1) % num_vertices
            idx_prev = (i - 1 + num_vertices) % num_vertices

            punto_inicio = vertices_ordenados[i]
            punto_fin    = vertices_ordenados[idx_next]
            punto_prev   = vertices_ordenados[idx_prev]

            segmento_geom = QgsGeometry.fromPolylineXY([punto_inicio, punto_fin])
            if not segmento_geom or segmento_geom.isEmpty():
                continue

            longitud = round(segmento_geom.length(), 4)
            if longitud < 1e-6:
                continue

            azimut = round(self.calcular_angulo_norte(punto_inicio, punto_fin), 1)
            azimut_prev = self.calcular_angulo_norte(punto_prev, punto_inicio)
            internal_angle = round((azimut_prev - azimut + 180) % 360, 2)
            external_angle = round(360.0 - internal_angle, 2)
            if abs(external_angle - 360) < 1e-6:
                external_angle = 0.0
            elif external_angle < 0:
                external_angle += 360

            id_v  = i + 1
            id_vn = idx_next + 1
            lado_str = "V" + str(id_v) + " a V" + str(id_vn)

            f_lin = QgsFeature(fields_lin)
            f_lin.setGeometry(segmento_geom)
            f_lin.setAttributes([id_global, id_poligono, id_v, longitud, azimut] + vals_lin)
            feats_lin.append(f_lin)

            f_pnt = QgsFeature(fields_pnt)
            f_pnt.setGeometry(QgsGeometry.fromPointXY(punto_inicio))
            f_pnt.setAttributes([
                id_global, id_poligono, id_v, lado_str,
                round(punto_inicio.x(), 6), round(punto_inicio.y(), 6),
                longitud, azimut, internal_angle, external_angle
            ] + vals_pnt)
            feats_pnt.append(f_pnt)

            id_global += 1

            if feedback:
                feedback(i + 1, num_vertices)

        return feats_lin, feats_pnt, id_global

    # ──────────────────────────────────────────────────────────────────────
    # Segmentación principal
    # ──────────────────────────────────────────────────────────────────────

    def segment_polygon(self, capa_poligonos, nombre_lineas="Segmentos",
                        nombre_puntos="Vertices", solo_seleccionados=False,
                        incluir_anillos_interiores=False, feedback_cb=None):
        """
        Segmenta polígonos en capas de Segmentos y Vértices.

        Mejoras v2.3:
        - Soporte multiparte completo (todos los anillos/partes)
        - Anillos interiores (huecos) opcionales
        - Solo features seleccionadas (solo_seleccionados=True)
        - Nombres de capas configurables (nombre_lineas, nombre_puntos)
        - Callback de progreso: feedback_cb(procesados, total)
        - Herencia de campos del polígono origen

        :param capa_poligonos: Capa de polígonos
        :param nombre_lineas: Nombre para la capa de segmentos
        :param nombre_puntos: Nombre para la capa de vértices
        :param solo_seleccionados: Si True, procesa solo features seleccionadas
        :param incluir_anillos_interiores: Si True, procesa también huecos
        :param feedback_cb: función(procesados, total) para progreso
        :returns: True si exitoso
        """
        try:
            if not capa_poligonos or capa_poligonos.geometryType() != QgsWkbTypes.PolygonGeometry:
                QgsMessageLog.logMessage(
                    "La capa no es valida o no es de tipo poligono.",
                    "YF Tools", Qgis.Critical)
                return False

            # Determinar qué features procesar
            if solo_seleccionados and capa_poligonos.selectedFeatureCount() > 0:
                features_iter = capa_poligonos.selectedFeatures()
                total = capa_poligonos.selectedFeatureCount()
            else:
                features_iter = capa_poligonos.getFeatures()
                total = capa_poligonos.featureCount()

            # Campos heredados
            ch_lin = self._campos_heredados(capa_poligonos, CAMPOS_PROPIOS_LINEAS)
            ch_pnt = self._campos_heredados(capa_poligonos, CAMPOS_PROPIOS_PUNTOS)

            # Crear capa de Segmentos
            crs_wkt = capa_poligonos.crs().toWkt()
            capa_lin = QgsVectorLayer("LineString?crs=" + crs_wkt, nombre_lineas, "memory")
            prov_lin = capa_lin.dataProvider()
            prov_lin.addAttributes([
                QgsField("ID_Global",   QVariant.Int),
                QgsField("ID_Poligono", QVariant.Int),
                QgsField("ID_Segmento", QVariant.Int),
                QgsField("longitud",    QVariant.Double),
                QgsField("azimut",      QVariant.Double),
            ] + ch_lin)
            capa_lin.updateFields()

            # Crear capa de Vértices
            capa_pnt = QgsVectorLayer("Point?crs=" + crs_wkt, nombre_puntos, "memory")
            prov_pnt = capa_pnt.dataProvider()
            prov_pnt.addAttributes([
                QgsField("ID_Global",   QVariant.Int),
                QgsField("ID_Poligono", QVariant.Int),
                QgsField("ID_Vertice",  QVariant.Int),
                QgsField("LADO",        QVariant.String),
                QgsField("Este",        QVariant.Double),
                QgsField("Norte",       QVariant.Double),
                QgsField("Distancia",   QVariant.Double),
                QgsField("Azimut",      QVariant.Double),
                QgsField("ang_int",     QVariant.Double),
                QgsField("ang_extr",    QVariant.Double),
            ] + ch_pnt)
            capa_pnt.updateFields()

            id_global = 1
            id_poligono = 1
            procesados = 0
            todas_lin = []
            todas_pnt = []

            for feature in features_iter:
                geom = feature.geometry()
                if not geom or geom.isEmpty():
                    continue

                vals_lin = self._valores_heredados(feature, ch_lin)
                vals_pnt = self._valores_heredados(feature, ch_pnt)

                # Recopilar partes y anillos según tipo de geometría
                anillos_a_procesar = []  # lista de (anillo, etiqueta)

                if geom.isMultipart():
                    partes = geom.asMultiPolygon()
                    for p_idx, parte in enumerate(partes):
                        if not parte:
                            continue
                        # Anillo exterior
                        anillos_a_procesar.append(
                            (parte[0], "P" + str(id_poligono) + "-parte" + str(p_idx + 1))
                        )
                        # Anillos interiores (huecos)
                        if incluir_anillos_interiores:
                            for h_idx, hueco in enumerate(parte[1:]):
                                anillos_a_procesar.append(
                                    (hueco, "P" + str(id_poligono) + "-hueco" + str(h_idx + 1))
                                )
                else:
                    poligono = geom.asPolygon()
                    if not poligono:
                        continue
                    # Anillo exterior
                    anillos_a_procesar.append(
                        (poligono[0], "P" + str(id_poligono))
                    )
                    # Anillos interiores (huecos)
                    if incluir_anillos_interiores:
                        for h_idx, hueco in enumerate(poligono[1:]):
                            anillos_a_procesar.append(
                                (hueco, "P" + str(id_poligono) + "-hueco" + str(h_idx + 1))
                            )

                for anillo, etiqueta in anillos_a_procesar:
                    fl, fp, id_global = self._procesar_anillo(
                        anillo, id_poligono, id_global,
                        capa_lin.fields(), capa_pnt.fields(),
                        vals_lin, vals_pnt, etiqueta
                    )
                    todas_lin.extend(fl)
                    todas_pnt.extend(fp)

                id_poligono += 1
                procesados += 1
                if feedback_cb and total > 0:
                    feedback_cb(procesados, total)

            # Añadir todas las features de una vez (más eficiente)
            prov_lin.addFeatures(todas_lin)
            prov_pnt.addFeatures(todas_pnt)

            capa_lin.updateExtents()
            capa_pnt.updateExtents()
            self._etiquetar_lineas(capa_lin)
            self._etiquetar_puntos(capa_pnt)
            QgsProject.instance().addMapLayer(capa_lin)
            QgsProject.instance().addMapLayer(capa_pnt)

            msg = ("Segmentacion OK: " + str(id_poligono - 1) + " poligono(s), " +
                   str(len(todas_lin)) + " segmentos. " +
                   "Campos heredados: " + str([c.name() for c in ch_lin]))
            if solo_seleccionados:
                msg += " [solo seleccionados]"
            QgsMessageLog.logMessage(msg, "YF Tools", Qgis.Success)
            return True

        except Exception as e:
            QgsMessageLog.logMessage(
                "Error al segmentar: " + str(e) + "\n" + traceback.format_exc(),
                "YF Tools", Qgis.Critical)
            raise Exception("Error al segmentar: " + str(e))

    # ──────────────────────────────────────────────────────────────────────
    # RECALCULAR atributos en capas existentes
    # ──────────────────────────────────────────────────────────────────────

    def recalcular_atributos(self, capa_lineas, capa_puntos):
        """
        Recalcula longitud, azimut, ángulos, coordenadas y LADO
        en capas existentes. Los campos heredados NO se tocan.
        Soporta recalculo por ID_Vertice reordenado por posición norte (v2.3).
        """
        ok_lin = self._recalc_lineas(capa_lineas) if capa_lineas else False
        ok_pnt = self._recalc_puntos(capa_puntos)  if capa_puntos else False
        return ok_lin, ok_pnt

    def _recalc_lineas(self, capa):
        try:
            if not capa or not capa.isValid():
                QgsMessageLog.logMessage("Capa de lineas no valida.", "YF Tools", Qgis.Warning)
                return False
            fields = capa.fields()
            idx_lon = fields.indexOf("longitud")
            idx_az  = fields.indexOf("azimut")
            if idx_lon < 0 or idx_az < 0:
                QgsMessageLog.logMessage(
                    "Faltan campos 'longitud'/'azimut'.", "YF Tools", Qgis.Warning)
                return False

            cambios = {}
            for feat in capa.getFeatures():
                geom = feat.geometry()
                if not geom or geom.isEmpty():
                    continue
                pts = geom.asPolyline() if not geom.isMultipart() else geom.asMultiPolyline()[0]
                if len(pts) < 2:
                    continue
                cambios[feat.id()] = {
                    idx_lon: round(geom.length(), 4),
                    idx_az:  round(self.calcular_angulo_norte(
                        QgsPointXY(pts[0]), QgsPointXY(pts[-1])), 1),
                }

            capa.dataProvider().changeAttributeValues(cambios)
            capa.updateExtents()
            capa.triggerRepaint()
            QgsMessageLog.logMessage(
                "Recalculados " + str(len(cambios)) + " segmentos en '" + capa.name() + "'.",
                "YF Tools", Qgis.Success)
            return True

        except Exception as e:
            QgsMessageLog.logMessage(
                "Error recalculando lineas: " + str(e), "YF Tools", Qgis.Critical)
            return False

    def _recalc_puntos(self, capa):
        """
        Recalcula atributos de vértices.
        v2.3: re-ordena por posición espacial norte antes de recalcular
        para corregir IDs desfasados tras edición de geometría.
        """
        try:
            if not capa or not capa.isValid():
                QgsMessageLog.logMessage("Capa de puntos no valida.", "YF Tools", Qgis.Warning)
                return False

            fields = capa.fields()
            I = {name: fields.indexOf(name) for name in
                 ["Este", "Norte", "Distancia", "Azimut", "ang_int", "ang_extr",
                  "LADO", "ID_Poligono", "ID_Vertice"]}

            faltantes = [k for k in ["Este", "Norte", "Distancia", "Azimut"] if I[k] < 0]
            if faltantes:
                QgsMessageLog.logMessage(
                    "Faltan campos: " + str(faltantes), "YF Tools", Qgis.Warning)
                return False

            # Agrupar por ID_Poligono
            grupos = {}
            for feat in capa.getFeatures():
                geom = feat.geometry()
                if not geom or geom.isEmpty():
                    continue
                id_pol = feat[I["ID_Poligono"]] if I["ID_Poligono"] >= 0 else 0
                pt = QgsPointXY(geom.asPoint())
                if id_pol not in grupos:
                    grupos[id_pol] = []
                grupos[id_pol].append([feat.id(), pt])

            cambios = {}
            for grupo in grupos.values():
                # Re-ordenar espacialmente desde el norte (corrige IDs tras edición)
                grupo.sort(key=lambda x: (-x[1].y(), x[1].x()))
                n = len(grupo)

                for i, (fid, pt) in enumerate(grupo):
                    pt_next = grupo[(i + 1) % n][1]
                    pt_prev = grupo[(i - 1 + n) % n][1]

                    lon = round(QgsGeometry.fromPolylineXY([pt, pt_next]).length(), 4)
                    az  = round(self.calcular_angulo_norte(pt, pt_next), 1)
                    az_prev = self.calcular_angulo_norte(pt_prev, pt)
                    ang_int = round((az_prev - az + 180) % 360, 2)
                    ang_ext = round(360.0 - ang_int, 2)
                    if abs(ang_ext - 360) < 1e-6:
                        ang_ext = 0.0
                    elif ang_ext < 0:
                        ang_ext += 360

                    nuevo_id_v  = i + 1
                    nuevo_id_vn = (i + 1) % n + 1
                    attrs = {
                        I["Este"]:      round(pt.x(), 6),
                        I["Norte"]:     round(pt.y(), 6),
                        I["Distancia"]: lon,
                        I["Azimut"]:    az,
                    }
                    if I["ID_Vertice"] >= 0:
                        attrs[I["ID_Vertice"]] = nuevo_id_v
                    if I["ang_int"] >= 0:
                        attrs[I["ang_int"]] = ang_int
                    if I["ang_extr"] >= 0:
                        attrs[I["ang_extr"]] = ang_ext
                    if I["LADO"] >= 0:
                        attrs[I["LADO"]] = "V" + str(nuevo_id_v) + " a V" + str(nuevo_id_vn)
                    cambios[fid] = attrs

            capa.dataProvider().changeAttributeValues(cambios)
            capa.updateExtents()
            capa.triggerRepaint()
            QgsMessageLog.logMessage(
                "Recalculados " + str(len(cambios)) + " vertices en '" + capa.name() + "'.",
                "YF Tools", Qgis.Success)
            return True

        except Exception as e:
            QgsMessageLog.logMessage(
                "Error recalculando puntos: " + str(e) + "\n" + traceback.format_exc(),
                "YF Tools", Qgis.Critical)
            return False

    # ──────────────────────────────────────────────────────────────────────
    # Etiquetas
    # ──────────────────────────────────────────────────────────────────────

    def _etiquetar_lineas(self, capa):
        pal = QgsPalLayerSettings()
        pal.fieldName = ("concat(round(\"longitud\", 2) || ' m' || '\\n' "
                         "|| round(\"azimut\", 1) || '\xb0')")
        pal.isExpression = True
        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 7))
        fmt.setColor(QColor(0, 0, 0))
        fmt.setSize(7)
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(0.5)
        buf.setColor(QColor(255, 255, 255))
        fmt.setBuffer(buf)
        pal.setFormat(fmt)
        pal.placement = QgsPalLayerSettings.Line
        pal.placementFlags = QgsPalLayerSettings.OnLine | QgsPalLayerSettings.AboveLine
        capa.setLabeling(QgsVectorLayerSimpleLabeling(pal))
        capa.setLabelsEnabled(True)

    def _etiquetar_puntos(self, capa):
        pal = QgsPalLayerSettings()
        pal.fieldName = "'V' || \"ID_Vertice\""
        pal.isExpression = True
        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 9))
        fmt.setColor(QColor(0, 0, 255))
        fmt.setSize(9)
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(0.5)
        buf.setColor(QColor(255, 255, 255))
        fmt.setBuffer(buf)
        pal.setFormat(fmt)
        pal.placement = QgsPalLayerSettings.AroundPoint
        pal.quadOffset = QgsPalLayerSettings.QuadrantAboveRight
        pal.dist = 1.0
        capa.setLabeling(QgsVectorLayerSimpleLabeling(pal))
        capa.setLabelsEnabled(True)
