# -*- coding: utf-8 -*-
"""
/***************************************************************************
 LayerUtils
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
from qgis.PyQt.QtCore import QObject, pyqtSignal, QVariant
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields,
    QgsWkbTypes, QgsFeatureRequest, QgsRectangle, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsVectorFileWriter, QgsSymbol, QgsSingleSymbolRenderer,
    QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer
)

class LayerUtils(QObject):
    """Utilities for layer operations."""
    
    layerCreated = pyqtSignal(QgsVectorLayer)  # Signal emitted when a layer is created
    
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(LayerUtils, self).__init__(parent)
        self.iface = iface
    
    def get_vector_layers(self):
        """Get all vector layers in the project."""
        layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                layers.append(layer)
        return layers
    
    def get_layer_by_name(self, name):
        """Get layer by name."""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == name:
                return layer
        return None
    
    def get_layer_fields(self, layer):
        """Get fields of a layer."""
        if not isinstance(layer, QgsVectorLayer):
            return []
        
        return [field.name() for field in layer.fields()]
    
    def get_field_values(self, layer, field_name, limit=100):
        """Get unique values of a field."""
        if not isinstance(layer, QgsVectorLayer):
            return []
        
        if field_name not in self.get_layer_fields(layer):
            return []
        
        values = set()
        for feature in layer.getFeatures():
            values.add(str(feature[field_name]))
            if len(values) >= limit:
                break
        
        return sorted(list(values))
    
    def create_layer_from_features(self, name, features, crs=None, fields=None):
        """Create a new layer from features."""
        if not features:
            return None
        
        # Determine geometry type from first feature
        first_feature = features[0]
        geometry = first_feature.geometry()
        
        if not geometry:
            return None
        
        if geometry.type() == QgsWkbTypes.PointGeometry:
            geom_str = "Point"
        elif geometry.type() == QgsWkbTypes.LineGeometry:
            geom_str = "LineString"
        else:
            geom_str = "Polygon"
        
        # Create layer
        if crs is None:
            crs = QgsProject.instance().crs()
        
        new_layer = QgsVectorLayer(
            f"{geom_str}?crs={crs.authid()}",
            name,
            "memory"
        )
        
        # Add fields
        provider = new_layer.dataProvider()
        
        if fields:
            provider.addAttributes(fields)
        else:
            # Copy fields from first feature
            provider.addAttributes(first_feature.fields())
        
        new_layer.updateFields()
        
        # Add features
        provider.addFeatures(features)
        
        # Update layer
        new_layer.updateExtents()
        
        # Add to project
        QgsProject.instance().addMapLayer(new_layer)
        
        # Emit signal
        self.layerCreated.emit(new_layer)
        
        return new_layer
    
    def create_buffer_layer(self, layer, distance, segments=5, name=None):
        """Create a buffer layer from a vector layer."""
        if not isinstance(layer, QgsVectorLayer):
            return None
        
        if name is None:
            name = f"{layer.name()}_buffer_{distance}"
        
        # Create fields
        fields = QgsFields()
        fields.append(QgsField("original_id", QVariant.Int))
        fields.append(QgsField("buffer_distance", QVariant.Double))
        
        # Create features
        features = []
        
        for feature in layer.getFeatures():
            geometry = feature.geometry()
            
            if geometry:
                # Create buffer
                buffer_geometry = geometry.buffer(distance, segments)
                
                # Create feature
                new_feature = QgsFeature(fields)
                new_feature.setGeometry(buffer_geometry)
                new_feature.setAttributes([feature.id(), distance])
                
                features.append(new_feature)
        
        # Create layer
        buffer_layer = self.create_layer_from_features(
            name,
            features,
            layer.crs(),
            fields
        )
        
        return buffer_layer
    
    def create_intersection_layer(self, layer1, layer2, name=None):
        """Create an intersection layer from two vector layers."""
        if not isinstance(layer1, QgsVectorLayer) or not isinstance(layer2, QgsVectorLayer):
            return None
        
        if name is None:
            name = f"{layer1.name()}_intersection_{layer2.name()}"
        
        # Create fields
        fields = QgsFields()
        fields.append(QgsField("layer1_id", QVariant.Int))
        fields.append(QgsField("layer2_id", QVariant.Int))
        
        # Create features
        features = []
        
        # Transform geometries if needed
        transform = None
        if layer1.crs() != layer2.crs():
            transform = QgsCoordinateTransform(
                layer1.crs(),
                layer2.crs(),
                QgsProject.instance()
            )
        
        for feature1 in layer1.getFeatures():
            geometry1 = feature1.geometry()
            
            if not geometry1:
                continue
            
            # Transform geometry if needed
            if transform:
                geometry1 = QgsGeometry(geometry1)
                geometry1.transform(transform)
            
            for feature2 in layer2.getFeatures():
                geometry2 = feature2.geometry()
                
                if not geometry2:
                    continue
                
                # Check intersection
                if geometry1.intersects(geometry2):
                    # Create intersection
                    intersection = geometry1.intersection(geometry2)
                    
                    # Create feature
                    new_feature = QgsFeature(fields)
                    new_feature.setGeometry(intersection)
                    new_feature.setAttributes([feature1.id(), feature2.id()])
                    
                    features.append(new_feature)
        
        # Create layer
        intersection_layer = self.create_layer_from_features(
            name,
            features,
            layer2.crs(),
            fields
        )
        
        return intersection_layer
    
    def create_difference_layer(self, layer1, layer2, name=None):
        """Create a difference layer from two vector layers."""
        if not isinstance(layer1, QgsVectorLayer) or not isinstance(layer2, QgsVectorLayer):
            return None
        
        if name is None:
            name = f"{layer1.name()}_difference_{layer2.name()}"
        
        # Create fields
        fields = QgsFields()
        fields.append(QgsField("original_id", QVariant.Int))
        
        # Create features
        features = []
        
        # Transform geometries if needed
        transform = None
        if layer1.crs() != layer2.crs():
            transform = QgsCoordinateTransform(
                layer1.crs(),
                layer2.crs(),
                QgsProject.instance()
            )
        
        for feature1 in layer1.getFeatures():
            geometry1 = feature1.geometry()
            
            if not geometry1:
                continue
            
            # Transform geometry if needed
            if transform:
                geometry1 = QgsGeometry(geometry1)
                geometry1.transform(transform)
            
            # Create difference with all features in layer2
            difference = QgsGeometry(geometry1)
            
            for feature2 in layer2.getFeatures():
                geometry2 = feature2.geometry()
                
                if not geometry2:
                    continue
                
                # Update difference
                if difference.intersects(geometry2):
                    difference = difference.difference(geometry2)
            
            # Create feature
            new_feature = QgsFeature(fields)
            new_feature.setGeometry(difference)
            new_feature.setAttributes([feature1.id()])
            
            features.append(new_feature)
        
        # Create layer
        difference_layer = self.create_layer_from_features(
            name,
            features,
            layer2.crs(),
            fields
        )
        
        return difference_layer
    
    def create_union_layer(self, layer1, layer2, name=None):
        """Create a union layer from two vector layers."""
        if not isinstance(layer1, QgsVectorLayer) or not isinstance(layer2, QgsVectorLayer):
            return None
        
        if name is None:
            name = f"{layer1.name()}_union_{layer2.name()}"
        
        # Create fields
        fields = QgsFields()
        fields.append(QgsField("layer1_id", QVariant.Int))
        fields.append(QgsField("layer2_id", QVariant.Int))
        
        # Create features
        features = []
        
        # Transform geometries if needed
        transform = None
        if layer1.crs() != layer2.crs():
            transform = QgsCoordinateTransform(
                layer1.crs(),
                layer2.crs(),
                QgsProject.instance()
            )
        
        # Add all features from layer1
        for feature1 in layer1.getFeatures():
            geometry1 = feature1.geometry()
            
            if not geometry1:
                continue
            
            # Transform geometry if needed
            if transform:
                geometry1 = QgsGeometry(geometry1)
                geometry1.transform(transform)
            
            # Create feature
            new_feature = QgsFeature(fields)
            new_feature.setGeometry(geometry1)
            new_feature.setAttributes([feature1.id(), None])
            
            features.append(new_feature)
        
        # Add all features from layer2
        for feature2 in layer2.getFeatures():
            geometry2 = feature2.geometry()
            
            if not geometry2:
                continue
            
            # Create feature
            new_feature = QgsFeature(fields)
            new_feature.setGeometry(geometry2)
            new_feature.setAttributes([None, feature2.id()])
            
            features.append(new_feature)
        
        # Create layer
        union_layer = self.create_layer_from_features(
            name,
            features,
            layer2.crs(),
            fields
        )
        
        return union_layer
    
    def create_centroids_layer(self, layer, name=None):
        """Create a centroids layer from a vector layer."""
        if not isinstance(layer, QgsVectorLayer):
            return None
        
        if name is None:
            name = f"{layer.name()}_centroids"
        
        # Create fields
        fields = QgsFields()
        fields.append(QgsField("original_id", QVariant.Int))
        
        # Create features
        features = []
        
        for feature in layer.getFeatures():
            geometry = feature.geometry()
            
            if geometry:
                # Create centroid
                centroid = geometry.centroid()
                
                # Create feature
                new_feature = QgsFeature(fields)
                new_feature.setGeometry(centroid)
                new_feature.setAttributes([feature.id()])
                
                features.append(new_feature)
        
        # Create layer
        centroids_layer = self.create_layer_from_features(
            name,
            features,
            layer.crs(),
            fields
        )
        
        return centroids_layer
    
    def export_layer(self, layer, file_path):
        """Export layer to file."""
        if not isinstance(layer, QgsVectorLayer):
            return False
        
        # Determine export format based on file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Map extension to driver name
        driver_map = {
            '.shp': 'ESRI Shapefile',
            '.geojson': 'GeoJSON',
            '.kml': 'KML',
            '.gpkg': 'GPKG',
            '.gml': 'GML',
            '.csv': 'CSV'
        }
        
        if ext not in driver_map:
            return False
        
        # Export layer
        QgsVectorFileWriter.writeAsVectorFormat(
            layer,
            file_path,
            'UTF-8',
            layer.crs(),
            driver_map[ext]
        )
        
        return True
    
    def style_layer(self, layer, style_type='single', field=None, color_ramp=None):
        """Apply style to layer."""
        if not isinstance(layer, QgsVectorLayer):
            return False
        
        if style_type == 'single':
            # Create symbol based on geometry type
            if layer.geometryType() == QgsWkbTypes.PointGeometry:
                symbol = QgsMarkerSymbol.createSimple({
                    'name': 'circle',
                    'color': '255,0,0,255',
                    'size': '2'
                })
            elif layer.geometryType() == QgsWkbTypes.LineGeometry:
                symbol = QgsLineSymbol.createSimple({
                    'color': '0,0,255,255',
                    'width': '0.5'
                })
            else:
                symbol = QgsFillSymbol.createSimple({
                    'color': '0,255,0,128',
                    'outline_color': '0,0,0,255',
                    'outline_width': '0.5'
                })
            
            # Apply symbol
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            
            return True
        
        elif style_type == 'categorized' and field:
            # Get unique values
            values = self.get_field_values(layer, field)
            
            # Create categories
            categories = []
            
            for i, value in enumerate(values):
                # Create symbol based on geometry type
                if layer.geometryType() == QgsWkbTypes.PointGeometry:
                    symbol = QgsMarkerSymbol.createSimple({
                        'name': 'circle',
                        'color': f'{i*30 % 255},{i*50 % 255},{i*70 % 255},255',
                        'size': '2'
                    })
                elif layer.geometryType() == QgsWkbTypes.LineGeometry:
                    symbol = QgsLineSymbol.createSimple({
                        'color': f'{i*30 % 255},{i*50 % 255},{i*70 % 255},255',
                        'width': '0.5'
                    })
                else:
                    symbol = QgsFillSymbol.createSimple({
                        'color': f'{i*30 % 255},{i*50 % 255},{i*70 % 255},128',
                        'outline_color': '0,0,0,255',
                        'outline_width': '0.5'
                    })
                
                # Create category
                category = QgsRendererCategory(value, symbol, value)
                categories.append(category)
            
            # Apply categories
            renderer = QgsCategorizedSymbolRenderer(field, categories)
            layer.setRenderer(renderer)
            
            return True
        
        return False
