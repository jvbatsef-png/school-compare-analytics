# Stage 4 — Simulated traffic and BigQuery export: design

Status: approved in conversation on 2026-11-06; awaiting owner review of this document.
Parent spec: `2026-11-05-school-compare-analytics-design.md` (sections 3, 4, 9 and the stage 4 acceptance check).
Previous stage: `2026-11-05-stage-3-gtm-ga4-design.md`.

## 1. Goal

Produce the two ground-truth logs the rest of the project reads, and land real GA4 data in BigQuery:

- a **real run** of 500 visitors driven by Playwright through the live site, GTM and GA4, exported daily to the BigQuery sandbox;
- a **synthetic A/B dataset** of 6,000 visitors generated in Python from the same behaviour model, carrying the known true effect.

Done means:

- `uv run pytest` passes (existing tests plus the new offline tests).
- Both ground-truth logs match `simulator/config.yaml`: exact visitor counts (500 and 6,000) and consent, ad-blocker and variant shares inside their expected sampling range (section 8).
- Fewer than 5% of real-run visitors end in `error`.
- The run day's `events_YYYYMMDD` table exists in BigQuery, and `docs/bigquery-export-notes.md` answers the three export questions (section 7).
- README marks stage 4 as done.

Out of scope: loading BigQuery into DuckDB and the GA4-versus-truth reconciliation (stage 5), Python access to BigQuery (stage 5), the DiD history (stage 8).

## 2. Decisions

- **Hybrid traffic.** The A/B volume is synthetic; a small real run proves the pipeline. Reason: the A/B decision is read on ground truth, not GA4 (stage 1 decision), so 6,000 real visits add hours of browser time and bot-filter risk without changing the decision. The real run still measures GA4's loss against truth and shows the real export schema. The GA4-side A/B estimate in stage 7 comes from the real run and is deliberately underpowered; that is a talking point, not a defect.
- **One behaviour model, two executors.** `behavior.py` turns (variant, random generator) into a visit plan. The browser executor runs the plan on the live site; the synthetic executor writes the events the plan implies. Reason: real and synthetic visitors behave the same, so differences in stage 5 come from GA4, not from two diverging rule sets. Rejected: two independent scripts (rules drift apart) and replaying 500 pre-drawn synthetic plans in the browser (the site draws the variant, so a plan drawn in advance may not fit the variant the site assigns).
- **The site keeps drawing the variant.** The browser executor reads it from the page after load (`SCA.getVariant()`), then asks the model for a plan. The synthetic executor draws it 50/50 itself.
- **Ground truth records what the site pushed.** Before leaving each page, the browser executor reads `window.dataLayer` and logs the events found there, not the events it intended. Reason: ground truth plays the production database; it must record what happened.
- **Consented visitors carry their GA4 client ID.** The executor reads the `_ga` cookie (`GA1.1.<random>.<timestamp>`) and logs `<random>.<timestamp>`, which is the `user_pseudo_id` GA4 exports. Stage 5 can then match consented visitors one to one. Visitors who declined or ignored the banner have no cookie and are reconciled on totals.
- **Export check by console SQL.** Stage 4 queries BigQuery through saved `.sql` files run in the BigQuery console. No credentials on the machine until stage 5 needs them.

### Cookieless pings in the export (checked in Google documentation, 2026-11-06)

Stage 3 recorded the hypothesis that consent-denied pings reach BigQuery with a null `user_pseudo_id`. Google's documentation does not support "null":

