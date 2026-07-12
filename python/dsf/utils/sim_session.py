"""
dsf.utils.sim_session
---------------------
Shared simulation engine used by both the GUI's headless_runner and the CLI
watch command. Owns the block tree construction, step loop, and property
introspection so neither caller has to duplicate this logic.
"""

from __future__ import annotations
import os
import sys
from typing import List, Tuple, Any, Dict, Optional


class SimSession:
    """
    Wraps a complete simulation lifecycle:
      build()          — load library, parse XML, create block tree, init
      headers()        — prefixed telemetry header names
      t()              — current simulation clock time
      step()           — advance one tick
      current_values() — flat list from sim.output (matches headers order)
      collect_state()  — deep recursive introspection → nested dict
      finalize()       — call sim.finalize()
    """

    def __init__(self, xml_path: str, lib_path: str, dt: float, tmax: float,
                 console_rate: float = 0.0, file_rate: float = 1.0,
                 integrator: str = "", atol: float = 1e-8, rtol: float = 1e-6,
                 csv: Optional[bool] = None, hdf5: Optional[bool] = None,
                 csv_level: Any = None, h5_level: Any = None,
                 case_id: int = -1, case_seed: int = 0,
                 strict: bool = True):
        """Construct a simulation session.

        The timing/output parameters make this the single tree-builder shared by
        `dsf run` (C++ exec loop), `dsf watch`, the GUI headless runner, and the
        MCP server, so those paths cannot drift in how they build the block tree.

        console_rate/file_rate : Output report rates passed to Sim::load.
        integrator/atol/rtol   : Integrator selection ("" = read from XML).
        csv/hdf5/csv_level/h5_level : Output policy (None = leave C++ defaults).
        """
        self.xml_path = xml_path
        self.lib_path = lib_path
        self.dt = dt
        self.tmax = tmax
        self.console_rate = console_rate
        self.file_rate = file_rate
        self.integrator = integrator
        self.atol = atol
        self.rtol = rtol
        self.csv = csv
        self.hdf5 = hdf5
        self.csv_level = csv_level
        self.h5_level = h5_level
        self.case_id = case_id       # Monte-Carlo case (< 0 = nominal run)
        self.case_seed = case_seed
        self.strict = strict         # fail on config-validation findings;
                                     # default ON — opt out via --not-strict or
                                     # <sim strict="false">

        self._sim = None
        self._sim_root = None
        self._all_blocks: List[Tuple[Any, Any, str]] = []  # (block, xml_node, id)
        self._final_headers: List[str] = []
        self._dsf = None
        self._xml_input = None   # keep the parsed xml doc alive (xmlnode refs into it)
        self._sim_node = None
        self._built = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def sim(self):
        """The underlying dsf.Sim (valid after build_tree/build)."""
        return self._sim

    def _load_library(self):
        """dlopen the model library via the shared C++ loader (RTLD_GLOBAL so
        it can resolve DSF symbols, with a deck-relative path fallback) — the
        SAME code path the `dynamic` executable uses."""
        self._dsf.load_model_library(
            self.lib_path, os.path.dirname(os.path.abspath(self.xml_path)))

    def build_tree(self):
        """Load library, parse XML, construct + configure the block tree, and
        load the Sim — but do NOT call sim.init(). This is the single shared
        construction step; callers then either run the C++ exec loop
        (exec_loop / sim.run) or init() + a Python step loop."""
        import dsf as _dsf
        self._dsf = _dsf

        if self.lib_path:
            self._load_library()

        # Apply output policy (leave the C++ defaults where unset).
        if self.csv is not None:       _dsf.Output.defaultCSV = self.csv
        if self.hdf5 is not None:      _dsf.Output.defaultHDF5 = self.hdf5
        if self.csv_level is not None: _dsf.Output.defaultCSVLevel = self.csv_level
        if self.h5_level is not None:  _dsf.Output.defaultHDF5Level = self.h5_level

        # Parse XML. Keep the xml document alive on the session: xmlnode objects
        # returned by the bindings are raw references into this document, and
        # _all_blocks stores them for later use (e.g. _build_headers). If the
        # document were a local it would be freed on return, dangling those
        # references (use-after-free / segfault).
        xml_input = _dsf.xml(self.xml_path)
        xml_input.parse()
        self._xml_input = xml_input
        sim_node = xml_input.xmlRoot.search("sim")
        self._sim_node = sim_node   # reused by init() for <events> registration

        # Build the block tree via the shared C++ loader (sim/sim_loader.h):
        # instantiate + configure + typo check, ONE fallback rule — the same
        # code the `dynamic` executable runs, so the paths cannot drift.
        self._sim_root = _dsf.build_tree(sim_node)

        # Rebuild the (block, xml_node, id) introspection list the step-loop
        # callers (watch/GUI/MCP) use: C++ built children in deck order,
        # skipping id-less elements — walk the two in lockstep.
        blocks = self._sim_root.getChildren()
        bi = 0
        for child in sim_node.children():
            if not child.attrAsString("id"):
                continue
            block = blocks[bi]
            self._all_blocks.append((block, child, block.get_name()))
            bi += 1

        # Apply Monte-Carlo dispersions (after configure, before load — matching
        # the C++ loader). No-op for a nominal run (case_id < 0).
        _dsf.apply_monte_carlo(self._sim_root, sim_node, self.case_id, self.case_seed)

        # Load the Sim (integrator: explicit config wins, else read from XML).
        self._sim = _dsf.Sim()
        integrator_type = self.integrator or sim_node.attrAsString("integrator")
        if integrator_type:
            atol_str = sim_node.attrAsString("atol")
            rtol_str = sim_node.attrAsString("rtol")
            atol = self.atol if self.integrator else (float(atol_str) if atol_str else 1e-8)
            rtol = self.rtol if self.integrator else (float(rtol_str) if rtol_str else 1e-6)
            self._sim.load(self._sim_root, self.dt, self.tmax,
                           self.console_rate, self.file_rate,
                           integrator_type, atol, rtol)
        else:
            self._sim.load(self._sim_root, self.dt, self.tmax,
                           self.console_rate, self.file_rate)

        # Pass XML info for HDF5 metadata and filename convention
        try:
            with open(self.xml_path, 'r') as f:
                xml_content = f.read()
            self._sim.set_xml_info(self.xml_path, xml_content)
        except Exception:
            pass  # Non-fatal: metadata is nice-to-have

        self._built = True

    def init(self):
        """Initialize the loaded Sim (registers integrands) and build the
        prefixed telemetry headers. Call after build_tree() for the step-loop
        path (watch / GUI / MCP)."""
        if not self._built:
            self.build_tree()
        self._sim.init()
        # Register <events> after init so Output has resolved variable pointers
        # (same order as the C++ loader). Both dsf run and watch now get events.
        self._dsf.register_events(self._sim, self._sim_node)
        self._validate_config()
        self._final_headers = self._build_headers()

    def _validate_config(self):
        """Config validation: diff the deck against what the models
        actually read. Unused attributes (typos) and failed table loads are
        fatal by default; opt out with --not-strict (session strict=False)
        or <sim strict=\"false\">. Resolution + banner are the SAME bound
        C++ the `dynamic` loader uses."""
        strict = self._dsf.resolve_strict(self._sim_node,
                                          cli_not_strict=not self.strict)
        report = self._dsf.validate_config(self._xml_input)
        for u in report["unused"]:
            print(f"[config] UNUSED (possible typo — value silently ignored): {u}",
                  file=sys.stderr)
        for t in report["table_errors"]:
            print(f"[config] TABLE (interpolating 0): {t}", file=sys.stderr)
        if report["missing"]:
            print(f"[config] {len(report['missing'])} lookup(s) defaulted "
                  "(absent attribute/element; often optional)", file=sys.stderr)
        fatal = len(report["unused"]) + len(report["table_errors"])
        if strict and fatal:
            print(self._dsf.strict_banner_text(len(report["unused"]),
                                               len(report["table_errors"])),
                  file=sys.stderr, end="")
            raise RuntimeError(
                f"config validation failed: {len(report['unused'])} unused "
                f"attribute(s)/element(s), {len(report['table_errors'])} table "
                "error(s) — see the [config] lines and banner above")

    def build(self):
        """Construct + init in one call (step-loop callers)."""
        self.build_tree()
        self.init()

    def exec_loop(self):
        """Run the C++ exec loop to completion (step to tmax, then finalize).
        For `dsf run`. Assumes init() has already run."""
        self._sim.exec()

    def headers(self) -> List[str]:
        return self._final_headers

    def t(self) -> float:
        return self._sim.clock.t()

    def running(self) -> bool:
        """False once the sim has been terminated (e.g. by a sim.terminate
        event). Step loops must check this so events end the run early."""
        return self._sim.clock.is_running()

    def step(self):
        """Advance simulation by one timestep."""
        self._sim.step()

    def current_values(self) -> List[Any]:
        """Flat output values matching headers() order."""
        return self._sim.output.get_current_values()

    def collect_state(self) -> Dict[str, Dict[str, Any]]:
        """
        Recursively walk the block tree using property introspection.
        Returns {block_dot_path: {property_name: value, ...}, ...}.
        """
        result: Dict[str, Dict[str, Any]] = {}

        def _recurse(block, path: str):
            try:
                class_name = block.get_class_name()
                meta = self._dsf.get_block_metadata(class_name)
                props = meta[0]
                block_data: Dict[str, Any] = {}
                for p in props:
                    try:
                        val = block.get_property(p.name)
                        if val is None:
                            continue
                        # Serialise Vec3 to list
                        if hasattr(val, "x") and hasattr(val, "y") and hasattr(val, "z"):
                            val = [val.x, val.y, val.z]
                        block_data[p.name] = val
                    except Exception:
                        pass
                if block_data:
                    result[path] = block_data
            except Exception:
                pass

            if hasattr(block, "has_children") and block.has_children():
                for child in block.getChildren():
                    c_name = child.get_name() or "child"
                    _recurse(child, f"{path}.{c_name}")

        for block, _node, b_id in self._all_blocks:
            _recurse(block, b_id)

        return result

    def finalize(self):
        if self._sim is not None:
            self._sim.finalize()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> List[str]:
        """Return telemetry header names, prefixed with vehicle ID when applicable."""
        raw = self._sim.output.get_header_names()
        vehicle_names = [
            b_id for block, node, b_id in self._all_blocks
            if node.attrAsString("class") == "Vehicle"
        ]
        if not vehicle_names:
            return raw

        # Already prefixed at the C++ level (Output::setGroupName per vehicle)?
        # Then don't re-prefix.
        if any(h.startswith(v + "_") for v in vehicle_names for h in raw):
            return raw

        # Single vehicle: unambiguous — prefix everything with its id.
        if len(vehicle_names) == 1:
            return [f"{vehicle_names[0]}_{h}" for h in raw]

        # Multiple vehicles: the flat header list carries no per-vehicle boundary.
        # An even split is only correct when every vehicle logs the SAME number of
        # channels; for vehicles with differing channel counts it silently
        # mislabels (vehicle A credited with vehicle B's channels). Only apply the
        # split when it divides evenly, and warn that it assumes homogeneity.
        n_v, n_h = len(vehicle_names), len(raw)
        if n_h % n_v != 0:
            return raw
        import sys
        print("SimSession: prefixing multi-vehicle telemetry by an even split; "
              "this is only correct if all vehicles log the same channels. "
              "Use per-vehicle Output groups for reliable labeling.", file=sys.stderr)
        vpv = n_h // n_v
        return [f"{vehicle_names[i // vpv]}_{h}" for i, h in enumerate(raw)]
