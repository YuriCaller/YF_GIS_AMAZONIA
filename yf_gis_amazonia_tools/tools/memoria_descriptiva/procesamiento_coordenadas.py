# -*- coding: utf-8 -*-
"""
Procesamiento de coordenadas para Memoria Descriptiva.
VERSIÓN 3.0 — Lógica basada en la estructura real:
  - AREA_TOTAL (polígonos): fid, NombresApellidos, Area_ha, Perímetro
  - Puntos: ID_Poligono, ID_Vertice, LADO, Este, Norte, Distancia, Azimut
  - perimetros: ID_Poligono, ID_Segmento, longitud, azimut (opcional)
"""

import logging
import re
import math
from qgis.core import QgsUnitTypes, QgsDistanceArea, QgsFeatureRequest

from ...core import formato_catastral as fc


def obtener_vertices_de_poligono(punto_layer, id_poligono, campos_config=None):
    """
    Obtiene los vértices de UN polígono específico filtrando por ID_Poligono.

    Estrategia de filtrado (en orden de preferencia):
      1. Campo configurado en campos_config['campo_id_poligono']
      2. Auto-detección por nombres conocidos: ID_Poligono, id_poligono, fid_area, poligono_id
      3. Si no existe campo de relación, usa TODOS los puntos ordenados

    Args:
        punto_layer   : QgsVectorLayer de puntos
        id_poligono   : valor del ID a filtrar (int o str)
        campos_config : dict con configuración de campos

    Returns:
        Lista de dicts con: vertice, lado, este, norte, distancia, azimut
    """
    if campos_config is None:
        campos_config = {}

    # ── Detectar campo de relación ────────────────────────────────────────────
    campo_rel = campos_config.get('campo_id_poligono')
    if not campo_rel:
        campo_rel = _detectar_campo(punto_layer,
            ['ID_Poligono', 'id_poligono', 'fid_area', 'poligono_id',
             'id_pol', 'pol_id', 'ID_POL', 'FID_area', 'fid_pol'])

    # ── Filtrar features ──────────────────────────────────────────────────────
    if campo_rel:
        try:
            id_val = int(id_poligono)
        except (ValueError, TypeError):
            id_val = id_poligono

        # Intentar expresión SQL primero (rápido)
        puntos = []
        try:
            campo_field = next((f for f in punto_layer.fields()
                                if f.name() == campo_rel), None)
            # Detección robusta de tipo numérico en PyQGIS 3.x
            # QVariant: Int=2, LongLong=4, Double=6, UInt=7, ULongLong=8
            TIPOS_NUM = {2, 4, 6, 7, 8}
            es_num = False
            if campo_field is not None:
                if campo_field.type() in TIPOS_NUM:
                    es_num = True
                else:
                    tn = campo_field.typeName().lower()
                    es_num = any(t in tn for t in ('int','long','double','float','real','numeric'))
            if es_num:
                expr = '"{}" = {}'.format(campo_rel, id_val)
            else:
                expr = '"{}" = \'{}\''.format(campo_rel, id_val)
            req = QgsFeatureRequest()
            req.setFilterExpression(expr)
            puntos = list(punto_layer.getFeatures(req))
            print("  Filtro SQL '{}': {} puntos".format(expr, len(puntos)))
        except Exception as e:
            print("  Error filtro SQL: {}".format(e))
            puntos = []

        # Fallback manual si SQL no devolvió nada
        if not puntos:
            print("  Fallback manual: buscando {} = {}...".format(campo_rel, id_val))
            for f in punto_layer.getFeatures():
                val = f[campo_rel]
                if val is None:
                    continue
                try:
                    if int(val) == int(id_val):
                        puntos.append(f)
                except (ValueError, TypeError):
                    if str(val).strip() == str(id_val).strip():
                        puntos.append(f)
            print("  Fallback encontró: {} puntos".format(len(puntos)))
    else:
        puntos = list(punto_layer.getFeatures())
        print("  Sin campo relación: usando todos los {} puntos".format(len(puntos)))

    if not puntos:
        return []

    # ── Ordenar por ID_Vertice ────────────────────────────────────────────────
    campo_orden = campos_config.get('campo_vertice') or _detectar_campo(
        punto_layer, ['ID_Vertice', 'id_vertice', 'orden', 'id', 'fid', 'secuencia'])

    if campo_orden:
        try:
            puntos.sort(key=lambda f: _to_float(f[campo_orden]))
        except Exception as e:
            print("  Advertencia ordenando por {}: {}".format(campo_orden, e))
    
    # ── Extraer datos de cada punto ───────────────────────────────────────────
    # Detectar campos de datos
    c_lado  = campos_config.get('campo_lado')      or _detectar_campo(punto_layer, ['LADO', 'lado', 'side', 'segment', 'tramo'])
    c_este  = campos_config.get('campo_este')      or _detectar_campo(punto_layer, ['Este', 'este', 'ESTE', 'X', 'x', 'coord_x', 'easting'])
    c_norte = campos_config.get('campo_norte')     or _detectar_campo(punto_layer, ['Norte', 'norte', 'NORTE', 'Y', 'y', 'coord_y', 'northing'])
    c_dist  = campos_config.get('campo_distancia') or _detectar_campo(punto_layer, ['Distancia', 'distancia', 'DISTANCIA', 'distance', 'dist', 'longitud'])
    c_az    = campos_config.get('campo_azimut')    or _detectar_campo(punto_layer, ['Azimut', 'azimut', 'AZIMUT', 'azimuth', 'rumbo', 'bearing'])
    c_vid   = campos_config.get('campo_vertice')   or _detectar_campo(punto_layer, ['ID_Vertice', 'id_vertice', 'vertice', 'ID', 'id'])

    vertices = []
    n = len(puntos)

    for i, punto in enumerate(puntos):
        geom = punto.geometry()
        if not geom or geom.isEmpty():
            continue
        coord = geom.asPoint()

        # ID del vértice — normalizado con patrón uniforme (default 'V-{n}')
        patron = campos_config.get('patron_vertice', 'V-{n}')
        vid_raw = _get_val_str(punto, c_vid)
        num_v = fc.extraer_numero_vertice(vid_raw)
        if num_v is None:
            num_v = i + 1
        vid = fc.normalizar_etiqueta(num_v, patron)

        # Coordenadas (campo BD o geometría)
        este  = _get_val_num(punto, c_este)
        norte = _get_val_num(punto, c_norte)
        if este  is None: este  = coord.x()
        if norte is None: norte = coord.y()

        # Distancia y azimut (campo BD o calcular después)
        distancia = _get_val_num(punto, c_dist)
        azimut    = _get_val_num(punto, c_az)

        # Lado
        lado = _get_val_str(punto, c_lado)

        vertices.append({
            'vertice': vid, 'lado': lado,
            'este': este,   'norte': norte,
            'distancia': distancia, 'azimut': azimut,
            '_x': coord.x(), '_y': coord.y()
        })

    # ── Completar distancias/azimuts/lados faltantes ─────────────────────────
    # IMPORTANTE: el pop de _x/_y se hace en un segundo loop separado para que
    # el último vértice pueda acceder a vertices[0]['_x'] sin que ya esté eliminado.
    n = len(vertices)
    usar_lado_bd = campos_config.get('usar_lado_bd', False)
    for i, v in enumerate(vertices):
        sig = vertices[(i + 1) % n]

        # LADO: regenerado con etiquetas normalizadas para garantizar
        # congruencia con la columna VÉRTICE (salvo que se pida usar el BD)
        if not usar_lado_bd or not v['lado']:
            v['lado'] = fc.etiqueta_lado(v['vertice'], sig['vertice'])

        # Distancia y azimut calculados desde las MISMAS coordenadas de la
        # tabla (Este/Norte) — fuente única de verdad
        d_calc = fc.distancia_desde_coordenadas(
            v['este'], v['norte'], sig['este'], sig['norte'])
        az_calc = fc.azimut_desde_coordenadas(
            v['este'], v['norte'], sig['este'], sig['norte'])

        # Distancia: el atributo BD manda (norma: 2 decimales) pero se valida
        if v['distancia'] is None or v['distancia'] == 0.0:
            v['distancia'] = round(d_calc, 2)
        elif abs(v['distancia'] - d_calc) > 0.05:
            print("  \u26a0 {}: distancia BD {:.2f} m difiere de geometr\u00eda {:.2f} m".format(
                v['vertice'], v['distancia'], d_calc))

        # Azimut: el atributo BD (generado por el Segmentador) es la fuente
        # autoritativa — la memoria RECOPILA, no recalcula. El cálculo desde
        # coordenadas es solo respaldo cuando el campo está vacío.
        if v['azimut'] is None:
            v['azimut'] = round(az_calc, 1) if az_calc is not None else 0.0
            print("  ⓘ {}: azimut vacío en BD — calculado desde coordenadas: {}".format(
                v['vertice'], v['azimut']))
        elif az_calc is not None and fc.diferencia_angular(v['azimut'], az_calc) > 0.5:
            # Solo advertencia informativa; el documento usa el valor BD intacto
            print("  ⚠ {}: azimut BD {} difiere del geométrico {:.1f} (se usa BD)".format(
                v['vertice'], v['azimut'], az_calc))

    # Segundo loop: limpiar claves internas DESPUÉS de todos los cálculos
    for v in vertices:
        v.pop('_x', None); v.pop('_y', None)

    # Advertir sobre segmentos de distancia cero (vértices duplicados)
    ceros = [v['vertice'] for v in vertices if v['distancia'] == 0.0]
    if ceros:
        print("  ⚠ Advertencia: {} vértice(s) con distancia=0 (posibles duplicados): {}".format(
            len(ceros), ceros))

    return vertices