- Cookieless pings are present in the export when consent mode is implemented ([BigQuery Export help](https://support.google.com/analytics/answer/9358801)).
- In the export, each session of a consent-denied visitor gets a different `user_pseudo_id`; none of the modeled data is exported ([Google for Developers blog, 2023](https://developers.google.com/analytics/blog/2023/bigquery-vs-ui)).
- `privacy_info.analytics_storage` takes `Yes`, `No` or `Unset` ([export schema](https://support.google.com/analytics/answer/7029846)).

Consequence: counting distinct `user_pseudo_id` overcounts declined visitors, one "user" per session. The blog is from 2023 and the schema page is silent on nulls, so stage 4 checks this on the real export (section 7).

## 3. Components

| Path | Purpose |
|---|---|
| `simulator/config.yaml` | All numbers in one place: banner and ad-blocker rates, funnel probabilities per path, run sizes (500 real, 6,000 synthetic), synthetic date span (14 days), random seed, site URL, worker count, error threshold. |
| `simulator/behavior.py` | `draw_visitor(rng)` → banner choice and ad blocker; `plan_visit(variant, rng, schools)` → ordered steps (search terms, which result to open, compare picks, form completeness). Pure Python, no browser. |
| `simulator/ground_truth.py` | Writes and reads the JSONL log (schema in section 4). Appends one visitor at a time so a run can stop and resume. |
| `simulator/browser_run.py` | Playwright executor against the live site. One fresh browser context per visitor, 4 in parallel. |
| `simulator/synthetic_run.py` | Synthetic executor: 6,000 visitors, timestamps spread over 14 days in daytime hours. |
| `simulator/runs/real_run.jsonl` | Real-run ground truth. Committed: small and not reproducible (the site draws the variant). |
| `simulator/output/ab_synthetic.jsonl` | Synthetic ground truth. Git-ignored (`simulator/output/` is already ignored); regenerated by one command, identical for the same seed. |
| `warehouse/bigquery/*.sql` | The console queries of section 7. |
| `docs/bigquery-export-notes.md` | Answers to the export questions, with the query results. |

## 4. Ground-truth schema

One JSON object per line, one line per event:

| Field | Type | Notes |
|---|---|---|
| `run` | string | `real` or `synthetic` |
| `visitor_id` | string | `v00001`… unique within a run |
| `seq` | int | order of the event within the visitor |
| `ts` | string | ISO 8601 UTC |
| `variant` | string | `A` or `B` |
| `banner` | string | `accept`, `reject` or `ignore` |
| `ad_blocker` | bool | |
| `ga_client_id` | string or null | only for `accept` without ad blocker, real run |
| `ga_requests` | int | `/g/collect` requests the browser sent for this visitor (real run; null in synthetic); written on the `visit_end` line |
| `status` | string | `ok` or `error`, on the `visit_end` line |
| `error_step` | string or null | the step that failed |
| `event` | string | a name from `tracking/events.yaml`, `page_view`, or `visit_end` |
| `params` | object | the event's parameters, keys as in `events.yaml` |

`visit_end` closes every visitor and carries `status`, `error_step` and `ga_requests`.

## 5. Behaviour model

Visitor draws, independent of each other and of the variant:

| Banner | Share |
|---|---|
| accept | 55% |
| reject | 15% |
| ignore (default stays denied, no `consent_update`) | 30% |

Ad blocker: 25%. With a blocker, the executor aborts every request to Google tag and analytics hosts, so GA4 receives nothing. Expected GA4 visibility: about 41% with cookies, 34% cookieless, 25% nothing.

Funnel, per visitor:

1. **Search:** 85% search; the rest bounce after the landing page (they never reach `view_search_results`, so they are outside the `lead_rate` denominator). Searches are drawn from `schools.json` values that return at least one result.
2. **Compare (variant B only):** 30% of visitors who saw results add 2 or 3 schools and open the table.
3. **Profile view and lead:**

| Path | Opens a profile | Sends a lead, given profile | Lead rate |
|---|---|---|---|
| A | 40% | 37.5% | 15% |
| B without Compare (70%) | 40% | 37.5% | 15% |
| B with Compare (30%) | 55% | 50% | 27.5% |
| **B overall** | 44.5% | | **18.75%** |

4. **Complete lead:** 70% of leads fill grade, year and message, in both variants.

True values: `lead_rate` 15% → 18.75% (+25%); `profile_view_rate` 40% → 44.5%; `complete_lead_share` 70% in both; `compare_adoption` 30% in B. One search and at most one lead per visitor. Observed sample values vary around these; stage 7 must recover +25% inside its confidence interval.

## 6. Browser executor

- **Target:** the published site URL in `config.yaml`.
- **Bot filtering:** regular desktop Chrome user agent (headless Chromium announces `HeadlessChrome`); debug mode never on; before the run, the owner checks that no GA4 internal-traffic filter matches their IP.
- **Pilot first:** 20 visitors with `-m live`, then the owner checks GA4 Realtime. If nothing shows, fall back to headed mode.
- **Flush before close:** after the last step, wait until no new `/g/collect` request has been sent for 3 seconds, then close the context. The count of requests sent goes to `ga_requests`.
- **Failures:** a step that times out marks the visitor `error` with `error_step`; events already pushed stay logged. No retry (a retry would double-send to GA4). The run stops when more than 5% of visitors so far have failed (checked after the first 40).
- **Pace:** 4 parallel contexts, about 25 minutes for 500 visitors, all on one day.

## 7. BigQuery export and checks

Order of work, because the export does not backfill:

1. Owner, guided: create a Google Cloud project in sandbox mode (no billing), enable the BigQuery API, link GA4 to BigQuery with **daily** export, check internal-traffic filters.
2. Same day or later: pilot, then the 500-visitor run.
3. Next day: the `events_YYYYMMDD` table appears (GA4 can take more than 24 hours).

Console queries in `warehouse/bigquery/`, answers in `docs/bigquery-export-notes.md`:

1. **What arrived:** event counts by `event_name` and `privacy_info.analytics_storage`.
2. **Cookieless identity:** any null `user_pseudo_id`? For `analytics_storage = 'No'`, does any `user_pseudo_id` span more than one `ga_session_id`, and how does the count of distinct IDs compare with the number of reject and ignore visitors without ad blocker in the real-run log? Each simulated visitor has one session, so the run can show one ID per session but not one visitor split across sessions; the notes say so.
3. **Client ID match:** share of real-run `ga_client_id` values found as `user_pseudo_id`.

Sandbox tables expire after 60 days; stage 5 copies the data to DuckDB before then.

## 8. Testing

Offline (`uv run pytest`):

- **Behaviour model:** with a fixed seed and 100,000 draws, every rate in section 5 lands within 1 percentage point of its true value; plans obey the rules (a lead needs a profile view, Compare only in B, at most 3 schools in the tray, one search, at most one lead).
- **Ground truth:** writer and reader round-trip; every event other than `page_view` and `visit_end` validates its name and parameter set against `events.yaml`.
- **Synthetic executor:** same seed, identical file; exactly 6,000 visitors; variant, banner and ad-blocker shares within 3 standard errors of their configured values; timestamps inside the 14-day span.
- **Browser executor:** runs a few visitors against the local test server the suite already starts, with Google hosts aborted; logged events match `events.yaml`; an ad-blocker visitor sends zero requests; a banner click is logged as `consent_update` and an ignored banner is not.

Live (`uv run pytest -m live`): the 20-visitor pilot against the published site, asserting that consented visitors send `/g/collect` requests and get a `_ga` cookie.

Acceptance (section 1): a script compares each log with `config.yaml` (counts exact; shares within 3 standard errors) and reports the error rate.
