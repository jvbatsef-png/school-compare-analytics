# School Compare Analytics — rules for Claude

## Purpose

An end-to-end product measurement project on a fictional school-search marketplace that launches a "Compare schools" feature. It goes from the business question to the decision: measurement requirements, GA4 event spec, dataLayer, GTM and GA4, QA, simulated traffic, reconciliation against a known source of truth, dbt and MetricFlow, Streamlit, Claude skills, an A/B readout and a difference-in-differences analysis. Design: `docs/superpowers/specs/2026-11-05-school-compare-analytics-design.md`.

## Rules

- No agent declares a stage done without running its verification and showing the output.
- Claude never computes numbers in prose: numbers come from SQL or Python, Claude narrates.
- Every stage closes with the owner's approval, a commit and a README line.
- Every number shown to anyone is registered in `validation/numbers.yaml` and recomputed by `tests/test_numbers.py`; results reach the owner only after `results-auditor` returns APPROVED.
- The owner reviews every stage. Steps marked **[OWNER]** in a plan are done by the owner; stop and hand back.
- All data is synthetic. No secrets in Git (`.env` is git-ignored).
- Agents and skills carry no personal context (no employer names, no personal history).
- Repository content is in English.

## Tracking

Read `tracking/events.yaml` before touching anything that sends or reads events. It is the single source of truth for event names, parameters and the dataLayer contract.

GA4 limits, enforced by `tests/test_tracking_spec.py`:

- event name ≤ 40 chars; parameter name ≤ 40 chars; ≤ 25 parameters per event
- names in `snake_case`, starting with a letter
- no reserved prefixes `google_`, `ga_`, `firebase_`
- no reserved event names: `session_start`, `first_visit`, `first_open`, `user_engagement`, `app_remove`

## Commands

- Tests: `uv run pytest -v`
