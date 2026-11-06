"""Browser executor: plays one simulated visitor on the site and logs what the page actually pushed.

The site draws the A/B variant; the executor reads it after load and asks the behaviour model for a plan.
"""
import re
import time

from playwright.sync_api import BrowserContext, Error as PlaywrightError

from simulator.behavior import Search, Visitor, plan_visit, visitor_rng
from simulator.ground_truth import utc_now, visitor_lines

GOOGLE_HOSTS = re.compile(r"https://([a-z0-9-]+\.)*(googletagmanager|google-analytics)\.com/")
COLLECT = re.compile(r"/g/collect")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

READY = "() => window.SCA && SCA.getVariant && document.querySelectorAll('#location option').length > 1"
PROFILE_READY = "() => !document.getElementById('profile').hidden"
SEARCH_SUBMIT = "#search-form button[type=submit]"
CARDS = "#results .card"
COMPARE_LINKS = "#compare-table th[data-school-id] a"
PUSHES = """() => (window.dataLayer || []).filter(
    item => item && typeof item.event === 'string' && !item.event.startsWith('gtm.')
).map(item => JSON.parse(JSON.stringify(item)))"""


def _wait_event(page, name: str, count: int = 1) -> None:
    page.wait_for_function(
        "([name, count]) => (window.dataLayer || []).filter(i => i && i.event === name).length >= count",
        arg=[name, count])


class _Log:
    """Events in the order the page pushed them, each stamped when it was read."""

    def __init__(self):
        self.events: list[tuple[str, dict, str]] = []
        self.seen = 0  # pushes already read on the current page

    def page_load(self, page_name: str) -> None:
        self.events.append(("page_view", {"page": page_name}, utc_now()))
        self.seen = 0

    def collect(self, page) -> None:
        pushes = page.evaluate(PUSHES)
        for push in pushes[self.seen:]:
            name = push.pop("event")
            self.events.append((name, push, utc_now()))
        self.seen = len(pushes)


def _flush(page, sent: list[float], quiet: float, cap: float) -> None:
    """Wait until no /g/collect request has gone out for `quiet` seconds (at most `cap`)."""
    start = time.monotonic()
    while True:
        now = time.monotonic()
        last = max(sent[-1] if sent else start, start)
        if now - last >= quiet or now - start >= cap:
            return
        page.wait_for_timeout(100)


def _client_id(context: BrowserContext) -> str | None:
    for cookie in context.cookies():
        if cookie["name"] == "_ga":
            parts = cookie["value"].split(".", 2)  # GA1.1.<random>.<timestamp>
            return parts[2] if len(parts) == 3 else None
    return None


def visit(context: BrowserContext, site_url: str, visitor_id: str, visitor: Visitor, cfg: dict,
          schools, options: list[Search]) -> list[dict]:
    """Ground-truth lines for one visitor (run="real"). The caller owns the context."""
    if visitor.ad_blocker:
        context.route(GOOGLE_HOSTS, lambda route: route.abort())
    sent: list[float] = []
    context.on("request", lambda r: sent.append(time.monotonic()) if COLLECT.search(r.url) else None)

    log = _Log()
    variant = None
    status, step = "ok", "load"
    page = context.new_page()
    try:
        page.goto(site_url)
        page.wait_for_function(READY)
        variant = page.evaluate("SCA.getVariant()")
        log.page_load("index")
        log.collect(page)

        step = "consent"
        if visitor.banner != "ignore":
            page.click("#consent-accept" if visitor.banner == "accept" else "#consent-reject")
            _wait_event(page, "consent_update")
            log.collect(page)

        plan = plan_visit(variant, visitor_rng(cfg["seed"], visitor_id + "/plan"), cfg, options)
        if plan.search:
            step = "search"
            page.select_option("#level", plan.search.level)
            page.select_option("#location", plan.search.location)
            page.click(SEARCH_SUBMIT)
            _wait_event(page, "view_search_results")
            log.collect(page)

        if plan.compare_positions:
            step = "compare"
            for n, pos in enumerate(plan.compare_positions, start=1):
                page.locator(CARDS).nth(pos - 1).locator(".compare-btn").click()
                _wait_event(page, "compare_add", n)
            page.click("#compare-open")
            _wait_event(page, "compare_view")
            log.collect(page)

        if plan.profile_from:
            step = "profile"
            links = page.locator(COMPARE_LINKS) if plan.profile_from == "compare" else page.locator(f"{CARDS} h3 a")
            links.nth(plan.profile_index - 1).click()
            page.wait_for_url(re.compile(r"school\.html"))
            log.page_load("school")
            page.wait_for_function(PROFILE_READY)
            _wait_event(page, "school_profile_view")
            log.collect(page)

        if plan.lead:
            step = "lead"
            page.fill("#email", "parent@example.com")
            if plan.lead == "complete":
                page.select_option("#grade", index=1)
                page.select_option("#start-year", index=1)
                page.fill("#message", "We move to the area next spring.")
            page.click("#lead-submit")
            _wait_event(page, "generate_lead")
            log.collect(page)

        step = None
        real = cfg["real"]
        _flush(page, sent, real["flush_quiet_seconds"], real["flush_max_seconds"])
    except PlaywrightError:
        status = "error"
        try:
            log.collect(page)  # events pushed before the failure stay logged
        except PlaywrightError:
            pass
    client_id = _client_id(context) if visitor.banner == "accept" and not visitor.ad_blocker else None
    return visitor_lines("real", visitor_id, variant, visitor, log.events, client_id, len(sent), status,
                         step if status == "error" else None, end_ts=utc_now())
