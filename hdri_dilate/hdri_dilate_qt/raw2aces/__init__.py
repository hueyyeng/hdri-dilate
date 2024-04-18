from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hdri_dilate.hdri_dilate_qt.raw2aces.widgets import (
        Raw2AcesExrRenamerDialog,
    )


def get_desktop_path() -> str:
    import ctypes
    from ctypes import windll, wintypes

    CSIDL_DESKTOP = 0

    _SHGetFolderPath = windll.shell32.SHGetFolderPathW
    _SHGetFolderPath.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPCWSTR,
    ]

    path_buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    result = _SHGetFolderPath(0, CSIDL_DESKTOP, 0, 0, path_buf)
    return path_buf.value


def renamer(parent: Raw2AcesExrRenamerDialog):
    new_name_text = parent.new_name_lineedit.text()
    model = parent.model
    count_padding = f'%0{parent.seq_padding_length_spinbox.value()}d'
    for row_idx in range(model.rowCount()):
        input_item = model.item(row_idx, 0)
        output_item = model.item(row_idx, 1)

        itt = input_item.text()
        filename, ext = os.path.splitext(itt)
        counter = count_padding % row_idx
        if new_name_text:
            new_name = f"{new_name_text}.{counter}{ext}"
        else:
            new_name = f"{filename}.{counter}{ext}"

        itt_path = Path(itt)
        out_path = itt_path.parent / new_name
        output_item.setText(str(out_path))
