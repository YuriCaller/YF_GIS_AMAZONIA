# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Consumo de geoservicios oficiales (WFS y ArcGIS REST).

Convierte entradas del catálogo en objetos `CapaEncontrada` que el motor
de superposición ya sabe analizar. No duplica lógica de intersección:
solo construye el URI correcto y etiqueta el origen.

CLAVE DE DISEÑO — descarga acotada
----------------------------------
El motor filtra con `QgsFeatureRequest().setFilterRect(bbox_predio)`. Con
`restrictToRequestBBOX='1'` en el URI, el proveedor WFS de QGIS traduce
ese rectángulo en un BBOX del GetFeature: se descargan solo las entidades
que rozan el predio, no la capa nacional completa. Sin esa opción, un
análisis contra Concesiones Forestales bajaría todo el Perú.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from .layer_scanner import CapaEncontrada

# Proveedores de QGIS por tipo de servicio.
PROVIDER_WFS = "WFS"
PROVIDER_REST = "arcgisfeatureserver"


def construir_uri_wfs(servicio_capa, restringir_bbox=True):
    """URI para el proveedor WFS de QGIS.

    Verificado el 2026-07-30 contra ArcGIS Server del SERFOR:
    devuelve capa válida y respeta el filtro por BBOX.
    """
    partes = [
        "pagingEnabled='true'",
        "restrictToRequestBBOX='{}'".format("1" if restringir_bbox else "0"),
        "srsname='{}'".format(servicio_capa.srs),
        "typename='{}'".format(servicio_capa.typename),
        "url='{}'".format(servicio_capa.url_wfs),
        "version='auto'",
    ]
    return " ".join(partes)


def construir_uri_rest(servicio_capa):
    """URI para el proveedor ArcGIS Feature Server de QGIS."""
    return "crs='{srs}' url='{url}/{lid}'".format(
        srs=servicio_capa.srs,
        url=servicio_capa.url_rest.rstrip("/"),
        lid=servicio_capa.rest_id,
    )


def uri_para(servicio_capa, restringir_bbox=True):
    """Elige WFS o REST según lo declarado y disponible en el catálogo.

    Devuelve (uri, provider) o (None, None) si la entrada es inservible.
    """
    if servicio_capa.soporta_wfs():
        return (construir_uri_wfs(servicio_capa, restringir_bbox),
                PROVIDER_WFS)
    if servicio_capa.soporta_rest():
        return construir_uri_rest(servicio_capa), PROVIDER_REST
    return None, None


def capa_desde_servicio(servicio_capa, restringir_bbox=True):
    """Construye la `CapaEncontrada` correspondiente.

    No valida la conexión: eso lo hace `preparar_capas`, que puede
    reportar el fallo sin abortar el análisis completo.
    """
    uri, provider = uri_para(servicio_capa, restringir_bbox)
    if uri is None:
        return None

    origen = servicio_capa.url_wfs or servicio_capa.url_rest
    return CapaEncontrada(
        uri=uri,
        nombre=servicio_capa.nombre_completo,
        archivo=origen,
        provider=provider,
        remota=True,
        origen_etiqueta="{} · {}".format(
            servicio_capa.entidad or servicio_capa.grupo,
            servicio_capa.titulo),
    )


# Intervalo mínimo entre peticiones al mismo host, en segundos.
#
# CORRECCIÓN 2026-07-30: una versión previa de este comentario afirmaba
# que el SERFOR bloqueaba por volumen tras ~40 consultas. Era falso. Los
# HTTP 403 observados provenían de pedir rutas REST bajo /services/ en
# vez de /rest/services/; el servidor nunca limitó la tasa.
#
# El control de ritmo se conserva igualmente, por cortesía con servicios
# públicos y porque un diálogo que valide quince capas dispararía quince
# peticiones simultáneas sin él. Pero NO es un requisito conocido del
# SERFOR: si estorba, puede desactivarse con throttle=False.
INTERVALO_MINIMO_S = 1.0

_ultimo_acceso = {}


def _throttle(url):
    """Espacia las peticiones por host para no activar el bloqueo."""
    import time
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc or url
    except Exception:
        host = url
    ahora = time.time()
    previo = _ultimo_acceso.get(host)
    if previo is not None:
        espera = INTERVALO_MINIMO_S - (ahora - previo)
        if espera > 0:
            time.sleep(espera)
    _ultimo_acceso[host] = time.time()


def validar_capa(capa_encontrada, throttle=True):
    """Abre la capa y comprueba que el servicio responde.

    Devuelve (ok, mensaje). Libera siempre el recurso: cada capa remota
    mantiene conexiones abiertas igual que un dataset OGR.

    IMPORTANTE: un fallo aquí significa "no se pudo evaluar", NUNCA "no
    hay superposición". Quien consuma este resultado debe propagarlo como
    incidencia, no como capa limpia.
    """
    try:
        from qgis.core import QgsVectorLayer
    except ImportError:
        return False, "QGIS no disponible en este entorno."

    if throttle:
        _throttle(capa_encontrada.archivo)

    capa = QgsVectorLayer(capa_encontrada.uri, capa_encontrada.nombre,
                          capa_encontrada.provider)
    try:
        if not capa.isValid():
            detalle = ""
            try:
                detalle = capa.error().summary() or ""
            except Exception:
                detalle = ""
            bajo = detalle.lower()
            if "403" in detalle or "forbidden" in bajo:
                return False, ("El servidor rechazó la consulta (403). "
                               "Causa habitual: URL mal formada — los "
                               "endpoints REST van bajo /rest/services/, "
                               "no bajo /services/. Revise el catálogo.")
            if "404" in detalle:
                return False, ("Capa inexistente en el servicio (404). "
                               "Revise el nombre en el catálogo.")
            return False, (detalle or "El servicio no respondió o el "
                                      "nombre de capa no existe.")
        return True, "OK"
    finally:
        try:
            del capa
        except Exception:  # nosec B110 - liberación best-effort en finally;
            pass           # fallar aquí no debe enmascarar el resultado


def preparar_capas(catalogo, grupo=None, validar=True, log=None,
                   restringir_bbox=True):
    """Capas remotas listas para `analizar(..., capas=[...])`.

    Devuelve (capas_ok, incidencias). Una entrada que falla NO aborta el
    análisis: se registra como incidencia y el informe la declara como
    capa no evaluada, que es información legalmente relevante.
    """
    capas_ok = []
    incidencias = []

    for sc in catalogo.capas(grupo=grupo, solo_activas=True):
        ce = capa_desde_servicio(sc, restringir_bbox=restringir_bbox)
        if ce is None:
            incidencias.append((sc.nombre_completo,
                                "Entrada de catálogo incompleta: sin "
                                "typename WFS ni id REST."))
            continue

        if not sc.verificado and log:
            log("AVISO: '{}' no tiene fecha de verificación en el "
                "catálogo.".format(sc.nombre_completo))

        if validar:
            ok, msg = validar_capa(ce)
            if not ok:
                incidencias.append((sc.nombre_completo, msg))
                if log:
                    log("No disponible: {} → {}".format(
                        sc.nombre_completo, msg))
                continue

        capas_ok.append(ce)
        if log:
            log("Servicio listo: {} [{}]".format(ce.nombre, ce.provider))

    return capas_ok, incidencias


def resumen_origenes(catalogo, capas_encontradas):
    """Advertencias legales aplicables a las capas efectivamente usadas."""
    nombres = {c.nombre for c in capas_encontradas}
    usadas = [sc for sc in catalogo.capas(solo_activas=True)
              if sc.nombre_completo in nombres]
    return catalogo.advertencias_legales(usadas)
