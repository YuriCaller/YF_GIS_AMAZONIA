# -*- coding: utf-8 -*-
"""
Qt Compatibility - Centralized PyQt5/PyQt6 compatibility helpers.

Import from here instead of directly from qgis.PyQt to handle
API differences between PyQt5 (QGIS ≤ 3.34) and PyQt6 (QGIS ≥ 3.40).
"""

from qgis.PyQt.QtCore import Qt

# ── Enum compatibility ──────────────────────────────────────────────
# In PyQt6, enums moved to scoped syntax (e.g., Qt.AlignmentFlag.AlignCenter)
# In PyQt5, they're unscoped (e.g., Qt.AlignCenter)


def _resolve_enum(parent, scoped_name, fallback_name):
    """Try scoped enum first (PyQt6), fall back to unscoped (PyQt5)."""
    val = getattr(parent, scoped_name, None)
    if val is not None:
        return val
    return getattr(parent, fallback_name)


# Common Qt enums used across the plugin
AlignCenter = _resolve_enum(Qt, "AlignmentFlag.AlignCenter", "AlignCenter")
AlignLeft = _resolve_enum(Qt, "AlignmentFlag.AlignLeft", "AlignLeft")
AlignRight = _resolve_enum(Qt, "AlignmentFlag.AlignRight", "AlignRight")

Checked = _resolve_enum(Qt, "CheckState.Checked", "Checked")
Unchecked = _resolve_enum(Qt, "CheckState.Unchecked", "Unchecked")

Horizontal = _resolve_enum(Qt, "Orientation.Horizontal", "Horizontal")
Vertical = _resolve_enum(Qt, "Orientation.Vertical", "Vertical")

WaitCursor = _resolve_enum(Qt, "CursorShape.WaitCursor", "WaitCursor")

UserRole = _resolve_enum(Qt, "ItemDataRole.UserRole", "UserRole")

# ── QVariant compatibility ──────────────────────────────────────────
try:
    from qgis.PyQt.QtCore import QVariant  # PyQt5

    QVariant_Int = QVariant.Int
    QVariant_Double = QVariant.Double
    QVariant_String = QVariant.String
except (ImportError, AttributeError):
    # PyQt6 - QVariant.Type enum may differ
    from qgis.PyQt.QtCore import QMetaType

    QVariant_Int = QMetaType.Type.Int
    QVariant_Double = QMetaType.Type.Double
    QVariant_String = QMetaType.Type.QString
