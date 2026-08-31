# -*- coding: utf-8 -*-
"""
Recalcular atributos: capa de segmentos (lineas) -> capa de vertices (puntos)

Flujo de trabajo que soporta
----------------------------
1. Se eliminan los vertices de quebrada de la capa de puntos, dejando solo
   los vertices de presentacion del plano (V1..Vn).
2. En la capa de lineas se recalcula la longitud REAL de cada lado, que en
   los tramos sinuosos sigue el cauce y por tanto es mayor que la cuerda.
3. En esos tramos el azimut se anula: una quebrada sinuosa no tiene azimut.
4. Esta funcion copia longitud y azimut de las lineas a los puntos y
   renumera los IDs de ambas capas en secuencia 1..n.

No se modifica ninguna geometria.

Por que no se empareja por ID
-----------------------------
QGIS no renumera el fid tras una edicion (a diferencia del OBJECTID de
ArcGIS). Los IDs heredados quedan rotos y, peor aun, rotos de forma
distinta en cada capa: el vertice 5 puede quedar con 5 y su lado con 38.
El emparejamiento se hace por posicion: cada segmento arranca en su
vertice, asi que se asocia el punto Vi con el segmento cuyo vertice
inicial coincide. Si eso falla, se cae a un emparejamiento ordinal.

Por que no se ordena por latitud
--------------------------------
Un poligono no se recorre de norte a sur. El orden sale de encadenar los
segmentos por topologia: el final de uno es el inicio del siguiente.
"""

import math
from qgis.core import QgsPointXY, edit


TOL_EMPAREJE = 0.05   # m: punto <-> vertice inicial del segmento
TOL_RECTO    = 0.02   # m: longitud vs cuerda para considerar el lado recto


def _idx(lyr, *nombres):
    """Primer indice de campo existente, tolerando el truncamiento a 10
    caracteres del DBF (ID_Poligono -> ID_Poligon)."""
    campos = lyr.fields()
    for nom in nombres:
        i = campos.indexOf(nom)
        if i >= 0:
            return i
        i = campos.indexOf(nom[:10])
        if i >= 0:
            return i
    return -1


def _puntos_de(geom):
    """Lista de QgsPointXY de una geometria de punto, linea o poligono.

    Deliberadamente NO se usa geom.vertices(): ese iterador conserva un
    puntero a la geometria subyacente, y cuando la geometria es el
    temporal que devuelve feature.geometry(), el recolector de basura la
    libera mientras el iterador sigue vivo. QGIS 3.44 cae con access
    violation. Los metodos asPoint/asPolyline/asMultiPolyline copian los
    datos a estructuras de Python y no tienen ese problema.
    """
    if geom is None or geom.isEmpty():
        return []
    try:
        tipo = geom.type()
        if tipo == 0:
            if geom.isMultipart():
                return [QgsPointXY(p) for p in geom.asMultiPoint()]
            return [QgsPointXY(geom.asPoint())]
        if tipo == 1:
            if geom.isMultipart():
                pts = []
                for parte in geom.asMultiPolyline():
                    pts.extend(parte)
                return [QgsPointXY(p) for p in pts]
            return [QgsPointXY(p) for p in geom.asPolyline()]
        if geom.isMultipart():
            mp = geom.asMultiPolygon()
            return [QgsPointXY(p) for p in mp[0][0]] if mp else []
        pl = geom.asPolygon()
        return [QgsPointXY(p) for p in pl[0]] if pl else []
    except Exception:
        return []


def _primer_punto(geom):
    pts = _puntos_de(geom)
    return pts[0] if pts else None


def _ultimo_punto(geom):
    pts = _puntos_de(geom)
    return pts[-1] if pts else None


def _es_nulo(v):
    return v is None or (hasattr(v, "isNull") and v.isNull()) or v == ""


def ordenar_segmentos(lyr_seg):
    """Encadena los segmentos por topologia. Devuelve (lista, aviso|None)."""
    feats = list(lyr_seg.getFeatures())
    if len(feats) < 3:
        return feats, "La capa de segmentos tiene solo %d entidad(es)." % len(feats)

    # Una sola llamada a geometry() por feature, guardada en variable local:
    # el temporal debe seguir vivo mientras se leen sus puntos.
    inicio, fin = {}, {}
    for f in feats:
        g = f.geometry()
        pts = _puntos_de(g)
        inicio[f.id()] = pts[0] if pts else None
        fin[f.id()] = pts[-1] if pts else None
    if any(v is None for v in inicio.values()):
        return feats, "Hay segmentos sin geometria; se usa el orden de la capa."

    por_id = {f.id(): f for f in feats}
    actual = feats[0]
    cadena = [actual]
    restantes = set(por_id) - {actual.id()}

    while restantes:
        p = fin[actual.id()]
        siguiente = None
        for fid in restantes:
            q = inicio[fid]
            if math.hypot(p.x() - q.x(), p.y() - q.y()) <= TOL_EMPAREJE:
                siguiente = fid
                break
        if siguiente is None:
            return feats, ("La cadena de segmentos se rompe tras %d lado(s); "
                           "se usa el orden de la capa." % len(cadena))
        actual = por_id[siguiente]
        cadena.append(actual)
        restantes.discard(siguiente)

    return cadena, None


