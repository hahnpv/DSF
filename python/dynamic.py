
import sys
import argparse
import ctypes
import os

# Add build directory to path so we can import dsf
sys.path.append(os.path.join(os.path.dirname(__file__), "../build"))

try:
    # Force symbols to be global so singletons (TClassDict) are shared with loaded libraries
    sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
    import dsf
except ImportError as e:
    print(f"Error: Could not import dsf module: {e}")
    sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(description="Run a simulation from an XML configuration file.")
    parser.add_argument("--fname", required=True, help="Path to the XML configuration file")
    return parser.parse_args()

def map_level(level_str):
    if level_str == "verbose":
        return dsf.LogLevel.LOG_VERBOSE
    if level_str == "critical":
        return dsf.LogLevel.LOG_CRITICAL
    return dsf.LogLevel.LOG_NORMAL

def main():
    args = parse_args()
    
    if not os.path.exists(args.fname):
        print(f"Error: File '{args.fname}' not found.")
        sys.exit(1)

    # 1. Parse XML
    xml_input = dsf.xml(args.fname)
    xml_input.parse()
    # Note: xml_input.xmlRoot is a pointer, bindings return reference to it?
    # bindings_util.cpp: .def_readonly("xmlRoot", &xml::xmlRoot, py::return_value_policy::reference);
    # So we get an xmlnode object.
    
    root_node = xml_input.xmlRoot
    sim_node = root_node.search("sim")
    
    # 2. Parse Simulation Settings (SimInput logic)
    # SimInput parsing logic manually implemented here since SimInput class isn't bound (and is simple enough)
    
    tmax = sim_node.attrAsDouble("tmax")
    dt = sim_node.attrAsDouble("dt")
    rate_console = sim_node.attrAsDouble("console")
    rate_file = sim_node.attrAsDouble("file")
    library_path = sim_node.attrAsString("library")
    output_cfg = sim_node.attrAsString("output") # e.g. "csv", "hdf5", or empty (default csv)
    
    log_level_str = sim_node.attrAsString("log_level")
    csv_log_level_str = sim_node.attrAsString("csv_log_level")
    hdf5_log_level_str = sim_node.attrAsString("hdf5_log_level")

    # Resolve Log Levels
    def resolve_level(specific, global_val):
        if specific: return map_level(specific)
        if global_val: return map_level(global_val)
        return dsf.LogLevel.LOG_NORMAL

    csv_level = resolve_level(csv_log_level_str, log_level_str)
    h5_level = resolve_level(hdf5_log_level_str, log_level_str)

    # Configure Global Output Defaults
    is_csv = (not output_cfg) or ("csv" in output_cfg)
    is_hdf5 = bool(output_cfg and "hdf5" in output_cfg)

    print(f"Configuration:")
    print(f"  Tmax: {tmax}, dt: {dt}")
    print(f"  Library: {library_path}")
    print(f"  Output: CSV={is_csv} ({csv_level}), HDF5={is_hdf5} ({h5_level})")

    dsf.Output.defaultCSV = is_csv
    dsf.Output.defaultHDF5 = is_hdf5
    dsf.Output.defaultCSVLevel = csv_level
    dsf.Output.defaultHDF5Level = h5_level

    # 3. Load Shared Library
    # The XML library attribute might be relative to the XML file or CWD. 
    # The C++ code does `dlopen(input.library().c_str()...)`
    # We should probably handle relative paths relative to CWD as C++ does by default.
    
    try:
        # RTLD_GLOBAL is essential so that the loaded library's symbols
        # RTLD_NOW ensures static initializers (factory registration) run immediately
        ctypes.CDLL(library_path, mode=os.RTLD_GLOBAL | os.RTLD_NOW)
        print(f"Loaded library: {library_path}")
    except OSError as e:
        print(f"Error loading library '{library_path}': {e}")
        # Try finding it relative to the XML file
        xml_dir = os.path.dirname(os.path.abspath(args.fname))
        alt_path = os.path.join(xml_dir, library_path)
        if os.path.exists(alt_path) and alt_path != library_path:
             try:
                ctypes.CDLL(alt_path, mode=os.RTLD_GLOBAL | os.RTLD_NOW)
                print(f"Loaded library from alternative path: {alt_path}")
             except OSError as e2:
                 print(f"Fatal error loading library: {e2}")
                 sys.exit(1)
        else:
            sys.exit(1)
    


    # 4. Instantiate and Configure Blocks
    # Create a root Block to hold everything
    sim_root = dsf.Block()
    
    # Iterate over children of 'sim' node
    children = sim_node.children()
    blocks = []
    children_nodes = []
    for child in children:
        child_id = child.attrAsString("id")
        child_class = child.attrAsString("class")
        if not child_id:
            continue
            
        class_to_use = child_class or child.tag().capitalize()
        print(f"Creating root block: {child_id} [class={class_to_use}]")
        
        try:
            new_block = dsf.make_block(class_to_use)
            if new_block:
                sim_root.addChild(new_block)
                blocks.append(new_block)
                children_nodes.append(child)
            else:
                print(f"Warning: Factory returned None for class '{class_to_use}' (id={child_id})")
        except Exception as e:
            print(f"Error creating block '{child_id}': {e}")

    # Configure Pass
    # Get children again or just iterate the blocks we added?
    # The C++ code iterates XML children again and calls getChild(i)->configure(node).
    # Since we added them in order, index alignment should hold.
    
    # We can iterate Python sim_root children? sim_root doesn't expose list of children directly?
    # Block binding: children is protected. no getChildren() exposed?
    # Wait, I didn't check if getChildren is exposed. 
    # Checked bindings_sim.cpp: 
    # .def("addChild", ...)
    # .def("has_children", ...)
    # // .def("getParent", &Block::getParent) 
    # // .def("getChild", &Block::getChild)
    # They are commented out in the file I viewed! 
    # But wait, looking at `main.cpp` logic:
    # `root->getChild(i)->configure( child_node);`
    # So I DO need access to the children blocks to configure them.
    
    # If getChild isn't exposed, I can't retrieve them from sim_root.
    # But I have the `new_block` reference in the first loop.
    # So I should configure it right there, OR store them in a list.
    
    # Re-reading C++ main.cpp:
    # for ( int i = 0; i < nx; i++) root->addChild( TRefUnique<Block>( child_node.attrAsString("id")));
    # for ( int i = 0; i < nx; i++) root->getChild(i)->configure( child_node);
    
    # Configure each block with its corresponding XML node
    for block, node in zip(blocks, children_nodes):
        block.configure(node)


    # 5. Run Simulation
    sim = dsf.Sim()
    sim.load(sim_root, dt, tmax, rate_console, rate_file)
    
    if hasattr(sim, 'init') and hasattr(sim, 'exec'):
        print("Starting simulation (init/exec)...")
        sim.init()
        
        # Quick Header Print
        if hasattr(sim, 'output'):
            headers = sim.output.get_header_names()
            print(f"Telemetry Headers: {headers}")
            
        sim.exec()
    else:
        print("Starting simulation (run)...")
        sim.run()
        
    print("Simulation complete.")

if __name__ == "__main__":
    main()
