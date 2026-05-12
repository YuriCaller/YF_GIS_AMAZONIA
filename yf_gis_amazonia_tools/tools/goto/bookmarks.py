# -*- coding: utf-8 -*-
"""
YF Go-To Tool - Bookmarks Manager
Gestiona puntos frecuentes guardados por el usuario, persistidos con QSettings.

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

import json
from qgis.PyQt.QtCore import QObject, QSettings, pyqtSignal


SETTINGS_KEY = "yf_goto_tool/bookmarks"


class BookmarksManager(QObject):
    """
    Gestiona bookmarks de puntos frecuentes.

    Cada bookmark es un dict:
        {'name': str, 'lat': float, 'lon': float, 'note': str}
    """

    bookmarksChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bookmarks = []
        self.load()

    def load(self):
        """Carga bookmarks desde QSettings."""
        settings = QSettings()
        raw = settings.value(SETTINGS_KEY, '')
        if isinstance(raw, str) and raw:
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    self._bookmarks = [
                        b for b in data
                        if isinstance(b, dict) and 'lat' in b and 'lon' in b
                    ]
            except json.JSONDecodeError:
                self._bookmarks = []
        self.bookmarksChanged.emit()

    def save(self):
        """Guarda bookmarks en QSettings."""
        settings = QSettings()
        raw = json.dumps(self._bookmarks, ensure_ascii=False)
        settings.setValue(SETTINGS_KEY, raw)

    def add(self, name, lat, lon, note=''):
        """Añade un bookmark."""
        if not name:
            return False
        bookmark = {
            'name': name.strip(),
            'lat': float(lat),
            'lon': float(lon),
            'note': (note or '').strip(),
        }
        self._bookmarks.append(bookmark)
        self.save()
        self.bookmarksChanged.emit()
        return True

    def remove(self, index):
        """Elimina un bookmark por índice."""
        if 0 <= index < len(self._bookmarks):
            self._bookmarks.pop(index)
            self.save()
            self.bookmarksChanged.emit()
            return True
        return False

    def update(self, index, name=None, lat=None, lon=None, note=None):
        """Actualiza un bookmark."""
        if 0 <= index < len(self._bookmarks):
            b = self._bookmarks[index]
            if name is not None:
                b['name'] = name.strip()
            if lat is not None:
                b['lat'] = float(lat)
            if lon is not None:
                b['lon'] = float(lon)
            if note is not None:
                b['note'] = note.strip()
            self.save()
            self.bookmarksChanged.emit()
            return True
        return False

    def get_all(self):
        return list(self._bookmarks)

    def get(self, index):
        if 0 <= index < len(self._bookmarks):
            return dict(self._bookmarks[index])
        return None

    def count(self):
        return len(self._bookmarks)

    def clear(self):
        self._bookmarks = []
        self.save()
        self.bookmarksChanged.emit()
