"""
mesh_warp.py — Núcleo del georreferenciador estilo Photoshop.

Idea central (la que discutimos):
  - La transformación no-lineal (TPS) se evalúa SOLO en los vértices de una grilla.
  - Dentro de cada celda, Qt interpola con una afín local (QTransform) por triángulo.
  - Eso colapsa "millones de píxeles" a "unos miles de vértices" => tiempo real.

Este módulo no depende de QGIS. Solo numpy + PyQt5.
"""

import numpy as np
# Siempre vía qgis.PyQt (compatible Qt5/Qt6, es el binding que expone QGIS).
from qgis.PyQt.QtGui import (QImage, QPainter, QPainterPath, QTransform,
                             QColor, QPen)
from qgis.PyQt.QtCore import QPointF, QRectF, Qt


# --------------------------------------------------------------------------
# 1) TRANSFORMACIONES  (src pixel -> dst coords)
#    Cada una expone .map(pts Nx2) -> Nx2
# --------------------------------------------------------------------------

class AffineTransform:
    """Caso degenerado: malla de 1 celda. Ajuste por mínimos cuadrados."""
    def __init__(self, src, dst):
        src = np.asarray(src, float); dst = np.asarray(dst, float)
        # [x y 1] @ M = [X Y]
        A = np.hstack([src, np.ones((len(src), 1))])
        self.M, *_ = np.linalg.lstsq(A, dst, rcond=None)  # 3x2

    def map(self, pts):
        pts = np.asarray(pts, float)
        A = np.hstack([pts, np.ones((len(pts), 1))])
        return A @ self.M


class TPSTransform:
    """Thin Plate Spline: el caso no-lineal que QTransform sola NO puede.
    Soporte global: mover un GCP deforma toda la imagen (suavemente)."""
    def __init__(self, src, dst, smoothing=0.0):
        self.src = np.asarray(src, float)
        dst = np.asarray(dst, float)
        n = len(self.src)
        K = self._U(self._dist(self.src, self.src))
        if smoothing:
            K += np.eye(n) * smoothing
        P = np.hstack([np.ones((n, 1)), self.src])      # n x 3
        L = np.zeros((n + 3, n + 3))
        L[:n, :n] = K
        L[:n, n:] = P
        L[n:, :n] = P.T
        Y = np.vstack([dst, np.zeros((3, 2))])          # (n+3) x 2
        self.W = np.linalg.solve(L, Y)                  # (n+3) x 2

    @staticmethod
    def _dist(a, b):
        d = a[:, None, :] - b[None, :, :]
        return np.sqrt((d ** 2).sum(-1))

    @staticmethod
    def _U(r):
        r = np.where(r == 0, 1e-12, r)
        return r ** 2 * np.log(r ** 2)

    def map(self, pts):
        pts = np.asarray(pts, float)
        U = self._U(self._dist(pts, self.src))          # m x n
        P = np.hstack([np.ones((len(pts), 1)), pts])    # m x 3
        A = np.hstack([U, P])                           # m x (n+3)
        return A @ self.W


class TranslationTransform:
    """1 GCP: solo traslación (como ArcGIS con un punto)."""
    def __init__(self, src, dst):
        src = np.asarray(src, float); dst = np.asarray(dst, float)
        self.t = (dst - src).mean(axis=0)

    def map(self, pts):
        return np.asarray(pts, float) + self.t


class SimilarityTransform:
    """2 GCP: traslación + rotación + escala uniforme (Helmert)."""
    def __init__(self, src, dst):
        src = np.asarray(src, float); dst = np.asarray(dst, float)
        n = len(src)
        A = np.zeros((2 * n, 4)); b = np.zeros(2 * n)
        for i, (sx, sy) in enumerate(src):
            A[2 * i] = [sx, -sy, 1, 0]
            A[2 * i + 1] = [sy, sx, 0, 1]
            b[2 * i] = dst[i, 0]; b[2 * i + 1] = dst[i, 1]
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        self.a, self.b, self.tx, self.ty = sol

    def map(self, pts):
        pts = np.asarray(pts, float)
        x = self.a * pts[:, 0] - self.b * pts[:, 1] + self.tx
        y = self.b * pts[:, 0] + self.a * pts[:, 1] + self.ty
        return np.column_stack([x, y])


def build_transform(mode, src, dst):
    if mode == "tps" and len(src) >= 3:
        return TPSTransform(src, dst, smoothing=0.0)
    return AffineTransform(src, dst)


