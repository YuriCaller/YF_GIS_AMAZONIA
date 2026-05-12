# -*- coding: utf-8 -*-
"""
CRS Utilities - Shared coordinate reference system helpers.

Common CRS operations used across multiple tools:
- UTM zone detection from coordinates
- CRS validation for projected systems
- Coordinate transformation helpers
- Auto-detection of UTM zone/band from project CRS (v2.0)
"""

import re

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsPointXY,
)


# Standard CRS for Madre de Dios
CRS_WGS84_UTM19S = QgsCoordinateReferenceSystem("EPSG:32719")
CRS_WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")

# EPSG ranges for UTM WGS84
EPSG_UTM_NORTH_BASE = 32600  # 32601-32660 = UTM zones 1N to 60N
EPSG_UTM_SOUTH_BASE = 32700  # 32701-32760 = UTM zones 1S to 60S


# ============================================================
# Legacy API (preserved from v1.x)
# ============================================================

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


# ============================================================
# NEW v2.0: UTM zone detection from project CRS
# Used by goto and other navigation tools
# ============================================================

def detect_utm_from_crs(crs):
    """
    Detect UTM zone and band from a QgsCoordinateReferenceSystem.

    Returns (zone, band, source_description) or (None, None, description).
    """
    if not crs or not crs.isValid():
        return (None, None, "CRS no válido")

    auth_id = crs.authid()
    description = crs.description()

    # Try parsing standard EPSG
    epsg_match = re.match(r'EPSG:(\d+)', auth_id)
    if epsg_match:
        epsg = int(epsg_match.group(1))

        # UTM WGS84 north: 32601-32660
        if EPSG_UTM_NORTH_BASE < epsg <= EPSG_UTM_NORTH_BASE + 60:
            zone = epsg - EPSG_UTM_NORTH_BASE
            band = 'N'
            return (zone, band, f"Detectado desde {auth_id} (UTM {zone} Norte)")

        # UTM WGS84 south: 32701-32760
        if EPSG_UTM_SOUTH_BASE < epsg <= EPSG_UTM_SOUTH_BASE + 60:
            zone = epsg - EPSG_UTM_SOUTH_BASE
            band = 'L'  # default southern band (Madre de Dios = L)
            return (zone, band, f"Detectado desde {auth_id} (UTM {zone} Sur)")

    # Try parsing WKT description
    desc_match = re.search(r'UTM\s+zone\s+(\d+)\s*([NS])?', description, re.IGNORECASE)
    if desc_match:
        zone = int(desc_match.group(1))
        hemi = desc_match.group(2)
        if hemi and hemi.upper() == 'S':
            band = 'L'
        elif hemi and hemi.upper() == 'N':
            band = 'N'
        else:
            band = 'L'
        return (zone, band, f"Detectado desde descripción: {description[:50]}")

    return (None, None, f"CRS no UTM: {auth_id}")


def refine_band_from_extent(zone, default_band, canvas_extent, canvas_crs):
    """
    Refine the UTM band using the center of the canvas extent.
    """
    if zone is None:
        return default_band

    try:
        center = canvas_extent.center()

        if canvas_crs.authid() != 'EPSG:4326':
            transform = QgsCoordinateTransform(
                canvas_crs, CRS_WGS84, QgsProject.instance()
            )
            center_geo = transform.transform(center)
            lat = center_geo.y()
        else:
            lat = center.y()

        bands = 'CDEFGHJKLMNPQRSTUVWX'
        if lat < -80 or lat > 84:
            return default_band
        idx = int((lat + 80) / 8)
        idx = max(0, min(idx, len(bands) - 1))
        return bands[idx]
    except Exception:
        return default_band


def get_project_utm_info():
    """
    Convenience function: returns (zone, band, description) using
    the current project's CRS and extent.
    """
    project = QgsProject.instance()
    crs = project.crs()

    zone, band, desc = detect_utm_from_crs(crs)

    if zone is not None:
        # Refine band using canvas extent
        try:
            from qgis.utils import iface
            if iface:
                canvas = iface.mapCanvas()
                extent = canvas.extent()
                refined_band = refine_band_from_extent(zone, band, extent, crs)
                if refined_band != band:
                    band = refined_band
                    desc += f" · Banda refinada: {band}"
        except Exception:
            pass

    return (zone, band, desc)
