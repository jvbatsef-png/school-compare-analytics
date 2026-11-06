"""Ground-truth log format and the synthetic A/B executor."""
import math
from datetime import datetime, timedelta

import pytest

from simulator.behavior import Visitor, load_config, load_schools
from simulator.ground_truth import FIELDS, append, by_visitor, read, visitor_lines
from simulator.synthetic_run import generate
from tests.site_helpers import assert_valid

CFG = load_config()
SCHOOLS = load_schools()


@pytest.fixture(scope="module")
def full():
    return generate(CFG, SCHOOLS)


def _small(n: int) -> dict:
    return {**CFG, "synthetic": {**CFG["synthetic"], "visitors": n}}


def test_round_trip(tmp_path):
    path = tmp_path / "log.jsonl"
    first = visitor_lines("real", "v00001", "B", Visitor("accept", False),
                          [("page_view", {"page": "index"}, "2026-11-06T12:00:00Z")],
                          "123.456", 4, "ok", None)
    second = visitor_lines("real", "v00002", None, Visitor("ignore", True), [], None, 0, "error", "load")
    append(path, first)
    append(path, second)
    lines = read(path)
    assert lines == first + second
    assert all(tuple(line) == FIELDS for line in lines)
    assert [line["seq"] for line in first] == [1, 2]
    end = first[-1]
    assert (end["event"], end["status"], end["ga_requests"], end["ts"]) == ("visit_end", "ok", 4, "2026-11-06T12:00:00Z")
    assert first[0]["status"] is None and first[0]["ga_requests"] is None
    assert list(by_visitor(lines)) == ["v00001", "v00002"]
    assert second[-1]["ts"].endswith("Z")


def test_events_validate_against_spec():
    for line in generate(_small(300), SCHOOLS):
        if line["event"] not in ("page_view", "visit_end"):
            assert_valid({"event": line["event"], **line["params"]})


def test_synthetic_is_deterministic():
    assert generate(_small(300), SCHOOLS) == generate(_small(300), SCHOOLS)


def test_synthetic_counts_and_shares(full):
    ends = [line for line in full if line["event"] == "visit_end"]
    n = CFG["synthetic"]["visitors"]
    assert len(ends) == n == len({e["visitor_id"] for e in ends})

    def close(share, p):
        return abs(share - p) <= 3 * math.sqrt(p * (1 - p) / n)

    assert close(sum(e["variant"] == "B" for e in ends) / n, 0.5)
    for choice, p in CFG["banner"].items():
        assert close(sum(e["banner"] == choice for e in ends) / n, p), choice
    assert close(sum(e["ad_blocker"] for e in ends) / n, CFG["ad_blocker"])
    assert all(line["run"] == "synthetic" for line in full)
    assert all(line["ga_client_id"] is None and line["ga_requests"] is None for line in full)
    assert all(e["status"] == "ok" and e["error_step"] is None for e in ends)


def test_synthetic_timestamps(full):
    start = datetime.fromisoformat(CFG["synthetic"]["start_date"])
    end = start + timedelta(days=CFG["synthetic"]["days"])
    for lines in by_visitor(full).values():
        stamps = [line["ts"] for line in lines]
        assert all(ts.endswith("Z") for ts in stamps)
        assert stamps == sorted(stamps)
        for ts in stamps:
            t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
            assert start <= t < end and 12 <= t.hour <= 23


def test_read_drops_torn_last_line(tmp_path):
    path = tmp_path / "log.jsonl"
    lines = visitor_lines("real", "v00001", "A", Visitor("accept", False), [], None, 0, "ok", None)
    append(path, lines)
    with path.open("a", encoding="utf-8") as f:
        f.write('{"run": "real", "visitor_id": "v0000')  # killed mid-write
    assert read(path) == lines
