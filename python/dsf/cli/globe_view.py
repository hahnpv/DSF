"""
dsf.cli.globe_view
------------------
Replay an HDF5 output file in the 3D PyVista globe (GlobePlotter).
Looks for XYZ ECEF position data (stored as a Vec3 dataset named "xyz_e"
or individual "XYZ_x/y/z" columns in a flat file).
"""

from __future__ import annotations
import sys
import os
import numpy as np


def run_globe(h5_path: str):
    from dsf.visualization.globe import GlobePlotter
    from dsf.utils.data_loader import load_h5

    print(f"Loading {h5_path}...")
    times, data = load_h5(h5_path)
    print(f"  {len(times)} timesteps, {len(data)} block(s)")

    gp = GlobePlotter(distinct_window=True)
    colors = ["cyan", "magenta", "orange", "lime", "yellow", "white", "red", "blue"]

    color_idx = 0
    found_any = False

    for block_id, props in data.items():
        xyz = None

        # Prefer ECEF position datasets (Earth-fixed, correct for ground track)
        for ecef_key in ("XYZ_ECEF", "xyz_e"):
            if ecef_key in props:
                arr = props[ecef_key]
                if arr.ndim == 2 and arr.shape[1] == 3:
                    xyz = arr
                    break

        # Fallback only if no ECEF data available — note XYZ is ECI (not Earth-fixed)
        if xyz is None and "XYZ" in props:
            arr = props["XYZ"]
            if arr.ndim == 2 and arr.shape[1] == 3:
                xyz = arr
                print(f"  Warning: '{block_id}' using ECI XYZ (no ECEF data found)")

        if xyz is not None and len(xyz) > 2:
            c = colors[color_idx % len(colors)]
            print(f"  Block '{block_id}': {len(xyz)} XYZ points → {c}")
            gp.add_trajectory(xyz, name=f"Traj_{block_id}", color=c, line_width=2, stop_marker=True)
            gp.add_ground_track(xyz, name=f"Gnd_{block_id}", color=c, line_width=1)
            color_idx += 1
            found_any = True

    if not found_any:
        print("Warning: no ECEF XYZ position data found in this file.")
        print("Available blocks/props:", {k: list(v.keys()) for k, v in data.items()})

    # Set wide camera for MEO/GEO orbits
    R_EARTH = 6378137.0
    gp.plotter.camera_position = [(10 * R_EARTH, 0, 0), (0, 0, 0), (0, 0, 1)]

    gp.plotter.show(title=f"dsf globe — {os.path.basename(h5_path)}")
    gp.close()
