import re
import subprocess
from pathlib import Path

import pytest

import yaml

ROOT = Path(__file__).parent.parent
AGENTS_DIR = ROOT / ".claude" / "agents"
# Terms that must never reach the public repo live in a git-ignored file, one per line.
PRIVATE_TERMS = ROOT / ".private-terms"
AGENTS = ["head-of-analytics", "business-analyst", "product-analyst",
          "gtm-engineer", "data-engineer", "statistician", "insights-presenter",
          "results-auditor"]


def _read(name: str) -> tuple[dict, str]:
    text = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front), body


def test_all_agents_exist_with_frontmatter():
    for name in AGENTS:
        meta, _ = _read(name)
        assert meta["name"] == name
        assert meta["description"].strip()


def test_repo_has_no_personal_context():
    if not PRIVATE_TERMS.exists():
        pytest.skip(".private-terms not present (only on the owner's machine)")
    terms = [l.strip().lower() for l in PRIVATE_TERMS.read_text(encoding="utf-8").splitlines() if l.strip()]
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.splitlines()
    hits = []
    for name in files:
        try:
            text = (ROOT / name).read_text(encoding="utf-8").lower()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        hits += [f"{name}: {term}" for term in terms if re.search(rf"\b{re.escape(term)}\b", text)]
    assert not hits, hits


def test_head_does_no_technical_work():
    meta, _ = _read("head-of-analytics")
    tools = {t.strip() for t in meta["tools"].split(",")}
    assert not tools & {"Write", "Edit", "Bash"}


def test_head_instructions_need_no_shell():
    _, body = _read("head-of-analytics")
    assert "git " not in body, "head has no Bash tool but is told to run git"


def test_head_knows_every_specialist():
    _, body = _read("head-of-analytics")
    for name in AGENTS[1:]:
        assert f"`{name}`" in body, f"head does not dispatch {name}"


def test_auditor_cannot_edit_others_work():
    meta, _ = _read("results-auditor")
    tools = {t.strip() for t in meta["tools"].split(",")}
    assert "Bash" in tools
    assert not tools & {"Write", "Edit"}
