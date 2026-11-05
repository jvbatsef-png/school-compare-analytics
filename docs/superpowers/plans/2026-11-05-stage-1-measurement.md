# Stage 1: Measurement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide what the "Compare schools" launch must measure, before any site or tracking code exists: business question, metrics, GA4 event spec and the A/B test size.

**Architecture:** Project scaffolding plus the six agents, then three documents and one script. The tracking spec has a machine-readable source (`tracking/events.yaml`) validated by tests against GA4's limits; later stages (site tests, GTM, the `measurement-gap-check` skill) read that same file. The power analysis is a small Python module with tests against a hand-computed value.

**Tech Stack:** Python 3.13 via uv, pytest, PyYAML, statsmodels.

**Spec:** `docs/superpowers/specs/2026-11-05-school-compare-analytics-design.md`

## Global Constraints

- All tools free; all data synthetic; no secrets in Git (`.env` git-ignored).
- Repository content in English. Conversation with the owner in Portuguese.
- Agents and skills carry no personal context: no employer names, no owner name, no personal history.
- The owner performs the manual parts marked **[OWNER]**; nothing advances past a task without the owner's approval.
- Claude never computes numbers in prose: numbers come from code.
- GA4 limits (enforced by tests): event name ≤ 40 chars, parameter name ≤ 40 chars, ≤ 25 parameters per event, names in `snake_case` starting with a letter, no reserved prefixes `google_`, `ga_`, `firebase_`, no reserved event names (`session_start`, `first_visit`, `first_open`, `user_engagement`, `app_remove`).

## Review Focus

- A metric in the measurement plan with no event that can compute it → test `test_every_metric_maps_to_events` (Task 4).
- An event that carries the A/B variant inconsistently (some events missing `experiment_variant`) → test `test_funnel_events_carry_variant` (Task 4).
- Two events or parameters differing only in case (`School_ID` vs `school_id`) → test `test_names_are_snake_case` (Task 4).
- A power analysis whose sample cannot be simulated in reasonable time → test `test_plan_fits_simulator_budget` (Task 5).
- Agent files leaking personal context into a public repo → test `test_agents_have_no_personal_context` (Task 2).

---

### Task 1: Project scaffolding

**Files:**
- Create: `README.md`, `CLAUDE.md`, `.gitignore`, `pyproject.toml`, `tests/__init__.py`

**Interfaces:**
- Produces: a uv project where `uv run pytest` runs; `CLAUDE.md` rules every agent reads.

- [ ] **Step 1:** `uv init --bare` in the repo root, then `uv add --dev pytest` and `uv add pyyaml statsmodels`.
- [ ] **Step 2:** `.gitignore` with `.env`, `.venv/`, `__pycache__/`, `*.duckdb`, `*.duckdb.wal`, `simulator/output/`.
- [ ] **Step 3:** `CLAUDE.md` with: purpose (one paragraph from spec §1), the three project rules from spec §9, the GA4 limits above, "read `tracking/events.yaml` before touching tracking", and "the owner reviews every stage".
- [ ] **Step 4:** `README.md` skeleton: title, one-paragraph story, the architecture diagram from spec §3, a "Stages" table with all 8 stages marked pending.
- [ ] **Step 5:** Run `uv run pytest` → expected "no tests ran" (exit code 5 is acceptable here).
- [ ] **Step 6:** Commit `chore: project scaffolding`.

### Task 2: The team (six agents)

**Files:**
- Create: `.claude/agents/head-of-analytics.md`, `business-analyst.md`, `product-analyst.md`, `gtm-engineer.md`, `data-engineer.md`, `statistician.md`
- Test: `tests/test_agents.py`

**Interfaces:**
- Produces: agent names exactly as above (file stem = `name` in frontmatter), used by every later stage.

- [ ] **Step 1: Write the failing tests**

```python
AGENTS = ["head-of-analytics", "business-analyst", "product-analyst",
          "gtm-engineer", "data-engineer", "statistician"]
FORBIDDEN = []  # forbidden terms live in the git-ignored .private-terms file

def test_all_agents_exist_with_frontmatter():  # name == file stem, description non-empty
def test_agents_have_no_personal_context():    # no FORBIDDEN term, whole word, case-insensitive
def test_head_does_no_technical_work():         # head's tools list has no Write/Edit/Bash
```

- [ ] **Step 2:** `uv run pytest tests/test_agents.py -v` → FAIL (files missing).
- [ ] **Step 3:** Write the six agents. Each: frontmatter (`name`, `description` with when to use, `tools`), role from spec §6, inputs it reads, outputs it writes, and "stop and hand back for owner review". The head's tools are `Read, Grep, Glob, Agent`; it ends every stage with a cross-check list and a summary for the owner.
- [ ] **Step 4:** `uv run pytest tests/test_agents.py -v` → PASS.
- [ ] **Step 5:** **[OWNER]** read `head-of-analytics.md` and one specialist; approve or ask for changes.
- [ ] **Step 6:** Commit `feat: analytics team agents`.

### Task 3: Measurement plan

**Files:**
- Create: `docs/measurement-plan.md`

**Interfaces:**
- Produces: a "Metrics" table with columns `metric_id | type (primary/secondary/guardrail) | definition | numerator | denominator | events_needed`. `metric_id` values and `events_needed` are read by Task 4's tests.

