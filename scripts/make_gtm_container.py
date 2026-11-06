"""Generate the GTM container import file from the tracking spec and the public IDs.

Run: uv run python -m scripts.make_gtm_container
Field names follow GTM's export format (version 2); they are GTM's, not choices.
"""
import json
from pathlib import Path

import yaml

from tracking.spec import load_spec

ROOT = Path(__file__).resolve().parent.parent
IDS_PATH = ROOT / "tracking" / "gtm" / "ids.yaml"
CONTAINER_PATH = ROOT / "tracking" / "gtm" / "container.json"
INIT_ALL_PAGES = "2147479573"  # GTM's built-in "Initialization - All Pages" trigger
SCOPE = {"accountId": "0", "containerId": "0"}


def load_ids(path: Path = IDS_PATH) -> dict[str, str]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _template(key: str, value: str) -> dict:
    return {"type": "TEMPLATE", "key": key, "value": value}


def _variable(var_id: str, param: str) -> dict:
    return {**SCOPE, "variableId": var_id, "name": f"dlv - {param}", "type": "v", "parameter": [
        {"type": "INTEGER", "key": "dataLayerVersion", "value": "2"},
        {"type": "BOOLEAN", "key": "setDefaultValue", "value": "false"},
        _template("name", param)]}


def _trigger(trigger_id: str, event: str) -> dict:
    return {**SCOPE, "triggerId": trigger_id, "name": f"ce - {event}", "type": "CUSTOM_EVENT",
            "customEventFilter": [{"type": "EQUALS", "parameter": [
                _template("arg0", "{{_event}}"), _template("arg1", event)]}]}


def _event_tag(tag_id: str, event: dict, measurement_id: str, trigger_id: str) -> dict:
    rows = [{"type": "MAP", "map": [_template("parameter", p["name"]),
                                    _template("parameterValue", f"{{{{dlv - {p['name']}}}}}")]}
            for p in event["params"]]
    return {**SCOPE, "tagId": tag_id, "name": f"GA4 event - {event['name']}", "type": "gaawe",
            "parameter": [_template("eventName", event["name"]),
                          _template("measurementIdOverride", measurement_id),
                          {"type": "LIST", "key": "eventSettingsTable", "list": rows}],
            "firingTriggerId": [trigger_id]}


def build_container(spec: dict, ids: dict) -> dict:
    """One Google tag, then per event (in spec order) one Custom Event trigger and one GA4 event tag."""
    measurement_id = ids["ga4_measurement_id"]
    counter = iter(range(1, 10_000))

    def next_id() -> str:
        # Consecutive string IDs keep the output deterministic.
        return str(next(counter))

    variables: dict[str, dict] = {}
    for event in spec["events"]:
        for param in event["params"]:
            if param["name"] not in variables:
                variables[param["name"]] = _variable(next_id(), param["name"])

    tags = [{**SCOPE, "tagId": next_id(), "name": "Google tag", "type": "googtag",
             "parameter": [_template("tagId", measurement_id)], "firingTriggerId": [INIT_ALL_PAGES]}]
    triggers = []
    for event in spec["events"]:
        trigger = _trigger(next_id(), event["name"])
        triggers.append(trigger)
        tags.append(_event_tag(next_id(), event, measurement_id, trigger["triggerId"]))

    return {"exportFormatVersion": 2, "containerVersion": {
        **SCOPE, "tag": tags, "trigger": triggers, "variable": list(variables.values()),
        # {{_event}} in the triggers is GTM's built-in Event variable.
        "builtInVariable": [{**SCOPE, "type": "EVENT", "name": "Event"}]}}


def render(container: dict) -> str:
    return json.dumps(container, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    CONTAINER_PATH.write_text(render(build_container(load_spec(), load_ids())), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
