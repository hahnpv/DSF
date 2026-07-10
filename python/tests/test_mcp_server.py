"""
Unit tests for MCP server robustness helpers (job reaping / eviction).

Covers the fixes: finished-job log handles are closed, and the jobs/sessions
dicts are capped so a long-lived server can't leak file descriptors or grow
without bound. Exercises the pure bookkeeping via fakes — no subprocess/sixdof.
"""
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
