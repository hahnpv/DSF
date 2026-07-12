"""
dsf.utils.data_loader
---------------------
The single reader for DSF simulation output files, plus the channel
resolvers the CLI views share.

`load_h5` reads an HDF5 output file into the same
`{block_id: {prop_name: array}}` shape used by the GUI's live viewers.
If the file has a group hierarchy (new format with setGroup), each
top-level group becomes a block_id. If the file is flat (legacy format),
all datasets are placed under a single synthetic block called "simulation".

`find_geodetic` / `find_ecef` own the position-channel alias tables that
were previously duplicated (with drift) across map_view, globe_view, and
terrain_view. Angle units VARY BY MODEL (6DOF/HydroEOM log radians,
Equinoctial logs degrees) and the HDF5 datasets say which via their
`units` attribute — load_h5 preserves it (`BlockData.units`) and
find_geodetic normalizes to RADIANS; callers convert for display.
"""

from __future__ import annotations
from typing import Dict, Optional, Tuple
import numpy as np

# Vec3 component datasets are stored as base_x / base_y / base_z; this maps the
# axis index (used internally while regrouping) back to its suffix.
_AXIS_SUFFIX = {0: "x", 1: "y", 2: "z"}


class BlockData(dict):
    """{prop_name: array} plus per-channel units from the HDF5 `units`
    attribute (`.units` maps prop_name → e.g. 'rad'/'deg'/'m'; channels
    without an attribute are absent). A dict subclass so every existing
    `{block: {prop: array}}` consumer keeps working unchanged."""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.units: Dict[str, str] = {}


def _regroup_vec3(items) -> BlockData:
    """Regroup (name, array, units) triples: full _x/_y/_z triplets become one
    (N,3) array under the base name; partial triplets keep their original
    suffix; everything else passes through unchanged. Units follow the
    channel (a Vec3 takes its components' units)."""
    out = BlockData()
    vec_components: Dict[str, Dict[int, np.ndarray]] = {}
    vec_units: Dict[str, str] = {}

    for name, arr, units in items:
        for suffix, axis in (("_x", 0), ("_y", 1), ("_z", 2)):
            if name.endswith(suffix):
                base = name[:-2]
                vec_components.setdefault(base, {})[axis] = arr
                if units is not None:
                    vec_units[base] = units
                break
        else:
            out[name] = arr
            if units is not None:
                out.units[name] = units

    for base, comps in vec_components.items():
        if len(comps) == 3:
            out[base] = np.stack([comps[0], comps[1], comps[2]], axis=1)  # (N,3)
            if base in vec_units:
                out.units[base] = vec_units[base]
        else:
            # Partial — keep as individual scalars, restoring the original
            # x/y/z suffix (comps is keyed by axis index).
            for ax, arr in comps.items():
                name = f"{base}_{_AXIS_SUFFIX.get(ax, ax)}"
                out[name] = arr
                if base in vec_units:
                    out.units[name] = vec_units[base]
    return out


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

        # The Time dataset is written at the file root, alongside any block
        # groups. Read it here; otherwise `times` would be fabricated as
        # arange(N) below, mislabeling every sample by its index instead of
        # its actual simulation time.
        times = datasets_at_root["Time"][:] if "Time" in datasets_at_root else None

        def _units(ds):
            u = ds.attrs.get("units")
            return u.decode() if isinstance(u, bytes) else u

        if groups:
            # New hierarchical format: groups are block IDs
            data: Dict[str, Dict[str, np.ndarray]] = {}
            for group_name, group in groups.items():
                items = []
                for ds_name in group.keys():
                    ds = group[ds_name]
                    arr = ds[:]
                    if ds_name == "Time":
                        if times is None:
                            times = arr
                        continue
                    items.append((ds_name, arr, _units(ds)))
                block_data = _regroup_vec3(items)
                if block_data:
                    data[group_name] = block_data
        else:
            # Legacy flat format: all datasets at root → one synthetic block
            items = [(name, ds[:], _units(ds))
                     for name, ds in datasets_at_root.items() if name != "Time"]
            data = {"simulation": _regroup_vec3(items)}

        if times is None:
            # Fallback: derive from length
            first_block = next(iter(data.values()))
            first_arr = next(iter(first_block.values()))
            times = np.arange(len(first_arr))

        return times, data


# =========================================================================
#  Channel resolvers — one home for the position-channel alias tables
# =========================================================================

