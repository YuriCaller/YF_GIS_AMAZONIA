# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Motor de análisis.

Evalúa un predio contra N capas de derechos preexistentes (concesiones
forestales, BPP, predios, lotes de hidrocarburos, comunidades nativas,
ANP...) y produce el ResultadoAnalisis definido en data_contract.py.

Decisiones de diseño importantes:

* El predio se transforma UNA vez al CRS de cada capa (no al revés): así
  se evita reproyectar miles de entidades de una capa nacional.
* El filtro por bounding box (setFilterRect) usa el índice espacial del
  proveedor — sin esto, una capa nacional de concesiones tardaría
  minutos por predio.
* Las geometrías inválidas se reparan con makeValid() antes de
  intersectar: las capas oficiales peruanas vienen con auto-intersecciones
  con frecuencia, y una geometría inválida hace fallar la intersección
  entera en silencio.
* El área se mide sobre el elipsoide por defecto (WGS84), con opción
  planar para cuadrar con planos y partidas registrales — la misma
  distinción que ya aplicamos en Smart Labels.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from .data_contract import (
    ResultadoAnalisis, Superposicion, clasificar_nivel,
    UMBRAL_TOLERANCIA_HA, UMBRAL_CRITICO_PCT, UMBRAL_OBSERVABLE_PCT,
)
from .layer_scanner import escanear_carpeta
from . import traceability

M2_POR_HA = 10000.0

# Heurísticas de detección de campos. El orden importa: el primero que
# aparezca gana. Todo en minúsculas — la comparación es case-insensitive.
CAMPOS_TITULAR = (
    "titular", "nombre", "nom_titula", "razon_soc", "razon_social",
    "propietar", "propietario", "beneficiar", "beneficiario",
    "contratist", "concesiona", "concesionario", "comunidad",
    "nom_com", "denominaci", "denominacion",
)
CAMPOS_CODIGO = (
    "codigo", "cod", "contrato", "n_contrato", "num_contra",
    "expediente", "n_expedien", "cod_conce", "codigo_con",
    "lote", "cod_lote", "id_predio", "cod_predio", "uc", "partida",
)
CAMPOS_TIPO = (
    "tipo", "categoria", "clase", "modalidad", "tipo_dere",
    "tipo_derecho", "uso",
)


def detectar_campo(nombres_campos, candidatos):
    """Primer campo de `candidatos` presente en `nombres_campos`.

    Comparación case-insensitive; devuelve el nombre REAL del campo tal
    como está en la capa (para poder consultarlo después).
    """
    reales = {str(n).lower(): n for n in nombres_campos}
    for cand in candidatos:
        if cand in reales:
            return reales[cand]
    # Segunda pasada: coincidencia parcial (p.ej. "TITULAR_1")
    for cand in candidatos:
        for bajo, real in reales.items():
            if bajo.startswith(cand):
                return real
    return None


def _valor(feature, campo):
    """Valor de un campo como texto limpio, o None."""
    if not campo:
        return None
    try:
        v = feature[campo]
    except (KeyError, IndexError):
        return None
    if v is None:
        return None
    texto = str(v).strip()
    if not texto or texto.upper() in ("NULL", "NONE", "NAN"):
        return None
    return texto


def _reparar(geom):
    """Devuelve una geometría válida, reparándola si hace falta.

    Las capas oficiales peruanas traen auto-intersecciones con
    frecuencia; sin esto, la intersección devuelve vacío o lanza error
    y la superposición pasaría desapercibida.
    """
    if geom is None or geom.isEmpty():
        return None
    try:
        if geom.isGeosValid():
            return geom
        reparada = geom.makeValid()
        if reparada is not None and not reparada.isEmpty():
            return reparada
    except Exception:
        return None
    return None


def _medidor(crs, elipsoidal=True):
    """QgsDistanceArea configurado para medir en el CRS dado."""
    from qgis.core import QgsDistanceArea, QgsProject
    da = QgsDistanceArea()
    da.setSourceCrs(crs, QgsProject.instance().transformContext())
    if elipsoidal:
        da.setEllipsoid("EPSG:7030")  # WGS 84
    return da


def _area_ha(geom, medidor, elipsoidal=True):
    """Área en hectáreas de una geometría."""
    if geom is None or geom.isEmpty():
        return 0.0
    if elipsoidal:
        return float(medidor.measureArea(geom)) / M2_POR_HA
    return float(geom.area()) / M2_POR_HA


