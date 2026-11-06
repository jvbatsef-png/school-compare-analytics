"""Ground-truth JSONL log: one line per event, closed by a visit_end line per visitor (spec section 4)."""
import json
from datetime import datetime, timezone
from pathlib import Path

from simulator.behavior import Visitor

FIELDS = ("run", "visitor_id", "seq", "ts", "variant", "banner", "ad_blocker", "ga_client_id",
          "ga_requests", "status", "error_step", "event", "params")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def visitor_lines(run: str, visitor_id: str, variant: str | None, visitor: Visitor,
                  events: list[tuple[str, dict, str]], ga_client_id: str | None, ga_requests: int | None,
                  status: str, error_step: str | None, end_ts: str | None = None) -> list[dict]:
    """events are (name, params, ts); visit_end takes end_ts, else the last event's time, else now."""
    end_ts = end_ts or (events[-1][2] if events else utc_now())
    rows = [(name, params, ts, None, None, None) for name, params, ts in events]
    rows.append(("visit_end", {}, end_ts, ga_requests, status, error_step))
    return [dict(zip(FIELDS, (run, visitor_id, seq, ts, variant, visitor.banner, visitor.ad_blocker,
                              ga_client_id, requests, st, step, name, params)))
            for seq, (name, params, ts, requests, st, step) in enumerate(rows, start=1)]


def append(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def by_visitor(lines) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for line in lines:
        grouped.setdefault(line["visitor_id"], []).append(line)
    return grouped
