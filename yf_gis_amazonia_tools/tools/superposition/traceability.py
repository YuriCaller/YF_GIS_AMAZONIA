# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Trazabilidad y verificabilidad.

Esto es lo que convierte un informe técnico en sustento defendible: quien
reciba el documento puede verificar que se analizaron EXACTAMENTE esos
archivos y no otros, recalculando el hash SHA-256 por su cuenta.

Sin esto, un informe de superposición es una afirmación; con esto, es
una afirmación verificable por un tercero.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import hashlib
import json
import os
from datetime import datetime

# Tamaño de bloque para hashear sin cargar el archivo entero en memoria
# (las capas nacionales de concesiones pueden pesar cientos de MB).
_BLOQUE = 1024 * 1024  # 1 MB

# Archivos acompañantes de un shapefile. El .shp solo no basta: los
# atributos viven en el .dbf y la proyección en el .prj — un informe que
# solo hashea el .shp no prueba qué atributos se leyeron.
EXTENSIONES_SHP = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix", ".sbn")


def sha256_archivo(ruta, bloque=_BLOQUE):
    """SHA-256 de un archivo, leído por bloques. None si no se puede leer."""
    try:
        h = hashlib.sha256()
        with open(ruta, "rb") as f:
            for trozo in iter(lambda: f.read(bloque), b""):
                h.update(trozo)
        return h.hexdigest()
    except OSError:
        return None


def _acompanantes_shapefile(ruta_shp):
    """Rutas existentes de los archivos que acompañan a un .shp."""
    base, ext = os.path.splitext(ruta_shp)
    if ext.lower() != ".shp":
        return []
    encontrados = []
    for e in EXTENSIONES_SHP:
        if e == ".shp":
            continue
        cand = base + e
        if os.path.exists(cand):
            encontrados.append(cand)
        else:
            cand_may = base + e.upper()
            if os.path.exists(cand_may):
                encontrados.append(cand_may)
    return encontrados


def ficha_archivo(ruta, crs=None, features=None, nombre_capa=None):
    """Construye la ficha de trazabilidad de un archivo de datos.

    Incluye hash del archivo principal y de sus acompañantes (caso
    shapefile), tamaño, fecha de modificación, CRS y número de entidades.
    """
    ficha = {
        "ruta": os.path.abspath(ruta),
        "nombre": os.path.basename(ruta),
        "capa": nombre_capa or os.path.splitext(os.path.basename(ruta))[0],
        "sha256": sha256_archivo(ruta),
        "tamano_bytes": None,
        "modificado_iso": None,
        "crs": crs,
        "features": features,
        "acompanantes": [],
    }
    try:
        st = os.stat(ruta)
        ficha["tamano_bytes"] = st.st_size
        ficha["modificado_iso"] = datetime.fromtimestamp(
            st.st_mtime).isoformat(timespec="seconds")
    except OSError:
        pass

    for aco in _acompanantes_shapefile(ruta):
        ficha["acompanantes"].append({
            "nombre": os.path.basename(aco),
            "sha256": sha256_archivo(aco),
        })
    return ficha


def ficha_servicio(url, uri=None, provider=None, crs=None, features=None,
                   nombre_capa=None, consultado=None):
    """Ficha de trazabilidad de una capa consultada por geoservicio.

    DIFERENCIA SUSTANTIVA CON `ficha_archivo`: aquí no hay archivo que
    hashear. Un servicio remoto puede cambiar sin aviso y sin dejar
    rastro del estado anterior, de modo que esta ficha acredita QUÉ se
    consultó y CUÁNDO, pero NO permite re-verificar unilateralmente que
    el servidor siga devolviendo lo mismo.

    Se declara explícitamente en `naturaleza` para que el informe no
    presente esta garantía como equivalente a la de un archivo con
    SHA-256, que sí es reproducible por un tercero.
    """
    return {
        "ruta": url,
        "nombre": url,
        "capa": nombre_capa or url,
        "sha256": None,
        "tamano_bytes": None,
        "modificado_iso": None,
        "crs": crs,
        "features": features,
        "acompanantes": [],
        # campos propios del origen remoto
        "es_remota": True,
        "naturaleza": "instantanea_remota",
        "uri": uri,
        "provider": provider,
        "consultado_iso": (consultado or datetime.now()).isoformat(
            timespec="seconds"),
        "advertencia": (
            "Instantánea de un geoservicio remoto. Acredita la consulta "
            "realizada en la fecha y hora indicadas; no constituye una "
            "copia verificable del dato de origen, que puede variar sin "
            "aviso. Para efectos registrales o administrativos debe "
            "recabarse la certificación oficial de la entidad."
        ),
    }


