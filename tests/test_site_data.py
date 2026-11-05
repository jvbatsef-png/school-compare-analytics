import json
from pathlib import Path

import pytest

from scripts.make_schools import make_schools
from tests.site_helpers import assert_valid

ROOT = Path(__file__).parent.parent
SCHOOLS_FILE = ROOT / "site" / "data" / "schools.json"


def test_schools_shape():
    schools = make_schools()
    assert len(schools) == 200
    ids = [s["id"] for s in schools]
    assert ids == [f"sch_{i:03d}" for i in range(1, 201)]
    assert {s["level"] for s in schools} == {"elementary", "middle", "high"}
    assert {s["type"] for s in schools} == {"public", "private", "charter"}
    for s in schools:
        assert (s["tuition"] == 0) == (s["type"] == "public")
        assert 1 <= s["rating"] <= 10
        assert len(s["state"]) == 2


def test_schools_file_matches_generator():
    assert json.loads(SCHOOLS_FILE.read_text(encoding="utf-8")) == make_schools()


def test_assert_valid_rejects_bad_push():
    good = {"event": "compare_add", "experiment_variant": "B", "school_id": "sch_001",
            "list_position": 3, "compare_count": 1}
    assert_valid(good)
    with pytest.raises(AssertionError):
        assert_valid({**good, "list_position": "3"})
    with pytest.raises(AssertionError):
        assert_valid({**good, "foo": "bar"})