- [ ] **Step 1: [OWNER] first draft, before any agent.** In chat, the owner answers: what question does the launch answer, for families and for school partners? Which one number says "Compare worked"? What must not get worse? Claude records the answers verbatim as the draft.
- [ ] **Step 2:** business-analyst challenges the draft (both sides of the marketplace, business outcome vs. click, opportunity sizing with stated assumptions); product-analyst turns it into the funnel `search → results_view → compare_add → compare_view → school_profile_view → request_info_submit` and the Metrics table.
- [ ] **Step 3:** Sections of the document: business question; hypothesis for the A/B (variant B shows "Compare" on each result card); funnel; Metrics table; decision rule (what result ships, what kills); known measurement limits (consent, ad blockers, GA4 is not the source of truth for counts).
- [ ] **Step 4: [OWNER]** defend each metric out loud (why this denominator, why this guardrail); Claude plays the Director of Product Analytics and pushes back once per metric.
- [ ] **Step 5:** Commit `docs: measurement plan for compare launch`.

### Task 4: Tracking spec (events.yaml + rendered doc)

**Files:**
- Create: `tracking/events.yaml`, `tracking/spec.py`, `docs/tracking-spec.md`
- Test: `tests/test_tracking_spec.py`

**Interfaces:**
- Consumes: `metric_id` and `events_needed` from the Metrics table in `docs/measurement-plan.md`.
- Produces:
  - `tracking/events.yaml`: list of events, each `{name, trigger, funnel: bool, params: [{name, type: string|int|bool, required: bool, example}]}`, plus top-level `consent: {analytics_storage, ad_storage}` defaults and `datalayer_contract` (the exact `dataLayer.push` shape).
  - `tracking/spec.py`: `load_spec(path: str = "tracking/events.yaml") -> dict` and `metric_events(md_path: str = "docs/measurement-plan.md") -> dict[str, list[str]]` (parses the Metrics table).

- [ ] **Step 1: Write the failing tests**

```python
def test_event_names_within_ga4_limits():        # ≤40 chars, snake_case, starts with letter
def test_param_names_within_ga4_limits():        # ≤40 chars, ≤25 per event
def test_no_reserved_names_or_prefixes():
def test_names_are_snake_case():                 # also: no two names equal after lowercasing
def test_funnel_events_carry_variant():          # every funnel: true event has required experiment_variant
def test_every_metric_maps_to_events():          # every events_needed entry exists in events.yaml
```

- [ ] **Step 2:** `uv run pytest tests/test_tracking_spec.py -v` → FAIL.
- [ ] **Step 3:** gtm-engineer writes `events.yaml` from the funnel (one event per funnel step, plus `consent_update`); implement `load_spec` and `metric_events` (parse the markdown table rows by `|`).
- [ ] **Step 4:** `uv run pytest -v` → all PASS.
- [ ] **Step 5:** Render `docs/tracking-spec.md` from the YAML (one table per event, the dataLayer contract as a code block, consent defaults). Written by hand or by a 20-line script in `tracking/spec.py::render_markdown(spec: dict) -> str`.
- [ ] **Step 6: [OWNER]** for one event, say in your own words when it fires and why each parameter exists.
- [ ] **Step 7:** Commit `feat: GA4 tracking spec with validation tests`.

### Task 5: Power analysis

**Files:**
- Create: `analysis/power.py`, `analysis/power_report.md`
- Test: `tests/test_power.py`

**Interfaces:**
- Produces:
  - `sample_size_per_arm(baseline: float, mde_relative: float, alpha: float = 0.05, power: float = 0.80) -> int` (two-sided, two proportions, `statsmodels` `NormalIndPower` + `proportion_effectsize`, rounded up).
  - `SIMULATOR_BUDGET_SESSIONS = 6000` (assumption: ~3 s per Playwright session, 4 in parallel, ≈ 1.25 h; re-measured in stage 4).
  - `analysis/power_report.md`: chosen baseline, MDE, n per arm, total sessions; read by stage 4 to configure the simulator and its true effect.

- [ ] **Step 1: Write the failing tests**

```python
def test_known_case():            # baseline 0.05, mde 0.10 → 30_500 <= n <= 31_700
def test_bigger_effect_needs_fewer():   # n(mde=0.20) < n(mde=0.10)
def test_rejects_bad_inputs():    # baseline outside (0,1) or mde <= 0 → ValueError
def test_plan_fits_simulator_budget():  # values in power_report.md: 2 * n <= SIMULATOR_BUDGET_SESSIONS
```

- [ ] **Step 2:** `uv run pytest tests/test_power.py -v` → FAIL.
- [ ] **Step 3:** Implement `sample_size_per_arm`; statistician explains the four inputs (baseline, MDE, alpha, power) in plain words in `power_report.md`.
- [ ] **Step 4: [OWNER]** choose baseline and MDE for the primary metric. The budget forces the real trade-off: a small effect needs more traffic than we can simulate, so pick the smallest MDE that fits and write down why. Statistician then sets the simulator's true effect above that MDE.
- [ ] **Step 5:** `uv run pytest -v` → all PASS.
- [ ] **Step 6:** Commit `feat: power analysis for compare A/B`.

### Task 6: Close the stage

**Files:**
- Modify: `README.md` (stage 1 section and table row)
- Create (outside repo): owner's private study notes for stage 1

- [ ] **Step 1:** head-of-analytics cross-check: every metric has events (test), every funnel event has the variant (test), power report matches the primary metric of the plan; summary to the owner.
- [ ] **Step 2:** `uv run pytest -v` → all PASS; paste the output.
- [ ] **Step 3:** README "Stage 1 — Measurement" section: what was decided and links to the three documents.
- [ ] **Step 4:** Owner's private study notes (outside the repo): how to instrument a feature, how to size an A/B test, why GA4 is not the source of truth.
- [ ] **Step 5: [OWNER]** approve the stage. Commit `docs: close stage 1`.
