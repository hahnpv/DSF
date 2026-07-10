"""
Event handling through the shared builder (H5 Phase 2).

Both run paths now register <events> from the XML <sim> node via the shared
SimSession builder and honor a sim.terminate action:
  * `dsf run`      — the C++ exec loop (checks clock.is_running()).
  * the step loop  — SimSession + running() (dsf watch / GUI / MCP).

Sims run in subprocesses (conftest pattern) to keep the C extension out of the
pytest process. Requires the sixdof model library.
"""
import os
import glob
import subprocess
import textwrap

import numpy as np
import pytest

from tests.conftest import require_sixdof, GPS_6MIN_DSF, BUILD_DIR, PYTHON_SRC


def _event_deck(tmp_path):
    """Convert the gps deck (tmax=360) to XML and inject a terminate-at-t=5 event."""
    import sys
    sys.path.insert(0, PYTHON_SRC)
    from dsf.utils.convert_dsf_to_xml import convert_dsf_to_xml
    xml = convert_dsf_to_xml(GPS_6MIN_DSF)
    txt = open(xml).read().replace(
        "</sim>",
        '  <events>\n    <event name="stop" type="time_ge" value="5.0" '
        'action="sim.terminate" />\n  </events>\n</sim>')
    deck = str(tmp_path / "deck_ev.xml")
    open(deck, "w").write(txt)
    return deck


def _env():
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{BUILD_DIR}:{env.get('LD_LIBRARY_PATH', '')}"
    return env


def test_dsf_run_honors_terminate_event(tmp_path):
    """C++ exec loop: a sim.terminate event ends the run well before tmax=360."""
    require_sixdof()
    deck = _event_deck(tmp_path)
    d = str(tmp_path / "run")
    os.makedirs(d, exist_ok=True)
    r = subprocess.run(["dsf", "run", deck, "--h5"], cwd=d,
                       capture_output=True, text=True, env=_env())
    assert "[Event] Terminating simulation" in r.stdout, r.stdout[-500:]
    h5 = glob.glob(os.path.join(d, "*.h5"))
    assert h5, f"no h5 produced. stdout: {r.stdout[-500:]}"
    import h5py
    t = np.array(h5py.File(h5[0], "r")["Time"])
    assert t[-1] < 20.0, f"event should stop the run near t=5, got t={t[-1]}"


def test_step_loop_honors_terminate_event(tmp_path):
    """SimSession step loop (watch/GUI/MCP path): running() goes False on the
    event, so the loop ends early. Driven in a subprocess like the CLI paths."""
    require_sixdof()
    deck = _event_deck(tmp_path)
    # Resolve the sixdof library path for SimSession's dlopen.
    lib = None
    for c in (os.path.join(BUILD_DIR, "..", "..", "sixdof", "build", "libsixdof.so"),
              "libsixdof.so"):
        if os.path.exists(c):
            lib = os.path.abspath(c)
            break
    lib = lib or "libsixdof.so"

    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {PYTHON_SRC!r})
        from dsf.utils.sim_session import SimSession
        s = SimSession({deck!r}, {lib!r}, 0.1, 360.0)
        s.build()
        while s.t() < 360.0 and s.running():
            s.step()
        s.finalize()
        print("FINAL_T", s.t())
    """)
    r = subprocess.run(["python", "-c", script],
                       capture_output=True, text=True, env=_env())
    assert "FINAL_T" in r.stdout, f"stdout: {r.stdout[-500:]}\nstderr: {r.stderr[-500:]}"
    final_t = float(r.stdout.split("FINAL_T")[1].split()[0])
    assert final_t < 20.0, f"step loop should stop near t=5 on the event, got t={final_t}"
