"""
dsf.utils.data_loader
---------------------
Reads HDF5 simulation output files and returns data in the same
`{block_id: {prop_name: array}}` shape used by the GUI's live viewers.

If the HDF5 file has a group hierarchy (new format with setGroup), each
top-level group becomes a block_id. If the file is flat (legacy format),
all datasets are placed under a single synthetic block called "simulation".
"""

from __future__ import annotations
from typing import Dict, Tuple
import numpy as np

# Vec3 component datasets are stored as base_x / base_y / base_z; this maps the
# axis index (used internally while regrouping) back to its suffix.
_AXIS_SUFFIX = {0: "x", 1: "y", 2: "z"}


def load_h5(path: str) -> Tuple[np.ndarray, Dict[str, Dict[str, np.ndarray]]]:
    """
    Load an HDF5 output file.

    Returns
    -------
    times : np.ndarray
        The Time array (shape (N,)).
    data : dict
        {block_id: {prop_name: np.ndarray(N,)}}
        For Vec3 datasets (stored as prop_x / prop_y / prop_z), they are
        reassembled into a (N, 3) array under prop name without the suffix.
    """
    import h5py

    with h5py.File(path, "r") as f:
        # Check whether the file has groups (new hierarchical format)
        groups = {k: f[k] for k in f.keys() if isinstance(f[k], h5py.Group)}
        datasets_at_root = {k: f[k] for k in f.keys() if isinstance(f[k], h5py.Dataset)}

        if groups:
            # New hierarchical format: groups are block IDs
            data: Dict[str, Dict[str, np.ndarray]] = {}
            times = None

            # The Time dataset is written at the file root, alongside the block
            # groups. Read it here; otherwise `times` would be fabricated as
            # arange(N) below, mislabeling every sample by its index instead of
            # its actual simulation time.
            if "Time" in datasets_at_root:
                times = datasets_at_root["Time"][:]

            for group_name, group in groups.items():
                block_data: Dict[str, np.ndarray] = {}
                scalars = {}
                vec_components: Dict[str, Dict[str, np.ndarray]] = {}

                for ds_name in group.keys():
                    arr = group[ds_name][:]
                    if ds_name == "Time":
                        if times is None:
                            times = arr
                        continue

                    # Vec3 reassembly: detect _x / _y / _z suffix pattern
                    for suffix, axis in [("_x", 0), ("_y", 1), ("_z", 2)]:
                        if ds_name.endswith(suffix):
                            base = ds_name[:-2]
                            if base not in vec_components:
                                vec_components[base] = {}
                            vec_components[base][axis] = arr
                            break
                    else:
                        scalars[ds_name] = arr

                # Merge scalars
                block_data.update(scalars)

                # Merge Vec3
                for base, comps in vec_components.items():
                    if len(comps) == 3:
                        mat = np.stack([comps[0], comps[1], comps[2]], axis=1)  # (N,3)
                        block_data[base] = mat
                    else:
                        # Partial — keep as individual scalars, restoring the
                        # original x/y/z suffix (comps is keyed by axis index).
                        for ax, arr in comps.items():
                            block_data[f"{base}_{_AXIS_SUFFIX.get(ax, ax)}"] = arr

                if block_data:
                    data[group_name] = block_data

            if times is None:
                # Fallback: derive from length
                first_block = next(iter(data.values()))
                first_arr = next(iter(first_block.values()))
                times = np.arange(len(first_arr))

            return times, data

        else:
            # Legacy flat format: all datasets at root
            scalars = {}
            vec_components: Dict[str, Dict[str, np.ndarray]] = {}
            times = None

            for ds_name, ds in datasets_at_root.items():
                arr = ds[:]
                if ds_name == "Time":
                    times = arr
                    continue
                for suffix, axis in [("_x", 0), ("_y", 1), ("_z", 2)]:
                    if ds_name.endswith(suffix):
                        base = ds_name[:-2]
                        if base not in vec_components:
                            vec_components[base] = {}
                        vec_components[base][axis] = arr
                        break
                else:
                    scalars[ds_name] = arr

            block_data: Dict[str, np.ndarray] = {}
            block_data.update(scalars)
            for base, comps in vec_components.items():
                if len(comps) == 3:
                    block_data[base] = np.stack([comps[0], comps[1], comps[2]], axis=1)
                else:
                    for ax, arr in comps.items():
                        block_data[f"{base}_{_AXIS_SUFFIX.get(ax, ax)}"] = arr

            if times is None:
                times = np.arange(len(next(iter(block_data.values()))))

            return times, {"simulation": block_data}


