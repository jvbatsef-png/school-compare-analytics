import re
from pathlib import Path

import pytest

from scripts.make_gtm_container import load_ids
from tests.site_helpers import assert_valid, events_named, layer, pushes
from tracking.spec import load_spec

SITE_DIR = Path(__file__).parent.parent / "site"
COLLECT_ERRORS = ("window.__errors = []; window.addEventListener('error', "
                  "e => window.__errors.push(String(e.message)));")
BLOCK_STORAGE = ("Storage.prototype.getItem = () => { throw new Error('blocked'); };"
                 "Storage.prototype.setItem = () => { throw new Error('blocked'); };")


def _variant(page) -> str:
    return page.evaluate("SCA.getVariant()")


def test_variant_is_stable(open_page):
    page = open_page("index.html", variant=None)
    first = _variant(page)
    page.reload()
    assert _variant(page) == first
    assert page.evaluate("localStorage.getItem('sca_variant')") == first


@pytest.mark.parametrize("draw, expected", [("0.1", "A"), ("0.9", "B")])
def test_variant_draw_uses_threshold(open_page, draw, expected):
    page = open_page("index.html", variant=None, init_scripts=(f"Math.random = () => {draw};",))
    assert _variant(page) == expected


def test_corrupt_variant_is_redrawn(open_page):
    page = open_page("index.html", variant="C")
    variant = _variant(page)
    assert variant in {"A", "B"}
    assert page.evaluate("localStorage.getItem('sca_variant')") == variant


def test_blocked_storage_still_works(open_page):
    page = open_page("index.html", variant=None, consent=None,
                     init_scripts=(COLLECT_ERRORS, BLOCK_STORAGE))
    assert _variant(page) in {"A", "B"}
    assert _variant(page) == _variant(page)
    page.click("#consent-reject")
    [push] = events_named(page, "consent_update")
    assert_valid(push)
    assert page.evaluate("window.__errors") == []


def test_consent_default_denied_first(open_page):
    page = open_page("index.html")
    assert layer(page)[0] == ["consent", "default", load_spec()["consent"]]


@pytest.mark.parametrize("button, state", [("#consent-accept", "granted"), ("#consent-reject", "denied")])
def test_consent_choice(open_page, button, state):
    page = open_page("index.html", consent=None)
    assert page.is_visible("#consent-banner")
    page.click(button)
    items = layer(page)
    update_at = max(i for i, it in enumerate(items) if isinstance(it, list) and it[:2] == ["consent", "update"])
    push_at = next(i for i, it in enumerate(items) if isinstance(it, dict) and it["event"] == "consent_update")
    assert update_at < push_at
    assert items[update_at][2] == {k: state for k in load_spec()["consent"]}
    push = items[push_at]
    assert_valid(push)
    assert (push["analytics_storage"], push["ad_storage"]) == (state, state)
    assert not page.is_visible("#consent-banner")
    page.reload()
    assert not page.is_visible("#consent-banner")
    assert events_named(page, "consent_update") == []
    assert ["consent", "update", {k: state for k in load_spec()["consent"]}] in layer(page)


def test_head_order():
    pages = sorted(SITE_DIR.glob("*.html"))
    assert pages
    for path in pages:
        html = path.read_text(encoding="utf-8")
        default_at = html.find("'consent', 'default'")
        slot_at = html.find("GTM slot")
        script_at = re.search(r"<script src=", html)
        assert -1 < default_at < slot_at, path.name
        assert script_at and slot_at < script_at.start(), path.name


@pytest.mark.parametrize("state", ["granted", "denied"])
def test_stored_consent_applied_in_head(open_page, state):
    """A saved choice is re-applied right after the default, before any site script or GTM runs."""
    # readyState turns "interactive" after parsing and before any deferred script runs.
    snapshot = ("document.addEventListener('readystatechange', () => { if (document.readyState === 'interactive') "
                "window.__early = window.dataLayer.map(i => Array.from(i)); });")
    page = open_page("index.html", consent=state, init_scripts=(snapshot,))
    expected = ["consent", "update", {k: state for k in load_spec()["consent"]}]
    assert page.evaluate("window.__early")[1] == expected
    items = layer(page)
    assert sum(1 for it in items if isinstance(it, list) and it[:2] == ["consent", "update"]) == 1
    for path in sorted(SITE_DIR.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        assert -1 < html.find("sca_consent") < html.find("GTM slot"), path.name


def test_gtm_snippet_on_every_page():
    gtm = load_ids()["gtm_container_id"]
    for path in sorted(SITE_DIR.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        snippet_at = html.find("googletagmanager.com/gtm.js")
        assert html.find("GTM slot") < snippet_at < re.search(r"<script src=", html).start(), path.name
        assert html.count(gtm) == 2, path.name  # head script + noscript iframe
        assert re.search(r"<body[^>]*>\s*<noscript><iframe src=\"https://www\.googletagmanager\.com/ns\.html\?id=" + gtm, html), path.name
        assert 'rel="icon" href="favicon.svg"' in html, path.name


def test_site_works_with_gtm_blocked(open_page):
    # conftest aborts Google requests; the full B journey still pushes every funnel event
    from tests.test_site_compare import toggle
    from tests.test_site_profile import PROFILE_READY, submit_lead
    from tests.test_site_search import card_ids, search

    blocked = []
    page = open_page("index.html", variant="B")
    page.context.on("requestfailed", lambda r: blocked.append(r.url))
    page.reload()
    search(page)
    ids = card_ids(page)
    toggle(page, 1)
    toggle(page, 2)
    page.click("#compare-open")
    names = [p["event"] for p in pushes(page)]
    page.click(f"#compare-table a[href*='{ids[1]}']")
    page.wait_for_function(PROFILE_READY)
    submit_lead(page)
    page.wait_for_selector("#lead-sent", state="visible")
    names += [p["event"] for p in pushes(page)]
    funnel = {e["name"] for e in load_spec()["events"]} - {"consent_update"}
    assert funnel <= set(names)
    assert any("googletagmanager.com/gtm.js" in url for url in blocked)
