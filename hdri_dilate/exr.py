import array

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


def write_exr(hdr_image: np.ndarray, exr_path: str, exr_header: dict, use_bgr_order=False):
    channel_layout = {
        "R": 0,
        "G": 1,
        "B": 2,
    }
    if use_bgr_order:
        channel_layout = {
            "R": 2,
            "G": 1,
            "B": 0,
        }

    exr_output = OpenEXR.OutputFile(exr_path, exr_header)
    exr_output.writePixels(
        dict(
            [
                (
                    channel,
                    hdr_image[:, :, channel_layout[channel]]
                    .astype(np.float32).tobytes()
                ) for channel in channel_layout.keys()
            ]
        )
    )
    exr_output.close()
