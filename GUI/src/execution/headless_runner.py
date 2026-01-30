
import sys
import os
import ctypes
import time
import json
import threading

# Add build paths
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

def main():
    if len(sys.argv) < 5:
        print(json.dumps({"error": "Usage: headless_runner.py <xml_path> <lib_path> <dt> <tmax>"}))
        sys.exit(1)

    xml_path = sys.argv[1]
    lib_path = sys.argv[2]
    dt = float(sys.argv[3])
    tmax = float(sys.argv[4])
    
    init_only = False
    if len(sys.argv) > 5 and sys.argv[5] == "--init-only":
        init_only = True

    try:
        # Load Library
        ctypes.CDLL(lib_path, mode=os.RTLD_GLOBAL | os.RTLD_NOW)
        
        # Setup Simulation
        # We need the same logic as SimulationWorker to handle <state> etc using the fixed XMLParser? 
        # Actually, XMLParser logic happens in GUI before saving the temporary XML.
        # So we can just trust the XML passed to us (dsf_runtime.xml).
        # We use dsf.xml() directly which uses C++ parser?
        # NO. standard dsf.xml/parse uses C++ parser.
        # The GUI fix was in how it generated the XML.
        # Now that we fixed the GUI generation, the XML file `dsf_runtime.xml` is correct.
        # The C++ parser reads it fine.
        # Wait, the C++ parser is `dsf.xml`. Does it use `id="Vehicle"`? Yes.
        # Does `dsf` bindings support `sim.load(sim_root)`? Yes.
        
        # We need to construct the block tree exactly as SimulationWorker did.
        # SimulationWorker Python code:
        xml_input = dsf.xml(xml_path)
        xml_input.parse()
        sim_node = xml_input.xmlRoot.search("sim")
        
        sim_root = dsf.Block()
        all_blocks_to_config = []
        
        for child in sim_node.children():
            child_id = child.attrAsString("id")
            child_class = child.attrAsString("class")
            if not child_id: continue
            
            raw_tag = child.name()
            # If class attr exists, use it. Otherwise, use tag with first char uppercased.
            # Avoid capitalize() because it lowercases the rest (BouncyBall -> Bouncyball).
            if child_class:
                class_to_use = child_class
            else:
                class_to_use = raw_tag[0].upper() + raw_tag[1:] if raw_tag else ""
                
            new_block = dsf.make_block(class_to_use)
            if new_block:
                # Handle instance_id
                if hasattr(new_block, "instance_id"):
                    new_block.instance_id = child_id
                sim_root.addChild(new_block)
                all_blocks_to_config.append((new_block, child))
        
        for block, node in all_blocks_to_config:
            block.configure(node)

        sim = dsf.Sim()
        sim.load(sim_root, dt, tmax, 0, 1.0)
        
        if hasattr(sim, 'init') and hasattr(sim, 'exec'):
            sim.init()
            
            # Emit Headers
            if hasattr(sim, 'output'):
                headers = sim.output.get_header_names()
                print(json.dumps({"headers": headers}))
                sys.stdout.flush()
            
            if init_only:
                return

            # Start Poller Thread
            stop_event = threading.Event()
            
            def poller():
                last_t = -1.0
                while not stop_event.is_set():
                    if sim.clock:
                        t = sim.clock.t()
                        if t >= tmax:
                            break
                        
                        # Throttle updates (30Hz)
                        if t > last_t:
                            vals = sim.output.get_current_values()
                            # Send progress and data
                            msg = {
                                "progress": (t / tmax) * 100.0,
                                "data": vals
                            }
                            print(json.dumps(msg))
                            sys.stdout.flush()
                            last_t = t
                    time.sleep(0.033)
            
            t = threading.Thread(target=poller, daemon=True)
            t.start()
            
            # Blocking Run
            sim.exec()
            
            stop_event.set()
            t.join(timeout=1.0)
            
            print(json.dumps({"finished": True, "message": "Simulation Complete"}))
        else:
            print(json.dumps({"error": "Legacy API not supported in headless mode"}))

    except Exception as e:
        import traceback
        # traceback.print_exc()
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
