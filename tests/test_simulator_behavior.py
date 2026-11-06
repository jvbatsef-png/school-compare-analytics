"""Behaviour model: draw rates, plan rules and the dataLayer events a plan implies."""
import random

import pytest

from simulator.behavior import (
    Plan, Search, Visitor, draw_visitor, load_config, load_schools, plan_events, plan_visit,
    search_options, search_results, visitor_rng,
)

CFG = load_config()
SCHOOLS = load_schools()
OPTIONS = search_options(SCHOOLS)
N = 100_000  # per variant


def _share(hits: int, total: int) -> float:
    return hits / total


@pytest.fixture(scope="module")
def plans():
    rng = random.Random(1)
    return {v: [plan_visit(v, rng, CFG, OPTIONS) for _ in range(N)] for v in "AB"}


def test_visitor_rates_match_config():
    rng = random.Random(1)
    visitors = [draw_visitor(rng, CFG) for _ in range(N)]
    for choice in ("accept", "reject", "ignore"):
        share = _share(sum(v.banner == choice for v in visitors), N)
        assert abs(share - CFG["banner"][choice]) < 0.01, (choice, share)
    blocker = _share(sum(v.ad_blocker for v in visitors), N)
    assert abs(blocker - CFG["ad_blocker"]) < 0.01


@pytest.mark.parametrize("variant, profile, lead", [("A", 0.40, 0.15), ("B", 0.445, 0.1875)])
def test_funnel_rates_match_config(plans, variant, profile, lead):
    ps = plans[variant]
    searched = [p for p in ps if p.search]
    assert abs(_share(len(searched), N) - 0.85) < 0.01
    assert abs(_share(sum(p.profile_from is not None for p in searched), len(searched)) - profile) < 0.01
    assert abs(_share(sum(p.lead is not None for p in searched), len(searched)) - lead) < 0.01
    leads = [p for p in searched if p.lead]
    assert abs(_share(sum(p.lead == "complete" for p in leads), len(leads)) - 0.70) < 0.01
    if variant == "B":
        adoption = _share(sum(bool(p.compare_positions) for p in searched), len(searched))
        assert abs(adoption - 0.30) < 0.01


def test_plan_rules(plans):
    for variant, ps in plans.items():
        for p in ps[:20_000]:
            if p.search is None:
                assert (p.compare_positions, p.profile_from, p.profile_index, p.lead) == ((), None, None, None)
                continue
            if variant == "A":
                assert p.compare_positions == ()
            if p.compare_positions:
                assert len(p.compare_positions) in (2, 3)
                assert len(set(p.compare_positions)) == len(p.compare_positions)
                assert all(1 <= pos <= p.search.n_results for pos in p.compare_positions)
            if p.lead:
                assert p.profile_from is not None
            if p.profile_from == "compare":
                assert p.compare_positions and 1 <= p.profile_index <= len(p.compare_positions)
            elif p.profile_from == "results":
                assert 1 <= p.profile_index <= min(5, p.search.n_results)
            else:
                assert p.profile_index is None


def test_search_options_have_three_results():
    assert OPTIONS
    assert any(o.level == "" for o in OPTIONS)
    for o in OPTIONS:
        assert o.n_results >= 3
        assert o.n_results == len(search_results(SCHOOLS, o.location, o.level))


def test_search_results_order():
    loc = OPTIONS[0].location
    found = search_results(SCHOOLS, loc, "")
    assert all(f"{s['city']}, {s['state']}" == loc for s in found)
    keys = [(-s["rating"], s["id"]) for s in found]
    assert keys == sorted(keys)


def test_plan_events_compare_and_lead():
    search = next(o for o in OPTIONS if o.level and o.n_results >= 3)
    shown = search_results(SCHOOLS, search.location, search.level)
    tray = [shown[0]["id"], shown[2]["id"]]
    plan = Plan("B", search, (1, 3), "compare", 2, "complete")
    events = plan_events(plan, Visitor("accept", False), SCHOOLS)
    assert [name for name, _ in events] == [
        "page_view", "consent_update", "search", "view_search_results",
        "compare_add", "compare_add", "compare_view", "page_view",
        "school_profile_view", "generate_lead"]
    params = [p for _, p in events]
    assert params[0] == {"page": "index"}
    assert params[1] == {"analytics_storage": "granted", "ad_storage": "granted"}
    assert params[2] == {"experiment_variant": "B", "school_level": search.level, "location": search.location}
    assert params[3] == {"experiment_variant": "B", "results_count": search.n_results}
    assert params[4] == {"experiment_variant": "B", "school_id": tray[0], "list_position": 1, "compare_count": 1}
    assert params[5] == {"experiment_variant": "B", "school_id": tray[1], "list_position": 3, "compare_count": 2}
    assert params[6] == {"experiment_variant": "B", "compare_count": 2, "school_ids": ",".join(tray)}
    assert params[7] == {"page": "school"}
    assert params[8] == {"experiment_variant": "B", "school_id": tray[1], "source": "compare"}
    assert params[9] == {"experiment_variant": "B", "school_id": tray[1], "source": "compare",
                         "form_complete": True, "lead_type": "info_request"}


def test_plan_events_results_profile_reject():
    search = OPTIONS[0]
    shown = search_results(SCHOOLS, search.location, search.level)
    plan = Plan("A", search, (), "results", 2, "incomplete")
    events = plan_events(plan, Visitor("reject", True), SCHOOLS)
    assert events[1] == ("consent_update", {"analytics_storage": "denied", "ad_storage": "denied"})
    assert events[-2] == ("school_profile_view", {"experiment_variant": "A", "school_id": shown[1]["id"],
                                                  "source": "results"})
    assert events[-1][1]["form_complete"] is False


def test_plan_events_ignore_and_bounce():
    plan = Plan("A", None, (), None, None, None)
    assert plan_events(plan, Visitor("ignore", False), SCHOOLS) == [("page_view", {"page": "index"})]
    search = next(o for o in OPTIONS if o.level == "")
    events = plan_events(Plan("A", search, (), None, None, None), Visitor("ignore", False), SCHOOLS)
    assert [n for n, _ in events] == ["page_view", "search", "view_search_results"]
    assert "school_level" not in events[1][1] and "search_term" not in events[1][1]


def test_visitor_rng_is_deterministic():
    a = plan_visit("B", visitor_rng(7, "v00001"), CFG, OPTIONS)
    b = plan_visit("B", visitor_rng(7, "v00001"), CFG, OPTIONS)
    assert a == b
    assert visitor_rng(7, "v00001").random() != visitor_rng(7, "v00002").random()
