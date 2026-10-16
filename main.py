import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk
import os, re, threading
import numpy as np

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


class GCPPicker:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

    def __init__(self, root):
        self.root = root
        self.root.title("GCP Pixel Picker")
        self.root.geometry("1380x900")
        self.root.minsize(1000, 650)
        self.root.configure(bg="#111827")

        self.image = None
        self.tk_image = None
        self.image_path = None

        self.image_files = []
        self.current_index = -1

        self.scale = 1.0
        self.min_scale = 0.05
        self.max_scale = 20.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.selected = None
        self.pan_start = None
        self.loading = False

        # Generated ODM observations
        self.records = []

        self.ground_x = tk.StringVar()
        self.ground_y = tk.StringVar()
        self.ground_z = tk.StringVar()
        self.label_var = tk.StringVar()

        self.build_ui()
        self.bind_shortcuts()

    def build_ui(self):
        # ------------------------------------------------------------
        # TOOLBAR
        # ------------------------------------------------------------
        toolbar = tk.Frame(self.root, bg="#1f2937", height=58)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        self.open_button = self.make_button(toolbar, "Open Image", self.open_image, "#2563eb")
        self.open_button.pack(side="left", padx=(10, 4), pady=9)

        self.prev_button = self.make_button(toolbar, "◀", self.previous_image, "#374151")
        self.prev_button.pack(side="left", padx=3, pady=9)

        self.next_button = self.make_button(toolbar, "▶", self.next_image, "#374151")
        self.next_button.pack(side="left", padx=3, pady=9)

        self.make_button(toolbar, "100%", self.actual_size, "#374151").pack(side="left", padx=(12, 4), pady=9)
        self.make_button(toolbar, "Fit", self.fit_image, "#374151").pack(side="left", padx=4, pady=9)

        self.copy_xy_button = self.make_button(toolbar, "Copy X,Y", self.copy_xy, "#0891b2")
        self.copy_xy_button.pack(side="left", padx=(12, 4), pady=9)

        self.add_button = self.make_button(toolbar, "Add", self.add_record, "#059669")
        self.add_button.pack(side="left", padx=4, pady=9)

        self.add_next_button = self.make_button(toolbar, "Add & Next", self.add_and_next, "#16a34a")
        self.add_next_button.pack(side="left", padx=4, pady=9)

        self.make_button(toolbar, "Undo", self.undo_last, "#b45309").pack(side="left", padx=4, pady=9)
        self.make_button(toolbar, "Export TXT", self.export_txt, "#7c3aed").pack(side="left", padx=4, pady=9)

        self.zoom_label = tk.Label(
            toolbar, text="Zoom: --", bg="#1f2937", fg="#93c5fd",
            font=("Segoe UI", 10, "bold")
        )
        self.zoom_label.pack(side="right", padx=14)

        # ------------------------------------------------------------
        # ODM / GCP DATA
        # ------------------------------------------------------------
        data_panel = tk.Frame(self.root, bg="#111827")
        data_panel.pack(fill="x", padx=12, pady=(8, 4))

        self.add_field(data_panel, "Ground X", self.ground_x, 0)
        self.add_field(data_panel, "Ground Y", self.ground_y, 2)
        self.add_field(data_panel, "Ground Z", self.ground_z, 4)
        self.add_field(data_panel, "Label", self.label_var, 6)

        self.record_count = tk.Label(
            data_panel, text="Records: 0", bg="#111827", fg="#34d399",
            font=("Segoe UI", 10, "bold")
        )
        self.record_count.grid(row=0, column=8, padx=(20, 0), sticky="w")

        # ------------------------------------------------------------
        # IMAGE INFORMATION
        # ------------------------------------------------------------
        info_panel = tk.Frame(self.root, bg="#111827")
        info_panel.pack(fill="x", padx=12, pady=(3, 6))

        first_row = tk.Frame(info_panel, bg="#111827")
        first_row.pack(fill="x")

        self.filename_label = tk.Label(
            first_row, text="No image loaded", bg="#111827", fg="#f9fafb",
            font=("Segoe UI", 11, "bold"), anchor="w"
        )
        self.filename_label.pack(side="left", fill="x", expand=True)

        self.image_counter_label = tk.Label(
            first_row, text="", bg="#111827", fg="#93c5fd",
            font=("Segoe UI", 10, "bold")
        )
        self.image_counter_label.pack(side="right")

        self.pixel_label = tk.Label(
            info_panel, text="Pixel: --", bg="#111827", fg="#fbbf24",
            font=("Segoe UI", 12, "bold"), anchor="w"
        )
        self.pixel_label.pack(fill="x", pady=(3, 0))

        self.description_label = tk.Label(
            info_panel, text="ODM row: --", bg="#111827", fg="#c4b5fd",
            font=("Consolas", 10, "bold"), anchor="w"
        )
        self.description_label.pack(fill="x", pady=(2, 0))

        self.info = tk.Label(
            info_panel,
            text="Open an image and click the center of the GCP.",
            bg="#111827", fg="#9ca3af", font=("Segoe UI", 9), anchor="w"
        )
        self.info.pack(fill="x", pady=(2, 0))

        # ------------------------------------------------------------
        # PROGRESS
        # ------------------------------------------------------------
        self.progress_frame = tk.Frame(info_panel, bg="#111827")

        self.loading_label = tk.Label(
            self.progress_frame, text="Loading image...",
            bg="#111827", fg="#60a5fa", font=("Segoe UI", 9, "bold")
        )
        self.loading_label.pack(side="left", padx=(0, 10))

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Loading.Horizontal.TProgressbar",
            troughcolor="#1f2937",
            background="#3b82f6"
        )

        self.progress = ttk.Progressbar(
            self.progress_frame,
            mode="indeterminate",
            style="Loading.Horizontal.TProgressbar"
        )
        self.progress.pack(side="left", fill="x", expand=True)

        # ------------------------------------------------------------
        # CANVAS
        # ------------------------------------------------------------
        canvas_frame = tk.Frame(self.root, bg="#111827")
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#030712",
            cursor="cross",
            highlightthickness=1,
            highlightbackground="#374151"
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

        bottom = tk.Frame(self.root, bg="#1f2937")
        bottom.pack(fill="x")

        tk.Label(
            bottom,
            text="100% = original image pixels   •   Wheel = zoom   •   Right/Middle drag = pan   •   Left click = select GCP",
            bg="#1f2937", fg="#9ca3af", font=("Segoe UI", 9)
        ).pack(side="left", padx=12, pady=5)

        self.update_navigation_buttons()

    def add_field(self, parent, name, variable, column):
        tk.Label(
            parent, text=name + ":", bg="#111827", fg="#d1d5db",
            font=("Segoe UI", 9, "bold")
        ).grid(row=0, column=column, padx=(0, 4), sticky="w")

        tk.Entry(
            parent, textvariable=variable, width=16,
            bg="#1f2937", fg="#f9fafb",
            insertbackground="white", relief="flat",
            font=("Segoe UI", 10)
        ).grid(row=0, column=column + 1, padx=(0, 12), ipady=4)

    def make_button(self, parent, text, command, color):
        return tk.Button(
            parent, text=text, command=command,
            bg=color, fg="white",
            activebackground=color, activeforeground="white",
            relief="flat", bd=0, padx=12, pady=6,
            font=("Segoe UI", 9, "bold"), cursor="hand2"
        )

    def bind_shortcuts(self):
        self.root.bind("<Left>", lambda e: self.previous_image())
        self.root.bind("<Right>", lambda e: self.next_image())
        self.root.bind("<Control-s>", lambda e: self.export_txt())

    # ============================================================
    # IMAGE DISCOVERY
    # ============================================================

    def natural_sort_key(self, path):
        return [
            int(x) if x.isdigit() else x.lower()
            for x in re.split(r"(\d+)", os.path.basename(path))
        ]

    def discover_folder_images(self, selected):
        selected = os.path.abspath(selected)
        folder = os.path.dirname(selected)

        self.image_files = sorted(
            [
                os.path.abspath(os.path.join(folder, name))
                for name in os.listdir(folder)
                if (
                    os.path.isfile(os.path.join(folder, name))
                    and os.path.splitext(name)[1].lower()
                    in self.IMAGE_EXTENSIONS
                )
            ],
            key=self.natural_sort_key
        )

        try:
            self.current_index = self.image_files.index(selected)
        except ValueError:
            self.image_files = [selected]
            self.current_index = 0

        self.update_counter()
        self.update_navigation_buttons()

    # ============================================================
    # IMAGE LOADING
    # ============================================================

    def open_image(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.tif *.tiff"),
                ("TIFF", "*.tif *.tiff"),
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("All files", "*.*")
            ]
        )

        if not path:
            return

        self.discover_folder_images(path)
        self.load_image(path)

    def load_image(self, path):
        if self.loading:
            return

        self.start_loading(path)

        threading.Thread(
            target=self.load_worker,
            args=(path,),
            daemon=True
        ).start()

    def load_worker(self, path):
        try:
            ext = os.path.splitext(path)[1].lower()

            if ext in {".tif", ".tiff"} and RASTERIO_AVAILABLE:
                image, bands = self.read_tiff(path)
            else:
                image = Image.open(path)
                image.load()

                original_size = image.size

                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGB")

                if image.size != original_size:
                    raise RuntimeError("Image geometry changed while loading.")

                bands = len(image.getbands())

            self.root.after(
                0,
                lambda img=image, p=path, b=bands:
                    self.finish_loading(img, p, b)
            )

        except Exception as e:
            self.root.after(
                0,
                lambda err=str(e): self.loading_failed(err)
            )

    def read_tiff(self, path):
        with rasterio.open(path) as src:
            width, height, count = src.width, src.height, src.count

            if count == 1:
                band = src.read(1)
                display = self.normalize_band(band)
                rgb = np.dstack((display, display, display))

            elif count >= 3:
                descriptions = [
                    (d or "").lower().strip()
                    for d in src.descriptions
                ]

                def find(name):
                    for i, d in enumerate(descriptions):
                        if d == name:
                            return i + 1
                    return None

                red = find("red")
                green = find("green")
                blue = find("blue")

                indexes = (
                    [red, green, blue]
                    if red and green and blue
                    else [1, 2, 3]
                )

                channels = [
                    self.normalize_band(src.read(i))
                    for i in indexes
                ]

                rgb = np.dstack(channels)

            else:
                b1 = self.normalize_band(src.read(1))
                b2 = self.normalize_band(src.read(2))
                rgb = np.dstack((b1, b2, b2))

            # ABSOLUTE geometry safeguard
            if rgb.shape[:2] != (height, width):
                raise RuntimeError(
                    f"Raster geometry changed: source={(width, height)}, "
                    f"preview={(rgb.shape[1], rgb.shape[0])}"
                )

            image = Image.fromarray(rgb.astype(np.uint8), "RGB")

            if image.size != (width, height):
                raise RuntimeError(
                    f"Preview size mismatch: source={(width, height)}, "
                    f"preview={image.size}"
                )

            return image, count

    def normalize_band(self, band):
        original_shape = band.shape

        a = band.astype(np.float32)
        valid = np.isfinite(a)

        if not np.any(valid):
            result = np.zeros(original_shape, dtype=np.uint8)
        else:
            values = a[valid]
            lo, hi = np.percentile(values, (2, 98))

            if hi <= lo:
                lo, hi = float(values.min()), float(values.max())

            if hi <= lo:
                result = np.zeros(original_shape, dtype=np.uint8)
            else:
                a = np.clip((a - lo) / (hi - lo), 0, 1)
                a[~valid] = 0
                result = (a * 255).astype(np.uint8)

        if result.shape != original_shape:
            raise RuntimeError("Band dimensions changed.")

        return result

    def finish_loading(self, image, path, bands):
        self.image = image
        self.image_path = path
        self.selected = None

        self.stop_loading()

        filename = os.path.basename(path)
        iw, ih = self.image.size

        self.root.title(f"GCP Pixel Picker - {filename}")
        self.filename_label.config(text=filename)

        self.info.config(
            text=f"Original raster: {iw} × {ih} pixels • {bands} band{'s' if bands != 1 else ''}",
            fg="#34d399"
        )

        self.pixel_label.config(text="Pixel: --")
        self.description_label.config(text="ODM row: --")

        self.update_counter()

        # IMPORTANT:
        # Do NOT fit automatically.
        # Start at original 1:1 pixel scale.
        self.show_original_image()

    def show_original_image(self):
        if self.image is None:
            return

        self.canvas.update_idletasks()

        self.scale = 1.0
        self.min_scale = 0.05
        self.max_scale = 20.0

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        iw, ih = self.image.size

        # Center only when image is smaller than canvas.
        # Larger images start at top-left.
        self.offset_x = (cw - iw) / 2 if iw < cw else 0
        self.offset_y = (ch - ih) / 2 if ih < ch else 0

        self.render()

    def start_loading(self, path):
        self.loading = True

        self.filename_label.config(
            text=os.path.basename(path)
        )

        self.progress_frame.pack(fill="x", pady=(3, 0))
        self.progress.start(12)

        self.open_button.config(state="disabled")
        self.add_button.config(state="disabled")
        self.add_next_button.config(state="disabled")

        self.update_navigation_buttons()

    def stop_loading(self):
        self.progress.stop()
        self.progress_frame.pack_forget()

        self.loading = False

        self.open_button.config(state="normal")
        self.add_button.config(state="normal")
        self.add_next_button.config(state="normal")

        self.update_navigation_buttons()

    def loading_failed(self, error):
        self.stop_loading()
        self.info.config(
            text=f"Unable to load image: {error}",
            fg="#f87171"
        )

    # ============================================================
    # MULTIPLE RECORD GENERATOR
    # ============================================================

    def get_ground_values(self):
        gx = self.ground_x.get().strip()
        gy = self.ground_y.get().strip()
        gz = self.ground_z.get().strip()
        label = self.label_var.get().strip()

        if not gx or not gy or not gz:
            self.info.config(
                text="Ground X, Y and Z are required.",
                fg="#f87171"
            )
            return None

        try:
            float(gx)
            float(gy)
            float(gz)
        except ValueError:
            self.info.config(
                text="Ground X, Y and Z must be numeric.",
                fg="#f87171"
            )
            return None

        return gx, gy, gz, label

    def build_record(self):
        if self.selected is None:
            self.info.config(
                text="Click the GCP center first.",
                fg="#f87171"
            )
            return None

        if not self.image_path:
            return None

        ground = self.get_ground_values()

        if ground is None:
            return None

        gx, gy, gz, label = ground
        px, py = self.selected
        filename = os.path.basename(self.image_path)

        # ODM:
        # geo_x geo_y geo_z im_x im_y image_name [label]
        row = f"{gx} {gy} {gz} {px} {py} {filename}"

        if label:
            row += f" {label}"

        return row

    def add_record(self):
        row = self.build_record()

        if row is None:
            return False

        # Avoid accidental duplicate line
        if row in self.records:
            self.info.config(
                text="This observation is already in the list.",
                fg="#fbbf24"
            )
            return False

        self.records.append(row)

        self.record_count.config(
            text=f"Records: {len(self.records)}"
        )

        self.info.config(
            text=f"Added observation #{len(self.records)}",
            fg="#34d399"
        )

        return True

    def add_and_next(self):
        if not self.add_record():
            return

        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_image(
                self.image_files[self.current_index]
            )
        else:
            self.info.config(
                text="Observation added. This is the last image.",
                fg="#34d399"
            )

    def undo_last(self):
        if not self.records:
            self.info.config(
                text="No observations to undo.",
                fg="#fbbf24"
            )
            return

        removed = self.records.pop()

        self.record_count.config(
            text=f"Records: {len(self.records)}"
        )

        self.info.config(
            text=f"Removed: {removed}",
            fg="#fbbf24"
        )

    def export_txt(self):
        if not self.records:
            self.info.config(
                text="There are no observations to export.",
                fg="#f87171"
            )
            return

        path = filedialog.asksaveasfilename(
            title="Export GCP List",
            defaultextension=".txt",
            initialfile="gcp_list.txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                for row in self.records:
                    f.write(row + "\n")

            self.info.config(
                text=f"Exported {len(self.records)} observations to {os.path.basename(path)}",
                fg="#34d399"
            )

        except OSError as e:
            messagebox.showerror(
                "Export Error",
                str(e)
            )

    # ============================================================
    # NAVIGATION
    # ============================================================

    def next_image(self):
        if self.loading:
            return

        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_image(
                self.image_files[self.current_index]
            )

    def previous_image(self):
        if self.loading:
            return

        if self.current_index > 0:
            self.current_index -= 1
            self.load_image(
                self.image_files[self.current_index]
            )

    def update_counter(self):
        if self.image_files and self.current_index >= 0:
            self.image_counter_label.config(
                text=f"{self.current_index + 1} / {len(self.image_files)}"
            )
        else:
            self.image_counter_label.config(text="")

    def update_navigation_buttons(self):
        previous_ok = (
            not self.loading
            and self.image_files
            and self.current_index > 0
        )

        next_ok = (
            not self.loading
            and self.image_files
            and self.current_index < len(self.image_files) - 1
        )

        self.prev_button.config(
            state="normal" if previous_ok else "disabled"
        )

        self.next_button.config(
            state="normal" if next_ok else "disabled"
        )

    # ============================================================
    # COORDINATES
    # ============================================================

    def select_point(self, event):
        if self.image is None:
            return

        x = (event.x - self.offset_x) / self.scale
        y = (event.y - self.offset_y) / self.scale

        iw, ih = self.image.size

        if not (0 <= x < iw and 0 <= y < ih):
            return

        x = min(max(int(round(x)), 0), iw - 1)
        y = min(max(int(round(y)), 0), ih - 1)

        self.selected = (x, y)

        self.pixel_label.config(
            text=f"Pixel:   X = {x}     Y = {y}"
        )

        row = self.build_record_preview()

        self.description_label.config(
            text=f"ODM row: {row}"
            if row else
            f"Pixel observation: {x} {y} {os.path.basename(self.image_path)}"
        )

        self.render()

    def build_record_preview(self):
        if self.selected is None or not self.image_path:
            return None

        gx = self.ground_x.get().strip()
        gy = self.ground_y.get().strip()
        gz = self.ground_z.get().strip()
        label = self.label_var.get().strip()

        if not gx or not gy or not gz:
            return None

        px, py = self.selected
        filename = os.path.basename(self.image_path)

        row = f"{gx} {gy} {gz} {px} {py} {filename}"

        if label:
            row += f" {label}"

        return row

    def copy_xy(self):
        if self.selected is None:
            self.info.config(
                text="Select a GCP first.",
                fg="#f87171"
            )
            return

        x, y = self.selected

        self.root.clipboard_clear()
        self.root.clipboard_append(
            f"{x}, {y}"
        )

        self.info.config(
            text=f"Copied X={x}, Y={y}",
            fg="#34d399"
        )

    # ============================================================
    # ORIGINAL IMAGE DISPLAY
    # ============================================================

    def actual_size(self):
        if self.image is None:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        center_x = (
            cw / 2 - self.offset_x
        ) / self.scale

        center_y = (
            ch / 2 - self.offset_y
        ) / self.scale

        self.scale = 1.0

        self.offset_x = (
            cw / 2 - center_x
        )

        self.offset_y = (
            ch / 2 - center_y
        )

        self.render()

    def fit_image(self):
        if self.image is None:
            return

        self.canvas.update_idletasks()

        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        iw, ih = self.image.size

        margin = 20

        self.scale = min(
            max(cw - margin * 2, 1) / iw,
            max(ch - margin * 2, 1) / ih
        )

        self.min_scale = min(
            self.scale * 0.25,
            0.05
        )

        self.max_scale = 20.0

        self.offset_x = (
            cw - iw * self.scale
        ) / 2

        self.offset_y = (
            ch - ih * self.scale
        ) / 2

        self.render()

    def mouse_zoom(self, event):
        if self.image is None:
            return

        self.zoom_at(
            event.x,
            event.y,
            1.20 if event.delta > 0 else 1 / 1.20
        )

    def mouse_zoom_linux(self, event):
        if self.image is None:
            return

        self.zoom_at(
            event.x,
            event.y,
            1.20 if event.num == 4 else 1 / 1.20
        )

    def zoom_at(self, mouse_x, mouse_y, factor):
        old_scale = self.scale

        new_scale = max(
            self.min_scale,
            min(
                old_scale * factor,
                self.max_scale
            )
        )

        if new_scale == old_scale:
            return

        image_x = (
            mouse_x - self.offset_x
        ) / old_scale

        image_y = (
            mouse_y - self.offset_y
        ) / old_scale

        self.scale = new_scale

        self.offset_x = (
            mouse_x - image_x * new_scale
        )

        self.offset_y = (
            mouse_y - image_y * new_scale
        )

        self.render()

    def start_pan(self, event):
        if self.image is None:
            return

        self.pan_start = (
            event.x,
            event.y,
            self.offset_x,
            self.offset_y
        )

        self.canvas.config(cursor="fleur")

    def pan(self, event):
        if self.image is None or self.pan_start is None:
            return

        sx, sy, ox, oy = self.pan_start

        self.offset_x = (
            ox + event.x - sx
        )

        self.offset_y = (
            oy + event.y - sy
        )

        self.render()

    def end_pan(self, event=None):
        self.pan_start = None
        self.canvas.config(cursor="cross")

    def render(self):
        if self.image is None:
            return

        # AUTHORITATIVE SOURCE DIMENSIONS
        iw, ih = self.image.size

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        img_left = max(
            0,
            int(-self.offset_x / self.scale)
        )

        img_top = max(
            0,
            int(-self.offset_y / self.scale)
        )

        img_right = min(
            iw,
            int(
                (cw - self.offset_x)
                / self.scale
            ) + 2
        )

        img_bottom = min(
            ih,
            int(
                (ch - self.offset_y)
                / self.scale
            ) + 2
        )

        self.canvas.delete("all")

        if (
            img_right <= img_left
            or img_bottom <= img_top
        ):
            return

        # Temporary VIEW ONLY.
        # self.image is never modified.
        crop = self.image.crop(
            (
                img_left,
                img_top,
                img_right,
                img_bottom
            )
        )

        crop_w = max(
            int(
                (img_right - img_left)
                * self.scale
            ),
            1
        )

        crop_h = max(
            int(
                (img_bottom - img_top)
                * self.scale
            ),
            1
        )

        resample = (
            Image.Resampling.NEAREST
            if self.scale >= 1
            else Image.Resampling.LANCZOS
        )

        display_crop = crop.resize(
            (crop_w, crop_h),
            resample
        )

        self.tk_image = ImageTk.PhotoImage(
            display_crop
        )

        canvas_x = (
            self.offset_x
            + img_left * self.scale
        )

        canvas_y = (
            self.offset_y
            + img_top * self.scale
        )

        self.canvas.create_image(
            canvas_x,
            canvas_y,
            anchor="nw",
            image=self.tk_image
        )

        if self.selected:
            self.draw_marker(
                *self.selected
            )

        self.zoom_label.config(
            text=f"Zoom: {self.scale * 100:.1f}%"
        )

    def draw_marker(self, x, y):
        cx = self.offset_x + x * self.scale
        cy = self.offset_y + y * self.scale
        r = 18

        self.canvas.create_line(
            cx - r, cy,
            cx + r, cy,
            width=2,
            fill="#ef4444"
        )

        self.canvas.create_line(
            cx, cy - r,
            cx, cy + r,
            width=2,
            fill="#ef4444"
        )

        self.canvas.create_oval(
            cx - 5,
            cy - 5,
            cx + 5,
            cy + 5,
            outline="#facc15",
            width=2
        )

        self.canvas.create_text(
            cx + 13,
            cy - 15,
            text=f"X={x}  Y={y}",
            anchor="sw",
            fill="#fde047",
            font=("Segoe UI", 10, "bold")
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = GCPPicker(root)
    root.mainloop()