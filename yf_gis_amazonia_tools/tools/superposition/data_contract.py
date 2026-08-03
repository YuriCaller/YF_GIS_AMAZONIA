# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Contrato de datos.

Este módulo define la ÚNICA estructura de datos que produce el motor de
análisis y que consumen todos los destinos: la tabla de resultados en
pantalla, el GeoPackage de salida y las plantillas de informe (docxtpl).

Definir esto una sola vez es lo que permite que agregar una plantilla
nueva para otra institución NO requiera tocar el motor: la plantilla
recibe siempre el mismo diccionario.

Estructura del contexto:

{
  "analisis": {
      "fecha_iso", "fecha_legible", "plugin_version",
      "predio": {"nombre", "area_ha", "perimetro_m", "crs", "n_partes"},
      "umbral_ha", "metodo_area", "carpeta_capas",
      "capas_evaluadas", "capas_con_superposicion",
      "area_superpuesta_total_ha", "porcentaje_superpuesto_total",
      "nivel_global",
  },
  "superposiciones": [ Superposicion.as_dict(), ... ],   # ordenadas por área desc
  "sin_superposicion": [ {"capa", "archivo", "features"}, ... ],
  "errores":           [ {"capa", "archivo", "motivo"}, ... ],
  "trazabilidad": {
      "archivos": [ {"ruta","nombre","sha256","tamano_bytes","modificado_iso",
                     "crs","features"} ],
      "log": [ "..." ],
  },
}

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from datetime import datetime


# ───────────────────────────────────────────────────────────────────────────
# Niveles de severidad
# ───────────────────────────────────────────────────────────────────────────

NIVEL_CRITICO = "critico"
NIVEL_OBSERVABLE = "observable"
NIVEL_NO_SIGNIFICATIVA = "no_significativa"
NIVEL_LIMPIO = "sin_superposicion"

# Etiquetas legibles para informes y tabla en pantalla
NIVELES_LEGIBLES = {
    NIVEL_CRITICO: "Crítica",
    NIVEL_OBSERVABLE: "Observable",
    NIVEL_NO_SIGNIFICATIVA: "No significativa",
    NIVEL_LIMPIO: "Sin superposición",
}

# Umbrales POR DEFECTO, en porcentaje del área del predio.
# Cada perfil institucional puede redefinirlos (GOREMAD ≠ SERFOR).
UMBRAL_CRITICO_PCT = 5.0
UMBRAL_OBSERVABLE_PCT = 0.5

# Área mínima para considerar una superposición real (ha).
# Por debajo de esto se asume error de digitalización de bordes.
UMBRAL_TOLERANCIA_HA = 0.01


def clasificar_nivel(porcentaje, umbral_critico=UMBRAL_CRITICO_PCT,
                     umbral_observable=UMBRAL_OBSERVABLE_PCT):
    """Clasifica una superposición según el % del predio que afecta.

    Los umbrales son parámetros —no constantes hardcodeadas— porque cada
    institución define su propio criterio de gravedad.
    """
    if porcentaje >= umbral_critico:
        return NIVEL_CRITICO
    if porcentaje >= umbral_observable:
        return NIVEL_OBSERVABLE
    return NIVEL_NO_SIGNIFICATIVA


# ───────────────────────────────────────────────────────────────────────────
# Entidades del contrato
# ───────────────────────────────────────────────────────────────────────────

class Superposicion:
    """Una superposición detectada entre el predio y un derecho preexistente."""

    __slots__ = ("capa", "archivo", "tipo", "titular", "codigo",
                 "area_ha", "porcentaje", "nivel", "atributos", "geometria")

    def __init__(self, capa, archivo, area_ha, porcentaje, nivel,
                 tipo=None, titular=None, codigo=None, atributos=None,
                 geometria=None):
        self.capa = capa
        self.archivo = archivo
        self.tipo = tipo or capa          # "Concesión forestal", "Lote petrolero"...
        self.titular = titular            # nombre del titular, si el campo existe
        self.codigo = codigo              # código/expediente del derecho
        self.area_ha = area_ha
        self.porcentaje = porcentaje
        self.nivel = nivel
        self.atributos = atributos or {}  # fila completa, por si la plantilla la usa
        self.geometria = geometria        # QgsGeometry de la intersección (no va al informe)

    def as_dict(self):
        """Versión serializable — la que ven las plantillas Jinja2."""
        return {
            "capa": self.capa,
            "archivo": self.archivo,
            "tipo": self.tipo,
            "titular": self.titular or "No identificado",
            "codigo": self.codigo or "—",
            "area_ha": round(self.area_ha, 4),
            "porcentaje": round(self.porcentaje, 2),
            "nivel": self.nivel,
            "nivel_legible": NIVELES_LEGIBLES.get(self.nivel, self.nivel),
            "atributos": self.atributos,
        }

    def __repr__(self):
        return "<Superposicion {} {:.4f} ha ({:.2f}%) {}>".format(
            self.capa, self.area_ha, self.porcentaje, self.nivel)


