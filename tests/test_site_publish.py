from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
PAGES = ["index.html", "school.html?id=sch_042", "privacy.html"]


def test_pages_workflow_publishes_site():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
    triggers = workflow[True]  # YAML 1.1 reads the bare key `on` as True
    assert "main" in triggers["push"]["branches"]
    assert "workflow_dispatch" in triggers
    assert workflow["permissions"] == {"contents": "read", "pages": "write", "id-token": "write"}
    steps = [s for job in workflow["jobs"].values() for s in job["steps"]]
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-pages-artifact@"))
    assert upload["with"]["path"] == "site"
    assert any(s.get("uses", "").startswith("actions/deploy-pages@") for s in steps)


def test_every_page_links_privacy():
    pages = sorted((ROOT / "site").glob("*.html"))
    assert {p.name for p in pages} == {"index.html", "school.html", "privacy.html"}
    for path in pages:
        assert 'href="privacy.html"' in path.read_text(encoding="utf-8"), path.name


@pytest.mark.parametrize("variant", ["A", "B"])
@pytest.mark.parametrize("path", PAGES)
def test_no_console_errors(open_page, path, variant):
    collect = ("window.__errors = []; window.addEventListener('error', e => window.__errors.push(String(e.message)));"
               "const _err = console.error; console.error = (...a) => { window.__errors.push(a.join(' ')); _err(...a); };")
    page = open_page(path, variant=variant, consent=None, init_scripts=(collect,))
    page.wait_for_load_state("networkidle")
    assert page.evaluate("typeof SCA === 'object' && typeof SCA.track") == "function"
    assert page.evaluate("window.__errors") == []