# Names are compared case-insensitively with backslash-escapes stripped
# (some decks log "Earth\ Longitude").
_LAT_KEYS = {"latitude", "lambda_d", "lat"}
_LON_KEYS = {"earth longitude", "l_i_earth", "lon"}   # Earth-fixed
_LON_INERTIAL_KEYS = {"longitude"}                    # inertial fallback
_ALT_KEYS = {"altitude", "alt"}

# ECEF position (Earth-fixed — correct for ground tracks); plain XYZ is ECI.
_ECEF_KEYS = ("XYZ_ECEF", "xyz_e")
_ECI_KEY = "XYZ"


def _norm(name: str) -> str:
    return name.replace("\\", "").strip().lower()


def find_geodetic(data: Dict[str, Dict[str, np.ndarray]]
                  ) -> Dict[str, Dict[str, np.ndarray]]:
    """Resolve geodetic position channels per block.

    Returns {block_id: {'lat': arr, 'lon': arr, 'alt': arr}} with whichever
    keys were found (blocks with none are omitted). Angles are normalized to
    RADIANS using each channel's HDF5 `units` attribute (models disagree:
    6DOF/HydroEOM log radians, Equinoctial logs degrees). A channel without
    a units attribute is assumed radians. Earth-fixed longitude is
    preferred, inertial longitude is the fallback.
    """
    out: Dict[str, Dict[str, np.ndarray]] = {}
    for block_id, props in data.items():
        units = getattr(props, "units", {})

        def _rad(prop, arr):
            return np.radians(arr) if units.get(prop) == "deg" else arr

        found: Dict[str, np.ndarray] = {}
        lon_inertial = None
        for prop, arr in props.items():
            if getattr(arr, "ndim", 0) != 1:
                continue
            n = _norm(prop)
            if n in _LAT_KEYS and "lat" not in found:
                found["lat"] = _rad(prop, arr)
            elif n in _LON_KEYS and "lon" not in found:
                found["lon"] = _rad(prop, arr)
            elif n in _LON_INERTIAL_KEYS and lon_inertial is None:
                lon_inertial = _rad(prop, arr)
            elif n in _ALT_KEYS and "alt" not in found:
                found["alt"] = arr
        if "lon" not in found and lon_inertial is not None:
            found["lon"] = lon_inertial
        if found:
            out[block_id] = found
    return out


def find_ecef(data: Dict[str, Dict[str, np.ndarray]]
              ) -> Dict[str, Tuple[np.ndarray, str]]:
    """Resolve cartesian position per block.

    Returns {block_id: (xyz (N,3), frame)} where frame is 'ecef' or — only
    when no Earth-fixed dataset exists — 'eci' (callers should warn: ECI is
    wrong for ground tracks).
    """
    out: Dict[str, Tuple[np.ndarray, str]] = {}
    for block_id, props in data.items():
        def _nx3(key):
            arr = props.get(key)
            if arr is not None and getattr(arr, "ndim", 0) == 2 and arr.shape[1] == 3:
                return arr
            return None
        xyz = None
        for key in _ECEF_KEYS:
            xyz = _nx3(key)
            if xyz is not None:
                out[block_id] = (xyz, "ecef")
                break
        if xyz is None:
            xyz = _nx3(_ECI_KEY)
            if xyz is not None:
                out[block_id] = (xyz, "eci")
    return out


# =========================================================================
#  Trajectory loader (thin adapter over load_h5)
# =========================================================================

def load_h5_trajectory(filepath, dataset_path='trajectory') -> Optional[np.ndarray]:
    """
    Load trajectory position data from an HDF5 file.

    Looks for `dataset_path` first, then falls back to the first Nx3 (or
    3xN, transposed) array in the file. Adapter over load_h5 — no separate
    H5-walking code.

    Args:
        filepath: Path to H5 file.
        dataset_path: Dataset name to prefer.

    Returns:
        np.ndarray: Nx3 array, or None on error.
    """
    def _as_nx3(arr):
        if getattr(arr, "ndim", 0) != 2:
            return None
        if arr.shape[1] == 3:
            return arr
        if arr.shape[0] == 3 and arr.shape[1] > 3:
            return arr.T
        return None

    try:
        _, data = load_h5(filepath)
        # Preferred name first (in any block), then the first Nx3 anywhere.
        for props in data.values():
            if dataset_path in props:
                arr = _as_nx3(props[dataset_path])
                if arr is not None:
                    return arr
        for props in data.values():
            for arr in props.values():
                nx3 = _as_nx3(arr)
                if nx3 is not None:
                    return nx3
        print(f"Dataset {dataset_path} not found in {filepath}")
        return None
    except Exception as e:
        print(f"Error loading H5 {filepath}: {e}")
        return None
