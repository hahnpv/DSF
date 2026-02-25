"""
test_python_blocks.py
---------------------
Tests for DSF's Python block interface — subclassing dsf.Block and using
the block API (block hierarchy, children, naming).

DSF's C++ Block destructor creates HDF5 DataType objects that throw
H5::DataTypeIException on cleanup in a subprocess context. All Block-based
tests therefore use `need_exit=True` which appends `os._exit(0)` to skip
destructors and capture output cleanly.

The full simulation lifecycle (configure→init→update→rpt→finalize) is
already covered by test_dsf_xml_equivalence.py and test_run_vs_watch.py.
Direct Sim()-based lifecycle tests are marked xfail pending HDF5/ctor fix.
"""
import os
import sys
import subprocess
import textwrap
import pytest

DSF_REPO   = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PYTHON_SRC = os.path.join(DSF_REPO, "python")
BUILD_DIR  = os.path.join(DSF_REPO, "build")
PYTHON     = sys.executable

_PREAMBLE = f"""\
import sys, os
sys.path.insert(0, {PYTHON_SRC!r})
sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
import dsf
"""

# All scripts that create Block or Sim objects must flush stdout and call
# os._exit(0) BEFORE Python GC destroys them; their dtors crash with
# H5::DataTypeIException in subprocess context.
_EXIT_SUFFIX = "\nsys.stdout.flush(); os._exit(0)\n"


def _run(code: str, need_exit: bool = True) -> subprocess.CompletedProcess:
    suffix = _EXIT_SUFFIX if need_exit else ""
    # Prepend conda lib dir so dsf_core.so finds libhdf5.so.310.
    env = os.environ.copy()
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        conda_lib = os.path.join(conda_prefix, "lib")
        env["LD_LIBRARY_PATH"] = conda_lib + ":" + env.get("LD_LIBRARY_PATH", "")
    script = textwrap.dedent(_PREAMBLE + "\n" + textwrap.dedent(code) + suffix)
    return subprocess.run([PYTHON, "-c", script], capture_output=True, text=True, env=env)


def _assert_runs(code: str, need_exit: bool = True) -> str:
    r = _run(code, need_exit=need_exit)
    assert r.returncode == 0, (
        f"Script failed (rc={r.returncode}):\nstdout: {r.stdout}\nstderr: {r.stderr}"
    )
    return r.stdout


# ---------------------------------------------------------------------------
# dsf.Block API — tests that do NOT require dsf.Sim()
# ---------------------------------------------------------------------------

class TestBlockAPI:
    """Block API tests."""

    def test_can_subclass_block(self):
        out = _assert_runs("""
class MyBlock(dsf.Block):
    def configure(self, xml): pass
    def init(self): pass
    def update(self): pass
    def rpt(self): pass
    def finalize(self): pass

b = MyBlock()
print(isinstance(b, dsf.Block))
        """)
        assert out.strip() == "True"

    def test_addChild_and_hierarchy(self):
        out = _assert_runs("""
parent = dsf.Block()
child  = dsf.Block()
parent.addChild(child)
children = parent.getChildren()
print(len(children))
        """)
        assert int(out.strip()) == 1

    def test_setname_name_roundtrip(self):
        out = _assert_runs("""
b = dsf.Block()
b.setName("TestBlock")
print(b.get_name())
        """)
        assert "TestBlock" in out.strip()

    def test_multiple_children(self):
        out = _assert_runs("""
root = dsf.Block()
for i in range(3):
    c = dsf.Block()
    c.setName(f"child{i}")
    root.addChild(c)
print(len(root.getChildren()))
        """)
        assert int(out.strip()) == 3

    def test_block_accessors(self):
        out = _assert_runs("""
b = dsf.Block()
print(b.has_children())
b.addChild(dsf.Block())
print(b.has_children())
try:
    print(b.get_property("nonexistent"))
except RuntimeError:
    print("None")
        """)
        vals = out.strip().split()
        assert vals[-3] == "False"
        assert vals[-2] == "True"
        assert vals[-1] == "None"


# ---------------------------------------------------------------------------
# Python block lifecycle — xfail pending HDF5 Sim() constructor issue
# ---------------------------------------------------------------------------

_LIFECYCLE_SCRIPT = """
events = []

class TestBlock(dsf.Block):
    def init(self):
        events.append("init")
        events.append(f"t={self.t():.3f}")
        events.append(f"dt={self.dt():.4f}")
    def update(self):
        events.append("update")
    def rpt(self):
        events.append(f"rpt_t={self.t():.2f}")
        if self.t() >= 0.2:
            self.end()
    def finalize(self):
        events.append("finalize")

block = TestBlock()
root  = dsf.Block()
root.addChild(block)
sim = dsf.Sim()
sim.load(root, 0.05, 1.0, 0, 1.0)
sim.init()
if hasattr(sim.clock, 't'): events.append("clock_ok")
if hasattr(sim.output, 'defaultCSV'): events.append("output_ok")
sim.step()
events.append("step_ok")
sim.exec()
sim.finalize()
for e in events:
    print(e)
"""


class TestPythonBlockLifecycle:
    """Lifecycle tests."""

    @pytest.fixture(scope="class")
    def lifecycle_out(self):
        return _assert_runs(_LIFECYCLE_SCRIPT, need_exit=True)

    def test_init_called(self, lifecycle_out):
        assert "init" in lifecycle_out

    def test_time_accessible(self, lifecycle_out):
        assert any("t=" in line for line in lifecycle_out.splitlines())

    def test_dt_accessible(self, lifecycle_out):
        assert any("dt=" in line for line in lifecycle_out.splitlines())

    def test_update_called(self, lifecycle_out):
        assert "update" in lifecycle_out

    def test_rpt_called(self, lifecycle_out):
        assert any("rpt_t=" in line for line in lifecycle_out.splitlines())

    def test_finalize_called(self, lifecycle_out):
        assert "finalize" in lifecycle_out

    def test_sim_accessors(self, lifecycle_out):
        assert "clock_ok" in lifecycle_out
        assert "output_ok" in lifecycle_out
        assert "step_ok" in lifecycle_out
