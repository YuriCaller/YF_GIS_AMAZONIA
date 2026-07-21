"""
gcp_matcher.py — Detección automática de GCPs con OpenCV.

Empareja una imagen de dron contra un ráster de referencia ya georreferenciado
y devuelve correspondencias listas para alimentar el georreferenciador de malla:

  src  = keypoints en la imagen de DRON      (píxeles, eje del warp)
  ref  = keypoints en la imagen de REFERENCIA (píxeles -> luego a coords de mapa)

Pipeline:
  1) Detectar features (SIFT por calidad, ORB por velocidad).
  2) Match con test de razón de Lowe (descarta ambigüedades).
  3) Verificación geométrica con RANSAC (homografía) -> descarta outliers.
  4) Filtro de DISTRIBUCIÓN: cobertura pareja en rejilla (clave para TPS).

Depende solo de numpy + opencv (cv2). No necesita QGIS.
"""
import numpy as np
import cv2


def _detector(name):
    name = name.upper()
    if name == "ORB":
        return cv2.ORB_create(nfeatures=5000), cv2.NORM_HAMMING
    return cv2.SIFT_create(), cv2.NORM_L2          # SIFT por defecto


def _to_gray(img):
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def auto_detect_gcps(drone_img, ref_img, detector="SIFT",
                     ratio=0.75, ransac_thresh=5.0,
                     max_gcps=40, spread_grid=6, min_matches=8):
    """Devuelve un dict con las correspondencias detectadas y diagnóstico.

    Claves: src (Nx2 px dron), ref (Nx2 px referencia), distances,
            n_raw, n_good, n_inliers, n_final, ok, msg.
    """
    g1, g2 = _to_gray(drone_img), _to_gray(ref_img)
    det, norm = _detector(detector)

    kp1, des1 = det.detectAndCompute(g1, None)
    kp2, des2 = det.detectAndCompute(g2, None)
    if des1 is None or des2 is None or len(kp1) < min_matches or len(kp2) < min_matches:
        return {"ok": False, "msg": "Muy pocos features detectados.",
                "n_raw": 0, "n_good": 0, "n_inliers": 0, "n_final": 0}

    # --- match k-NN + razón de Lowe ---
    bf = cv2.BFMatcher(norm)
    knn = bf.knnMatch(des1, des2, k=2)
    good = []
    for pair in knn:
        if len(pair) == 2:
            m, n = pair
            if m.distance < ratio * n.distance:
                good.append(m)
    if len(good) < min_matches:
        return {"ok": False,
                "msg": f"Solo {len(good)} matches buenos (<{min_matches}). "
                       "¿Imágenes muy distintas o sin solape?",
                "n_raw": len(knn), "n_good": len(good),
                "n_inliers": 0, "n_final": 0}

    src = np.float32([kp1[m.queryIdx].pt for m in good])
    ref = np.float32([kp2[m.trainIdx].pt for m in good])
    dist = np.float32([m.distance for m in good])

    # --- verificación geométrica RANSAC (homografía) ---
    H, mask = cv2.findHomography(src, ref, cv2.RANSAC, ransac_thresh)
    if mask is None:
        return {"ok": False, "msg": "RANSAC no encontró modelo consistente.",
                "n_raw": len(knn), "n_good": len(good),
                "n_inliers": 0, "n_final": 0}
    inl = mask.ravel().astype(bool)
    src, ref, dist = src[inl], ref[inl], dist[inl]

    # --- filtro de DISTRIBUCIÓN espacial (cobertura pareja para TPS) ---
    src, ref, dist = _spread_filter(src, ref, dist, g1.shape,
                                    spread_grid, max_gcps)

    return {"ok": len(src) >= 3, "src": src, "ref": ref, "distances": dist,
            "n_raw": len(knn), "n_good": len(good),
            "n_inliers": int(inl.sum()), "n_final": len(src),
            "homography": H,
            "msg": f"{len(src)} GCPs distribuidos de {int(inl.sum())} inliers."}


def _spread_filter(src, ref, dist, shape, grid, max_gcps):
    """Conserva el MEJOR match (menor distancia de descriptor) por celda de una
    rejilla sobre la imagen de dron => evita amontonamiento, cobertura pareja."""
    h, w = shape
    best = {}
    for i, (x, y) in enumerate(src):
        cx = min(int(x / w * grid), grid - 1)
        cy = min(int(y / h * grid), grid - 1)
        key = (cx, cy)
        if key not in best or dist[i] < dist[best[key]]:
            best[key] = i
    idx = sorted(best.values(), key=lambda i: dist[i])[:max_gcps]
    idx = np.array(idx, int)
    return src[idx], ref[idx], dist[idx]


def ref_px_to_map(ref_px, geotransform):
    """Convierte píxeles de la referencia a coords de MAPA usando el
    geotransform estilo GDAL (6 coef): [gt0,gt1,gt2,gt3,gt4,gt5].
      X = gt0 + col*gt1 + row*gt2 ;  Y = gt3 + col*gt4 + row*gt5
    En QGIS lo obtienes de la capa de referencia (provider.dataSourceUri / GDAL).
    """
    gt = geotransform
    col = ref_px[:, 0]; row = ref_px[:, 1]
    X = gt[0] + col * gt[1] + row * gt[2]
    Y = gt[3] + col * gt[4] + row * gt[5]
    return np.column_stack([X, Y])


def draw_matches(drone_img, ref_img, result, max_draw=60):
    """Visualización de control: líneas entre correspondencias detectadas."""
    if not result.get("ok"):
        return None
    src, ref = result["src"], result["ref"]
    h1, w1 = drone_img.shape[:2]; h2, w2 = ref_img.shape[:2]
    H = max(h1, h2)
    canvas = np.zeros((H, w1 + w2 + 20, 3), np.uint8)
    d3 = drone_img if drone_img.ndim == 3 else cv2.cvtColor(drone_img, cv2.COLOR_GRAY2BGR)
    r3 = ref_img if ref_img.ndim == 3 else cv2.cvtColor(ref_img, cv2.COLOR_GRAY2BGR)
    canvas[:h1, :w1] = d3
    canvas[:h2, w1 + 20:w1 + 20 + w2] = r3
    rng = np.random.default_rng(0)
    for i in range(min(len(src), max_draw)):
        c = tuple(int(v) for v in rng.integers(60, 255, 3))
        p1 = (int(src[i, 0]), int(src[i, 1]))
        p2 = (int(ref[i, 0]) + w1 + 20, int(ref[i, 1]))
        cv2.circle(canvas, p1, 4, c, -1)
        cv2.circle(canvas, p2, 4, c, -1)
        cv2.line(canvas, p1, p2, c, 1, cv2.LINE_AA)
    return canvas
