from __future__ import annotations

import csv
import datetime
import json
import os
import time
from pathlib import Path

import pyexiv2
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate.constants import icons
from hdri_dilate.exr import get_exr_header
from hdri_dilate.hdri_dilate_qt import tr
from hdri_dilate.hdri_dilate_qt.checkbox import CheckBox
from hdri_dilate.hdri_dilate_qt.forms import (
    FormNoSideMargins,
)
from hdri_dilate.hdri_dilate_qt.inputs import (
    FilePathSelectorWidget,
)
from hdri_dilate.hdri_dilate_qt.message_box import (
    NewMessageBox,
)
from hdri_dilate.hdri_dilate_qt.raw2aces import get_desktop_path, renamer
from hdri_dilate.hdri_dilate_qt.raw2aces.models import (
    Raw2AcesModel,
    Raw2AcesStatusItem, Raw2AcesExrRenamerModel,
)
from hdri_dilate.hdri_dilate_qt.raw2aces.workers import (
    Raw2AcesWorker, Raw2AcesDroppedWorker,
)
from hdri_dilate.hdri_dilate_qt.workers import (
    run_worker_in_thread,
)

RAW_FORMATS = (
    "*.CR2",
    "*.RAF",
    "*.RW2",
    "*.ERF",
    "*.NRW",
    "*.NEF",
    "*.ARW",
    "*.RWZ",
    "*.EIP",
    "*.DNG",
    "*.BAY",
    "*.DCR",
    "*.GPR",
    "*.RAW",
    "*.CRW",
    "*.3FR",
    "*.SR2",
    "*.K25",
    "*.KC2",
    "*.MEF",
    "*.DNG",
    "*.CS1",
    "*.ORF",
    "*.MOS",
    "*.KDC",
    "*.CR3",
    "*.ARI",
    "*.SRF",
    "*.SRW",
    "*.J6I",
    "*.FFF",
    "*.MRW",
    "*.MFW",
    "*.RWL",
    "*.X3F",
    "*.PEF",
    "*.IIQ",
    "*.CXI",
    "*.NKSC",
    "*.MDC",
)


class PropertyModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reset_headers()

    def reset_headers(self):
        self.setHorizontalHeaderLabels(
            [
                "Property",
                "Value",
            ]
        )

    def reset(self):
        self.clear()
        self.reset_headers()


class SearchLineEdit(QLineEdit):
    placeholder_text = "Search Property"

    def __init__(self, proxy: QSortFilterProxyModel, parent=None):
        super().__init__(parent=parent)
        self.setClearButtonEnabled(True)
        self.setPlaceholderText(self.placeholder_text)
        self.textChanged.connect(proxy.setFilterRegularExpression)


class PropertyProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterRole(Qt.ItemDataRole.DisplayRole)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)


class PropertyTreeView(QTreeView):
    def __init__(self, parent: PropertyPanelWidget):
        super().__init__(parent)
        self.setSortingEnabled(True)
        self.setRootIsDecorated(False)

        self.is_file_selected: bool = False
        self.is_file_valid: bool = False

    def paintEvent(self, e: QPaintEvent):
        super().paintEvent(e)
        if self.model() and self.model().rowCount() > 0:
            return

        msg = tr("Invalid/No Metadata")
        if not self.is_file_selected and not self.is_file_valid:
            msg = tr("Select a file to view metadata")

        p = QPainter(self.viewport())
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)


