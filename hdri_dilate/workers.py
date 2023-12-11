from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import MainWindow

import cv2
import numpy as np
from PySide6.QtCore import Signal

from hdri_dilate.enums import MorphShape
from hdri_dilate.exr import load_exr
from hdri_dilate.hdri_dilate_qt import qWait, tr
from hdri_dilate.hdri_dilate_qt.workers import (
    Worker,
    WorkerSignals,
)

logger = logging.getLogger()


def get_morph_shape(shape: str):
    if shape == MorphShape.CROSS:
        return cv2.MORPH_CROSS

    if shape == MorphShape.ELLIPSIS:
        return cv2.MORPH_ELLIPSE

    return cv2.MORPH_RECT


class DilateWorkerSignals(WorkerSignals):
    progress = Signal(int)
    progress_max = Signal(int)
    progress_stage = Signal(str)

    output_mask_thresh = Signal(object)
    output_mask_dilated = Signal(object)
    output_hdri_original = Signal(object)
    output_hdri_dilated = Signal(object)

    export_four_way = Signal(str, str, tuple)


class DilateWorker(Worker):
    def __init__(self, parent: "MainWindow", *args, **kwargs):
        super().__init__()
        self.parent = parent
        self.args = args
        self.kwargs = kwargs
        self.signals = DilateWorkerSignals()
        self.active = False

        self.threshold_mask = None
        self.hdri_dilated = None
        self.dilated_cc_mask = None
        self.temp_dilated_cc_mask = None
        self.intersection = None

        self.iteration = 0
        self.image_path = ""
        self.intensity = 15.0
        self.threshold = 1.0
        self.dilate_iteration = 3
        self.dilate_size = 2  # FIXME: Using high dilate size is slow...
        self.dilate_shape = MorphShape.RECTANGLE
        self.use_bgr_order = False
        self.use_blur = True
        self.blur_size = 3
        self.mask_intensity = (1.0, 1.0, 1.0)

        self.total_cc = 0
        self.checkpoint_iteration = 0
        self.iteration_cap = 100

        self.element = cv2.getStructuringElement(
            get_morph_shape(self.dilate_shape),
            (self.dilate_size * self.dilate_iteration + 1, self.dilate_size * self.dilate_iteration + 1),
            (self.dilate_iteration, self.dilate_iteration)
        )

    def _export_four_way(self, dilated_cc_mask):
        if not self.active:
            return

        images = (
            dilated_cc_mask,
            self.temp_dilated_cc_mask,
            self.threshold_mask,
            self.intersection,
        )
        path = Path(self.image_path)
        title = f"{path.stem.lower()} - CC {self.cc_count} - Iteration {self.iteration}"
        input_filename = path.stem.lower()
        output_dir = Path("export") / input_filename
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"export/{input_filename}/{input_filename}_cc_{self.cc_count:04}_itr_{self.iteration:04}.png"
        self.signals.export_four_way.emit(
            title,
            filename,
            images
        )
        qWait(300)

    # FIXME: Suspecting recursive dilate is not releasing memory
    def _dilate(
        self,
        cc_labels,
        cc_label,
        hdri_input,
        cc_mask=None,
        dilated_mask_preview=None,
    ):
        if not self.active:
            return

        self.iteration += 1
        if self.iteration > self.checkpoint_iteration + self.iteration_cap:
            self.checkpoint_iteration += self.iteration_cap
            self.signals.progress_stage.emit(
                tr(
                    "Average Pixel Value Iteration is taking longer than usual. "
                    "Please wait..."
                ).format(self.iteration)
            )
            self.signals.progress.emit(0)
            self.signals.progress_max.emit(0)

        if cc_mask is None:
            cc_mask = (cc_labels == cc_label).astype(np.uint8) * 255

        self.dilated_cc_mask = cv2.dilate(
            cc_mask,
            self.element,
        )
        self.temp_dilated_cc_mask = cv2.subtract(self.threshold_mask, self.dilated_cc_mask)
        self.intersection = cv2.bitwise_and(self.dilated_cc_mask, self.temp_dilated_cc_mask)
        is_intersect = np.any(self.intersection > 0)
        is_export_debug = self.parent.export_debug_dilate_checkbox.isChecked()
        export_debug_interval = self.parent.export_debug_dilate_interval_spinbox.value()
        if is_export_debug and self.iteration % export_debug_interval == 0:
            self._export_four_way(self.dilated_cc_mask)

        hdri_channels_averaged = cv2.mean(hdri_input, mask=cc_mask)[:3]
        is_exceeded_threshold = any(channel >= self.threshold for channel in hdri_channels_averaged)

        print(
            f"Iteration {self.iteration} - CC {cc_label} = "
            f"Exceed Threshold {self.threshold}? {'Y' if is_exceeded_threshold else 'N'} - "
            f"Intersect? {'Y' if is_intersect else 'N'} - "
            f"Average Pixel Value: {hdri_channels_averaged}"
        )

        if is_exceeded_threshold:
            self._dilate(
                cc_labels,
                cc_label,
                hdri_input,
                dilated_mask_preview=dilated_mask_preview,
                cc_mask=self.dilated_cc_mask,
            )

        elif self.use_blur:
            # TODO: Blurring is working but not the composite process
            dilated_cc_mask = self.dilated_cc_mask.astype(np.uint8)
            kernel_sizes = (self.blur_size, self.blur_size)
            dilated_cc_mask = cv2.GaussianBlur(
                dilated_cc_mask,
                kernel_sizes,
                0,
            )

            self.hdri_dilated[dilated_cc_mask > 0] = hdri_channels_averaged
            if dilated_mask_preview is not None:
                dilated_mask_preview[dilated_cc_mask > 0] = self.mask_intensity

            if is_export_debug:
                self._export_four_way(dilated_cc_mask)

        else:
            dilated_cc_mask = self.dilated_cc_mask.astype(np.uint8)
            self.hdri_dilated[dilated_cc_mask > 0] = hdri_channels_averaged
            if dilated_mask_preview is not None:
                dilated_mask_preview[dilated_cc_mask > 0] = self.mask_intensity

            if is_export_debug:
                self._export_four_way(dilated_cc_mask)

    def _run(self):
        self.image_path = self.parent.image_path_lineedit.get_path()
        self.intensity = self.parent.intensity_spinbox.value()
        self.threshold = self.parent.threshold_spinbox.value()
        self.dilate_iteration = self.parent.dilate_iteration_spinbox.value()
        self.dilate_size = self.parent.dilate_size_spinbox.value()
        self.dilate_shape = self.parent.dilate_shape_combobox.currentText()
        self.use_bgr_order = self.parent.use_bgr_order_checkbox.isChecked()
        self.use_blur = self.parent.use_blur_checkbox.isChecked()
        self.blur_size = self.parent.blur_size_spinbox.value()

        _image_path = Path(self.image_path)

        loading_msg = tr(
            "Loading image... {0}"
        ).format(_image_path.name)
        self.signals.progress_stage.emit(loading_msg)

        if not _image_path.exists():
            msg = tr(
                "The specified path does not exist: {0}"
            ).format(str(_image_path))

            raise FileNotFoundError(msg)

        if _image_path.suffix.lower() == ".exr":
            hdri_input = load_exr(
                self.image_path,
                use_bgr_order=self.use_bgr_order,
            )
            hdri_original = load_exr(
                self.image_path,
                use_bgr_order=self.use_bgr_order,
            )

        # Assume valid .hdr file
        else:
            hdri_input = cv2.imread(
                self.image_path,
                flags=cv2.IMREAD_ANYDEPTH,
            )
            hdri_original = cv2.imread(
                self.image_path,
                flags=cv2.IMREAD_ANYDEPTH,
            )

        self.hdri_dilated = hdri_original.copy()
        self.signals.progress_stage.emit(tr("Image loaded"))

        # Prepare Kernel
        self.element = cv2.getStructuringElement(
            get_morph_shape(self.dilate_shape),
            (self.dilate_size * self.dilate_iteration + 1, self.dilate_size * self.dilate_iteration + 1),
            (self.dilate_iteration, self.dilate_iteration)
        )

        # Find saturated pixels (saturated here refers to
        # pixel value intensity, not color saturation)
        self.signals.progress_stage.emit(tr("Processing mask..."))
        saturated_mask = (hdri_input > self.intensity).astype(np.uint8) * 255
        saturated_mask_grayscale = cv2.cvtColor(saturated_mask, cv2.COLOR_BGR2GRAY)
        self.threshold_mask = cv2.threshold(
            saturated_mask_grayscale,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]
        output = cv2.connectedComponentsWithStats(self.threshold_mask, connectivity=8)
        _, cc_labels, stats, _ = output

        dilated_mask_preview = np.zeros(hdri_input.shape, dtype=np.uint8)

        labels_mb_size = round(cc_labels.nbytes / 1024 / 1024, 2)
        self.signals.progress_stage.emit(f"CC Labels Memory {labels_mb_size} MB")
        saturated_mask_mb_size = round(saturated_mask.nbytes / 1024 / 1024, 2)
        self.signals.progress_stage.emit(f"Saturated Mask Memory {saturated_mask_mb_size} MB")
        saturated_mask_grayscale_mb_size = round(saturated_mask_grayscale.nbytes / 1024 / 1024, 2)
        self.signals.progress_stage.emit(f"Saturated Mask Grayscale Memory {saturated_mask_grayscale_mb_size} MB")

        self.total_cc = len(stats)
        found_cc_msg = tr(
            "Found {0} connected components"
        ).format(self.total_cc)
        self.signals.progress_stage.emit(found_cc_msg)
        self.signals.progress_stage.emit(tr("Processing and dilating connected components"))

        self.cc_count = 0
        for cc_label in range(1, self.total_cc):
            if not self.active:
                self.signals.progress_stage.emit(tr("Aborting!"))
                qWait(1000)
                self.signals.progress_stage.emit(tr("You can safely close this window."))
                return

            self.signals.progress_max.emit(self.total_cc)

            # Extract connected component
            self.cc_count += 1
            self.iteration = 0
            self.checkpoint_iteration = 0
            print("-----------------------------------------")
            print(f"Connected Component Loop ", self.cc_count)
            print("=========================================")

            self.signals.progress.emit(self.cc_count)

            self._dilate(
                cc_labels,
                cc_label,
                hdri_input,
                dilated_mask_preview=dilated_mask_preview,
            )

        self.signals.progress_max.emit(len(stats))

        dilated_threshold_mask = cv2.threshold(
            dilated_mask_preview,
            0,
            255,
            cv2.THRESH_BINARY
        )[1]

        self.signals.output_mask_thresh.emit(self.threshold_mask)
        self.signals.output_mask_dilated.emit(dilated_threshold_mask)
        self.signals.output_hdri_original.emit(hdri_original)
        self.signals.output_hdri_dilated.emit(self.hdri_dilated)

        self.signals.progress_stage.emit(tr("Done processing"))

        if self.parent.show_debug_preview_checkbox.isChecked():
            self.signals.progress_stage.emit(tr("Generating 4-Way Debug Preview sheet..."))

    def cancel(self):
        warning_msg = tr(
            "Interrupted by user! "
            "Exiting..."
        )
        logger.warning(warning_msg)
        self.active = False

    def run(self):
        # Better to pause 0.2 sec in case of busy network/disk/CPU blah
        qWait(200)

        self.active = True
        self.signals.started.emit()

        try:
            self.measure_time(self._run)
        except Exception as e:
            self.log_error(e)

        self.signals.finished.emit()
