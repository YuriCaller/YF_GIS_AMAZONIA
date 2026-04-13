# -*- coding: utf-8 -*-
"""
Base Tool - Abstract base class for all YF GIS Amazonia tools.

Every tool module must expose a class named `Tool` that inherits from
`BaseTool` and implements at minimum the `run()` method.
"""

import os
from abc import ABC, abstractmethod


class BaseTool(ABC):
    """
    Base class for all tools in the suite.

    Provides:
        - iface: QGIS interface reference
        - plugin_dir: path to the plugin root directory
        - tool_dir: path to the specific tool's directory
        - icon(): helper to load icons
    """

    # Each subclass should set this to its tool name (used in logging)
    TOOL_NAME = "BaseTool"

    def __init__(self, iface, plugin_dir):
        self.iface = iface
        self.plugin_dir = plugin_dir
        # tool_dir is computed from the subclass's file location
        self.tool_dir = os.path.dirname(
            os.path.abspath(self.__class__.__module__.replace(".", os.sep) + ".py")
        )

    @abstractmethod
    def run(self):
        """Execute the tool. Called when the user clicks the menu/toolbar action."""
        pass

    def unload(self):
        """
        Clean up resources when the plugin is unloaded.
        Override in subclass if needed (e.g., to close dialogs, remove map tools).
        """
        pass

    def icon(self, filename):
        """Load an icon from the plugin's icons/ directory."""
        from qgis.PyQt.QtGui import QIcon

        path = os.path.join(self.plugin_dir, "icons", filename)
        if os.path.exists(path):
            return QIcon(path)
        return QIcon()

    def tr(self, message):
        """
        Translate a string. For future i18n support.
        Currently returns the message as-is.
        """
        return message
