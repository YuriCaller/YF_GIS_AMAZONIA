# -*- coding: utf-8 -*-
"""
About Dialog - Enhanced "Acerca de" with TUCSA branding and services info.

Shows:
- Logo TUCSA / YF GIS Amazonia
- Author info (Yuri Caller, CIP 214377)
- TUCSA services list
- Contact links
- List of included tools with versions
"""

import os
import webbrowser

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap, QFont, QDesktopServices
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QSizePolicy
)


class AboutDialog(QDialog):
    """Enhanced About dialog with TUCSA branding."""

    def __init__(self, parent, version, plugin_dir):
        super().__init__(parent)
        self.version = version
        self.plugin_dir = plugin_dir

        self.setWindowTitle("Acerca de YF GIS Amazonia Tools")
        self.setMinimumWidth(520)
        self.setMinimumHeight(620)

        self._build_ui()

    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # ScrollArea wrapper
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # ---- Logo / Title ----
        logo_path = os.path.join(self.plugin_dir, "icons", "main_icon.png")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                # Scale to reasonable size, smooth
                scaled = pixmap.scaled(
                    96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                logo_label.setPixmap(scaled)
                logo_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(logo_label)

        title = QLabel("YF GIS Amazonia Tools")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        version_label = QLabel(f"<b>Versión {self.version}</b>")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #2980b9;")
        layout.addWidget(version_label)

        subtitle = QLabel(
            "<i>Suite profesional de herramientas GIS para la Amazonía peruana</i>"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #555;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Divider
        layout.addWidget(self._divider())

        # ---- Author info ----
        author_box = QLabel(
            "<table cellpadding='3' style='font-size: 10pt;'>"
            "<tr><td><b>Autor:</b></td>"
            "<td>Yuri Fabian Caller Córdova</td></tr>"
            "<tr><td><b>Profesión:</b></td>"
            "<td>Especialista en GIS, Geomática y Geodesia</td></tr>"
            "<tr><td><b>CIP:</b></td>"
            "<td>N° 214377</td></tr>"
            "<tr><td><b>Empresa:</b></td>"
            "<td>Training Universal Company SAC (TUCSA)</td></tr>"
            "<tr><td><b>Ubicación:</b></td>"
            "<td>Puerto Maldonado, Madre de Dios, Perú</td></tr>"
            "</table>"
        )
        author_box.setWordWrap(True)
        layout.addWidget(author_box)

        # ---- Contact buttons ----
        contact_row = QHBoxLayout()
        contact_row.setSpacing(6)

        web_btn = QPushButton("🌐  gis-amazonia.pe")
        web_btn.setMinimumHeight(32)
        web_btn.setStyleSheet(self._button_style("#2980b9", "#3498db"))
        web_btn.clicked.connect(lambda: self._open_url("https://gis-amazonia.pe"))
        contact_row.addWidget(web_btn)

        email_btn = QPushButton("✉  Contactar")
        email_btn.setMinimumHeight(32)
        email_btn.setStyleSheet(self._button_style("#27ae60", "#2ecc71"))
        email_btn.clicked.connect(
            lambda: self._open_url("mailto:yuricaller@gmail.com")
        )
        contact_row.addWidget(email_btn)

        github_btn = QPushButton("📦  GitHub")
        github_btn.setMinimumHeight(32)
        github_btn.setStyleSheet(self._button_style("#34495e", "#5d6d7e"))
        github_btn.clicked.connect(
            lambda: self._open_url("https://github.com/YuriCaller/YF_GIS_AMAZONIA")
        )
        contact_row.addWidget(github_btn)

        layout.addLayout(contact_row)

        # Divider
        layout.addWidget(self._divider())

        # ---- Services ----
        services_title = QLabel("<b>🔧 Servicios profesionales TUCSA:</b>")
        layout.addWidget(services_title)

        services_html = (
            "<ul style='margin-left: 0; padding-left: 18px; font-size: 10pt;'>"
            "<li>Mapeo cadastral y catastro forestal</li>"
            "<li>Operación de drones (DJI Matrice 4T, M300 RTK)</li>"
            "<li>Fotogrametría y ortomosaicos de alta precisión</li>"
            "<li>Post-proceso GNSS (PPK/PPP) con RTKLIB</li>"
            "<li>Monitoreo ambiental amazónico</li>"
            "<li>Estudios IGAFOM para minería formal</li>"
            "<li>Capacitación profesional en GIS y QGIS</li>"
            "<li>Desarrollo de plugins QGIS personalizados</li>"
            "</ul>"
        )
        services_label = QLabel(services_html)
        services_label.setWordWrap(True)
        layout.addWidget(services_label)

        # Divider
        layout.addWidget(self._divider())

        # ---- Tools included ----
        tools_title = QLabel("<b>📦 Herramientas incluidas en esta suite:</b>")
        layout.addWidget(tools_title)

        tools_html = (
            "<table cellpadding='4' style='font-size: 10pt;'>"
            "<tr><td>📐</td><td><b>Memoria Descriptiva</b></td>"
            "<td>Generación automática de memorias técnicas DOCX</td></tr>"
            "<tr><td>✂</td><td><b>Segmentador de Parcelas</b></td>"
            "<td>Cálculo de azimuts, ángulos y subdivisión</td></tr>"
            "<tr><td>🧮</td><td><b>YF Tools Plus</b></td>"
            "<td>Coords, vértices, área, perímetro, multipart</td></tr>"
            "<tr><td>🛰️</td><td><b>Post-Proceso PPK/PPP</b></td>"
            "<td>RTKLIB, reportes PDF, .cor para IGN Perú</td></tr>"
            "<tr><td>🌳</td><td><b>SAF Generator</b></td>"
            "<td>Sistemas Agroforestales con 6 métodos</td></tr>"
            "<tr><td>🔍</td><td><b>Búsqueda de Atributos</b></td>"
            "<td>Multi-capa con reportes y visualización</td></tr>"
            "<tr><td>↔</td><td><b>Swipe Tool</b> <i>(nuevo v2.0)</i></td>"
            "<td>Comparación visual estilo ArcGIS Pro</td></tr>"
            "<tr><td>📍</td><td><b>Go-To Tool</b> <i>(nuevo v2.0)</i></td>"
            "<td>Navegación a coordenadas (DD/DMS/UTM/MGRS)</td></tr>"
            "</table>"
        )
        tools_label = QLabel(tools_html)
        tools_label.setWordWrap(True)
        layout.addWidget(tools_label)

        # Divider
        layout.addWidget(self._divider())

        # ---- Footer ----
        footer = QLabel(
            f"<center>"
            f"<small>© 2025-2026 TUCSA — Todos los derechos reservados<br>"
            f"Licencia GPL-3.0-or-later · Software libre y de código abierto</small>"
            f"</center>"
        )
        footer.setStyleSheet("color: #777;")
        layout.addWidget(footer)

        # Add stretch to push everything up
        layout.addStretch()

        # ---- Close button (outside scroll) ----
        button_row = QHBoxLayout()
        button_row.setContentsMargins(20, 8, 20, 12)
        button_row.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.setMinimumHeight(32)
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        outer_layout.addLayout(button_row)

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #ddd;")
        return line

    def _button_style(self, bg_color, hover_color):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """

    def _open_url(self, url):
        """Open a URL in the default browser."""
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception:
            try:
                webbrowser.open(url)
            except Exception:
                pass
