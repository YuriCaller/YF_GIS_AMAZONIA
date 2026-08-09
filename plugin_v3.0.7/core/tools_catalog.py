# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Catálogo de herramientas de la suite.

FUENTE ÚNICA de la descripción de cada herramienta. De aquí se alimentan:

  * el diálogo «Acerca de» (lista visible al usuario),
  * los botones de ayuda contextual (ancla en el manual),
  * la navegación del manual publicado.

MOTIVO
------
Hasta v3.0.6 la lista del «Acerca de» estaba escrita a mano en el propio
diálogo. Se quedó congelada en v2.0: anunciaba ocho herramientas cuando
la suite ya tenía diecisiete, y seguía marcando como «nuevo v2.0» cosas
publicadas hacía un año. Con la lista escrita en un solo sitio, ese
desfase no puede repetirse.

REGLA AL AÑADIR UNA HERRAMIENTA
-------------------------------
Se registra aquí Y en core/plugin_manager.py. El test
tests/test_catalogo.py comprueba que ambas listas coincidan, de modo que
olvidar una de las dos falla en las pruebas y no en producción.

`clave` es a la vez el ancla en el manual y el identificador del menú:
debe coincidir con el `tool_id` de plugin_manager.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

from collections import OrderedDict

DOCS_BASE = "https://yuricaller.github.io/YF_GIS_AMAZONIA"

# Orden de presentación. Reproduce el orden del menú de QGIS: quien busca
# una herramienta en el «Acerca de» la encuentra donde ya la usa.
ORDEN_CATEGORIAS = (
    "Catastral",
    "Geodesia / GNSS",
    "Búsqueda y Análisis",
    "Agroforestal / Ambiental",
    "Layout / Compositor",
    "Comparación y Navegación",
)


class Herramienta:
    """Ficha de una herramienta de la suite."""

    __slots__ = ("clave", "nombre", "resumen", "categoria", "desde", "icono")

    def __init__(self, clave, nombre, resumen, categoria, desde, icono):
        self.clave = clave
        self.nombre = nombre
        self.resumen = resumen
        self.categoria = categoria
        self.desde = desde        # versión en que se publicó
        self.icono = icono

    @property
    def url_manual(self):
        return "{}/herramientas/{}/".format(DOCS_BASE, self.clave)

    def es_nueva(self, version_actual, ventana=2):
        """True si se publicó dentro de las últimas `ventana` versiones menores.

        Se calcula en tiempo de ejecución en vez de escribir «(nuevo
        v2.0)» a mano, que es lo que dejó etiquetas obsoletas durante un
        año en el diálogo anterior.
        """
        def menor(v):
            partes = str(v).split(".")
            try:
                return int(partes[0]) * 100 + int(partes[1])
            except (ValueError, IndexError):
                return 0
        return menor(version_actual) - menor(self.desde) <= ventana