def _valor_util(feature, campo):
    """Valor numerico de un campo, o None si no sirve como dato.

    Un 0, un NULL o un vacio son AUSENCIA de dato, no un area de cero
    hectareas. La version anterior usaba `if val is not None`, con lo que
    un campo en 0.0 se aceptaba como valido y nunca se caia a la
    geometria: la memoria salia con 0.0000 ha.
    """
    if not campo:
        return None
    if campo not in [f.name() for f in feature.fields()]:
        return None
    val = feature[campo]
    if val is None or val == "":
        return None
    try:
        num = float(val)
    except (ValueError, TypeError):
        return None
    return None if num == 0 else num


def _interpretar_unidad(val, area_geom_ha):
    """Decide si `val` esta en hectareas o en m2 comparando con la geometria.

    La heuristica anterior era `if val > 5000: son m2`. Funciona en predios
    rurales y falla en urbanos: un lote de 3000 m2 quedaba por debajo del
    umbral, se leia como hectareas y la memoria declaraba 3000 ha en vez
    de 0.3. Comparar contra la geometria no tiene ese punto ciego, porque
    el area verdadera siempre esta ahi para desempatar.

    Devuelve (area_ha, unidad_detectada).
    """
    como_ha = val
    como_m2 = val / 10000.0
    if area_geom_ha and area_geom_ha > 0:
        if abs(como_m2 - area_geom_ha) < abs(como_ha - area_geom_ha):
            return round(como_m2, 6), "m2"
        return round(como_ha, 6), "ha"
    # sin geometria de referencia, el umbral clasico como ultimo recurso
    return (round(como_m2, 6), "m2") if val > 5000 else (round(como_ha, 6), "ha")


