# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Motor de informes.

Genera el informe en HTML (vista previa inmediata, cero dependencias) y
lo exporta como .doc que Word abre nativamente como documento editable —
sin python-docx ni docxtpl. El HTML lleva estilos office-compatibles.

Filosofía (definida con el usuario):
  · El motor PROPONE conclusiones graduadas según el nivel del hallazgo.
  · La conclusión jurídica final es EDITABLE por el usuario antes de
    exportar: firma el profesional, no el software.
  · Perfiles por institución: cada uno define encabezado, umbrales y
    redacción. Se empieza con GOREMAD y genérico; el resto se clona.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import html as _html


# ───────────────────────────────────────────────────────────────────────────
# Perfiles institucionales
# ───────────────────────────────────────────────────────────────────────────

PERFILES = {
    "generico": {
        "nombre": "Genérico (técnico)",
        "encabezado": "INFORME TÉCNICO DE ANÁLISIS DE SUPERPOSICIÓN",
        "subtitulo": "Evaluación de derechos preexistentes",
        "institucion": "",
        "color": "1F4E5F",
    },
    "goremad": {
        "nombre": "GOREMAD — Gerencia Forestal",
        "encabezado": "INFORME TÉCNICO DE ANÁLISIS DE SUPERPOSICIÓN DE DERECHOS",
        "subtitulo": ("Gobierno Regional de Madre de Dios — "
                      "Gerencia Regional Forestal y de Fauna Silvestre"),
        "institucion": "GOREMAD / GRFFS",
        "color": "2E5E3A",
    },
    "serfor": {
        "nombre": "SERFOR / ARFFS",
        "encabezado": "INFORME TÉCNICO DE SUPERPOSICIÓN DE DERECHOS FORESTALES",
        "subtitulo": ("Servicio Nacional Forestal y de Fauna Silvestre — "
                      "Autoridad Regional Forestal y de Fauna Silvestre"),
        "institucion": "SERFOR / ARFFS",
        "color": "1F4E5F",
    },
}


def perfiles_disponibles():
    """[(clave, nombre_legible)] para poblar el combo del diálogo."""
    return [(k, v["nombre"]) for k, v in PERFILES.items()]


# ───────────────────────────────────────────────────────────────────────────
# Conclusiones graduadas (propuestas — el usuario las edita)
# ───────────────────────────────────────────────────────────────────────────

