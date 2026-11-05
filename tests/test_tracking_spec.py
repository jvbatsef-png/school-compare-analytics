import re

import pytest

from tracking.spec import load_spec, metric_events

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
RESERVED_PREFIXES = ("google_", "ga_", "firebase_")
RESERVED_EVENTS = {"session_start", "first_visit", "first_open", "user_engagement", "app_remove"}


@pytest.fixture(scope="module")
def spec():
    return load_spec()


def _all_names(spec):
    for event in spec["events"]:
        yield event["name"]
        for param in event["params"]:
            yield param["name"]


def test_event_names_within_ga4_limits(spec):
    for event in spec["events"]:
        assert len(event["name"]) <= 40, event["name"]
        assert NAME_RE.match(event["name"]), event["name"]


def test_param_names_within_ga4_limits(spec):
    for event in spec["events"]:
        assert len(event["params"]) <= 25, event["name"]
        for param in event["params"]:
            assert len(param["name"]) <= 40, param["name"]
            assert param["type"] in {"string", "int", "bool"}, param["name"]


def test_no_reserved_names_or_prefixes(spec):
    for event in spec["events"]:
        assert event["name"] not in RESERVED_EVENTS, event["name"]
    for name in _all_names(spec):
        assert not name.startswith(RESERVED_PREFIXES), name


def test_names_are_snake_case(spec):
    names = [e["name"] for e in spec["events"]]
    assert len({n.lower() for n in names}) == len(names), "event names collide ignoring case"
    for name in _all_names(spec):
        assert NAME_RE.match(name), name
    for event in spec["events"]:
        params = [p["name"].lower() for p in event["params"]]
        assert len(set(params)) == len(params), f"duplicate params in {event['name']}"


def test_funnel_events_carry_variant(spec):
    funnel = [e for e in spec["events"] if e["funnel"]]
    assert funnel, "no funnel events"
    for event in funnel:
        variant = [p for p in event["params"] if p["name"] == "experiment_variant"]
        assert variant and variant[0]["required"], event["name"]


def test_every_metric_maps_to_events(spec):
    defined = {e["name"] for e in spec["events"]}
    metrics = metric_events()
    assert {"lead_rate", "profile_view_rate", "complete_lead_share", "compare_adoption"} <= metrics.keys()
    for metric_id, events in metrics.items():
        missing = set(events) - defined
        assert not missing, f"{metric_id} needs undefined events {missing}"


def test_lead_quality_param_exists(spec):
    lead = next(e for e in spec["events"] if e["name"] == "generate_lead")
    form = [p for p in lead["params"] if p["name"] == "form_complete"]
    assert form and form[0]["type"] == "bool" and form[0]["required"]


def test_metric_events_parses_table(tmp_path):
    md = tmp_path / "plan.md"
    md.write_text(
        "| metric_id | type | definition | numerator | denominator | events_needed |\n"
        "|---|---|---|---|---|---|\n"
        "| m1 | primary | d | n | d | a, b |\n",
        encoding="utf-8",
    )
    assert metric_events(str(md)) == {"m1": ["a", "b"]}
