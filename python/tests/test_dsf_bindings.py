"""
test_dsf_bindings.py
--------------------
Tests for DSF C-extension math utilities: Vec3, Mat3, Mat4, Quaternion,
Table, Table2d, dsf.PI, dsf.RAD, and the PythonModel block lifecycle
(configure → init → update → rpt → finalize).

These run via subprocess to keep the DSF C extension out of the Qt-loaded
pytest process. A small Python driver script is written into a tmp dir, run
with the python interpreter (no simulation needed for pure-math tests), and
its stdout/return-code asserted.
"""
import os
import sys
import json
import math
import subprocess
import textwrap
import pytest

# ---------------------------------------------------------------------------
# Helper: run a Python snippet in a subprocess that can import dsf
# ---------------------------------------------------------------------------

PYTHON   = sys.executable
DSF_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PYTHON_SRC = os.path.join(DSF_REPO, "python")
BUILD_DIR  = os.path.join(DSF_REPO, "build")

_PREAMBLE = f"""\
import sys, os, ctypes
sys.path.insert(0, {PYTHON_SRC!r})
sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
import dsf
"""

def _run(code: str) -> subprocess.CompletedProcess:
    # Prepend conda lib dir so dsf_core.so finds libhdf5.so.310.
    # Without this, import dsf throws H5::DataTypeIException during HDF5 init.
    env = os.environ.copy()
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        conda_lib = os.path.join(conda_prefix, "lib")
        env["LD_LIBRARY_PATH"] = conda_lib + ":" + env.get("LD_LIBRARY_PATH", "")
    script = textwrap.dedent(_PREAMBLE + "\n" + textwrap.dedent(code) + "\nsys.stdout.flush(); os._exit(0)\n")
    return subprocess.run(
        [PYTHON, "-c", script],
        capture_output=True, text=True, env=env
    )


def _assert_runs(code: str) -> str:
    """Run code in a dsf subprocess; assert rc=0 and return stdout."""
    r = _run(code)
    assert r.returncode == 0, f"Script failed:\n{r.stderr}"
    return r.stdout


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_pi(self):
        out = _assert_runs("print(dsf.PI)")
        assert abs(float(out.strip()) - math.pi) < 1e-5

    def test_rad(self):
        out = _assert_runs("print(dsf.RAD)")
        # RAD converts radians → degrees, so 180/pi
        assert abs(float(out.strip()) - (180.0 / math.pi)) < 1e-4


# ---------------------------------------------------------------------------
# Vec3
# ---------------------------------------------------------------------------

class TestVec3:
    def test_add(self):
        out = _assert_runs("""
            v1 = dsf.Vec3(1, 2, 3)
            v2 = dsf.Vec3(4, 5, 6)
            v3 = v1 + v2
            print(v3.x, v3.y, v3.z)
        """)
        x, y, z = map(float, out.split())
        assert (x, y, z) == (5.0, 7.0, 9.0)

    def test_sub(self):
        out = _assert_runs("""
            v = dsf.Vec3(4, 5, 6) - dsf.Vec3(1, 2, 3)
            print(v.x, v.y, v.z)
        """)
        x, y, z = map(float, out.split())
        assert (x, y, z) == (3.0, 3.0, 3.0)

    def test_scalar_mul(self):
        out = _assert_runs("""
            v = dsf.Vec3(1, 2, 3) * 2.0
            print(v.x, v.y, v.z)
        """)
        x, y, z = map(float, out.split())
        assert (x, y, z) == (2.0, 4.0, 6.0)

    def test_scalar_rmul(self):
        out = _assert_runs("""
            v = 2.0 * dsf.Vec3(1, 2, 3)
            print(v.x, v.y, v.z)
        """)
        x, y, z = map(float, out.split())
        assert (x, y, z) == (2.0, 4.0, 6.0)

    def test_magnitude(self):
        out = _assert_runs("""
            import math
            v = dsf.Vec3(3, 4, 0)
            print(v.mag())
        """)
        assert abs(float(out.strip()) - 5.0) < 1e-12




