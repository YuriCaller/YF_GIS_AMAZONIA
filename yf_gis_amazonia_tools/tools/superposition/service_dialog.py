# -*- coding: utf-8 -*-
"""
YF GIS Amazonia — Análisis de Superposición
Selector de geoservicios oficiales.

Presenta el catálogo (service_catalog) como un árbol con casillas,
agrupado por país y servicio. Permite probar la conexión antes de
analizar y abrir el JSON para editarlo.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import os

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QColor, QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout,
)

from . import service_catalog, wfs_source


class ServiciosDialog(QDialog):
    """Elige qué capas de geoservicios entran al análisis."""

    def __init__(self, parent=None, seleccion_previa=None):
        super().__init__(parent)
        self.setWindowTitle("Geoservicios oficiales")
        self.resize(720, 560)
        self.catalogo = service_catalog.CatalogoServicios.cargar()
        self._seleccion_previa = set(seleccion_previa or [])
        self.capas_elegidas = []
        self._build_ui()
        self._poblar()

    # ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        main = QVBoxLayout(self)

        main.addWidget(QLabel(
            "Marque las capas oficiales contra las que desea evaluar el "
            "predio.\nLa descarga se acota automáticamente al área del "
            "predio."))

        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels(["Capa", "Vía", "Verificado"])
        self.arbol.setColumnWidth(0, 420)
        self.arbol.itemChanged.connect(self._on_item_cambiado)
        main.addWidget(self.arbol, 1)

        fila = QHBoxLayout()
        btn_todo = QPushButton("Marcar todo")
        btn_todo.clicked.connect(lambda: self._marcar_todo(True))
        fila.addWidget(btn_todo)
        btn_nada = QPushButton("Desmarcar todo")
        btn_nada.clicked.connect(lambda: self._marcar_todo(False))
        fila.addWidget(btn_nada)
        fila.addStretch(1)
        self.btn_probar = QPushButton("Probar conexión de lo marcado")
        self.btn_probar.clicked.connect(self._probar)
        fila.addWidget(self.btn_probar)
        btn_restaurar = QPushButton("Restaurar de fábrica")
        btn_restaurar.setToolTip(
            "Devuelve TODOS los servicios precargados a la definición que "
            "trae el plugin. No afecta a los servicios que usted añadió.")
        btn_restaurar.clicked.connect(self._restaurar_fabrica)
        fila.addWidget(btn_restaurar)
        btn_json = QPushButton("Abrir catálogo (JSON)...")
        btn_json.clicked.connect(self._abrir_json)
        fila.addWidget(btn_json)
        main.addLayout(fila)

        self.txt_estado = QTextEdit()
        self.txt_estado.setReadOnly(True)
        self.txt_estado.setMaximumHeight(120)
        main.addWidget(self.txt_estado)

        self.lbl_legal = QLabel()
        self.lbl_legal.setWordWrap(True)
        self.lbl_legal.setStyleSheet("color: #8a6d00;")
        main.addWidget(self.lbl_legal)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        main.addWidget(botones)

    # ──────────────────────────────────────────────────────────────
    def _poblar(self):
        self.arbol.blockSignals(True)
        self.arbol.clear()
        for grupo in self.catalogo.grupos():
            n_grupo = QTreeWidgetItem(self.arbol, [grupo, "", ""])
            n_grupo.setFlags(n_grupo.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            n_grupo.setCheckState(0, Qt.CheckState.Unchecked)
            n_grupo.setExpanded(True)

            for servicio in self.catalogo.servicios(grupo):
                n_srv = QTreeWidgetItem(n_grupo, [servicio, "", ""])
                n_srv.setFlags(n_srv.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                n_srv.setCheckState(0, Qt.CheckState.Unchecked)
                n_srv.setExpanded(True)

                for capa in self.catalogo.capas(grupo=grupo,
                                                solo_activas=False):
                    if capa.servicio != servicio:
                        continue
                    _, provider = wfs_source.uri_para(capa)
                    via = {"WFS": "WFS",
                           "arcgisfeatureserver": "REST"}.get(provider, "—")
                    n_capa = QTreeWidgetItem(
                        n_srv, [capa.titulo, via, capa.verificado or "no"])
                    n_capa.setFlags(n_capa.flags() |
                                    Qt.ItemFlag.ItemIsUserCheckable)
                    clave = capa.nombre_completo
                    marcado = (clave in self._seleccion_previa
                               if self._seleccion_previa
                               else bool(capa.titulo and provider))
                    if provider is None:
                        marcado = False
                        n_capa.setDisabled(True)
                        n_capa.setToolTip(
                            0, "Entrada de catálogo incompleta.")
                    n_capa.setCheckState(
                        0, Qt.CheckState.Checked if marcado
                        else Qt.CheckState.Unchecked)
                    n_capa.setData(0, Qt.ItemDataRole.UserRole, capa)
                    if not capa.verificado:
                        n_capa.setForeground(2, QColor(180, 80, 0))
                        n_capa.setToolTip(
                            2, "Sin fecha de verificación: el endpoint no "
                               "ha sido comprobado.")
        self.arbol.blockSignals(False)
        self._actualizar_legal()
        self._avisar_novedades()

    # ──────────────────────────────────────────────────────────────
    def _iter_hojas(self):
        raiz = self.arbol.invisibleRootItem()
        for i in range(raiz.childCount()):
            g = raiz.child(i)
            for j in range(g.childCount()):
                s = g.child(j)
                for k in range(s.childCount()):
                    yield s.child(k)

    def _on_item_cambiado(self, item, columna):
        if columna != 0:
            return
        self.arbol.blockSignals(True)
        # Padre marcado propaga a hijos.
        if item.childCount():
            for i in range(item.childCount()):
                hijo = item.child(i)
                if not hijo.isDisabled():
                    hijo.setCheckState(0, item.checkState(0))
                if hijo.childCount():
                    for j in range(hijo.childCount()):
                        nieto = hijo.child(j)
                        if not nieto.isDisabled():
                            nieto.setCheckState(0, item.checkState(0))
        self.arbol.blockSignals(False)
        self._actualizar_legal()

    def _marcar_todo(self, marcar):
        self.arbol.blockSignals(True)
        estado = Qt.CheckState.Checked if marcar else Qt.CheckState.Unchecked
        for hoja in self._iter_hojas():
            if not hoja.isDisabled():
                hoja.setCheckState(0, estado)
        self.arbol.blockSignals(False)
        self._actualizar_legal()

    def _avisar_novedades(self):
        """Informa de lo que cambió respecto del catálogo guardado."""
        mensajes = []
        for nombre in getattr(self.catalogo, "incorporados", []):
            mensajes.append("+ Servicio nuevo disponible: {}".format(nombre))
        for grupo, srv, campo, mio, fab in self.catalogo.divergencias_con_fabrica():
            mensajes.append(
                "! '{}' tiene {} distinto al del plugin.\n"
                "    su catálogo: {}\n"
                "    plugin      : {}\n"
                "    Use «Restaurar de fábrica» si el suyo es antiguo."
                .format(srv, campo, mio or "(vacío)", fab or "(vacío)"))
        if mensajes:
            self.txt_estado.append("\n".join(mensajes))
            self.txt_estado.append(
                "\nLos servicios nuevos se guardarán al pulsar Aceptar.")

    def _capas_marcadas(self):
        elegidas = []
        for hoja in self._iter_hojas():
            if hoja.checkState(0) == Qt.CheckState.Checked:
                capa = hoja.data(0, Qt.ItemDataRole.UserRole)
                if capa is not None:
                    elegidas.append(capa)
        return elegidas

    def _actualizar_legal(self):
        marcadas = self._capas_marcadas()
        textos = self.catalogo.advertencias_legales(marcadas)
        self.lbl_legal.setText("\n\n".join(textos) if textos else "")

    # ──────────────────────────────────────────────────────────────
    def _probar(self):
        marcadas = self._capas_marcadas()
        if not marcadas:
            QMessageBox.information(self, "Sin selección",
                                    "Marque al menos una capa.")
            return
        self.txt_estado.clear()
        self.btn_probar.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        ok = fallo = 0
        try:
            for capa in marcadas:
                ce = wfs_source.capa_desde_servicio(capa)
                if ce is None:
                    self.txt_estado.append(
                        "✗ {} — entrada incompleta".format(
                            capa.nombre_completo))
                    fallo += 1
                    continue
                bien, msg = wfs_source.validar_capa(ce)
                self.txt_estado.append(
                    "{} {} — {}".format("✓" if bien else "✗",
                                        capa.titulo, msg))
                ok += bien
                fallo += (not bien)
                QApplication.processEvents()
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_probar.setEnabled(True)
        self.txt_estado.append(
            "\n{} disponible(s), {} con problema(s).".format(ok, fallo))

    def _restaurar_fabrica(self):
        from qgis.PyQt.QtWidgets import QMessageBox as _QMB
        resp = _QMB.question(
            self, "Restaurar de fábrica",
            "Se devolverán los servicios precargados (SERFOR, SERNANP, "
            "MIDAGRI) a la definición del plugin.\n\nSus servicios propios "
            "no se tocan. ¿Continuar?")
        if resp != _QMB.StandardButton.Yes:
            return
        n = 0
        for grupo, servicios in service_catalog.CATALOGO_FABRICA.get(
                "grupos", {}).items():
            for nombre in servicios:
                if self.catalogo.restaurar_servicio(grupo, nombre):
                    n += 1
        self._poblar()
        self.txt_estado.append(
            "{} servicio(s) restaurado(s) a la definición del plugin."
            .format(n))

    def _abrir_json(self):
        ruta = service_catalog.ruta_catalogo()
        if not os.path.exists(ruta):
            resp = QMessageBox.question(
                self, "Catálogo",
                "Aún no existe el archivo editable; se está usando el "
                "catálogo de fábrica.\n\n¿Crearlo ahora en:\n{}?".format(ruta))
            if resp != QMessageBox.StandardButton.Yes:
                return
            try:
                self.catalogo.guardar(ruta)
            except OSError as e:
                QMessageBox.critical(self, "Catálogo",
                                     "No se pudo escribir:\n{}".format(e))
                return
        # QDesktopServices abre el gestor de archivos del sistema sin
        # lanzar procesos externos: evita subprocess y es multiplataforma.
        carpeta = os.path.dirname(ruta)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(carpeta)):
            QMessageBox.information(self, "Catálogo",
                                    "El catálogo está en:\n{}".format(ruta))

    # ──────────────────────────────────────────────────────────────
    def _aceptar(self):
        marcadas = self._capas_marcadas()
        if not marcadas:
            QMessageBox.information(
                self, "Sin selección",
                "Marque al menos una capa, o cancele.")
            return
        sin_verificar = [c.titulo for c in marcadas if not c.verificado]
        if sin_verificar:
            resp = QMessageBox.question(
                self, "Capas sin verificar",
                "Estas capas no tienen fecha de verificación en el "
                "catálogo:\n\n  {}\n\nSi el endpoint es incorrecto el "
                "análisis las reportará como no evaluadas.\n\n¿Continuar?"
                .format("\n  ".join(sin_verificar)))
            if resp != QMessageBox.StandardButton.Yes:
                return
        self.capas_elegidas = marcadas
        if getattr(self.catalogo, "incorporados", None):
            try:
                self.catalogo.guardar()
            except OSError:
                pass  # no es crítico: la fusión se repite en el próximo inicio
        self.accept()

    def capas_encontradas(self):
        """`CapaEncontrada` listas para overlap_engine.analizar(capas=...)."""
        salida = []
        for capa in self.capas_elegidas:
            ce = wfs_source.capa_desde_servicio(capa)
            if ce is not None:
                salida.append(ce)
        return salida

    def claves_elegidas(self):
        return [c.nombre_completo for c in self.capas_elegidas]

    def advertencias(self):
        return self.catalogo.advertencias_legales(self.capas_elegidas)
