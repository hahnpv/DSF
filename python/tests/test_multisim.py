"""
Two SimSessions interleaved in ONE process — the GUI / MCP-session host
shape (R1: Sim-owned registries; see R1_SINGLETONS.md).

Before R1, SimSession B's build wiped sim A's integrand registry (the
global clear-on-load), so interleaved stepping froze or corrupted A. The
sims run in a SUBPROCESS per the conftest design (keeps the C extension
out of the pytest process); the parent only checks the printed verdict.
"""

import os
import subprocess
import sys

import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SIXDOF_BUILD = os.path.abspath(os.path.join(REPO_ROOT, "..", "sixdof", "build"))

SCRIPT = r"""
import sys
from dsf.utils.sim_session import SimSession

DECK, LIB = sys.argv[1], sys.argv[2]
N = 20

def build():
    s = SimSession(DECK, LIB, dt=0.1, tmax=86400.0, file_rate=1e9)
    s.build()
    return s

# Solo baselines
a = build()
for _ in range(N):
    a.step()
solo_a = list(a.current_values())

b = build()
for _ in range(2 * N):
    b.step()
solo_b = list(b.current_values())

# Interleaved: B steps twice per A step; neither may perturb the other.
a2, b2 = build(), build()
for _ in range(N):
    a2.step()
    b2.step()
    b2.step()

assert list(a2.current_values()) == solo_a, "interleaved A diverged from solo A"
assert list(b2.current_values()) == solo_b, "interleaved B diverged from solo B"
assert a2.t() != b2.t(), "sims advanced by different amounts"
print("MULTISIM_OK")
"""


def test_two_sim_sessions_interleaved(tmp_path):
    if not os.path.exists(os.path.join(SIXDOF_BUILD, "libsixdof.so")):
        pytest.skip("sixdof model library (../sixdof/build/libsixdof.so) not built")
    deck = os.path.join(FIXTURES_DIR, "gps_1.xml")

    env = os.environ.copy()
    build_dir = os.path.join(REPO_ROOT, "build")
    env["LD_LIBRARY_PATH"] = f"{build_dir}:{SIXDOF_BUILD}:{env.get('LD_LIBRARY_PATH', '')}"

    r = subprocess.run(
        [sys.executable, "-c", SCRIPT, deck, "libsixdof.so"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=300,
    )
    assert r.returncode == 0, f"subprocess failed:\n{r.stdout}\n{r.stderr}"
    assert "MULTISIM_OK" in r.stdout
