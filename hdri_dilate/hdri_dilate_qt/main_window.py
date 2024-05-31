from pathlib import Path

import cv2
from comel.wrapper import ComelMainWindowWrapper
from matplotlib import pyplot as plt
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from hdri_dilate.enums import MorphShape
from hdri_dilate.hdri_dilate_qt import tr
from hdri_dilate.hdri_dilate_qt.checkbox import CheckBox
from hdri_dilate.hdri_dilate_qt.collapsible import (
    CollapsibleWidget,
)
from hdri_dilate.hdri_dilate_qt.dilate.widgets import (
    DilateProgressDialog,
)
from hdri_dilate.hdri_dilate_qt.forms import (
    FormNoSideMargins,
)
from hdri_dilate.hdri_dilate_qt.inputs import (
    FilePathSelectorWidget,
    FolderPathSelectorWidget,
)
from hdri_dilate.hdri_dilate_qt.menu import (
    MainWindowMenuBar,
)
from hdri_dilate.hdri_dilate_qt.message_box import (
    NewMessageBox,
)
from hdri_dilate.hdri_dilate_qt.raw2aces.widgets import (
    ExrRawMetadataViewerDialog,
    Raw2AcesConverterDialog,
    Raw2AcesExrRenamerDialog,
)
from hdri_dilate.hdri_dilate_qt.toolbars import (
    VerticalToolBar,
)


