# -*- coding: utf-8 -*-
"""
pegado_poligonal.py — Pegado de tablas de azimut/distancia con mapeo de columnas
YF GIS Amazonia Tools · core · complemento de poligonal.py

Distinto de core/paste_helpers.py, que resuelve PARES DE COORDENADAS.
Aqui el problema es otro: una tabla de lados con azimut, distancia y
colindante, que es lo que trae una memoria descriptiva.

Dos capas, a propósito:

    1. Funciones puras (dividir_tabla, sugerir_roles, construir_segmentos).
       Sin Qt, sin QGIS. Testeables con pytest.
    2. TablaPegadoWidget, la cáscara Qt que solo orquesta lo anterior.

Toda la lógica de parseo vive en la capa 1. Si algo falla, se depura sin
levantar QGIS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .poligonal import Segmento, parse_azimut, parse_distancia

__all__ = [
    "ROLES", "IGNORAR", "AZIMUT", "DISTANCIA", "VERTICE_INI", "VERTICE_FIN",
    "COLINDANTE", "NOMBRE",
    "dividir_tabla", "detectar_encabezado", "sugerir_roles",
    "construir_segmentos", "ResultadoPegado",
]

# ──────────────────────────────────────────────────────────────────────
#  ROLES DE COLUMNA
# ──────────────────────────────────────────────────────────────────────

IGNORAR = "ignorar"
VERTICE_INI = "vertice_ini"
VERTICE_FIN = "vertice_fin"
AZIMUT = "azimut"
DISTANCIA = "distancia"
COLINDANTE = "colindante"
NOMBRE = "nombre"

ROLES = [
    (IGNORAR, "— ignorar —"),
    (VERTICE_INI, "Vértice inicio"),
    (VERTICE_FIN, "Vértice fin"),
    (AZIMUT, "Azimut / Rumbo"),
    (DISTANCIA, "Distancia"),
    (COLINDANTE, "Colindante"),
    (NOMBRE, "Nombre del lado"),
]

_PISTAS = {
    AZIMUT: ("azimut", "azimuth", "rumbo", "az.", "az ", "direccion", "dirección"),
    DISTANCIA: ("distancia", "dist", "longitud", "long", "medida", "metros"),
    VERTICE_INI: ("vertice", "vértice", "punto", "esquina", "hito", "desde", "p1"),
    VERTICE_FIN: ("hasta", "hacia", "p2", "siguiente"),
    COLINDANTE: ("colindante", "colindancia", "lindero", "linda", "vecino", "propietario"),
    NOMBRE: ("nombre", "lado", "tramo", "descripcion", "descripción"),
}


@dataclass
class ResultadoPegado:
    """Lo que devuelve construir_segmentos: datos buenos y errores por fila."""
    segmentos: list[Segmento]
    errores: dict[int, str]          # índice de fila de datos -> mensaje
    filas_ok: int = 0

    @property
    def valido(self) -> bool:
        return bool(self.segmentos) and not self.errores

    def resumen(self) -> str:
        if not self.segmentos and not self.errores:
            return "Sin datos que interpretar."
        n = len(self.segmentos)
        if not self.errores:
            return (f"{n} lado{'s' if n != 1 else ''} "
                    f"interpretado{'s' if n != 1 else ''} correctamente.")
        return (f"{n} lado{'s' if n != 1 else ''} correcto{'s' if n != 1 else ''}, "
                f"{len(self.errores)} con problemas. Corrige o quita esas filas.")


# ──────────────────────────────────────────────────────────────────────
#  1. FUNCIONES PURAS
# ──────────────────────────────────────────────────────────────────────

def dividir_tabla(texto: str) -> list[list[str]]:
    """
    Trocea texto pegado en filas y columnas.

    Detecta el separador por sí solo, en este orden:
        tabulador      -> Excel, Google Sheets, tablas de Word
        punto y coma   -> CSV en configuración regional española
        2+ espacios    -> copiado desde PDF o texto plano alineado

    Nunca parte por un solo espacio: rompería "Terrenos del Estado".
    """
    filas: list[list[str]] = []
    lineas = [ln for ln in texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
              if ln.strip()]
    if not lineas:
        return filas

    if any("\t" in ln for ln in lineas):
        partir = lambda ln: ln.split("\t")                       # noqa: E731
    elif sum(ln.count(";") for ln in lineas) >= len(lineas):
        partir = lambda ln: ln.split(";")                        # noqa: E731
    else:
        partir = lambda ln: re.split(r" {2,}|\t", ln.strip())    # noqa: E731

    for ln in lineas:
        celdas = [c.strip() for c in partir(ln)]
        while celdas and not celdas[-1]:
            celdas.pop()
        if celdas:
            filas.append(celdas)

    ancho = max(len(f) for f in filas)
    return [f + [""] * (ancho - len(f)) for f in filas]


def _parece_numerico(valor: str) -> bool:
    return bool(re.search(r"\d", valor))


def _compatible(rol: str, valores: list[str]) -> bool:
    """
    ¿El contenido de la columna admite ese rol?

    El encabezado miente más de lo que uno cree: una columna titulada "Lado"
    puede traer "V1-V2" y no una longitud. Antes de aceptar un rol sugerido
    por el título, se comprueba contra los datos.
    """
    vals = [v for v in valores if v.strip()]
    if not vals:
        return True
    parser = {AZIMUT: parse_azimut, DISTANCIA: parse_distancia}.get(rol)
    if parser is None:
        return True
    for v in vals:
        try:
            parser(v)
        except ValueError:
            return False
    return True


def detectar_encabezado(filas: list[list[str]]) -> bool:
    """
    ¿La primera fila son títulos? Sí cuando casi no tiene números y la
    segunda sí, o cuando contiene alguna palabra clave conocida.
    """
    if len(filas) < 2:
        return False
    primera, segunda = filas[0], filas[1]
    texto = " ".join(primera).lower()
    if any(p in texto for pistas in _PISTAS.values() for p in pistas):
        if sum(_parece_numerico(c) for c in primera) <= 1:
            return True
    con_num_1 = sum(_parece_numerico(c) for c in primera if c)
    con_num_2 = sum(_parece_numerico(c) for c in segunda if c)
    return con_num_1 == 0 and con_num_2 > 0


def _puntaje_columna(valores: list[str]) -> dict[str, float]:
    """Olfatea el contenido de una columna y puntúa cada rol posible."""
    vals = [v for v in valores if v.strip()]
    if not vals:
        return {}
    p: dict[str, float] = {}

    az_ok = dis_ok = con_cuadrante = 0
    maximo = 0.0
    for v in vals:
        try:
            a = parse_azimut(v)
            if a is not None:
                az_ok += 1
                if re.match(r"^\s*[NS]", v.strip().upper()):
                    con_cuadrante += 1
        except ValueError:
            pass
        try:
            d = parse_distancia(v)
            dis_ok += 1
            maximo = max(maximo, d)
        except ValueError:
            pass

    n = len(vals)
    if az_ok == n:
        # el rumbo por cuadrante es firma inequívoca de azimut
        p[AZIMUT] = 0.9 if con_cuadrante else (0.6 if maximo <= 360 else 0.2)
    if dis_ok == n:
        # distancias no llevan letras de cuadrante y suelen pasar de 360
        p[DISTANCIA] = 0.2 if con_cuadrante else (0.8 if maximo > 360 else 0.5)

    letras = sum(1 for v in vals if not _parece_numerico(v))
    if letras == n:
        largo = sum(len(v) for v in vals) / n
        p[COLINDANTE] = 0.7 if largo > 8 else 0.3
        p[NOMBRE] = 0.5 if largo <= 12 else 0.3
    elif all(len(v) <= 5 for v in vals):
        p[VERTICE_INI] = 0.4
    return p


def sugerir_roles(filas: list[list[str]], con_encabezado: bool) -> list[str]:
    """
    Propone un rol por columna. Primero por el texto del encabezado, que es
    la señal más fiable; lo que quede sin asignar se decide olfateando el
    contenido. Cada rol único se asigna una sola vez.
    """
    if not filas:
        return []
    ancho = len(filas[0])
    roles: list[str] = [IGNORAR] * ancho
    usados: set[str] = set()
    datos = filas[1:] if con_encabezado else filas

    if con_encabezado:
        for i, cab in enumerate(filas[0]):
            c = cab.strip().lower()
            if not c:
                continue
            for rol, pistas in _PISTAS.items():
                if rol in usados:
                    continue
                if not any(p in c for p in pistas):
                    continue
                if not _compatible(rol, [f[i] for f in datos if i < len(f)]):
                    continue          # el título dice una cosa, los datos otra
                roles[i] = rol
                usados.add(rol)
                break

    puntajes = [_puntaje_columna([f[i] for f in datos]) if i < len(filas[0]) else {}
                for i in range(ancho)]

    for rol in (AZIMUT, DISTANCIA, COLINDANTE, VERTICE_INI, NOMBRE):
        if rol in usados:
            continue
        mejor, mejor_p = -1, 0.35
        for i in range(ancho):
            if roles[i] != IGNORAR:
                continue
            if puntajes[i].get(rol, 0.0) > mejor_p:
                mejor, mejor_p = i, puntajes[i][rol]
        if mejor >= 0:
            roles[mejor] = rol
            usados.add(rol)

    return roles


def construir_segmentos(filas: list[list[str]], roles: list[str],
                        con_encabezado: bool) -> ResultadoPegado:
    """
    Aplica el mapeo y construye los Segmento. No se detiene en el primer
    error: recorre todo y devuelve los problemas por fila, para que la
    interfaz los marque todos de una vez.
    """
    datos = filas[1:] if con_encabezado else filas
    idx = {rol: roles.index(rol) for rol in set(roles) if rol != IGNORAR}

    if DISTANCIA not in idx:
        return ResultadoPegado([], {-1: "Falta asignar la columna de Distancia."})
    if AZIMUT not in idx:
        return ResultadoPegado([], {-1: "Falta asignar la columna de Azimut."})

    segmentos: list[Segmento] = []
    errores: dict[int, str] = {}

    for i, fila in enumerate(datos):
        def celda(rol: str) -> str:
            j = idx.get(rol, -1)
            return fila[j].strip() if 0 <= j < len(fila) else ""

        if not any(c.strip() for c in fila):
            continue
        try:
            seg = Segmento(
                distancia=parse_distancia(celda(DISTANCIA)),
                azimut=parse_azimut(celda(AZIMUT)),
                nombre=celda(NOMBRE),
                colindante=celda(COLINDANTE),
                vertice_ini=celda(VERTICE_INI),
                vertice_fin=celda(VERTICE_FIN),
            )
        except ValueError as e:
            errores[i] = str(e)
            continue
        segmentos.append(seg)

    return ResultadoPegado(segmentos, errores, filas_ok=len(segmentos))


# ──────────────────────────────────────────────────────────────────────
#  2. CÁSCARA QT
# ──────────────────────────────────────────────────────────────────────

try:
    from qgis.PyQt.QtCore import pyqtSignal
    from qgis.PyQt.QtGui import QBrush, QColor
    from qgis.PyQt.QtWidgets import (QApplication, QCheckBox, QComboBox,
                                     QHBoxLayout, QLabel, QPlainTextEdit,
                                     QPushButton, QTableWidget,
                                     QTableWidgetItem, QVBoxLayout, QWidget)
    from .qt_compat import ItemIsEnabled, ItemIsSelectable, Stretch
    _QT = True
except ImportError:                                       # pragma: no cover
    _QT = False


if _QT:

    _OK = QColor(232, 245, 233)
    _MAL = QColor(255, 235, 238)
    _CAB = QColor(238, 238, 238)

    class TablaPegadoWidget(QWidget):
        """
        Pega la tabla, revisa el mapeo, mira la vista previa.

        Señal:
            cambiado(bool valido) — tras cada relectura.
        Uso:
            w.resultado().segmentos  ->  list[Segmento]
        """

        cambiado = pyqtSignal(bool)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._filas: list[list[str]] = []
            self._roles: list[str] = []
            self._resultado = ResultadoPegado([], {})
            self._bloqueo = False
            self._construir_ui()

        # ---------------------------------------------------------- UI
        def _construir_ui(self):
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)

            lay.addWidget(QLabel(
                "Pega la tabla de la memoria descriptiva (Excel, Word o PDF). "
                "Se detectan solas las columnas; corrígelas si hace falta."))

            self.txt = QPlainTextEdit()
            self.txt.setPlaceholderText(
                "V1\tV2\t0°00'\t2000.00\tParcela 9\n"
                "V2\tV3\t253°00'\t410.00\tTerrenos del Estado\n"
                "V3\tV4\t180°00'\t2000.00\tParcela 11")
            self.txt.setMaximumHeight(110)
            lay.addWidget(self.txt)

            fila = QHBoxLayout()
            self.btn_pegar = QPushButton("Pegar del portapapeles")
            self.btn_leer = QPushButton("Analizar")
            self.chk_cab = QCheckBox("La primera fila es encabezado")
            fila.addWidget(self.btn_pegar)
            fila.addWidget(self.btn_leer)
            fila.addWidget(self.chk_cab)
            fila.addStretch()
            lay.addLayout(fila)

            self.tabla = QTableWidget()
            self.tabla.setAlternatingRowColors(True)
            self.tabla.verticalHeader().setVisible(False)
            lay.addWidget(self.tabla, 1)

            self.lbl = QLabel()
            self.lbl.setWordWrap(True)
            lay.addWidget(self.lbl)

            self.btn_pegar.clicked.connect(self._del_portapapeles)
            self.btn_leer.clicked.connect(self.releer)
            self.chk_cab.toggled.connect(self._cambio_encabezado)
            self.txt.textChanged.connect(self._texto_cambio)

        # ------------------------------------------------------ acciones
        def _del_portapapeles(self):
            texto = QApplication.clipboard().text()
            if texto.strip():
                self.txt.setPlainText(texto)
                self.releer()
            else:
                self._avisar("El portapapeles está vacío.", False)

        def _texto_cambio(self):
            if not self._bloqueo:
                self.btn_leer.setDefault(True)

        def _cambio_encabezado(self):
            if self._filas and not self._bloqueo:
                self._roles = sugerir_roles(self._filas, self.chk_cab.isChecked())
                self._pintar()

        def releer(self):
            self._filas = dividir_tabla(self.txt.toPlainText())
            if not self._filas:
                self.tabla.clear()
                self.tabla.setRowCount(0)
                self.tabla.setColumnCount(0)
                self._avisar("Nada que interpretar. Pega una tabla.", False)
                return
            self._bloqueo = True
            self.chk_cab.setChecked(detectar_encabezado(self._filas))
            self._bloqueo = False
            self._roles = sugerir_roles(self._filas, self.chk_cab.isChecked())
            self._pintar()

        # -------------------------------------------------------- pintado
        def _pintar(self):
            filas, ancho = self._filas, len(self._filas[0])
            con_cab = self.chk_cab.isChecked()

            self.tabla.clear()
            self.tabla.setColumnCount(ancho)
            self.tabla.setRowCount(len(filas) + 1)      # +1: fila de combos

            etiquetas = [c if con_cab and c else f"Col {i + 1}"
                         for i, c in enumerate(filas[0])]
            self.tabla.setHorizontalHeaderLabels(etiquetas)

            for j in range(ancho):
                combo = QComboBox()
                for clave, texto in ROLES:
                    combo.addItem(texto, clave)
                combo.setCurrentIndex(
                    [r[0] for r in ROLES].index(self._roles[j]))
                combo.currentIndexChanged.connect(
                    lambda _, col=j, c=combo: self._rol_cambio(col, c))
                self.tabla.setCellWidget(0, j, combo)

            for i, fila in enumerate(filas):
                for j in range(ancho):
                    it = QTableWidgetItem(fila[j] if j < len(fila) else "")
                    it.setFlags(ItemIsEnabled | ItemIsSelectable)
                    if con_cab and i == 0:
                        it.setBackground(QBrush(_CAB))
                    self.tabla.setItem(i + 1, j, it)

            self.tabla.horizontalHeader().setSectionResizeMode(Stretch)
            self._validar()

        def _rol_cambio(self, col: int, combo):
            nuevo = combo.itemData(combo.currentIndex())
            if nuevo != IGNORAR:
                for j, r in enumerate(self._roles):      # rol único por columna
                    if j != col and r == nuevo:
                        self._roles[j] = IGNORAR
                        otro = self.tabla.cellWidget(0, j)
                        if otro is not None:
                            otro.blockSignals(True)
                            otro.setCurrentIndex(0)
                            otro.blockSignals(False)
            self._roles[col] = nuevo
            self._validar()

        def _validar(self):
            con_cab = self.chk_cab.isChecked()
            self._resultado = construir_segmentos(self._filas, self._roles, con_cab)

            desfase = 1 + (1 if con_cab else 0)
            n_datos = len(self._filas) - (1 if con_cab else 0)
            err_global = self._resultado.errores.get(-1)

            # Qué segmento salió de cada fila. Se reconstruye el emparejamiento
            # saltando filas vacías y filas con error, igual que hace
            # construir_segmentos, para no desalinear los tooltips.
            por_fila: dict[int, Segmento] = {}
            if not err_global:
                k = 0
                for i in range(n_datos):
                    fila = self._filas[i + (1 if con_cab else 0)]
                    if not any(c.strip() for c in fila):
                        continue
                    if i in self._resultado.errores:
                        continue
                    if k < len(self._resultado.segmentos):
                        por_fila[i] = self._resultado.segmentos[k]
                        k += 1

            jaz = self._roles.index(AZIMUT) if AZIMUT in self._roles else -1

            for i in range(n_datos):
                if err_global:
                    brocha = QBrush()                 # sin color: falta mapeo
                else:
                    brocha = QBrush(_MAL if i in self._resultado.errores else _OK)

                for j in range(self.tabla.columnCount()):
                    it = self.tabla.item(i + desfase, j)
                    if it is not None:
                        it.setBackground(brocha)
                        it.setToolTip("")

                if i in self._resultado.errores:
                    it0 = self.tabla.item(i + desfase, 0)
                    if it0 is not None:
                        it0.setToolTip(self._resultado.errores[i])

                # el azimut interpretado se muestra como rumbo: control visual
                seg = por_fila.get(i)
                if seg is not None and jaz >= 0:
                    it = self.tabla.item(i + desfase, jaz)
                    if it is not None:
                        it.setToolTip(
                            "Lindero natural (sin azimut)" if seg.es_natural
                            else f"{seg.azimut:.4f}°  ·  {seg.rumbo}")

            self._avisar(err_global or self._resultado.resumen(),
                         self._resultado.valido)

        def _avisar(self, texto: str, ok: bool):
            color = "#2e7d32" if ok else "#c62828"
            self.lbl.setText(f'<span style="color:{color}">{texto}</span>')
            self.cambiado.emit(ok)

        # ---------------------------------------------------------- API
        def resultado(self) -> ResultadoPegado:
            return self._resultado

        def segmentos(self) -> list[Segmento]:
            return self._resultado.segmentos

        def cargar_texto(self, texto: str):
            self.txt.setPlainText(texto)
            self.releer()
