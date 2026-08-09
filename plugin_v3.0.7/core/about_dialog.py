# -*- coding: utf-8 -*-
"""
About Dialog — «Acerca de» con identidad TUCSA e índice de la suite.

Muestra:
- Logo TUCSA / YF GIS Amazonia y versión leída del metadata
- Datos del autor (Yuri Caller, CIP 214377)
- Acceso al manual en línea
- Índice completo de herramientas, generado desde core/tools_catalog
- Servicios TUCSA y contacto

NOTA DE DISEÑO
--------------
La lista de herramientas NO se escribe aquí. Se genera desde
core/tools_catalog, que es la fuente única. La versión anterior la
tenía escrita a mano y quedó desfasada: mostraba 8 de 17 herramientas y
etiquetas «nuevo v2.0» un año después de esa versión.

Cada nombre de herramienta es un enlace a su sección del manual, de modo
que el diálogo deja de ser una lista informativa y pasa a ser el índice
navegable de la suite.
"""

import logging
import os
import webbrowser

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QPixmap, QFont, QDesktopServices
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget
)

from .tools_catalog import DOCS_BASE, por_categoria


class AboutDialog(QDialog):
    """Diálogo «Acerca de» con identidad TUCSA."""

    def __init__(self, parent, version, plugin_dir):
        super().__init__(parent)
        self.version = version
        self.plugin_dir = plugin_dir

        self.setWindowTitle("Acerca de YF GIS Amazonia Tools")
        self.setMinimumWidth(560)
        self.setMinimumHeight(640)

        self._build_ui()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # ---- Logo / Título ----
        logo_path = os.path.join(self.plugin_dir, "icons", "main_icon.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                logo_label = QLabel()
                logo_label.setPixmap(pixmap.scaled(
                    96, 96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(logo_label)

        title = QLabel("YF GIS Amazonia Tools")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_label = QLabel("<b>Versión {}</b>".format(self.version))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #2980b9;")
        layout.addWidget(version_label)

        subtitle = QLabel(
            "<i>Suite profesional de herramientas GIS para la "
            "Amazonía peruana</i>")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #555;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ---- Manual (acción principal) ----
        manual_btn = QPushButton("📖  Abrir el manual de usuario")
        manual_btn.setMinimumHeight(38)
        manual_btn.setStyleSheet(self._button_style("#8C3A2E", "#A8483A"))
        manual_btn.setToolTip(
            "Guía completa de las {} herramientas, con casos reales "
            "documentados".format(len(list(self._todas()))))
        manual_btn.clicked.connect(lambda: self._open_url(DOCS_BASE + "/"))
        layout.addWidget(manual_btn)

        layout.addWidget(self._divider())

        # ---- Autor ----
        author_box = QLabel(
            "<table cellpadding='3' style='font-size: 10pt;'>"
            "<tr><td><b>Autor:</b></td>"
            "<td>Yuri Fabián Caller Córdova</td></tr>"
            "<tr><td><b>Profesión:</b></td>"
            "<td>Especialista en GIS, Geomática y Geodesia</td></tr>"
            "<tr><td><b>CIP:</b></td><td>N° 214377</td></tr>"
            "<tr><td><b>Empresa:</b></td>"
            "<td>Training Universal Company SAC (TUCSA)</td></tr>"
            "<tr><td><b>Ubicación:</b></td>"
            "<td>Puerto Maldonado, Madre de Dios, Perú</td></tr>"
            "</table>")
        author_box.setWordWrap(True)
        layout.addWidget(author_box)

        # ---- Contacto ----
        contact_row = QHBoxLayout()
        contact_row.setSpacing(6)
        for texto, color, hover, url in (
            ("🌐  gis-amazonia.pe", "#2980b9", "#3498db",
             "https://yuricaller.github.io/gis-amazonia/"),
            ("✉  Contactar", "#27ae60", "#2ecc71",
             "mailto:yuricaller@gmail.com"),
            ("📦  GitHub", "#34495e", "#5d6d7e",
             "https://github.com/YuriCaller/YF_GIS_AMAZONIA"),
        ):
            btn = QPushButton(texto)
            btn.setMinimumHeight(32)
            btn.setStyleSheet(self._button_style(color, hover))
            btn.clicked.connect(
                lambda _checked=False, u=url: self._open_url(u))
            contact_row.addWidget(btn)
        layout.addLayout(contact_row)

        layout.addWidget(self._divider())

        # ---- Herramientas (generadas desde el catálogo) ----
        tools_title = QLabel(
            "<b>📦 Herramientas incluidas ({}):</b>"
            "<br><small style='color:#777;'>Pulse el nombre de una "
            "herramienta para abrir su capítulo del manual.</small>"
            .format(len(list(self._todas()))))
        tools_title.setWordWrap(True)
        layout.addWidget(tools_title)

        tools_label = QLabel(self._tabla_herramientas())
        tools_label.setWordWrap(True)
        tools_label.setOpenExternalLinks(True)
        tools_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(tools_label)

        layout.addWidget(self._divider())

        # ---- Servicios ----
        layout.addWidget(QLabel("<b>🔧 Servicios profesionales TUCSA:</b>"))
        services = QLabel(
            "<ul style='margin-left: 0; padding-left: 18px; font-size: 10pt;'>"
            "<li>Levantamiento catastral y catastro forestal</li>"
            "<li>Operación de drones (DJI Matrice 4T, M300 RTK)</li>"
            "<li>Fotogrametría y ortomosaicos de alta precisión</li>"
            "<li>Post-proceso GNSS (PPK/PPP) con RTKLIB</li>"
            "<li>Monitoreo ambiental amazónico</li>"
            "<li>Estudios IGAFOM para minería formal</li>"
            "<li>Capacitación profesional en GIS y QGIS</li>"
            "<li>Desarrollo de plugins QGIS personalizados</li>"
            "</ul>")
        services.setWordWrap(True)
        layout.addWidget(services)

        layout.addWidget(self._divider())

        # ---- Pie ----
        footer = QLabel(
            "<center><small>"
            "© 2025-2026 TUCSA · Licencia GPL-3.0-or-later<br>"
            "Iconos de Font-GIS (Jean-Marc Viglino, CC BY 4.0) y del "
            "proyecto QGIS (GPL)"
            "</small></center>")
        footer.setStyleSheet("color: #777;")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        layout.addStretch()

        # ---- Botonera inferior ----
        button_row = QHBoxLayout()
        button_row.setContentsMargins(20, 8, 20, 12)

        diag_btn = QPushButton("Diagnóstico...")
        diag_btn.setMinimumHeight(32)
        diag_btn.setToolTip(
            "Estado de los componentes opcionales (python-docx, OpenCV...). "
            "Útil para reportar una incidencia.")
        diag_btn.clicked.connect(self._mostrar_diagnostico)
        button_row.addWidget(diag_btn)

        button_row.addStretch()

        close_btn = QPushButton("Cerrar")
        close_btn.setMinimumHeight(32)
        close_btn.setMinimumWidth(100)
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        outer_layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # Contenido generado
    # ------------------------------------------------------------------

    def _todas(self):
        for herramientas in por_categoria().values():
            for h in herramientas:
                yield h

    def _tabla_herramientas(self):
        """Tabla HTML agrupada por categoría, con enlace al manual."""
        filas = []
        for categoria, herramientas in por_categoria().items():
            filas.append(
                "<tr><td colspan='2' style='padding-top:10px;'>"
                "<b style='color:#8C3A2E;'>{}</b></td></tr>".format(categoria))
            for h in herramientas:
                nuevo = ""
                if h.es_nueva(self.version):
                    nuevo = (" <span style='color:#27ae60;'>"
                             "<small>nuevo</small></span>")
                filas.append(
                    "<tr>"
                    "<td valign='top' style='padding-right:10px;'>"
                    "<a href='{url}' style='color:#2980b9; "
                    "text-decoration:none;'><b>{nombre}</b></a>{nuevo}</td>"
                    "<td valign='top' style='color:#444;'>{resumen}</td>"
                    "</tr>".format(url=h.url_manual, nombre=h.nombre,
                                   nuevo=nuevo, resumen=h.resumen))
        return ("<table cellpadding='4' style='font-size: 9.5pt;'>{}</table>"
                .format("".join(filas)))

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _mostrar_diagnostico(self):
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox
        try:
            from .dependencies import diagnostico_entorno
            texto = diagnostico_entorno()
        except Exception as e:
            texto = "No se pudo obtener el diagnóstico: {}".format(e)

        caja = QMessageBox(self)
        caja.setWindowTitle("Diagnóstico del entorno")
        caja.setIcon(QMessageBox.Icon.Information)
        caja.setText(
            "Estado de los componentes opcionales de la suite.\n\n"
            "Si va a reportar un problema, copie este texto y adjúntelo.")
        caja.setDetailedText(texto)
        btn_copiar = caja.addButton("Copiar",
                                    QMessageBox.ButtonRole.ActionRole)
        caja.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
        caja.exec()
        if caja.clickedButton() is btn_copiar:
            QApplication.clipboard().setText(texto)

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #ddd;")
        return line

    def _button_style(self, bg_color, hover_color):
        return """
            QPushButton {{
                background-color: {bg};
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {hv}; }}
        """.format(bg=bg_color, hv=hover_color)

    def _open_url(self, url):
        """Abre una URL en el navegador del sistema."""
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception:
            try:
                webbrowser.open(url)
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
