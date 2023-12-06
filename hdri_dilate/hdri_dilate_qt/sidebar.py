from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import MainWindow

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget


class SidebarWidget(QWidget):
    WIDTH = 480

    def __init__(self, parent: "MainWindow"):
        super().__init__(parent=parent)
        self.setup_ui()

    def setup_ui(self):
        self.setFixedWidth(self.WIDTH)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(layout)

    def addWidget(self, widget: QWidget):
        self.layout().addWidget(widget)

    def toggle_visibility(self):
        self.hide() if self.isVisible() else self.show()
