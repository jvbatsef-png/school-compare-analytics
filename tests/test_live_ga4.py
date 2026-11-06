"""Live check against the published site: capture every GA4 hit, abort it, and compare with events.yaml.

Run by hand after publishing: uv run pytest -m live
Nothing reaches GA4: every /g/collect request is aborted after it is read.
"""
import re

import pytest

from tests.ga4_hits import LIVE_URL, HitLog
from tests.test_site_compare import toggle
from tests.test_site_profile import PROFILE_READY, submit_lead
from tests.test_site_search import card_ids, search
from tracking.spec import load_spec

pytestmark = pytest.mark.live

COLLECT = re.compile(r"/g/collect")
GRANTED, DENIED = "G111", "G100"


def _key(param: dict) -> str:
    return ("epn." if param["type"] == "int" else "ep.") + param["name"]


@pytest.fixture
def live(browser):
    context = browser.new_context()
    context.set_default_timeout(15000)
    context.add_init_script(
        "if (localStorage.getItem('sca_variant') === null) localStorage.setItem('sca_variant', 'B');")
    log = HitLog()

    def capture(route):
        log.add(route.request.url, route.request.post_data)
        route.abort()

    context.route(COLLECT, capture)
    page = context.new_page()
    page.goto(LIVE_URL)
    page.wait_for_load_state("networkidle")
    yield page, log.hits
    context.close()


def _wait_for(page, hits, event: str, seconds: int = 10):
    for _ in range(seconds * 2):
        if any(h.get("en") == event for h in hits):
            return
        page.wait_for_timeout(500)
    pytest.fail(f"no {event} hit within {seconds}s; got {[h.get('en') for h in hits]}")


def test_live_granted_journey(live):
    page, hits = live
    _wait_for(page, hits, "page_view")
    before = len(hits)
    assert all(h["gcs"] == DENIED for h in hits), [h["gcs"] for h in hits]

    page.click("#consent-accept")
    # A term puts ?q= in the URL, which is what enhanced measurement "Site search" would react to.
    search(page, q="school", location="Austin, TX")
    ids = card_ids(page)
    toggle(page, 1)
    toggle(page, 2)
    page.click("#compare-open")
    # gtag.js batches hits; read them before leaving the page so none is flushed by an unload beacon.
    for event in ("consent_update", "search", "view_search_results", "compare_add", "compare_view"):
        _wait_for(page, hits, event)
    page.click(f"#compare-table a[href*='{ids[1]}']")
    page.wait_for_function(PROFILE_READY)
    submit_lead(page)
    page.wait_for_selector("#lead-sent", state="visible")
    _wait_for(page, hits, "generate_lead")

    after = hits[before:]
    for event in load_spec()["events"]:
        mine = [h for h in after if h.get("en") == event["name"]]
        assert mine, f"no {event['name']} hit"
        allowed = {_key(p) for p in event["params"]}
        for h in mine:
            assert h["gcs"] == GRANTED, (event["name"], h["gcs"])
            missing = {_key(p) for p in event["params"] if p["required"]} - set(h)
            assert not missing, (event["name"], missing)
            extra = {k for k in h if k.startswith(("ep.", "epn."))} - allowed
            assert not extra, (event["name"], extra)
    [results_hit] = [h for h in after if h.get("en") == "view_search_results"]
    assert results_hit.get("ep.search_term") == "school"
    assert any(c["name"] == "_ga" for c in page.context.cookies())


def test_live_cleared_fields_not_resent(live):
    # A second search with empty fields must not carry the first search's values (GTM data model).
    page, hits = live
    page.click("#consent-accept")
    search(page, q="school", level="high", location="Austin, TX")
    search(page)
    page.wait_for_function("() => dataLayer.filter(i => i.event === 'search').length === 2")
    for _ in range(20):
        if len([h for h in hits if h.get("en") == "search"]) == 2:
            break
        page.wait_for_timeout(500)
    first, second = [h for h in hits if h.get("en") == "search"]
    assert first.get("ep.location") == "Austin, TX"
    assert not {"ep.search_term", "ep.school_level", "ep.location"} & set(second), second


def test_live_denied_hits_are_cookieless(live):
    page, hits = live
    page.click("#consent-reject")
    search(page)
    _wait_for(page, hits, "view_search_results")
    assert hits and all(h["gcs"] == DENIED for h in hits), [h["gcs"] for h in hits]
    assert not any(c["name"] == "_ga" for c in page.context.cookies())
