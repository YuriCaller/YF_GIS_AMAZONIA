# -*- coding: utf-8 -*-
"""
Plugin Manager - Orchestrates all YF GIS Amazonia tools.

v2.0 changes:
- Added "Comparación visual" submenu with Swipe tool
- Added "Navegación" submenu with Go-To tool
- Enhanced "Acerca" dialog with TUCSA branding and services info

Handles menu creation, tool registration, and lifecycle management.
Each tool is a self-contained module under tools/ that registers itself
via the ToolRegistry.
"""

import logging
import os
try:
    from qgis.PyQt.QtGui import QAction        # Qt6: QAction vive en QtGui
except ImportError:
    from qgis.PyQt.QtWidgets import QAction    # Qt5: QAction vive en QtWidgets
from qgis.PyQt.QtWidgets import QMenu
from qgis.PyQt.QtGui import QIcon

from .tool_registry import ToolRegistry
from .logger import log_info, log_error
from .tools_catalog import DOCS_BASE

# Plugin version


def _leer_version():
    """Lee la versión desde metadata.txt (fuente única de verdad)."""
    try:
        import os as _os
        meta = _os.path.join(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__))), "metadata.txt")
        with open(meta, encoding="utf-8") as f:
            for linea in f:
                if linea.startswith("version="):
                    return linea.split("=", 1)[1].strip()
    except Exception:
        logging.getLogger(__name__).debug("no version", exc_info=True)
    return "?"


