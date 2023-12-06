from typing import Tuple

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate.constants import DOUBLE_LINEBREAKS

MESSAGEBOX_TYPE = Tuple[str, int]


class NewMessageBox(QMessageBox):
    width_padding = 8
    height_padding = round(width_padding / 2)

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setStyleSheet(
            f"""
            QPushButton {{
                min-width: 64px;
                padding-top: {self.height_padding}px;
                padding-bottom: {self.height_padding}px;
                padding-left: {self.width_padding}px;
                padding-right: {self.width_padding}px;
            }}
            """
        )

    def setup_ui(self, title: str, text: str, button0: MESSAGEBOX_TYPE = None, button1: MESSAGEBOX_TYPE = None):
        self.setWindowTitle(title)
        self.setText(text)

        if button0:
            self.addButton(*button0)
        else:
            self.addButton(QMessageBox.StandardButton.Ok)

        if button1:
            self.addButton(*button1)

    def information(self, title: str, text: str, button0: MESSAGEBOX_TYPE = None, button1: MESSAGEBOX_TYPE = None):
        self.setIcon(QMessageBox.Icon.Information)
        self.setup_ui(title, text, button0=button0, button1=button1)
        return self.exec_()

    def warning(self, title: str, text: str, button0: MESSAGEBOX_TYPE = None, button1: MESSAGEBOX_TYPE = None):
        self.setIcon(QMessageBox.Icon.Warning)
        self.setup_ui(title, text, button0=button0, button1=button1)
        return self.exec_()

    def critical(self, title: str, text: str, button0: MESSAGEBOX_TYPE = None, button1: MESSAGEBOX_TYPE = None):
        self.setIcon(QMessageBox.Icon.Critical)
        self.setup_ui(title, text, button0=button0, button1=button1)
        return self.exec_()

    def question(self, title: str, text: str, button0: MESSAGEBOX_TYPE = None, button1: MESSAGEBOX_TYPE = None):
        self.setIcon(QMessageBox.Icon.Question)
        self.setup_ui(title, text, button0=button0, button1=button1)
        return self.exec_()


class ProceedMessageBox(NewMessageBox):
    def setup_ui(self, title: str, text: str, button0: MESSAGEBOX_TYPE = None, button1: MESSAGEBOX_TYPE = None):
        self.setWindowTitle(title)
        self.setText(text)

        self.addButton("Proceed", QMessageBox.ButtonRole.AcceptRole)
        self.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)


class ErrorReportMessageBox(NewMessageBox):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

    def setup_ui(self, title: str, text: str, button0: MESSAGEBOX_TYPE = None, button1: MESSAGEBOX_TYPE = None):
        self.setWindowTitle(title)
        self.setText(text)

        self.addButton("Close", QMessageBox.ButtonRole.RejectRole)


class LaunchErrorMessageBox(ErrorReportMessageBox):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.setWindowTitle("Launch Fatal Error")
        self.setIcon(self.Icon.Critical)
        text = (
            f"Something went wrong when launching HDRI Dilate."
            f"{DOUBLE_LINEBREAKS}"
            f"An error report has been generated. Please try again."
        )
        self.setText(text)
        self.addButton("Close", QMessageBox.ButtonRole.RejectRole)
