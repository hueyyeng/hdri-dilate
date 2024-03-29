from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import pyexiv2
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate.constants import icons
from hdri_dilate.exr import get_exr_header
from hdri_dilate.hdri_dilate_qt import tr
from hdri_dilate.hdri_dilate_qt.forms import (
    FormNoSideMargins,
)
from hdri_dilate.hdri_dilate_qt.inputs import (
    FilePathSelectorWidget,
)
from hdri_dilate.hdri_dilate_qt.message_box import (
    NewMessageBox,
)
from hdri_dilate.hdri_dilate_qt.raw2aces.models import (
    Raw2AcesModel,
    Raw2AcesStatusItem,
)
from hdri_dilate.hdri_dilate_qt.raw2aces.workers import (
    Raw2AcesWorker,
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
    def __init__(self, parent: "PropertyPanelWidget"):
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
    def __init__(self, parent: "Raw2AcesDialog"):
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
        super().paintEvent(e)
        if self.model() and self.model().rowCount() > 0:
            return

        msg = tr("Drag and drop supported RAW files here")
        p = QPainter(self.viewport())
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)


class Raw2AcesFileWidget(QWidget):
    def __init__(self, parent: "Raw2AcesDialog"):
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

    def add_treeview(self, widget: "Raw2AcesFileTreeView"):
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
    def __init__(self, parent: "Raw2AcesDialog"):
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

        self.addRow("rawtoaces.exe path", self.r2a_path_lineedit)
        self.addRow("White Balance", self.white_balance_combobox)
        self.addRow("White Balance Custom Arg", self.white_balance_custom_lineedit)
        self.addRow("", self.white_balance_help_label)
        self.addRow("IDT Matrix Calculation", self.matrix_combobox)
        self.addRow("Highlight Headroom", self.headroom_spinbox)
        self.addRow("rawtoaces.exe Process Count Presets", self.process_count_preset_combobox)
        self.addRow("rawtoaces.exe Process Count", self.process_count_spinbox)

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
