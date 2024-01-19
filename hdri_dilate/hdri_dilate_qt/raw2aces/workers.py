from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pyexiv2

if TYPE_CHECKING:
    from hdri_dilate.hdri_dilate_qt.raw2aces.widgets import Raw2AcesFormWidget

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QBrush, QColor

from hdri_dilate.exr import get_exr_header, write_exr_header
from hdri_dilate.hdri_dilate_qt import qWait, tr
from hdri_dilate.hdri_dilate_qt.workers import (
    Worker,
    WorkerSignals,
)

logger = logging.getLogger()


class Raw2AcesWorkerSignals(WorkerSignals):
    progress = Signal(int)
    progress_max = Signal(int)
    progress_file = Signal(str)
    progress_stage = Signal(str)


class Raw2AcesWorker(Worker):
    def __init__(self, parent: "Raw2AcesFormWidget", *args, **kwargs):
        super().__init__()
        self.parent = parent
        self.args = args
        self.kwargs = kwargs
        self.signals = Raw2AcesWorkerSignals()
        self.active = False

    def _run(self):
        model = self.parent.parent_.model
        parent = self.parent
        r2a_exe = Path(parent.r2a_path_lineedit.get_path())
        if not r2a_exe.exists():
            self.parent.run_btn.setText("rawtoaces.exe not found!")
            qWait(1500)
            self.parent.run_btn.setText("Run")
            return

        cmd = (
            f"{parent.r2a_path_lineedit.get_path()} "
            f"--wb-method {parent.white_balance_combobox.currentIndex()} "
            f"--mat-method {parent.matrix_combobox.currentIndex()} "
            f"--headroom {parent.headroom_spinbox.value()} "
        )
        count = model.rowCount()
        self.signals.progress_max.emit(count + 1)
        for row_idx in range(count):
            self.signals.progress.emit(row_idx + 1)
            if not self.active:
                return

            input_item = model.item(row_idx, 0)
            output_item = model.item(row_idx, 1)
            status_item = model.item(row_idx, 2)

            done = input_item.data(Qt.ItemDataRole.UserRole)
            if done is True:
                status_item.setText("SKIPPED! ALREADY PROCESSED")
                continue

            status_item.setText("PROCESSING")
            file_name = input_item.text()
            self.signals.progress_file.emit(file_name)
            print(f"{cmd=}")
            new_cmd = cmd + file_name
            print(f"{new_cmd=}")
            process = subprocess.Popen(
                new_cmd.split(),
                stdout=subprocess.PIPE,
            )
            output, error = process.communicate()
            print(output.decode())
            if error:
                print(error.decode())
                input_item.setBackground(QBrush(QColor(255, 40, 46)))
                status_item.setText("ERROR")
            else:

                img = pyexiv2.Image(file_name)
                exif_data = img.read_exif()
                aperture: str = exif_data["Exif.Photo.FNumber"]
                expTime: str = exif_data["Exif.Photo.ExposureTime"]
                isoSpeed: str = exif_data["Exif.Photo.ISOSpeedRatings"]

                try:
                    foo, bar = aperture.split("/")
                    aperture_value = int(foo) / int(bar)
                except ValueError:
                    aperture_value = 0.0

                try:
                    foo, bar = expTime.split("/")
                    exposure_value = int(foo) / int(bar)
                except ValueError:
                    exposure_value = 0.0

                raw_path = Path(file_name)
                raw_stem = raw_path.stem
                exr_path = raw_path.parent / f"{raw_stem}_aces.exr"
                exr_header = get_exr_header(str(exr_path))

                exr_header["aperture"] = float(aperture_value)
                exr_header["expTime"] = float(exposure_value)
                exr_header["isoSpeed"] = float(isoSpeed)

                try:
                    write_exr_header(exr_path, exr_path, exr_header)
                    output_item.setText(str(exr_path))
                    status_item.setText(f"DONE!")
                    input_item.setData(True, Qt.ItemDataRole.UserRole)
                    input_item.setBackground(QBrush(QColor(40, 220, 10)))
                except Exception as e:
                    status_item.setText(f"ERROR! {e}")
                    input_item.setData(False, Qt.ItemDataRole.UserRole)
                    input_item.setBackground(QBrush(QColor(255, 40, 46)))

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
