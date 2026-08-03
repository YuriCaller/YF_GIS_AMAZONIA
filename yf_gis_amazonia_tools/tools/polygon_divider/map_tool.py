# -*- coding: utf-8 -*-
"""
Polygon Divider — Map Tool.

Herramienta de canvas que permite al usuario trazar la línea de corte
(2 clics) directamente sobre el mapa, replicando el flujo de "Divide"
de ArcGIS Pro.

- La línea de corte se dibuja en ROJO con flechas de dirección.
- Mientras se traza, se muestra una vista previa en AMARILLO de cómo
  quedarían los fragmentos resultantes (rubber bands de polígono).
- El ángulo resultante se reporta al diálogo vía señal Qt para
  sincronizar con el spinbox de ángulo.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging
import math

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QCursor, QPixmap, QPainter, QPen
from qgis.PyQt.QtWidgets import QApplication

from qgis.core import QgsWkbTypes, QgsPointXY
from qgis.gui import (QgsMapTool, QgsRubberBand,
                      QgsMapCanvasSnappingUtils, QgsSnapIndicator)

from ...core.logger import log_info, log_error
from . import division_engine as engine


# Colores fijos del módulo (siguiendo la apreciación visual acordada)
COLOR_LINEA_CORTE = QColor(224, 92, 42, 230)      # rojo/naranja TUCSA — línea de corte
COLOR_PREVIEW_FILL = QColor(240, 192, 64, 60)     # amarillo translúcido — preview fragmentos
COLOR_PREVIEW_LINE = QColor(240, 192, 64, 200)    # amarillo — borde preview


class PolygonDividerMapTool(QgsMapTool):
    """
    Map tool de 2 clics: primer clic fija el punto de inicio de la línea,
    segundo clic fija el punto final. Mientras el mouse se mueve entre
    ambos clics, se dibuja en vivo la línea roja + preview amarillo.
    """

    # Emitida cada vez que la línea cambia (incluye angulo en radianes)
    lineaActualizada = pyqtSignal(float)
    # Emitida cuando el usuario completa el trazo (2do clic)
    lineaCompletada = pyqtSignal(float)
    # Emitida si el usuario cancela (Esc o clic derecho)
    trazadoCancelado = pyqtSignal()

    def __init__(self, canvas, geom_referencia=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.geom_referencia = geom_referencia  # QgsGeometry del polígono activo

        self._punto_inicio = None
        self._punto_actual = None
        self._angulo_rad = 0.0

        # Rubber band de la línea (roja)
        self._rb_linea = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
        self._rb_linea.setColor(COLOR_LINEA_CORTE)
        self._rb_linea.setWidth(3)

        # Rubber band del preview de fragmentos (amarillo) — opcional,
        # se activa solo si hay area_objetivo configurada externamente.
        self._rb_preview = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self._rb_preview.setColor(COLOR_PREVIEW_LINE)
        self._rb_preview.setFillColor(COLOR_PREVIEW_FILL)
        self._rb_preview.setWidth(2)

        self._area_objetivo_preview = None  # si se define, dibuja preview en vivo

        self.setCursor(self._build_cross_cursor())

        # v3.0.4: snapping a vértices/segmentos de las capas del canvas.
        # Utils PROPIO (no depende de la config de snapping del proyecto):
        # así el trazado siempre ajusta aunque el usuario tenga el snap
        # global apagado, y sin alterar su configuración.
        self._snap_activo = True
        self._snap_utils = None
        self._snap_indicator = None
        try:
            self._snap_utils = self._crear_snap_utils()
            self._snap_indicator = QgsSnapIndicator(self.canvas)
        except Exception:
            logging.getLogger(__name__).warning(
                "Polygon Divider: snapping no disponible", exc_info=True)

    # ------------------------------------------------------------------
    # Configuración externa
    # ------------------------------------------------------------------

    def set_geometria_referencia(self, geom):
        """Actualiza el polígono sobre el cual se traza la línea."""
        self.geom_referencia = geom

    def set_area_objetivo_preview(self, area):
        """
        Si se define un área objetivo, el map tool mostrará en vivo el
        fragmento resultante (amarillo) mientras el usuario mueve el
        segundo punto de la línea. Pasar None para desactivar.
        """
        self._area_objetivo_preview = area

    def set_snap_activo(self, activo):
        """Activa/desactiva el ajuste a vértices y segmentos."""
        self._snap_activo = bool(activo)
        if not self._snap_activo:
            self._ocultar_snap()

    def _crear_snap_utils(self):
        """Construye un QgsMapCanvasSnappingUtils propio: todas las capas,
        vértice + segmento, tolerancia 14 px. Compatible Qt5/Qt6."""
        from qgis.core import QgsProject, QgsSnappingConfig, Qgis
        utils = QgsMapCanvasSnappingUtils(self.canvas)
        cfg = QgsSnappingConfig(QgsProject.instance())
        cfg.setEnabled(True)
        try:
            cfg.setMode(Qgis.SnappingMode.AllLayers)
        except AttributeError:
            cfg.setMode(getattr(QgsSnappingConfig, "SnappingMode",
                                QgsSnappingConfig).AllLayers)
        try:
            cfg.setTypeFlag(Qgis.SnappingTypes(
                Qgis.SnappingType.Vertex | Qgis.SnappingType.Segment))
        except (AttributeError, TypeError):
            cfg.setTypeFlag(
                QgsSnappingConfig.SnappingType.VertexFlag
                | QgsSnappingConfig.SnappingType.SegmentFlag)
        try:
            cfg.setUnits(Qgis.MapToolUnit.Pixels)
        except AttributeError:
            from qgis.core import QgsTolerance
            cfg.setUnits(QgsTolerance.UnitType.Pixels)
        cfg.setTolerance(14)
        utils.setConfig(cfg)
        return utils

    def _punto_con_snap(self, event):
        """Punto del evento, ajustado a vértice/segmento si corresponde.
        Actualiza el indicador visual (cruz magenta estándar de QGIS)."""
        if not self._snap_activo or self._snap_utils is None:
            self._ocultar_snap()
            return self.toMapCoordinates(event.pos())
        try:
            match = self._snap_utils.snapToMap(event.pos())
            if self._snap_indicator is not None:
                self._snap_indicator.setMatch(match)
            if match.isValid():
                return QgsPointXY(match.point())
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        return self.toMapCoordinates(event.pos())

    def _ocultar_snap(self):
        if self._snap_indicator is None:
            return
        try:
            from qgis.core import QgsPointLocator
            self._snap_indicator.setMatch(QgsPointLocator.Match())
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def angulo_actual_grados(self):
        """Ángulo de la línea trazada, en grados (0-180), para sincronizar UI."""
        return math.degrees(self._angulo_rad) % 180

    # ------------------------------------------------------------------
    # Ciclo de vida QgsMapTool
    # ------------------------------------------------------------------

    def activate(self):
        super().activate()
        self.canvas.setCursor(self._build_cross_cursor())
        self._punto_inicio = None
        self._punto_actual = None

    def deactivate(self):
        self._ocultar_snap()
        self._limpiar_rubber_bands()
        self.canvas.unsetCursor()
        super().deactivate()

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return True

    # ------------------------------------------------------------------
    # Eventos de mouse
    # ------------------------------------------------------------------

    def canvasPressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._cancelar()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        punto_mapa = self._punto_con_snap(event)

        if self._punto_inicio is None:
            # Primer clic: fija inicio
            self._punto_inicio = QgsPointXY(punto_mapa)
            self._punto_actual = QgsPointXY(punto_mapa)
        else:
            # Segundo clic: completa el trazo
            self._punto_actual = QgsPointXY(punto_mapa)
            self._actualizar_angulo()
            self._dibujar_linea()
            self.lineaCompletada.emit(self._angulo_rad)
            log_info(
                f"Polygon Divider: línea de corte trazada — "
                f"ángulo={math.degrees(self._angulo_rad):.1f}°"
            )
            # Listo para un nuevo trazo si el usuario quiere rehacer
            self._punto_inicio = None

    def canvasMoveEvent(self, event):
        # El indicador de snap se muestra desde antes del primer clic,
        # para que el usuario vea a qué vértice/segmento va a anclar.
        punto_mapa = self._punto_con_snap(event)
        if self._punto_inicio is None:
            return

        self._punto_actual = QgsPointXY(punto_mapa)
        self._actualizar_angulo()
        self._dibujar_linea()
        self.lineaActualizada.emit(self._angulo_rad)
        self._actualizar_preview()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancelar()
            event.accept()

    # ------------------------------------------------------------------
    # Lógica interna
    # ------------------------------------------------------------------

    def _actualizar_angulo(self):
        if self._punto_inicio is None or self._punto_actual is None:
            return
        dx = self._punto_actual.x() - self._punto_inicio.x()
        dy = self._punto_actual.y() - self._punto_inicio.y()
        if dx == 0 and dy == 0:
            return
        self._angulo_rad = math.atan2(dy, dx)

    def _dibujar_linea(self):
        """Dibuja la línea roja con flechas de dirección sobre el canvas."""
        if self._punto_inicio is None or self._punto_actual is None:
            return

        self._rb_linea.reset(QgsWkbTypes.GeometryType.LineGeometry)

        # Extender la línea más allá de los puntos clicados, para que
        # cruce completamente el polígono (igual que ArcGIS Pro).
        if self.geom_referencia is not None:
            diag = engine._bbox_diagonal(self.geom_referencia) * 0.7 + 1.0
        else:
            diag = math.hypot(
                self._punto_actual.x() - self._punto_inicio.x(),
                self._punto_actual.y() - self._punto_inicio.y(),
            ) * 3.0 + 1.0

        centro = QgsPointXY(
            (self._punto_inicio.x() + self._punto_actual.x()) / 2.0,
            (self._punto_inicio.y() + self._punto_actual.y()) / 2.0,
        )

        dx = math.cos(self._angulo_rad) * diag
        dy = math.sin(self._angulo_rad) * diag
        p1 = QgsPointXY(centro.x() - dx, centro.y() - dy)
        p2 = QgsPointXY(centro.x() + dx, centro.y() + dy)

        self._rb_linea.addPoint(p1, False)
        self._rb_linea.addPoint(p2, True)

    def _actualizar_preview(self):
        """
        Si hay area_objetivo_preview configurada y geometría de referencia
        disponible, calcula y dibuja en amarillo el fragmento resultante
        en vivo. Si el cálculo falla (ángulo no válido todavía), simplemente
        no actualiza el preview — no se interrumpe el trazo.
        """
        if self._area_objetivo_preview is None or self.geom_referencia is None:
            return

        try:
            frag_a, _, _, _, _ = engine.calcular_corte_por_area(
                self.geom_referencia, self._angulo_rad, self._area_objetivo_preview
            )
            self._rb_preview.setToGeometry(frag_a, None)
        except Exception:
            # Durante el trazo en vivo es normal que algunos ángulos
            # intermedios no sean válidos todavía; se ignora silenciosamente.
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def _limpiar_rubber_bands(self):
        self._rb_linea.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self._rb_preview.reset(QgsWkbTypes.GeometryType.PolygonGeometry)

    def _cancelar(self):
        self._ocultar_snap()
        self._punto_inicio = None
        self._punto_actual = None
        self._limpiar_rubber_bands()
        self.trazadoCancelado.emit()

    def limpiar(self):
        """Llamado externamente (ej. al cerrar el diálogo) para limpiar el canvas."""
        self._limpiar_rubber_bands()

    def actualizar_preview_externo(self, geom_resultado):
        """Permite que el diálogo empuje un preview ya calculado (ej. para
        modo N-partes, donde el cálculo se hace fuera del map tool)."""
        if geom_resultado is not None:
            self._rb_preview.setToGeometry(geom_resultado, None)
        else:
            self._rb_preview.reset(QgsWkbTypes.GeometryType.PolygonGeometry)

    # ------------------------------------------------------------------
    # Cursor
    # ------------------------------------------------------------------

    def _build_cross_cursor(self):
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(COLOR_LINEA_CORTE, 2))
        p.drawLine(16, 4, 16, 28)
        p.drawLine(4, 16, 28, 16)
        p.end()
        return QCursor(pix, 16, 16)
