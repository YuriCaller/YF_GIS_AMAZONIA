# -*- coding: utf-8 -*-
"""
main_dialog.py
Interfaz principal del plugin GNSS Post-Process v2.
5 pestañas: Modo/Archivos | Base IGN | Configuración | Informe | Salida
"""
import logging
import os
from qgis.PyQt.QtGui import QDesktopServices as __QDS
from qgis.PyQt.QtCore import QUrl as __QURL
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QTabWidget, QTextEdit, QFileDialog,
    QProgressBar, QFrame, QScrollArea, QFormLayout,
    QRadioButton, QButtonGroup, QMessageBox, QSizePolicy
)
from qgis.PyQt.QtCore import Qt, QSettings
from ....core.qt_compat import QVariant_Int, QVariant_Double, QVariant_String
from qgis.PyQt.QtGui import QFont

from ..gnss_engine.config_builder import ProcessingParams
from ..gnss_engine.coord_converter import BaseCoords
from ..validators.base_validator import BaseCoordValidator

# ──────────────────────────────────────────────────────
# STYLESHEET
# ──────────────────────────────────────────────────────
SS = """
QWidget{background:#f7f7f4;font-family:'Segoe UI',Arial,sans-serif;font-size:12px;}
QGroupBox{font-weight:bold;font-size:11px;color:#1a472a;
  border:1.5px solid #2d6a4f;border-radius:5px;margin-top:8px;padding-top:6px;}
QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 4px;}
QPushButton{background:#2d6a4f;color:white;border:none;
  border-radius:4px;padding:5px 12px;font-weight:bold;}
QPushButton:hover{background:#1a472a;}
QPushButton:disabled{background:#aaa;color:#eee;}
QPushButton#browse{background:#607d8b;padding:3px 8px;font-size:11px;}
QPushButton#browse:hover{background:#455a64;}
QPushButton#run{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
  stop:0 #1a472a,stop:1 #2d6a4f);font-size:13px;padding:9px;border-radius:5px;}
QPushButton#report{background:#4a5568;}
QPushButton#report:hover{background:#2d3748;}
QPushButton#apply_base{background:#1565c0;}
QPushButton#apply_base:hover{background:#0d47a1;}
QLineEdit{border:1px solid #ccc;border-radius:3px;padding:4px 6px;background:white;}
QLineEdit:focus{border-color:#2d6a4f;}
QLineEdit#invalid{border-color:#f44336;background:#fff8f8;}
QComboBox{border:1px solid #ccc;border-radius:3px;padding:4px;background:white;}
QTabWidget::pane{border:1px solid #ccc;border-radius:4px;}
QTabBar::tab{padding:6px 12px;background:#e8e8e0;border-radius:3px 3px 0 0;margin-right:2px;}
QTabBar::tab:selected{background:#2d6a4f;color:white;font-weight:bold;}
QProgressBar{border:1px solid #ccc;border-radius:3px;height:16px;text-align:center;}
QProgressBar::chunk{background:#2d6a4f;border-radius:2px;}
QTextEdit{border:1px solid #ccc;border-radius:3px;background:white;}
"""


