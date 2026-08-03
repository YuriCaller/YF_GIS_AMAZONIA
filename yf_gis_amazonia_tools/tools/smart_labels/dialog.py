# -*- coding: utf-8 -*-
"""
Diálogo de Smart Labels — selector de estilo por tipo de geometría.

v3.0.4-dev: selectores de unidad (m²/ha/km², m/km) y método de cálculo
(campo precalculado / planar / elipsoidal) con vista previa usando
valores reales de la primera entidad de la capa.

Autor: Yuri F. Caller Córdova — TUCSA / gis-amazonia.pe
"""

import logging

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QLabel, QDialogButtonBox, QPushButton,
    QFrame, QSizePolicy
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes

from .label_engine import (
    ESTILOS_POLIGONO, ESTILOS_LINEA, ESTILOS_PUNTO,
    UNIDADES_AREA, UNIDADES_LONGITUD,
    detectar_campos_medida,
)


class SmartLabelsDialog(QDialog):
    """Diálogo selector de estilos de etiqueta."""

    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.geom_type = QgsWkbTypes.geometryType(layer.wkbType())
        self._campos_texto = [
            f.name() for f in layer.fields()
            if f.typeName() in ("String", "string", "text", "Text")
        ]
        self._campos_medida = detectar_campos_medida(layer)
        self._muestra = self._calcular_muestra_real()
        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    # Muestra real: mide la primera entidad de la capa (planar y
    # elipsoidal) para que la vista previa enseñe números verdaderos.
    # ──────────────────────────────────────────────────────────────────
    def _calcular_muestra_real(self):
        m = {"area_planar": None, "area_elip": None,
             "perim_planar": None, "perim_elip": None,
             "area_campo": None, "perim_campo": None}
        try:
            feat = next(self.layer.getFeatures(), None)
            if feat is None:
                return m
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                return m

            if self.geom_type == 2:          # Polígono
                m["area_planar"] = geom.area()          # m² en CRS proyectado
                m["perim_planar"] = geom.length()       # m
            elif self.geom_type == 1:        # Línea
                m["perim_planar"] = geom.length()

            # Elipsoidal con QgsDistanceArea explícita (WGS84)
            from qgis.core import QgsDistanceArea, QgsProject
            da = QgsDistanceArea()
            da.setSourceCrs(self.layer.crs(),
                            QgsProject.instance().transformContext())
            da.setEllipsoid("EPSG:7030")
            if self.geom_type == 2:
                m["area_elip"] = float(da.measureArea(geom))
                m["perim_elip"] = float(da.measurePerimeter(geom))
            elif self.geom_type == 1:
                m["perim_elip"] = float(da.measureLength(geom))

            # Valores de campos precalculados (convención: ha / m)
            if self._campos_medida.get("area"):
                v = feat[self._campos_medida["area"]]
                if v is not None:
                    m["area_campo"] = float(v) * 10000.0   # ha → m²
            campo_l = (self._campos_medida.get("perim")
                       or self._campos_medida.get("long"))
            if campo_l:
                v = feat[campo_l]
                if v is not None:
                    m["perim_campo"] = float(v)            # m
        except Exception:
            logging.getLogger(__name__).debug(
                "Smart Labels: no se pudo calcular muestra real",
                exc_info=True,
            )
        return m

    # ──────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle("YF · Smart Labels")
        self.setMinimumWidth(420)
        main = QVBoxLayout(self)
        main.setSpacing(10)

        # Cabecera
        header = QLabel(
            f"<b>Capa:</b> {self.layer.name()}<br>"
            f"<b>Tipo:</b> {self._geom_label()} &nbsp;|&nbsp; "
            f"<b>CRS:</b> {self.layer.crs().authid()}"
        )
        header.setFrameStyle(QFrame.Shape.StyledPanel)
        header.setContentsMargins(8, 6, 8, 6)
        main.addWidget(header)

        # Estilos disponibles según tipo
        grp = QGroupBox("Estilo de etiqueta")
        grp_layout = QVBoxLayout(grp)

        grp_layout.addWidget(QLabel("Estilo:"))
        self.combo_estilo = QComboBox()
        self._poblar_estilos()
        self.combo_estilo.currentIndexChanged.connect(self._on_estilo_changed)
        grp_layout.addWidget(self.combo_estilo)

        # Campo nombre (solo para polígono catastral y punto nombre)
        self.lbl_campo = QLabel("Campo de nombre:")
        self.combo_campo = QComboBox()
        self.combo_campo.addItem("── Sin campo ──", None)
        for c in self._campos_texto:
            self.combo_campo.addItem(c, c)
        self.lbl_campo.setVisible(False)
        self.combo_campo.setVisible(False)
        grp_layout.addWidget(self.lbl_campo)
        grp_layout.addWidget(self.combo_campo)
        main.addWidget(grp)

        # ── Grupo de medidas: unidades y método (v3.0.4-dev) ──
        self.grp_medidas = QGroupBox("Medidas")
        med_layout = QVBoxLayout(self.grp_medidas)

        fila_u = QHBoxLayout()
        self.lbl_uarea = QLabel("Unidad de área:")
        self.combo_uarea = QComboBox()
        for key, meta in UNIDADES_AREA.items():
            self.combo_uarea.addItem(meta["nombre"], key)
        self.combo_uarea.setCurrentIndex(
            list(UNIDADES_AREA.keys()).index("ha"))
        fila_u.addWidget(self.lbl_uarea)
        fila_u.addWidget(self.combo_uarea)

        self.lbl_ulong = QLabel("Unidad de perímetro:")
        self.combo_ulong = QComboBox()
        for key, meta in UNIDADES_LONGITUD.items():
            self.combo_ulong.addItem(meta["nombre"], key)
        fila_u.addWidget(self.lbl_ulong)
        fila_u.addWidget(self.combo_ulong)
        med_layout.addLayout(fila_u)

        med_layout.addWidget(QLabel("Método de cálculo:"))
        self.combo_metodo = QComboBox()
        tiene_campo = bool(self._campos_medida.get("area")
                           or self._campos_medida.get("perim")
                           or self._campos_medida.get("long"))
        if tiene_campo:
            etiqueta = "Campo precalculado ({})".format(
                " / ".join(v for v in (self._campos_medida.get("area"),
                                       self._campos_medida.get("perim"),
                                       self._campos_medida.get("long")) if v))
            self.combo_metodo.addItem(etiqueta, "campo")
        self.combo_metodo.addItem(
            "Planar — plano de proyección (uso catastral)", "planar")
        self.combo_metodo.addItem(
            "Elipsoidal — superficie del elipsoide (WGS84)", "elipsoidal")
        self.combo_metodo.setToolTip(
            "Planar: área/longitud sobre el plano de proyección UTM "
            "(la que debe cuadrar con planos y partidas registrales).\n"
            "Elipsoidal: sobre la superficie del elipsoide terrestre "
            "(medición 'real de terreno').\n"
            "Campo precalculado: usa los valores ya guardados en la capa."
        )
        med_layout.addWidget(self.combo_metodo)

        self.combo_uarea.currentIndexChanged.connect(self._refrescar_preview)
        self.combo_ulong.currentIndexChanged.connect(self._refrescar_preview)
        self.combo_metodo.currentIndexChanged.connect(self._refrescar_preview)
        main.addWidget(self.grp_medidas)

        # Preview de la expresión
        self.lbl_preview = QLabel()
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setStyleSheet(
            "background:#f5f5f5; border:1px solid #ccc; "
            "padding:6px; font-family:monospace; font-size:11px;"
        )
        main.addWidget(QLabel("Vista previa de etiqueta (1ª entidad de la capa):"))
        main.addWidget(self.lbl_preview)

        # Botones
        btn_layout = QHBoxLayout()
        self.btn_quitar = QPushButton("🚫  Quitar etiquetas")
        self.btn_quitar.clicked.connect(self._quitar)
        btn_layout.addWidget(self.btn_quitar)

        btn_box = QDialogButtonBox()
        btn_box.addButton("✅  Aplicar", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton("Cancelar",   QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        btn_layout.addWidget(btn_box)
        main.addLayout(btn_layout)

        self._on_estilo_changed(0)

    def _poblar_estilos(self):
        if self.geom_type == 2:   # Polígono
            for key, meta in ESTILOS_POLIGONO.items():
                self.combo_estilo.addItem(meta["nombre"], key)
        elif self.geom_type == 1:  # Línea
            for key, meta in ESTILOS_LINEA.items():
                self.combo_estilo.addItem(meta["nombre"], key)
        else:                      # Punto
            for key, meta in ESTILOS_PUNTO.items():
                self.combo_estilo.addItem(meta["nombre"], key)

    # ──────────────────────────────────────────────────────────────────
    # Reactividad
    # ──────────────────────────────────────────────────────────────────
    def _on_estilo_changed(self, idx):
        key = self.combo_estilo.currentData()
        if not key:
            return

        # Mostrar campo nombre si aplica
        necesita_campo = key in ("catastral", "nombre_campo")
        self.lbl_campo.setVisible(necesita_campo)
        self.combo_campo.setVisible(necesita_campo)

        # Grupo de medidas: solo estilos que miden algo
        usa_area = (self.geom_type == 2)
        usa_long = (self.geom_type == 2 or
                    key in ("distancia_azimut", "solo_distancia"))
        self.grp_medidas.setVisible(usa_area or usa_long)
        self.lbl_uarea.setVisible(usa_area)
        self.combo_uarea.setVisible(usa_area)
        self.lbl_ulong.setVisible(usa_long)
        self.combo_ulong.setVisible(usa_long)
        self.lbl_ulong.setText("Unidad de perímetro:" if self.geom_type == 2
                               else "Unidad de longitud:")

        self._refrescar_preview()

    def _fmt(self, valor_m2_o_m, unidades, key_unidad):
        """Formatea un valor base (m² o m) a la unidad elegida."""
        if valor_m2_o_m is None:
            return "—"
        u = unidades[key_unidad]
        factor = u.get("factor_m2", u.get("factor_m"))
        return f"{valor_m2_o_m * factor:.{u['dec']}f}{u['sufijo']}"

    def _refrescar_preview(self):
        key = self.combo_estilo.currentData()
        if not key:
            return

        met = self.combo_metodo.currentData() or "planar"
        ua = self.combo_uarea.currentData() or "ha"
        ul = self.combo_ulong.currentData() or "m"

        if met == "campo":
            area_b, perim_b = (self._muestra["area_campo"],
                               self._muestra["perim_campo"])
        elif met == "elipsoidal":
            area_b, perim_b = (self._muestra["area_elip"],
                               self._muestra["perim_elip"])
        else:
            area_b, perim_b = (self._muestra["area_planar"],
                               self._muestra["perim_planar"])

        area_txt = self._fmt(area_b, UNIDADES_AREA, ua)
        perim_txt = self._fmt(perim_b, UNIDADES_LONGITUD, ul)
        perim_corto = perim_txt.rstrip('.')

        previews = {
            # Polígono
            "tecnico":     ("ÁREA GEOREFERENCIADA\n"
                            f"Área: {area_txt}\n"
                            f"Perímetro: {perim_txt}"),
            "simple_area": f"Área: {area_txt}",
            "catastral":   ("NOMBRE DEL PREDIO\n"
                            f"Área: {area_txt}\n"
                            f"Perímetro: {perim_txt}"),
            "forestal":    f"ÁREA DE ESTUDIO\n{area_txt}",
            # Línea
            "distancia_azimut": f"L={perim_corto}\nAz=324°15'22\"",
            "solo_distancia":   perim_corto,
            "solo_azimut":      "324°15'22\"",
            # Punto
            "vertice":          "V-01  V-02  V-03",
            "coordenadas":      "353500.12\n8355500.34",
            "nombre_campo":     "[valor del campo seleccionado]",
        }
        self.lbl_preview.setText(previews.get(key, ""))

    def _quitar(self):
        from .label_engine import quitar_etiquetas
        quitar_etiquetas(self.layer)
        self.reject()

    def _geom_label(self):
        return {0: "Punto", 1: "Línea", 2: "Polígono"}.get(self.geom_type, "?")

    # ──────────────────────────────────────────────────────────────────
    # Getters
    # ──────────────────────────────────────────────────────────────────
    def get_estilo_key(self):
        return self.combo_estilo.currentData()

    def get_campo_nombre(self):
        return self.combo_campo.currentData()

    def get_unidad_area(self):
        return self.combo_uarea.currentData() or "ha"

    def get_unidad_longitud(self):
        return self.combo_ulong.currentData() or "m"

    def get_metodo(self):
        return self.combo_metodo.currentData() or "auto"