def _desvio_minimo(val, referencias):
    """Desvio relativo de `val` respecto a la referencia mas cercana.

    Se compara contra la medida elipsoidal Y la plana. Motivo: el campo de
    un shapefile casi siempre se calculo en UTM plano (ArcGIS, calculadora
    de campos), mientras la herramienta reporta medida elipsoidal. Esa sola
    diferencia ya vale ~0.06% en Madre de Dios, y avisaria de un campo que
    en realidad esta bien. Solo interesa el valor que no cuadra con ninguna
    de las dos.
    """
    refs = [r for r in referencias if r and r > 0]
    if not refs:
        return 0.0
    return min(abs(val - r) / r for r in refs)


def calcular_area_perimetro_feature(feature, pol_layer, campos_config=None,
                                    tolerancia_aviso=0.001):
    """
    Obtiene area y perimetro de un feature de poligono.
    Prioridad: campo BD -> geometria WGS84.

    Un campo en 0, NULL o vacio se considera ausente y se usa la
    geometria. Si el valor del campo se aparta de la geometria mas de
    `tolerancia_aviso` (0.5% por defecto), se respeta el campo pero se
    devuelve un aviso: es sintoma de un area calculada antes de editar la
    geometria, y una memoria cuyo apartado de area no cuadra con su propio
    cuadro de vertices es rechazable en registro.

    Returns:
        dict: area (ha), perimetro (m), fuente_area, fuente_perimetro,
              avisos (lista de str)
    """
    if campos_config is None:
        campos_config = {}

    geom = feature.geometry()
    avisos = []

    da = QgsDistanceArea()
    da.setEllipsoid('WGS84')
    try:
        area_geom_ha = round(da.measureArea(geom) / 10000, 6)
        perim_geom_m = round(da.measurePerimeter(geom), 4)
    except Exception:
        area_geom_ha = round(geom.area() / 10000, 6)
        perim_geom_m = round(geom.length(), 4)

    # medida plana, como referencia adicional para el aviso de desvio
    try:
        area_plana_ha = round(geom.area() / 10000, 6)
        perim_plano_m = round(geom.length(), 4)
    except Exception:
        area_plana_ha, perim_plano_m = area_geom_ha, perim_geom_m

    # -- Campo BD para area -------------------------------------------------
    # POLY_AREA / Shape_Area / SHAPE_STAr son los nombres que genera ArcGIS
    # con Calculate Geometry, y son los que mas llegan en expedientes.
    c_area = campos_config.get('campo_area') or _detectar_campo(
        pol_layer, ['Area_ha', 'area_ha', 'AREA_HA', 'area', 'AREA',
                    'hectareas', 'Hectareas', 'HECTAREAS', 'superficie',
                    'POLY_AREA', 'poly_area', 'Shape_Area', 'SHAPE_Area',
                    'shape_area', 'SHAPE_STAr', 'area_m2', 'AREA_M2'])
    area_ha = None
    fuente_area = 'geometria'

    val = _valor_util(feature, c_area)
    if val is not None:
        area_ha, unidad = _interpretar_unidad(val, area_geom_ha)
        fuente_area = 'campo BD "{}"{}'.format(
            c_area, ' (convertido de m2)' if unidad == 'm2' else '')
        desvio = _desvio_minimo(area_ha, [area_geom_ha, area_plana_ha])
        if desvio > tolerancia_aviso:
            avisos.append(
                'El area del campo "{}" ({:.4f} ha) difiere {:.2%} de la '
                'geometria ({:.4f} ha, {:.0f} m2 de diferencia). Suele '
                'significar que el campo se calculo antes de editar el '
                'poligono. El cuadro de vertices de la memoria describe la '
                'geometria, no el campo: si no coinciden, el documento se '
                'contradice a si mismo.'
                .format(c_area, area_ha, desvio, area_geom_ha,
                        abs(area_ha - area_geom_ha) * 10000))

    if area_ha is None:
        area_ha = area_geom_ha
        fuente_area = 'geometria (WGS84)'

    # -- Campo BD para perimetro --------------------------------------------
    c_perim = campos_config.get('campo_perimetro') or _detectar_campo(
        pol_layer, ['Perimetro', 'PERIMETRO', 'perimetro', 'Per\u00edmetro',
                    'perimeter', 'PERIMETER', 'shape_length', 'Shape_Length',
                    'Shape_Leng', 'SHAPE_STLe'])
    perim_m = None
    fuente_perim = 'geometria'

    val = _valor_util(feature, c_perim)
    if val is not None:
        perim_m = val
        fuente_perim = 'campo BD "{}"'.format(c_perim)
        desvio = _desvio_minimo(perim_m, [perim_geom_m, perim_plano_m])
        if desvio > tolerancia_aviso:
            avisos.append(
                'El perimetro del campo "{}" ({:.2f} m) difiere {:.2%} de la '
                'geometria ({:.2f} m).'
                .format(c_perim, perim_m, desvio, perim_geom_m))

    if perim_m is None:
        perim_m = perim_geom_m
        fuente_perim = 'geometria (WGS84)'

    print("  Area: {:.4f} ha [{}]  |  Perimetro: {:.2f} m [{}]".format(
        area_ha, fuente_area, perim_m, fuente_perim))
    for a in avisos:
        print("  AVISO: {}".format(a))

    return {'area': area_ha, 'perimetro': perim_m,
            'fuente_area': fuente_area, 'fuente_perimetro': fuente_perim,
            'area_geometria': area_geom_ha, 'perimetro_geometria': perim_geom_m,
            'avisos': avisos}


