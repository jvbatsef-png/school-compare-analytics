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
| 1 | Measurement: plan, tracking spec, power analysis | in progress |
| 2 | Site and dataLayer | pending |
| 3 | GTM and GA4 | pending |
| 4 | Simulated traffic and BigQuery export | pending |
| 5 | DuckDB and reconciliation | pending |
| 6 | dbt and MetricFlow | pending |
| 7 | Streamlit, Claude skills, A/B readout | pending |
| 8 | Difference-in-differences | pending |
