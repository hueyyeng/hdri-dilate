from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent, QPixmap, QStandardItem
from PySide6.QtWidgets import QApplication, QWidgetItem

from hdri_dilate import settings
from hdri_dilate.hdri_dilate_qt.main_window import (
    MainWindow,
)


class Application(QApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setApplicationName(settings.APP_NAME)
        self.setApplicationVersion(settings.APP_VERSION)

        self.setWindowIcon(QPixmap(str(settings.WINDOW_ICON)))

        self.main_window: MainWindow = MainWindow()
        self.main_window.setWindowTitle(f"{settings.APP_NAME} - {settings.APP_VERSION}")
        self.main_window.show()

    # https://stackoverflow.com/a/64902020/8337847
    # Using QApplication notify to set application wide shortcut
    def notify(self, receiver: QObject, event: QEvent) -> bool:
        # Weird hack to prevent "Windows fatal exception: access violation"
        if isinstance(receiver, QStandardItem) or isinstance(event, QStandardItem):
            return True

        if event.type() == QEvent.Type.KeyPress:
            key_event = QKeyEvent(event)
            if key_event.key() == Qt.Key.Key_F2 and self.main_window:
                self.main_window.toggle_theme()
                return True

        # Possible weird fix for QWidgetItem widget reorder
        if isinstance(receiver, QWidgetItem):
            return False

        return super().notify(receiver, event)