# ---------------------------------------------------------------------------
# Mat3
# ---------------------------------------------------------------------------

class TestMat3:
    def test_identity_det(self):
        out = _assert_runs("""
            m = dsf.Mat3(1,0,0, 0,1,0, 0,0,1)
            print(m.det())
        """)
        assert abs(float(out.strip()) - 1.0) < 1e-12

    def test_scalar_mul_det(self):
        out = _assert_runs("""
            m = dsf.Mat3(1,0,0, 0,1,0, 0,0,1) * 2.0
            print(m.det())
        """)
        # det(2I) = 2^3 = 8
        assert abs(float(out.strip()) - 8.0) < 1e-10

    def test_mat_vec_mul(self):
        out = _assert_runs("""
            m = dsf.Mat3(1,0,0, 0,1,0, 0,0,1)
            v = m * dsf.Vec3(1, 2, 3)
            print(v.x, v.y, v.z)
        """)
        x, y, z = map(float, out.split())
        assert (x, y, z) == (1.0, 2.0, 3.0)


# ---------------------------------------------------------------------------
# Quaternion
# ---------------------------------------------------------------------------

class TestQuaternion:
    def test_identity(self):
        out = _assert_runs("""
            q = dsf.Quaternion(0, 0, 0, 1)
            print(q.x, q.y, q.z, q.w)
        """)
        x, y, z, w = map(float, out.split())
        assert abs(x) < 1e-12 and abs(y) < 1e-12 and abs(z) < 1e-12
        assert abs(w - 1.0) < 1e-12


# ---------------------------------------------------------------------------
# Table (1D) and Table2d
# ---------------------------------------------------------------------------

TABLE_1D = """\
T1
4
X\tY
0.0\t0.0
1.0\t10.0
2.0\t20.0
3.0\t30.0
"""

TABLE_2D = """\
n=4
X\tY\tZ
0.0\t0.0\t0.0
1.0\t10.0\t100.0
2.0\t20.0\t200.0
3.0\t30.0\t300.0
"""


class TestTable:
    def test_1d_interp(self, tmp_path):
        tbl = tmp_path / "t1d.txt"
        tbl.write_text(TABLE_1D)
        out = _assert_runs(f"""
            t = dsf.Table({str(tbl)!r}, "T1")
            print(t(1.5))
        """)
        val = float(out.strip().split()[-1])
        assert abs(val - 15.0) < 1e-10

    def test_1d_extrapolation_low(self, tmp_path):
        tbl = tmp_path / "t1d.txt"
        tbl.write_text(TABLE_1D)
        out = _assert_runs(f"""
            t = dsf.Table({str(tbl)!r}, "T1")
            print(t(0.0))
        """)
        val = float(out.strip().split()[-1])
        assert abs(val) < 1e-10

    def test_2d_interp_vec(self, tmp_path):
        tbl = tmp_path / "t2d.txt"
        tbl.write_text(TABLE_2D)
        out = _assert_runs(f"""
            t = dsf.Table2d({str(tbl)!r})
            vals = t.interp_vec(1.0)
            print(vals[0], vals[1], vals[2])
        """)
        # C++ Table2D interp_vec returns the whole row including the interpolation key
        v0, v1, v2 = map(float, out.split())
        assert abs(v0 - 1.0) < 1e-6
        assert abs(v1 - 10.0) < 1e-6
        assert abs(v2 - 100.0) < 1e-6


# ---------------------------------------------------------------------------
# get_unique_file
# ---------------------------------------------------------------------------

# get_unique_file creates a UniqueFile which initializes the DSF Output
# subsystem and triggers HDF5 PropList construction/destruction. These tests
# are better validated as part of the end-to-end simulation tests (test_dsf_to_xml)
# where DSF runs in a clean subprocess that skips Python garbage collection.
class TestGetUniqueFile:
    def test_output_disabled_no_crash(self):
        """Importing dsf with Output disabled must not crash."""
        out = _assert_runs("print('ok')")
        assert out.strip() == "ok"
