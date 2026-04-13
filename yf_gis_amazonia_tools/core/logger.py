# -*- coding: utf-8 -*-
"""
Logger - Unified logging for all YF GIS Amazonia tools.

Uses QGIS message log so messages appear in View → Log Messages.
"""

from qgis.core import QgsMessageLog, Qgis

TAG = "YF GIS Amazonia"


def log_info(message):
    """Log an informational message."""
    QgsMessageLog.logMessage(str(message), TAG, Qgis.Info)


def log_warning(message):
    """Log a warning message."""
    QgsMessageLog.logMessage(str(message), TAG, Qgis.Warning)


def log_error(message):
    """Log an error message."""
    QgsMessageLog.logMessage(str(message), TAG, Qgis.Critical)
