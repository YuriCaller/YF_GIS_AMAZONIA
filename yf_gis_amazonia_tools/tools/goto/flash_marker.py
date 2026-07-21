# -*- coding: utf-8 -*-
"""
YF Go-To Tool - Flash Marker
Marker animado estilo ArcGIS Pro: destello expansivo + marker persistente.

El destello consiste en 3 anillos que se expanden y se desvanecen,
similar al efecto "Pan To" + "Flash" de ArcGIS Pro.

El marker persistente queda visible hasta que se elimina manualmente.

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import logging
from qgis.PyQt.QtCore import Qt, QTimer, QObject, pyqtSignal
from ...core.qt_compat import QVariant_Int, QVariant_Double, QVariant_String
from qgis.PyQt.QtGui import QColor, QFont

from qgis.core import (
    QgsPointXY, QgsGeometry, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
)
from qgis.gui import QgsRubberBand, QgsVertexMarker, QgsMapCanvasItem


# ============================================================
# Flash animation (pulso expansivo)
# ============================================================

class FlashAnimation(QObject):
    """
    Genera un destello expansivo en una posición específica.
    Crea anillos QgsRubberBand que crecen y se desvanecen.
    """

    finished = pyqtSignal()

    def __init__(self, canvas, point_xy, color=None, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.point = point_xy
        self.color = color or QColor(255, 50, 50)

        # Parámetros de animación
        self.num_pulses = 3       # Cuántos anillos
        self.pulse_steps = 10     # Frames por pulso
        self.pulse_interval = 40  # ms entre frames
        self.max_radius = 25      # Radio máximo del anillo (en píxeles canvas)

        self.current_pulse = 0
        self.current_step = 0
        self.rings = []  # rubber bands activos

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def start(self):
        """Inicia la animación."""
        self.timer.start(self.pulse_interval)

    def stop(self):
        """Detiene y limpia."""
        self.timer.stop()
        self._cleanup_rings()
        self.finished.emit()

    def _tick(self):
        # Lanzar un nuevo pulso cada `pulse_steps`
        if self.current_step == 0:
            self._spawn_ring()

        # Actualizar todos los anillos activos
        for ring_data in self.rings:
            ring_data['step'] += 1

        # Renderizar
        self._update_rings()

        # Limpiar anillos terminados
        self.rings = [r for r in self.rings if r['step'] <= self.pulse_steps]

        self.current_step += 1
        if self.current_step >= self.pulse_steps:
            self.current_step = 0
            self.current_pulse += 1

        # Terminar cuando se completaron todos los pulsos y no quedan anillos
        if self.current_pulse >= self.num_pulses and not self.rings:
            self.stop()

    def _spawn_ring(self):
        """Crea un nuevo anillo en la posición."""
        rb = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PointGeometry)
        rb.setIcon(QgsRubberBand.IconType.ICON_CIRCLE)
        rb.setIconSize(2)
        rb.setColor(self.color)
        rb.setWidth(3)
        rb.setToGeometry(QgsGeometry.fromPointXY(self.point), None)
        self.rings.append({'rb': rb, 'step': 0})

    def _update_rings(self):
        """Actualiza tamaño y opacidad de los anillos."""
        for ring_data in self.rings:
            step = ring_data['step']
            progress = step / self.pulse_steps  # 0.0 a 1.0
            radius = int(2 + progress * self.max_radius)

            rb = ring_data['rb']
            rb.setIconSize(radius)

            # Opacidad disminuye
            alpha = int(255 * (1.0 - progress))
            c = QColor(self.color)
            c.setAlpha(alpha)
            rb.setColor(c)

    def _cleanup_rings(self):
        """Elimina todos los rubber bands."""
        for ring_data in self.rings:
            try:
                self.canvas.scene().removeItem(ring_data['rb'])
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
        self.rings = []


# ============================================================
# Persistent Marker (graphic estilo ArcGIS Pro)
# ============================================================

class PersistentMarker:
    """
    Marker persistente en el canvas, con etiqueta numérica y popup de info.
    No crea capa en la TOC. Vive como graphic en el canvas.
    """

    def __init__(self, canvas, point_xy, number=1, label=None, color=None):
        self.canvas = canvas
        self.point = QgsPointXY(point_xy)
        self.number = number
        self.label = label or ""
        self.color = color or QColor(220, 30, 30)

        # Punto principal (cross con outline)
        self.vertex_marker = QgsVertexMarker(canvas)
        self.vertex_marker.setIconType(QgsVertexMarker.IconType.ICON_DOUBLE_TRIANGLE)
        self.vertex_marker.setColor(QColor(0, 0, 0))
        self.vertex_marker.setFillColor(self.color)
        self.vertex_marker.setIconSize(14)
        self.vertex_marker.setPenWidth(2)
        self.vertex_marker.setCenter(self.point)

        # Rubber band para halo (efecto "highlight")
        self.halo = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PointGeometry)
        self.halo.setIcon(QgsRubberBand.IconType.ICON_CIRCLE)
        self.halo.setIconSize(20)
        halo_color = QColor(self.color)
        halo_color.setAlpha(60)
        self.halo.setColor(halo_color)
        self.halo.setFillColor(halo_color)
        self.halo.setWidth(2)
        self.halo.setToGeometry(QgsGeometry.fromPointXY(self.point), None)

        # Label item para el número
        self.label_item = NumberedLabelItem(canvas, self.point, str(number))

    def remove(self):
        """Elimina el marker del canvas."""
        try:
            self.canvas.scene().removeItem(self.vertex_marker)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        try:
            self.canvas.scene().removeItem(self.halo)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        try:
            self.canvas.scene().removeItem(self.label_item)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

    def hide(self):
        self.vertex_marker.hide()
        self.halo.hide()
        self.label_item.hide()

    def show(self):
        self.vertex_marker.show()
        self.halo.show()
        self.label_item.show()


# ============================================================
# Label item con número
# ============================================================

from qgis.PyQt.QtCore import QRectF, QPointF
from qgis.PyQt.QtGui import QPainter, QPen, QBrush


class NumberedLabelItem(QgsMapCanvasItem):
    """Item que dibuja un círculo con número junto al marker."""

    def __init__(self, canvas, point_xy, text):
        super().__init__(canvas)
        self.canvas = canvas
        self.map_point = QgsPointXY(point_xy)
        self.text = text
        self.setZValue(900)
        self.updatePosition()

    def updatePosition(self):
        """Convierte coordenadas de mapa a pixel."""
        screen_pt = self.toCanvasCoordinates(self.map_point)
        self.setPos(screen_pt)
        self.prepareGeometryChange()

    def boundingRect(self):
        return QRectF(-25, -45, 50, 30)

    def paint(self, painter, option=None, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Círculo de fondo con número (offset arriba-derecha del marker)
        cx, cy = 12, -25
        radius = 11

        # Sombra
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.drawEllipse(QPointF(cx + 1, cy + 1), radius, radius)

        # Círculo principal
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(QColor(220, 30, 30)))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Texto
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(
            QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
            Qt.AlignmentFlag.AlignCenter, self.text
        )


# ============================================================
# Marker Manager
# ============================================================

class MarkerManager(QObject):
    """
    Gestiona el ciclo de vida de markers en el canvas:
    - Añadir con destello animado
    - Listar
    - Eliminar individual o todos
    - Convertir todos a capa
    """

    markersChanged = pyqtSignal()

    def __init__(self, canvas, iface, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.iface = iface
        self.markers = []  # list of dicts: {marker, lat, lon, label, original}
        self._counter = 0
        self._active_flashes = []

    def add_marker(self, lat, lon, label='', original='', flash=True):
        """Añade un marker en (lat, lon) WGS84. Devuelve el dict."""
        # Transformar lat/lon WGS84 a CRS del canvas
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        src_crs = QgsCoordinateReferenceSystem('EPSG:4326')
        transform = QgsCoordinateTransform(src_crs, canvas_crs, QgsProject.instance())
        try:
            point = transform.transform(QgsPointXY(lon, lat))
        except Exception:
            point = QgsPointXY(lon, lat)

        self._counter += 1
        marker = PersistentMarker(self.canvas, point, number=self._counter, label=label)

        entry = {
            'marker': marker,
            'lat': lat,
            'lon': lon,
            'point_canvas': point,
            'number': self._counter,
            'label': label,
            'original': original,
        }
        self.markers.append(entry)

        if flash:
            self._flash_at(point)

        self.markersChanged.emit()
        return entry

    def _flash_at(self, point):
        """Lanza el destello animado en ese punto."""
        flash = FlashAnimation(self.canvas, point, color=QColor(255, 50, 50))
        self._active_flashes.append(flash)

        def _on_finished():
            try:
                self._active_flashes.remove(flash)
            except ValueError:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            flash.deleteLater()

        flash.finished.connect(_on_finished)
        flash.start()

    def remove_marker(self, index):
        """Elimina un marker por índice de la lista."""
        if 0 <= index < len(self.markers):
            entry = self.markers.pop(index)
            entry['marker'].remove()
            self.markersChanged.emit()

    def clear_all(self):
        """Elimina todos los markers."""
        for entry in self.markers:
            entry['marker'].remove()
        self.markers = []
        self._counter = 0
        # Detener animaciones activas
        for flash in list(self._active_flashes):
            flash.stop()
        self._active_flashes = []
        self.markersChanged.emit()

    def get_markers(self):
        """Retorna la lista de markers."""
        return list(self.markers)

    def zoom_to_marker(self, index):
        """Re-centra el canvas en el marker."""
        if 0 <= index < len(self.markers):
            entry = self.markers[index]
            point = entry['point_canvas']

            # Centrar y aplicar zoom
            extent = self.canvas.extent()
            w = extent.width()
            h = extent.height()
            from qgis.core import QgsRectangle
            new_extent = QgsRectangle(
                point.x() - w / 2, point.y() - h / 2,
                point.x() + w / 2, point.y() + h / 2
            )
            self.canvas.setExtent(new_extent)
            self.canvas.refresh()

            # Destello nuevamente al re-visitar
            self._flash_at(point)

    def to_layer(self, layer_name="Go-To Markers", as_memory=True, file_path=None):
        """
        Convierte todos los markers a una capa permanente.
        - as_memory=True: capa temporal en memoria
        - as_memory=False: guardar como GeoPackage en file_path
        Retorna la capa creada.
        """
        from qgis.core import (
            QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
            QgsVectorFileWriter, QgsProject, QgsWkbTypes
        )
        from qgis.PyQt.QtCore import QVariant

        if not self.markers:
            return None

        # Crear capa memoria primero
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        uri = f"Point?crs={canvas_crs.authid()}"
        layer = QgsVectorLayer(uri, layer_name, "memory")
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField("id", QVariant_Int),
            QgsField("label", QVariant_String, len=200),
            QgsField("lat", QVariant_Double),
            QgsField("lon", QVariant_Double),
            QgsField("original", QVariant_String, len=200),
        ])
        layer.updateFields()

        features = []
        for entry in self.markers:
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(entry['point_canvas']))
            f.setAttribute("id", entry['number'])
            f.setAttribute("label", entry['label'])
            f.setAttribute("lat", entry['lat'])
            f.setAttribute("lon", entry['lon'])
            f.setAttribute("original", entry['original'])
            features.append(f)
        pr.addFeatures(features)
        layer.updateExtents()

        if as_memory:
            QgsProject.instance().addMapLayer(layer)
            return layer
        else:
            # Guardar a archivo
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer_name
            transform_context = QgsProject.instance().transformContext()
            err = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer, file_path, transform_context, options
            )
            # Cargar el archivo guardado
            saved = QgsVectorLayer(file_path, layer_name, "ogr")
            if saved.isValid():
                QgsProject.instance().addMapLayer(saved)
                return saved
            return None
