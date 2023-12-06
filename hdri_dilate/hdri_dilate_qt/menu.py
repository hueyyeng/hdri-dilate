from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMenuBar

from hdri_dilate.hdri_dilate_qt import get_app_instance, tr


class MainWindowMenuBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)

        # File menu
        file_menu = QMenu(tr("&File"), self)
        file_exit_action = QAction(tr("E&xit"), self)
        file_exit_action.triggered.connect(self._exit)
        file_menu.addActions(
            [
                file_exit_action,
            ]
        )
        self.addMenu(file_menu)

        # View menu
        view_menu = QMenu(tr("&View"), self)
        view_toggle_theme_action = QAction(tr("Toggle &Theme"), self)
        view_toggle_theme_action.triggered.connect(self._toggle_theme)
        view_toggle_theme_action.setShortcut(Qt.Key.Key_F2)
        view_toggle_theme_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        view_menu.addAction(view_toggle_theme_action)
        self.addMenu(view_menu)

    def _toggle_theme(self):
        app = get_app_instance()
        app.main_window.toggle_theme()

    def _exit(self):
        app = get_app_instance()
        app.exit(0)
