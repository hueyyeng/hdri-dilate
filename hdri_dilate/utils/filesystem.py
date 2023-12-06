import platform
import subprocess
import sys
from pathlib import Path


def resource_path(relative_path: str) -> str:
    """Resource Path

    Workaround for specifying resource path when using pyinstaller

    Parameters
    ----------
    relative_path : str
        The relative path of the file from root directory
        E.g. "resources/icons/blah.png"

    Returns
    -------
    str
        The absolute resource path

    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = Path(".").absolute()

    new_path = Path(base_path, relative_path)

    return str(new_path)


def reveal_path(path: str):
    """Reveal path

    Reveal the file/directory path using the OS File Manager.

    Parameters
    ----------
    path : str
        The path of the file/directory.

    Raises
    ------
    Exception
        Invalid or inaccessible path.

    """
    system = platform.system()
    path = Path(path)

    if not path.exists():
        raise Exception("Invalid or inaccessible path!")

    is_windows = system == "Windows"
    is_linux = system == "Linux"

    # Default to macOS since no extra handling
    cmd = (["open", "-R", path.as_posix()])

    if is_linux:
        dir_path = str(path.parent)  # Omit file_name from path
        cmd = (["xdg-open", dir_path])

    if is_windows and path.is_dir():
        cmd = f"explorer /e,{path}"
    elif is_windows and path.exists():
        cmd = f"explorer /select,{path}"

    subprocess.call(cmd)