
import sys
import argparse
import ctypes
import os
import importlib.util


def _load_dsf_core():
    """Load the ``dsf_core`` C++ extension exactly once.

    The extension must be loaded with RTLD_GLOBAL so model libraries can resolve
    DSF symbols. Critically, we register it in ``sys.modules['dsf.dsf_core']``
    *before* anything imports the ``dsf`` package, so the package's
    ``from .dsf_core import *`` reuses this same module object rather than
    dlopen'ing a second copy — a second copy makes pybind11 abort with
    "generic_type: type 'Vec3' is already registered".

    Returns the module, or None if the extension cannot be found/loaded.
    """
    # Already loaded (e.g. the package was imported first)? Reuse it.
    if "dsf.dsf_core" in sys.modules:
        return sys.modules["dsf.dsf_core"]

    here = os.path.dirname(__file__)
    # Prefer a freshly-built extension, then the copy inside the package,
    # then a pip-installed copy (scikit-build-core puts the compiled files in
    # site-packages/dsf/ even for editable installs of this source tree).
    search_dirs = [
        os.path.join(here, "../../../build"),   # repo build/
        os.path.join(here, "../../build"),      # alt build/
        os.path.join(here, ".."),               # python/dsf/ (in-tree copy)
    ]
    import site
    site_dirs = list(getattr(site, "getsitepackages", lambda: [])())
    user_site = getattr(site, "getusersitepackages", lambda: None)()
    if user_site:
        site_dirs.append(user_site)
    search_dirs += [os.path.join(sp, "dsf") for sp in site_dirs]
    so_path = None
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        # Match the exact extension name; sort for determinism (avoids the old
        # arbitrary os.listdir order that could pick a stale ABI).
        cands = sorted(f for f in os.listdir(d)
                       if f.startswith("dsf_core") and f.endswith(".so"))
        if cands:
            so_path = os.path.join(d, cands[0])
            break

    old_flags = sys.getdlopenflags()
    try:
        sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
        if so_path:
            spec = importlib.util.spec_from_file_location("dsf.dsf_core", so_path)
            mod = importlib.util.module_from_spec(spec)
            # Register before exec so a re-entrant `import dsf` reuses this copy.
            sys.modules["dsf.dsf_core"] = mod
            sys.modules.setdefault("dsf_core", mod)
            spec.loader.exec_module(mod)
            return mod
        # Last resort: an installed extension importable as a top-level module.
        import dsf as pkg
        return pkg
    except (ImportError, FileNotFoundError):
        return None
    finally:
        sys.setdlopenflags(old_flags)   # don't leak RTLD_GLOBAL to later imports


dsf = _load_dsf_core()

def parse_args():
    parser = argparse.ArgumentParser(description="Run a simulation from an XML configuration file.")
    parser.add_argument("--fname", required=True, help="Path to the XML configuration file")
    parser.add_argument("--h5", action="store_true", default=False,
                        help="Also write an HDF5 output file (overrides project/XML setting)")
    return parser.parse_args()

def map_level(level_str):
    if level_str == "verbose":
        return dsf.LogLevel.LOG_VERBOSE
    if level_str == "critical":
        return dsf.LogLevel.LOG_CRITICAL
    return dsf.LogLevel.LOG_NORMAL

def main():
    if dsf is None:
        print("Error: Could not load the dsf_core C++ extension. "
              "Build it (see CLAUDE.md) and copy build/dsf_core*.so into python/dsf/.")
        sys.exit(1)

    args = parse_args()

    if not os.path.exists(args.fname):
        print(f"Error: File '{args.fname}' not found.")
        sys.exit(1)

    # 1. Parse XML (or JSON/DSF dynamically)
    is_temp_xml = False
    target_xml_path = args.fname
    run_config = None  # populated only for .dsf / .json inputs
    
    if args.fname.lower().endswith('.json') or args.fname.lower().endswith('.dsf'):
        # -- Load runner policy from JSON metadata FIRST --
        try:
            from dsf.utils.run_config import load_run_config
            run_config = load_run_config(args.fname)
        except Exception as e:
            print(f"Warning: Could not load run config from DSF metadata: {e}")
            run_config = None

        # -- Convert block graph JSON -> temp XML for C++ --
        try:
            from dsf.utils.convert_dsf_to_xml import convert_dsf_to_xml
            target_xml_path = convert_dsf_to_xml(args.fname)
            is_temp_xml = True
        except Exception as e:
            print(f"Error converting DSF/JSON file to XML: {e}")
            sys.exit(1)
            
    xml_input = dsf.xml(target_xml_path)
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
    
    # Integrator selection (default: RK4)
    integrator_type = sim_node.attrAsString("integrator") or "RK4"
    atol = sim_node.attrAsDouble("atol") if sim_node.attrAsString("atol") else 1e-8
    rtol = sim_node.attrAsDouble("rtol") if sim_node.attrAsString("rtol") else 1e-6

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

    # If a RunConfig was loaded from .dsf metadata, let it override XML-derived settings.
    # This allows the JSON project file to be the authoritative source of output policy
    # rather than relying on <sim> XML attributes (which are written by the converter anyway).
    if run_config is not None:
        is_csv      = run_config.is_csv
        is_hdf5     = run_config.is_hdf5
        csv_level   = run_config.to_log_level(dsf, "csv_level_name")
        h5_level    = run_config.to_log_level(dsf, "hdf5_level_name")
        if run_config.console_rate > 0:
            rate_console = run_config.console_rate
        if run_config.file_rate > 0:
            rate_file = run_config.file_rate

    # --h5 CLI flag always wins, regardless of project/XML defaults
    if args.h5:
        is_hdf5 = True

    print(f"Configuration:")
    print(f"  Tmax: {tmax}, dt: {dt}")
    print(f"  Library: {library_path}")
    print(f"  Output: CSV={is_csv} ({csv_level}), HDF5={is_hdf5} ({h5_level})")

    # Build the simulation via the shared SimSession builder — the SAME
    # construction path used by `dsf watch`, the GUI, and the MCP server, so the
    # run / watch / GUI / MCP paths can no longer drift in how they build the
    # block tree. Output policy + report rates are passed as config.
    from dsf.utils.sim_session import SimSession
    session = SimSession(
        target_xml_path, library_path, dt, tmax,
        console_rate=rate_console, file_rate=rate_file,
        integrator=integrator_type, atol=atol, rtol=rtol,
        csv=is_csv, hdf5=is_hdf5, csv_level=csv_level, h5_level=h5_level,
    )

    try:
        session.build_tree()
    except Exception as e:
        print(f"Error building simulation: {e}")
        sys.exit(1)

    # init() registers integrands and builds telemetry headers.
    session.init()

    all_headers = session.sim.output.get_header_names()
    watch = (run_config.watch if run_config is not None else [])
    if watch:
        matched = [h for h in all_headers if any(w in h for w in watch)]
        if matched:
            print(f"Watching {len(matched)}/{len(all_headers)} telemetry channels: {matched}")
        else:
            print(f"Warning: watch list {watch!r} matched no headers. Available: {all_headers}")
    else:
        print(f"Telemetry Headers: {all_headers}")

    print("Starting simulation...")
    session.exec_loop()
    print("Simulation complete.")

    # Cleanup temporary XML if it was dynamically generated from a JSON project
    if is_temp_xml and os.path.exists(target_xml_path):
        try:
            os.remove(target_xml_path)
        except OSError:
            pass

if __name__ == "__main__":
    main()
