# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MainDialog
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
    QDockWidget, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QComboBox, QCheckBox, QLineEdit,
    QGroupBox, QRadioButton, QToolBar, QAction, QMenu, QHeaderView,
    QMessageBox, QFileDialog, QToolButton, QSizePolicy
)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QSettings, QSize
from qgis.PyQt.QtGui import QIcon, QFont, QColor

from qgis.core import QgsProject, QgsVectorLayer, QgsMapLayerType
from qgis.gui import QgsFilterLineEdit

from .search_panel import SearchPanel
from .results_panel import ResultsPanel
from .report_panel import ReportPanel
from .settings_panel import SettingsPanel

class MainDialog(QDockWidget):
    """Main dialog for the QGIS Attribute Search plugin."""
    
    closingPlugin = pyqtSignal()
    
    def __init__(self, iface):
        """Constructor."""
        super(MainDialog, self).__init__(iface.mainWindow())
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        
        # Set up the user interface
        self.setup_ui()
        
        # Load settings
        self.load_settings()
        
        # Connect signals
        self.connect_signals()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Búsqueda Avanzada de Atributos")
        self.setMinimumSize(800, 600)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Main widget and layout
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
        # Add toolbar actions
        self.action_new_search = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Nueva Búsqueda",
            self
        )
        self.toolbar.addAction(self.action_new_search)
        
        self.action_save_results = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Guardar Resultados",
            self
        )
        self.toolbar.addAction(self.action_save_results)
        
        self.action_generate_report = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Generar Reporte",
            self
        )
        self.toolbar.addAction(self.action_generate_report)
        
        self.toolbar.addSeparator()
        
        self.action_help = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Ayuda",
            self
        )
        self.toolbar.addAction(self.action_help)
        
        self.main_layout.addWidget(self.toolbar)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Create panels
        self.search_panel = SearchPanel(self.iface)
        self.results_panel = ResultsPanel(self.iface)
        self.report_panel = ReportPanel(self.iface)
        self.settings_panel = SettingsPanel(self.iface)
        
        # Add tabs
        self.tab_widget.addTab(self.search_panel, "Búsqueda")
        self.tab_widget.addTab(self.results_panel, "Resultados")
        self.tab_widget.addTab(self.report_panel, "Reportes")
        self.tab_widget.addTab(self.settings_panel, "Configuración")
        
        self.main_layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = QWidget()
        self.status_layout = QHBoxLayout(self.status_bar)
        self.status_layout.setContentsMargins(5, 2, 5, 2)
        
        self.status_label = QLabel("Listo")
        self.status_layout.addWidget(self.status_label)
        
        self.results_count_label = QLabel("0 resultados")
        self.status_layout.addWidget(self.results_count_label, 0, Qt.AlignRight)
        
        self.main_layout.addWidget(self.status_bar)
        
        # Set the main widget
        self.setWidget(self.main_widget)
    
    def connect_signals(self):
        """Connect signals and slots."""
        # Connect tab widget signals
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Connect toolbar actions
        self.action_new_search.triggered.connect(self.on_new_search)
        self.action_save_results.triggered.connect(self.on_save_results)
        self.action_generate_report.triggered.connect(self.on_generate_report)
        self.action_help.triggered.connect(self.on_help)
        
        # Connect panel signals
        self.search_panel.search_completed.connect(self.on_search_completed)
        self.results_panel.selection_changed.connect(self.on_result_selection_changed)
        
        # Connect to QGIS project signals
        QgsProject.instance().layersAdded.connect(self.on_layers_changed)
        QgsProject.instance().layersRemoved.connect(self.on_layers_changed)
    
    def load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        settings.beginGroup("QGISAttributeSearch")
        
        # Restore geometry
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # Restore dock location
        area = settings.value("dockArea", Qt.RightDockWidgetArea)
        if area:
            self.iface.mainWindow().addDockWidget(int(area), self)
        
        # Restore current tab
        current_tab = settings.value("currentTab", 0)
        if current_tab:
            self.tab_widget.setCurrentIndex(int(current_tab))
        
        settings.endGroup()
    
    def save_settings(self):
        """Save settings to QSettings."""
        settings = QSettings()
        settings.beginGroup("QGISAttributeSearch")
        
        # Save geometry
        settings.setValue("geometry", self.saveGeometry())
        
        # Save dock location
        settings.setValue("dockArea", self.iface.mainWindow().dockWidgetArea(self))
        
        # Save current tab
        settings.setValue("currentTab", self.tab_widget.currentIndex())
        
        settings.endGroup()
    
    def closeEvent(self, event):
        """Handle close event."""
        self.save_settings()
        self.closingPlugin.emit()
        event.accept()
    
    def setCurrentTab(self, index):
        """Set the current tab index."""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)
    
    def on_tab_changed(self, index):
        """Handle tab changed event."""
        # Update toolbar actions based on current tab
        if index == 0:  # Search tab
            self.action_new_search.setEnabled(True)
            self.action_save_results.setEnabled(False)
            self.action_generate_report.setEnabled(False)
        elif index == 1:  # Results tab
            self.action_new_search.setEnabled(True)
            self.action_save_results.setEnabled(True)
            self.action_generate_report.setEnabled(True)
        elif index == 2:  # Reports tab
            self.action_new_search.setEnabled(True)
            self.action_save_results.setEnabled(False)
            self.action_generate_report.setEnabled(True)
        elif index == 3:  # Settings tab
            self.action_new_search.setEnabled(True)
            self.action_save_results.setEnabled(False)
            self.action_generate_report.setEnabled(False)
    
    def on_new_search(self):
        """Handle new search action."""
        self.tab_widget.setCurrentIndex(0)
        self.search_panel.clear_search()
    
    def on_save_results(self):
        """Handle save results action."""
        if not hasattr(self.results_panel, 'results') or not self.results_panel.results:
            QMessageBox.warning(self, "Advertencia", "No hay resultados para guardar.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Resultados",
            "",
            "CSV (*.csv);;Excel (*.xlsx);;GeoJSON (*.geojson)"
        )
        
        if file_path:
            try:
                self.results_panel.export_results(file_path)
                QMessageBox.information(
                    self,
                    "Éxito",
                    f"Resultados guardados exitosamente en:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Error al guardar resultados: {str(e)}"
                )
    
    def on_generate_report(self):
        """Handle generate report action."""
        self.tab_widget.setCurrentIndex(2)
        self.report_panel.prepare_report()
    
    def on_help(self):
        """Handle help action."""
        QMessageBox.information(
            self,
            "Ayuda",
            "Búsqueda Avanzada de Atributos\n\n"
            "Este plugin permite realizar búsquedas avanzadas en las capas de QGIS, "
            "visualizar los resultados y generar reportes.\n\n"
            "Para comenzar, seleccione las capas y criterios de búsqueda en la pestaña 'Búsqueda'."
        )
    
    def on_search_completed(self, results):
        """Handle search completed signal from search panel."""
        self.results_panel.set_results(results)
        self.results_count_label.setText(f"{len(results)} resultados")
        self.tab_widget.setCurrentIndex(1)  # Switch to results tab
    
    def on_result_selection_changed(self, selected_features):
        """Handle result selection changed signal from results panel."""
        if selected_features:
            self.status_label.setText(f"{len(selected_features)} elementos seleccionados")
        else:
            self.status_label.setText("Listo")
    
    def on_layers_changed(self):
        """Handle layers added or removed from the project."""
        self.search_panel.update_layer_list()
