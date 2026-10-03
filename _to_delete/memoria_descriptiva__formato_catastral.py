# -*- coding: utf-8 -*-
"""
formato_catastral.py - Utilidades de formato para Memoria Descriptiva
YF GIS Amazonia Tools

Convenciones catastrales peruanas (DRA/GOREMAD, SNCP):
  - Coordenadas UTM: 4 decimales (norma - NO cambiar)
  - Distancias: 2 decimales (norma - NO cambiar)
  - Azimut y rumbo: sexagesimal GMS (143\u00b054'00")
  - Etiquetas de vertice: patron uniforme configurable (V-1, V01, P-1...)
"""

import math
import re


# ---------------------------------------------------------------------------
# AZIMUT / RUMBO
# ---------------------------------------------------------------------------

def azimut_decimal_a_gms(azimut, seg_decimales=0):
    """Convierte azimut decimal a cadena sexagesimal: 143.9 -> 143\u00b054'00"."""
    try:
        az = float(azimut) % 360.0
    except (ValueError, TypeError):
        return str(azimut)
    grados = int(az)
    resto_min = (az - grados) * 60.0
    minutos = int(resto_min)
    segundos = round((resto_min - minutos) * 60.0, seg_decimales)
    if segundos >= 60:
        segundos -= 60
        minutos += 1
    if minutos >= 60:
        minutos -= 60
        grados += 1
    grados %= 360
    if seg_decimales == 0:
        seg_txt = "%02d" % int(segundos)
    else:
        seg_txt = ("%0" + str(3 + seg_decimales) + "." + str(seg_decimales) + "f") % segundos
    return "%d\u00b0%02d'%s\"" % (grados, minutos, seg_txt)


def azimut_a_rumbo_gms(azimut, seg_decimales=0):
    """Azimut decimal a rumbo cuadrante GMS: 143.9 -> S 36\u00b006'00" E.

    Garantiza coherencia matematica: narrativa 5.1 y tabla 5.2 derivan
    del mismo valor fuente.
    """
    try:
        az = float(azimut) % 360.0
    except (ValueError, TypeError):
        return str(azimut)
    if az <= 90.0:
        letras, ang = ("N", "E"), az
    elif az <= 180.0:
        letras, ang = ("S", "E"), 180.0 - az
    elif az <= 270.0:
        letras, ang = ("S", "O"), az - 180.0
    else:
        letras, ang = ("N", "O"), 360.0 - az
    return "%s %s %s" % (letras[0], azimut_decimal_a_gms(ang, seg_decimales), letras[1])


def azimut_desde_coordenadas(e1, n1, e2, n2):
    """Azimut geodesico (desde el Norte, horario) entre dos vertices.

    Fuente unica de verdad: calcular siempre desde las coordenadas que
    apareceran en la tabla, no desde atributos potencialmente truncados.
    """
    de, dn = float(e2) - float(e1), float(n2) - float(n1)
    if de == 0 and dn == 0:
        return None
    return math.degrees(math.atan2(de, dn)) % 360.0


def distancia_desde_coordenadas(e1, n1, e2, n2):
    """Distancia plana UTM entre dos vertices."""
    return math.hypot(float(e2) - float(e1), float(n2) - float(n1))


def diferencia_angular(a, b):
    """Diferencia minima entre dos azimuts en grados (0-180)."""
    return abs(((float(a) - float(b) + 180.0) % 360.0) - 180.0)


# ---------------------------------------------------------------------------
# NORMALIZADOR DE ETIQUETAS DE VERTICE
# ---------------------------------------------------------------------------

PATRONES_VERTICE = ("V-{n}", "V{n}", "V{nn}", "P-{n}", "P{nn}")


def extraer_numero_vertice(etiqueta):
    """Extrae numero de etiqueta existente: 'V01'->1, 'V-3'->3. None si no hay."""
    if etiqueta is None:
        return None
    m = re.search(r"(\d+)", str(etiqueta))
    return int(m.group(1)) if m else None


def normalizar_etiqueta(numero, patron="V-{n}"):
    """Genera etiqueta uniforme para el vertice `numero` (1-based)."""
    return (patron.replace("{nn}", "%02d" % numero)
                  .replace("{n}", "%d" % numero))


def etiqueta_lado(etiq_a, etiq_b):
    """Etiqueta del lado entre dos vertices ya normalizados: 'V-1 a V-2'."""
    return "%s a %s" % (etiq_a, etiq_b)


# ---------------------------------------------------------------------------
# FORMATO DE AZIMUT CONFIGURABLE
# ---------------------------------------------------------------------------
# Modos:
#   'decimal' (default): 355.1\u00b0  \u2014 igual al plano; replanteo con br\u00fajula
#   'gms'              : 355\u00b006'19"  \u2014 para instituciones que lo exijan
#   'ambos'            : 355.1\u00b0 (355\u00b006'19")

MODO_AZIMUT_DEFAULT = 'decimal'
DECIMALES_AZIMUT_DEFAULT = 1


def formato_azimut(az, modo=None, decimales=None):
    """Formatea un azimut segun el modo configurado."""
    if modo is None:
        modo = MODO_AZIMUT_DEFAULT
    if decimales is None:
        decimales = DECIMALES_AZIMUT_DEFAULT
    try:
        val = float(az) % 360.0
    except (ValueError, TypeError):
        return str(az)
    dec_txt = '%.*f\u00b0' % (decimales, val)
    if modo == 'gms':
        return azimut_decimal_a_gms(val)
    if modo == 'ambos':
        return '%s (%s)' % (dec_txt, azimut_decimal_a_gms(val))
    return dec_txt


def frase_azimut_narrativa(az, modo=None, decimales=None):
    """Fragmento para la narrativa 5.1 coherente con la tabla y el plano.

    decimal -> "con azimut de 355.1\u00b0"
    gms     -> "con rumbo N 4\u00b054' O"   (convencion de gabinete)
    ambos   -> "con azimut de 355.1\u00b0 (rumbo N 4\u00b054' O)"
    """
    if modo is None:
        modo = MODO_AZIMUT_DEFAULT
    if modo == 'gms':
        return 'con rumbo %s' % azimut_a_rumbo_gms(az)
    if modo == 'ambos':
        return 'con azimut de %s (rumbo %s)' % (
            formato_azimut(az, 'decimal', decimales), azimut_a_rumbo_gms(az))
    return 'con azimut de %s' % formato_azimut(az, 'decimal', decimales)


def formato_azimut_tabla(az, modo=None, decimales=None):
    """Formato para celda de tabla: en modo decimal SIN simbolo (la unidad
    va en el encabezado de columna, igual que la tabla del Segmentador)."""
    if modo is None:
        modo = MODO_AZIMUT_DEFAULT
    if modo == 'decimal':
        if decimales is None:
            decimales = DECIMALES_AZIMUT_DEFAULT
        try:
            return '%.*f' % (decimales, float(az) % 360.0)
        except (ValueError, TypeError):
            return str(az)
    return formato_azimut(az, modo, decimales)
