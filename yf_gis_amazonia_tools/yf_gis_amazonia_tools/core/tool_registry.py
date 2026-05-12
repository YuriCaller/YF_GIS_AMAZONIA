# -*- coding: utf-8 -*-
"""
Tool Registry - Lazy-loading system for tool modules.

Each tool module must expose a class that implements:
    - __init__(self, iface, plugin_dir)
    - run(self)                         → called when menu/toolbar action is triggered
    - unload(self)   [optional]         → called on plugin shutdown
"""

import importlib
import os

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .logger import log_info, log_error, log_warning


class ToolEntry:
    """Holds metadata and lazy-loaded instance for a single tool."""

    __slots__ = (
        "tool_id", "label", "icon_path", "module_path",
        "action", "instance", "menu", "toolbar", "add_to_toolbar",
    )

    def __init__(self, tool_id, label, icon_path, module_path,
                 menu, toolbar, add_to_toolbar):
        self.tool_id = tool_id
        self.label = label
        self.icon_path = icon_path
        self.module_path = module_path
        self.menu = menu
        self.toolbar = toolbar
        self.add_to_toolbar = add_to_toolbar
        self.action = None
        self.instance = None


class ToolRegistry:
    """
    Central registry that manages tool registration, lazy loading,
    and cleanup.
    """

    def __init__(self, iface, plugin_dir):
        self.iface = iface
        self.plugin_dir = plugin_dir
        self._tools = {}  # tool_id → ToolEntry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, menu, toolbar, tool_id, label, icon,
                 module_path, add_to_toolbar=False):
        """
        Register a tool. Creates a QAction in the given menu (and optionally
        toolbar) but does NOT import the tool module yet — that happens on
        first click (lazy loading).
        """
        icon_path = os.path.join(self.plugin_dir, "icons", icon)
        qicon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        action = QAction(qicon, label, self.iface.mainWindow())
        action.setData(tool_id)
        action.triggered.connect(lambda checked, tid=tool_id: self._run_tool(tid))

        # Add to menu
        if menu is not None:
            menu.addAction(action)

        # Add to toolbar (only for primary tools)
        if add_to_toolbar and toolbar is not None:
            toolbar.addAction(action)

        entry = ToolEntry(
            tool_id=tool_id,
            label=label,
            icon_path=icon_path,
            module_path=module_path,
            menu=menu,
            toolbar=toolbar,
            add_to_toolbar=add_to_toolbar,
        )
        entry.action = action
        self._tools[tool_id] = entry

        log_info(f"Herramienta registrada: {label} ({tool_id})")

    def unload_all(self):
        """Unload every registered tool and clean up actions."""
        for tool_id, entry in self._tools.items():
            # Call tool's unload if it was ever loaded
            if entry.instance is not None:
                try:
                    if hasattr(entry.instance, "unload"):
                        entry.instance.unload()
                except Exception as e:
                    log_error(f"Error descargando {tool_id}: {e}")
                entry.instance = None

            # Remove action from toolbar
            if entry.add_to_toolbar and entry.toolbar and entry.action:
                entry.toolbar.removeAction(entry.action)

        self._tools.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_tool(self, tool_id):
        """Lazy-load and run a tool."""
        entry = self._tools.get(tool_id)
        if entry is None:
            log_error(f"Herramienta no encontrada: {tool_id}")
            return

        # Lazy load on first run
        if entry.instance is None:
            entry.instance = self._load_tool(entry)
            if entry.instance is None:
                return

        # Execute
        try:
            entry.instance.run()
        except Exception as e:
            log_error(f"Error ejecutando {tool_id}: {e}")
            import traceback
            traceback.print_exc()

    def _load_tool(self, entry):
        """
        Import and instantiate the tool module.

        Expected module structure:
            yf_gis_amazonia_tools.tools.<tool_name>
                └── __init__.py  →  must expose `Tool` class

        The Tool class receives (iface, plugin_dir) in __init__.
        """
        # Build full module path relative to the top package
        full_module = f"yf_gis_amazonia_tools.{entry.module_path}"

        try:
            module = importlib.import_module(full_module)
        except ImportError as e:
            log_error(
                f"No se pudo cargar el módulo '{full_module}': {e}\n"
                f"Verifica que el módulo exista y no tenga errores de importación."
            )
            self._show_load_error(entry.label, str(e))
            return None

        # Look for a 'Tool' class in the module
        tool_class = getattr(module, "Tool", None)
        if tool_class is None:
            log_error(
                f"El módulo '{full_module}' no expone la clase 'Tool'. "
                f"Cada herramienta debe tener: class Tool(BaseTool): ..."
            )
            return None

        try:
            instance = tool_class(self.iface, self.plugin_dir)
            log_info(f"Herramienta cargada: {entry.label}")
            return instance
        except Exception as e:
            log_error(f"Error instanciando {entry.label}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _show_load_error(self, label, error_msg):
        """Show a user-friendly error when a tool fails to load."""
        from qgis.PyQt.QtWidgets import QMessageBox

        QMessageBox.warning(
            self.iface.mainWindow(),
            "YF GIS Amazonia Tools",
            f"No se pudo cargar la herramienta:\n"
            f"<b>{label}</b>\n\n"
            f"Error: {error_msg}\n\n"
            f"Verifica que todas las dependencias estén instaladas.",
        )
