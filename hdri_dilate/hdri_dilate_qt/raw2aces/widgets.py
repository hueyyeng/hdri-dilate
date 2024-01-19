from __future__ import annotations

import os
from pathlib import Path

import pyexiv2
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate.exr import get_exr_header
from hdri_dilate.hdri_dilate_qt import tr


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
