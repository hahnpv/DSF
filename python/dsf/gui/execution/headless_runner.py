"""
headless_runner.py
------------------
Subprocess entry point launched by the GUI's SimulationWorker.
Communicates via stdout JSON lines.

All simulation engine logic is now in dsf.utils.sim_session.SimSession.
This file is a thin protocol adapter: it drives SimSession and formats its
output as JSON for the parent process to consume.
"""

import sys
import os
import json
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../../"))
build_path = os.path.join(root_dir, "build")
sys.path.append(build_path)

sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)

try:
    import dsf
except ImportError:
    print(json.dumps({"error": "Failed to import dsf module"}))
    sys.exit(1)


def _emit(obj):
    print(json.dumps(obj))
    sys.stdout.flush()


def main():
    if len(sys.argv) < 5:
        _emit({"error": "Usage: headless_runner.py <xml_path> <lib_path> <dt> <tmax> [--init-only]"})
        sys.exit(1)

    xml_path = sys.argv[1]
    lib_path = sys.argv[2]
    dt       = float(sys.argv[3])
    tmax     = float(sys.argv[4])
    init_only = len(sys.argv) > 5 and sys.argv[5] == "--init-only"

    try:
        from dsf.utils.sim_session import SimSession
        session = SimSession(xml_path, lib_path, dt, tmax)
        session.build()
    except Exception as e:
        _emit({"error": str(e)})
        sys.exit(1)

    # Emit headers
    _emit({"headers": session.headers()})

    def report():
        state = session.collect_state()
        _emit({
            "time":     session.t(),
            "progress": (session.t() / tmax) * 100.0,
            "data":     session.current_values(),
            "deep_data": state,
        })

    # Initial state (used for GUI introspection probe)
    report()

    if init_only:
        return

    # Step loop — report at ~30 Hz wall-clock
    last_pt = time.time()
    while session.t() < tmax:
        session.step()
        pt = time.time()
        if pt - last_pt > 0.033:
            report()
            last_pt = pt

    report()  # Final state
    session.finalize()
    _emit({"finished": True, "message": "Simulation Complete"})


if __name__ == "__main__":
    main()
