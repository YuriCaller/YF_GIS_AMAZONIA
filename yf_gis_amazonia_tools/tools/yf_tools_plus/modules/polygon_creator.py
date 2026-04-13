# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PolygonCreator
                                 A QGIS plugin
 Herramientas para generar capas a partir de archivos Excel
                             -------------------
        begin                : 2025-04-21
        copyright            : (C) 2025 by Yuri Caller
        email                : yuricaller@gmail.com
 ***************************************************************************/
"""

import os
import csv
from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsProject,
    QgsSimpleLineSymbolLayer, QgsSingleSymbolRenderer, QgsFillSymbol,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings, 
    QgsVectorLayerSimpleLabeling, QgsCoordinateReferenceSystem,
    QgsMessageLog, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor, QFont

class PolygonCreator:
    """Clase para crear polígonos a partir de archivos CSV"""
    
    def __init__(self):
        """Constructor."""
        pass
    
    def get_csv_fields(self, csv_path):
        """
        Obtiene los nombres de los campos (columnas) de un archivo CSV
        
        :param csv_path: Ruta al archivo CSV
        :type csv_path: str
        
        :returns: Lista de nombres de campos
        :rtype: list
        """
        try:
            if not os.path.exists(csv_path):
                QgsMessageLog.logMessage(
                    f"El archivo CSV no existe: {csv_path}", 
                    "YF Tools Plus", 
                    Qgis.Critical
                )
                return []
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                return headers
                
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error al leer campos del CSV: {str(e)}", 
                "YF Tools Plus", 
                Qgis.Warning
            )
            return []
        
    def create_polygon(self, csv_path, field_x, field_y, crs, style_params=None):
        """
        Crea un polígono a partir de coordenadas en un archivo CSV
        
        :param csv_path: Ruta al archivo CSV
        :type csv_path: str
        
        :param field_x: Nombre del campo que contiene la coordenada X
        :type field_x: str
        
        :param field_y: Nombre del campo que contiene la coordenada Y
        :type field_y: str
        
        :param crs: Sistema de referencia de coordenadas (string como 'EPSG:32719')
        :type crs: str
        
        :param style_params: Parámetros de estilo para el polígono
        :type style_params: dict
        
        :returns: Capa de polígono creada
        :rtype: QgsVectorLayer or None
        """
        try:
            QgsMessageLog.logMessage(
                f"========== INICIANDO CREACIÓN DE POLÍGONO ==========", 
                "YF Tools Plus", 
                Qgis.Info
            )
            QgsMessageLog.logMessage(
                f"Archivo CSV: {csv_path}", 
                "YF Tools Plus", 
                Qgis.Info
            )
            QgsMessageLog.logMessage(
                f"Campo X: '{field_x}', Campo Y: '{field_y}'", 
                "YF Tools Plus", 
                Qgis.Info
            )
            QgsMessageLog.logMessage(
                f"CRS: {crs}", 
                "YF Tools Plus", 
                Qgis.Info
            )
            
            # Verificar que el archivo CSV existe
            if not os.path.exists(csv_path):
                QgsMessageLog.logMessage(
                    f"El archivo CSV no existe: {csv_path}", 
                    "YF Tools Plus", 
                    Qgis.Critical
                )
                return None
            
            # Configurar parámetros de estilo predeterminados
            if style_params is None:
                style_params = {
                    'polygon_color': '#ffffff',
                    'border_color': '#ff340b',
                    'border_width': '0.26',
                    'label_font': 'Arial',
                    'label_size': '9',
                    'label_color': '#ff340b'
                }
            
            # Verificar campos en el CSV
            available_fields = self.get_csv_fields(csv_path)
            QgsMessageLog.logMessage(
                f"Campos disponibles en CSV: {available_fields}", 
                "YF Tools Plus", 
                Qgis.Info
            )
            
            if field_x not in available_fields:
                QgsMessageLog.logMessage(
                    f"El campo X '{field_x}' no existe en el CSV. Campos disponibles: {available_fields}", 
                    "YF Tools Plus", 
                    Qgis.Critical
                )
                return None
                
            if field_y not in available_fields:
                QgsMessageLog.logMessage(
                    f"El campo Y '{field_y}' no existe en el CSV. Campos disponibles: {available_fields}", 
                    "YF Tools Plus", 
                    Qgis.Critical
                )
                return None
            
            # Crear objeto CRS
            if isinstance(crs, str):
                crs_obj = QgsCoordinateReferenceSystem(crs)
            else:
                crs_obj = crs
            
            if not crs_obj.isValid():
                QgsMessageLog.logMessage(
                    f"El CRS '{crs}' no es válido", 
                    "YF Tools Plus", 
                    Qgis.Critical
                )
                return None
            
            # Leer puntos directamente del CSV
            points = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                row_count = 0
                for row in reader:
                    row_count += 1
                    try:
                        x = float(row[field_x])
                        y = float(row[field_y])
                        points.append(QgsPointXY(x, y))
                        QgsMessageLog.logMessage(
                            f"Punto {row_count}: X={x}, Y={y}", 
                            "YF Tools Plus", 
                            Qgis.Info
                        )
                    except (ValueError, KeyError) as e:
                        QgsMessageLog.logMessage(
                            f"Error al leer fila {row_count}: {str(e)}", 
                            "YF Tools Plus", 
                            Qgis.Warning
                        )
                        continue
            
            # Verificar que hay suficientes puntos
            if len(points) < 3:
                QgsMessageLog.logMessage(
                    f"Se necesitan al menos 3 puntos para crear un polígono. Solo se encontraron {len(points)} puntos válidos.", 
                    "YF Tools Plus", 
                    Qgis.Critical
                )
                return None
            
            QgsMessageLog.logMessage(
                f"Se cargaron {len(points)} puntos correctamente", 
                "YF Tools Plus", 
                Qgis.Success
            )
            
            # Crear capa de polígonos en memoria
            polygon_layer = QgsVectorLayer(
                f"Polygon?crs={crs_obj.authid()}", 
                "Polígono", 
                "memory"
            )
            
            if not polygon_layer.isValid():
                QgsMessageLog.logMessage(
                    "Error al crear la capa de polígonos en memoria", 
                    "YF Tools Plus", 
                    Qgis.Critical
                )
                return None
            
            provider = polygon_layer.dataProvider()
            
            # Añadir campos
            provider.addAttributes([
                QgsField("ID", QVariant.Int),
                QgsField("AREA", QVariant.Double),
                QgsField("PERIMETRO", QVariant.Double)
            ])
            polygon_layer.updateFields()
            
            # Crear geometría del polígono
            polygon = QgsGeometry.fromPolygonXY([points])
            
            if polygon.isEmpty():
                QgsMessageLog.logMessage(
                    "La geometría del polígono está vacía", 
                    "YF Tools Plus", 
                    Qgis.Critical
                )
                return None
            
            # Crear feature
            feature = QgsFeature(polygon_layer.fields())
            feature.setGeometry(polygon)
            
            # Calcular área y perímetro
            area = polygon.area() / 10000  # Convertir a hectáreas
            perimeter = polygon.length()  # Perímetro en metros
            
            QgsMessageLog.logMessage(
                f"Polígono creado - Área: {area:.4f} Ha, Perímetro: {perimeter:.2f} m", 
                "YF Tools Plus", 
                Qgis.Success
            )
            
            # Añadir atributos
            feature.setAttributes([1, round(area, 4), round(perimeter, 2)])
            
            # Añadir feature a la capa
            provider.addFeatures([feature])
            polygon_layer.updateExtents()
            
            # Aplicar simbología
            symbol = QgsFillSymbol.createSimple({
                'color': style_params.get('polygon_color', '#ffffff'),
                'color_border': style_params.get('border_color', '#ff340b'),
                'width_border': style_params.get('border_width', '0.26'),
                'style': 'solid',
                'style_border': 'solid'
            })
            polygon_layer.renderer().setSymbol(symbol)
            
            # Aplicar etiquetas
            label_settings = QgsPalLayerSettings()
            label_settings.fieldName = (
                "'PARCELA GEOREFERENCIADA' || '\\n' || "
                "'AREA : ' || round(\"AREA\", 4) || ' Ha.' || '\\n' || "
                "'PERIMETRO : ' || round(\"PERIMETRO\", 2) || ' m.'"
            )
            label_settings.isExpression = True
            
            text_format = QgsTextFormat()
            text_format.setColor(QColor(style_params.get('label_color', '#ff340b')))
            text_format.setSize(float(style_params.get('label_size', '9')))
            text_format.setFont(QFont(
                style_params.get('label_font', 'Arial'), 
                int(style_params.get('label_size', '9')), 
                QFont.Bold
            ))
            
            buffer_settings = QgsTextBufferSettings()
            buffer_settings.setEnabled(True)
            buffer_settings.setSize(1.0)
            buffer_settings.setColor(QColor("white"))
            text_format.setBuffer(buffer_settings)
            
            label_settings.setFormat(text_format)
            
            # Compatibilidad con QGIS 3.x para placement
            try:
                # Para QGIS 3.16+
                label_settings.placement = Qgis.LabelPlacement.OverPoint
            except (AttributeError):
                # Para versiones anteriores de QGIS 3.x
                try:
                    label_settings.placement = QgsPalLayerSettings.Placement.OverPoint
                except:
                    # Fallback para versiones muy antiguas
                    label_settings.placement = 0  # OverPoint
            
            label_settings.centroidWhole = True
            
            polygon_layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
            polygon_layer.setLabelsEnabled(True)
            
            # Añadir al proyecto
            QgsProject.instance().addMapLayer(polygon_layer)
            polygon_layer.triggerRepaint()
            
            QgsMessageLog.logMessage(
                "✓ Polígono añadido al proyecto exitosamente", 
                "YF Tools Plus", 
                Qgis.Success
            )
            
            return polygon_layer
            
        except Exception as e:
            import traceback
            error_msg = f"Error al crear polígono: {str(e)}\n{traceback.format_exc()}"
            QgsMessageLog.logMessage(error_msg, "YF Tools Plus", Qgis.Critical)
            return None