"""Load the tracking spec and the metric-to-event mapping from the measurement plan."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "tracking" / "events.yaml"
PLAN_PATH = ROOT / "docs" / "measurement-plan.md"


def load_spec(path: str = str(SPEC_PATH)) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def metric_events(md_path: str = str(PLAN_PATH)) -> dict[str, list[str]]:
    """Parse the Metrics table (header starts with `| metric_id |`) into {metric_id: [events]}."""
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.replace(" ", "").startswith("|metric_id|"))
    header = [c.strip() for c in lines[start].strip("|").split("|")]
    col = header.index("events_needed")
    result = {}
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        result[cells[0]] = [e.strip() for e in cells[col].split(",") if e.strip()]
    return result


def render_markdown(spec: dict) -> str:
    out = ["# Tracking spec", "",
           "Generated from `tracking/events.yaml` by `tracking/spec.py`. Do not edit by hand.", ""]
    out += ["## Consent defaults", ""]
    out += [f"- `{k}`: {v}" for k, v in spec["consent"].items()]
    out += ["", "## dataLayer contract", "", "```js", spec["datalayer_contract"].rstrip(), "```", ""]
    for event in spec["events"]:
        out += [f"## `{event['name']}`", "", f"**Fires when:** {event['trigger']}",
                f"**Funnel step:** {'yes' if event['funnel'] else 'no'}", "",
                "| parameter | type | required | example |", "|---|---|---|---|"]
        out += [f"| {p['name']} | {p['type']} | {'yes' if p['required'] else 'no'} | {p['example']} |"
                for p in event["params"]]
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    (ROOT / "docs" / "tracking-spec.md").write_text(render_markdown(load_spec()), encoding="utf-8")
