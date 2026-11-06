"""Real-run runner: resume after a crash, abort threshold, parallel run against the local site."""
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
