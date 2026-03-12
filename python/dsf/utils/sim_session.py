"""
dsf.utils.sim_session
---------------------
Shared simulation engine used by both the GUI's headless_runner and the CLI
watch command. Owns the block tree construction, step loop, and property
introspection so neither caller has to duplicate this logic.
"""

from __future__ import annotations
import ctypes
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

    def __init__(self, xml_path: str, lib_path: str, dt: float, tmax: float):
        self.xml_path = xml_path
        self.lib_path = lib_path
        self.dt = dt
        self.tmax = tmax

        self._sim = None
        self._sim_root = None
        self._all_blocks: List[Tuple[Any, Any, str]] = []  # (block, xml_node, id)
        self._final_headers: List[str] = []
        self._dsf = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self):
        """Load library, parse XML, construct block tree, and call sim.init()."""
        import dsf as _dsf
        self._dsf = _dsf

        # Load shared library
        ctypes.CDLL(self.lib_path, mode=os.RTLD_GLOBAL | os.RTLD_NOW)

        # Parse XML
        xml_input = _dsf.xml(self.xml_path)
        xml_input.parse()
        sim_node = xml_input.xmlRoot.search("sim")

        # Build block tree
        self._sim_root = _dsf.Block()
        for child in sim_node.children():
            child_id    = child.attrAsString("id")
            child_name  = child.attrAsString("name")
            child_class = child.attrAsString("class")
            if not child_id:
                continue

            final_id  = child_name if child_name else child_id
            raw_tag   = child.name()
            class_to_use = (child_class if child_class
                            else (raw_tag[0].upper() + raw_tag[1:] if raw_tag else ""))

            block = _dsf.make_block(class_to_use)
            if block is None:
                raise RuntimeError(
                    f"Factory returned None for class '{class_to_use}' (id={child_id}). "
                    "Is the library loaded and the class name correct?"
                )
            self._sim_root.addChild(block)
            self._all_blocks.append((block, child, final_id))

        # Configure pass
        for block, node, name_override in self._all_blocks:
            block.configure(node)

        # Init simulation
        self._sim = _dsf.Sim()
        
        # Parse integrator selection from XML
        integrator_type = sim_node.attrAsString("integrator")
        if integrator_type:
            atol_str = sim_node.attrAsString("atol")
            rtol_str = sim_node.attrAsString("rtol")
            atol = float(atol_str) if atol_str else 1e-8
            rtol = float(rtol_str) if rtol_str else 1e-6
            self._sim.load(self._sim_root, self.dt, self.tmax, 0, 1.0,
                           integrator_type, atol, rtol)
        else:
            self._sim.load(self._sim_root, self.dt, self.tmax, 0, 1.0)
        self._sim.init()

        # Build prefixed headers
        self._final_headers = self._build_headers()

    def headers(self) -> List[str]:
        return self._final_headers

    def t(self) -> float:
        return self._sim.clock.t()

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

        n_v, n_h = len(vehicle_names), len(raw)
        if n_h % n_v != 0:
            return raw  # Can't cleanly assign headers to vehicles

        vpv = n_h // n_v
        return [
            f"{vehicle_names[i // vpv]}_{h}"
            for i, h in enumerate(raw)
        ]
