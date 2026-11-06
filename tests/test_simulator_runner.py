"""Real-run runner: resume after a crash, abort threshold, parallel run against the local site."""
import threading

import pytest

from simulator import browser_run
from simulator.behavior import Visitor, load_config
from simulator.browser_run import close_interrupted, next_ids, run_real, should_abort
from simulator.ground_truth import read, visitor_lines

CFG = load_config()
FAST = {**CFG, "real": {**CFG["real"], "flush_quiet_seconds": 0.2, "flush_max_seconds": 1}}
EVENT = [("page_view", {"page": "index"}, "2026-11-06T12:00:00Z")]


def _visitor(n: int, status: str = "ok") -> list[dict]:
    return visitor_lines("real", f"v{n:05d}", "A", Visitor("accept", False), EVENT, None, 1, status,
                         "search" if status == "error" else None)


def _finished(ok: int, errors: int) -> list[dict]:
    return [line for n in range(1, ok + errors + 1) for line in _visitor(n, "error" if n <= errors else "ok")]


def test_close_interrupted():
    lines = _visitor(1) + _visitor(2)[:-1] + _visitor(3)
    [end] = close_interrupted(lines)
    assert (end["visitor_id"], end["event"], end["status"], end["error_step"]) == (
        "v00002", "visit_end", "error", "interrupted")
    assert end["seq"] == 2 and end["variant"] == "A" and end["banner"] == "accept"


def test_next_ids_counts_interrupted():
    lines = _visitor(1) + _visitor(2) + _visitor(3) + _visitor(4)[:-1]
    lines += close_interrupted(lines)
    assert next_ids(lines, 6) == ["v00005", "v00006"]
    assert next_ids(lines, 4) == []


def test_no_abort_before_min():
    assert not should_abort(_finished(3, 2), 0.05, 40)


def test_abort_above_rate():
    assert should_abort(_finished(37, 3), 0.05, 40)
    assert not should_abort(_finished(38, 2), 0.05, 40)


def test_run_real_offline(tmp_path, site_url):
    out = tmp_path / "real.jsonl"
    run_real(FAST, 3, out, site_url, workers=2, offline=True)
    ends = [line for line in read(out) if line["event"] == "visit_end"]
    assert len(ends) == 3
    run_real(FAST, 5, out, site_url, workers=2, offline=True)
    ends = [line for line in read(out) if line["event"] == "visit_end"]
    assert sorted(e["visitor_id"] for e in ends) == [f"v{n:05d}" for n in range(1, 6)]
    assert all(e["status"] == "ok" for e in ends), [e["error_step"] for e in ends]


def _fake_visit(calls, fail_on=None):
    def fake(context, site_url, visitor_id, visitor, cfg, schools, options):
        calls.append(visitor_id)
        if visitor_id == fail_on:
            raise RuntimeError("process killed mid-visit")
        return visitor_lines("real", visitor_id, "A", visitor, EVENT, None, 1, "ok", None)
    return fake


def test_killed_visitor_is_closed_not_rerun(tmp_path, site_url, monkeypatch):
    out = tmp_path / "real.jsonl"
    calls = []
    monkeypatch.setattr(browser_run, "visit", _fake_visit(calls, fail_on="v00002"))
    with pytest.raises(RuntimeError):
        run_real(FAST, 3, out, site_url, workers=1, offline=True)
    monkeypatch.setattr(browser_run, "visit", _fake_visit(calls))
    run_real(FAST, 3, out, site_url, workers=1, offline=True)
    assert calls == ["v00001", "v00002", "v00003"]  # v00002 never visits twice
    ends = {e["visitor_id"]: e for e in read(out) if e["event"] == "visit_end"}
    assert sorted(ends) == ["v00001", "v00002", "v00003"]
    assert (ends["v00002"]["status"], ends["v00002"]["error_step"]) == ("error", "interrupted")


def test_next_ids_fills_gaps():
    lines = _visitor(1) + _visitor(3)
    assert next_ids(lines, 4) == ["v00002", "v00004"]


def test_ctrl_c_lets_running_visitors_finish():
    stop = threading.Event()

    class Worker:
        joins = 0

        def join(self):
            Worker.joins += 1
            if Worker.joins == 1:
                raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        browser_run._join_all([Worker()], stop)
    assert stop.is_set() and Worker.joins == 2


def test_resume_after_torn_write(tmp_path, site_url, monkeypatch):
    out = tmp_path / "real.jsonl"
    calls = []
    monkeypatch.setattr(browser_run, "visit", _fake_visit(calls))
    run_real(FAST, 1, out, site_url, workers=1, offline=True)
    with out.open("a", encoding="utf-8") as f:
        f.write('{"run": "real", "visitor_id": "v0000')  # killed mid-write
    run_real(FAST, 2, out, site_url, workers=1, offline=True)
    ends = [line["visitor_id"] for line in read(out) if line["event"] == "visit_end"]
    assert ends == ["v00001", "v00002"]
    assert out.read_text(encoding="utf-8").endswith("\n")