class PropertyPanelWidget(QWidget):
    property_selected = Signal(str)
    keywords = (
        "Exif.Photo.FNumber",
        "Exif.Photo.ISOSpeedRatings",
        "Exif.Photo.ExposureTime",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = PropertyModel()
        self.proxy_model = PropertyProxyModel()
        self.proxy_model.setSourceModel(self.model)

        self.search_lineedit = SearchLineEdit(self.proxy_model, self)
        self.search_lineedit.setText("")
        self.treeview = PropertyTreeView(self)
        # self.treeview.clicked.connect(self.get_property_name)
        self.treeview.setModel(self.proxy_model)

        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(self.search_lineedit)
        layout.addWidget(self.treeview)

    def populate(self, data: dict | None):
        self.model.reset()

        # FIXME: Simplify this condition checking
        self.treeview.is_file_selected = True
        self.treeview.is_file_valid = True
        if data is None:
            self.treeview.is_file_selected = False
            self.treeview.is_file_valid = False
            return

        if data is False:
            self.treeview.is_file_selected = True
            self.treeview.is_file_valid = False
            return

        keywords_color = QColor("#ffb8e9")
        for k, v in data.items():
            property_item = QStandardItem()
            property_item.setEditable(False)
            property_item.setText(k)
            property_item.setData(v, Qt.ItemDataRole.UserRole)

            value_item = QStandardItem()
            value_item.setEditable(False)
            value_item.setText(str(v))

            if k in self.keywords:
                property_item.setBackground(QBrush(keywords_color))
                value_item.setBackground(QBrush(keywords_color))

            self.model.appendRow(
                [
                    property_item,
                    value_item,
                ]
            )

        self.treeview.resizeColumnToContents(0)

    def get_property_name(self, index: QModelIndex):
        proxy_model: PropertyProxyModel = index.model()
        model: PropertyModel = proxy_model.sourceModel()
        idx = proxy_model.mapToSource(index)
        idx = idx.siblingAtColumn(0)
        item: QStandardItem = model.itemFromIndex(idx)
        property_text = item.text()
        self.property_selected.emit(property_text)


class FilePathToolbar(QWidget):
    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.path_lineedit = QLineEdit()
        self.path_lineedit.setPlaceholderText("Select Folder")
        self.path_lineedit.returnPressed.connect(self._return_pressed)
        layout.addWidget(self.path_lineedit)
        self.tool_btn = QToolButton()
        self.tool_btn.setText("Browse")
        self.tool_btn.clicked.connect(self.select)
        layout.addWidget(self.tool_btn)

    def _return_pressed(self):
        file_path = self.get_path()
        self.path_lineedit.setText(file_path)
        self.selected.emit(file_path)

    def select(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.Directory)

        if not file_dialog.exec():
            return

        selected_files = file_dialog.selectedFiles()
        if selected_files:
            file_path = os.path.normpath(selected_files[0])
            self.path_lineedit.setText(file_path)
            self.selected.emit(file_path)

    def set_path(self, path: str):
        return self.path_lineedit.setText(path)

    def get_path(self) -> str:
        return self.path_lineedit.text()


class ImageOnlyFileSystemModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setNameFilters(
            (
                "*.jpg",
                "*.jpeg",
                "*.tif",
                "*.tiff",
                "*.exr",
                "*.hdr",
                *RAW_FORMATS,
            )
        )
        self.setNameFilterDisables(False)
        self.setRootPath("")


class FileBrowserWidget(QWidget):
    exif_founded = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_ = parent
        self.layout_ = QVBoxLayout(self)
        self.setLayout(self.layout_)

        self.fsm = ImageOnlyFileSystemModel(self)

        self.toolbar = FilePathToolbar(self)
        self.toolbar.selected.connect(self.set_fsm_path)
        self.layout_.addWidget(self.toolbar)

        self.fsm_treeview = QTreeView(self)
        self.fsm_treeview.setSelectionMode(self.fsm_treeview.SelectionMode.ExtendedSelection)
        self.fsm_treeview.setSortingEnabled(True)
        self.fsm_treeview.clicked.connect(self._load_metadata)
        self.fsm_treeview.setModel(self.fsm)
        self.fsm_treeview.selectionModel().selectionChanged.connect(self._load_metadata_changed)
        self.fsm_treeview.setColumnWidth(0, 200)
        self.layout_.addWidget(self.fsm_treeview)

    def set_fsm_path(self, folder_path: str):
        self.exif_founded.emit(None)
        self.fsm_treeview.setRootIndex(
            self.fsm.index(folder_path)
        )
        self.fsm_treeview.resizeColumnToContents(1)

    def _load_metadata_changed(self):
        idx = self.fsm_treeview.currentIndex()
        idx = idx.siblingAtColumn(0)
        self._load_metadata(idx)

    def _load_metadata(self, idx: QModelIndex):
        if not idx:
            self.exif_founded.emit(False)
            return

        file_path = self.fsm.filePath(idx)
        fp = Path(file_path)
        if not fp.is_file():
            self.exif_founded.emit(False)
            return

        if "exr" in fp.suffix.lower():
            data = get_exr_header(str(fp))
            self.exif_founded.emit(data)
        else:
            try:
                img = pyexiv2.Image(str(fp))
                data = img.read_exif()
                self.exif_founded.emit(data)
            except (RuntimeError, Exception):
                print("Unsupported file")
                self.exif_founded.emit(False)


class ExrRawMetadataViewerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EXR/RAW Metadata Viewer")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setGeometry(100, 100, 800, 600)

        layout = QHBoxLayout(self)

        self.file_browser = FileBrowserWidget(self)
        self.property_panel = PropertyPanelWidget(self)

        layout.addWidget(self.file_browser)
        layout.addWidget(self.property_panel)

        self.file_browser.exif_founded.connect(self.property_panel.populate)


class Raw2AcesContainer(QSplitter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setChildrenCollapsible(False)
        self.setContentsMargins(0, 0, 0, 0)
        self.setHandleWidth(8)
        self.setObjectName(f"{self.__class__.__name__}")
        self.setOrientation(Qt.Orientation.Vertical)


class Raw2AcesRunBtn(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAutoDefault(False)
        self.spinner = QMovie(icons.SPINNER)
        self.default_text = "Run"
        self.spinner_text = "Processing"
        self.setStyleSheet(
            """
            QPushButton:disabled {
                color: #CACACA;
                background-color: #DF5E5E;
            }
            """
        )

    def start_spinner(self):
        self.spinner.frameChanged.connect(self.update_spinner)
        self.spinner.start()

    def update_spinner(self):
        self.setEnabled(False)
        self.setText(self.spinner_text)
        self.setIcon(QIcon(self.spinner.currentPixmap()))

    def stop_spinner(self):
        self.spinner.stop()
        self.setIcon(QIcon())
        self.setText(self.default_text)
        self.setEnabled(True)


class Raw2AcesFileTreeView(QTreeView):
    def __init__(self, parent: Raw2AcesDialog):
        super().__init__(parent)
        self.setSortingEnabled(True)
        self.setRootIsDecorated(False)

        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QTreeView.SelectionMode.SingleSelection)

        self.files = set()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = os.path.normpath(url.toLocalFile())
                if file_path in self.files:
                    continue

                file_format = f"*{file_path[-4:]}"
                if file_format not in RAW_FORMATS:
                    continue

                self.add_file_item(file_path)

    def add_file_item(self, file_path: str):
        item = QStandardItem(file_path)
        model: QStandardItemModel = self.model()
        model.appendRow(item)
        item_idx = model.indexFromItem(item)

        raw_path = Path(file_path)
        raw_stem = raw_path.stem
        exr_path = raw_path.parent / f"{raw_stem}_aces.exr"
        if exr_path.exists():
            status_item = Raw2AcesStatusItem()
            status_item.set_warning_status(
                "Found existing aces exr file. Will be overridden!"
            )
        else:
            status_item = Raw2AcesStatusItem.from_status(Raw2AcesStatusItem.READY)

        output_item = QStandardItem()
        model.setItem(item_idx.row(), 1, output_item)
        model.setItem(item_idx.row(), 2, status_item)

        self.files.add(file_path)

    def paintEvent(self, e: QPaintEvent):
        if self.model() and self.model().rowCount() > 0:
            super().paintEvent(e)
            return

        msg = tr("Drag and drop supported RAW files here")
        p = QPainter(self.viewport())
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)


class Raw2AcesFileWidget(QWidget):
    def __init__(self, parent: Raw2AcesDialog):
        super().__init__(parent)
        self.parent_ = parent
        self.layout_ = QVBoxLayout(self)
        self._treeview: Raw2AcesFileTreeView | None = None

        self.clear_btn = QPushButton(tr("Clear"))
        self.clear_btn.setToolTip(tr("Clear file list"))

        self.export_list_btn = QPushButton(tr("Export JSON"))
        self.export_list_btn.setToolTip(tr("Export file list and settings to JSON"))

        self.import_list_btn = QPushButton(tr("Import JSON"))
        self.import_list_btn.setToolTip(tr("Import file list and settings from JSON"))

        self.clear_btn.clicked.connect(self._clear)
        self.export_list_btn.clicked.connect(self._export)
        self.import_list_btn.clicked.connect(self._import)

        self.clear_btn.setAutoDefault(False)
        self.export_list_btn.setAutoDefault(False)
        self.import_list_btn.setAutoDefault(False)

        self.clear_btn.setEnabled(False)
        self.export_list_btn.setEnabled(False)
        self.import_list_btn.setEnabled(False)

        btn_layout = QHBoxLayout(self)
        btn_layout.addWidget(self.import_list_btn)
        btn_layout.addWidget(self.export_list_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clear_btn)

        self.layout_.addLayout(btn_layout)

    def add_treeview(self, widget: Raw2AcesFileTreeView):
        if self._treeview is None:
            self.layout_.addWidget(widget)
            self._treeview = widget
            self.clear_btn.setEnabled(True)
            self.export_list_btn.setEnabled(True)
            self.import_list_btn.setEnabled(True)

    def _clear(self):
        model: Raw2AcesModel = self._treeview.model()
        model.reset()
        self._treeview.files.clear()

    def _import(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("JSON (*.json)")
        if not file_dialog.exec():
            return

        selected_files = file_dialog.selectedFiles()
        if not selected_files:
            return

        file_path = os.path.normpath(selected_files[0])
        with open(file_path, "r") as f:
            data = json.load(f)

        self.parent_.populate_settings(data["settings"])

        model: Raw2AcesModel = self._treeview.model()
        model.reset()
        for row_data in data["model"]:
            status, msg = row_data[2]
            status_item = Raw2AcesStatusItem.from_status(status)
            status_item.msg = msg
            status_item.refresh()
            row = [
                QStandardItem(row_data[0]),
                QStandardItem(row_data[1]),
                status_item,
            ]
            model.appendRow(row)

    def _export(self):
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%Y%m%d_%H%M%S")

        temp_filename = f"rawtoaces_export_{formatted_time}.json"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save JSON File"),
            temp_filename,
            tr("JSON (*.json)"),
        )
        if not filename:
            return

        model: Raw2AcesModel = self._treeview.model()
        model_data = []
        for row_idx in range(model.rowCount()):
            input_item: QStandardItem = model.item(row_idx, 0)
            output_item: QStandardItem = model.item(row_idx, 1)
            status_item: Raw2AcesStatusItem = model.item(row_idx, 2)
            row_data = [
                input_item.text(),
                output_item.text(),
                [
                    status_item.get_status(),
                    status_item.msg,
                ],
            ]
            model_data.append(row_data)

        data = {
            "datetime": current_time.isoformat(),
            "settings": self.parent_.get_settings(),
            "model": model_data,
        }

        with open(filename, "w+") as f:
            f.write(json.dumps(data, indent=4))


class Raw2AcesFormWidget(FormNoSideMargins):
    def __init__(self, parent: Raw2AcesDialog):
        super().__init__(parent)
        self.parent_ = parent
        self.r2a_path_lineedit = FilePathSelectorWidget(self)
        self.white_balance_combobox = QComboBox(self)
        self.white_balance_combobox.setToolTip(
            tr(
                "White balance factor calculation method. "
                "Default 0"
            )
        )
        self.white_balance_combobox.addItems(
            [
                tr("0 - Use File Metadata"),
                tr("1 - User specified illuminant [str]"),
                tr("2 - Average the whole image for white balance"),
                tr("3 - Average a grey box for white balance <x y w h>"),
                tr("4 - Use Custom White Balance <r g b g>"),
            ]
        )
        self.white_balance_combobox.currentIndexChanged.connect(self._check_white_balance)

        self.white_balance_custom_lineedit = QLineEdit()
        self.white_balance_custom_lineedit.setToolTip(
            tr("The custom parameter for White Balance Mode 1, 3, 4")
        )
        self.white_balance_custom_lineedit.setEnabled(False)

        self.white_balance_help_label = QLabel("")

        self.matrix_combobox = QComboBox(self)
        self.matrix_combobox.setToolTip(
            tr(
                "IDT matrix calculation method. "
                "Default 0"
            )
        )
        self.matrix_combobox.addItems(
            [
                tr("0 - Calculate matrix from camera spec sens"),
                tr("1 - Use file metadata color matrix"),
                tr("2 - Use Adobe coeffs included in libraw"),
            ]
        )
        self.matrix_combobox.setCurrentIndex(1)

        self.headroom_spinbox = QDoubleSpinBox(self)
        self.headroom_spinbox.setToolTip(
            tr("Set highlight headroom factor. Default 6.00")
        )
        self.headroom_spinbox.setMinimum(0.01)
        self.headroom_spinbox.setMaximum(100.00)
        self.headroom_spinbox.setValue(6.00)
        self.headroom_spinbox.setSingleStep(0.10)

        self.process_count_spinbox = QSpinBox(self)
        self.process_count_spinbox.setEnabled(False)
        self.process_count_spinbox.setToolTip(
            tr("Max rawtoaces.exe process count to spawn. Default 2")
        )
        self.process_count_spinbox.setMinimum(1)
        self.process_count_spinbox.setMaximum(10)
        self.process_count_spinbox.setValue(2)

        self.process_count_preset_combobox = QComboBox(self)
        self.process_count_preset_combobox.setToolTip(
            tr("Process count presets")
        )
        self.process_count_preset_combobox.addItem(
            tr("Safe (slowest but suitable for background process) - 1"), 1
        )
        self.process_count_preset_combobox.addItem(
            tr("HDD - 2"), 2
        )
        self.process_count_preset_combobox.addItem(
            tr("SSD (use lower value if the program hangs frequently) - 5"), 5
        )
        self.process_count_preset_combobox.addItem(
            tr("Custom"), None
        )
        self.process_count_preset_combobox.setCurrentIndex(1)
        self.process_count_preset_combobox.currentIndexChanged.connect(self._set_process_count)

        self.rename_file_padding_checkbox = CheckBox(self)
        self.rename_file_padding_checkbox.toggled.connect(self._rename_toggled)
        self.rename_file_padding_checkbox.setToolTip(
            tr(
                "Rename the output EXR file with sequential padding. "
                "E.g. DSC02024.00000.exr, DSC02025.00001.exr"
            )
        )

        self.seq_padding_length_spinbox = QSpinBox(self)
        self.seq_padding_length_spinbox.setEnabled(False)
        self.seq_padding_length_spinbox.setToolTip(
            tr("The sequence padding length. E.g. Value of 5 is represented as 00001.")
        )
        self.seq_padding_length_spinbox.setMinimum(3)
        self.seq_padding_length_spinbox.setMaximum(10)
        self.seq_padding_length_spinbox.setValue(5)

        self.addRow("rawtoaces.exe path", self.r2a_path_lineedit)
        self.addRow("White Balance", self.white_balance_combobox)
        self.addRow("White Balance Custom Arg", self.white_balance_custom_lineedit)
        self.addRow("", self.white_balance_help_label)
        self.addRow("IDT Matrix Calculation", self.matrix_combobox)
        self.addRow("Highlight Headroom", self.headroom_spinbox)
        self.addRow("rawtoaces.exe Process Count Presets", self.process_count_preset_combobox)
        self.addRow("rawtoaces.exe Process Count", self.process_count_spinbox)
        self.addRow("Rename File with Sequence Padding", self.rename_file_padding_checkbox)
        self.addRow("Sequence Padding Length", self.seq_padding_length_spinbox)

        self.run_btn = Raw2AcesRunBtn("Run")
        self.run_btn.clicked.connect(self._run)
        self.addRow("", self.run_btn)

        r2a_exe = Path(os.getcwd()) / "hdri_dilate" / "resources" / "bin" / "rawtoaces.exe"
        if not r2a_exe.exists():
            # Workaround for pyinstaller _internal folder...
            r2a_exe = Path(os.getcwd()) / "_internal" / "hdri_dilate" / "resources" / "bin" / "rawtoaces.exe"

        if r2a_exe.exists():
            self.r2a_path_lineedit.set_path(str(r2a_exe))
        else:
            self.r2a_path_lineedit.setPlaceholderText(
                tr("rawtoaces.exe not found in default location! Specify the path manually.")
            )

    def _rename_toggled(self):
        checked = self.rename_file_padding_checkbox.isChecked()
        self.seq_padding_length_spinbox.setEnabled(checked)

    def _check_white_balance(self):
        value = self.white_balance_combobox.currentIndex()
        special_modes = {
            1: 'The name of the illuminant e.g. "D60", "3500K"',
            3: 'The position of the grey box e.g. "100 200 320 240"',
            4: 'The custom white balance in float e.g. "1.0 0.5 0.2 0.5"',
        }

        label = ""
        enabled = False
        if value in special_modes:
            enabled = True
            label = special_modes[value]

        self.white_balance_help_label.setText(label)
        self.white_balance_custom_lineedit.setEnabled(enabled)

    def _set_process_count(self):
        value = self.process_count_preset_combobox.currentData()
        if value is None:
            self.process_count_spinbox.setEnabled(True)
        else:
            self.process_count_spinbox.setEnabled(False)
            self.process_count_spinbox.setValue(value)

    def _validate_r2a_exe(self) -> bool:
        r2a_exe = Path(self.r2a_path_lineedit.get_path())
        if r2a_exe.exists():
            return True

        title = tr("Warning")
        msg = tr("rawtoaces.exe not found!")
        NewMessageBox(self).warning(
            title=title,
            text=msg,
        )
        return False

    def _run(self):
        if not self._validate_r2a_exe():
            return

        btn = self.run_btn
        btn.start_spinner()
        worker = Raw2AcesWorker(self)
        run_worker_in_thread(
            worker,
            on_finish=btn.stop_spinner
        )


class Raw2AcesDialog(QDialog):
    width_padding = 8
    height_padding = round(width_padding / 2)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"""
              QPushButton {{
                  min-width: 64px;
                  padding-top: {self.height_padding}px;
                  padding-bottom: {self.height_padding}px;
                  padding-left: {self.width_padding}px;
                  padding-right: {self.width_padding}px;
              }}
              """
        )
        self.setWindowTitle("Raw2Aces Converter")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setGeometry(100, 100, 800, 600)

        self.settings = Raw2AcesFormWidget(self)
        self.treeview = Raw2AcesFileTreeView(self)
        self.file_widget = Raw2AcesFileWidget(self)
        self.file_widget.add_treeview(self.treeview)
        self.model = Raw2AcesModel(self)
        self.treeview.setModel(self.model)

        container = Raw2AcesContainer(self)
        container.addWidget(self.settings)
        container.addWidget(self.file_widget)
        container.setStretchFactor(0, 0)
        container.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(container)

    def get_settings(self) -> dict:
        settings = {
            "white_balance": self.settings.white_balance_combobox.currentIndex(),
            "white_balance_custom": self.settings.white_balance_custom_lineedit.text(),
            "matrix": self.settings.matrix_combobox.currentIndex(),
            "headroom": self.settings.headroom_spinbox.value(),
            "process_count": self.settings.process_count_spinbox.value(),
            "process_count_preset": self.settings.process_count_preset_combobox.currentIndex(),
        }
        return settings

    def populate_settings(self, settings: dict):
        self.settings.white_balance_combobox.setCurrentIndex(settings["white_balance"])
        self.settings.white_balance_custom_lineedit.setText(settings["white_balance_custom"])
        self.settings.matrix_combobox.setCurrentIndex(settings["matrix"])
        self.settings.headroom_spinbox.setValue(settings["headroom"])
        self.settings.process_count_spinbox.setValue(settings["process_count"])
        self.settings.process_count_preset_combobox.setCurrentIndex(settings["process_count_preset"])