def conclusion_sugerida(contexto):
    """Redacta una conclusión BORRADOR según el nivel global del análisis.

    Deliberadamente NO emite juicio de improcedencia: gradúa hallazgos y
    recomienda. La decisión jurídica la pone el profesional que firma.
    """
    a = contexto["analisis"]
    predio = a["predio"]["nombre"]

    # Capas que no pudieron consultarse. La advertencia va DENTRO de la
    # conclusión, no solo en una sección aparte: este párrafo es el que se
    # transcribe al expediente, y sin la salvedad afirmaría una cobertura
    # que el análisis no tuvo.
    errores = contexto.get("errores") or []
    n_fallidas = len(errores)
    if n_fallidas:
        reserva = (
            " Se deja expresa constancia de que {n} capa(s) no pudieron ser "
            "evaluadas por causas ajenas al análisis (indisponibilidad del "
            "servicio, error de acceso o fuente ilegible), conforme al "
            "detalle consignado en la sección «Capas no evaluadas». En "
            "consecuencia, la presente verificación NO agota el universo de "
            "derechos preexistentes y debe complementarse con el "
            "pronunciamiento oficial de las entidades competentes."
        ).format(n=n_fallidas)
    else:
        reserva = ""

    # Cobertura nula: no hay nada sobre lo cual concluir.
    if not a["capas_evaluadas"]:
        return (
            "No fue posible efectuar el análisis de superposición sobre el "
            "área denominada «{predio}» ({area:.4f} ha): ninguna de las "
            "{n} capa(s) previstas pudo ser consultada. El presente "
            "documento NO acredita ausencia ni existencia de superposición, "
            "y no debe ser empleado como sustento técnico hasta repetir la "
            "verificación con las fuentes disponibles."
        ).format(predio=predio, area=a["predio"]["area_ha"],
                 n=n_fallidas or "las")

    if not a["hay_superposicion"]:
        return (
            "Del análisis técnico efectuado sobre el área denominada "
            "«{predio}» ({area:.4f} ha), contrastada contra {n} de {t} "
            "capa(s) de derechos preexistentes previstas, se concluye que "
            "NO se ha identificado superposición por encima del umbral de "
            "tolerancia establecido ({umbral} ha). "
            "En consecuencia, desde el punto de vista técnico-cartográfico, "
            "el área evaluada se encuentra libre de superposiciones respecto "
            "de las fuentes efectivamente verificadas.{reserva}"
        ).format(predio=predio, area=a["predio"]["area_ha"],
                 n=a["capas_evaluadas"],
                 t=a.get("capas_totales", a["capas_evaluadas"]),
                 umbral=a["umbral_ha"], reserva=reserva)

    nivel = a["nivel_global"]
    area_afectada = a.get("area_afectada_unica_ha",
                          a["area_superpuesta_total_ha"])
    pct = a.get("porcentaje_afectado_unico",
                a["porcentaje_superpuesto_total"])
    n_sup = a["capas_con_superposicion"]

    base = (
        "Del análisis técnico efectuado sobre el área denominada "
        "«{predio}» ({area:.4f} ha) se ha identificado superposición con "
        "{n} derecho(s) preexistente(s), afectando una superficie de "
        "{afect:.4f} ha ({pct:.2f}% del área evaluada), conforme al detalle "
        "y al anexo de verificación técnica adjuntos. "
    ).format(predio=predio, area=a["predio"]["area_ha"], n=n_sup,
             afect=area_afectada, pct=pct)

    if nivel == "critico":
        cierre = (
            "Dada la magnitud de la superposición identificada, se recomienda "
            "que, previamente a cualquier acto administrativo sobre el área, "
            "se resuelva la concurrencia de derechos detectada y se requiera "
            "el pronunciamiento de las instancias competentes."
        )
    elif nivel == "observable":
        cierre = (
            "Se recomienda subsanar la superposición identificada mediante la "
            "rectificación correspondiente y/o el deslinde con los titulares "
            "de los derechos concurrentes, previo a la continuación del "
            "procedimiento."
        )
    else:
        cierre = (
            "Las superposiciones identificadas se encuentran por debajo del "
            "umbral de significancia y podrían ser atribuibles a la precisión "
            "cartográfica de las fuentes; se recomienda su verificación en "
            "campo antes de descartarlas definitivamente."
        )
    return base + cierre + reserva


# ───────────────────────────────────────────────────────────────────────────
# Generación del HTML
# ───────────────────────────────────────────────────────────────────────────

def _e(texto):
    """Escapa texto para HTML."""
    return _html.escape(str(texto if texto is not None else ""))


# Estilo inline de celda de datos: Word respeta border en el atributo y
# en el style; se ponen ambos para máxima compatibilidad.
_TD = ("border:1px solid #cccccc;padding:4px 7px;"
       "font-size:10pt;font-family:Calibri,Arial,sans-serif;")


def _th_office(titulos, color="1F4E5F"):
    """Encabezados <th> con estilo INLINE (Word ignora el <style> th{}).

    bgcolor + style para que el fondo de cabecera salga en Word y navegador.
    """
    th = ("border:1px solid #{c};padding:5px 7px;font-size:10pt;"
          "background:#{c};color:#ffffff;text-align:left;"
          "font-family:Calibri,Arial,sans-serif;").format(c=color)
    return "".join(
        "<th bgcolor='#{c}' style='{s}'>{t}</th>".format(c=color, s=th, t=_e(x))
        for x in titulos)


