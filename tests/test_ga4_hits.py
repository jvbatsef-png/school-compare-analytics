from tests.ga4_hits import HitLog, parse_hits

BATCH = "en=search&_et=83&ep.location=Austin%2C%20TX\r\nen=compare_add&_et=5&ep.school_id=sch_001"


def test_retried_request_is_counted_once():
    # gtag.js resends an aborted request with the same session hit number (_s)
    log = HitLog()
    log.add("https://x/g/collect?v=2&sid=1&_s=4&gcs=G111", BATCH)
    log.add("https://x/g/collect?v=2&sid=1&_s=4&gcs=G111&_r=1", BATCH)
    assert [h["en"] for h in log.hits] == ["search", "compare_add"]


def test_same_event_twice_is_kept():
    log = HitLog()
    log.add("https://x/g/collect?v=2&sid=1&_s=5", "en=compare_add&_et=5&ep.school_id=sch_001\r\n"
                                                   "en=compare_add&_et=9&ep.school_id=sch_002")
    assert [h["ep.school_id"] for h in log.hits] == ["sch_001", "sch_002"]


def test_parse_get_hit():
    [h] = parse_hits("https://region1.google-analytics.com/g/collect?v=2&tid=G-X&gcs=G111&en=page_view", None)
    assert (h["en"], h["gcs"]) == ("page_view", "G111")


def test_parse_batched_body():
    hits = parse_hits("https://x/g/collect?v=2&tid=G-X&gcs=G111",
                      "en=search&ep.location=Austin%2C%20TX\r\nen=view_search_results&epn.results_count=24")
    assert [h["en"] for h in hits] == ["search", "view_search_results"]
    assert hits[0]["ep.location"] == "Austin, TX" and hits[1]["epn.results_count"] == "24"
    assert all(h["tid"] == "G-X" for h in hits)


def test_body_line_wins_over_url():
    [h] = parse_hits("https://x/g/collect?v=2&en=page_view&gcs=G100", "en=search")
    assert (h["en"], h["gcs"]) == ("search", "G100")
