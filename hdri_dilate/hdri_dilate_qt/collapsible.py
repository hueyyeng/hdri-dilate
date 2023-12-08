from __future__ import annotations

import logging

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate.constants import icons
from hdri_dilate.hdri_dilate_qt import tr

logger = logging.getLogger()


class CollapsibleRemoveButton(QToolButton):
    icon_size = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setToolTip(tr("Remove"))
        self.pixmap = QIcon(icons.CROSS).pixmap(self.icon_size, self.icon_size)
        self.pixmap_cache = None
        self.setStyleSheet(
            """
            QToolButton {
              border: none;
            }
            """
        )

    # TODO: Optimize this later
    def paintEvent(self, event: QPaintEvent):
        full_rect = QRect(
            round(self.icon_size / 3),
            round(self.icon_size / 3),
            self.icon_size,
            self.icon_size,
        )

        if self.underMouse() and self.pixmap_cache:
            painter = QPainter(self)
            painter.drawPixmap(
                full_rect,
                self.pixmap_cache,
            )
            painter.end()
        elif self.underMouse():
            image = self.pixmap.toImage()
            _painter = QPainter(image)
            _painter.drawImage(0, 0, image)
            _painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
            _painter.drawImage(0, 0, image)
            _painter.end()
            self.pixmap_cache = QPixmap().fromImage(image)
            painter = QPainter(self)
            painter.drawPixmap(
                full_rect,
                self.pixmap_cache,
            )
            painter.end()
        else:
            painter = QPainter(self)
            painter.drawPixmap(
                full_rect,
                self.pixmap,
            )
            painter.end()


class CollapsibleWidgetHeader(QWidget):
    ARROW_SIZE = 16
    clicked = Signal()
    removed = Signal()

    def __init__(self, name: str, parent: "CollapsibleWidget"):
        """

        Parameters
        ----------
        name : str
            Header name
        parent : CollapsibleWidget
            Instance of CollapsibleWidget

        """
        super().__init__(parent)
        self.content = parent.content
        self.expanded_pixmap = QIcon(icons.DOWN_ARROW).pixmap(self.ARROW_SIZE, self.ARROW_SIZE)
        self.collapsed_pixmap = QIcon(icons.PLAY_ARROW).pixmap(self.ARROW_SIZE, self.ARROW_SIZE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        stacked = QStackedLayout(self)
        stacked.setStackingMode(QStackedLayout.StackAll)
        background = QLabel(self)
        background.setStyleSheet(
            """
            QLabel {
              background-color: rgb(210, 210, 210);
            }
            """
        )

        widget = QWidget(self)
        layout = QHBoxLayout(self)
        widget.setLayout(layout)

        self.icon = QLabel(self)
        self.icon.setMinimumWidth(self.ARROW_SIZE)
        self.icon.setPixmap(self.expanded_pixmap)
        layout.addWidget(self.icon)
        layout.setContentsMargins(0, 0, 0, 0)

        font = QFont()
        font.setBold(True)
        self.title = QLabel(name)
        self.title.setFont(font)

        self.remove_btn = CollapsibleRemoveButton(self)
        self.remove_btn.setVisible(False)
        self.remove_btn.clicked.connect(self.removed.emit)

        layout.addWidget(self.title)
        layout.addStretch()
        layout.addWidget(self.remove_btn)

        stacked.addWidget(widget)
        stacked.addWidget(background)
        background.setMinimumHeight(layout.sizeHint().height() * 1.5)

    def mousePressEvent(self, *args):
        self.clicked.emit()

    def setTitle(self, text: str):
        self.title.setText(text)

    def set_arrow_size(self, arrow_size: int):
        self.expanded_pixmap = QIcon(icons.DOWN_ARROW).pixmap(arrow_size, arrow_size)
        self.collapsed_pixmap = QIcon(icons.PLAY_ARROW).pixmap(arrow_size, arrow_size)

        if self.content.isVisible():
            self.icon.setPixmap(self.expanded_pixmap)
        else:
            self.icon.setPixmap(self.collapsed_pixmap)

    def reset_arrow_size(self):
        self.set_arrow_size(self.ARROW_SIZE)

    def show_remove_btn(self):
        self.remove_btn.setVisible(True)

    def hide_remove_btn(self):
        self.remove_btn.setVisible(False)

    def expand(self):
        self.content.setVisible(True)
        self.icon.setPixmap(self.expanded_pixmap)

    def collapse(self):
        self.content.setVisible(False)
        self.icon.setPixmap(self.collapsed_pixmap)


class CollapsibleWidgetContent(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)


class CollapsibleWidget(QWidget):
    def __init__(self, name="Widget", parent=None):
        super().__init__(parent)
        self.setObjectName(f"cw_{name}")
        self.content = CollapsibleWidgetContent(self)
        self.header = CollapsibleWidgetHeader(name, self)
        self.header.clicked.connect(self.toggle)
        self.setup_ui()

    def addWidget(self, widget: QWidget):
        self.content.layout().addWidget(widget)

    def setHeaderTitle(self, text: str):
        self.header.setTitle(text)

    def setup_ui(self):
        self.layout_ = QVBoxLayout()
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout_)

        self.layout_.addWidget(self.header)
        self.layout_.addWidget(self.content)

    def collapse(self):
        self.header.collapse()

    def expand(self):
        self.header.expand()

    def toggle(self):
        self.expand() if not self.content.isVisible() else self.collapse()
