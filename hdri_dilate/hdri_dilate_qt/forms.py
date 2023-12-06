from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *


class FormLayoutNoSideMargins(QFormLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 8, 0, 8)


class FormNoSideMargins(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._layout = FormLayoutNoSideMargins()
        self.setLayout(self._layout)

    def layout(self) -> FormLayoutNoSideMargins:
        return super().layout()

    def addWidget(self, widget: QWidget):
        self._layout.addWidget(widget)

    def addRow(self, label: str | QWidget, field: QWidget):
        self._layout.addRow(label, field)

    def addBlankRow(self):
        blank_label = QLabel("", parent=self)
        self._layout.addRow(blank_label)

    def addWidgetAsRow(self, widget: QWidget):
        self._layout.addRow(widget)
