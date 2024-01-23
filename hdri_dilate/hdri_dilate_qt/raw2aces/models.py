from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from hdri_dilate.hdri_dilate_qt import tr


class Raw2AcesStatusItem(QStandardItem):
    READY = 0
    PROCESSING = 1
    DONE = 2
    WARNING = 3
    ERROR = 4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._status_labels = {
            0: tr("READY"),
            1: tr("PROCESSING"),
            2: tr("DONE"),
            3: tr("WARNING"),
            4: tr("ERROR"),
        }
        self.msg = ""
        self.setData(0, Qt.ItemDataRole.UserRole)

    @classmethod
    def from_status(cls, status: int):
        instance = cls()
        instance.set_status(status)
        return instance

    def refresh(self):
        try:
            label = self._status_labels[self.get_status()]
        except KeyError:
            raise Exception(tr("Invalid status value!"))

        if self.msg:
            label = f"{label}: {self.msg}"

        self.setText(label)

    def set_status(self, status: int):
        try:
            label = self._status_labels[status]
        except KeyError:
            raise Exception(tr("Invalid status value!"))

        self.setData(status, Qt.ItemDataRole.UserRole)
        self.setText(label)

    def set_warning_status(self, msg: str):
        self.setData(self.WARNING, Qt.ItemDataRole.UserRole)
        self.msg = msg
        self.setText(f"WARNING: {msg}")

    def set_error_status(self, msg: str):
        self.setData(self.ERROR, Qt.ItemDataRole.UserRole)
        self.msg = msg
        self.setText(f"ERROR: {msg}")

    def get_status(self) -> int:
        return self.data(Qt.ItemDataRole.UserRole)


class Raw2AcesModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reset_headers()

    def reset_headers(self):
        self.setHorizontalHeaderLabels(
            [
                "Input",
                "Output",
                "Status",
            ]
        )

    def reset(self):
        self.clear()
        self.reset_headers()