def generar_descripcion_linderos(vertices, modo_azimut=None, decimales_azimut=None):
    """Descripción narrativa de linderos, coherente con la tabla y el plano.

    modo_azimut: 'decimal' (default, igual al plano), 'gms' o 'ambos'.
    """
    if not vertices:
        return "No se encontraron vértices para este polígono."
    n = len(vertices)
    if n < 3:
        return "Se encontraron solo {} vértice(s); se necesitan al menos 3 para describir linderos.".format(n)
    partes = ["Comienza en el vértice {}".format(vertices[0]['vertice'])]
    for i, v in enumerate(vertices):
        sig = vertices[(i + 1) % n]
        dist = v.get('distancia') or 0.0
        az   = v.get('azimut')   or 0.0
        partes.append(
            "{} y una distancia de {:.2f} m llega al vértice {}".format(
                fc.frase_azimut_narrativa(az, modo_azimut, decimales_azimut),
                dist, sig['vertice']))
    return "; ".join(partes) + "; cerrando así el perímetro del predio."


NOMBRES_PROYECCION = {
    'utm': 'Transversa de Mercator (UTM)',
    'tmerc': 'Transversa de Mercator',
    'merc': 'Mercator',
    'omerc': 'Mercator Oblicua',
    'lcc': 'Conica Conforme de Lambert',
    'aea': 'Conica de Areas Iguales de Albers',
    'laea': 'Azimutal de Areas Iguales de Lambert',
    'stere': 'Estereografica',
    'sterea': 'Estereografica Oblicua',
    'poly': 'Policonica',
    'cea': 'Cilindrica de Areas Iguales',
    'eqc': 'Equidistante Cilindrica',
    'sinu': 'Sinusoidal',
    'moll': 'Mollweide',
    'robin': 'Robinson',
    'longlat': 'Geografica (coordenadas angulares)',
}


