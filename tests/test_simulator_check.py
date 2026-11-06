"""Acceptance checker: each ground-truth log against config.yaml, and the client-ID match query."""
from simulator.behavior import Visitor, load_config, load_schools
from simulator.check_run import client_id_match_sql, problems, summarize
from simulator.ground_truth import visitor_lines
from simulator.synthetic_run import generate

CFG = load_config()
EVENT = [("page_view", {"page": "index"}, "2026-11-06T12:00:00Z")]


def _visitor(n, variant, banner, blocker, status="ok", client_id=None):
    return visitor_lines("real", f"v{n:05d}", variant, Visitor(banner, blocker), EVENT, client_id, 1, status,
                         "search" if status == "error" else None)


def _ok_summary(n: int) -> dict:
    return {"visitors": n, "share_B": 0.5, "share_accept": 0.55, "share_reject": 0.15, "share_ignore": 0.30,
            "share_ad_blocker": 0.25, "error_rate": 0.0, "cookieless_visitors": 0}


def test_summary_on_hand_built_log():
    lines = (_visitor(1, "A", "accept", False, client_id="1.2") + _visitor(2, "B", "reject", False)
             + _visitor(3, "B", "ignore", True) + _visitor(4, "B", "ignore", False, status="error"))
    assert summarize(lines) == {
        "visitors": 4, "share_B": 0.75, "share_accept": 0.25, "share_reject": 0.25, "share_ignore": 0.5,
        "share_ad_blocker": 0.25, "error_rate": 0.25, "cookieless_visitors": 1}


def test_problems_flags_wrong_count_and_share():
    assert problems(_ok_summary(6000), CFG, 6000) == []
    [count] = problems(_ok_summary(5999), CFG, 6000)
    assert "5999" in count and "6000" in count
    [share] = problems({**_ok_summary(6000), "share_accept": 0.60}, CFG, 6000)
    assert "share_accept" in share
    [errors] = problems({**_ok_summary(500), "error_rate": 0.05}, CFG, 500)
    assert "error_rate" in errors


def test_problems_ok_on_synthetic():
    assert problems(summarize(generate(CFG, load_schools())), CFG, CFG["synthetic"]["visitors"]) == []


def test_client_id_sql_lists_ids():
    lines = (_visitor(1, "A", "accept", False, client_id="111.222") + _visitor(2, "B", "accept", False,
             client_id="333.444") + _visitor(3, "B", "reject", False))
    sql = client_id_match_sql(lines, "`proj.analytics_1.events_*`")
    assert "'111.222'" in sql and "'333.444'" in sql and "None" not in sql and "null" not in sql.lower()
    assert sql.count("'111.222'") == 1
    assert "`proj.analytics_1.events_*`" in sql
    for column in ("logged", "found", "share_found"):
        assert column in sql
