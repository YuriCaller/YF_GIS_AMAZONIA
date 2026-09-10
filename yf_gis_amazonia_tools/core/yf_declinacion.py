# -*- coding: utf-8 -*-
"""
YF GIS Amazonia - Azimut magnetico (declinacion WMM + convergencia UTM).

Registra en el grupo "YF Amazonia" las funciones de expresion:
    yf_declinacion(geom, fecha)      D en grados decimales (Este +, Oeste -)
    yf_variacion_anual(geom, fecha)  deriva anual de D en grados/anio
    yf_convergencia(geom)            gamma en grados decimales (Este +)
    yf_az_cuadricula(geom)           azimut de cuadricula del tramo
    yf_az_magnetico(geom, fecha)     azimut para brujula de campo
    yf_contra_az(azimut)             contrarrumbo
    yf_rumbo_campo(azimut, paso)     azimut redondeado al paso indicado
    yf_gms(azimut)                   texto en grados/minutos/segundos

Convencion de signos:
    Az_verdadero = Az_cuadricula + gamma
    Az_magnetico = Az_verdadero  - D
    => Az_magnetico = Az_cuadricula + gamma - D

USO EXCLUSIVO DE CAMPO: el azimut de cuadricula es el que rige el
replanteo oficial y la reproduccion de coordenadas.

Autor: Yuri F. Caller Cordova - TUCSA / gis-amazonia.pe
"""

import datetime as _dt
import logging
import math
import os
from functools import lru_cache

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsExpression,
    QgsProject,
    QgsWkbTypes,
)
from qgis.utils import qgsfunction

GRUPO = "YF Amazonia"

# Modelo geomagnetico. Se usa el .COF que trae pygeomag; el rango de
# validez se lee de la cabecera del propio archivo (epoca + 5 anios),
# asi no hay constantes que actualizar a mano al cambiar de modelo.
ARCHIVO_COF = "WMM_2025.COF"

# Altitud de trabajo en km (llanura amazonica ~200 m). La declinacion es
# practicamente insensible a este valor.
ALTITUD_KM = 0.2

# Desviacion maxima de los vertices intermedios respecto a la cuerda, en
# metros. Por encima de esto el tramo se considera sinuoso (quebrada) y el
# azimut se devuelve NULL, segun la convencion de planos perimetricos.
TOLERANCIA_RECTA_M = 0.05

_WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


# --------------------------------------------------------------------
# Modelo geomagnetico
# --------------------------------------------------------------------
def _leer_cof(ruta):
    """Parsea un .COF del WMM al formato que espera pygeomag."""
    datos = []
    with open(ruta) as f:
        cab = f.readline().split()
        cabecera = (float(cab[0]), cab[1], cab[2])
        for ln in f:
            if ln[:4] == "9999":
                break
            v = ln.split()
            if len(v) == 6:
                datos.append((int(v[0]), int(v[1]), float(v[2]),
                              float(v[3]), float(v[4]), float(v[5])))
    return cabecera, datos


@lru_cache(maxsize=2)
def _modelo():
    """Devuelve (GeoMag, epoca, nombre, anio_fin).

    Se cargan los coeficientes a mano y se pasan por coefficients_data
    en vez de coefficients_file: pygeomag resuelve la ruta del .COF
    contra el directorio de trabajo, que en QGIS es impredecible y
    provoca un FileNotFoundError segun desde donde se haya abierto.
    """
    import pygeomag
    from pygeomag import GeoMag

    ruta = os.path.join(os.path.dirname(pygeomag.__file__), "wmm", ARCHIVO_COF)
    cabecera, coeficientes = _leer_cof(ruta)
    epoca, nombre, _release = cabecera
    return GeoMag(coefficients_data=(cabecera, coeficientes)), epoca, nombre, epoca + 5.0


def _anio_decimal(fecha):
    """Acepta None, date, datetime, QDate o cadena ISO."""
    if fecha is None:
        d = _dt.date.today()
    elif isinstance(fecha, _dt.datetime):
        d = fecha.date()
    elif isinstance(fecha, _dt.date):
        d = fecha
    elif hasattr(fecha, "year") and callable(getattr(fecha, "year")):
        d = _dt.date(fecha.year(), fecha.month(), fecha.day())
    else:
        d = _dt.date.fromisoformat(str(fecha)[:10])
    ini = _dt.date(d.year, 1, 1)
    fin = _dt.date(d.year + 1, 1, 1)
    return d.year + (d - ini).days / (fin - ini).days


@lru_cache(maxsize=1024)
def _declinacion(lat_r, lon_r, anio_r):
    """D en grados. Cacheada por lat/lon redondeadas a 0.1 grados."""
    gm, _epoca, _nombre, _fin = _modelo()
    return float(gm.calculate(glat=lat_r, glon=lon_r,
                              alt=ALTITUD_KM, time=anio_r).d)


