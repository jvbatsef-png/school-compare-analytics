# Stage 3 — GTM and GA4: design

Status: approved in conversation on 2026-11-05; awaiting owner review of this document.
Parent spec: `2026-11-05-school-compare-analytics-design.md` (sections 3, 5, 9 and the stage 3 acceptance check).
Previous stage: `2026-11-05-stage-2-site-design.md`.

## 1. Goal

Send the seven events of `tracking/events.yaml` from the live site to a demo-only GA4 property through a GTM container, under Consent Mode v2, with a workflow that guards against human error: the container is generated from the events contract, checked offline, checked against real outgoing hits, and only then checked by hand in GTM Preview and GA4 DebugView.

Done means:

- `uv run pytest` passes (existing site tests plus the new offline tests).
- The live test (`uv run pytest -m live`) passes against the published site.
- Every line of `tracking/gtm/qa-script.md` is marked OK in DebugView, with a screenshot.
- The live site's console shows no 404 (the favicon request is gone).

Out of scope: BigQuery export and the traffic simulator (stage 4), the GTM API, Google Ads or any advertising tag. Three stage 2 minors stay deferred because they do not affect tagging: variant drawn per page when storage is blocked, blank page if `schools.json` fails, no double-submit guard on search.

## 2. Decisions

- **Consent Mode v2, advanced mode.** GA4 tags load even while consent is denied and send cookieless pings with no identifier. Reason: stage 5 can then show that "declined" is not the same as "missing", and this is the setup most companies run. The denied default and the re-applied saved choice stay inline in `<head>`, before the GTM snippet (built in stage 2). GA4 tags honour `analytics_storage` through their built-in consent checks; no extra consent rules in GTM.
- **Location is a closed list.** The free-text field becomes a `<select>` of the cities in `schools.json`, formatted `City, ST`, sorted alphabetically, with "Any location" first (empty value). Filtering uses exact equality. An unknown `?location=` value (e.g. an old link with `tx`) is treated as "Any location" and the parameter is omitted. Reason: GA4 groups by exact value and folds excess distinct values into `(other)`; a closed list keeps `location` clean and gives the simulator a list to draw from. Search by state alone is dropped.
- **One GA4 event tag per event.** Seven tags, each carrying only its own parameters as listed in `events.yaml`. Reason: one-to-one with the contract, readable in the GTM UI, testable.
- **The container is generated, never hand-built.** A script writes the container JSON from `events.yaml`; the owner imports it, reviews it and publishes. Reason: no hand-typed event or parameter names. The GTM API was rejected: it needs OAuth credentials in the project for a container that rarely changes.

## 3. Components

| Path | Purpose |
|---|---|
| `tracking/gtm/ids.yaml` | The two public IDs: `gtm_container_id` (`GTM-…`) and `ga4_measurement_id` (`G-…`). Public by nature (they appear in the page source); not secrets. |
| `scripts/make_gtm_container.py` | Reads `events.yaml` and `ids.yaml`, writes `tracking/gtm/container.json`. Deterministic output (stable ordering and IDs) so a regenerate-and-compare test is meaningful. |
| `tracking/gtm/container.json` | GTM import file (export format version 2) containing: one Google tag (`G-…`, fires on Initialization – All Pages, sends `page_view`); seven GA4 event tags; seven Custom Event triggers matching each event name exactly; one Data Layer Variable (version 2) per distinct parameter name. |
| `tracking/gtm/qa-script.md` | Manual QA script: one line per event plus configuration checks, each with expected result, observed result and screenshot reference. |
| `site/index.html`, `site/school.html`, `site/privacy.html` | GTM snippet in the `<head>` slot, right after the consent script; GTM `<noscript>` iframe at the start of `<body>`; `<link rel="icon" href="favicon.svg">`. |
| `site/favicon.svg` | Simple icon so browsers stop requesting `/favicon.ico`. |
| `site/js/search.js`, `site/index.html` | Location `<select>` built from `schools.json`; exact-match filter; unknown URL value ignored. |

## 4. Data flow

1. The site pushes the event to `dataLayer` (`track.js`, unchanged since stage 2).
2. The Custom Event trigger matches the event name.
3. The event tag reads the parameters through Data Layer Variables.
4. GA4 receives the hit: with consent, with the `_ga` cookie; without consent, as a cookieless ping.

