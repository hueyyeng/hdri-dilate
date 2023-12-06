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


def morph_shape(shape: str):
    print(f"{shape=}")
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


class DilateWorker(Worker):
    def __init__(self, parent: "MainWindow", *args, **kwargs):
        super().__init__()
        self.parent = parent
        self.args = args
        self.kwargs = kwargs
        self.signals = DilateWorkerSignals()
        self.active = False

        self.iteration = 0
        self.image_path = ""
        self.intensity = 15.0
        self.threshold = 1.0
        self.dilate_iteration = 1
        self.dilate_shape = MorphShape.RECTANGLE
        self.use_bgr_order = False
        self.use_blur = True
        self.blur_size = 3
        self.mask_intensity = (1.0, 1.0, 1.0)

        self.checkpoint_iteration = 0
        self.iteration_cap = 100

    def _dilate(
        self,
        cc_labels,
        cc_label,
        hdri_input,
        threshold_mask,
        cc_mask=None,
        dilated_mask_preview=None,
    ):
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

        bgr_channels_averaged = cv2.mean(hdri_input, mask=cc_mask)[:3]
        print(
            f"Dilate - Iteration {self.iteration} - Connected Component {cc_label} "
            f"Average Pixel Value: {bgr_channels_averaged}"
        )

        is_exceeded_threshold = any(channel >= self.threshold for channel in bgr_channels_averaged)

        dilate_shape = morph_shape(self.dilate_shape)
        self.signals.progress_stage.emit(f"Using Morph Shape {dilate_shape}")

        element = cv2.getStructuringElement(
            dilate_shape,
            (2 * self.dilate_iteration + 1, 2 * self.dilate_iteration + 1),
            (self.dilate_iteration, self.dilate_iteration)
        )
        dilated_cc_mask = cv2.dilate(
            cc_mask,
            element,
        )

        # dilated_cc_mask = cv2.dilate(
        #     cc_mask,
        #     None,
        #     iterations=self.dilate_iteration,
        # )

        dilated_cc_mask = np.bitwise_and(
            dilated_cc_mask,
            np.logical_not(threshold_mask),
        )

        # cv2.imshow(f"Connected Component {cc_label}", dilated_cc_mask[2])
        if is_exceeded_threshold:
            self._dilate(
                cc_labels,
                cc_label,
                hdri_input,
                threshold_mask,
                dilated_mask_preview=dilated_mask_preview,
                cc_mask=dilated_cc_mask,
            )

        elif self.use_blur:
            dilated_cc_mask = cv2.add(dilated_cc_mask, threshold_mask)
            dilated_cc_mask = dilated_cc_mask.astype(np.uint8)
            kernel_sizes = (self.blur_size, self.blur_size)
            dilated_cc_mask = cv2.GaussianBlur(
                dilated_cc_mask,
                kernel_sizes,
                0,
            )
            # TODO: Blurring is working but not the composite process
            # cv2.imshow("TEST", dilated_cc_mask)
            # cv2.waitKey(0)

            hdri_input[dilated_cc_mask > 0] = bgr_channels_averaged
            if dilated_mask_preview is not None:
                dilated_mask_preview[dilated_cc_mask > 0] = self.mask_intensity

        else:
            dilated_cc_mask = cv2.add(dilated_cc_mask, threshold_mask)
            dilated_cc_mask = dilated_cc_mask.astype(np.uint8)
            hdri_input[dilated_cc_mask > 0] = bgr_channels_averaged
            if dilated_mask_preview is not None:
                dilated_mask_preview[dilated_cc_mask > 0] = self.mask_intensity

    def _run(self):
        self.image_path = self.parent.image_path_lineedit.get_path()
        self.intensity = self.parent.intensity_spinbox.value()
        self.threshold = self.parent.threshold_spinbox.value()
        self.dilate_iteration = self.parent.dilate_iteration_spinbox.value()
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
            hdri_input = load_exr(self.image_path, use_bgr_order=self.use_bgr_order)
            hdri_original = load_exr(self.image_path, use_bgr_order=self.use_bgr_order)

        # Assume valid .hdr file
        else:
            hdri_input = cv2.imread(self.image_path, flags=cv2.IMREAD_ANYDEPTH)
            hdri_original = cv2.imread(self.image_path, flags=cv2.IMREAD_ANYDEPTH)

        self.signals.progress_stage.emit(tr("Image loaded"))

        # Find saturated pixels (saturated here refers to pixel value intensity, not color saturation)
        self.signals.progress_stage.emit(tr("Processing mask..."))
        dilated_mask_preview = np.zeros(hdri_input.shape, dtype=np.uint8)
        saturated_mask = (hdri_input > self.intensity).astype(np.uint8) * 255
        saturated_mask_grayscale = cv2.cvtColor(saturated_mask, cv2.COLOR_BGR2GRAY)
        threshold_mask = cv2.threshold(
            saturated_mask_grayscale,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]
        output = cv2.connectedComponentsWithStats(threshold_mask, connectivity=8)
        _, cc_labels, stats, _ = output

        found_cc_msg = tr(
            "Found {0} connected components"
        ).format(len(stats))
        self.signals.progress_stage.emit(found_cc_msg)
        self.signals.progress_stage.emit(tr("Processing and dilating connected components"))

        self.count = 0
        for cc_label in range(1, len(stats)):
            self.signals.progress_max.emit(len(stats))

            # Extract connected component
            self.count += 1
            self.iteration = 0
            self.checkpoint_iteration = 0
            print("--------------------------------------")
            print(f"Connected Component Loop ", self.count)
            print("--------------------------------------")

            self.signals.progress.emit(self.count)

            self._dilate(
                cc_labels,
                cc_label,
                hdri_input,
                threshold_mask,
                dilated_mask_preview=dilated_mask_preview,
            )

        self.signals.progress_max.emit(len(stats))

        dilated_threshold_mask = cv2.threshold(
            dilated_mask_preview,
            0,
            255,
            cv2.THRESH_BINARY
        )[1]

        self.signals.output_mask_thresh.emit(threshold_mask)
        self.signals.output_mask_dilated.emit(dilated_threshold_mask)
        self.signals.output_hdri_original.emit(hdri_original)
        self.signals.output_hdri_dilated.emit(hdri_input)

        self.signals.progress_stage.emit(tr("Done processing"))
        self.signals.progress_stage.emit(tr("Generating 4-Way sheets..."))

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
