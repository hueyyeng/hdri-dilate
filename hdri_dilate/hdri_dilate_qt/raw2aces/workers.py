from __future__ import annotations

import datetime
import logging
import os
import subprocess
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

import pyexiv2

if TYPE_CHECKING:
    from hdri_dilate.hdri_dilate_qt.raw2aces.widgets import (
        Raw2AcesFormWidget,
        Raw2AcesExrRenamerDialog,
    )

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QStandardItem, QStandardItemModel

from hdri_dilate.exr import get_exr_header, write_exr_header
from hdri_dilate.hdri_dilate_qt import qWait, tr
from hdri_dilate.hdri_dilate_qt.raw2aces import (
    get_desktop_path,
    renamer,
)
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


class Raw2AcesColumnIndex:
    INPUT = 0
    OUTPUT = 1
    STATUS = 2


class Raw2AcesWorker(Worker):
    def __init__(self, parent: Raw2AcesFormWidget, *args, **kwargs):
        super().__init__()
        self.parent = parent
        self.args = args
        self.kwargs = kwargs
        self.signals = Raw2AcesWorkerSignals()
        self.active = False
        self.exr_files: list[Path] = []

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

        r2a_path = f'"{parent.r2a_path_lineedit.get_path()}"'

        if parent.white_balance_custom_lineedit.isEnabled():
            cmd = (
                rf"{r2a_path} "
                rf"--wb-method {parent.white_balance_combobox.currentIndex()} "
                rf"{parent.white_balance_custom_lineedit.text()} "
                rf"--mat-method {parent.matrix_combobox.currentIndex()} "
                rf"--headroom {parent.headroom_spinbox.value()} "
            )
        else:
            cmd = (
                rf"{r2a_path} "
                rf"--wb-method {parent.white_balance_combobox.currentIndex()} "
                rf"--mat-method {parent.matrix_combobox.currentIndex()} "
                rf"--headroom {parent.headroom_spinbox.value()} "
            )

        commands: list[tuple[str, int, int]] = []
        count = model.rowCount()
        self.signals.progress_max.emit(count + 1)
        for row_idx in range(count):
            self.signals.progress.emit(row_idx + 1)
            if not self.active:
                return

            input_item = model.item(row_idx, Raw2AcesColumnIndex.INPUT)
            status_item = model.item(row_idx, Raw2AcesColumnIndex.STATUS)

            is_done = status_item.get_status() == Raw2AcesStatusItem.DONE
            if is_done:
                msg = "Skipped! Already processed"
                status_item.msg = msg
                status_item.setText(msg)
                continue

            file_path = input_item.text()
            self.signals.progress_file.emit(file_path)
            new_cmd = cmd + rf'"{file_path}"'
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
                    process_ = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    running.append((process_, command, _row_idx, tries))
                    print(f"Started task {command}")
                except OSError:
                    print(f'Failed to start command {command}')

            # check running commands
            for _ in range(len(running)):
                process, command, _row_idx, tries = running.popleft()
                output, error = process.communicate()

                input_item = model.item(_row_idx, Raw2AcesColumnIndex.INPUT)
                output_item = model.item(_row_idx, Raw2AcesColumnIndex.OUTPUT)
                status_item: Raw2AcesStatusItem = model.item(_row_idx, Raw2AcesColumnIndex.STATUS)

                if error:
                    if tries < max_tries:
                        waiting.append((command, _row_idx, tries + 1))
                    else:
                        print(f"Command: {command} error-ed after {max_tries} tries")
                        status_item.set_error_status(error.decode().strip())
                        input_item.setData(False, Qt.ItemDataRole.UserRole)
                        input_item.setBackground(QBrush(QColor(255, 40, 46)))
                else:
                    # TODO: Hopefully should work on Linux environment
                    # /path/to/rawtoaces.exe --blah "D:\test4\White Space\test3\DSC07977.ARW"
                    # ['/path/to/rawtoaces.exe --blah ', 'D:\\test4\\White Space\\test3\\DSC07977.ARW', '']
                    input_file = command.split('"')[-2]
                    input_bytes = Path(input_file).read_bytes()
                    img = pyexiv2.ImageData(input_bytes)
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
                        self.exr_files.append(exr_path)
                        status_item.set_status(Raw2AcesStatusItem.DONE)
                        status_item.msg = ""
                        input_item.setData(True, Qt.ItemDataRole.UserRole)
                        input_item.setBackground(QBrush(QColor(40, 220, 10)))
                    except Exception as e:
                        status_item.set_error_status(str(e))
                        input_item.setData(False, Qt.ItemDataRole.UserRole)
                        input_item.setBackground(QBrush(QColor(255, 40, 46)))

        if not parent.rename_file_padding_checkbox.isChecked():
            print(f"All tasks finished")
            return

        count = 0
        logs: list[str] = []
        count_padding = f'%0{parent.seq_padding_length_spinbox.value()}d'

        try:
            for exr_file in sorted(self.exr_files):
                count += 1
                counter = count_padding % count
                filename = exr_file.stem
                file_ext = exr_file.suffix
                new_name = f"{filename}.{counter}{file_ext}"
                new_name_path = exr_file.parent / new_name
                exr_file.rename(new_name_path)
                log_text = f"{exr_file} -> {new_name}"
                logs.append(log_text)
        except (OSError, Exception) as e:
            pass

        self._save_renamed_log(logs)
        print(f"All tasks finished")

    def _save_renamed_log(self, logs: list[str]):
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%Y%m%d_%H%M%S")

        log_filename = f"renamed_exrs_{formatted_time}.log"
        log_file = Path(get_desktop_path()) / "raw2aces_logs" / log_filename
        log_file.parent.mkdir(exist_ok=True, parents=True)
        log_file.write_text("\n".join(logs))

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


