"""
DSF MCP Server — Model Context Protocol tools for DSF simulations.

Exposes structured access to:
  - Running DSF simulations from XML configs
  - Reading CSV and HDF5 output files (headers, timeseries)
  - Live per-step introspection via SimSession (watch)
  - XML configuration introspection

Run standalone:  python -m dsf.mcp.server
Configure in mcp_config.json to use from AI assistants.
"""

import json
import os
import sys
import csv
import time as _time
import uuid
import threading
import subprocess
from pathlib import Path
from typing import Annotated, List, Dict, Any, Optional

import numpy as np

from mcp.server.fastmcp import FastMCP
from pydantic import Field

import functools
from pathlib import Path
import json as _json_builtin

FILE_ROOT = Path(os.environ.get("DSF_WORKSPACE", "/opt/sixdof")).resolve()

def safe_dumps(*args, **kwargs):
    s = _json_builtin.dumps(*args, **kwargs)
    s = s.replace(str(FILE_ROOT) + '/', '')
    s = s.replace(str(FILE_ROOT), '')
    return s

def resolve_path(rel_path: str) -> str:
    if not rel_path:
        return ""
    p = Path(rel_path)
    if not p.is_absolute():
        p = (FILE_ROOT / p).resolve()
    else:
        p = p.resolve()
        
    # Containment check via path semantics, not string prefix. A plain
    # startswith() lets "/opt/sixdof_secrets" pass as inside "/opt/sixdof".
    if p != FILE_ROOT and FILE_ROOT not in p.parents:
        raise ValueError(f"Security error: path '{rel_path}' ({p}) attempts to escape FILE_ROOT '{FILE_ROOT}'")
    return str(p)

