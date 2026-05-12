# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ExcelToCSV
                                 A QGIS plugin
 Herramientas para generar capas a partir de archivos Excel
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
import pandas as pd
from qgis.core import QgsMessageLog, Qgis

class ExcelToCsv:
    """Clase para convertir archivos Excel a CSV"""
    
    def __init__(self):
        """Constructor."""
        pass
        
    def convert(self, excel_path, csv_path, encoding='UTF-8'):
        """
        Convierte un archivo Excel a CSV
        
        :param excel_path: Ruta al archivo Excel
        :type excel_path: str
        
        :param csv_path: Ruta donde guardar el archivo CSV
        :type csv_path: str
        
        :param encoding: Codificación del archivo CSV
        :type encoding: str
        
        :returns: True si la conversión fue exitosa, False en caso contrario
        :rtype: bool
        """
        try:
            # Verificar que el archivo Excel existe
            if not os.path.exists(excel_path):
                QgsMessageLog.logMessage(f"El archivo Excel no existe: {excel_path}", "YF Tools Plus", Qgis.Critical)
                return False
            
            # Leer el archivo de Excel
            df = pd.read_excel(excel_path)
            
            # Guardar como CSV
            df.to_csv(csv_path, index=False, encoding=encoding)
            
            # Verificar que el archivo CSV se creó correctamente
            if not os.path.exists(csv_path):
                QgsMessageLog.logMessage(f"No se pudo crear el archivo CSV: {csv_path}", "YF Tools Plus", Qgis.Critical)
                return False
                
            return True
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error al convertir Excel a CSV: {str(e)}", "YF Tools Plus", Qgis.Critical)
            return False
