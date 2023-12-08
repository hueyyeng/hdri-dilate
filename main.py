import logging
import os
import sys
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from comel.wrapper import ComelMainWindowWrapper
from matplotlib import pyplot as plt
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate import settings
from hdri_dilate.constants import DOUBLE_LINEBREAKS
from hdri_dilate.enums import MorphShape
from hdri_dilate.exr import get_exr_header, write_exr
from hdri_dilate.hdri_dilate_qt import qWait, tr
from hdri_dilate.hdri_dilate_qt.checkbox import CheckBox
from hdri_dilate.hdri_dilate_qt.collapsible import CollapsibleWidget
from hdri_dilate.hdri_dilate_qt.forms import (
    FormNoSideMargins,
)
from hdri_dilate.hdri_dilate_qt.inputs import (
    FilePathSelectorWidget, FolderPathSelectorWidget,
)
from hdri_dilate.hdri_dilate_qt.menu import (
    MainWindowMenuBar,
)
from hdri_dilate.hdri_dilate_qt.message_box import (
    LaunchErrorMessageBox,
)
from hdri_dilate.hdri_dilate_qt.sidebar import SidebarWidget
from hdri_dilate.hdri_dilate_qt.toolbars import (
    MainWindowToolBar, VerticalToolBar,
)
from hdri_dilate.hdri_dilate_qt.workers import (
    run_worker_in_thread,
)
from hdri_dilate.workers import DilateWorker

logger = logging.getLogger()

T_IMAGES = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]


def show_four_way(images: T_IMAGES, fig_title: str = None, fig_texts: Sequence[str] = None):
    titles = (
        "THRESHOLD MASK",
        "DILATED THRESHOLD MASK",
        "ORIGINAL",
        "PROCESSED",
    )
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

    if fig_title:
        plt.suptitle(
            fig_title,
            fontsize=10,
        )

    if fig_texts:
        distance = 1.0 / (len(fig_texts) + 1)
        x = 1.0 / (len(fig_texts) + 3)
        for fig_text in fig_texts:
            plt.figtext(
                x, 0.12,
                fig_text,
                verticalalignment="top",
                horizontalalignment="left",
                fontsize=10,
            )
            x += distance

    plt.show()


def save_four_way(fig_title: str, filename: str, images: T_IMAGES):
    print(f"{fig_title=}, {filename=}")
    titles = (
        "dilated_cc_mask",
        "temp_dilated_cc_mask",
        "threshold_mask",
        "intersection",
    )
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
        self.setWindowTitle(tr("Generating HDRI Dilate"))
        self.setup_ui()

        self.result_duration = 0.0
        self.worker = DilateWorker(self.parent_)
        self.run_worker()

    def _set_output_mask_thresh(self, output):
        self.output_mask_thresh: np.ndarray = output

    def _set_output_mask_dilated(self, output):
        self.output_mask_dilated: np.ndarray = output

    def _set_output_hdri_original(self, output):
        self.output_hdri_original: np.ndarray = output

    def _set_output_hdri_dilated(self, output):
        self.output_hdri_dilated: np.ndarray = output

    def _change_abort_to_close(self):
        self.abort_btn.setText("Close")
        self.abort_btn.clicked.disconnect()
        self.abort_btn.clicked.connect(self.close)

    def _append_result_duration(self, result_duration: float):
        self.result_duration = result_duration
        duration = f"{result_duration:0.4f}"
        result_msg = tr("Overall dilation process took {0} secs").format(duration)
        self.progress_textedit.appendPlainText(result_msg)

    def setup_ui(self):
        self.progress_textedit = QPlainTextEdit(self)
        self.progress_textedit.setReadOnly(True)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(0)

        self.abort_btn = QPushButton("Abort")
        self.abort_btn.setDefault(False)
        self.abort_btn.setAutoDefault(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.progress_textedit)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.abort_btn)

    def run_worker(self):
        worker = self.worker
        worker.signals.measure_time_result.connect(self._append_result_duration)
        worker.signals.progress.connect(self.progress_bar.setValue)
        worker.signals.progress_max.connect(self.progress_bar.setMaximum)
        worker.signals.progress_stage.connect(self.progress_textedit.appendPlainText)

        worker.signals.output_mask_thresh.connect(self._set_output_mask_thresh)
        worker.signals.output_mask_dilated.connect(self._set_output_mask_dilated)
        worker.signals.output_hdri_original.connect(self._set_output_hdri_original)
        worker.signals.output_hdri_dilated.connect(self._set_output_hdri_dilated)

        worker.signals.export_four_way.connect(save_four_way)
        self.abort_btn.clicked.connect(worker.cancel)

        run_worker_in_thread(
            worker,
            on_finish=self.post_run_worker
        )

    def post_run_worker(self):
        if not self.worker.active:
            self._change_abort_to_close()
            return

        self.progress_bar.setValue(self.progress_bar.maximum())
        images = (
            self.output_mask_thresh,
            self.output_mask_dilated,
            self.output_hdri_original,
            self.output_hdri_dilated,
        )
        if self.parent_.show_debug_preview_checkbox.isChecked():
            path = Path(self.parent_.image_path_lineedit.get_path())
            title = f"{path.name}"
            text1 = (
                f"Dilate Iteration: {self.parent_.dilate_iteration_spinbox.value()}"
                f"{DOUBLE_LINEBREAKS[0]}"
                f"Dilate Size: {self.parent_.dilate_size_spinbox.value()}"
                f"{DOUBLE_LINEBREAKS[0]}"
                f"Dilate Shape: {self.parent_.dilate_shape_combobox.currentText()}"
            )
            text2 = (
                f"Intensity: {self.parent_.intensity_spinbox.value()}"
                f"{DOUBLE_LINEBREAKS[0]}"
                f"Threshold: {self.parent_.threshold_spinbox.value()}"
            )
            text3 = (
                f"Use Blur: {self.parent_.use_blur_checkbox.isChecked()}"
                f"{DOUBLE_LINEBREAKS[0]}"
                f"Blur Size: {self.parent_.blur_size_spinbox.value()}"
            )
            texts = (
                text1,
                text2,
                text3,
            )
            show_four_way(images, title, texts)

        if self.parent_.save_output_checkbox.isChecked():
            output_path = Path(self.parent_.output_folder_lineedit.get_path())
            output_path.mkdir(parents=True, exist_ok=True)

            image_path = Path(self.parent_.image_path_lineedit.get_path())
            if image_path.suffix.casefold().endswith("exr"):
                exr_header = get_exr_header(
                    self.parent_.image_path_lineedit.get_path()
                )

                mask_thresh = output_path / f"{image_path.stem}_mask_threshold.exr"
                mask_dilated = output_path / f"{image_path.stem}_mask_dilated.exr"
                hdri_dilated = output_path / f"{image_path.stem}_dilated.exr"

                # write_exr(
                #     self.output_mask_thresh,
                #     mask_thresh,
                #     exr_header,
                # )
                write_exr(
                    self.output_mask_dilated,
                    mask_dilated,
                    exr_header,
                )
                write_exr(
                    self.output_hdri_dilated,
                    hdri_dilated,
                    exr_header,
                )

            else:
                mask_thresh = output_path / f"{image_path.stem}_mask_threshold.hdr"
                mask_dilated = output_path / f"{image_path.stem}_mask_dilated.hdr"
                hdri_dilated = output_path / f"{image_path.stem}_dilated.hdr"
                cv2.imwrite(str(mask_thresh), self.output_mask_thresh)
                cv2.imwrite(str(mask_dilated), self.output_mask_dilated)
                cv2.imwrite(str(hdri_dilated), self.output_hdri_dilated)

        self._change_abort_to_close()


