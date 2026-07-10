"""
Tests for the MCP server (H3):

- job reaping / eviction bookkeeping (fakes, no subprocess),
- resolve_path containment — the security boundary of every file tool,
- the argument-normalization layer (aliases, missing-required errors),
- a smoke test per cheap tool: CSV/XML/H5 introspection, file read/write,
  job-state queries, and the no-subprocess error paths of the run/build tools.

Tools are plain module-level callables (keyword-args only); no network server
is started and no sixdof/sim subprocess is needed. The workspace root is
monkeypatched to a tmp dir per test.
"""
import json
import os

import pytest

pytest.importorskip("mcp")
pytest.importorskip("pydantic")

from dsf.mcp import server as srv


class FakeProc:
    def __init__(self, rc=0):
        self.returncode = rc

    def poll(self):
        return self.returncode          # not None => finished


class FakeLog:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _job(rc=0, t=0.0):
    return {"proc": FakeProc(rc), "log_file": FakeLog(),
            "log_path": "/tmp/x.log", "xml_file": "x.xml",
            "cwd": "/tmp", "start_time": t}


def test_reap_closes_finished_log(monkeypatch):
    monkeypatch.setattr(srv, "_running_jobs", {})
    job = _job(rc=0)
    srv._running_jobs["j1"] = job
    srv._reap_jobs()
    assert job["log_file"].closed, "finished job's log handle should be closed"
    assert job["_reaped"] is True
    assert job["exit_code"] == 0


def test_reap_leaves_running_job_open(monkeypatch):
    monkeypatch.setattr(srv, "_running_jobs", {})

    class Running(FakeProc):
        def poll(self):
            return None                 # still running

    job = {"proc": Running(), "log_file": FakeLog(), "start_time": 0.0}
    srv._running_jobs["r1"] = job
    srv._reap_jobs()
    assert not job["log_file"].closed, "running job's log must stay open"
    assert "_reaped" not in job


def test_reap_evicts_beyond_cap(monkeypatch):
    monkeypatch.setattr(srv, "_running_jobs", {})
    n = srv._MAX_KEPT_JOBS + 10
    for i in range(n):
        srv._running_jobs[f"j{i}"] = _job(rc=0, t=float(i))
    srv._reap_jobs()
    assert len(srv._running_jobs) <= srv._MAX_KEPT_JOBS
    # Oldest finished jobs are the ones dropped; newest retained.
    assert f"j{n-1}" in srv._running_jobs


def test_jobs_lock_exists():
    # The lock that guards _running_jobs against concurrent tool calls.
    import threading
    assert isinstance(srv._jobs_lock, type(threading.Lock()))


# ── resolve_path: the containment boundary ──────────────────────────────────

@pytest.fixture
def workspace(monkeypatch, tmp_path):
    """Point the server's workspace root at a tmp dir for this test."""
    root = tmp_path.resolve()
    monkeypatch.setattr(srv, "FILE_ROOT", root)
    return root


def test_resolve_path_relative_inside(workspace):
    assert srv.resolve_path("sub/file.csv") == str(workspace / "sub" / "file.csv")


def test_resolve_path_root_itself(workspace):
    assert srv.resolve_path(str(workspace)) == str(workspace)


def test_resolve_path_absolute_inside(workspace):
    p = workspace / "a.txt"
    assert srv.resolve_path(str(p)) == str(p)


def test_resolve_path_empty_is_passthrough(workspace):
    assert srv.resolve_path("") == ""


def test_resolve_path_rejects_dotdot_escape(workspace):
    with pytest.raises(ValueError, match="escape"):
        srv.resolve_path("../outside.txt")
    with pytest.raises(ValueError, match="escape"):
        srv.resolve_path("sub/../../../etc/passwd")


def test_resolve_path_rejects_absolute_outside(workspace):
    with pytest.raises(ValueError, match="escape"):
        srv.resolve_path("/etc/passwd")


def test_resolve_path_rejects_sibling_prefix(workspace):
    # The startswith() bug this replaced: /root_secrets "starts with" /root.
    with pytest.raises(ValueError, match="escape"):
        srv.resolve_path(str(workspace) + "_secrets/creds.txt")


def test_resolve_path_rejects_symlink_escape(workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    secret = outside / "secret.txt"
    secret.write_text("s3cret")
    link = workspace / "innocent"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="escape"):
        srv.resolve_path("innocent/secret.txt")


def test_safe_dumps_strips_workspace_root(workspace):
    out = srv.safe_dumps({"path": str(workspace / "out" / "run.csv")})
    assert str(workspace) not in out
    assert "run.csv" in out


# ── argument normalization layer ────────────────────────────────────────────

CSV_TEXT = "Time,Altitude,Speed\n0.0,0.0,100.0\n1.0,50.0,110.0\n2.0,150.0,120.0\n"


@pytest.fixture
def csv_file(workspace):
    p = workspace / "out.csv"
    p.write_text(CSV_TEXT)
    return "out.csv"  # workspace-relative, as a client would pass it


def test_alias_csv_file_maps_to_file(workspace, csv_file):
    out = json.loads(srv.get_headers_csv(csv_file=csv_file))
    assert out["n_columns"] == 3
    assert "Altitude" in out["headers"]


def test_missing_required_returns_structured_error(workspace):
    out = srv.get_headers_csv()
    assert "missing_required" in out
    assert "file" in out


def test_tool_rejects_escaping_path(workspace):
    with pytest.raises(ValueError, match="escape"):
        srv.get_headers_csv(file="../../etc/passwd")