# =========================================================================
#  Trajectory Loaders (migrated from dsf.visualization.data_loader)
# =========================================================================

def load_csv_trajectory(filepath, x_col='xyz_e_0', y_col='xyz_e_1', z_col='xyz_e_2'):
    """
    Load trajectory position data from a CSV file.

    Auto-detects common column name patterns if defaults are not found.

    Args:
        filepath: Path to CSV.
        x_col, y_col, z_col: Column names for position.

    Returns:
        np.ndarray: Nx3 array of points, or None on error.
    """
    import pandas as pd

    try:
        df = pd.read_csv(filepath)

        if x_col not in df.columns:
            candidates = [['x', 'y', 'z'],
                          ['X', 'Y', 'Z'],
                          ['xyz_i_0', 'xyz_i_1', 'xyz_i_2'],
                          ['xe', 'ye', 'ze'],
                          ['Earth XYZ (x)', 'Earth XYZ (y)', 'Earth XYZ (z)'],
                          ['Earth XYZ (x) ', 'Earth XYZ (y) ', 'Earth XYZ (z) ']]

            for c in candidates:
                df_cols_stripped = [col.strip() for col in df.columns]
                c_stripped = [col.strip() for col in c]

                if all(col in df.columns for col in c):
                    x_col, y_col, z_col = c
                    break

                if all(col in df_cols_stripped for col in c_stripped):
                    x_col = df.columns[df_cols_stripped.index(c_stripped[0])]
                    y_col = df.columns[df_cols_stripped.index(c_stripped[1])]
                    z_col = df.columns[df_cols_stripped.index(c_stripped[2])]
                    break

        if x_col not in df.columns:
            raise ValueError(f"Could not find position columns. Defaults: {x_col}, {y_col}, {z_col}")

        subset = df[[x_col, y_col, z_col]].copy()
        subset = subset.apply(pd.to_numeric, errors='coerce')
        subset = subset.dropna()
        return subset.to_numpy()

    except Exception as e:
        print(f"Error loading CSV {filepath}: {e}")
        return None


def load_h5_trajectory(filepath, dataset_path='trajectory'):
    """
    Load trajectory position data from an HDF5 file.

    Args:
        filepath: Path to H5 file.
        dataset_path: Path to the dataset within the H5 file.

    Returns:
        np.ndarray: Nx3 array, or None on error.
    """
    import h5py

    try:
        with h5py.File(filepath, 'r') as f:
            if dataset_path in f:
                data = f[dataset_path][:]
                if data.ndim == 2 and data.shape[0] == 3 and data.shape[1] > 3:
                    data = data.T
                return data
            else:
                for key in f.keys():
                    d = f[key]
                    # Only consider 2-D Nx3 / 3xN datasets. Probing shape[1] on a
                    # 1-D dataset (e.g. the Time array) raised IndexError and
                    # aborted the whole load.
                    if hasattr(d, 'ndim') and d.ndim == 2 and (d.shape[1] == 3 or d.shape[0] == 3):
                        data = d[:]
                        if data.shape[0] == 3 and data.shape[1] != 3:
                            data = data.T
                        return data
                print(f"Dataset {dataset_path} not found in {filepath}")
                return None
    except Exception as e:
        print(f"Error loading H5 {filepath}: {e}")
        return None
