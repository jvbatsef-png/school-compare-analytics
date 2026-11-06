# Stage 3 QA script: GTM Preview and GA4 DebugView

Run after the live test (`uv run pytest -m live`) passes, and before stage 4's simulator starts.
Event names and parameters below come from `tracking/events.yaml`; if that file changes, regenerate the container and update this table.

## How to open the tools

- **GTM Preview:** tagmanager.google.com → container → **Preview** → enter the site URL → a new tab opens with the site connected to Tag Assistant. Each `dataLayer` push appears in the left column; click it to see **Tags fired** and **Variables**.
- **GA4 DebugView:** analytics.google.com → Admin → **DebugView**. Preview traffic carries `debug_mode`, so events from the Preview tab show up here within seconds. Click an event to see its parameters.
- **Journey (variant B):** accept cookies → search with Location "Austin, TX" → Compare on two cards → Compare (open the table) → open a school from the table → fill email, grade, start year and message → Send.
- **Screenshots:** `tracking/gtm/qa/NN-<check>.png`, where NN is the row number.

## Checks

| # | Check | Expected | Result | Screenshot |
|---|---|---|---|---|
| 01 | `page_view` on `index.html` | One `page_view` per load in DebugView | | |
| 02 | `page_view` on `school.html` | One `page_view` per load | | |
| 03 | `page_view` on `privacy.html` | One `page_view` per load | | |
| 04 | `consent_update` | Tag "GA4 event - consent_update" fired; params `experiment_variant`, `analytics_storage`, `ad_storage` | | |
| 05 | `search` | Tag "GA4 event - search" fired; params `experiment_variant`, `location` = "Austin, TX" (`search_term`, `school_level` when filled) | | |
| 06 | `view_search_results` | Tag fired; params `experiment_variant`, `results_count` (`search_term` when filled) | | |
| 07 | `compare_add` | Tag fired twice; params `experiment_variant`, `school_id`, `list_position`, `compare_count` (1 then 2) | | |
| 08 | `compare_view` | Tag fired once; params `experiment_variant`, `compare_count` = 2, `school_ids` | | |
| 09 | `school_profile_view` | Tag fired; params `experiment_variant`, `school_id`, `source` = "compare" | | |
| 10 | `generate_lead` | Tag fired; params `experiment_variant`, `school_id`, `source`, `form_complete` = "true", `lead_type` | | |
| 11 | No duplicate `view_search_results` | Exactly one `view_search_results` per search in DebugView (enhanced measurement "Site search" is off) | | |
| 12 | No `form_start` / `form_submit` | Neither event appears in DebugView during the form step ("Form interactions" is off) | | |
| 12b | No extra `page_view` after a search | A search does not add a `page_view` in DebugView (page views on history changes are off) | | |
| 13 | Consent denied on first hits | Before accepting, Tag Assistant → Consent tab shows `analytics_storage: denied`; after accepting, `granted` | | |
| 14 | Custom dimensions registered | GA4 Admin → Custom definitions lists event-scoped `experiment_variant`, `source`, `location`, `school_level`, `school_id`, `form_complete`, `lead_type` | | |
| 15 | Custom metrics registered | Event-scoped `results_count`, `compare_count`, `list_position` | | |
| 16 | Key event | GA4 Admin → Key events lists `generate_lead` | | |
| 17 | Live console clean | DevTools on the live site: no 404 (favicon included) and no error | | |
