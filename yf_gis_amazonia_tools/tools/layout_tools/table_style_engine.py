# -*- coding: utf-8 -*-
"""
Table Style Manager Engine — API verificada directamente en QGIS 3.44.

Métodos reales confirmados:
  tabla.setHeaderFont(QFont)
  tabla.setHeaderFontColor(QColor)
  tabla.setHeaderTextFormat(QgsTextFormat)
  tabla.setContentFont(QFont)
  tabla.setContentFontColor(QColor)
  tabla.setContentTextFormat(QgsTextFormat)
  tabla.setCellStyle(CellStyleGroup, QgsLayoutTableStyle)
  tabla.setGridColor(QColor)
  tabla.setGridStrokeWidth(float)
  tabla.setCellMargin(float)
  QgsLayoutTableStyle.cellBackgroundColor = QColor
  QgsLayoutTableStyle.enabled = bool

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import json
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    QgsLayoutItemAttributeTable,
    QgsLayoutTableStyle,
    QgsLayoutFrame,
    QgsTextFormat,
)


# ─────────────────────────────────────────────────────────────────────────────
# Estilos predefinidos
# ─────────────────────────────────────────────────────────────────────────────

ESTILOS_PREDEFINIDOS = {
    "coordenadas_utm": {
        "nombre":      "Coordenadas UTM",
        "descripcion": "Para memorias descriptivas y catastro",
        "header_bg":   "#2c5f8a",
        "header_fg":   "#ffffff",
        "header_size": 9,
        "header_bold": True,
        "content_fg":  "#000000",
        "content_size": 8,
        "content_bold": False,
        "even_bg":     "#e8f0f7",
        "odd_bg":      "#ffffff",
        "grid_color":  "#2c5f8a",
        "grid_width":  0.3,
        "cell_margin": 1.0,
    },
    "puntos_gnss": {
        "nombre":      "Puntos GNSS",
        "descripcion": "Para informes de levantamiento topográfico",
        "header_bg":   "#1a6e2e",
        "header_fg":   "#ffffff",
        "header_size": 8,
        "header_bold": True,
        "content_fg":  "#000000",
        "content_size": 7,
        "content_bold": False,
        "even_bg":     "#e8f5ec",
        "odd_bg":      "#ffffff",
        "grid_color":  "#1a6e2e",
        "grid_width":  0.3,
        "cell_margin": 0.8,
    },
    "inventario_forestal": {
        "nombre":      "Inventario Forestal",
        "descripcion": "Para POA, DEMA, planes de manejo SERFOR",
        "header_bg":   "#4a3520",
        "header_fg":   "#ffffff",
        "header_size": 8,
        "header_bold": True,
        "content_fg":  "#000000",
        "content_size": 7,
        "content_bold": False,
        "even_bg":     "#f5ede0",
        "odd_bg":      "#ffffff",
        "grid_color":  "#4a3520",
        "grid_width":  0.3,
        "cell_margin": 0.8,
    },
    "institucional": {
        "nombre":      "Institucional / Neutro",
        "descripcion": "Para entregables GOREMAD, FENAMAD, ACCA",
        "header_bg":   "#333333",
        "header_fg":   "#ffffff",
        "header_size": 8,
        "header_bold": True,
        "content_fg":  "#000000",
        "content_size": 7,
        "content_bold": False,
        "even_bg":     "#f0f0f0",
        "odd_bg":      "#ffffff",
        "grid_color":  "#666666",
        "grid_width":  0.25,
        "cell_margin": 1.0,
    },
    "minimalista": {
        "nombre":      "Minimalista",
        "descripcion": "Para mapas de presentación y reportes ACCA",
        "header_bg":   "#ffffff",
        "header_fg":   "#000000",
        "header_size": 8,
        "header_bold": True,
        "content_fg":  "#333333",
        "content_size": 7,
        "content_bold": False,
        "even_bg":     "#f9f9f9",
        "odd_bg":      "#ffffff",
        "grid_color":  "#cccccc",
        "grid_width":  0.2,
        "cell_margin": 0.8,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def aplicar_estilo(tabla, estilo):
    """
    Aplica estilo a QgsLayoutItemAttributeTable.
    Usa la API verificada en QGIS 3.44.
    """
    try:
        from ...core.logger import log_info, log_error
    except Exception:
        log_info = print
        log_error = print

    try:
        # ── Fuente y color del encabezado ─────────────────────────────
        font_h = QFont(
            estilo.get("header_font", "Arial"),
            int(estilo.get("header_size", 9))
        )
        font_h.setBold(estilo.get("header_bold", True))

        tabla.setHeaderFont(font_h)
        tabla.setHeaderFontColor(QColor(estilo.get("header_fg", "#ffffff")))

        # setHeaderTextFormat — controla color + fuente juntos
        fmt_h = QgsTextFormat()
        fmt_h.setFont(font_h)
        fmt_h.setColor(QColor(estilo.get("header_fg", "#ffffff")))
        fmt_h.setSize(float(estilo.get("header_size", 9)))
        tabla.setHeaderTextFormat(fmt_h)

        # ── Fuente y color del contenido ──────────────────────────────
        font_c = QFont(
            estilo.get("content_font", "Arial"),
            int(estilo.get("content_size", 8))
        )
        font_c.setBold(estilo.get("content_bold", False))

        tabla.setContentFont(font_c)
        tabla.setContentFontColor(QColor(estilo.get("content_fg", "#000000")))

        fmt_c = QgsTextFormat()
        fmt_c.setFont(font_c)
        fmt_c.setColor(QColor(estilo.get("content_fg", "#000000")))
        fmt_c.setSize(float(estilo.get("content_size", 8)))
        tabla.setContentTextFormat(fmt_c)

        # ── Fondo del encabezado (cellStyle HeaderRow) ────────────────
        s_header = QgsLayoutTableStyle()
        s_header.enabled = True
        s_header.cellBackgroundColor = QColor(estilo.get("header_bg", "#333333"))
        tabla.setCellStyle(QgsLayoutItemAttributeTable.CellStyleGroup.HeaderRow, s_header)

        # ── Filas impares ─────────────────────────────────────────────
        s_odd = QgsLayoutTableStyle()
        s_odd.enabled = True
        s_odd.cellBackgroundColor = QColor(estilo.get("odd_bg", "#ffffff"))
        tabla.setCellStyle(QgsLayoutItemAttributeTable.CellStyleGroup.OddRows, s_odd)

        # ── Filas pares — zebra ───────────────────────────────────────
        s_even = QgsLayoutTableStyle()
        s_even.enabled = True
        s_even.cellBackgroundColor = QColor(estilo.get("even_bg", "#f0f0f0"))
        tabla.setCellStyle(QgsLayoutItemAttributeTable.CellStyleGroup.EvenRows, s_even)

        # ── Grilla ────────────────────────────────────────────────────
        tabla.setGridColor(QColor(estilo.get("grid_color", "#666666")))
        tabla.setGridStrokeWidth(estilo.get("grid_width", 0.3))

        # ── Márgenes ──────────────────────────────────────────────────
        tabla.setCellMargin(estilo.get("cell_margin", 1.0))

        # Refresh robusto — forzar redibujado de tabla y frames
        tabla.refresh()
        try:
            for i in range(tabla.frameCount()):
                frame = tabla.frame(i)
                if frame:
                    frame.update()
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        # Refrescar el layout completo
        try:
            from qgis.core import QgsProject
            for layout in QgsProject.instance().layoutManager().layouts():
                for mf in layout.multiFrames():
                    if mf == tabla:
                        layout.refresh()
                        break
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        log_info(f"✅ Table Style '{estilo.get('nombre','?')}' aplicado")

    except Exception as e:
        try:
            log_error(f"aplicar_estilo error: {e}")
        except Exception:
            print(f"aplicar_estilo error: {e}")
        import traceback
        traceback.print_exc()


def capturar_estilo(tabla):
    """Captura el estilo actual de una tabla."""
    try:
        font_h = tabla.headerFont()
        font_c = tabla.contentFont()
        fg_h   = tabla.headerFontColor().name()
        fg_c   = tabla.contentFontColor().name()

        s_header = tabla.cellStyle(QgsLayoutItemAttributeTable.CellStyleGroup.HeaderRow)
        s_even   = tabla.cellStyle(QgsLayoutItemAttributeTable.CellStyleGroup.EvenRows)
        s_odd    = tabla.cellStyle(QgsLayoutItemAttributeTable.CellStyleGroup.OddRows)

        return {
            "nombre":       "Estilo copiado",
            "descripcion":  "Copiado desde tabla del layout",
            "header_bg":    s_header.cellBackgroundColor.name() if s_header.enabled else "#333333",
            "header_fg":    fg_h,
            "header_size":  font_h.pointSize(),
            "header_bold":  font_h.bold(),
            "header_font":  font_h.family(),
            "content_fg":   fg_c,
            "content_size": font_c.pointSize(),
            "content_bold": font_c.bold(),
            "content_font": font_c.family(),
            "even_bg":      s_even.cellBackgroundColor.name() if s_even.enabled else "#f0f0f0",
            "odd_bg":       s_odd.cellBackgroundColor.name() if s_odd.enabled else "#ffffff",
            "grid_color":   tabla.gridColor().name(),
            "grid_width":   tabla.gridStrokeWidth(),
            "cell_margin":  tabla.cellMargin(),
        }
    except Exception as e:
        try:
            from ...core.logger import log_error
            log_error(f"capturar_estilo: {e}")
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        return None


def guardar_estilo_json(estilo, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(estilo, f, indent=2, ensure_ascii=False)


def cargar_estilo_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_tablas_en_layout(layout):
    """
    Retorna todas las QgsLayoutItemAttributeTable del layout.
    Busca en multiFrames() y en items() con sus frames.
    NOTA: QgsLayoutItemHtml NO es una tabla de atributos — se ignora.
    """
    tablas = []
    seen = set()
    try:
        # Búsqueda principal: multiFrames()
        for mf in layout.multiFrames():
            if isinstance(mf, QgsLayoutItemAttributeTable):
                if id(mf) not in seen:
                    tablas.append(mf)
                    seen.add(id(mf))

        # Búsqueda secundaria: items directos y frames
        for item in layout.items():
            if isinstance(item, QgsLayoutItemAttributeTable):
                if id(item) not in seen:
                    tablas.append(item)
                    seen.add(id(item))
            elif isinstance(item, QgsLayoutFrame):
                try:
                    mf = item.multiFrame()
                    if isinstance(mf, QgsLayoutItemAttributeTable):
                        if id(mf) not in seen:
                            tablas.append(mf)
                            seen.add(id(mf))
                except Exception:
                    logging.getLogger(__name__).debug("suppressed", exc_info=True)

        try:
            from ...core.logger import log_info
            log_info(
                f"get_tablas_en_layout '{layout.name()}': "
                f"{len(tablas)} tabla(s) encontrada(s) | "
                f"multiFrames totales: {len(layout.multiFrames())} "
                f"(tipos: {[type(mf).__name__ for mf in layout.multiFrames()]})"
            )
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    except Exception as e:
        try:
            from ...core.logger import log_error
            log_error(f"get_tablas_en_layout: {e}")
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
    return tablas


def get_layouts_con_tablas(project):
    """
    Retorna lista de (layout, tablas) para todos los layouts
    que tengan al menos una QgsLayoutItemAttributeTable.
    Útil para el selector del diálogo.
    """
    from qgis.core import QgsPrintLayout
    resultado = []
    for layout in project.layoutManager().layouts():
        if not isinstance(layout, QgsPrintLayout):
            continue
        tablas = get_tablas_en_layout(layout)
        if tablas:
            resultado.append((layout, tablas))
    return resultado


def nombre_tabla(tabla):
    """Retorna nombre descriptivo de la tabla para el selector."""
    try:
        capa = tabla.vectorLayer()
        if capa:
            # Contar columnas
            cols = len(tabla.columns())
            filas = tabla.maximumNumberOfFeatures() if hasattr(tabla, 'maximumNumberOfFeatures') else "?"
            return f"{capa.name()}  ({cols} columnas)"
        else:
            # Sin capa — puede ser tabla vacía o de atlas
            return "Tabla sin capa vinculada"
    except Exception:
        logging.getLogger(__name__).debug("suppressed", exc_info=True)
    return "Tabla de atributos"
