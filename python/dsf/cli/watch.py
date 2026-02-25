"""
dsf.cli.watch
-------------
High-visibility simulation runner. Uses the SimSession step loop to query
live property values after each tick and print them to the console, filtered
by the `watch` list in RunConfig metadata.

Unlike `dsf run` (which calls sim.exec() and lets C++ own the loop),
this command drives the loop from Python, which allows per-step introspection
at the cost of some throughput overhead.
"""

from __future__ import annotations
import sys
import os
import time
from typing import List, Dict, Any


def _resolve_watch(watch: List[str], headers: List[str]) -> List[str]:
    """
    Match watch patterns against available header names.
    Returns the subset of headers whose names contain at least one watch token.
    Deduplicates by suffixing with _0, _1 if the same short name appears more than once.
    """
    if not watch:
        return headers
    return [h for h in headers if any(w.lower() in h.lower() for w in watch)]


def _short_name(header: str) -> str:
    """Return the last dot-segment of a dotted header, or the full string."""
    return header.split(".")[-1].split("_")[-1] if "." in header else header.split("_")[-1]


def _format_row(headers: List[str], values: List[Any], width: int = 12) -> str:
    pairs = []
    for h, v in zip(headers, values):
        label = _short_name(h)
        if isinstance(v, float):
            pairs.append(f"{label}: {v:.4g}")
        else:
            pairs.append(f"{label}: {str(v)[:width]}")
    return "  |  ".join(pairs)


def run_watch(xml_path: str, lib_path: str, dt: float, tmax: float, watch: List[str],
              console_rate: float = 1.0):
    """
    Core watch loop. Drives SimSession's step loop and prints filtered telemetry.

    Parameters
    ----------
    xml_path     : Path to the XML simulation file.
    lib_path     : Path to the simulation shared library.
    dt, tmax     : Simulation timing.
    watch        : List of variable name patterns to display. Empty = all headers.
    console_rate : Minimum wall-clock seconds between console prints.
    """
    from dsf.utils.sim_session import SimSession

    print(f"\ndsf watch [{os.path.basename(xml_path)}]")
    print(f"  dt={dt}  tmax={tmax}  library={os.path.basename(lib_path)}")
    if watch:
        print(f"  Watching: {watch}")
    print()

    session = SimSession(xml_path, lib_path, dt, tmax)
    try:
        session.build()
    except Exception as e:
        print(f"Error building simulation: {e}")
        sys.exit(1)

    all_headers  = session.headers()
    disp_headers = _resolve_watch(watch, all_headers)

    if not disp_headers:
        print(f"Warning: watch patterns {watch!r} matched none of the {len(all_headers)} headers.")
        print(f"Available: {all_headers[:10]}{'...' if len(all_headers) > 10 else ''}")
        disp_headers = all_headers  # Fall back to all

    # Print column header row once
    col_row = "  |  ".join(h.split(".")[-1] for h in disp_headers)
    print(f"{'t(s)':>10}  {col_row}")
    print("-" * min(120, 12 + len(col_row) + 5))

    # Header index positions for efficient lookup from flat values array
    header_indices = {h: i for i, h in enumerate(all_headers)}
    disp_indices   = [header_indices[h] for h in disp_headers if h in header_indices]

    last_pt = time.time()

    while session.t() < tmax:
        session.step()
        t = session.t()
        pt = time.time()

        if pt - last_pt >= max(console_rate, 0.033):
            vals = session.current_values()
            disp_vals = [vals[i] for i in disp_indices]
            row = _format_row(disp_headers, disp_vals)
            print(f"{t:>10.1f}  {row}")
            last_pt = pt

    # Final state
    vals = session.current_values()
    disp_vals = [vals[i] for i in disp_indices]
    row = _format_row(disp_headers, disp_vals)
    print(f"{session.t():>10.1f}  {row}")
    print(f"\nSimulation complete. ({tmax}s of sim time)")

    session.finalize()
