# -*- coding: utf-8 -*-
"""
CogoMapTool — herramienta de mapa para digitalizar en vivo por
azimut/distancia (COGO), estilo "Traverse" de ArcGIS Pro.

Responsabilidad única: interacción con el canvas.
    - Fijar el punto de origen con un clic.
    - Dibujar en vivo (QgsRubberBand) la poligonal a medida que el
      panel (panel.py) va agregando lados.
    - Mostrar en línea punteada el "cierre pendiente" (del último
      vértice al origen) para que el usuario vea en todo momento
      qué tan lejos está de cerrar la figura.

Toda la matemática (parseo de azimut/distancia, recorrido de la
poligonal, error de cierre, compensación) vive en core/poligonal.py.
Este módulo no la duplica ni la reimplementa.

Autor: Yuri F. Caller Cordova — TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsPointXY, QgsGeometry
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker

from ...core.qt_compat import CrossCursor, DashLine, LineGeometry


class CogoMapTool(QgsMapTool):
    """Captura el clic de origen y dibuja la poligonal COGO en vivo."""

    # Emitida cuando el usuario hace clic para fijar el origen.
    # Coordenadas en el CRS del proyecto (E, N).
    origen_fijado = pyqtSignal(float, float)

    # Emitida cuando se desactiva la herramienta (p. ej. el usuario
    # activa otra herramienta de QGIS) — el panel debe reaccionar.
    herramienta_desactivada = pyqtSignal()

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.setCursor(CrossCursor)

        self._esperando_origen = False

        self._banda = QgsRubberBand(canvas, LineGeometry)
        self._banda.setColor(QColor(255, 140, 0))
        self._banda.setWidth(3)

        self._banda_cierre = QgsRubberBand(canvas, LineGeometry)
        self._banda_cierre.setColor(QColor(220, 30, 30))
        self._banda_cierre.setWidth(2)
        self._banda_cierre.setLineStyle(DashLine)

        self._marcador_origen = QgsVertexMarker(canvas)
        self._marcador_origen.setColor(QColor(0, 150, 0))
        self._marcador_origen.setIconType(QgsVertexMarker.ICON_BOX)
        self._marcador_origen.setPenWidth(3)
        self._marcador_origen.hide()

    # ------------------------------------------------------------------
    # API para el panel
    # ------------------------------------------------------------------

    def pedir_origen_por_clic(self):
        """Activa la herramienta y espera un clic en el canvas."""
        self._esperando_origen = True
        self.canvas.setMapTool(self)

    def fijar_origen_programatico(self, x, y):
        """Fija el origen sin necesidad de clic (coordenadas tecleadas)."""
        self._esperando_origen = False
        self._marcador_origen.setCenter(QgsPointXY(x, y))
        self._marcador_origen.show()

    def mostrar_vertices(self, vertices, cerrado):
        """Redibuja la poligonal en vivo.

        vertices: lista de tuplas (E, N), en el orden recorrido.
        cerrado: True si la figura ya se cerró (no se dibuja la línea
                 punteada de cierre pendiente).
        """
        self._banda.reset(LineGeometry)
        self._banda_cierre.reset(LineGeometry)
        if not vertices:
            return

        pts = [QgsPointXY(e, n) for e, n in vertices]
        if len(pts) >= 2:
            self._banda.setToGeometry(QgsGeometry.fromPolylineXY(pts), None)

        if not cerrado and len(pts) >= 1:
            self._banda_cierre.setToGeometry(
                QgsGeometry.fromPolylineXY([pts[-1], pts[0]]), None)

    def limpiar(self):
        """Borra todo lo dibujado y resetea el estado de espera de clic."""
        self._banda.reset(LineGeometry)
        self._banda_cierre.reset(LineGeometry)
        self._marcador_origen.hide()
        self._esperando_origen = False

    # ------------------------------------------------------------------
    # Eventos de QgsMapTool
    # ------------------------------------------------------------------

    def canvasPressEvent(self, event):
        if not self._esperando_origen:
            return
        punto = self.toMapCoordinates(event.pos())
        self._esperando_origen = False
        self._marcador_origen.setCenter(punto)
        self._marcador_origen.show()
        self.origen_fijado.emit(punto.x(), punto.y())

    def deactivate(self):
        super().deactivate()
        self.herramienta_desactivada.emit()
