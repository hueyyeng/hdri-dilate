from __future__ import annotations

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


class Raw2AcesModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reset_headers()

    def reset_headers(self):
        self.setHorizontalHeaderLabels(
            [
                "Input",
                "Output",
                "Status",
            ]
        )

    def reset(self):
        self.clear()
        self.reset_headers()


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
                file_path = url.toLocalFile()
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
            status_item = QStandardItem("WARNING Found existing aces exr file. Will be overridden!")
        else:
            status_item = QStandardItem("READY")

        output_item = QStandardItem()
        model.setItem(item_idx.row(), 1, output_item)
        model.setItem(item_idx.row(), 2, status_item)


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

        self.addRow("rawtoaces.exe path", self.r2a_path_lineedit)
        self.addRow("White Balance", self.white_balance_combobox)
        self.addRow("IDT Matrix Calculation", self.matrix_combobox)
        self.addRow("Highlight Headroom", self.headroom_spinbox)

        self.run_btn = Raw2AcesRunBtn("Run")
        self.run_btn.clicked.connect(self._run)
        self.addRow("", self.run_btn)

        rawtoaces_path = Path(os.getcwd()) / "hdri_dilate" / "resources" / "bin" / "rawtoaces.exe"
        self.r2a_path_lineedit.set_path(str(rawtoaces_path))

    def _run(self):
        btn = self.run_btn
        btn.start_spinner()
        worker = Raw2AcesWorker(self)
        run_worker_in_thread(
            worker,
            on_finish=btn.stop_spinner
        )


class Raw2AcesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Raw2Aces Converter")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setGeometry(100, 100, 800, 600)

        self.params = Raw2AcesFormWidget(self)
        self.treeview = Raw2AcesFileTreeView(self)
        self.model = Raw2AcesModel(self)
        self.treeview.setModel(self.model)

        container = Raw2AcesContainer(self)
        container.addWidget(self.params)
        container.addWidget(self.treeview)
        container.setStretchFactor(0, 0)
        container.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(container)
