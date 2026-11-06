"""Ground-truth JSONL log: one line per event, closed by a visit_end line per visitor (spec section 4).

The real run also writes a visit_start line (seq 0) before the browser opens the page, so a visitor
cut off by a crash is still on record and can be closed as interrupted instead of lost or re-run.
"""
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


def start_line(run: str, visitor_id: str, visitor: Visitor) -> dict:
    return dict(zip(FIELDS, (run, visitor_id, 0, utc_now(), None, visitor.banner, visitor.ad_blocker,
                             None, None, None, None, "visit_start", {})))


def append(path: Path, lines: list[dict]) -> None:
    """One write per call, so a kill can tear at most the last line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines))
        f.flush()


def read(path: Path) -> list[dict]:
    """A last line torn by a kill mid-write is dropped; a broken line anywhere else is an error."""
    raw = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = [json.loads(line) for line in raw[:-1]]
    if raw:
        try:
            lines.append(json.loads(raw[-1]))
        except json.JSONDecodeError:
            pass
    return lines


def drop_torn_tail(path: Path) -> None:
    """Cut a last line left without its newline by a kill mid-write, so new lines start clean."""
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        path.write_bytes(data[:data.rfind(b"\n") + 1])


def by_visitor(lines) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for line in lines:
        grouped.setdefault(line["visitor_id"], []).append(line)
    return grouped