Types: `results_count`, `list_position` and `compare_count` are sent as numbers. `form_complete` arrives in GA4 as the string `"true"` or `"false"` (GA4 has no boolean parameter type); stage 5 must read it as a string.

## 5. GA4 property configuration

Created by the owner, guided step by step:

- Account and property named as demo-only; one web data stream for the GitHub Pages URL.
- **Enhanced measurement: turn off "Site search" and "Form interactions".** Site search would fire its own `view_search_results` on every URL with `?q=`, which the site uses, doubling every search. Form interactions would add `form_start`/`form_submit` alongside `generate_lead`. Page views and the other enhanced events stay on, except page views on browser history changes: each search rewrites the URL with `history.replaceState`, which GA4 would count as an extra `page_view` (seen in GTM Preview on 2026-11-06), so that sub-option is off.
- Data retention: 14 months (default is 2, which would truncate explorations).
- `generate_lead` marked as a key event.
- Custom definitions (event scope), registered by hand from a checklist and verified in the QA script:
  - Dimensions: `experiment_variant`, `source`, `location`, `school_level`, `school_id`, `form_complete`, `lead_type`.
  - Metrics: `results_count`, `compare_count`, `list_position`.
  - Not registered: `search_term` (GA4 has a built-in search term dimension), `school_ids` (comma-separated list, too many distinct values), the two `consent_update` parameters (BigQuery carries consent state per row). All parameters still reach BigQuery.

**Hypothesis to verify in stage 4, not a fact:** cookieless pings appear in the BigQuery export with a null `user_pseudo_id` and `privacy_info.analytics_storage = 'No'`; Google's modelled data does not. This comes from practitioner sources, not from Google's documentation, and they disagree on edge cases (meaning of NULL). Stage 4 confirms it on our own data before stage 5 relies on it.

## 6. Error handling

- **GTM blocked (ad blocker) or unreachable:** the site works exactly as without GTM. No site feature depends on GTM; pushes still land in `dataLayer` with no reader.
- **No answer on the banner:** consent stays denied; GA4 receives cookieless pings only.
- **Container drift:** if `events.yaml` changes and the container is not regenerated (or the container is edited by hand), the offline test fails.
- **QA traffic polluting stage 4 data:** the live test captures and aborts every GA4 request, so nothing it does reaches GA4. Preview and DebugView traffic carries `debug_mode` and stage 4 filters it out. Rule: QA finishes before the simulator starts.

## 7. Testing

| Layer | Runs | Checks |
|---|---|---|
| Offline (default `uv run pytest`) | every run | Regenerating the container reproduces `container.json` byte for byte. Every event in `events.yaml` has exactly one tag and one trigger, and the tag carries exactly that event's parameters (no more, no fewer). The Google tag uses the ID in `ids.yaml`. The GTM snippet is in all three pages, after the consent script, with the ID from `ids.yaml`. The Location list is built correctly, filters by exact match, ignores unknown URL values and omits `location` for "Any location". The site works with `googletagmanager.com` blocked. All existing tests keep passing; Playwright blocks Google domains so the suite stays offline and deterministic. |
| Live (`uv run pytest -m live`, excluded by default) | by hand, after publishing | Against the GitHub Pages URL, intercepting requests to `*/g/collect`: no GA4 hit is sent before the consent default is in place; after accepting, the seven events are sent with the right event names, the parameters from `events.yaml` and `experiment_variant`; after declining, hits carry the denied consent flag and no `_ga` cookie is set. Every intercepted request is aborted. |
| Manual | after the live test | `tracking/gtm/qa-script.md` in GTM Preview and GA4 DebugView: each event and its parameters, enhanced measurement not duplicating `view_search_results`, custom definitions registered, `generate_lead` as key event. Screenshot per line. This is the parent spec's stage 3 acceptance check. |

## 8. Order of work

1. Accounts, guided with the owner: GTM container (Web), GA4 account, property and data stream, enhanced measurement and retention settings. Output: the two IDs in `ids.yaml`.
2. Site changes, test first: Location list, favicon, GTM snippet.
3. Container generator and offline tests.
4. Owner imports `container.json` into GTM and reviews it.
5. GTM Preview against the local site; then publish the container and deploy the site.
6. Live test.
7. Manual QA in DebugView with screenshots; register custom definitions and the key event.
8. Close the stage: README, vault, personal study notes.