__version__ = _leer_version()


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
        # Integración con compositor de mapas
        try:
            from ..tools.layout_designer_integration import LayoutDesignerIntegration
            self._layout_integration = LayoutDesignerIntegration(
                self.iface, self.plugin_dir
            )
        except Exception as e:
            log_error(f"No se pudo integrar con el compositor: {e}")
            logging.getLogger(__name__).debug("layout", exc_info=True)
            self._layout_integration = None

        """Build the top-level menu, toolbar, and register every tool."""
        log_info(f"Iniciando YF GIS Amazonia Tools v{__version__}")

        # Componentes opcionales instalados en el perfil. Debe ocurrir
        # antes de registrar herramientas: varias importan su dependencia
        # en la cabecera del modulo y fallarian pese a estar instalada.
        try:
            from .dependencies import asegurar_sys_path
            asegurar_sys_path()
        except Exception:
            logging.getLogger(__name__).debug("sys.path", exc_info=True)

        # Create the top-level menu in the menu bar
        menu_bar = self.iface.mainWindow().menuBar()
        self.menu = QMenu(self.MENU_NAME, menu_bar)

        # Insert before Help so it appears as a tab like Vectorial, Ráster, etc.
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

        # Toolbar
        self.toolbar = self.iface.addToolBar("YF GIS Amazonia Tools")
        self.toolbar.setObjectName("YFGISAmazonia")

        # Register all tools
        self._register_tools()

        # Separator + Manual + About
        self.menu.addSeparator()

        manual_action = QAction(
            self._icon("main_icon.png"),
            "Manual de usuario (en linea)",
            self.iface.mainWindow(),
        )
        manual_action.setToolTip(
            "Abre el manual completo de la suite en el navegador")
        manual_action.triggered.connect(self._abrir_manual)
        self.menu.addAction(manual_action)
        self.actions.append(manual_action)

        about_action = QAction(
            self._icon("main_icon.png"),
            "Acerca de YF GIS Amazonia Tools...",
            self.iface.mainWindow(),
        )
        about_action.triggered.connect(self._show_about)
        self.menu.addAction(about_action)
        self.actions.append(about_action)

    def unload(self):
        if hasattr(self, '_layout_integration') and self._layout_integration:
            try:
                self._layout_integration.unload()
            except Exception:
                logging.getLogger(__name__).debug("suppressed", exc_info=True)

        """Clean up: unload all tools, remove menu and toolbar."""
        log_info("Descargando YF GIS Amazonia Tools")

        self.registry.unload_all()

        if self.menu:
            menu_bar = self.iface.mainWindow().menuBar()
            menu_bar.removeAction(self.menu.menuAction())
            self.menu.deleteLater()
            self.menu = None

        if self.toolbar:
            del self.toolbar
            self.toolbar = None

        self.actions.clear()

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_tools(self):
        """Register all tool modules grouped into thematic submenus."""

        # ── Catastral ──────────────────────────────────────────────
        catastral_menu = self.menu.addMenu(
            self._icon("catastral.png"), "Catastral"
        )

        self.registry.register(
            menu=catastral_menu, toolbar=self.toolbar,
            tool_id="memoria_descriptiva",
            label="Memoria Descriptiva",
            icon="memoria_descriptiva.png",
            module_path="tools.memoria_descriptiva",
            add_to_toolbar=True,
        )

        self.registry.register(
            menu=catastral_menu, toolbar=self.toolbar,
            tool_id="segmentador",
            label="Segmentador de Parcelas",
            icon="segmentador.png",
            module_path="tools.segmentador",
            add_to_toolbar=True,
        )

        self.registry.register(
            menu=catastral_menu, toolbar=self.toolbar,
            tool_id="vector_geometry",
            label="Calcular Geometría Vectorial",
            icon="vector_geometry.png",
            module_path="tools.vector_geometry",
            add_to_toolbar=True,
        )

        self.registry.register(
            menu=catastral_menu, toolbar=None,
            tool_id="yf_tools_plus",
            label="YF Tools Plus",
            icon="yf_tools.png",
            module_path="tools.yf_tools_plus",
        )

        self.registry.register(
            menu=catastral_menu, toolbar=self.toolbar,
            tool_id="polygon_divider",
            label="Polygon Divider — Dividir Polígono",
            icon="polygon_divider.png",
            module_path="tools.polygon_divider",
            add_to_toolbar=True,
        )

        self.registry.register(
            menu=catastral_menu, toolbar=self.toolbar,
            tool_id="smart_georeferencer",
            label="Smart Georeferencer — Georreferenciar en vivo",
            icon="smart_georeferencer.png",
            module_path="tools.smart_georeferencer",
            add_to_toolbar=True,
        )

        # ── Geodesia / GNSS ───────────────────────────────────────
        gnss_menu = self.menu.addMenu(
            self._icon("gnss.png"), "Geodesia / GNSS"
        )

        self.registry.register(
            menu=gnss_menu, toolbar=self.toolbar,
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
            menu=agro_menu, toolbar=self.toolbar,
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
            menu=search_menu, toolbar=self.toolbar,
            tool_id="attribute_search",
            label="Búsqueda Avanzada de Atributos",
            icon="search.png",
            module_path="tools.attribute_search",
            add_to_toolbar=True,
        )

        self.registry.register(
            menu=search_menu, toolbar=self.toolbar,
            tool_id="superposition",
            label="Análisis de Superposición de Derechos",
            icon="superposition.png",
            module_path="tools.superposition",
            add_to_toolbar=True,
        )

        # ── Batch Export ──────────────────────────────────────────
        self.registry.register(
            menu=catastral_menu, toolbar=self.toolbar,
            tool_id="batch_export",
            label="Exportar Expediente",
            icon="batch_export.png",
            module_path="tools.batch_export",
            add_to_toolbar=True,
        )

        # ── Layout Tools ──────────────────────────────────────────
        layout_menu = self.menu.addMenu(
            self._icon("layout_tools.png"), "Layout / Compositor"
        )

        self.registry.register(
            menu=catastral_menu, toolbar=self.toolbar,
            tool_id="smart_labels",
            label="Smart Labels — Etiquetar capa",
            icon="smart_labels.png",
            module_path="tools.smart_labels",
            add_to_toolbar=True,
        )

        self.registry.register(
            menu=layout_menu, toolbar=self.toolbar,
            tool_id="layout_tools",
            label="Table Style Manager",
            icon="layout_tools.png",
            module_path="tools.layout_tools",
            add_to_toolbar=False,
        )

        self.registry.register(
            menu=layout_menu, toolbar=self.toolbar,
            tool_id="title_block",
            label="Generar Cajetín",
            icon="title_block.png",
            module_path="tools.layout_tools.title_block_tool",
            add_to_toolbar=False,
        )

        self.registry.register(
            menu=layout_menu, toolbar=self.toolbar,
            tool_id="layout_rescaler",
            label="Redimensionar Layout",
            icon="layout_rescaler.png",
            module_path="tools.layout_rescaler",
            add_to_toolbar=False,
        )
        # ── Comparación Visual (NEW v2.0) ─────────────────────────
        compare_menu = self.menu.addMenu(
            self._icon("swipe.png"), "Comparación Visual"
        )

        self.registry.register(
            menu=compare_menu, toolbar=self.toolbar,
            tool_id="swipe",
            label="Swipe Tool",
            icon="swipe.png",
            module_path="tools.swipe",
            add_to_toolbar=True,
        )

        # ── Navegación (NEW v2.0) ─────────────────────────────────
        nav_menu = self.menu.addMenu(
            self._icon("goto.png"), "Navegación"
        )

        self.registry.register(
            menu=nav_menu, toolbar=self.toolbar,
            tool_id="goto",
            label="Go-To (Ir a coordenadas)",
            icon="goto.png",
            module_path="tools.goto",
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

    def _abrir_manual(self):
        """Abre el manual en el navegador del sistema.

        QDesktopServices y no un visor incrustado: QtWebEngine no esta
        garantizado en todas las instalaciones de QGIS.
        """
        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(DOCS_BASE + "/"))

    def _show_about(self):
        """Show the enhanced About dialog with TUCSA branding."""
        from .about_dialog import AboutDialog
        dlg = AboutDialog(self.iface.mainWindow(), __version__, self.plugin_dir)
        dlg.exec()
