from __future__ import annotations

import logging
import subprocess
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

import pyexiv2

if TYPE_CHECKING:
    from hdri_dilate.hdri_dilate_qt.raw2aces.widgets import Raw2AcesFormWidget

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor

from hdri_dilate.exr import get_exr_header, write_exr_header
from hdri_dilate.hdri_dilate_qt import qWait, tr
from hdri_dilate.hdri_dilate_qt.raw2aces.models import (
    Raw2AcesStatusItem,
)
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
        parent = self.parent
        r2a_exe = Path(parent.r2a_path_lineedit.get_path())
        if not r2a_exe.exists():
            self.parent.run_btn.setText("rawtoaces.exe not found!")
            qWait(1500)
            self.parent.run_btn.setText("Run")
            return

        model = parent.parent_.model
        max_process_count = parent.process_count_spinbox.value()
        max_tries = 2

        cmd = (
            f"{parent.r2a_path_lineedit.get_path()} "
            f"--wb-method {parent.white_balance_combobox.currentIndex()} "
            f"--mat-method {parent.matrix_combobox.currentIndex()} "
            f"--headroom {parent.headroom_spinbox.value()} "
        )
        commands: list[tuple[str, int, int]] = []
        count = model.rowCount()
        self.signals.progress_max.emit(count + 1)
        for row_idx in range(count):
            self.signals.progress.emit(row_idx + 1)
            if not self.active:
                return

            input_item = model.item(row_idx, 0)
            status_item = model.item(row_idx, 2)

            is_done = status_item.get_status() == Raw2AcesStatusItem.DONE
            if is_done:
                msg = "Skipped! Already processed"
                status_item.msg = msg
                status_item.setText(msg)
                continue

            file_name = input_item.text()
            self.signals.progress_file.emit(file_name)
            new_cmd = cmd + file_name
            commands.append((new_cmd, row_idx, 1))

        waiting = deque(commands)
        running = deque()

        while len(waiting) > 0 or len(running) > 0:
            print(f'Running: {len(running)}, Waiting: {len(waiting)}')

            # start new jobs
            while len(waiting) > 0 and len(running) < max_process_count:
                command, _row_idx, tries = waiting.popleft()
                try:
                    status_item: Raw2AcesStatusItem = model.item(_row_idx, 2)
                    status_item.setText("PROCESSING")
                    running.append((subprocess.Popen(command), command, _row_idx, tries))
                    print(f"Started task {command}")
                except OSError:
                    print(f'Failed to start command {command}')

            # check running commands
            for _ in range(len(running)):
                process, command, _row_idx, tries = running.popleft()
                output, error = process.communicate()

                input_item = model.item(_row_idx, 0)
                output_item = model.item(_row_idx, 1)
                status_item: Raw2AcesStatusItem = model.item(_row_idx, 2)

                if error:
                    if tries < max_tries:
                        waiting.append((command, _row_idx, tries + 1))
                    else:
                        print(f"Command: {command} error-ed after {max_tries} tries")
                else:
                    input_file = command.split(" ")[-1]
                    img = pyexiv2.Image(input_file)
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

                    raw_path = Path(input_file)
                    raw_stem = raw_path.stem
                    exr_path = raw_path.parent / f"{raw_stem}_aces.exr"
                    exr_header = get_exr_header(str(exr_path))
                    exr_header["aperture"] = float(aperture_value)
                    exr_header["expTime"] = float(exposure_value)
                    exr_header["isoSpeed"] = float(isoSpeed)

                    try:
                        write_exr_header(exr_path, exr_path, exr_header)
                        output_item.setText(str(exr_path))
                        status_item.set_status(Raw2AcesStatusItem.DONE)
                        input_item.setData(True, Qt.ItemDataRole.UserRole)
                        input_item.setBackground(QBrush(QColor(40, 220, 10)))
                    except Exception as e:
                        status_item.set_error_status(str(e))
                        input_item.setData(False, Qt.ItemDataRole.UserRole)
                        input_item.setBackground(QBrush(QColor(255, 40, 46)))

        print(f"All tasks finished")

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