def _fila_superposicion(s):
    colores = {
        "critico": "#ffcdcd", "observable": "#ffebbe",
        "no_significativa": "#e1f0e1",
    }
    bg = colores.get(s["nivel"], "#ffffff")
    td = _TD + "background:" + bg + ";"
    td_r = td + "text-align:right;"
    return (
        "<tr>"
        "<td bgcolor='{bg}' style='{td}'>{capa}</td>"
        "<td bgcolor='{bg}' style='{td}'>{tipo}</td>"
        "<td bgcolor='{bg}' style='{td}'>{titular}</td>"
        "<td bgcolor='{bg}' style='{td}'>{codigo}</td>"
        "<td bgcolor='{bg}' style='{td_r}'>{area:.4f}</td>"
        "<td bgcolor='{bg}' style='{td_r}'>{pct:.2f}</td>"
        "<td bgcolor='{bg}' style='{td}'>{nivel}</td></tr>"
    ).format(bg=bg, td=td, td_r=td_r,
             capa=_e(s["capa"]), tipo=_e(s["tipo"]),
             titular=_e(s["titular"]), codigo=_e(s["codigo"]),
             area=s["area_ha"], pct=s["porcentaje"],
             nivel=_e(s["nivel_legible"]))


def generar_html(contexto, perfil_key="generico", conclusion=None,
                 responsable=None, incluir_anexo=True,
                 subtitulo=None, predio_titular=None, predio_derecho=None):
    """Construye el informe completo en HTML.

    conclusion: si se pasa, se usa tal cual (la versión editada por el
    usuario). Si es None, se genera la sugerida.
    """
    perfil = PERFILES.get(perfil_key, PERFILES["generico"])
    a = contexto["analisis"]
    p = a["predio"]
    color = perfil["color"]
    # Subtítulo editable por el usuario (independencia por informe).
    subtitulo_final = subtitulo if subtitulo is not None else perfil["subtitulo"]

    if conclusion is None:
        conclusion = conclusion_sugerida(contexto)

    # Filas de superposiciones (ordenadas por área en el contexto)
    filas = "".join(_fila_superposicion(s)
                    for s in contexto["superposiciones"])
    if not filas:
        filas = ("<tr><td colspan='7' style='text-align:center;color:#2E5E3A;'>"
                 "Sin superposiciones por encima del umbral.</td></tr>")

    # Capas no evaluadas
    errores_html = ""
    if contexto["errores"]:
        items = "".join(
            "<li>{}: {}</li>".format(_e(e["capa"]), _e(e["motivo"]))
            for e in contexto["errores"])
        errores_html = (
            '<h2>Capas no evaluadas</h2>'
            '<div style="border:1.5pt solid #B45309; background:#FEF3C7; '
            'padding:8pt; margin-bottom:8pt;">'
            '<p style="margin:0 0 6pt 0;"><b>ADVERTENCIA — cobertura '
            'incompleta.</b> Las siguientes {n} capa(s) NO pudieron '
            'incorporarse al análisis. Su omisión <b>no implica ausencia de '
            'superposición</b>: sobre estas fuentes el presente informe no '
            'se pronuncia.</p>'
            '<ul style="margin:0;">{items}</ul>'
            '</div>').format(n=len(contexto["errores"]), items=items)

    # Anexo de verificación
    anexo_html = ""
    if incluir_anexo:
        archivos = contexto.get("trazabilidad", {}).get("archivos", [])
        _td_capa = ("border:1px solid #ccc;padding:4px 7px;font-size:10pt;"
                    "width:35%;word-break:break-word;"
                    "font-family:Calibri,Arial,sans-serif;")
        _td_hash = ("border:1px solid #ccc;padding:4px 7px;"
                    "font-family:'Courier New',monospace;font-size:8pt;"
                    "width:52%;word-break:break-all;"
                    "overflow-wrap:break-word;word-wrap:break-word;")
        _td_ft = ("border:1px solid #ccc;padding:4px 7px;font-size:10pt;"
                  "width:13%;text-align:center;"
                  "font-family:Calibri,Arial,sans-serif;")
        filas_hash = "".join(
            "<tr><td style='{tc}'>{capa}</td>"
            "<td style='{th}'>{hash}</td>"
            "<td style='{tf}'>{ft}</td></tr>".format(
                tc=_td_capa, th=_td_hash, tf=_td_ft,
                capa=_e(af.get("capa", "—")),
                hash=_e(af.get("sha256") or "no disponible"),
                ft=_e(af.get("features", "—")))
            for af in archivos)
        anexo_html = (
            "<h2>Anexo de verificación técnica</h2>"
            "<p>Cada archivo analizado se identifica por su huella digital "
            "SHA-256, verificable por terceros "
            "(<code>certutil -hashfile &lt;archivo&gt; SHA256</code> en "
            "Windows).</p>"
            "<table border='1' cellspacing='0' cellpadding='4' "
            "style='border-collapse:collapse;width:100%;table-layout:fixed;'>"
            "<thead><tr>{th}</tr></thead>"
            "<tbody>{filas}</tbody></table>".format(
                th=_th_office(["Capa", "SHA-256", "Entidades"]),
                filas="{}")
        ).format(filas_hash)

    resp_html = ""
    if responsable:
        resp_html = ("<p style='margin-top:40px;'>_______________________<br>"
                     "{}</p>".format(_e(responsable)))

    # Métricas de resumen
    if a["hay_superposicion"]:
        resumen_extra = (
            "<tr><td>Área afectada (sin doble conteo)</td><td>{:.4f} ha "
            "({:.2f}%)</td></tr>"
            "<tr><td>Nivel del hallazgo</td><td><b>{}</b></td></tr>"
        ).format(a.get("area_afectada_unica_ha", 0.0),
                 a.get("porcentaje_afectado_unico", 0.0),
                 _e(a["nivel_global_legible"]))
    else:
        resumen_extra = ("<tr><td>Resultado</td><td><b>Sin superposición"
                         "</b></td></tr>")

    fila_titular = ""
    if predio_titular:
        fila_titular = "<tr><td>Titular / propietario</td><td><b>{}</b></td></tr>".format(
            _e(predio_titular))
    fila_derecho = ""
    if predio_derecho:
        fila_derecho = "<tr><td>Tipo de derecho evaluado</td><td>{}</td></tr>".format(
            _e(predio_derecho))

    return _PLANTILLA.format(
        color=color,
        encabezado=_e(perfil["encabezado"]),
        subtitulo=_e(subtitulo_final),
        institucion=_e(perfil["institucion"]),
        fecha=_e(a["fecha_legible"]),
        version=_e(a["plugin_version"]),
        predio=_e(p["nombre"]),
        fila_titular=fila_titular,
        fila_derecho=fila_derecho,
        area=p["area_ha"],
        perimetro=p["perimetro_m"],
        crs=_e(p["crs"]),
        metodo=_e(a["metodo_area"]),
        n_evaluadas=a["capas_evaluadas"],
        n_super=a["capas_con_superposicion"],
        umbral=a["umbral_ha"],
        resumen_extra=resumen_extra,
        filas=filas,
        th_detalle=_th_office(["Capa / Derecho", "Tipo", "Titular", "Código",
                               "Área (ha)", "% predio", "Nivel"], color),
        conclusion=_e(conclusion).replace("\n", "<br>"),
        errores_html=errores_html,
        anexo_html=anexo_html,
        responsable_html=resp_html,
    )


