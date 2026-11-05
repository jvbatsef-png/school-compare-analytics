"""Serve site/ locally and open pages with a seeded variant and consent choice."""
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SITE_DIR = Path(__file__).parent.parent / "site"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def site_url():
    handler = functools.partial(_QuietHandler, directory=str(SITE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


@pytest.fixture
def open_page(browser, site_url):
    contexts = []

    def _open(path: str, variant: str | None = "B", consent: str | None = "denied",
              init_scripts: tuple[str, ...] = ()):
        context = browser.new_context()
        context.set_default_timeout(5000)
        contexts.append(context)
        seeds = {k: v for k, v in {"sca_variant": variant, "sca_consent": consent}.items() if v}
        # Seed only absent keys, so the page's own writes survive a reload.
        context.add_init_script(
            f"(() => {{ const s = {json.dumps(seeds)}; for (const k in s) "
            "if (localStorage.getItem(k) === null) localStorage.setItem(k, s[k]); })();")
        for script in init_scripts:
            context.add_init_script(script)
        page = context.new_page()
        page.goto(site_url + path)
        return page

    yield _open
    for context in contexts:
        context.close()