def _tipo_poligono():
    """GeometryType.Polygon con compatibilidad Qt5/Qt6.

    QGIS 4 / Qt6 mueve estos enums a formas escopadas; el plugin ya sufrió
    194 correcciones por esto en la migración Qt6, así que aquí se resuelve
    de entrada en vez de asumir.
    """
    from qgis.core import QgsWkbTypes
    # Ver nota en output_export._wkb_multipoligono: indirección getattr
    # para cubrir Qt5 y Qt6 sin literal sin scope.
    return getattr(QgsWkbTypes, "GeometryType",
                   QgsWkbTypes).PolygonGeometry


def analizar_capa(predio_geom, predio_crs, capa_info, medidor,
                  umbral_ha=UMBRAL_TOLERANCIA_HA, elipsoidal=True,
                  predio_area_ha=None, campos_config=None,
                  umbral_critico=UMBRAL_CRITICO_PCT,
                  umbral_observable=UMBRAL_OBSERVABLE_PCT,
                  log=None):
    """Analiza el predio contra UNA capa, liberando SIEMPRE los recursos.

    v3.0.4 fix (fuga de recursos): cada QgsVectorLayer abre un dataset
    OGR/GDAL con file handles. Con decenas o miles de capas por corrida,
    no liberarlos acumula handles y degrada QGIS corrida tras corrida
    (se cuelga o tarda en abrir). El try/finally garantiza la liberación
    por cualquiera de los múltiples caminos de salida.
    """
    from qgis.core import QgsVectorLayer

    info = {"crs": None, "features": None, "candidatas": 0}
    # v3.0.4: el proveedor ya no es siempre "ogr". Una capa de geoservicio
    # necesita "WFS" o "arcgisfeatureserver"; forzar "ogr" la invalidaba.
    provider = getattr(capa_info, "provider", "ogr") or "ogr"
    capa = QgsVectorLayer(capa_info.uri, capa_info.nombre, provider)
    if not capa.isValid():
        # Liberar incluso la capa inválida (abrió handles al intentar)
        try:
            del capa
        except Exception:  # nosec B110 - liberación best-effort de un
            pass           # recurso ya inválido; no hay acción correctiva
        return [], info, "La capa no pudo abrirse (formato o archivo dañado)."
    try:
        return _analizar_capa_impl(
            capa, predio_geom, predio_crs, capa_info, medidor,
            umbral_ha=umbral_ha, elipsoidal=elipsoidal,
            predio_area_ha=predio_area_ha, campos_config=campos_config,
            umbral_critico=umbral_critico,
            umbral_observable=umbral_observable, log=log)
    finally:
        # Liberar explícitamente el dataset OGR: sin esto los file handles
        # se acumulan hasta degradar QGIS.
        try:
            capa.setDataSource("", "", provider)  # cierra el proveedor
        except Exception:  # nosec B110 - si el proveedor ya está cerrado
            pass           # el objetivo (liberar handles) está cumplido
        try:
            del capa
        except Exception:  # nosec B110 - liberación best-effort del objeto
            pass           # capa; los handles ya se cerraron arriba