class DroppedProgressDialog(QDialog):
    def __init__(self, parent: Raw2AcesExrRenamerDialog):
        super().__init__(parent)
        self.parent_ = parent
        self.setWindowTitle(tr("Processing EXRs"))

        self._progress: int = 0
        self._progress_total: int = 0

        self.label = QLabel(
            tr("Processing dropped EXR files... please wait.")
        )
        self.progress_label = QLabel(
            tr("{0} out of {1}").format(self._progress, self._progress_total)
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.progress_label)

        size: QSize = self.sizeHint()
        self.setFixedHeight(size.height())

    def set_progress_total(self, total: int):
        self._progress_total = total

    def set_progress(self, progress: int):
        self._progress = progress
        self.progress_label.setText(
            tr("{0} out of {1}").format(self._progress, self._progress_total)
        )

    def closeEvent(self, event: QCloseEvent):
        if self.parent_.paste_start_time:
            event.ignore()


class Raw2AcesExrRenamerTreeView(QTreeView):
    def __init__(self, parent: Raw2AcesExrRenamerDialog):
        super().__init__(parent)
        self.parent_ = parent
        self.setSortingEnabled(True)
        self.setRootIsDecorated(False)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QTreeView.SelectionMode.SingleSelection)

        self.files = set()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            parent = self.parent_
            parent.paste_start_time = time.perf_counter()
            worker = Raw2AcesDroppedWorker(
                parent=parent,
                urls=urls,
            )
            worker.signals.progress_total.connect(parent._paste_dialog.set_progress_total)
            worker.signals.progress.connect(parent._paste_dialog.set_progress)
            worker.signals.is_busy.connect(parent._update_paste_dialog)
            run_worker_in_thread(
                worker,
                on_finish=self.post_dropped,
            )

    def post_dropped(self):
        self.setSortingEnabled(False)

    def paintEvent(self, e: QPaintEvent):
        if self.model() and self.model().rowCount() > 0:
            super().paintEvent(e)
            return

        msg = tr("Drag and drop EXR files here")
        p = QPainter(self.viewport())
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)


