from tests.site_helpers import assert_valid, events_named
from tests.test_site_search import card_ids, search


def toggle(page, position: int):
    """Click Compare on the card at a 1-based position in the shown list."""
    page.locator("#results .card").nth(position - 1).locator(".compare-btn").click()


def tray_ids(page) -> list[str]:
    return page.eval_on_selector_all("#compare-tray [data-school-id]", "els => els.map(e => e.dataset.schoolId)")


def searched(open_page):
    page = open_page("index.html", variant="B")
    search(page)
    return page


def test_compare_add_params(open_page):
    page = searched(open_page)
    ids = card_ids(page)
    toggle(page, 2)
    toggle(page, 5)
    adds = events_named(page, "compare_add")
    for a in adds:
        assert_valid(a)
    assert [(a["school_id"], a["list_position"], a["compare_count"]) for a in adds] == [
        (ids[1], 2, 1), (ids[4], 5, 2)]


def test_fourth_add_rejected(open_page):
    page = searched(open_page)
    assert not page.is_visible("#compare-full")
    for position in (1, 2, 3, 4):
        toggle(page, position)
    assert len(events_named(page, "compare_add")) == 3
    assert page.is_visible("#compare-full")
    assert tray_ids(page) == card_ids(page)[:3]


def test_remove_fires_nothing(open_page):
    page = searched(open_page)
    toggle(page, 1)
    toggle(page, 1)
    assert len(events_named(page, "compare_add")) == 1
    assert tray_ids(page) == []


def test_compare_view_once_per_opening(open_page):
    page = searched(open_page)
    ids = card_ids(page)
    for position in (3, 1, 2):
        toggle(page, position)
    page.click("#compare-open")
    assert page.is_visible("#compare-table")
    [view] = events_named(page, "compare_view")
    assert_valid(view)
    assert view["compare_count"] == 3
    assert view["school_ids"] == ",".join([ids[2], ids[0], ids[1]])
    assert page.locator("#compare-table th[data-school-id]").count() == 3
    toggle(page, 1)
    assert page.locator("#compare-table th[data-school-id]").count() == 2
    assert len(events_named(page, "compare_view")) == 1
    page.click("#compare-close")
    assert not page.is_visible("#compare-table")
    page.click("#compare-open")
    assert len(events_named(page, "compare_view")) == 2


def test_compare_needs_two(open_page):
    page = searched(open_page)
    toggle(page, 1)
    assert page.is_disabled("#compare-open")
    toggle(page, 2)
    assert page.is_enabled("#compare-open")


def test_comparison_links_carry_compare_source(open_page):
    page = searched(open_page)
    toggle(page, 1)
    toggle(page, 2)
    page.click("#compare-open")
    hrefs = page.eval_on_selector_all("#compare-table a", "els => els.map(e => e.getAttribute('href'))")
    assert hrefs == [f"school.html?id={i}&src=compare" for i in card_ids(page)[:2]]
