# -*- coding: utf-8 -*-
"""
Swipe Tool — Herramienta de comparación visual entre capas.

Replica e integra la funcionalidad "Swipe" de ArcGIS Pro:
- Barra divisora arrastrable horizontal o vertical
- Modo lupa circular
- Transparencia ajustable
- Exportación PNG/PDF
- Atajos de teclado (flechas, +/-, Ctrl+S)
- Persistencia con QSettings

Soporta todos los tipos de capa: raster, vector, WMS/XYZ, mesh.

Integrado en YF GIS Amazonia Tools v2.0.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction

from ...core.base_tool import BaseTool
from ...core.logger import log_info, log_error


class Tool(BaseTool):
    """Swipe Tool entry point - conforms to YF GIS Amazonia contract."""

    TOOL_NAME = "Swipe"

    def __init__(self, iface, plugin_dir):
        super().__init__(iface, plugin_dir)
        self.canvas = iface.mapCanvas()
        self.panel = None
        self.map_tool = None
        self.previous_tool = None
        self.is_active = False
        self._signals_connected = False

    # ------------------------------------------------------------------
    # BaseTool interface
    # ------------------------------------------------------------------

    def run(self):
        """Toggle the swipe tool: show/hide the dock panel."""
        if self.panel is not None and self.panel.isVisible():
            self._deactivate()
        else:
            self._activate()

    def unload(self):
        """Called on plugin shutdown — clean up everything."""
        log_info("Descargando Swipe Tool")

        self._deactivate_map_tool()

        if self.panel is not None:
            try:
                self.iface.removeDockWidget(self.panel)
                self.panel.deleteLater()
            except Exception as e:
                log_error(f"Error removiendo panel Swipe: {e}")
            self.panel = None

        if self.map_tool is not None:
            if self.canvas.mapTool() == self.map_tool:
                self.canvas.unsetMapTool(self.map_tool)
            self.map_tool = None

        try:
            self.canvas.mapToolSet.disconnect(self._on_map_tool_set)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def _activate(self):
        """Lazy-initialize panel and map tool on first activation."""
        from .map_tool import SwipeMapTool
        from .panel import SwipePanel

        if self.map_tool is None:
            self.map_tool = SwipeMapTool(self.canvas, self.iface)
            self.map_tool.positionChanged.connect(self._on_canvas_position_changed)
            self.map_tool.radiusChanged.connect(self._on_canvas_radius_changed)
            self.map_tool.exportRequested.connect(self._on_export_requested)
            self.canvas.mapToolSet.connect(self._on_map_tool_set)

        if self.panel is None:
            self.panel = SwipePanel(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel)
            self._connect_signals()

        self.panel.show()
        self.panel.raise_()

        # If panel toggle was active before, reactivate map tool
        if self.panel.is_active():
            layer = self.panel.get_selected_layer()
            if layer:
                self.map_tool.set_layer(layer)
                self._activate_map_tool()

        log_info("Swipe Tool activado")

    def _deactivate(self):
        """Hide the panel and deactivate the map tool."""
        self._deactivate_map_tool()
        if self.panel is not None:
            self.panel.set_active(False)
            self.panel.hide()
        self.is_active = False

    def _activate_map_tool(self):
        if self.canvas.mapTool() != self.map_tool:
            self.previous_tool = self.canvas.mapTool()
            self.canvas.setMapTool(self.map_tool)
        self.is_active = True

    def _deactivate_map_tool(self):
        if self.map_tool and self.canvas.mapTool() == self.map_tool:
            if self.previous_tool is not None:
                self.canvas.setMapTool(self.previous_tool)
            else:
                self.canvas.unsetMapTool(self.map_tool)
        self.is_active = False

    def _on_map_tool_set(self, new_tool, old_tool):
        """When user switches to another map tool, sync panel state."""
        if new_tool != self.map_tool and self.panel is not None:
            if self.panel.is_active():
                self.panel.blockSignals(True)
                self.panel.set_active(False)
                self.panel.blockSignals(False)
            self.is_active = False

    # ------------------------------------------------------------------
    # Panel signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self):
        """Connect panel signals to handlers (only once)."""
        if self._signals_connected:
            return
        self.panel.layerChanged.connect(self._on_layer_changed)
        self.panel.modeChanged.connect(self._on_mode_changed)
        self.panel.directionChanged.connect(self._on_direction_changed)
        self.panel.activationToggled.connect(self._on_activation_toggled)
        self.panel.positionChanged.connect(self._on_position_changed)
        self.panel.opacityChanged.connect(self._on_opacity_changed)
        self.panel.radiusChanged.connect(self._on_radius_changed)
        self.panel.swapRequested.connect(self._on_swap_requested)
        self.panel.exportRequested.connect(self._on_export_requested)
        self._signals_connected = True

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_layer_changed(self, layer):
        if self.map_tool:
            self.map_tool.set_layer(layer)

    def _on_mode_changed(self, mode):
        if self.map_tool:
            self.map_tool.set_mode(mode)

    def _on_direction_changed(self, direction):
        if self.map_tool:
            self.map_tool.set_direction(direction)

    def _on_activation_toggled(self, active):
        from qgis.core import Qgis
        if active:
            layer = self.panel.get_selected_layer()
            if layer is None:
                self.iface.messageBar().pushMessage(
                    "Swipe Tool",
                    "Selecciona una capa antes de activar el swipe.",
                    level=Qgis.Warning, duration=4
                )
                self.panel.set_active(False)
                return
            self.map_tool.set_layer(layer)
            self._activate_map_tool()
        else:
            self._deactivate_map_tool()

    def _on_position_changed(self, proportion):
        if self.map_tool:
            self.map_tool.swipe_position = proportion
            if self.map_tool.swipe_item:
                self.map_tool.swipe_item.set_position(proportion)
            if self.map_tool.divider_item:
                self.map_tool.divider_item.set_position(proportion)
            self.canvas.refresh()

    def _on_opacity_changed(self, proportion):
        if self.map_tool:
            self.map_tool.set_opacity_value(proportion)
            self.canvas.refresh()

    def _on_radius_changed(self, radius):
        if self.map_tool:
            self.map_tool.set_magnifier_radius(radius)
            self.canvas.refresh()

    def _on_swap_requested(self):
        from qgis.core import Qgis
        if self.panel:
            self.panel.swap_to_next_layer()
            self.iface.messageBar().pushMessage(
                "Swipe Tool",
                "Capa cambiada a la siguiente del proyecto.",
                level=Qgis.Info, duration=2
            )

    def _on_canvas_position_changed(self, proportion):
        if self.panel is not None:
            self.panel.set_position_silent(proportion)

    def _on_canvas_radius_changed(self, radius):
        if self.panel is not None:
            self.panel.set_radius_silent(radius)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _on_export_requested(self):
        """Export composite view to PNG/JPG/PDF."""
        import os
        from qgis.PyQt.QtCore import QSettings
        from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
        from qgis.core import Qgis

        if not self.is_active or self.map_tool is None:
            self.iface.messageBar().pushMessage(
                "Swipe Tool",
                "Activa el swipe antes de exportar.",
                level=Qgis.Warning, duration=3
            )
            return

        if self.panel is None or self.panel.get_selected_layer() is None:
            self.iface.messageBar().pushMessage(
                "Swipe Tool",
                "Selecciona una capa primero.",
                level=Qgis.Warning, duration=3
            )
            return

        last_dir = QSettings().value("yf_swipe/last_export_dir", "")
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.iface.mainWindow(),
            "Exportar vista comparativa",
            last_dir,
            "Imagen PNG (*.png);;Documento PDF (*.pdf);;Imagen JPEG (*.jpg)"
        )
        if not file_path:
            return

        ext_map = {
            "Imagen PNG (*.png)": ".png",
            "Documento PDF (*.pdf)": ".pdf",
            "Imagen JPEG (*.jpg)": ".jpg",
        }
        expected_ext = ext_map.get(selected_filter, ".png")
        if not file_path.lower().endswith(expected_ext):
            file_path += expected_ext

        QSettings().setValue("yf_swipe/last_export_dir", os.path.dirname(file_path))

        try:
            if file_path.lower().endswith(".pdf"):
                self._export_to_pdf(file_path)
            else:
                self._export_to_image(file_path)

            self.iface.messageBar().pushMessage(
                "Swipe Tool",
                f"Exportado: {os.path.basename(file_path)}",
                level=Qgis.Success, duration=4
            )
        except Exception as e:
            log_error(f"Error al exportar swipe: {e}")
            QMessageBox.critical(
                self.iface.mainWindow(), "Error de exportación", str(e)
            )

    def _render_composite_image(self):
        """Render composite of base layers + swipe layer with clipping."""
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QImage, QPainter, QColor
        from qgis.core import (
            QgsMapSettings, QgsMapRendererCustomPainterJob
        )
        from .map_tool import MODE_SWIPE, DIR_HORIZONTAL

        size = self.canvas.size()
        extent = self.canvas.extent()
        dpi = self.canvas.mapSettings().outputDpi()
        crs = self.canvas.mapSettings().destinationCrs()

        final = QImage(size, QImage.Format_ARGB32_Premultiplied)
        bg_color = self.canvas.canvasColor()
        final.fill(bg_color)

        swipe_layer = self.map_tool.swipe_layer
        base_layers = [l for l in self.canvas.layers() if l != swipe_layer]

        base_painter = QPainter(final)
        base_painter.setRenderHint(QPainter.Antialiasing, True)
        try:
            if base_layers:
                ms = QgsMapSettings()
                ms.setLayers(base_layers)
                ms.setBackgroundColor(QColor(0, 0, 0, 0))
                ms.setOutputSize(size)
                ms.setExtent(extent)
                ms.setDestinationCrs(crs)
                ms.setOutputDpi(dpi)
                job = QgsMapRendererCustomPainterJob(ms, base_painter)
                job.start()
                job.waitForFinished()
        finally:
            base_painter.end()

        if swipe_layer:
            swipe_img = self.map_tool.get_rendered_swipe_image()
            if swipe_img is not None:
                w = size.width()
                h = size.height()
                p = QPainter(final)
                p.setRenderHint(QPainter.Antialiasing, True)
                p.setOpacity(self.map_tool.opacity)
                if self.map_tool.mode == MODE_SWIPE:
                    if self.map_tool.direction == DIR_HORIZONTAL:
                        clip_w = int(w * self.map_tool.swipe_position)
                        p.setClipRect(0, 0, clip_w, h)
                    else:
                        clip_h = int(h * self.map_tool.swipe_position)
                        p.setClipRect(0, 0, w, clip_h)
                    p.drawImage(0, 0, swipe_img)
                else:
                    p.drawImage(0, 0, swipe_img)
                p.end()

        return final

    def _export_to_image(self, file_path):
        from qgis.PyQt.QtGui import QImage, QPainter
        img = self._render_composite_image()
        if file_path.lower().endswith(".jpg"):
            rgb = QImage(img.size(), QImage.Format_RGB32)
            rgb.fill(self.canvas.canvasColor())
            p = QPainter(rgb)
            p.drawImage(0, 0, img)
            p.end()
            ok = rgb.save(file_path, "JPG", 92)
        else:
            ok = img.save(file_path, "PNG")
        if not ok:
            raise RuntimeError("No se pudo guardar la imagen.")

    def _export_to_pdf(self, file_path):
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QPainter
        from qgis.PyQt.QtPrintSupport import QPrinter

        img = self._render_composite_image()
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(file_path)
        try:
            from qgis.PyQt.QtGui import QPageSize
            page_size = QPageSize(
                img.size(), QPageSize.Point, "swipe", QPageSize.ExactMatch
            )
            printer.setPageSize(page_size)
        except Exception:
            pass

        p = QPainter(printer)
        try:
            target = p.viewport()
            scaled = img.scaled(
                target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (target.width() - scaled.width()) // 2
            y = (target.height() - scaled.height()) // 2
            p.drawImage(x, y, scaled)
        finally:
            p.end()
