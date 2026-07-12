"""
dsf.cli.map_view
----------------
Replay an HDF5 output file in the 2D ground-track map (MapWidget).
"""

from __future__ import annotations
import sys
import os


def run_map(h5_path: str):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    from dsf.gui.ui.map_window import MapWindow
    from dsf.utils.data_loader import load_h5

    print(f"Loading {h5_path}...")
    times, data = load_h5(h5_path)
    print(f"  {len(times)} timesteps, {len(data)} block(s)")

    app = QApplication.instance() or QApplication(sys.argv)

    win = MapWindow()
    win.setWindowTitle(f"dsf map — {os.path.basename(h5_path)}")
    win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    # map_widget expects lambda_d (geodetic lat, rad) and l_i_earth (geo lon,
    # rad). find_geodetic owns the channel aliases and the radians convention.
    from dsf.utils.data_loader import find_geodetic
    geo = find_geodetic(data)

    # In replay mode we have all frames upfront — keep the full history
    win.map_widget.max_history = len(times)

    for i, t in enumerate(times):
        frame = {}
        for block_id, props in data.items():
            block_frame = {
                prop: (float(vals[i]) if vals.ndim == 1 else vals[i].tolist())
                for prop, vals in props.items()
            }
            # Inject with the names map_widget looks for
            g = geo.get(block_id, {})
            if "lat" in g:
                block_frame["lambda_d"] = float(g["lat"][i])
            if "lon" in g:
                block_frame["l_i_earth"] = float(g["lon"][i])
            frame[block_id] = block_frame

        win.update_deep_data(t, frame)

    win.show()
    sys.exit(app.exec())