def emparejar(lyr_ver, segmentos):
    """Asocia cada segmento con el punto de su vertice inicial."""
    puntos = list(lyr_ver.getFeatures())
    avisos = []

    if len(puntos) != len(segmentos):
        avisos.append(
            "La capa de puntos tiene %d entidades y la de lineas %d. "
            "Deben coincidir." % (len(puntos), len(segmentos)))

    pares, sin_par, usados = [], [], set()
    for seg in segmentos:
        p_ini = _primer_punto(seg.geometry())
        if p_ini is None:
            sin_par.append(seg)
            continue
        mejor, mejor_d = None, float("inf")
        for pt in puntos:
            if pt.id() in usados:
                continue
            g = _primer_punto(pt.geometry())
            if g is None:
                continue
            d = math.hypot(p_ini.x() - g.x(), p_ini.y() - g.y())
            if d < mejor_d:
                mejor, mejor_d = pt, d
        if mejor is not None and mejor_d <= TOL_EMPAREJE:
            pares.append((mejor, seg))
            usados.add(mejor.id())
        else:
            sin_par.append(seg)

    if sin_par and len(puntos) == len(segmentos):
        avisos.append(
            "%d segmento(s) no coinciden geometricamente con ningun punto; "
            "se emparejaron por orden. Revisa el resultado." % len(sin_par))
        pares = list(zip(puntos, segmentos))
    elif sin_par:
        avisos.append(
            "%d segmento(s) sin punto correspondiente y los conteos no "
            "calzan. Corrige las capas antes de recalcular." % len(sin_par))

    return pares, avisos


def anclar_en_v1(pares, lyr_ver):
    """Rota la cadena para que empiece en el vertice que YA estaba numerado 1.

    ordenar_segmentos() encadena por topologia, pero arranca en el primer
    feature que devuelve la capa y ese orden lo decide el proveedor: sin
    anclaje la numeracion V1..Vn rota entre ejecuciones y se pierde la que
    el usuario fijo a mano. Devuelve (pares, aviso o None).
    """
    i_v = _idx(lyr_ver, "ID_Vertice", "ID_Vertice_CW", "ID_Verti_1")
    if i_v < 0:
        return pares, ("La capa de puntos no tiene campo de numero de vertice; "
                       "V1 queda en el inicio de la cadena.")
    for k, par in enumerate(pares):
        try:
            v = par[0].attribute(i_v)
            if v is None or (hasattr(v, "isNull") and v.isNull()):
                continue
            if int(v) == 1:
                return ((pares[k:] + pares[:k]) if k else pares), None
        except (TypeError, ValueError):
            continue
    return pares, ("Ningun punto estaba numerado como 1; V1 queda en el inicio "
                   "de la cadena. Revisa la numeracion resultante.")


