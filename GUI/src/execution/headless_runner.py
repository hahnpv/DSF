
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
            child_name = child.attrAsString("name")
            
            # Prioritize 'name' for instance_id if available (for UI uniqueness), 
            # fallback to 'id' (for connection wiring).
            # Limitation: Wiring references 'id'. If we change instance_id in memory, 
            # implicit auto-wiring by 'id' inside the C++ engine might break if it relies on a lookup by id.
            # However, standard XML loading uses the constructed tree structure. explicit connections use pointers?
            # Actually, configure(node) might do looking up.
            # But top-level blocks in 'sim' are usually autonomous vehicles.
            final_id = child_name if child_name else child_id
            
            child_class = child.attrAsString("class")
            if not final_id: continue
            
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
                    new_block.instance_id = final_id
                if hasattr(new_block, "instance_id"):
                    new_block.instance_id = final_id
                sim_root.addChild(new_block)
                all_blocks_to_config.append((new_block, child, final_id))
        
        for block, node, name_override in all_blocks_to_config:
            block.configure(node)
            # Re-apply unique name because configure(node) might have reset it to the raw XML 'id'
            if name_override and hasattr(block, "instance_id"):
                 print(f"DEBUG: Overwriting ID '{block.instance_id}' with '{name_override}'", file=sys.stderr)
                 block.instance_id = name_override
                 print(f"DEBUG: New ID is '{block.instance_id}'", file=sys.stderr)

        # Recursive renaming to ensure unique IDs for all children
        # e.g. GPS_1 -> GPS_1_Equinoctial
        def rename_recursive(block, parent_prefix):
             # DFS
             # Children access currently not exposed via simple iteration on Block object in Python 
             # unless we kept track of them during construction.
             pass
        
        # We constructed the tree. We can traverse our construction list?
        # No, we only have the flat list 'all_blocks_to_config' but we know the structure from XML logic?
        # Actually, `sim_root` has children... but dsf.Block might not expose `children()` iterator in Python?
        # Let's rely on the fact that we set top-level IDs correctly.
        # If prefixing is working, at least top-level 'Vehicle' (renamed to GPS...) should work.
        
        sim = dsf.Sim()
        sim.load(sim_root, dt, tmax, 0, 1.0)
        
        if hasattr(sim, 'init') and hasattr(sim, 'exec'):
            sim.init()
            if hasattr(sim.output, "set_prefix_with_id"):
                 sim.output.set_prefix_with_id(True)
            
            # Emit Headers
            if hasattr(sim, 'output'):
                raw_headers = sim.output.get_header_names()
                
                # Heuristic: Prefix headers with vehicle names if counts match
                # Use the updated instance_ids from our config loop
                vehicle_names = []
                for b, node, v_name in all_blocks_to_config:
                    c_class = node.attrAsString("class")
                    # Only include if it is a Vehicle. 
                    # This excludes things like 'Earth' or 'Ephemeris' if they are top level but don't output headers in the same way,
                    # or if they are just configuration blocks.
                    if v_name and c_class == "Vehicle":
                         vehicle_names.append(v_name)

                final_headers = raw_headers
                
                if vehicle_names:
                    num_v = len(vehicle_names)
                    num_h = len(raw_headers)
                    # print(json.dumps({"progress": 0, "message": f"DEBUG: Heuristic Check: num_v={num_v} num_h={num_h}"}))

                    if num_v > 0 and num_h % num_v == 0:
                        vars_per_v = num_h // num_v
                        # Construct new headers
                        new_headers = []
                        for i, h in enumerate(raw_headers):
                            v_idx = i // vars_per_v
                            if v_idx < num_v:
                                v_name = vehicle_names[v_idx]
                                new_headers.append(f"{v_name}_{h}")
                            else:
                                new_headers.append(h)
                        final_headers = new_headers
                
                print(json.dumps({"headers": final_headers}))
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
