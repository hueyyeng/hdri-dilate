from PySide6.QtCore import *
from PySide6.QtWidgets import *


class MainWindowToolBar(QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("ToolBar")
        self.setWindowTitle("Toolbar")
        self.setMovable(False)
        self.visible_labels = True
        self._show_labels()

    def _show_labels(self):
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.set_button_width(48)

    def _hide_labels(self):
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.set_button_width(28)

    def set_button_width(self, width=48):
        self.setStyleSheet(
            f"""
            QToolButton {{
                min-width: {width}px;
            }}
            """
        )

    def toggle_labels(self, state: bool = None):
        self.visible_labels = state if state is not None else not self.visible_labels

        if self.visible_labels:
            self._show_labels()
        else:
            self._hide_labels()


class HorizontalToolBar(QWidget):
    width_margin = 0
    height_margin = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        self.setLayout(layout)
        self.useDefaultMargins()

    def layout(self) -> QHBoxLayout:
        return super().layout()

    def addWidget(self, w: QWidget):
        self.layout().addWidget(w)

    def addStretch(self):
        self.layout().addStretch()

    def useNoMargins(self):
        self.layout().setContentsMargins(0, 0, 0, 0)

    def useDefaultMargins(self):
        self.layout().setContentsMargins(
            self.width_margin,
            self.height_margin,
            self.width_margin,
            self.height_margin,
        )


class VerticalToolBar(QWidget):
    width_margin = 12
    height_margin = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.useDefaultMargins()

    def layout(self) -> QVBoxLayout:
        return super().layout()

    def addWidget(self, w: QWidget):
        self.layout().addWidget(w)

    def addStretch(self):
        self.layout().addStretch()

    def useNoMargins(self):
        self.layout().setContentsMargins(0, 0, 0, 0)

    def useDefaultMargins(self):
        self.layout().setContentsMargins(
            self.width_margin,
            self.height_margin,
            self.width_margin,
            self.height_margin,
        )