def recalcular_atributos(lyr_vertices, lyr_segmentos, id_poligono=1,
                         sobrescribir_azimut_nulo=True, anclar_v1=True):
    """Copia longitud/azimut de los segmentos a los vertices y renumera los
    IDs de ambas capas. No toca ninguna geometria."""

    segmentos, aviso_orden = ordenar_segmentos(lyr_segmentos)
    pares, avisos = emparejar(lyr_vertices, segmentos)
    if aviso_orden:
        avisos.insert(0, aviso_orden)
    if pares and anclar_v1:
        pares, aviso_ancla = anclar_en_v1(pares, lyr_vertices)
        if aviso_ancla:
            avisos.append(aviso_ancla)
    if not pares:
        return {"ok": False, "n": 0, "avisos": avisos, "perimetro": 0.0,
                "sinuosos": 0,
                "mensaje": "No se pudo emparejar ninguna entidad.\n- "
                           + "\n- ".join(avisos)}

    n = len(pares)

    v_vert  = _idx(lyr_vertices, "ID_Vertice", "ID_Vertice_CW", "ID_Verti_1")
    v_pol   = _idx(lyr_vertices, "ID_Poligono", "ID_Poligon")
    v_glb   = _idx(lyr_vertices, "ID_Global")
    v_lado  = _idx(lyr_vertices, "LADO")
    v_lbl   = _idx(lyr_vertices, "LABEL_V")
    v_este  = _idx(lyr_vertices, "Este")
    v_norte = _idx(lyr_vertices, "Norte")
    v_dist  = _idx(lyr_vertices, "Distancia")
    v_azim  = _idx(lyr_vertices, "Azimut")

    s_seg   = _idx(lyr_segmentos, "ID_Segmento", "ID_Segment")
    s_pol   = _idx(lyr_segmentos, "ID_Poligono", "ID_Poligon")
    s_glb   = _idx(lyr_segmentos, "ID_Global")
    s_lado  = _idx(lyr_segmentos, "LADO")
    s_num   = _idx(lyr_segmentos, "LADO_NUM")
    s_recto = _idx(lyr_segmentos, "ES_RECTO")
    s_long  = _idx(lyr_segmentos, "longitud", "Distancia")
    s_azim  = _idx(lyr_segmentos, "azimut", "Azimut")

    if s_long < 0:
        msg = "La capa de lineas no tiene campo de longitud."
        return {"ok": False, "n": 0, "avisos": [msg], "mensaje": msg,
                "perimetro": 0.0, "sinuosos": 0}

    cambios_v, cambios_s = {}, {}
    total_long, sinuosos, azimut_sospechoso = 0.0, 0, []

    for i, (pt, seg) in enumerate(pares):
        num = i + 1
        sig = (i + 1) % n + 1
        lado = "V%d a V%d" % (num, sig)

        longitud = seg.attribute(s_long)
        azimut   = seg.attribute(s_azim) if s_azim >= 0 else None

        p_ini = _primer_punto(seg.geometry())
        p_fin = _ultimo_punto(seg.geometry())
        cuerda = math.hypot(p_fin.x() - p_ini.x(), p_fin.y() - p_ini.y())

        try:
            longitud_f = float(longitud)
            total_long += longitud_f
            es_recto = abs(longitud_f - cuerda) <= TOL_RECTO
        except (TypeError, ValueError):
            es_recto = False
            avisos.append("Lado %s: la longitud no es numerica." % lado)

        if not es_recto:
            sinuosos += 1
            if not _es_nulo(azimut):
                azimut_sospechoso.append(lado)

        a = {}
        if v_vert >= 0: a[v_vert] = num
        if v_pol  >= 0: a[v_pol]  = id_poligono
        if v_glb  >= 0: a[v_glb]  = id_poligono
        if v_lado >= 0: a[v_lado] = lado
        if v_lbl  >= 0: a[v_lbl]  = "V%d" % num
        if v_dist >= 0: a[v_dist] = longitud
        if v_azim >= 0 and (sobrescribir_azimut_nulo or not _es_nulo(azimut)):
            a[v_azim] = azimut
        g = _primer_punto(pt.geometry())
        if g is not None:
            if v_este  >= 0: a[v_este]  = round(g.x(), 3)
            if v_norte >= 0: a[v_norte] = round(g.y(), 3)
        cambios_v[pt.id()] = a

        b = {}
        if s_seg   >= 0: b[s_seg]   = num
        if s_pol   >= 0: b[s_pol]   = id_poligono
        if s_glb   >= 0: b[s_glb]   = id_poligono
        if s_lado  >= 0: b[s_lado]  = lado
        if s_num   >= 0: b[s_num]   = num
        if s_recto >= 0: b[s_recto] = es_recto
        cambios_s[seg.id()] = b

    ok = True
    for lyr, cambios in ((lyr_vertices, cambios_v), (lyr_segmentos, cambios_s)):
        if not cambios:
            continue
        if not lyr.dataProvider().changeAttributeValues(cambios):
            with edit(lyr):
                for fid, attrs in cambios.items():
                    for i_campo, val in attrs.items():
                        if not lyr.changeAttributeValue(fid, i_campo, val):
                            ok = False
        lyr.triggerRepaint()

    if azimut_sospechoso:
        avisos.append(
            "Estos lados no son rectos pero conservan azimut: %s. "
            "Anulalos si corresponden a quebrada."
            % ", ".join(azimut_sospechoso))
    if not ok:
        avisos.append("Algunos atributos no pudieron escribirse.")

    mensaje = ("Recalculados %d vertices y %d lados. Perimetro (suma de "
               "longitudes) %.3f m. Lados sinuosos: %d."
               % (n, n, total_long, sinuosos))
    if avisos:
        mensaje += "\n\nADVERTENCIAS:\n- " + "\n- ".join(avisos)

    return {"ok": ok and not avisos, "n": n, "perimetro": total_long,
            "sinuosos": sinuosos, "avisos": avisos, "mensaje": mensaje}
