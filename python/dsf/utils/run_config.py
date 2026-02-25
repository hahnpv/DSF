"""
dsf.utils.run_config
--------------------
Reads the `metadata` section of a `.dsf` JSON project file and returns a
typed RunConfig object that governs *runner policy* — what the Python CLI
layer does around the C++ simulation math.

Nothing here touches the block graph or the XML-based C++ configuration.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Log-level helpers (mirrors dsf.LogLevel without importing dsf at parse time)
# ---------------------------------------------------------------------------

LOG_LEVEL_MAP = {
    "normal":   "LOG_NORMAL",
    "verbose":  "LOG_VERBOSE",
    "critical": "LOG_CRITICAL",
}

def _parse_log_level(s: str) -> str:
    """Return the dsf.LogLevel enum name string from a human-readable string."""
    return LOG_LEVEL_MAP.get((s or "normal").strip().lower(), "LOG_NORMAL")


# ---------------------------------------------------------------------------
# RunConfig dataclass
# ---------------------------------------------------------------------------

@dataclass
class RunConfig:
    """
    All Python-side simulation policy derived from a .dsf project's metadata.
    
    Fields
    ------
    dt, tmax        : Simulation timing.
    library         : Path to the shared library (.so/.dll) to load.
    is_csv          : Whether to write CSV output.
    is_hdf5         : Whether to write HDF5 output.
    csv_level_name  : dsf.LogLevel enum name for CSV output.
    hdf5_level_name : dsf.LogLevel enum name for HDF5 output.
    console_rate    : Seconds between console prints (0 = off / every step).
    file_rate       : Seconds between file writes (0 = default / every step).
    watch           : Dot-path variable names to echo after the run.
                      Empty list means print all headers (legacy behaviour).
    """
    dt:              float       = 0.1
    tmax:            float       = 100.0
    library:         str         = ""
    is_csv:          bool        = True
    is_hdf5:         bool        = False
    csv_level_name:  str         = "LOG_NORMAL"
    hdf5_level_name: str         = "LOG_NORMAL"
    console_rate:    float       = 0.0
    file_rate:       float       = 0.0
    watch:           List[str]   = field(default_factory=list)

    def to_log_level(self, dsf_module, attr: str):
        """Return the actual dsf.LogLevel enum value for a *_level_name attr."""
        name = getattr(self, attr)
        return getattr(dsf_module.LogLevel, name, dsf_module.LogLevel.LOG_NORMAL)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_run_config(dsf_path: str) -> RunConfig:
    """
    Parse the *metadata* block of a .dsf JSON project file into a RunConfig.

    Only the ``metadata`` key is read here — the block graph is ignored.
    Missing keys fall back to RunConfig defaults so old files remain valid.
    """
    with open(dsf_path, "r") as f:
        data = json.load(f)

    meta = data.get("metadata", {})

    # --- Timing ----------------------------------------------------------
    dt   = float(meta.get("dt",   0.1))
    tmax = float(meta.get("tmax", 100.0))

    # --- Library ---------------------------------------------------------
    library = meta.get("lib_path", "") or meta.get("library", "")

    # --- Output formats & log levels ------------------------------------
    out_cfg = meta.get("output", {})

    if isinstance(out_cfg, str):
        # Legacy: "output" used to be a bare string like "csv" or "csv,hdf5"
        formats = [s.strip().lower() for s in out_cfg.split(",")]
        is_csv  = "csv"  in formats or not formats
        is_hdf5 = "hdf5" in formats
        csv_level_name  = _parse_log_level(meta.get("log_level", "normal"))
        hdf5_level_name = csv_level_name
    else:
        formats = [s.lower() for s in out_cfg.get("formats", ["csv"])]
        is_csv  = "csv"  in formats
        is_hdf5 = "hdf5" in formats
        global_level    = out_cfg.get("log_level", "normal")
        csv_level_name  = _parse_log_level(out_cfg.get("csv_log_level",  global_level))
        hdf5_level_name = _parse_log_level(out_cfg.get("hdf5_log_level", global_level))

    # --- Telemetry policy -----------------------------------------------
    telem = meta.get("telemetry", {})
    console_rate = float(telem.get("console_rate", 0.0))
    file_rate    = float(telem.get("file_rate",    0.0))
    watch        = list(telem.get("watch", []))

    return RunConfig(
        dt=dt, tmax=tmax, library=library,
        is_csv=is_csv, is_hdf5=is_hdf5,
        csv_level_name=csv_level_name, hdf5_level_name=hdf5_level_name,
        console_rate=console_rate, file_rate=file_rate,
        watch=watch,
    )
