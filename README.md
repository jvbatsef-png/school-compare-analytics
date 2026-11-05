# School Compare Analytics

A fictional school-search marketplace launches **"Compare schools"**. Did it work?

This repository follows that launch the way a product analytics team would: from the business question to the decision. It writes the measurement requirements and the GA4 event spec, builds the dataLayer and the GTM tags, and runs QA. It then drives simulated traffic through a real browser and reconciles GA4 against a known source of truth. dbt and a MetricFlow semantic layer define the sanctioned metrics, and a Streamlit app serves them. The analysis covers an A/B test and a difference-in-differences study. The work is done by a team of Claude Code agents, with a human reviewing every stage.

Everything is synthetic and runs at zero cost.

## Architecture

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

## Stages

| # | Stage | Status |
|---|---|---|
| 1 | Measurement: plan, tracking spec, power analysis | done |
| 2 | Site and dataLayer | pending |
| 3 | GTM and GA4 | pending |
| 4 | Simulated traffic and BigQuery export | pending |
| 5 | DuckDB and reconciliation | pending |
| 6 | dbt and MetricFlow | pending |
| 7 | Streamlit, Claude skills, A/B readout | pending |
| 8 | Difference-in-differences | pending |
| 9 | Readout deck | pending |

## Stage 1 — Measurement

Everything here was decided before a single line of site code exists.

- **Question and decision rule.** Primary metric `lead_rate`: share of visitors who saw results and sent at least one info request. Guardrails: `profile_view_rate` and `complete_lead_share`. Ship only if `lead_rate` rises significantly and no guardrail drops. See [docs/measurement-plan.md](docs/measurement-plan.md).
- **Comparison.** A/B test, randomized by visitor, read as intent-to-treat. Comparing "users who clicked Compare" with "users who did not" would mix the button's effect with selection bias.
- **Event spec.** Six funnel events, GA4 recommended names where they exist (`search`, `view_search_results`, `generate_lead`), every one carrying `experiment_variant`, Consent Mode v2 defaults to denied. [tracking/events.yaml](tracking/events.yaml) is the source; [docs/tracking-spec.md](docs/tracking-spec.md) is generated from it, and tests enforce GA4 naming limits and metric-to-event coverage.
- **Sample size.** Baseline 15%, minimum detectable effect +20% relative (15% → 18%), alpha 0.05 two-sided, power 0.80: **2,399 visitors per arm**, inside the 3,000-per-arm simulator budget. See [analysis/power_report.md](analysis/power_report.md); the numbers come from `analysis/power.py`.
- **Source of truth.** GA4 loses events to consent and ad blockers, so it is the tool under test, not the source of truth. The simulator's ground-truth log is, and stage 5 measures the gap per variant.

Run the checks with `uv run pytest`.