def exportar_doc(html_texto, ruta):
    """Guarda el informe como .doc que Word abre editable, sin dependencias.

    Word interpreta un HTML con cabeceras Office como documento nativo.
    CLAVE (v3.0.4 fix): NO se puede envolver el HTML completo dentro de
    otro <html><body> — eso anida dos documentos y Word desarma las
    tablas. Aquí se INYECTAN las cabeceras Office dentro del <head> ya
    existente, produciendo un único documento bien formado.
    """
    if not ruta.lower().endswith((".doc", ".html", ".htm")):
        ruta += ".doc"

    cabecera_office = (
        "<!--[if gte mso 9]><xml><w:WordDocument>"
        "<w:View>Print</w:View><w:Zoom>100</w:Zoom>"
        "<w:DoNotOptimizeForBrowser/></w:WordDocument></xml><![endif]-->"
    )
    # Namespaces Office en el <html> raíz + cabecera dentro del <head>
    doc = html_texto.replace(
        "<html>",
        "<html xmlns:o='urn:schemas-microsoft-com:office:office' "
        "xmlns:w='urn:schemas-microsoft-com:office:word' "
        "xmlns='http://www.w3.org/TR/REC-html40'>", 1)
    doc = doc.replace("</head>", cabecera_office + "</head>", 1)

    with open(ruta, "w", encoding="utf-8") as f:
        f.write(doc)
    return ruta