def verificar_archivo(ficha):
    """Re-verifica una ficha previa contra el archivo en disco hoy.

    Devuelve dict con: existe, hash_coincide, hash_actual.
    Sirve para responder "¿el shapefile cambió desde que emití el informe?"
    — pregunta habitual cuando un expediente se observa meses después.
    """
    ruta = ficha.get("ruta")
    res = {"ruta": ruta, "existe": False,
           "hash_coincide": False, "hash_actual": None}

    # Una ficha remota no es re-verificable por hash. Decirlo así evita
    # que el informe muestre "hash no coincide" — un falso negativo que
    # sugeriría manipulación donde solo hay un origen de otra naturaleza.
    if ficha.get("es_remota"):
        res["no_verificable"] = True
        res["motivo"] = ("Origen remoto: la ficha acredita la consulta, "
                         "no permite comprobación por hash.")
        return res

    if not ruta or not os.path.exists(ruta):
        return res
    res["existe"] = True
    res["hash_actual"] = sha256_archivo(ruta)
    res["hash_coincide"] = (res["hash_actual"] == ficha.get("sha256"))
    return res


def construir_log_proceso(contexto, parametros_extra=None):
    """Log JSON reproducible del análisis completo.

    Guarda todo lo necesario para que otra persona (o tú mismo en seis
    meses) pueda repetir el análisis y obtener el mismo resultado.
    """
    analisis = contexto.get("analisis", {})
    log = {
        "generado_por": "YF GIS Amazonia Tools — Análisis de Superposición",
        "plugin_version": analisis.get("plugin_version"),
        "fecha": analisis.get("fecha_iso"),
        "predio": analisis.get("predio"),
        "parametros": {
            "carpeta_capas": analisis.get("carpeta_capas"),
            "umbral_tolerancia_ha": analisis.get("umbral_ha"),
            "umbral_critico_pct": analisis.get("umbral_critico_pct"),
            "umbral_observable_pct": analisis.get("umbral_observable_pct"),
            "metodo_area": analisis.get("metodo_area"),
        },
        "resumen": {
            "capas_evaluadas": analisis.get("capas_evaluadas"),
            "capas_con_superposicion": analisis.get("capas_con_superposicion"),
            "area_superpuesta_total_ha": analisis.get(
                "area_superpuesta_total_ha"),
            "nivel_global": analisis.get("nivel_global"),
        },
        "superposiciones": [
            {k: s.get(k) for k in
             ("capa", "archivo", "tipo", "titular", "codigo",
              "area_ha", "porcentaje", "nivel")}
            for s in contexto.get("superposiciones", [])
        ],
        "errores": contexto.get("errores", []),
        "archivos_analizados": contexto.get(
            "trazabilidad", {}).get("archivos", []),
        "eventos": contexto.get("trazabilidad", {}).get("log", []),
    }
    if parametros_extra:
        log["parametros"].update(parametros_extra)
    return log


def guardar_log_json(contexto, ruta_salida, parametros_extra=None):
    """Escribe el log de proceso como JSON. Devuelve la ruta escrita."""
    log = construir_log_proceso(contexto, parametros_extra)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return ruta_salida


def texto_anexo_verificacion(contexto):
    """Anexo de verificación en texto plano, listo para pegar al informe.

    Formato pensado para que un tercero pueda verificar con herramientas
    estándar (certutil en Windows, sha256sum en Linux).
    """
    archivos = contexto.get("trazabilidad", {}).get("archivos", [])
    analisis = contexto.get("analisis", {})
    lineas = [
        "ANEXO DE VERIFICACIÓN TÉCNICA",
        "=" * 60,
        "Análisis realizado: {}".format(analisis.get("fecha_legible", "—")),
        "Herramienta: YF GIS Amazonia Tools v{}".format(
            analisis.get("plugin_version", "—")),
        "Método de cálculo de área: {}".format(
            analisis.get("metodo_area", "—")),
        "",
        "Los archivos analizados se identifican por su huella digital",
        "SHA-256. Para verificar en Windows:",
        "    certutil -hashfile \"<archivo>\" SHA256",
        "En Linux/macOS:",
        "    sha256sum \"<archivo>\"",
        "",
        "-" * 60,
    ]
    for a in archivos:
        lineas.append("Capa:     {}".format(a.get("capa", "—")))
        lineas.append("Archivo:  {}".format(a.get("nombre", "—")))
        lineas.append("SHA-256:  {}".format(a.get("sha256") or "no disponible"))
        lineas.append("Tamaño:   {} bytes".format(a.get("tamano_bytes", "—")))
        lineas.append("Modificado: {}".format(a.get("modificado_iso", "—")))
        lineas.append("CRS:      {}".format(a.get("crs") or "—"))
        lineas.append("Entidades: {}".format(a.get("features", "—")))
        for aco in a.get("acompanantes", []):
            lineas.append("   + {}  SHA-256: {}".format(
                aco.get("nombre"), aco.get("sha256") or "—"))
        lineas.append("-" * 60)
    return "\n".join(lineas)
