GCP Pixel Picker
================

|version| |license| |windows| |linux| |macos-arm64| |macos-intel|

.. |version| image:: https://img.shields.io/badge/version-0.0.1-brightgreen
   :alt: Version 0.0.1

.. |license| image:: https://img.shields.io/badge/license-MIT-blue
   :target: https://github.com/MAGALA-RICHARD/GCP/blob/main/LICENSE.txt
   :alt: MIT License

.. |windows| image:: https://github.com/MAGALA-RICHARD/GCP/actions/workflows/build_windows.yml/badge.svg
   :target: https://github.com/MAGALA-RICHARD/GCP/actions/workflows/build_windows.yml
   :alt: Windows Build

.. |linux| image:: https://github.com/MAGALA-RICHARD/GCP/actions/workflows/build_linux.yml/badge.svg
   :target: https://github.com/MAGALA-RICHARD/GCP/actions/workflows/build_linux.yml
   :alt: Linux Build

.. |macos-arm64| image:: https://github.com/MAGALA-RICHARD/GCP/actions/workflows/build_macos.yml/badge.svg
   :target: https://github.com/MAGALA-RICHARD/GCP/actions/workflows/build_macos.yml
   :alt: macOS Apple Silicon Build

.. |macos-intel| image:: https://github.com/MAGALA-RICHARD/GCP/actions/workflows/build%20mac%20os%20Intel.yml/badge.svg
   :target: https://github.com/MAGALA-RICHARD/GCP/actions/workflows/build%20mac%20os%20Intel.yml
   :alt: macOS Intel Build

Features
--------

* Open a folder containing JPG, JPEG, PNG, TIF, or TIFF images.
* Open an individual supported image file.
* Navigate through folder images with Previous and Next controls.
* Automatically display the next image in Fit mode while preserving aspect ratio.
* Select a GCP by left-clicking directly on the image.
* Right-click any valid image location to select that pixel and open a context menu showing its pixel coordinates.
* Store one active observation per image; adding a new point for the same image updates the existing observation.
* Enter optional X, Y, Z, label, and CRS information.
* Export all observations or records grouped by image-file extension.
* Export observations as TXT or CSV.
* Copy the current record, selected saved records, or all saved records to the clipboard.
* Inspect image metadata from the right-click context menu.
* Zoom with the mouse wheel, toolbar buttons, or keyboard.
* Pan with the middle mouse button.
* Drag the divider between the image viewer and information panel.

Keyboard shortcuts
------------------

==================  ========================================
Shortcut            Action
==================  ========================================
Ctrl+O              Open image folder
Ctrl+Shift+O        Open a single image file
N                   Next image
P                   Previous image
Ctrl+N              Next image
Ctrl+P              Previous image
Ctrl+Shift+A        Add/update the current observation
Ctrl+Shift+N        Add/update observation and go next
Ctrl+E              Export TXT
Ctrl+Shift+E        Export CSV
F                   Fit image to the viewer
0                   Show image at 100% / original scale
+                   Zoom in
-                   Zoom out
I                   Show image metadata
==================  ========================================

Single-key shortcuts such as ``N``, ``P``, ``F``, and ``I`` are ignored while
typing in text-entry fields, so coordinate and label entry is not interrupted.

Text-field behavior
-------------------

When editing X, Y, Z, Label, or CRS, press ``Enter`` or ``Esc`` to leave the
active text field and return keyboard control to the image viewer. Clicking
anywhere outside an editable field also clears text-input focus. This allows
single-key viewer shortcuts such as ``N`` and ``P`` to work immediately after
coordinate entry.

Mouse controls
--------------

==================  ========================================
Mouse action        Result
==================  ========================================
Left click          Select a pixel/GCP center
Right click         Select clicked pixel and open context menu
Mouse wheel         Zoom around the pointer
Middle-button drag  Pan the image
==================  ========================================

Typical workflow
----------------