class MainWindow(ComelMainWindowWrapper):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent=parent)
        self.threadpool = QThreadPool().globalInstance()
        self.setup_ui()
        self.setMinimumWidth(512)

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

        # # Sidebar widgets
        # self.sidebar_widget = SidebarWidget(self)
        # self.setCentralWidget(self.sidebar_widget)

        # Central Widget
        self.central_widget = VerticalToolBar(self)
        self.setCentralWidget(self.central_widget)

        # Form
        form = FormNoSideMargins(self)
        self.advanced_form = FormNoSideMargins(self)

        self.image_path_lineedit = FilePathSelectorWidget(self)
        self.image_path_lineedit.set_path(
            # r"D:\Projects\Work\hdri-tools\image\rural_asphalt_road_1k.exr"
            # r"D:\Projects\Work\hdri-tools\image\small_empty_room_2_1k.exr"
            r"D:\Projects\Work\hdri-tools\image\christmas_photo_studio_02_1k.exr"
        )

        self.output_folder_lineedit = FolderPathSelectorWidget(self)
        self.save_output_checkbox = CheckBox(self)
        self.save_output_checkbox.setChecked(True)

        self.export_debug_dilate_checkbox = CheckBox(self)
        self.export_debug_dilate_checkbox.setChecked(False)

        self.export_debug_dilate_interval_spinbox = QSpinBox(self)
        self.export_debug_dilate_interval_spinbox.setValue(10)
        self.export_debug_dilate_interval_spinbox.setMaximum(500)

        self.show_debug_preview_checkbox = CheckBox(self)
        self.show_debug_preview_checkbox.setChecked(False)

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

        self.dilate_size_spinbox = QSpinBox(self)
        self.dilate_size_spinbox.setValue(2)
        self.dilate_size_spinbox.setMinimum(2)
        self.dilate_size_spinbox.setMaximum(50)

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
        form.addRow(tr("Output Folder"), self.output_folder_lineedit)
        form.addRow(tr("Save Output"), self.save_output_checkbox)
        form.addRow(tr("Intensity"), self.intensity_spinbox)
        form.addRow(tr("Threshold"), self.threshold_spinbox)

        self.advanced_form.addRow(tr("Dilate Size (px)"), self.dilate_size_spinbox)
        self.advanced_form.addRow(tr("Dilate Iteration"), self.dilate_iteration_spinbox)
        self.advanced_form.addRow(tr("Dilate Shape"), self.dilate_shape_combobox)
        self.advanced_form.addRow(tr("Use BGR Order"), self.use_bgr_order_checkbox)
        self.advanced_form.addRow(tr("Use Blur"), self.use_blur_checkbox)
        self.advanced_form.addRow(tr("Blur Size (px)"), self.blur_size_spinbox)
        self.advanced_form.addRow(tr("Export Debug Dilate Figures?"), self.export_debug_dilate_checkbox)
        self.advanced_form.addRow(tr("Export Debug Dilate Interval"), self.export_debug_dilate_interval_spinbox)
        self.advanced_form.addRow(tr("Show Debug Preview?"), self.show_debug_preview_checkbox)

        self.generate_btn = QPushButton(tr("Generate"))
        self.generate_btn.clicked.connect(self.generate)

        advanced_settings = CollapsibleWidget("Advanced Settings")
        advanced_settings.addWidget(self.advanced_form)
        advanced_settings.collapse()

        self.central_widget.addWidget(form)
        self.central_widget.addWidget(advanced_settings)
        self.central_widget.addWidget(self.generate_btn)
        self.central_widget.addStretch()

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
        self.setApplicationDisplayName(f"{settings.APP_NAME} - {settings.APP_VERSION}")
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
