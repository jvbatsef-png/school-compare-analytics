"""Read the page's dataLayer and validate each push against tracking/events.yaml."""
from tracking.spec import load_spec

PY_TYPES = {"string": str, "int": int, "bool": bool}


def pushes(page) -> list[dict]:
    """Event pushes only: skips gtag() argument lists and GTM's own gtm.* events."""
    return page.evaluate("""() => (window.dataLayer || []).filter(
        item => item && typeof item.event === 'string' && !item.event.startsWith('gtm.')
    ).map(item => Object.assign({}, item))""")


def events_named(page, name: str) -> list[dict]:
    return [p for p in pushes(page) if p["event"] == name]


def assert_valid(push: dict) -> None:
    events = {e["name"]: e for e in load_spec()["events"]}
    name = push.get("event")
    assert name in events, f"unknown event {name!r}"
    params = {p["name"]: p for p in events[name]["params"]}
    extra = set(push) - set(params) - {"event"}
    assert not extra, f"{name}: undeclared params {sorted(extra)}"
    for pname, p in params.items():
        if p["required"]:
            assert pname in push, f"{name}: missing required {pname}"
        if pname in push:
            value = push[pname]
            expected = PY_TYPES[p["type"]]
            ok = isinstance(value, expected) and not (expected is int and isinstance(value, bool))
            assert ok, f"{name}.{pname}: expected {p['type']}, got {value!r}"
