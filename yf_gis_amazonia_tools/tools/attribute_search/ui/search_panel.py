# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SearchPanel
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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QPushButton, QComboBox, QLineEdit, QCheckBox, QGroupBox, QRadioButton,
    QSplitter, QToolButton, QMenu, QMessageBox, QApplication, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize
from qgis.PyQt.QtGui import QIcon, QFont, QColor

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsMapLayerType, QgsExpression,
    QgsFeatureRequest, QgsExpressionContext, QgsExpressionContextUtils
)
from qgis.gui import QgsFilterLineEdit, QgsFieldExpressionWidget

class SearchPanel(QWidget):
    """Panel for advanced attribute search."""
    
    search_completed = pyqtSignal(list)  # Signal emitted when search is completed
    
    def __init__(self, iface):
        """Constructor."""
        super(SearchPanel, self).__init__()
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Set up the user interface
        self.setup_ui()
        
        # Initialize variables
        self.selected_layers = []
        self.search_results = []
        
        # Populate layer list
        self.update_layer_list()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        
        # Splitter for layer selection and search options
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # === LEFT SIDE: LAYER SELECTION ===
        self.layer_widget = QWidget()
        self.layer_layout = QVBoxLayout(self.layer_widget)
        self.layer_layout.setContentsMargins(0, 0, 0, 0)
        
        # Layer selection header
        self.layer_header = QLabel("Selección de Capas")
        self.layer_header.setFont(QFont("Arial", 10, QFont.Bold))
        self.layer_layout.addWidget(self.layer_header)
        
        # Layer filter
        self.layer_filter_layout = QHBoxLayout()
        self.layer_filter_label = QLabel("Filtrar:")
        self.layer_filter_layout.addWidget(self.layer_filter_label)
        
        self.layer_filter_input = QgsFilterLineEdit()
        self.layer_filter_input.setPlaceholderText("Filtrar capas por nombre...")
        self.layer_filter_layout.addWidget(self.layer_filter_input)
        
        self.layer_layout.addLayout(self.layer_filter_layout)
        
        # Layer tree
        self.layer_tree = QTreeWidget()
        self.layer_tree.setHeaderLabels(["Capas"])
        self.layer_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.layer_tree.setAlternatingRowColors(True)
        self.layer_layout.addWidget(self.layer_tree)
        
        # Layer options
        self.layer_options_layout = QHBoxLayout()
        
        self.select_all_button = QPushButton("Seleccionar Todo")
        self.layer_options_layout.addWidget(self.select_all_button)
        
        self.clear_selection_button = QPushButton("Limpiar Selección")
        self.layer_options_layout.addWidget(self.clear_selection_button)
        
        self.layer_layout.addLayout(self.layer_options_layout)
        
        # Add layer widget to splitter
        self.main_splitter.addWidget(self.layer_widget)
        
        # === RIGHT SIDE: SEARCH OPTIONS ===
        self.search_widget = QWidget()
        self.search_layout = QVBoxLayout(self.search_widget)
        self.search_layout.setContentsMargins(0, 0, 0, 0)
        
        # Search options header
        self.search_header = QLabel("Opciones de Búsqueda")
        self.search_header.setFont(QFont("Arial", 10, QFont.Bold))
        self.search_layout.addWidget(self.search_header)
        
        # Search type group
        self.search_type_group = QGroupBox("Tipo de Búsqueda")
        self.search_type_layout = QVBoxLayout(self.search_type_group)
        
        self.simple_search_radio = QRadioButton("Búsqueda Simple")
        self.simple_search_radio.setChecked(True)
        self.search_type_layout.addWidget(self.simple_search_radio)
        
        self.advanced_search_radio = QRadioButton("Búsqueda Avanzada (Expresión)")
        self.search_type_layout.addWidget(self.advanced_search_radio)
        
        self.search_layout.addWidget(self.search_type_group)
        
        # Simple search options
        self.simple_search_widget = QWidget()
        self.simple_search_layout = QVBoxLayout(self.simple_search_widget)
        self.simple_search_layout.setContentsMargins(0, 0, 0, 0)
        
        # Search text
        self.search_text_layout = QHBoxLayout()
        self.search_text_label = QLabel("Texto a buscar:")
        self.search_text_layout.addWidget(self.search_text_label)
        
        self.search_text_input = QLineEdit()
        self.search_text_input.setPlaceholderText("Ingrese texto para buscar...")
        self.search_text_layout.addWidget(self.search_text_input)
        
        self.simple_search_layout.addLayout(self.search_text_layout)
        
        # Search options
        self.search_options_group = QGroupBox("Opciones de Búsqueda Simple")
        self.search_options_layout = QVBoxLayout(self.search_options_group)
        
        self.case_sensitive_check = QCheckBox("Sensible a mayúsculas/minúsculas")
        self.search_options_layout.addWidget(self.case_sensitive_check)
        
        self.whole_word_check = QCheckBox("Coincidir palabra completa")
        self.search_options_layout.addWidget(self.whole_word_check)
        
        self.search_all_fields_check = QCheckBox("Buscar en todos los campos")
        self.search_all_fields_check.setChecked(True)
        self.search_options_layout.addWidget(self.search_all_fields_check)
        
        self.field_selection_layout = QHBoxLayout()
        self.field_selection_label = QLabel("Campo:")
        self.field_selection_layout.addWidget(self.field_selection_label)
        
        self.field_selection_combo = QComboBox()
        self.field_selection_combo.setEnabled(False)
        self.field_selection_layout.addWidget(self.field_selection_combo)
        
        self.search_options_layout.addLayout(self.field_selection_layout)
        
        self.simple_search_layout.addWidget(self.search_options_group)
        
        self.search_layout.addWidget(self.simple_search_widget)
        
        # Advanced search options
        self.advanced_search_widget = QWidget()
        self.advanced_search_layout = QVBoxLayout(self.advanced_search_widget)
        self.advanced_search_layout.setContentsMargins(0, 0, 0, 0)
        
        self.expression_label = QLabel("Expresión de búsqueda:")
        self.advanced_search_layout.addWidget(self.expression_label)
        
        self.expression_widget = QgsFieldExpressionWidget()
        self.advanced_search_layout.addWidget(self.expression_widget)
        
        self.advanced_search_layout.addStretch()
        
        self.search_layout.addWidget(self.advanced_search_widget)
        self.advanced_search_widget.setVisible(False)
        
        # Search limit
        self.limit_layout = QHBoxLayout()
        self.limit_label = QLabel("Límite de resultados:")
        self.limit_layout.addWidget(self.limit_label)
        
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["100", "500", "1000", "5000", "Sin límite"])
        self.limit_layout.addWidget(self.limit_combo)
        
        self.search_layout.addLayout(self.limit_layout)
        
        # Search buttons
        self.search_buttons_layout = QHBoxLayout()
        
        self.search_button = QPushButton("Buscar")
        self.search_button.setIcon(QIcon(os.path.join(self.plugin_dir, "icon.png")))
        self.search_buttons_layout.addWidget(self.search_button)
        
        self.clear_button = QPushButton("Limpiar")
        self.search_buttons_layout.addWidget(self.clear_button)
        
        self.search_layout.addLayout(self.search_buttons_layout)
        
        # Add search widget to splitter
        self.main_splitter.addWidget(self.search_widget)
        
        # Set splitter sizes
        self.main_splitter.setSizes([300, 500])
        
        # Add splitter to main layout
        self.main_layout.addWidget(self.main_splitter)
        
        # Connect signals
        self.connect_signals()
    
    def connect_signals(self):
        """Connect signals and slots."""
        # Layer filter
        self.layer_filter_input.textChanged.connect(self.filter_layers)
        
        # Layer selection buttons
        self.select_all_button.clicked.connect(self.select_all_layers)
        self.clear_selection_button.clicked.connect(self.clear_layer_selection)
        
        # Search type radio buttons
        self.simple_search_radio.toggled.connect(self.toggle_search_type)
        
        # Search all fields checkbox
        self.search_all_fields_check.toggled.connect(self.toggle_field_selection)
        
        # Layer tree selection
        self.layer_tree.itemSelectionChanged.connect(self.update_field_list)
        
        # Search buttons
        self.search_button.clicked.connect(self.execute_search)
        self.clear_button.clicked.connect(self.clear_search)
    
    def update_layer_list(self):
        """Update the layer list with current project layers."""
        self.layer_tree.clear()
        
        # Get all vector layers from the project
        layers = QgsProject.instance().mapLayers().values()
        vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
        
        # Add layers to tree
        for layer in vector_layers:
            item = QTreeWidgetItem(self.layer_tree)
            item.setText(0, layer.name())
            item.setData(0, Qt.UserRole, layer.id())
            
            # Set icon based on geometry type
            if layer.geometryType() == 0:  # Point
                item.setIcon(0, QIcon(os.path.join(self.plugin_dir, "icon.png")))
            elif layer.geometryType() == 1:  # Line
                item.setIcon(0, QIcon(os.path.join(self.plugin_dir, "icon.png")))
            elif layer.geometryType() == 2:  # Polygon
                item.setIcon(0, QIcon(os.path.join(self.plugin_dir, "icon.png")))
            else:
                item.setIcon(0, QIcon(os.path.join(self.plugin_dir, "icon.png")))
        
        # Update field list
        self.update_field_list()
    
    def filter_layers(self, text):
        """Filter layers by name."""
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            if text.lower() in item.text(0).lower():
                item.setHidden(False)
            else:
                item.setHidden(True)
    
    def select_all_layers(self):
        """Select all visible layers in the tree."""
        for i in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(i)
            if not item.isHidden():
                item.setSelected(True)
    
    def clear_layer_selection(self):
        """Clear layer selection."""
        self.layer_tree.clearSelection()
    
    def toggle_search_type(self, checked):
        """Toggle between simple and advanced search."""
        self.simple_search_widget.setVisible(self.simple_search_radio.isChecked())
        self.advanced_search_widget.setVisible(self.advanced_search_radio.isChecked())
        
        # Update expression widget layer
        if self.advanced_search_radio.isChecked():
            self.update_expression_widget()
    
    def toggle_field_selection(self, checked):
        """Toggle field selection combo box."""
        self.field_selection_combo.setEnabled(not checked)
    
    def update_field_list(self):
        """Update field list based on selected layers."""
        self.field_selection_combo.clear()
        
        # Get selected layers
        selected_items = self.layer_tree.selectedItems()
        if not selected_items:
            return
        
        # Get fields from first selected layer
        layer_id = selected_items[0].data(0, Qt.UserRole)
        layer = QgsProject.instance().mapLayer(layer_id)
        
        if layer and isinstance(layer, QgsVectorLayer):
            for field in layer.fields():
                self.field_selection_combo.addItem(field.name())
        
        # Update expression widget
        self.update_expression_widget()
    
    def update_expression_widget(self):
        """Update expression widget with selected layer."""
        # Get selected layers
        selected_items = self.layer_tree.selectedItems()
        if not selected_items:
            return
        
        # Set layer for expression widget
        layer_id = selected_items[0].data(0, Qt.UserRole)
        layer = QgsProject.instance().mapLayer(layer_id)
        
        if layer and isinstance(layer, QgsVectorLayer):
            self.expression_widget.setLayer(layer)
    
    def execute_search(self):
        """Execute search based on current settings."""
        # Check if layers are selected
        selected_items = self.layer_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self,
                "Advertencia",
                "Seleccione al menos una capa para buscar."
            )
            return
        
        # Get selected layers
        selected_layers = []
        for item in selected_items:
            layer_id = item.data(0, Qt.UserRole)
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer and isinstance(layer, QgsVectorLayer):
                selected_layers.append(layer)
        
        if not selected_layers:
            QMessageBox.warning(
                self,
                "Advertencia",
                "No se encontraron capas vectoriales seleccionadas."
            )
            return
        
        # Get search parameters
        if self.simple_search_radio.isChecked():
            # Simple search
            search_text = self.search_text_input.text().strip()
            if not search_text:
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    "Ingrese texto para buscar."
                )
                return
            
            case_sensitive = self.case_sensitive_check.isChecked()
            whole_word = self.whole_word_check.isChecked()
            search_all_fields = self.search_all_fields_check.isChecked()
            selected_field = self.field_selection_combo.currentText() if not search_all_fields else None
            
            # Build expression
            if search_all_fields:
                # Search in all fields
                self.search_results = self.search_in_all_fields(
                    selected_layers,
                    search_text,
                    case_sensitive,
                    whole_word
                )
            else:
                # Search in selected field
                self.search_results = self.search_in_field(
                    selected_layers,
                    selected_field,
                    search_text,
                    case_sensitive,
                    whole_word
                )
        else:
            # Advanced search
            expression_text = self.expression_widget.expression()
            if not expression_text:
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    "Ingrese una expresión de búsqueda."
                )
                return
            
            # Execute search with expression
            self.search_results = self.search_with_expression(
                selected_layers,
                expression_text
            )
        
        # Get result limit
        limit_text = self.limit_combo.currentText()
        if limit_text != "Sin límite":
            limit = int(limit_text)
            if len(self.search_results) > limit:
                self.search_results = self.search_results[:limit]
                QMessageBox.information(
                    self,
                    "Información",
                    f"Se encontraron más de {limit} resultados. "
                    f"Mostrando los primeros {limit}."
                )
        
        # Emit search completed signal
        self.search_completed.emit(self.search_results)
        
        # Show message
        if not self.search_results:
            QMessageBox.information(
                self,
                "Información",
                "No se encontraron resultados que coincidan con los criterios de búsqueda."
            )
    
    def search_in_all_fields(self, layers, search_text, case_sensitive, whole_word):
        """Search in all fields of the selected layers."""
        results = []
        
        # Escape single quotes to prevent expression injection
        safe_text = search_text.replace("'", "''")
        
        # Show progress
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            for layer in layers:
                # Build expression parts for each field
                expr_parts = []
                for field in layer.fields():
                    field_name = field.name()
                    
                    # Skip geometry fields
                    if field.typeName() == "geometry":
                        continue
                    
                    # Build expression based on search options
                    if whole_word:
                        if case_sensitive:
                            expr_parts.append(f'"{field_name}" = \'{safe_text}\'')
                        else:
                            expr_parts.append(f'lower("{field_name}") = lower(\'{safe_text}\')')
                    else:
                        if case_sensitive:
                            expr_parts.append(f'"{field_name}" LIKE \'%{safe_text}%\'')
                        else:
                            expr_parts.append(f'lower("{field_name}") LIKE lower(\'%{safe_text}%\')')
                
                # Combine expressions with OR
                if expr_parts:
                    expression_text = " OR ".join(expr_parts)
                    expression = QgsExpression(expression_text)
                    
                    # Check if expression is valid
                    if expression.hasParserError():
                        QMessageBox.warning(
                            self,
                            "Error",
                            f"Error en la expresión: {expression.parserErrorString()}"
                        )
                        continue
                    
                    # Create feature request
                    request = QgsFeatureRequest(expression)
                    
                    # Get features
                    for feature in layer.getFeatures(request):
                        # Find matching field(s)
                        matching_fields = []
                        for field in layer.fields():
                            field_name = field.name()
                            field_value = str(feature[field_name])
                            
                            # Check if field matches search text
                            if whole_word:
                                if case_sensitive:
                                    if field_value == search_text:
                                        matching_fields.append(field_name)
                                else:
                                    if field_value.lower() == search_text.lower():
                                        matching_fields.append(field_name)
                            else:
                                if case_sensitive:
                                    if search_text in field_value:
                                        matching_fields.append(field_name)
                                else:
                                    if search_text.lower() in field_value.lower():
                                        matching_fields.append(field_name)
                        
                        # Add result
                        for field_name in matching_fields:
                            results.append({
                                'layer': layer,
                                'feature_id': feature.id(),
                                'feature': feature,
                                'field_name': field_name,
                                'field_value': str(feature[field_name])
                            })
        finally:
            QApplication.restoreOverrideCursor()
        
        return results
    
    def search_in_field(self, layers, field_name, search_text, case_sensitive, whole_word):
        """Search in a specific field of the selected layers."""
        results = []
        
        # Escape single quotes to prevent expression injection
        safe_text = search_text.replace("'", "''")
        
        # Show progress
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            for layer in layers:
                # Check if field exists in layer
                if field_name not in layer.fields().names():
                    continue
                
                # Build expression based on search options
                if whole_word:
                    if case_sensitive:
                        expression_text = f'"{field_name}" = \'{safe_text}\''
                    else:
                        expression_text = f'lower("{field_name}") = lower(\'{safe_text}\')'
                else:
                    if case_sensitive:
                        expression_text = f'"{field_name}" LIKE \'%{safe_text}%\''
                    else:
                        expression_text = f'lower("{field_name}") LIKE lower(\'%{safe_text}%\')'
                
                expression = QgsExpression(expression_text)
                
                # Check if expression is valid
                if expression.hasParserError():
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Error en la expresión: {expression.parserErrorString()}"
                    )
                    continue
                
                # Create feature request
                request = QgsFeatureRequest(expression)
                
                # Get features
                for feature in layer.getFeatures(request):
                    # Add result
                    results.append({
                        'layer': layer,
                        'feature_id': feature.id(),
                        'feature': feature,
                        'field_name': field_name,
                        'field_value': str(feature[field_name])
                    })
        finally:
            QApplication.restoreOverrideCursor()
        
        return results
    
    def search_with_expression(self, layers, expression_text):
        """Search with custom expression."""
        results = []
        
        # Show progress
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            for layer in layers:
                expression = QgsExpression(expression_text)
                
                # Check if expression is valid
                if expression.hasParserError():
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Error en la expresión: {expression.parserErrorString()}"
                    )
                    continue
                
                # Create context
                context = QgsExpressionContext()
                context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
                
                # Create feature request
                request = QgsFeatureRequest(expression, context)
                
                # Get features
                for feature in layer.getFeatures(request):
                    # Add result for each field
                    for field_name in layer.fields().names():
                        results.append({
                            'layer': layer,
                            'feature_id': feature.id(),
                            'feature': feature,
                            'field_name': field_name,
                            'field_value': str(feature[field_name])
                        })
        finally:
            QApplication.restoreOverrideCursor()
        
        return results
    
    def clear_search(self):
        """Clear search inputs and results."""
        # Clear search text
        self.search_text_input.clear()
        
        # Reset search options
        self.case_sensitive_check.setChecked(False)
        self.whole_word_check.setChecked(False)
        self.search_all_fields_check.setChecked(True)
        
        # Clear expression
        self.expression_widget.setExpression("")
        
        # Reset search type
        self.simple_search_radio.setChecked(True)
        
        # Clear results
        self.search_results = []