def _parametros_proj(crs):
    """Cadena PROJ del SRC como diccionario de parametros."""
    txt = crs.toProj()
    params = {}
    for tok in txt.strip().split():
        if tok.startswith('+'):
            clave, _, val = tok[1:].partition('=')
            params[clave] = val or True
    return params


def _meridiano_gms(lon):
    hemi = 'W' if lon < 0 else 'E'
    lon = abs(lon)
    grados = int(lon)
    minutos = int(round((lon - grados) * 60))
    return u"{}\u00b0{}{}".format(grados,
                                  "{:02d}'".format(minutos) if minutos else '',
                                  hemi)


def _nombre_elipsoide(crs):
    """Nombre legible del elipsoide.

    ellipsoidAcronym() devuelve el codigo ('EPSG:7030'), no sirve para un
    documento. QgsEllipsoidUtils lo resuelve a 'WGS 84', 'International
    1924', etc.
    """
    acronimo = crs.ellipsoidAcronym()
    try:
        from qgis.core import QgsEllipsoidUtils
        for d in QgsEllipsoidUtils.definitions():
            if d.acronym == acronimo:
                return d.description.split(' (')[0].strip()
    except Exception:
        logging.getLogger(__name__).debug("suppressed", exc_info=True)
    return acronimo


def descripcion_proyeccion(crs):
    """Proyeccion cartografica del SRC, redactada para la memoria.

    Sustituye al antiguo campo 'Grillado', que era un texto fijo y no
    describia nada del proyecto. Para UTM incluye zona, hemisferio,
    meridiano central y factor de escala, que son los parametros que
    permiten reproducir las coordenadas del cuadro de vertices.
    """
    if crs.isGeographic():
        return NOMBRES_PROYECCION['longlat']

    params = _parametros_proj(crs)
    acronimo = crs.projectionAcronym() or params.get('proj', '')
    base = NOMBRES_PROYECCION.get(acronimo)
    if not base:
        try:
            base = crs.operation().description()
        except Exception:
            base = acronimo or 'Proyectada'

    if acronimo == 'utm' and 'zone' in params:
        zona = int(params['zone'])
        hemisferio = 'Sur' if params.get('south') else 'Norte'
        merid = zona * 6 - 183
        return u'{}, zona {} {}, meridiano central {}, factor de escala 0,9996'.format(
            base, zona, hemisferio, _meridiano_gms(merid))

    partes = [base]
    if 'lon_0' in params:
        try:
            partes.append(u'meridiano central ' + _meridiano_gms(float(params['lon_0'])))
        except (ValueError, TypeError):
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
    factor = params.get('k_0') or params.get('k')
    if factor and factor is not True:
        partes.append(u'factor de escala {}'.format(str(factor).replace('.', ',')))
    return u', '.join(partes)


