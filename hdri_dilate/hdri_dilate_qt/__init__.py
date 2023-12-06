from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import Application

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication


def tr(text: str):
    return QObject.tr(text)


def qWait(msec: int):
    """Implementation of PyQt's qWait for PySide"""
    start = time.time()
    QApplication.processEvents()
    while time.time() < start + msec * 0.001:
        QApplication.processEvents()


def get_app_instance() -> Application:
    return QApplication.instance()
