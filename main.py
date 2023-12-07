import logging
import os
import sys
from pathlib import Path

import cv2
import numpy
from comel.wrapper import ComelMainWindowWrapper
from matplotlib import pyplot as plt
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate import settings
from hdri_dilate.enums import MorphShape
from hdri_dilate.exr import write_exr, get_exr_header
from hdri_dilate.hdri_dilate_qt import qWait, tr
from hdri_dilate.hdri_dilate_qt.checkbox import CheckBox
from hdri_dilate.hdri_dilate_qt.forms import (
    FormNoSideMargins,
)
from hdri_dilate.hdri_dilate_qt.inputs import (
    FilePathSelectorWidget,
)
from hdri_dilate.hdri_dilate_qt.menu import (
    MainWindowMenuBar,
)
from hdri_dilate.hdri_dilate_qt.message_box import (
    LaunchErrorMessageBox,
)
from hdri_dilate.hdri_dilate_qt.sidebar import SidebarWidget
from hdri_dilate.hdri_dilate_qt.toolbars import (
    MainWindowToolBar,
)
from hdri_dilate.hdri_dilate_qt.workers import (
    run_worker_in_thread,
)
from hdri_dilate.workers import DilateWorker

logger = logging.getLogger()


def show_four_way(images: list[numpy.ndarray]):
    titles = [
        "THRESHOLD MASK",
        "DILATED THRESHOLD MASK",
        "ORIGINAL",
        "PROCESSED",
    ]
    fig, axes = plt.subplots(
        nrows=2,
        ncols=2,
        figsize=(10, 10),
        tight_layout=False,
    )
    axes = axes.flatten()
    for ax, image, title in zip(axes, images, titles):
        ax.imshow(image)
        ax.set(title=title)
        ax.axis("off")

    plt.show()


def save_four_way(fig_title: str, filename: str, images: list[numpy.ndarray]):
    print(f"{fig_title=}, {filename=}")
    titles = [
        "dilated_cc_mask",
        "temp_dilated_cc_mask",
        "threshold_mask",
        "intersection",
    ]
    fig, axes = plt.subplots(
        nrows=2,
        ncols=2,
        figsize=(10, 10),
        tight_layout=False,
    )
    axes = axes.flatten()
    for ax, image, title in zip(axes, images, titles):
        ax.imshow(image)
        ax.set(title=title)
        ax.axis("off")

    plt.suptitle(fig_title)
    plt.savefig(filename)
    plt.close()


class DilateProgressDialog(QDialog):
    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self.parent_ = parent
        # self.output_mask_thresh = None
        # self.output_mask_dilated = None
        # self.output_hdri_original = None
        # self.output_hdri_dilated = None

        self.setWindowTitle(tr("Generating HDRI Dilate"))
        self.setup_ui()
        self.run_worker()

    def _set_output_mask_thresh(self, output):
        self.output_mask_thresh = output

    def _set_output_mask_dilated(self, output):
        self.output_mask_dilated = output

    def _set_output_hdri_original(self, output):
        self.output_hdri_original = output

    def _set_output_hdri_dilated(self, output):
        self.output_hdri_dilated = output

    def setup_ui(self):
        self.progress_textedit = QPlainTextEdit(self)
        self.progress_textedit.setReadOnly(True)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(0)

        layout = QVBoxLayout(self)
        layout.addWidget(self.progress_textedit)
        layout.addWidget(self.progress_bar)

    def run_worker(self):
        worker = DilateWorker(self.parent_)
        worker.signals.progress.connect(self.progress_bar.setValue)
        worker.signals.progress_max.connect(self.progress_bar.setMaximum)
        worker.signals.progress_stage.connect(self.progress_textedit.appendPlainText)

        worker.signals.output_mask_thresh.connect(self._set_output_mask_thresh)
        worker.signals.output_mask_dilated.connect(self._set_output_mask_dilated)
        worker.signals.output_hdri_original.connect(self._set_output_hdri_original)
        worker.signals.output_hdri_dilated.connect(self._set_output_hdri_dilated)

        worker.signals.foo.connect(save_four_way)

        run_worker_in_thread(
            worker,
            on_finish=self.post_run_worker
        )

    def post_run_worker(self):
        self.progress_bar.setValue(self.progress_bar.maximum())
        images = [
            self.output_mask_thresh,
            self.output_mask_dilated,
            self.output_hdri_original,
            self.output_hdri_dilated,
        ]
        image_path = Path(self.parent_.image_path_lineedit.get_path())
        if image_path.suffix.casefold().endswith("exr"):
            exr_header = get_exr_header(
                self.parent_.image_path_lineedit.get_path()
            )

        # write_exr(
        #     self.output_mask_thresh,
        #     "output_mask_threshold.exr",
        #     exr_header,
        # )
        # write_exr(
        #     self.output_mask_dilated,
        #     "output_mask_dilated.exr",
        #     exr_header,
        # )
        # cv2.imwrite('image/output_mask_thresh.hdr', self.output_mask_thresh,)
        # cv2.imwrite('image/output_mask_dilated.hdr', self.output_mask_dilated,)
        #
        # write_exr(
        #     self.output_hdri_original,
        #     "output_hdri_original.exr",
        #     exr_header,
        # )
        # write_exr(
        #     self.output_hdri_dilated,
        #     "output_hdri_dilated.exr",
        #     exr_header,
        # )
        show_four_way(images)


