GCP Pixel Picker
================

GCP Pixel Picker is a cross-platform desktop utility for selecting Ground
Control Point (GCP) pixel locations from RGB and multispectral imagery and
exporting the resulting observations to text files.

The viewer preserves source-image geometry during normal use. Images open at
100% scale, where one source raster pixel maps to one displayed image pixel.
Resizing the application window or dragging the divider between the image viewer
and information panel changes only the visible workspace; it does not silently
rescale the source image.

Features
--------

* Open a directory containing JPG, JPEG, PNG, TIF, or TIFF images.
* Browse images with Previous and Next controls.
* Select a GCP by clicking directly on the source image.
* Keep one saved observation per image; adding again replaces that image's
  previous pixel location.
* Enter optional X, Y, Z, label, and CRS information.
* Export all observations or export by image-file extension.
* Read multispectral TIFF files with Rasterio and NumPy.
* Inspect image metadata from the right-click context menu.
* Zoom with the mouse wheel, toolbar buttons, or keyboard.
* Pan with the middle mouse button.
* Resize the image and information panels with the draggable divider.
* Use native application packaging for Windows, macOS, and Linux.

Keyboard shortcuts
------------------

==================  ========================================
Shortcut            Action
==================  ========================================
Ctrl+O              Open an image directory
Ctrl+Shift+A        Add/update the current observation
Ctrl+Shift+N        Add/update the observation and go next
Ctrl+N              Next image
Ctrl+P              Previous image
Ctrl+E              Export observations
F                   Fit image to the viewer
0                   Show image at 100% / original scale
+                   Zoom in
-                   Zoom out
I                   Show image metadata
==================  ========================================

On macOS, Tkinter receives the Control-key shortcuts above as written. If you
later prefer Command-key equivalents, they can be added without changing the
underlying workflow.

Mouse controls
--------------

==================  ========================================
Mouse action        Result
==================  ========================================
Left click          Select a pixel/GCP center
Mouse wheel         Zoom around the pointer
Middle-button drag  Pan the image
Right click         Open the image context menu
==================  ========================================

Observation replacement behavior
--------------------------------

Each image has one saved observation. If a point is wrong, click the correct
location and add the observation again. The existing record for that image is
replaced by the latest pixel location rather than creating a duplicate.

Requirements for source development
-----------------------------------

* Python 3.12 or newer recommended.
* Tk/Tkinter supplied by the Python installation or operating system.
* Pillow.
* NumPy.
* Rasterio.

Install the Python dependencies with::

    python -m pip install -r requirements.txt

Running from source
-------------------

Keep the project files together, then run::

    python main.py

On Linux, if Tkinter is not installed by the distribution, install the Tk
package first. Examples::

    # Ubuntu / Debian
    sudo apt install python3-tk

    # Fedora
    sudo dnf install python3-tkinter

    # Arch Linux
    sudo pacman -S tk

Platform-specific builds
------------------------

PyInstaller produces binaries for the operating system on which it runs. Build
Windows on Windows, macOS on macOS, and Linux on Linux. PyInstaller is not a
cross-compiler.

Windows executable
~~~~~~~~~~~~~~~~~~

From Command Prompt::

    build_windows.bat

Or from PowerShell::

    Set-ExecutionPolicy -Scope Process Bypass
    .\build_windows.ps1

The result is::

    dist\GCPPixelPicker.exe

The Windows build uses ``GCPPixelPicker.spec`` and embeds ``app_icon.ico``.

macOS application
~~~~~~~~~~~~~~~~~

Open Terminal in the project directory and run::

    chmod +x build_macos.sh
    ./build_macos.sh

The result is::

    dist/GCP Pixel Picker.app

The macOS build uses ``GCPPixelPicker-macos.spec`` and ``app_icon.icns``.

For local testing, launch it with::

    open "dist/GCP Pixel Picker.app"

Unsigned applications distributed outside the Mac App Store may trigger
Gatekeeper. For public distribution, sign the app with an Apple Developer ID
and optionally notarize it. The supplied build script intentionally does not
insert someone else's signing identity.

Linux executable
~~~~~~~~~~~~~~~~

Open a terminal in the project directory and run::

    chmod +x build_linux.sh
    ./build_linux.sh

The result is::

    dist/GCPPixelPicker

Run it with::

    ./dist/GCPPixelPicker

Linux binaries are sensitive to the distribution and system libraries used for
the build. For broad distribution, build on the oldest Linux distribution you
intend to support, or provide separate builds for major distribution families.

Executable architecture
-----------------------

The generated program architecture follows the Python interpreter used during
the build. For example, an ARM64 Python installation produces an ARM64-targeted
build where PyInstaller and the dependencies support it. Build separately on
Intel/AMD64 and ARM64 machines when you need native packages for both.

Manual PyInstaller builds
-------------------------

Windows::

    py -3.12 -m venv .venv
    .venv\Scripts\activate
    python -m pip install -r requirements.txt
    pyinstaller --clean --noconfirm GCPPixelPicker.spec

macOS::

    python3 -m venv .venv-macos
    source .venv-macos/bin/activate
    python -m pip install -r requirements.txt
    pyinstaller --clean --noconfirm GCPPixelPicker-macos.spec

Linux::

    python3 -m venv .venv-linux
    source .venv-linux/bin/activate
    python -m pip install -r requirements.txt
    pyinstaller --clean --noconfirm GCPPixelPicker-linux.spec

Ruff formatting and linting
---------------------------

The included ``pyproject.toml`` configures Ruff for Python 3.12 and a compact
120-character line length::

    ruff format main.py helpers.py
    ruff check --fix main.py helpers.py
    ruff check main.py helpers.py

Project files
-------------

``main.py``
    Tkinter GUI, viewer, navigation, zoom/pan, context menu, shortcuts,
    metadata, records, and export workflow.

``helpers.py``
    Image/raster loading, natural sorting, record creation/replacement,
    grouping, formatting, and export.

``app_icon.png``
    Cross-platform runtime icon asset.

``app_icon.ico``
    Windows application icon.

``app_icon.icns``
    macOS application icon.

``GCPPixelPicker.spec``
    Windows PyInstaller configuration.

``GCPPixelPicker-macos.spec``
    macOS ``.app`` PyInstaller configuration.

``GCPPixelPicker-linux.spec``
    Linux executable PyInstaller configuration.

``build_windows.bat`` / ``build_windows.ps1``
    One-command Windows build scripts.

``build_macos.sh``
    One-command macOS build script.

``build_linux.sh``
    One-command Linux build script.

``requirements.txt``
    Runtime, development, and build dependencies.

``pyproject.toml``
    Project metadata and Ruff configuration.

Notes for reviewers
-------------------

The viewer intentionally separates source-image coordinates from screen
presentation. Pixel coordinates are calculated against the original raster
using the active zoom and view offsets. Panel resizing does not alter source
width, source height, or the selected source pixel coordinate.

For TIFF imagery, Rasterio supplies the original raster width, height, and band
metadata. A display composite may be contrast-stretched for visualization, but
its width and height remain identical to the source raster, so click coordinates
remain in source-pixel space.
