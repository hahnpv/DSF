import sys
import os
import ctypes
from PyQt6.QtCore import QThread, pyqtSignal

class SimulationWorker(QThread):
    progress = pyqtSignal(float)
    finished = pyqtSignal(str) # Summary message
    error = pyqtSignal(str)
    
    def __init__(self, xml_path, lib_path, dt, tmax):
        super().__init__()
        self.xml_path = xml_path
        self.lib_path = lib_path
        self.dt = dt
        self.tmax = tmax
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            # 1. Setup Environment
            # Ensure dsf is importable (using build dir relative to this file)
            # GUI/src/execution/simulation_worker.py -> Root -> build
            build_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../build"))
            if build_path not in sys.path:
                sys.path.append(build_path)

            # Need RTLD_GLOBAL for singletons
            sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
            import dsf

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
            
            clock = sim.clock
            self.current_clock = clock
            
            if not clock:
                self.error.emit("Simulation Engine: Failed to initialize Clock.")
                return

            # 5. Progress Poller (Separate thread to monitor clock)
            import threading
            import time as pytime
            
            def poll_progress():
                try:
                    while self._is_running and clock.t() < self.tmax:
                        prog = (clock.t() / self.tmax) * 100
                        self.progress.emit(prog)
                        pytime.sleep(0.5) # Poll every 500ms
                except Exception as e:
                    print(f"Poller Exception: {e}")
            
            poller = threading.Thread(target=poll_progress, daemon=True)
            poller.start()

            # 6. Blocking Run
            print(f"Starting Simulation: dt={self.dt}, tmax={self.tmax}")
            sim.run()
            
            # Final progress
            self.progress.emit(100.0)
            
            if not self._is_running:
                self.finished.emit("Simulation stopped by user.")
            else:
                self.finished.emit(f"Simulation complete. t={clock.t():.2f}s")

        except Exception as e:
            self.error.emit(f"Simulation Error: {e}")

    def stop(self):
        self._is_running = False
        if hasattr(self, 'current_clock'):
            self.current_clock.end()
