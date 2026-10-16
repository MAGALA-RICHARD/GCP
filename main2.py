import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageTk

try:
    import rasterio

    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


class GCPPicker:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

    BG = "#111827"
    PANEL = "#1f2937"
    CANVAS_BG = "#030712"
    TEXT = "#f9fafb"
    MUTED = "#9ca3af"
    BLUE = "#2563eb"
    GREEN = "#059669"
    CYAN = "#0891b2"
    PURPLE = "#7c3aed"
    RED = "#dc2626"
    YELLOW = "#fbbf24"

    def __init__(self, root):
        self.root = root
        self.root.title("GCP Pixel Picker")
        self.root.geometry("1450x900")
        self.root.minsize(1050, 680)
        self.root.configure(bg=self.BG)

        self.image = None
        self.tk_image = None
        self.image_path = None

        self.image_files = []
        self.current_index = -1

        self.source_width = 0
        self.source_height = 0
        self.band_count = 0
        self.band_names = []

        self.scale = 1.0
        self.min_scale = 0.01
        self.max_scale = 20.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        self.selected = None
        self.pan_start = None
        self.loading = False
        self.first_display = True

        # Records grouped ONLY by actual file suffix.
        #
        # Example:
        # {
        #     ".jpg": {record1, record2},
        #     ".tif": {record3, record4}
        # }
        self.records = {}

        # Tree item -> (suffix, record)
        self.tree_records = {}

        self.x_var = tk.StringVar()
        self.y_var = tk.StringVar()
        self.z_var = tk.StringVar()
        self.label_var = tk.StringVar()
        self.crs_var = tk.StringVar(value="EPSG:4326")

        for var in (self.x_var, self.y_var, self.z_var, self.label_var):
            var.trace_add("write", lambda *_: self.update_description())

        self.build_ui()
        self.bind_shortcuts()

    # ==========================================================
    # UI
    # ==========================================================

    def make_button(self, parent, text, command, color="#374151"):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            disabledforeground="#6b7280",
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )

    def make_entry(self, parent, variable, width=18):
        return tk.Entry(
            parent,
            textvariable=variable,
            width=width,
            bg=self.PANEL,
            fg=self.TEXT,
            insertbackground="white",
            selectbackground=self.BLUE,
            selectforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
        )

    def form_row(self, parent, title, variable):
        row = tk.Frame(parent, bg=self.PANEL, highlightbackground="green")
        row.pack(fill="x", pady=3)

        tk.Label(
            row,
            text=title,
            width=14,
            anchor="w",
            bg=self.PANEL,
            fg="#e5e7eb",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        self.make_entry(row, variable).pack(side="left", fill="x", expand=True, ipady=5)

    def build_ui(self):
        toolbar = tk.Frame(self.root, bg=self.PANEL, height=56)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        self.open_button = self.make_button(toolbar, "Open Image", self.open_image, self.BLUE)
        self.open_button.pack(side="left", padx=(10, 4), pady=9)

        self.prev_button = self.make_button(toolbar, "◀ Previous", self.previous_image)
        self.prev_button.pack(side="left", padx=4, pady=9)

        self.next_button = self.make_button(toolbar, "Next ▶", self.next_image)
        self.next_button.pack(side="left", padx=4, pady=9)

        self.add_button = self.make_button(toolbar, "+ Add", self.add_observation, self.GREEN)
        self.add_button.pack(side="left", padx=(14, 4), pady=9)

        self.add_next_button = self.make_button(
            toolbar, "+ Add & Next", self.add_and_next, "#047857"
        )
        self.add_next_button.pack(side="left", padx=4, pady=9)

        self.export_button = self.make_button(toolbar, "Export TXT", self.export_txt, self.PURPLE)
        self.export_button.pack(side="left", padx=(14, 4), pady=9)

        self.make_button(toolbar, "Fit to current window", self.fit_image).pack(
            side="left", padx=(14, 4), pady=9
        )

        self.make_button(toolbar, "100%", self.actual_size).pack(side="left", padx=4, pady=9)

        self.zoom_label = tk.Label(
            toolbar, text="Zoom: --", bg=self.PANEL, fg="#93c5fd", font=("Segoe UI", 10, "bold")
        )
        self.zoom_label.pack(side="right", padx=15)

        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        left = tk.Frame(body, bg=self.BG)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(body, bg=self.PANEL, width=380)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        info = tk.Frame(left, bg=self.BG)
        info.pack(fill="x", pady=(0, 7))

        file_row = tk.Frame(info, bg=self.BG)
        file_row.pack(fill="x")

        self.filename_label = tk.Label(
            file_row,
            text="No image loaded",
            bg=self.BG,
            fg=self.TEXT,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        self.filename_label.pack(side="left", fill="x", expand=True)

        self.counter_label = tk.Label(
            file_row, text="", bg=self.BG, fg="#60a5fa", font=("Segoe UI", 10, "bold")
        )
        self.counter_label.pack(side="right")

        self.info_label = tk.Label(
            info,
            text="Open an image and click the center of the GCP.",
            bg=self.BG,
            fg=self.MUTED,
            anchor="w",
            font=("Segoe UI", 9),
        )
        self.info_label.pack(fill="x")

        self.band_label = tk.Label(
            info, text="Bands: --", bg=self.BG, fg="#94a3b8", anchor="w", font=("Segoe UI", 9)
        )
        self.band_label.pack(fill="x")

        self.pixel_label = tk.Label(
            info,
            text="Pixel: --",
            bg=self.BG,
            fg=self.YELLOW,
            anchor="w",
            font=("Segoe UI", 12, "bold"),
        )
        self.pixel_label.pack(fill="x", pady=(3, 0))

        self.canvas = tk.Canvas(
            left,
            bg=self.CANVAS_BG,
            cursor="cross",
            highlightthickness=1,
            highlightbackground="#374151",
            highlightcolor="#3b82f6",
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.select_point)

        self.canvas.bind("<MouseWheel>", self.mouse_zoom)

        self.canvas.bind("<Button-4>", self.mouse_zoom_linux)

        self.canvas.bind("<Button-5>", self.mouse_zoom_linux)

        self.canvas.bind("<ButtonPress-2>", self.start_pan)

        self.canvas.bind("<B2-Motion>", self.pan)

        self.canvas.bind("<ButtonRelease-2>", self.end_pan)

        self.canvas.bind("<ButtonPress-3>", self.start_pan)

        self.canvas.bind("<B3-Motion>", self.pan)

        self.canvas.bind("<ButtonRelease-3>", self.end_pan)

        self.canvas.bind("<Configure>", self.canvas_resized)

        # ------------------------------------------------------
        # Right panel
        # ------------------------------------------------------

        tk.Label(
            right,
            text="GCP INFORMATION",
            bg=self.PANEL,
            fg="#93c5fd",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=14, pady=(14, 10))

        form = tk.Frame(right, bg=self.PANEL)
        form.pack(fill="x", padx=14)

        self.form_row(form, "X / Longitude", self.x_var)

        self.form_row(form, "Y / Latitude", self.y_var)

        self.form_row(form, "Z / Elevation", self.z_var)

        self.form_row(form, "Label", self.label_var)

        self.form_row(form, "CRS", self.crs_var)

        tk.Label(
            right,
            text=("XYZ and label stay unchanged while moving\nbetween overlapping images."),
            justify="left",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=14, pady=(8, 12))

        tk.Label(
            right, text="CURRENT RECORD", bg=self.PANEL, fg="#c4b5fd", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=14)

        self.description = tk.Text(
            right,
            height=5,
            wrap="word",
            bg=self.BG,
            fg="#ddd6fe",
            insertbackground="white",
            relief="flat",
            bd=0,
            font=("Consolas", 9),
        )
        self.description.pack(fill="x", padx=14, pady=(6, 12))

        self.description.config(state="disabled")

        stats_row = tk.Frame(right, bg=self.PANEL)
        stats_row.pack(fill="x", padx=14)

        tk.Label(
            stats_row,
            text="OBSERVATIONS",
            bg=self.PANEL,
            fg="#86efac",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        self.obs_count_label = tk.Label(
            stats_row, text="0", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 10, "bold")
        )
        self.obs_count_label.pack(side="right")

        self.group_label = tk.Label(
            right, text="Groups: --", bg=self.PANEL, fg="#94a3b8", anchor="w", font=("Segoe UI", 9)
        )
        self.group_label.pack(fill="x", padx=14, pady=(3, 5))

        table_frame = tk.Frame(right, bg=self.PANEL)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        self.tree = ttk.Treeview(
            table_frame, columns=("suffix", "label", "image", "pixel"), show="headings", height=12
        )

        self.tree.heading("suffix", text="Type")

        self.tree.heading("label", text="GCP")

        self.tree.heading("image", text="Image")

        self.tree.heading("pixel", text="Pixel")

        self.tree.column("suffix", width=50, anchor="center")

        self.tree.column("label", width=60)

        self.tree.column("image", width=150)

        self.tree.column("pixel", width=100)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)

        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar.pack(side="right", fill="y")

        action_row = tk.Frame(right, bg=self.PANEL)
        action_row.pack(fill="x", padx=14, pady=(0, 14))

        self.make_button(action_row, "Delete Selected", self.delete_selected, self.RED).pack(
            side="left"
        )

        self.make_button(action_row, "Clear All", self.clear_all).pack(side="right")

        self.update_navigation_buttons()

    # ==========================================================
    # File discovery
    # ==========================================================

    def natural_sort_key(self, path):
        import re

        name = Path(path).name.lower()

        return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]

    def discover_folder_images(self, selected_path):
        selected_path = Path(selected_path).resolve()

        folder = selected_path.parent

        try:
            files = [
                path.resolve()
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in self.IMAGE_EXTENSIONS
            ]

        except OSError as e:
            messagebox.showerror("Folder error", str(e))
            files = [selected_path]

        files.sort(key=self.natural_sort_key)

        self.image_files = files

        try:
            self.current_index = self.image_files.index(selected_path)

        except ValueError:
            self.image_files.append(selected_path)

            self.image_files.sort(key=self.natural_sort_key)

            self.current_index = self.image_files.index(selected_path)

        self.update_navigation_buttons()
        self.update_counter()

    # ==========================================================
    # Image loading
    # ==========================================================

    def open_image(self):
        if self.loading:
            return

        path = filedialog.askopenfilename(
            filetypes=[
                ("Supported images", "*.jpg *.jpeg *.png *.tif *.tiff"),
                ("JPEG", "*.jpg *.jpeg"),
                ("TIFF", "*.tif *.tiff"),
                ("PNG", "*.png"),
                ("All files", "*.*"),
            ]
        )

        if not path:
            return

        path = Path(path).resolve()

        self.discover_folder_images(path)

        self.load_image(path)

    def load_image(self, path):
        if self.loading:
            return

        self.loading = True

        self.info_label.config(text="Loading image...", fg="#60a5fa")

        self.update_navigation_buttons()

        threading.Thread(target=self.load_image_worker, args=(Path(path),), daemon=True).start()

    def load_image_worker(self, path):
        try:
            suffix = path.suffix.lower()

            if suffix in {".tif", ".tiff"} and RASTERIO_AVAILABLE:
                data = self.load_raster_image(path)

            else:
                data = self.load_pillow_image(path)

            self.root.after(0, lambda: self.finish_loading(path, data))

        except Exception:
            self.root.after(0, lambda: self.loading_failed(str(e)))

    def load_pillow_image(self, path):
        source = Image.open(path)

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

    def load_raster_image(self, path):
        with rasterio.open(path) as src:
            width = src.width
            height = src.height
            count = src.count

            descriptions = [
                desc.strip() if desc else f"Band {i + 1}" for i, desc in enumerate(src.descriptions)
            ]

            if count == 1:
                band = self.normalize_band(src.read(1))

                rgb = np.stack([band, band, band], axis=-1)

            else:
                indexes = self.choose_display_bands(descriptions, count)

                bands = [self.normalize_band(src.read(index)) for index in indexes]

                while len(bands) < 3:
                    bands.append(bands[-1])

                rgb = np.stack(bands[:3], axis=-1)

            image = Image.fromarray(rgb.astype(np.uint8), mode="RGB")

            return {
                "image": image,
                "width": width,
                "height": height,
                "bands": count,
                "band_names": descriptions,
            }

    def choose_display_bands(self, descriptions, count):
        cleaned = [
            value.lower().replace("_", "").replace("-", "").replace(" ", "")
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

        if red is not None and green is not None and blue is not None:
            return [red, green, blue]

        return list(range(1, min(count, 3) + 1))

    def normalize_band(self, array):
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

    def finish_loading(self, path, data):
        self.image = data["image"]
        self.image_path = Path(path)

        self.source_width = data["width"]
        self.source_height = data["height"]

        self.band_count = data["bands"]
        self.band_names = data["band_names"]

        self.selected = None
        self.loading = False
        self.first_display = True

        try:
            self.current_index = self.image_files.index(self.image_path.resolve())
        except ValueError:
            pass

        filename = self.image_path.name

        self.root.title(f"GCP Pixel Picker - {filename}")

        self.filename_label.config(text=filename)

        self.info_label.config(
            text=(f"Original raster: {self.source_width} × {self.source_height} px"), fg="#34d399"
        )

        if self.band_names:
            self.band_label.config(text=("Bands: " + ", ".join(self.band_names)))
        else:
            self.band_label.config(text=f"Bands: {self.band_count}")

        self.pixel_label.config(text="Pixel: --")

        self.update_description()
        self.update_counter()
        self.update_navigation_buttons()

        self.root.update_idletasks()

        self.fit_image()

    def loading_failed(self, error):
        self.loading = False

        self.info_label.config(text=f"Could not open image: {error}", fg="#f87171")

        self.update_navigation_buttons()

    # ==========================================================
    # Navigation
    # ==========================================================

    def next_image(self):
        if self.loading or not self.image_files or self.current_index >= len(self.image_files) - 1:
            return

        self.current_index += 1

        self.load_image(self.image_files[self.current_index])

    def previous_image(self):
        if self.loading or not self.image_files or self.current_index <= 0:
            return

        self.current_index -= 1

        self.load_image(self.image_files[self.current_index])

    def update_counter(self):
        if self.image_files and self.current_index >= 0:
            self.counter_label.config(text=(f"{self.current_index + 1} / {len(self.image_files)}"))
        else:
            self.counter_label.config(text="")

    def update_navigation_buttons(self):
        previous_available = bool(self.image_files) and self.current_index > 0 and not self.loading

        next_available = (
            bool(self.image_files)
            and 0 <= self.current_index < len(self.image_files) - 1
            and not self.loading
        )

        self.prev_button.config(state=("normal" if previous_available else "disabled"))

        self.next_button.config(state=("normal" if next_available else "disabled"))

    # ==========================================================
    # Records
    # ==========================================================

    def create_record(self):
        if self.selected is None or self.image_path is None:
            return None

        gx = self.x_var.get().strip()
        gy = self.y_var.get().strip()
        gz = self.z_var.get().strip()
        label = self.label_var.get().strip()

        if any((gx, gy, gz)) and not all((gx, gy, gz)):
            return None

        px, py = self.selected

        return (gx, gy, gz, round(px, 3), round(py, 3), self.image_path.name, label)

    def format_record(self, record):
        gx, gy, gz, px, py, filename, label = record

        parts = []

        if gx and gy and gz:
            parts.extend([gx, gy, gz])

        parts.extend([f"{px:.3f}", f"{py:.3f}", filename])

        if label:
            parts.append(label)

        return " ".join(parts)

    def update_description(self):
        record = self.create_record()

        self.description.config(state="normal")

        self.description.delete("1.0", "end")

        if record is not None:
            self.description.insert("1.0", self.format_record(record))

        elif self.selected is not None:
            gx = self.x_var.get().strip()
            gy = self.y_var.get().strip()
            gz = self.z_var.get().strip()

            if any((gx, gy, gz)):
                self.description.insert("1.0", "Provide X, Y and Z together.")

        self.description.config(state="disabled")

    def add_observation(self):
        if self.selected is None:
            messagebox.showwarning("No GCP selected", "Click the center of the GCP first.")
            return False

        gx = self.x_var.get().strip()
        gy = self.y_var.get().strip()
        gz = self.z_var.get().strip()

        if any((gx, gy, gz)) and not all((gx, gy, gz)):
            messagebox.showwarning(
                "Incomplete coordinates", "Provide X, Y and Z together, or leave all three blank."
            )
            return False

        record = self.create_record()

        if record is None:
            return False

        filename = record[5]

        # STRICT extension grouping.
        # No _D / _MS / band-name inference.
        suffix = Path(filename).suffix.lower()

        bucket = self.records.setdefault(suffix, set())

        count_before = len(bucket)

        bucket.add(record)

        # Set prevents exact duplicate automatically.
        if len(bucket) == count_before:
            self.info_label.config(text=(f"Duplicate ignored: {filename}"), fg=self.YELLOW)

            return False

        self.refresh_record_table()

        px, py = self.selected

        self.info_label.config(
            text=(f"Added {suffix}: {filename} @ ({px:.3f}, {py:.3f})"), fg="#34d399"
        )

        return True

    def add_and_next(self):
        if not self.add_observation():
            return

        if self.current_index < len(self.image_files) - 1:
            self.next_image()

        else:
            self.info_label.config(
                text=("Observation added. This is the last image."), fg=self.YELLOW
            )

    def total_records(self):
        return sum(len(records) for records in self.records.values())

    def refresh_record_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.tree_records.clear()

        for suffix in sorted(self.records):
            records = sorted(
                self.records[suffix], key=lambda r: (r[5].lower(), r[6].lower(), r[3], r[4])
            )

            for record in records:
                (gx, gy, gz, px, py, filename, label) = record

                item = self.tree.insert(
                    "", "end", values=(suffix, label or "—", filename, f"{px:.3f}, {py:.3f}")
                )

                self.tree_records[item] = (suffix, record)

        self.obs_count_label.config(text=str(self.total_records()))

        if self.records:
            groups = [
                f"{suffix}: {len(records)}" for suffix, records in sorted(self.records.items())
            ]

            self.group_label.config(text=("Groups: " + "   ".join(groups)))
        else:
            self.group_label.config(text="Groups: --")

    def delete_selected(self):
        selected_items = self.tree.selection()

        if not selected_items:
            return

        for item in selected_items:
            data = self.tree_records.get(item)

            if data is None:
                continue

            suffix, record = data

            bucket = self.records.get(suffix)

            if bucket is not None:
                bucket.discard(record)

                if not bucket:
                    del self.records[suffix]

        self.refresh_record_table()

    def clear_all(self):
        if not self.records:
            return

        confirmed = messagebox.askyesno("Clear all observations", "Delete every saved observation?")

        if not confirmed:
            return

        self.records.clear()

        self.refresh_record_table()

    # ==========================================================
    # Export
    # ==========================================================

    def export_txt(self):
        if not self.records:
            messagebox.showwarning("Nothing to export", "Add at least one observation first.")
            return

        suffixes = sorted(self.records.keys())

        self.show_export_dialog(suffixes)

    def show_export_dialog(self, suffixes):
        dialog = tk.Toplevel(self.root)

        dialog.title("Export Observations")

        dialog.configure(bg=self.PANEL)

        dialog.resizable(False, False)

        dialog.transient(self.root)

        dialog.grab_set()

        tk.Label(
            dialog,
            text="Choose what to export",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(padx=25, pady=(20, 5))

        tk.Label(
            dialog,
            text=("Records are grouped strictly by file extension."),
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(padx=25, pady=(0, 15))

        self.make_button(
            dialog,
            f"Export ALL ({self.total_records()})",
            lambda: self.export_group(dialog, None),
            self.PURPLE,
        ).pack(fill="x", padx=25, pady=4)

        for suffix in suffixes:
            count = len(self.records[suffix])

            self.make_button(
                dialog,
                f"Export {suffix} ({count})",
                lambda s=suffix: self.export_group(dialog, s),
                self.BLUE,
            ).pack(fill="x", padx=25, pady=4)

        self.make_button(dialog, "Cancel", dialog.destroy).pack(fill="x", padx=25, pady=(10, 20))

        dialog.update_idletasks()

        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2

        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2

        dialog.geometry(f"+{x}+{y}")

    def export_group(self, dialog, suffix=None):
        dialog.destroy()

        if suffix is None:
            records = []

            for group_suffix in sorted(self.records):
                records.extend(
                    sorted(
                        self.records[group_suffix],
                        key=lambda r: (r[5].lower(), r[6].lower(), r[3], r[4]),
                    )
                )

            default_name = "gcp_all.txt"

        else:
            records = sorted(
                self.records.get(suffix, set()),
                key=lambda r: (r[5].lower(), r[6].lower(), r[3], r[4]),
            )

            suffix_name = suffix.replace(".", "") or "records"

            default_name = f"gcp_{suffix_name}.txt"

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )

        if not path:
            return

        crs = self.crs_var.get().strip()

        with open(path, "w", encoding="utf-8") as file:
            if crs:
                file.write(crs + "\n")

            for record in records:
                file.write(self.format_record(record) + "\n")

        description = "all groups" if suffix is None else suffix

        messagebox.showinfo(
            "Export complete", (f"Exported {len(records)} record(s) from {description}.\n\n{path}")
        )

    # ==========================================================
    # Pixel selection
    # ==========================================================

    def select_point(self, event):
        if self.image is None:
            return

        # Convert canvas position directly into
        # ORIGINAL source-image coordinates.
        x = (event.x - self.offset_x) / self.scale

        y = (event.y - self.offset_y) / self.scale

        if not (0 <= x < self.source_width and 0 <= y < self.source_height):
            return

        # Keep subpixel precision.
        # DO NOT round to integer pixels.
        x = min(max(float(x), 0.0), self.source_width - 1.0)

        y = min(max(float(y), 0.0), self.source_height - 1.0)

        self.selected = (x, y)

        self.pixel_label.config(text=(f"Pixel: X = {x:.3f}     Y = {y:.3f}"))

        self.info_label.config(
            text=(
                "Selected GCP center • "
                f"Original raster: "
                f"{self.source_width} × "
                f"{self.source_height} px"
            ),
            fg="#34d399",
        )

        self.update_description()
        self.render()

    # ==========================================================
    # Zoom / pan
    # ==========================================================

    def fit_image(self):
        if self.image is None:
            return

        self.canvas.update_idletasks()

        cw = max(self.canvas.winfo_width(), 1)

        ch = max(self.canvas.winfo_height(), 1)

        iw = self.source_width
        ih = self.source_height

        margin = 20

        self.scale = min(max(cw - margin * 2, 1) / iw, max(ch - margin * 2, 1) / ih)

        self.min_scale = self.scale * 0.25

        self.max_scale = max(20.0, self.scale * 100)

        self.offset_x = (cw - iw * self.scale) / 2

        self.offset_y = (ch - ih * self.scale) / 2

        self.render()

    def actual_size(self):
        if self.image is None:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        center_x = (cw / 2 - self.offset_x) / self.scale

        center_y = (ch / 2 - self.offset_y) / self.scale

        self.scale = 1.0

        self.offset_x = cw / 2 - center_x

        self.offset_y = ch / 2 - center_y

        self.render()

    def mouse_zoom(self, event):
        if self.image is None:
            return

        factor = 1.20 if event.delta > 0 else 1 / 1.20

        self.zoom_at(event.x, event.y, factor)

    def mouse_zoom_linux(self, event):
        if self.image is None:
            return

        factor = 1.20 if event.num == 4 else 1 / 1.20

        self.zoom_at(event.x, event.y, factor)

    def zoom_at(self, mouse_x, mouse_y, factor):
        if self.image is None:
            return

        old_scale = self.scale

        new_scale = max(self.min_scale, min(old_scale * factor, self.max_scale))

        if new_scale == old_scale:
            return

        image_x = (mouse_x - self.offset_x) / old_scale

        image_y = (mouse_y - self.offset_y) / old_scale

        self.scale = new_scale

        self.offset_x = mouse_x - image_x * new_scale

        self.offset_y = mouse_y - image_y * new_scale

        self.render()

    def start_pan(self, event):
        if self.image is None:
            return

        self.pan_start = (event.x, event.y, self.offset_x, self.offset_y)

        self.canvas.config(cursor="fleur")

    def pan(self, event):
        if self.pan_start is None:
            return

        (start_x, start_y, old_offset_x, old_offset_y) = self.pan_start

        self.offset_x = old_offset_x + event.x - start_x

        self.offset_y = old_offset_y + event.y - start_y

        self.render()

    def end_pan(self, event=None):
        self.pan_start = None

        self.canvas.config(cursor="cross")

    # ==========================================================
    # Rendering
    # ==========================================================

    def render(self):
        if self.image is None:
            return

        iw = self.source_width
        ih = self.source_height

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        img_left = max(0, int(-self.offset_x / self.scale))

        img_top = max(0, int(-self.offset_y / self.scale))

        img_right = min(iw, int((cw - self.offset_x) / self.scale) + 2)

        img_bottom = min(ih, int((ch - self.offset_y) / self.scale) + 2)

        self.canvas.delete("all")

        if img_right <= img_left or img_bottom <= img_top:
            return

        # Rendering uses a crop/resize only for display.
        # The original raster coordinate system remains unchanged.
        crop = self.image.crop((img_left, img_top, img_right, img_bottom))

        crop_width = max(int((img_right - img_left) * self.scale), 1)

        crop_height = max(int((img_bottom - img_top) * self.scale), 1)

        resample = Image.Resampling.NEAREST if self.scale >= 4 else Image.Resampling.LANCZOS

        crop = crop.resize((crop_width, crop_height), resample)

        self.tk_image = ImageTk.PhotoImage(crop)

        canvas_x = self.offset_x + img_left * self.scale

        canvas_y = self.offset_y + img_top * self.scale

        self.canvas.create_image(canvas_x, canvas_y, anchor="nw", image=self.tk_image)

        if self.selected is not None:
            self.draw_marker(*self.selected)

        self.zoom_label.config(text=(f"Zoom: {self.scale * 100:.1f}%"))

    def draw_marker(self, x, y):
        cx = self.offset_x + x * self.scale

        cy = self.offset_y + y * self.scale

        radius = 18

        self.canvas.create_line(cx - radius, cy, cx + radius, cy, fill="#ef4444", width=2)

        self.canvas.create_line(cx, cy - radius, cx, cy + radius, fill="#ef4444", width=2)

        self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, outline="#fde047", width=2)

        self.canvas.create_text(
            cx + 13,
            cy - 15,
            text=(f"X={x:.3f}  Y={y:.3f}"),
            anchor="sw",
            fill="#fde047",
            font=("Segoe UI", 10, "bold"),
        )

    def canvas_resized(self, event):
        if self.image is None:
            return

        if self.first_display:
            self.first_display = False
            self.fit_image()
        else:
            self.render()

    # ==========================================================
    # Shortcuts
    # ==========================================================

    def bind_shortcuts(self):
        self.root.bind("<Left>", lambda event: self.previous_image())

        self.root.bind("<Right>", lambda event: self.next_image())

        self.root.bind("<Control-Return>", lambda event: self.add_and_next())


if __name__ == "__main__":
    root = tk.Tk()
    app = GCPPicker(root)
    root.mainloop()