class MainWindow(ComelMainWindowWrapper):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent=parent)
        self.threadpool = QThreadPool().globalInstance()
        self.setup_ui()
        self.setMinimumWidth(512)

    def closeEvent(self, event):
        plt.close("all")
        cv2.destroyAllWindows()
        super().closeEvent(event)

    def setup_ui(self):
        # Required for DockWidget to dock into DockWidget
        self.setDockNestingEnabled(True)

        # Toolbar
        # self.toolbar = MainWindowToolBar(self)
        # self.addToolBar(self.toolbar)
        self.setup_toolbar()

        # Menu bar
        self.menu_bar = MainWindowMenuBar(self)
        metadata_dialog_action = QAction(tr("View EXR/Raw &Metadata..."), self)
        metadata_dialog_action.triggered.connect(self.show_exr_raw_metadata_dialog)
        self.menu_bar.tools_menu.addAction(metadata_dialog_action)
        raw2aces_dialog_action = QAction(tr("&Raw2Aces..."), self)
        raw2aces_dialog_action.triggered.connect(self.show_raw2aces_dialog)
        exr_renamer_dialog_action = QAction(tr("&EXR Renamer..."), self)
        exr_renamer_dialog_action.triggered.connect(self.show_exr_renamer_dialog)
        self.menu_bar.tools_menu.addAction(raw2aces_dialog_action)
        self.menu_bar.tools_menu.addAction(exr_renamer_dialog_action)
        self.setMenuBar(self.menu_bar)

        # # Sidebar widgets
        # self.sidebar_widget = SidebarWidget(self)
        # self.setCentralWidget(self.sidebar_widget)

        # Central Widget
        self.central_widget = VerticalToolBar(self)
        self.setCentralWidget(self.central_widget)

        # Form
        form = FormNoSideMargins(self)
        self.advanced_form = FormNoSideMargins(self)

        self.image_path_lineedit = FilePathSelectorWidget(self)
        self.output_folder_lineedit = FolderPathSelectorWidget(self)
        self.save_output_checkbox = CheckBox(self)
        self.save_output_checkbox.setChecked(True)

        self.export_debug_dilate_checkbox = CheckBox(self)
        self.export_debug_dilate_checkbox.setChecked(False)

        self.export_debug_dilate_interval_spinbox = QSpinBox(self)
        self.export_debug_dilate_interval_spinbox.setValue(10)
        self.export_debug_dilate_interval_spinbox.setMaximum(500)

        self.show_debug_preview_checkbox = CheckBox(self)
        self.show_debug_preview_checkbox.setChecked(False)

        self.use_bgr_order_checkbox = CheckBox(self)
        self.use_bgr_order_checkbox.setChecked(False)

        self.terminate_early_checkbox = CheckBox(self)
        self.terminate_early_checkbox.setChecked(False)

        self.use_blur_checkbox = CheckBox(self)
        self.use_blur_checkbox.setChecked(True)

        self.blur_size_spinbox = QSpinBox(self)
        self.blur_size_spinbox.setValue(3)
        self.blur_size_spinbox.editingFinished.connect(self.odd_blur_size)
        self.blur_size_spinbox.setMinimum(3)
        self.blur_size_spinbox.setMaximum(99)
        self.blur_size_spinbox.setSingleStep(2)

        self.dilate_iteration_spinbox = QSpinBox(self)
        self.dilate_iteration_spinbox.setValue(3)
        self.dilate_iteration_spinbox.setMaximum(50)

        self.dilate_size_spinbox = QSpinBox(self)
        self.dilate_size_spinbox.setValue(2)
        self.dilate_size_spinbox.setMinimum(2)
        self.dilate_size_spinbox.setMaximum(50)

        self.final_intensity_multiplier_spinbox = QDoubleSpinBox(self)
        self.final_intensity_multiplier_spinbox.setValue(1.00)
        self.final_intensity_multiplier_spinbox.setSingleStep(0.01)
        self.final_intensity_multiplier_spinbox.setMinimum(0.01)
        self.final_intensity_multiplier_spinbox.setMaximum(10.00)

        self.intensity_spinbox = QDoubleSpinBox(self)
        self.intensity_spinbox.setValue(15.0)
        self.intensity_spinbox.setSingleStep(0.1)

        self.threshold_spinbox = QDoubleSpinBox(self)
        self.threshold_spinbox.setValue(1.0)
        self.threshold_spinbox.setSingleStep(0.1)

        self.dilate_shape_combobox = QComboBox(self)
        self.dilate_shape_combobox.addItems(
            [
                MorphShape.RECTANGLE,
                MorphShape.CROSS,
                MorphShape.ELLIPSIS,
            ]
        )
        self.dilate_shape_combobox.setCurrentText(MorphShape.ELLIPSIS)

        form.addRow(tr("EXR/HDR Path"), self.image_path_lineedit)
        form.addRow(tr("Output Folder"), self.output_folder_lineedit)
        form.addRow(tr("Save Output"), self.save_output_checkbox)
        form.addRow(tr("Intensity"), self.intensity_spinbox)
        form.addRow(tr("Threshold"), self.threshold_spinbox)
        form.addRow(tr("Final Intensity Multiplier"), self.final_intensity_multiplier_spinbox)

        self.advanced_form.addRow(tr("Dilate Size (px)"), self.dilate_size_spinbox)
        self.advanced_form.addRow(tr("Dilate Iteration"), self.dilate_iteration_spinbox)
        self.advanced_form.addRow(tr("Dilate Shape"), self.dilate_shape_combobox)
        self.advanced_form.addRow(tr("Terminate Early When Any Channel Hit Threshold"), self.terminate_early_checkbox)
        self.advanced_form.addRow(tr("Use BGR Order"), self.use_bgr_order_checkbox)
        self.advanced_form.addRow(tr("Use Blur"), self.use_blur_checkbox)
        self.advanced_form.addRow(tr("Blur Size (px)"), self.blur_size_spinbox)
        self.advanced_form.addRow(tr("Export Debug Dilate Figures?"), self.export_debug_dilate_checkbox)
        self.advanced_form.addRow(tr("Export Debug Dilate Interval"), self.export_debug_dilate_interval_spinbox)
        self.advanced_form.addRow(tr("Show Debug Preview?"), self.show_debug_preview_checkbox)

        self.generate_btn = QPushButton(tr("Generate"))
        self.generate_btn.clicked.connect(self.generate)

        advanced_settings = CollapsibleWidget("Advanced Settings", self)
        advanced_settings.addWidget(self.advanced_form)
        advanced_settings.collapse()

        self.central_widget.addWidget(form)
        self.central_widget.addWidget(advanced_settings)
        self.central_widget.addWidget(self.generate_btn)
        self.central_widget.addStretch()

    def show_exr_raw_metadata_dialog(self):
        dlg = ExrRawMetadataViewerDialog(parent=self)
        dlg.show()

    def show_raw2aces_dialog(self):
        dlg = Raw2AcesConverterDialog(parent=self)
        dlg.show()

    def show_exr_renamer_dialog(self):
        dlg = Raw2AcesExrRenamerDialog(parent=self)
        dlg.exec()

    def odd_blur_size(self):
        blur_size = self.blur_size_spinbox.value()
        if blur_size % 2 == 0:
            self.blur_size_spinbox.setValue(blur_size - 1)

    def setup_toolbar(self):
        ...

    def generate(self):
        hdri_input = self.image_path_lineedit.get_path()
        if not hdri_input:
            msg = tr(
                "EXR/HDR Path is blank! Please specify the path."
            )
            NewMessageBox(self).warning(
                title=tr("Blank EXR/HDR Path"),
                text=msg
            )
            return

        is_valid_hdri_path = self.image_path_lineedit.validate_path()
        if not is_valid_hdri_path:
            msg = tr(
                "Invalid EXR/HDR path! EXR/HDR path must not "
                "contains illegal characters."
            )
            NewMessageBox(self).warning(
                title=tr("Warning"),
                text=msg
            )
            return

        if not Path(hdri_input).exists():
            msg = tr(
                "EXR/HDR path does not exists! Verify the path is accessible or "
                "reselect the file."
            )
            NewMessageBox(self).warning(
                title=tr("Warning"),
                text=msg
            )
            return

        is_save_output = self.save_output_checkbox.isChecked()
        output_folder = self.output_folder_lineedit.get_path()
        if is_save_output and not output_folder:
            msg = tr(
                "Output folder path is blank! Please specify the output folder path."
            )
            NewMessageBox(self).warning(
                title=tr("Blank Output Folder Path"),
                text=msg
            )
            return

        is_valid_output_folder = self.output_folder_lineedit.validate_path()
        if is_save_output and not is_valid_output_folder:
            msg = tr(
                "Invalid output folder path! Output folder path must not "
                "contains illegal characters."
            )
            NewMessageBox(self).warning(
                title=tr("Warning"),
                text=msg
            )
            return

        dialog = DilateProgressDialog(self)
        dialog.show()
