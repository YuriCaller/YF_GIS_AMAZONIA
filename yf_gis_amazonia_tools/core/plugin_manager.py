# -*- coding: utf-8 -*-
"""
Plugin Manager - Orchestrates all YF GIS Amazonia tools.

Handles menu creation, tool registration, and lifecycle management.
Each tool is a self-contained module under tools/ that registers itself
via the ToolRegistry.
"""

import os
from qgis.PyQt.QtWidgets import QAction, QMenu
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsApplication

from .tool_registry import ToolRegistry
from .logger import log_info, log_error

# Plugin version
__version__ = "1.0.0"


class YFGISAmazonia:
    """Main plugin class - manages the unified menu and all sub-tools."""

    MENU_NAME = "YF GIS Amazonia"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.menu = None
        self.toolbar = None
        self.actions = []
        self.registry = ToolRegistry(iface, self.plugin_dir)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initGui(self):
        """Build the top-level menu, toolbar, and register every tool."""
        log_info(f"Iniciando YF GIS Amazonia Tools v{__version__}")

        # Create the top-level menu in the menu bar
        # IMPORTANT: Do NOT set an icon on the top-level QMenu — QGIS would
        # render it as an icon-only button instead of a text tab like
        # "Vectorial", "Ráster", etc. Icons only go on submenus and actions.
        menu_bar = self.iface.mainWindow().menuBar()
        self.menu = QMenu(self.MENU_NAME, menu_bar)

        # Insert before the Help menu so it appears as a proper tab
        help_menu_action = None
        for action in menu_bar.actions():
            menu_obj = action.menu()
            if menu_obj is not None:
                title = menu_obj.title().replace("&", "").lower()
                if title in ("help", "ayuda", "aide", "hilfe", "ajuda"):
                    help_menu_action = action
                    break

        if help_menu_action is not None:
            menu_bar.insertMenu(help_menu_action, self.menu)
        else:
            menu_bar.addMenu(self.menu)

        # Create toolbar
        self.toolbar = self.iface.addToolBar("YF GIS Amazonia Tools")
        self.toolbar.setObjectName("YFGISAmazonia")

        # ----------------------------------------------------------
        # Register tool groups (each creates a submenu)
        # ----------------------------------------------------------
        self._register_tools()

        # Separator + About
        self.menu.addSeparator()
        about_action = QAction(
            self._icon("main_icon.png"),
            "Acerca de YF GIS Amazonia Tools...",
            self.iface.mainWindow(),
        )
        about_action.triggered.connect(self._show_about)
        self.menu.addAction(about_action)
        self.actions.append(about_action)

    def unload(self):
        """Clean up: unload all tools, remove menu and toolbar."""
        log_info("Descargando YF GIS Amazonia Tools")

        # Unload every registered tool
        self.registry.unload_all()

        # Remove top-level menu
        if self.menu:
            menu_bar = self.iface.mainWindow().menuBar()
            menu_bar.removeAction(self.menu.menuAction())
            self.menu.deleteLater()
            self.menu = None

        # Remove toolbar
        if self.toolbar:
            del self.toolbar
            self.toolbar = None

        self.actions.clear()

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_tools(self):
        """Register all tool modules grouped into submenus."""

        # ── Catastral ──────────────────────────────────────────────
        catastral_menu = self.menu.addMenu(
            self._icon("catastral.png"), "Catastral"
        )

        self.registry.register(
            menu=catastral_menu,
            toolbar=self.toolbar,
            tool_id="memoria_descriptiva",
            label="Memoria Descriptiva",
            icon="memoria_descriptiva.png",
            module_path="tools.memoria_descriptiva",
            add_to_toolbar=True,
        )

        self.registry.register(
            menu=catastral_menu,
            toolbar=None,
            tool_id="segmentador",
            label="Segmentador de Parcelas",
            icon="segmentador.png",
            module_path="tools.segmentador",
        )

        self.registry.register(
            menu=catastral_menu,
            toolbar=None,
            tool_id="yf_tools_plus",
            label="YF Tools Plus",
            icon="yf_tools.png",
            module_path="tools.yf_tools_plus",
        )

        # ── Geodesia / GNSS ───────────────────────────────────────
        gnss_menu = self.menu.addMenu(
            self._icon("gnss.png"), "Geodesia / GNSS"
        )

        self.registry.register(
            menu=gnss_menu,
            toolbar=self.toolbar,
            tool_id="gnss_postprocess",
            label="Post-Proceso PPK/PPP",
            icon="gnss.png",
            module_path="tools.gnss_postprocess",
            add_to_toolbar=True,
        )

        # ── Agroforestal / Ambiental ──────────────────────────────
        agro_menu = self.menu.addMenu(
            self._icon("agroforestal.png"), "Agroforestal / Ambiental"
        )

        self.registry.register(
            menu=agro_menu,
            toolbar=self.toolbar,
            tool_id="saf_generator",
            label="SAF Generator",
            icon="saf.png",
            module_path="tools.saf_generator",
            add_to_toolbar=True,
        )

        # ── Búsqueda y Análisis ───────────────────────────────────
        search_menu = self.menu.addMenu(
            self._icon("search.png"), "Búsqueda y Análisis"
        )

        self.registry.register(
            menu=search_menu,
            toolbar=self.toolbar,
            tool_id="attribute_search",
            label="Búsqueda Avanzada de Atributos",
            icon="search.png",
            module_path="tools.attribute_search",
            add_to_toolbar=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _icon(self, filename):
        """Load an icon from the icons/ directory."""
        path = os.path.join(self.plugin_dir, "icons", filename)
        if os.path.exists(path):
            return QIcon(path)
        return QIcon()

    def _show_about(self):
        """Show the About dialog."""
        from qgis.PyQt.QtWidgets import QMessageBox

        QMessageBox.information(
            self.iface.mainWindow(),
            "Acerca de YF GIS Amazonia Tools",
            f"<b>YF GIS Amazonia Tools</b> v{__version__}<br><br>"
            f"Suite profesional de herramientas GIS para<br>"
            f"saneamiento físico legal, catastro rural,<br>"
            f"geodesia y gestión agroforestal.<br><br>"
            f"<b>Autor:</b> Yuri Fabian Caller Córdova<br>"
            f"<b>CIP:</b> 214377<br>"
            f"<b>Empresa:</b> Training Universal Company SAC<br>"
            f"<b>Web:</b> <a href='https://gis-amazonia.pe'>gis-amazonia.pe</a><br><br>"
            f"© 2025 TUCSA — Todos los derechos reservados",
        )
