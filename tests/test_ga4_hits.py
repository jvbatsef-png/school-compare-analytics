from tests.ga4_hits import parse_hits


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
