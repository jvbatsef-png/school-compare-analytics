"""Synthetic A/B executor: the behaviour model's events written straight to the ground-truth log.

uv run python -m simulator.synthetic_run
"""
from datetime import datetime, timedelta

from simulator.behavior import (
    ROOT, draw_visitor, load_config, load_schools, plan_events, plan_visit, search_options, visitor_rng,
)
from simulator.ground_truth import append, visitor_lines

OUT_PATH = ROOT / "simulator" / "output" / "ab_synthetic.jsonl"
DAY_START_HOUR = 12  # UTC; visits start between 12:00 and 23:00
DAY_SECONDS = 11 * 3600
STEP_SECONDS = (5, 40)


def generate(cfg: dict, schools) -> list[dict]:
    syn = cfg["synthetic"]
    start = datetime.fromisoformat(syn["start_date"])
    options = search_options(schools)
    lines: list[dict] = []
    for i in range(1, syn["visitors"] + 1):
        visitor_id = f"v{i:05d}"
        rng = visitor_rng(cfg["seed"], visitor_id)
        visitor = draw_visitor(rng, cfg)
        variant = "A" if rng.random() < 0.5 else "B"
        t = start + timedelta(days=rng.randrange(syn["days"]), hours=DAY_START_HOUR,
                              seconds=rng.randrange(DAY_SECONDS))
        plan = plan_visit(variant, visitor_rng(cfg["seed"], visitor_id + "/plan"), cfg, options)
        events = []
        for name, params in plan_events(plan, visitor, schools):
            events.append((name, params, t.strftime("%Y-%m-%dT%H:%M:%SZ")))
            t += timedelta(seconds=rng.randint(*STEP_SECONDS))
        lines += visitor_lines("synthetic", visitor_id, variant, visitor, events, None, None, "ok", None)
    return lines


def main() -> None:
    lines = generate(load_config(), load_schools())
    OUT_PATH.unlink(missing_ok=True)
    append(OUT_PATH, lines)
    print(f"{sum(line['event'] == 'visit_end' for line in lines)} visitors -> {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
