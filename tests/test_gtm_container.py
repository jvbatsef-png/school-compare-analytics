import re

from scripts.make_gtm_container import load_ids


def test_ids_format():
    ids = load_ids()
    assert set(ids) == {"gtm_container_id", "ga4_measurement_id"}
    assert re.fullmatch(r"GTM-[A-Z0-9]+", ids["gtm_container_id"])
    assert re.fullmatch(r"G-[A-Z0-9]+", ids["ga4_measurement_id"])
