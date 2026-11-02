import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import tifffile
from PIL import Image, ImageTk
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_scan_folders(root):
    prefixes = ("output_tiff", "automap", "scan")
    return sorted([
        d for d in os.listdir(root)
        if os.path.isdir(os.path.join(root, d)) and d.startswith(prefixes)
    ])


def load_band(path):
    arr = tifffile.imread(path).astype(np.float32)
    lo, hi = np.nanpercentile(arr, 2), np.nanpercentile(arr, 98)
    if hi > lo:
        arr = (arr - lo) / (hi - lo)
    else:
        arr = np.zeros_like(arr)
    return np.clip(arr, 0, 1)


def make_rgb(r_path, g_path, b_path):
    r = load_band(r_path)
    g = load_band(g_path)
    b = load_band(b_path)
    h = min(r.shape[0], g.shape[0], b.shape[0])
    w = min(r.shape[1], g.shape[1], b.shape[1])
    rgb = np.stack([r[:h, :w], g[:h, :w], b[:h, :w]], axis=-1)
    rgb = (rgb * 255).astype(np.uint8)
    return Image.fromarray(rgb)


def normalize_to_pil(path):
    arr = tifffile.imread(path).astype(np.float32)
    if arr.ndim > 2:
        arr = arr[..., 0]
    lo, hi = np.nanpercentile(arr, 2), np.nanpercentile(arr, 98)
    if hi > lo:
        arr = (arr - lo) / (hi - lo)
    else:
        arr = np.zeros_like(arr)
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XRF Mosaic Viewer")
        self.configure(bg="#1e1e2e")
        self.resizable(True, True)

        self.root_dir = SCRIPT_DIR

        self._apply_style()

        self.notebook = ttk.Notebook(self, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 8))

        self.rgb_tab = tk.Frame(self.notebook, bg="#1e1e2e")
        self.notebook.add(self.rgb_tab, text="  RGB Composer  ")

        self.single_tab = tk.Frame(self.notebook, bg="#1e1e2e")
        self.notebook.add(self.single_tab, text="  Single TIFF  ")

        self._build_rgb_sidebar()
        self._build_rgb_image_panel()
        self._build_single_tiff_tab()

        # RGB state
        self.current_pil = None
        self._zoom = 1.0
        self._pinned_channels = {"R": "", "G": "", "B": ""}

        # Single TIFF state
        self.single_folder = None
        self.single_files = []
        self.single_idx = 0
        self.single_pil = None
        self._single_zoom = 1.0

        self.bind("<Left>", self._on_left)
        self.bind("<Right>", self._on_right)

        self._load_root(SCRIPT_DIR)

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Dark.TNotebook", background="#1e1e2e", borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("Dark.TNotebook.Tab",
                        background="#313244", foreground="#cdd6f4",
                        font=("Helvetica", 10, "bold"),
                        padding=[12, 6])
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", "#89b4fa"), ("active", "#45475a")],
                  foreground=[("selected", "#1e1e2e"), ("active", "#cdd6f4")])
        style.configure("TCombobox",
                        fieldbackground="#313244", background="#313244",
                        foreground="#cdd6f4", selectbackground="#45475a",
                        selectforeground="#cdd6f4", arrowcolor="#cdd6f4")
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#313244"), ("disabled", "#1e1e2e")],
                  foreground=[("readonly", "#cdd6f4"), ("disabled", "#6c7086")],
                  selectbackground=[("readonly", "#313244")],
                  selectforeground=[("readonly", "#cdd6f4")])

    # ---------------------------------------------------------------- key nav

    def _on_left(self, e):
        if self.notebook.index(self.notebook.select()) == 0:
            self._nav_folder(-1)
        else:
            self._nav_single(-1)

    def _on_right(self, e):
        if self.notebook.index(self.notebook.select()) == 0:
            self._nav_folder(1)
        else:
            self._nav_single(1)

    # ---------------------------------------------------------------- RGB TAB

    def _build_rgb_sidebar(self):
        side = tk.Frame(self.rgb_tab, bg="#1e1e2e", width=280)
        side.pack(side="left", fill="y", padx=(12, 0), pady=12)
        side.pack_propagate(False)

        tk.Label(side, text="Root directory", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Helvetica", 11, "bold")).pack(anchor="w")
        self.root_label_var = tk.StringVar(value=SCRIPT_DIR)
        tk.Label(side, textvariable=self.root_label_var, bg="#1e1e2e", fg="#6c7086",
                 font=("Helvetica", 8), wraplength=260, justify="left").pack(anchor="w")
        tk.Button(side, text="Browse root folder…", command=self._browse_root,
                  bg="#313244", fg="#cdd6f4", font=("Helvetica", 9),
                  relief="flat", padx=6, pady=3, cursor="hand2").pack(fill="x", pady=(4, 12))

        tk.Label(side, text="Scan folder", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Helvetica", 11, "bold")).pack(anchor="w")
        self.folder_var = tk.StringVar()
        self.folder_cb = ttk.Combobox(side, textvariable=self.folder_var,
                                      values=[], state="readonly", width=30)
        self.folder_cb.pack(fill="x", pady=(4, 12))
        self.folder_cb.bind("<<ComboboxSelected>>", lambda e: self._on_folder_change())

        self.channel_vars = {}
        self.channel_cbs = {}
        self.channel_file_labels = {}
        ch_colors = {"R": "#f38ba8", "G": "#a6e3a1", "B": "#89b4fa"}
        for ch, color in ch_colors.items():
            header = tk.Frame(side, bg="#1e1e2e")
            header.pack(fill="x", pady=(6, 0))
            tk.Label(header, text=f"{ch} channel", bg="#1e1e2e", fg=color,
                     font=("Helvetica", 10, "bold")).pack(side="left")
            tk.Button(header, text="x", command=lambda c=ch: self._unpin_channel(c),
                      bg="#1e1e2e", fg="#6c7086", font=("Helvetica", 8),
                      relief="flat", cursor="hand2", padx=2, pady=0,
                      activebackground="#1e1e2e", activeforeground="#f38ba8").pack(side="right")

            var = tk.StringVar()
            cb = ttk.Combobox(side, textvariable=var, state="readonly", width=30)
            cb.pack(fill="x", pady=(2, 0))
            self.channel_vars[ch] = var
            self.channel_cbs[ch] = cb
            cb.bind("<<ComboboxSelected>>", lambda e, c=ch: self._on_channel_pick(c))

            lbl = tk.Label(side, text="", bg="#1e1e2e", fg="#6c7086",
                           font=("Helvetica", 8), wraplength=258, justify="left")
            lbl.pack(anchor="w", pady=(1, 2))
            self.channel_file_labels[ch] = lbl

        tk.Button(side, text="Compose RGB", command=self._compose,
                  bg="#89b4fa", fg="#1e1e2e", font=("Helvetica", 11, "bold"),
                  relief="flat", padx=8, pady=6, cursor="hand2").pack(fill="x", pady=(12, 0))

        zoom_frame = tk.Frame(side, bg="#1e1e2e")
        zoom_frame.pack(fill="x", pady=(12, 0))
        tk.Label(zoom_frame, text="Zoom", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Helvetica", 10)).pack(side="left")
        tk.Button(zoom_frame, text=" - ", command=self._zoom_out,
                  bg="#313244", fg="#cdd6f4", relief="flat", cursor="hand2").pack(side="right")
        tk.Button(zoom_frame, text=" + ", command=self._zoom_in,
                  bg="#313244", fg="#cdd6f4", relief="flat", cursor="hand2").pack(side="right", padx=4)
        tk.Button(zoom_frame, text="fit", command=self._zoom_fit,
                  bg="#313244", fg="#cdd6f4", relief="flat", cursor="hand2").pack(side="right")

        tk.Button(side, text="Save PNG…", command=self._save,
                  bg="#313244", fg="#cdd6f4", font=("Helvetica", 10),
                  relief="flat", padx=6, pady=4, cursor="hand2").pack(fill="x", pady=(8, 0))

        self.status_var = tk.StringVar(value="Select 3 channels and click Compose RGB")
        tk.Label(side, textvariable=self.status_var, bg="#1e1e2e", fg="#6c7086",
                 font=("Helvetica", 9), wraplength=260, justify="left").pack(
            anchor="w", pady=(12, 0))

    def _build_rgb_image_panel(self):
        panel = tk.Frame(self.rgb_tab, bg="#181825")
        panel.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        self.canvas = tk.Canvas(panel, bg="#181825", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

    # -------------------------------------------------------- SINGLE TIFF TAB

    def _build_single_tiff_tab(self):
        # Left panel: folder picker + file list
        left = tk.Frame(self.single_tab, bg="#1e1e2e", width=260)
        left.pack(side="left", fill="y", padx=(12, 0), pady=12)
        left.pack_propagate(False)

        tk.Label(left, text="Single TIFF Viewer", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Helvetica", 11, "bold")).pack(anchor="w")

        tk.Button(left, text="Browse folder…", command=self._single_browse,
                  bg="#313244", fg="#cdd6f4", font=("Helvetica", 9),
                  relief="flat", padx=6, pady=3, cursor="hand2").pack(fill="x", pady=(6, 4))

        self.single_folder_label = tk.Label(
            left, text="No folder selected", bg="#1e1e2e", fg="#6c7086",
            font=("Helvetica", 8), wraplength=240, justify="left")
        self.single_folder_label.pack(anchor="w", pady=(0, 8))

        tk.Label(left, text="TIFF files", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Helvetica", 10, "bold")).pack(anchor="w")

        list_frame = tk.Frame(left, bg="#181825", relief="flat", bd=1)
        list_frame.pack(fill="both", expand=True, pady=(4, 0))

        scrollbar = tk.Scrollbar(list_frame, orient="vertical", bg="#313244",
                                 troughcolor="#181825", bd=0)
        scrollbar.pack(side="right", fill="y")

        self.single_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg="#181825", fg="#cdd6f4",
            selectbackground="#89b4fa", selectforeground="#1e1e2e",
            font=("Helvetica", 9),
            relief="flat",
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
        )
        self.single_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.single_listbox.yview)
        self.single_listbox.bind("<<ListboxSelect>>", self._on_single_select)

        nav_frame = tk.Frame(left, bg="#1e1e2e")
        nav_frame.pack(fill="x", pady=(8, 0))
        tk.Button(nav_frame, text="← Prev", command=lambda: self._nav_single(-1),
                  bg="#313244", fg="#cdd6f4", relief="flat", cursor="hand2",
                  padx=6, pady=4).pack(side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(nav_frame, text="Next →", command=lambda: self._nav_single(1),
                  bg="#313244", fg="#cdd6f4", relief="flat", cursor="hand2",
                  padx=6, pady=4).pack(side="right", fill="x", expand=True, padx=(2, 0))

        self.single_status_var = tk.StringVar(value="Browse a folder to begin  |  ← → to navigate")
        tk.Label(left, textvariable=self.single_status_var, bg="#1e1e2e", fg="#6c7086",
                 font=("Helvetica", 8), wraplength=240, justify="left").pack(
            anchor="w", pady=(8, 0))

        # Right panel: image + zoom bar
        right = tk.Frame(self.single_tab, bg="#181825")
        right.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        zoom_bar = tk.Frame(right, bg="#181825")
        zoom_bar.pack(fill="x", side="bottom", pady=(4, 0))
        tk.Button(zoom_bar, text="fit", command=self._single_zoom_fit,
                  bg="#313244", fg="#cdd6f4", relief="flat", cursor="hand2").pack(side="left")
        tk.Button(zoom_bar, text=" + ", command=self._single_zoom_in,
                  bg="#313244", fg="#cdd6f4", relief="flat", cursor="hand2").pack(side="left", padx=4)
        tk.Button(zoom_bar, text=" - ", command=self._single_zoom_out,
                  bg="#313244", fg="#cdd6f4", relief="flat", cursor="hand2").pack(side="left")

        self.single_canvas = tk.Canvas(right, bg="#181825", highlightthickness=0)
        self.single_canvas.pack(fill="both", expand=True)

        self.single_canvas.bind("<MouseWheel>", self._on_single_mousewheel)
        self.single_canvas.bind("<Button-4>", self._on_single_mousewheel)
        self.single_canvas.bind("<Button-5>", self._on_single_mousewheel)

    # -------------------------------------------- Single TIFF logic

    def _single_browse(self):
        chosen = filedialog.askdirectory(title="Select folder with TIFF files")
        if not chosen:
            return
        self.single_folder = chosen
        self.single_folder_label.config(text=chosen)
        files = sorted([
            f for f in os.listdir(chosen)
            if f.lower().endswith(".tiff") or f.lower().endswith(".tif")
        ])
        self.single_files = files
        self.single_listbox.delete(0, "end")
        for f in files:
            self.single_listbox.insert("end", f)
        if files:
            self.single_idx = 0
            self.single_listbox.selection_set(0)
            self.single_listbox.see(0)
            self._load_single(0)
        else:
            self.single_status_var.set("No TIFF files found in this folder.")

    def _on_single_select(self, event):
        sel = self.single_listbox.curselection()
        if sel:
            self.single_idx = sel[0]
            self._load_single(self.single_idx)

    def _nav_single(self, direction):
        if not self.single_files:
            return
        self.single_idx = (self.single_idx + direction) % len(self.single_files)
        self.single_listbox.selection_clear(0, "end")
        self.single_listbox.selection_set(self.single_idx)
        self.single_listbox.see(self.single_idx)
        self._load_single(self.single_idx)

    def _load_single(self, idx):
        if not self.single_files or idx >= len(self.single_files):
            return
        fname = self.single_files[idx]
        path = os.path.join(self.single_folder, fname)
        try:
            pil = normalize_to_pil(path)
            self.single_pil = pil
            self._single_zoom = 1.0
            self._single_zoom_fit()
            self.single_status_var.set(
                f"[{idx + 1}/{len(self.single_files)}] {fname}\n"
                f"{pil.width}×{pil.height} px  |  ← → to navigate"
            )
        except Exception as ex:
            self.single_status_var.set(f"Error: {ex}")

    def _single_display(self):
        if self.single_pil is None:
            return
        w = max(1, int(self.single_pil.width * self._single_zoom))
        h = max(1, int(self.single_pil.height * self._single_zoom))
        img = self.single_pil.resize((w, h), Image.LANCZOS)
        self._single_tk_img = ImageTk.PhotoImage(img)
        self.single_canvas.delete("all")
        cw = self.single_canvas.winfo_width()
        ch = self.single_canvas.winfo_height()
        self.single_canvas.create_image(
            max(w // 2, cw // 2), max(h // 2, ch // 2),
            anchor="center", image=self._single_tk_img,
        )

    def _single_zoom_fit(self):
        if self.single_pil is None:
            return
        self.update_idletasks()
        cw = self.single_canvas.winfo_width() or 800
        ch = self.single_canvas.winfo_height() or 600
        self._single_zoom = min(cw / self.single_pil.width, ch / self.single_pil.height)
        self._single_display()

    def _single_zoom_in(self):
        self._single_zoom = min(self._single_zoom * 1.25, 16)
        self._single_display()

    def _single_zoom_out(self):
        self._single_zoom = max(self._single_zoom * 0.8, 0.05)
        self._single_display()

    def _on_single_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self._single_zoom_in()
        else:
            self._single_zoom_out()

    # -------------------------------------------- RGB logic

    def _browse_root(self):
        chosen = filedialog.askdirectory(title="Select root folder", initialdir=self.root_dir)
        if chosen:
            self._load_root(chosen)

    def _load_root(self, path):
        self.root_dir = path
        self.root_label_var.set(path)
        folders = get_scan_folders(path)
        self.folder_cb["values"] = folders
        self.folder_var.set("")
        for cb in self.channel_cbs.values():
            cb["values"] = []
            cb.set("")
        if folders:
            self.folder_var.set(folders[0])
            self._on_folder_change()
        else:
            self.status_var.set("No output_tiff* folders found in selected directory")

    def _unpin_channel(self, ch):
        self._pinned_channels[ch] = ""
        self._update_channel_label(ch, pinned=False)

    def _update_channel_label(self, ch, pinned):
        fname = self.channel_vars[ch].get()
        if not fname:
            self.channel_file_labels[ch].config(text="", fg="#6c7086")
        elif pinned:
            self.channel_file_labels[ch].config(text=f"pinned: {fname}", fg="#fab387")
        else:
            self.channel_file_labels[ch].config(text=fname, fg="#6c7086")

    def _on_channel_pick(self, ch):
        self._pinned_channels[ch] = self.channel_vars[ch].get()
        self._update_channel_label(ch, pinned=True)

    def _nav_folder(self, direction):
        folders = list(self.folder_cb["values"])
        if not folders:
            return
        current = self.folder_var.get()
        try:
            idx = folders.index(current)
        except ValueError:
            idx = 0
        self.folder_var.set(folders[(idx + direction) % len(folders)])
        self._on_folder_change()

    def _on_folder_change(self):
        folder = self.folder_var.get()
        path = os.path.join(self.root_dir, folder)
        files = sorted([f for f in os.listdir(path) if f.lower().endswith(".tiff")])
        file_set = set(files)
        for ch in ("R", "G", "B"):
            self.channel_cbs[ch]["values"] = files

        # restore pinned channels; fill any unpinned slots with random picks
        assigned = {}
        for ch in ("R", "G", "B"):
            pinned = self._pinned_channels[ch]
            if pinned in file_set:
                assigned[ch] = pinned
                self.channel_cbs[ch].set(pinned)
            else:
                assigned[ch] = None
                self.channel_cbs[ch].set("")

        unpinned = [ch for ch in ("R", "G", "B") if assigned[ch] is None]
        if unpinned and files:
            used = set(v for v in assigned.values() if v)
            pool = [f for f in files if f not in used]
            if len(pool) < len(unpinned):
                pool = files  # fall back to full list if not enough distinct files
            picks = random.sample(pool, min(len(unpinned), len(pool)))
            for ch, pick in zip(unpinned, picks):
                self.channel_cbs[ch].set(pick)
                assigned[ch] = pick

        for ch in ("R", "G", "B"):
            self._update_channel_label(ch, pinned=bool(self._pinned_channels[ch] and self._pinned_channels[ch] in file_set))

        folders = list(self.folder_cb["values"])
        idx = folders.index(folder) + 1 if folder in folders else "?"
        self.status_var.set(f"Folder {idx}/{len(folders)}: {folder}  (← → to navigate)")

        if all(self.channel_vars[ch].get() for ch in ("R", "G", "B")):
            self._compose(silent=True)

    def _compose(self, silent=False):
        folder = self.folder_var.get()
        if not folder:
            if not silent:
                messagebox.showwarning("No folder", "Please select a scan folder.")
            return

        paths = {}
        for ch in ("R", "G", "B"):
            val = self.channel_vars[ch].get()
            if not val:
                if not silent:
                    messagebox.showwarning("Missing channel", f"Please select a file for the {ch} channel.")
                return
            paths[ch] = os.path.join(self.root_dir, folder, val)

        self.status_var.set("Composing…")
        self.update_idletasks()
        try:
            img = make_rgb(paths["R"], paths["G"], paths["B"])
            self.current_pil = img
            self._zoom = 1.0
            self._zoom_fit()
            folders = list(self.folder_cb["values"])
            idx = folders.index(folder) + 1 if folder in folders else "?"
            self.status_var.set(
                f"[{idx}/{len(folders)}] {folder}\n"
                f"R: {os.path.basename(paths['R'])}\n"
                f"G: {os.path.basename(paths['G'])}\n"
                f"B: {os.path.basename(paths['B'])}\n"
                f"{img.width}×{img.height} px  |  ← → to navigate"
            )
        except Exception as ex:
            if not silent:
                messagebox.showerror("Error", str(ex))
            self.status_var.set(f"Error: {ex}")

    def _display(self):
        if self.current_pil is None:
            return
        w = max(1, int(self.current_pil.width * self._zoom))
        h = max(1, int(self.current_pil.height * self._zoom))
        img = self.current_pil.resize((w, h), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        self.canvas.create_image(
            max(w // 2, cw // 2), max(h // 2, ch // 2),
            anchor="center", image=self._tk_img,
        )

    def _zoom_fit(self):
        if self.current_pil is None:
            return
        self.update_idletasks()
        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 600
        self._zoom = min(cw / self.current_pil.width, ch / self.current_pil.height)
        self._display()

    def _zoom_in(self):
        self._zoom = min(self._zoom * 1.25, 16)
        self._display()

    def _zoom_out(self):
        self._zoom = max(self._zoom * 0.8, 0.05)
        self._display()

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()

    def _save(self):
        if self.current_pil is None:
            messagebox.showinfo("Nothing to save", "Compose an image first.")
            return
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("TIFF", "*.tiff")],
            initialfile="rgb_composite.png",
        )
        if path:
            self.current_pil.save(path)
            self.status_var.set(f"Saved → {os.path.basename(path)}")


if __name__ == "__main__":
    app = App()
    app.geometry("1100x700")
    app.mainloop()