class ResultadoAnalisis:
    """Resultado completo de un análisis de superposición.

    `as_context()` produce el diccionario que consumen las plantillas de
    informe, la tabla de resultados y el exportador de GeoPackage.
    """

    def __init__(self, predio_nombre, predio_area_ha, predio_perimetro_m,
                 predio_crs, carpeta_capas, umbral_ha=UMBRAL_TOLERANCIA_HA,
                 metodo_area="elipsoidal", plugin_version="",
                 predio_n_partes=1,
                 umbral_critico=UMBRAL_CRITICO_PCT,
                 umbral_observable=UMBRAL_OBSERVABLE_PCT):
        self.predio_nombre = predio_nombre
        self.predio_area_ha = predio_area_ha
        self.predio_perimetro_m = predio_perimetro_m
        self.predio_crs = predio_crs
        self.predio_n_partes = predio_n_partes
        self.carpeta_capas = carpeta_capas
        self.umbral_ha = umbral_ha
        self.metodo_area = metodo_area
        self.plugin_version = plugin_version
        self.umbral_critico = umbral_critico
        self.umbral_observable = umbral_observable

        self.superposiciones = []   # [Superposicion]
        self.sin_superposicion = []  # [{"capa","archivo","features"}]
        self.errores = []           # [{"capa","archivo","motivo"}]
        self.archivos_trazabilidad = []  # [dict] — ver traceability.py
        self.log = []               # [str]
        self.fecha = datetime.now()

    # ── registro durante el análisis ──

    def agregar_superposicion(self, sup):
        self.superposiciones.append(sup)

    def agregar_limpia(self, capa, archivo, features=None):
        self.sin_superposicion.append(
            {"capa": capa, "archivo": archivo, "features": features})

    def agregar_error(self, capa, archivo, motivo):
        self.errores.append(
            {"capa": capa, "archivo": archivo, "motivo": str(motivo)})

    def log_msg(self, msg):
        self.log.append(msg)

    # ── métricas derivadas ──

    @property
    def area_superpuesta_total_ha(self):
        """Suma simple de áreas superpuestas.

        OJO: si dos derechos distintos se superponen ENTRE SÍ sobre el
        mismo predio, esta suma cuenta dos veces esa porción. Para el
        área realmente afectada (unión geométrica) ver
        `area_afectada_unica_ha`, que el motor calcula aparte.
        """
        return sum(s.area_ha for s in self.superposiciones)

    @property
    def porcentaje_superpuesto_total(self):
        if not self.predio_area_ha:
            return 0.0
        return (self.area_superpuesta_total_ha / self.predio_area_ha) * 100.0

    @property
    def nivel_global(self):
        """Nivel del hallazgo más grave encontrado."""
        if not self.superposiciones:
            return NIVEL_LIMPIO
        for nivel in (NIVEL_CRITICO, NIVEL_OBSERVABLE, NIVEL_NO_SIGNIFICATIVA):
            if any(s.nivel == nivel for s in self.superposiciones):
                return nivel
        return NIVEL_LIMPIO

    @property
    def capas_evaluadas(self):
        """Capas EFECTIVAMENTE analizadas.

        v3.0.4: antes se sumaban también las capas con error, de modo que
        una fuente que nunca pudo leerse engrosaba el recuento y el
        informe afirmaba haberla contrastado. Una capa caída no es una
        capa evaluada; se cuenta aparte en `capas_no_evaluadas`.
        """
        capas = {s.capa for s in self.superposiciones}
        capas |= {c["capa"] for c in self.sin_superposicion}
        return len(capas)

    @property
    def capas_no_evaluadas(self):
        """Capas que no pudieron consultarse (servicio caído, error, etc.)."""
        return len({c["capa"] for c in self.errores})

    @property
    def capas_totales(self):
        """Capas previstas: evaluadas más no evaluadas."""
        return self.capas_evaluadas + self.capas_no_evaluadas

    @property
    def capas_con_superposicion(self):
        return len({s.capa for s in self.superposiciones})

    # ── contrato final ──

    def as_context(self, area_afectada_unica_ha=None):
        """Diccionario que consumen plantillas, tabla y exportador.

        area_afectada_unica_ha: área de la UNIÓN de todas las
        intersecciones (sin doble conteo). La calcula el motor; si no se
        entrega, se omite del contexto para no publicar un dato dudoso.
        """
        sups = sorted(self.superposiciones,
                      key=lambda s: s.area_ha, reverse=True)

        analisis = {
            "fecha_iso": self.fecha.isoformat(timespec="seconds"),
            "fecha_legible": self.fecha.strftime("%d/%m/%Y %H:%M"),
            "plugin_version": self.plugin_version,
            "predio": {
                "nombre": self.predio_nombre,
                "area_ha": round(self.predio_area_ha, 4),
                "perimetro_m": round(self.predio_perimetro_m, 2),
                "crs": self.predio_crs,
                "n_partes": self.predio_n_partes,
            },
            "umbral_ha": self.umbral_ha,
            "umbral_critico_pct": self.umbral_critico,
            "umbral_observable_pct": self.umbral_observable,
            "metodo_area": self.metodo_area,
            "carpeta_capas": self.carpeta_capas,
            "capas_evaluadas": self.capas_evaluadas,
            "capas_no_evaluadas": self.capas_no_evaluadas,
            "capas_totales": self.capas_totales,
            "capas_con_superposicion": self.capas_con_superposicion,
            "area_superpuesta_total_ha": round(
                self.area_superpuesta_total_ha, 4),
            "porcentaje_superpuesto_total": round(
                self.porcentaje_superpuesto_total, 2),
            "nivel_global": self.nivel_global,
            "nivel_global_legible": NIVELES_LEGIBLES.get(
                self.nivel_global, self.nivel_global),
            "hay_superposicion": bool(self.superposiciones),
            "hay_errores": bool(self.errores),
        }
        if area_afectada_unica_ha is not None:
            analisis["area_afectada_unica_ha"] = round(
                area_afectada_unica_ha, 4)
            if self.predio_area_ha:
                analisis["porcentaje_afectado_unico"] = round(
                    (area_afectada_unica_ha / self.predio_area_ha) * 100.0, 2)

        return {
            "analisis": analisis,
            "superposiciones": [s.as_dict() for s in sups],
            "sin_superposicion": list(self.sin_superposicion),
            "errores": list(self.errores),
            "trazabilidad": {
                "archivos": list(self.archivos_trazabilidad),
                "log": list(self.log),
            },
        }