class GNSSMainDialog(QWidget):

    def __init__(self, iface, plugin_dir: str, parent=None):
        super().__init__(parent)
        self.iface       = iface
        self.plugin_dir  = plugin_dir
        self.settings    = QSettings('GNSSPostProcess', 'v2')
        self._base_coords: BaseCoords = None
        self._last_stats = None
        self._last_occ_results = None
        self._last_proc_info = {}
        self._last_params = None
        self._last_pos   = None
        self.setStyleSheet(SS)
        self._build()
        self._restore()

    # ══════════════════════════════════════════════
    # CONSTRUCCIÓN UI
    # ══════════════════════════════════════════════
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)
        root.addWidget(self._header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_archivos(),    '📂 Archivos')
        self.tabs.addTab(self._tab_base(),        '📌 Base IGN')
        self.tabs.addTab(self._tab_config(),      '⚙️ Config')
        self.tabs.addTab(self._tab_informe(),     '📋 Informe')
        self.tabs.addTab(self._tab_salida(),      '📤 Salida')
        self.tabs.addTab(self._tab_ayuda(),       '❓ Ayuda / Guía')
        root.addWidget(self.tabs, 1)
        root.addWidget(self._bottom_bar())
        root.addWidget(self._log_console())

    def _header(self):
        f = QFrame()
        f.setStyleSheet(
            'background:qlineargradient(x1:0,y1:0,x2:1,y2:0,'
            'stop:0 #1a472a,stop:1 #40916c);border-radius:6px;')
        lay = QVBoxLayout(f); lay.setContentsMargins(12, 8, 12, 8)
        t = QLabel('🛰️  GNSS Post-Process PPK/PPP v2')
        t.setStyleSheet('color:white;font-size:14px;font-weight:bold;background:transparent;')
        s = QLabel('RTKLIB · pyproj · Ficha IGN Perú · Trazabilidad · reportlab')
        s.setStyleSheet('color:#b7e4c7;font-size:10px;background:transparent;')
        lay.addWidget(t); lay.addWidget(s)
        return f

    # ─────────── TAB ARCHIVOS ───────────
    def _tab_ayuda(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setHtml(self._ayuda_html())
        lay.addWidget(txt)
        return w

    def _ayuda_html(self):
        return """
<style>
  h2 { color:#1a6e2e; border-bottom:2px solid #1a6e2e; padding-bottom:3px; }
  h3 { color:#2c5f8a; margin-bottom:4px; }
  .box { background:#f4f8f4; border-left:4px solid #1a6e2e; padding:8px; margin:6px 0; }
  .warn { background:#fff8e1; border-left:4px solid #f0a000; padding:8px; margin:6px 0; }
  .crit { background:#fdecea; border-left:4px solid #d33; padding:8px; margin:6px 0; }
  code { background:#eee; padding:1px 4px; border-radius:3px; font-family:monospace; }
  table { border-collapse:collapse; width:100%; margin:6px 0; }
  th { background:#1a6e2e; color:white; padding:5px; text-align:left; }
  td { border:1px solid #ccc; padding:5px; vertical-align:top; }
</style>

<h2>📡 Guía de Post-Proceso GNSS</h2>
<p>Esta guía te ayuda a elegir <b>qué modo usar según tus datos y condiciones de campo</b>.
Recuerda el principio de esta herramienta: <i>una coordenada honesta vale más que un FIX falso bonito.</i></p>

<h2>1. PPK vs PPP — ¿con base o sin base?</h2>
<table>
<tr><th>Modo</th><th>Cuándo usarlo</th><th>Requiere</th></tr>
<tr><td><b>PPK</b><br>(diferencial)</td>
    <td>Tu caso normal. Corriges tu rover contra una base de coordenada conocida
    (ERP del IGN: MD01, MD04…). Mejor precisión a línea base corta.</td>
    <td>RINEX del rover + RINEX de la base + coordenadas oficiales de la base.</td></tr>
<tr><td><b>PPP</b><br>(punto preciso)</td>
    <td>No tienes base cercana o quieres una posición absoluta independiente.
    Necesita sesiones largas (varias horas) para converger.</td>
    <td>RINEX del rover + efemérides precisas (SP3/CLK). Sin base.</td></tr>
</table>

<h2>2. El árbol de decisión del modo de solución</h2>
<div class="box">
<b>¿Tienes buena vista del cielo y la base está cerca (&lt; 20-30 km)?</b><br>
→ Usa <b>Estático</b> (o Cinemático si te mueves). Busca FIX centimétrico.
</div>
<div class="warn">
<b>¿Estás bajo dosel denso, o la base está lejos (&gt; 30-50 km), y el FIX no es confiable?</b><br>
→ Usa <b>📡 Submétrico DGPS</b>. Renuncia al centímetro a cambio de una
coordenada de 0.3-1 m <i>estable y honesta</i>, sin riesgo de falsos fix.
</div>

<h3>🌍 Estático / Cinemático (FIX centimétrico)</h3>
<p>Resuelve ambigüedades de la fase portadora. Da precisión de centímetros…
<b>pero solo si la señal es buena</b>. Bajo dosel o a gran distancia, la fase
se corta (cycle slips) y el sistema puede reportar <b>falsos fix</b>:
posiciones que parecen centimétricas pero están desplazadas metros.</p>
<div class="crit">
<b>Protección anti-falso-fix:</b> este plugin descarta automáticamente las
épocas FIX que se dispersan más de 0.5 m entre sí y etiqueta el resultado como
<code>NO CONFIABLE</code>. Si ves esa etiqueta, NO uses esa coordenada para tu
plano — cambia a modo DGPS o repite la toma en mejores condiciones.
</div>

<h3>📡 Submétrico DGPS (la solución para selva amazónica)</h3>
<p>Usa <b>pseudodistancia (código)</b>, no la fase portadora. Como no hay
ambigüedad de fase que resolver, <b>es imposible generar un falso fix</b>.
La precisión es honesta: típicamente 0.3-1 m contra una base cercana.</p>
<div class="box">
<b>Ideal para:</b> puntos bajo cobertura forestal, vértices a gran distancia de
la base IGN, levantamientos donde la norma admite precisión submétrica
(catastro rural, deslindes referenciales, inventarios forestales).
</div>

<h2>3. Cómo leer la etiqueta de calidad del resultado</h2>
<table>
<tr><th>Etiqueta</th><th>Significado</th><th>¿Usable?</th></tr>
<tr><td><b>FIX</b></td><td>Ambigüedades resueltas y consistentes. Precisión cm.</td>
    <td>✅ Sí, la mejor.</td></tr>
<tr><td><b>SUBMÉTRICO DGPS</b></td><td>Solución de código diferencial. 0.3-1 m.</td>
    <td>✅ Sí, para norma submétrica.</td></tr>
<tr><td><b>FLOAT</b></td><td>Ambigüedades no fijadas del todo. Decimétrico a métrico.</td>
    <td>⚠️ Con reservas; revisa la dispersión.</td></tr>
<tr><td><b>... (NO CONFIABLE)</b></td><td>La dispersión supera el umbral seguro.</td>
    <td>❌ No usar para plano legal.</td></tr>
<tr><td><b>SINGLE</b></td><td>Posición autónoma, sin corrección diferencial.</td>
    <td>❌ Solo orientativa (metros).</td></tr>
</table>

<h2>4. Altura de antena — el error silencioso más común</h2>
<div class="warn">
Ingresa SIEMPRE la altura real de antena del rover (la del bastón, ej.
<code>2.000 m</code>) y de la base (de la ficha IGN, ej. <code>0.0750 m</code>
para MD04). Un error aquí desplaza la altura final exactamente esa cantidad.
El plugin puede leerla del header del RINEX con el botón de autocompletar.
</div>

<h2>5. Procesamiento por lotes</h2>
<p>En la pestaña <b>Archivos</b>, agrega varios rovers (o una carpeta completa)
para procesar toda una campaña contra la misma base en una sola corrida. Obtienes
una capa única con todos los puntos y un resumen de calidad por archivo —
estilo Trimble Business Center / Pathfinder.</p>

<h2>6. Efemérides precisas</h2>
<p>El botón <b>Descargar efemérides automáticamente</b> lee la fecha de tu RINEX,
calcula la semana GPS y baja los productos SP3/CLK finales del IGS/ESA. Mejoran
la solución en líneas base largas. Para levantamientos recientes (menos de ~2
semanas) puede que solo estén disponibles las rápidas, que para uso submétrico
son igual de válidas.</p>

<hr>
<p style="color:#666;font-size:11px;">
<b>YF GIS Amazonia Tools</b> · Yuri F. Caller Córdova · CIP 214377 · TUCSA / gis-amazonia.pe<br>
Esta herramienta prioriza la honestidad geodésica: ante la duda, reporta menos
precisión, nunca más de la que los datos respaldan.</p>
"""

    def _tab_archivos(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)

        # Selector de modo PPK / PPP
        g_modo = QGroupBox('Modo de procesamiento')
        m_lay = QHBoxLayout(g_modo)
        self.rb_ppk = QRadioButton('PPK  (Post Processed Kinematic — con base)')
        self.rb_ppp = QRadioButton('PPP  (Precise Point Positioning — sin base)')
        self.rb_ppk.setChecked(True)
        self.rb_ppk.toggled.connect(self._on_mode_toggle)
        m_lay.addWidget(self.rb_ppk); m_lay.addWidget(self.rb_ppp)
        lay.addWidget(g_modo)

        # Rover
        g_rover = QGroupBox('Rover')
        g_rover_lay = QFormLayout(g_rover)

        # Filtros RINEX expandidos: incluyen extensiones por año (.26o, .25n, etc.)
        # Patrón *.*o captura .obs, .26o, .25o, .24o, etc.
        # Patrón *.*n captura .nav, .26n, .25n, .24n, etc.
        _FILT_OBS = 'RINEX Obs (*.*o *.*O *.obs *.OBS *.rnx *.RNX);;Todos (*.*)'
        _FILT_NAV = 'RINEX Nav (*.*n *.*N *.*l *.*L *.*g *.*G *.*p *.*P *.nav *.NAV *.rnx *.RNX *.gnav *.GNAV);;Todos (*.*)'
        _FILT_GNAV = 'GLONASS Nav (*.*g *.*G *.gnav *.GNAV *.rnx *.RNX);;Todos (*.*)'

        self.ed_rover  = self._file_field(g_rover_lay,
            'RINEX Obs (.obs/.26o/.rnx):', _FILT_OBS)
        self.ed_nav    = self._file_field(g_rover_lay,
            'Nav GPS (.nav/.26n/.rnx):', _FILT_NAV)
        self.ed_gnav   = self._file_field(g_rover_lay,
            'Nav GLONASS (.gnav/.26g):', _FILT_GNAV, optional=True)

        # Auto-detectar nav cuando se selecciona rover
        self.ed_rover.textChanged.connect(self._auto_detect_nav)
        self.ed_rover.textChanged.connect(self._check_occupations)

        lay.addWidget(g_rover)

        # ── Modo OCUPACIONES (varios puntos en un archivo, estilo TBC) ──
        self.g_occ = QGroupBox('📍 Ocupaciones múltiples en el archivo')
        goc = QVBoxLayout(self.g_occ)
        self.chk_occ_mode = QCheckBox(
            'Separar y resolver cada ocupación por separado (no promediar entre puntos)')
        self.chk_occ_mode.setToolTip(
            'Detecta los eventos de ocupación marcados por el receptor\n'
            '(Geo7X/DA2) dentro de un archivo continuo y resuelve cada\n'
            'punto con SUS propias épocas, en modo cinemático + corte por\n'
            'ventana de tiempo. Igual que TBC / Pathfinder.')
        self.chk_occ_mode.setStyleSheet('font-weight:bold;color:#5e35b1;')
        goc.addWidget(self.chk_occ_mode)
        self.lbl_occ_info = QLabel('— selecciona un rover para detectar ocupaciones —')
        self.lbl_occ_info.setWordWrap(True)
        self.lbl_occ_info.setStyleSheet('color:#666;font-size:10px;')
        goc.addWidget(self.lbl_occ_info)
        lay.addWidget(self.g_occ)

        # ── Procesamiento por LOTES (estilo TBC/Pathfinder) ──
        from qgis.PyQt.QtWidgets import QListWidget, QAbstractItemView
        self.g_batch = QGroupBox('📂 Procesamiento por lotes (opcional) — varios rovers, una base')
        gbat = QVBoxLayout(self.g_batch)
        lbl_b = QLabel(
            'Agrega varios archivos rover de la misma campaña. '
            'Si la lista tiene archivos, se procesan TODOS contra la base '
            '(el campo rover individual de arriba se ignora).')
        lbl_b.setWordWrap(True)
        lbl_b.setStyleSheet('color:#666;font-size:10px;')
        gbat.addWidget(lbl_b)

        self.lst_rovers = QListWidget()
        self.lst_rovers.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lst_rovers.setMaximumHeight(110)
        gbat.addWidget(self.lst_rovers)

        hb = QHBoxLayout()
        btn_add_f = QPushButton('➕ Archivos…')
        btn_add_d = QPushButton('📁 Carpeta…')
        btn_del   = QPushButton('➖ Quitar')
        btn_clr   = QPushButton('🗑 Limpiar')
        for b in (btn_add_f, btn_add_d, btn_del, btn_clr):
            hb.addWidget(b)
        gbat.addLayout(hb)
        self.lbl_batch_count = QLabel('0 archivos en lote')
        self.lbl_batch_count.setStyleSheet('font-weight:bold;color:#1a6e2e;')
        gbat.addWidget(self.lbl_batch_count)

        btn_add_f.clicked.connect(self._batch_add_files)
        btn_add_d.clicked.connect(self._batch_add_folder)
        btn_del.clicked.connect(self._batch_remove_selected)
        btn_clr.clicked.connect(lambda: (self.lst_rovers.clear(), self._batch_update_count()))

        lay.addWidget(self.g_batch)

        # Base RINEX (PPK)
        self.g_base_rinex = QGroupBox('Base — RINEX (PPK)')
        gb_lay = QFormLayout(self.g_base_rinex)
        self.ed_base_rinex = self._file_field(gb_lay,
            'RINEX Base (.obs/.26o/.rnx):', _FILT_OBS)
        lay.addWidget(self.g_base_rinex)

        # Archivos precisos — obligatorios en PPP, OPCIONALES en PPK
        # (mejoran precisión en líneas base largas >20km)
        self.g_precise = QGroupBox('Archivos precisos (opcionales en PPK, mejoran línea base larga)')
        gp_lay = QFormLayout(self.g_precise)
        self.ed_sp3    = self._file_field(gp_lay, 'Órbitas precisas (.sp3):',
                                           'SP3 (*.sp3 *.SP3 *.eph)')
        self.ed_clk    = self._file_field(gp_lay, 'Relojes precisos (.clk):',
                                           'CLK (*.clk *.CLK)')
        self.ed_ionex  = self._file_field(gp_lay, 'IONEX (.i/.ionex):',
                                           'IONEX (*.i *.ionex *.??i)', optional=True)

        # Botón de descarga automática según fecha del RINEX rover
        self.btn_auto_eph = QPushButton('⬇  Descargar efemérides automáticamente')
        self.btn_auto_eph.setToolTip(
            'Lee la fecha del RINEX rover, calcula la semana GPS\n'
            'y descarga SP3 + CLK de fuentes públicas (ESA/IGS).\n'
            'Prioriza Final → Rapid según disponibilidad.')
        self.btn_auto_eph.setStyleSheet(
            'QPushButton{background:#1565c0;color:white;font-weight:bold;'
            'padding:6px;border-radius:4px;}'
            'QPushButton:hover{background:#1976d2;}'
            'QPushButton:disabled{background:#999;}')
        self.btn_auto_eph.clicked.connect(self._descargar_efemerides)
        gp_lay.addRow(self.btn_auto_eph)

        lay.addWidget(self.g_precise)

        self._on_mode_toggle(True)  # Sync visibilidad inicial
        lay.addStretch()
        return w

    # ─────────── TAB BASE IGN ───────────
    def _tab_base(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)

        info = QLabel(
            '⚠️  OBLIGATORIO en PPK. Puedes autocompletar desde el RINEX base\n'
            'y luego corregir con las coordenadas oficiales (ficha IGN) — como en TBC.'
        )
        info.setStyleSheet(
            'background:#fff8e1;border:1px solid #f9a825;border-radius:4px;'
            'padding:7px;color:#e65100;font-weight:bold;'
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        # Selector de formato de entrada
        g_fmt = QGroupBox('Formato de coordenadas')
        fmt_lay = QHBoxLayout(g_fmt)
        self.rb_utm  = QRadioButton('UTM');              self.rb_utm.setChecked(True)
        self.rb_dms  = QRadioButton('Geog. DMS')
        self.rb_dec  = QRadioButton('Geog. decimal')
        self.rb_ecef = QRadioButton('ECEF (X,Y,Z)')
        self.rb_file = QRadioButton('Archivo CSV/JSON/XLSX')
        for rb in [self.rb_utm, self.rb_dms, self.rb_dec, self.rb_ecef, self.rb_file]:
            fmt_lay.addWidget(rb)
            rb.toggled.connect(self._sync_base_format)
        lay.addWidget(g_fmt)

        # Stack de formularios
        self.g_utm_form  = self._build_utm_form()
        self.g_dms_form  = self._build_dms_form()
        self.g_dec_form  = self._build_dec_form()
        self.g_ecef_form = self._build_ecef_form()
        self.g_file_form = self._build_file_form()
        for g in [self.g_utm_form, self.g_dms_form, self.g_dec_form,
                  self.g_ecef_form, self.g_file_form]:
            lay.addWidget(g)

        # Identificación IGN
        g_id = QGroupBox('Identificación del vértice IGN (referencia)')
        id_lay = QFormLayout(g_id)
        # ── Autocompletar desde el RINEX de la base (estilo TBC) ──
        self.btn_auto_base = QPushButton('📥  Autocompletar desde RINEX base')
        self.btn_auto_base.setToolTip(
            'Lee el header del RINEX de la base (pestaña Archivos):\n'
            '• APPROX POSITION XYZ → coordenadas\n'
            '• MARKER NAME → código de estación\n\n'
            '⚠ Las coordenadas del header son APROXIMADAS (~1-2 m).\n'
            'Corrige los valores con la ficha oficial IGN.')
        self.btn_auto_base.setStyleSheet(
            'QPushButton{background:#5e35b1;color:white;font-weight:bold;'
            'padding:6px;border-radius:4px;}'
            'QPushButton:hover{background:#6a45c1;}')
        self.btn_auto_base.clicked.connect(self._autocompletar_base)
        lay.insertWidget(2, self.btn_auto_base)

        self.ed_ign_cod    = QLineEdit(); self.ed_ign_cod.setPlaceholderText('Ej: MDDIO')
        self.ed_ign_nombre = QLineEdit(); self.ed_ign_nombre.setPlaceholderText('Ej: Puerto Maldonado')
        self.cb_ign_orden  = QComboBox()
        self.cb_ign_orden.addItems(['GPS Orden A', 'GPS Orden B', 'GPS Orden C',
                                     'Primer Orden', 'Segundo Orden', 'Tercer Orden'])
        self.ed_ign_epoca  = QLineEdit(); self.ed_ign_epoca.setPlaceholderText('Ej: 2005.0')
        self.ed_ign_sigma_h = QDoubleSpinBox()
        self.ed_ign_sigma_h.setRange(0, 9999); self.ed_ign_sigma_h.setDecimals(4); self.ed_ign_sigma_h.setSuffix(' m')
        self.ed_ign_sigma_v = QDoubleSpinBox()
        self.ed_ign_sigma_v.setRange(0, 9999); self.ed_ign_sigma_v.setDecimals(4); self.ed_ign_sigma_v.setSuffix(' m')
        id_lay.addRow('Código IGN:',   self.ed_ign_cod)
        id_lay.addRow('Nombre:',       self.ed_ign_nombre)
        id_lay.addRow('Orden:',        self.cb_ign_orden)
        id_lay.addRow('Época ref.:',   self.ed_ign_epoca)
        id_lay.addRow('σ horizontal:', self.ed_ign_sigma_h)
        id_lay.addRow('σ vertical:',   self.ed_ign_sigma_v)
        lay.addWidget(g_id)

        # Botón aplicar + resultado
        btn_apply = QPushButton('✅  Validar y aplicar coordenadas de base')
        btn_apply.setObjectName('apply_base')
        btn_apply.clicked.connect(self._apply_base)
        lay.addWidget(btn_apply)

        self.lbl_base_result = QLabel('— Coordenada resultante aparecerá aquí —')
        self.lbl_base_result.setStyleSheet(
            'background:white;border:1px solid #ccc;border-radius:3px;'
            'padding:6px;font-family:monospace;color:#333;'
        )
        self.lbl_base_result.setWordWrap(True)
        lay.addWidget(self.lbl_base_result)
        lay.addStretch()

        self._sync_base_format()
        return w

    # ─────────── FORMULARIOS BASE ───────────
    def _build_utm_form(self):
        g = QGroupBox('Coordenadas UTM')
        lay = QFormLayout(g)
        self.ed_utm_este  = QDoubleSpinBox(); self.ed_utm_este.setRange(100000,999999); self.ed_utm_este.setDecimals(3); self.ed_utm_este.setSuffix(' m E')
        self.ed_utm_norte = QDoubleSpinBox(); self.ed_utm_norte.setRange(7000000,11000000); self.ed_utm_norte.setDecimals(3); self.ed_utm_norte.setSuffix(' m N')
        self.cb_utm_zona  = QComboBox(); self.cb_utm_zona.addItems(['17S','18S','19S','18N','19N'])
        self.ed_utm_h     = QDoubleSpinBox(); self.ed_utm_h.setRange(-200,9000); self.ed_utm_h.setDecimals(4); self.ed_utm_h.setSuffix(' m')
        lay.addRow('Este:',  self.ed_utm_este)
        lay.addRow('Norte:', self.ed_utm_norte)
        lay.addRow('Zona UTM:', self.cb_utm_zona)
        lay.addRow('Altura elipsoidal:', self.ed_utm_h)
        return g

    def _build_dms_form(self):
        g = QGroupBox('Coordenadas Geográficas DMS')
        lay = QFormLayout(g)
        # Latitud
        lat_w = QWidget(); ll = QHBoxLayout(lat_w); ll.setContentsMargins(0,0,0,0)
        self.sp_lat_d = QSpinBox(); self.sp_lat_d.setRange(0,90); self.sp_lat_d.setSuffix(' °')
        self.sp_lat_m = QSpinBox(); self.sp_lat_m.setRange(0,59); self.sp_lat_m.setSuffix(' \'')
        self.sp_lat_s = QDoubleSpinBox(); self.sp_lat_s.setRange(0,59.9999); self.sp_lat_s.setDecimals(5); self.sp_lat_s.setSuffix(' "')
        self.cb_lat_h = QComboBox(); self.cb_lat_h.addItems(['S','N'])
        for w in [self.sp_lat_d, self.sp_lat_m, self.sp_lat_s, self.cb_lat_h]: ll.addWidget(w)
        # Longitud
        lon_w = QWidget(); lo = QHBoxLayout(lon_w); lo.setContentsMargins(0,0,0,0)
        self.sp_lon_d = QSpinBox(); self.sp_lon_d.setRange(0,180); self.sp_lon_d.setSuffix(' °')
        self.sp_lon_m = QSpinBox(); self.sp_lon_m.setRange(0,59); self.sp_lon_m.setSuffix(' \'')
        self.sp_lon_s = QDoubleSpinBox(); self.sp_lon_s.setRange(0,59.9999); self.sp_lon_s.setDecimals(5); self.sp_lon_s.setSuffix(' "')
        self.cb_lon_h = QComboBox(); self.cb_lon_h.addItems(['W','E'])
        for w in [self.sp_lon_d, self.sp_lon_m, self.sp_lon_s, self.cb_lon_h]: lo.addWidget(w)
        self.sp_dms_h = QDoubleSpinBox(); self.sp_dms_h.setRange(-200,9000); self.sp_dms_h.setDecimals(4); self.sp_dms_h.setSuffix(' m')
        lay.addRow('Latitud:',  lat_w)
        lay.addRow('Longitud:', lon_w)
        lay.addRow('Altura:',   self.sp_dms_h)
        return g

    def _build_dec_form(self):
        g = QGroupBox('Coordenadas Geográficas Decimales')
        lay = QFormLayout(g)
        self.sp_dec_lat = QDoubleSpinBox(); self.sp_dec_lat.setRange(-90,90); self.sp_dec_lat.setDecimals(10); self.sp_dec_lat.setSuffix(' °')
        self.sp_dec_lon = QDoubleSpinBox(); self.sp_dec_lon.setRange(-180,180); self.sp_dec_lon.setDecimals(10); self.sp_dec_lon.setSuffix(' °')
        self.sp_dec_h   = QDoubleSpinBox(); self.sp_dec_h.setRange(-200,9000); self.sp_dec_h.setDecimals(4); self.sp_dec_h.setSuffix(' m')
        lay.addRow('Latitud:',  self.sp_dec_lat)
        lay.addRow('Longitud:', self.sp_dec_lon)
        lay.addRow('Altura:',   self.sp_dec_h)
        return g

    def _build_ecef_form(self):
        g = QGroupBox('Coordenadas ECEF (Cartesianas WGS84)')
        lay = QFormLayout(g)
        self.sp_ecef_x = QDoubleSpinBox(); self.sp_ecef_x.setRange(-7e6,7e6); self.sp_ecef_x.setDecimals(4); self.sp_ecef_x.setSuffix(' m')
        self.sp_ecef_y = QDoubleSpinBox(); self.sp_ecef_y.setRange(-7e6,7e6); self.sp_ecef_y.setDecimals(4); self.sp_ecef_y.setSuffix(' m')
        self.sp_ecef_z = QDoubleSpinBox(); self.sp_ecef_z.setRange(-7e6,7e6); self.sp_ecef_z.setDecimals(4); self.sp_ecef_z.setSuffix(' m')
        lay.addRow('X:', self.sp_ecef_x)
        lay.addRow('Y:', self.sp_ecef_y)
        lay.addRow('Z:', self.sp_ecef_z)
        return g

    def _build_file_form(self):
        g = QGroupBox('Carga desde archivo (CSV/JSON/XLSX)')
        lay = QFormLayout(g)
        row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
        self.ed_base_file = QLineEdit(); self.ed_base_file.setPlaceholderText('Archivo con coords de base...')
        btn = QPushButton('...'); btn.setObjectName('browse'); btn.setFixedWidth(32)
        btn.clicked.connect(lambda: self._browse(self.ed_base_file,
                            'CSV/JSON/XLSX (*.csv *.json *.xlsx *.xls)'))
        rl.addWidget(self.ed_base_file); rl.addWidget(btn)
        lay.addRow('Archivo:', row)
        lbl = QLabel('Campos aceptados: este/norte/zona, lat/lon, x/y/z\n'
                     'Ver README para formato esperado.')
        lbl.setStyleSheet('color:#555;font-size:10px;')
        lay.addRow(lbl)
        return g

    # ─────────── TAB CONFIG ───────────
    def _tab_config(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)

        g_sol = QGroupBox('Tipo de solución')
        gs = QFormLayout(g_sol)
        self.cb_sol_type = QComboBox()
        self.cb_sol_type.addItems(['Estático (static)', 'Cinemático (kinematic)',
                                    'Stop & Go (movbase)',
                                    '📡 Submétrico DGPS-Estático (dosel/línea larga)',
                                    '📡 Submétrico DGPS-Cinemático',
                                    'PPP-Estático (ppp-static)',
                                    'PPP-Cinemático (ppp-kinematic)'])
        self.cb_sol_type.setToolTip(
            'Estático/Cinemático: busca FIX centimétrico (requiere buena\n'
            'señal y línea base corta).\n\n'
            '📡 Submétrico DGPS: usa código diferencial (no fase). NO resuelve\n'
            'ambigüedades → IMPOSIBLE generar falsos fix. Precisión honesta\n'
            '0.3-1 m. Ideal para puntos bajo dosel o a gran distancia de la\n'
            'base, donde el FIX no es alcanzable de forma confiable.')
        self.cb_filter = QComboBox()
        self.cb_filter.addItems(['Forward', 'Backward', 'Combined (forward+backward)'])
        gs.addRow('Modo solución:', self.cb_sol_type)
        gs.addRow('Filtro Kalman:', self.cb_filter)
        lbl_dgps = QLabel(
            'Sugerencia: si tus puntos quedan en FLOAT/NO CONFIABLE por dosel '
            'o distancia, usa Submétrico DGPS para una coordenada honesta.')
        lbl_dgps.setWordWrap(True)
        lbl_dgps.setStyleSheet('color:#666;font-size:10px;')
        gs.addRow('', lbl_dgps)
        lay.addWidget(g_sol)

        g_sys = QGroupBox('Constelaciones GNSS')
        gsy = QHBoxLayout(g_sys)
        self.chk_gps = QCheckBox('GPS');     self.chk_gps.setChecked(True)
        self.chk_glo = QCheckBox('GLONASS'); self.chk_glo.setChecked(True)
        self.chk_gal = QCheckBox('Galileo'); self.chk_gal.setChecked(True)
        self.chk_bds = QCheckBox('BeiDou')
        self.chk_sbs = QCheckBox('SBAS')
        for c in [self.chk_gps, self.chk_glo, self.chk_gal, self.chk_bds, self.chk_sbs]:
            gsy.addWidget(c)
        lay.addWidget(g_sys)

        g_freq = QGroupBox('Frecuencias y calidad')
        gf = QFormLayout(g_freq)
        self.cb_freq = QComboBox()
        self.cb_freq.addItems(['L1 (simple)', 'L1+L2 (doble)', 'L1+L2+L5 (triple)'])
        self.cb_freq.setCurrentIndex(1)
        self.sp_elev = QSpinBox(); self.sp_elev.setRange(0,30); self.sp_elev.setValue(10); self.sp_elev.setSuffix(' °')
        self.sp_snr  = QSpinBox(); self.sp_snr.setRange(0,50); self.sp_snr.setSuffix(' dBHz')
        gf.addRow('Frecuencia:', self.cb_freq)
        gf.addRow('Máscara elevación:', self.sp_elev)
        gf.addRow('Umbral SNR mín.:',   self.sp_snr)
        lay.addWidget(g_freq)
        lay.addStretch()
        return w

    # ─────────── TAB INFORME ───────────
    def _tab_informe(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)

        g_prof = QGroupBox('Datos del profesional')
        gp = QFormLayout(g_prof)
        self.ed_prof    = QLineEdit(); self.ed_prof.setPlaceholderText('Ing. Nombre Apellido')
        self.ed_cip     = QLineEdit(); self.ed_cip.setPlaceholderText('CIP 000000')
        self.ed_empresa = QLineEdit(); self.ed_empresa.setPlaceholderText('Cliente / empresa')
        self.ed_proy    = QLineEdit(); self.ed_proy.setPlaceholderText('Nombre del proyecto')
        self.ed_lugar   = QLineEdit(); self.ed_lugar.setPlaceholderText('Ej: Madre de Dios, Perú')
        gp.addRow('Profesional:', self.ed_prof)
        gp.addRow('CIP:',        self.ed_cip)
        gp.addRow('Empresa:',    self.ed_empresa)
        gp.addRow('Proyecto:',   self.ed_proy)
        gp.addRow('Lugar:',      self.ed_lugar)
        lay.addWidget(g_prof)

        g_eq = QGroupBox('Equipo GNSS')
        geq = QFormLayout(g_eq)
        self.ed_receptor = QLineEdit(); self.ed_receptor.setPlaceholderText('Modelo receptor')
        # Antena: combo EDITABLE. Vacío = solo documental (comportamiento
        # v2.4). Poblado desde ANTEX = nombre normalizado IGS → RTKLIB
        # aplica PCO/PCV reales (posopt2), como TBC.
        self.cb_antena = QComboBox()
        self.cb_antena.setEditable(True)
        self.cb_antena.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cb_antena.lineEdit().setPlaceholderText(
            'Modelo antena (cargar ANTEX para lista IGS)')
        self.ed_serial   = QLineEdit(); self.ed_serial.setPlaceholderText('N° de serie')
        geq.addRow('Receptor:', self.ed_receptor)
        geq.addRow('Antena:',   self.cb_antena)
        geq.addRow('N° serie:', self.ed_serial)
        lay.addWidget(g_eq)

        # ── Calibración de antena (ANTEX) ──
        g_atx = QGroupBox('Calibración de antena (ANTEX)')
        gatx = QFormLayout(g_atx)
        self._antex_path = ''        # .atx final (maestro o fusionado)
        self._antex_customs = []     # .atx del usuario (ej. METX5)

        atx_row = QWidget(); atx_hl = QHBoxLayout(atx_row)
        atx_hl.setContentsMargins(0, 0, 0, 0)
        self.btn_atx_igs = QPushButton('Descargar IGS20')
        self.btn_atx_igs.setObjectName('browse')
        self.btn_atx_igs.setToolTip(
            'Descarga el ANTEX maestro del IGS (igs20.atx): calibraciones\n'
            'de Trimble, CHCNAV, Leica, South, Emlid y miles de antenas más.')
        self.btn_atx_custom = QPushButton('ANTEX del fabricante…')
        self.btn_atx_custom.setObjectName('browse')
        self.btn_atx_custom.setToolTip(
            'Agrega un .atx del fabricante que no esté en el maestro IGS\n'
            '(ej. METX5 de Mettatec, calibrado por el NGS). Se fusiona\n'
            'con el maestro sin sobrescribirlo.')
        atx_hl.addWidget(self.btn_atx_igs)
        atx_hl.addWidget(self.btn_atx_custom)
        gatx.addRow(atx_row)

        self.lbl_atx = QLabel('Sin ANTEX: el campo antena es solo documental '
                              '(sin corrección PCO/PCV).')
        self.lbl_atx.setStyleSheet('color:#666;font-size:10px;')
        self.lbl_atx.setWordWrap(True)
        gatx.addRow(self.lbl_atx)
        lay.addWidget(g_atx)

        self.btn_atx_igs.clicked.connect(self._load_antex_master)
        self.btn_atx_custom.clicked.connect(self._load_antex_custom)

        # ── Altura de antena — CRÍTICO para precisión ──
        g_ant = QGroupBox('Altura de antena (CRÍTICO)')
        g_ant.setStyleSheet(
            'QGroupBox{font-weight:bold;color:#c0392b;}'
        )
        gant = QFormLayout(g_ant)

        ant_row = QWidget()
        ant_hl  = QHBoxLayout(ant_row)
        ant_hl.setContentsMargins(0,0,0,0)
        self.spin_ant_height = QDoubleSpinBox()
        self.spin_ant_height.setRange(0.0, 9.999)
        self.spin_ant_height.setDecimals(3)
        self.spin_ant_height.setValue(0.0)
        self.spin_ant_height.setSuffix('  m')
        self.spin_ant_height.setSingleStep(0.001)
        lbl_ant_info = QLabel('Medir desde el punto al borde inferior de la antena')
        lbl_ant_info.setStyleSheet('color:#666;font-size:10px;')
        ant_hl.addWidget(self.spin_ant_height)
        gant.addRow('Altura rover:', ant_row)
        gant.addRow('', lbl_ant_info)

        lbl_cors = QLabel(
            'Para CORS IGN (MD01/MD04): altura de antena '
            'de la base se lee del RINEX header.'
        )
        lbl_cors.setStyleSheet('color:#1565c0;font-size:10px;padding:3px;')
        gant.addRow(lbl_cors)
        lay.addWidget(g_ant)

        g_notas = QGroupBox('Observaciones técnicas')
        gn = QVBoxLayout(g_notas)
        self.ed_notas = QTextEdit(); self.ed_notas.setMaximumHeight(70)
        self.ed_notas.setPlaceholderText('Condiciones de campo, interferencias, observaciones...')
        gn.addWidget(self.ed_notas)
        lay.addWidget(g_notas)

        g_punto = QGroupBox('Nombre del punto (para ficha IGN)')
        gpt = QFormLayout(g_punto)
        self.ed_nombre_punto = QLineEdit(); self.ed_nombre_punto.setPlaceholderText('Ej: BM-001')
        gpt.addRow('Nombre punto:', self.ed_nombre_punto)
        lay.addWidget(g_punto)

        lay.addStretch()
        return w

    # ─────────── TAB SALIDA ───────────
    def _tab_salida(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)

        g_dir = QGroupBox('Directorio de salida')
        gd = QFormLayout(g_dir)
        row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
        self.ed_out_dir    = QLineEdit(); self.ed_out_dir.setPlaceholderText('Carpeta de salida...')
        self.ed_out_prefix = QLineEdit(); self.ed_out_prefix.setPlaceholderText('Prefijo archivos (Ej: PROYECTO_PPK)')
        btn = QPushButton('...'); btn.setObjectName('browse'); btn.setFixedWidth(32)
        btn.clicked.connect(lambda: self._browse_dir(self.ed_out_dir))
        rl.addWidget(self.ed_out_dir); rl.addWidget(btn)
        gd.addRow('Carpeta:', row)
        gd.addRow('Prefijo:', self.ed_out_prefix)
        lay.addWidget(g_dir)

        g_exp = QGroupBox('Formatos de exportación GIS')
        ge = QVBoxLayout(g_exp)
        self.chk_gpkg    = QCheckBox('GeoPackage (.gpkg)'); self.chk_gpkg.setChecked(True)
        self.chk_shp     = QCheckBox('Shapefile (.shp)')
        self.chk_kml     = QCheckBox('KML (Google Earth)')
        self.chk_geojson = QCheckBox('GeoJSON')
        self.chk_csv     = QCheckBox('CSV coordenadas'); self.chk_csv.setChecked(True)
        for c in [self.chk_gpkg, self.chk_shp, self.chk_kml, self.chk_geojson, self.chk_csv]:
            ge.addWidget(c)
        lay.addWidget(g_exp)

        g_capa = QGroupBox('Qué cargar en QGIS')
        gc = QVBoxLayout(g_capa)

        # Modo de salida — por defecto SOLO el punto corregido
        self.chk_solo_corregido = QCheckBox(
            'Solo el punto corregido (coordenada final + detalles)')
        self.chk_solo_corregido.setChecked(True)
        self.chk_solo_corregido.setStyleSheet('font-weight:bold;color:#1a6e2e;')
        gc.addWidget(self.chk_solo_corregido)

        lbl_info = QLabel(
            'Recomendado: carga únicamente la coordenada corregida\n'
            'con todos los datos del post-proceso en sus atributos.')
        lbl_info.setStyleSheet('color:#666;font-size:10px;')
        gc.addWidget(lbl_info)

        # Opciones avanzadas (solo si destildan "solo corregido")
        self.grp_capas_detalle = QGroupBox('Capas adicionales (avanzado)')
        gcd = QVBoxLayout(self.grp_capas_detalle)
        self.chk_fix    = QCheckBox('Épocas Fix (Q=1)  — verde');     self.chk_fix.setChecked(True)
        self.chk_float  = QCheckBox('Épocas Float (Q=2) — amarillo'); self.chk_float.setChecked(True)
        self.chk_single = QCheckBox('Épocas Single (Q=4) — rojo')
        self.chk_ppp    = QCheckBox('Épocas PPP (Q=6)   — morado');   self.chk_ppp.setChecked(True)
        self.chk_tray   = QCheckBox('Trayectoria como línea')
        for c in [self.chk_fix, self.chk_float, self.chk_single, self.chk_ppp, self.chk_tray]:
            gcd.addWidget(c)
        gc.addWidget(self.grp_capas_detalle)

        # Conectar: deshabilitar detalle cuando "solo corregido" está activo
        self.grp_capas_detalle.setEnabled(False)
        self.chk_solo_corregido.toggled.connect(
            lambda checked: self.grp_capas_detalle.setEnabled(not checked))

        lay.addWidget(g_capa)
        lay.addStretch()
        return w

    # ─────────── BARRA INFERIOR ───────────
    def _bottom_bar(self):
        f = QFrame(); lay = QVBoxLayout(f); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        self.progress = QProgressBar(); self.progress.setValue(0)
        lay.addWidget(self.progress)
        row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
        self.btn_run    = QPushButton('▶  Ejecutar post-proceso')
        self.btn_run.setObjectName('run')
        self.btn_run.clicked.connect(self._run)
        self.btn_report = QPushButton('📋  Informe + Ficha')
        self.btn_report.setObjectName('report')
        self.btn_report.clicked.connect(self._generate_reports)
        self.btn_report.setEnabled(False)
        rl.addWidget(self.btn_run, 2); rl.addWidget(self.btn_report, 1)
        lay.addWidget(row)
        return f

    def _log_console(self):
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(110)
        self.log_box.setStyleSheet(
            'background:#1e1e2e;color:#cdd6f4;'
            'font-family:Consolas,monospace;font-size:10px;'
            'border-radius:4px;border:none;'
        )
        return self.log_box

    # ══════════════════════════════════════════════
    # HELPERS UI
    # ══════════════════════════════════════════════
    def _file_field(self, form_layout, label, filt, optional=False):
        row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0,0,0,0)
        ed = QLineEdit(); ed.setPlaceholderText('Seleccionar...')
        if optional: label += ' (opcional)'
        btn = QPushButton('...'); btn.setObjectName('browse'); btn.setFixedWidth(32)
        btn.clicked.connect(lambda: self._browse(ed, filt))
        lay.addWidget(ed); lay.addWidget(btn)
        form_layout.addRow(label, row)
        return ed

    def _browse(self, ed, filt):
        p, _ = QFileDialog.getOpenFileName(self, 'Seleccionar', '', filt)
        if p: ed.setText(p)

    def _browse_dir(self, ed):
        p = QFileDialog.getExistingDirectory(self, 'Carpeta de salida')
        if p: ed.setText(p)

    def _log(self, msg, level='info'):
        colors = {'info':'#cdd6f4','ok':'#a6e3a1','warn':'#fab387','error':'#f38ba8'}
        self.log_box.append(
            f'<span style="color:{colors.get(level,colors["info"])};">{msg}</span>'
        )

    def _descargar_efemerides(self):
        """Descarga automática de SP3/CLK según la fecha del RINEX rover."""
        rover = self.ed_rover.text().strip()
        if not rover or not os.path.isfile(rover):
            QMessageBox.warning(self, 'YF · Efemérides',
                'Primero selecciona el archivo RINEX del rover\n'
                '(pestaña Archivos). La fecha se lee de su header.')
            return

        self.btn_auto_eph.setEnabled(False)
        self.btn_auto_eph.setText('⏳ Descargando...')
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            from ..gnss_engine.ephemeris_downloader import descargar_efemerides
            out_dir = os.path.dirname(rover)
            res = descargar_efemerides(
                rover, out_dir=out_dir,
                log=lambda m: (self._log(m), QApplication.processEvents()),
                incluir_clk=True
            )
            if res['sp3']:
                self.ed_sp3.setText(res['sp3'])
                if res['clk']:
                    self.ed_clk.setText(res['clk'])
                self._log(f"✅ {res['msg']} — campos completados", 'ok')
                QMessageBox.information(self, 'YF · Efemérides',
                    f"Efemérides {res['tipo']} descargadas y cargadas.\n\n"
                    f"SP3: {os.path.basename(res['sp3'])}\n"
                    + (f"CLK: {os.path.basename(res['clk'])}" if res['clk']
                       else "CLK: no disponible (RTKLIB usará relojes del SP3)"))
            else:
                QMessageBox.warning(self, 'YF · Efemérides',
                    res['msg'] + '\n\nPuedes descargar manualmente de:\n'
                    'https://cddis.nasa.gov/archive/gnss/products/')
        except Exception as e:
            import traceback
            self._log(f'❌ Error descargando efemérides: {e}', 'error')
            traceback.print_exc()
            QMessageBox.critical(self, 'YF · Efemérides', f'Error: {e}')
        finally:
            self.btn_auto_eph.setEnabled(True)
            self.btn_auto_eph.setText('⬇  Descargar efemérides automáticamente')

    def _on_mode_toggle(self, ppk):
        self.g_base_rinex.setVisible(self.rb_ppk.isChecked())
        # Los archivos precisos se muestran SIEMPRE:
        # - PPP: obligatorios
        # - PPK: opcionales (mejoran línea base larga >20km)
        self.g_precise.setVisible(True)
        if self.rb_ppp.isChecked():
            self.g_precise.setTitle('Archivos precisos (PPP — obligatorios)')
        else:
            self.g_precise.setTitle('Archivos precisos (opcionales en PPK, mejoran línea base larga)')

    # ══════════════════════════════════════════════
    # LOTE: manejo de lista y ejecución
    # ══════════════════════════════════════════════
    def _batch_files(self):
        return [self.lst_rovers.item(i).text()
                for i in range(self.lst_rovers.count())]

    def _batch_update_count(self):
        n = self.lst_rovers.count()
        self.lbl_batch_count.setText(f'{n} archivo{"s" if n != 1 else ""} en lote')

    def _batch_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Agregar rovers al lote', '',
            'RINEX Obs (*.*o *.*O *.obs *.OBS *.rnx *.RNX);;Todos (*.*)')
        existentes = set(self._batch_files())
        for f in files:
            if f not in existentes:
                self.lst_rovers.addItem(f)
        self._batch_update_count()

    @staticmethod
    def _es_rover_obs(nombre):
        """True si el archivo es una OBSERVACIÓN rover (no navegación).

        Acepta:
          .obs / .OBS
          .NNo  (año + 'o': .26o, .25o, .24o ...)   ← formato más común
          .o / .O  (extensión corta Trimble)
          *_MO.rnx  (RINEX 3 nombre largo, observación)
        Rechaza navegación: .NNn .NNg .NNl .NNp .NNc .NNmix .nav .sp3 .clk ...
        """
        import re as _re
        low = nombre.lower()
        # Rechazar explícitamente navegación y productos
        if _re.search(r'\.[0-9]{2}[nglpcd]$', low):      # .26n .26g .26l .26p .26c .26d
            return False
        if low.endswith('.26mix') or low.endswith('mix'):
            return False
        if low.endswith(('.nav', '.sp3', '.clk', '.ionex', '.t04', '.t02',
                         '.gnav', '.eph', '.inx')):
            return False
        # Aceptar observación
        if low.endswith('.obs'):
            return True
        if _re.search(r'\.[0-9]{2}o$', low):              # .26o .25o ...
            return True
        if low.endswith('.o'):                            # extensión corta Trimble
            return True
        if '_mo' in low and low.endswith('.rnx'):         # RINEX 3 largo
            return True
        return False

    def _batch_add_folder(self):
        carpeta = QFileDialog.getExistingDirectory(self, 'Carpeta de la campaña')
        if not carpeta:
            return
        existentes = set(self._batch_files())
        nuevos = 0
        for fn in sorted(os.listdir(carpeta)):
            if self._es_rover_obs(fn):
                full = os.path.join(carpeta, fn)
                if os.path.isfile(full) and full not in existentes:
                    self.lst_rovers.addItem(full)
                    nuevos += 1
        self._batch_update_count()
        self._log(f'📁 {nuevos} rovers detectados en la carpeta', 'info')

    def _batch_remove_selected(self):
        for item in self.lst_rovers.selectedItems():
            self.lst_rovers.takeItem(self.lst_rovers.row(item))
        self._batch_update_count()

    def _ensure_rtklib_binary(self):
        """Verifica el binario rnx2rtkp; si falta, lo instala automáticamente.
        Retorna True si está disponible, False si no se pudo obtener."""
        try:
            gnss_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            bin_dir = os.path.join(gnss_dir, 'rtklib_bin')
            import platform as _plat
            exe_name = 'rnx2rtkp.exe' if _plat.system() == 'Windows' else 'rnx2rtkp'
            exe_path = os.path.join(bin_dir, exe_name)
            if os.path.isfile(exe_path):
                return True
            self._log('⚠ rnx2rtkp no encontrado — instalando automáticamente...', 'warn')
            from qgis.PyQt.QtWidgets import QApplication
            QApplication.processEvents()
            from ..gnss_engine.ephemeris_downloader import instalar_rtklib
            resultado = instalar_rtklib(
                bin_dir,
                log=lambda m: (self._log(m), QApplication.processEvents()))
            if not resultado:
                QMessageBox.critical(self, 'YF · GNSS',
                    'No se pudo descargar RTKLIB automáticamente.\n'
                    'Verifica tu conexión a internet e intenta de nuevo.')
                return False
            return True
        except Exception as ex:
            self._log(f'⚠ Verificación de binario: {ex}', 'warn')
            return True  # dejar continuar; el processor reportará si falla

    def _run_batch(self, batch_files):
        """Lanza el procesamiento por lotes."""
        import traceback
        # Template de parámetros: usa el primer archivo del lote como
        # rover para pasar la validación del formulario
        # El lote NO requiere cargar archivos en el formulario individual:
        # tomamos el primer archivo del lote como plantilla y auto-detectamos
        # su navegación para pasar la validación de parámetros.
        from ..gnss_engine.batch_processor import detect_nav_for_rover
        self.ed_rover.blockSignals(True)
        self.ed_rover.setText(batch_files[0])
        self.ed_rover.blockSignals(False)
        _nav, _gnav = detect_nav_for_rover(batch_files[0])
        if _nav and not self.ed_nav.text().strip():
            self.ed_nav.setText(_nav)
        if _gnav and not self.ed_gnav.text().strip():
            self.ed_gnav.setText(_gnav)
        try:
            template = self._collect_params()
        except ValueError as ex:
            QMessageBox.warning(self, 'Parámetros incompletos', str(ex))
            return
        except Exception as ex:
            QMessageBox.critical(self, 'Error en parámetros',
                                 f'{type(ex).__name__}: {ex}\n\n{traceback.format_exc()}')
            return

        if template.base_coords is None:
            QMessageBox.warning(self, 'Base sin validar',
                'Valida las coordenadas de la base IGN primero\n'
                '(pestaña Base IGN → Validar y aplicar).')
            return

        # Verificar/instalar binario antes del lote
        if not self._ensure_rtklib_binary():
            return

        # Verificar binario RTKLIB — auto-instalar si falta (igual que single)
        try:
            gnss_dir = os.path.join(
                self.plugin_dir, 'tools', 'gnss_postprocess')
            import platform as _plat
            exe_name = 'rnx2rtkp.exe' if _plat.system() == 'Windows' else 'rnx2rtkp'
            exe_path = os.path.join(gnss_dir, 'rtklib_bin', exe_name)
            if not os.path.isfile(exe_path):
                self._log('⚠ rnx2rtkp no encontrado — instalando automáticamente...', 'warn')
                from qgis.PyQt.QtWidgets import QApplication
                QApplication.processEvents()
                from ..gnss_engine.ephemeris_downloader import instalar_rtklib
                if not instalar_rtklib(
                        os.path.join(gnss_dir, 'rtklib_bin'),
                        log=lambda m: (self._log(m), QApplication.processEvents())):
                    QMessageBox.critical(self, 'YF · Lote',
                        'No se pudo instalar RTKLIB. Verifica tu conexión.')
                    return
        except Exception as ex:
            self._log(f'⚠ Verificación de binario: {ex}', 'warn')

        from ..gnss_engine.batch_processor import BatchProcessor
        self.batch_proc = BatchProcessor(batch_files, template, self.plugin_dir)
        self.batch_proc.log.connect(self._log)
        self.batch_proc.progress.connect(self.progress.setValue)
        self.batch_proc.file_progress.connect(
            lambda i, n, nom: self._log(f'⏳ Procesando {i}/{n}: {nom}', 'info'))
        self.batch_proc.batch_finished.connect(self._on_batch_finished)

        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self._last_params = template
        self._log(f'▶ LOTE: iniciando {len(batch_files)} archivos…', 'info')
        self.batch_proc.start()

    def _on_batch_finished(self, resultados):
        """Consolida todos los puntos (OccResult) en UNA capa + resumen TBC."""
        import traceback
        self.btn_run.setEnabled(True)
        if not resultados:
            self._log('Lote sin resultados.', 'warn')
            return
        # Guardar para el informe (estilo TBC)
        self._last_occ_results = resultados
        self.btn_report.setEnabled(True)   # habilitar informe tras lote
        _bp = getattr(self, 'batch_proc', None)
        self._last_proc_info = {
            'modo': 'Procesamiento por lotes (varios archivos)',
            'archivos': sorted(set(getattr(r, 'archivo', '') for r in resultados)),
            'cmd': getattr(_bp, 'last_cmd', ''),
            'binary': getattr(_bp, 'last_binary', ''),
            'pos': getattr(_bp, 'last_pos', ''),
        }
        try:
            from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature,
                                   QgsGeometry, QgsPointXY, QgsField)
            from qgis.PyQt.QtCore import QVariant

            capa = QgsVectorLayer('Point?crs=EPSG:32719',
                                  'Campania_GNSS_corregidos', 'memory')
            prov = capa.dataProvider()
            prov.addAttributes([
                QgsField('archivo',   QVariant_String),
                QgsField('punto',     QVariant_String),
                QgsField('calidad',   QVariant_String),
                QgsField('este',      QVariant_Double),
                QgsField('norte',     QVariant_Double),
                QgsField('altura',    QVariant_Double),
                QgsField('sigma_h_m', QVariant_Double),
                QgsField('sigma_v_m', QVariant_Double),
                QgsField('sigma_h_cm', QVariant_String),
                QgsField('sigma_v_cm', QVariant_String),
                QgsField('disp_h_m',  QVariant_Double),
                QgsField('ep_usadas', QVariant_Int),
                QgsField('fix_pct',   QVariant_Double),
                QgsField('confiable', QVariant_String),
            ])
            capa.updateFields()

            resumen = []
            for r in resultados:
                if getattr(r, 'lat', 0) == 0 and getattr(r, 'lon', 0) == 0:
                    resumen.append((getattr(r, 'archivo', ''), r.name, 'SIN SOLUCIÓN', False))
                    continue
                f = QgsFeature(capa.fields())
                f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(r.este, r.norte)))
                f['archivo'] = getattr(r, 'archivo', '')
                f['punto'] = r.name
                f['calidad'] = r.q_label
                f['este'] = round(r.este, 4)
                f['norte'] = round(r.norte, 4)
                f['altura'] = round(r.h, 4)
                f['sigma_h_m'] = round(r.sigma_h, 4)
                f['sigma_v_m'] = round(r.sigma_v, 4)
                f['sigma_h_cm'] = f'{r.sigma_h*100:.1f} cm'
                f['sigma_v_cm'] = f'{r.sigma_v*100:.1f} cm'
                f['disp_h_m'] = round(r.dispersion_h, 4)
                f['ep_usadas'] = r.n_used
                f['fix_pct'] = round(r.fix_pct, 1)
                f['confiable'] = 'SÍ' if r.confiable else 'NO'
                prov.addFeatures([f])
                resumen.append((getattr(r, 'archivo', ''), r.name, r.q_label, r.confiable))

            capa.updateExtents()
            QgsProject.instance().addMapLayer(capa)

            n_ok = sum(1 for *_, conf in resumen if conf)
            self._log(f'═══ CAMPAÑA: {len(resumen)} puntos '
                      f'({n_ok} confiables) ═══', 'info')
            for arch, punto, calidad, conf in resumen:
                self._log(f'  {arch}/{punto:<8} → {calidad}',
                          'ok' if conf else 'warn')
            self._log(f'🗺 Capa: Campania_GNSS_corregidos '
                      f'({capa.featureCount()} puntos)', 'ok')
        except Exception as ex:
            self._log(f'❌ Error consolidando lote: {ex}', 'error')
            traceback.print_exc()

    def _run_occupations(self):
        import traceback
        rover = self.ed_rover.text().strip()
        if not rover or not os.path.isfile(rover):
            QMessageBox.warning(self, 'YF · Ocupaciones',
                'Selecciona el archivo RINEX del rover.')
            return
        try:
            template = self._collect_params()
        except ValueError as ex:
            QMessageBox.warning(self, 'Parámetros incompletos', str(ex)); return
        except Exception as ex:
            QMessageBox.critical(self, 'Error', f'{type(ex).__name__}: {ex}'); return

        if template.base_coords is None:
            QMessageBox.warning(self, 'Base sin validar',
                'Valida la base IGN primero (pestaña Base IGN).'); return

        # Verificar/instalar binario
        try:
            gnss_dir = os.path.join(self.plugin_dir, 'tools', 'gnss_postprocess')
            import platform as _plat
            exe = 'rnx2rtkp.exe' if _plat.system() == 'Windows' else 'rnx2rtkp'
            if not os.path.isfile(os.path.join(gnss_dir, 'rtklib_bin', exe)):
                self._log('Instalando RTKLIB...', 'warn')
                from qgis.PyQt.QtWidgets import QApplication
                QApplication.processEvents()
                from ..gnss_engine.ephemeris_downloader import instalar_rtklib
                instalar_rtklib(os.path.join(gnss_dir, 'rtklib_bin'),
                    log=lambda m: (self._log(m), QApplication.processEvents()))
        except Exception as ex:
            self._log(f'Binario: {ex}', 'warn')

        from ..gnss_engine.occupation_processor import OccupationProcessor
        self.occ_proc = OccupationProcessor(template, self.plugin_dir, rover)
        self.occ_proc.log.connect(self._log)
        self.occ_proc.progress.connect(self.progress.setValue)
        self.occ_proc.finished_occ.connect(self._on_occupations_finished)
        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self._last_params = template
        self._log('▶ Modo OCUPACIONES: procesando…', 'info')
        self.occ_proc.start()

    def _on_occupations_finished(self, resultados):
        import traceback
        self.btn_run.setEnabled(True)
        if not resultados:
            self._log('Sin resultados de ocupaciones.', 'warn'); return
        # Guardar para el informe (estilo TBC)
        self._last_occ_results = resultados
        self.btn_report.setEnabled(True)   # habilitar informe tras ocupaciones
        self._last_proc_info = {
            'modo': 'Ocupaciones múltiples (1 archivo)',
            'cmd': getattr(getattr(self, 'occ_proc', None), 'last_cmd', ''),
            'pos': getattr(getattr(self, 'occ_proc', None), 'last_pos', ''),
            'archivos': [self.ed_rover.text().strip()],
        }
        try:
            from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature,
                                   QgsGeometry, QgsPointXY, QgsField)
            from qgis.PyQt.QtCore import QVariant

            crs_id = 'EPSG:32719'
            capa = QgsVectorLayer(f'Point?crs={crs_id}',
                                  'Ocupaciones_GNSS_corregidas', 'memory')
            prov = capa.dataProvider()
            prov.addAttributes([
                QgsField('punto',     QVariant_String),
                QgsField('calidad',   QVariant_String),
                QgsField('este',      QVariant_Double),
                QgsField('norte',     QVariant_Double),
                QgsField('altura',    QVariant_Double),
                QgsField('sigma_h_m', QVariant_Double),
                QgsField('sigma_v_m', QVariant_Double),
                QgsField('sigma_h_cm', QVariant_String),
                QgsField('sigma_v_cm', QVariant_String),
                QgsField('disp_h_m',  QVariant_Double),
                QgsField('ep_usadas', QVariant_Int),
                QgsField('ep_total',  QVariant_Int),
                QgsField('fix_pct',   QVariant_Double),
                QgsField('dur_seg',   QVariant_Double),
                QgsField('confiable', QVariant_String),
            ])
            capa.updateFields()

            for r in resultados:
                if r.lat == 0 and r.lon == 0:
                    continue
                f = QgsFeature(capa.fields())
                f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(r.este, r.norte)))
                f['punto'] = r.name
                f['calidad'] = r.q_label
                f['este'] = round(r.este, 4)
                f['norte'] = round(r.norte, 4)
                f['altura'] = round(r.h, 4)
                f['sigma_h_m'] = round(r.sigma_h, 4)
                f['sigma_v_m'] = round(r.sigma_v, 4)
                f['sigma_h_cm'] = f'{r.sigma_h*100:.1f} cm'
                f['sigma_v_cm'] = f'{r.sigma_v*100:.1f} cm'
                f['disp_h_m'] = round(r.dispersion_h, 4)
                f['ep_usadas'] = r.n_used
                f['ep_total'] = r.n_total
                f['fix_pct'] = round(r.fix_pct, 1)
                f['dur_seg'] = round(r.duration_s, 0)
                f['confiable'] = 'SÍ' if r.confiable else 'NO'
                prov.addFeatures([f])

            capa.updateExtents()
            QgsProject.instance().addMapLayer(capa)

            # Tabla resumen estilo TBC en el log
            n_ok = sum(1 for r in resultados if r.confiable)
            self._log(f'═══ {len(resultados)} OCUPACIONES '
                      f'({n_ok} confiables) ═══', 'info')
            self._log(f'{"Punto":<8}{"Calidad":<22}{"σH":>7}{"Disp":>8}{"%Fix":>7}', 'info')
            for r in resultados:
                self._log(
                    f'{r.name:<8}{r.q_label:<22}'
                    f'{r.sigma_h*100:>6.1f}c{r.dispersion_h*100:>7.1f}c{r.fix_pct:>6.0f}%',
                    'ok' if r.confiable else 'warn')
            self._log(f'🗺 Capa: Ocupaciones_GNSS_corregidas '
                      f'({capa.featureCount()} puntos)', 'ok')
        except Exception as ex:
            self._log(f'❌ Error consolidando ocupaciones: {ex}', 'error')
            traceback.print_exc()

    def _check_occupations(self, rover_path):
        """Detecta ocupaciones múltiples y avisa al usuario."""
        if not rover_path or not os.path.isfile(rover_path):
            self.lbl_occ_info.setText('— selecciona un rover para detectar ocupaciones —')
            return
        try:
            from ..gnss_engine.occupation_parser import parse_occupations
            occs = parse_occupations(rover_path)
            if len(occs) > 1:
                nombres = ', '.join(o.name for o in occs[:6])
                if len(occs) > 6:
                    nombres += f' … (+{len(occs)-6})'
                self.lbl_occ_info.setText(
                    f'✅ {len(occs)} ocupaciones detectadas: {nombres}\n'
                    f'Activa la casilla para resolver cada punto por separado.')
                self.chk_occ_mode.setChecked(True)
            elif len(occs) == 1:
                self.lbl_occ_info.setText(
                    f'1 ocupación ({occs[0].name}) — modo normal es suficiente.')
                self.chk_occ_mode.setChecked(False)
            else:
                self.lbl_occ_info.setText(
                    'Sin marcas de ocupación (archivo de punto único o cinemático).')
                self.chk_occ_mode.setChecked(False)
        except Exception as ex:
            self.lbl_occ_info.setText(f'No se pudo analizar ocupaciones: {ex}')

    def _auto_detect_nav(self, rover_path):
        """Auto-detect navigation file when rover observation file is selected.

        RINEX naming convention:
          Observation: SSSS0910.26o  or  SSSS00XXX_R_20260910000_01D_30S_MO.rnx
          Navigation:  SSSS0910.26n  or  BRDC00IGS_R_20260910000_01D_MN.rnx
                       SSSS0910.26l  (GLONASS)
                       SSSS0910.26g  (Galileo)
                       SSSS0910.26p  (mixed/BeiDou)

        Legacy:       *.obs → *.nav
        Year-based:   *.*o  → *.*n, *.*l, *.*g, *.*p
        RINEX3 long:  *_MO.rnx → *_MN.rnx (GPS nav)
        """
        if not rover_path or not os.path.isfile(rover_path):
            return

        # Don't overwrite if nav is already set
        if self.ed_nav.text() and os.path.isfile(self.ed_nav.text()):
            return

        rover_dir = os.path.dirname(rover_path)
        rover_base = os.path.basename(rover_path)
        rover_name, rover_ext = os.path.splitext(rover_base)

        nav_candidates = []

        # Case 1: Year-based extensions (.26o → .26n, .26l, .26g, .26p)
        if len(rover_ext) >= 3 and rover_ext[-1].lower() == 'o':
            year_prefix = rover_ext[:-1]  # e.g., ".26"
            for nav_char in ['n', 'N', 'l', 'L', 'g', 'G', 'p', 'P']:
                nav_candidates.append(rover_name + year_prefix + nav_char)

        # Case 2: Legacy (.obs → .nav)
        if rover_ext.lower() == '.obs':
            nav_candidates.extend([
                rover_name + '.nav', rover_name + '.NAV',
                rover_name + '.gnav', rover_name + '.GNAV',
            ])

        # Case 3: RINEX 3 long name (_MO.rnx → _MN.rnx, _GN.rnx)
        if rover_ext.lower() == '.rnx' and '_MO' in rover_name:
            for suffix in ['_MN', '_GN', '_EN', '_CN', '_JN']:
                nav_candidates.append(rover_name.replace('_MO', suffix) + '.rnx')
                nav_candidates.append(rover_name.replace('_MO', suffix) + '.RNX')

        # Case 3b: Short Trimble extension (.O) → year lives in NAV ext
        # (07031420.O → 07031420.26n / .26g)
        if rover_ext.lower() == '.o':
            import glob as _glob
            for c_ in ['n', 'N', 'p', 'P', 'l', 'L', 'g', 'G']:
                for hit in sorted(_glob.glob(os.path.join(
                        rover_dir, rover_name + '.[0-9][0-9]' + c_))):
                    nav_candidates.append(os.path.basename(hit))

        # Case 4: Also look for broadcast files (BRDC*) in same folder
        for f in os.listdir(rover_dir):
            fl = f.lower()
            if fl.startswith('brdc') and (fl.endswith('.rnx') or fl.endswith('n')
                    or fl.endswith('l') or fl.endswith('g') or fl.endswith('p')):
                nav_candidates.append(f)

        # Try each candidate
        nav_found = None
        gnav_found = None
        for cand in nav_candidates:
            full = os.path.join(rover_dir, cand)
            if os.path.isfile(full):
                ext_low = os.path.splitext(cand)[1].lower()
                # GLONASS nav → ed_gnav
                if ext_low.endswith('g') or ext_low == '.gnav':
                    if not gnav_found:
                        gnav_found = full
                # GPS/mixed nav → ed_nav
                elif not nav_found:
                    nav_found = full

        if nav_found:
            self.ed_nav.setText(nav_found)
            self._log(f'🔍 Nav auto-detectado: {os.path.basename(nav_found)}', 'ok')

        if gnav_found and not self.ed_gnav.text():
            self.ed_gnav.setText(gnav_found)
            self._log(f'🔍 GLONASS nav auto-detectado: {os.path.basename(gnav_found)}', 'ok')

    def _sync_base_format(self):
        self.g_utm_form.setVisible(self.rb_utm.isChecked())
        self.g_dms_form.setVisible(self.rb_dms.isChecked())
        self.g_dec_form.setVisible(self.rb_dec.isChecked())
        self.g_ecef_form.setVisible(self.rb_ecef.isChecked())
        self.g_file_form.setVisible(self.rb_file.isChecked())

    # ══════════════════════════════════════════════
    # LÓGICA: AUTOCOMPLETAR DESDE RINEX BASE (estilo TBC)
    # ══════════════════════════════════════════════
    def _autocompletar_base(self):
        """Lee el header del RINEX base y autocompleta el formulario.
        Las coordenadas del header son APROXIMADAS — el usuario debe
        corregirlas con la ficha oficial IGN (igual flujo que TBC)."""
        rinex_base = self.ed_base_rinex.text().strip()
        if not rinex_base or not os.path.isfile(rinex_base):
            QMessageBox.warning(self, 'YF · Base',
                'Primero selecciona el RINEX de la base\n'
                'en la pestaña Archivos.')
            return

        # Parsear header
        marker, xyz, ant_h = None, None, None
        try:
            with open(rinex_base, 'r', errors='replace') as f:
                for i, line in enumerate(f):
                    if 'MARKER NAME' in line:
                        marker = line[:60].strip()
                    elif 'APPROX POSITION XYZ' in line:
                        parts = line[:60].split()
                        if len(parts) >= 3:
                            xyz = (float(parts[0]), float(parts[1]), float(parts[2]))
                    elif 'ANTENNA: DELTA H/E/N' in line:
                        parts = line[:60].split()
                        if parts:
                            ant_h = float(parts[0])
                    if 'END OF HEADER' in line or i > 120:
                        break
        except Exception as e:
            QMessageBox.critical(self, 'YF · Base',
                f'No se pudo leer el header del RINEX:\n{e}')
            return

        if not xyz:
            QMessageBox.warning(self, 'YF · Base',
                'El RINEX base no tiene APPROX POSITION XYZ en el header.')
            return

        # ECEF → geodésicas (pyproj viene con QGIS)
        try:
            from pyproj import Transformer
            t = Transformer.from_crs('EPSG:4978', 'EPSG:4979', always_xy=True)
            lon, lat, h = t.transform(xyz[0], xyz[1], xyz[2])
        except Exception as e:
            QMessageBox.critical(self, 'YF · Base',
                f'Error en conversión ECEF→geodésicas:\n{e}')
            return

        # decimal → DMS
        def dd_to_dms(dd):
            sign = -1 if dd < 0 else 1
            dd = abs(dd)
            d = int(dd)
            m = int((dd - d) * 60)
            s = (dd - d - m/60.0) * 3600.0
            return d, m, s, sign

        lat_d, lat_m, lat_s, lat_sign = dd_to_dms(lat)
        lon_d, lon_m, lon_s, lon_sign = dd_to_dms(lon)

        # Activar formulario DMS y llenar campos
        self.rb_dms.setChecked(True)
        self.sp_lat_d.setValue(lat_d)
        self.sp_lat_m.setValue(lat_m)
        self.sp_lat_s.setValue(round(lat_s, 5))
        self.cb_lat_h.setCurrentText('S' if lat_sign < 0 else 'N')
        self.sp_lon_d.setValue(lon_d)
        self.sp_lon_m.setValue(lon_m)
        self.sp_lon_s.setValue(round(lon_s, 5))
        self.cb_lon_h.setCurrentText('W' if lon_sign < 0 else 'E')
        self.sp_dms_h.setValue(round(h, 4))

        # Código de estación del MARKER NAME
        if marker:
            self.ed_ign_cod.setText(marker)

        # Log + advertencia honesta
        msg_ant = f' | Altura antena base (header): {ant_h:.4f} m' if ant_h is not None else ''
        self._log(
            f'📥 Base autocompletada desde RINEX header: {marker or "?"} | '
            f'Lat={lat:.8f} Lon={lon:.8f} h={h:.4f}{msg_ant}', 'info')
        QMessageBox.information(self, 'YF · Base autocompletada',
            f'Datos leídos del RINEX header de {marker or "la base"}.\n\n'
            f'⚠ IMPORTANTE: las coordenadas APPROX del header tienen\n'
            f'precisión de ~1-2 metros (posición autónoma).\n\n'
            f'Compara con la ficha oficial IGN y corrige los segundos\n'
            f'y la altura si difieren. Luego presiona\n'
            f'"Validar y aplicar coordenadas de base".'
            + (f'\n\nAltura de antena de la base (header): {ant_h:.4f} m'
               if ant_h is not None else ''))

    # ══════════════════════════════════════════════
    # LÓGICA: APLICAR BASE
    # ══════════════════════════════════════════════
    def _apply_base(self):
        validator = BaseCoordValidator()
        bc = None
        errors = []

        if self.rb_utm.isChecked():
            bc, errors = validator.from_utm_form(
                self.ed_utm_este.value(), self.ed_utm_norte.value(),
                self.cb_utm_zona.currentText(), self.ed_utm_h.value()
            )
        elif self.rb_dms.isChecked():
            bc, errors = validator.from_geo_dms_form(
                self.sp_lat_d.value(), self.sp_lat_m.value(), self.sp_lat_s.value(),
                self.cb_lat_h.currentText(),
                self.sp_lon_d.value(), self.sp_lon_m.value(), self.sp_lon_s.value(),
                self.cb_lon_h.currentText(),
                self.sp_dms_h.value()
            )
        elif self.rb_dec.isChecked():
            bc, errors = validator.from_geo_decimal(
                self.sp_dec_lat.value(), self.sp_dec_lon.value(), self.sp_dec_h.value()
            )
        elif self.rb_ecef.isChecked():
            bc, errors = validator.from_ecef(
                self.sp_ecef_x.value(), self.sp_ecef_y.value(), self.sp_ecef_z.value()
            )
        elif self.rb_file.isChecked():
            bc, errors = validator.from_file(self.ed_base_file.text())

        if errors:
            for e in errors:
                self._log(f'❌ Base: {e}', 'error')
            self.lbl_base_result.setStyleSheet(
                'background:#fff3f3;border:1px solid #f44336;'
                'border-radius:3px;padding:6px;color:#c62828;'
            )
            self.lbl_base_result.setText('\n'.join(errors))
            self._base_coords = None
            return

        self._base_coords = bc
        self.lbl_base_result.setStyleSheet(
            'background:#f1f8e9;border:1px solid #4caf50;'
            'border-radius:3px;padding:6px;font-family:monospace;color:#2e7d32;'
        )
        self.lbl_base_result.setText(
            f'✅  Base validada [{bc.fuente}]\n'
            f'Lat: {bc.lat_dd:.10f}°  |  Lon: {bc.lon_dd:.10f}°  |  h: {bc.h_elip:.4f} m\n'
            f'IGN: {self.ed_ign_cod.text()} — {self.ed_ign_nombre.text()}'
        )
        self._log(
            f'✅ Base aplicada [{bc.fuente}]: '
            f'Lat={bc.lat_dd:.8f}° Lon={bc.lon_dd:.8f}° h={bc.h_elip:.4f}m',
            'ok'
        )

    # ══════════════════════════════════════════════
    # LÓGICA: EJECUTAR
    # ══════════════════════════════════════════════
    def _run(self):
        import traceback

        # ── Desvío a LOTE: si hay archivos en la lista, tiene prioridad ──
        # (es una acción explícita: el usuario cargó varios archivos)
        batch_files = self._batch_files() if hasattr(self, 'lst_rovers') else []
        if batch_files:
            if self.rb_ppp.isChecked():
                QMessageBox.warning(self, 'YF · Lote',
                    'El procesamiento por lotes está disponible en modo PPK.\n'
                    'Para PPP procesa los archivos individualmente.')
                return
            self._run_batch(batch_files)
            return

        # ── Desvío a OCUPACIONES: un archivo con varios puntos marcados ──
        if (hasattr(self, 'chk_occ_mode') and self.chk_occ_mode.isChecked()
                and self.rb_ppk.isChecked()):
            self._run_occupations()
            return

        # ── Flujo normal de UN punto ──
        # Si el archivo tiene event flags de ocupación pero el usuario NO marcó
        # el modo ocupaciones, redirigir igualmente: procesar todo el archivo
        # promediando incluiría la caminata y daría un punto desplazado.
        # El modo ocupaciones (kinematic + corte por ventana) es lo correcto.
        if self.rb_ppk.isChecked():
            try:
                from ..gnss_engine.occupation_parser import parse_occupations
                rover_chk = self.ed_rover.text().strip()
                if rover_chk and os.path.isfile(rover_chk):
                    _occs = parse_occupations(rover_chk)
                    if _occs:
                        self._log(f'ℹ El archivo tiene {len(_occs)} ocupación(es) '
                                  f'marcada(s) — usando modo ocupaciones para evitar '
                                  f'promediar la caminata.', 'info')
                        self._run_occupations()
                        return
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)  # si falla la detección, seguir con el flujo normal

        # Construir parámetros — capturar CUALQUIER error, no solo ValueError
        try:
            params = self._collect_params()
        except ValueError as ex:
            QMessageBox.warning(self, 'Parámetros incompletos', str(ex))
            return
        except Exception as ex:
            # Error inesperado (AttributeError, etc) — mostrarlo en vez de fallar silencioso
            tb = traceback.format_exc()
            QMessageBox.critical(
                self, 'Error al recoger parámetros',
                f'{type(ex).__name__}: {ex}\n\n{tb}'
            )
            self._log(f'❌ Error en _collect_params: {ex}', 'error')
            return

        # Validaciones mínimas antes de lanzar
        if self.rb_ppk.isChecked():
            if not params.rinex_rover or not params.rinex_base:
                QMessageBox.warning(self, 'Archivos faltantes',
                    'PPK requiere archivo rover Y archivo base.')
                return
            if params.base_coords is None:
                QMessageBox.warning(self, 'Base sin validar',
                    'Debes validar las coordenadas de la base IGN primero\n'
                    '(pestaña Base IGN → Validar y aplicar).')
                return

        # Verificar binario RTKLIB — auto-instalar si falta
        if not self._ensure_rtklib_binary():
            return

        # Seleccionar procesador
        try:
            mode = 'ppk' if self.rb_ppk.isChecked() else 'ppp'
            if mode == 'ppk':
                from ..gnss_engine.ppk_processor import PPKProcessor
                self.processor = PPKProcessor(params, self.plugin_dir)
            else:
                from ..gnss_engine.ppp_processor import PPPProcessor
                self.processor = PPPProcessor(params, self.plugin_dir)

            self.processor.progress.connect(self.progress.setValue)
            self.processor.log.connect(self._log)
            self.processor.finished.connect(self._on_finished)

            self.btn_run.setEnabled(False)
            self.progress.setValue(0)
            self._last_params = params
            self._log('▶ Iniciando post-proceso...', 'info')
            self.processor.start()
        except Exception as ex:
            tb = traceback.format_exc()
            QMessageBox.critical(
                self, 'Error al iniciar procesador',
                f'{type(ex).__name__}: {ex}\n\n{tb}'
            )
            self.btn_run.setEnabled(True)

    def _collect_params(self) -> ProcessingParams:
        mode_map = {0:'static', 1:'kinematic', 2:'movbase',
                    3:'dgps-static', 4:'dgps-kinematic',
                    5:'ppp-static', 6:'ppp-kinematic'}
        filt_map = {0:'forward',1:'backward',2:'combined'}

        navsys = 0
        if self.chk_gps.isChecked(): navsys |= 0x01
        if self.chk_sbs.isChecked(): navsys |= 0x02
        if self.chk_glo.isChecked(): navsys |= 0x04
        if self.chk_gal.isChecked(): navsys |= 0x08
        if self.chk_bds.isChecked(): navsys |= 0x20

        out_dir = self.ed_out_dir.text()
        if not out_dir:
            raise ValueError('Selecciona una carpeta de salida.')

        return ProcessingParams(
            mode            = 'ppk' if self.rb_ppk.isChecked() else 'ppp',
            solution_type   = mode_map[self.cb_sol_type.currentIndex()],
            kalman_filter   = filt_map[self.cb_filter.currentIndex()],
            rinex_rover     = self.ed_rover.text(),
            nav_file        = self.ed_nav.text(),
            rinex_base      = self.ed_base_rinex.text() if self.rb_ppk.isChecked() else None,
            base_coords     = self._base_coords,
            sp3_file        = self.ed_sp3.text() or None,
            clk_file        = self.ed_clk.text() or None,
            ionex_file      = self.ed_ionex.text() or None,
            gnav_file       = self.ed_gnav.text() or None,
            freq            = self.cb_freq.currentIndex() + 1,
            elev_mask_deg   = float(self.sp_elev.value()),
            snr_mask_dbhz   = self.sp_snr.value(),
            navsys          = navsys,
            out_dir         = out_dir,
            out_prefix      = self.ed_out_prefix.text() or 'gnss_result',
            project_name    = self.ed_proy.text(),
            operator        = self.ed_prof.text(),
            receptor        = self.ed_receptor.text(),
            antena          = self.cb_antena.currentText().strip(),
            antex_file      = self._antex_path or None,
            antena_base     = self._read_base_antenna(),
            ant_height_rover = self.spin_ant_height.value(),
            serial_receptor = self.ed_serial.text(),
            notas           = self.ed_notas.toPlainText(),
        )

    def _on_finished(self, success, pos_file, stats_dict):
        self.btn_run.setEnabled(True)
        if success:
            from ..results.pos_parser import PosStats, PosParser
            self._last_stats = PosParser().parse_full(pos_file)
            self._last_pos   = pos_file
            # Trazabilidad para el informe (estilo TBC)
            self._last_proc_info = {
                'modo': 'PPK punto único',
                'cmd': getattr(self.proc, 'last_cmd', ''),
                'binary': getattr(self.proc, 'last_binary', ''),
                'conf': getattr(self.proc, 'last_conf', ''),
                'pos': pos_file,
                'archivos': [self._last_params.rinex_rover],
            } if hasattr(self, 'proc') else {}

            # Cargar capas en QGIS
            from ..results.layer_builder import LayerBuilder
            from qgis.core import QgsProject
            load_q = set()
            if self.chk_fix.isChecked():    load_q.add(1)
            if self.chk_float.isChecked():  load_q.add(2)
            if self.chk_single.isChecked(): load_q.add(4)
            if self.chk_ppp.isChecked():    load_q.add(6)

            builder = LayerBuilder(self.iface, self._last_params)

            solo_corregido = (
                self.chk_solo_corregido.isChecked()
                if hasattr(self, 'chk_solo_corregido') else True
            )

            if not solo_corregido:
                pts = builder.build_points_layer(
                    self._last_stats,
                    self._last_params.project_name or 'GNSS',
                    load_q
                )
                QgsProject.instance().addMapLayer(pts)

                if self.chk_tray.isChecked():
                    tray = builder.build_trajectory_layer(
                        self._last_stats, self._last_params.project_name or 'GNSS'
                    )
                    QgsProject.instance().addMapLayer(tray)

            # Punto promediado (coordenada corregida final)
            avg_layer = builder.build_averaged_layer(
                self._last_stats, self._last_params.project_name or 'GNSS'
            )
            if avg_layer:
                QgsProject.instance().addMapLayer(avg_layer)
                self._log(
                    f'\u2605 Coordenada corregida: '
                    f'{avg_layer.getFeature(1)["calidad"]} | '
                    f'Lat={avg_layer.getFeature(1)["lat_dd"]:.10f} '
                    f'Lon={avg_layer.getFeature(1)["lon_dd"]:.10f} '
                    f'h={avg_layer.getFeature(1)["altura_elip"]:.4f}m | '
                    f'{avg_layer.getFeature(1)["n_epocas_usadas"]} epocas usadas',
                    'ok'
                )

            # Exportaciones GIS
            fmts = []
            if self.chk_gpkg.isChecked():    fmts.append('gpkg')
            if self.chk_shp.isChecked():     fmts.append('shp')
            if self.chk_kml.isChecked():     fmts.append('kml')
            if self.chk_geojson.isChecked(): fmts.append('geojson')
            if fmts:
                # Épocas individuales: solo si se generó la capa
                # (en modo "solo punto corregido" no existe)
                if not solo_corregido:
                    results = builder.export_layer(pts, self._last_params.out_dir,
                                                   self._last_params.out_prefix, fmts)
                    for fmt, path in results.items():
                        self._log(f'💾 {fmt.upper()}: {path}', 'ok')

                # Exportar punto corregido — SIEMPRE
                if avg_layer:
                    avg_res = builder.export_layer(
                        avg_layer, self._last_params.out_dir,
                        self._last_params.out_prefix + '_corregido', fmts
                    )
                    for fmt2, path2 in avg_res.items():
                        self._log(f'CORREGIDO {fmt2.upper()}: {path2}', 'ok')

            self.btn_report.setEnabled(True)
            self.progress.setValue(100)
        else:
            self.progress.setValue(0)

    # ══════════════════════════════════════════════
    # LÓGICA: INFORMES
    # ══════════════════════════════════════════════
    def _generate_reports(self):
        import traceback
        # El informe funciona con cualquiera de los 3 flujos:
        # punto único (_last_stats), ocupaciones o lote (_last_occ_results)
        tiene_stats = bool(self._last_stats)
        tiene_occ = bool(getattr(self, '_last_occ_results', None))
        if not (tiene_stats or tiene_occ) or not self._last_params:
            QMessageBox.warning(self, 'Sin datos',
                'Ejecuta el post-proceso primero (punto, ocupaciones o lote).')
            return

        meta = {
            'profesional': self.ed_prof.text(),
            'cip':         self.ed_cip.text(),
            'empresa':     self.ed_empresa.text(),
            'proyecto':    self.ed_proy.text(),
            'lugar':       self.ed_lugar.text(),
            'receptor':    self.ed_receptor.text(),
            'antena':      self.cb_antena.currentText().strip(),
            'antex':       os.path.basename(self._antex_path)
                           if self._antex_path else 'no aplicado',
            'ant_height':  self.spin_ant_height.value(),
            'serial':      self.ed_serial.text(),
            'notas':       self.ed_notas.toPlainText(),
        }

        from ..reports.pdf_report import PDFReportGenerator

        # Para ocupaciones/lote no hay stats de un solo punto: si no existe,
        # reconstruir stats desde el .pos del último procesamiento para que
        # el informe pueda mostrar la trazabilidad del archivo .pos ejecutado.
        stats_para_informe = self._last_stats
        if stats_para_informe is None:
            pos_traza = (self._last_proc_info or {}).get('pos', '')
            if pos_traza and os.path.isfile(pos_traza):
                try:
                    from ..results.pos_parser import PosParser
                    stats_para_informe = PosParser().parse_full(pos_traza)
                except Exception:
                    stats_para_informe = None

        try:
            gen = PDFReportGenerator(self._last_params, meta, stats_para_informe)
            # Inyectar trazabilidad y resultados multi-punto (estilo TBC)
            gen.proc_info = self._last_proc_info or {}
            gen.occ_results = getattr(self, '_last_occ_results', None)

            # PDF / HTML
            rpt_path = gen.generate()
            self._log(f'📋 Informe: {rpt_path}', 'ok')
        except Exception as ex:
            tb = traceback.format_exc()
            QMessageBox.critical(self, 'Error al generar el informe',
                f'No se pudo generar el informe:\n\n{ex}\n\n'
                f'Detalle técnico:\n{tb[-500:]}')
            self._log(f'❌ Error en informe: {ex}', 'error')
            return

        # Ficha IGN JSON (solo para punto único; en lote/ocupaciones se omite)
        ficha_path = None
        if self._last_stats is not None:
            try:
                nombre_pt = self.ed_nombre_punto.text() if hasattr(self, 'ed_nombre_punto') else 'PUNTO'
                ficha_path = gen.generate_ign_ficha_json(nombre_pt)
                self._log(f'📄 Ficha IGN (JSON): {ficha_path}', 'ok')
            except Exception as ex:
                self._log(f'⚠ Ficha IGN no generada: {ex}', 'warn')

        # Abrir automáticamente
        import subprocess, sys
        for path in [rpt_path, ficha_path]:
            if not path or not os.path.isfile(path):
                continue
            try:
                __QDS.openUrl(__QURL.fromLocalFile(path))
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)

    # ══════════════════════════════════════════════
    # LÓGICA: ANTEX (calibración de antenas)
    # ══════════════════════════════════════════════
    def _read_base_antenna(self):
        """
        Lee el tipo de antena de la BASE desde el header del RINEX
        ('ANT # / TYPE'). Con ANTEX cargado, RTKLIB corrige PCV en
        ambos extremos de la línea base — igual que TBC. Solo se
        aplica si el nombre existe en el .atx (si no, RTKLIB lo ignora
        sin fallar, comportamiento seguro).
        """
        if not (self.rb_ppk.isChecked() and self._antex_path):
            return ''
        base = self.ed_base_rinex.text()
        if not base or not os.path.isfile(base):
            return ''
        from ..gnss_engine import antex_manager as axm
        ant = axm.read_rinex_antenna(base)
        if ant:
            self._log(f'📡 Antena de la base (RINEX header): {ant}', 'ok')
        return ant

    def _load_antex_master(self):
        """Descarga (o reutiliza) el igs20.atx y puebla el combo de antenas."""
        from ..gnss_engine import antex_manager as axm
        self.lbl_atx.setText('Descargando ANTEX maestro del IGS…')
        try:
            path, names = axm.resolve_antex(self._antex_customs,
                                            log=lambda m: None)
        except Exception as ex:
            path, names = None, []
            self._log(f'❌ ANTEX: {ex}', 'error')
        self._apply_antex(path, names)

    def _load_antex_custom(self):
        """Agrega un .atx del fabricante (ej. METX5) y refusiona."""
        f, _ = QFileDialog.getOpenFileName(
            self, 'ANTEX del fabricante', '', 'ANTEX (*.atx *.ATX)')
        if not f:
            return
        if f not in self._antex_customs:
            self._antex_customs.append(f)
        self._load_antex_master()   # resolve_antex refusiona todo

    def _apply_antex(self, path, names):
        """Aplica el .atx resuelto: guarda ruta, puebla combo, informa."""
        if not path:
            self.lbl_atx.setText('No se pudo obtener el ANTEX '
                                 '(¿sin internet?). El campo antena queda '
                                 'solo documental.')
            return
        self._antex_path = path
        actual = self.cb_antena.currentText()
        self.cb_antena.clear()
        self.cb_antena.addItem('')            # opción vacía = sin PCV
        self.cb_antena.addItems(names)
        # Autocompletado sobre la lista completa
        try:
            from qgis.PyQt.QtWidgets import QCompleter
            from qgis.PyQt.QtCore import Qt  # noqa: F811
            comp = QCompleter(names, self.cb_antena)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            self.cb_antena.setCompleter(comp)
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        if actual:
            self.cb_antena.setCurrentText(actual)
        n_cust = len(self._antex_customs)
        extra = f' + {n_cust} ANTEX del fabricante' if n_cust else ''
        self.lbl_atx.setText(
            f'ANTEX activo: {os.path.basename(path)}{extra} — '
            f'{len(names)} antenas de receptor. Selecciona el nombre '
            f'IGS exacto para aplicar PCO/PCV.')
        self._log(f'📡 ANTEX cargado: {len(names)} antenas', 'ok')

    # ══════════════════════════════════════════════
    # SETTINGS
    # ══════════════════════════════════════════════
    def _restore(self):
        self.ed_prof.setText(self.settings.value('prof', ''))
        self.ed_cip.setText(self.settings.value('cip', ''))
        self.ed_empresa.setText(self.settings.value('empresa', ''))
        # ANTEX: restaurar customs y repoblar el combo desde la copia
        # local (sin descargar; si no hay copia, queda en modo documental)
        customs = self.settings.value('antex_customs', []) or []
        if isinstance(customs, str):
            customs = [customs]
        self._antex_customs = [c for c in customs if os.path.isfile(c)]
        try:
            from ..gnss_engine import antex_manager as axm
            if os.path.isfile(axm.master_path()):
                path = axm.merge_antex(axm.master_path(),
                                       self._antex_customs)
                self._apply_antex(path, axm.list_receiver_antennas(path))
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        ant_prev = self.settings.value('antena', '')
        if ant_prev:
            self.cb_antena.setCurrentText(ant_prev)

    def closeEvent(self, e):
        self.settings.setValue('prof', self.ed_prof.text())
        self.settings.setValue('cip', self.ed_cip.text())
        self.settings.setValue('empresa', self.ed_empresa.text())
        self.settings.setValue('antex_customs', self._antex_customs)
        self.settings.setValue('antena', self.cb_antena.currentText())
        super().closeEvent(e)
