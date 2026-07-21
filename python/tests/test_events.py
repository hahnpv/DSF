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
import re
import glob
import subprocess
import textwrap

import numpy as np
import pytest

from tests.conftest import require_sixdof, GPS_6MIN_DSF, BUILD_DIR, PYTHON_SRC


def _event_deck(tmp_path, value="5.0"):
    """Convert the gps deck (tmax=360) to XML and inject a terminate event."""
    import sys
    sys.path.insert(0, PYTHON_SRC)
    from dsf.utils.convert_dsf_to_xml import convert_dsf_to_xml
    xml = convert_dsf_to_xml(GPS_6MIN_DSF)
    txt = open(xml).read().replace(
        "</sim>",
        f'  <events>\n    <event name="stop" type="time_ge" value="{value}" '
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


# ── Fire-time accuracy (code verification of event localization) ─────────────
#
# The EventBus interpolates the crossing within the step and reports it as
# fire_time ("[Event] t=... 'name'"). The interpolation math itself is
# verified against an analytic crossing in test/test_integrators.cpp; these
# two tests verify the same contract through the full run path (deck ->
# register_events -> Sim loop -> stdout).


def test_time_event_fires_at_interpolated_threshold(tmp_path):
    """A TIME_GE threshold between ticks (5.03 s, dt=0.1) must report the
    threshold itself as the fire time, not the enclosing step boundary."""
    require_sixdof()
    deck = _event_deck(tmp_path, value="5.03")
    d = str(tmp_path / "run")
    os.makedirs(d, exist_ok=True)
    r = subprocess.run(["dsf", "run", deck, "--h5"], cwd=d,
                       capture_output=True, text=True, env=_env())
    m = re.search(r"\[Event\] t=([0-9.eE+-]+) 'stop'", r.stdout)
    assert m, f"no fire-time line in stdout: {r.stdout[-500:]}"
    assert abs(float(m.group(1)) - 5.03) < 1e-6, \
        f"fire time {m.group(1)} != interpolated threshold 5.03"


def test_crossing_event_fire_time_matches_trajectory(tmp_path):
    """Full-stack crossing verification: a rising event on the Equinoctial
    true anomaly must fire where the logged trajectory actually crosses the
    threshold. A probe run (no event, 1 Hz output) supplies the trajectory;
    the threshold is picked mid-run and the expected crossing time comes from
    interpolating the probe series. Verifies variable binding
    (Output::find_variable), crossing detection, and sub-step interpolation
    against the trajectory itself — no analytic model needed."""
    require_sixdof()
    import sys
    import h5py
    sys.path.insert(0, PYTHON_SRC)
    from dsf.utils.convert_dsf_to_xml import convert_dsf_to_xml

    xml = convert_dsf_to_xml(GPS_6MIN_DSF)
    base = open(xml).read().replace('<sim ', '<sim file="1.0" ', 1)

    def run(txt, name):
        d = str(tmp_path / name)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "deck.xml"), "w").write(txt)
        r = subprocess.run(["dsf", "run", "deck.xml", "--h5"], cwd=d,
                           capture_output=True, text=True, env=_env())
        assert r.returncode == 0, r.stdout[-800:] + r.stderr[-400:]
        h5 = glob.glob(os.path.join(d, "*.h5"))
        assert h5, f"no h5 produced: {r.stdout[-500:]}"
        return r, h5[0]

    _, h5 = run(base, "probe")
    with h5py.File(h5, "r") as f:
        t = np.array(f["Time"])
        keys = []
        f.visit(keys.append)  # datasets sit under a per-vehicle group
        key = [k for k in keys if "tanom" in k.rsplit("/", 1)[-1]][0]
        nu = np.array(f[key])

    # Threshold mid-run, off the sample grid; expected crossing interpolated
    # from a local window (true anomaly is monotonic there).
    thr = float(np.interp(180.3, t, nu))
    i, j = int(np.searchsorted(t, 175.0)), int(np.searchsorted(t, 186.0))
    expected = float(np.interp(thr, nu[i:j], t[i:j]))

    ev = base.replace(
        "</sim>",
        f'  <events>\n    <event name="nu_cross" type="rising" '
        f'variable="tanom" value="{thr!r}" action="sim.terminate" />\n'
        f'  </events>\n</sim>')
    r, h5e = run(ev, "event")
    m = re.search(r"\[Event\] t=([0-9.eE+-]+) 'nu_cross'", r.stdout)
    assert m, f"crossing event did not fire: {r.stdout[-800:]}"
    fire = float(m.group(1))

    # Error budget: probe-series interpolation (<<1 ms — tiny curvature) +
    # stdout print precision (~1e-3 s at t~180). 0.05 s is far below the
    # 1 s output cadence and the 0.1 s step, so a step-quantized or
    # mis-bound fire time fails clearly.
    assert abs(fire - expected) < 0.05, (fire, expected)

    # And the terminate action ended the run at that step.
    with h5py.File(h5e, "r") as f:
        assert np.array(f["Time"])[-1] < expected + 1.0
