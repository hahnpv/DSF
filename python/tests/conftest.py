"""
Shared pytest fixtures for the DSF test suite.

Simulations run in subprocesses via `dsf run --h5`. This keeps DSF's C
extension (and its loaded libs) out of the main pytest process, which has
Qt loaded from pytest-qt. The main process reads .h5 files with h5py only.
"""
import os
import sys
import glob
import subprocess
import tempfile
import shutil
import pytest

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT    = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PYTHON_SRC   = os.path.join(REPO_ROOT, "python")
BUILD_DIR    = os.path.join(REPO_ROOT, "build")

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GPS_XML      = os.path.join(FIXTURES_DIR, "gps_1.xml")
GPS_DSF      = os.path.join(FIXTURES_DIR, "gps_1.dsf")
GPS_1HR_XML  = os.path.join(FIXTURES_DIR, "gps_1hr.xml")   # tmax=3600
GPS_1HR_DSF  = os.path.join(FIXTURES_DIR, "gps_1hr.dsf")   # tmax=3600, for dsf watch
GPS_6MIN_DSF = os.path.join(FIXTURES_DIR, "gps_6min.dsf")  # tmax=360,  fast run-vs-watch

if PYTHON_SRC not in sys.path:
    sys.path.insert(0, PYTHON_SRC)
if BUILD_DIR not in sys.path:
    sys.path.insert(0, BUILD_DIR)


# ── Subprocess runner ──────────────────────────────────────────────────────────

def run_sim(input_path: str, work_dir: str) -> str:
    """
    Run `dsf run <input_path> --h5` in a clean subprocess inside `work_dir`.
    Returns the path to the generated .h5 file.

    Subprocess isolation keeps DSF's C extension out of the main pytest
    process (which has Qt/VTK loaded via pytest-qt).
    """
    before = set(glob.glob(os.path.join(work_dir, "*.h5")))

    result = subprocess.run(
        ["dsf", "run", input_path, "--h5"],
        cwd=work_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"dsf run failed (rc={result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    after = set(glob.glob(os.path.join(work_dir, "*.h5")))
    new   = after - before
    if not new:
        raise FileNotFoundError(
            f"dsf run produced no .h5 file in {work_dir}.\n"
            f"stdout: {result.stdout}"
        )
    return max(new, key=os.path.getmtime)


def load(h5_path: str):
    """Load an HDF5 file with h5py (in-process, no DSF)."""
    from dsf.utils.data_loader import load_h5
    return load_h5(h5_path)


# ── Session-scoped fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def xml_h5(tmp_path_factory):
    """Run gps_1hr.xml (tmax=3600) via subprocess → (times, data)."""
    d = str(tmp_path_factory.mktemp("xml_run"))
    return load(run_sim(GPS_1HR_XML, d))


@pytest.fixture(scope="session")
def dsf_h5(tmp_path_factory):
    """Run gps_1hr.dsf (tmax=3600) via subprocess → (times, data)."""
    d = str(tmp_path_factory.mktemp("dsf_run"))
    return load(run_sim(GPS_1HR_DSF, d))


@pytest.fixture(scope="session")
def exec_h5(tmp_path_factory):
    """Run gps_6min.dsf via 'dsf run' subprocess → (times, data)."""
    d = str(tmp_path_factory.mktemp("exec_run"))
    return load(run_sim(GPS_6MIN_DSF, d))


@pytest.fixture(scope="session")
def watch_h5(tmp_path_factory):
    """Run gps_6min.dsf via 'dsf watch --h5' subprocess → (times, data)."""
    d = str(tmp_path_factory.mktemp("watch_run"))
    before = set(glob.glob(os.path.join(d, "*.h5")))

    result = subprocess.run(
        ["dsf", "watch", GPS_6MIN_DSF, "--h5"],
        cwd=d,
        capture_output=True,
        text=True,
    )

    after = set(glob.glob(os.path.join(d, "*.h5")))
    new   = after - before

    if not new:
        raise FileNotFoundError(
            f"dsf watch produced no .h5 file.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return load(max(new, key=os.path.getmtime))
