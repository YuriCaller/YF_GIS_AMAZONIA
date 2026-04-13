# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ResultsManager
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
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from qgis.PyQt.QtCore import QObject, pyqtSignal, QVariant, QSettings, QTimer
from qgis.PyQt.QtGui import QColor

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields,
    QgsWkbTypes, QgsFeatureRequest, QgsRectangle, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsVectorFileWriter, QgsSymbol, QgsSingleSymbolRenderer,
    QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer
)
from qgis.gui import QgsRubberBand

class ResultsManager(QObject):
    """Manager for search results."""
    
    resultSelected = pyqtSignal(dict)  # Signal emitted when a result is selected
    resultsHighlighted = pyqtSignal(list)  # Signal emitted when results are highlighted
    statisticsCalculated = pyqtSignal(dict)  # Signal emitted when statistics are calculated
    
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(ResultsManager, self).__init__(parent)
        self.iface = iface
        self.results = []
        self.selected_results = []
        self.rubber_bands = []
        
        # Load settings
        self.load_settings()
    
    def load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        settings.beginGroup("QGISAttributeSearch")
        
        # Highlight settings
        self.highlight_color = QColor(settings.value("highlightColor", "#FF0000"))
        self.highlight_transparency = settings.value("highlightTransparency", 50, type=int)
        self.highlight_duration = settings.value("highlightDuration", 3, type=int)
        
        settings.endGroup()
    
    def set_results(self, results):
        """Set search results."""
        self.results = results
        self.selected_results = []
        self.clear_rubber_bands()
    
    def select_result(self, result):
        """Select a single result."""
        self.selected_results = [result]
        self.resultSelected.emit(result)
    
    def select_results(self, results):
        """Select multiple results."""
        self.selected_results = results
        if results:
            self.resultSelected.emit(results[0])
    
    def zoom_to_results(self, results=None):
        """Zoom to selected results."""
        if results is None:
            results = self.selected_results
        
        if not results:
            return False
        
        # Create combined extent
        combined_extent = None
        
        for result in results:
            layer = result['layer']
            feature_id = result['feature_id']
            
            # Get feature
            request = QgsFeatureRequest().setFilterFid(feature_id)
            features = list(layer.getFeatures(request))
            
            if features:
                feature = features[0]
                geometry = feature.geometry()
                
                if geometry:
                    # Get feature extent
                    extent = geometry.boundingBox()
                    
                    # Transform extent to project CRS if needed
                    if layer.crs() != QgsProject.instance().crs():
                        transform = QgsCoordinateTransform(
                            layer.crs(),
                            QgsProject.instance().crs(),
                            QgsProject.instance()
                        )
                        extent = transform.transformBoundingBox(extent)
                    
                    # Combine extents
                    if combined_extent is None:
                        combined_extent = extent
                    else:
                        combined_extent.combineExtentWith(extent)
        
        # Zoom to combined extent
        if combined_extent:
            # Add buffer for better visibility
            combined_extent.grow(combined_extent.width() * 0.1)
            
            # Zoom to extent
            self.iface.mapCanvas().setExtent(combined_extent)
            self.iface.mapCanvas().refresh()
            
            return True
        
        return False
    
    def highlight_results(self, results=None, duration=None):
        """Highlight results on the map."""
        if results is None:
            results = self.selected_results
        
        if not results:
            return False
        
        # Clear existing rubber bands
        self.clear_rubber_bands()
        
        # Create rubber bands for selected features
        canvas = self.iface.mapCanvas()
        
        for result in results:
            layer = result['layer']
            feature_id = result['feature_id']
            
            # Get feature
            request = QgsFeatureRequest().setFilterFid(feature_id)
            features = list(layer.getFeatures(request))
            
            if features:
                feature = features[0]
                geometry = feature.geometry()
                
                if geometry:
                    # Create rubber band based on geometry type
                    if layer.geometryType() == QgsWkbTypes.PointGeometry:
                        rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
                        rubber_band.setIcon(QgsRubberBand.ICON_CIRCLE)
                        rubber_band.setIconSize(10)
                    elif layer.geometryType() == QgsWkbTypes.LineGeometry:
                        rubber_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
                        rubber_band.setWidth(2)
                    else:
                        rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
                    
                    # Set color with transparency
                    color = QColor(self.highlight_color)
                    color.setAlpha(255 * (100 - self.highlight_transparency) // 100)
                    rubber_band.setColor(color)
                    
                    # Add geometry to rubber band
                    if layer.crs() != canvas.mapSettings().destinationCrs():
                        # Transform geometry if needed
                        transform = QgsCoordinateTransform(
                            layer.crs(),
                            canvas.mapSettings().destinationCrs(),
                            QgsProject.instance()
                        )
                        geometry.transform(transform)
                    
                    rubber_band.setToGeometry(geometry, None)
                    
                    # Add to list
                    self.rubber_bands.append(rubber_band)
        
        # Refresh map canvas
        canvas.refresh()
        
        # Emit signal
        self.resultsHighlighted.emit(results)
        
        # Schedule removal of rubber bands after duration
        if duration is None:
            duration = self.highlight_duration
        
        if duration > 0:
            QTimer.singleShot(duration * 1000, self.clear_rubber_bands)
        
        return True
    
    def clear_rubber_bands(self):
        """Clear all rubber bands."""
        for rubber_band in self.rubber_bands:
            self.iface.mapCanvas().scene().removeItem(rubber_band)
        
        self.rubber_bands = []
    
    def select_features_in_qgis(self, results=None):
        """Select features in QGIS."""
        if results is None:
            results = self.selected_results
        
        if not results:
            return False
        
        # Group features by layer
        features_by_layer = {}
        for result in results:
            layer = result['layer']
            feature_id = result['feature_id']
            
            if layer not in features_by_layer:
                features_by_layer[layer] = []
            
            features_by_layer[layer].append(feature_id)
        
        # Select features in each layer
        for layer, feature_ids in features_by_layer.items():
            layer.selectByIds(feature_ids)
        
        # Refresh map canvas
        self.iface.mapCanvas().refresh()
        
        return True
    
    def open_attribute_table(self, result=None):
        """Open attribute table for a result."""
        if result is None and self.selected_results:
            result = self.selected_results[0]
        
        if not result:
            return False
        
        layer = result['layer']
        feature_id = result['feature_id']
        
        # Select feature
        layer.selectByIds([feature_id])
        
        # Open attribute table
        self.iface.showAttributeTable(layer)
        
        return True
    
    def export_results(self, file_path, results=None):
        """Export results to file."""
        if results is None:
            results = self.results
        
        if not results:
            return False
        
        # Determine export format based on file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext == '.csv':
            # Export to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['Capa', 'ID', 'Campo', 'Valor'])
                
                # Write data
                for result in results:
                    writer.writerow([
                        result['layer'].name(),
                        result['feature_id'],
                        result['field_name'],
                        result['field_value']
                    ])
            
            return True
        
        elif ext == '.xlsx':
            # Export to Excel
            df = pd.DataFrame([
                {
                    'Capa': result['layer'].name(),
                    'ID': result['feature_id'],
                    'Campo': result['field_name'],
                    'Valor': result['field_value']
                }
                for result in results
            ])
            
            df.to_excel(file_path, index=False)
            
            return True
        
        elif ext == '.geojson':
            # Export to GeoJSON
            # Group features by layer
            features_by_layer = {}
            for result in results:
                layer = result['layer']
                feature_id = result['feature_id']
                
                if layer not in features_by_layer:
                    features_by_layer[layer] = set()
                
                features_by_layer[layer].add(feature_id)
            
            # Create temporary layer with all features
            temp_layer = QgsVectorLayer("MultiPolygon", "temp", "memory")
            temp_provider = temp_layer.dataProvider()
            
            # Add fields
            temp_provider.addAttributes([
                QgsField("layer_name", QVariant.String),
                QgsField("feature_id", QVariant.Int),
                QgsField("field_name", QVariant.String),
                QgsField("field_value", QVariant.String)
            ])
            temp_layer.updateFields()
            
            # Add features
            for layer, feature_ids in features_by_layer.items():
                for feature_id in feature_ids:
                    # Get feature
                    request = QgsFeatureRequest().setFilterFid(feature_id)
                    features = list(layer.getFeatures(request))
                    
                    if features:
                        feature = features[0]
                        
                        # Create new feature
                        new_feature = QgsFeature()
                        new_feature.setGeometry(feature.geometry())
                        
                        # Find matching results
                        matching_results = [
                            r for r in results
                            if r['layer'] == layer and r['feature_id'] == feature_id
                        ]
                        
                        # Add attributes
                        for result in matching_results:
                            new_feature.setAttributes([
                                layer.name(),
                                feature_id,
                                result['field_name'],
                                result['field_value']
                            ])
                            
                            # Add feature to layer
                            temp_provider.addFeature(new_feature)
            
            # Save layer to GeoJSON
            QgsVectorFileWriter.writeAsVectorFormat(
                temp_layer,
                file_path,
                "UTF-8",
                QgsCoordinateReferenceSystem("EPSG:4326"),
                "GeoJSON"
            )
            
            return True
        
        else:
            return False
    
    def create_layer_from_results(self, layer_name, results=None):
        """Create a new layer from results."""
        if results is None:
            results = self.selected_results
        
        if not results:
            return None
        
        # Group features by geometry type
        features_by_type = {
            QgsWkbTypes.PointGeometry: [],
            QgsWkbTypes.LineGeometry: [],
            QgsWkbTypes.PolygonGeometry: []
        }
        
        for result in results:
            layer = result['layer']
            feature_id = result['feature_id']
            
            # Get feature
            request = QgsFeatureRequest().setFilterFid(feature_id)
            features = list(layer.getFeatures(request))
            
            if features:
                feature = features[0]
                geometry = feature.geometry()
                
                if geometry:
                    # Add to appropriate list
                    if layer.geometryType() == QgsWkbTypes.PointGeometry:
                        features_by_type[QgsWkbTypes.PointGeometry].append((feature, layer, result))
                    elif layer.geometryType() == QgsWkbTypes.LineGeometry:
                        features_by_type[QgsWkbTypes.LineGeometry].append((feature, layer, result))
                    else:
                        features_by_type[QgsWkbTypes.PolygonGeometry].append((feature, layer, result))
        
        # Create layers for each geometry type
        created_layers = []
        
        for geom_type, features in features_by_type.items():
            if not features:
                continue
            
            # Determine geometry type string
            if geom_type == QgsWkbTypes.PointGeometry:
                geom_str = "Point"
                type_name = "Puntos"
            elif geom_type == QgsWkbTypes.LineGeometry:
                geom_str = "LineString"
                type_name = "Líneas"
            else:
                geom_str = "Polygon"
                type_name = "Polígonos"
            
            # Create layer
            new_layer = QgsVectorLayer(
                f"{geom_str}?crs=EPSG:4326",
                f"{layer_name}_{type_name}",
                "memory"
            )
            
            # Add fields
            provider = new_layer.dataProvider()
            provider.addAttributes([
                QgsField("layer_name", QVariant.String),
                QgsField("feature_id", QVariant.Int),
                QgsField("field_name", QVariant.String),
                QgsField("field_value", QVariant.String)
            ])
            new_layer.updateFields()
            
            # Add features
            for feature, source_layer, result in features:
                # Create new feature
                new_feature = QgsFeature()
                
                # Copy geometry
                geometry = feature.geometry()
                
                # Transform geometry if needed
                if source_layer.crs() != new_layer.crs():
                    transform = QgsCoordinateTransform(
                        source_layer.crs(),
                        new_layer.crs(),
                        QgsProject.instance()
                    )
                    geometry.transform(transform)
                
                new_feature.setGeometry(geometry)
                
                # Set attributes
                new_feature.setAttributes([
                    source_layer.name(),
                    feature.id(),
                    result['field_name'],
                    result['field_value']
                ])
                
                # Add feature
                provider.addFeature(new_feature)
            
            # Update layer
            new_layer.updateExtents()
            
            # Add to project
            QgsProject.instance().addMapLayer(new_layer)
            created_layers.append(new_layer)
        
        return created_layers
    
    def calculate_statistics(self, field_name, results=None):
        """Calculate statistics for a field."""
        if results is None:
            results = self.results
        
        if not results:
            return None
        
        # Filter results by field name
        field_results = [r for r in results if r['field_name'] == field_name]
        
        if not field_results:
            return None
        
        # Count values
        value_counts = {}
        for result in field_results:
            value = result['field_value']
            if value in value_counts:
                value_counts[value] += 1
            else:
                value_counts[value] = 1
        
        # Calculate statistics
        stats = {
            'field_name': field_name,
            'count': len(field_results),
            'unique_values': len(value_counts),
            'value_counts': value_counts,
            'most_common': sorted(value_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        }
        
        # Try to calculate numeric statistics
        numeric_values = []
        for value in value_counts.keys():
            try:
                numeric_values.append(float(value))
            except (ValueError, TypeError):
                pass
        
        if numeric_values:
            stats['numeric'] = {
                'min': min(numeric_values),
                'max': max(numeric_values),
                'mean': sum(numeric_values) / len(numeric_values),
                'median': sorted(numeric_values)[len(numeric_values) // 2],
                'std': np.std(numeric_values) if len(numeric_values) > 1 else 0
            }
        
        # Emit signal
        self.statisticsCalculated.emit(stats)
        
        return stats
    
    def generate_chart(self, field_name, chart_type, output_path, results=None):
        """Generate chart for a field."""
        if results is None:
            results = self.results
        
        if not results:
            return False
        
        # Calculate statistics
        stats = self.calculate_statistics(field_name, results)
        
        if not stats:
            return False
        
        # Sort items by count
        sorted_items = sorted(stats['value_counts'].items(), key=lambda x: x[1], reverse=True)
        
        # Limit to top 10 for readability
        if len(sorted_items) > 10:
            sorted_items = sorted_items[:10]
            other_count = sum(stats['value_counts'][k] for k in stats['value_counts'] if k not in [x[0] for x in sorted_items])
            if other_count > 0:
                sorted_items.append(("Otros", other_count))
        
        # Extract labels and values
        labels = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Create chart based on type
        if chart_type == "Barras":
            plt.bar(labels, values)
            plt.xlabel('Valores')
            plt.ylabel('Conteo')
            plt.title(f'Distribución de valores para el campo "{field_name}"')
            plt.xticks(rotation=45, ha='right')
        elif chart_type == "Pastel":
            plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
            plt.axis('equal')
            plt.title(f'Distribución de valores para el campo "{field_name}"')
        elif chart_type == "Líneas":
            plt.plot(labels, values, marker='o')
            plt.xlabel('Valores')
            plt.ylabel('Conteo')
            plt.title(f'Distribución de valores para el campo "{field_name}"')
            plt.xticks(rotation=45, ha='right')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save chart
        plt.savefig(output_path)
        plt.close()
        
        return True
