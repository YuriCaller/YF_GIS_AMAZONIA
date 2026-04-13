# -*- coding: utf-8 -*-
"""
main_dialog.py
Interfaz principal del plugin GNSS Post-Process v2.
5 pestañas: Modo/Archivos | Base IGN | Configuración | Informe | Salida
"""
import os
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QTabWidget, QTextEdit, QFileDialog,
    QProgressBar, QFrame, QScrollArea, QFormLayout,
    QRadioButton, QButtonGroup, QMessageBox, QSizePolicy
)
from qgis.PyQt.QtCore import Qt, QSettings
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
        self.ed_rover  = self._file_field(g_rover_lay, 'RINEX Obs (.obs/.rnx):',
                                           'RINEX Obs (*.obs *.rnx *.OBS *.RNX)')
        self.ed_nav    = self._file_field(g_rover_lay, 'Nav GPS (.nav/.rnx):',
                                           'RINEX Nav (*.nav *.rnx *.NAV *.RNX)')
        self.ed_gnav   = self._file_field(g_rover_lay, 'Nav GLONASS (.gnav):',
                                           'GLONASS Nav (*.gnav *.GNAV)', optional=True)
        lay.addWidget(g_rover)

        # Base RINEX (PPK)
        self.g_base_rinex = QGroupBox('Base — RINEX (PPK)')
        gb_lay = QFormLayout(self.g_base_rinex)
        self.ed_base_rinex = self._file_field(gb_lay, 'RINEX Base (.obs/.rnx):',
                                               'RINEX Obs (*.obs *.rnx *.OBS *.RNX)')
        lay.addWidget(self.g_base_rinex)

        # Archivos precisos (PPP)
        self.g_precise = QGroupBox('Archivos precisos (PPP — obligatorios)')
        gp_lay = QFormLayout(self.g_precise)
        self.ed_sp3    = self._file_field(gp_lay, 'Órbitas precisas (.sp3):',
                                           'SP3 (*.sp3 *.SP3)')
        self.ed_clk    = self._file_field(gp_lay, 'Relojes precisos (.clk):',
                                           'CLK (*.clk *.CLK)')
        self.ed_ionex  = self._file_field(gp_lay, 'IONEX (.i/.ionex):',
                                           'IONEX (*.i *.ionex)', optional=True)
        lay.addWidget(self.g_precise)

        self._on_mode_toggle(True)  # Sync visibilidad inicial
        lay.addStretch()
        return w

    # ─────────── TAB BASE IGN ───────────
    def _tab_base(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(6)

        info = QLabel(
            '⚠️  OBLIGATORIO en PPK. El plugin NO usa coordenadas del RINEX header.\n'
            'Ingresa las coordenadas oficiales de la base (ficha IGN o equivalente).'
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
                                    'PPP-Estático (ppp-static)',
                                    'PPP-Cinemático (ppp-kinematic)'])
        self.cb_filter = QComboBox()
        self.cb_filter.addItems(['Forward', 'Backward', 'Combined (forward+backward)'])
        gs.addRow('Modo solución:', self.cb_sol_type)
        gs.addRow('Filtro Kalman:', self.cb_filter)
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
        self.ed_antena   = QLineEdit(); self.ed_antena.setPlaceholderText('Modelo antena')
        self.ed_serial   = QLineEdit(); self.ed_serial.setPlaceholderText('N° de serie')
        geq.addRow('Receptor:', self.ed_receptor)
        geq.addRow('Antena:',   self.ed_antena)
        geq.addRow('N° serie:', self.ed_serial)
        lay.addWidget(g_eq)

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

        g_capa = QGroupBox('Capas a cargar en QGIS')
        gc = QVBoxLayout(g_capa)
        self.chk_fix    = QCheckBox('Fix (Q=1)  — verde');     self.chk_fix.setChecked(True)
        self.chk_float  = QCheckBox('Float (Q=2) — amarillo'); self.chk_float.setChecked(True)
        self.chk_single = QCheckBox('Single (Q=4) — rojo')
        self.chk_ppp    = QCheckBox('PPP (Q=6)   — morado');   self.chk_ppp.setChecked(True)
        self.chk_tray   = QCheckBox('Trayectoria como línea'); self.chk_tray.setChecked(True)
        for c in [self.chk_fix, self.chk_float, self.chk_single, self.chk_ppp, self.chk_tray]:
            gc.addWidget(c)
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

    def _on_mode_toggle(self, ppk):
        self.g_base_rinex.setVisible(self.rb_ppk.isChecked())
        self.g_precise.setVisible(self.rb_ppp.isChecked())

    def _sync_base_format(self):
        self.g_utm_form.setVisible(self.rb_utm.isChecked())
        self.g_dms_form.setVisible(self.rb_dms.isChecked())
        self.g_dec_form.setVisible(self.rb_dec.isChecked())
        self.g_ecef_form.setVisible(self.rb_ecef.isChecked())
        self.g_file_form.setVisible(self.rb_file.isChecked())

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
        # Construir parámetros
        try:
            params = self._collect_params()
        except ValueError as ex:
            QMessageBox.warning(self, 'Parámetros incompletos', str(ex))
            return

        # Seleccionar procesador
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
        self.processor.start()

    def _collect_params(self) -> ProcessingParams:
        mode_map = {0:'static',1:'kinematic',2:'movbase',3:'ppp-static',4:'ppp-kinematic'}
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
            antena          = self.ed_antena.text(),
            serial_receptor = self.ed_serial.text(),
            notas           = self.ed_notas.toPlainText(),
        )

    def _on_finished(self, success, pos_file, stats_dict):
        self.btn_run.setEnabled(True)
        if success:
            from ..results.pos_parser import PosStats, PosParser
            self._last_stats = PosParser().parse_full(pos_file)
            self._last_pos   = pos_file

            # Cargar capas en QGIS
            from ..results.layer_builder import LayerBuilder
            from qgis.core import QgsProject
            load_q = set()
            if self.chk_fix.isChecked():    load_q.add(1)
            if self.chk_float.isChecked():  load_q.add(2)
            if self.chk_single.isChecked(): load_q.add(4)
            if self.chk_ppp.isChecked():    load_q.add(6)

            builder = LayerBuilder(self.iface, self._last_params)
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

            # Exportaciones GIS
            fmts = []
            if self.chk_gpkg.isChecked():    fmts.append('gpkg')
            if self.chk_shp.isChecked():     fmts.append('shp')
            if self.chk_kml.isChecked():     fmts.append('kml')
            if self.chk_geojson.isChecked(): fmts.append('geojson')
            if fmts:
                results = builder.export_layer(pts, self._last_params.out_dir,
                                               self._last_params.out_prefix, fmts)
                for fmt, path in results.items():
                    self._log(f'💾 {fmt.upper()}: {path}', 'ok')

            self.btn_report.setEnabled(True)
            self.progress.setValue(100)
        else:
            self.progress.setValue(0)

    # ══════════════════════════════════════════════
    # LÓGICA: INFORMES
    # ══════════════════════════════════════════════
    def _generate_reports(self):
        if not self._last_stats or not self._last_params:
            QMessageBox.warning(self, 'Sin datos', 'Ejecuta el post-proceso primero.')
            return

        meta = {
            'profesional': self.ed_prof.text(),
            'cip':         self.ed_cip.text(),
            'empresa':     self.ed_empresa.text(),
            'proyecto':    self.ed_proy.text(),
            'lugar':       self.ed_lugar.text(),
            'receptor':    self.ed_receptor.text(),
            'antena':      self.ed_antena.text(),
            'serial':      self.ed_serial.text(),
            'notas':       self.ed_notas.toPlainText(),
        }

        from ..reports.pdf_report import PDFReportGenerator
        gen = PDFReportGenerator(self._last_params, meta, self._last_stats)

        # PDF / HTML
        rpt_path = gen.generate()
        self._log(f'📋 Informe: {rpt_path}', 'ok')

        # Ficha IGN JSON
        ficha_path = gen.generate_ign_ficha_json(self.ed_nombre_punto.text())
        self._log(f'📄 Ficha IGN (JSON): {ficha_path}', 'ok')

        # Abrir automáticamente
        import subprocess, sys
        for path in [rpt_path, ficha_path]:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', path])
            else:
                subprocess.run(['xdg-open', path])

    # ══════════════════════════════════════════════
    # SETTINGS
    # ══════════════════════════════════════════════
    def _restore(self):
        self.ed_prof.setText(self.settings.value('prof', ''))
        self.ed_cip.setText(self.settings.value('cip', ''))
        self.ed_empresa.setText(self.settings.value('empresa', ''))

    def closeEvent(self, e):
        self.settings.setValue('prof', self.ed_prof.text())
        self.settings.setValue('cip', self.ed_cip.text())
        self.settings.setValue('empresa', self.ed_empresa.text())
        super().closeEvent(e)
