# XRF Mosaic Viewer

A desktop GUI for browsing and compositing XRF scan TIFF files into false-colour RGB images.

---

## Features

- **RGB Composer** — assign any three TIFF bands to R, G, B channels and compose a false-colour image; pin a channel so it stays fixed while you flip through scan folders with the arrow keys
- **Single TIFF Viewer** — browse any folder of `.tif`/`.tiff` files one-by-one with a scrollable file list and keyboard navigation
- Auto-detects scan folders named `output_tiff*`, `automap*`, or `scan*` under the root directory
- 2%–98% percentile stretch applied automatically so faint detail is visible
- Zoom in/out with buttons or mouse wheel; fit-to-window button
- Save composed RGB image as PNG or TIFF

---

## Requirements

- Python 3.8 or newer
- `numpy`
- `tifffile`
- `Pillow`
- `tkinter` (bundled with Python on Windows; on Linux install `python3-tk`)

Install the Python packages:

```bash
pip install numpy tifffile Pillow
```

On Linux, if the window does not open:

```bash
sudo apt install python3-tk   # Debian/Ubuntu
```

---

## Running

### Linux / macOS

```bash
python3 rgb_viewer.py
```

Or use the included launcher (makes it double-clickable):

```bash
bash run_rgb_viewer.sh
```

### Windows

Double-click `run_rgb_viewer.bat`, or run:

```cmd
python rgb_viewer.py
```

---

## Data layout expected by the RGB Composer

The viewer looks for subfolders whose names start with `output_tiff`, `automap`, or `scan` inside the chosen root directory. Each subfolder should contain `.tiff` files (one file per element/band).

```
root/
├── output_tiff_Fe/
│   ├── Fe_Ka.tiff
│   └── ...
├── output_tiff_Cu/
│   └── ...
└── scan_001/
    └── ...
```

You can also **Browse root folder…** from inside the app to point it at any directory.

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `←` | Previous scan folder (RGB tab) / previous file (Single TIFF tab) |
| `→` | Next scan folder (RGB tab) / next file (Single TIFF tab) |
