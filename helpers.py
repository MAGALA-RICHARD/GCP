import re
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import rasterio

    RASTERIO_AVAILABLE = True
except ImportError:
    rasterio = None
    RASTERIO_AVAILABLE = False

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
}


# ============================================================
# File discovery
# ============================================================


def natural_sort_key(path):
    """
    Natural sorting.

    Example:
        image1.jpg
        image2.jpg
        image10.jpg

    instead of:
        image1.jpg
        image10.jpg
        image2.jpg
    """

    name = Path(path).name.lower()
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def discover_folder_images(selected_path):
    """
    Discover supported images in the same folder as selected_path.

    Returns:
        files: list[Path]
        selected_index: int
    """

    selected_path = Path(selected_path).resolve()
    folder = selected_path.parent

    files = [
        path.resolve()
        for path in folder.iterdir()
        if (path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    ]

    if selected_path not in files:
        files.append(selected_path)
    files.sort(key=natural_sort_key)
    selected_index = files.index(selected_path)
    return files, selected_index


# ============================================================
# Raster / image loading
# ============================================================


def normalize_band(array):
    """
    Convert a raster band to an 8-bit display representation.

    IMPORTANT:
    This does not change the original raster dimensions.

    Only pixel values are stretched for visualization.
    """

    array = np.asarray(array, dtype=np.float32)
    valid = np.isfinite(array)
    if not np.any(valid):
        return np.zeros(array.shape, dtype=np.uint8)
    values = array[valid]
    low = np.percentile(values, 2)
    high = np.percentile(values, 98)

    if high <= low:
        low = float(values.min())
        high = float(values.max())

    if high <= low:
        return np.zeros(array.shape, dtype=np.uint8)

    output = (array - low) / (high - low)

    output = np.clip(output, 0, 1)

    output[~valid] = 0

    return (output * 255).astype(np.uint8)


def choose_display_bands(descriptions, count):
    """Return RGB band indexes if identifiable; otherwise use the first 3 bands."""

    cleaned = [
        str(value).lower().replace("_", "").replace("-", "").replace(" ", "")
        for value in descriptions
    ]

    def find(names):
        for name in names:
            for i, desc in enumerate(cleaned):
                if desc == name:
                    return i + 1

        for name in names:
            for i, desc in enumerate(cleaned):
                if name in desc:
                    return i + 1

        return None

    red = find(["red", "r"])
    green = find(["green", "g"])
    blue = find(["blue", "b"])

    if all(index is not None for index in (red, green, blue)):
        return [red, green, blue]

    return list(range(1, min(count, 3) + 1))


def load_pillow_image(path):
    """Load a Pillow-readable image while preserving original dimensions."""

    source = Image.open(Path(path))
    source.load()

    width, height = source.size

    if source.mode not in ("RGB", "RGBA"):
        source = source.convert("RGB")

    return {
        "image": source,
        "width": width,
        "height": height,
        "bands": len(source.getbands()),
        "band_names": list(source.getbands()),
    }


def load_raster_image(path):
    """Load a TIFF/multi-spectral raster without changing its dimensions."""

    if not RASTERIO_AVAILABLE:
        raise RuntimeError("Rasterio is not installed.")

    with rasterio.open(Path(path)) as src:
        width, height, count = src.width, src.height, src.count

        descriptions = [
            desc.strip() if desc else f"Band {i + 1}" for i, desc in enumerate(src.descriptions)
        ]

        if count == 1:
            band = normalize_band(src.read(1))
            rgb = np.stack([band, band, band], axis=-1)

        else:
            indexes = choose_display_bands(descriptions, count)
            bands = [normalize_band(src.read(i)) for i in indexes]

            while len(bands) < 3:
                bands.append(bands[-1])

            rgb = np.stack(bands[:3], axis=-1)

        return {
            "image": Image.fromarray(rgb.astype(np.uint8), mode="RGB"),
            "width": width,
            "height": height,
            "bands": count,
            "band_names": descriptions,
        }


def load_image_data(path):
    """Load an image using rasterio for TIFFs, otherwise Pillow."""
    path = Path(path)
    if path.suffix.lower() in {".tif", ".tiff"} and RASTERIO_AVAILABLE:
        return load_raster_image(path)
    return load_pillow_image(path)


# ============================================================
# Record handling
# ============================================================


def create_record(selected, image_path, x_value, y_value, z_value, label):
    """Create a GCP record from map coordinates, pixel coordinates, image name, and label."""
    if selected is None or image_path is None:
        return None
    gx, gy, gz = (value.strip() for value in (x_value, y_value, z_value))
    label = label.strip()
    if any((gx, gy, gz)) and not all((gx, gy, gz)):
        return None
    pixel_x, pixel_y = selected
    return (
        gx,
        gy,
        gz,
        round(float(pixel_x), 3),
        round(float(pixel_y), 3),
        Path(image_path).name,
        label,
    )


def format_record(record):
    """Format a GCP record for TXT export."""
    gx, gy, gz, pixel_x, pixel_y, filename, label = record
    parts = []
    if all((gx, gy, gz)):
        parts.extend((gx, gy, gz))
    parts.extend(
        (
            f"{pixel_x:.3f}",
            f"{pixel_y:.3f}",
            filename,
        )
    )
    if label:
        parts.append(label)
    return " ".join(parts)


def record_sort_key(record):
    """
    Consistent ordering for UI and export.
    """

    return (
        record[5].lower(),
        record[6].lower(),
        record[3],
        record[4],
    )


def add_record(records, record):
    filename = record[5]
    suffix = Path(filename).suffix.lower()
    group = records.setdefault(suffix, [])

    for i, existing in enumerate(group):
        if existing[5] == filename:
            group[i] = record
            return suffix, False

    group.append(record)
    return suffix, True


def remove_record(records, suffix, record):
    """
    Remove one record from the records' dictionary.
    """
    bucket = records.get(suffix)
    if bucket is None:
        return
    bucket.remove(record)
    if not bucket:
        del records[suffix]


def total_records(records):
    """
    Total number of observations.
    """
    return sum(len(group) for group in records.values())


def sorted_group(records, suffix):
    """
    Return one suffix group in stable order.
    """
    return sorted(records.get(suffix, set()), key=record_sort_key)


def sorted_all_records(records):
    """
    Return every observation grouped and sorted by extension.
    """
    output = []
    for suffix in sorted(records):
        output.extend(sorted_group(records, suffix))
    return output


# ============================================================
# Export
# ============================================================


def export_records(path, records, crs=""):
    """
    Write GCP observations to text file.
    """
    path = Path(path)
    with path.open("w", encoding="utf-8") as file:
        crs = crs.strip()
        if crs:
            file.write(crs + "\n")
        for record in records:
            file.write(format_record(record) + "\n")
