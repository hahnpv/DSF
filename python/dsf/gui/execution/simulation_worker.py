import sys
import os
import ctypes
import time as pytime
from PyQt6.QtCore import QThread, pyqtSignal

class SimulationWorker(QThread):
    progress = pyqtSignal(float)
    # Named sim_finished (not `finished`) so it does not shadow QThread's own
    # built-in finished() signal, which Qt relies on for thread cleanup.
    sim_finished = pyqtSignal(str) # Summary message
    error = pyqtSignal(str)
    deep_data_ready = pyqtSignal(float, dict) # Emits (time, structured introspection data)

    def __init__(self, xml_path, lib_path, dt, tmax, init_only=False):
        super().__init__()
        self.xml_path = xml_path
        self.lib_path = lib_path
        self.dt = dt
        self.tmax = tmax
        self.init_only = init_only
        self._is_running = True

    def run(self):
        import subprocess
        import json

        runner_script = os.path.join(os.path.dirname(__file__), "headless_runner.py")
        cmd = [
            sys.executable, 
            runner_script, 
            self.xml_path, 
            self.lib_path, 
            str(self.dt), 
            str(self.tmax)
        ]
        
        if self.init_only:
            cmd.append("--init-only")
        
        print(f"SimulationWorker: Launching {cmd}")
        
        try:
            # Start Subprocess (bufsize=1 for line buffering). stderr is merged
            # into stdout so a chatty model library cannot fill an undrained
            # stderr pipe and deadlock the child (which would freeze the sim).
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            proc = self.process   # local handle: stop() may null self.process

            while self._is_running:
                # Blocking read line
                line = proc.stdout.readline()
                if not line:
                    break # EOF

                line = line.strip()
                if not line: continue

                try:
                    msg = json.loads(line)

                    # A periodic report carries time+progress+data+deep_data in
                    # ONE message, so these are independent `if`s (not elif) and
                    # deep_data is emitted exactly once.
                    if "error" in msg:
                        self.error.emit(msg["error"])
                    elif "finished" in msg:
                        self.sim_finished.emit(msg.get("message", "Simulation Complete"))
                        self.progress.emit(100.0)
                        self._is_running = False
                    else:
                        if "progress" in msg:
                            self.progress.emit(msg["progress"])
                        if "deep_data" in msg:
                            self.deep_data_ready.emit(msg.get("time", 0.0), msg["deep_data"])

                except json.JSONDecodeError:
                    # Non-JSON line (merged stderr / C++ raw output)
                    print(f"[Sim Log] {line}")

            # Check exit code (stderr was merged into the stdout log above).
            rc = proc.poll()
            if rc not in (None, 0, -15): # -15 is SIGTERM (user Stop)
                self.error.emit(f"Simulation process exited with code {rc} "
                                f"(see [Sim Log] output above).")

        except Exception as e:
            self.error.emit(f"Worker Error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self.stop() # Ensure cleanup

    def stop(self):
        self._is_running = False
        if hasattr(self, 'process') and self.process:
            if self.process.poll() is None:
                print("SimulationWorker: Terminating subprocess...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=1.0)
                except:
                    self.process.kill()
            self.process = None
