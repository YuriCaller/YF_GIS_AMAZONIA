# -*- coding: utf-8 -*-
"""
Go-To Tool — Navega a coordenadas, busca lugares y guarda bookmarks.

Replica e integra la funcionalidad "Go To XY" de ArcGIS Pro:
- Entrada por campos separados (DD/DMS/UTM/MGRS)
- Auto-detección de zona UTM desde CRS del proyecto
- Pegado inteligente directo en campos (Excel/WhatsApp)
- Pegado de múltiples coordenadas para crear N markers de una vez
- Markers como gráficos efímeros (no ensucian la TOC)
- Destello animado al llegar (estilo ArcGIS Pro)
- Geocoder Nominatim (búsqueda por nombre)
- Bookmarks persistentes

Integrado en YF GIS Amazonia Tools v2.0.
"""

import logging
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeySequence
try:
    from qgis.PyQt.QtGui import QShortcut       # Qt6: QShortcut vive en QtGui
except ImportError:
    from qgis.PyQt.QtWidgets import QShortcut   # Qt5: QShortcut vive en QtWidgets
from qgis.PyQt.QtWidgets import QMessageBox

from qgis.core import (
    QgsProject, QgsPointXY, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsRectangle, Qgis
)

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Go-To Tool entry point — conforms to YF GIS Amazonia contract."""

    TOOL_NAME = "Go-To"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self.canvas = iface.mapCanvas()
        self.panel = None
        self.marker_manager = None
        self.geocoder = None
        self.bookmarks = None
        self.shortcut = None
        self._signals_connected = False
        self._crs_listener_connected = False

    def run(self):
        """Toggle panel visibility."""
        if self.panel is not None and self.panel.isVisible():
            self._deactivate()
        else:
            self._activate()

    def unload(self):
        """Called on plugin shutdown."""
        log_info("Descargando Go-To Tool")

        try:
            if self._crs_listener_connected:
                QgsProject.instance().crsChanged.disconnect(self._on_project_crs_changed)
                self._crs_listener_connected = False
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)

        if self.marker_manager:
            try:
                self.marker_manager.clear_all()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.marker_manager = None

        if self.geocoder:
            try:
                self.geocoder.cancel()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.geocoder = None

        if self.panel is not None:
            try:
                self.iface.removeDockWidget(self.panel)
                self.panel.deleteLater()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.panel = None

        if self.shortcut is not None:
            try:
                self.shortcut.setParent(None)
                self.shortcut.deleteLater()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
            self.shortcut = None

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def _activate(self):
        """Lazy-init panel, managers, and shortcuts on first run."""
        from .panel import GoToPanel
        from .flash_marker import MarkerManager
        from .geocoder import NominatimGeocoder
        from .bookmarks import BookmarksManager

        if self.marker_manager is None:
            self.marker_manager = MarkerManager(self.canvas, self.iface)
            self.geocoder = NominatimGeocoder()
            self.bookmarks = BookmarksManager()

        if self.panel is None:
            self.panel = GoToPanel(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.panel)
            self._connect_signals()
            self._refresh_bookmarks()
            self._refresh_markers()

        # Listen to project CRS changes (only once)
        if not self._crs_listener_connected:
            try:
                QgsProject.instance().crsChanged.connect(self._on_project_crs_changed)
                self._crs_listener_connected = True
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)

        # Ctrl+G shortcut (only create once)
        if self.shortcut is None:
            self.shortcut = QShortcut(
                QKeySequence("Ctrl+G"), self.iface.mainWindow()
            )
            self.shortcut.activated.connect(self._on_shortcut_activated)

        self.panel.show()
        self.panel.raise_()
        self.panel.notify_crs_changed()
        log_info("Go-To Tool activado")

    def _deactivate(self):
        if self.panel is not None:
            self.panel.hide()

    def _on_shortcut_activated(self):
        if self.panel is None or not self.panel.isVisible():
            self._activate()
        self.panel.focus_coord_input()

    def _on_project_crs_changed(self):
        if self.panel is not None:
            self.panel.notify_crs_changed()

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        if self._signals_connected:
            return
        self.panel.goToRequested.connect(self._go_to)
        self.panel.multiCoordsRequested.connect(self._on_multi_coords)
        self.panel.searchRequested.connect(self._on_search)
        self.panel.bookmarkAdd.connect(self._add_bookmark)
        self.panel.bookmarkRemove.connect(self._remove_bookmark)
        self.panel.bookmarkGoTo.connect(self._goto_bookmark)
        self.panel.markerGoTo.connect(self._goto_marker)
        self.panel.markerRemove.connect(self._remove_marker)
        self.panel.markersClearAll.connect(self._clear_markers)
        self.panel.markersToLayer.connect(self._markers_to_layer)

        self.geocoder.resultsReady.connect(self.panel.set_search_results)
        self.geocoder.searchError.connect(self.panel.set_search_error)
        self.bookmarks.bookmarksChanged.connect(self._refresh_bookmarks)
        self.marker_manager.markersChanged.connect(self._refresh_markers)

        self._signals_connected = True

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _go_to(self, lat, lon, original_text):
        try:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
            transform = QgsCoordinateTransform(
                wgs84, canvas_crs, QgsProject.instance()
            )
            canvas_point = transform.transform(QgsPointXY(lon, lat))

            current_extent = self.canvas.extent()
            scale = self.panel.get_zoom_scale()

            if scale is None:
                w = current_extent.width()
                h = current_extent.height()
                new_extent = QgsRectangle(
                    canvas_point.x() - w / 2, canvas_point.y() - h / 2,
                    canvas_point.x() + w / 2, canvas_point.y() + h / 2
                )
                self.canvas.setExtent(new_extent)
            else:
                self.canvas.setCenter(canvas_point)
                self.canvas.zoomScale(scale)

            self.canvas.refresh()

            self.marker_manager.add_marker(
                lat, lon, label=original_text, original=original_text, flash=True
            )

            self.iface.messageBar().pushMessage(
                "Go-To Tool",
                f"Navegado a {lat:.6f}, {lon:.6f}",
                level=Qgis.MessageLevel.Success, duration=3
            )
        except Exception as e:
            log_error(f"Error navegando: {e}")
            QMessageBox.warning(
                self.iface.mainWindow(), "Error",
                f"No se pudo navegar al punto:\n{e}"
            )

    def _on_search(self, query):
        country = self.panel.get_country_code()
        self.geocoder.search(query, country_codes=country, limit=12)

    def _on_multi_coords(self, coords_list):
        if not coords_list:
            return
        try:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
            transform = QgsCoordinateTransform(
                wgs84, canvas_crs, QgsProject.instance()
            )

            xs, ys = [], []
            for lat, lon, label in coords_list:
                self.marker_manager.add_marker(
                    lat, lon, label=label, original=label, flash=False
                )
                pt = transform.transform(QgsPointXY(lon, lat))
                xs.append(pt.x())
                ys.append(pt.y())

            if xs and ys:
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                dx = max_x - min_x
                dy = max_y - min_y
                margin = max(dx, dy) * 0.2
                if margin < 100:
                    margin = 100
                extent = QgsRectangle(
                    min_x - margin, min_y - margin,
                    max_x + margin, max_y + margin
                )
                self.canvas.setExtent(extent)
                self.canvas.refresh()

            self.iface.messageBar().pushMessage(
                "Go-To Tool",
                f"{len(coords_list)} markers creados desde texto pegado.",
                level=Qgis.MessageLevel.Success, duration=4
            )
        except Exception as e:
            log_error(f"Error creando markers múltiples: {e}")
            QMessageBox.warning(
                self.iface.mainWindow(), "Error",
                f"No se pudieron crear los markers:\n{e}"
            )

    def _refresh_bookmarks(self):
        if self.panel:
            self.panel.set_bookmarks(self.bookmarks.get_all())

    def _add_bookmark(self, name, lat, lon, note):
        if self.bookmarks.add(name, lat, lon, note):
            self.iface.messageBar().pushMessage(
                "Go-To Tool",
                f"Bookmark '{name}' guardado",
                level=Qgis.MessageLevel.Success, duration=2
            )

    def _remove_bookmark(self, index):
        self.bookmarks.remove(index)

    def _goto_bookmark(self, index):
        bm = self.bookmarks.get(index)
        if bm:
            self._go_to(bm['lat'], bm['lon'], bm['name'])

    def _refresh_markers(self):
        if self.panel:
            self.panel.set_markers(self.marker_manager.get_markers())

    def _goto_marker(self, index):
        self.marker_manager.zoom_to_marker(index)

    def _remove_marker(self, index):
        self.marker_manager.remove_marker(index)

    def _clear_markers(self):
        self.marker_manager.clear_all()

    def _markers_to_layer(self, as_memory, file_path):
        try:
            layer = self.marker_manager.to_layer(
                layer_name="Go-To Markers",
                as_memory=as_memory,
                file_path=file_path if not as_memory else None
            )
            if layer:
                self.iface.messageBar().pushMessage(
                    "Go-To Tool",
                    f"Markers convertidos a capa: {layer.name()}",
                    level=Qgis.MessageLevel.Success, duration=4
                )
        except Exception as e:
            log_error(f"Error: {e}")
            QMessageBox.critical(self.iface.mainWindow(), "Error", str(e))
