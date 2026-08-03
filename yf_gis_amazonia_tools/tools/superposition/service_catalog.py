# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Catálogo EDITABLE de geoservicios oficiales.

El catálogo vive en un JSON dentro de la carpeta de configuración del
perfil de QGIS. El usuario lo edita desde el diálogo (o a mano) sin tocar
código: quien trabaje en Colombia, Bolivia o Brasil añade su propio grupo
y sus servicios, y el analizador los consume igual.

REGLA DE ORO: este archivo NO inventa endpoints. Cada servicio lleva un
campo `verificado` con la fecha en que se comprobó su GetCapabilities
real. Un servicio sin verificar se marca como tal y el analizador avisa
antes de usarlo.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import copy
import json
import os

VERSION_CATALOGO = 1

NOMBRE_ARCHIVO = "geoservicios.json"

# ---------------------------------------------------------------------------
# Advertencias legales por entidad. Se propagan al informe.
# ---------------------------------------------------------------------------

ADVERTENCIA_SERFOR = (
    "El geoservicio del SERFOR es referencial. Conforme al artículo 62 de "
    "la Ley N° 29763, Ley Forestal y de Fauna Silvestre, la información "
    "consultada por este medio NO sustituye la opinión técnica oficial de "
    "la autoridad forestal competente, la cual debe solicitarse de manera "
    "expresa para todo procedimiento administrativo o registral."
)

ADVERTENCIA_GENERICA = (
    "Información obtenida de un geoservicio público con carácter "
    "referencial. No sustituye la certificación oficial emitida por la "
    "entidad competente."
)


# ---------------------------------------------------------------------------
# Catálogo de fábrica.
#
# Los servicios del SERFOR fueron verificados contra su GetCapabilities y
# su endpoint ArcGIS REST el 2026-07-30. Los nombres de capa (`typename`)
# y los `rest_id` provienen de esa consulta, no de documentación.
#
# Otras entidades peruanas (SERNANP, INGEMMET/GEOCATMIN, ANA, MINCUL)
# quedan deliberadamente FUERA hasta verificar sus endpoints en vivo.
# Añadirlas sin comprobar produciría un catálogo que falla en campo.
# ---------------------------------------------------------------------------

# ArcGIS Server expone DOS rutas distintas para el mismo servicio:
#   /geoservicios/services/...      -> endpoints OGC (WMSServer, WFSServer)
#   /geoservicios/rest/services/... -> API REST (?f=json, /query, providers)
# Confundirlas devuelve HTTP 403, que se confunde fácilmente con un
# bloqueo por volumen. Verificado el 2026-07-30.
_SERFOR_OGC = ("https://geo.serfor.gob.pe/geoservicios/services/"
               "Servicios_OGC/{servicio}/MapServer")
_SERFOR_REST = ("https://geo.serfor.gob.pe/geoservicios/rest/services/"
                "Servicios_OGC/{servicio}/MapServer")

