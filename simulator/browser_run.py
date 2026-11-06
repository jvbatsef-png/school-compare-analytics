"""Browser executor: plays simulated visitors on the site and logs what the page actually pushed.

The site draws the A/B variant; the executor reads it after load and asks the behaviour model for a plan.

uv run python -m simulator.browser_run --target 20 [--headed]
"""
import argparse
import queue
import re
import threading
import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Error as PlaywrightError, sync_playwright

from simulator.behavior import (
    ROOT, Search, Visitor, draw_visitor, load_config, load_schools, plan_visit, search_options, visitor_rng,
)
from simulator.ground_truth import append, by_visitor, drop_torn_tail, read, start_line, utc_now, visitor_lines

OUT_PATH = ROOT / "simulator" / "runs" / "real_run.jsonl"
VISIT_TIMEOUT_MS = 15000

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

        step = "flush"
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


class RunAborted(RuntimeError):
    pass


def close_interrupted(lines: list[dict]) -> list[dict]:
    """visit_end lines for visitors cut off mid-visit. They count toward the target and are never re-run:
    their hits may already have reached GA4."""
    ends = []
    for visitor_id, own in by_visitor(lines).items():
        if own[-1]["event"] != "visit_end":
            last = own[-1]
            ends.append({**last, "seq": last["seq"] + 1, "ga_requests": None, "status": "error",
                         "error_step": "interrupted", "event": "visit_end", "params": {}})
    return ends


def next_ids(lines: list[dict], target: int) -> list[str]:
    """Ids up to `target` with no line yet; an id with any line (even visit_start) is never run again."""
    done = set(by_visitor(lines))
    return [f"v{n:05d}" for n in range(1, target + 1) if f"v{n:05d}" not in done]


def should_abort(lines: list[dict], max_rate: float, min_finished: int) -> bool:
    ends = [line for line in lines if line["event"] == "visit_end"]
    if len(ends) < min_finished:
        return False
    return sum(e["status"] == "error" for e in ends) / len(ends) > max_rate


def _join_all(threads, stop: threading.Event) -> None:
    """Ctrl-C stops new visitors but lets the ones in flight finish and be logged, then re-raises."""
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        stop.set()
        for thread in threads:
            thread.join()
        raise


def run_real(cfg: dict, target: int, out_path: Path, site_url: str, workers: int,
             offline: bool = False, headed: bool = False) -> None:
    """Run visitors until out_path holds `target` of them; `offline` aborts Google hosts (tests only)."""
    if out_path.exists():
        drop_torn_tail(out_path)
    existing = read(out_path) if out_path.exists() else []
    closed = close_interrupted(existing)
    if closed:
        append(out_path, closed)
    ends = [line for line in existing + closed if line["event"] == "visit_end"]
    todo: queue.Queue[str] = queue.Queue()
    for visitor_id in next_ids(existing + closed, target):
        todo.put(visitor_id)
    schools = load_schools()
    options = search_options(schools)
    lock = threading.Lock()
    stop = threading.Event()
    failures: list[BaseException] = []

    def worker() -> None:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=not headed)
                while not stop.is_set():
                    try:
                        visitor_id = todo.get_nowait()
                    except queue.Empty:
                        break
                    visitor = draw_visitor(visitor_rng(cfg["seed"], visitor_id), cfg)
                    with lock:  # on record before any request leaves the browser
                        append(out_path, [start_line("real", visitor_id, visitor)])
                    context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1366, "height": 768})
                    context.set_default_timeout(VISIT_TIMEOUT_MS)
                    if offline:
                        context.route(GOOGLE_HOSTS, lambda route: route.abort())
                    lines = visit(context, site_url, visitor_id, visitor, cfg, schools, options)
                    with lock:
                        append(out_path, lines)
                        ends.append(lines[-1])
                        real = cfg["real"]
                        if should_abort(ends, real["max_error_rate"], real["min_visitors_before_abort"]):
                            stop.set()
                    try:
                        context.close()
                    except PlaywrightError:
                        pass  # the visitor is logged; a dead browser surfaces on the next new_context
                browser.close()
        except BaseException as exc:  # a broken worker stops the run instead of dying silently
            failures.append(exc)
            stop.set()

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    _join_all(threads, stop)
    if failures:
        raise failures[0]
    if stop.is_set():
        errors = sum(e["status"] == "error" for e in ends)
        raise RunAborted(f"{errors} of {len(ends)} visitors failed; stopped above the error threshold")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulated visitors on the live site (real run).")
    parser.add_argument("--target", type=int, required=True, help="visitors the log should hold when done")
    parser.add_argument("--headed", action="store_true", help="show the browser windows")
    args = parser.parse_args()
    cfg = load_config()
    try:
        run_real(cfg, args.target, OUT_PATH, cfg["site_url"], cfg["real"]["workers"], headed=args.headed)
    finally:
        ends = [line for line in read(OUT_PATH) if line["event"] == "visit_end"] if OUT_PATH.exists() else []
        errors = sum(e["status"] == "error" for e in ends)
        print(f"{len(ends)} visitors in {OUT_PATH.relative_to(ROOT)}, {errors} errors")


if __name__ == "__main__":
    main()