def build_progressive(src, dst, mode="tps"):
    """Elige el modelo según el número de GCPs, como ArcGIS:
    1 -> traslación, 2 -> similitud, 3+ -> afín o TPS. 0 -> None."""
    src = np.asarray(src, float); dst = np.asarray(dst, float)
    n = len(src)
    if n == 0:
        return None
    if n == 1:
        return TranslationTransform(src, dst)
    if n == 2:
        return SimilarityTransform(src, dst)
    if mode == "tps":
        return TPSTransform(src, dst, smoothing=0.0)
    return AffineTransform(src, dst)


# --------------------------------------------------------------------------
# 2) MALLA + RENDERER POR TRIÁNGULOS
# --------------------------------------------------------------------------

def _affine_qtransform(s, d):
    """QTransform que mapea exactamente 3 puntos src->dst (afín por triángulo)."""
    s = np.asarray(s, float); d = np.asarray(d, float)
    A = np.array([[s[0,0], s[0,1], 1],
                  [s[1,0], s[1,1], 1],
                  [s[2,0], s[2,1], 1]], float)
    mx = np.linalg.solve(A, d[:, 0])   # m11, m21, dx
    my = np.linalg.solve(A, d[:, 1])   # m12, m22, dy
    return QTransform(mx[0], my[0], mx[1], my[1], mx[2], my[2])


class MeshWarpRenderer:
    """Renderiza una QImage warpeada según GCPs, vía malla NxN.
    grid mayor = warp más suave / más costo. grid=1 equivale a afín pura."""
    def __init__(self, image: QImage, grid=24):
        self.image = image
        self.grid = grid
        self.w, self.h = image.width(), image.height()
        # vértices de la grilla en coords de PÍXEL de la imagen (fijos)
        gx = np.linspace(0, self.w, grid + 1)
        gy = np.linspace(0, self.h, grid + 1)
        self.gx, self.gy = gx, gy
        XX, YY = np.meshgrid(gx, gy)
        self.src_vertices = np.column_stack([XX.ravel(), YY.ravel()])
        self.cols = grid + 1
        self.dst_vertices = self.src_vertices.copy()
        self.map_vertices = self.src_vertices.copy()
        self.last_eval_ms = 0.0
        self.last_proj_ms = 0.0

    def update_transform(self, transform):
        """ETAPA 1 (warp): evalúa TPS SOLO en los vértices => coords de MAPA.
        Se recalcula únicamente al EDITAR un GCP. Independiente del pan/zoom."""
        import time
        t0 = time.perf_counter()
        self.map_vertices = transform.map(self.src_vertices)   # coords de mapa
        self.dst_vertices = self.map_vertices                  # default: identidad
        self.last_eval_ms = (time.perf_counter() - t0) * 1000

    def project(self, fn):
        """ETAPA 2 (proyección): coords de MAPA -> píxeles del canvas.
        Se recalcula en CADA pan/zoom, pero NO re-evalúa TPS. Es barata.
        `fn` recibe un array Nx2 (mapa) y devuelve Nx2 (píxel canvas)."""
        import time
        t0 = time.perf_counter()
        self.dst_vertices = fn(self.map_vertices)
        self.last_proj_ms = (time.perf_counter() - t0) * 1000

    def _vid(self, r, c):
        return r * self.cols + c

    def paint(self, painter: QPainter):
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        img = self.image
        sv, dv = self.src_vertices, self.dst_vertices
        for r in range(self.grid):
            for c in range(self.grid):
                i00 = self._vid(r, c);     i10 = self._vid(r, c + 1)
                i01 = self._vid(r + 1, c); i11 = self._vid(r + 1, c + 1)
                for tri in ((i00, i10, i11), (i00, i11, i01)):
                    s = sv[list(tri)]
                    d = dv[list(tri)]
                    path = QPainterPath()
                    path.moveTo(QPointF(*d[0]))
                    path.lineTo(QPointF(*d[1]))
                    path.lineTo(QPointF(*d[2]))
                    path.closeSubpath()
                    # solo el sub-rectángulo fuente del triángulo (evita overdraw)
                    x0, y0 = s.min(0); x1, y1 = s.max(0)
                    sub = QRectF(x0, y0, x1 - x0, y1 - y0)
                    painter.save()
                    painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
                    painter.setTransform(_affine_qtransform(s, d), True)
                    painter.drawImage(sub, img, sub)
                    painter.restore()
