# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SettingsPanel
                                 A QGIS plugin
 Búsqueda avanzada de atributos con funcionalidades similares a ArcMap
                             -------------------
        begin                : 2025-04-21
        copyright            : (C) 2025 by Yuri Caller
        email                : yuricaller@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QCheckBox, QComboBox, QSpinBox, QColorDialog, QFileDialog,
    QMessageBox, QTabWidget, QFormLayout, QRadioButton, QButtonGroup,
    QSpacerItem, QSizePolicy
)
from qgis.PyQt.QtCore import Qt, QSettings, QSize
from qgis.PyQt.QtGui import QIcon, QFont, QColor

from qgis.core import QgsProject, QgsVectorLayer

class SettingsPanel(QWidget):
    """Panel for plugin settings."""
    
    def __init__(self, iface):
        """Constructor."""
        super(SettingsPanel, self).__init__()
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Set up the user interface
        self.setup_ui()
        
        # Load settings
        self.load_settings()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        
        # Settings tabs
        self.tabs = QTabWidget()
        
        # === GENERAL SETTINGS TAB ===
        self.general_tab = QWidget()
        self.general_layout = QVBoxLayout(self.general_tab)
        
        # Search settings
        self.search_group = QGroupBox("Configuración de Búsqueda")
        self.search_layout = QFormLayout(self.search_group)
        
        # Default search limit
        self.default_limit_label = QLabel("Límite de resultados predeterminado:")
        self.default_limit_combo = QComboBox()
        self.default_limit_combo.addItems(["100", "500", "1000", "5000", "Sin límite"])
        self.search_layout.addRow(self.default_limit_label, self.default_limit_combo)
        
        # Case sensitivity
        self.case_sensitive_check = QCheckBox("Búsqueda sensible a mayúsculas/minúsculas por defecto")
        self.search_layout.addRow(self.case_sensitive_check)
        
        # Search in all fields
        self.search_all_fields_check = QCheckBox("Buscar en todos los campos por defecto")
        self.search_all_fields_check.setChecked(True)
        self.search_layout.addRow(self.search_all_fields_check)
        
        self.general_layout.addWidget(self.search_group)
        
        # Results settings
        self.results_group = QGroupBox("Configuración de Resultados")
        self.results_layout = QFormLayout(self.results_group)
        
        # Auto zoom to results
        self.auto_zoom_check = QCheckBox("Zoom automático a resultados")
        self.auto_zoom_check.setChecked(True)
        self.results_layout.addRow(self.auto_zoom_check)
        
        # Flash results
        self.flash_results_check = QCheckBox("Resaltar resultados automáticamente")
        self.flash_results_check.setChecked(True)
        self.results_layout.addRow(self.flash_results_check)
        
        # Default chart type
        self.default_chart_label = QLabel("Tipo de gráfico predeterminado:")
        self.default_chart_combo = QComboBox()
        self.default_chart_combo.addItems(["Barras", "Pastel", "Líneas"])
        self.results_layout.addRow(self.default_chart_label, self.default_chart_combo)
        
        self.general_layout.addWidget(self.results_group)
        
        # Export settings
        self.export_group = QGroupBox("Configuración de Exportación")
        self.export_layout = QFormLayout(self.export_group)
        
        # Default export format
        self.default_export_label = QLabel("Formato de exportación predeterminado:")
        self.default_export_combo = QComboBox()
        self.default_export_combo.addItems(["CSV", "Excel", "GeoJSON"])
        self.export_layout.addRow(self.default_export_label, self.default_export_combo)
        
        # Default export directory
        self.default_export_dir_label = QLabel("Directorio de exportación predeterminado:")
        
        self.export_dir_layout = QHBoxLayout()
        self.default_export_dir_input = QLineEdit()
        self.export_dir_layout.addWidget(self.default_export_dir_input)
        
        self.browse_export_dir_button = QPushButton("Examinar...")
        self.browse_export_dir_button.clicked.connect(self.browse_export_dir)
        self.export_dir_layout.addWidget(self.browse_export_dir_button)
        
        self.export_layout.addRow(self.default_export_dir_label, self.export_dir_layout)
        
        self.general_layout.addWidget(self.export_group)
        
        # Add spacer
        self.general_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Add general tab
        self.tabs.addTab(self.general_tab, "General")
        
        # === APPEARANCE TAB ===
        self.appearance_tab = QWidget()
        self.appearance_layout = QVBoxLayout(self.appearance_tab)
        
        # Results table settings
        self.table_group = QGroupBox("Tabla de Resultados")
        self.table_layout = QFormLayout(self.table_group)
        
        # Alternate row colors
        self.alternate_colors_check = QCheckBox("Alternar colores de filas")
        self.alternate_colors_check.setChecked(True)
        self.table_layout.addRow(self.alternate_colors_check)
        
        # Row height
        self.row_height_label = QLabel("Altura de fila:")
        self.row_height_spin = QSpinBox()
        self.row_height_spin.setRange(20, 50)
        self.row_height_spin.setValue(25)
        self.row_height_spin.setSuffix(" px")
        self.table_layout.addRow(self.row_height_label, self.row_height_spin)
        
        # Font size
        self.font_size_label = QLabel("Tamaño de fuente:")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 16)
        self.font_size_spin.setValue(10)
        self.font_size_spin.setSuffix(" pt")
        self.table_layout.addRow(self.font_size_label, self.font_size_spin)
        
        self.appearance_layout.addWidget(self.table_group)
        
        # Highlight settings
        self.highlight_group = QGroupBox("Resaltado de Entidades")
        self.highlight_layout = QFormLayout(self.highlight_group)
        
        # Highlight color
        self.highlight_color_label = QLabel("Color de resaltado:")
        
        self.highlight_color_layout = QHBoxLayout()
        self.highlight_color_preview = QLabel()
        self.highlight_color_preview.setFixedSize(20, 20)
        self.highlight_color_preview.setStyleSheet("background-color: #FF0000; border: 1px solid #000000;")
        self.highlight_color_layout.addWidget(self.highlight_color_preview)
        
        self.highlight_color_button = QPushButton("Cambiar...")
        self.highlight_color_button.clicked.connect(self.change_highlight_color)
        self.highlight_color_layout.addWidget(self.highlight_color_button)
        
        self.highlight_layout.addRow(self.highlight_color_label, self.highlight_color_layout)
        
        # Highlight transparency
        self.highlight_transparency_label = QLabel("Transparencia:")
        self.highlight_transparency_spin = QSpinBox()
        self.highlight_transparency_spin.setRange(0, 100)
        self.highlight_transparency_spin.setValue(50)
        self.highlight_transparency_spin.setSuffix(" %")
        self.highlight_layout.addRow(self.highlight_transparency_label, self.highlight_transparency_spin)
        
        # Highlight duration
        self.highlight_duration_label = QLabel("Duración del resaltado:")
        self.highlight_duration_spin = QSpinBox()
        self.highlight_duration_spin.setRange(1, 10)
        self.highlight_duration_spin.setValue(3)
        self.highlight_duration_spin.setSuffix(" segundos")
        self.highlight_layout.addRow(self.highlight_duration_label, self.highlight_duration_spin)
        
        self.appearance_layout.addWidget(self.highlight_group)
        
        # Add spacer
        self.appearance_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Add appearance tab
        self.tabs.addTab(self.appearance_tab, "Apariencia")
        
        # === REPORT SETTINGS TAB ===
        self.report_tab = QWidget()
        self.report_layout = QVBoxLayout(self.report_tab)
        
        # Report settings
        self.report_group = QGroupBox("Configuración de Reportes")
        self.report_layout_form = QFormLayout(self.report_group)
        
        # Default report format
        self.default_report_format_label = QLabel("Formato predeterminado:")
        self.default_report_format_combo = QComboBox()
        self.default_report_format_combo.addItems(["Word (.docx)", "PDF"])
        self.report_layout_form.addRow(self.default_report_format_label, self.default_report_format_combo)
        
        # Default report directory
        self.default_report_dir_label = QLabel("Directorio predeterminado:")
        
        self.report_dir_layout = QHBoxLayout()
        self.default_report_dir_input = QLineEdit()
        self.report_dir_layout.addWidget(self.default_report_dir_input)
        
        self.browse_report_dir_button = QPushButton("Examinar...")
        self.browse_report_dir_button.clicked.connect(self.browse_report_dir)
        self.report_dir_layout.addWidget(self.browse_report_dir_button)
        
        self.report_layout_form.addRow(self.default_report_dir_label, self.report_dir_layout)
        
        # Company logo
        self.company_logo_label = QLabel("Logo de empresa:")
        
        self.company_logo_layout = QHBoxLayout()
        self.company_logo_input = QLineEdit()
        self.company_logo_layout.addWidget(self.company_logo_input)
        
        self.browse_logo_button = QPushButton("Examinar...")
        self.browse_logo_button.clicked.connect(self.browse_logo)
        self.company_logo_layout.addWidget(self.browse_logo_button)
        
        self.report_layout_form.addRow(self.company_logo_label, self.company_logo_layout)
        
        # Default report title
        self.default_report_title_label = QLabel("Título predeterminado:")
        self.default_report_title_input = QLineEdit()
        self.default_report_title_input.setPlaceholderText("Reporte de Búsqueda de Atributos")
        self.report_layout_form.addRow(self.default_report_title_label, self.default_report_title_input)
        
        # Author name
        self.author_name_label = QLabel("Nombre del autor:")
        self.author_name_input = QLineEdit()
        self.report_layout_form.addRow(self.author_name_label, self.author_name_input)
        
        self.report_layout.addWidget(self.report_group)
        
        # Report content settings
        self.report_content_group = QGroupBox("Contenido Predeterminado")
        self.report_content_layout = QVBoxLayout(self.report_content_group)
        
        # Include map
        self.include_map_check = QCheckBox("Incluir mapa de ubicación")
        self.include_map_check.setChecked(True)
        self.report_content_layout.addWidget(self.include_map_check)
        
        # Include attributes
        self.include_attributes_check = QCheckBox("Incluir tabla de atributos")
        self.include_attributes_check.setChecked(True)
        self.report_content_layout.addWidget(self.include_attributes_check)
        
        # Include charts
        self.include_charts_check = QCheckBox("Incluir gráficos estadísticos")
        self.include_charts_check.setChecked(True)
        self.report_content_layout.addWidget(self.include_charts_check)
        
        # Include metadata
        self.include_metadata_check = QCheckBox("Incluir metadatos de la capa")
        self.include_metadata_check.setChecked(True)
        self.report_content_layout.addWidget(self.include_metadata_check)
        
        self.report_layout.addWidget(self.report_content_group)
        
        # Add spacer
        self.report_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Add report tab
        self.tabs.addTab(self.report_tab, "Reportes")
        
        # === ADVANCED TAB ===
        self.advanced_tab = QWidget()
        self.advanced_layout = QVBoxLayout(self.advanced_tab)
        
        # Performance settings
        self.performance_group = QGroupBox("Rendimiento")
        self.performance_layout = QFormLayout(self.performance_group)
        
        # Max features per layer
        self.max_features_label = QLabel("Máximo de entidades por capa:")
        self.max_features_spin = QSpinBox()
        self.max_features_spin.setRange(100, 100000)
        self.max_features_spin.setValue(10000)
        self.max_features_spin.setSingleStep(1000)
        self.performance_layout.addRow(self.max_features_label, self.max_features_spin)
        
        # Use spatial index
        self.spatial_index_check = QCheckBox("Usar índice espacial cuando esté disponible")
        self.spatial_index_check.setChecked(True)
        self.performance_layout.addRow(self.spatial_index_check)
        
        # Asynchronous search
        self.async_search_check = QCheckBox("Búsqueda asíncrona (no bloquea la interfaz)")
        self.async_search_check.setChecked(True)
        self.performance_layout.addRow(self.async_search_check)
        
        self.advanced_layout.addWidget(self.performance_group)
        
        # Debug settings
        self.debug_group = QGroupBox("Depuración")
        self.debug_layout = QVBoxLayout(self.debug_group)
        
        # Enable logging
        self.enable_logging_check = QCheckBox("Habilitar registro de depuración")
        self.debug_layout.addWidget(self.enable_logging_check)
        
        # Log level
        self.log_level_layout = QHBoxLayout()
        self.log_level_label = QLabel("Nivel de registro:")
        self.log_level_layout.addWidget(self.log_level_label)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_layout.addWidget(self.log_level_combo)
        
        self.debug_layout.addLayout(self.log_level_layout)
        
        self.advanced_layout.addWidget(self.debug_group)
        
        # Add spacer
        self.advanced_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Add advanced tab
        self.tabs.addTab(self.advanced_tab, "Avanzado")
        
        # Add tabs to main layout
        self.main_layout.addWidget(self.tabs)
        
        # Buttons
        self.buttons_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Guardar Configuración")
        self.save_button.clicked.connect(self.save_settings)
        self.buttons_layout.addWidget(self.save_button)
        
        self.reset_button = QPushButton("Restablecer Valores Predeterminados")
        self.reset_button.clicked.connect(self.reset_settings)
        self.buttons_layout.addWidget(self.reset_button)
        
        self.main_layout.addLayout(self.buttons_layout)
    
    def load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        settings.beginGroup("QGISAttributeSearch")
        
        # General settings
        self.default_limit_combo.setCurrentText(settings.value("defaultLimit", "1000"))
        self.case_sensitive_check.setChecked(settings.value("caseSensitive", False, type=bool))
        self.search_all_fields_check.setChecked(settings.value("searchAllFields", True, type=bool))
        self.auto_zoom_check.setChecked(settings.value("autoZoom", True, type=bool))
        self.flash_results_check.setChecked(settings.value("flashResults", True, type=bool))
        self.default_chart_combo.setCurrentText(settings.value("defaultChartType", "Barras"))
        self.default_export_combo.setCurrentText(settings.value("defaultExportFormat", "CSV"))
        self.default_export_dir_input.setText(settings.value("defaultExportDir", ""))
        
        # Appearance settings
        self.alternate_colors_check.setChecked(settings.value("alternateRowColors", True, type=bool))
        self.row_height_spin.setValue(settings.value("rowHeight", 25, type=int))
        self.font_size_spin.setValue(settings.value("fontSize", 10, type=int))
        
        highlight_color = settings.value("highlightColor", "#FF0000")
        self.highlight_color_preview.setStyleSheet(f"background-color: {highlight_color}; border: 1px solid #000000;")
        
        self.highlight_transparency_spin.setValue(settings.value("highlightTransparency", 50, type=int))
        self.highlight_duration_spin.setValue(settings.value("highlightDuration", 3, type=int))
        
        # Report settings
        self.default_report_format_combo.setCurrentText(settings.value("defaultReportFormat", "Word (.docx)"))
        self.default_report_dir_input.setText(settings.value("defaultReportDir", ""))
        self.company_logo_input.setText(settings.value("companyLogo", ""))
        self.default_report_title_input.setText(settings.value("defaultReportTitle", "Reporte de Búsqueda de Atributos"))
        self.author_name_input.setText(settings.value("authorName", ""))
        
        self.include_map_check.setChecked(settings.value("includeMap", True, type=bool))
        self.include_attributes_check.setChecked(settings.value("includeAttributes", True, type=bool))
        self.include_charts_check.setChecked(settings.value("includeCharts", True, type=bool))
        self.include_metadata_check.setChecked(settings.value("includeMetadata", True, type=bool))
        
        # Advanced settings
        self.max_features_spin.setValue(settings.value("maxFeatures", 10000, type=int))
        self.spatial_index_check.setChecked(settings.value("useSpatialIndex", True, type=bool))
        self.async_search_check.setChecked(settings.value("asyncSearch", True, type=bool))
        self.enable_logging_check.setChecked(settings.value("enableLogging", False, type=bool))
        self.log_level_combo.setCurrentText(settings.value("logLevel", "INFO"))
        
        settings.endGroup()
    
    def save_settings(self):
        """Save settings to QSettings."""
        settings = QSettings()
        settings.beginGroup("QGISAttributeSearch")
        
        # General settings
        settings.setValue("defaultLimit", self.default_limit_combo.currentText())
        settings.setValue("caseSensitive", self.case_sensitive_check.isChecked())
        settings.setValue("searchAllFields", self.search_all_fields_check.isChecked())
        settings.setValue("autoZoom", self.auto_zoom_check.isChecked())
        settings.setValue("flashResults", self.flash_results_check.isChecked())
        settings.setValue("defaultChartType", self.default_chart_combo.currentText())
        settings.setValue("defaultExportFormat", self.default_export_combo.currentText())
        settings.setValue("defaultExportDir", self.default_export_dir_input.text())
        
        # Appearance settings
        settings.setValue("alternateRowColors", self.alternate_colors_check.isChecked())
        settings.setValue("rowHeight", self.row_height_spin.value())
        settings.setValue("fontSize", self.font_size_spin.value())
        
        # Get highlight color from stylesheet
        style = self.highlight_color_preview.styleSheet()
        color = style.split("background-color:")[1].split(";")[0].strip()
        settings.setValue("highlightColor", color)
        
        settings.setValue("highlightTransparency", self.highlight_transparency_spin.value())
        settings.setValue("highlightDuration", self.highlight_duration_spin.value())
        
        # Report settings
        settings.setValue("defaultReportFormat", self.default_report_format_combo.currentText())
        settings.setValue("defaultReportDir", self.default_report_dir_input.text())
        settings.setValue("companyLogo", self.company_logo_input.text())
        settings.setValue("defaultReportTitle", self.default_report_title_input.text())
        settings.setValue("authorName", self.author_name_input.text())
        
        settings.setValue("includeMap", self.include_map_check.isChecked())
        settings.setValue("includeAttributes", self.include_attributes_check.isChecked())
        settings.setValue("includeCharts", self.include_charts_check.isChecked())
        settings.setValue("includeMetadata", self.include_metadata_check.isChecked())
        
        # Advanced settings
        settings.setValue("maxFeatures", self.max_features_spin.value())
        settings.setValue("useSpatialIndex", self.spatial_index_check.isChecked())
        settings.setValue("asyncSearch", self.async_search_check.isChecked())
        settings.setValue("enableLogging", self.enable_logging_check.isChecked())
        settings.setValue("logLevel", self.log_level_combo.currentText())
        
        settings.endGroup()
        
        QMessageBox.information(
            self,
            "Éxito",
            "Configuración guardada correctamente."
        )
    
    def reset_settings(self):
        """Reset settings to default values."""
        # Ask for confirmation
        result = QMessageBox.question(
            self,
            "Confirmar",
            "¿Está seguro de que desea restablecer todos los valores a la configuración predeterminada?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            # Remove all settings
            settings = QSettings()
            settings.beginGroup("QGISAttributeSearch")
            settings.remove("")
            settings.endGroup()
            
            # Reload settings
            self.load_settings()
            
            QMessageBox.information(
                self,
                "Éxito",
                "Configuración restablecida a valores predeterminados."
            )
    
    def browse_export_dir(self):
        """Browse for export directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Directorio de Exportación",
            self.default_export_dir_input.text()
        )
        
        if directory:
            self.default_export_dir_input.setText(directory)
    
    def browse_report_dir(self):
        """Browse for report directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Directorio de Reportes",
            self.default_report_dir_input.text()
        )
        
        if directory:
            self.default_report_dir_input.setText(directory)
    
    def browse_logo(self):
        """Browse for company logo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Logo de Empresa",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if file_path:
            self.company_logo_input.setText(file_path)
    
    def change_highlight_color(self):
        """Change highlight color."""
        # Get current color from stylesheet
        style = self.highlight_color_preview.styleSheet()
        current_color = style.split("background-color:")[1].split(";")[0].strip()
        
        # Open color dialog
        color = QColorDialog.getColor(QColor(current_color), self, "Seleccionar Color de Resaltado")
        
        if color.isValid():
            # Update color preview
            self.highlight_color_preview.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #000000;")
