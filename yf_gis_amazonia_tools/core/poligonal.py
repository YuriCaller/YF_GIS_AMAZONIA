# -*- coding: utf-8 -*-
"""
poligonal.py — Poligonales por azimut y distancia (COGO)
YF GIS Amazonia Tools · core

Construye geometria a partir de una tabla de azimuts y distancias: la
operacion inversa de la que ya hace Memoria Descriptiva. Sirve para
reconstruir un predio cuando llega el expediente con la memoria pero sin
shapefile, que es la mitad de los casos en saneamiento fisico legal.

REPARTO DE RESPONSABILIDADES
----------------------------
Este modulo NO formatea azimuts ni los calcula desde coordenadas: eso ya
vive en core/formato_catastral.py y esa sigue siendo la fuente unica de
verdad. Aqui solo esta lo que no existia:

    * parseo de azimuts y distancias escritos por humanos,
    * recorrido de la poligonal,
    * error de cierre y compensacion.

La declinacion magnetica tampoco se calcula aqui: core/yf_declinacion.py
ya carga el modelo WMM y expone declinacion_punto().

Nucleo en Python puro (solo math y re) para poder probarlo sin QGIS.

Autor: Yuri F. Caller Cordova — TUCSA / gis-amazonia.pe
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .formato_catastral import (azimut_a_rumbo_gms, azimut_decimal_a_gms,
                                azimut_desde_coordenadas,
                                distancia_desde_coordenadas)

__all__ = [
    "Segmento", "Cierre", "Poligonal",
    "parse_azimut", "parse_distancia", "corregir_azimut",
    "poligonal_a_poligono", "poligono_a_poligonal",
    "compensar_bowditch", "area_poligono",
    "TOLERANCIA_CIERRE_DEFECTO",
]

TOLERANCIA_CIERRE_DEFECTO = 1 / 1000.0   # 1:1000, razonable para rural


# ──────────────────────────────────────────────────────────────────────
#  PARSEO
# ──────────────────────────────────────────────────────────────────────

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_VACIO = {"", "-", "--", "s/n", "sn", "none", "null", "nulo", "n/a", "na"}


def _gms_a_decimal(nums: Sequence[float]) -> float:
    """1 numero = grados decimales; 2 = G M; 3 = G M S."""
    if not nums:
        raise ValueError("sin componente numerica")
    g = nums[0]
    if len(nums) >= 2:
        g += nums[1] / 60.0
    if len(nums) >= 3:
        g += nums[2] / 3600.0
    return g


def parse_azimut(texto):
    """
    Azimut escrito por humanos -> grados decimales 0-360, o None.

    Acepta:
        253            253.00        253,5
        253°15'30"     253 15 30     253° 15'
        N 4°44' W      S 68°16' W    N4.73W        S 4 44 E
        ""  "-"  "s/n" None          -> None (lindero natural)

    El cuadrante se detecta por la primera y la ultima letra: N/S al
    inicio, E/W/O al final. Rechaza en vez de adivinar: un azimut mal
    leido en un lindero de 2 km son cientos de metros.
    """
    if texto is None:
        return None
    t = str(texto).strip().upper().replace("º", "°")
    if t.lower() in _VACIO:
        return None

    letras = [c for c in t if c in "NSEWO"]
    ns = t[0] if t[:1] in ("N", "S") else None
    ew = t[-1] if t[-1:] in ("E", "W", "O") else None

    nums = [float(n.replace(",", ".")) for n in _NUM.findall(t)]
    if not nums:
        raise ValueError("azimut ilegible: {!r}".format(texto))
    ang = _gms_a_decimal(nums)

    if ns and ew:                       # rumbo por cuadrante
        if ang > 90.0 + 1e-9:
            raise ValueError("rumbo con angulo >90°: {!r}".format(texto))
        if ns == "N" and ew == "E":
            az = ang
        elif ns == "S" and ew == "E":
            az = 180.0 - ang
        elif ns == "S":                 # S..W / S..O
            az = 180.0 + ang
        else:                           # N..W / N..O
            az = 360.0 - ang
    elif letras and not (ns and ew):
        raise ValueError("cuadrante incompleto: {!r}".format(texto))
    else:
        az = ang

    return az % 360.0


def parse_distancia(texto):
    """Acepta '2000', '2,000.50', '410 m', '1 490,00 ml'. Devuelve metros."""
    if texto is None:
        raise ValueError("distancia vacia")
    t = str(texto).strip().lower()
    t = re.sub(r"\b(m|ml|mts?|metros?)\b", "", t)
    t = t.replace(" ", "")
    if "," in t and "." in t:            # separador de miles
        t = t.replace("." if t.rfind(",") > t.rfind(".") else ",", "")
    t = t.replace(",", ".")
    try:
        d = float(t)
    except ValueError:
        raise ValueError("distancia ilegible: {!r}".format(texto))
    if d <= 0:
        raise ValueError("distancia no positiva: {!r}".format(texto))
    return d


def corregir_azimut(az_plano, declinacion=0.0, convergencia=0.0):
    """
    Azimut del plano (normalmente magnetico) -> azimut de trabajo.

        Az_verdadero  = Az_magnetico + D
        Az_cuadricula = Az_verdadero - gamma

    D va con signo: Oeste es negativa (Peru). Deja convergencia en 0 si
    trabajas en Norte verdadero.
    """
    return (az_plano + declinacion - convergencia) % 360.0


# ──────────────────────────────────────────────────────────────────────
#  MODELO
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Segmento:
    """Un lado de la poligonal, tal como viene del plano."""
    distancia: float
    azimut: float = None                 # None = lindero natural
    nombre: str = ""
    colindante: str = ""
    vertice_ini: str = ""
    vertice_fin: str = ""

    @property
    def es_natural(self):
        return self.azimut is None

    @property
    def gms(self):
        return "" if self.es_natural else azimut_decimal_a_gms(self.azimut)

    @property
    def rumbo(self):
        return "" if self.es_natural else azimut_a_rumbo_gms(self.azimut)

    @classmethod
    def desde_texto(cls, azimut, distancia, **kw):
        return cls(distancia=parse_distancia(distancia),
                   azimut=parse_azimut(azimut), **kw)


@dataclass
class Cierre:
    """Error de cierre de una poligonal."""
    dE: float
    dN: float
    perimetro: float

    @property
    def lineal(self):
        return math.hypot(self.dE, self.dN)

    @property
    def relativo(self):
        return self.lineal / self.perimetro if self.perimetro else float("inf")

    @property
    def denominador(self):
        return self.perimetro / self.lineal if self.lineal else float("inf")

    def acepta(self, tolerancia=TOLERANCIA_CIERRE_DEFECTO):
        return self.relativo <= tolerancia

    def __str__(self):
        d = self.denominador
        dstr = "perfecto" if math.isinf(d) else "1:{:,.0f}".format(d)
        return ("cierre {:.3f} m (dE {:+.3f}, dN {:+.3f}) rel. {}"
                .format(self.lineal, self.dE, self.dN, dstr))


@dataclass
class Poligonal:
    """Resultado de recorrer una lista de segmentos."""
    vertices: list
    segmentos: list
    cierre: Cierre
    declinacion: float = 0.0
    convergencia: float = 0.0
    compensada: bool = False
    avisos: list = field(default_factory=list)

    @property
    def area(self):
        return area_poligono(self.vertices)

    @property
    def area_ha(self):
        return self.area / 10000.0


# ──────────────────────────────────────────────────────────────────────
#  GEOMETRIA
# ──────────────────────────────────────────────────────────────────────

def area_poligono(vertices):
    """Area por formula del zapato. Siempre positiva, en m2."""
    pts = list(vertices)
    if len(pts) > 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return 0.0
    s = sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
            - pts[(i + 1) % len(pts)][0] * pts[i][1]
            for i in range(len(pts)))
    return abs(s) / 2.0


def poligonal_a_poligono(origen, segmentos, declinacion=0.0,
                         convergencia=0.0, cerrar=True):
    """
    Construye la poligonal desde `origen` siguiendo los segmentos.

    Un segmento natural (azimut None) no se puede calcular por rumbo: se
    salta y se registra un aviso. Es deliberado — preferimos un aviso
    honesto a inventar una alineacion que el plano no declara.

    Si el unico lindero natural es el ultimo, el «cierre» deja de ser un
    error y pasa a ser la longitud calculada de ese lado. Compararla con
    la distancia declarada valida de una vez el origen, la declinacion y
    las distancias.
    """
    segs = list(segmentos)
    if not segs:
        raise ValueError("la poligonal no tiene segmentos")

    E, N = float(origen[0]), float(origen[1])
    vertices = [(E, N)]
    avisos = []
    perimetro = 0.0

    for i, s in enumerate(segs):
        perimetro += s.distancia
        if s.es_natural:
            if i != len(segs) - 1:
                avisos.append(
                    "Segmento {} ({}): lindero natural de {:.2f} m sin azimut, "
                    "en medio de la poligonal. La cadena se rompe aqui: los "
                    "vertices que siguen quedan desplazados."
                    .format(i + 1, s.nombre or "sin nombre", s.distancia))
            continue
        az = corregir_azimut(s.azimut, declinacion, convergencia)
        E += s.distancia * math.sin(math.radians(az))
        N += s.distancia * math.cos(math.radians(az))
        vertices.append((E, N))

    cierre = Cierre(dE=vertices[-1][0] - vertices[0][0],
                    dN=vertices[-1][1] - vertices[0][1],
                    perimetro=perimetro)

    naturales = [s for s in segs if s.es_natural]
    if len(naturales) == 1 and segs[-1].es_natural:
        calc, decl = cierre.lineal, segs[-1].distancia
        dif = calc - decl
        rel = abs(dif) / decl if decl else float("inf")
        avisos.append(
            "Control del lado natural ({}): calculado {:.2f} m vs declarado "
            "{:.2f} m (dif. {:+.2f} m, {:.1%}) — {}. Recta provisional en "
            "cuerda; reemplazala por la geometria real."
            .format(segs[-1].nombre or "ultimo lado", calc, decl, dif, rel,
                    "consistente" if rel <= 0.05 else
                    "SOSPECHOSO, revisa origen, declinacion o distancias"))

    if cerrar and vertices[-1] != vertices[0]:
        vertices.append(vertices[0])

    return Poligonal(vertices=vertices, segmentos=segs, cierre=cierre,
                     declinacion=declinacion, convergencia=convergencia,
                     avisos=avisos)


def poligono_a_poligonal(vertices, declinacion=0.0, convergencia=0.0,
                         nombres=None):
    """
    Inversa: geometria -> tabla de azimuts y distancias.

    Delega el calculo en formato_catastral para que la tabla que salga de
    aqui sea identica a la del cuadro de vertices de la memoria. Los
    azimuts se devuelven EN EL SISTEMA DEL PLANO, de modo que ida y vuelta
    son mutuamente inversas con los mismos parametros.
    """
    pts = list(vertices)
    if len(pts) > 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        raise ValueError("se necesitan al menos 3 vertices")

    segs = []
    for i, (E1, N1) in enumerate(pts):
        E2, N2 = pts[(i + 1) % len(pts)]
        az_trabajo = azimut_desde_coordenadas(E1, N1, E2, N2)
        az_plano = (None if az_trabajo is None
                    else (az_trabajo - declinacion + convergencia) % 360.0)
        segs.append(Segmento(
            distancia=distancia_desde_coordenadas(E1, N1, E2, N2),
            azimut=az_plano,
            nombre=nombres[i] if nombres and i < len(nombres) else "",
            vertice_ini="V-{}".format(i + 1),
            vertice_fin="V-{}".format((i + 1) % len(pts) + 1)))
    return segs


def compensar_bowditch(pol, tolerancia=TOLERANCIA_CIERRE_DEFECTO,
                       forzar=False):
    """
    Compensacion por regla de la brujula: reparte el error de cierre
    proporcionalmente a la longitud de cada lado.

    OPT-IN Y CON FRENO. Si el error relativo supera `tolerancia` no
    compensa y levanta ValueError, salvo forzar=True. Compensar un cierre
    malo no lo arregla: lo esconde. Un plano de lotizacion nominal puede
    no cerrar por diseño, y eso hay que verlo, no taparlo.

    No aplica si hay linderos naturales: no tienen alineacion que ajustar.
    """
    if any(s.es_natural for s in pol.segmentos):
        raise ValueError(
            "La poligonal tiene linderos naturales (azimut nulo). "
            "Resuelvelos contra su geometria real antes de compensar.")
    if not pol.cierre.acepta(tolerancia) and not forzar:
        raise ValueError(
            "Error de cierre {} fuera de tolerancia (1:{:,.0f}). Revisa "
            "datos, declinacion u origen."
            .format(pol.cierre, 1 / tolerancia))

    pts = list(pol.vertices)
    if len(pts) > 2 and pts[0] == pts[-1]:
        pts = pts[:-1]

    P = pol.cierre.perimetro
    acum = 0.0
    nuevos = [pts[0]]
    for i, s in enumerate(pol.segmentos[:-1]):
        acum += s.distancia
        f = acum / P
        E, N = pts[i + 1]
        nuevos.append((E - pol.cierre.dE * f, N - pol.cierre.dN * f))
    nuevos.append(nuevos[0])

    return Poligonal(
        vertices=nuevos, segmentos=pol.segmentos,
        cierre=Cierre(0.0, 0.0, P),
        declinacion=pol.declinacion, convergencia=pol.convergencia,
        compensada=True,
        avisos=pol.avisos + ["Compensada por Bowditch. Error repartido: {}"
                             .format(pol.cierre)])
