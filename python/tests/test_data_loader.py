"""
Unit tests for dsf.utils.data_loader HDF5 handling.

Regression coverage:
  - root-level Time dataset is used (not fabricated as arange)          [Time bug]
  - partial Vec3 datasets keep their x/y/z suffix (not axis integers)   [M5]
  - a 1-D dataset (e.g. Time) does not crash Nx3 trajectory probing     [M13]
"""
import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from dsf.utils.data_loader import load_h5, load_h5_trajectory


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


def test_trajectory_probe_ignores_1d_dataset(tmp_path):
    # A file whose first dataset is 1-D (Time) plus a valid Nx3 later. Probing
    # shape[1] on the 1-D dataset used to raise IndexError and abort the load.
    def build(f):
        f.create_dataset("Time", data=np.arange(5.0))          # 1-D
        f.create_dataset("xyz", data=np.arange(15.0).reshape(5, 3))  # Nx3
    arr = load_h5_trajectory(_write(tmp_path / "c.h5", build), "does_not_exist")
    assert arr is not None, "should find the Nx3 dataset, not crash on Time"
    assert arr.shape == (5, 3)
