# HDRI Dilate

Based on https://arxiv.org/abs/2205.07873

## Quick Setup

Ensure at least Python 3.11 installed. Please refer to [Known Issues](#known-issues) before running the following
commands.

```shell
# Install dependencies
pip install -r requirements.txt

# Highly advisable to create virtualenv
python -m venv env

# Using Windows Command Prompt if you're not using Git Bash (or Unix terminal emulator)
.\env\Scripts\activate.bat

# If using Git Bash
source env/Scripts/activate

# Run the app
python main.py
```

## Quick Start

1. Select the HDRI file (.exr/.hdr) for EXR/HDR Path.
2. Select the desired output folder (if Save Output is unchecked, this value is ignored).
3. Set the Intensity value. The default value is `15.00`. This the minimum value to detect the saturated pixel values (
   the brightness) in the HDRI. Caution! Not to be confused with color saturation.
4. Set the Threshold value. The default value is `1.00`. This is the value where it will stop dilating the found
   saturated pixels when the calculated average value is below the threshold.
5. Click Generate to output the dilated HDRI, dilated mask and the threshold mask.

## Optimization and Advanced Tweaks

1. Test with lower res HDRI that is lower than 4K if possible before applying on higher res HDRI (8K or higher).
2. Enable Show Debug Preview to display a Matplotlib window that shows the original HDRI, dilated HDRI, threshold mask (
   the found saturated pixels) and the dilated mask. Take note that higher res HDRI can slow down Matplotlib window.
3. Increase the dilate size value when working with higher res HDRI to reduce memory usage at the expense of longer
   calculation for each iteration. Try 4px for 8K, 8px for 16K and 16px for 32K res.
4. Bump the Threshold value to the known maximum value that the target display hardware can handle. Using higher
   Threshold value can help reduce memory usage as it will use fewer iterations to achieve the target Threshold value.
5. Using Rectangle or Cross dilate shape can provide speed up on slow system if the dilated shape is not a concern.

## Caution

Do not immediately test with 16K res unless your system have at least 128GB RAM! You have been warned!

## Tools

### EXR/RAW Metadata Viewer

A simple metadata viewer for EXR and RAW (but not limited to files with embedded EXIF) with search filter.

### Raw2Aces Converter

A frontend manager for [rawtoaces](https://github.com/AcademySoftwareFoundation/rawtoaces) executable. Might work on Linux but not tested.

For Windows user, you can grab the `rawtoaces.exe` executable
from https://github.com/AcademySoftwareFoundation/rawtoaces/issues/124 courtesy of michelerenzullo.

Place the `rawtoaces.exe` executable in `hdri_dilate/resources/bin` for Raw2Aces Converter dialog to detect manually.

## Known Issues

Last tested working on Windows 10 and Python 3.11.

1. The Python OpenEXR library will fail to install for most users on Windows... refer
   to https://stackoverflow.com/questions/65702285/error-in-installing-openexr-on-windows-platform for more details.
   A workaround that works for me is using `pipwin`:
   ```commandline
   pip install pipwin
   pipwin install openexr
   ```
