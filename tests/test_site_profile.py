import json

import pytest

from tests.site_helpers import assert_valid, events_named, layer, pushes
from tests.test_site_compare import toggle
from tests.test_site_search import card_ids, search

PROFILE_READY = "() => !document.getElementById('profile').hidden || !document.getElementById('not-found').hidden"
EMAIL = "parent@example.com"
MESSAGE = "We move to the area next spring."


def open_profile(open_page, query: str):
    page = open_page("school.html" + query)
    page.wait_for_function(PROFILE_READY)
    return page


def submit_lead(page, email=EMAIL, complete=True):
    page.fill("#email", email)
    if complete:
        page.select_option("#grade", index=1)
        page.select_option("#start-year", index=1)
        page.fill("#message", MESSAGE)
    page.click("#lead-submit")


@pytest.mark.parametrize("query, source", [
    ("?id=sch_042&src=results", "results"), ("?id=sch_042&src=compare", "compare"),
    ("?id=sch_042", "direct"), ("?id=sch_042&src=junk", "direct")])
def test_profile_view_sources(open_page, query, source):
    page = open_profile(open_page, query)
    [view] = events_named(page, "school_profile_view")
    assert_valid(view)
    assert (view["school_id"], view["source"]) == ("sch_042", source)
    assert page.is_visible("#profile h1")


@pytest.mark.parametrize("query", ["?id=sch_999", ""])
def test_unknown_school(open_page, query):
    page = open_profile(open_page, query)
    assert page.is_visible("#not-found")
    assert not page.is_visible("#lead-form")
    assert pushes(page) == []


def test_lead_complete(open_page):
    page = open_profile(open_page, "?id=sch_042&src=results")
    submit_lead(page)
    page.wait_for_selector("#lead-sent", state="visible")
    [lead] = events_named(page, "generate_lead")
    assert_valid(lead)
    assert lead == {"event": "generate_lead", "experiment_variant": "B", "school_id": "sch_042",
                    "source": "results", "form_complete": True, "lead_type": "info_request"}
    dump = json.dumps(layer(page))
    assert EMAIL not in dump and MESSAGE not in dump


def test_lead_incomplete(open_page):
    page = open_profile(open_page, "?id=sch_042")
    submit_lead(page, complete=False)
    page.wait_for_selector("#lead-sent", state="visible")
    [lead] = events_named(page, "generate_lead")
    assert lead["form_complete"] is False


def test_whitespace_message_is_not_complete(open_page):
    page = open_profile(open_page, "?id=sch_042")
    page.fill("#email", EMAIL)
    page.select_option("#grade", index=1)
    page.select_option("#start-year", index=1)
    page.fill("#message", "   ")
    page.click("#lead-submit")
    page.wait_for_selector("#lead-sent", state="visible")
    assert events_named(page, "generate_lead")[0]["form_complete"] is False


def test_invalid_email(open_page):
    page = open_profile(open_page, "?id=sch_042")
    submit_lead(page, email="not-an-email")
    assert page.is_visible("#email-error")
    page.wait_for_timeout(500)
    assert events_named(page, "generate_lead") == []
    assert not page.is_visible("#lead-sent")


def test_double_click_single_lead(open_page):
    page = open_profile(open_page, "?id=sch_042")
    page.fill("#email", EMAIL)
    page.dblclick("#lead-submit")
    page.wait_for_selector("#lead-sent", state="visible")
    page.wait_for_timeout(500)
    assert len(events_named(page, "generate_lead")) == 1


def test_full_funnel_variant_b(open_page):
    page = open_page("index.html", variant="B")
    search(page)
    ids = card_ids(page)
    toggle(page, 1)
    toggle(page, 2)
    page.click("#compare-open")
    assert [p["event"] for p in pushes(page)] == [
        "search", "view_search_results", "compare_add", "compare_add", "compare_view"]
    page.click(f"#compare-table a[href*='{ids[1]}']")
    page.wait_for_function(PROFILE_READY)
    submit_lead(page)
    page.wait_for_selector("#lead-sent", state="visible")
    events = pushes(page)
    assert [p["event"] for p in events] == ["school_profile_view", "generate_lead"]
    for p in events:
        assert_valid(p)
        assert (p["school_id"], p["source"], p["experiment_variant"]) == (ids[1], "compare", "B")
