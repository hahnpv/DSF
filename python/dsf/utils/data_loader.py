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
                        # Partial — keep as individual scalars
                        for ax, arr in comps.items():
                            block_data[f"{base}_{ax}"] = arr

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
                        block_data[f"{base}_{ax}"] = arr

            if times is None:
                times = np.arange(len(next(iter(block_data.values()))))

            return times, {"simulation": block_data}
