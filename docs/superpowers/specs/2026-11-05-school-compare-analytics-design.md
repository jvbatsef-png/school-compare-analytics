# School Compare Analytics: design

Date: 2026-11-05 · Status: approved in brainstorming, pending written-spec review

## 1. Purpose

A hands-on, end-to-end product measurement project, built to learn by doing and to serve as a public portfolio demo of senior product analytics work (measurement partnership and Claude-powered analytics).

The story: a fictional school-search marketplace launches a **"Compare schools"** feature. The project follows that launch from the business question to the decision: measurement requirements, GA4 event spec, dataLayer, GTM and GA4 (real accounts), QA, simulated traffic, reconciliation against a source of truth, dbt models and a MetricFlow semantic layer, a Streamlit app, Claude skills that make the data self-serve, an A/B test readout and a difference-in-differences analysis.

Success criteria:

- Every stage runs end to end on a local machine, at zero cost.
- Every number the project reports is checked against a known ground truth.
- The owner can explain the *why* of every decision, in English, to a technical audience.

Working mode: slow and guided. The owner performs the manual steps (accounts, GTM UI, Preview, reviews); Claude Code agents do the build work; nothing advances without the owner's review.

## 2. Constraints

- All tools free: GitHub Pages, GTM, GA4, BigQuery sandbox, DuckDB, dbt Core, MetricFlow (Apache 2.0 since v0.209), Streamlit, Playwright.
- DuckDB stands in for Snowflake. A Snowflake trial (30 days / US$400) is activated only if a Snowflake run is ever needed.
- All data is synthetic. No real school, user or company data.
- Public repository: no secrets in Git, no personal context in agents or skills.
- Repository content is in English.

## 3. Architecture and data flow

```
static site (GitHub Pages)              simulator (Playwright, local)
 search → card → Compare → Request info   ├─ visits the site as a real browser
 cookie banner (Consent Mode v2)          ├─ draws: consent? ad blocker? A/B variant
 dataLayer.push(...)                      └─ logs what it actually did → ground_truth.jsonl
        │
       GTM ──► GA4 (demo-only property) ──► daily export ──► BigQuery sandbox
                                                                  │
                        DuckDB (local) ◄── download ──────────────┘
                           │  ◄── ground_truth.jsonl
                           │  ◄── 24-week synthetic backend history (DiD only)
                        dbt (dbt-duckdb) → staging → marts → MetricFlow metrics
                           │
              Streamlit (reconciliation, funnel, A/B, DiD)   +   Claude skills
```

Decisions:

- **Site:** plain HTML and JavaScript, no framework, so every `dataLayer.push` is visible in source. About 200 fake schools in `schools.json`.
- **A/B assignment:** randomized in the browser, persisted in `localStorage` so a visitor always sees the same variant; the variant is pushed to the dataLayer and written to the ground-truth log.
- **Source of truth:** the simulator's `ground_truth.jsonl` plays the role of the production database. It records every action each simulated visitor took, including the ones GA4 never saw because of declined consent or an ad blocker. Because the simulator sets those rates, the reconciliation can be checked against a known answer.
- **Consent:** a cookie banner implementing Google Consent Mode v2.
- **GA4:** a property used only for this demo.
- **Export:** GA4 daily (batch) export to the BigQuery sandbox. Streaming export needs billing and is out of scope, so data lands the next day. Sandbox limits (10 GB storage, 1 TB queries/month, 1M events/day export) are far above the simulated volume.
- **Known risk:** GA4 excludes known bot traffic, and headless Playwright identifies itself. Stage 4 starts with a small test run; if hits are dropped, the simulator uses a regular browser user agent or headed mode.
- **Secrets:** the GTM container ID is public by nature. BigQuery credentials live in a git-ignored `.env`.

## 4. Two launches, two methods

**A/B test (stages 1, 4, 5, 7).** Variant B shows a "Compare" button on every search result card; control does not. The simulator is given a known true effect on the primary metric. The statistician sizes the test (power analysis) before traffic runs, and the readout must recover the true effect within its confidence interval.

**Difference-in-differences (stage 8, optional).** Compare is rolled out first to a subset of states (for example TX and FL). Because GA4 cannot receive backdated events (Measurement Protocol allows 72 hours), this case uses 24 weeks of synthetic **backend** history generated directly in DuckDB, with the admissions-season peak (September to January), parallel pre-trends and a known true effect. The analysis must show that a naive pre/post estimate overstates the effect, that DiD recovers it with a confidence interval, and must include a parallel-trends check. This mirrors practice: DiD runs on warehouse data, not on GA4.

## 5. Repository layout

```
school-compare-analytics/
├─ README.md                    the story, one section added per stage
├─ CLAUDE.md                    project rules for Claude
├─ .claude/
│  ├─ agents/                   head-of-analytics, business-analyst, product-analyst,
│  │                            gtm-engineer, data-engineer, statistician, insights-presenter,
│  │                            results-auditor
│  └─ skills/                   school-metrics, launch-readout, measurement-gap-check
├─ docs/
│  ├─ superpowers/specs/        this spec
│  ├─ measurement-plan.md       stage 1
│  ├─ tracking-spec.md          stage 1: events, parameters, dataLayer contract
│  └─ gtm/                      stage 3: container export and QA script
├─ site/                        HTML/JS + schools.json
├─ simulator/                   Playwright traffic + DiD history generator
├─ warehouse/                   BigQuery → DuckDB loader (.duckdb file git-ignored)
├─ dbt/                         models, tests, semantic models
├─ validation/                  numbers.yaml: registry of every published number
├─ app/                         Streamlit
└─ analysis/                    power analysis, A/B readout, DiD
```

