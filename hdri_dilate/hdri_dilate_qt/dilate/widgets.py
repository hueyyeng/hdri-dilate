from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hdri_dilate.hdri_dilate_qt.main_window import (
        MainWindow,
    )

import cv2
import numpy as np
from PySide6.QtWidgets import *

from hdri_dilate.constants import DOUBLE_LINEBREAKS
from hdri_dilate.exr import get_exr_header, write_exr
from hdri_dilate.hdri_dilate_qt import tr
from hdri_dilate.hdri_dilate_qt.dilate.workers import (
    DilateWorker,
)
from hdri_dilate.hdri_dilate_qt.workers import (
    run_worker_in_thread,
)
from hdri_dilate.plotting import (
    save_four_way,
    show_four_way,
)


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
                f"{DOUBLE_LINEBREAKS[0]}"
                f"Terminate Early: {self.parent_.terminate_early_checkbox.isChecked()}"
            )
            text3 = (
                f"Final Intensity Multiplier: {self.parent_.final_intensity_multiplier_spinbox.value()}"
                f"{DOUBLE_LINEBREAKS[0]}"
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
                mask_thresh_exr_header = exr_header.copy()

                mask_thresh = output_path / f"{image_path.stem}_mask_threshold.exr"
                mask_dilated = output_path / f"{image_path.stem}_mask_dilated.exr"
                hdri_dilated = output_path / f"{image_path.stem}_dilated.exr"

                write_exr(
                    self.output_mask_thresh,
                    mask_thresh,
                    mask_thresh_exr_header,
                )
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
