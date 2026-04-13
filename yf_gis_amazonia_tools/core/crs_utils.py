# -*- coding: utf-8 -*-
"""
CRS Utilities - Shared coordinate reference system helpers.

Common CRS operations used across multiple tools:
- UTM zone detection from coordinates
- CRS validation for projected systems
- Coordinate transformation helpers
"""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsPointXY,
)


# Standard CRS for Madre de Dios
CRS_WGS84_UTM19S = QgsCoordinateReferenceSystem("EPSG:32719")
CRS_WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


def is_projected(crs):
    """Check if a CRS is projected (uses meters, not degrees)."""
    if crs is None or not crs.isValid():
        return False
    return not crs.isGeographic()


def get_utm_zone(longitude, latitude):
    """
    Determine the UTM EPSG code from geographic coordinates.

    Returns:
        str: EPSG code like 'EPSG:32719' for UTM Zone 19S
    """
    zone_number = int((longitude + 180) / 6) + 1

    if latitude >= 0:
        epsg = 32600 + zone_number  # Northern hemisphere
    else:
        epsg = 32700 + zone_number  # Southern hemisphere

    return f"EPSG:{epsg}"


def transform_point(point, source_crs, dest_crs):
    """
    Transform a QgsPointXY from one CRS to another.

    Args:
        point: QgsPointXY
        source_crs: QgsCoordinateReferenceSystem
        dest_crs: QgsCoordinateReferenceSystem

    Returns:
        QgsPointXY in the destination CRS
    """
    transform = QgsCoordinateTransform(
        source_crs, dest_crs, QgsProject.instance()
    )
    return transform.transform(point)


def layer_crs_is_valid_for_measurements(layer):
    """
    Check if a layer's CRS is suitable for distance/area measurements.
    Returns (is_valid, message).
    """
    if layer is None:
        return False, "No se proporcionó una capa"

    crs = layer.crs()
    if not crs.isValid():
        return False, "La capa no tiene un CRS válido"

    if crs.isGeographic():
        return False, (
            f"La capa '{layer.name()}' usa CRS geográfico ({crs.authid()}).\n"
            f"Se requiere un CRS proyectado (metros) como UTM.\n"
            f"Sugerencia: reproyectar a {CRS_WGS84_UTM19S.authid()} "
            f"(WGS84 / UTM Zone 19S) para Madre de Dios."
        )

    return True, "OK"
