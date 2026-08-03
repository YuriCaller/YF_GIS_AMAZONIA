# -*- coding: utf-8 -*-
"""
Polygon Divider — Motor de división geométrica.

Implementa el algoritmo de bisección iterativa para dividir un polígono
con una línea de corte recta, replicando el comportamiento del comando
"Divide" de ArcGIS Pro:

    1. El usuario define una DIRECCIÓN (ángulo) para la línea de corte,
       trazándola en el canvas o mediante un spinbox de ángulo.
    2. El motor desplaza una línea infinita en esa dirección a lo largo
       del polígono, usando bisección binaria sobre la posición, hasta
       encontrar la posición exacta que separa el área objetivo.
    3. Para "N partes iguales", el proceso se repite secuencialmente
       sobre el fragmento restante (split recursivo).

100% basado en QgsGeometry nativo — sin dependencias externas (shapely),
para mantener consistencia con el resto del plugin y evitar bloqueos de
publicación en plugins.qgis.org (Bandit / dependencias no declaradas).

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import math

from qgis.core import (
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
)

from ...core.logger import log_info, log_warning, log_error


# ─────────────────────────────────────────────────────────────────────
# Excepciones propias
# ─────────────────────────────────────────────────────────────────────

class DivisionError(Exception):
    """Error controlado del motor de división (mostrado al usuario)."""
    pass


# ─────────────────────────────────────────────────────────────────────
# Utilidades geométricas
# ─────────────────────────────────────────────────────────────────────

def _validar_poligono_simple(geom: QgsGeometry):
    """
    Valida y normaliza la geometría a dividir.

    v3.0.4 — se admiten multipolígonos:
    - Multi con UNA sola parte (típico de capas cuyo tipo es MultiPolygon,
      como GeoPackage/QField): se desenvuelve a polígono simple de forma
      transparente. Era el falso positivo más frecuente de la restricción
      anterior.
    - Multi genuino (varias partes): se permite. El barrido por bisección
      es monótono también con varias partes — _area_a_un_lado clasifica y
      une los fragmentos por lado — y los resultados no contiguos ya se
      detectan y reportan aguas abajo (indices_multiparte).
    """
    if geom is None or geom.isEmpty():
        raise DivisionError("La geometría está vacía o es nula.")

    if QgsWkbTypes.geometryType(geom.wkbType()) != QgsWkbTypes.GeometryType.PolygonGeometry:
        raise DivisionError("La geometría seleccionada no es un polígono.")

    if geom.isMultipart():
        partes = [p for p in geom.asGeometryCollection()
                  if p is not None and not p.isEmpty()]
        if not partes:
            raise DivisionError("La geometría está vacía o es nula.")
        if len(partes) == 1:
            geom = partes[0]
            log_info("Polygon Divider: multipolígono de una sola parte — "
                     "convertido a polígono simple automáticamente.")
        else:
            log_warning(
                "Polygon Divider: multipolígono de {} partes admitido. "
                "Algunos fragmentos podrían resultar no contiguos; se "
                "reportarán al aplicar la división.".format(len(partes))
            )

    if not geom.isGeosValid():
        # Intento de reparación automática antes de rendirse
        reparada = geom.makeValid()
        if reparada is None or reparada.isEmpty():
            raise DivisionError(
                "El polígono tiene una geometría inválida y no pudo "
                "repararse automáticamente."
            )
        return reparada

    return geom


def _bbox_diagonal(geom: QgsGeometry) -> float:
    """Longitud de la diagonal del bounding box — usada para construir
    líneas de corte garantizadamente más largas que el polígono."""
    bbox = geom.boundingBox()
    return math.hypot(bbox.width(), bbox.height())


def _rango_offset_seguro(geom: QgsGeometry, centro: QgsPointXY, angulo_rad: float):
    """
    Calcula el rango [lo, hi] de offsets perpendiculares (relativos al
    centro) dentro del cual la línea de corte garantizadamente toca el
    polígono y lo divide en exactamente 2 partes.

    Es CRÍTICO usar el ancho del polígono proyectado sobre la dirección
    perpendicular al corte — NO la diagonal del bounding box — porque en
    polígonos alargados o rotados, un offset basado en la diagonal puede
    quedar completamente fuera del polígono, haciendo que el corte no lo
    toque (split devolvería 1 sola parte en vez de 2) y rompiendo la
    bisección justo en sus extremos.
    """
    perp = angulo_rad + (math.pi / 2.0)
    dir_perp = (math.cos(perp), math.sin(perp))

    proy_centro = centro.x() * dir_perp[0] + centro.y() * dir_perp[1]

    vertices = list(geom.vertices())
    proyecciones = [v.x() * dir_perp[0] + v.y() * dir_perp[1] for v in vertices]
    min_proy, max_proy = min(proyecciones), max(proyecciones)

    lo = min_proy - proy_centro
    hi = max_proy - proy_centro

    # Margen pequeño hacia adentro para evitar tangencias exactas en los
    # extremos (offset que toca el polígono justo en un vértice puede
    # producir splits degenerados con 1 o >2 partes).
    margen = (hi - lo) * 0.001
    return lo + margen, hi - margen


def _linea_infinita(centro: QgsPointXY, angulo_rad: float, longitud: float) -> QgsGeometry:
    """
    Construye una QgsGeometry de tipo línea, centrada en `centro`,
    orientada según `angulo_rad` (medido desde el eje X, sentido
    matemático estándar), con la longitud dada en cada dirección.
    """
    dx = math.cos(angulo_rad) * longitud
    dy = math.sin(angulo_rad) * longitud
    p1 = QgsPointXY(centro.x() - dx, centro.y() - dy)
    p2 = QgsPointXY(centro.x() + dx, centro.y() + dy)
    return QgsGeometry.fromPolylineXY([p1, p2])


def _offset_perpendicular(centro: QgsPointXY, angulo_rad: float, offset: float) -> QgsPointXY:
    """
    Desplaza un punto perpendicularmente a la dirección de corte.
    El offset barre el polígono de un extremo al otro durante la bisección.
    """
    # Perpendicular a angulo_rad es angulo_rad + 90°
    perp = angulo_rad + (math.pi / 2.0)
    return QgsPointXY(
        centro.x() + math.cos(perp) * offset,
        centro.y() + math.sin(perp) * offset,
    )


def _partir_por_linea(geom: QgsGeometry, linea: QgsGeometry):
    """
    Parte `geom` con `linea` y devuelve la lista de fragmentos resultantes
    como geometrías independientes (QgsGeometry.splitGeometry).

    Retorna (lista_fragmentos, mensaje_error_o_None).
    """
    geom_copia = QgsGeometry(geom)  # splitGeometry muta el objeto
    puntos_linea = [v for v in linea.vertices()]
    puntos_linea_xy = [QgsPointXY(p) for p in puntos_linea]

    resultado = geom_copia.splitGeometry(puntos_linea_xy, False)
    # PyQGIS splitGeometry retorna: (errorCode, newGeometries[, topologyTestPoints])
    error_code = resultado[0]
    nuevas_geoms = resultado[1]

    if error_code != 0:
        return None, f"splitGeometry devolvió código de error {error_code}"

    fragmentos = [geom_copia] + list(nuevas_geoms)
    fragmentos = [f for f in fragmentos if f is not None and not f.isEmpty()]

    if len(fragmentos) < 2:
        return None, "La línea no produjo una división válida (no cruza el polígono en dos partes)."

    return fragmentos, None


def _clasificar_y_unir_fragmentos(fragmentos, punto_offset, angulo_rad):
    """
    Clasifica cada fragmento resultante de un corte según el lado
    (negativo/positivo) de la perpendicular a la línea de corte, y une
    (por unaryUnion) todos los fragmentos del mismo lado en una sola
    geometría.

    Esto es necesario porque en polígonos NO CONVEXOS una sola línea
    recta puede atravesar el polígono y producir 3, 4 o más fragmentos
    (en vez de exactamente 2). El comportamiento correcto — el mismo que
    usa ArcGIS Pro — es agrupar todas las piezas que quedan "antes" de
    la línea en un lado, y todas las que quedan "después" en el otro,
    no rendirse ni tratar cada pieza como un corte independiente.

    Retorna (geom_lado_negativo, geom_lado_positivo), donde alguno puede
    ser una geometría vacía si todos los fragmentos cayeron al otro lado.
    """
    perp = angulo_rad + (math.pi / 2.0)
    dir_perp = (math.cos(perp), math.sin(perp))

    lado_negativo = []
    lado_positivo = []

    for frag in fragmentos:
        c = frag.centroid().asPoint()
        vec = (c.x() - punto_offset.x(), c.y() - punto_offset.y())
        signo = vec[0] * dir_perp[0] + vec[1] * dir_perp[1]
        if signo < 0:
            lado_negativo.append(frag)
        else:
            lado_positivo.append(frag)

    def _unir(lista):
        if not lista:
            return QgsGeometry()
        if len(lista) == 1:
            return lista[0]
        return QgsGeometry.unaryUnion(lista)

    return _unir(lado_negativo), _unir(lado_positivo)


def _area_a_un_lado(geom: QgsGeometry, centro: QgsPointXY, angulo_rad: float, offset: float):
    """
    Dado un offset perpendicular, corta el polígono y devuelve el área
    del fragmento (o unión de fragmentos) que queda en el lado
    "negativo" de la línea — lado de referencia consistente usado por
    la bisección.

    Soporta polígonos NO CONVEXOS: si el corte produce más de 2 piezas,
    las agrupa por lado en vez de fallar (ver _clasificar_y_unir_fragmentos).

    Retorna (area_lado_a, (geom_lado_a, geom_lado_b)) o (None, None) si
    el corte falla por completo (ej. la línea no toca el polígono).
    """
    diag = _bbox_diagonal(geom) * 1.5 + 1.0
    punto_offset = _offset_perpendicular(centro, angulo_rad, offset)
    linea = _linea_infinita(punto_offset, angulo_rad, diag)

    fragmentos, err = _partir_por_linea(geom, linea)
    if fragmentos is None:
        if geom.isMultipart():
            # v3.0.4: en un multipolígono, el offset puede caer en el vacío
            # ENTRE partes: la línea no corta ninguna, pero el área por lado
            # sigue bien definida — se clasifican las partes enteras.
            fragmentos = [p for p in geom.asGeometryCollection()
                          if p is not None and not p.isEmpty()]
            if len(fragmentos) < 2:
                return None, None
        else:
            return None, None

    geom_lado_a, geom_lado_b = _clasificar_y_unir_fragmentos(
        fragmentos, punto_offset, angulo_rad
    )

    if geom_lado_a.isEmpty() and geom_lado_b.isEmpty():
        return None, None

    return geom_lado_a.area(), (geom_lado_a, geom_lado_b)


# ─────────────────────────────────────────────────────────────────────
# API pública — bisección por un único corte (un área objetivo)
# ─────────────────────────────────────────────────────────────────────

def calcular_corte_por_area(geom: QgsGeometry, angulo_rad: float, area_objetivo: float,
                             tolerancia_relativa: float = 0.00001, max_iter: int = 80):
    """
    Encuentra la línea de corte (en la dirección `angulo_rad`) que separa
    del polígono un fragmento de área exactamente `area_objetivo`
    (lado "negativo" de la perpendicular), mediante bisección binaria.

    Precisión por defecto: tolerancia_relativa = 0.00001 (0.001% del área
    total). Para un predio típico de 44 ha esto equivale a ±0.44 m² de
    error máximo por corte — aceptable para trabajo catastral, donde el
    error posicional del GPS de campo suele superar esa cifra. El cálculo
    de área es PLANAR (cartesiano en el CRS del proyecto), NO elipsoidal.

    Retorna: (fragmento_a, fragmento_b, area_a, area_b, es_multiparte)
    Lanza DivisionError si no converge o el polígono no es apto.
    """
    geom = _validar_poligono_simple(geom)
    area_total = geom.area()

    if area_objetivo <= 0 or area_objetivo >= area_total:
        raise DivisionError(
            f"El área objetivo ({area_objetivo:.4f}) debe ser mayor que 0 "
            f"y menor que el área total del polígono ({area_total:.4f})."
        )

    centroide = geom.centroid().asPoint()
    lo, hi = _rango_offset_seguro(geom, centroide, angulo_rad)

    area_lo, _ = _area_a_un_lado(geom, centroide, angulo_rad, lo)
    area_hi, _ = _area_a_un_lado(geom, centroide, angulo_rad, hi)

    if area_lo is None or area_hi is None:
        raise DivisionError(
            "No fue posible evaluar el corte en los extremos de búsqueda. "
            "Verifica que la línea trazada realmente atraviese el polígono."
        )

    # Asegurar que el objetivo está dentro del rango monótono [area_lo, area_hi]
    if area_lo > area_hi:
        lo, hi = hi, lo
        area_lo, area_hi = area_hi, area_lo

    if not (area_lo - 1e-6 <= area_objetivo <= area_hi + 1e-6):
        raise DivisionError(
            "El área objetivo no es alcanzable con esta dirección de corte. "
            "Esto puede ocurrir en polígonos no convexos. Intenta ajustar "
            "el ángulo de la línea de corte."
        )

    tolerancia_abs = area_total * tolerancia_relativa
    mid_fragmentos = None
    area_mid = None

    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        area_mid, mid_fragmentos = _area_a_un_lado(geom, centroide, angulo_rad, mid)

        if area_mid is None:
            # La línea no tocó el polígono en este punto exacto (caso
            # extremadamente raro, ej. offset cae justo en un vértice).
            # Se desplaza levemente y se reintenta una sola vez.
            mid += (hi - lo) * 1e-4
            area_mid, mid_fragmentos = _area_a_un_lado(geom, centroide, angulo_rad, mid)
            if area_mid is None:
                raise DivisionError(
                    "La línea de corte no logró atravesar el polígono en "
                    "este punto. Intenta con otro ángulo."
                )

        if abs(area_mid - area_objetivo) <= tolerancia_abs:
            break

        # Monotonía: si area crece con offset, ajustamos lo/hi según signo
        if area_hi >= area_lo:
            if area_mid < area_objetivo:
                lo = mid
            else:
                hi = mid
        else:
            if area_mid < area_objetivo:
                hi = mid
            else:
                lo = mid
    else:
        log_warning(
            f"Polygon Divider: bisección alcanzó max_iter sin converger "
            f"dentro de tolerancia ({abs(area_mid - area_objetivo):.4f} "
            f"vs tolerancia {tolerancia_abs:.4f})."
        )

    if mid_fragmentos is None:
        raise DivisionError("No se pudo completar el corte.")

    frag_a, frag_b = mid_fragmentos

    if frag_a.isEmpty() or frag_b.isEmpty():
        raise DivisionError(
            "El corte resultó en un fragmento vacío. Esto puede ocurrir "
            "en polígonos con concavidades muy pronunciadas. Intenta "
            "ajustar el ángulo de la línea de corte."
        )

    area_a, area_b = frag_a.area(), frag_b.area()

    # Garantizar que frag_a sea el del área objetivo (consistencia para el caller)
    if abs(area_a - area_objetivo) > abs(area_b - area_objetivo):
        frag_a, frag_b = frag_b, frag_a
        area_a, area_b = area_b, area_a

    es_multiparte = frag_a.isMultipart() or frag_b.isMultipart()
    if es_multiparte:
        n_partes_a = len(frag_a.asGeometryCollection()) if frag_a.isMultipart() else 1
        n_partes_b = len(frag_b.asGeometryCollection()) if frag_b.isMultipart() else 1
        log_warning(
            f"Polygon Divider: el corte en ángulo {math.degrees(angulo_rad):.1f}° "
            f"produjo un fragmento NO contiguo (polígono de entrada no convexo). "
            f"Fragmento A: {n_partes_a} parte(s), Fragmento B: {n_partes_b} parte(s)."
        )

    log_info(
        f"Polygon Divider: corte por área OK — objetivo={area_objetivo:.4f}, "
        f"obtenido={area_a:.4f}, diferencia={abs(area_a - area_objetivo):.6f}, "
        f"multiparte={es_multiparte}"
    )

    return frag_a, frag_b, area_a, area_b, es_multiparte


def construir_linea_de_corte(geom: QgsGeometry, angulo_rad: float, area_objetivo: float):
    """
    Variante de uso para la vista previa: solo calcula y devuelve la
    QgsGeometry de la línea de corte final (recortada a la extensión del
    polígono), sin generar los fragmentos. Útil para dibujar el rubber
    band rojo antes de aplicar la división.
    """
    geom = _validar_poligono_simple(geom)
    centroide = geom.centroid().asPoint()
    area_total = geom.area()

    lo, hi = _rango_offset_seguro(geom, centroide, angulo_rad)
    area_lo, _ = _area_a_un_lado(geom, centroide, angulo_rad, lo)
    area_hi, _ = _area_a_un_lado(geom, centroide, angulo_rad, hi)

    if area_lo is None or area_hi is None:
        raise DivisionError("No se pudo trazar la línea de corte para esta dirección.")

    if area_lo > area_hi:
        lo, hi = hi, lo
        area_lo, area_hi = area_hi, area_lo

    tolerancia_abs = area_total * 0.0005
    mid = (lo + hi) / 2.0

    for _ in range(60):
        mid = (lo + hi) / 2.0
        area_mid, _ = _area_a_un_lado(geom, centroide, angulo_rad, mid)
        if area_mid is None:
            break
        if abs(area_mid - area_objetivo) <= tolerancia_abs:
            break
        if area_hi >= area_lo:
            if area_mid < area_objetivo:
                lo = mid
            else:
                hi = mid
        else:
            if area_mid < area_objetivo:
                hi = mid
            else:
                lo = mid

    diag = _bbox_diagonal(geom) * 0.6 + 1.0
    punto_offset = _offset_perpendicular(centroide, angulo_rad, mid)
    linea_infinita = _linea_infinita(punto_offset, angulo_rad, diag)

    # Recortar la línea a la extensión del polígono (más estética para el preview)
    interseccion = linea_infinita.intersection(geom.buffer(0.0, 5))
    if interseccion is not None and not interseccion.isEmpty():
        return interseccion
    return linea_infinita


# ─────────────────────────────────────────────────────────────────────
# API pública — N partes iguales (split recursivo)
# ─────────────────────────────────────────────────────────────────────

def dividir_n_partes_iguales(geom: QgsGeometry, angulo_rad: float, n_partes: int):
    """
    Divide el polígono en `n_partes` fragmentos de área igual, todos
    cortados con líneas paralelas en la misma dirección `angulo_rad`.

    Estrategia: corta secuencialmente el primer 1/n del área restante,
    avanzando sobre el fragmento que queda, hasta tener n fragmentos.

    Retorna: (lista_de_QgsGeometry, lista_indices_multiparte) donde
    lista_indices_multiparte contiene los números de fracción (1-based)
    cuyo resultado quedó como multipolígono — esto ocurre cuando el
    polígono de entrada no es convexo y una línea de corte atraviesa
    una concavidad, produciendo "islas" separadas que suman el área
    correcta pero no son una sola pieza contigua. El caller (diálogo)
    debe advertir al usuario antes de aplicar si esta lista no está vacía.
    """
    geom = _validar_poligono_simple(geom)

    if n_partes < 2:
        raise DivisionError("El número de partes debe ser 2 o más.")
    if n_partes > 50:
        raise DivisionError("Por seguridad, el máximo admitido es 50 partes.")

    fragmentos = []
    indices_multiparte = []
    restante = geom
    partes_pendientes = n_partes

    for i in range(n_partes - 1):
        area_restante = restante.area()
        area_objetivo = area_restante / partes_pendientes

        frag_a, frag_b, _, _, es_multiparte = calcular_corte_por_area(
            restante, angulo_rad, area_objetivo
        )
        if es_multiparte and frag_a.isMultipart():
            indices_multiparte.append(len(fragmentos) + 1)
        fragmentos.append(frag_a)
        restante = frag_b
        partes_pendientes -= 1

    fragmentos.append(restante)
    if restante.isMultipart():
        indices_multiparte.append(len(fragmentos))

    log_info(
        f"Polygon Divider: {n_partes} partes iguales generadas "
        f"({len(indices_multiparte)} con geometría no contigua)."
    )
    return fragmentos, indices_multiparte


def dividir_por_porcentajes(geom: QgsGeometry, angulo_rad: float, porcentajes: list):
    """
    Divide el polígono según una lista de porcentajes (ej. [30, 70] o
    [25, 25, 50]). Los porcentajes deben sumar 100 (± 0.01 de tolerancia).

    Retorna: (lista_de_QgsGeometry, lista_indices_multiparte) — ver nota
    en dividir_n_partes_iguales sobre el significado de
    lista_indices_multiparte.
    """
    geom = _validar_poligono_simple(geom)

    suma = sum(porcentajes)
    if abs(suma - 100.0) > 0.01:
        raise DivisionError(
            f"Los porcentajes deben sumar 100%. Suma actual: {suma:.2f}%."
        )
    if any(p <= 0 for p in porcentajes):
        raise DivisionError("Todos los porcentajes deben ser mayores que 0.")
    if len(porcentajes) < 2:
        raise DivisionError("Se necesitan al menos 2 porcentajes.")

    fragmentos = []
    indices_multiparte = []
    restante = geom
    pendiente = list(porcentajes)

    for i in range(len(porcentajes) - 1):
        pct_actual = pendiente[0]
        pct_restante_total = sum(pendiente)
        area_objetivo = restante.area() * (pct_actual / pct_restante_total)

        frag_a, frag_b, _, _, es_multiparte = calcular_corte_por_area(
            restante, angulo_rad, area_objetivo
        )
        if es_multiparte and frag_a.isMultipart():
            indices_multiparte.append(len(fragmentos) + 1)
        fragmentos.append(frag_a)
        restante = frag_b
        pendiente = pendiente[1:]

    fragmentos.append(restante)
    if restante.isMultipart():
        indices_multiparte.append(len(fragmentos))

    log_info(
        f"Polygon Divider: división por porcentajes {porcentajes} completada "
        f"({len(indices_multiparte)} con geometría no contigua)."
    )
    return fragmentos, indices_multiparte
