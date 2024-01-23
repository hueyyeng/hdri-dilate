import array
from pathlib import Path

import Imath
import numpy as np
import OpenEXR


class ExrDataType:
    INT_8 = np.int8
    FLOAT_16 = np.float16
    FLOAT_32 = np.float32


def get_exr_header(exr_path: str) -> dict:
    exr = OpenEXR.InputFile(exr_path)
    exr_header = exr.header()
    return exr_header


def load_exr(exr_path: str, use_bgr_order=False):
    exr = OpenEXR.InputFile(exr_path)

    dw = exr.header()["dataWindow"]
    image_size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)

    dtype = ExrDataType.FLOAT_32
    pixel_type = Imath.PixelType(Imath.PixelType.FLOAT)

    img_R, img_G, img_B = exr.channels("RGB", pixel_type)

    arr_R = array.array("f", img_R)
    arr_G = array.array("f", img_G)
    arr_B = array.array("f", img_B)

    ndarr_R = np.array(arr_R, dtype=dtype)
    ndarr_G = np.array(arr_G, dtype=dtype)
    ndarr_B = np.array(arr_B, dtype=dtype)

    # OpenCV process as BGR order internally by default
    arrays = [ndarr_R, ndarr_G, ndarr_B]
    if use_bgr_order:
        arrays = [ndarr_B, ndarr_G, ndarr_R]

    results = np.stack(arrays, axis=1)
    results = results.reshape(image_size[1], image_size[0], 3)

    return results


# TODO: Make this general purpose in the future
def write_exr(hdr_image: np.ndarray, exr_path: str | Path, exr_header: dict, use_bgr_order=False):
    # The Alpha/Mask stuff
    if len(hdr_image.shape) == 2:
        data = hdr_image[:, :].astype(np.float32).tobytes()
        pixels = [
            ("R", data),
            ("G", data),
            ("B", data),
        ]
        exr_header["channels"] = {
            "R": Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT), 1, 1),
            "G": Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT), 1, 1),
            "B": Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT), 1, 1),
        }

    # FIXME: Dilated mask workaround for now...
    elif hdr_image.dtype == np.uint8 and len(hdr_image.shape) == 3:
        channels = {
            "R": 0,
            "G": 1,
            "B": 2,
        }
        pixels = [
            (
                channel,
                hdr_image[:, :, channels[channel]].astype(np.float32).tobytes()
            ) for channel in channels.keys()
        ]

    # The usual RGB stuff
    else:
        channels = {
            "R": 0,
            "G": 1,
            "B": 2,
        }
        if use_bgr_order:
            channels = {
                "R": 2,
                "G": 1,
                "B": 0,
            }
        pixels = [
            (
                channel,
                hdr_image[:, :, channels[channel]].astype(hdr_image.dtype).tobytes()
            ) for channel in channels.keys()
        ]

    exr_output = OpenEXR.OutputFile(str(exr_path), exr_header)
    exr_output.writePixels(dict(pixels))
    exr_output.close()


def write_exr_header(input_path: str | Path, output_path: str | Path, exr_header: dict):
    exr_input = OpenEXR.InputFile(str(input_path))
    pixel_type = Imath.PixelType(Imath.PixelType.HALF)
    img_R, img_G, img_B = exr_input.channels("RGB", pixel_type)
    pixels = [
            ("R", img_R),
            ("G", img_G),
            ("B", img_B),
        ]
    exr_output = OpenEXR.OutputFile(str(output_path), exr_header)
    exr_output.writePixels(dict(pixels))
    exr_output.close()
