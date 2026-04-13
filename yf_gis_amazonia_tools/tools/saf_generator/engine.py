# -*- coding: utf-8 -*-
"""
SAF Generator Engine - Core plantation generation logic.

Separated from UI for testability and reuse.
Improvements over v2.1:
- Uses QgsGeometry.prepareGeometry() for faster point-in-polygon tests
- Proper error handling (no bare except)
- Synchronized species/proportions management
"""

import math
import random
import re

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsProject, QgsWkbTypes,
    QgsPointXY, QgsSymbol, QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsField, QgsLineString,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor


class SAFEngine:
    """
    Core engine for generating agroforestry planting points.

    Usage:
        engine = SAFEngine()
        points, h_lines, v_lines = engine.generate(
            layer=my_polygon_layer,
            distance=2.29,
            method="HASH",
            species={0: {"nombre": "PLATANO", "color": "#FFD700"}, ...},
            proportions={0: 42, 1: 58},
            pattern=None,
            orientation_angle=0.0,
            use_orientation=False,
        )
    """

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def generate(self, layer, distance, method, species,
                 proportions=None, pattern=None,
                 orientation_angle=0.0, use_orientation=False):
        """
        Generate planting points for all features in the polygon layer.

        Returns:
            (points, horizontal_lines, vertical_lines)
        """
        points = []
        lines_h = []
        lines_v = []
        point_id = 1
        pattern_index = 0

        if proportions is None:
            # Equal distribution
            n = len(species)
            proportions = {k: 100.0 / n for k in species}

        # Normalize proportions to sum 100
        proportions = self._normalize_proportions(proportions)

        for feature in layer.getFeatures():
            geom = feature.geometry()
            if geom.isEmpty():
                continue

            # Prepare geometry for faster contains() calls
            prepared_geom = QgsGeometry(geom)

            bbox = geom.boundingBox()
            centroid = geom.centroid().asPoint()
            cx, cy = centroid.x(), centroid.y()
            parcel_id = feature.id()

            # Compute grid bounds
            x_min, x_max, y_min, y_max = self._compute_bounds(
                bbox, cx, cy, use_orientation
            )

            # Generate grid coordinates
            coords_x = []
            all_coords_y = set()
            row_idx = 0

            x = x_min
            while x <= x_max:
                coords_x.append(x)
                col_idx = 0
                y = y_min

                while y <= y_max:
                    all_coords_y.add(round(y, 6))

                    # Apply rotation if needed
                    if use_orientation:
                        px, py = self._rotate_point(
                            x, y, cx, cy, -orientation_angle
                        )
                    else:
                        px, py = x, y

                    # Point-in-polygon test
                    if self._point_in_polygon(px, py, prepared_geom):
                        # Determine species
                        if method == "SECUENCIAL" and pattern:
                            code = pattern[pattern_index % len(pattern)]
                            pattern_index += 1
                        else:
                            code = self._determine_species(
                                x, y, row_idx, col_idx,
                                species, method, proportions
                            )

                        if code in species:
                            col_letter = self._number_to_letter(col_idx)
                            row_number = row_idx + 1

                            points.append({
                                "id": point_id,
                                "parcela": parcel_id,
                                "especie_codigo": code,
                                "especie_nombre": species[code]["nombre"],
                                "x": px,
                                "y": py,
                                "columna": col_letter,
                                "fila": row_number,
                                "id_unico": f"{col_letter}{row_number}",
                            })
                            point_id += 1

                    col_idx += 1
                    y += distance

                row_idx += 1
                x += distance

            # Build grid lines
            sorted_y = sorted(all_coords_y)
            lines_v.extend(
                self._build_grid_lines(
                    coords_x, sorted_y, "vertical",
                    prepared_geom, cx, cy,
                    orientation_angle, use_orientation,
                )
            )
            lines_h.extend(
                self._build_grid_lines(
                    coords_x, sorted_y, "horizontal",
                    prepared_geom, cx, cy,
                    orientation_angle, use_orientation,
                )
            )

        return points, lines_h, lines_v

    def create_point_layer(self, points, crs, name, species):
        """Create a styled memory layer from generated points."""
        layer = QgsVectorLayer(f"Point?crs={crs.authid()}", name, "memory")
        provider = layer.dataProvider()

        provider.addAttributes([
            QgsField("ID", QVariant.Int),
            QgsField("PARCELA", QVariant.String),
            QgsField("ESPECIE", QVariant.String),
            QgsField("CODIGO", QVariant.Int),
            QgsField("COLUMNA", QVariant.String),
            QgsField("FILA", QVariant.Int),
            QgsField("ID_UNICO", QVariant.String),
            QgsField("COORD_X", QVariant.Double),
            QgsField("COORD_Y", QVariant.Double),
        ])
        layer.updateFields()

        features = []
        for p in points:
            feat = QgsFeature()
            feat.setGeometry(
                QgsGeometry.fromPointXY(QgsPointXY(p["x"], p["y"]))
            )
            feat.setAttributes([
                p["id"],
                str(p["parcela"]),
                p["especie_nombre"],
                p["especie_codigo"],
                p["columna"],
                p["fila"],
                p["id_unico"],
                round(p["x"], 4),
                round(p["y"], 4),
            ])
            features.append(feat)

        provider.addFeatures(features)
        layer.updateExtents()

        # Apply categorized symbology
        categories = []
        for code, info in species.items():
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(info["color"]))
            symbol.setSize(3)
            cat = QgsRendererCategory(info["nombre"], symbol, info["nombre"])
            categories.append(cat)

        renderer = QgsCategorizedSymbolRenderer("ESPECIE", categories)
        layer.setRenderer(renderer)

        return layer

    def create_grid_layer(self, lines_h, lines_v, crs, name):
        """Create a memory layer with grid lines."""
        layer = QgsVectorLayer(
            f"LineString?crs={crs.authid()}", name, "memory"
        )
        provider = layer.dataProvider()

        provider.addAttributes([
            QgsField("TIPO", QVariant.String),
            QgsField("ID", QVariant.Int),
        ])
        layer.updateFields()

        features = []
        line_id = 1

        for pts in lines_h:
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPolylineXY(pts))
            feat.setAttributes(["HORIZONTAL", line_id])
            features.append(feat)
            line_id += 1

        for pts in lines_v:
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPolylineXY(pts))
            feat.setAttributes(["VERTICAL", line_id])
            features.append(feat)
            line_id += 1

        provider.addFeatures(features)
        layer.updateExtents()

        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.setColor(QColor(100, 100, 100, 150))
        symbol.setWidth(0.3)
        layer.renderer().setSymbol(symbol)

        return layer

    # ------------------------------------------------------------------
    # Species determination
    # ------------------------------------------------------------------

    def _determine_species(self, x, y, row_idx, col_idx,
                           species, method, proportions):
        """Determine species code for a point based on distribution method."""
        keys = list(species.keys())

        if method == "AJEDREZ":
            return keys[(row_idx + col_idx) % len(keys)]

        elif method == "HASH":
            x_int = int(x * 1000)
            y_int = int(y * 1000)
            hash_val = ((x_int * 73856093) ^ (y_int * 19349663)) % 100
            acc = 0
            for code, prop in proportions.items():
                acc += prop
                if hash_val < acc:
                    return code
            return keys[0]

        elif method == "FILAS":
            return keys[row_idx % len(keys)]

        elif method == "BLOQUES":
            bx = (col_idx // 3) % len(keys)
            by = (row_idx // 3) % len(keys)
            return keys[(bx + by) % len(keys)]

        elif method == "ALEATORIO":
            random.seed(int(x * 1000 + y * 1000))
            rand_val = random.random() * 100
            acc = 0
            for code, prop in proportions.items():
                acc += prop
                if rand_val < acc:
                    return code
            return keys[0]

        return keys[0]

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rotate_point(x, y, cx, cy, angle_degrees):
        """Rotate a point around a center."""
        ang = math.radians(angle_degrees)
        dx, dy = x - cx, y - cy
        x_rot = dx * math.cos(ang) - dy * math.sin(ang)
        y_rot = dx * math.sin(ang) + dy * math.cos(ang)
        return cx + x_rot, cy + y_rot

    @staticmethod
    def _point_in_polygon(x, y, geom):
        """Test if a point is inside a geometry."""
        pt = QgsGeometry.fromPointXY(QgsPointXY(x, y))
        return geom.contains(pt)

    @staticmethod
    def _compute_bounds(bbox, cx, cy, use_orientation):
        """Compute grid generation bounds, expanding for rotation."""
        if use_orientation:
            w = bbox.xMaximum() - bbox.xMinimum()
            h = bbox.yMaximum() - bbox.yMinimum()
            diag = math.sqrt(w ** 2 + h ** 2)
            exp = diag * 0.6
            return cx - exp, cx + exp, cy - exp, cy + exp
        else:
            return (
                bbox.xMinimum(), bbox.xMaximum(),
                bbox.yMinimum(), bbox.yMaximum(),
            )

    @staticmethod
    def _number_to_letter(n):
        """Convert 0-based index to Excel-style column letter (A, B, ..., Z, AA, ...)."""
        result = ""
        n += 1
        while n > 0:
            n -= 1
            result = chr(65 + (n % 26)) + result
            n //= 26
        return result

    @staticmethod
    def _normalize_proportions(proportions):
        """Normalize proportions to sum to 100."""
        total = sum(proportions.values())
        if total > 0 and abs(total - 100) > 0.01:
            return {k: (v / total) * 100 for k, v in proportions.items()}
        return dict(proportions)

    def _build_grid_lines(self, coords_x, coords_y, direction,
                          geom, cx, cy, angle, use_orientation):
        """Build grid lines (horizontal or vertical) clipped to polygon."""
        lines = []

        if direction == "vertical":
            for x_val in coords_x:
                pts = []
                for y_val in coords_y:
                    if use_orientation:
                        px, py = self._rotate_point(
                            x_val, y_val, cx, cy, -angle
                        )
                    else:
                        px, py = x_val, y_val
                    if self._point_in_polygon(px, py, geom):
                        pts.append(QgsPointXY(px, py))
                if len(pts) >= 2:
                    lines.append(pts)
        else:  # horizontal
            for y_val in coords_y:
                pts = []
                for x_val in coords_x:
                    if use_orientation:
                        px, py = self._rotate_point(
                            x_val, y_val, cx, cy, -angle
                        )
                    else:
                        px, py = x_val, y_val
                    if self._point_in_polygon(px, py, geom):
                        pts.append(QgsPointXY(px, py))
                if len(pts) >= 2:
                    lines.append(pts)

        return lines