def declinacion_punto(lat, lon, fecha=None):
    """API para dialogos y cajetin. Devuelve (D, variacion_anual, info)."""
    anio = _anio_decimal(fecha)
    _gm, epoca, nombre, fin = _modelo()
    d = _declinacion(round(lat, 1), round(lon, 1), round(anio, 2))
    d1 = _declinacion(round(lat, 1), round(lon, 1), round(min(anio + 1.0, fin - 0.01), 2))
    return d, d1 - d, {"modelo": nombre, "epoca": epoca,
                       "valido_hasta": fin, "anio_calculo": anio}


# --------------------------------------------------------------------
# Geometria
# --------------------------------------------------------------------
def _crs_capa(context):
    if context is not None:
        capa = context.variable("layer")
        if capa is not None and hasattr(capa, "crs") and capa.crs().isValid():
            return capa.crs()
        authid = context.variable("layer_crs")
        if authid:
            crs = QgsCoordinateReferenceSystem(str(authid))
            if crs.isValid():
                return crs
    return QgsProject.instance().crs()


def _a_wgs84(x, y, crs):
    if crs == _WGS84:
        return x, y
    tr = QgsCoordinateTransform(crs, _WGS84, QgsProject.instance())
    p = tr.transform(x, y)
    return p.x(), p.y()


@lru_cache(maxsize=1024)
def _convergencia(x_r, y_r, authid):
    """gamma: azimut verdadero de la direccion norte de cuadricula."""
    crs = QgsCoordinateReferenceSystem(authid)
    if crs.isGeographic():
        return 0.0
    from pyproj import Geod
    lon1, lat1 = _a_wgs84(x_r, y_r, crs)
    lon2, lat2 = _a_wgs84(x_r, y_r + 1000.0, crs)
    az, _, _ = Geod(ellps="WGS84").inv(lon1, lat1, lon2, lat2)
    return (az + 180.0) % 360.0 - 180.0


def convergencia_punto(x, y, authid):
    """Convergencia meridiana en un punto proyectado. API publica.

    gamma > 0: el norte de cuadricula queda al este del norte verdadero.
        Az_cuadricula = Az_verdadero - gamma

    Expuesta porque el modo «Reconstruir predio» (Memoria Descriptiva)
    la necesita desde el dialogo, no solo desde una expresion.
    """
    return _convergencia(x, y, authid)


def _centroide(geom):
    if geom is None or geom.isEmpty():
        return None
    c = geom.centroid()
    if c is None or c.isEmpty():
        return None
    return c.asPoint()


def _vertices(geom):
    if geom is None or geom.isEmpty():
        return None
    if QgsWkbTypes.geometryType(geom.wkbType()) != QgsWkbTypes.LineGeometry:
        return None
    vs = list(geom.vertices())
    return vs if len(vs) >= 2 else None


def _es_recta(vs):
    if len(vs) == 2:
        return True
    x1, y1 = vs[0].x(), vs[0].y()
    x2, y2 = vs[-1].x(), vs[-1].y()
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy)
    if largo == 0:
        return False
    for v in vs[1:-1]:
        if abs(dy * (v.x() - x1) - dx * (v.y() - y1)) / largo > TOLERANCIA_RECTA_M:
            return False
    return True


def _az_cuadricula(geom):
    vs = _vertices(geom)
    if vs is None or not _es_recta(vs):
        return None
    ini, fin = vs[0], vs[-1]
    return math.degrees(math.atan2(fin.x() - ini.x(), fin.y() - ini.y())) % 360.0


def _d_en_geom(geom, fecha, parent, context):
    p = _centroide(geom)
    if p is None:
        return None
    crs = _crs_capa(context)
    lon, lat = _a_wgs84(p.x(), p.y(), crs)
    anio = _anio_decimal(fecha)
    try:
        return _declinacion(round(lat, 1), round(lon, 1), round(anio, 2))
    except ImportError:
        if parent is not None:
            parent.setEvalErrorString(
                "Falta pygeomag. Instalalo desde el gestor de dependencias.")
        return None
    except ValueError as e:
        # pygeomag rechaza fechas fuera de la vigencia del modelo
        if parent is not None:
            _gm, epoca, nombre, fin = _modelo()
            parent.setEvalErrorString(
                "Fecha %.2f fuera de la vigencia de %s (%.1f-%.1f): %s"
                % (anio, nombre, epoca, fin, e))
        return None


