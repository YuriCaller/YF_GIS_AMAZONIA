# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ExcelExporter
                                 A QGIS plugin
 Módulo para exportar capas vectoriales a Excel
                             -------------------
        begin                : 2025-04-21
        copyright            : (C) 2025 by Yuri Caller
        email                : yuricaller@gmail.com
 ***************************************************************************/
"""

import os
import sys
import subprocess
from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsMessageLog, Qgis
from qgis.PyQt.QtWidgets import QMessageBox


class ExcelExporter:
    """Clase para exportar capas vectoriales a Excel"""
    
    def __init__(self):
        """Constructor."""
        pass
    
    def export_to_excel(self, layer, output_file, open_file=True):
        """
        Exporta la tabla de atributos de una capa vectorial a un archivo XLSX.
        
        :param layer: Capa vectorial a exportar
        :type layer: QgsVectorLayer
        
        :param output_file: Ruta del archivo XLSX de salida
        :type output_file: str
        
        :param open_file: Si se debe abrir el archivo después de exportar
        :type open_file: bool
        
        :raises Exception: Si ocurre un error durante la exportación
        """
        
        if not layer or not isinstance(layer, QgsVectorLayer):
            raise Exception("La capa proporcionada no es válida")
        
        # Si no se proporciona ruta de salida, usar carpeta de usuario
        if not output_file:
            layer_name = layer.name().replace(" ", "_")
            output_dir = os.path.expanduser("~")
            output_file = os.path.join(output_dir, f"{layer_name}_atributos.xlsx")
        
        # Asegurar que tiene extensión .xlsx
        if not output_file.endswith('.xlsx'):
            output_file += '.xlsx'
        
        # Opciones de exportación: solo atributos (sin geometría)
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "XLSX"
        options.onlySelected = False  # Exportar todos los elementos
        options.attributes = list(range(len(layer.fields())))  # Exportar todos los campos
        
        # Exportar usando QgsVectorFileWriter
        error = QgsVectorFileWriter.writeAsVectorFormat(
            layer,
            output_file,
            options
        )
        
        if error[0] != QgsVectorFileWriter.NoError:
            raise Exception(f"Error al exportar a XLSX: {error[1]}")
        
        QgsMessageLog.logMessage(
            f"Exportación exitosa a: {output_file}", 
            "YF Tools Plus", 
            Qgis.Success
        )
        
        # Abrir archivo si se solicita
        if open_file:
            self.open_file_in_os(output_file)
    
    def quick_export(self, layer):
        """
        Exportación rápida (un clic) de una capa a Excel.
        Guarda en la carpeta del usuario y abre automáticamente.
        
        :param layer: Capa vectorial a exportar
        :type layer: QgsVectorLayer
        """
        try:
            layer_name = layer.name().replace(" ", "_")
            output_dir = os.path.expanduser("~")
            output_file = os.path.join(output_dir, f"{layer_name}_atributos.xlsx")
            
            self.export_to_excel(layer, output_file, open_file=True)
            
            # Mensaje de éxito se maneja en export_to_excel
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error en exportación rápida: {str(e)}", 
                "YF Tools Plus", 
                Qgis.Critical
            )
            raise
    
    def open_file_in_os(self, file_path):
        """
        Abre el archivo especificado usando la aplicación predeterminada del sistema operativo.
        
        :param file_path: Ruta del archivo a abrir
        :type file_path: str
        """
        try:
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(('open', file_path))
            else:  # Linux/other Unix-like
                subprocess.call(('xdg-open', file_path))
                
            QgsMessageLog.logMessage(
                f"Archivo abierto: {file_path}", 
                "YF Tools Plus", 
                Qgis.Info
            )
        except Exception as e:
            QgsMessageLog.logMessage(
                f"No se pudo abrir el archivo automáticamente: {str(e)}", 
                "YF Tools Plus", 
                Qgis.Warning
            )