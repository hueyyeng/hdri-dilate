import sys
from pathlib import Path

from hdri_dilate.utils.filesystem import resource_path

APP_NAME = "HDRI Dilate"
APP_VERSION = "0.1.0"
WINDOW_ICON = resource_path("hdri_dilate/resources/icons/app.png")

LOG_PATH = Path().home() / "Logs" / "HDRI Dilate" / APP_VERSION
LOG_PATH.mkdir(parents=True, exist_ok=True)
LOG_WINDOW_MAX_LINES = 1000

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(levelname)s] %(asctime)s %(module)s %(process)d %(thread)d %(message)s"
        },
        "simple": {
            "format": "[%(levelname)s] %(asctime)s - %(message)s"
        },
        "default": {
            "format": "[%(levelname)s] %(asctime)s %(filename)s:%(lineno)d - %(funcName)s - %(message)s"
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "default",
        },
        "hdri_dilate": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOG_PATH / "hdri_dilate.log",
            "formatter": "default",
            "when": "W0",
            "interval": 1,
            "backupCount": 4,
        },
    },
    "loggers": {
        "": {
            "handlers": [
                "console",
                "hdri_dilate",
            ],
            "level": "DEBUG",
            "propagate": True,
        },
        "hdri_dilate": {
            "handlers": [
                "console",
                "hdri_dilate",
            ],
            "propagate": False,
        },
    },
}