class Raw2AcesExrRenamerDialog(QDialog):
    width_padding = 8
    height_padding = round(width_padding / 2)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"""
              QPushButton {{
                  min-width: 64px;
                  padding-top: {self.height_padding}px;
                  padding-bottom: {self.height_padding}px;
                  padding-left: {self.width_padding}px;
                  padding-right: {self.width_padding}px;
              }}
              """
        )
        self.setWindowTitle("Raw2Aces EXR Renamer")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setGeometry(100, 100, 800, 600)

        self._paste_dialog = DroppedProgressDialog(self)
        self.paste_start_time: float | None = None
        self.is_busy: bool = False
        self.exr_files = []

        self.treeview = Raw2AcesExrRenamerTreeView(self)
        self.model = Raw2AcesExrRenamerModel(self)
        self.treeview.setModel(self.model)

        self.new_name_lineedit = QLineEdit(self)
        self.new_name_lineedit.setText("DSC10000_")
        self.new_name_lineedit.textChanged.connect(lambda: renamer(self))
        self.new_name_lineedit.setPlaceholderText(
            tr("Replace original filename with new name value.")
        )

        self.sort_by_date_taken_checkbox = CheckBox(self)
        self.sort_by_date_taken_checkbox.setChecked(True)
        self.sort_by_date_taken_checkbox.toggled.connect(self._date_taken_toggled)
        self.seq_padding_length_spinbox = QSpinBox(self)
        self.seq_padding_length_spinbox.setToolTip(
            tr("The sequence padding length. E.g. Value of 5 is represented as 00001.")
        )
        self.seq_padding_length_spinbox.setMinimum(3)
        self.seq_padding_length_spinbox.setMaximum(10)
        self.seq_padding_length_spinbox.setValue(5)
        self.seq_padding_length_spinbox.valueChanged.connect(lambda: renamer(self))

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset)

        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self._run_rename)
        howto_label = QLabel(
            f"Rename EXRs with sequential padding number. "
            f"This will always sort by ascending order."
        )
        container = Raw2AcesContainer(self)
        form = FormNoSideMargins(self)
        form.addWidgetAsRow(howto_label)
        form.addRow(QLabel("New Name:"), self.new_name_lineedit)
        form.addRow(QLabel("Sort by Date Taken:"), self.sort_by_date_taken_checkbox)
        form.addRow(QLabel("Padding Count:"), self.seq_padding_length_spinbox)
        container.addWidget(form)
        container.addWidget(self.treeview)
        container.addWidget(self.run_btn)
        container.addWidget(self.reset_btn)
        container.setStretchFactor(0, 0)
        container.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(container)

    def _reset(self):
        self.treeview.files.clear()
        self.model.reset()
        self.exr_files.clear()

    def _update_paste_dialog(self, is_busy: bool):
        if not is_busy:
            self.paste_start_time = None
            self._paste_dialog.close()
            return

        current_time = time.perf_counter()
        if current_time - self.paste_start_time > 2:
            if not self._paste_dialog.isVisible():
                self._paste_dialog.exec()

    def _date_taken_toggled(self):
        if self.sort_by_date_taken_checkbox.isChecked():
            self.treeview.sortByColumn(2, Qt.SortOrder.AscendingOrder)
        else:
            self.treeview.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def _run_rename(self):
        self.treeview.setEnabled(False)
        self.run_btn.setEnabled(False)

        logs: list[dict[str, str]] = []

        try:
            for row_idx in range(self.model.rowCount()):
                status_item: Raw2AcesStatusItem = self.model.item(row_idx, 3)
                if status_item.get_status() == Raw2AcesStatusItem.DONE:
                    continue

                input_item = self.model.item(row_idx, 0)
                output_item = self.model.item(row_idx, 1)
                original_file = Path(input_item.text())
                new_file = Path(output_item.text())
                original_file.rename(new_file)
                status_item.set_status(Raw2AcesStatusItem.DONE)
                log_text = f"{original_file} -> {new_file}"
                print(log_text)
                log_data = {
                    "original_file": original_file,
                    "new_file": str(new_file),
                }
                logs.append(log_data)
        except (OSError, Exception) as e:
            print(f"{e=}")

        self.treeview.resizeColumnToContents(0)
        self.treeview.resizeColumnToContents(1)

        self._save_renamed_log(logs)

        self.treeview.setEnabled(True)
        self.run_btn.setEnabled(True)

    def _save_renamed_log(self, logs: list[dict[str, str]]):
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%Y%m%d_%H%M%S")

        log_filename = f"renamed_exrs_{formatted_time}.csv"
        log_file = Path(get_desktop_path()) / "raw2aces_logs" / log_filename
        log_file.parent.mkdir(exist_ok=True, parents=True)

        keys = logs[0].keys()
        with open(log_file, 'w', newline='') as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(logs)
