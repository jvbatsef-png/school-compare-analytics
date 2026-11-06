import re

import pytest

from scripts.make_gtm_container import CONTAINER_PATH, build_container, load_ids, render
from tracking.spec import load_spec

INIT_ALL_PAGES = "2147479573"


@pytest.fixture(scope="module")
def spec():
    return load_spec()


@pytest.fixture(scope="module")
def ids():
    return load_ids()


@pytest.fixture(scope="module")
def version(spec, ids):
    return build_container(spec, ids)["containerVersion"]


def _params(item) -> dict:
    return {p["key"]: p for p in item["parameter"]}


def _settings(tag) -> list[tuple[str, str]]:
    rows = _params(tag)["eventSettingsTable"]["list"]
    return [tuple({m["key"]: m["value"] for m in row["map"]}[k] for k in ("parameter", "parameterValue"))
            for row in rows]


def test_ids_format():
    ids = load_ids()
    assert set(ids) == {"gtm_container_id", "ga4_measurement_id"}
    assert re.fullmatch(r"GTM-[A-Z0-9]+", ids["gtm_container_id"])
    assert re.fullmatch(r"G-[A-Z0-9]+", ids["ga4_measurement_id"])


def test_envelope_names_the_web_container(spec, ids):
    # GTM's import answers "Not found" without this block; account/container numbers are not needed.
    c = build_container(spec, ids)
    assert c["containerVersion"]["container"] == {"publicId": ids["gtm_container_id"], "usageContext": ["WEB"]}
    assert '"accountId"' not in render(c) and '"containerId"' not in render(c)


def test_container_file_is_current():
    assert CONTAINER_PATH.read_text(encoding="utf-8") == render(build_container(load_spec(), load_ids()))


def test_one_tag_and_trigger_per_event(spec, version):
    triggers = {t["triggerId"]: t for t in version["trigger"]}
    event_tags = [t for t in version["tag"] if t["type"] == "gaawe"]
    assert len(event_tags) == len(spec["events"])
    for event in spec["events"]:
        name = event["name"]
        [tag] = [t for t in event_tags if t["name"] == f"GA4 event - {name}"]
        assert _params(tag)["eventName"]["value"] == name
        params = [p["name"] for p in event["params"]]
        assert _settings(tag) == [(p, f"{{{{dlv - {p}}}}}") for p in params]
        [trigger_id] = tag["firingTriggerId"]
        trigger = triggers[trigger_id]
        assert trigger["name"] == f"ce - {name}" and trigger["type"] == "CUSTOM_EVENT"
        [condition] = trigger["customEventFilter"]
        assert condition["type"] == "EQUALS"
        assert _params(condition)["arg0"]["value"] == "{{_event}}"
        assert _params(condition)["arg1"]["value"] == name
    assert len(version["trigger"]) == len(spec["events"])


def test_google_tag_uses_measurement_id(version, ids):
    [google] = [t for t in version["tag"] if t["type"] == "googtag"]
    assert _params(google)["tagId"]["value"] == ids["ga4_measurement_id"]
    assert google["firingTriggerId"] == [INIT_ALL_PAGES]
    for tag in version["tag"]:
        if tag["type"] == "gaawe":
            assert _params(tag)["measurementIdOverride"]["value"] == ids["ga4_measurement_id"]


def test_variables_cover_params_once(spec, version):
    names = [v["name"] for v in version["variable"]]
    assert len(names) == len(set(names))
    expected = {f"dlv - {p['name']}" for e in spec["events"] for p in e["params"]}
    assert set(names) == expected
    for var in version["variable"]:
        assert var["type"] == "v"
        assert _params(var)["name"]["value"] == var["name"].removeprefix("dlv - ")
        assert _params(var)["dataLayerVersion"]["value"] == "2"
    refs = set(re.findall(r"\{\{(dlv - [^}]+)\}\}", render({"containerVersion": version})))
    assert refs <= set(names)


def test_ids_are_unique_and_deterministic(spec, ids):
    first, second = build_container(spec, ids), build_container(spec, ids)
    assert render(first) == render(second)
    v = first["containerVersion"]
    for kind, key in (("tag", "tagId"), ("trigger", "triggerId"), ("variable", "variableId")):
        values = [item[key] for item in v[kind]]
        assert len(values) == len(set(values)), kind


def test_new_param_flows_into_container(ids):
    spec = load_spec()
    spec["events"][0]["params"].append({"name": "sort_order", "type": "string", "required": False, "example": "rating"})
    c = build_container(spec, ids)["containerVersion"]
    assert "dlv - sort_order" in {v["name"] for v in c["variable"]}
    [search_tag] = [t for t in c["tag"] if t["name"] == f"GA4 event - {spec['events'][0]['name']}"]
    assert _settings(search_tag)[-1] == ("sort_order", "{{dlv - sort_order}}")