CATALOGO_FABRICA = {
    "version": VERSION_CATALOGO,
    "grupos": {
        "Perú": {
            "SERFOR — Modalidad de Acceso": {
                "entidad": "SERFOR",
                "tipo": "wfs",
                "url_wfs": _SERFOR_OGC.format(
                    servicio="Modalidad_Acceso") + "/WFSServer",
                "url_rest": _SERFOR_REST.format(servicio="Modalidad_Acceso"),
                "srs": "EPSG:4326",
                "verificado": "2026-07-30",
                "advertencia_legal": ADVERTENCIA_SERFOR,
                "capas": [
                    {"titulo": "Concesiones Forestales",
                     "typename": "Servicios_OGC_Modalidad_Acceso:Concesiones_Forestales",
                     "rest_id": 6, "activa": True},
                    {"titulo": "Permisos",
                     "typename": "Servicios_OGC_Modalidad_Acceso:Permisos",
                     "rest_id": 0, "activa": True},
                    {"titulo": "Cesiones en Uso",
                     "typename": "Servicios_OGC_Modalidad_Acceso:Cesiones_en_Uso",
                     "rest_id": 1, "activa": True},
                    {"titulo": "Autorizaciones PFDM en AVNB",
                     "typename": "Servicios_OGC_Modalidad_Acceso:Autorizaciones_de_PFDM_en_AVNB",
                     "rest_id": 2, "activa": True},
                    {"titulo": "Cambio de uso a fines agropecuarios",
                     "typename": ("Servicios_OGC_Modalidad_Acceso:"
                                  "Autorizacion_de_cambio_de_uso_actual_de_las_"
                                  "tierras_a_fines_agropecuarios"),
                     "rest_id": 3, "activa": True},
                    {"titulo": "Bosques Locales (título habilitante)",
                     "typename": "Servicios_OGC_Modalidad_Acceso:Bosques_Locales",
                     "rest_id": 4, "activa": True},
                    {"titulo": "Unidad de Aprovechamiento",
                     "typename": "Servicios_OGC_Modalidad_Acceso:Unidad_de_Aprovechamiento",
                     "rest_id": 5, "activa": True},
                ],
            },
            "SERFOR — Ordenamiento Forestal": {
                "entidad": "SERFOR",
                # Verificado el 2026-07-30:
                #  - WFS GetCapabilities: HTTP 400 en 1.0.0, 1.1.0 y 2.0.0.
                #    Este servicio no publica WFS; por eso `tipo` es rest.
                #  - Proveedor arcgisfeatureserver sobre /rest/: capa
                #    válida, 22 campos. Es la vía correcta.
                "tipo": "rest",
                "url_wfs": "",
                "url_rest": _SERFOR_REST.format(
                    servicio="Ordenamiento_Forestal"),
                "srs": "EPSG:4326",
                "verificado": "2026-07-30",
                "nota": ("WFS no disponible (HTTP 400 en toda versión). "
                         "Se consume por ArcGIS REST, verificado. "
                         "LENTO: los polígonos de BPP son muy grandes; "
                         "medido 44 s para 2 entidades. Conviene avisar "
                         "al usuario y permitir cancelar."),
                "advertencia_legal": ADVERTENCIA_SERFOR,
                "capas": [
                    {"titulo": "Bosques de Producción Permanente",
                     "typename": "", "rest_id": 2, "activa": True},
                    {"titulo": "Bosques Protectores",
                     "typename": "", "rest_id": 1, "activa": True},
                    {"titulo": "Bosques Locales",
                     "typename": "", "rest_id": 0, "activa": True},
                ],
            },
            "SERFOR — Zonificación Forestal": {
                "entidad": "SERFOR",
                "tipo": "wfs",
                "url_wfs": _SERFOR_OGC.format(
                    servicio="Zonificacion_Forestal") + "/WFSServer",
                "url_rest": _SERFOR_REST.format(
                    servicio="Zonificacion_Forestal"),
                "srs": "EPSG:4326",
                "verificado": "2026-07-30",
                "advertencia_legal": ADVERTENCIA_SERFOR,
                "capas": [
                    {"titulo": "Zonificación Forestal",
                     "typename": "Servicios_OGC_Zonificacion_Forestal:Zonificacion_Forestal",
                     "rest_id": 0, "activa": True},
                ],
            },
            "SERFOR — Inventario Forestal": {
                "entidad": "SERFOR",
                "tipo": "wfs",
                "url_wfs": _SERFOR_OGC.format(
                    servicio="Inventario_Forestal") + "/WFSServer",
                "url_rest": _SERFOR_REST.format(
                    servicio="Inventario_Forestal"),
                "srs": "EPSG:4326",
                "verificado": "2026-07-30",
                "advertencia_legal": ADVERTENCIA_SERFOR,
                "capas": [
                    {"titulo": "Ecosistemas Frágiles",
                     "typename": "Servicios_OGC_Inventario_Forestal:Ecosistemas_Fragiles",
                     "rest_id": 0, "activa": True},
                    {"titulo": "Hábitats Críticos",
                     "typename": "Servicios_OGC_Inventario_Forestal:Habitats_Criticos",
                     "rest_id": 1, "activa": True},
                ],
            },
            "SERFOR — Unidad de Monitoreo Satelital": {
                "entidad": "SERFOR",
                "tipo": "wfs",
                "url_wfs": _SERFOR_OGC.format(
                    servicio="Unidad_Monitoreo_Satelital") + "/WFSServer",
                "url_rest": _SERFOR_REST.format(
                    servicio="Unidad_Monitoreo_Satelital"),
                "srs": "EPSG:4326",
                "verificado": "2026-07-30",
                # Focos de calor son puntos: no generan superposición de
                # área. Se dejan inactivos por defecto.
                "advertencia_legal": ADVERTENCIA_SERFOR,
                "capas": [
                    {"titulo": "Focos de Calor",
                     "typename": "Servicios_OGC_Unidad_Monitoreo_Satelital:FocosdeCalor",
                     "rest_id": 0, "activa": False},
                    {"titulo": "Incendio Forestal",
                     "typename": "Servicios_OGC_Unidad_Monitoreo_Satelital:IncendioForestal",
                     "rest_id": 1, "activa": False},
                ],
            },
            "SERNANP — Áreas Naturales Protegidas": {
                "entidad": "SERNANP",
                # Verificado 2026-07-30: servicio con 67 capas. WFS de
                # interoperabilidad existe aparte, pero REST cubre todo y
                # es el que responde de forma uniforme.
                "tipo": "rest",
                "url_wfs": "",
                "url_rest": ("https://geoservicios.sernanp.gob.pe/arcgis/"
                             "rest/services/sernanp_visor/"
                             "servicio_descarga/MapServer"),
                "srs": "EPSG:4326",
                "verificado": "2026-07-30",
                "nota": ("Ruta bajo /arcgis/rest/services/, distinta a la "
                         "de SERFOR. Las capas 9-11 son zonificación "
                         "interna de cada área; inactivas por defecto."),
                "advertencia_legal": (
                    "Información referencial del SERNANP. Conforme a la "
                    "Ley N° 26834, Ley de Áreas Naturales Protegidas, la "
                    "determinación oficial de superposición con un ANP o "
                    "su zona de amortiguamiento corresponde a la propia "
                    "autoridad, que debe emitir el pronunciamiento "
                    "correspondiente."),
                "capas": [
                    {"titulo": "ANP Nacional Definitiva",
                     "typename": "", "rest_id": 1, "activa": True},
                    {"titulo": "Zona de Amortiguamiento",
                     "typename": "", "rest_id": 8, "activa": True},
                    {"titulo": "Zona Reservada",
                     "typename": "", "rest_id": 2, "activa": True},
                    {"titulo": "Área de Conservación Regional",
                     "typename": "", "rest_id": 3, "activa": True},
                    {"titulo": "Área de Conservación Privada",
                     "typename": "", "rest_id": 4, "activa": True},
                    {"titulo": "Sitios Prioritarios (nivel nacional)",
                     "typename": "", "rest_id": 5, "activa": False},
                    {"titulo": "Zonificación ANP",
                     "typename": "", "rest_id": 9, "activa": False},
                    {"titulo": "Zonificación ACR",
                     "typename": "", "rest_id": 10, "activa": False},
                    {"titulo": "Zonificación ACP",
                     "typename": "", "rest_id": 11, "activa": False},
                ],
            },
            "MIDAGRI — Catastro Rural": {
                "entidad": "MIDAGRI",
                # Verificado 2026-07-30: WFS devuelve HTTP 400; REST sirve
                # las tres capas sin problema.
                "tipo": "rest",
                "url_wfs": "",
                "url_rest": ("https://georural.midagri.gob.pe/geoservicios/"
                             "rest/services/servicios_ogc/Catastro_Rural/"
                             "MapServer"),
                "srs": "EPSG:4326",
                "verificado": "2026-07-30",
                "nota": "WFS no publicado (HTTP 400). Se consume por REST.",
                "advertencia_legal": (
                    "Catastro rural referencial del MIDAGRI. No sustituye "
                    "la información catastral oficial que emite la "
                    "Dirección Regional Agraria competente ni la "
                    "publicidad registral de SUNARP."),
                "capas": [
                    {"titulo": "Predio Rural",
                     "typename": "", "rest_id": 0, "activa": True},
                    {"titulo": "Comunidades Nativas",
                     "typename": "", "rest_id": 2, "activa": True},
                    {"titulo": "Comunidades Campesinas",
                     "typename": "", "rest_id": 1, "activa": True},
                ],
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Ubicación del archivo de configuración
# ---------------------------------------------------------------------------

def carpeta_config():
    """Carpeta de configuración del plugin dentro del perfil de QGIS.

    Fuera de QGIS (tests) cae a una carpeta local, para que el módulo sea
    importable y testeable sin entorno gráfico.
    """
    try:
        from qgis.core import QgsApplication
        base = QgsApplication.qgisSettingsDirPath()
        if base:
            ruta = os.path.join(base, "yf_gis_amazonia_tools", "config")
            return ruta
    except Exception:  # nosec B110 - fuera de QGIS (tests) se cae al
        pass           # directorio local; es el comportamiento buscado
    return os.path.join(os.path.expanduser("~"),
                        ".yf_gis_amazonia_tools", "config")


def ruta_catalogo(carpeta=None):
    return os.path.join(carpeta or carpeta_config(), NOMBRE_ARCHIVO)


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

class ServicioCapa:
    """Una capa concreta de un geoservicio, lista para consumir."""

    __slots__ = ("grupo", "servicio", "titulo", "typename", "rest_id",
                 "tipo", "url_wfs", "url_rest", "srs", "entidad",
                 "advertencia_legal", "verificado")

    def __init__(self, grupo, servicio, titulo, typename, rest_id, tipo,
                 url_wfs, url_rest, srs, entidad, advertencia_legal,
                 verificado):
        self.grupo = grupo
        self.servicio = servicio
        self.titulo = titulo
        self.typename = typename
        self.rest_id = rest_id
        self.tipo = tipo
        self.url_wfs = url_wfs
        self.url_rest = url_rest
        self.srs = srs or "EPSG:4326"
        self.entidad = entidad
        self.advertencia_legal = advertencia_legal
        self.verificado = verificado

    @property
    def nombre_completo(self):
        return "{} — {}".format(self.servicio, self.titulo)

    def soporta_wfs(self):
        return bool(self.tipo == "wfs" and self.url_wfs and self.typename)

    def soporta_rest(self):
        return bool(self.url_rest and self.rest_id is not None)

    def __repr__(self):
        return "<ServicioCapa {}>".format(self.nombre_completo)


def _clave(grupo, servicio):
    return "{}\u2192{}".format(grupo, servicio)


def fusionar_con_fabrica(datos):
    """Incorpora al catálogo del usuario los servicios de fábrica ausentes.

    Sin esto, guardar el catálogo una sola vez congelaba al usuario en la
    versión de ese día: cualquier servicio añadido en una actualización
    posterior del plugin quedaba invisible, porque el JSON del disco tenía
    prioridad absoluta sobre el código.

    Se respeta lo que el usuario tocó: los servicios que ya existen NO se
    modifican, y los que borró a propósito quedan anotados en `eliminados`
    para no resucitarlos en cada arranque.

    Devuelve la lista de servicios incorporados.
    """
    incorporados = []
    grupos = datos.setdefault("grupos", {})
    borrados = set(datos.get("eliminados", []))

    for grupo, servicios in CATALOGO_FABRICA.get("grupos", {}).items():
        destino = grupos.setdefault(grupo, {})
        for nombre, cfg in servicios.items():
            if nombre in destino:
                continue
            if _clave(grupo, nombre) in borrados:
                continue
            destino[nombre] = copy.deepcopy(cfg)
            incorporados.append("{} — {}".format(grupo, nombre))
    return incorporados


class CatalogoServicios:
    """Catálogo de geoservicios, persistido en JSON y editable."""

    def __init__(self, datos=None, ruta=None):
        self.ruta = ruta or ruta_catalogo()
        self.datos = datos if datos is not None else copy.deepcopy(
            CATALOGO_FABRICA)
        # Servicios de fábrica añadidos en el último `cargar()`.
        self.incorporados = []

    # -- persistencia -------------------------------------------------
    @classmethod
    def cargar(cls, ruta=None):
        """Carga el catálogo del disco; si no existe, usa el de fábrica."""
        ruta = ruta or ruta_catalogo()
        if not os.path.exists(ruta):
            return cls(ruta=ruta)
        try:
            with open(ruta, "r", encoding="utf-8") as fh:
                datos = json.load(fh)
        except (ValueError, OSError):
            # JSON corrupto: no se pierde el trabajo del usuario en
            # silencio, se conserva junto al nuevo.
            try:
                os.replace(ruta, ruta + ".corrupto")
            except OSError:
                pass
            return cls(ruta=ruta)
        if not isinstance(datos, dict) or "grupos" not in datos:
            return cls(ruta=ruta)
        cat = cls(datos=datos, ruta=ruta)
        cat.incorporados = fusionar_con_fabrica(cat.datos)
        return cat

    def guardar(self, ruta=None):
        ruta = ruta or self.ruta
        carpeta = os.path.dirname(ruta)
        if carpeta and not os.path.isdir(carpeta):
            os.makedirs(carpeta)
        tmp = ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.datos, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, ruta)
        return ruta

    def restaurar_fabrica(self):
        self.datos = copy.deepcopy(CATALOGO_FABRICA)
        return self.datos

    # -- consulta -----------------------------------------------------
    def grupos(self):
        return sorted(self.datos.get("grupos", {}).keys())

    def servicios(self, grupo):
        return sorted(self.datos.get("grupos", {}).get(grupo, {}).keys())

    def _iter_capas(self, grupo=None, solo_activas=True):
        grupos = self.datos.get("grupos", {})
        for gname, servicios in grupos.items():
            if grupo is not None and gname != grupo:
                continue
            if not isinstance(servicios, dict):
                continue
            for sname, cfg in servicios.items():
                if not isinstance(cfg, dict):
                    continue
                for capa in cfg.get("capas", []):
                    if solo_activas and not capa.get("activa", True):
                        continue
                    yield ServicioCapa(
                        grupo=gname,
                        servicio=sname,
                        titulo=capa.get("titulo", "(sin título)"),
                        typename=capa.get("typename", ""),
                        rest_id=capa.get("rest_id"),
                        tipo=cfg.get("tipo", "wfs"),
                        url_wfs=cfg.get("url_wfs", ""),
                        url_rest=cfg.get("url_rest", ""),
                        srs=cfg.get("srs", "EPSG:4326"),
                        entidad=cfg.get("entidad", ""),
                        advertencia_legal=cfg.get(
                            "advertencia_legal", ADVERTENCIA_GENERICA),
                        verificado=cfg.get("verificado", ""),
                    )

    def capas(self, grupo=None, solo_activas=True):
        return list(self._iter_capas(grupo=grupo, solo_activas=solo_activas))

    def capas_sin_verificar(self):
        return [c for c in self._iter_capas(solo_activas=False)
                if not c.verificado]

    def advertencias_legales(self, capas):
        """Textos legales únicos aplicables a un conjunto de capas."""
        vistos = []
        for c in capas:
            texto = c.advertencia_legal
            if texto and texto not in vistos:
                vistos.append(texto)
        return vistos

    # -- edición ------------------------------------------------------
    def agregar_grupo(self, nombre):
        self.datos.setdefault("grupos", {}).setdefault(nombre, {})
        return nombre

    def agregar_servicio(self, grupo, nombre, url_wfs="", url_rest="",
                         tipo="wfs", srs="EPSG:4326", entidad="",
                         advertencia_legal=None, verificado="", capas=None):
        self.agregar_grupo(grupo)
        self.datos["grupos"][grupo][nombre] = {
            "entidad": entidad,
            "tipo": tipo,
            "url_wfs": url_wfs,
            "url_rest": url_rest,
            "srs": srs,
            "verificado": verificado,
            "advertencia_legal": (advertencia_legal
                                  if advertencia_legal is not None
                                  else ADVERTENCIA_GENERICA),
            "capas": capas or [],
        }
        return self.datos["grupos"][grupo][nombre]

    def eliminar_servicio(self, grupo, nombre):
        try:
            del self.datos["grupos"][grupo][nombre]
        except KeyError:
            return False
        # Si era de fábrica, anotarlo para que la fusión no lo reponga.
        if nombre in CATALOGO_FABRICA.get("grupos", {}).get(grupo, {}):
            borrados = self.datos.setdefault("eliminados", [])
            clave = _clave(grupo, nombre)
            if clave not in borrados:
                borrados.append(clave)
        return True

    def restaurar_servicio(self, grupo, nombre):
        """Devuelve un servicio de fábrica a su definición original."""
        original = CATALOGO_FABRICA.get("grupos", {}).get(grupo, {}).get(nombre)
        if original is None:
            return False
        self.datos.setdefault("grupos", {}).setdefault(grupo, {})[nombre] = (
            copy.deepcopy(original))
        borrados = self.datos.get("eliminados", [])
        clave = _clave(grupo, nombre)
        if clave in borrados:
            borrados.remove(clave)
        return True

    def divergencias_con_fabrica(self):
        """Servicios de fábrica cuyas URLs difieren de las del código.

        Sirve para avisar cuando una corrección del plugin no llega al
        usuario porque su JSON conserva la versión antigua.
        """
        salida = []
        for grupo, servicios in CATALOGO_FABRICA.get("grupos", {}).items():
            actuales = self.datos.get("grupos", {}).get(grupo, {})
            for nombre, cfg in servicios.items():
                mio = actuales.get(nombre)
                if not isinstance(mio, dict):
                    continue
                for campo in ("url_wfs", "url_rest"):
                    if mio.get(campo, "") != cfg.get(campo, ""):
                        salida.append((grupo, nombre, campo,
                                       mio.get(campo, ""), cfg.get(campo, "")))
        return salida

    def marcar_verificado(self, grupo, servicio, fecha):
        try:
            self.datos["grupos"][grupo][servicio]["verificado"] = fecha
            return True
        except KeyError:
            return False
