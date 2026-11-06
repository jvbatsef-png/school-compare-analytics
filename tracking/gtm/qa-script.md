# Stage 3 QA script: GTM Preview and GA4 DebugView

Run after the live test (`uv run pytest -m live`) passes, and before stage 4's simulator starts.
Event names and parameters below come from `tracking/events.yaml`; if that file changes, regenerate the container and update this table.

## How to open the tools

- **GTM Preview:** tagmanager.google.com → container → **Preview** → enter the site URL → a new tab opens with the site connected to Tag Assistant. Each `dataLayer` push appears in the left column; click it to see **Tags fired** and **Variables**.
- **GA4 DebugView:** analytics.google.com → Admin → **DebugView**. Preview traffic carries `debug_mode`, so events from the Preview tab show up here within seconds. Click an event to see its parameters.
- **Journey (variant B):** accept cookies → search with Location "Austin, TX" → Compare on two cards → Compare (open the table) → open a school from the table → fill email, grade, start year and message → Send.
- **Journey end:** open Privacy from the footer, so each of the three pages loads once.
- **Evidence:** Tag Assistant → GA4 tag (`G-…`) → **Hits sent** → click a hit. It shows the exact `/g/collect` payload: event name, `ep.*`/`epn.*` params and `_dbg=1` (the debug flag DebugView keys on). DebugView can lag by several minutes and show only part of the stream, so the hit payload is the primary evidence and DebugView the secondary one.
- **Screenshots:** `tracking/gtm/qa/NN-<check>.png`, where NN is the row number; one screenshot can cover several rows.
- **Fresh visitor:** row 13 needs the consent banner unanswered. Clear `sca_consent` from localStorage (and set `sca_variant` to `B`) before connecting Preview.

## Checks

Last run: 2026-11-06, live site, container version 2 (Preview), browser Chrome, variant B. Result: **all 18 rows OK**.

| # | Check | Expected | Result | Screenshot |
|---|---|---|---|---|
| 01 | `page_view` on `index.html` | One `page_view` per load in DebugView | OK: one `page_view` for the index load | `qa/01-03-hits-full-journey.png` |
| 02 | `page_view` on `school.html` | One `page_view` per load | OK: one `page_view` for the school load | `qa/01-03-hits-full-journey.png` |
| 03 | `page_view` on `privacy.html` | One `page_view` per load | OK: one `page_view` for the privacy load (3 page loads, 3 `page_view` in all) | `qa/01-03-hits-full-journey.png` |
| 04 | `consent_update` | Tag "GA4 event - consent_update" fired; params `analytics_storage`, `ad_storage` (no `experiment_variant`: `track.js` leaves it out of this event on purpose) | OK: tag fired; `analytics_storage` = granted, `ad_storage` = granted, `gcs` = G111 | `qa/04-consent-update-tag.png` |
| 05 | `search` | Tag "GA4 event - search" fired; params `experiment_variant`, `location` = "Austin, TX" (`search_term`, `school_level` when filled) | OK: `experiment_variant` = B, `location` = Austin, TX; no `search_term`/`school_level` (left empty) | `qa/05-search-hit.png` |
| 06 | `view_search_results` | Tag fired; params `experiment_variant`, `results_count` (`search_term` when filled) | OK: `experiment_variant` = B, `results_count` = 13 | `qa/06-view-search-results-hit.png` |
| 07 | `compare_add` | Tag fired twice; params `experiment_variant`, `school_id`, `list_position`, `compare_count` (1 then 2) | OK: sch_107 at position 1 with count 1, then sch_064 at position 3 with count 2 | `qa/07-09-hits-after-compare.png` |
| 08 | `compare_view` | Tag fired once; params `experiment_variant`, `compare_count` = 2, `school_ids` | OK: one hit; `compare_count` = 2, `school_ids` = sch_107,sch_064 | `qa/07-09-hits-after-compare.png` |
| 09 | `school_profile_view` | Tag fired; params `experiment_variant`, `school_id`, `source` = "compare" | OK: `school_id` = sch_064, `source` = compare | `qa/07-09-hits-after-compare.png` |
| 10 | `generate_lead` | Tag fired; params `experiment_variant`, `school_id`, `source`, `form_complete` = "true", `lead_type` | OK: sch_064, `source` = compare, `form_complete` = true, `lead_type` = info_request; hit carries `_c` = 1 (key event) | `qa/10-generate-lead-hit.png` |
| 11 | No duplicate `view_search_results` | Exactly one `view_search_results` per search in DebugView (enhanced measurement "Site search" is off) | OK: one per search | `qa/01-03-hits-full-journey.png` |
| 12 | No `form_start` / `form_submit` | Neither event appears in DebugView during the form step ("Form interactions" is off) | OK: neither was sent | `qa/01-03-hits-full-journey.png` |
| 12b | No extra `page_view` after a search | A search does not add a `page_view` in DebugView (page views on history changes are off) | OK: the search sent only `search` and `view_search_results` | `qa/01-03-hits-full-journey.png` |
| 13 | Consent denied on first hits | Before accepting, Tag Assistant → Consent tab shows `analytics_storage: denied`; after accepting, `granted` | OK: all four types denied by default, granted after the update | `qa/13a-consent-denied.png`, `qa/13b-consent-granted.png` |
| 14 | Custom dimensions registered | GA4 Admin → Custom definitions lists event-scoped `experiment_variant`, `source`, `location`, `school_level`, `school_id`, `form_complete`, `lead_type` | OK: 7 of 7, event scope | `qa/14-custom-dimensions.png` |
| 15 | Custom metrics registered | Event-scoped `results_count`, `compare_count`, `list_position` | OK: 3 of 3, event scope, unit Standard | `qa/15-custom-metrics.png` |
| 16 | Key event | GA4 Admin → Key events lists `generate_lead` | OK: created by name ("create with code"), no default value, counted once per event | `qa/16-key-event.png` |
| 17 | Live console clean | DevTools on the live site: no 404 (favicon included) and no error | OK: every same-origin request 200 on the three pages (favicon.svg included); no console error from the site (only warnings from a browser extension) | none (console log read by tool) |

DebugView received the debug device and events (`qa/debugview-device.png`), several minutes behind the hits.