def obtener_info_sistema_coordenadas(layer):
    """Info del SRC de la capa para el apartado tecnico del mapa.

    El datum se toma del propio SRC. La version anterior extraia solo el
    numero de zona con una expresion regular y escribia 'Datum WGS 84'
    literal, de modo que una capa en PSAD56 o Peru96 se declaraba como
    WGS 84 en la memoria: un datum falso en un documento registral.
    """
    crs = layer.crs()
    desc = crs.description()

    if '/' in desc:
        datum, resto = [t.strip() for t in desc.split('/', 1)]
    else:
        datum, resto = desc.strip(), ''

    zona = re.search(r'zone\s*(\d+)\s*([NS])?', resto, re.IGNORECASE)
    if zona:
        hemisferio = {'S': 'Sur', 'N': 'Norte'}.get(
            (zona.group(2) or '').upper(), '')
        resto = 'UTM zona {} {}'.format(zona.group(1), hemisferio).strip()

    sistema = 'Datum {}{}'.format(datum, ', ' + resto if resto else '')
    if crs.authid():
        sistema = '{} ({})'.format(sistema, crs.authid())

    try:
        unidades = QgsUnitTypes.toString(crs.mapUnits()).capitalize()
    except Exception:
        unidades = 'Metros'

    return {'Sistema de coordenadas': sistema,
            'Unidades': unidades,
            'Elipsoide': _nombre_elipsoide(crs),
            u'Proyecci\u00f3n': descripcion_proyeccion(crs)}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _detectar_campo(layer, nombres_posibles):
    """Busca el primer campo que coincida con la lista (case-insensitive)."""
    campos = {f.name().lower(): f.name() for f in layer.fields()}
    for n in nombres_posibles:
        if n.lower() in campos:
            return campos[n.lower()]
    return None


def _get_val_num(feature, campo):
    if not campo: return None
    try:
        v = feature[campo]
        return float(v) if v is not None else None
    except Exception: return None


def _get_val_str(feature, campo):
    if not campo: return None
    try:
        v = feature[campo]
        return str(v).strip() if v is not None else None
    except Exception: return None


def _to_float(v):
    try: return float(v)
    except Exception: return 0.0


def _az_rumbo(az_deg):
    """Rumbo cuadrante GMS derivado del azimut (delegado a formato_catastral)."""
    return fc.azimut_a_rumbo_gms(az_deg)
