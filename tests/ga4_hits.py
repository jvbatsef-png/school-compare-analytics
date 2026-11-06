"""Read GA4 /g/collect requests into one dict per event, keys as GA4 sends them (en, gcs, ep.x, epn.x)."""
from urllib.parse import parse_qsl, urlsplit

LIVE_URL = "https://jvbatsef-png.github.io/school-compare-analytics/"


def parse_hits(url: str, body: str | None) -> list[dict[str, str]]:
    """gtag.js batches events: shared params ride in the URL, each body line is one event (line wins)."""
    shared = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    lines = [line for line in (body or "").splitlines() if line.strip()]
    if not lines:
        return [shared]
    return [{**shared, **dict(parse_qsl(line, keep_blank_values=True))} for line in lines]


class HitLog:
    """Captured hits, each event once: gtag.js resends an aborted request, same session hit number (_s)."""

    def __init__(self):
        self.hits: list[dict[str, str]] = []
        self._seen: set[tuple] = set()

    def add(self, url: str, body: str | None) -> None:
        for hit in parse_hits(url, body):
            params = tuple(sorted((k, v) for k, v in hit.items() if k.startswith(("ep.", "epn."))))
            key = (hit.get("sid"), hit.get("_s"), hit.get("en"), hit.get("_et"), params)
            if key not in self._seen:
                self._seen.add(key)
                self.hits.append(hit)