HERRAMIENTAS = (
    # ── Catastral ─────────────────────────────────────────────────────
    Herramienta(
        "memoria_descriptiva", "Memoria Descriptiva",
        "Genera la memoria descriptiva en Word a partir del polígono, "
        "con cuadro de vértices, narrativa de colindancias y croquis.",
        "Catastral", "1.0.0", "memoria_descriptiva.png"),
    Herramienta(
        "segmentador", "Segmentador de Parcelas",
        "Calcula azimuts, ángulos internos y distancias por lado, y "
        "genera las capas de segmentos y vértices.",
        "Catastral", "1.0.0", "segmentador.png"),
    Herramienta(
        "vector_geometry", "Calculadora de Geometría Vectorial",
        "Área, perímetro, centroide, longitud y azimut sobre la propia "
        "capa, con método elipsoidal o plano.",
        "Catastral", "2.1.0", "vector_geometry.png"),
    Herramienta(
        "yf_tools_plus", "YF Tools Plus",
        "Coordenadas, vértices, área y perímetro. Incluye Tabla → "
        "Polígono, que arma predios desde Excel o CSV con soporte "
        "multipolígono.",
        "Catastral", "3.0.0", "yf_tools.png"),
    Herramienta(
        "polygon_divider", "Divisor de Polígonos",
        "Divide un predio por área exacta, partes iguales o porcentajes, "
        "con línea de corte trazada o definida por ángulo.",
        "Catastral", "2.3.0", "polygon_divider.png"),
    Herramienta(
        "smart_georeferencer", "Georreferenciador Inteligente",
        "Georreferencia planos escaneados e imágenes de dron en vivo "
        "sobre el lienzo, con warp TPS y diagnóstico de calidad.",
        "Catastral", "2.4.0", "smart_georeferencer.png"),
    Herramienta(
        "smart_labels", "Etiquetado Técnico",
        "Etiquetas de vértice, distancia con azimut y bloque de área "
        "con perímetro, aplicadas según el tipo de geometría.",
        "Catastral", "2.1.0", "smart_labels.png"),
    Herramienta(
        "batch_export", "Exportar Expediente",
        "Exporta capas y composiciones a una carpeta estructurada "
        "(SHP, GPKG, PDF, XLSX y metadatos) en una sola acción.",
        "Catastral", "2.1.0", "batch_export.png"),

    # ── Geodesia / GNSS ───────────────────────────────────────────────
    Herramienta(
        "gnss_postprocess", "Post-Proceso PPK / PPP",
        "Post-proceso GNSS con RTKLIB: efemérides precisas, corrección "
        "ANTEX, validación antifalso-fix y procesamiento por lotes.",
        "Geodesia / GNSS", "1.0.0", "gnss.png"),

    # ── Búsqueda y Análisis ───────────────────────────────────────────
    Herramienta(
        "superposition", "Análisis de Superposición de Derechos",
        "Contrasta un predio contra derechos preexistentes y áreas "
        "protegidas, desde archivos locales o geoservicios oficiales, "
        "con informe trazable.",
        "Búsqueda y Análisis", "3.0.5", "superposition.png"),
    Herramienta(
        "attribute_search", "Búsqueda Avanzada de Atributos",
        "Busca en varias capas a la vez, con reportes y localización de "
        "los resultados en el mapa.",
        "Búsqueda y Análisis", "1.0.0", "search.png"),

    # ── Agroforestal / Ambiental ──────────────────────────────────────
    Herramienta(
        "saf_generator", "Generador de Sistemas Agroforestales",
        "Diseña la distribución de un SAF dentro del predio con seis "
        "métodos de siembra.",
        "Agroforestal / Ambiental", "1.0.0", "saf.png"),

    # ── Layout / Compositor ───────────────────────────────────────────
    Herramienta(
        "title_block", "Generador de Cajetín",
        "Inserta el cajetín del plano con expresiones dinámicas de "
        "escala, fecha, datum y proyección, y elementos agrupados.",
        "Layout / Compositor", "2.6.1", "title_block.png"),
    Herramienta(
        "layout_tools", "Gestor de Estilos de Tabla",
        "Aplica, copia y pega estilos de tabla de atributos en el "
        "compositor, con cinco estilos predefinidos.",
        "Layout / Compositor", "2.1.0", "layout_tools.png"),
    Herramienta(
        "layout_rescaler", "Redimensionar Composición",
        "Cambia el tamaño de papel manteniendo la proporción y la "
        "posición relativa de todos los elementos.",
        "Layout / Compositor", "2.1.0", "layout_rescaler.png"),

    # ── Comparación y Navegación ──────────────────────────────────────
    Herramienta(
        "swipe", "Comparación Visual (Swipe)",
        "Cortina deslizante para comparar dos capas, al estilo de "
        "ArcGIS Pro.",
        "Comparación y Navegación", "2.0.0", "swipe.png"),
    Herramienta(
        "goto", "Navegación a Coordenadas (Go-To)",
        "Lleva el mapa a una coordenada en DD, GMS, UTM o MGRS, con "
        "pegado desde Excel y lectura por OCR.",
        "Comparación y Navegación", "2.0.0", "goto.png"),
)


# ──────────────────────────────────────────────────────────────────────
# Consultas
# ──────────────────────────────────────────────────────────────────────

def por_clave(clave):
    """Devuelve la ficha de una herramienta, o None."""
    for h in HERRAMIENTAS:
        if h.clave == clave:
            return h
    return None


def por_categoria():
    """OrderedDict categoría → [Herramienta], en el orden del menú."""
    agrupado = OrderedDict((c, []) for c in ORDEN_CATEGORIAS)
    for h in HERRAMIENTAS:
        agrupado.setdefault(h.categoria, []).append(h)
    return OrderedDict((c, v) for c, v in agrupado.items() if v)


def url_ayuda(clave):
    """URL del manual para una herramienta. Cae en la portada si no existe."""
    h = por_clave(clave)
    return h.url_manual if h else DOCS_BASE + "/"


def abrir_ayuda(clave):
    """Abre el manual de una herramienta en el navegador.

    Se usa QDesktopServices y no un visor incrustado: QtWebEngine no
    está garantizado en todas las instalaciones de QGIS, y una ayuda que
    revienta el diálogo es peor que ninguna ayuda.
    """
    from qgis.PyQt.QtCore import QUrl
    from qgis.PyQt.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl(url_ayuda(clave)))
