# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SearchEngine
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
import re
import time
from datetime import datetime

from qgis.PyQt.QtCore import QObject, pyqtSignal, QThread, QVariant, QSettings
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsExpression,
    QgsFeatureRequest, QgsExpressionContext, QgsExpressionContextUtils,
    QgsField, QgsFields, QgsWkbTypes, QgsSpatialIndex, QgsRectangle,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform
)

class SearchWorker(QThread):
    """Worker thread for asynchronous search operations."""
    
    searchCompleted = pyqtSignal(list)
    searchProgress = pyqtSignal(int, int)  # current, total
    searchError = pyqtSignal(str)
    
    def __init__(self, search_params):
        """Constructor."""
        super(SearchWorker, self).__init__()
        self.search_params = search_params
        self.abort_requested = False
    
    def run(self):
        """Run the search operation."""
        try:
            results = []
            
            # Extract search parameters
            layers = self.search_params.get('layers', [])
            search_type = self.search_params.get('search_type', 'simple')
            search_text = self.search_params.get('search_text', '')
            case_sensitive = self.search_params.get('case_sensitive', False)
            whole_word = self.search_params.get('whole_word', False)
            search_all_fields = self.search_params.get('search_all_fields', True)
            selected_field = self.search_params.get('selected_field', '')
            expression_text = self.search_params.get('expression_text', '')
            limit = self.search_params.get('limit', 1000)
            spatial_filter = self.search_params.get('spatial_filter', None)
            
            # Get settings
            settings = QSettings()
            settings.beginGroup("QGISAttributeSearch")
            max_features = settings.value("maxFeatures", 10000, type=int)
            use_spatial_index = settings.value("useSpatialIndex", True, type=bool)
            settings.endGroup()
            
            # Count total layers for progress reporting
            total_layers = len(layers)
            
            # Execute search based on type
            for i, layer in enumerate(layers):
                # Check if abort was requested
                if self.abort_requested:
                    break
                
                # Report progress
                self.searchProgress.emit(i, total_layers)
                
                # Skip non-vector layers
                if not isinstance(layer, QgsVectorLayer):
                    continue
                
                # Apply spatial filter if provided
                if spatial_filter:
                    # Get spatial filter parameters
                    filter_type = spatial_filter.get('type', 'extent')
                    filter_geometry = spatial_filter.get('geometry', None)
                    
                    if filter_geometry:
                        # Create spatial filter
                        if filter_type == 'extent':
                            # Filter by extent
                            extent = filter_geometry.boundingBox()
                            
                            # Transform extent if needed
                            if filter_geometry.crs() != layer.crs():
                                transform = QgsCoordinateTransform(
                                    filter_geometry.crs(),
                                    layer.crs(),
                                    QgsProject.instance()
                                )
                                extent = transform.transformBoundingBox(extent)
                            
                            # Create request with extent
                            request = QgsFeatureRequest().setFilterRect(extent)
                            
                            # Use spatial index if available and enabled
                            if use_spatial_index and layer.hasSpatialIndex():
                                request.setUseExpression(False)
                            
                            # Get features within extent
                            features = list(layer.getFeatures(request))
                        
                        elif filter_type == 'intersects':
                            # Filter by intersection
                            # Transform geometry if needed
                            search_geometry = QgsGeometry(filter_geometry)
                            if filter_geometry.crs() != layer.crs():
                                transform = QgsCoordinateTransform(
                                    filter_geometry.crs(),
                                    layer.crs(),
                                    QgsProject.instance()
                                )
                                search_geometry.transform(transform)
                            
                            # Create request with spatial filter
                            request = QgsFeatureRequest()
                            
                            # Use spatial index if available and enabled
                            if use_spatial_index and layer.hasSpatialIndex():
                                # Get features using spatial index
                                index = QgsSpatialIndex(layer.getFeatures())
                                ids = index.intersects(search_geometry.boundingBox())
                                request.setFilterFids(ids)
                            
                            # Get features
                            features = []
                            for feature in layer.getFeatures(request):
                                # Check for abort
                                if self.abort_requested:
                                    break
                                
                                # Check intersection
                                if feature.hasGeometry() and feature.geometry().intersects(search_geometry):
                                    features.append(feature)
                        
                        elif filter_type == 'contains':
                            # Filter by containment
                            # Transform geometry if needed
                            search_geometry = QgsGeometry(filter_geometry)
                            if filter_geometry.crs() != layer.crs():
                                transform = QgsCoordinateTransform(
                                    filter_geometry.crs(),
                                    layer.crs(),
                                    QgsProject.instance()
                                )
                                search_geometry.transform(transform)
                            
                            # Create request with spatial filter
                            request = QgsFeatureRequest()
                            
                            # Use spatial index if available and enabled
                            if use_spatial_index and layer.hasSpatialIndex():
                                # Get features using spatial index
                                index = QgsSpatialIndex(layer.getFeatures())
                                ids = index.intersects(search_geometry.boundingBox())
                                request.setFilterFids(ids)
                            
                            # Get features
                            features = []
                            for feature in layer.getFeatures(request):
                                # Check for abort
                                if self.abort_requested:
                                    break
                                
                                # Check containment
                                if feature.hasGeometry() and search_geometry.contains(feature.geometry()):
                                    features.append(feature)
                        
                        elif filter_type == 'within':
                            # Filter by within
                            # Transform geometry if needed
                            search_geometry = QgsGeometry(filter_geometry)
                            if filter_geometry.crs() != layer.crs():
                                transform = QgsCoordinateTransform(
                                    filter_geometry.crs(),
                                    layer.crs(),
                                    QgsProject.instance()
                                )
                                search_geometry.transform(transform)
                            
                            # Create request with spatial filter
                            request = QgsFeatureRequest()
                            
                            # Use spatial index if available and enabled
                            if use_spatial_index and layer.hasSpatialIndex():
                                # Get features using spatial index
                                index = QgsSpatialIndex(layer.getFeatures())
                                ids = index.intersects(search_geometry.boundingBox())
                                request.setFilterFids(ids)
                            
                            # Get features
                            features = []
                            for feature in layer.getFeatures(request):
                                # Check for abort
                                if self.abort_requested:
                                    break
                                
                                # Check within
                                if feature.hasGeometry() and feature.geometry().within(search_geometry):
                                    features.append(feature)
                        
                        else:
                            # No valid spatial filter type, use all features
                            features = list(layer.getFeatures())
                    else:
                        # No valid geometry, use all features
                        features = list(layer.getFeatures())
                else:
                    # No spatial filter, use all features
                    features = list(layer.getFeatures())
                
                # Limit features for performance
                if len(features) > max_features:
                    features = features[:max_features]
                
                # Execute search based on type
                if search_type == 'simple':
                    # Simple search
                    if search_all_fields:
                        # Search in all fields
                        layer_results = self.search_in_all_fields(
                            layer,
                            features,
                            search_text,
                            case_sensitive,
                            whole_word
                        )
                    else:
                        # Search in selected field
                        layer_results = self.search_in_field(
                            layer,
                            features,
                            selected_field,
                            search_text,
                            case_sensitive,
                            whole_word
                        )
                else:
                    # Advanced search with expression
                    layer_results = self.search_with_expression(
                        layer,
                        features,
                        expression_text
                    )
                
                # Add results
                results.extend(layer_results)
                
                # Check limit
                if limit != "Sin límite" and len(results) >= int(limit):
                    results = results[:int(limit)]
                    break
            
            # Report completion
            self.searchProgress.emit(total_layers, total_layers)
            
            # Emit results
            self.searchCompleted.emit(results)
        
        except Exception as e:
            self.searchError.emit(str(e))
    
    def abort(self):
        """Abort the search operation."""
        self.abort_requested = True
    
    def search_in_all_fields(self, layer, features, search_text, case_sensitive, whole_word):
        """Search in all fields of the layer."""
        results = []
        
        for feature in features:
            # Check if abort was requested
            if self.abort_requested:
                break
            
            # Find matching field(s)
            matching_fields = []
            for field in layer.fields():
                field_name = field.name()
                
                # Skip geometry fields
                if field.typeName() == "geometry":
                    continue
                
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
        
        return results
    
    def search_in_field(self, layer, features, field_name, search_text, case_sensitive, whole_word):
        """Search in a specific field of the layer."""
        results = []
        
        # Check if field exists in layer
        if field_name not in layer.fields().names():
            return results
        
        for feature in features:
            # Check if abort was requested
            if self.abort_requested:
                break
            
            field_value = str(feature[field_name])
            
            # Check if field matches search text
            match = False
            if whole_word:
                if case_sensitive:
                    if field_value == search_text:
                        match = True
                else:
                    if field_value.lower() == search_text.lower():
                        match = True
            else:
                if case_sensitive:
                    if search_text in field_value:
                        match = True
                else:
                    if search_text.lower() in field_value.lower():
                        match = True
            
            # Add result
            if match:
                results.append({
                    'layer': layer,
                    'feature_id': feature.id(),
                    'feature': feature,
                    'field_name': field_name,
                    'field_value': field_value
                })
        
        return results
    
    def search_with_expression(self, layer, features, expression_text):
        """Search with custom expression."""
        results = []
        
        # Create expression
        expression = QgsExpression(expression_text)
        
        # Check if expression is valid
        if expression.hasParserError():
            self.searchError.emit(f"Error en la expresión: {expression.parserErrorString()}")
            return results
        
        # Create context
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
        
        for feature in features:
            # Check if abort was requested
            if self.abort_requested:
                break
            
            # Evaluate expression
            context.setFeature(feature)
            value = expression.evaluate(context)
            
            # Check if expression evaluates to true
            if value:
                # Add result for each field
                for field_name in layer.fields().names():
                    results.append({
                        'layer': layer,
                        'feature_id': feature.id(),
                        'feature': feature,
                        'field_name': field_name,
                        'field_value': str(feature[field_name])
                    })
                
                # Break after first matching field to avoid duplicates
                break
        
        return results

class SearchEngine(QObject):
    """Engine for advanced attribute search."""
    
    searchStarted = pyqtSignal()
    searchCompleted = pyqtSignal(list)
    searchProgress = pyqtSignal(int, int)  # current, total
    searchError = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Constructor."""
        super(SearchEngine, self).__init__(parent)
        self.worker = None
    
    def search(self, search_params):
        """Execute search with the given parameters."""
        # Check if a search is already running
        if self.worker and self.worker.isRunning():
            self.worker.abort()
            self.worker.wait()
        
        # Create worker thread
        self.worker = SearchWorker(search_params)
        
        # Connect signals
        self.worker.searchCompleted.connect(self.on_search_completed)
        self.worker.searchProgress.connect(self.searchProgress)
        self.worker.searchError.connect(self.searchError)
        
        # Start search
        self.searchStarted.emit()
        self.worker.start()
    
    def abort(self):
        """Abort the current search operation."""
        if self.worker and self.worker.isRunning():
            self.worker.abort()
    
    def on_search_completed(self, results):
        """Handle search completion."""
        self.searchCompleted.emit(results)
