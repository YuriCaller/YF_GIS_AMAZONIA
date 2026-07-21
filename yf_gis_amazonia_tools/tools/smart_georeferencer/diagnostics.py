"""
diagnostics.py — Validación de GCPs por leave-one-out (LOO).

Con TPS el residual en muestra es CERO (interpola exacto), así que no sirve para
detectar puntos malos. El LOO sí: por cada GCP se le quita del ajuste, se reajusta
con los demás, y se mide cuánto se desvía su predicción respecto a su valor real.
Un residual LOO alto => ese punto es inconsistente con los otros (probable error
de medición/digitalización) o está en zona de mucha distorsión.
"""
import numpy as np
from .mesh_warp import build_progressive


def loo_residuals(src_px, map_xy, mode="tps"):
    """Devuelve un array Nx1 con el residual LOO (en unidades de mapa) por GCP.
    NaN si no hay suficientes puntos (se requieren >=3)."""
    src = np.asarray(src_px, float).reshape(-1, 2)
    dst = np.asarray(map_xy, float).reshape(-1, 2)
    n = len(src)
    res = np.full(n, np.nan)
    if n < 5:
        return res          # <5: sin redundancia, el outlier contamina el ajuste
    idx = np.arange(n)
    for i in range(n):
        keep = idx != i
        T = build_progressive(src[keep], dst[keep], mode)
        if T is None:
            continue
        pred = T.map(src[i:i + 1])[0]
        res[i] = float(np.hypot(pred[0] - dst[i, 0], pred[1] - dst[i, 1]))
    return res


def loo_rms(res):
    """RMS de los residuales LOO (ignora NaN)."""
    r = res[~np.isnan(res)]
    if len(r) == 0:
        return None
    return float(np.sqrt((r ** 2).mean()))


def residual_color(r, tol):
    """Color (R,G,B) por semáforo: verde <= tol/2, amarillo <= tol, rojo > tol."""
    if r is None or (isinstance(r, float) and np.isnan(r)):
        return (150, 150, 150)            # gris: sin dato
    if r <= tol * 0.5:
        return (60, 200, 90)              # verde
    if r <= tol:
        return (240, 190, 60)             # amarillo
    return (230, 60, 60)                  # rojo
