"""
dependencies.py — Detección e instalación guiada de dependencias de Python.

QGIS no instala dependencias de pip automáticamente, y OpenCV es un wheel
compilado por plataforma (no se puede empaquetar en el zip). Este módulo:
  1) Detecta qué falta (cv2).
  2) Localiza el intérprete Python correcto del entorno QGIS (el punto frágil
     en Windows, donde sys.executable apunta a qgis-bin.exe, no a python.exe).
  3) Corre `pip install` por debajo y reporta resultado, pidiendo reiniciar.

Usamos opencv-python-HEADLESS a propósito: el opencv-python normal trae su
propio Qt y puede chocar con el Qt de QGIS. El headless lo evita.
"""
import os
import sys
import subprocess  # nosec B404 — solo se usa para 'pip install' con lista de args fija (sin shell)

# paquetes requeridos: nombre_import -> spec_pip
REQUIRED = {
    "cv2": "opencv-python-headless",
    # numpy ya viene con QGIS; lo dejamos como respaldo por si acaso
    "numpy": "numpy",
}


def missing_dependencies():
    """Devuelve [(import_name, pip_spec), ...] de lo que NO está instalado."""
    miss = []
    for mod, spec in REQUIRED.items():
        try:
            __import__(mod)
        except Exception:
            miss.append((mod, spec))
    return miss


def find_python_executable():
    """Localiza el python del entorno de QGIS para correr pip.
    En Linux/macOS sys.executable suele servir; en Windows (qgis-bin.exe)
    hay que buscar el python.exe del propio QGIS/OSGeo4W."""
    exe = sys.executable or ""
    if "python" in os.path.basename(exe).lower():
        return exe

    candidates = []
    if sys.platform.startswith("win"):
        names = ("python.exe", "python3.exe", "pythonw.exe")
        # sys.prefix suele apuntar a apps\PythonXX en OSGeo4W
        for n in names:
            candidates += [os.path.join(sys.prefix, n),
                           os.path.join(os.path.dirname(exe), n),
                           os.path.join(sys.prefix, "Scripts", n)]
    else:
        for n in ("python3", "python"):
            candidates += [os.path.join(sys.prefix, "bin", n),
                           os.path.join(os.path.dirname(exe), n)]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return exe  # último recurso: puede funcionar con -m pip en algunos setups


def install(packages, user=True, log=None):
    """Instala `packages` con pip. Devuelve (ok, salida_texto).
    Prueba primero con --user (evita problemas de permisos); si falla,
    reintenta sin --user."""
    py = find_python_executable()

    def _run(cmd):
        if log:
            log(" ".join(cmd))
        # nosec B603 — cmd es una lista fija [python, -m, pip, install, ...paquetes],
        # sin shell=True ni entrada de usuario; los paquetes son constantes del plugin
        p = subprocess.run(cmd, stdout=subprocess.PIPE,  # nosec B603
                           stderr=subprocess.STDOUT, text=True)
        return p.returncode, p.stdout

    base = [py, "-m", "pip", "install", "--disable-pip-version-check"]
    attempts = []
    if user:
        attempts.append(base + ["--user"] + list(packages))
    attempts.append(base + list(packages))

    out_all = ""
    for cmd in attempts:
        rc, out = _run(cmd)
        out_all += out + "\n"
        if rc == 0:
            return True, out_all
    return False, out_all


# --- UI opcional (solo si hay QGIS/Qt disponible) ---
def prompt_and_install(parent=None):
    """Muestra un diálogo ofreciendo instalar lo que falte. Devuelve True si
    todas las dependencias quedaron disponibles (tras instalar o ya estaban)."""
    miss = missing_dependencies()
    if not miss:
        return True

    from qgis.PyQt.QtWidgets import (QMessageBox, QApplication)
    from qgis.PyQt.QtCore import Qt

    specs = [spec for _, spec in miss]
    mods = ", ".join(m for m, _ in miss)
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("YF Georeferenciador — dependencias")
    box.setText(f"Faltan dependencias de Python: {mods}")
    box.setInformativeText(
        "Se instalarán en el entorno de Python de QGIS:\n  "
        + "\n  ".join(specs)
        + "\n\n¿Instalar automáticamente ahora?\n"
          "(Necesitarás reiniciar QGIS al terminar.)")
    box.setStandardButtons(QMessageBox.StandardButton.Yes
                           | QMessageBox.StandardButton.No)
    if box.exec() != QMessageBox.StandardButton.Yes:
        return False

    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        ok, out = install(specs)
    finally:
        QApplication.restoreOverrideCursor()

    res = QMessageBox(parent)
    if ok:
        res.setIcon(QMessageBox.Icon.Information)
        res.setWindowTitle("Instalación completa")
        res.setText("Dependencias instaladas. Reinicia QGIS y vuelve a abrir "
                    "el plugin.")
    else:
        res.setIcon(QMessageBox.Icon.Critical)
        res.setWindowTitle("No se pudo instalar")
        res.setText("La instalación automática falló. Instala manualmente en "
                    "la consola de OSGeo4W / terminal:\n\n"
                    "  python -m pip install " + " ".join(specs))
        res.setDetailedText(out[-3000:])
    res.exec()
    return False  # pedir reinicio igualmente
