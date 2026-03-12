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

mcp = FastMCP("dsf", instructions="DSF simulation framework tools for running sims, reading output, and live introspection")

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
    conda_lib = "/opt/miniconda3/envs/DSF/lib"
    current_ld = env.get('LD_LIBRARY_PATH', '')
    if conda_lib not in current_ld:
        env['LD_LIBRARY_PATH'] = f"{conda_lib}:{current_ld}" if current_ld else conda_lib

    if lib_path:
        existing_preload = env.get('LD_PRELOAD', '')
        if lib_path not in existing_preload:
            env['LD_PRELOAD'] = f"{lib_path}:{existing_preload}" if existing_preload else lib_path

    # Find the dynamic executable
    dynamic_exe = "/home/philip/git/DSF/build/examples/dynamic/dynamic"
    if not os.path.exists(dynamic_exe):
        raise FileNotFoundError(f"DSF dynamic executable not found at {dynamic_exe}")

    cmd = [dynamic_exe, str(xml_path)]
    return cmd, env, xml_dir


# =========================================================================
# Simulation Execution Tools
# =========================================================================

@mcp.tool(name="dsf_run_sim")
def run_sim(
    xml_file: Annotated[str, Field(description="Absolute path to a DSF XML configuration file")],
    library: Annotated[str, Field(description="Path to shared library (e.g. libsixdof.so). Empty = read from XML.")] = "",
    tmax: Annotated[float, Field(description="Override simulation end time in seconds. 0 = use XML value.")] = 0,
) -> str:
    """Run a DSF simulation from an XML configuration file and return results.

    Example:
        dsf_run_sim(xml_file="/path/to/sim.xml", library="/path/to/libsixdof.so")
    """
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return json.dumps({"error": f"XML file not found: {xml_file}"})

    try:
        cmd, env, cwd = _build_run_command(str(xml_path), library or None)
    except Exception as e:
        return json.dumps({"error": str(e)})

    t0 = _time.time()
    try:
        proc = subprocess.run(
            cmd, env=env, cwd=str(cwd),
            capture_output=True, text=True, timeout=600  # 10 min timeout
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Simulation timed out after 600 seconds"})
    except Exception as e:
        return json.dumps({"error": f"Failed to run simulation: {e}"})

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

    return json.dumps(result, indent=2)


@mcp.tool(name="dsf_run_sim_async")
def run_sim_async(
    xml_file: Annotated[str, Field(description="Absolute path to a DSF XML configuration file")],
    library: Annotated[str, Field(description="Path to shared library. Empty = read from XML.")] = "",
) -> str:
    """Start a DSF simulation in the background and return immediately.

    Returns a job_id to pass to dsf_run_status and dsf_stop_run.

    Example:
        dsf_run_sim_async(xml_file="/path/to/sim.xml")
    """
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return json.dumps({"error": f"XML file not found: {xml_file}"})

    try:
        cmd, env, cwd = _build_run_command(str(xml_path), library or None)
    except Exception as e:
        return json.dumps({"error": str(e)})

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

    return json.dumps({
        "job_id": job_id,
        "pid": proc.pid,
        "log_path": str(log_path),
    }, indent=2)


@mcp.tool(name="dsf_run_status")
def run_status(
    job_id: Annotated[str, Field(description="Job ID returned by dsf_run_sim_async")],
    tail_lines: Annotated[int, Field(description="Number of recent log lines to return")] = 30,
) -> str:
    """Check the status of a background simulation.

    Example:
        dsf_run_status(job_id="abc12345")
    """
    if job_id not in _running_jobs:
        return json.dumps({"error": f"Unknown job_id: {job_id}"})

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

    return json.dumps(result, indent=2)


@mcp.tool(name="dsf_stop_run")
def stop_run(
    job_id: Annotated[str, Field(description="Job ID returned by dsf_run_sim_async")],
) -> str:
    """Stop a running background simulation.

    Example:
        dsf_stop_run(job_id="abc12345")
    """
    if job_id not in _running_jobs:
        return json.dumps({"error": f"Unknown job_id: {job_id}"})

    job = _running_jobs[job_id]
    proc = job["proc"]

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return json.dumps({"job_id": job_id, "status": "terminated"})
    else:
        return json.dumps({"job_id": job_id, "status": "already_done", "exit_code": proc.returncode})


# =========================================================================
# CSV Output Tools
# =========================================================================

@mcp.tool(name="dsf_get_headers_csv")
def get_headers_csv(
    csv_file: Annotated[str, Field(description="Absolute path to a DSF CSV output file")],
) -> str:
    """List all column headers from a CSV output file.

    Example:
        dsf_get_headers_csv(csv_file="/path/to/output1.csv")
    """
    csv_path = Path(csv_file).resolve()
    if not csv_path.exists():
        return json.dumps({"error": f"File not found: {csv_file}"})

    try:
        headers = _parse_csv_headers(str(csv_path))

        # Count rows
        with open(csv_path, 'r') as f:
            n_rows = sum(1 for _ in f) - 1  # subtract header

        return json.dumps({
            "file": str(csv_path),
            "n_columns": len(headers),
            "n_rows": n_rows,
            "headers": headers,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(name="dsf_get_timeseries_csv")
def get_timeseries_csv(
    csv_file: Annotated[str, Field(description="Absolute path to a DSF CSV output file")],
    variables: Annotated[str, Field(description="Comma-separated column names (substring match). Empty = all columns.")] = "",
    t_start: Annotated[float, Field(description="Start time filter. -1 = no filter.")] = -1,
    t_end: Annotated[float, Field(description="End time filter. -1 = no filter.")] = -1,
    decimation: Annotated[int, Field(description="Return every Nth row. 1 = all rows.")] = 1,
) -> str:
    """Read timeseries data from a CSV output file.

    Example:
        dsf_get_timeseries_csv(csv_file="/path/to/output1.csv", variables="Altitude,Mach", decimation=10)
    """
    csv_path = Path(csv_file).resolve()
    if not csv_path.exists():
        return json.dumps({"error": f"File not found: {csv_file}"})

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

        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# =========================================================================
# HDF5 Output Tools
# =========================================================================

@mcp.tool(name="dsf_get_headers_h5")
def get_headers_h5(
    h5_file: Annotated[str, Field(description="Absolute path to a DSF HDF5 output file")],
) -> str:
    """List all dataset names from an HDF5 output file.

    Example:
        dsf_get_headers_h5(h5_file="/path/to/output1.h5")
    """
    h5_path = Path(h5_file).resolve()
    if not h5_path.exists():
        return json.dumps({"error": f"File not found: {h5_file}"})

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

        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(name="dsf_get_timeseries_h5")
def get_timeseries_h5(
    h5_file: Annotated[str, Field(description="Absolute path to a DSF HDF5 output file")],
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
    h5_path = Path(h5_file).resolve()
    if not h5_path.exists():
        return json.dumps({"error": f"File not found: {h5_file}"})

    try:
        from dsf.utils.data_loader import load_h5

        times, data = load_h5(str(h5_path))

        # Select group
        if group:
            if group not in data:
                return json.dumps({"error": f"Group '{group}' not found",
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

        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


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
def inspect_xml(
    xml_file: Annotated[str, Field(description="Absolute path to a DSF XML configuration file")],
) -> str:
    """Parse a DSF XML configuration file and return its structure.

    Does NOT run the simulation — only reads the XML.

    Example:
        dsf_inspect_xml(xml_file="/path/to/sim.xml")
    """
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return json.dumps({"error": f"File not found: {xml_file}"})

    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(xml_path))
        root = tree.getroot()

        result = {"file": str(xml_path)}

        # Find <sim> node
        sim_node = root if root.tag == 'sim' else root.find('.//sim')
        if sim_node is None:
            return json.dumps({"error": "No <sim> element found"})

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

        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# =========================================================================
# Summary Tool
# =========================================================================

@mcp.tool(name="dsf_get_summary")
def get_summary(
    output_file: Annotated[str, Field(description="Absolute path to a CSV or HDF5 output file")],
) -> str:
    """Get a compact statistical summary of a simulation output file.

    Supports both CSV and HDF5. Returns min/max/mean/initial/final per variable.

    Example:
        dsf_get_summary(output_file="/path/to/output1.csv")
    """
    fpath = Path(output_file).resolve()
    if not fpath.exists():
        return json.dumps({"error": f"File not found: {output_file}"})

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

        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


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
def watch_sim(
    xml_file: Annotated[str, Field(description="Absolute path to a DSF XML configuration file")],
    library: Annotated[str, Field(description="Absolute path to shared library (required)")],
    watch: Annotated[str, Field(description="Comma-separated variable name patterns to track. Empty = all.")] = "",
    dt: Annotated[float, Field(description="Timestep in seconds. 0 = read from XML.")] = 0,
    tmax: Annotated[float, Field(description="End time in seconds. 0 = read from XML.")] = 0,
) -> str:
    """Start a simulation with per-step Python introspection.

    Runs in a background thread, allowing live variable queries via dsf_get_watch_state.

    Example:
        dsf_watch_sim(xml_file="/path/to/sim.xml", library="/path/to/libsixdof.so")
    """
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return json.dumps({"error": f"XML file not found: {xml_file}"})

    lib_path = Path(library).resolve()
    if not lib_path.exists():
        return json.dumps({"error": f"Library not found: {library}"})

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

    return json.dumps({
        "job_id": job_id,
        "xml_file": str(xml_path),
        "dt": dt,
        "tmax": tmax,
        "watch_patterns": watch_patterns,
    }, indent=2)


@mcp.tool(name="dsf_get_watch_state")
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
            return json.dumps({"error": f"Unknown job_id: {job_id}"})

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

        return json.dumps(result, indent=2)


@mcp.tool(name="dsf_stop_watch")
def stop_watch(
    job_id: Annotated[str, Field(description="Job ID returned by dsf_watch_sim")],
) -> str:
    """Stop a running watch simulation.

    Example:
        dsf_stop_watch(job_id="abc12345")
    """
    with _watch_lock:
        if job_id not in _watch_sessions:
            return json.dumps({"error": f"Unknown job_id: {job_id}"})
        _watch_sessions[job_id]["stop"] = True

    return json.dumps({"job_id": job_id, "status": "stop_signaled"})


# =========================================================================
# List Jobs
# =========================================================================

@mcp.tool(name="dsf_list_jobs")
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

    return json.dumps(result, indent=2)


# =========================================================================
# Plotting Tools
# =========================================================================

@mcp.tool(name="dsf_plot_timeseries_csv")
def plot_timeseries_csv(
    csv_file: Annotated[str, Field(description="Absolute path to a DSF CSV output file")],
    variables: Annotated[str, Field(description="Comma-separated column names (substring match) to plot")],
    out_file: Annotated[str, Field(description="Path to save the plot image (e.g. 'plot.png'). Empty = auto-generate.")] = "",
) -> str:
    """Plot timeseries data from a CSV output file and save to an image.

    Example:
        dsf_plot_timeseries_csv(csv_file="/path/to/output1.csv", variables="Altitude,Mach", out_file="/tmp/plot.png")
    """
    import matplotlib
    matplotlib.use('Agg')  # Prevent GUI popups that could hang the server
    import matplotlib.pyplot as plt
    from pathlib import Path
    import json
    import time
    
    fpath = Path(csv_file).resolve()
    if not fpath.exists():
        return json.dumps({"error": f"File not found: {csv_file}"})
        
    try:
        headers = _parse_csv_headers(str(fpath))
        data_dict = _read_csv_data(str(fpath))
        
        if not headers or not data_dict:
            return json.dumps({"error": "No data found or empty CSV"})
            
        time_col = headers[0]
        times = data_dict.get(time_col, [])
        
        var_list = [v.strip() for v in variables.split(',') if v.strip()]
        if not var_list:
            return json.dumps({"error": "No variables provided to plot"})
            
        # Find matching columns
        cols_to_plot = []
        for v in var_list:
            matched = [h for h in headers if v.lower() in h.lower() and h != time_col]
            cols_to_plot.extend(matched)
            
        # Remove duplicates preserving order
        cols_to_plot = list(dict.fromkeys(cols_to_plot))
        
        if not cols_to_plot:
            return json.dumps({"error": f"No matching columns found for variables: {variables}", "available": headers})
            
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
        
        return json.dumps({"file": str(out_path), "plotted_variables": cols_to_plot})
        
    except Exception as e:
        return json.dumps({"error": str(e)})


# =========================================================================
# Analysis & Tuning Tools
# =========================================================================

@mcp.tool(name="dsf_compare_runs_csv")
def compare_runs_csv(
    csv_file1: Annotated[str, Field(description="Absolute path to the first (baseline) CSV output file")],
    csv_file2: Annotated[str, Field(description="Absolute path to the second (modified) CSV output file")],
    variables: Annotated[str, Field(description="Comma-separated column names (substring match) to compare")],
) -> str:
    """Compare two simulation CSV outputs and return min/max/RMS differences.

    Example:
        dsf_compare_runs_csv(csv_file1="/path/to/baseline.csv", csv_file2="/path/to/modified.csv", variables="Altitude,Mach")
    """
    from pathlib import Path
    import json
    fpath1 = Path(csv_file1).resolve()
    fpath2 = Path(csv_file2).resolve()
    
    if not fpath1.exists():
        return json.dumps({"error": f"File not found: {csv_file1}"})
    if not fpath2.exists():
        return json.dumps({"error": f"File not found: {csv_file2}"})
        
    try:
        headers1 = _parse_csv_headers(str(fpath1))
        data1 = _read_csv_data(str(fpath1))
        headers2 = _parse_csv_headers(str(fpath2))
        data2 = _read_csv_data(str(fpath2))
        
        var_list = [v.strip() for v in variables.split(',') if v.strip()]
        if not var_list:
            return json.dumps({"error": "No variables provided"})
            
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
                
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(name="dsf_extract_events")
def extract_events(
    csv_file: Annotated[str, Field(description="Absolute path to a DSF CSV output file")],
    variable: Annotated[str, Field(description="Column name (or substring) to evaluate")],
    operator_str: Annotated[str, Field(description="Comparison operator: '>', '<', '>=', '<=', '==', '!=', or 'crosses'")],
    threshold: Annotated[float, Field(description="Numeric threshold value to compare against")],
) -> str:
    """Find timestamps in a CSV where a condition becomes true (crosses threshold).

    Example:
        dsf_extract_events(csv_file="/path/to/output1.csv", variable="Altitude", operator_str="<", threshold=0)
    """
    from pathlib import Path
    import json
    fpath = Path(csv_file).resolve()
    if not fpath.exists():
        return json.dumps({"error": f"File not found: {csv_file}"})
        
    try:
        headers = _parse_csv_headers(str(fpath))
        data = _read_csv_data(str(fpath))
        
        if not headers:
            return json.dumps({"error": "Empty CSV / No headers"})
            
        time_col = headers[0]
        times = data.get(time_col, [])
        
        col = next((h for h in headers if variable.lower() in h.lower() and h != time_col), None)
        if not col or col not in data:
            return json.dumps({"error": f"Variable matching '{variable}' not found."})
            
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
                
        return json.dumps({
            "file": str(fpath),
            "variable": col,
            "operator": operator_str,
            "threshold": threshold,
            "events_found": len(events),
            "events": events
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool(name="dsf_patch_run_xml")
def patch_run_xml(
    xml_file: Annotated[str, Field(description="Absolute path to the baseline DSF XML configuration file")],
    xpath: Annotated[str, Field(description="ElementTree XPath to the node to modify, e.g. './/block[@id=\"AltHold\"]'")],
    attributes: Annotated[str, Field(description="JSON string of attribute key-value pairs to set, e.g. '{\"Kp\": \"0.5\"}'")],
    out_file: Annotated[str, Field(description="Path to save patched XML. Empty = <stem>_patched.xml.")] = "",
    library: Annotated[str, Field(description="Path to shared library. Empty = read from XML.")] = "",
    tmax: Annotated[float, Field(description="Override simulation end time. 0 = use XML value.")] = 0,
) -> str:
    """Modify an XML file at the given xpath, save it, run the simulation, and return results.

    Example:
        dsf_patch_run_xml(xml_file="/path/to/sim.xml", xpath=".//fcs[@id='F16FCS']", attributes='{"Kp_h": "0.01"}')
    """
    from pathlib import Path
    import json
    import xml.etree.ElementTree as ET
    
    xml_path = Path(xml_file).resolve()
    if not xml_path.exists():
        return json.dumps({"error": f"File not found: {xml_file}"})
        
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        
        node = root.find(xpath)
        if node is None:
            return json.dumps({"error": f"Node not found for xpath: {xpath}"})
            
        try:
            attrs = json.loads(attributes)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Failed to parse attributes JSON: {e}"})
            
        for k, v in attrs.items():
            node.set(k, str(v))
            
        if not out_file:
            out_path = xml_path.parent / f"{xml_path.stem}_patched.xml"
        else:
            out_path = Path(out_file).resolve()
            
        tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
        
        # We process the simulation synchronously
        return run_sim(str(out_path), library, tmax)
    except Exception as e:
        return json.dumps({"error": str(e)})

# =========================================================================
# Entry point
# =========================================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
