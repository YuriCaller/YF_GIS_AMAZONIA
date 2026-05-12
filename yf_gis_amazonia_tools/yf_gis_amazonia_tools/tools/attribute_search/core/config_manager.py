# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ConfigManager
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
from qgis.PyQt.QtCore import QObject, QSettings, QVariant

class ConfigManager(QObject):
    """Manager for plugin configuration."""
    
    def __init__(self, parent=None):
        """Constructor."""
        super(ConfigManager, self).__init__(parent)
        self.settings_prefix = "QGISAttributeSearch"
    
    def get_setting(self, key, default=None, setting_type=None):
        """Get setting value."""
        settings = QSettings()
        settings.beginGroup(self.settings_prefix)
        
        value = settings.value(key, default, type=setting_type)
        
        settings.endGroup()
        
        return value
    
    def set_setting(self, key, value):
        """Set setting value."""
        settings = QSettings()
        settings.beginGroup(self.settings_prefix)
        
        settings.setValue(key, value)
        
        settings.endGroup()
    
    def remove_setting(self, key):
        """Remove setting."""
        settings = QSettings()
        settings.beginGroup(self.settings_prefix)
        
        settings.remove(key)
        
        settings.endGroup()
    
    def clear_settings(self):
        """Clear all settings."""
        settings = QSettings()
        settings.beginGroup(self.settings_prefix)
        
        settings.remove("")
        
        settings.endGroup()
    
    def get_all_settings(self):
        """Get all settings as dictionary."""
        settings = QSettings()
        settings.beginGroup(self.settings_prefix)
        
        keys = settings.childKeys()
        result = {}
        
        for key in keys:
            result[key] = settings.value(key)
        
        settings.endGroup()
        
        return result
    
    def load_default_settings(self):
        """Load default settings."""
        # General settings
        self.set_setting("defaultLimit", "1000")
        self.set_setting("caseSensitive", False)
        self.set_setting("searchAllFields", True)
        self.set_setting("autoZoom", True)
        self.set_setting("flashResults", True)
        self.set_setting("defaultChartType", "Barras")
        self.set_setting("defaultExportFormat", "CSV")
        
        # Appearance settings
        self.set_setting("alternateRowColors", True)
        self.set_setting("rowHeight", 25)
        self.set_setting("fontSize", 10)
        self.set_setting("highlightColor", "#FF0000")
        self.set_setting("highlightTransparency", 50)
        self.set_setting("highlightDuration", 3)
        
        # Report settings
        self.set_setting("defaultReportFormat", "Word (.docx)")
        self.set_setting("defaultReportTitle", "Reporte de Búsqueda de Atributos")
        self.set_setting("includeMap", True)
        self.set_setting("includeAttributes", True)
        self.set_setting("includeCharts", True)
        self.set_setting("includeMetadata", True)
        
        # Advanced settings
        self.set_setting("maxFeatures", 10000)
        self.set_setting("useSpatialIndex", True)
        self.set_setting("asyncSearch", True)
        self.set_setting("enableLogging", False)
        self.set_setting("logLevel", "INFO")
    
    def save_search_history(self, search_text):
        """Save search text to history."""
        history = self.get_search_history()
        
        # Add to beginning of list
        if search_text in history:
            history.remove(search_text)
        
        history.insert(0, search_text)
        
        # Limit to 20 items
        if len(history) > 20:
            history = history[:20]
        
        # Save history
        self.set_setting("searchHistory", history)
    
    def get_search_history(self):
        """Get search history."""
        return self.get_setting("searchHistory", [], list)
    
    def clear_search_history(self):
        """Clear search history."""
        self.set_setting("searchHistory", [])
    
    def save_layer_field_mapping(self, layer_id, field_name):
        """Save layer-field mapping for quick access."""
        mappings = self.get_setting("layerFieldMappings", {}, dict)
        
        mappings[layer_id] = field_name
        
        self.set_setting("layerFieldMappings", mappings)
    
    def get_layer_field_mapping(self, layer_id):
        """Get field name for layer."""
        mappings = self.get_setting("layerFieldMappings", {}, dict)
        
        return mappings.get(layer_id, "")
    
    def save_custom_expression(self, name, expression):
        """Save custom expression."""
        expressions = self.get_setting("customExpressions", {}, dict)
        
        expressions[name] = expression
        
        self.set_setting("customExpressions", expressions)
    
    def get_custom_expressions(self):
        """Get all custom expressions."""
        return self.get_setting("customExpressions", {}, dict)
    
    def remove_custom_expression(self, name):
        """Remove custom expression."""
        expressions = self.get_setting("customExpressions", {}, dict)
        
        if name in expressions:
            del expressions[name]
            self.set_setting("customExpressions", expressions)
            return True
        
        return False