def _g_en_geom(geom, context):
    p = _centroide(geom)
    if p is None:
        return None
    crs = _crs_capa(context)
    if not crs.isValid():
        return None
    return _convergencia(round(p.x(), 0), round(p.y(), 0), crs.authid())


# --------------------------------------------------------------------
# Funciones de expresion
# --------------------------------------------------------------------
@qgsfunction(args="auto", group=GRUPO, referenced_columns=[])
def yf_declinacion(geom, fecha, feature, parent, context):
    """Declinacion magnetica en el centroide (Este +, Oeste -).<br>
    <b>yf_declinacion($geometry, '2026-09-07')</b>"""
    return _d_en_geom(geom, fecha, parent, context)


@qgsfunction(args="auto", group=GRUPO, referenced_columns=[])
def yf_variacion_anual(geom, fecha, feature, parent, context):
    """Deriva anual de la declinacion, en grados por anio.<br>
    <b>yf_variacion_anual($geometry, '2026-09-07')</b>"""
    d0 = _d_en_geom(geom, fecha, parent, context)
    if d0 is None:
        return None
    anio = _anio_decimal(fecha)
    _gm, _ep, _nom, fin = _modelo()
    p = _centroide(geom)
    lon, lat = _a_wgs84(p.x(), p.y(), _crs_capa(context))
    d1 = _declinacion(round(lat, 1), round(lon, 1),
                      round(min(anio + 1.0, fin - 0.01), 2))
    return d1 - d0


@qgsfunction(args="auto", group=GRUPO, referenced_columns=[])
def yf_convergencia(geom, feature, parent, context):
    """Convergencia de meridianos en el centroide (Este +).<br>
    <b>yf_convergencia($geometry)</b>"""
    return _g_en_geom(geom, context)


@qgsfunction(args="auto", group=GRUPO, referenced_columns=[])
def yf_az_cuadricula(geom, feature, parent, context):
    """Azimut de cuadricula del tramo. NULL en tramos sinuosos
    (linderos de quebrada).<br><b>yf_az_cuadricula($geometry)</b>"""
    return _az_cuadricula(geom)


@qgsfunction(args="auto", group=GRUPO, referenced_columns=[])
def yf_az_magnetico(geom, fecha, feature, parent, context):
    """Azimut magnetico: Az_cuadricula + convergencia - declinacion.
    USO EXCLUSIVO DE CAMPO.<br>
    <b>yf_az_magnetico($geometry, '2026-09-07')</b>"""
    az = _az_cuadricula(geom)
    if az is None:
        return None
    g = _g_en_geom(geom, context)
    d = _d_en_geom(geom, fecha, parent, context)
    if g is None or d is None:
        return None
    return (az + g - d) % 360.0


@qgsfunction(args="auto", group=GRUPO, referenced_columns=[])
def yf_contra_az(azimut, feature, parent):
    """Contrarrumbo, para verificar la linea desde el vertice de llegada.<br>
    <b>yf_contra_az(az)</b>"""
    if azimut is None:
        return None
    return (float(azimut) + 180.0) % 360.0


@qgsfunction(args="auto", group=GRUPO, referenced_columns=[])
def yf_rumbo_campo(azimut, paso, feature, parent):
    """Redondea el azimut al paso indicado en grados (0.5 recomendado).
    Evita precision falsa frente a una brujula de mano.<br>
    <b>yf_rumbo_campo(az, 0.5)</b>"""
    if azimut is None:
        return None
    p = float(paso) if paso else 0.5
    if p <= 0:
        return None
    return round(float(azimut) / p) * p % 360.0


@qgsfunction(args="auto", group=GRUPO, referenced_columns=[])
def yf_gms(azimut, feature, parent):
    """Formatea un angulo decimal como grados, minutos y segundos.<br>
    <b>yf_gms(98.8215)</b>"""
    if azimut is None:
        return None
    a = float(azimut) % 360.0
    g = int(a)
    r = (a - g) * 60.0
    m = int(r)
    s = int(round((r - m) * 60.0))
    if s == 60:
        s, m = 0, m + 1
    if m == 60:
        m, g = 0, (g + 1) % 360
    return "%d\u00b0%02d'%02d\"" % (g, m, s)


# --------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------
FUNCIONES = [
    yf_declinacion,
    yf_variacion_anual,
    yf_convergencia,
    yf_az_cuadricula,
    yf_az_magnetico,
    yf_contra_az,
    yf_rumbo_campo,
    yf_gms,
]


def registrar_funciones():
    for f in FUNCIONES:
        QgsExpression.registerFunction(f)


def desregistrar_funciones():
    for f in FUNCIONES:
        try:
            QgsExpression.unregisterFunction(f.name())
        except Exception:
            logging.getLogger(__name__).debug(
                "desregistro de %s", f.name(), exc_info=True)