class Raw2AcesDroppedWorkerSignals(WorkerSignals):
    progress = Signal(int)
    progress_task = Signal(str)
    progress_total = Signal(int)
    is_busy = Signal(bool)


class Raw2AcesDroppedWorker(Worker):
    def __init__(self, urls, parent: Raw2AcesExrRenamerDialog, *args, **kwargs):
        super().__init__()
        self.parent = parent
        self.urls = urls
        self.args = args
        self.kwargs = kwargs
        self.signals = Raw2AcesDroppedWorkerSignals()

    def add_file_item(self, file_path: str):
        parent = self.parent
        item = QStandardItem(file_path)
        model: QStandardItemModel = parent.model
        model.appendRow(item)
        item_idx = model.indexFromItem(item)

        raw_path = Path(file_path)
        raw_stem = raw_path.stem

        exr_path = raw_path.parent / f"{raw_stem}.exr"

        arw_path = raw_path.parent / f"{raw_stem.replace('_aces', '')}.ARW"
        arw_path_ = Path(arw_path)

        jpg_path = raw_path.parent / f"{raw_stem.replace('_aces', '')}.JPG"
        jpg_path_ = Path(jpg_path)

        input_bytes = None
        if jpg_path_.exists():
            input_bytes = jpg_path_.read_bytes()

        elif arw_path_.exists():
            input_bytes = arw_path_.read_bytes()

        sony_dsc_name_prefix = raw_stem[:8]
        arw_path = raw_path.parent / f"{sony_dsc_name_prefix}.ARW"
        arw_path_ = Path(arw_path)

        jpg_path = raw_path.parent / f"{sony_dsc_name_prefix}.JPG"
        jpg_path_ = Path(jpg_path)

        if jpg_path_.exists():
            input_bytes = jpg_path_.read_bytes()

        elif arw_path_.exists():
            input_bytes = arw_path_.read_bytes()

        if not input_bytes:
            raise OSError("Cannot find equivalent files for EXIF metadata!")

        img = pyexiv2.ImageData(input_bytes)
        exif_data = img.read_exif()
        dt: str = exif_data["Exif.Image.DateTime"]

        parent.exr_files.append(exr_path)

        output_item = QStandardItem()
        date_taken_item = QStandardItem(str(dt))
        status_item = Raw2AcesStatusItem.from_status(Raw2AcesStatusItem.READY)

        model.setItem(item_idx.row(), 1, output_item)
        model.setItem(item_idx.row(), 2, date_taken_item)
        model.setItem(item_idx.row(), 3, status_item)

        parent.treeview.files.add(file_path)

    def _run(self):
        self.signals.is_busy.emit(True)

        parent = self.parent
        urls = self.urls
        self.signals.progress_total.emit(len(urls))

        for file_idx, url in enumerate(urls):
            self.signals.progress.emit(file_idx + 1)
            file_path = os.path.normpath(url.toLocalFile())
            if file_path in parent.treeview.files:
                continue

            if not file_path.lower().endswith("exr"):
                continue

            self.add_file_item(file_path)

        parent.treeview.setSortingEnabled(True)
        parent.treeview.resizeColumnToContents(0)
        if parent.sort_by_date_taken_checkbox.isChecked():
            parent.treeview.sortByColumn(2, Qt.SortOrder.AscendingOrder)
        else:
            parent.treeview.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        renamer(parent)

    def run(self):
        self.active = True
        self.signals.started.emit()

        try:
            self.measure_time(self._run)
        except Exception as e:
            self.log_error(e)

        self.signals.is_busy.emit(False)
        self.signals.finished.emit()