def guardar_html(html_texto, ruta):
    """Guarda el HTML tal cual (para vista en navegador)."""
    if not ruta.lower().endswith((".html", ".htm")):
        ruta += ".html"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html_texto)
    return ruta


# ───────────────────────────────────────────────────────────────────────────
# Plantilla HTML (estilos office-compatibles)
# ───────────────────────────────────────────────────────────────────────────

_PLANTILLA = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Calibri, Arial, sans-serif; color:#222;
          font-size:11pt; line-height:1.4; }}
  h1 {{ color:#{color}; font-size:16pt; text-align:center; margin-bottom:2px; }}
  .sub {{ text-align:center; color:#555; font-size:10pt; margin-top:0; }}
  h2 {{ color:#{color}; font-size:12pt; border-bottom:2px solid #{color};
        padding-bottom:2px; margin-top:22px; }}
  table {{ border-collapse:collapse; width:100%; margin:8px 0; }}
  th {{ background:#{color}; color:white; padding:5px 7px; font-size:10pt;
        text-align:left; }}
  td {{ border:1px solid #ccc; padding:4px 7px; font-size:10pt; }}
  .meta td {{ border:none; padding:2px 6px; }}
  .meta td:first-child {{ color:#555; width:38%; }}
  .concl {{ background:#f7f9f9; border:1px solid #{color}; padding:10px;
            text-align:justify; }}
  .foot {{ margin-top:30px; color:#888; font-size:8pt;
           border-top:1px solid #ccc; padding-top:4px; }}
</style></head><body>

<h1>{encabezado}</h1>
<p class="sub">{subtitulo}</p>

<table cellspacing="0" cellpadding="2" style="border-collapse:collapse;width:100%;">
  <tr><td>Fecha del análisis</td><td>{fecha}</td></tr>
  <tr><td>Institución</td><td>{institucion}</td></tr>
  <tr><td>Herramienta</td><td>YF GIS Amazonia Tools v{version}</td></tr>
</table>

<h2>1. Área evaluada</h2>
<table cellspacing="0" cellpadding="2" style="border-collapse:collapse;width:100%;">
  <tr><td>Predio</td><td><b>{predio}</b></td></tr>
  {fila_titular}
  {fila_derecho}
  <tr><td>Área</td><td>{area:.4f} ha</td></tr>
  <tr><td>Perímetro</td><td>{perimetro:.2f} m</td></tr>
  <tr><td>Sistema de coordenadas</td><td>{crs}</td></tr>
  <tr><td>Método de cálculo de área</td><td>{metodo}</td></tr>
</table>

<h2>2. Resumen del análisis</h2>
<table cellspacing="0" cellpadding="2" style="border-collapse:collapse;width:100%;">
  <tr><td>Capas evaluadas</td><td>{n_evaluadas}</td></tr>
  <tr><td>Capas con superposición</td><td>{n_super}</td></tr>
  <tr><td>Umbral de tolerancia</td><td>{umbral} ha</td></tr>
  {resumen_extra}
</table>

<h2>3. Detalle de superposiciones</h2>
<table border="1" cellspacing="0" cellpadding="4"
       style="border-collapse:collapse;width:100%;">
  <thead><tr>{th_detalle}</tr></thead>
  <tbody>{filas}</tbody>
</table>

{errores_html}

<h2>4. Conclusión</h2>
<div class="concl">{conclusion}</div>
{responsable_html}

{anexo_html}

<p class="foot">Documento generado por YF GIS Amazonia Tools · gis-amazonia.pe ·
La conclusión es un borrador técnico sujeto a revisión y validación
profesional. Los resultados dependen de la vigencia y exactitud de las
capas de origen analizadas.</p>

</body></html>"""