class MainWindow(ComelMainWindowWrapper):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent=parent)
        self.threadpool = QThreadPool().globalInstance()
        self.setup_ui()

    def closeEvent(self, event):
        plt.close("all")
        cv2.destroyAllWindows()
        super().closeEvent(event)

    def setup_ui(self):
        # Required for DockWidget to dock into DockWidget
        self.setDockNestingEnabled(True)

        # Toolbar
        self.toolbar = MainWindowToolBar(self)
        self.addToolBar(self.toolbar)
        self.setup_toolbar()

        # Menu bar
        self.menu_bar = MainWindowMenuBar(self)
        self.setMenuBar(self.menu_bar)

        # Sidebar widgets
        self.sidebar_widget = SidebarWidget(self)
        self.setCentralWidget(self.sidebar_widget)

        # Form
        form = FormNoSideMargins(self)

        self.image_path_lineedit = FilePathSelectorWidget(self)
        self.image_path_lineedit.set_path(
            # r"D:\Projects\Work\hdri-tools\image\rural_asphalt_road_1k.exr"
            # r"D:\Projects\Work\hdri-tools\image\small_empty_room_2_1k.exr"
            r"D:\Projects\Work\hdri-tools\image\christmas_photo_studio_02_1k.exr"
        )
        self.use_bgr_order_checkbox = CheckBox(self)
        self.use_bgr_order_checkbox.setChecked(False)
        self.use_blur_checkbox = CheckBox(self)
        self.use_blur_checkbox.setChecked(True)

        self.blur_size_spinbox = QSpinBox(self)
        self.blur_size_spinbox.setValue(3)
        self.blur_size_spinbox.editingFinished.connect(self.odd_blur_size)
        self.blur_size_spinbox.setMinimum(3)
        self.blur_size_spinbox.setMaximum(99)
        self.blur_size_spinbox.setSingleStep(2)

        self.dilate_iteration_spinbox = QSpinBox(self)
        self.dilate_iteration_spinbox.setValue(3)
        self.dilate_iteration_spinbox.setMaximum(50)

        self.intensity_spinbox = QDoubleSpinBox(self)
        self.intensity_spinbox.setValue(15.0)
        self.intensity_spinbox.setSingleStep(0.1)

        self.threshold_spinbox = QDoubleSpinBox(self)
        self.threshold_spinbox.setValue(1.0)
        self.threshold_spinbox.setSingleStep(0.1)

        self.dilate_shape_combobox = QComboBox(self)
        self.dilate_shape_combobox.addItems(
            [
                MorphShape.RECTANGLE,
                MorphShape.CROSS,
                MorphShape.ELLIPSIS,
            ]
        )
        self.dilate_shape_combobox.setCurrentText(MorphShape.ELLIPSIS)

        form.addRow(tr("EXR/HDR Path"), self.image_path_lineedit)
        form.addRow(tr("Intensity"), self.intensity_spinbox)
        form.addRow(tr("Threshold"), self.threshold_spinbox)
        form.addRow(tr("Dilate Iteration"), self.dilate_iteration_spinbox)
        form.addRow(tr("Dilate Shape"), self.dilate_shape_combobox)
        form.addRow(tr("Use BGR Order"), self.use_bgr_order_checkbox)
        form.addRow(tr("Use Blur"), self.use_blur_checkbox)
        form.addRow(tr("Blur Size (px)"), self.blur_size_spinbox)

        self.generate_btn = QPushButton(tr("Generate"))
        self.generate_btn.clicked.connect(self.generate)

        self.sidebar_widget.addWidget(form)
        self.sidebar_widget.addWidget(self.generate_btn)

    def odd_blur_size(self):
        blur_size = self.blur_size_spinbox.value()
        if blur_size % 2 == 0:
            self.blur_size_spinbox.setValue(blur_size - 1)

    def setup_toolbar(self):
        ...

    def generate(self):
        dialog = DilateProgressDialog(self)
        dialog.show()


class Application(QApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setApplicationName(settings.APP_NAME)
        self.setApplicationDisplayName(settings.APP_NAME)
        self.setApplicationVersion(settings.APP_VERSION)

        self.setWindowIcon(QPixmap(str(settings.WINDOW_ICON)))

        self.main_window: MainWindow = MainWindow()
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


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    QDir.addSearchPath(
        "icons",
        os.path.join(root, "hdri_dilate/resources/icons")
    )

    try:
        app = Application([])
        sys.exit(app.exec())
    except Exception as e:
        logger.error(e, exc_info=True)
        logger.debug("Fatal Error: %s", str(e))
        mb = LaunchErrorMessageBox()
        mb.setDetailedText(f"{e}")
        mb.exec()


if __name__ == "__main__":
    main()
