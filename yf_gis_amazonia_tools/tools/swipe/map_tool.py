# -*- coding: utf-8 -*-
"""
YF Swipe Map Tool v1.1
Map tool que implementa el efecto swipe sobre el canvas de QGIS.

Modos disponibles:
- Swipe lineal: divisor arrastrable horizontal o vertical
- Lupa: círculo que sigue al cursor mostrando la capa swipe

Features:
- Transparencia ajustable de la capa swipe (0-100%)
- Cache inteligente de imagen renderizada
- Atajos de teclado: flechas (mover), +/- (radio lupa), Ctrl+S (exportar)

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import logging
from qgis.PyQt.QtCore import (
    Qt, QPoint, QPointF, QRect, QRectF, QSize, pyqtSignal, QTimer
)
from qgis.PyQt.QtGui import (
    QCursor, QPixmap, QPainter, QPen, QBrush, QColor,
    QFont, QPolygon, QImage, QPainterPath, QKeySequence
)
from qgis.PyQt.QtWidgets import QApplication

from qgis.core import (
    QgsMapSettings, QgsMapRendererCustomPainterJob,
    QgsRectangle, QgsProject, QgsMapLayer
)
from qgis.gui import QgsMapTool, QgsMapCanvasItem


# Modos del map tool
MODE_SWIPE = 'swipe'
MODE_MAGNIFIER = 'magnifier'

# Direcciones del swipe
DIR_HORIZONTAL = 'horizontal'
DIR_VERTICAL = 'vertical'


class SwipeCanvasItem(QgsMapCanvasItem):
    """
    Item de canvas que renderiza la capa swipe encima del mapa base.

    Soporta dos modos de visualización:
    - 'swipe': clipping rectangular según la posición del divisor
    - 'magnifier': clipping circular siguiendo al cursor

    Aplica transparencia (opacity) configurable.
    """

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.swipe_layer = None
        self.mode = MODE_SWIPE
        self.direction = DIR_HORIZONTAL
        self.swipe_position = 0.5
        self.opacity = 1.0

        # Modo lupa
        self.cursor_pos = QPointF(0, 0)
        self.magnifier_radius = 150

        # Cache
        self.cached_image = None
        self.cached_extent = None
        self.cached_size = None

        self.setZValue(1000)

    # ---- Setters ----
    def set_layer(self, layer):
        self.swipe_layer = layer
        self.invalidate_cache()
        self.update()

    def set_mode(self, mode):
        self.mode = mode
        self.update()

    def set_direction(self, direction):
        self.direction = direction
        self.update()

    def set_position(self, position):
        self.swipe_position = max(0.0, min(1.0, position))
        self.update()

    def set_opacity_value(self, opacity):
        """0.0 (transparente) a 1.0 (opaco)."""
        self.opacity = max(0.0, min(1.0, opacity))
        self.update()

    def set_cursor_pos(self, pos):
        """Posición del cursor para el modo lupa."""
        self.cursor_pos = QPointF(pos)
        self.update()

    def set_magnifier_radius(self, radius):
        self.magnifier_radius = max(30, min(500, radius))
        self.update()

    def invalidate_cache(self):
        self.cached_image = None
        self.cached_extent = None
        self.cached_size = None

    # ---- Render ----
    def _render_layer_to_image(self):
        """Renderiza la capa swipe a una QImage. Cachea el resultado."""
        if not self.swipe_layer:
            return None

        canvas_size = self.canvas.size()
        canvas_extent = self.canvas.extent()

        if (self.cached_image is not None
                and self.cached_size == canvas_size
                and self.cached_extent == canvas_extent):
            return self.cached_image

        ms = QgsMapSettings()
        ms.setLayers([self.swipe_layer])
        ms.setBackgroundColor(QColor(0, 0, 0, 0))
        ms.setOutputSize(canvas_size)
        ms.setExtent(canvas_extent)
        ms.setDestinationCrs(self.canvas.mapSettings().destinationCrs())
        ms.setOutputDpi(self.canvas.mapSettings().outputDpi())

        image = QImage(canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        try:
            job = QgsMapRendererCustomPainterJob(ms, painter)
            job.start()
            job.waitForFinished()
        finally:
            painter.end()

        self.cached_image = image
        self.cached_extent = QgsRectangle(canvas_extent)
        self.cached_size = QSize(canvas_size)

        return image

    def boundingRect(self):
        return QRectF(0, 0, self.canvas.width(), self.canvas.height())

    def updatePosition(self):
        self.prepareGeometryChange()
        self.setPos(0, 0)
        self.invalidate_cache()

    def paint(self, painter, option=None, widget=None):
        if not self.swipe_layer:
            return

        image = self._render_layer_to_image()
        if image is None:
            return

        w = self.canvas.width()
        h = self.canvas.height()

        painter.save()
        painter.setOpacity(self.opacity)

        if self.mode == MODE_SWIPE:
            # Clipping rectangular
            if self.direction == DIR_HORIZONTAL:
                clip_w = int(w * self.swipe_position)
                clip_rect = QRectF(0, 0, clip_w, h)
            else:
                clip_h = int(h * self.swipe_position)
                clip_rect = QRectF(0, 0, w, clip_h)
            painter.setClipRect(clip_rect)
            painter.drawImage(0, 0, image)

        elif self.mode == MODE_MAGNIFIER:
            # Clipping circular siguiendo al cursor
            path = QPainterPath()
            path.addEllipse(self.cursor_pos, self.magnifier_radius,
                            self.magnifier_radius)
            painter.setClipPath(path)
            painter.drawImage(0, 0, image)

        painter.restore()


class SwipeDivider(QgsMapCanvasItem):
    """
    Item que dibuja la barra divisora (modo swipe) o el círculo de la lupa
    (modo magnifier), siempre encima del SwipeCanvasItem.
    """

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.mode = MODE_SWIPE
        self.direction = DIR_HORIZONTAL
        self.swipe_position = 0.5
        self.cursor_pos = QPointF(0, 0)
        self.magnifier_radius = 150
        self.is_hovered = False
        self.is_dragging = False
        self.setZValue(1001)

    def set_mode(self, mode):
        self.mode = mode
        self.update()

    def set_direction(self, direction):
        self.direction = direction
        self.update()

    def set_position(self, position):
        self.swipe_position = max(0.0, min(1.0, position))
        self.update()

    def set_cursor_pos(self, pos):
        self.cursor_pos = QPointF(pos)
        self.update()

    def set_magnifier_radius(self, radius):
        self.magnifier_radius = max(30, min(500, radius))
        self.update()

    def set_hovered(self, hovered):
        self.is_hovered = hovered
        self.update()

    def set_dragging(self, dragging):
        self.is_dragging = dragging
        self.update()

    def boundingRect(self):
        return QRectF(0, 0, self.canvas.width(), self.canvas.height())

    def updatePosition(self):
        self.prepareGeometryChange()
        self.setPos(0, 0)

    def get_divider_line(self):
        w = self.canvas.width()
        h = self.canvas.height()
        if self.direction == DIR_HORIZONTAL:
            x = int(w * self.swipe_position)
            return (x, 0, x, h)
        else:
            y = int(h * self.swipe_position)
            return (0, y, w, y)

    def get_handle_rect(self):
        w = self.canvas.width()
        h = self.canvas.height()
        handle_long = 60
        handle_short = 24
        if self.direction == DIR_HORIZONTAL:
            x = int(w * self.swipe_position)
            cy = h // 2
            return QRect(x - handle_short // 2, cy - handle_long // 2,
                         handle_short, handle_long)
        else:
            y = int(h * self.swipe_position)
            cx = w // 2
            return QRect(cx - handle_long // 2, y - handle_short // 2,
                         handle_long, handle_short)

    def paint(self, painter, option=None, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.mode == MODE_SWIPE:
            self._paint_divider(painter)
        elif self.mode == MODE_MAGNIFIER:
            self._paint_magnifier(painter)

    def _paint_divider(self, painter):
        """Dibuja la barra divisora del modo swipe."""
        x1, y1, x2, y2 = self.get_divider_line()

        # Sombra
        pen_shadow = QPen(QColor(0, 0, 0, 180), 4)
        pen_shadow.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen_shadow)
        painter.drawLine(x1, y1, x2, y2)

        # Línea blanca
        line_color = QColor(255, 255, 255, 255)
        if self.is_dragging:
            line_color = QColor(120, 200, 255, 255)
        elif self.is_hovered:
            line_color = QColor(200, 230, 255, 255)
        pen_main = QPen(line_color, 2)
        pen_main.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen_main)
        painter.drawLine(x1, y1, x2, y2)

        # Handle
        handle_rect = self.get_handle_rect()
        shadow_rect = handle_rect.adjusted(2, 2, 2, 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.drawRoundedRect(shadow_rect, 4, 4)

        handle_fill = QColor(245, 245, 245)
        if self.is_dragging:
            handle_fill = QColor(120, 200, 255)
        elif self.is_hovered:
            handle_fill = QColor(220, 235, 250)

        painter.setPen(QPen(QColor(60, 60, 60), 1.5))
        painter.setBrush(QBrush(handle_fill))
        painter.drawRoundedRect(handle_rect, 4, 4)

        self._draw_arrows(painter, handle_rect)

    def _paint_magnifier(self, painter):
        """Dibuja el círculo de la lupa estilo ArcGIS Pro."""
        center = self.cursor_pos
        radius = self.magnifier_radius

        # Sombra exterior (suave)
        shadow_color = QColor(0, 0, 0, 100)
        painter.setPen(QPen(shadow_color, 6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius + 1, radius + 1)

        # Borde principal blanco
        border_color = QColor(255, 255, 255, 255)
        if self.is_dragging:
            border_color = QColor(120, 200, 255, 255)
        elif self.is_hovered:
            border_color = QColor(200, 230, 255, 255)

        painter.setPen(QPen(border_color, 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)

        # Borde interno oscuro para contraste
        painter.setPen(QPen(QColor(40, 40, 40, 200), 1))
        painter.drawEllipse(center, radius - 1, radius - 1)

        # Cruz central pequeña
        cx, cy = int(center.x()), int(center.y())
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        painter.drawLine(cx - 6, cy, cx + 6, cy)
        painter.drawLine(cx, cy - 6, cx, cy + 6)
        painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
        painter.drawLine(cx - 6, cy, cx + 6, cy)
        painter.drawLine(cx, cy - 6, cx, cy + 6)

    def _draw_arrows(self, painter, rect):
        painter.setPen(QPen(QColor(40, 40, 40), 2))
        painter.setBrush(QBrush(QColor(40, 40, 40)))
        cx = rect.center().x()
        cy = rect.center().y()
        arrow_size = 5

        if self.direction == DIR_HORIZONTAL:
            painter.drawPolygon(QPolygon([
                QPoint(cx - 8, cy),
                QPoint(cx - 8 + arrow_size, cy - arrow_size),
                QPoint(cx - 8 + arrow_size, cy + arrow_size)
            ]))
            painter.drawPolygon(QPolygon([
                QPoint(cx + 8, cy),
                QPoint(cx + 8 - arrow_size, cy - arrow_size),
                QPoint(cx + 8 - arrow_size, cy + arrow_size)
            ]))
        else:
            painter.drawPolygon(QPolygon([
                QPoint(cx, cy - 8),
                QPoint(cx - arrow_size, cy - 8 + arrow_size),
                QPoint(cx + arrow_size, cy - 8 + arrow_size)
            ]))
            painter.drawPolygon(QPolygon([
                QPoint(cx, cy + 8),
                QPoint(cx - arrow_size, cy + 8 - arrow_size),
                QPoint(cx + arrow_size, cy + 8 - arrow_size)
            ]))

    def is_point_on_divider(self, point, tolerance=8):
        w = self.canvas.width()
        h = self.canvas.height()
        if self.direction == DIR_HORIZONTAL:
            divider_x = int(w * self.swipe_position)
            return abs(point.x() - divider_x) <= tolerance
        else:
            divider_y = int(h * self.swipe_position)
            return abs(point.y() - divider_y) <= tolerance


class SwipeMapTool(QgsMapTool):
    """Map tool principal con soporte para swipe y lupa."""

    positionChanged = pyqtSignal(float)
    radiusChanged = pyqtSignal(int)
    exportRequested = pyqtSignal()

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.canvas = canvas
        self.iface = iface

        self.swipe_layer = None
        self.mode = MODE_SWIPE
        self.direction = DIR_HORIZONTAL
        self.swipe_position = 0.5
        self.opacity = 1.0
        self.magnifier_radius = 150

        self.swipe_item = None
        self.divider_item = None

        self.is_dragging = False
        self.is_hovering_divider = False
        self.last_cursor_pos = QPoint(0, 0)

        self.canvas.extentsChanged.connect(self._on_extents_changed)

    # ---- Setters / API pública ----
    def set_layer(self, layer):
        self.swipe_layer = layer
        if self.swipe_item:
            self.swipe_item.set_layer(layer)
        self.canvas.refresh()

    def set_mode(self, mode):
        self.mode = mode
        if self.swipe_item:
            self.swipe_item.set_mode(mode)
        if self.divider_item:
            self.divider_item.set_mode(mode)
        self._update_cursor()
        self.canvas.refresh()

    def set_direction(self, direction):
        self.direction = direction
        if self.swipe_item:
            self.swipe_item.set_direction(direction)
        if self.divider_item:
            self.divider_item.set_direction(direction)
        self._update_cursor()
        self.canvas.refresh()

    def set_opacity_value(self, opacity):
        self.opacity = opacity
        if self.swipe_item:
            self.swipe_item.set_opacity_value(opacity)

    def set_magnifier_radius(self, radius):
        self.magnifier_radius = radius
        if self.swipe_item:
            self.swipe_item.set_magnifier_radius(radius)
        if self.divider_item:
            self.divider_item.set_magnifier_radius(radius)

    def get_rendered_swipe_image(self):
        """Devuelve la imagen renderizada de la capa swipe (para exportar)."""
        if self.swipe_item:
            return self.swipe_item._render_layer_to_image()
        return None

    # ---- Eventos ----
    def _on_extents_changed(self):
        if self.swipe_item:
            self.swipe_item.invalidate_cache()

    def _update_cursor(self):
        if self.mode == MODE_MAGNIFIER:
            self.canvas.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            return

        if self.is_dragging or self.is_hovering_divider:
            if self.direction == DIR_HORIZONTAL:
                self.canvas.setCursor(QCursor(Qt.CursorShape.SplitHCursor))
            else:
                self.canvas.setCursor(QCursor(Qt.CursorShape.SplitVCursor))
        else:
            self.canvas.setCursor(self._build_swipe_cursor())

    def _build_swipe_cursor(self):
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(0, 0, 0), 2))
        p.setBrush(QBrush(QColor(255, 255, 255)))

        if self.direction == DIR_HORIZONTAL:
            p.drawLine(6, 16, 26, 16)
            p.drawPolygon(QPolygon([
                QPoint(6, 16), QPoint(11, 11), QPoint(11, 21)
            ]))
            p.drawPolygon(QPolygon([
                QPoint(26, 16), QPoint(21, 11), QPoint(21, 21)
            ]))
        else:
            p.drawLine(16, 6, 16, 26)
            p.drawPolygon(QPolygon([
                QPoint(16, 6), QPoint(11, 11), QPoint(21, 11)
            ]))
            p.drawPolygon(QPolygon([
                QPoint(16, 26), QPoint(11, 21), QPoint(21, 21)
            ]))
        p.end()
        return QCursor(pix, 16, 16)

    def activate(self):
        super().activate()

        if self.swipe_item is None:
            self.swipe_item = SwipeCanvasItem(self.canvas)
            self.swipe_item.set_mode(self.mode)
            self.swipe_item.set_direction(self.direction)
            self.swipe_item.set_position(self.swipe_position)
            self.swipe_item.set_opacity_value(self.opacity)
            self.swipe_item.set_magnifier_radius(self.magnifier_radius)
            if self.swipe_layer:
                self.swipe_item.set_layer(self.swipe_layer)

        if self.divider_item is None:
            self.divider_item = SwipeDivider(self.canvas)
            self.divider_item.set_mode(self.mode)
            self.divider_item.set_direction(self.direction)
            self.divider_item.set_position(self.swipe_position)
            self.divider_item.set_magnifier_radius(self.magnifier_radius)

        # Foco para recibir eventos de teclado
        self.canvas.setFocus()

        self._update_cursor()
        self.canvas.refresh()

    def deactivate(self):
        if self.swipe_item:
            try:
                self.canvas.scene().removeItem(self.swipe_item)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.swipe_item = None
        if self.divider_item:
            try:
                self.canvas.scene().removeItem(self.divider_item)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.divider_item = None
        self.canvas.unsetCursor()
        self.canvas.refresh()
        super().deactivate()

    def canvasPressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.mode == MODE_MAGNIFIER:
            # En lupa, el press simplemente activa drag para mover
            self.is_dragging = True
            if self.divider_item:
                self.divider_item.set_dragging(True)
            return

        if self.divider_item and self.divider_item.is_point_on_divider(event.pos()):
            self.is_dragging = True
            self.divider_item.set_dragging(True)
            self._update_cursor()
        else:
            self._update_position_from_point(event.pos())

    def canvasMoveEvent(self, event):
        pos = event.pos()
        self.last_cursor_pos = pos

        if self.mode == MODE_MAGNIFIER:
            # La lupa siempre sigue al cursor
            if self.swipe_item:
                self.swipe_item.set_cursor_pos(pos)
            if self.divider_item:
                self.divider_item.set_cursor_pos(pos)
            return

        if self.is_dragging:
            self._update_position_from_point(pos)
        else:
            on_divider = (self.divider_item is not None
                          and self.divider_item.is_point_on_divider(pos))
            if on_divider != self.is_hovering_divider:
                self.is_hovering_divider = on_divider
                if self.divider_item:
                    self.divider_item.set_hovered(on_divider)
                self._update_cursor()

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.is_dragging:
            self.is_dragging = False
            if self.divider_item:
                self.divider_item.set_dragging(False)
            self._update_cursor()

    def keyPressEvent(self, event):
        """Atajos de teclado."""
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+S: exportar
        if key == Qt.Key.Key_S and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.exportRequested.emit()
            event.accept()
            return

        if self.mode == MODE_SWIPE:
            step = 0.05 if modifiers & Qt.KeyboardModifier.ShiftModifier else 0.01

            if self.direction == DIR_HORIZONTAL:
                if key == Qt.Key.Key_Left:
                    self._set_position(self.swipe_position - step)
                    event.accept()
                    return
                elif key == Qt.Key.Key_Right:
                    self._set_position(self.swipe_position + step)
                    event.accept()
                    return
            else:
                if key == Qt.Key.Key_Up:
                    self._set_position(self.swipe_position - step)
                    event.accept()
                    return
                elif key == Qt.Key.Key_Down:
                    self._set_position(self.swipe_position + step)
                    event.accept()
                    return

        elif self.mode == MODE_MAGNIFIER:
            # +/- ajustan el radio de la lupa
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                new_radius = self.magnifier_radius + 20
                self.set_magnifier_radius(new_radius)
                self.radiusChanged.emit(self.magnifier_radius)
                self.canvas.refresh()
                event.accept()
                return
            elif key == Qt.Key.Key_Minus:
                new_radius = self.magnifier_radius - 20
                self.set_magnifier_radius(new_radius)
                self.radiusChanged.emit(self.magnifier_radius)
                self.canvas.refresh()
                event.accept()
                return

    def _set_position(self, position):
        self.swipe_position = max(0.0, min(1.0, position))
        if self.swipe_item:
            self.swipe_item.set_position(self.swipe_position)
        if self.divider_item:
            self.divider_item.set_position(self.swipe_position)
        self.positionChanged.emit(self.swipe_position)

    def _update_position_from_point(self, point):
        w = self.canvas.width()
        h = self.canvas.height()
        if self.direction == DIR_HORIZONTAL:
            pos = point.x() / float(w) if w > 0 else 0.5
        else:
            pos = point.y() / float(h) if h > 0 else 0.5
        self._set_position(pos)

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return False
