"""One behaviour model for both executors: who the visitor is, what they plan to do, and the events that implies."""
import json
import random
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
CONFIG_PATH = Path(__file__).parent / "config.yaml"
SCHOOLS_PATH = ROOT / "site" / "data" / "schools.json"
LEVELS = ("", "elementary", "middle", "high")
MAX_RESULTS_PROFILE = 5  # a visitor opens a profile from the first five cards
MAX_RESULTS_COMPARE = 6  # and picks schools to compare from the first six


@dataclass(frozen=True)
class Visitor:
    banner: str  # accept | reject | ignore
    ad_blocker: bool


@dataclass(frozen=True)
class Search:
    location: str  # "City, ST"
    level: str  # "" or elementary | middle | high
    n_results: int


@dataclass(frozen=True)
class Plan:
    variant: str
    search: Search | None
    compare_positions: tuple[int, ...]  # 1-based list positions, in click order
    profile_from: str | None  # results | compare
    profile_index: int | None  # list position (results) or tray position (compare), 1-based
    lead: str | None  # complete | incomplete


def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_schools(path: Path = SCHOOLS_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def visitor_rng(seed: int, visitor_id: str) -> random.Random:
    return random.Random(f"{seed}-{visitor_id}")


def search_results(schools, location: str, level: str) -> list[dict]:
    """Port of filter() in site/js/search.js with an empty name query: rating desc, then id asc."""
    found = [s for s in schools
             if (not level or s["level"] == level) and (not location or f"{s['city']}, {s['state']}" == location)]
    return sorted(found, key=lambda s: (-s["rating"], s["id"]))


def search_options(schools, min_results: int = 3) -> list[Search]:
    locations = sorted({f"{s['city']}, {s['state']}" for s in schools})
    options = []
    for location in locations:
        for level in LEVELS:
            n = len(search_results(schools, location, level))
            if n >= min_results:
                options.append(Search(location, level, n))
    return options


def draw_visitor(rng: random.Random, cfg: dict) -> Visitor:
    b = cfg["banner"]
    r = rng.random()
    banner = "accept" if r < b["accept"] else "reject" if r < b["accept"] + b["reject"] else "ignore"
    return Visitor(banner, rng.random() < cfg["ad_blocker"])


def plan_visit(variant: str, rng: random.Random, cfg: dict, options: list[Search]) -> Plan:
    f = cfg["funnel"]
    if rng.random() >= f["search"]:
        return Plan(variant, None, (), None, None, None)
    search = rng.choice(options)
    compare: tuple[int, ...] = ()
    if variant == "B" and rng.random() < f["compare_b"]:
        count = rng.choice((2, 3))
        compare = tuple(rng.sample(range(1, min(MAX_RESULTS_COMPARE, search.n_results) + 1), count))
    path = "compare" if compare else "no_compare"
    profile_from = profile_index = lead = None
    if rng.random() < f["profile"][path]:
        if compare:
            profile_from, profile_index = "compare", rng.randint(1, len(compare))
        else:
            profile_from, profile_index = "results", rng.randint(1, min(MAX_RESULTS_PROFILE, search.n_results))
        if rng.random() < f["lead_given_profile"][path]:
            lead = "complete" if rng.random() < f["complete_lead"] else "incomplete"
    return Plan(variant, search, compare, profile_from, profile_index, lead)


def plan_events(plan: Plan, visitor: Visitor, schools) -> list[tuple[str, dict]]:
    """The dataLayer pushes the site makes for this plan, as site/js/track.js sends them, plus page loads."""
    v = {"experiment_variant": plan.variant}
    events: list[tuple[str, dict]] = [("page_view", {"page": "index"})]
    if visitor.banner != "ignore":
        state = "granted" if visitor.banner == "accept" else "denied"
        events.append(("consent_update", {"analytics_storage": state, "ad_storage": state}))
    if plan.search is None:
        return events
    s = plan.search
    shown = search_results(schools, s.location, s.level)
    search = {**v, **({"school_level": s.level} if s.level else {}), "location": s.location}
    events += [("search", search), ("view_search_results", {**v, "results_count": len(shown)})]
    tray = []
    for pos in plan.compare_positions:
        tray.append(shown[pos - 1]["id"])
        events.append(("compare_add", {**v, "school_id": tray[-1], "list_position": pos,
                                       "compare_count": len(tray)}))
    if tray:
        events.append(("compare_view", {**v, "compare_count": len(tray), "school_ids": ",".join(tray)}))
    if plan.profile_from is None:
        return events
    school_id = tray[plan.profile_index - 1] if plan.profile_from == "compare" else shown[plan.profile_index - 1]["id"]
    ids = {"school_id": school_id, "source": plan.profile_from}
    events += [("page_view", {"page": "school"}), ("school_profile_view", {**v, **ids})]
    if plan.lead:
        events.append(("generate_lead", {**v, **ids, "form_complete": plan.lead == "complete",
                                         "lead_type": "info_request"}))
    return events