def _analizar_capa_impl(capa, predio_geom, predio_crs, capa_info, medidor,
                        umbral_ha=UMBRAL_TOLERANCIA_HA, elipsoidal=True,
                        predio_area_ha=None, campos_config=None,
                        umbral_critico=UMBRAL_CRITICO_PCT,
                        umbral_observable=UMBRAL_OBSERVABLE_PCT,
                        log=None):
    """Analiza el predio contra UNA capa.

    Devuelve (lista_superposiciones, info_capa, error_str_o_None).
    info_capa = {"crs":..., "features":..., "candidatas":...}
    """
    from qgis.core import (QgsCoordinateTransform,
                           QgsProject, QgsFeatureRequest, QgsWkbTypes)

    info = {"crs": None, "features": None, "candidatas": 0}
    info["crs"] = capa.crs().authid()
    info["features"] = capa.featureCount()

    if QgsWkbTypes.geometryType(capa.wkbType()) != _tipo_poligono():
        return [], info, "No es una capa de polígonos (se omite del análisis)."

    if not capa.crs().isValid():
        return [], info, ("La capa no tiene CRS definido — no se puede "
                          "comparar con seguridad.")

    # Predio → CRS de la capa (una sola transformación, no N)
    geom_predio_capa = predio_geom
    if capa.crs() != predio_crs:
        try:
            tr = QgsCoordinateTransform(predio_crs, capa.crs(),
                                        QgsProject.instance())
            geom_predio_capa = type(predio_geom)(predio_geom)
            if geom_predio_capa.transform(tr) != 0:
                return [], info, "Falló la reproyección del predio a esta capa."
        except Exception as e:
            return [], info, "Error de reproyección: {}".format(e)

    geom_predio_capa = _reparar(geom_predio_capa)
    if geom_predio_capa is None:
        return [], info, "El predio quedó inválido tras reproyectar."

    # Transformación inversa para medir en el CRS del predio
    tr_inv = None
    if capa.crs() != predio_crs:
        tr_inv = QgsCoordinateTransform(capa.crs(), predio_crs,
                                        QgsProject.instance())

    campos = [f.name() for f in capa.fields()]
    cfg = (campos_config or {}).get(capa_info.nombre, {})
    campo_titular = cfg.get("titular") or detectar_campo(campos, CAMPOS_TITULAR)
    campo_codigo = cfg.get("codigo") or detectar_campo(campos, CAMPOS_CODIGO)
    campo_tipo = cfg.get("tipo") or detectar_campo(campos, CAMPOS_TIPO)

    # Filtro rápido por bbox: usa el índice del proveedor
    request = QgsFeatureRequest().setFilterRect(geom_predio_capa.boundingBox())

    superposiciones = []
    for feat in capa.getFeatures(request):
        info["candidatas"] += 1
        g = _reparar(feat.geometry())
        if g is None:
            continue
        try:
            if not g.intersects(geom_predio_capa):
                continue
            inter = g.intersection(geom_predio_capa)
        except Exception:  # nosec B112 - geometría corrupta en el origen:
            continue       # se omite esa entidad y el análisis prosigue
        inter = _reparar(inter)
        if inter is None:
            continue

        # Medir en el CRS del predio (coherencia con el área del predio)
        inter_medida = inter
        if tr_inv is not None:
            try:
                inter_medida = type(inter)(inter)
                if inter_medida.transform(tr_inv) != 0:
                    inter_medida = inter
            except Exception:
                inter_medida = inter

        area = _area_ha(inter_medida, medidor, elipsoidal)
        if area < umbral_ha:
            continue

        pct = (area / predio_area_ha * 100.0) if predio_area_ha else 0.0
        atributos = {}
        for n in campos:
            v = _valor(feat, n)
            if v is not None:
                atributos[n] = v

        superposiciones.append(Superposicion(
            capa=capa_info.nombre,
            archivo=capa_info.origen_corto(),
            area_ha=area,
            porcentaje=pct,
            nivel=clasificar_nivel(pct, umbral_critico, umbral_observable),
            tipo=_valor(feat, campo_tipo) or capa_info.nombre,
            titular=_valor(feat, campo_titular),
            codigo=_valor(feat, campo_codigo),
            atributos=atributos,
            geometria=inter_medida,
        ))

    if log and superposiciones:
        log("{}: {} superposición(es), {:.4f} ha".format(
            capa_info.nombre, len(superposiciones),
            sum(s.area_ha for s in superposiciones)))
    return superposiciones, info, None


