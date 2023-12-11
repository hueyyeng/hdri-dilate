import argparse
import logging
import os
import subprocess
import sys
from logging import FileHandler
from pathlib import Path

from hdri_dilate import settings

os.makedirs("logs", exist_ok=True)
file_handler = FileHandler("logs/build_onedir.log")
file_handler.setFormatter(logging.Formatter(
    "[%(levelname)s] %(asctime)s %(filename)s:%(lineno)d - %(funcName)s - %(message)s"
))
file_handler.setLevel(logging.INFO)

stdout_handler_format = logging.Formatter("%(message)s")
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(stdout_handler_format)
stdout_handler.setLevel(logging.DEBUG)

handlers = [
    file_handler,
    stdout_handler,
]
logging.basicConfig(handlers=handlers)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

INNO_APP_NAME = "hdri_dilate"
INNO_APP_EXE_NAME = "hdri_dilate"
APP_BETA = False
APP_VERSION = settings.APP_VERSION


def get_app_exe_name() -> str:
    name = INNO_APP_EXE_NAME
    return f"{name}Beta" if APP_BETA else name


def get_pyinstaller_dist_output() -> Path:
    return Path("dist", get_app_exe_name())


def pyinstaller_makespec():
    app_name = get_app_exe_name()
    header = f"Generating {app_name} spec file"
    divider = "=" * len(header)

    logger.debug("\n".join([
        divider,
        header,
        divider
    ]))

    app_icon = "app.png"

    makespec_cmd = " ".join([
        "pyi-makespec",
        "--onedir",
        "--hide-console hide-late",
        "--hiddenimport xmlrpc",
        "--hiddenimport xmlrpc.client",
        "--add-data app.png;.",
        "--add-data hdri_dilate/resources;hdri_dilate/resources",
        # "--add-data language;language",
        "--add-data env/Lib/site-packages/comel;comel",
        f"-i {app_icon}",
        f"--name {app_name}",
        "main.py",
    ])

    logger.info(makespec_cmd)

    process = subprocess.Popen(
        makespec_cmd.split(),
        stdout=subprocess.PIPE,
    )
    output, error = process.communicate()
    logger.debug(output.decode())
    if error:
        logger.error(error.decode())
        raise Exception(f"Fail to generate {app_name} spec file")


def pyinstaller_build():
    app_name = get_app_exe_name()
    spec_filename = f"{app_name}.spec"

    header = f"Building {spec_filename}"
    divider = "=" * len(header)

    logger.debug("\n".join([
        divider,
        header,
        divider
    ]))

    build_cmd = " ".join([
        "pyinstaller",
        "--clean",
        "-y",
        spec_filename,
    ])

    process = subprocess.Popen(
        build_cmd.split(),
        stdout=subprocess.PIPE,
    )
    output, error = process.communicate()
    logger.debug(output.decode())
    if error:
        logger.error(error.decode())
        raise Exception(f"Fail to build {spec_filename}!")

    logger.info(f"Successfully build {spec_filename}")


def main():
    if APP_BETA:
        logger.info(f"Building BETA release...")

    pyinstaller_makespec()
    pyinstaller_build()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Build HDRI Dilate executable using pyinstaller"
        )
    )
    group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        "-b",
        "--beta",
        action="store_true",
        help="Add Beta label"
    )
    args = parser.parse_args()

    if args.beta:
        APP_BETA = True

    main()
