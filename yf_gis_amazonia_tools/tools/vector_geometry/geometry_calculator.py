# -*- coding: utf-8 -*-
"""
Geometry Calculator — calcula atributos geométricos sobre la misma capa.
Soporta polígonos, líneas y puntos. No crea capas nuevas.
Las funciones reciben `opciones` como dict {key: nombre_campo_destino}.
Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from math import atan2, degrees
from qgis.core import (
    QgsProject, QgsField, QgsDistanceArea,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsWkbTypes
)
from qgis.PyQt.QtCore import QVariant
from ...core.qt_compat import QVariant_Int, QVariant_Double, QVariant_String


def _get_distance_area(layer, target_crs_authid=None):
    da = QgsDistanceArea()
    crs = QgsCoordinateReferenceSystem(target_crs_authid) if target_crs_authid else layer.crs()
    da.setSourceCrs(crs, QgsProject.instance().transformContext())
    da.setEllipsoid(crs.ellipsoidAcronym() or "WGS84")
    return da


def _ensure_field(layer, field_name, field_type):
    """Crea el campo si no existe."""
    if layer.fields().indexOf(field_name) == -1:
        layer.dataProvider().addAttributes([QgsField(field_name, field_type)])
        layer.updateFields()


def _transform_geom(feature, layer, target_crs_authid):
    geom = feature.geometry()
    if target_crs_authid and layer.crs().authid() != target_crs_authid:
        target_crs = QgsCoordinateReferenceSystem(target_crs_authid)
        transform = QgsCoordinateTransform(
            layer.crs(), target_crs,
            QgsProject.instance().transformContext()
        )
        geom.transform(transform)
    return geom


def calcular_azimut(p1, p2):
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    return degrees(atan2(dx, dy)) % 360


def azimut_a_gms(az):
    """Convierte azimut decimal a string GMS: 324°15'22.00" """
    g = int(az)
    md = (az - g) * 60
    m = int(md)
    s = (md - m) * 60
    return "{:03d}°{:02d}'{:05.2f}\"" .format(g, m, s)


# ─────────────────────────────────────────────────────────────────────────────
# POLÍGONOS
# opciones: {"area_ha": "mi_campo", "perimetro_m": "perim", ...}
# ─────────────────────────────────────────────────────────────────────────────

def calcular_poligono(layer, opciones, target_crs_authid=None, solo_seleccion=False,
                      metodo="elipsoidal"):
    """
    metodo:
      "elipsoidal" → QgsDistanceArea (equivale a $area) — mundo real,
                     considera curvatura. Para análisis geoespacial.
      "planar"     → geom.area() (equivale a area($geometry)) — plano
                     cartesiano. Para planos legales, catastro, predios.
    """
    da = _get_distance_area(layer, target_crs_authid)

    # Validación planar: requiere CRS proyectado (en geográficas daría grados²)
    crs_efectivo = (QgsCoordinateReferenceSystem(target_crs_authid)
                    if target_crs_authid else layer.crs())
    if metodo == "planar" and crs_efectivo.isGeographic():
        raise ValueError(
            "El cálculo PLANAR requiere un CRS proyectado (ej. EPSG:32719 "
            "UTM 19S). La capa/CRS actual es geográfico — reproyecta o "
            "elige un CRS de destino proyectado.")

    layer.startEditing()

    # Preparar campos necesarios con sus tipos
    tipo_por_key = {
        "area_ha": QVariant_Double, "area_m2": QVariant_Double,
        "perimetro_m": QVariant_Double,
        "centroide_x": QVariant_Double, "centroide_y": QVariant_Double,
    }
    for key, fname in opciones.items():
        _ensure_field(layer, fname, tipo_por_key[key])

    features = layer.selectedFeatures() if solo_seleccion else layer.getFeatures()
    count = 0

    for feat in features:
        geom = _transform_geom(feat, layer, target_crs_authid)
        updates = {}

        if metodo == "planar":
            # area($geometry) / perimeter($geometry) — plano cartesiano
            _area_m2 = geom.area()
            _perim_m = geom.length()   # para polígonos: perímetro planar
        else:
            # $area / $perimeter — elipsoidal (mundo real)
            _area_m2 = da.measureArea(geom)
            _perim_m = da.measurePerimeter(geom)

        if "area_ha" in opciones:
            updates[opciones["area_ha"]] = round(_area_m2 / 10000, 4)
        if "area_m2" in opciones:
            updates[opciones["area_m2"]] = round(_area_m2, 4)
        if "perimetro_m" in opciones:
            updates[opciones["perimetro_m"]] = round(_perim_m, 4)
        if "centroide_x" in opciones or "centroide_y" in opciones:
            c = geom.centroid().asPoint()
            if "centroide_x" in opciones:
                updates[opciones["centroide_x"]] = round(c.x(), 4)
            if "centroide_y" in opciones:
                updates[opciones["centroide_y"]] = round(c.y(), 4)

        for fname, value in updates.items():
            idx = layer.fields().indexOf(fname)
            if idx >= 0:
                layer.changeAttributeValue(feat.id(), idx, value)
        count += 1

    layer.commitChanges()
    return count


