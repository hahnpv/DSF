
import sys
import argparse
import ctypes
import os
import importlib.util


def _extension_candidates():
    """All discoverable dsf_core extension copies, in preference order.

    Preference: repo build/ (freshly cmake-built) → in-tree package copy →
    pip-installed copies (scikit-build-core puts the compiled files in
    site-packages/dsf/ even for editable installs of this source tree).
    Within a directory, the exact ABI tag of THIS interpreter wins; a lone
    foreign-ABI copy is still returned (sorted) as a last resort.
    """
    import sysconfig
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".so"

    here = os.path.dirname(__file__)
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

    candidates = []
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        exact = os.path.join(d, "dsf_core" + ext_suffix)
        if os.path.exists(exact):
            candidates.append(exact)
            continue
        candidates.extend(os.path.join(d, f) for f in
                          sorted(f for f in os.listdir(d)
                                 if f.startswith("dsf_core") and f.endswith(".so")))
    return candidates


def _warn_if_stale(loaded_path):
    """Warn when another dsf_core copy is newer than the one in use.

    The repo build/ copy and the pip-installed copy go stale relative to each
    other (CLAUDE.md gotcha): which one wins depends on whether the package or
    this module imports first, and a stale winner silently runs old C++. The
    mismatch is cheap to detect — make it self-diagnosing instead of a
    debugging session.
    """
    try:
        loaded_mtime = os.path.getmtime(loaded_path)
        newer = [c for c in _extension_candidates()
                 if not os.path.samefile(c, loaded_path)
                 and os.path.getmtime(c) > loaded_mtime + 1.0]
        if newer:
            print(f"WARNING: the loaded dsf_core extension\n"
                  f"    {loaded_path}\n"
                  f"  is OLDER than another copy on this system:\n"
                  f"    {newer[0]}\n"
                  f"  C++ changes may be missing from this run. Re-sync with\n"
                  f"  `pip install -e . --no-build-isolation` (refreshes the pip copy)\n"
                  f"  or rebuild in build/ (see CLAUDE.md).", file=sys.stderr)
    except OSError:
        pass


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
    # Already loaded (e.g. the package was imported first)? Reuse it — but
    # check it isn't a stale copy shadowing a fresher build.
    if "dsf.dsf_core" in sys.modules:
        mod = sys.modules["dsf.dsf_core"]
        loaded = getattr(mod, "__file__", None)
        if loaded:
            _warn_if_stale(loaded)
        return mod

    cands = _extension_candidates()
    so_path = cands[0] if cands else None

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
            _warn_if_stale(so_path)
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
    parser.add_argument("--not-strict", dest="not_strict", action="store_true",
                        default=False,
                        help="Run despite config-validation findings (unused/"
                             "typo'd attributes, failed table loads). Strict "
                             "mode is the default.")
    return parser.parse_args()

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

    # 2. Parse simulation settings via the BOUND SimInput — the same reader
    # the C++ `dynamic` loader uses, so the two paths cannot drift (times,
    # output policy, log levels, integrator, Monte-Carlo case identity).
    si = dsf.SimInput(sim_node)
    tmax, dt = si.tmax(), si.dt()
    rate_console, rate_file = si.rate_console(), si.rate_file()
    library_path = si.library()
    integrator_type = si.integrator() or "RK4"
    atol, rtol = si.atol(), si.rtol()
    case_id, case_seed = si.case_id(), si.seed()
    is_csv, is_hdf5 = si.is_csv(), si.is_hdf5()
    csv_level, h5_level = si.csv_level(), si.hdf5_level()

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
        case_id=case_id, case_seed=case_seed,
        strict=not args.not_strict,
    )

    try:
        session.build_tree()
    except Exception as e:
        print(f"Error building simulation: {e}")
        sys.exit(1)

    # init() registers integrands, validates the config (strict mode may
    # refuse to run here), and builds telemetry headers.
    try:
        session.init()
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

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
