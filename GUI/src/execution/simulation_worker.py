import sys
import os
import ctypes
import time as pytime
from PyQt6.QtCore import QThread, pyqtSignal

class SimulationWorker(QThread):
    progress = pyqtSignal(float)
    finished = pyqtSignal(str) # Summary message
    error = pyqtSignal(str)
    headers_ready = pyqtSignal(list) # Emits list of variable names
    data_ready = pyqtSignal(list)    # Emits list of float values
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
            # Start Subprocess (bufsize=1 for line buffering)
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                bufsize=1
            )
            
            while self._is_running:
                # Blocking read line
                line = self.process.stdout.readline()
                if not line:
                    break # EOF
                    
                line = line.strip()
                if not line: continue
                
                try:
                    msg = json.loads(line)
                    
                    if "headers" in msg:
                        self.headers_ready.emit(msg["headers"])
                    if "headers" in msg:
                        self.headers_ready.emit(msg["headers"])
                        # Don't stop here if init_only, wait for state report which follows
                            
                            
                    elif "data" in msg:
                        self.data_ready.emit(msg["data"])
                        if "deep_data" in msg:
                            t = msg.get("time", 0.0)
                            self.deep_data_ready.emit(t, msg["deep_data"])
                        
                    elif "progress" in msg:
                        self.progress.emit(msg["progress"])
                        
                    elif "finished" in msg:
                        self.finished.emit(msg["message"])
                        self.progress.emit(100.0)
                        self._is_running = False
                        
                    elif "error" in msg:
                        self.error.emit(msg["error"])
                        
                except json.JSONDecodeError:
                    # Log C++ raw output
                    print(f"[Sim Log] {line}")
            
            # Check exit code
            self.process.poll()
            if self.process.returncode not in (None, 0, -15): # -15 is SIGTERM
                stderr_out = self.process.stderr.read()
                if stderr_out:
                    self.error.emit(f"Process Failed: {stderr_out}")

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
