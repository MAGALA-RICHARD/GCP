from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _natural_key(path: Path):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", path.name)]


def discover_folder_images(selected_path):
    selected = Path(selected_path).resolve()
    files = sorted(
        (p.resolve() for p in selected.parent.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=_natural_key,
    )
    if selected not in files:
        files.append(selected)
        files.sort(key=_natural_key)
    return files, files.index(selected)


def _stretch_uint8(array):
    """Contrast-stretch one raster band while respecting masks and NoData."""
    if np.ma.isMaskedArray(array):
        array = array.astype(np.float32).filled(np.nan)
    else:
        array = np.asarray(array, dtype=np.float32)

    finite = np.isfinite(array)
    if not finite.any():
        return np.zeros(array.shape, dtype=np.uint8)

    values = array[finite]
    lo, hi = np.percentile(values, (2, 98))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(values.min()), float(values.max())
    if hi <= lo:
        return np.zeros(array.shape, dtype=np.uint8)

    scaled = np.zeros(array.shape, dtype=np.float32)
    scaled[finite] = np.clip((array[finite] - lo) / (hi - lo), 0, 1) * 255
    return scaled.astype(np.uint8)


def _raster_to_pil(path):
    with rasterio.open(path) as src:
        width, height, count = src.width, src.height, src.count
        descriptions = [d.strip() if d else "" for d in src.descriptions]
        band_names = [d or f"Band {i}" for i, d in enumerate(descriptions, 1)]

        if count <= 0:
            raise ValueError("Raster contains no bands.")

        if count == 1:
            data = _stretch_uint8(src.read(1, masked=True))
            image = Image.fromarray(data, mode="L").convert("RGB")
        else:
            # Prefer true-color bands when descriptions identify them.
            # Otherwise use the first three bands. This affects display only;
            # source raster dimensions and pixel coordinates remain unchanged.
            names = [name.casefold() for name in band_names]

            def find_band(*terms):
                for index, name in enumerate(names, 1):
                    if any(term in name for term in terms):
                        return index
                return None

            red = find_band("red")
            green = find_band("green")
            blue = find_band("blue")
            indexes = [red, green, blue] if all((red, green, blue)) else list(range(1, min(count, 3) + 1))

            channels = [_stretch_uint8(src.read(i, masked=True)) for i in indexes]
            while len(channels) < 3:
                channels.append(channels[-1])
            image = Image.fromarray(np.dstack(channels[:3]), mode="RGB")

    if image.size != (width, height):
        raise RuntimeError("Image geometry changed while loading the raster.")

    return {
        "image": image,
        "width": width,
        "height": height,
        "bands": count,
        "band_names": band_names,
    }


def load_image_data(path):
    path = Path(path)
    if path.suffix.lower() in {".tif", ".tiff"}:
        return _raster_to_pil(path)

    with Image.open(path) as source:
        width, height = source.size
        band_names = list(source.getbands())
        band_count = len(band_names)
        image = source.convert("RGB") if source.mode != "RGB" else source.copy()

    if image.size != (width, height):
        raise RuntimeError("Image geometry changed while loading.")

    return {
        "image": image,
        "width": width,
        "height": height,
        "bands": band_count,
        "band_names": band_names,
    }


def create_record(selected, image_path, x, y, z, label):
    if selected is None or image_path is None:
        return None

    xyz = tuple(v.strip() for v in (x, y, z))
    if any(xyz) and not all(xyz):
        return None

    if all(xyz):
        try:
            gx, gy, gz = (float(v) for v in xyz)
        except ValueError:
            return None
    else:
        gx = gy = gz = ""

    px, py = map(float, selected)
    return gx, gy, gz, px, py, Path(image_path).name, label.strip()


def add_record(records, record):
    """Insert or replace one observation per image within its suffix group."""
    filename = record[5]
    suffix = Path(filename).suffix.lower()
    group = records.setdefault(suffix, [])

    for i, existing in enumerate(group):
        if existing[5].casefold() == filename.casefold():
            group[i] = record
            return suffix, False

    group.append(record)
    return suffix, True


def remove_record(records, suffix, record):
    group = records.get(suffix)
    if not group:
        return
    try:
        group.remove(record)
    except ValueError:
        return
    if not group:
        records.pop(suffix, None)


def sorted_group(records, suffix):
    return sorted(records.get(suffix, []), key=lambda r: (r[5].casefold(), r[6].casefold(), r[3], r[4]))


def sorted_all_records(records):
    return [record for suffix in sorted(records) for record in sorted_group(records, suffix)]


def total_records(records):
    return sum(len(group) for group in records.values())


def _number(value):
    if value == "":
        return ""
    if isinstance(value, float):
        return f"{value:.10g}"
    return str(value)


def format_record(record):
    gx, gy, gz, px, py, filename, label = record
    fields = []
    if gx != "":
        fields.extend((_number(gx), _number(gy), _number(gz)))
    fields.extend((f"{px:.3f}", f"{py:.3f}", filename))
    if label:
        fields.append(label)
    return " ".join(fields)


def export_records(path, records, crs=""):
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        if crs:
            stream.write(f"# CRS: {crs}\n")
        for record in records:
            stream.write(format_record(record) + "\n")


def update_navigation_buttons(self):
    active = bool(self.image_files) and not self.loading
    self.prev_button.config(state="normal" if active and self.current_index > 0 else "disabled")
    self.next_button.config(state="normal" if active and self.current_index < len(self.image_files) - 1 else "disabled")
