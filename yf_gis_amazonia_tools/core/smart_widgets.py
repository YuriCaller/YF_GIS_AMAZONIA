# -*- coding: utf-8 -*-
"""
YF Go-To Tool - Smart Input Widgets
SpinBoxes y LineEdits que interceptan paste con múltiples valores.

Caso de uso típico:
- Yuri copia "485185\t8625060" desde Excel
- Pega en cualquier campo (Easting o Northing)
- El widget detecta los 2 valores y los distribuye automáticamente
  entre Easting y Northing

Autor: Yuri Caller - TUCSA / gis-amazonia.pe
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QKeyEvent, QClipboard
from qgis.PyQt.QtWidgets import (
    QDoubleSpinBox, QSpinBox, QLineEdit, QApplication
)

from .paste_helpers import extract_number_pair


class SmartDoubleSpinBox(QDoubleSpinBox):
    """
    QDoubleSpinBox que detecta cuando el clipboard tiene 2+ valores
    y emite una señal para que el widget padre distribuya los valores.
    """

    # Señal emitida cuando se pega un par. Argumentos: (val1, val2)
    pairPasted = pyqtSignal(float, float)

    def keyPressEvent(self, event):
        # Detectar Ctrl+V
        if event.matches(self.keyEvent_paste()):
            clipboard_text = QApplication.clipboard().text()
            pair = extract_number_pair(clipboard_text)
            if pair is not None:
                val1, val2 = pair
                # Emitir señal — el contenedor decide cómo distribuir
                self.pairPasted.emit(val1, val2)
                event.accept()
                return
        super().keyPressEvent(event)

    def keyEvent_paste(self):
        """Retorna una secuencia de paste para comparar con .matches()."""
        from qgis.PyQt.QtGui import QKeySequence
        return QKeySequence.StandardKey.Paste


class SmartSpinBox(QSpinBox):
    """Variante para enteros."""
    pairPasted = pyqtSignal(float, float)

    def keyPressEvent(self, event):
        from qgis.PyQt.QtGui import QKeySequence
        if event.matches(QKeySequence.StandardKey.Paste):
            clipboard_text = QApplication.clipboard().text()
            pair = extract_number_pair(clipboard_text)
            if pair is not None:
                val1, val2 = pair
                self.pairPasted.emit(val1, val2)
                event.accept()
                return
        super().keyPressEvent(event)


class SmartLineEdit(QLineEdit):
    """QLineEdit que también detecta paste de pares numéricos."""
    pairPasted = pyqtSignal(float, float)

    def keyPressEvent(self, event):
        from qgis.PyQt.QtGui import QKeySequence
        if event.matches(QKeySequence.StandardKey.Paste):
            clipboard_text = QApplication.clipboard().text()
            pair = extract_number_pair(clipboard_text)
            if pair is not None:
                val1, val2 = pair
                self.pairPasted.emit(val1, val2)
                event.accept()
                return
        super().keyPressEvent(event)
