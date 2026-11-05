"""Generate the fictional school list served by the site (fixed seed, so the file never drifts)."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "site" / "data" / "schools.json"

CITIES = [("Austin", "TX"), ("Dallas", "TX"), ("Denver", "CO"), ("Boulder", "CO"),
          ("Portland", "OR"), ("Seattle", "WA"), ("Phoenix", "AZ"), ("Raleigh", "NC"),
          ("Columbus", "OH"), ("Madison", "WI"), ("Nashville", "TN"), ("Orlando", "FL")]
NAME_FIRST = ["Oak", "Maple", "Cedar", "River", "Lake", "Hill", "Pine", "Willow", "Summit",
              "Harbor", "Meadow", "Brook", "Elm", "Valley", "Sunrise", "Liberty"]
NAME_SECOND = ["wood", "field", "view", "side", "crest", "ridge", "gate", "park"]
LEVEL_SUFFIX = {"elementary": "Elementary", "middle": "Middle School", "high": "High School"}
TYPE_PREFIX = {"public": "", "private": "Academy of ", "charter": "Charter "}


def make_schools(n: int = 200, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    schools = []
    for i in range(1, n + 1):
        level = rng.choice(list(LEVEL_SUFFIX))
        kind = rng.choices(list(TYPE_PREFIX), weights=[6, 3, 2])[0]
        city, state = rng.choice(CITIES)
        base = rng.choice(NAME_FIRST) + rng.choice(NAME_SECOND)
        name = f"{TYPE_PREFIX[kind]}{base} {LEVEL_SUFFIX[level]}"
        tuition = 0 if kind == "public" else rng.randrange(6000, 30001, 500)
        schools.append({"id": f"sch_{i:03d}", "name": name, "city": city, "state": state,
                        "level": level, "type": kind, "rating": rng.randint(1, 10),
                        "students": rng.randrange(150, 2401, 10), "tuition": tuition})
    return schools


if __name__ == "__main__":
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(make_schools(), indent=1) + "\n", encoding="utf-8")
