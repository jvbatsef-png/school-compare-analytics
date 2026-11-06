from scripts.make_schools import make_schools
from tests.site_helpers import assert_valid, events_named, pushes

RESULTS_SHOWN = "() => document.querySelector('#results .card') || !document.querySelector('#no-results').hidden"


def search(page, q="", level="", location=""):
    page.fill("#q", q)
    page.select_option("#level", level)
    page.wait_for_selector("#location option:nth-child(2)", state="attached")
    page.select_option("#location", location)
    page.click("#search-form button[type=submit]")
    page.wait_for_function("() => dataLayer.some(i => i.event === 'view_search_results')")


def card_ids(page) -> list[str]:
    return page.eval_on_selector_all("#results .card", "els => els.map(e => e.dataset.schoolId)")


def test_search_fires_both_events(open_page):
    word = make_schools()[0]["name"].split()[1]
    page = open_page("index.html")
    search(page, q=word.lower(), level="", location="")
    events = [p for p in pushes(page) if p["event"] in ("search", "view_search_results")]
    assert [e["event"] for e in events] == ["search", "view_search_results"]
    for e in events:
        assert_valid(e)
    assert events[0]["search_term"] == word.lower()
    assert events[1]["results_count"] == len(card_ids(page)) > 0


def test_empty_optional_fields_are_omitted(open_page):
    page = open_page("index.html")
    search(page)
    [s] = events_named(page, "search")
    assert not {"search_term", "school_level", "location"} & set(s)
    [v] = events_named(page, "view_search_results")
    assert "search_term" not in v
    assert v["results_count"] == 200


def test_filters_by_level_and_location(open_page):
    page = open_page("index.html")
    search(page, level="high", location="Austin, TX")
    expected = [s["id"] for s in make_schools() if s["level"] == "high" and (s["city"], s["state"]) == ("Austin", "TX")]
    assert sorted(card_ids(page)) == sorted(expected)
    [s] = events_named(page, "search")
    assert (s["school_level"], s["location"]) == ("high", "Austin, TX")


def test_zero_results(open_page):
    page = open_page("index.html")
    search(page, q="zzzz")
    assert page.is_visible("#no-results")
    [v] = events_named(page, "view_search_results")
    assert v["results_count"] == 0


def test_reload_does_not_refire(open_page):
    page = open_page("index.html")
    search(page, level="middle")
    before = card_ids(page)
    page.reload()
    page.wait_for_function(RESULTS_SHOWN)
    assert card_ids(page) == before
    assert events_named(page, "search") == events_named(page, "view_search_results") == []


def test_back_from_profile_does_not_refire(open_page):
    page = open_page("index.html")
    search(page, level="elementary")
    before = card_ids(page)
    page.click("#results .card a")
    page.wait_for_url("**/school.html?id=*&src=results")
    page.go_back()
    page.wait_for_function(RESULTS_SHOWN)
    assert card_ids(page) == before
    assert events_named(page, "search") == []


def test_variant_a_has_no_compare_button(open_page):
    page = open_page("index.html", variant="A")
    search(page)
    assert page.locator(".card .compare-btn").count() == 0


def test_variant_b_has_compare_button(open_page):
    page = open_page("index.html", variant="B")
    search(page)
    assert page.locator(".card .compare-btn").count() == 200


def test_cleared_fields_overwrite_previous_values(open_page):
    # GTM's data model keeps keys from earlier pushes, so an omitted field would resend the old value.
    page = open_page("index.html")
    search(page, q="school", level="high", location="Austin, TX")
    search(page)
    page.wait_for_function("() => dataLayer.filter(i => i.event === 'search').length === 2")
    cleared = page.evaluate("""() => {
        const s = dataLayer.filter(i => i.event === 'search')[1];
        return ['search_term', 'school_level', 'location'].map(k => k in s && s[k] === undefined);
    }""")
    assert cleared == [True, True, True]
    [_, second] = events_named(page, "search")
    assert not {"search_term", "school_level", "location"} & set(second)


def test_location_options(open_page):
    # built from data, "Any location" first, then sorted unique "City, ST"
    page = open_page("index.html")
    page.wait_for_selector("#location option:nth-child(2)", state="attached")
    values = page.eval_on_selector_all("#location option", "els => els.map(e => e.value)")
    labels = page.eval_on_selector_all("#location option", "els => els.map(e => e.textContent)")
    expected = sorted({f'{s["city"]}, {s["state"]}' for s in make_schools()})
    assert values == [""] + expected and labels[0] == "Any location"


def test_location_restored_from_url(open_page):
    page = open_page("index.html?location=Austin%2C+TX")
    page.wait_for_selector("#results .card")
    assert page.input_value("#location") == "Austin, TX"
    assert all("Austin, TX" in m for m in page.eval_on_selector_all("#results .meta", "els => els.map(e => e.textContent)"))


def test_unknown_location_is_ignored(open_page):
    page = open_page("index.html?location=tx")
    page.wait_for_selector("#results .card")
    assert page.input_value("#location") == ""
    search(page)
    [s] = events_named(page, "search")
    assert "location" not in s
