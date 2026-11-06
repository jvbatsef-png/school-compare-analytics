"""Browser executor against the local site, with every Google request aborted (the suite stays offline)."""
import pytest

from simulator import browser_run
from simulator.behavior import (
    Plan, Visitor, load_config, load_schools, plan_events, plan_visit, search_options, search_results,
    visitor_rng,
)

CFG = load_config()
SCHOOLS = load_schools()
OPTIONS = search_options(SCHOOLS)
# Every path exercised often, and a short flush: these visitors send nothing to GA4 anyway.
TEST_CFG = {
    **CFG,
    "real": {**CFG["real"], "flush_quiet_seconds": 0.2, "flush_max_seconds": 1},
    "funnel": {**CFG["funnel"], "search": 0.95, "compare_b": 0.6,
               "profile": {"no_compare": 0.8, "compare": 0.8},
               "lead_given_profile": {"no_compare": 0.7, "compare": 0.7}},
}


@pytest.fixture
def new_context(browser):
    contexts = []

    def _new():
        context = browser.new_context()
        context.set_default_timeout(5000)
        context.route(browser_run.GOOGLE_HOSTS, lambda route: route.abort())
        contexts.append(context)
        return context

    yield _new
    for context in contexts:
        context.close()


def _visit(new_context, site_url, visitor_id, visitor, cfg=TEST_CFG):
    return browser_run.visit(new_context(), site_url, visitor_id, visitor, cfg, SCHOOLS, OPTIONS)


def _logged(lines):
    return [(line["event"], line["params"]) for line in lines[:-1]]


def test_logged_events_equal_plan_events(new_context, site_url):
    banners = ("accept", "reject", "ignore")
    for i in range(1, 13):
        visitor_id = f"v{i:05d}"
        visitor = Visitor(banners[i % 3], False)
        lines = _visit(new_context, site_url, visitor_id, visitor)
        end = lines[-1]
        assert (end["event"], end["status"], end["error_step"]) == ("visit_end", "ok", None), end
        assert all(line["run"] == "real" and line["visitor_id"] == visitor_id for line in lines)
        variant = end["variant"]
        plan = plan_visit(variant, visitor_rng(TEST_CFG["seed"], visitor_id + "/plan"), TEST_CFG, OPTIONS)
        assert _logged(lines) == plan_events(plan, visitor, SCHOOLS), visitor_id


@pytest.mark.parametrize("option", OPTIONS[:: max(1, len(OPTIONS) // 5)][:5], ids=lambda o: f"{o.location}|{o.level}")
def test_cards_match_python_port(new_context, site_url, option):
    page = new_context().new_page()
    page.goto(site_url)
    page.wait_for_function(browser_run.READY)
    page.select_option("#level", option.level)
    page.select_option("#location", option.location)
    page.click(browser_run.SEARCH_SUBMIT)
    page.wait_for_function("() => !document.getElementById('results-count').hidden")
    ids = page.eval_on_selector_all("#results .card", "els => els.map(e => e.dataset.schoolId)")
    assert ids == [s["id"] for s in search_results(SCHOOLS, option.location, option.level)]


def test_ignore_banner_full_plan(new_context, site_url, monkeypatch):
    search = next(o for o in OPTIONS if o.n_results == 3) if any(o.n_results == 3 for o in OPTIONS) else OPTIONS[0]
    forced = Plan("B", search, (3, 1, 2), "compare", 3, "complete")
    monkeypatch.setattr(browser_run, "plan_visit", lambda *args: forced)
    context = new_context()
    context.add_init_script("localStorage.setItem('sca_variant', 'B');")
    visitor = Visitor("ignore", False)
    lines = browser_run.visit(context, site_url, "v00001", visitor, TEST_CFG, SCHOOLS, OPTIONS)
    assert lines[-1]["status"] == "ok", lines[-1]["error_step"]
    assert _logged(lines) == plan_events(forced, visitor, SCHOOLS)
    assert "consent_update" not in [line["event"] for line in lines]


def test_ad_blocker_sends_nothing(browser, site_url):
    context = browser.new_context()  # no test-side abort: the executor's own blocker must stop Google
    context.set_default_timeout(5000)
    reached = []
    context.on("requestfinished",
               lambda r: reached.append(r.url) if browser_run.GOOGLE_HOSTS.search(r.url) else None)
    try:
        lines = browser_run.visit(context, site_url, "v00003", Visitor("accept", True), TEST_CFG, SCHOOLS, OPTIONS)
    finally:
        context.close()
    end = lines[-1]
    assert reached == []
    assert end["status"] == "ok" and end["ga_requests"] == 0 and end["ga_client_id"] is None
    assert all(line["ad_blocker"] is True for line in lines)


def test_failed_step_is_logged(new_context, site_url, monkeypatch):
    monkeypatch.setattr(browser_run, "SEARCH_SUBMIT", "#never-there")
    monkeypatch.setattr(browser_run, "plan_visit", lambda *args: Plan("A", OPTIONS[0], (), None, None, None))
    context = new_context()
    context.set_default_timeout(1000)
    lines = browser_run.visit(context, site_url, "v00004", Visitor("accept", False), TEST_CFG, SCHOOLS, OPTIONS)
    end = lines[-1]
    assert (end["status"], end["error_step"]) == ("error", "search")
    assert [line["event"] for line in lines[:-1]] == ["page_view", "consent_update"]


def test_failed_flush_is_logged(new_context, site_url, monkeypatch):
    def broken_flush(*args):
        raise browser_run.PlaywrightError("page closed during flush")

    monkeypatch.setattr(browser_run, "_flush", broken_flush)
    monkeypatch.setattr(browser_run, "plan_visit", lambda *args: Plan("A", None, (), None, None, None))
    lines = browser_run.visit(new_context(), site_url, "v00005", Visitor("accept", False), TEST_CFG, SCHOOLS, OPTIONS)
    end = lines[-1]
    assert (end["status"], end["error_step"]) == ("error", "flush")
