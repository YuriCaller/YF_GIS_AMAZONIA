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

import logging
import os
from qgis.PyQt.QtGui import QDesktopServices as __QDS
from qgis.PyQt.QtCore import QUrl as __QURL
import sys
import subprocess
from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsMessageLog, Qgis, QgsProject
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
        
        # Exportar usando QgsVectorFileWriter (API no deprecada, compatible con PyQt5 y PyQt6)
        error = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            output_file,
            QgsProject.instance().transformContext(),
            options
        )

        # writeAsVectorFormatV3 retorna una tupla (WriterError, errorMessage, ...)
        error_code = error[0] if isinstance(error, tuple) else error
        error_message = error[1] if isinstance(error, tuple) and len(error) > 1 else ""

        if error_code != QgsVectorFileWriter.WriterError.NoError:
            raise Exception(f"Error al exportar a XLSX: {error_message}")
        
        QgsMessageLog.logMessage(
            f"Exportación exitosa a: {output_file}", 
            "YF Tools Plus", 
            Qgis.MessageLevel.Success
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
                Qgis.MessageLevel.Critical
            )
            raise
    
    def open_file_in_os(self, file_path):
        """Abre el archivo con la app predeterminada. En Windows usa
        os.startfile (el más fiable para lanzar Excel); si falla, cae a
        QDesktopServices y luego a subprocess."""
        import os as _os, sys as _sys, subprocess as _sp
        abspath = _os.path.abspath(file_path)
        # 1) Windows: os.startfile
        if _os.name == 'nt':
            try:
                _os.startfile(abspath)  # nosec B606 - apertura de archivo propio exportado por el usuario
                return True
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)
        # 2) QDesktopServices (multiplataforma)
        try:
            from qgis.PyQt.QtGui import QDesktopServices
            from qgis.PyQt.QtCore import QUrl
            if QDesktopServices.openUrl(QUrl.fromLocalFile(abspath)):
                return True
        except Exception:
            logging.getLogger(__name__).debug("suppressed", exc_info=True)
        # 3) subprocess por plataforma
        QgsMessageLog.logMessage(
            "No se pudo abrir automaticamente: {}".format(abspath),
            "YF Tools Plus", Qgis.MessageLevel.Warning)
        return False

