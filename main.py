import gc
import logging
import os
import sys

import matplotlib
from PySide6.QtCore import *

from hdri_dilate.hdri_dilate_qt.application import (
    Application,
)
from hdri_dilate.hdri_dilate_qt.message_box import (
    LaunchErrorMessageBox,
)

logger = logging.getLogger()


def main():
    gc.set_threshold(70000, 5000, 5000)
    root = os.path.dirname(os.path.abspath(__file__))
    QDir.addSearchPath(
        "icons",
        os.path.join(root, "hdri_dilate/resources/icons")
    )
    matplotlib.use("QtAgg")
    try:
        app = Application([])
        sys.exit(app.exec())
    except Exception as e:
        logger.error(e, exc_info=True)
        logger.debug("Fatal Error: %s", str(e))
        mb = LaunchErrorMessageBox()
        mb.setDetailedText(f"{e}")
        mb.exec()


if __name__ == "__main__":
    main()
