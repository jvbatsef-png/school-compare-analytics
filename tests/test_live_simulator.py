"""Live check of the browser executor against the published site.

Run by hand: uv run pytest -m live tests/test_live_simulator.py
Nothing reaches GA4: every /g/collect request is aborted in the test's context.
"""
import re

import pytest

from simulator import browser_run
from simulator.behavior import Visitor, load_config, load_schools, search_options
from tests.ga4_hits import LIVE_URL

pytestmark = pytest.mark.live


def test_live_accepting_visitor(browser):
    cfg = load_config()
    schools = load_schools()
    context = browser.new_context(user_agent=browser_run.USER_AGENT)
    context.set_default_timeout(browser_run.VISIT_TIMEOUT_MS)
    context.route(browser_run.COLLECT, lambda route: route.abort())
    try:
        lines = browser_run.visit(context, LIVE_URL, "v00001", Visitor("accept", False), cfg, schools,
                                  search_options(schools))
    finally:
        context.close()
    end = lines[-1]
    assert end["status"] == "ok", end["error_step"]
    assert end["ga_requests"] > 0
    assert re.fullmatch(r"\d+\.\d+", end["ga_client_id"] or ""), end["ga_client_id"]