def analizar(predio_geom, predio_crs, carpeta_capas,
             predio_nombre="Predio evaluado",
             umbral_ha=UMBRAL_TOLERANCIA_HA,
             elipsoidal=True, recursivo=True, campos_config=None,
             plugin_version="", umbral_critico=UMBRAL_CRITICO_PCT,
             umbral_observable=UMBRAL_OBSERVABLE_PCT,
             capas=None, progreso=None):
    """Análisis completo: predio contra todas las capas de una carpeta.

    predio_geom : QgsGeometry del área evaluada (en predio_crs)
    predio_crs  : QgsCoordinateReferenceSystem del predio
    carpeta_capas: carpeta raíz con los derechos preexistentes
    capas       : opcional, lista de CapaEncontrada ya escaneada
    progreso    : callable(actual, total, nombre) para la barra de
                  avance. Si devuelve False, el análisis se detiene y
                  las capas pendientes quedan como no evaluadas.

    Devuelve (ResultadoAnalisis, area_afectada_unica_ha).
    """
    medidor = _medidor(predio_crs, elipsoidal)
    predio_valido = _reparar(predio_geom)
    if predio_valido is None:
        raise ValueError("La geometría del predio es inválida o está vacía.")

    area_predio = _area_ha(predio_valido, medidor, elipsoidal)
    perim = 0.0
    try:
        perim = (float(medidor.measurePerimeter(predio_valido)) if elipsoidal
                 else float(predio_valido.length()))
    except Exception:
        perim = 0.0

    n_partes = 1
    try:
        if predio_valido.isMultipart():
            n_partes = len(predio_valido.asGeometryCollection())
    except Exception:
        n_partes = 1

    res = ResultadoAnalisis(
        predio_nombre=predio_nombre,
        predio_area_ha=area_predio,
        predio_perimetro_m=perim,
        predio_crs=predio_crs.authid() if hasattr(predio_crs, "authid") else str(predio_crs),
        carpeta_capas=carpeta_capas,
        umbral_ha=umbral_ha,
        metodo_area="elipsoidal (WGS84)" if elipsoidal else "planar",
        plugin_version=plugin_version,
        predio_n_partes=n_partes,
        umbral_critico=umbral_critico,
        umbral_observable=umbral_observable,
    )
    res.log_msg("Predio: {:.4f} ha ({}), método {}".format(
        area_predio, res.predio_crs, res.metodo_area))

    if capas is None:
        capas = escanear_carpeta(carpeta_capas, recursivo, log=res.log_msg)
    total = len(capas)
    if total == 0:
        res.log_msg("No se encontraron capas vectoriales en la carpeta.")
        return res, 0.0

    geometrias_inter = []
    for i, capa_info in enumerate(capas, start=1):
        if progreso:
            # v3.0.4: si el callback devuelve False, el usuario canceló.
            # Las capas que quedan pendientes NO se omiten en silencio: se
            # registran como no evaluadas, para que el informe declare la
            # cobertura incompleta en vez de dar por limpio lo no revisado.
            if progreso(i, total, capa_info.nombre) is False:
                for pendiente in capas[i - 1:]:
                    res.agregar_error(
                        pendiente.nombre, pendiente.origen_corto(),
                        "No evaluada: análisis cancelado por el usuario.")
                res.log_msg(
                    "Análisis cancelado por el usuario en la capa {} de {}."
                    .format(i, total))
                break
        try:
            sups, info, error = analizar_capa(
                predio_valido, predio_crs, capa_info, medidor,
                umbral_ha=umbral_ha, elipsoidal=elipsoidal,
                predio_area_ha=area_predio, campos_config=campos_config,
                umbral_critico=umbral_critico,
                umbral_observable=umbral_observable, log=res.log_msg)
        except Exception as e:
            res.agregar_error(capa_info.nombre,
                              capa_info.origen_corto(), e)
            res.log_msg("ERROR en {}: {}".format(capa_info.nombre, e))
            continue

        # Ficha de trazabilidad: se registra SIEMPRE, haya o no
        # superposición — probar que una capa se evaluó y salió limpia
        # es tan importante como reportar la que sí cruza.
        # v3.0.4: una capa remota no tiene archivo que hashear. Su ficha
        # documenta la INSTANTÁNEA consultada (URL, hora, conteo), que es
        # una garantía de naturaleza distinta y así se declara.
        if getattr(capa_info, "remota", False):
            res.archivos_trazabilidad.append(traceability.ficha_servicio(
                capa_info.archivo, uri=capa_info.uri,
                provider=getattr(capa_info, "provider", ""),
                crs=info.get("crs"), features=info.get("features"),
                nombre_capa=capa_info.nombre))
        else:
            res.archivos_trazabilidad.append(traceability.ficha_archivo(
                capa_info.archivo, crs=info.get("crs"),
                features=info.get("features"), nombre_capa=capa_info.nombre))

        if error:
            res.agregar_error(capa_info.nombre,
                              capa_info.origen_corto(), error)
            res.log_msg("{}: {}".format(capa_info.nombre, error))
            continue

        if sups:
            for s in sups:
                res.agregar_superposicion(s)
                if s.geometria is not None:
                    geometrias_inter.append(s.geometria)
        else:
            res.agregar_limpia(capa_info.nombre,
                               capa_info.origen_corto(),
                               info.get("features"))

    area_unica = _area_afectada_unica(geometrias_inter, medidor, elipsoidal)
    res.log_msg(
        "Resultado: {} superposición(es) en {} capa(s); "
        "área afectada (sin doble conteo): {:.4f} ha".format(
            len(res.superposiciones), res.capas_con_superposicion, area_unica))
    return res, area_unica


def _area_afectada_unica(geometrias, medidor, elipsoidal=True):
    """Área de la UNIÓN de todas las intersecciones.

    Necesaria porque dos derechos distintos pueden solaparse entre sí
    sobre el mismo pedazo de predio: sumar sus áreas daría más superficie
    afectada que la que realmente existe — un error que en un informe
    técnico se nota y se objeta.
    """
    if not geometrias:
        return 0.0
    try:
        union = geometrias[0]
        for g in geometrias[1:]:
            union = union.combine(g)
        union = _reparar(union)
        return _area_ha(union, medidor, elipsoidal)
    except Exception:
        return 0.0