# ── tool smoke tests: CSV introspection ─────────────────────────────────────

def test_get_headers_csv(workspace, csv_file):
    out = json.loads(srv.get_headers_csv(file=csv_file))
    assert out["n_rows"] == 3
    assert out["headers"] == ["Time", "Altitude", "Speed"]


def test_get_timeseries_csv(workspace, csv_file):
    out = srv.get_timeseries_csv(file=csv_file, variables="Altitude")
    assert "error" not in json.loads(out)
    assert "Altitude" in out


def test_get_summary_csv(workspace, csv_file):
    out = srv.get_summary(file=csv_file)
    assert "error" not in json.loads(out)
    assert "Altitude" in out


def test_compare_runs_csv(workspace, csv_file):
    other = srv.FILE_ROOT / "out2.csv"
    other.write_text(CSV_TEXT.replace("150.0", "160.0"))
    out = srv.compare_runs_csv(file_a=csv_file, file_b="out2.csv",
                               variables="Altitude")
    assert "error" not in json.loads(out)
    assert "Altitude" in out


def test_extract_events_threshold_crossing(workspace, csv_file):
    out = json.loads(srv.extract_events(file=csv_file, variable="Altitude",
                                        operator=">", threshold=100.0))
    assert out["events_found"] == 1
    assert out["events"][0]["time"] == 2.0
    assert out["events"][0]["type"] == "transition"


def test_extract_events_unknown_variable(workspace, csv_file):
    out = json.loads(srv.extract_events(file=csv_file, variable="NoSuchVar",
                                        operator=">", threshold=0.0))
    assert "error" in out


# ── tool smoke tests: XML / HDF5 introspection ──────────────────────────────

SIM_XML = ('<sim dt="0.1" tmax="1.0">'
           '<vehicle id="V1" class="Vehicle">'
           '<mass id="M1" class="Mass" mass="10"/></vehicle></sim>')


def test_inspect_xml(workspace):
    (srv.FILE_ROOT / "deck.xml").write_text(SIM_XML)
    out = srv.inspect_xml(file="deck.xml")
    assert "error" not in json.loads(out)
    assert "V1" in out and "M1" in out


@pytest.fixture
def h5_file(workspace):
    h5py = pytest.importorskip("h5py")
    p = srv.FILE_ROOT / "run.h5"
    with h5py.File(p, "w") as f:
        f.create_dataset("Time", data=[0.0, 1.0, 2.0])
        g = f.create_group("Veh")
        g.create_dataset("Altitude", data=[0.0, 50.0, 150.0])
    return "run.h5"


def test_get_headers_h5(workspace, h5_file):
    out = srv.get_headers_h5(file=h5_file)
    assert "error" not in json.loads(out)
    assert "Veh" in out and "Altitude" in out


def test_get_timeseries_h5(workspace, h5_file):
    out = srv.get_timeseries_h5(file=h5_file, variables="Altitude")
    assert "error" not in json.loads(out)
    assert "Altitude" in out


# ── tool smoke tests: workspace file tools ──────────────────────────────────

def test_write_read_search_replace_roundtrip(workspace):
    srv.dsf_write_file(relative_path="notes/a.txt", content="alpha beta")
    assert (srv.FILE_ROOT / "notes" / "a.txt").read_text() == "alpha beta"

    out = srv.dsf_read_file(relative_path="notes/a.txt")
    assert "alpha beta" in out

    srv.dsf_search_replace(relative_path="notes/a.txt",
                           target="beta", replacement="gamma")
    assert (srv.FILE_ROOT / "notes" / "a.txt").read_text() == "alpha gamma"


def test_file_tools_refuse_escape(workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside2")
    out = srv.dsf_write_file(relative_path=str(outside / "evil.txt"),
                             content="x")
    assert "Error" in out
    assert not (outside / "evil.txt").exists()

    out = srv.dsf_read_file(relative_path="../../etc/passwd")
    assert "Error" in out


# ── tool smoke tests: job state + no-subprocess error paths ─────────────────

def test_unknown_job_ids_error_cleanly(monkeypatch, workspace):
    monkeypatch.setattr(srv, "_running_jobs", {})
    monkeypatch.setattr(srv, "_watch_sessions", {})
    for tool in (srv.run_status, srv.stop_run,
                 srv.get_watch_state, srv.stop_watch):
        out = tool(job_id="no-such-job")
        assert "error" in out.lower()


def test_list_jobs_empty(monkeypatch, workspace):
    monkeypatch.setattr(srv, "_running_jobs", {})
    monkeypatch.setattr(srv, "_watch_sessions", {})
    out = srv.list_jobs()
    assert "error" not in json.loads(out)


def test_run_sim_missing_deck_errors_before_subprocess(workspace):
    out = srv.run_sim(file="no_such_deck.xml")
    assert "error" in json.loads(out)


def test_run_sim_async_missing_deck_errors(workspace):
    out = srv.run_sim_async(file="no_such_deck.xml")
    assert "error" in json.loads(out)


def test_build_unknown_project_errors(workspace):
    out = srv.build(project="not_a_project")
    assert "error" in json.loads(out)


# ── tool smoke test: CSV plotting (Agg, writes a PNG) ───────────────────────

def test_plot_timeseries_csv(workspace, csv_file):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg", force=True)
    out = srv.plot_timeseries_csv(file=csv_file, variables="Altitude",
                                  output="plot.png")
    assert "error" not in json.loads(out)
    assert (srv.FILE_ROOT / "plot.png").exists()
