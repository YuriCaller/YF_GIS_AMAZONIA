"""
canvas_item.py — Item de canvas + herramienta de captura de GCPs estilo ArcGIS Pro.

Modelo de interacción:
  - La imagen se coloca con un encuadre inicial (bootstrap) que define su escala.
  - Los GCPs aplican una CORRECCIÓN encima (en coords de mapa):
        1 GCP -> traslación · 2 -> similitud · 3+ -> afín/TPS.
  - Captura de dos clics: clic en una feature de la IMAGEN (se fija el punto
    origen en píxel) -> flecha guía -> clic en el punto de control en el MAPA.
  - Inversa (clic -> píxel de imagen) por ajuste swap, validada con round-trip 0.
"""
import numpy as np
from qgis.PyQt.QtCore import Qt, QPointF, QRectF
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QPen, QBrush, QPolygonF
from qgis.core import QgsPointXY, QgsPointLocator
from qgis.gui import QgsMapCanvasItem, QgsMapTool, QgsSnapIndicator

from .mesh_warp import MeshWarpRenderer, build_progressive, AffineTransform
from .diagnostics import residual_color


class _Composed:
    """forward = b(a(x)). Compone bootstrap + corrección."""
    def __init__(self, a, b):
        self.a, self.b = a, b

    def map(self, pts):
        p = self.a.map(pts) if self.a else np.asarray(pts, float)
        return self.b.map(p) if self.b else p


