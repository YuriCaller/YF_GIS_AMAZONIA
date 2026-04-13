# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ResultsPanel
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
import csv
from io import BytesIO

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QCheckBox, QGroupBox, QRadioButton, QSplitter,
    QToolButton, QMenu, QAction, QMessageBox, QFileDialog, QHeaderView,
    QAbstractItemView, QTabWidget, QToolBar, QInputDialog, QLineEdit # Added QLineEdit
)
# Added pyqtSignal, QTimer, QVariant
from qgis.PyQt.QtCore import Qt, pyqtSignal, QSortFilterProxyModel, QSize, QTimer, QVariant 
from qgis.PyQt.QtGui import QIcon, QFont, QColor, QPixmap

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsRectangle,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsWkbTypes,
    QgsVectorFileWriter, QgsFeatureRequest, QgsField, QgsMessageLog, Qgis # Added QgsField, QgsMessageLog, Qgis
)
from qgis.gui import QgsMapCanvas, QgsRubberBand, QgsMapToolPan

class ResultsPanel(QWidget):
    """Panel for displaying and interacting with search results."""
    
    selection_changed = pyqtSignal(list)  # Signal emitted when selection changes
    restart_requested = pyqtSignal() # Signal emitted to request going back to search tab
    
    def __init__(self, iface):
        """Constructor."""
        super(ResultsPanel, self).__init__()
        self.iface = iface
        # Correct plugin_dir path assuming this file is in ui folder
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        
        # Initialize variables
        self.results = []
        self.selected_features_info = [] # Store {"layer": layer, "feature_id": fid} for selected rows
        self.rubber_bands = {} # Use dict to manage rubber bands per layer {layer_id: [rubber_band, ...]}
        
        # Set up the user interface
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        
        # Tabs for results view and visualization
        self.tabs = QTabWidget()
        
        # === RESULTS TAB ===
        self.results_tab = QWidget()
        self.results_layout = QVBoxLayout(self.results_tab)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        
        # Results toolbar
        self.results_toolbar = QToolBar()
        self.results_toolbar.setIconSize(QSize(16, 16))
        # --- Set style to show text beside icons ---
        self.results_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # --- End style setting ---

        # --- Added Restart Search Action ---
        self.restart_search_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")), # Consider a different icon
            "Reiniciar Búsqueda",
            self
        )
        self.restart_search_action.setToolTip("Limpia los resultados y vuelve a la pestaña de búsqueda")
        self.restart_search_action.triggered.connect(self.handle_restart_request)
        self.results_toolbar.addAction(self.restart_search_action)
        self.results_toolbar.addSeparator()
        # --- End Added Restart Search Action ---
        
        # Zoom to selected action
        self.zoom_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Zoom a Seleccionados",
            self
        )
        self.zoom_action.triggered.connect(self.zoom_to_selected)
        self.results_toolbar.addAction(self.zoom_action)
        
        # Select features action
        self.select_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Seleccionar Entidades",
            self
        )
        self.select_action.triggered.connect(self.select_features)
        self.results_toolbar.addAction(self.select_action)
        
        # Deselect Action
        self.deselect_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")), # Consider a different icon
            "Desactivar Resaltado",
            self
        )
        self.deselect_action.triggered.connect(lambda: self.deselect_all_features(silent=False))
        self.results_toolbar.addAction(self.deselect_action)
        
        # Flash features action (Kept for temporary flash)
        self.flash_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Destacar Temporalmente", # Renamed for clarity
            self
        )
        self.flash_action.triggered.connect(self.flash_features)
        self.results_toolbar.addAction(self.flash_action)
        
        # Open attribute table action
        self.attribute_table_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Abrir Tabla de Atributos",
            self
        )
        self.attribute_table_action.triggered.connect(self.open_attribute_table)
        self.results_toolbar.addAction(self.attribute_table_action)
        
        self.results_toolbar.addSeparator()
        
        # Export results action
        self.export_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Exportar Resultados",
            self
        )
        self.export_action.triggered.connect(self.export_results_dialog)
        self.results_toolbar.addAction(self.export_action)
        
        # Create layer from results action
        self.create_layer_action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icon.png")),
            "Crear Capa desde Resultados",
            self
        )
        self.create_layer_action.triggered.connect(self.create_layer_from_results)
        self.results_toolbar.addAction(self.create_layer_action)
        
        self.results_layout.addWidget(self.results_toolbar)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Capa", "ID", "Campo", "Valor"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        # Make last column stretch, others resize to contents initially
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        
        self.results_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self.show_context_menu)
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        self.results_layout.addWidget(self.results_table)
        
        # Add results tab
        self.tabs.addTab(self.results_tab, "Tabla de Resultados")
        
        # === VISUALIZATION TAB ===
        self.visualization_tab = QWidget()
        self.visualization_layout = QVBoxLayout(self.visualization_tab)
        self.visualization_layout.setContentsMargins(0, 0, 0, 0)
        
        # Visualization options
        self.visualization_options = QHBoxLayout()
        
        self.chart_type_label = QLabel("Tipo de Gráfico:")
        self.visualization_options.addWidget(self.chart_type_label)
        
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["Barras", "Pastel", "Líneas"])
        self.chart_type_combo.currentIndexChanged.connect(self.update_visualization)
        self.visualization_options.addWidget(self.chart_type_combo)
        
        self.field_label = QLabel("Campo:")
        self.visualization_options.addWidget(self.field_label)
        
        self.field_combo = QComboBox()
        self.field_combo.currentIndexChanged.connect(self.update_visualization)
        self.visualization_options.addWidget(self.field_combo)
        
        self.visualization_options.addStretch()
        
        self.visualization_layout.addLayout(self.visualization_options)
        
        # Chart canvas (requires matplotlib)
        if HAS_MATPLOTLIB:
            self.figure = Figure(figsize=(5, 4), dpi=100)
            self.canvas = FigureCanvas(self.figure)
            self.visualization_layout.addWidget(self.canvas)
        else:
            self.figure = None
            self.canvas = None
            no_mpl = QLabel("Visualización no disponible.\nInstale matplotlib: pip install matplotlib")
            no_mpl.setAlignment(Qt.AlignCenter)
            self.visualization_layout.addWidget(no_mpl)
        
        # Add visualization tab
        self.tabs.addTab(self.visualization_tab, "Visualización")
        
        # Add tabs to main layout
        self.main_layout.addWidget(self.tabs)
        
        # Connect tab changed signal
        self.tabs.currentChanged.connect(self.on_tab_changed)
    
    def set_results(self, results):
        """Set search results and update UI."""
        self.results = results
        self.update_results_table()
        self.update_field_combo()
        # Don"t automatically update visualization, let user choose field
        # self.update_visualization()
        # Clear previous selection when new results arrive
        self.deselect_all_features(silent=True)
        self.clear_rubber_bands()
    
    def update_results_table(self):
        """Update results table with current results."""
        self.results_table.setSortingEnabled(False) # Disable sorting during update
        # Clear table
        self.results_table.setRowCount(0)
        
        # Add results to table
        for i, result in enumerate(self.results):
            self.results_table.insertRow(i)
            
            # Layer name
            layer_item = QTableWidgetItem(result["layer"].name())
            # Store the actual result dictionary in the first item for later retrieval
            layer_item.setData(Qt.UserRole, result) 
            self.results_table.setItem(i, 0, layer_item)
            
            # Feature ID
            id_item = QTableWidgetItem(str(result["feature_id"]))
            self.results_table.setItem(i, 1, id_item)
            
            # Field name
            field_item = QTableWidgetItem(result["field_name"])
            self.results_table.setItem(i, 2, field_item)
            
            # Field value
            value_item = QTableWidgetItem(str(result["field_value"])) # Ensure value is string
            self.results_table.setItem(i, 3, value_item)
        
        # Resize columns to content after populating
        self.results_table.resizeColumnsToContents()
        # Re-apply stretch to last column if needed
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.results_table.setSortingEnabled(True) # Re-enable sorting
    
    def update_field_combo(self):
        """Update field combo box with available fields from results."""
        self.field_combo.clear()
        
        if not self.results:
            return
        
        # Get unique field names from the results list
        field_names = set(result["field_name"] for result in self.results)
        
        # Add field names to combo box
        self.field_combo.addItems(sorted(list(field_names)))
    
    def update_visualization(self):
        """Update visualization based on current settings."""
        if not HAS_MATPLOTLIB or self.figure is None:
            return
        
        if not self.results:
            self.figure.clear()
            self.canvas.draw()
            return
        
        # Clear figure
        self.figure.clear()
        
        # Get selected field
        field_name = self.field_combo.currentText()
        if not field_name:
            self.canvas.draw() # Draw empty canvas if no field selected
            return
        
        # Get chart type
        chart_type = self.chart_type_combo.currentText()
        
        # Filter results by selected field
        filtered_results = [r for r in self.results if r["field_name"] == field_name]
        if not filtered_results:
             self.canvas.draw()
             return

        # Count values
        value_counts = {}
        for result in filtered_results:
            # Use string representation for counting, handle potential None
            value_str = str(result["field_value"]) if result["field_value"] is not None else "(Vacío)"
            value_counts[value_str] = value_counts.get(value_str, 0) + 1
        
        # Sort by count
        # Limit number of items to plot for clarity
        MAX_ITEMS = 15
        sorted_items = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
        
        if len(sorted_items) > MAX_ITEMS:
            top_items = sorted_items[:MAX_ITEMS]
            other_count = sum(item[1] for item in sorted_items[MAX_ITEMS:])
            if other_count > 0:
                plot_items = top_items + [("Otros", other_count)]
            else:
                plot_items = top_items
        else:
            plot_items = sorted_items
        
        # Extract labels and values
        labels = [item[0] for item in plot_items]
        values = [item[1] for item in plot_items]
        
        # Create subplot
        ax = self.figure.add_subplot(111)
        
        # Create chart based on type
        try:
            if chart_type == "Barras":
                ax.bar(labels, values)
                ax.set_ylabel("Conteo")
            elif chart_type == "Pastel":
                # Ensure labels are unique for pie chart if needed, or handle duplicates
                wedges, texts, autotexts = ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
                ax.axis("equal") # Equal aspect ratio ensures that pie is drawn as a circle.
            elif chart_type == "Líneas":
                # Line chart might not be suitable for categorical data unless ordered
                ax.plot(labels, values, marker="o")
                ax.set_ylabel("Conteo")
            
            ax.set_title(f"Distribución para \"{field_name}\"")
            # Improve label readability
            if chart_type != "Pastel":
                plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

        except Exception as e:
            QgsMessageLog.logMessage(f"Error generando gráfico: {e}", "AttributeSearch", Qgis.Warning)
            ax.text(0.5, 0.5, "Error al generar gráfico", horizontalalignment="center", verticalalignment="center")

        # Adjust layout
        try:
            self.figure.tight_layout()
        except ValueError: # Avoid potential tight_layout errors with certain data
            pass 
        
        # Redraw canvas
        self.canvas.draw()
    
    def on_tab_changed(self, index):
        """Handle tab changed event."""
        # Update visualization only if the visualization tab is selected
        if self.tabs.widget(index) == self.visualization_tab:
            self.update_visualization()
    
    def on_selection_changed(self):
        """Handle selection changed in results table."""
        self.selected_features_info = []
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            self.selection_changed.emit(self.selected_features_info)
            return
        
        selected_rows = sorted(list(set(item.row() for item in selected_items)))
        
        for row in selected_rows:
            # Retrieve the stored result dictionary from the first column"s UserRole data
            result_item = self.results_table.item(row, 0)
            if result_item:
                result_data = result_item.data(Qt.UserRole)
                if result_data and isinstance(result_data, dict):
                    self.selected_features_info.append(result_data)
        
        self.selection_changed.emit(self.selected_features_info)

    def get_selected_layers_and_fids(self):
        """Helper to get selected layer objects and feature IDs."""
        features_by_layer = {}
        if not self.selected_features_info:
            return features_by_layer
            
        for result_info in self.selected_features_info:
            layer = result_info.get("layer")
            feature_id = result_info.get("feature_id")
            if layer and layer.isValid() and feature_id is not None:
                if layer not in features_by_layer:
                    features_by_layer[layer] = []
                features_by_layer[layer].append(feature_id)
        return features_by_layer

    def zoom_to_selected(self):
        """Zoom to selected features."""
        features_by_layer = self.get_selected_layers_and_fids()
        if not features_by_layer:
            QMessageBox.warning(self, "Advertencia", "Seleccione al menos una entidad válida para hacer zoom.")
            return
        
        combined_extent = QgsRectangle()
        combined_extent.setMinimal()
        valid_extent_found = False
        
        project_crs = QgsProject.instance().crs()
        
        for layer, feature_ids in features_by_layer.items():
            request = QgsFeatureRequest().setFilterFids(feature_ids)
            layer_extent = QgsRectangle()
            layer_extent.setMinimal()
            transform = None
            if layer.crs() != project_crs:
                transform = QgsCoordinateTransform(layer.crs(), project_crs, QgsProject.instance())

            for feature in layer.getFeatures(request):
                geom = feature.geometry()
                if geom and not geom.isEmpty():
                    bbox = geom.boundingBox()
                    if transform:
                        bbox = transform.transformBoundingBox(bbox)
                    layer_extent.combineExtentWith(bbox)
                    valid_extent_found = True
            
            if layer_extent.isEmpty(): # Check if extent is still empty (no valid geometries)
                 QgsMessageLog.logMessage(f"No se pudo obtener la extensión para las entidades seleccionadas en la capa {layer.name()}", "AttributeSearch", Qgis.Warning)
                 continue

            combined_extent.combineExtentWith(layer_extent)

        if not valid_extent_found or combined_extent.isEmpty():
            QMessageBox.warning(self, "Advertencia", "No se pudo determinar la extensión de las entidades seleccionadas.")
            return

        # Zoom to combined extent with buffer
        canvas = self.iface.mapCanvas()
        if combined_extent.width() == 0 and combined_extent.height() == 0: # Single point
             canvas.setCenter(combined_extent.center())
             canvas.zoomScale(canvas.scale() / 2) # Zoom in a bit
        else:
             canvas.setExtent(combined_extent)
             canvas.zoomByFactor(1.2) # Zoom out slightly for buffer
        canvas.refresh()
        
        # Optionally flash features after zoom
        # self.flash_features()
        # Or select them
        self.select_features()
    
    def select_features(self):
        """Select features in QGIS based on table selection."""
        features_by_layer = self.get_selected_layers_and_fids()
        if not features_by_layer:
            QMessageBox.warning(self, "Advertencia", "Seleccione al menos una entidad válida para seleccionar en el mapa.")
            return
        
        # Deselect features in all project layers first for a clean selection
        # self.deselect_all_features(silent=True) 
        # Or deselect only in involved layers
        for layer in features_by_layer.keys():
             layer.removeSelection()

        # Select features in each relevant layer
        for layer, feature_ids in features_by_layer.items():
            layer.selectByIds(feature_ids)
        
        self.iface.mapCanvas().refresh() # Refresh map canvas to show selection
        QgsMessageLog.logMessage(f"Seleccionadas {len(self.selected_features_info)} entidades.", "AttributeSearch", Qgis.Info)

    # Deselect All Function
    def deselect_all_features(self, silent=False):
        """Deselects features in all vector layers in the project."""
        layers = QgsProject.instance().mapLayers().values()
        deselected_count = 0
        for layer in layers:
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                if layer.selectedFeatureCount() > 0:
                    layer.removeSelection()
                    deselected_count += 1
        
        if deselected_count > 0:
            self.iface.mapCanvas().refresh()
            if not silent:
                QMessageBox.information(self, "Resaltado Desactivado", f"Se ha quitado la selección en {deselected_count} capa(s).")
        elif not silent:
             QMessageBox.information(self, "Resaltado Desactivado", "No había entidades seleccionadas.")

    def flash_features(self):
        """Flash selected features on the map temporarily using rubber bands."""
        features_by_layer = self.get_selected_layers_and_fids()
        if not features_by_layer:
            QMessageBox.warning(self, "Advertencia", "Seleccione al menos una entidad válida para destacar.")
            return

        # Clear existing rubber bands first
        self.clear_rubber_bands()
        
        canvas = self.iface.mapCanvas()
        project_crs = canvas.mapSettings().destinationCrs()
        bands_created = False

        for layer, feature_ids in features_by_layer.items():
            request = QgsFeatureRequest().setFilterFids(feature_ids)
            transform = None
            if layer.crs() != project_crs:
                transform = QgsCoordinateTransform(layer.crs(), project_crs, QgsProject.instance())
            
            if layer.id() not in self.rubber_bands:
                 self.rubber_bands[layer.id()] = []

            for feature in layer.getFeatures(request):
                geom = feature.geometry()
                if geom and not geom.isEmpty():
                    if transform:
                        try:
                            geom.transform(transform)
                        except Exception as e:
                            QgsMessageLog.logMessage(f"Error transformando geometría FID {feature.id()} en capa {layer.name()}: {e}", "AttributeSearch", Qgis.Warning)
                            continue
                    
                    # Create rubber band based on geometry type
                    geom_type = geom.wkbType()
                    rb = QgsRubberBand(canvas, QgsWkbTypes.geometryType(geom_type))
                    rb.setColor(QColor(255, 0, 0, 128)) # Semi-transparent red
                    rb.setWidth(2)
                    # --- Fix for isPointType --- 
                    # Check if geometry type is any of the point types
                    if geom_type in [QgsWkbTypes.Point, QgsWkbTypes.PointZ, QgsWkbTypes.PointM, QgsWkbTypes.PointZM]:
                         rb.setIcon(QgsRubberBand.ICON_CIRCLE)
                         rb.setIconSize(10)
                    # --- End fix ---
                    
                    rb.setToGeometry(geom, layer) # Pass layer for context if needed
                    self.rubber_bands[layer.id()].append(rb)
                    bands_created = True
        
        if bands_created:
            canvas.refresh()
            # Schedule removal of rubber bands after a short delay (e.g., 2 seconds)
            QTimer.singleShot(2000, self.clear_rubber_bands)
        else:
             QMessageBox.warning(self, "Advertencia", "No se pudieron obtener geometrías válidas para destacar.")

    def clear_rubber_bands(self):
        """Clear all rubber bands managed by this panel."""
        canvas = self.iface.mapCanvas()
        something_cleared = False
        for layer_id in list(self.rubber_bands.keys()): # Iterate over keys copy
            bands = self.rubber_bands.pop(layer_id, [])
            for rb in bands:
                if rb: # Check if rubber band still exists
                    try:
                        canvas.scene().removeItem(rb)
                        # rb.reset() # Alternative? Check QGIS API docs
                        del rb # Explicitly delete?
                        something_cleared = True
                    except Exception as e:
                         # Catch potential errors if item already removed
                         QgsMessageLog.logMessage(f"Error eliminando rubber band: {e}", "AttributeSearch", Qgis.Debug)
            
        if something_cleared:
            # Only refresh if something was actually cleared
            # canvas.refresh() # Refresh might be excessive if called frequently
            pass
        self.rubber_bands = {} # Ensure it"s empty
    
    def open_attribute_table(self):
        """Open attribute table for the layer of the first selected feature."""
        # Check if features are selected
        if not self.selected_features_info:
            QMessageBox.warning(self, "Advertencia", "Seleccione al menos una entidad para abrir la tabla de atributos.")
            return
        
        # Get the layer of the first selected result
        first_result = self.selected_features_info[0]
        layer = first_result.get("layer")
        
        if layer and layer.isValid():
            # Select features in this layer corresponding to the table selection
            fids_for_layer = [res["feature_id"] for res in self.selected_features_info if res.get("layer") == layer]
            if fids_for_layer:
                 layer.selectByIds(fids_for_layer)
            # Open attribute table for this layer
            self.iface.showAttributeTable(layer)
        else:
             QMessageBox.critical(self, "Error", "La capa asociada a la entidad seleccionada no es válida.")

    def export_results_dialog(self):
        """Show dialog to export results."""
        if not self.results:
            QMessageBox.warning(self, "Advertencia", "No hay resultados para exportar.")
            return
        
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exportar Resultados",
            "",
            "CSV (*.csv);;Excel (*.xlsx)" # Removed GeoJSON for simplicity, focus on table data
            # ";;GeoJSON (*.geojson)" 
        )
        
        if not file_path:
            return
        
        try:
            self.export_results(file_path)
            QMessageBox.information(self, "Éxito", f"Resultados exportados exitosamente a:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar resultados: {str(e)}")
            QgsMessageLog.logMessage(f"Error exportando resultados: {e}", "AttributeSearch", Qgis.Critical)
    
    def export_results(self, file_path):
        """Export results (table data) to file."""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Prepare data as list of dicts for easier export
        data_to_export = []
        for result in self.results:
             data_to_export.append({
                 "Capa": result["layer"].name(),
                 "ID": result["feature_id"],
                 "Campo": result["field_name"],
                 "Valor": str(result["field_value"]) # Ensure string
             })

        if ext == ".csv":
            if not data_to_export:
                 # Write empty file with header if no data
                 with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                      writer = csv.writer(csvfile)
                      writer.writerow(["Capa", "ID", "Campo", "Valor"]) # Header
                 return
                 
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                # Use DictWriter for robustness
                fieldnames = ["Capa", "ID", "Campo", "Valor"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data_to_export)
        
        elif ext == ".xlsx":
            try:
                df = pd.DataFrame(data_to_export)
                df.to_excel(file_path, index=False, engine="openpyxl") # Specify engine
            except ImportError:
                 QMessageBox.critical(self, 'Error', 'La exportación a Excel requiere las bibliotecas "pandas" y "openpyxl". Instálelas (ej: pip install pandas openpyxl) e inténtelo de nuevo.')
                 # Fallback to CSV?
                 # csv_path = os.path.splitext(file_path)[0] + ".csv"
                 # self.export_results(csv_path)
                 # QMessageBox.warning(self, "Alternativa", f"Se intentó guardar como CSV en: {csv_path}")
                 raise # Re-raise the import error to stop execution here
            except Exception as e:
                 raise Exception(f"Error al escribir archivo Excel: {e}")

        # Removed GeoJSON export logic - focus on table data export
        # elif ext == ".geojson": ...
        
        else:
            raise ValueError(f"Formato de archivo no soportado: {ext}")
    
    def create_layer_from_results(self):
        """Create a new layer(s) from selected results."""
        features_by_layer = self.get_selected_layers_and_fids()
        if not features_by_layer:
            QMessageBox.warning(self, "Advertencia", "Seleccione al menos una entidad válida para crear una capa.")
            return

        # Ask for layer name prefix
        prefix, ok = QInputDialog.getText(self, "Crear Capa", "Prefijo para nombre de capa(s):", QLineEdit.Normal, "Resultados")
        if not ok or not prefix:
            prefix = "Resultados"

        layers_created_count = 0
        for original_layer, fids in features_by_layer.items():
            new_layer_name = f"{prefix}_{original_layer.name()}"
            # Ensure unique name
            # Need QgsProject instance, assuming it"s available via self.iface or passed in
            # Using QgsProject.instance() directly here
            # Generate unique layer name (legendInterface removed in QGIS 3.x)
            existing_names = [l.name() for l in QgsProject.instance().mapLayers().values()]
            base_name = new_layer_name
            counter = 1
            while new_layer_name in existing_names:
                counter += 1
                new_layer_name = f"{base_name}_{counter}"

            # Create a new memory layer with the same structure and CRS
            new_layer = QgsVectorLayer(
                f"{QgsWkbTypes.displayString(original_layer.wkbType())}?crs={original_layer.crs().authid()}&index=yes",
                new_layer_name,
                "memory"
            )
            provider = new_layer.dataProvider()
            provider.addAttributes(original_layer.fields())
            new_layer.updateFields()

            # Copy selected features
            request = QgsFeatureRequest().setFilterFids(fids)
            new_features = []
            for feature in original_layer.getFeatures(request):
                new_feature = QgsFeature(new_layer.fields())
                new_feature.setGeometry(feature.geometry())
                new_feature.setAttributes(feature.attributes())
                new_features.append(new_feature)
            
            if new_features:
                provider.addFeatures(new_features)
                new_layer.updateExtents()
                QgsProject.instance().addMapLayer(new_layer)
                layers_created_count += 1
            else:
                 QgsMessageLog.logMessage(f"No se copiaron entidades para la capa {new_layer_name}", "AttributeSearch", Qgis.Warning)

        if layers_created_count > 0:
            QMessageBox.information(self, "Éxito", f"Se crearon {layers_created_count} capa(s) con las entidades seleccionadas.")
        else:
            QMessageBox.warning(self, "Advertencia", "No se pudo crear ninguna capa nueva (quizás no se encontraron geometrías válidas).")

    def show_context_menu(self, position):
        """Show context menu for the results table."""
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            return # No menu if nothing selected

        menu = QMenu()
        # Add restart action to context menu as well?
        # menu.addAction(self.restart_search_action)
        # menu.addSeparator()
        menu.addAction(self.zoom_action)
        menu.addAction(self.select_action)
        menu.addAction(self.deselect_action) # Added deselect action
        menu.addAction(self.flash_action)
        menu.addAction(self.attribute_table_action)
        menu.addSeparator()
        menu.addAction(self.export_action)
        menu.addAction(self.create_layer_action)
        
        menu.exec_(self.results_table.viewport().mapToGlobal(position))

    def clear_results(self):
         """Clears the results table and internal data."""
         self.results = []
         self.selected_features_info = []
         self.results_table.setRowCount(0)
         self.update_field_combo() # Clear combo box
         if self.figure is not None:
             self.figure.clear() # Clear chart
             self.canvas.draw()
         self.deselect_all_features(silent=True) # Clear selection on map
         self.clear_rubber_bands() # Clear any temporary highlights
         QgsMessageLog.logMessage("Resultados limpiados.", "AttributeSearch", Qgis.Info)

    # --- Added Handler for Restart Request ---
    def handle_restart_request(self):
        """Clears results and emits signal to switch tab."""
        self.clear_results()
        self.restart_requested.emit()
    # --- End Added Handler ---

