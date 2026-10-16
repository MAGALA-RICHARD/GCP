import sys
import threading
import tkinter as tk
from contextlib import suppress
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from helpers import (
    add_record,
    create_record,
    export_records,
    format_record,
    load_image_data,
    remove_record,
    sorted_all_records,
    sorted_group,
    total_records,
)


def resource_path(filename):
    """Return an asset path that works in development and PyInstaller builds."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / filename


class RoundedInfoCard(tk.Canvas):
    def __init__(
        self,
        parent,
        title,
        value="--",
        fill="#0f172a",
        outline="#334155",
        title_color="#94a3b8",
        value_color="#f8fafc",
        height=68,
        radius=16,
    ):
        super().__init__(
            parent,
            height=height,
            bg=parent.cget("bg"),
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self._title = title
        self._value = value
        self._fill = fill
        self._outline = outline
        self._title_color = title_color
        self._value_color = value_color
        self._radius = radius
        self.bind("<Configure>", lambda _e: self._draw())

    def set_value(self, value):
        self._value = value
        self._draw()

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 2)
        h = max(self.winfo_height(), 2)
        r = min(self._radius, w // 2, h // 2)
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        points = [
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1,
        ]
        self.create_polygon(
            points,
            smooth=True,
            splinesteps=36,
            fill=self._fill,
            outline=self._outline,
            width=1,
        )
        self.create_text(
            14,
            16,
            text=self._title,
            anchor="w",
            fill=self._title_color,
            font=("Segoe UI", 8, "bold"),
        )
        self.create_text(
            14,
            42,
            text=self._value,
            anchor="w",
            fill=self._value_color,
            font=("Segoe UI", 10, "bold"),
        )


class GCPPicker:
    BG = "#111827"
    PANEL = "#1f2937"
    CANVAS_BG = "#030712"

    TEXT = "#f9fafb"
    MUTED = "#9ca3af"

    BLUE = "#2563eb"
    GREEN = "#059669"
    PURPLE = "#7c3aed"
    RED = "#dc2626"
    YELLOW = "#fbbf24"

    def __init__(self, root):
        self.root = root
        self.root.title("GCP Pixel Picker")
        self.root.geometry("1450x900")
        self.root.minsize(1050, 680)
        self.root.configure(bg=self.BG)
        self.set_app_icon()

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

        self.records = {}
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

    def set_app_icon(self):
        """Set the window/taskbar icon without failing if an asset is missing."""
        png_path = resource_path("app_icon.png")
        ico_path = resource_path("app_icon.ico")

        try:
            # iconphoto is portable and keeps the PhotoImage alive on the instance.
            if png_path.exists():
                self.app_icon = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, self.app_icon)

            # On Windows, .ico also improves title-bar/taskbar presentation.
            if sys.platform.startswith("win") and ico_path.exists():
                self.root.iconbitmap(default=str(ico_path))
        except tk.TclError:
            # The application should still start if an OS/window manager rejects an icon.
            pass

    # =========================================================
    # UI helpers
    # =========================================================

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

    def make_zoom_button(self, parent, text, command, tooltip):
        button = self.make_button(parent, text, command)
        button.config(font=("Segoe UI", 13, "bold"), padx=10, pady=3)
        button.bind("<Enter>", lambda e, t=tooltip: self.show_tooltip(e.widget, t))
        button.bind("<Leave>", lambda e: self.hide_tooltip())
        return button

    def show_tooltip(self, widget, text):
        self.hide_tooltip()
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tooltip,
            text=text,
            bg="#0f172a",
            fg=self.TEXT,
            relief="solid",
            bd=1,
            padx=8,
            pady=4,
            font=("Segoe UI", 9),
        ).pack()

    def hide_tooltip(self):
        tooltip = getattr(self, "tooltip", None)
        if tooltip is not None:
            tooltip.destroy()
            self.tooltip = None

    def make_entry(self, parent, variable, width=18):
        return tk.Entry(
            parent,
            textvariable=variable,
            width=width,
            bg="#0f172a",
            fg=self.TEXT,
            insertbackground="white",
            selectbackground=self.BLUE,
            selectforeground="white",
            relief="solid",
            bd=1,
            highlightthickness=2,
            highlightbackground="#475569",
            highlightcolor="#3b82f6",
            font=("Segoe UI", 10),
        )

    def form_row(self, parent, title, variable):
        row = tk.Frame(parent, bg=self.PANEL)
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

    # =========================================================
    # UI
    # =========================================================

    def build_ui(self):
        toolbar = tk.Frame(self.root, bg=self.PANEL, height=56)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        self.open_button = self.make_button(toolbar, "Open Folder", self.open_image, self.BLUE)
        self.prev_button = self.make_button(toolbar, "◀ Previous", self.previous_image)
        self.next_button = self.make_button(toolbar, "Next ▶", self.next_image)
        self.add_button = self.make_button(toolbar, "+ Add", self.add_observation, self.GREEN)
        self.add_next_button = self.make_button(toolbar, "+ Add & Next", self.add_and_next, "#047857")
        self.export_button = self.make_button(toolbar, "Export TXT", self.export_txt, self.PURPLE)

        self.open_button.pack(side="left", padx=(10, 4), pady=9)
        self.prev_button.pack(side="left", padx=4, pady=9)
        self.next_button.pack(side="left", padx=4, pady=9)
        self.add_button.pack(side="left", padx=(14, 4), pady=9)
        self.add_next_button.pack(side="left", padx=4, pady=9)
        self.export_button.pack(side="left", padx=(14, 4), pady=9)

        self.make_button(toolbar, "Fit", self.fit_image).pack(side="left", padx=(14, 4), pady=9)
        self.make_button(toolbar, "100%", self.actual_size).pack(side="left", padx=4, pady=9)
        self.zoom_out_button = self.make_zoom_button(toolbar, "−", self.zoom_out, "Zoom out")
        self.zoom_out_button.pack(side="left", padx=(10, 2), pady=9)
        self.zoom_in_button = self.make_zoom_button(toolbar, "+", self.zoom_in, "Zoom in")
        self.zoom_in_button.pack(side="left", padx=2, pady=9)

        self.zoom_label = tk.Label(
            toolbar,
            text="Zoom: --",
            bg=self.PANEL,
            fg="#93c5fd",
            font=("Segoe UI", 10, "bold"),
        )
        self.zoom_label.pack(side="right", padx=15)

        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # Draggable divider between the image and information panels.
        # Resizing these panels NEVER changes self.scale.
        self.main_panes = tk.PanedWindow(
            body,
            orient="horizontal",
            bg="#374151",
            sashwidth=6,
            sashrelief="flat",
            bd=0,
        )
        self.main_panes.pack(fill="both", expand=True)

        left = tk.Frame(self.main_panes, bg=self.BG)
        right = tk.Frame(self.main_panes, bg=self.PANEL, width=380)

        self.main_panes.add(left, stretch="always", minsize=400)
        self.main_panes.add(right, stretch="never", minsize=280)

        self.build_image_panel(left)
        self.build_control_panel(right)

        # Start with a sensible right-panel width. The user can drag the sash.
        self.root.after_idle(lambda: self.main_panes.sash_place(0, max(self.root.winfo_width() - 410, 400), 0))

        self.update_navigation_buttons()

    def build_image_panel(self, parent):
        header = tk.Frame(parent, bg=self.BG)
        header.pack(fill="x", pady=(0, 10))

        info_card = tk.Frame(
            header,
            bg="#0f172a",
            highlightbackground="#1e293b",
            highlightthickness=1,
            bd=0,
            padx=14,
            pady=12,
        )
        info_card.pack(fill="x")

        top_row = tk.Frame(info_card, bg="#0f172a")
        top_row.pack(fill="x")

        self.filename_label = tk.Label(
            top_row,
            text="No image loaded",
            bg="#0f172a",
            fg=self.TEXT,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            justify="left",
        )
        self.filename_label.pack(side="left", fill="x", expand=True)

        counter_wrap = tk.Frame(top_row, bg="#1d4ed8", bd=0)
        counter_wrap.pack(side="right", padx=(10, 0))
        self.counter_label = tk.Label(
            counter_wrap,
            text="",
            bg="#1d4ed8",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
        )
        self.counter_label.pack()

        self.info_label = tk.Label(
            info_card,
            text="Open an image and click the center of the GCP.",
            bg="#0f172a",
            fg=self.MUTED,
            anchor="w",
            justify="left",
            font=("Segoe UI", 9),
            pady=6,
        )
        self.info_label.pack(fill="x")

        meta_row = tk.Frame(info_card, bg="#0f172a")
        meta_row.pack(fill="x", pady=(4, 0))
        meta_row.columnconfigure(0, weight=1, uniform="meta")
        meta_row.columnconfigure(1, weight=1, uniform="meta")

        self.raster_card = RoundedInfoCard(
            meta_row,
            "RASTER SIZE",
            fill="black",
            outline="#e5e7eb",
            title_color="#99f6e4",
            value_color="#ecfeff",
            height=68,
            radius=18,
        )
        self.raster_card.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.band_card = RoundedInfoCard(
            meta_row,
            "BANDS",
            fill="black",
            outline="#e5e7eb",
            title_color="#bfdbfe",
            value_color="#eff6ff",
            height=68,
            radius=18,
        )
        self.band_card.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.pixel_card = RoundedInfoCard(
            info_card,
            "SELECTED PIXEL",
            fill="black",
            outline="black",
            title_color="#fcd34d",
            value_color="#fff7ed",
            height=76,
            radius=18,
        )
        self.pixel_card.pack(fill="x", pady=(10, 0))

        self.canvas = tk.Canvas(
            parent,
            bg=self.CANVAS_BG,
            cursor="cross",
            highlightthickness=1,
            highlightbackground="#374151",
            highlightcolor="#3b82f6",
        )
        self.canvas.pack(fill="both", expand=True)

        bindings = {
            "<Button-1>": self.select_point,
            "<Button-3>": self.show_image_context_menu,
            "<MouseWheel>": self.mouse_zoom,
            "<Button-4>": self.mouse_zoom_linux,
            "<Button-5>": self.mouse_zoom_linux,
            "<ButtonPress-2>": self.start_pan,
            "<B2-Motion>": self.pan,
            "<ButtonRelease-2>": self.end_pan,
            "<Configure>": self.canvas_resized,
        }
        for event, handler in bindings.items():
            self.canvas.bind(event, handler)

        self.build_image_context_menu()

    def build_image_context_menu(self):
        self.image_context_menu = tk.Menu(
            self.root,
            tearoff=False,
            bg="#111827",
            fg="#f8fafc",
            activebackground="#2563eb",
            activeforeground="white",
            disabledforeground="#64748b",
            relief="flat",
            bd=1,
            font=("Segoe UI", 9),
        )
        menu = self.image_context_menu
        menu.add_command(
            label="Add observation",
            accelerator="Ctrl+Shift+A",
            command=self.add_observation,
        )
        menu.add_command(label="Add & Next", accelerator="Ctrl+Shift+N", command=self.add_and_next)
        menu.add_separator()
        menu.add_command(label="Image metadata", accelerator="I", command=self.show_image_metadata)
        menu.add_command(label="Fit image", accelerator="F", command=self.fit_image)
        menu.add_command(label="Actual size (100%)", accelerator="0", command=self.actual_size)
        menu.add_command(label="Zoom in", accelerator="+", command=self.zoom_in)
        menu.add_command(label="Zoom out", accelerator="-", command=self.zoom_out)
        menu.add_separator()
        menu.add_command(label="Previous image", accelerator="Ctrl+P", command=self.previous_image)
        menu.add_command(label="Next image", accelerator="Ctrl+N", command=self.next_image)
        menu.add_separator()
        menu.add_command(label="Export TXT", accelerator="Ctrl+E", command=self.export_txt)

    def show_image_context_menu(self, event):
        if self.image is None:
            return
        self.image_context_menu.entryconfig(0, state="normal" if self.selected else "disabled")
        self.image_context_menu.entryconfig(1, state="normal" if self.selected else "disabled")
        self.image_context_menu.entryconfig(9, state="normal" if self.current_index > 0 else "disabled")
        self.image_context_menu.entryconfig(
            10,
            state="normal" if self.current_index < len(self.image_files) - 1 else "disabled",
        )
        self.image_context_menu.entryconfig(12, state="normal" if self.records else "disabled")
        try:
            self.image_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.image_context_menu.grab_release()

    def show_image_metadata(self):
        if self.image is None or self.image_path is None:
            return
        try:
            file_size = self.image_path.stat().st_size
            size_text = f"{file_size / (1024 * 1024):.2f} MB"
        except OSError:
            size_text = "Unavailable"

        selected = f"X = {self.selected[0]:.3f}, Y = {self.selected[1]:.3f}" if self.selected else "None"
        bands = ", ".join(self.band_names) if self.band_names else str(self.band_count)
        details = (
            f"File: {self.image_path.name}\n"
            f"Path: {self.image_path}\n\n"
            f"Raster size: {self.source_width} × {self.source_height} px\n"
            f"Bands: {bands}\n"
            f"File type: {self.image_path.suffix.lower() or 'Unknown'}\n"
            f"File size: {size_text}\n"
            f"Zoom: {self.scale * 100:.1f}%\n"
            f"Selected pixel: {selected}\n"
            f"Image position: {self.current_index + 1} of {len(self.image_files)}"
        )
        messagebox.showinfo("Image Metadata", details, parent=self.root)

    def _shortcut_allowed(self, event):
        return not isinstance(event.widget, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox))

    def _run_shortcut(self, event, command):
        if self._shortcut_allowed(event):
            command()
            return "break"
        return None

    def build_control_panel(self, parent):
        tk.Label(
            parent,
            text="GCP INFORMATION",
            bg=self.PANEL,
            fg="#93c5fd",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=14, pady=(14, 10))

        form = tk.Frame(parent, bg=self.PANEL)
        form.pack(fill="x", padx=14)

        for title, variable in (
            ("X / Longitude", self.x_var),
            ("Y / Latitude", self.y_var),
            ("Z / Elevation", self.z_var),
            ("Label", self.label_var),
            ("CRS", self.crs_var),
        ):
            self.form_row(form, title, variable)

        tk.Label(
            parent,
            text="XYZ and label stay unchanged while moving\nbetween overlapping images.",
            justify="left",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=14, pady=(8, 12))

        tk.Label(
            parent,
            text="CURRENT RECORD",
            bg=self.PANEL,
            fg="#c4b5fd",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=14)

        self.description = tk.Text(
            parent,
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

        stats = tk.Frame(parent, bg=self.PANEL)
        stats.pack(fill="x", padx=14)
        tk.Label(
            stats,
            text="Records",
            bg=self.PANEL,
            fg="#86efac",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        self.obs_count_label = tk.Label(
            stats,
            text="0",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10, "bold"),
        )
        self.obs_count_label.pack(side="right")

        self.group_label = tk.Label(
            parent,
            text="Groups: --",
            bg=self.PANEL,
            fg="#94a3b8",
            anchor="w",
            font=("Segoe UI", 9),
        )
        self.group_label.pack(fill="x", padx=14, pady=(3, 5))

        table_frame = tk.Frame(parent, bg=self.PANEL)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        self.tree = ttk.Treeview(
            table_frame,
            columns=("suffix", "label", "image", "pixel"),
            show="headings",
            height=12,
        )

        headings = {
            "suffix": ("Type", 50),
            "label": ("GCP", 60),
            "image": ("Image", 150),
            "pixel": ("Pixel", 100),
        }

        for column, (title, width) in headings.items():
            self.tree.heading(column, text=title)
            self.tree.column(
                column,
                width=width,
                anchor="center" if column == "suffix" else "w",
            )

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        actions = tk.Frame(parent, bg=self.PANEL)
        actions.pack(fill="x", padx=14, pady=(0, 14))
        self.make_button(actions, "Delete Selected", self.delete_selected, self.RED).pack(side="left")
        self.make_button(actions, "Clear All", self.clear_all).pack(side="right")

    # =========================================================
    # Image loading
    # =========================================================

    def open_image(self):
        """Open a directory and load the first supported image in it."""
        if self.loading:
            return

        folder = filedialog.askdirectory(title="Open Image Folder")
        if not folder:
            return

        folder = Path(folder).resolve()
        supported = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

        try:
            self.image_files = sorted(
                (p.resolve() for p in folder.iterdir() if p.is_file() and p.suffix.lower() in supported),
                key=lambda p: p.name.lower(),
            )
        except OSError as error:
            messagebox.showerror("Folder error", str(error))
            return

        if not self.image_files:
            messagebox.showwarning(
                "No supported images",
                "The selected folder does not contain JPG, JPEG, PNG, TIF, or TIFF images.",
            )
            return

        self.current_index = 0
        self.update_counter()
        self.update_navigation_buttons()
        self.load_image(self.image_files[0])

    def load_image(self, path):
        if self.loading:
            return

        self.loading = True
        self.info_label.config(text="Loading image...", fg="#60a5fa")
        self.update_navigation_buttons()
        threading.Thread(
            target=self.load_image_worker,
            args=(Path(path),),
            daemon=True,
        ).start()

    def load_image_worker(self, path):
        try:
            data = load_image_data(path)
            self.root.after(0, lambda: self.finish_loading(path, data))
        except Exception as error:
            message = str(error)
            self.root.after(0, lambda: self.loading_failed(message))

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

        with suppress(ValueError):
            self.current_index = self.image_files.index(self.image_path.resolve())

        filename = self.image_path.name

        self.root.title(f"GCP Pixel Picker - {filename}")
        self.filename_label.config(text=filename)

        self.info_label.config(
            text="Image loaded successfully. Click the center of the GCP to capture the pixel location.",
            fg="#cbd5e1",
        )

        self.raster_card.set_value(f"{self.source_width} × {self.source_height} px")
        self.band_card.set_value(", ".join(self.band_names) if self.band_names else str(self.band_count))

        self.pixel_card.set_value("--")

        self.update_description()
        self.update_counter()
        self.update_navigation_buttons()

        self.root.update_idletasks()
        self.show_original_size()

    def loading_failed(self, error):
        self.loading = False
        self.info_label.config(
            text=f"Could not open image: {error}",
            fg="#fca5a5",
        )
        self.raster_card.set_value("--")
        self.band_card.set_value("--")
        self.pixel_card.set_value("--")
        self.update_navigation_buttons()

    # =========================================================
    # Navigation
    # =========================================================

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
        text = (
            f"{self.current_index + 1} / {len(self.image_files)}"
            if self.image_files and self.current_index >= 0
            else ""
        )
        self.counter_label.config(text=text)

    def update_navigation_buttons(self):
        previous = bool(self.image_files) and self.current_index > 0 and not self.loading

        following = bool(self.image_files) and 0 <= self.current_index < len(self.image_files) - 1 and not self.loading

        self.prev_button.config(state="normal" if previous else "disabled")
        self.next_button.config(state="normal" if following else "disabled")

    # =========================================================
    # Records
    # =========================================================

    def current_record(self):
        return create_record(
            self.selected,
            self.image_path,
            self.x_var.get(),
            self.y_var.get(),
            self.z_var.get(),
            self.label_var.get(),
        )

    def update_description(self):
        record = self.current_record()
        self.description.config(state="normal")
        self.description.delete("1.0", "end")
        if record:
            self.description.insert("1.0", format_record(record))
        elif self.selected is not None:
            xyz = tuple(var.get().strip() for var in (self.x_var, self.y_var, self.z_var))
            if any(xyz):
                self.description.insert("1.0", "Provide X, Y and Z together.")
        self.description.config(state="disabled")

    def add_observation(self):
        if self.selected is None:
            messagebox.showwarning(
                "No GCP selected",
                "Click the center of the GCP first.",
            )
            return False
        xyz = tuple(var.get().strip() for var in (self.x_var, self.y_var, self.z_var))
        if any(xyz) and not all(xyz):
            messagebox.showwarning(
                "Incomplete coordinates",
                "Provide X, Y and Z together, or leave all three blank.",
            )
            return False
        record = self.current_record()
        if record is None:
            return False
        suffix, added = add_record(self.records, record)
        filename = record[5]
        self.refresh_record_table()
        px, py = self.selected
        action = "Added" if added else "Updated"
        self.info_label.config(
            text=f"{action} {suffix}: {filename} @ ({px:.3f}, {py:.3f})",
            fg="#34d399",
        )
        return True

    def add_and_next(self):
        if not self.add_observation():
            return
        if self.current_index < len(self.image_files) - 1:
            self.next_image()
        else:
            self.info_label.config(
                text="Observation added. This is the last image.",
                fg=self.YELLOW,
            )

    def refresh_record_table(self):
        self.tree.delete(*self.tree.get_children())
        self.tree_records.clear()
        for suffix in sorted(self.records):
            for record in sorted_group(self.records, suffix):
                _, _, _, px, py, filename, label = record
                item = self.tree.insert(
                    "",
                    "end",
                    values=(
                        suffix,
                        label or "—",
                        filename,
                        f"{px:.3f}, {py:.3f}",
                    ),
                )
                self.tree_records[item] = (suffix, record)
        self.obs_count_label.config(text=str(total_records(self.records)))
        groups = "   ".join(f"{suffix}: {len(records)}" for suffix, records in sorted(self.records.items()))
        self.group_label.config(text=f"Groups: {groups}" if groups else "Groups: --")

    def delete_selected(self):
        for item in self.tree.selection():
            data = self.tree_records.get(item)

            if data:
                suffix, record = data
                remove_record(self.records, suffix, record)
        self.refresh_record_table()

    def clear_all(self):
        if not self.records:
            return
        if not messagebox.askyesno(
            "Clear all observations",
            "Delete every saved observation?",
        ):
            return
        self.records.clear()
        self.refresh_record_table()

    # =========================================================
    # Export
    # =========================================================

    def export_txt(self):
        if not self.records:
            messagebox.showwarning(
                "Nothing to export",
                "Add at least one observation first.",
            )
            return

        self.show_export_dialog(sorted(self.records))

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
            text="Records are grouped strictly by file extension.",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(padx=25, pady=(0, 15))

        self.make_button(
            dialog,
            f"Export ALL ({total_records(self.records)})",
            lambda: self.export_group(dialog),
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

        self.make_button(
            dialog,
            "Cancel",
            dialog.destroy,
        ).pack(fill="x", padx=25, pady=(10, 20))

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2

        dialog.geometry(f"+{x}+{y}")

    def export_group(self, dialog, suffix=None):
        dialog.destroy()

        if suffix is None:
            records = sorted_all_records(self.records)
            default_name = "gcp_all.txt"
            description = "all groups"
        else:
            records = sorted_group(self.records, suffix)
            default_name = f"gcp_{suffix.lstrip('.') or 'records'}.txt"
            description = suffix

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[
                ("Text file", "*.txt"),
                ("All files", "*.*"),
            ],
        )

        if not path:
            return

        try:
            export_records(path, records, self.crs_var.get().strip())
        except OSError as error:
            messagebox.showerror("Export failed", str(error))
            return
        messagebox.showinfo(
            "Export complete",
            f"Exported {len(records)} record(s) from {description}.\n\n{path}",
        )

    # =========================================================
    # Pixel selection
    # =========================================================

    def select_point(self, event):
        if self.image is None:
            return
        x = (event.x - self.offset_x) / self.scale
        y = (event.y - self.offset_y) / self.scale
        if not (0 <= x < self.source_width and 0 <= y < self.source_height):
            return
        x = min(max(float(x), 0.0), self.source_width - 1.0)
        y = min(max(float(y), 0.0), self.source_height - 1.0)
        self.selected = (x, y)
        self.pixel_card.set_value(f"X = {x:.3f}    Y = {y:.3f}")

        self.info_label.config(
            text="GCP center selected. Review the coordinates on the right, then click Add to save.",
            fg="#86efac",
        )

        self.update_description()
        self.render()

    # =========================================================
    # Zoom / pan
    # =========================================================

    def fit_image(self):
        if self.image is None:
            return
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        iw = self.source_width
        ih = self.source_height
        margin = 20
        self.scale = min(
            max(cw - margin * 2, 1) / iw,
            max(ch - margin * 2, 1) / ih,
        )
        self.min_scale = self.scale * 0.25
        self.max_scale = max(20.0, self.scale * 100)
        self.offset_x = (cw - iw * self.scale) / 2
        self.offset_y = (ch - ih * self.scale) / 2
        self.render()

    def show_original_size(self):
        """Show the source image at exactly 1 image pixel = 1 screen pixel."""
        if self.image is None:
            return
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        self.scale = 1.0
        self.min_scale = 0.01
        self.max_scale = 20.0
        self.offset_x = (cw - self.source_width) / 2
        self.offset_y = (ch - self.source_height) / 2
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

    def zoom_in(self):
        self.zoom_center(1.20)

    def zoom_out(self):
        self.zoom_center(1 / 1.20)

    def zoom_center(self, factor):
        if self.image is None:
            return
        self.zoom_at(
            self.canvas.winfo_width() / 2,
            self.canvas.winfo_height() / 2,
            factor,
        )

    def mouse_zoom(self, event):
        if self.image is not None:
            self.zoom_at(
                event.x,
                event.y,
                1.20 if event.delta > 0 else 1 / 1.20,
            )

    def mouse_zoom_linux(self, event):
        if self.image is not None:
            self.zoom_at(
                event.x,
                event.y,
                1.20 if event.num == 4 else 1 / 1.20,
            )

    def zoom_at(self, mouse_x, mouse_y, factor):
        if self.image is None:
            return
        old_scale = self.scale
        new_scale = max(
            self.min_scale,
            min(old_scale * factor, self.max_scale),
        )
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
        self.pan_start = (
            event.x,
            event.y,
            self.offset_x,
            self.offset_y,
        )
        self.canvas.config(cursor="fleur")

    def pan(self, event):
        if self.pan_start is None:
            return
        start_x, start_y, offset_x, offset_y = self.pan_start
        self.offset_x = offset_x + event.x - start_x
        self.offset_y = offset_y + event.y - start_y

        self.render()

    def end_pan(self, event=None):
        self.pan_start = None
        self.canvas.config(cursor="cross")

    # =========================================================
    # Rendering
    # =========================================================

    def render(self):
        if self.image is None:
            return
        iw, ih = self.source_width, self.source_height
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        left = max(0, int(-self.offset_x / self.scale))
        top = max(0, int(-self.offset_y / self.scale))
        right = min(
            iw,
            int((cw - self.offset_x) / self.scale) + 2,
        )
        bottom = min(
            ih,
            int((ch - self.offset_y) / self.scale) + 2,
        )
        self.canvas.delete("all")
        if right <= left or bottom <= top:
            return
        # Display-only crop; source raster dimensions remain unchanged.
        crop = self.image.crop((left, top, right, bottom))
        display_width = max(int((right - left) * self.scale), 1)
        display_height = max(int((bottom - top) * self.scale), 1)
        resample = Image.Resampling.NEAREST if self.scale >= 4 else Image.Resampling.LANCZOS

        crop = crop.resize(
            (display_width, display_height),
            resample,
        )

        self.tk_image = ImageTk.PhotoImage(crop)
        canvas_x = self.offset_x + left * self.scale
        canvas_y = self.offset_y + top * self.scale
        self.canvas.create_image(
            canvas_x,
            canvas_y,
            anchor="nw",
            image=self.tk_image,
        )
        if self.selected is not None:
            self.draw_marker(*self.selected)
        self.zoom_label.config(text=f"Zoom: {self.scale * 100:.1f}%")

    def draw_marker(self, x, y):
        cx = self.offset_x + x * self.scale
        cy = self.offset_y + y * self.scale
        radius = 18

        self.canvas.create_line(
            cx - radius,
            cy,
            cx + radius,
            cy,
            fill="#ef4444",
            width=2,
        )

        self.canvas.create_line(
            cx,
            cy - radius,
            cx,
            cy + radius,
            fill="#ef4444",
            width=2,
        )

        self.canvas.create_oval(
            cx - 5,
            cy - 5,
            cx + 5,
            cy + 5,
            outline="#fde047",
            width=2,
        )

        self.canvas.create_text(
            cx + 13,
            cy - 15,
            text=f"X={x:.3f}  Y={y:.3f}",
            anchor="sw",
            fill="#fde047",
            font=("Segoe UI", 10, "bold"),
        )

    def canvas_resized(self, event):
        if self.image is None:
            return
        # Panel/window resizing changes only the visible canvas area.
        # It never changes the image scale.
        self.render()

    # =========================================================
    # Shortcuts
    # =========================================================

    def bind_shortcuts(self):
        # Primary application shortcuts. These intentionally work even while
        # an entry field has focus because they use Ctrl-based combinations.
        commands = {
            "<Control-o>": self.open_image,
            "<Control-e>": self.export_txt,
            "<Control-n>": self.next_image,
            "<Control-p>": self.previous_image,
            "<Control-Shift-A>": self.add_observation,
            "<Control-Shift-a>": self.add_observation,
            "<Control-Shift-N>": self.add_and_next,
            "<Control-Shift-n>": self.add_and_next,
        }
        for sequence, command in commands.items():
            self.root.bind(sequence, lambda _event, cmd=command: (cmd(), "break")[1])

        # Viewer-only shortcuts are ignored while typing in an input field.
        viewer_bindings = {
            "<Key-f>": self.fit_image,
            "<Key-F>": self.fit_image,
            "<Key-i>": self.show_image_metadata,
            "<Key-I>": self.show_image_metadata,
            "<Key-0>": self.actual_size,
            "<Key-plus>": self.zoom_in,
            "<Key-equal>": self.zoom_in,
            "<Key-minus>": self.zoom_out,
        }
        for sequence, command in viewer_bindings.items():
            self.root.bind(sequence, lambda event, cmd=command: self._run_shortcut(event, cmd))


def main():
    root = tk.Tk()
    GCPPicker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