def enforce_relative_paths(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        new_kwargs = {}
        # Match the new canonical param names + old names for backward compat
        path_params = {'file', 'file_a', 'file_b', 'library', 'output',
                       'xml_file', 'csv_file', 'h5_file', 'csv_file1', 'csv_file2',
                       'output_file', 'out_file', 'build_dir', 'src_dir', 'directory'}
        for k, v in kwargs.items():
            if k in path_params and isinstance(v, str):
                new_kwargs[k] = resolve_path(v)
            else:
                new_kwargs[k] = v
        return func(*args, **new_kwargs)
    return wrapper


# ── Parameter alias map ─────────────────────────────────────────
import inspect

PARAM_ALIASES = {
    # xml/csv/h5 file aliases → "file"
    "xml_file": "file",
    "csv_file": "file",
    "h5_file": "file",
    "output_file": "file",
    "path": "file",
    "file_path": "file",
    # comparison aliases
    "csv_file1": "file_a",
    "csv_file2": "file_b",
    # output aliases
    "out_file": "output",
    "output_path": "output",
    # operator alias
    "operator_str": "operator",
    # variable aliases
    "vars": "variables",
    "variable_names": "variables",
}


def normalize_args(func):
    """Decorator that maps common LLM parameter name mistakes to correct names.

    If an alias maps successfully, proceeds silently. If a parameter can't be
    resolved at all, returns a helpful JSON error with expected parameter names.
    """
    sig = inspect.signature(func)
    expected_params = set(sig.parameters.keys())

    # Build help dict from annotations for error messages
    param_help = {}
    for name, param in sig.parameters.items():
        desc = ""
        if hasattr(param.annotation, '__metadata__'):
            for meta in param.annotation.__metadata__:
                if hasattr(meta, 'description'):
                    desc = meta.description
        required = param.default is inspect.Parameter.empty
        param_help[name] = f"({'required' if required else 'optional'}) {desc}"

    @functools.wraps(func)
    def wrapper(**kwargs):
        normalized = {}
        unknown_keys = []

        for key, value in kwargs.items():
            if key in expected_params:
                normalized[key] = value
            elif key in PARAM_ALIASES and PARAM_ALIASES[key] in expected_params:
                canonical = PARAM_ALIASES[key]
                if canonical not in normalized:
                    normalized[canonical] = value
            else:
                unknown_keys.append(key)

        # Check for missing required params
        missing = [
            name for name, param in sig.parameters.items()
            if param.default is inspect.Parameter.empty and name not in normalized
        ]

        if missing:
            import json as _json
            hints = []
            for uk in unknown_keys:
                if uk in PARAM_ALIASES:
                    hints.append(f"'{uk}' -> use '{PARAM_ALIASES[uk]}' instead")
                else:
                    hints.append(f"'{uk}' is not a recognized parameter")

            return _json.dumps({
                "error": f"Parameter error calling {func.__name__}",
                "missing_required": missing,
                "unknown_parameters": unknown_keys,
                "hints": hints,
                "expected_parameters": param_help,
            })

        return func(**normalized)

    wrapper.__annotations__ = func.__annotations__
    return wrapper


mcp = FastMCP("dsf", instructions="DSF simulation framework tools for running sims, reading output, and live introspection")

# Monkey-patch mcp.tool to auto-apply normalize_args to every tool
_original_tool = mcp.tool


def _robust_tool(*args, **kwargs):
    """Wraps mcp.tool to add parameter alias normalization."""
    decorator = _original_tool(*args, **kwargs)

    def wrapping_decorator(func):
        wrapped = normalize_args(func)
        wrapped.__annotations__ = func.__annotations__
        wrapped.__doc__ = func.__doc__
        return decorator(wrapped)

    return wrapping_decorator


mcp.tool = _robust_tool

# =========================================================================
# State
# =========================================================================

# Background simulation jobs: job_id -> dict with proc, status, etc.
_running_jobs: dict = {}

# Watch sessions: job_id -> dict with SimSession, thread, state
_watch_sessions: dict = {}
_watch_lock = threading.Lock()


# =========================================================================
# Helpers
# =========================================================================

def _np_to_python(obj):
    """Recursively convert numpy types to Python native types for JSON."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _np_to_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_np_to_python(v) for v in obj]
    return obj


def _parse_csv_headers(csv_path: str) -> List[str]:
    """Read the header row from a CSV file."""
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
    return [h.strip() for h in headers]


def _read_csv_data(csv_path: str, variables: List[str] = None,
                   t_start: float = None, t_end: float = None,
                   decimation: int = 1) -> Dict:
    """Read CSV data, optionally filtered by variables, time range, and decimation."""
    headers = _parse_csv_headers(csv_path)

    # Build column index map
    col_map = {h: i for i, h in enumerate(headers)}

    # Determine which columns to read
    if variables:
        target_cols = {}
        for v in variables:
            v = v.strip()
            if v in col_map:
                target_cols[v] = col_map[v]
            else:
                # Fuzzy match: search for substring
                matches = [h for h in headers if v.lower() in h.lower()]
                if matches:
                    for m in matches:
                        target_cols[m] = col_map[m]
    else:
        target_cols = col_map

    # Find time column (first column, or one named "time"/"Time"/"t")
    time_col = 0
    for name in ["time", "Time", "t"]:
        if name in col_map:
            time_col = col_map[name]
            break

    # Read data
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row_idx, row in enumerate(reader):
            if len(row) < len(headers):
                continue
            try:
                t_val = float(row[time_col])
            except (ValueError, IndexError):
                continue

            if t_start is not None and t_val < t_start:
                continue
            if t_end is not None and t_val > t_end:
                continue
            if decimation > 1 and row_idx % decimation != 0:
                continue
            rows.append(row)

    # Build result
    result = {}
    for name, idx in target_cols.items():
        values = []
        for row in rows:
            try:
                values.append(float(row[idx]))
            except (ValueError, IndexError):
                values.append(None)
        result[name] = values

    return result


def _build_run_command(xml_file: str, library: str = None) -> tuple:
    """Build the command line and environment for running a DSF simulation."""
    xml_path = Path(xml_file).resolve()
    xml_dir = xml_path.parent

    # Determine library path
    if library:
        lib_path = str(Path(library).resolve())
    else:
        # Try to extract from XML
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        sim_node = root if root.tag == 'sim' else root.find('sim')
        if sim_node is not None:
            lib_path = sim_node.get('library', '')
        else:
            lib_path = ''

    # Build environment
    env = os.environ.copy()
    conda_lib = os.environ.get("DSF_CONDA_LIB", "")
    current_ld = env.get('LD_LIBRARY_PATH', '')
    if conda_lib and conda_lib not in current_ld:
        env['LD_LIBRARY_PATH'] = f"{conda_lib}:{current_ld}" if current_ld else conda_lib

    if lib_path:
        existing_preload = env.get('LD_PRELOAD', '')
        if lib_path not in existing_preload:
            env['LD_PRELOAD'] = f"{lib_path}:{existing_preload}" if existing_preload else lib_path

    # Find the dynamic executable
    dynamic_exe = os.environ.get("DSF_DYNAMIC_EXE", "/opt/DSF/build/examples/dynamic/dynamic")
    if not os.path.exists(dynamic_exe):
        raise FileNotFoundError(f"DSF dynamic executable not found at {dynamic_exe}")

    cmd = [dynamic_exe, str(xml_path)]
    return cmd, env, xml_dir


# =========================================================================
# Simulation Execution Tools
# =========================================================================

@mcp.tool(name="dsf_run_sim")
@enforce_relative_paths
def run_sim(
    file: Annotated[str, Field(description="Relative path to a DSF XML configuration file")],
    library: Annotated[str, Field(description="Path to shared library (e.g. libsixdof.so). Empty = read from XML.")] = "",
    tmax: Annotated[float, Field(description="Override simulation end time in seconds. 0 = use XML value.")] = 0,
) -> str:
    """Run a DSF simulation from an XML configuration file and return results.

    Example:
        dsf_run_sim(xml_file="/path/to/sim.xml", library="/path/to/libsixdof.so")
    """
    xml_file = file
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return safe_dumps({"error": f"XML file not found: {xml_file}"})

    try:
        cmd, env, cwd = _build_run_command(str(xml_path), library or None)
    except Exception as e:
        return safe_dumps({"error": str(e)})

    t0 = _time.time()
    try:
        proc = subprocess.run(
            cmd, env=env, cwd=str(cwd),
            capture_output=True, text=True, timeout=600  # 10 min timeout
        )
    except subprocess.TimeoutExpired:
        return safe_dumps({"error": "Simulation timed out after 600 seconds"})
    except Exception as e:
        return safe_dumps({"error": f"Failed to run simulation: {e}"})

    elapsed = round(_time.time() - t0, 2)

    # Find most recently modified output files
    # DSF uses get_unique_file() which creates output1.csv, output2.csv, etc.
    import glob
    csv_candidates = sorted(
        glob.glob(str(cwd / "output*.csv")),
        key=lambda f: os.path.getmtime(f), reverse=True
    )
    h5_candidates = sorted(
        glob.glob(str(cwd / "output*.h5")),
        key=lambda f: os.path.getmtime(f), reverse=True
    )
    output_csv = Path(csv_candidates[0]) if csv_candidates and os.path.getmtime(csv_candidates[0]) > t0 else None
    output_h5 = Path(h5_candidates[0]) if h5_candidates and os.path.getmtime(h5_candidates[0]) > t0 else None

    result = {
        "exit_code": proc.returncode,
        "wall_clock_seconds": elapsed,
        "xml_file": str(xml_path),
        "cwd": str(cwd),
        "ld_preload": env.get('LD_PRELOAD', ''),
    }

    if proc.stderr:
        result["stderr"] = proc.stderr[-1000:]
    if proc.stdout:
        result["stdout_tail"] = proc.stdout[-2000:]  # AP debug messages

    # Parse final state from CSV
    if output_csv and output_csv.exists():
        result["output_csv"] = str(output_csv)
        try:
            # Count lines and read last line
            with open(output_csv, 'r') as f:
                headers = next(f).strip().split(',')
                lines = f.readlines()
            result["n_samples"] = len(lines)
            if lines:
                last = lines[-1].strip().split(',')
                summary = {}
                for i, h in enumerate(headers):
                    h = h.strip()
                    if i < len(last):
                        try:
                            summary[h] = round(float(last[i]), 4)
                        except ValueError:
                            pass
                result["final_state"] = summary
        except Exception as e:
            result["csv_error"] = str(e)

    if output_h5 and output_h5.exists():
        result["output_h5"] = str(output_h5)

    return safe_dumps(result, indent=2)


@mcp.tool(name="dsf_run_sim_async")
@enforce_relative_paths
def run_sim_async(
    file: Annotated[str, Field(description="Relative path to a DSF XML configuration file")],
    library: Annotated[str, Field(description="Path to shared library. Empty = read from XML.")] = "",
) -> str:
    """Start a DSF simulation in the background and return immediately.

    Returns a job_id to pass to dsf_run_status and dsf_stop_run.

    Example:
        dsf_run_sim_async(xml_file="/path/to/sim.xml")
    """
    xml_file = file
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return safe_dumps({"error": f"XML file not found: {xml_file}"})

    try:
        cmd, env, cwd = _build_run_command(str(xml_path), library or None)
    except Exception as e:
        return safe_dumps({"error": str(e)})

    job_id = str(uuid.uuid4())[:8]
    log_path = cwd / f"sim_{job_id}.log"

    log_file = open(log_path, 'w')
    proc = subprocess.Popen(
        cmd, env=env, cwd=str(cwd),
        stdout=log_file, stderr=subprocess.STDOUT
    )

    _running_jobs[job_id] = {
        "proc": proc,
        "log_file": log_file,
        "log_path": str(log_path),
        "xml_file": str(xml_path),
        "cwd": str(cwd),
        "start_time": _time.time(),
    }

    return safe_dumps({
        "job_id": job_id,
        "pid": proc.pid,
        "log_path": str(log_path),
    }, indent=2)


@mcp.tool(name="dsf_run_status")
@enforce_relative_paths
def run_status(
    job_id: Annotated[str, Field(description="Job ID returned by dsf_run_sim_async")],
    tail_lines: Annotated[int, Field(description="Number of recent log lines to return")] = 30,
) -> str:
    """Check the status of a background simulation.

    Example:
        dsf_run_status(job_id="abc12345")
    """
    if job_id not in _running_jobs:
        return safe_dumps({"error": f"Unknown job_id: {job_id}"})

    job = _running_jobs[job_id]
    proc = job["proc"]
    elapsed = round(_time.time() - job["start_time"], 1)

    status = "running" if proc.poll() is None else "done"

    result = {
        "job_id": job_id,
        "status": status,
        "elapsed_seconds": elapsed,
    }

    if status == "done":
        result["exit_code"] = proc.returncode

    # Read log tail
    try:
        with open(job["log_path"], 'r') as f:
            lines = f.readlines()
        result["log_lines"] = len(lines)
        result["log_tail"] = "".join(lines[-tail_lines:])
    except Exception:
        result["log_tail"] = "(could not read log)"

    return safe_dumps(result, indent=2)


@mcp.tool(name="dsf_stop_run")
@enforce_relative_paths
def stop_run(
    job_id: Annotated[str, Field(description="Job ID returned by dsf_run_sim_async")],
) -> str:
    """Stop a running background simulation.

    Example:
        dsf_stop_run(job_id="abc12345")
    """
    if job_id not in _running_jobs:
        return safe_dumps({"error": f"Unknown job_id: {job_id}"})

    job = _running_jobs[job_id]
    proc = job["proc"]

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return safe_dumps({"job_id": job_id, "status": "terminated"})
    else:
        return safe_dumps({"job_id": job_id, "status": "already_done", "exit_code": proc.returncode})


# =========================================================================
# CSV Output Tools
# =========================================================================

@mcp.tool(name="dsf_get_headers_csv")
@enforce_relative_paths
def get_headers_csv(
    file: Annotated[str, Field(description="Relative path to a DSF CSV output file")],
) -> str:
    """List all column headers from a CSV output file.

    Example:
        dsf_get_headers_csv(csv_file="/path/to/output1.csv")
    """
    csv_file = file
    csv_path = Path(csv_file).resolve()
    if not csv_path.exists():
        return safe_dumps({"error": f"File not found: {csv_file}"})

    try:
        headers = _parse_csv_headers(str(csv_path))

        # Count rows
        with open(csv_path, 'r') as f:
            n_rows = sum(1 for _ in f) - 1  # subtract header

        return safe_dumps({
            "file": str(csv_path),
            "n_columns": len(headers),
            "n_rows": n_rows,
            "headers": headers,
        }, indent=2)
    except Exception as e:
        return safe_dumps({"error": str(e)})


@mcp.tool(name="dsf_get_timeseries_csv")
@enforce_relative_paths
def get_timeseries_csv(
    file: Annotated[str, Field(description="Relative path to a DSF CSV output file")],
    variables: Annotated[str, Field(description="Comma-separated column names (substring match). Empty = all columns.")] = "",
    t_start: Annotated[float, Field(description="Start time filter. -1 = no filter.")] = -1,
    t_end: Annotated[float, Field(description="End time filter. -1 = no filter.")] = -1,
    decimation: Annotated[int, Field(description="Return every Nth row. 1 = all rows.")] = 1,
) -> str:
    """Read timeseries data from a CSV output file.

    Example:
        dsf_get_timeseries_csv(csv_file="/path/to/output1.csv", variables="Altitude,Mach", decimation=10)
    """
    csv_file = file
    csv_path = Path(csv_file).resolve()
    if not csv_path.exists():
        return safe_dumps({"error": f"File not found: {csv_file}"})

    try:
        var_list = [v.strip() for v in variables.split(',') if v.strip()] if variables else None
        data = _read_csv_data(
            str(csv_path), var_list,
            t_start if t_start >= 0 else None,
            t_end if t_end >= 0 else None,
            max(1, decimation)
        )

        result = {"file": str(csv_path), "variables": {}}
        for name, values in data.items():
            clean = [v for v in values if v is not None]
            entry = {"n_points": len(clean)}
            if clean:
                entry["min"] = round(min(clean), 6)
                entry["max"] = round(max(clean), 6)
                entry["final"] = round(clean[-1], 6)
                entry["initial"] = round(clean[0], 6)
                # Only include full values array if < 500 points
                if len(clean) <= 500:
                    entry["values"] = [round(v, 6) for v in clean]
                else:
                    entry["values_truncated"] = True
                    entry["first_10"] = [round(v, 6) for v in clean[:10]]
                    entry["last_10"] = [round(v, 6) for v in clean[-10:]]
            result["variables"][name] = entry

        return safe_dumps(result, indent=2)
    except Exception as e:
        return safe_dumps({"error": str(e)})


# =========================================================================
# HDF5 Output Tools
# =========================================================================

@mcp.tool(name="dsf_get_headers_h5")
@enforce_relative_paths
def get_headers_h5(
    file: Annotated[str, Field(description="Relative path to a DSF HDF5 output file")],
) -> str:
    """List all dataset names from an HDF5 output file.

    Example:
        dsf_get_headers_h5(h5_file="/path/to/output1.h5")
    """
    h5_file = file
    h5_path = Path(h5_file).resolve()
    if not h5_path.exists():
        return safe_dumps({"error": f"File not found: {h5_file}"})

    try:
        import h5py
        with h5py.File(str(h5_path), 'r') as f:
            groups = {}
            flat_datasets = []

            def visit(name, obj):
                if isinstance(obj, h5py.Dataset):
                    parts = name.split('/')
                    if len(parts) > 1:
                        group = parts[0]
                        ds_name = '/'.join(parts[1:])
                        if group not in groups:
                            groups[group] = []
                        groups[group].append(ds_name)
                    else:
                        flat_datasets.append(name)

            f.visititems(visit)

        result = {"file": str(h5_path)}
        if groups:
            result["groups"] = {g: sorted(ds) for g, ds in groups.items()}
            result["total_datasets"] = sum(len(ds) for ds in groups.values())
        else:
            result["datasets"] = sorted(flat_datasets)
            result["total_datasets"] = len(flat_datasets)

        return safe_dumps(result, indent=2)
    except Exception as e:
        return safe_dumps({"error": str(e)})


@mcp.tool(name="dsf_get_timeseries_h5")
@enforce_relative_paths
def get_timeseries_h5(
    file: Annotated[str, Field(description="Relative path to a DSF HDF5 output file")],
    variables: Annotated[str, Field(description="Comma-separated dataset names (substring match). Empty = all.")] = "",
    group: Annotated[str, Field(description="HDF5 group name (e.g. vehicle name). Empty = auto-detect.")] = "",
    t_start: Annotated[float, Field(description="Start time filter. -1 = no filter.")] = -1,
    t_end: Annotated[float, Field(description="End time filter. -1 = no filter.")] = -1,
    decimation: Annotated[int, Field(description="Return every Nth point. 1 = all.")] = 1,
) -> str:
    """Read timeseries data from an HDF5 output file.

    Example:
        dsf_get_timeseries_h5(h5_file="/path/to/output1.h5", variables="Altitude,Mach")
    """
    h5_file = file
    h5_path = Path(h5_file).resolve()
    if not h5_path.exists():
        return safe_dumps({"error": f"File not found: {h5_file}"})

    try:
        from dsf.utils.data_loader import load_h5

        times, data = load_h5(str(h5_path))

        # Select group
        if group:
            if group not in data:
                return safe_dumps({"error": f"Group '{group}' not found",
                                   "available_groups": list(data.keys())})
            block_data = data[group]
        else:
            # Merge all groups if no specific one requested
            block_data = {}
            for g_data in data.values():
                block_data.update(g_data)

        # Apply time filter
        mask = np.ones(len(times), dtype=bool)
        if t_start >= 0:
            mask &= times >= t_start
        if t_end >= 0:
            mask &= times <= t_end
        if decimation > 1:
            dec_mask = np.zeros(len(times), dtype=bool)
            dec_mask[::decimation] = True
            mask &= dec_mask

        filtered_times = times[mask]

        # Select variables
        var_list = [v.strip() for v in variables.split(',') if v.strip()] if variables else list(block_data.keys())

        result = {"file": str(h5_path), "variables": {"time": {
            "n_points": len(filtered_times),
            "initial": round(float(filtered_times[0]), 4) if len(filtered_times) > 0 else None,
            "final": round(float(filtered_times[-1]), 4) if len(filtered_times) > 0 else None,
        }}}

        for var_pattern in var_list:
            # Substring match
            matched = [k for k in block_data.keys() if var_pattern.lower() in k.lower()]
            for name in matched:
                arr = block_data[name]
                if arr.ndim == 2:
                    # Vec3 — report components
                    for i, suffix in enumerate(['_x', '_y', '_z']):
                        comp = arr[mask, i]
                        entry = _build_ts_entry(comp)
                        result["variables"][f"{name}{suffix}"] = entry
                else:
                    comp = arr[mask]
                    entry = _build_ts_entry(comp)
                    result["variables"][name] = entry

        return safe_dumps(result, indent=2)
    except Exception as e:
        return safe_dumps({"error": str(e)})


def _build_ts_entry(arr: np.ndarray) -> dict:
    """Build a timeseries entry dict with stats and optionally values."""
    entry = {"n_points": len(arr)}
    if len(arr) > 0:
        entry["min"] = round(float(np.nanmin(arr)), 6)
        entry["max"] = round(float(np.nanmax(arr)), 6)
        entry["initial"] = round(float(arr[0]), 6)
        entry["final"] = round(float(arr[-1]), 6)
        if len(arr) <= 500:
            entry["values"] = [round(float(v), 6) for v in arr]
        else:
            entry["values_truncated"] = True
            entry["first_10"] = [round(float(v), 6) for v in arr[:10]]
            entry["last_10"] = [round(float(v), 6) for v in arr[-10:]]
    return entry


# =========================================================================
# XML Introspection Tools
# =========================================================================

@mcp.tool(name="dsf_inspect_xml")
@enforce_relative_paths
def inspect_xml(
    file: Annotated[str, Field(description="Relative path to a DSF XML configuration file")],
) -> str:
    """Parse a DSF XML configuration file and return its structure.

    Does NOT run the simulation — only reads the XML.

    Example:
        dsf_inspect_xml(xml_file="/path/to/sim.xml")
    """
    xml_file = file
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return safe_dumps({"error": f"File not found: {xml_file}"})

    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(xml_path))
        root = tree.getroot()

        result = {"file": str(xml_path)}

        # Find <sim> node
        sim_node = root if root.tag == 'sim' else root.find('.//sim')
        if sim_node is None:
            return safe_dumps({"error": "No <sim> element found"})

        # Sim settings
        result["sim_settings"] = {
            k: v for k, v in sim_node.attrib.items()
        }

        # Parse block hierarchy
        def parse_block(elem, depth=0):
            block = {
                "tag": elem.tag,
                "id": elem.get("id", ""),
                "class": elem.get("class", ""),
            }
            # Collect non-standard attributes as params
            params = {k: v for k, v in elem.attrib.items()
                     if k not in ("id", "class")}
            if params:
                block["params"] = params

            # Collect text content
            if elem.text and elem.text.strip():
                block["text"] = elem.text.strip()

            # Recurse children
            children = []
            for child in elem:
                children.append(parse_block(child, depth + 1))
            if children:
                block["children"] = children

            return block

        result["blocks"] = [parse_block(child) for child in sim_node]

        return safe_dumps(result, indent=2)
    except Exception as e:
        return safe_dumps({"error": str(e)})


# =========================================================================
# Summary Tool
# =========================================================================

@mcp.tool(name="dsf_get_summary")
@enforce_relative_paths
def get_summary(
    file: Annotated[str, Field(description="Relative path to a CSV or HDF5 output file")],
) -> str:
    """Get a compact statistical summary of a simulation output file.

    Supports both CSV and HDF5. Returns min/max/mean/initial/final per variable.

    Example:
        dsf_get_summary(output_file="/path/to/output1.csv")
    """
    output_file = file
    fpath = Path(output_file).resolve()
    if not fpath.exists():
        return safe_dumps({"error": f"File not found: {output_file}"})

    result = {"file": str(fpath), "format": fpath.suffix, "variables": {}}

    try:
        if fpath.suffix in ('.h5', '.hdf5'):
            from dsf.utils.data_loader import load_h5
            times, data = load_h5(str(fpath))
            result["n_samples"] = len(times)
            result["t_start"] = round(float(times[0]), 4) if len(times) > 0 else None
            result["t_end"] = round(float(times[-1]), 4) if len(times) > 0 else None

            for group, block_data in data.items():
                for name, arr in block_data.items():
                    key = f"{group}.{name}" if len(data) > 1 else name
                    if arr.ndim == 1:
                        result["variables"][key] = {
                            "min": round(float(np.nanmin(arr)), 4),
                            "max": round(float(np.nanmax(arr)), 4),
                            "mean": round(float(np.nanmean(arr)), 4),
                            "initial": round(float(arr[0]), 4),
                            "final": round(float(arr[-1]), 4),
                        }
        else:
            # CSV
            headers = _parse_csv_headers(str(fpath))
            data_dict = _read_csv_data(str(fpath))
            first_col = headers[0] if headers else "col0"
            time_vals = data_dict.get(first_col, [])
            result["n_samples"] = len(time_vals)
            if time_vals:
                result["t_start"] = round(time_vals[0], 4)
                result["t_end"] = round(time_vals[-1], 4)

            for name, values in data_dict.items():
                clean = [v for v in values if v is not None]
                if clean:
                    result["variables"][name] = {
                        "min": round(min(clean), 4),
                        "max": round(max(clean), 4),
                        "mean": round(sum(clean) / len(clean), 4),
                        "initial": round(clean[0], 4),
                        "final": round(clean[-1], 4),
                    }

        return safe_dumps(result, indent=2)
    except Exception as e:
        return safe_dumps({"error": str(e)})


# =========================================================================
# Watch (Live Introspection) Tools
# =========================================================================

def _watch_worker(job_id: str, xml_path: str, lib_path: str,
                  dt: float, tmax: float, watch_patterns: List[str]):
    """Background thread that drives the SimSession step loop."""
    # Must import dsf inside the thread after library is loaded
    sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)
    from dsf.utils.sim_session import SimSession

    session = SimSession(xml_path, lib_path, dt, tmax)
    try:
        session.build()
    except Exception as e:
        with _watch_lock:
            _watch_sessions[job_id]["error"] = str(e)
            _watch_sessions[job_id]["status"] = "error"
        return

    all_headers = session.headers()

    # Filter headers by watch patterns
    if watch_patterns:
        disp_headers = [h for h in all_headers
                        if any(w.lower() in h.lower() for w in watch_patterns)]
    else:
        disp_headers = all_headers

    header_indices = {h: i for i, h in enumerate(all_headers)}
    disp_indices = [header_indices[h] for h in disp_headers if h in header_indices]

    with _watch_lock:
        _watch_sessions[job_id]["session"] = session
        _watch_sessions[job_id]["headers"] = disp_headers
        _watch_sessions[job_id]["all_headers"] = all_headers
        _watch_sessions[job_id]["disp_indices"] = disp_indices
        _watch_sessions[job_id]["status"] = "running"

    while session.t() < tmax:
        # Check for stop signal
        with _watch_lock:
            if _watch_sessions[job_id].get("stop"):
                break

        session.step()

        # Update current values snapshot periodically
        with _watch_lock:
            vals = session.current_values()
            _watch_sessions[job_id]["current_time"] = session.t()
            _watch_sessions[job_id]["current_values"] = {
                disp_headers[i]: vals[disp_indices[i]]
                for i in range(len(disp_indices))
                if disp_indices[i] < len(vals)
            }

    with _watch_lock:
        _watch_sessions[job_id]["status"] = "done"
        session.finalize()


@mcp.tool(name="dsf_watch_sim")
@enforce_relative_paths
def watch_sim(
    file: Annotated[str, Field(description="Relative path to a DSF XML configuration file")],
    library: Annotated[str, Field(description="Relative path to shared library (required)")],
    watch: Annotated[str, Field(description="Comma-separated variable name patterns to track. Empty = all.")] = "",
    dt: Annotated[float, Field(description="Timestep in seconds. 0 = read from XML.")] = 0,
    tmax: Annotated[float, Field(description="End time in seconds. 0 = read from XML.")] = 0,
) -> str:
    """Start a simulation with per-step Python introspection.

    Runs in a background thread, allowing live variable queries via dsf_get_watch_state.

    Example:
        dsf_watch_sim(xml_file="/path/to/sim.xml", library="/path/to/libsixdof.so")
    """
    xml_file = file
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return safe_dumps({"error": f"XML file not found: {xml_file}"})

    lib_path = Path(library).resolve()
    if not lib_path.exists():
        return safe_dumps({"error": f"Library not found: {library}"})

    # Parse dt/tmax from XML if not provided
    if dt <= 0 or tmax <= 0:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        sim_node = root if root.tag == 'sim' else root.find('.//sim')
        if sim_node is not None:
            if dt <= 0:
                dt = float(sim_node.get('dt', '0.01'))
            if tmax <= 0:
                tmax = float(sim_node.get('tmax', '60'))

    watch_patterns = [w.strip() for w in watch.split(',') if w.strip()] if watch else []

    job_id = str(uuid.uuid4())[:8]

    with _watch_lock:
        _watch_sessions[job_id] = {
            "status": "starting",
            "xml_file": str(xml_path),
            "library": str(lib_path),
            "start_time": _time.time(),
            "current_time": 0.0,
            "current_values": {},
        }

    thread = threading.Thread(
        target=_watch_worker,
        args=(job_id, str(xml_path), str(lib_path), dt, tmax, watch_patterns),
        daemon=True
    )
    thread.start()

    with _watch_lock:
        _watch_sessions[job_id]["thread"] = thread

    return safe_dumps({
        "job_id": job_id,
        "xml_file": str(xml_path),
        "dt": dt,
        "tmax": tmax,
        "watch_patterns": watch_patterns,
    }, indent=2)


@mcp.tool(name="dsf_get_watch_state")
@enforce_relative_paths
def get_watch_state(
    job_id: Annotated[str, Field(description="Job ID returned by dsf_watch_sim")],
    variables: Annotated[str, Field(description="Comma-separated variable names to return. Empty = all watched.")] = "",
) -> str:
    """Query the current state of a running watch simulation.

    Example:
        dsf_get_watch_state(job_id="abc12345", variables="Altitude,Mach")
    """
    with _watch_lock:
        if job_id not in _watch_sessions:
            return safe_dumps({"error": f"Unknown job_id: {job_id}"})

        session_info = _watch_sessions[job_id]
        result = {
            "job_id": job_id,
            "status": session_info["status"],
            "sim_time": round(session_info.get("current_time", 0), 4),
            "elapsed_seconds": round(_time.time() - session_info["start_time"], 1),
        }

        if session_info.get("error"):
            result["error"] = session_info["error"]

        current_vals = session_info.get("current_values", {})

        if variables:
            var_list = [v.strip() for v in variables.split(',') if v.strip()]
            filtered = {}
            for v in var_list:
                # Substring match against available keys
                for k, val in current_vals.items():
                    if v.lower() in k.lower():
                        filtered[k] = round(val, 6) if isinstance(val, float) else val
            result["values"] = filtered
        else:
            result["values"] = {
                k: round(v, 6) if isinstance(v, float) else v
                for k, v in current_vals.items()
            }

        if session_info.get("headers"):
            result["n_watched"] = len(session_info["headers"])

        return safe_dumps(result, indent=2)


@mcp.tool(name="dsf_stop_watch")
@enforce_relative_paths
def stop_watch(
    job_id: Annotated[str, Field(description="Job ID returned by dsf_watch_sim")],
) -> str:
    """Stop a running watch simulation.

    Example:
        dsf_stop_watch(job_id="abc12345")
    """
    with _watch_lock:
        if job_id not in _watch_sessions:
            return safe_dumps({"error": f"Unknown job_id: {job_id}"})
        _watch_sessions[job_id]["stop"] = True

    return safe_dumps({"job_id": job_id, "status": "stop_signaled"})


# =========================================================================
# List Jobs
# =========================================================================

@mcp.tool(name="dsf_list_jobs")
@enforce_relative_paths
def list_jobs() -> str:
    """List all known DSF simulation jobs (running and completed).

    Example:
        dsf_list_jobs()
    """
    result = {"async_jobs": {}, "watch_jobs": {}}

    for jid, job in _running_jobs.items():
        proc = job["proc"]
        result["async_jobs"][jid] = {
            "status": "running" if proc.poll() is None else "done",
            "xml_file": job["xml_file"],
            "elapsed": round(_time.time() - job["start_time"], 1),
        }

    with _watch_lock:
        for jid, session in _watch_sessions.items():
            result["watch_jobs"][jid] = {
                "status": session["status"],
                "sim_time": round(session.get("current_time", 0), 4),
                "elapsed": round(_time.time() - session["start_time"], 1),
            }

    return safe_dumps(result, indent=2)


# =========================================================================
# Plotting Tools
# =========================================================================

@mcp.tool(name="dsf_plot_timeseries_csv")
@enforce_relative_paths
def plot_timeseries_csv(
    file: Annotated[str, Field(description="Relative path to a DSF CSV output file")],
    variables: Annotated[str, Field(description="Comma-separated column names (substring match) to plot")],
    output: Annotated[str, Field(description="Path to save the plot image (e.g. 'plot.png'). Empty = auto-generate.")] = "",
) -> str:
    """Plot timeseries data from a CSV output file and save to an image.

    Example:
        dsf_plot_timeseries_csv(csv_file="/path/to/output1.csv", variables="Altitude,Mach", out_file="/tmp/plot.png")
    """
    csv_file = file
    out_file = output
    import matplotlib
    matplotlib.use('Agg')  # Prevent GUI popups that could hang the server
    import matplotlib.pyplot as plt
    from pathlib import Path
    import json
    import time
    
    fpath = Path(csv_file).resolve()
    if not fpath.exists():
        return safe_dumps({"error": f"File not found: {csv_file}"})
        
    try:
        headers = _parse_csv_headers(str(fpath))
        data_dict = _read_csv_data(str(fpath))
        
        if not headers or not data_dict:
            return safe_dumps({"error": "No data found or empty CSV"})
            
        time_col = headers[0]
        times = data_dict.get(time_col, [])
        
        var_list = [v.strip() for v in variables.split(',') if v.strip()]
        if not var_list:
            return safe_dumps({"error": "No variables provided to plot"})
            
        # Find matching columns
        cols_to_plot = []
        for v in var_list:
            matched = [h for h in headers if v.lower() in h.lower() and h != time_col]
            cols_to_plot.extend(matched)
            
        # Remove duplicates preserving order
        cols_to_plot = list(dict.fromkeys(cols_to_plot))
        
        if not cols_to_plot:
            return safe_dumps({"error": f"No matching columns found for variables: {variables}", "available": headers})
            
        fig, axs = plt.subplots(len(cols_to_plot), 1, figsize=(10, 3 * len(cols_to_plot)), sharex=True)
        if len(cols_to_plot) == 1:
            axs = [axs]
            
        for ax, col in zip(axs, cols_to_plot):
            vals = data_dict[col]
            ax.plot(times, vals, label=col)
            ax.set_ylabel(col)
            ax.grid(True)
            ax.legend()
            
        axs[-1].set_xlabel(time_col)
        fig.suptitle(f"Timeseries Plot: {fpath.name}")
        plt.tight_layout()
        
        if not out_file:
            timestamp = int(time.time())
            out_path = fpath.parent / f"{fpath.stem}_plot_{timestamp}.png"
        else:
            out_path = Path(out_file).resolve()
            
        fig.savefig(str(out_path))
        plt.close(fig)
        
        return safe_dumps({"file": str(out_path), "plotted_variables": cols_to_plot})
        
    except Exception as e:
        return safe_dumps({"error": str(e)})


# =========================================================================
# Analysis & Tuning Tools
# =========================================================================

@mcp.tool(name="dsf_compare_runs_csv")
@enforce_relative_paths
def compare_runs_csv(
    file_a: Annotated[str, Field(description="Relative path to the first (baseline) CSV output file")],
    file_b: Annotated[str, Field(description="Relative path to the second (modified) CSV output file")],
    variables: Annotated[str, Field(description="Comma-separated column names (substring match) to compare")],
) -> str:
    """Compare two simulation CSV outputs and return min/max/RMS differences.

    Example:
        dsf_compare_runs_csv(csv_file1="/path/to/baseline.csv", csv_file2="/path/to/modified.csv", variables="Altitude,Mach")
    """
    csv_file1 = file_a
    csv_file2 = file_b
    from pathlib import Path
    import json
    fpath1 = Path(csv_file1).resolve()
    fpath2 = Path(csv_file2).resolve()
    
    if not fpath1.exists():
        return safe_dumps({"error": f"File not found: {csv_file1}"})
    if not fpath2.exists():
        return safe_dumps({"error": f"File not found: {csv_file2}"})
        
    try:
        headers1 = _parse_csv_headers(str(fpath1))
        data1 = _read_csv_data(str(fpath1))
        headers2 = _parse_csv_headers(str(fpath2))
        data2 = _read_csv_data(str(fpath2))
        
        var_list = [v.strip() for v in variables.split(',') if v.strip()]
        if not var_list:
            return safe_dumps({"error": "No variables provided"})
            
        result = {"file1": str(fpath1), "file2": str(fpath2), "comparisons": {}}
        
        for v in var_list:
            col1 = next((h for h in headers1 if v.lower() in h.lower()), None)
            col2 = next((h for h in headers2 if v.lower() in h.lower()), None)
            
            if col1 and col2 and col1 in data1 and col2 in data2:
                vals1 = [x for x in data1[col1] if x is not None]
                vals2 = [x for x in data2[col2] if x is not None]
                
                if not vals1 or not vals2:
                    continue
                    
                s1 = {
                    "min": min(vals1), "max": max(vals1), 
                    "span": max(vals1) - min(vals1),
                    "mean": sum(vals1)/len(vals1),
                    "final": vals1[-1]
                }
                s2 = {
                    "min": min(vals2), "max": max(vals2),
                    "span": max(vals2) - min(vals2),
                    "mean": sum(vals2)/len(vals2),
                    "final": vals2[-1]
                }
                
                diffs = {k: round(s2[k] - s1[k], 6) for k in s1}
                result["comparisons"][v] = {
                    "matched_col1": col1, "matched_col2": col2,
                    "baseline": {k: round(v, 6) for k, v in s1.items()},
                    "modified": {k: round(v, 6) for k, v in s2.items()},
                    "delta (mod-base)": diffs
                }
                
        return safe_dumps(result, indent=2)
    except Exception as e:
        return safe_dumps({"error": str(e)})


@mcp.tool(name="dsf_extract_events")
@enforce_relative_paths
def extract_events(
    file: Annotated[str, Field(description="Relative path to a DSF CSV output file")],
    variable: Annotated[str, Field(description="Column name (or substring) to evaluate")],
    operator: Annotated[str, Field(description="Comparison operator: '>', '<', '>=', '<=', '==', '!=', or 'crosses'")],
    threshold: Annotated[float, Field(description="Numeric threshold value to compare against")],
) -> str:
    """Find timestamps in a CSV where a condition becomes true (crosses threshold).

    Example:
        dsf_extract_events(csv_file="/path/to/output1.csv", variable="Altitude", operator_str="<", threshold=0)
    """
    csv_file = file
    operator_str = operator
    from pathlib import Path
    import json
    fpath = Path(csv_file).resolve()
    if not fpath.exists():
        return safe_dumps({"error": f"File not found: {csv_file}"})
        
    try:
        headers = _parse_csv_headers(str(fpath))
        data = _read_csv_data(str(fpath))
        
        if not headers:
            return safe_dumps({"error": "Empty CSV / No headers"})
            
        time_col = headers[0]
        times = data.get(time_col, [])
        
        col = next((h for h in headers if variable.lower() in h.lower() and h != time_col), None)
        if not col or col not in data:
            return safe_dumps({"error": f"Variable matching '{variable}' not found."})
            
        vals = data[col]
        events = []
        
        for i in range(1, len(vals)):
            if vals[i] is None or vals[i-1] is None:
                continue
                
            v_prev = vals[i-1]
            v_curr = vals[i]
            t_curr = times[i]
            
            triggered = False
            if operator_str == '>': triggered = v_prev <= threshold < v_curr
            elif operator_str == '<': triggered = v_prev >= threshold > v_curr
            elif operator_str == '>=': triggered = v_prev < threshold <= v_curr
            elif operator_str == '<=': triggered = v_prev > threshold >= v_curr
            elif operator_str == '==': triggered = v_prev != threshold and v_curr == threshold
            elif operator_str == '!=': triggered = v_prev == threshold and v_curr != threshold
            elif operator_str == 'crosses': triggered = (v_prev < threshold <= v_curr) or (v_prev > threshold >= v_curr)
            
            if i == 1:
                init_trig = False
                if operator_str in ('>', '>=') and v_prev >= threshold: init_trig = True
                elif operator_str in ('<', '<=') and v_prev <= threshold: init_trig = True
                elif operator_str == '==' and v_prev == threshold: init_trig = True
                elif operator_str == '!=' and v_prev != threshold: init_trig = True
                if init_trig:
                    events.append({"time": times[0], "value": v_prev, "type": "initial_state"})
                    
            if triggered:
                events.append({"time": t_curr, "value": v_curr, "type": "transition"})
                
        return safe_dumps({
            "file": str(fpath),
            "variable": col,
            "operator": operator_str,
            "threshold": threshold,
            "events_found": len(events),
            "events": events
        }, indent=2)
    except Exception as e:
        return safe_dumps({"error": str(e)})


@mcp.tool(name="dsf_patch_run_xml")
@enforce_relative_paths
def patch_run_xml(
    file: Annotated[str, Field(description="Relative path to the baseline DSF XML configuration file")],
    xpath: Annotated[str, Field(description="ElementTree XPath to the node to modify, e.g. './/block[@id=\"AltHold\"]'")],
    attributes: Annotated[str, Field(description="JSON string of attribute key-value pairs to set, e.g. '{\"Kp\": \"0.5\"}'")],
    output: Annotated[str, Field(description="Path to save patched XML. Empty = <stem>_patched.xml.")] = "",
    library: Annotated[str, Field(description="Path to shared library. Empty = read from XML.")] = "",
    tmax: Annotated[float, Field(description="Override simulation end time. 0 = use XML value.")] = 0,
) -> str:
    """Modify an XML file at the given xpath, save it, run the simulation, and return results.

    Example:
        dsf_patch_run_xml(xml_file="/path/to/sim.xml", xpath=".//fcs[@id='F16FCS']", attributes='{"Kp_h": "0.01"}')
    """
    xml_file = file
    out_file = output
    from pathlib import Path
    import json
    import xml.etree.ElementTree as ET
    
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return safe_dumps({"error": f"File not found: {xml_file}"})
        
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        
        node = root.find(xpath)
        if node is None:
            return safe_dumps({"error": f"Node not found for xpath: {xpath}"})
            
        try:
            attrs = json.loads(attributes)
        except json.JSONDecodeError as e:
            return safe_dumps({"error": f"Failed to parse attributes JSON: {e}"})
            
        for k, v in attrs.items():
            node.set(k, str(v))
            
        if not out_file:
            out_path = xml_path.parent / f"{xml_path.stem}_patched.xml"
        else:
            out_path = Path(out_file).resolve()
            
        tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
        
        # We process the simulation synchronously. run_sim is wrapped by
        # normalize_args (a **kwargs-only wrapper), so it must be called with
        # keyword arguments — positional args raise TypeError.
        return run_sim(file=str(out_path), library=library, tmax=tmax)
    except Exception as e:
        return safe_dumps({"error": str(e)})

# =========================================================================
# Build Tools
# =========================================================================

_BUILD_DIRS = {
    "sixdof": "/home/philip/git/sixdof/build",
    "dsf":    "/home/philip/git/DSF/build",
}

@mcp.tool(name="dsf_build")
@enforce_relative_paths
def build(
    project: Annotated[str, Field(description="Project to build: 'sixdof' (default), 'dsf', or 'both'")] = "sixdof",
    action: Annotated[str, Field(description="Build action: 'build' (default), 'clean', 'rebuild' (clean+build), 'cmake' (reconfigure+build)")] = "build",
    build_dir: Annotated[str, Field(description="Override build directory. Empty = use project default.")] = "",
) -> str:
    """Build the sixdof or DSF shared libraries.

    Projects:
      - sixdof: builds libsixdof.so (vehicle models, EOM, aero, hydro)
      - dsf:    builds DSF core (sim engine, integrators, I/O)
      - both:   builds DSF first, then sixdof (dependency order)

    Actions:
      - build:   Incremental build (make -j)
      - clean:   Remove build artifacts (make clean)
      - rebuild: Clean then build
      - cmake:   Re-run cmake then build

    Example:
        dsf_build()                              # incremental sixdof build
        dsf_build(project="dsf", action="cmake") # reconfigure DSF
        dsf_build(project="both")                # build everything
    """
    import multiprocessing
    nproc = multiprocessing.cpu_count()

    # Determine which project(s) to build
    if build_dir:
        targets = [("custom", Path(build_dir).resolve())]
    elif project == "both":
        targets = [("dsf", Path(_BUILD_DIRS["dsf"])), ("sixdof", Path(_BUILD_DIRS["sixdof"]))]
    elif project in _BUILD_DIRS:
        targets = [(project, Path(_BUILD_DIRS[project]))]
    else:
        return safe_dumps({"error": f"Unknown project '{project}'. Use 'sixdof', 'dsf', or 'both'."})

    all_results = {}
    overall_success = True
    t0 = _time.time()

    for proj_name, build_path in targets:
        if not build_path.exists():
            all_results[proj_name] = {"error": f"Build directory not found: {build_path}"}
            overall_success = False
            continue

        # Build the step list
        steps = []
        if action == "clean":
            steps = [["make", "clean"]]
        elif action == "rebuild":
            steps = [["make", "clean"], ["make", f"-j{nproc}"]]
        elif action == "cmake":
            src_dir = str(build_path.parent)
            steps = [["cmake", src_dir], ["make", f"-j{nproc}"]]
        else:
            steps = [["make", f"-j{nproc}"]]

        step_results = []
        for cmd in steps:
            try:
                proc = subprocess.run(
                    cmd, cwd=str(build_path),
                    capture_output=True, text=True, timeout=120
                )
                step_result = {
                    "cmd": " ".join(cmd),
                    "exit_code": proc.returncode,
                }
                if proc.stdout:
                    step_result["stdout_tail"] = proc.stdout[-2000:]
                if proc.stderr:
                    step_result["stderr_tail"] = proc.stderr[-2000:]
                step_results.append(step_result)

                if proc.returncode != 0:
                    overall_success = False
                    break
            except subprocess.TimeoutExpired:
                step_results.append({"cmd": " ".join(cmd), "error": "Timed out after 120s"})
                overall_success = False
                break
            except Exception as e:
                step_results.append({"cmd": " ".join(cmd), "error": str(e)})
                overall_success = False
                break

        all_results[proj_name] = {"steps": step_results}

        # Stop building further projects if one failed
        if not overall_success:
            break

    elapsed = round(_time.time() - t0, 2)

    return safe_dumps({
        "success": overall_success,
        "action": action,
        "wall_clock_seconds": elapsed,
        "projects": all_results,
    }, indent=2)


# =========================================================================
# Report Tool
# =========================================================================

def _select_plot_variables(headers: List[str], data: Dict) -> List[str]:
    """Auto-select interesting variables to plot from available headers.

    Priority order:
    1. Altitude / height-like variables
    2. Velocity / speed / Mach
    3. Angular rates / attitudes
    4. Position components
    5. Miss distance / range
    Falls back to first N non-time numeric columns.
    """
    priority_patterns = [
        # altitude / height
        ['altitude', 'alt', 'height', 'h_msl', 'h_agl', 'z_geo'],
        # velocity / speed / mach
        ['velocity', 'speed', 'mach', 'v_mag', 'vt', 'airspeed'],
        # acceleration / load factor
        ['accel', 'load_factor', 'nz', 'g_load', 'az'],
        # angles / attitudes
        ['alpha', 'beta', 'gamma', 'theta', 'phi', 'psi', 'aoa',
         'flight_path', 'heading'],
        # position / range
        ['range', 'miss_distance', 'downrange', 'crossrange'],
    ]

    selected = []
    used = set()
    lc_headers = {h.lower().strip(): h for h in headers}

    for pattern_group in priority_patterns:
        for pat in pattern_group:
            for lc_name, orig_name in lc_headers.items():
                if pat in lc_name and orig_name not in used:
                    # Check it has real data
                    vals = data.get(orig_name, [])
                    clean = [v for v in vals if v is not None]
                    if clean and max(clean) != min(clean):  # non-constant
                        selected.append(orig_name)
                        used.add(orig_name)
                        break  # one per pattern group
            if any(h in used for h in [lc_headers.get(p) for p in pattern_group if p in lc_headers]):
                break

    # If we didn't find enough, grab first non-time varying columns
    if len(selected) < 3:
        time_names = {'time', 't', 'time (s)', 'time(s)'}
        for h in headers:
            if h.lower().strip() in time_names or h in used:
                continue
            vals = data.get(h, [])
            clean = [v for v in vals if v is not None]
            if clean and len(clean) > 1 and max(clean) != min(clean):
                selected.append(h)
                used.add(h)
            if len(selected) >= 6:
                break

    return selected[:6]  # max 6 subplots


def _generate_report_plot(output_path: str, plot_path: str,
                          variables: List[str] = None) -> str:
    """Generate a multi-panel timeseries plot for the report.

    Supports both CSV and HDF5 output files. Auto-selects variables
    if none are specified.

    Returns the path to the saved plot image.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fpath = Path(output_path).resolve()
    suffix = fpath.suffix.lower()

    if suffix in ('.h5', '.hdf5'):
        from dsf.utils.data_loader import load_h5
        times_arr, raw = load_h5(str(fpath))
        # Flatten to {name: array}
        flat_data = {}
        for block, props in raw.items():
            for name, arr in props.items():
                key = f"{block}.{name}" if len(raw) > 1 else name
                if arr.ndim == 2:
                    for i, sfx in enumerate(['_x', '_y', '_z']):
                        flat_data[f"{key}{sfx}"] = arr[:, i].tolist()
                else:
                    flat_data[key] = arr.tolist()
        times = times_arr.tolist()
        all_headers = list(flat_data.keys())
        data_dict = flat_data
        data_dict['time'] = times
    else:
        all_headers = _parse_csv_headers(str(fpath))
        data_dict = _read_csv_data(str(fpath))
        time_col = all_headers[0] if all_headers else 'time'
        times = data_dict.get(time_col, [])

    if variables:
        # Substring match
        cols_to_plot = []
        for v in variables:
            matched = [h for h in all_headers
                       if v.lower() in h.lower() and h.lower() not in ('time', 't')]
            cols_to_plot.extend(matched)
        cols_to_plot = list(dict.fromkeys(cols_to_plot))
    else:
        cols_to_plot = _select_plot_variables(all_headers, data_dict)

    if not cols_to_plot:
        return ""

    n = len(cols_to_plot)
    fig, axs = plt.subplots(n, 1, figsize=(12, 2.8 * n), sharex=True)
    if n == 1:
        axs = [axs]

    colors = plt.cm.tab10.colors

    for i, (ax, col) in enumerate(zip(axs, cols_to_plot)):
        vals = data_dict.get(col, [])
        ax.plot(times[:len(vals)], vals, color=colors[i % len(colors)],
                linewidth=1.2, label=col)
        ax.set_ylabel(col, fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=8)
        ax.tick_params(labelsize=8)

    axs[-1].set_xlabel('Time (s)', fontsize=10)
    fig.suptitle(f'DSF Simulation Report: {fpath.name}', fontsize=12, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    out = Path(plot_path).resolve()
    fig.savefig(str(out), dpi=150, bbox_inches='tight')
    plt.close(fig)
    return str(out)


@mcp.tool(name="dsf_report")
@enforce_relative_paths
def build_report(
    file: Annotated[str, Field(description="Relative path to the DSF XML configuration file")],
    output_file: Annotated[str, Field(description="Path to the output CSV or HDF5 file. Empty = auto-detect most recent output next to XML.")] = "",
) -> str:
    """Generate a comprehensive simulation report with plots from a DSF run.

    Aggregates XML configuration, per-vehicle/block statistics, key events,
    and generates a multi-panel timeseries plot. Returns structured JSON
    with a workflow_hint for formatting as a markdown report.

    Example:
        dsf_report(xml_file="/path/to/sim.xml")
        dsf_report(xml_file="/path/to/sim.xml", output_file="/path/to/output1.csv")
    """
    xml_file = file
    # NB: do NOT overwrite output_file with the XML path — that made the report
    # try to parse the .xml as CSV and disabled auto-detection of the real output.
    import xml.etree.ElementTree as ET
    import glob

    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return safe_dumps({"error": f"XML file not found: {xml_file}"})

    # ── Parse XML configuration ──
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
    except Exception as e:
        return safe_dumps({"error": f"Failed to parse XML: {e}"})

    sim_node = root if root.tag == 'sim' else root.find('.//sim')
    if sim_node is None:
        return safe_dumps({"error": "No <sim> element found in XML"})

    # Extract sim settings
    sim_settings = dict(sim_node.attrib)
    dt = float(sim_settings.get('dt', '0.01'))
    tmax = float(sim_settings.get('tmax', '0'))
    library = sim_settings.get('library', '')
    output_format = sim_settings.get('output', 'csv')

    # Extract block hierarchy
    vehicles = []
    blocks_flat = []
    for child in sim_node:
        block_info = {
            "tag": child.tag,
            "id": child.get("id", ""),
            "class": child.get("class", ""),
        }
        params = {k: v for k, v in child.attrib.items() if k not in ("id", "class")}
        if params:
            block_info["params"] = params

        # Count sub-blocks
        sub_blocks = []
        for sub in child:
            sub_info = {
                "tag": sub.tag,
                "id": sub.get("id", ""),
                "class": sub.get("class", ""),
            }
            sub_params = {k: v for k, v in sub.attrib.items() if k not in ("id", "class")}
            if sub_params:
                sub_info["params"] = sub_params
            sub_blocks.append(sub_info)

        block_info["sub_blocks"] = sub_blocks

        if child.tag == "vehicle":
            vehicles.append(block_info)
        blocks_flat.append(block_info)

    # ── Locate output file ──
    xml_dir = xml_path.parent
    out_path = None

    if output_file:
        out_path = Path(output_file).resolve()
        if not out_path.exists():
            return safe_dumps({"error": f"Output file not found: {output_file}"})
    else:
        # Auto-detect: look for most recent output file next to XML
        for pattern in ['output*.h5', 'output*.hdf5', 'output*.csv']:
            candidates = sorted(
                glob.glob(str(xml_dir / pattern)),
                key=lambda f: os.path.getmtime(f), reverse=True
            )
            if candidates:
                out_path = Path(candidates[0])
                break

    if out_path is None or not out_path.exists():
        return safe_dumps({"error": "No output file found. Run the simulation first."})

    # ── Read output data and build per-block summary ──
    suffix = out_path.suffix.lower()
    block_summaries = {}
    all_variables = {}
    n_samples = 0
    t_start = 0.0
    t_end = 0.0

    try:
        if suffix in ('.h5', '.hdf5'):
            from dsf.utils.data_loader import load_h5
            times, data = load_h5(str(out_path))
            n_samples = len(times)
            t_start = round(float(times[0]), 4) if len(times) > 0 else 0
            t_end = round(float(times[-1]), 4) if len(times) > 0 else 0

            for block_id, props in data.items():
                block_vars = {}
                for name, arr in props.items():
                    if arr.ndim == 2:
                        # Vec3 — summarize magnitude
                        mag = np.linalg.norm(arr, axis=1)
                        block_vars[name] = {
                            "initial": [round(float(arr[0, i]), 4) for i in range(3)],
                            "final": [round(float(arr[-1, i]), 4) for i in range(3)],
                            "mag_min": round(float(np.nanmin(mag)), 4),
                            "mag_max": round(float(np.nanmax(mag)), 4),
                        }
                        # Also add to flat all_variables for plotting
                        for i, sfx in enumerate(['_x', '_y', '_z']):
                            key = f"{block_id}.{name}{sfx}" if len(data) > 1 else f"{name}{sfx}"
                            all_variables[key] = arr[:, i].tolist()
                    else:
                        block_vars[name] = {
                            "min": round(float(np.nanmin(arr)), 4),
                            "max": round(float(np.nanmax(arr)), 4),
                            "mean": round(float(np.nanmean(arr)), 4),
                            "initial": round(float(arr[0]), 4),
                            "final": round(float(arr[-1]), 4),
                        }
                        key = f"{block_id}.{name}" if len(data) > 1 else name
                        all_variables[key] = arr.tolist()
                block_summaries[block_id] = block_vars
        else:
            # CSV
            headers = _parse_csv_headers(str(out_path))
            data_dict = _read_csv_data(str(out_path))
            time_col = headers[0] if headers else "time"
            time_vals = data_dict.get(time_col, [])
            n_samples = len(time_vals)
            t_start = round(time_vals[0], 4) if time_vals else 0
            t_end = round(time_vals[-1], 4) if time_vals else 0

            # Group by block prefix (dot notation: Block.Property)
            for name, values in data_dict.items():
                clean = [v for v in values if v is not None]
                if not clean:
                    continue
                all_variables[name] = values

                parts = name.split('.')
                if len(parts) >= 2:
                    block_id = parts[0]
                    prop_name = '.'.join(parts[1:])
                else:
                    block_id = "simulation"
                    prop_name = name

                if block_id not in block_summaries:
                    block_summaries[block_id] = {}

                block_summaries[block_id][prop_name] = {
                    "min": round(min(clean), 4),
                    "max": round(max(clean), 4),
                    "mean": round(sum(clean) / len(clean), 4),
                    "initial": round(clean[0], 4),
                    "final": round(clean[-1], 4),
                }

    except Exception as e:
        return safe_dumps({"error": f"Failed to read output file: {e}"})

    # ── Generate report plot ──
    plot_path = out_path.parent / f"{xml_path.stem}_report.png"
    try:
        generated_plot = _generate_report_plot(str(out_path), str(plot_path))
    except Exception as e:
        generated_plot = ""

    # ── Extract description from XML comments ──
    description = ""
    try:
        with open(str(xml_path), 'r') as f:
            content = f.read()
        # Find first XML comment block
        import re
        match = re.search(r'<!--\s*(.*?)\s*-->', content, re.DOTALL)
        if match:
            desc_lines = match.group(1).strip().split('\n')
            description = '\n'.join(line.strip() for line in desc_lines)
    except Exception:
        pass

    # ── Assemble report ──
    result = {
        "_workflow_hint": (
            "Format this data into a simulation analysis report using the "
            "dsf-report workflow at .agents/workflows/dsf-report.md"
        ),
        "simulation": {
            "name": xml_path.stem,
            "description": description,
            "xml_file": str(xml_path),
            "output_file": str(out_path),
            "output_format": output_format,
            "dt": dt,
            "tmax": tmax,
            "library": library,
        },
        "configuration": {
            "num_vehicles": len(vehicles),
            "num_blocks": len(blocks_flat),
            "vehicles": vehicles,
            "blocks": blocks_flat,
        },
        "results": {
            "n_samples": n_samples,
            "t_start": t_start,
            "t_end": t_end,
            "t_actual_vs_tmax": "complete" if abs(t_end - tmax) < dt * 2 else f"early_termination (t_end={t_end}, tmax={tmax})",
        },
        "block_summaries": block_summaries,
        "plot_file": generated_plot,
    }

    return safe_dumps(_np_to_python(result), indent=2)



# =========================================================================
# File System Operations
# =========================================================================

@mcp.tool()
def dsf_read_file(relative_path: Annotated[str, Field(description="Relative path from the sixdof workspace root")]) -> str:
    """Read a text file, script, or XML deck from the DSF repository."""
    try:
        p = Path(resolve_path(relative_path))
        if not p.exists():
            return f"Error: File '{relative_path}' does not exist."
        if not p.is_file():
            return f"Error: '{relative_path}' is a directory, not a file."
        return p.read_text(encoding='utf-8')
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def dsf_write_file(relative_path: Annotated[str, Field(description="Relative path from the sixdof workspace root")], content: str) -> str:
    """Create a new file or completely overwrite an existing file on DSF.
    If directories in the path do not exist, they will be created."""
    try:
        p = Path(resolve_path(relative_path))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return f"Successfully wrote {relative_path}"
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def dsf_search_replace(relative_path: Annotated[str, Field(description="Relative path from the sixdof workspace root")], target: str, replacement: str) -> str:
    """Find a specific string in a file on DSF and replace it. 
    The target string must match exactly, including leading spaces/tabs."""
    try:
        p = Path(resolve_path(relative_path))
        if not p.exists():
            return f"Error: File '{relative_path}' does not exist."
        file_str = p.read_text(encoding='utf-8')
        if target not in file_str:
            return "Error: Target string not found exactly"
        file_str = file_str.replace(target, replacement)
        p.write_text(file_str, encoding='utf-8')
        return f"Successfully replaced target in {relative_path}"
    except Exception as e:
        return f"Error: {e}"

# =========================================================================
# Entry point
# =========================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DSF MCP Server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"],
                        help="Transport mode: stdio (default) or sse")
    # Bind to loopback by default. This server exposes file-write and build
    # tools; combined with the `library` LD_PRELOAD path that is an unauthenticated
    # RCE surface if bound to 0.0.0.0. Remote exposure must be opted into
    # explicitly and should sit behind an authenticating proxy.
    parser.add_argument("--host", default="127.0.0.1",
                        help="SSE host (default: 127.0.0.1 / loopback)")
    parser.add_argument("--port", type=int, default=9100, help="SSE port (default: 9100)")
    parser.add_argument("--allow-remote", action="store_true",
                        help="Permit binding to a non-loopback host (e.g. 0.0.0.0). "
                             "Only use behind an authenticating reverse proxy.")
    args = parser.parse_args()

    if args.transport == "sse":
        loopback = args.host in ("127.0.0.1", "localhost", "::1")
        if not loopback and not args.allow_remote:
            parser.error(
                f"refusing to bind SSE transport to non-loopback host '{args.host}' "
                "without --allow-remote (this server exposes file-write/build tools). "
                "Put it behind an authenticating proxy and pass --allow-remote to override."
            )
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        # DNS-rebinding protection is only relaxed for explicit remote use.
        from mcp.server.transport_security import TransportSecuritySettings
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=(not args.allow_remote)
        )
    mcp.run(transport=args.transport)