1. Open the ``File`` menu and choose ``Open Folder``, or press ``Ctrl+O``.
2. Click the center of the GCP in the displayed image.
3. Enter X, Y, Z, label, and CRS values as needed.
4. Add the observation with ``Ctrl+Shift+A``, or use ``Ctrl+Shift+N`` to add it and move to the next image.
5. Use ``N`` and ``P`` for fast single-key navigation. ``Ctrl+N`` and ``Ctrl+P`` remain available as alternatives.
6. Export the observations from ``File > Export`` as TXT or CSV.

Observation replacement behavior
--------------------------------

Each image has one saved observation. If a selected point is incorrect, select
the correct location and add the observation again. The previous record for that
image is replaced rather than duplicated.

Image display and coordinate behavior
-------------------------------------

GCP Pixel Picker separates source-image coordinates from screen presentation.
A source position ``(x, y)`` is displayed using the current scale and offsets,
and mouse clicks are transformed back to source coordinates using the inverse
mapping.

The ``Fit`` command scales the display to fit the available canvas while
preserving the image aspect ratio. It does not alter the original raster width or
height. Zoom and pan likewise modify only the display transform.

When moving to the next image, the new image is displayed in Fit mode for easier
navigation. Selecting a point and then zooming does not change the stored source
pixel location; the marker remains attached to the same source-image coordinate.

At strong Fit-mode reduction, one displayed screen pixel may represent several
source pixels. For the most precise manual placement, zoom in before selecting the
GCP center.

Clipboard support
-----------------

The Current Record section can copy the generated record directly to the system
clipboard. The Records section can copy selected records or all saved records,
allowing data to be pasted directly into another application without exporting a
file first.

Image metadata
--------------

Right-click inside the image and choose ``Image metadata`` (or press ``I``) to
view information including:

* file name and path;
* raster width and height;
* band names or band count;
* file type and file size;
* current zoom level;
* selected pixel; and
* image position within the opened folder.

Download a release
------------------

Prebuilt application packages are published from the GitHub ``Releases`` tab:

https://github.com/MAGALA-RICHARD/GCP/releases

Windows
~~~~~~~

Windows users should normally download the latest executable or Windows ZIP from
the most recent release. Python is not required for the packaged Windows build.

Typical assets include::

    GCPPixelPicker.exe
    GCPPixelPicker-Windows-x64.zip

macOS
~~~~~

If a compatible prebuilt macOS package is not available, build GCP Pixel Picker
from source. macOS compatibility can depend on processor architecture, application
signing, and native GDAL/Rasterio dependencies.

Linux
~~~~~

When available, Linux builds are published in the Releases tab, typically as a
compressed archive. Linux users can also run or build directly from source.

Requirements
------------

Users running from source should use Python 3.12 or a compatible version and
install the project requirements::

    python -m pip install --upgrade pip
    pip install -r requirements.txt

The main Python dependencies include Pillow, NumPy, and Rasterio. Rasterio depends
on GDAL, so macOS and Linux source builds may require compatible native GDAL
libraries.

Running from source
-------------------

Clone or download the repository, install the requirements, and run::

    python main.py

On macOS, if Rasterio installation fails because GDAL is unavailable, install
GDAL first and then reinstall the project requirements::

    brew install gdal
    pip install -r requirements.txt

Building packaged applications
------------------------------

Platform-specific PyInstaller specifications and GitHub Actions workflows are
included in the project. Native application packages should be built on the
operating system they target.

Windows::

    pyinstaller --clean --noconfirm GCPPixelPicker.spec

macOS::

    pyinstaller --clean --noconfirm GCPPixelPicker-macos.spec

Linux::

    pyinstaller --clean --noconfirm GCPPixelPicker-linux.spec

Project files
-------------

``main.py``
    Tkinter user interface, navigation, image interaction, shortcuts, metadata,
    clipboard tools, record management, and export workflow.

``helpers.py``
    Image loading and record creation, grouping, replacement, formatting,
    removal, sorting, and export utilities.

Coordinate integrity
--------------------

The viewer intentionally distinguishes source-image coordinates from display
coordinates. Pixel coordinates are computed against the original raster using the
current zoom and view offsets. Fit, zoom, pan, and panel resizing do not redefine
the source raster geometry.