# ─────────────────────────────────────────────────────────────────────────────
# LÍNEAS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_linea(layer, opciones, target_crs_authid=None, solo_seleccion=False,
                   metodo="elipsoidal"):
    da = _get_distance_area(layer, target_crs_authid)
    crs_efectivo = (QgsCoordinateReferenceSystem(target_crs_authid)
                    if target_crs_authid else layer.crs())
    if metodo == "planar" and crs_efectivo.isGeographic():
        raise ValueError(
            "El cálculo PLANAR requiere un CRS proyectado (ej. EPSG:32719).")
    layer.startEditing()

    tipo_por_key = {
        "longitud_m": QVariant_Double, "azimut_dec": QVariant_Double,
        "azimut_gms": QVariant_String,
        "inicio_x": QVariant_Double, "inicio_y": QVariant_Double,
        "fin_x": QVariant_Double, "fin_y": QVariant_Double,
    }
    for key, fname in opciones.items():
        _ensure_field(layer, fname, tipo_por_key[key])

    features = layer.selectedFeatures() if solo_seleccion else layer.getFeatures()
    count = 0

    for feat in features:
        geom = _transform_geom(feat, layer, target_crs_authid)
        updates = {}

        if "longitud_m" in opciones:
            _long_m = geom.length() if metodo == "planar" else da.measureLength(geom)
            updates[opciones["longitud_m"]] = round(_long_m, 4)

        vertices = list(geom.vertices())
        if vertices:
            p0, pn = vertices[0], vertices[-1]
            if "azimut_dec" in opciones or "azimut_gms" in opciones:
                az = calcular_azimut(p0, pn)
                if "azimut_dec" in opciones:
                    updates[opciones["azimut_dec"]] = round(az, 6)
                if "azimut_gms" in opciones:
                    updates[opciones["azimut_gms"]] = azimut_a_gms(az)
            if "inicio_x" in opciones:
                updates[opciones["inicio_x"]] = round(p0.x(), 4)
            if "inicio_y" in opciones:
                updates[opciones["inicio_y"]] = round(p0.y(), 4)
            if "fin_x" in opciones:
                updates[opciones["fin_x"]] = round(pn.x(), 4)
            if "fin_y" in opciones:
                updates[opciones["fin_y"]] = round(pn.y(), 4)

        for fname, value in updates.items():
            idx = layer.fields().indexOf(fname)
            if idx >= 0:
                layer.changeAttributeValue(feat.id(), idx, value)
        count += 1

    layer.commitChanges()
    return count


# ─────────────────────────────────────────────────────────────────────────────
# PUNTOS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_punto(layer, opciones, target_crs_authid=None, solo_seleccion=False):
    layer.startEditing()

    tipo_por_key = {
        "coord_x": QVariant_Double,
        "coord_y": QVariant_Double,
        "elevacion_z": QVariant_Double,
    }
    for key, fname in opciones.items():
        _ensure_field(layer, fname, tipo_por_key[key])

    features = layer.selectedFeatures() if solo_seleccion else layer.getFeatures()
    count = 0

    for feat in features:
        geom = _transform_geom(feat, layer, target_crs_authid)
        punto = geom.asPoint()
        updates = {}

        if "coord_x" in opciones:
            updates[opciones["coord_x"]] = round(punto.x(), 6)
        if "coord_y" in opciones:
            updates[opciones["coord_y"]] = round(punto.y(), 6)
        if "elevacion_z" in opciones and QgsWkbTypes.hasZ(geom.wkbType()):
            pt3d = list(geom.vertices())[0]
            updates[opciones["elevacion_z"]] = round(pt3d.z(), 4)

        for fname, value in updates.items():
            idx = layer.fields().indexOf(fname)
            if idx >= 0:
                layer.changeAttributeValue(feat.id(), idx, value)
        count += 1

    layer.commitChanges()
    return count
