# -*- coding: utf-8 -*-
"""
YF GIS Amazonia Tools
Suite profesional de herramientas GIS para la Amazonía peruana

Author: Yuri Fabian Caller Córdova (CIP 214377)
Website: https://gis-amazonia.pe
Company: Training Universal Company SAC (TUCSA)
"""


def classFactory(iface):
    """QGIS Plugin entry point."""
    from .core.plugin_manager import YFGISAmazonia
    return YFGISAmazonia(iface)
