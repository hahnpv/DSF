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
    
    def __init__(self, xml_path, lib_path, dt, tmax, init_only=False):
        super().__init__()
        self.xml_path = xml_path
        self.lib_path = lib_path
        self.dt = dt
        self.tmax = tmax
        self.init_only = init_only
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            # 1. Setup Environment
            # Ensure dsf is importable (using build dir relative to this file)
            # GUI/src/execution/simulation_worker.py -> Root -> build
            build_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../build"))
            # Add build directory to path for dsf module
            sys.path.append(build_path)
            # RTLD_GLOBAL required for C++ casting (dynamic_cast) to work across boundaries
            sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
            
            import dsf
            print(f"DEBUG: Loaded dsf module from: {dsf.__file__}", file=sys.stderr)
            print(f"DEBUG: dsf.Sim dir: {dir(dsf.Sim)}", file=sys.stderr)

            # 2. Load Shared Library
            try:
                ctypes.CDLL(self.lib_path, mode=os.RTLD_GLOBAL | os.RTLD_NOW)
            except OSError as e:
                self.error.emit(f"Failed to load library {self.lib_path}: {e}")
                return

            # 3. Setup Simulation
            xml_input = dsf.xml(self.xml_path)
            xml_input.parse()
            sim_node = xml_input.xmlRoot.search("sim")
            
            sim_root = dsf.Block()
            all_blocks_to_config = []
            
            for child in sim_node.children():
                child_id = child.attrAsString("id")
                child_class = child.attrAsString("class")
                if not child_id:
                    continue
                    
                # Root level blocks: use class attribute or capitalize the tag
                class_to_use = child_class or child.tag().capitalize()
                
                print(f"Creating root block: {child_id} [class={class_to_use}]")
                new_block = dsf.make_block(class_to_use)
                if new_block:
                    if hasattr(new_block, "instance_id"):
                        new_block.instance_id = child_id
                    sim_root.addChild(new_block)
                    all_blocks_to_config.append((new_block, child))
                else:
                    print(f"Warning: Factory returned None for class '{class_to_use}' (id={child_id})")
            
            # Second pass: Configure top-level blocks
            for block, node in all_blocks_to_config:
                print(f"Configuring root block: {node.attrAsString('id')}")
                block.configure(node)

            sim = dsf.Sim()
            # console=0, file=1.0 (reporting rates)
            sim.load(sim_root, self.dt, self.tmax, 0, 1.0)
            
            # 4. Initialize Simulation (Registers Variables)
            # Use new init/exec API if available (fallback to run)
            if hasattr(sim, 'init') and hasattr(sim, 'exec'):
                print("Using new init/exec API")
                sim.init()
                
                # Fetch Headers Immediately
                if hasattr(sim, 'output'):
                    headers = sim.output.get_header_names()
                    if headers:
                        print(f"SimulationWorker: Found {len(headers)} headers (Early Init).")
                        sys.stdout.flush()
                        self.headers_ready.emit(headers)
                        # Give main thread a brief moment to process headers before slamming CPU
                        pytime.sleep(0.1) 
                
                if self.init_only:
                    print("SimulationWorker: init_only is True. Exiting after fetching headers.")
                    # Explicitly cleanup to avoid double-free during GC of sim/root
                    del sim
                    del sim_root
                    return

                # 5. Progress Poller (Now safe to start)
                import threading
                
                self.poller_finished = threading.Event()
                
                def poll_progress():
                    try:
                        while self._is_running:
                            # Check completion first
                            if sim.clock and sim.clock.t() >= self.tmax:
                                break
                                
                            # Progress
                            if sim.clock: 
                                prog = (sim.clock.t() / self.tmax) * 100
                                self.progress.emit(prog)
                                
                                if hasattr(sim, 'output'):
                                    vals = sim.output.get_current_values()
                                    if vals:
                                        self.data_ready.emit(vals)
                            
                            pytime.sleep(0.033) # 30Hz poll
                    except Exception as e:
                        print(f"Poller Exception: {e}")
                    finally:
                        self.poller_finished.set()
                
                poller = threading.Thread(target=poll_progress, daemon=True)
                poller.start()

                # 6. Blocking Run (Native Speed)
                print(f"Starting Simulation Loop: dt={self.dt}, tmax={self.tmax}")
                sim.exec()
                
                # 7. Cleanup
                # Signal thread to stop
                self._is_running = False
                
                # Wait for thread to finish BEFORE returning and destroying 'sim'
                # This prevents the race condition where thread accesses 'clock/sim' after destruction
                print("Waiting for poller to finish...")
                self.poller_finished.wait(timeout=1.0)
                print("Poller finished.")
                
            else:
                # Legacy path (should not happen after re-compile)
                print("Using legacy run API")
                if self.init_only:
                     print("SimulationWorker: init_only not supported on legacy API. Returning.")
                     return
                # ... would need original logic ...
                sim.run()
            
            # Final progress
            self.progress_bar_val = 100.0
            self.progress.emit(100.0)
            
            if not self._is_running: # If stopped manually
                self.finished.emit("Simulation stopped by user.")
            else:
                final_t = sim.clock.t() if sim.clock else self.tmax
                self.finished.emit(f"Simulation complete. t={final_t:.2f}s")

        except Exception as e:
            self.error.emit(f"Simulation Error: {e}")
            import traceback
            traceback.print_exc()

    def stop(self):
        self._is_running = False
        if hasattr(self, 'current_clock'):
            self.current_clock.end()