class GeorefCanvasItem(QgsMapCanvasItem):
    GRID_DRAG = 10
    GRID_FINE = 26

    def __init__(self, canvas, image, mode="tps"):
        super().__init__(canvas)
        self.canvas = canvas
        self.mode = mode
        self.image = image.convertToFormat(QImage.Format.Format_ARGB32)
        orig_w = max(self.image.width(), 1)
        if max(self.image.width(), self.image.height()) > 2000:
            self.image = self.image.scaled(
                2000, 2000, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        self.W, self.H = self.image.width(), self.image.height()
        # factor px-original -> px-item (si se reescaló la imagen para el preview)
        self.src_scale = self.W / orig_w
        self.renderer = MeshWarpRenderer(self.image, grid=self.GRID_FINE)

        self.src_px = np.zeros((0, 2))
        self.map_xy = np.zeros((0, 2))

        self.pending_src = None
        self.guide_from = None
        self.guide_to = None
        self._drag_idx = None

        # comparación / validación contra la referencia
        self.opacity = 1.0          # 0..1
        self.show_image = True      # flicker on/off
        self.swipe_enabled = False
        self.swipe_frac = 0.5       # 0..1 del ancho del canvas
        self.preview = False        # dibuja la imagen (mesh) solo durante arrastre;
                                    # en reposo la muestra la capa VRT de la TOC
        # diagnóstico leave-one-out (heatmap de calidad por GCP)
        self.loo = None             # array de residuales LOO (m) alineado a src_px
        self.tol = 1.0              # tolerancia (m) para el semáforo
        self.show_heatmap = True
        self.highlight_idx = None   # GCP resaltado (clic en la tabla)

        self._make_bootstrap()
        self._rebuild()

    def _make_bootstrap(self):
        ext = self.canvas.extent()
        mupp = ext.width() * 0.6 / max(self.W, 1)
        cx, cy = ext.center().x(), ext.center().y()
        x0, y0 = cx - self.W * mupp / 2, cy + self.H * mupp / 2
        src = np.array([[0, 0], [self.W, 0], [self.W, self.H], [0, self.H]], float)
        dst = np.array([[x0, y0], [x0 + self.W * mupp, y0],
                        [x0 + self.W * mupp, y0 - self.H * mupp],
                        [x0, y0 - self.H * mupp]], float)
        self.boot = AffineTransform(src, dst)
        self.boot_inv = AffineTransform(dst, src)

    def _build_transforms(self):
        n = len(self.src_px)
        if n == 0:
            self.fwd = self.boot
            self.inv = self.boot_inv
            return
        src_map = self.boot.map(self.src_px)
        corr = build_progressive(src_map, self.map_xy, self.mode)
        corr_inv = build_progressive(self.map_xy, src_map, self.mode)
        self.fwd = _Composed(self.boot, corr)
        self.inv = _Composed(corr_inv, self.boot_inv)

    def _rebuild(self):
        self._build_transforms()
        self.renderer.update_transform(self.fwd)
        self.updatePosition()

    def set_grid(self, g):
        if g != self.renderer.grid:
            self.renderer = MeshWarpRenderer(self.image, grid=g)
            self.renderer.update_transform(self.fwd)
        self.updatePosition()

    # ---- comparación / validación ----
    def set_opacity(self, frac):
        self.opacity = max(0.0, min(1.0, frac)); self.update()

    def set_show_image(self, on):
        self.show_image = bool(on); self.update()

    def set_swipe(self, on):
        self.swipe_enabled = bool(on); self.update()

    def set_swipe_frac(self, frac):
        self.swipe_frac = max(0.0, min(1.0, frac)); self.update()

    def set_preview(self, on):
        self.preview = bool(on); self.update()

    def set_loo(self, loo, tol=None):
        self.loo = loo
        if tol is not None:
            self.tol = tol
        self.update()

    def set_show_heatmap(self, on):
        self.show_heatmap = bool(on); self.update()

    def set_highlight(self, idx):
        self.highlight_idx = idx; self.update()

    def canvas_to_image_px(self, map_point):
        px = self.inv.map(np.array([[map_point.x(), map_point.y()]]))[0]
        if -2 <= px[0] <= self.W + 2 and -2 <= px[1] <= self.H + 2:
            return px
        return None

    def image_px_to_canvas(self, px):
        m = self.fwd.map(np.array([px], float))[0]
        c = self.toCanvasCoordinates(QgsPointXY(m[0], m[1])) - self.pos()
        return QPointF(c.x(), c.y())

    def add_gcp(self, src_px, map_point):
        self.src_px = np.vstack([self.src_px, src_px])
        self.map_xy = np.vstack([self.map_xy, [map_point.x(), map_point.y()]])
        self._rebuild()

    def pick_target(self, qpoint_px, tol=14):
        m2p = self.canvas.getCoordinateTransform()
        best, bd = None, tol
        for i, (x, y) in enumerate(self.map_xy):
            p = m2p.transform(QgsPointXY(x, y))
            d = ((p.x() - qpoint_px.x()) ** 2 + (p.y() - qpoint_px.y()) ** 2) ** 0.5
            if d < bd:
                best, bd = i, d
        return best

    def move_target(self, idx, map_point):
        self.map_xy[idx] = [map_point.x(), map_point.y()]
        self._rebuild()

    def remove_gcp(self, idx):
        self.src_px = np.delete(self.src_px, idx, axis=0)
        self.map_xy = np.delete(self.map_xy, idx, axis=0)
        self._rebuild()

    def set_gcps(self, src, mapc):
        self.src_px = np.asarray(src, float).reshape(-1, 2)
        self.map_xy = np.asarray(mapc, float).reshape(-1, 2)
        self._rebuild()

    def clear_gcps(self):
        self.src_px = np.zeros((0, 2))
        self.map_xy = np.zeros((0, 2))
        self._rebuild()

    def gcps_original_px(self):
        """GCPs en píxel de la imagen ORIGINAL (deshace el reescalado del preview).
        GDAL georreferencia contra el archivo original, así que usa esto."""
        if self.src_scale == 0:
            return self.src_px
        return self.src_px / self.src_scale

    def residual_rms(self):
        if len(self.src_px) < 1:
            return None
        pred = self.fwd.map(self.src_px)
        r = np.linalg.norm(pred - self.map_xy, axis=1)
        return float(np.sqrt((r ** 2).mean()))

    def updatePosition(self):
        def project(map_pts):
            out = np.empty_like(map_pts)
            for i, (x, y) in enumerate(map_pts):
                c = self.toCanvasCoordinates(QgsPointXY(x, y)) - self.pos()  # VERIFICAR offset
                out[i] = [c.x(), c.y()]
            return out
        self.renderer.project(project)
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        dv = self.renderer.dst_vertices
        if dv is None or len(dv) == 0:
            return QRectF()
        x0, y0 = dv.min(0); x1, y1 = dv.max(0)
        m = 60
        return QRectF(x0 - m, y0 - m, (x1 - x0) + 2 * m, (y1 - y0) + 2 * m)

    def paint(self, painter, option=None, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                              self._drag_idx is None and self.pending_src is None)

        # --- imagen (con transparencia / swipe / flicker) ---
        cw, ch = self.canvas.width(), self.canvas.height()
        ox, oy = self.pos().x(), self.pos().y()
        left, top = -ox - 50, -oy - 50
        divider_local = None
        if self.swipe_enabled:
            divider_local = self.swipe_frac * cw - ox
        if self.preview and self.show_image and self.opacity > 0.001:
            painter.save()
            if divider_local is not None:
                # mostrar la imagen solo a la IZQUIERDA del divisor (rect finito)
                painter.setClipRect(QRectF(left, top,
                                           divider_local - left, ch + 100))
            painter.setOpacity(self.opacity)
            self.renderer.paint(painter)
            painter.restore()
        # línea divisoria del swipe (a opacidad plena)
        if divider_local is not None:
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(QPointF(divider_local, top),
                             QPointF(divider_local, top + ch + 100))
            painter.setPen(QPen(QColor(40, 40, 40), 1))
            painter.drawLine(QPointF(divider_local + 1.5, top),
                             QPointF(divider_local + 1.5, top + ch + 100))

        # --- enlaces y puntos de control (siempre visibles, opacidad plena) ---
        m2p = self.canvas.getCoordinateTransform()
        for i in range(len(self.src_px)):
            here = self.image_px_to_canvas(self.src_px[i])
            tgt = m2p.transform(QgsPointXY(*self.map_xy[i]))
            tgtp = QPointF(tgt.x() - self.pos().x(), tgt.y() - self.pos().y())
            on = (self._drag_idx == i)
            hl = (self.highlight_idx == i)
            # color del punto: heatmap LOO (verde/amarillo/rojo) o por defecto
            if (self.show_heatmap and self.loo is not None
                    and i < len(self.loo)):
                rc, gc, bc = residual_color(float(self.loo[i]), self.tol)
                mark = QColor(rc, gc, bc)
            else:
                mark = QColor(255, 70, 70)
            if on:
                mark = QColor(255, 230, 120)
            self._draw_arrow(painter, here, tgtp,
                             QColor(255, 200, 60) if on else QColor(120, 200, 255), 2)
            r = 9 if hl else 6
            if hl:
                painter.setPen(QPen(QColor(255, 255, 255), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(tgtp, r + 4, r + 4)
            painter.setPen(QPen(mark.darker(130), 2))
            painter.setBrush(QBrush(QColor(mark.red(), mark.green(), mark.blue(), 180)))
            painter.drawEllipse(tgtp, r, r)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(120, 200, 255), 2))
            painter.drawEllipse(here, 4, 4)
            painter.setPen(QColor(230, 240, 255))
            painter.drawText(tgtp + QPointF(8, -8), str(i + 1))

        # flecha guía durante la captura del 2.º clic (ancla recalculada desde
        # el píxel de la imagen, así NO se desfasa al moverse el canvas)
        if self.pending_src is not None and self.guide_to is not None:
            gfrom = self.image_px_to_canvas(self.pending_src)
            self._draw_arrow(painter, gfrom, self.guide_to,
                             QColor(255, 230, 120), 2, dashed=True)
            painter.setPen(QPen(QColor(120, 200, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(gfrom, 5, 5)

    def _draw_arrow(self, painter, p0, p1, color, width, dashed=False):
        pen = QPen(color, width)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(p0, p1)
        v = np.array([p1.x() - p0.x(), p1.y() - p0.y()], float)
        L = np.hypot(*v)
        if L < 6:
            return
        v /= L
        n = np.array([-v[1], v[0]])
        size = 9
        a = QPointF(p1.x() - v[0] * size + n[0] * size * 0.5,
                    p1.y() - v[1] * size + n[1] * size * 0.5)
        b = QPointF(p1.x() - v[0] * size - n[0] * size * 0.5,
                    p1.y() - v[1] * size - n[1] * size * 0.5)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color, 1))
        painter.drawPolygon(QPolygonF([p1, a, b]))


class CaptureGcpTool(QgsMapTool):
    """Dos clics: origen (imagen) -> destino (mapa). Clic izq sobre un punto de
    control existente = arrastrarlo. Clic der = borrarlo."""
    def __init__(self, canvas, item, on_change=None, on_preview=None,
                 on_context=None):
        super().__init__(canvas)
        self.canvas = canvas
        self.item = item
        self.on_change = on_change
        self.on_preview = on_preview     # (active: bool) -> oculta/rebuild capa
        self.on_context = on_context     # (map_point, idx, image_px) -> menú
        self.snap = QgsSnapIndicator(canvas)   # marca de autoensamblado

    def _snap(self, qpoint):
        """Autoensambla a vértices según la config de snapping de QGIS.
        Devuelve (QgsPointXY, match). Si no hay snap, usa la coord cruda."""
        match = self.canvas.snappingUtils().snapToMap(qpoint)
        self.snap.setMatch(match)
        if match.isValid():
            return match.point(), match
        return self.toMapCoordinates(qpoint), None

    def _notify(self):
        if self.on_change:
            self.on_change()

    def _preview(self, active):
        self.item.set_preview(active)
        if self.on_preview:
            self.on_preview(active)

    def canvasPressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            # cancelar captura en curso, o abrir menú contextual
            if self.item.pending_src is not None:
                self.item.pending_src = None
                self.item.guide_from = self.item.guide_to = None
                self.snap.setMatch(QgsPointLocator.Match())
                self.item.update()
                return
            if self.on_context:
                mp = self.toMapCoordinates(e.pos())
                idx = self.item.pick_target(e.pos())
                px = self.item.canvas_to_image_px(mp)
                self.on_context(mp, idx, px)
            return

        if self.item.pending_src is not None:
            target, _ = self._snap(e.pos())     # autoensambla a vértice si hay
            self.item.add_gcp(self.item.pending_src, target)
            self.item.pending_src = None
            self.item.guide_from = self.item.guide_to = None
            self.snap.setMatch(QgsPointLocator.Match())   # limpiar indicador
            self.item.set_grid(self.item.GRID_FINE)
            self._notify()
            return

        idx = self.item.pick_target(e.pos())
        if idx is not None:
            self.item._drag_idx = idx
            self.item.set_grid(self.item.GRID_DRAG)
            self._preview(True)          # muestra preview en vivo, oculta capa VRT
            return

        px = self.item.canvas_to_image_px(self.toMapCoordinates(e.pos()))
        if px is not None:
            self.item.pending_src = px
            self.item.guide_from = self.item.image_px_to_canvas(px)
            self.item.guide_to = QPointF(e.pos().x() - self.item.pos().x(),
                                         e.pos().y() - self.item.pos().y())
            self.item.update()

    def canvasMoveEvent(self, e):
        if self.item._drag_idx is not None:
            self.item.move_target(self.item._drag_idx, self.toMapCoordinates(e.pos()))
            self._notify()
        elif self.item.pending_src is not None:
            pt, _ = self._snap(e.pos())     # muestra indicador de snap
            cpt = self.canvas.getCoordinateTransform().transform(pt)
            self.item.guide_to = QPointF(cpt.x() - self.item.pos().x(),
                                         cpt.y() - self.item.pos().y())
            self.item.update()

    def canvasReleaseEvent(self, e):
        if self.item._drag_idx is not None:
            self.item._drag_idx = None
            self.item.set_grid(self.item.GRID_FINE)
            self._preview(False)         # oculta preview, reconstruye capa VRT
            self._notify()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape and self.item.pending_src is not None:
            self.item.pending_src = None
            self.item.guide_from = self.item.guide_to = None
            self.snap.setMatch(QgsPointLocator.Match())
            self.item.update()
