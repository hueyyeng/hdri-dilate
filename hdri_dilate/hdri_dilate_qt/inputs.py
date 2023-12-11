import os
import re
from pathlib import Path

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate.constants import icons
from hdri_dilate.hdri_dilate_qt import tr


class CrossPlatformPathLineEdit(QLineEdit):
    pattern = (
        r'^(\\\\.*|\/.*|[A-Z]:\\(?:([^<>:"\/\\|?*]*[^<>:"\/\\|?*.]\\|..\\)'
        r'*([^<>:"\/\\|?*]*[^<>:"\/\\|?*.]\\?|..\\))?)$'
    )

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._default_tooltip = tr("Windows/Unix compatible characters")
        self._invalid_toolip = tr("Invalid path format")
        self.is_valid = False
        self.setMaxLength(254)
        self.setToolTip(self._default_tooltip)
        self.textChanged.connect(self.validate_path)

    def _clear_actions(self):
        for action in self.actions():
            self.removeAction(action)

    def validate_path(self, path: str):
        self._clear_actions()
        is_valid = bool(re.match(self.pattern, path))
        if path and not is_valid:
            icon = QIcon(QPixmap(icons.WARNING))
            self.addAction(icon, QLineEdit.ActionPosition.TrailingPosition)
            self.setToolTip(self._invalid_toolip)
            self.is_valid = is_valid
        else:
            self.setToolTip(self._default_tooltip)
            self.is_valid = is_valid


class BasePathSelectorWidget(QWidget):
    FILE_MODE = QFileDialog.FileMode.ExistingFile
    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.path_lineedit = CrossPlatformPathLineEdit()
        self.tool_btn = QToolButton()
        self.tool_btn.setText("...")
        self.tool_btn.clicked.connect(self.select_file)

        layout.addWidget(self.path_lineedit)
        layout.addWidget(self.tool_btn)

        self.path_lineedit.setFixedHeight(self.tool_btn.sizeHint().height())

    def text(self) -> str:
        return self.path_lineedit.text()

    def setText(self, text: str):
        self.path_lineedit.setText(text)

    def setPlaceholderText(self, text: str):
        self.path_lineedit.setPlaceholderText(text)

    def select_file(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(self.FILE_MODE)
        _ = Path(self.get_path())
        if _.exists():
            if _.is_dir():
                file_dialog.setDirectory(str(_))
            else:
                file_dialog.setDirectory(str(_.parent))

        if not file_dialog.exec():
            return

        selected_files = file_dialog.selectedFiles()
        if selected_files:
            file_path = os.path.normpath(selected_files[0])
            self.path_lineedit.setText(file_path)
            self.selected.emit(file_path)

    def set_path(self, path: str):
        return self.path_lineedit.setText(path)

    def get_path(self) -> str:
        return self.path_lineedit.text()

    def validate_path(self):
        return self.path_lineedit.is_valid


class FilePathSelectorWidget(BasePathSelectorWidget):
    pass


class FolderPathSelectorWidget(BasePathSelectorWidget):
    FILE_MODE = QFileDialog.FileMode.Directory