## 6. The team (Claude Code agents)

Project-specific agents in `.claude/agents/`, written for this repository and free of personal context.

| Agent | Role |
|---|---|
| head-of-analytics | Orchestrator. Reads the spec and project state, splits each stage into tasks, dispatches specialists, cross-checks their outputs (does the metric match the event?) and stops for the owner's review. Does no technical work itself. |
| business-analyst | Business question for both sides of the marketplace (families, school partners), opportunity sizing, the "so what" of the final readout. |
| product-analyst | Measurement requirements, funnel, primary/secondary/guardrail metrics, GA4 event spec. |
| gtm-engineer | dataLayer contract, GTM tags/triggers/variables, Consent Mode v2, Preview and DebugView QA script. |
| data-engineer | Simulator, BigQuery export and DuckDB load, dbt models and tests, DiD history. |
| statistician | Power analysis, A/B design and readout, confidence intervals in the reconciliation, DiD, honest signal-versus-noise calls; explains every result in plain words (is it real, is it causal, how big, does it matter). |
| insights-presenter | Streamlit self-serve app (stage 7) and, optionally, the readout deck (stage 9). Never computes numbers; reads only validated metrics. |
| results-auditor | Independent, sceptical validation at the end of stages 5, 7, 8 and 9: recomputes every published number from raw data by a different path, checks lineage and experiment validity, returns APPROVED or REJECTED. Runs queries; edits nothing. |

Every agent is written as a senior specialist in its field: what it masters, the checks it runs, the pitfalls it catches.

## 7. Product skills (deliverables for the "Claude-powered analytics" block)

Built in stage 7, once data and metrics exist.

- **school-metrics:** sanctioned metric definitions, table guide for DuckDB and dbt, rules such as "never count leads from GA4; use the source of truth".
- **launch-readout:** produces the Compare launch readout. Pulls numbers through MetricFlow only, re-checks each number with a second query, drafts the text with a clear "so what".
- **measurement-gap-check:** reads a pull request diff and flags UI changes that did not update the dataLayer or the tracking spec.

## 8. Stages

Each stage is its own session with its own implementation plan. Each ends with the owner's review, a commit and a README section.

| # | Stage | Agents | Owner's manual part | Output |
|---|---|---|---|---|
| 1 | Measurement | business-analyst, product-analyst, statistician | write and defend the metrics | measurement plan, tracking spec, power analysis |
| 2 | Site and dataLayer | gtm-engineer | publish on GitHub Pages, check pushes in the console | live site |
| 3 | GTM and GA4 | gtm-engineer | create accounts, build tags, run Preview and DebugView | published container, QA script |
| 4 | Traffic and export | data-engineer, statistician | enable BigQuery export, run the simulator | data in BigQuery, ground-truth log |
| 5 | DuckDB and reconciliation | data-engineer, statistician | explain the GA4-versus-truth gap | reconciliation report |
| 6 | dbt and MetricFlow | data-engineer, product-analyst | run `dbt build`, query metrics | tested models, sanctioned metrics |
| 7 | Streamlit, skills, readout | insights-presenter, statistician, business-analyst | use the app, review the generated readout | app, 3 skills, A/B readout |
| 8 | Difference-in-differences | data-engineer, statistician | interpret the result | DiD analysis (optional) |
| 9 | Readout deck | insights-presenter, business-analyst, statistician | present it out loud | deck covering reconciliation, A/B and DiD (optional) |

## 9. Verification

The ground truth is known, so every analysis is tested against it.

| Stage | Must pass |
|---|---|
| 2 | Every interaction produces the `dataLayer.push` the spec defines, with all parameters (automated Playwright test). |
| 3 | Every spec event appears in DebugView with the right parameters (manual QA script, screenshot and result per item). |
| 4 | Ground-truth totals match what the simulator was configured to run. |
| 5 | The measured GA4-versus-truth gap falls within the range implied by the configured consent and ad-blocker rates; otherwise investigate before moving on. |
| 6 | `dbt build` passes (unique, not-null, accepted-values tests); each MetricFlow metric matches a hand-written SQL query. |
| 7 | Every number in the generated readout is re-checked by a second query; the estimated A/B effect lands near the true effect, inside its CI. |
| 8 | DiD recovers the true effect; naive pre/post does not. |
| 9 | Every number on the deck matches the app and the readout. |

**Validation layer (from stage 5 on).** Whoever produces a number does not get to be the only one who checks it.

- **Number registry:** `validation/numbers.yaml` lists every number shown to anyone (readout, app, deck) with its value, source query and tolerance. `tests/test_numbers.py` recomputes each one, and checks lineage totals along ground truth → DuckDB → dbt marts → MetricFlow. The app, the deck and the `launch-readout` skill show only registered numbers.
- **Independent audit:** `results-auditor` recomputes headline numbers by its own path from raw data and must return APPROVED before results reach the owner.

Project rules (go into `CLAUDE.md`):

- No agent declares a stage done without running its verification and showing the output.
- Claude never computes numbers in prose: numbers come from SQL or Python, Claude narrates.
- Every stage closes with the owner's approval, a commit and a README line.

## 10. Out of scope

Real server-side tagging, CI on GitHub, cloud deploy of Streamlit (possible later on Streamlit Community Cloud, free), real data, and Snowflake.
