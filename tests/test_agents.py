import re
from pathlib import Path

import yaml

AGENTS_DIR = Path(__file__).parent.parent / ".claude" / "agents"
AGENTS = ["head-of-analytics", "business-analyst", "product-analyst",
          "gtm-engineer", "data-engineer", "statistician", "insights-presenter",
          "results-auditor"]
FORBIDDEN = []  # forbidden terms live in the git-ignored .private-terms file


def _read(name: str) -> tuple[dict, str]:
    text = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front), body


def test_all_agents_exist_with_frontmatter():
    for name in AGENTS:
        meta, _ = _read(name)
        assert meta["name"] == name
        assert meta["description"].strip()


def test_agents_have_no_personal_context():
    for name in AGENTS:
        text = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8").lower()
        for term in FORBIDDEN:
            assert not re.search(rf"\b{re.escape(term)}\b", text), f"{name} mentions {term}"


def test_head_does_no_technical_work():
    meta, _ = _read("head-of-analytics")
    tools = {t.strip() for t in meta["tools"].split(",")}
    assert not tools & {"Write", "Edit", "Bash"}


def test_head_knows_every_specialist():
    _, body = _read("head-of-analytics")
    for name in AGENTS[1:]:
        assert f"`{name}`" in body, f"head does not dispatch {name}"


def test_auditor_cannot_edit_others_work():
    meta, _ = _read("results-auditor")
    tools = {t.strip() for t in meta["tools"].split(",")}
    assert "Bash" in tools
    assert not tools & {"Write", "Edit"}
