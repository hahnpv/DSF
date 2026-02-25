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

    import math

    app = QApplication.instance() or QApplication(sys.argv)

    win = MapWindow()
    win.setWindowTitle(f"dsf map — {os.path.basename(h5_path)}")
    win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    # Property-name aliases: HDF5 display name → map_widget internal name
    # map_widget expects lambda_d (geodetic lat, rad) and l_i_earth (geo lon, rad).
    # HDF5 stores these as "Latitude" and "Earth Longitude" in degrees.
    LAT_KEYS = {"Latitude", "lambda_d", "lat", "latitude"}
    LON_KEYS = {"Earth Longitude", "l_i_earth", "lon", "longitude", "Earth\\ Longitude"}

    for i, t in enumerate(times):
        frame = {}
        for block_id, props in data.items():
            block_frame = {}
            lat_val = None
            lon_val = None
            for prop, vals in props.items():
                v = float(vals[i]) if vals.ndim == 1 else vals[i].tolist()
                block_frame[prop] = v
                # Detect lat/lon — stored in degrees in HDF5
                if prop in LAT_KEYS and vals.ndim == 1:
                    lat_val = math.radians(float(vals[i]))
                if prop in LON_KEYS and vals.ndim == 1:
                    lon_val = math.radians(float(vals[i]))

            # Inject with the names map_widget looks for
            if lat_val is not None:
                block_frame["lambda_d"] = lat_val
            if lon_val is not None:
                block_frame["l_i_earth"] = lon_val
            frame[block_id] = block_frame

        win.update_deep_data(t, frame)

    win.show()
    sys.exit(app.exec())
