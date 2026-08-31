# -*- coding: utf-8 -*-
"""
Diálogo Memoria Descriptiva v3.1

LÓGICA DE DATOS DEL SOLICITANTE:
─────────────────────────────────
  MODO ÚNICO:
    • groupSolicitante ACTIVO — el usuario escribe nombre y DNI manualmente
    • Esos datos van a TODAS las secciones del documento

  MODO ATLAS (completo o selección):
    • groupSolicitante DESACTIVADO (se atenúa)
    • Aparecen dos combos para elegir el CAMPO de la capa de polígonos
      que contiene el nombre y DNI de cada propietario
    • En cada iteración se lee el valor del campo para ESE polígono
    • Los datos comunes (ubicación, datum, generalidades, colindantes)
      se ingresan UNA sola vez y se repiten en todas las memorias

DATOS QUE ITERAN con cada polígono (atlas):
  - Nombre del propietario    ← campo elegido en la BD
  - DNI del propietario       ← campo elegido en la BD
  - Nombre del predio/archivo ← campo elegido en la BD

DATOS QUE SE REPITEN en todas las memorias (atlas):
  - Ubicación (sector, distrito, provincia, departamento, zona UTM)
  - Generalidades
  - Info del mapa (datum, elipsoide, grillado)
  - Colindantes (manual o auto-detectados)
"""

import os
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsVectorLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'memoria_descriptiva_dialog_base.ui'))


class MemoriaDescriptivaDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self._crear_panel_atlas_solicitante()  # Panel que reemplaza al solicitante en atlas
        self._crear_panel_predio()             # Panel "Identificación del Predio"
        self._crear_tab_modo()                 # Pestaña "Modo de Trabajo"
        self._crear_tab_campos()               # Pestaña "Campos"

        # ── Conexiones ──────────────────────────────────────────────────────
        self.chkDetectarColindantes.toggled.connect(
            lambda c: self.groupColindantesManual.setEnabled(not c))
        self.chkTextoDefault.toggled.connect(
            lambda c: self.txtGeneralidades.setReadOnly(c))

        self.cboPoligonos.currentIndexChanged.connect(self.actualizar_campos_poligono)
        self.cboPuntos.currentIndexChanged.connect(self.actualizar_campos_puntos)

        # Cambio de modo → actualizar UI
        self.rbUnico.toggled.connect(self._on_modo_changed)
        self.rbAtlasCompleto.toggled.connect(self._on_modo_changed)
        self.rbAtlasSeleccion.toggled.connect(self._on_modo_changed)

        # Estado inicial
        self.groupColindantesManual.setEnabled(not self.chkDetectarColindantes.isChecked())
        self.txtGeneralidades.setReadOnly(self.chkTextoDefault.isChecked())
        self._on_modo_changed()  # Aplica estado inicial según modo seleccionado
        self._reorganizar_ui()   # Fase 2: títulos, duplicados, botones
        self._configurar_generalidades()  # Fase 2: método/equipo de levantamiento
        self._instalar_ayudas()           # Fase 2: tooltips explicativos
        self._crear_selectores_bd()       # Combos 'desde la tabla' en cada campo

    # =========================================================================
    # PANEL ATLAS-SOLICITANTE (se inserta debajo del groupSolicitante)
    # =========================================================================

    def _crear_panel_atlas_solicitante(self):
        """
        Crea un panel que aparece SOLO en modo atlas, debajo del groupSolicitante,
        con combos para elegir el campo de nombre y DNI de la capa de polígonos.
        """
        # Encontrar el layout de la pestaña Datos Básicos
        tab_layout = self.tabDatosBasicos.layout()

        # Panel contenedor
        self.panelAtlasSolicitante = QtWidgets.QGroupBox(
            "📋  Datos del Solicitante — Modo Atlas")
        self.panelAtlasSolicitante.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #17375E; "
            "background: #EAF4EA; border: 2px solid #2E6E3E; "
            "border-radius: 6px; margin-top: 8px; padding-top: 8px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; }")

        form = QtWidgets.QFormLayout()
        form.setSpacing(8)

        # Nota explicativa
        lbl_nota = QtWidgets.QLabel(
            "<i>En modo Atlas, el nombre y DNI se leen automáticamente<br>"
            "del campo de la capa de polígonos para cada predio.</i>")
        lbl_nota.setWordWrap(True)
        lbl_nota.setStyleSheet("color: #2E6E3E; font-size: 10px; padding: 4px;")
        form.addRow(lbl_nota)

        # Combo: campo nombre/propietario
        self.cboAtlasCampoNombre = QtWidgets.QComboBox()
        self.cboAtlasCampoNombre.setToolTip(
            "Campo de la capa de polígonos con el nombre del propietario.\n"
            "Ejemplo: NombresApellidos, nombre, titular")
        form.addRow("Campo Nombre / Propietario:", self.cboAtlasCampoNombre)

        # Combo: campo DNI
        self.cboAtlasCampoDNI = QtWidgets.QComboBox()
        self.cboAtlasCampoDNI.setToolTip(
            "Campo con el DNI o documento de identidad.\n"
            "Déjalo en '-- Sin DNI --' si no existe en la capa.")
        form.addRow("Campo DNI:", self.cboAtlasCampoDNI)

        # Vista previa del primer predio
        self.lblAtlasPreviewPredio = QtWidgets.QLabel("")
        self.lblAtlasPreviewPredio.setStyleSheet(
            "color: #555; font-size: 10px; padding: 2px 4px;")
        self.cboAtlasCampoNombre.currentIndexChanged.connect(self._actualizar_preview_predio)
        form.addRow("Vista previa:", self.lblAtlasPreviewPredio)

        self.panelAtlasSolicitante.setLayout(form)

        # Insertar en la posición 0 (encima del groupSolicitante) en el tab
        tab_layout.insertWidget(0, self.panelAtlasSolicitante)
        self.panelAtlasSolicitante.setVisible(False)  # Oculto hasta activar atlas

    def _crear_panel_predio(self):
        """Panel de identificación del predio: nombre y condición.

        El nombre del predio es distinto del nombre del titular. Puede
        venir de un campo de la capa de polígonos (recomendado en modo
        atlas, donde cada predio tiene el suyo) o escribirse a mano.
        La condición (matriz / fracción / remanente) es opcional.
        """
        tab_layout = self.tabDatosBasicos.layout()

        self.panelPredio = QtWidgets.QGroupBox("Identificación del Predio")
        self.panelPredio.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #17375E; "
            "background: #F4F0E6; border: 2px solid #17375E; "
            "border-radius: 6px; margin-top: 8px; padding-top: 8px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; }")

        form = QtWidgets.QFormLayout()
        form.setSpacing(8)

        lbl_nota = QtWidgets.QLabel(
            "<i>El nombre del predio aparece en el encabezado del documento.<br>"
            "No es el nombre del titular, que va en Datos del Solicitante.</i>")
        lbl_nota.setWordWrap(True)
        lbl_nota.setStyleSheet("color: #17375E; font-size: 10px; padding: 4px;")
        form.addRow(lbl_nota)

        self.cboCampoNombrePredio = QtWidgets.QComboBox()
        self.cboCampoNombrePredio.setToolTip(
            "Campo de la capa de polígonos con el nombre del predio.\n"
            "Ejemplo: PREDIO, nom_predio, denominacion.\n"
            "Déjalo en '-- Sin campo --' para escribirlo a mano abajo.")
        self.cboCampoNombrePredio.currentIndexChanged.connect(
            self._actualizar_preview_nombre_predio)
        form.addRow("Campo Nombre del Predio:", self.cboCampoNombrePredio)

        self.txtNombrePredio = QtWidgets.QLineEdit()
        self.txtNombrePredio.setPlaceholderText("Ej.: Las Mercedes")
        self.txtNombrePredio.setToolTip(
            "Nombre del predio escrito a mano.\n"
            "Solo se usa si no seleccionaste un campo arriba.")
        form.addRow("...o nombre manual:", self.txtNombrePredio)

        self.cboTipoPredio = QtWidgets.QComboBox()
        self.cboTipoPredio.addItem("-- Sin condición --", "")
        self.cboTipoPredio.addItem("Predio Matriz", "MATRIZ")
        self.cboTipoPredio.addItem("Predio Fracción", "FRACCIÓN")
        self.cboTipoPredio.addItem("Predio Remanente", "REMANENTE")
        self.cboTipoPredio.setToolTip(
            "Condición del predio en el saneamiento.\n"
            "Aparece en el encabezado: 'PREDIO MATRIZ: LAS MERCEDES'.")
        form.addRow("Condición:", self.cboTipoPredio)

        self.lblPreviewNombrePredio = QtWidgets.QLabel("")
        self.lblPreviewNombrePredio.setStyleSheet(
            "color: #555; font-size: 10px; padding: 2px 4px;")
        self.cboTipoPredio.currentIndexChanged.connect(
            self._actualizar_preview_nombre_predio)
        self.txtNombrePredio.textChanged.connect(
            self._actualizar_preview_nombre_predio)
        form.addRow("Encabezado:", self.lblPreviewNombrePredio)

        self.panelPredio.setLayout(form)
        tab_layout.insertWidget(0, self.panelPredio)

    def _actualizar_preview_nombre_predio(self):
        """Muestra cómo quedará el encabezado del documento."""
        nombre = ""
        campo = self.cboCampoNombrePredio.currentData()
        if campo:
            lid = self.cboPoligonos.currentData()
            layer = QgsProject.instance().mapLayer(lid) if lid else None
            if layer:
                feats = list(layer.getFeatures())
                if feats:
                    try:
                        v = feats[0][campo]
                        nombre = str(v).strip() if v else ""
                    except Exception:
                        nombre = ""
        if not nombre:
            nombre = self.txtNombrePredio.text().strip()
        if not nombre:
            nombre = self.txtSector.text().strip()

        tipo = self.cboTipoPredio.currentData() or ""
        etiqueta = "PREDIO {}".format(tipo) if tipo else "PREDIO"
        if nombre:
            texto = "{}: {}".format(etiqueta, nombre.upper())
        elif tipo:
            texto = etiqueta
        else:
            texto = "(sin subtítulo)"
        self.lblPreviewNombrePredio.setText("<b>{}</b>".format(texto))

    # =========================================================================
    # SELECTORES "DESDE LA TABLA" (solicitante y ubicacion)
    # =========================================================================

    # clave interna -> (widget, etiqueta, candidatos de autodeteccion)
    CAMPOS_BD = [
        ('nombre',       'txtNombre',       'Nombre',
         ['NombresApellidos', 'nombre', 'nom_tit', 'propietario', 'titular']),
        ('dni',          'txtDNI',          'DNI',
         ['dni', 'DNI', 'doc', 'documento', 'nro_doc']),
        ('sector',       'txtSector',       'Sector',
         ['SECTOR', 'sector', 'nom_sector', 'localidad', 'CASERIO', 'caserio']),
        ('zona',         'txtZona',         'Zona',
         ['ZONA', 'zona', 'nom_zona']),
        ('distrito',     'txtDistrito',     'Distrito',
         ['DISTRITO', 'distrito', 'nom_dist', 'DIST']),
        ('provincia',    'txtProvincia',    'Provincia',
         ['PROVINCIA', 'provincia', 'nom_prov', 'PROV']),
        ('departamento', 'txtDepartamento', 'Departamento',
         ['DEPARTAMEN', 'DEPARTAMENTO', 'departamento', 'nom_dpto', 'DPTO']),
    ]

    def _crear_selectores_bd(self):
        """Coloca un combo junto a cada campo de texto para tomar su valor
        de la tabla de atributos.

        El QLineEdit no se toca: se saca de su fila del QFormLayout y se
        reinserta dentro de un contenedor horizontal junto al combo. Asi no
        hay que modificar el .ui y los nombres de widget siguen siendo los
        mismos para el resto del codigo.
        """
        self._combos_bd = {}

        for clave, attr, etiqueta, _cands in self.CAMPOS_BD:
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            contenedor = widget.parentWidget()
            layout = contenedor.layout() if contenedor else None
            if not isinstance(layout, QtWidgets.QFormLayout):
                continue

            fila, rol = layout.getWidgetPosition(widget)
            if fila < 0:
                continue

            combo = QtWidgets.QComboBox()
            combo.setMinimumWidth(150)
            combo.setToolTip(
                "Tomar {} desde un campo de la capa de poligonos.\n"
                "En modo atlas cada predio usa su propio valor.\n"
                "Deja '-- Manual --' para escribirlo a mano.".format(etiqueta.lower()))
            combo.addItem('-- Manual --', None)
            combo.currentIndexChanged.connect(
                lambda _i, c=clave: self._on_campo_bd_changed(c))

            caja = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(caja)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            layout.removeWidget(widget)
            h.addWidget(widget, 3)
            h.addWidget(combo, 2)
            layout.setWidget(fila, QtWidgets.QFormLayout.FieldRole, caja)

            self._combos_bd[clave] = combo

    def _on_campo_bd_changed(self, clave):
        """Al elegir un campo, el cuadro muestra el valor del primer predio
        y pasa a solo lectura; al volver a manual, se libera."""
        combo = self._combos_bd.get(clave)
        attrs = dict((c, a) for c, a, _e, _x in self.CAMPOS_BD)
        widget = getattr(self, attrs[clave], None)
        if combo is None or widget is None:
            return

        campo = combo.currentData()
        if not campo:
            widget.setReadOnly(False)
            widget.setStyleSheet("")
            widget.setPlaceholderText("")
            return

        valor = self._valor_primer_feature(campo)
        widget.setText(valor or "")
        widget.setReadOnly(True)
        widget.setStyleSheet("background: #EDF2F7; color: #17375E;")
        widget.setPlaceholderText("(desde el campo {})".format(campo))
        if hasattr(self, 'lblPreviewNombrePredio'):
            self._actualizar_preview_nombre_predio()

    def _valor_primer_feature(self, campo):
        """Valor del campo en el primer poligono, como vista previa."""
        lid = self.cboPoligonos.currentData()
        if not lid or not campo:
            return ""
        layer = QgsProject.instance().mapLayer(lid)
        if not layer:
            return ""
        try:
            feats = list(layer.getFeatures())
            if not feats:
                return ""
            v = feats[0][campo]
            return str(v).strip() if v not in (None, "") else ""
        except Exception:
            return ""

    def _poblar_combos_bd(self, campos):
        """Rellena los combos con los campos de la capa de poligonos y
        autodetecta el mas probable para cada uno."""
        if not hasattr(self, '_combos_bd'):
            return
        for clave, _attr, _etiqueta, candidatos in self.CAMPOS_BD:
            combo = self._combos_bd.get(clave)
            if combo is None:
                continue
            anterior = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('-- Manual --', None)
            for c in campos:
                combo.addItem(c, c)
            if anterior and anterior in campos:
                combo.setCurrentIndex(combo.findData(anterior))
            combo.blockSignals(False)
            if not anterior:
                for cand in candidatos:
                    idx = combo.findData(cand)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                        break

    def _actualizar_preview_predio(self):
        """Muestra un ejemplo con el valor del primer polígono."""
        lid = self.cboPoligonos.currentData()
        if not lid: return
        layer = QgsProject.instance().mapLayer(lid)
        if not layer: return
        campo = self.cboAtlasCampoNombre.currentData()
        if not campo: return
        feats = list(layer.getFeatures())
        if not feats: return
        try:
            val = feats[0][campo]
            self.lblAtlasPreviewPredio.setText(
                "1er predio: <b>{}</b>".format(str(val) if val else '(vacío)'))
        except Exception:
            self.lblAtlasPreviewPredio.setText("")

    # =========================================================================
    # PESTAÑA MODO DE TRABAJO
    # =========================================================================

    def _crear_tab_modo(self):
        self.tabModo = QtWidgets.QWidget()
        self.tabWidget.insertTab(1, self.tabModo, "📋 Modo de Trabajo")

        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        cont = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(cont)
        scroll.setWidget(cont)
        outer = QtWidgets.QVBoxLayout(self.tabModo)
        outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(scroll)

        # ── Selector de modo ──────────────────────────────────────────────────
        grp_modo = QtWidgets.QGroupBox("¿Cuántas memorias quieres generar?")
        grp_modo.setStyleSheet("QGroupBox { font-weight: bold; }")
        vl = QtWidgets.QVBoxLayout()

        self.rbUnico = QtWidgets.QRadioButton(
            "🔵  Polígono único  —  1 memoria para el polígono seleccionado")
        self.rbAtlasCompleto = QtWidgets.QRadioButton(
            "🟢  Atlas completo  —  1 memoria por CADA polígono de la capa")
        self.rbAtlasSeleccion = QtWidgets.QRadioButton(
            "🟡  Atlas selección  —  1 memoria por cada polígono SELECCIONADO en QGIS")

        self.rbUnico.setChecked(True)
        for rb in [self.rbUnico, self.rbAtlasCompleto, self.rbAtlasSeleccion]:
            rb.setStyleSheet("font-size: 11px; padding: 5px;")
            vl.addWidget(rb)

        grp_modo.setLayout(vl); layout.addWidget(grp_modo)

        # ── Relación polígono ↔ puntos ────────────────────────────────────────
        grp_rel = QtWidgets.QGroupBox(
            "Relación entre capas  (¿qué campo vincula polígonos con puntos?)")
        fl = QtWidgets.QFormLayout()

        lbl = QtWidgets.QLabel(
            "<b>El plugin filtra los puntos de cada polígono usando un campo compartido.</b><br>"
            "<i>Ejemplo con tus capas:</i><br>"
            "• <b>AREA_TOTAL</b>: campo <b>fid</b> = 1, 2, 3, 4, 5, 6<br>"
            "• <b>Puntos</b>: campo <b>ID_Poligono</b> = 1,1,1... 2,2,2... 3,3,3...")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "background: #E8F4FD; padding: 8px; border-radius: 4px; "
            "border: 1px solid #AED6F1; font-size: 10px;")
        fl.addRow(lbl)

        self.cboCampoIdPoligono = QtWidgets.QComboBox()
        self.cboCampoIdPoligono.setToolTip("Campo ID único de cada polígono (ej: fid)")
        fl.addRow("Campo ID del polígono:", self.cboCampoIdPoligono)

        self.cboCampoRelPuntos = QtWidgets.QComboBox()
        self.cboCampoRelPuntos.setToolTip("Campo en la capa de Puntos que contiene el ID del polígono (ej: ID_Poligono)")
        fl.addRow("Campo relación en Puntos:", self.cboCampoRelPuntos)

        grp_rel.setLayout(fl); layout.addWidget(grp_rel)

        # ── Previsualización ──────────────────────────────────────────────────
        self.grpPreview = QtWidgets.QGroupBox("Previsualización del Atlas")
        vl2 = QtWidgets.QVBoxLayout()
        self.lblPreview = QtWidgets.QLabel(
            "<i>Activa modo Atlas para ver los predios que se procesarán.</i>")
        self.lblPreview.setWordWrap(True)
        self.lblPreview.setStyleSheet("color: #666; padding: 4px; font-size: 10px;")
        self.btnPreview = QtWidgets.QPushButton("👁  Ver predios a procesar")
        self.btnPreview.clicked.connect(self._previsualizar)
        self.btnPreview.setEnabled(False)
        vl2.addWidget(self.lblPreview); vl2.addWidget(self.btnPreview)
        self.grpPreview.setLayout(vl2); layout.addWidget(self.grpPreview)

        layout.addStretch()

    # =========================================================================
    # PESTAÑA CAMPOS
    # =========================================================================

    def _crear_tab_campos(self):
        self.tabCampos = QtWidgets.QWidget()
        self.tabWidget.addTab(self.tabCampos, "⚙ Campos")

        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        cont = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(cont)
        scroll.setWidget(cont)
        outer = QtWidgets.QVBoxLayout(self.tabCampos)
        outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(scroll)

        lbl = QtWidgets.QLabel(
            "<b>Campos de datos:</b> deja <i>-- Automático --</i> para detección automática.<br>"
            "Distancias y azimuts se calculan geométricamente si no existen como atributos.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: #EAF4EA; padding: 8px; border-radius: 4px;")
        layout.addWidget(lbl)

        # Campos en Puntos
        grp_p = QtWidgets.QGroupBox("Campos en la Capa de Puntos")
        fp = QtWidgets.QFormLayout()
        self.cboCampoVerticeID  = QtWidgets.QComboBox()
        self.cboCampoOrdenPunto = QtWidgets.QComboBox()
        self.cboCampoDistancia  = QtWidgets.QComboBox()
        self.cboCampoAzimut     = QtWidgets.QComboBox()
        self.cboCampoEste       = QtWidgets.QComboBox()
        self.cboCampoNorte      = QtWidgets.QComboBox()
        self.cboCampoLado       = QtWidgets.QComboBox()
        fp.addRow("ID / Etiqueta vértice:",   self.cboCampoVerticeID)
        fp.addRow("Orden / Secuencia:",        self.cboCampoOrdenPunto)
        fp.addRow("Distancia (m):",            self.cboCampoDistancia)
        fp.addRow("Azimut (°):",               self.cboCampoAzimut)
        fp.addRow("Coordenada Este / X:",      self.cboCampoEste)
        fp.addRow("Coordenada Norte / Y:",     self.cboCampoNorte)
        fp.addRow("Nombre del Lado:",          self.cboCampoLado)
        grp_p.setLayout(fp); layout.addWidget(grp_p)

        # Campos en Polígonos
        grp_pol = QtWidgets.QGroupBox("Campos en la Capa de Polígonos")
        fpol = QtWidgets.QFormLayout()
        self.cboCampoArea      = QtWidgets.QComboBox()
        self.cboCampoPerimetro = QtWidgets.QComboBox()
        fpol.addRow("Área (ha):",        self.cboCampoArea)
        fpol.addRow("Perímetro (m):",    self.cboCampoPerimetro)
        grp_pol.setLayout(fpol); layout.addWidget(grp_pol)
        self._fpol_campos = fpol  # referencia para mudar Nombre/DNI (Fase 2)

        # ── Formato del documento (Fase 2) ───────────────────────────────
        grp_fmt = QtWidgets.QGroupBox("Formato del documento")
        ff = QtWidgets.QFormLayout()
        self.cboPatronVertice = QtWidgets.QComboBox()
        for lbl, val in [
                ("V-1, V-2, V-3 ...",  "V-{n}"),
                ("V1, V2, V3 ...",     "V{n}"),
                ("V01, V02, V03 ...",  "V{nn}"),
                ("P-1, P-2, P-3 ...",  "P-{n}"),
                ("P01, P02, P03 ...",  "P{nn}")]:
            self.cboPatronVertice.addItem(lbl, val)
        self.cboFormatoAzimut = QtWidgets.QComboBox()
        for lbl, val in [
                ("Decimal, 1 decimal - igual al plano (110.2)", ("decimal", 1)),
                ("Decimal, 2 decimales (110.25)",               ("decimal", 2)),
                ("Sexagesimal GMS (110\u00b012'30\")",             ("gms", 0)),
                ("Ambos: decimal (GMS)",                        ("ambos", 1))]:
            self.cboFormatoAzimut.addItem(lbl, val)
        ff.addRow("Patr\u00f3n de v\u00e9rtices:", self.cboPatronVertice)
        ff.addRow("Formato de azimut:",  self.cboFormatoAzimut)
        grp_fmt.setLayout(ff); layout.addWidget(grp_fmt)

        btn = QtWidgets.QPushButton("🔍  Auto-detectar todos los campos")
        btn.setStyleSheet("padding: 6px; font-weight: bold;")
        btn.clicked.connect(self._autodetectar)
        layout.addWidget(btn)
        layout.addStretch()

    # =========================================================================
    # CONTROL DE MODO — lógica central de la UI
    # =========================================================================

    def _on_modo_changed(self):
        """
        Cuando cambia el modo:
        - ÚNICO:  groupSolicitante activo, panelAtlasSolicitante oculto
        - ATLAS:  groupSolicitante desactivado+atenuado, panelAtlasSolicitante visible
        """
        es_atlas = self.rbAtlasCompleto.isChecked() or self.rbAtlasSeleccion.isChecked()

        # Solicitante manual: activo solo en modo único
        self.groupSolicitante.setEnabled(not es_atlas)
        self.groupSolicitante.setStyleSheet(
            "" if not es_atlas else
            "QGroupBox { color: #999; } QGroupBox * { color: #999; }"
        )

        # Panel atlas solicitante: visible solo en atlas
        self.panelAtlasSolicitante.setVisible(es_atlas)

        # Botón previsualizar
        self.btnPreview.setEnabled(es_atlas)
        if not es_atlas:
            self.lblPreview.setText(
                "<i>Activa modo Atlas para ver los predios que se procesarán.</i>")

        # Actualizar título del groupSolicitante para que sea claro
        if es_atlas:
            self.groupSolicitante.setTitle(
                "1. Datos del Solicitante  ⚠ (desactivado en modo Atlas — se lee de la BD)")
        else:
            self.groupSolicitante.setTitle("1. Datos del Solicitante")

    # =========================================================================
    # ACTUALIZACIÓN DE CAPAS Y CAMPOS
    # =========================================================================

    def actualizar_campos_poligono(self):
        lid = self.cboPoligonos.currentData()
        if not lid: return
        layer = QgsProject.instance().mapLayer(lid)
        if not layer: return
        campos = [f.name() for f in layer.fields()]

        # Combos del tab principal (modo único)
        for cbo in [self.cboCampoNombre, self.cboCampoDNI]:
            cbo.clear(); cbo.addItem('-- Automático --', None)
            for c in campos: cbo.addItem(c, c)

        # Combo de nombre del predio (panel Identificación del Predio)
        if hasattr(self, 'cboCampoNombrePredio'):
            self.cboCampoNombrePredio.clear()
            self.cboCampoNombrePredio.addItem('-- Sin campo (manual) --', None)
            for c in campos: self.cboCampoNombrePredio.addItem(c, c)

        # Combos del panel atlas solicitante
        self.cboAtlasCampoNombre.clear()
        self.cboAtlasCampoNombre.addItem('-- Seleccione campo --', None)
        for c in campos: self.cboAtlasCampoNombre.addItem(c, c)

        self.cboAtlasCampoDNI.clear()
        self.cboAtlasCampoDNI.addItem('-- Sin DNI --', None)
        for c in campos: self.cboAtlasCampoDNI.addItem(c, c)

        # Combos de campos de polígono (pestaña Campos)
        for cbo in [self.cboCampoArea, self.cboCampoPerimetro]:
            cbo.clear(); cbo.addItem('-- Calcular automáticamente --', None)
            for c in campos: cbo.addItem(c, c)

        # Campo ID del polígono (pestaña Modo)
        if hasattr(self, 'cboCampoIdPoligono'):
            self.cboCampoIdPoligono.clear()
            self.cboCampoIdPoligono.addItem('-- Seleccione --', None)
            for c in campos: self.cboCampoIdPoligono.addItem(c, c)

        # Auto-selección
        self._sel(self.cboCampoNombre,        ['NombresApellidos','nombre','nom_tit','propietario','titular'])
        self._sel(self.cboCampoDNI,           ['dni','DNI','doc','documento'])
        self._sel(self.cboAtlasCampoNombre,   ['NombresApellidos','nombre','nom_tit','propietario','titular'])
        self._sel(self.cboAtlasCampoDNI,      ['dni','DNI','doc','documento'])
        self._sel(self.cboCampoArea,          ['Area_ha','area_ha','AREA_HA','area','AREA','hectareas'])
        self._sel(self.cboCampoPerimetro,     ['Perímetro','Perimetro','PERIMETRO','perimetro','perimeter'])
        self._sel(self.cboCampoIdPoligono,    ['fid','FID','FID_','fid_','id','ID','objectid'])
        self._sel(self.cboCampoNombrePredio,  ['PREDIO','predio','nom_predio','NOM_PREDIO',
                                               'denominacion','DENOMINACION','nombre_predio'])

        self._poblar_combos_bd(campos)

        self._actualizar_preview_predio()
        self._actualizar_preview_nombre_predio()

    def actualizar_campos_puntos(self):
        lid = self.cboPuntos.currentData()
        if not lid: return
        layer = QgsProject.instance().mapLayer(lid)
        if not layer: return
        campos = [f.name() for f in layer.fields()]

        for cbo in [self.cboCampoOrden, self.cboCampoID]:
            cbo.clear(); cbo.addItem('-- Automático --', None)
            for c in campos: cbo.addItem(c, c)

        auto_map = {
            self.cboCampoVerticeID:  '-- Generar automáticamente --',
            self.cboCampoOrdenPunto: '-- Detectar automáticamente --',
            self.cboCampoDistancia:  '-- Calcular geométricamente --',
            self.cboCampoAzimut:     '-- Calcular geométricamente --',
            self.cboCampoEste:       '-- Usar coordenada X del punto --',
            self.cboCampoNorte:      '-- Usar coordenada Y del punto --',
            self.cboCampoLado:       '-- Generar automáticamente --',
        }
        for cbo, lbl in auto_map.items():
            cbo.clear(); cbo.addItem(lbl, None)
            for c in campos: cbo.addItem(c, c)

        # Campo de relación en puntos
        if hasattr(self, 'cboCampoRelPuntos'):
            self.cboCampoRelPuntos.clear()
            self.cboCampoRelPuntos.addItem('-- Seleccione --', None)
            for c in campos: self.cboCampoRelPuntos.addItem(c, c)
            self._sel(self.cboCampoRelPuntos,
                      ['ID_Poligono','id_poligono','fid_area','poligono_id','pol_id'])

        self._sel(self.cboCampoOrden,      ['ID_Vertice','id_vertice','orden','order','id','fid'])
        self._sel(self.cboCampoID,         ['ID_Vertice','id_vertice','fid','id'])
        self._sel(self.cboCampoVerticeID,  ['ID_Vertice','id_vertice','vertice','id'])
        self._sel(self.cboCampoOrdenPunto, ['ID_Vertice','id_vertice','orden','order','fid'])
        self._sel(self.cboCampoDistancia,  ['Distancia','distancia','DISTANCIA','distance','dist'])
        self._sel(self.cboCampoAzimut,     ['Azimut','azimut','AZIMUT','azimuth','rumbo'])
        self._sel(self.cboCampoEste,       ['Este','este','ESTE','X','x','coord_x'])
        self._sel(self.cboCampoNorte,      ['Norte','norte','NORTE','Y','y','coord_y'])
        self._sel(self.cboCampoLado,       ['LADO','Lado','lado','side','segment'])

    def actualizar_campos_lineas(self): pass

    def _autodetectar(self):
        self.actualizar_campos_poligono()
        self.actualizar_campos_puntos()
        QtWidgets.QMessageBox.information(
            self, "Auto-detección completada",
            "Los campos han sido detectados automáticamente.\n"
            "Revisa los valores y ajusta si es necesario.")

    def _sel(self, combo, nombres):
        """Selecciona el primer campo que coincida con la lista de nombres."""
        for i in range(1, combo.count()):
            d = combo.itemData(i)
            if d and d.lower() in [n.lower() for n in nombres]:
                combo.setCurrentIndex(i); return

    # =========================================================================
    # PREVISUALIZACIÓN ATLAS
    # =========================================================================

    def _previsualizar(self):
        lid = self.cboPoligonos.currentData()
        if not lid:
            QtWidgets.QMessageBox.warning(self,"Atlas","Selecciona una capa de polígonos."); return
        layer = QgsProject.instance().mapLayer(lid)
        if not layer: return

        feats = (list(layer.selectedFeatures())
                 if self.rbAtlasSeleccion.isChecked()
                 else list(layer.getFeatures()))

        if not feats:
            self.lblPreview.setText("<b style='color:red'>No hay polígonos para procesar.</b>"); return

        campo_nombre = self.cboAtlasCampoNombre.currentData()
        campo_id     = self.cboCampoIdPoligono.currentData()
        fnames       = [f.name() for f in feats[0].fields()]

        filas = []
        for feat in feats:
            nombre = ''
            if campo_nombre and campo_nombre in fnames:
                nombre = str(feat[campo_nombre] or '')
            if not nombre and campo_id and campo_id in fnames:
                nombre = 'ID={}'.format(feat[campo_id])
            if not nombre:
                nombre = 'FID={}'.format(feat.id())
            filas.append(nombre)

        modo = "seleccionados" if self.rbAtlasSeleccion.isChecked() else "totales"
        resumen = ("<b>{} predios {} → {} memorias a generar:</b><br>".format(
                   len(filas), modo, len(filas)) +
                   "<br>".join("✓ {}".format(n) for n in filas[:15]) +
                   ("<br><i>... y {} más</i>".format(len(filas)-15) if len(filas)>15 else ""))
        self.lblPreview.setText(resumen)

    # =========================================================================
    # OBTENER DATOS DEL FORMULARIO
    # =========================================================================

    def obtener_datos_formulario(self):
        es_atlas = self.rbAtlasCompleto.isChecked() or self.rbAtlasSeleccion.isChecked()

        return {
            # ── Datos del solicitante ──────────────────────────────────────────
            # En modo único: valores manuales del formulario
            # En modo atlas: None (se leerán de la BD en cada iteración)
            'solicitante': {
                'nombre': self.txtNombre.text().strip() if not es_atlas else None,
                'dni':    self.txtDNI.text().strip()    if not es_atlas else None,
            },

            # ── Campos BD para solicitante en modo atlas ───────────────────────
            'atlas_solicitante': {
                'campo_nombre': self.cboAtlasCampoNombre.currentData(),
                'campo_dni':    self.cboAtlasCampoDNI.currentData(),
            },

            # ── Campos tomados de la tabla de atributos ──────────────────
            # clave -> campo de la capa de polígonos (None = manual).
            # En modo atlas se resuelven por cada predio.
            'campos_bd': {k: c.currentData()
                          for k, c in getattr(self, '_combos_bd', {}).items()},

            # ── Identificación del predio ─────────────────────────────
            # Nombre del PREDIO (distinto del titular) y su condición.
            # 'campo_nombre' tiene prioridad; si es None se usa 'nombre_manual'.
            'predio': {
                'campo_nombre':  self.cboCampoNombrePredio.currentData(),
                'nombre_manual': self.txtNombrePredio.text().strip(),
                'tipo':          self.cboTipoPredio.currentData() or '',
            },

            # ── Datos comunes (se repiten en todas las memorias) ───────────────
            'ubicacion': {
                'sector':       self.txtSector.text().strip(),
                'zona':         self.txtZona.text().strip(),
                'distrito':     self.txtDistrito.text().strip(),
                'provincia':    self.txtProvincia.text().strip(),
                'departamento': self.txtDepartamento.text().strip()
            },
            'generalidades':    self.txtGeneralidades.toPlainText().strip(),
            'metodo_levantamiento': self.txtMetodoLev.text().strip(),
            'equipo_levantamiento': self.txtEquipoLev.text().strip(),
            'formato_azimut':   self.cboFormatoAzimut.currentData(),
            'incluir_mapa':     self.chkIncluirMapa.isChecked(),
            'info_mapa': {
                'Sistema de coordenadas': self.txtSistema.text().strip(),
                'Unidades':   self.txtUnidades.text().strip(),
                'Elipsoide':  self.txtElipsoide.text().strip(),
                'Grillado':   self.txtGrillado.text().strip()
            },
            'colindantes': {
                'detectar_automatico': self.chkDetectarColindantes.isChecked(),
                'manual': {
                    'NORTE': self.txtNorte.text().strip(), 'SUR':   self.txtSur.text().strip(),
                    'ESTE':  self.txtEste.text().strip(),  'OESTE': self.txtOeste.text().strip()
                }
            },

            # ── Capas ──────────────────────────────────────────────────────────
            'capas': {
                'poligono_id': self.cboPoligonos.currentData(),
                'punto_id':    self.cboPuntos.currentData(),
                'linea_id':    self.cboLineas.currentData()
            },

            # ── Modo ───────────────────────────────────────────────────────────
            'modo': ('unico'           if self.rbUnico.isChecked()
                     else 'atlas_seleccion' if self.rbAtlasSeleccion.isChecked()
                     else 'atlas_completo'),

            # ── Relación entre capas ───────────────────────────────────────────
            'relacion': {
                'campo_id_poligono': self.cboCampoIdPoligono.currentData(),
                'campo_rel_puntos':  self.cboCampoRelPuntos.currentData(),
            },

            # ── Configuración de campos ────────────────────────────────────────
            'campos': {
                'campo_id_poligono': self.cboCampoIdPoligono.currentData(),
                'campo_id_rel_pts':  self.cboCampoRelPuntos.currentData(),
                'campo_vertice':     self.cboCampoVerticeID.currentData(),
                'campo_orden':       self.cboCampoOrdenPunto.currentData(),
                'campo_distancia':   self.cboCampoDistancia.currentData(),
                'campo_azimut':      self.cboCampoAzimut.currentData(),
                'campo_este':        self.cboCampoEste.currentData(),
                'campo_norte':       self.cboCampoNorte.currentData(),
                'campo_lado':        self.cboCampoLado.currentData(),
                'campo_area':        self.cboCampoArea.currentData(),
                'campo_perimetro':   self.cboCampoPerimetro.currentData(),
                'patron_vertice':    self.cboPatronVertice.currentData(),
                # Solo usados en modo único
                'campo_nombre':      self.cboCampoNombre.currentData(),
                'campo_dni':         self.cboCampoDNI.currentData(),
            },
            'output_file': self.txtOutputFile.text().strip()
        }

    # =========================================================================
    # FASE 2 — TOOLTIPS DE AYUDA
    # =========================================================================

    def _instalar_ayudas(self):
        """Tooltips explicativos: qu\u00e9 seleccionar en cada campo y por qu\u00e9.
        Se muestran al pasar el mouse sobre el control o su etiqueta."""
        AYUDAS = {
            # ── Datos B\u00e1sicos ──
            'cboPoligonos': (
                "<b>Capa de pol\u00edgonos</b><br>La capa con el/los predios (\u00e1rea). "
                "De aqu\u00ed se leen \u00e1rea, per\u00edmetro y nombre del propietario.<br>"
                "<i>Ejemplo: AREA, AREA_TOTAL, predios.gpkg</i>"),
            'cboPuntos': (
                "<b>Capa de puntos</b><br>Los v\u00e9rtices del per\u00edmetro generados por el "
                "Segmentador, con Este, Norte, Distancia y Azimut como atributos.<br>"
                "<i>Ejemplo: Vertices, Ptos_Fraccion_1</i>"),
            'cboLineas': (
                "<b>Capa de l\u00edneas (opcional)</b><br>Segmentos del per\u00edmetro. "
                "No es necesaria: distancias y azimuts ya vienen en los puntos."),
            'txtOutputFile': (
                "<b>Archivo de salida</b><br>Ruta del .docx a generar. En modo Atlas "
                "se agrega el nombre de cada propietario como sufijo autom\u00e1ticamente."),
            # ── Relaci\u00f3n ──
            'cboCampoIdPoligono': (
                "<b>Campo ID del pol\u00edgono</b><br>Campo de la capa de pol\u00edgonos que "
                "identifica cada predio (fid, OBJECTID). Su valor debe coincidir con "
                "el campo de relaci\u00f3n en los puntos."),
            'cboCampoRelPuntos': (
                "<b>Campo relaci\u00f3n en puntos</b><br>Campo de la capa de puntos que "
                "indica a qu\u00e9 pol\u00edgono pertenece cada v\u00e9rtice "
                "(normalmente ID_Poligono, generado por el Segmentador)."),
            # ── Campos de puntos ──
            'cboCampoVerticeID': (
                "<b>ID / Etiqueta del v\u00e9rtice</b><br>Campo con el n\u00famero de cada "
                "v\u00e9rtice (ID_Vertice). Se re-etiqueta seg\u00fan el patr\u00f3n elegido abajo, "
                "as\u00ed la tabla, el LADO y la narrativa quedan congruentes."),
            'cboCampoOrdenPunto': (
                "<b>Orden / Secuencia</b><br>Campo que define el recorrido del "
                "per\u00edmetro (ID_Vertice o fid). Si el orden es incorrecto, la "
                "narrativa dar\u00e1 saltos entre v\u00e9rtices no contiguos."),
            'cboCampoDistancia': (
                "<b>Distancia (m)</b><br>Distancia al v\u00e9rtice siguiente, generada por "
                "el Segmentador. Se muestra con 2 decimales (norma). Si un valor "
                "falta, se calcula desde las coordenadas como respaldo."),
            'cboCampoAzimut': (
                "<b>Azimut (\u00b0)</b><br>Azimut al v\u00e9rtice siguiente, generado por el "
                "Segmentador \u2014 este valor manda, el plugin no recalcula. Debe "
                "coincidir con las etiquetas del plano."),
            'cboCampoEste': (
                "<b>Coordenada Este / X</b><br>Coordenada UTM Este del v\u00e9rtice. "
                "Se muestra con 4 decimales (norma). Si no existe el campo, se toma "
                "de la geometr\u00eda del punto."),
            'cboCampoNorte': (
                "<b>Coordenada Norte / Y</b><br>Coordenada UTM Norte del v\u00e9rtice. "
                "Se muestra con 4 decimales (norma)."),
            'cboCampoLado': (
                "<b>Nombre del lado</b><br>Opcional. El plugin regenera el lado con "
                "el patr\u00f3n de v\u00e9rtices (V-1 a V-2) para garantizar congruencia; "
                "solo se usa el campo BD si activas esa opci\u00f3n en el c\u00f3digo."),
            # ── Campos de pol\u00edgono ──
            'cboCampoArea': (
                "<b>\u00c1rea (ha)</b><br>Campo con el \u00e1rea en hect\u00e1reas (AREA_HA). "
                "Si viene en m\u00b2 (valor > 5000) se convierte autom\u00e1ticamente. "
                "Sin campo, se calcula sobre elipsoide WGS84."),
            'cboCampoPerimetro': (
                "<b>Per\u00edmetro (m)</b><br>Campo con el per\u00edmetro en metros "
                "(PERIMETRO, PERIMETER). Sin campo, se calcula de la geometr\u00eda."),
            'cboCampoNombre': (
                "<b>Nombre del propietario</b><br>Campo con nombres y apellidos "
                "(NOMBRE). En modo Atlas, cada memoria toma el nombre de su predio."),
            'cboCampoDNI': (
                "<b>DNI del propietario</b><br>Campo con el DNI. Si la capa no lo "
                "tiene, puede escribirse manualmente en Datos B\u00e1sicos (modo \u00fanico)."),
            # ── Formato ──
            'cboPatronVertice': (
                "<b>Patr\u00f3n de v\u00e9rtices</b><br>C\u00f3mo se etiquetan los v\u00e9rtices en "
                "TODO el documento: tabla, columna LADO y narrativa. "
                "Debe coincidir con las etiquetas del plano."),
            'cboFormatoAzimut': (
                "<b>Formato de azimut</b><br><b>Decimal 1 dec</b> (recomendado): igual "
                "al plano y \u00fatil para replanteo con br\u00fajula.<br><b>GMS</b>: para "
                "instituciones que exijan sexagesimal.<br><b>Ambos</b>: decimal (GMS)."),
            # ── Generalidades ──
            'cboEquipoPreset': (
                "<b>Preset de levantamiento</b><br>Llena M\u00e9todo y Equipo con un clic "
                "seg\u00fan el equipo usado en campo. Elige Personalizado para escribir "
                "libremente. El texto de Generalidades se actualiza en vivo."),
            'txtMetodoLev': (
                "<b>M\u00e9todo de levantamiento</b><br>C\u00f3mo se hizo el trabajo de campo. "
                "Se inserta en el primer p\u00e1rrafo de Generalidades."),
            'txtEquipoLev': (
                "<b>Equipo usado</b><br>Con qu\u00e9 se midi\u00f3. Se inserta en Generalidades. "
                "S\u00e9 espec\u00edfico: marca y modelo dan respaldo t\u00e9cnico al documento."),
            'chkTextoDefault': (
                "<b>Usar texto predeterminado</b><br>Marcado: el texto se arma "
                "autom\u00e1ticamente con M\u00e9todo y Equipo (lo que ves es lo que se "
                "genera). Desmarcado: escribe tu propio texto libremente."),
            # ── Colindantes ──
            'chkDetectarColindantes': (
                "<b>Detectar colindantes autom\u00e1ticamente</b><br>Busca pol\u00edgonos "
                "vecinos en las capas del proyecto y toma su campo NOMBRE. "
                "Verifica el resultado: si no hay vecino, usa 'Terrenos del Estado'."),
            # ── Info T\u00e9cnica ──
            'txtGrillado': (
                "<b>Grillado</b><br>Separaci\u00f3n de la grilla de coordenadas del plano "
                "(ej. 'Cada 500 metros'). Debe coincidir con el plano impreso."),
        }
        for nombre, texto in AYUDAS.items():
            w = getattr(self, nombre, None)
            if w is not None:
                w.setToolTip(texto)

    # =========================================================================
    # FASE 2 — GENERALIDADES: MÉTODO Y EQUIPO DE LEVANTAMIENTO
    # =========================================================================

    PRESETS_LEVANTAMIENTO = [
        ("GNSS diferencial \u2014 Trimble Catalyst DA2",
         "topogr\u00e1fico de campo con posicionamiento satelital diferencial GNSS",
         "receptor GNSS Trimble Catalyst DA2"),
        ("GNSS post-proceso PPK",
         "topogr\u00e1fico de campo con posicionamiento GNSS y post-procesamiento PPK",
         "receptor GNSS de doble frecuencia"),
        ("GPS navegador",
         "topogr\u00e1fico de campo",
         "equipos GPS navegador con precisi\u00f3n decim\u00e9trica"),
        ("Fotogrametr\u00eda con drone \u2014 DJI Matrice 4T",
         "fotogram\u00e9trico mediante aeronave pilotada a distancia (RPAS)",
         "drone DJI Matrice 4T con puntos de apoyo GNSS"),
        ("Estaci\u00f3n total",
         "topogr\u00e1fico de campo",
         "estaci\u00f3n total"),
        ("Personalizado...", "", ""),
    ]

    PLANTILLA_GENERALIDADES = (
        "El presente documento constituye la Memoria Descriptiva del plano "
        "perim\u00e9trico adjunto, elaborado con el prop\u00f3sito de precisar los "
        "linderos, la configuraci\u00f3n geom\u00e9trica y la extensi\u00f3n superficial del "
        "terreno en cuesti\u00f3n. La informaci\u00f3n t\u00e9cnica aqu\u00ed consignada se "
        "fundamenta en un levantamiento {}, ejecutado mediante {}, garantizando "
        "la exactitud m\u00e9trica y el cumplimiento de las normativas vigentes en "
        "materia de geodesia y cartograf\u00eda.\n\n"
        "Esta memoria tiene por objeto respaldar jur\u00eddica y t\u00e9cnicamente la "
        "delimitaci\u00f3n del predio, sustentando su titularidad y proporcionando "
        "datos verificables para fines catastrales, registrales o "
        "administrativos, seg\u00fan corresponda.")

    def _configurar_generalidades(self):
        """Combo de presets + campos m\u00e9todo/equipo, con preview sincronizado."""
        grp = self.groupGeneralidades
        lay = grp.layout()

        form = QtWidgets.QFormLayout()
        self.cboEquipoPreset = QtWidgets.QComboBox()
        for p in self.PRESETS_LEVANTAMIENTO:
            self.cboEquipoPreset.addItem(p[0])
        self.txtMetodoLev = QtWidgets.QLineEdit(self.PRESETS_LEVANTAMIENTO[0][1])
        self.txtEquipoLev = QtWidgets.QLineEdit(self.PRESETS_LEVANTAMIENTO[0][2])
        form.addRow("Levantamiento:", self.cboEquipoPreset)
        form.addRow("M\u00e9todo:", self.txtMetodoLev)
        form.addRow("Equipo:", self.txtEquipoLev)

        cont = QtWidgets.QWidget(); cont.setLayout(form)
        try:
            lay.insertWidget(1, cont)
        except Exception:
            lay.addWidget(cont)

        self.cboEquipoPreset.currentIndexChanged.connect(self._aplicar_preset_equipo)
        self.txtMetodoLev.textChanged.connect(self._actualizar_preview_generalidades)
        self.txtEquipoLev.textChanged.connect(self._actualizar_preview_generalidades)
        self.chkTextoDefault.toggled.connect(self._actualizar_preview_generalidades)
        self._actualizar_preview_generalidades()

    def _aplicar_preset_equipo(self, idx):
        p = self.PRESETS_LEVANTAMIENTO[idx]
        if p[1] or p[2]:
            self.txtMetodoLev.setText(p[1])
            self.txtEquipoLev.setText(p[2])
        self._actualizar_preview_generalidades()

    def _actualizar_preview_generalidades(self, *args):
        """El cuadro de texto muestra EXACTAMENTE lo que ir\u00e1 al documento."""
        if not self.chkTextoDefault.isChecked():
            return
        metodo = self.txtMetodoLev.text().strip() or "topogr\u00e1fico de campo"
        equipo = self.txtEquipoLev.text().strip() or "equipos GNSS"
        self.txtGeneralidades.setPlainText(
            self.PLANTILLA_GENERALIDADES.format(metodo, equipo))

    # =========================================================================
    # FASE 2 — REORGANIZACIÓN DE UI
    # =========================================================================

    def _reorganizar_ui(self):
        """Títulos sin numeración huérfana, elimina grupo duplicado de campos,
        y deja Generar Memoria como única acción primaria."""
        self.groupSolicitante.setTitle("Datos del Solicitante")
        self.groupUbicacion.setTitle("Ubicación")
        self.groupColindantes.setTitle("Colindantes")
        self.groupGeneralidades.setTitle("Generalidades")
        self.groupInfoMapa.setTitle("Información Técnica del Mapa")

        # Grupo "Selección de Campos" duplicado en Info Técnica:
        # Nombre/DNI se mudan a la pestaña Campos; orden/ID eran UI muerta.
        try:
            self._fpol_campos.addRow("Nombre del propietario:", self.cboCampoNombre)
            self._fpol_campos.addRow("DNI del propietario:",    self.cboCampoDNI)
            self.groupCampos.setVisible(False)
        except Exception as e:
            print("Aviso reorganizando campos: {}".format(e))

        # Botones: Generar Memoria primario único; button_box solo Cerrar
        try:
            from qgis.PyQt.QtWidgets import QDialogButtonBox
            SB = getattr(QDialogButtonBox, 'StandardButton', QDialogButtonBox)
            self.button_box.setStandardButtons(SB.Close)
            btn_close = self.button_box.button(SB.Close)
            if btn_close:
                btn_close.setText("Cerrar")
        except Exception as e:
            print("Aviso configurando botones: {}".format(e))
        self.btnGenerar.setStyleSheet(
            "padding: 8px 18px; font-weight: bold; font-size: 11pt;")
        self.btnGenerar.setDefault(True)

    # =========================================================================
    # VALIDACIÓN
    # =========================================================================

    def validar_formulario(self):
        def _w(msg, tab=0, w=None):
            self.tabWidget.setCurrentIndex(tab)
            if w: w.setFocus()
            QtWidgets.QMessageBox.warning(self, "Campo requerido", msg)
            return False

        es_atlas = self.rbAtlasCompleto.isChecked() or self.rbAtlasSeleccion.isChecked()

        # En modo único: nombre y DNI son obligatorios
        if not es_atlas:
            if not self.txtNombre.text().strip():
                return _w("Ingrese el nombre del solicitante.", 0, self.txtNombre)
            if not self.txtDNI.text().strip():
                return _w("Ingrese el DNI del solicitante.", 0, self.txtDNI)

        # En modo atlas: campo nombre obligatorio
        if es_atlas:
            if not self.cboAtlasCampoNombre.currentData():
                return _w(
                    "En modo Atlas debes seleccionar el campo que contiene\n"
                    "el nombre del propietario en la capa de polígonos.\n\n"
                    "Revisa la pestaña 'Datos Básicos'.", 0, self.cboAtlasCampoNombre)

        # Ubicación mínima
        if not self.txtSector.text().strip():
            return _w("Ingresa el sector o localidad de ubicación.", 0, self.txtSector)

        # Capas
        if not self.cboPoligonos.currentData():
            return _w("Selecciona la capa de polígonos (ej: AREA_TOTAL).", 0)
        if not self.cboPuntos.currentData():
            return _w("Selecciona la capa de puntos (ej: Puntos).", 0)

        # Archivo de salida
        if not self.txtOutputFile.text().strip():
            return _w("Especifica la ruta del archivo de salida.", 0, self.txtOutputFile)

        # Atlas selección: verificar que haya objetos seleccionados
        if self.rbAtlasSeleccion.isChecked():
            lid = self.cboPoligonos.currentData()
            if lid:
                layer = QgsProject.instance().mapLayer(lid)
                if layer and layer.selectedFeatureCount() == 0:
                    return _w(
                        "No hay polígonos seleccionados en la capa.\n"
                        "Selecciona al menos un polígono en QGIS antes de continuar.", 1)

        # Colindantes manuales
        if not self.chkDetectarColindantes.isChecked():
            for nm, wid in [('Norte', self.txtNorte), ('Sur', self.txtSur),
                             ('Este', self.txtEste), ('Oeste', self.txtOeste)]:
                if not wid.text().strip():
                    return _w("Ingresa el colindante {}.".format(nm), 2, wid)

        return True
