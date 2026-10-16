GCP Pixel Location Picker
================

GCP Pixel Picker is a desktop utility for selecting Ground Control Point (GCP)
pixel locations from RGB and multi-spectral imagery and exporting the resulting
observations to text files.

The viewer is designed to preserve image geometry during normal use. Images are
opened at their original display scale (100%), where one source-image pixel maps
to one displayed image pixel. Resizing the application window or dragging the
separator between the image viewer and information panel does not automatically
rescale the image.

Features
--------

* Open a directory containing JPG, JPEG, PNG, TIF, or TIFF images.
* Browse images in the selected directory with Previous and Next controls.
* Select a GCP by clicking directly on the image.
* Store one active observation per image; adding a new point for the same image
  updates the previously stored pixel location.
* Enter optional X, Y, Z, label, and CRS information.
* Export all observations or export records by image-file extension.
* Inspect image metadata from the right-click context menu.
* Zoom with the mouse wheel, toolbar buttons, or keyboard.
* Pan the image with the middle mouse button.
* Drag the divider between the image viewer and the information panel.
* Use a right-click context menu for common image-viewer commands.

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

Typical workflow
----------------

1. Press ``Ctrl+O`` or click ``Open Folder`` and select an image directory.
2. Click the center of the GCP in the displayed image.
3. Enter X, Y, Z, label, and CRS values as needed.
4. Press ``Ctrl+Shift+A`` to save/update the current image observation, or
   ``Ctrl+Shift+N`` to save/update it and immediately move to the next image.
5. Use ``Ctrl+N`` and ``Ctrl+P`` to navigate through the folder.
6. Press ``Ctrl+E`` to export the observations.

Observation replacement behavior
--------------------------------

Each image has one saved observation. If the selected point for an image is
wrong, click the correct location and add the observation again. The existing
record for that image is replaced with the latest pixel location instead of
creating a duplicate image record.

Image display behavior
----------------------

The application separates image scale from panel size. Dragging the divider,
resizing the window, or changing the width of the information panel only changes
the visible viewing area; it does not change the current image zoom.

When an image is first loaded it is shown at 100% scale. The ``Fit`` command is
explicit and only rescales the display when requested. The ``100%`` command
returns the image to its original display scale.

Image metadata
--------------

Right-click inside the image and choose ``Image metadata`` (or press ``I``) to
view information including:

* file name and path;
* raster width and height;
* band names or band count;
* file type and file size;
* current zoom level;
* currently selected pixel; and
* image position within the opened directory.

Requirements
------------

The application requires Python 3.12 or a compatible Python 3 version and the
Python packages used by ``main.py`` and ``helpers.py``. Pillow is required for
image display::

    pip install pillow

Additional packages may be required by ``helpers.py`` depending on the image
formats and raster-loading implementation used by the project.

Running the application
-----------------------

Keep ``main.py`` and ``helpers.py`` in the same project directory, then run::

    python main.py

On Windows, the application can also be started from an IDE such as PyCharm or
by using the configured Python interpreter for the project.

Project files
-------------

``main.py``
    Tkinter user interface, navigation, image interaction, shortcuts, metadata,
    record-management workflow, and export dialog.

``helpers.py``
    Image discovery/loading and record creation, grouping, replacement,
    formatting, removal, sorting, and export utilities.

Notes for reviewers
-------------------

The viewer intentionally distinguishes between source-image coordinates and
screen presentation. Pixel coordinates are computed against the source raster
using the current zoom and view offsets, while panel resizing does not alter the
underlying source dimensions. This preserves consistent coordinate selection
across the image workflow.
