"""
Unit tests for dsf.utils.data_loader HDF5 handling.

Regression coverage:
  - root-level Time dataset is used (not fabricated as arange)          [Time bug]
  - partial Vec3 datasets keep their x/y/z suffix (not axis integers)   [M5]
  - a 1-D dataset (e.g. Time) does not crash Nx3 trajectory probing     [M13]
  - flat legacy files regroup Vec3 identically to hierarchical ones     [R7]
  - find_geodetic / find_ecef channel resolution (the alias tables the
    CLI views share instead of carrying their own)                      [R7]
"""
import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from dsf.utils.data_loader import (load_h5, load_h5_trajectory,
                                   find_geodetic, find_ecef)


def _write(path, builder):
    with h5py.File(path, "w") as f:
        builder(f)
    return str(path)


def test_root_time_and_full_vec3(tmp_path):
    def build(f):
        f.create_dataset("Time", data=np.array([0.0, 1.0, 2.0]))
        g = f.create_group("V1")
        g.create_dataset("Pos_x", data=np.array([1.0, 2.0, 3.0]))
        g.create_dataset("Pos_y", data=np.array([4.0, 5.0, 6.0]))
        g.create_dataset("Pos_z", data=np.array([7.0, 8.0, 9.0]))
    times, data = load_h5(_write(tmp_path / "a.h5", build))
    # Time comes from the root dataset, not arange.
    assert np.allclose(times, [0.0, 1.0, 2.0])
    # Full Vec3 is regrouped into (N,3).
    assert data["V1"]["Pos"].shape == (3, 3)
    assert np.allclose(data["V1"]["Pos"][:, 0], [1, 2, 3])


def test_partial_vec3_keeps_suffix(tmp_path):
    def build(f):
        f.create_dataset("Time", data=np.arange(3.0))
        g = f.create_group("V1")
        # Only the x component present → must stay "Speed_x", not "Speed_0".
        g.create_dataset("Speed_x", data=np.array([1.0, 2.0, 3.0]))
    _, data = load_h5(_write(tmp_path / "b.h5", build))
    assert "Speed_x" in data["V1"], f"expected 'Speed_x', got {list(data['V1'])}"
    assert "Speed_0" not in data["V1"]


def test_flat_legacy_format_regroups_vec3(tmp_path):
    """Flat (no groups) files land under the synthetic 'simulation' block and
    get the SAME Vec3 regrouping as hierarchical files — the two code paths
    used to be copy-pasted; now they share _regroup_vec3."""
    def build(f):
        f.create_dataset("Time", data=np.arange(3.0))
        f.create_dataset("Pos_x", data=np.array([1.0, 2.0, 3.0]))
        f.create_dataset("Pos_y", data=np.array([4.0, 5.0, 6.0]))
        f.create_dataset("Pos_z", data=np.array([7.0, 8.0, 9.0]))
        f.create_dataset("Speed_x", data=np.arange(3.0))   # partial → suffixed
        f.create_dataset("Mass", data=np.ones(3))          # scalar passthrough
    times, data = load_h5(_write(tmp_path / "flat.h5", build))
    assert list(data) == ["simulation"]
    blk = data["simulation"]
    assert blk["Pos"].shape == (3, 3)
    assert "Speed_x" in blk and "Speed_0" not in blk
    assert np.allclose(blk["Mass"], 1.0)
    assert np.allclose(times, [0, 1, 2])


def test_find_geodetic_aliases_and_fallback():
    N = 4
    data = {
        "V1": {  # canonical sixdof names, Earth-fixed lon present
            "Latitude": np.ones(N), "Earth Longitude": np.full(N, 2.0),
            "Longitude": np.full(N, 9.0),   # inertial — must NOT win
            "Altitude": np.full(N, 100.0),
            "XYZ": np.zeros((N, 3)),        # 2-D channels are ignored
        },
        "V2": {"lambda_d": np.ones(N), "Longitude": np.full(N, 3.0)},  # inertial fallback
        "V3": {"Mass": np.ones(N)},         # nothing geodetic → omitted
    }
    geo = find_geodetic(data)
    assert set(geo) == {"V1", "V2"}
    assert np.allclose(geo["V1"]["lon"], 2.0), "Earth-fixed lon preferred"
    assert np.allclose(geo["V1"]["lat"], 1.0)
    assert np.allclose(geo["V1"]["alt"], 100.0)
    assert np.allclose(geo["V2"]["lon"], 3.0), "inertial lon as fallback"


def test_find_geodetic_escaped_and_cased_names():
    # Some decks log "Earth\ Longitude"; matching is case-insensitive with
    # backslashes stripped (the old per-view tables drifted on exactly this).
    data = {"V": {"latitude": np.ones(2), "Earth\\ Longitude": np.ones(2)}}
    geo = find_geodetic(data)
    assert set(geo["V"]) == {"lat", "lon"}


def test_find_geodetic_normalizes_units(tmp_path):
    """Angle units vary by model (Equinoctial logs degrees, 6DOF radians) and
    the HDF5 `units` attribute says which. find_geodetic must normalize to
    radians — a blanket radians assumption put orbit decks at lat 3100°."""
    def build(f):
        f.create_dataset("Time", data=np.arange(2.0))
        g = f.create_group("Orbit")
        d = g.create_dataset("Latitude", data=np.array([54.0, 55.0]))  # degrees
        d.attrs["units"] = "deg"
        d = g.create_dataset("Earth Longitude", data=np.array([147.0, 148.0]))
        d.attrs["units"] = "deg"
        h = f.create_group("Aircraft")
        d = h.create_dataset("Latitude", data=np.array([0.6, 0.61]))   # radians
        d.attrs["units"] = "rad"
        h.create_dataset("lambda_d", data=np.array([0.5, 0.5]))        # no attr → rad
    _, data = load_h5(_write(tmp_path / "units.h5", build))
    assert data["Orbit"].units["Latitude"] == "deg"
    geo = find_geodetic(data)
    assert np.allclose(geo["Orbit"]["lat"], np.radians([54.0, 55.0]))
    assert np.allclose(geo["Orbit"]["lon"], np.radians([147.0, 148.0]))
    assert np.allclose(geo["Aircraft"]["lat"], [0.6, 0.61])  # untouched


def test_find_ecef_preference_and_eci_flag():
    N = 5
    ecef = np.ones((N, 3))
    eci = np.zeros((N, 3))
    data = {
        "A": {"XYZ_ECEF": ecef, "XYZ": eci},   # ECEF wins
        "B": {"xyz_e": ecef},
        "C": {"XYZ": eci},                     # ECI fallback, flagged
        "D": {"Mass": np.ones(N)},             # no position → omitted
    }
    out = find_ecef(data)
    assert out["A"][1] == "ecef" and np.allclose(out["A"][0], 1.0)
    assert out["B"][1] == "ecef"
    assert out["C"][1] == "eci"
    assert "D" not in out


def test_trajectory_probe_ignores_1d_dataset(tmp_path):
    # A file whose first dataset is 1-D (Time) plus a valid Nx3 later. Probing
    # shape[1] on the 1-D dataset used to raise IndexError and abort the load.
    def build(f):
        f.create_dataset("Time", data=np.arange(5.0))          # 1-D
        f.create_dataset("xyz", data=np.arange(15.0).reshape(5, 3))  # Nx3
    arr = load_h5_trajectory(_write(tmp_path / "c.h5", build), "does_not_exist")
    assert arr is not None, "should find the Nx3 dataset, not crash on Time"
    assert arr.shape == (5, 3)
