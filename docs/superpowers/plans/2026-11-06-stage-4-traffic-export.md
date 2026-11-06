# Stage 4 — Simulated traffic and BigQuery export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one behaviour model with two executors (Playwright on the live site, pure Python for the synthetic A/B), write both ground-truth logs, and land the real run in BigQuery with the export questions answered.

**Architecture:** `simulator/behavior.py` turns (variant, seeded RNG) into a `Plan` and into the exact dataLayer events that plan should produce. `browser_run.py` executes plans on the live site and logs what the page actually pushed; `synthetic_run.py` logs `plan_events` directly. `ground_truth.py` owns the JSONL format; `check_run.py` checks each log against `config.yaml` and builds the BigQuery client-ID query.

**Tech Stack:** Python 3.13, PyYAML, Playwright (sync API, already a dev dependency through pytest-playwright), pytest, BigQuery console (sandbox).

**Spec:** `docs/superpowers/specs/2026-11-06-stage-4-traffic-export-design.md`

## Global Constraints

- No new dependencies; randomness from stdlib `random.Random`, seeded per visitor with the string `f"{seed}-{visitor_id}"`.
- Banner: accept 0.55, reject 0.15, ignore 0.30. Ad blocker 0.25, independent of banner and variant.
- Funnel: search 0.85; Compare (B only) 0.30 of visitors who saw results; profile 0.40 (no Compare) / 0.55 (Compare); lead given profile 0.375 / 0.50; complete lead 0.70. One search, at most one lead per visitor.
- Run sizes: real 500, synthetic 6,000 over 14 days. Real-run workers 4; abort when error rate > 0.05 after at least 40 finished visitors; flush waits for 3 s without a new `/g/collect` request (cap 15 s).
- Ground-truth fields exactly as spec section 4; `ts` ISO 8601 UTC ending in `Z`; `visitor_id` `v00001` style.
- `simulator/runs/real_run.jsonl` is committed; `simulator/output/` stays git-ignored.
- No retries of a failed visitor. Debug mode never on. Desktop Chrome user agent string, not `HeadlessChrome`.
- Code and documents in English. Commits `type: short description`, ending with the `Co-Authored-By` line. The anti-leak test (`tests/test_agents.py`) must keep passing.

## Review Focus

1. **The ignored banner is fixed at the bottom of every page** and may sit over result cards, compare buttons or the lead form; an `ignore` visitor must still finish a full Compare-and-lead plan (test in Task 3).
2. **The Python port of the site's filter and sort** (`search.js`: rating desc, then id asc) may drift from the page, which would give the synthetic log wrong `school_id`s; the browser test asserts card ids equal `search_results` ids (Task 3).
3. **A run killed mid-visitor** leaves lines without `visit_end`; on resume that visitor is closed as `error` / `interrupted` and counts toward the target, never re-run (its hits already reached GA4) (Task 4).
4. **Abort threshold on small numbers:** two errors in the first five visitors must not stop the run; the rule only applies from 40 finished visitors (Task 4).
5. **Boundary searches:** a search with exactly 3 results combined with a 3-school Compare and a profile opened from the comparison must stay inside valid positions (Task 1).

---

### Task 1: Config and behaviour model

**Files:**
- Create: `simulator/__init__.py`, `simulator/config.yaml`, `simulator/behavior.py`
- Test: `tests/test_simulator_behavior.py`

**Interfaces:**
- Produces:
  - `load_config(path: Path = CONFIG_PATH) -> dict`; `load_schools(path: Path = SCHOOLS_PATH) -> list[dict]` (`site/data/schools.json`).
  - `@dataclass(frozen=True) Visitor(banner: str, ad_blocker: bool)` — banner in `accept|reject|ignore`.
  - `@dataclass(frozen=True) Search(location: str, level: str, n_results: int)` — `location` is `"City, ST"`, `level` is `""` or `elementary|middle|high`.
  - `@dataclass(frozen=True) Plan(variant: str, search: Search | None, compare_positions: tuple[int, ...], profile_from: str | None, profile_index: int | None, lead: str | None)` — `profile_from` in `results|compare`; `profile_index` is the 1-based list position (results) or tray position (compare); `lead` in `complete|incomplete|None`.
  - `search_results(schools, location: str, level: str) -> list[dict]` — port of `filter` in `site/js/search.js` with empty `q`.
  - `search_options(schools, min_results: int = 3) -> list[Search]` — every (location, level) pair, level `""` included, with at least `min_results` results.
  - `draw_visitor(rng: random.Random, cfg: dict) -> Visitor`
  - `plan_visit(variant: str, rng: random.Random, cfg: dict, options: list[Search]) -> Plan`
  - `plan_events(plan: Plan, visitor: Visitor, schools) -> list[tuple[str, dict]]` — the ordered dataLayer events the site pushes for this plan, plus `("page_view", {"page": "index" | "school"})` at each page load. Params exactly as `site/js/track.js` pushes them: `experiment_variant` on every event except `consent_update`; empty values omitted.
  - `visitor_rng(seed: int, visitor_id: str) -> random.Random`

- [ ] **Step 1: Write `simulator/config.yaml`** with the values in Global Constraints under keys `seed: 20261106`, `site_url` (`https://jvbatsef-png.github.io/school-compare-analytics/`), `real: {visitors, workers, max_error_rate, min_visitors_before_abort, flush_quiet_seconds, flush_max_seconds}`, `synthetic: {visitors, start_date: "2026-10-12", days: 14}`, `banner: {accept, reject, ignore}`, `ad_blocker`, `funnel: {search, compare_b, profile: {no_compare, compare}, lead_given_profile: {no_compare, compare}, complete_lead}`, `bigquery: {project: null, dataset: null}`.

- [ ] **Step 2: Write the failing tests**

```python
def test_rates_match_config():  # 100,000 visitors, seed 1, half A half B
    # each within 0.01 of: accept .55, reject .15, ignore .30, blocker .25,
    # search .85, compare_adoption(B | searched) .30,
    # profile_view_rate(A | searched) .40, (B) .445,
    # lead_rate(A | searched) .15, (B) .1875, complete share .70 both

def test_plan_rules():  # 20,000 plans per variant
    # A never has compare_positions; B compare has 2 or 3 distinct positions <= search.n_results
    # lead implies profile_from; no search implies nothing else
    # profile_from == "compare" implies compare_positions and 1 <= profile_index <= len(compare_positions)
    # profile_from == "results" implies 1 <= profile_index <= min(5, n_results)

def test_search_options_have_three_results():
    # every option: n_results >= 3 and == len(search_results(schools, o.location, o.level))

def test_search_results_order():
    # sorted by rating desc, then id asc

def test_plan_events_compare_and_lead():
    # hand-built Plan(B, Search(..), (1, 3), "compare", 2, "complete") with Visitor("accept", False):
    # names == ["page_view", "consent_update", "search", "view_search_results",
    #           "compare_add", "compare_add", "compare_view", "page_view",
    #           "school_profile_view", "generate_lead"]
    # compare_add list_position/compare_count, compare_view school_ids joined in tray order,
    # school_profile_view source "compare" and school_id == tray[1], generate_lead form_complete True

def test_plan_events_ignore_and_bounce():
    # Visitor("ignore", False) with no search -> [("page_view", {"page": "index"})] only
    # search with level "" -> search params have no school_level and no search_term

def test_visitor_rng_is_deterministic():
    # same (seed, id) -> same plan; different id -> different sequence
```

- [ ] **Step 3: Run** `uv run pytest tests/test_simulator_behavior.py -q` — expected FAIL (module not found).

- [ ] **Step 4: Implement `simulator/behavior.py`.** Draw order inside `plan_visit`: search?, option (uniform over `options`), Compare (B only: count 2 or 3 at 50/50, distinct positions uniform from 1..min(6, n_results)), profile? (rate by path; source `compare` when Compare was used, index uniform over the tray; else `results`, position uniform from 1..min(5, n_results)), lead?, complete?. `consent_update` follows the landing `page_view` for accept/reject with `analytics_storage` and `ad_storage` both `granted` or `denied`.

- [ ] **Step 5: Run** the same command — expected PASS.

- [ ] **Step 6: Commit** `feat: simulator config and behaviour model`

---

### Task 2: Ground-truth log and synthetic executor

**Files:**
- Create: `simulator/ground_truth.py`, `simulator/synthetic_run.py`
- Test: `tests/test_simulator_synthetic.py`

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces:
  - `FIELDS: tuple[str, ...]` — the spec section 4 fields in order.
  - `visitor_lines(run: str, visitor_id: str, variant: str, visitor: Visitor, events: list[tuple[str, dict, str]], ga_client_id: str | None, ga_requests: int | None, status: str, error_step: str | None) -> list[dict]` — `events` items are `(name, params, ts)`; appends the `visit_end` line; `seq` from 1.
  - `append(path: Path, lines: list[dict]) -> None`; `read(path: Path) -> list[dict]`; `by_visitor(lines) -> dict[str, list[dict]]`.
  - `generate(cfg: dict, schools) -> list[dict]` and `main()` writing `simulator/output/ab_synthetic.jsonl` (`uv run python -m simulator.synthetic_run`).

- [ ] **Step 1: Write the failing tests**

```python
def test_round_trip(tmp_path):  # append two visitors, read back equal, every line has exactly FIELDS

def test_events_validate_against_spec():  # generate on a 300-visitor config copy;
    # every line except page_view/visit_end passes tests.site_helpers.assert_valid({"event": e, **params})

def test_synthetic_is_deterministic():  # two generate() calls on the same cfg -> identical lines

def test_synthetic_counts_and_shares():  # full config
    # exactly 6,000 visit_end lines; shares of variant B, each banner value and ad_blocker
    # within 3 * sqrt(p(1-p)/6000) of config; ga_client_id and ga_requests null; status all "ok"

def test_synthetic_timestamps():
    # all ts end with "Z", inside [start_date, start_date + 14 days), hour between 12 and 23 UTC,
    # non-decreasing within a visitor
```

- [ ] **Step 2: Run** `uv run pytest tests/test_simulator_synthetic.py -q` — expected FAIL.

- [ ] **Step 3: Implement.** Variant 50/50 from the visitor RNG; visit start = uniform day in the span, uniform second between 12:00 and 23:00 UTC; events spaced 5–40 s apart.

- [ ] **Step 4: Run** — expected PASS.

- [ ] **Step 5: Commit** `feat: ground-truth log and synthetic A/B executor`

---

### Task 3: Browser executor (one visitor)

**Files:**
- Create: `simulator/browser_run.py` (visitor part)
- Test: `tests/test_simulator_browser.py`

**Interfaces:**
- Consumes: Task 1 (`Visitor`, `plan_visit`, `plan_events`, `search_results`), Task 2 (`visitor_lines`).
- Produces:
  - `GOOGLE_HOSTS: re.Pattern` (same pattern as `tests/conftest.py` `GOOGLE`); `COLLECT = re.compile(r"/g/collect")`; `USER_AGENT: str` (a current desktop Chrome on Windows string).
  - `visit(context: BrowserContext, site_url: str, visitor_id: str, visitor: Visitor, cfg: dict, schools, options: list[Search]) -> list[dict]` — returns ground-truth lines for one visitor (`run="real"`). The caller owns the context.

- [ ] **Step 1: Write the failing tests** (pytest-playwright `browser` and the `site_url` fixture; each test opens `browser.new_context()` and aborts `GOOGLE_HOSTS` itself so the suite stays offline)

```python
def test_logged_events_equal_plan_events(...):  # 12 visitors, ids v00001..v00012, mixed banners
    # for each: [(l["event"], l["params"]) for l in lines[:-1]] == plan_events(plan, visitor, schools)
    # where plan is rebuilt with visitor_rng and the variant logged

def test_cards_match_python_port(...):  # for 5 options: page card ids == [s["id"] for s in search_results(...)]

def test_ignore_banner_full_plan(...):  # force a Plan with Compare of 3 + profile from compare + complete lead
    # and Visitor("ignore", False) via monkeypatching plan_visit; status "ok", generate_lead logged,
    # no consent_update

def test_ad_blocker_sends_nothing(...):  # Visitor(..., True): ga_requests == 0, ga_client_id is None

def test_failed_step_is_logged(...):  # monkeypatch a selector to one that never appears:
    # visit_end status "error", error_step names the step, earlier events kept
```

- [ ] **Step 2: Run** `uv run pytest tests/test_simulator_browser.py -q` — expected FAIL.

- [ ] **Step 3: Implement `visit`.** Ad blocker: `context.route(GOOGLE_HOSTS, abort)` before the first `goto`. Count `/g/collect` via `context.on("request")` only when not blocked. Read the variant with `page.evaluate("SCA.getVariant()")` after load, then `plan_visit(variant, visitor_rng(cfg["seed"], visitor_id), cfg, options)`. Drive the page with the selectors the site tests use (`#consent-accept`, `#consent-reject`, `#level`, `#location`, `#search-form button[type=submit]`, `.compare-btn` on the nth card, `#compare-open`, table links, card links, `#email`, `#grade`, `#start-year`, `#message`, `#lead-submit`); incomplete lead fills only `#email`. Before leaving each page, read its event pushes as `tests/site_helpers.pushes` does and stamp each with the current UTC time. On any Playwright error, stop and log `error` with the step name. Flush: wait until `flush_quiet_seconds` pass without a new collect request (cap `flush_max_seconds`), then read `_ga` from `context.cookies()` and keep the part after the second dot (`GA1.1.123.456` → `123.456`).

- [ ] **Step 4: Run** — expected PASS. Then the whole offline suite: `uv run pytest -q` — expected all pass.

- [ ] **Step 5: Commit** `feat: browser executor for one simulated visitor`

---

### Task 4: Real-run runner, resume and live check

**Files:**
- Modify: `simulator/browser_run.py` (runner and CLI)
- Test: `tests/test_simulator_runner.py`, `tests/test_live_simulator.py`

**Interfaces:**
- Consumes: Task 3 `visit`, Task 2 `append`/`read`/`by_visitor`/`visitor_lines`.
- Produces:
  - `close_interrupted(lines: list[dict]) -> list[dict]` — `visit_end` lines (`status="error"`, `error_step="interrupted"`) for visitors with lines but no `visit_end`.
  - `next_ids(lines: list[dict], target: int) -> list[str]` — ids still to run so the file reaches `target` visitors.
  - `should_abort(lines: list[dict], max_rate: float, min_finished: int) -> bool`
  - `run_real(cfg: dict, target: int, out_path: Path, site_url: str, workers: int, offline: bool = False) -> None` — `workers` threads, each with its own `sync_playwright()` and Chromium (headless, `USER_AGENT`), one new context per visitor, a lock around `append`, checks `should_abort` after each visitor and raises `RunAborted`. `offline=True` aborts Google hosts for every visitor (tests only).
  - CLI: `uv run python -m simulator.browser_run --target 20 [--headed]` → appends to `simulator/runs/real_run.jsonl`, prints a one-line summary.

- [ ] **Step 1: Write the failing tests**

```python
def test_close_interrupted():  # v00002 has events but no visit_end -> one error/interrupted line for v00002 only
def test_next_ids_counts_interrupted():  # 3 finished + 1 interrupted, target 6 -> ["v00005", "v00006"]
def test_no_abort_before_min():  # 2 errors in 5 finished, min 40 -> False
def test_abort_above_rate():  # 3 errors in 40 -> True (7.5%); 2 in 40 -> False (5% is not above)
def test_run_real_offline(tmp_path, site_url):  # target 3, workers 2, offline -> 3 visit_end lines; rerun with target 5 -> 5, ids unique
```

`tests/test_live_simulator.py` (`pytestmark = pytest.mark.live`): one `Visitor("accept", False)` against `tests.ga4_hits.LIVE_URL`, with `/g/collect` captured and aborted in the test's context; assert `ga_requests > 0` and `ga_client_id` matches `^\d+\.\d+$`.

- [ ] **Step 2: Run** `uv run pytest tests/test_simulator_runner.py -q` — expected FAIL.

- [ ] **Step 3: Implement** the four functions and the CLI. `run_real` first appends `close_interrupted(read(out_path))` when the file exists.

- [ ] **Step 4: Run** the offline suite — expected PASS. Run `uv run pytest -m live tests/test_live_simulator.py -q` — expected PASS (no hit reaches GA4).

- [ ] **Step 5: Commit** `feat: real-run runner with resume and abort threshold`

---

### Task 5: Acceptance checker and synthetic dataset

**Files:**
- Create: `simulator/check_run.py`
- Test: `tests/test_simulator_check.py`

**Interfaces:**
- Consumes: Task 2 `read`/`by_visitor`.
- Produces:
  - `summarize(lines) -> dict` — keys `visitors`, `share_B`, `share_accept`, `share_reject`, `share_ignore`, `share_ad_blocker`, `error_rate`, `cookieless_visitors` (reject or ignore, no blocker, status ok).
  - `problems(summary: dict, cfg: dict, expected_visitors: int) -> list[str]` — empty when counts are exact, every share is within 3 standard errors of its configured value (B against 0.5) and `error_rate < max_error_rate`.
  - `client_id_match_sql(lines, table: str) -> str` — a query over `UNNEST([...])` of the logged `ga_client_id`s returning `logged`, `found` and `share_found` against `table` (`` `project.dataset.events_*` ``).
  - CLI: `uv run python -m simulator.check_run <log> --expected N` prints the summary and either `OK` or each problem, exit code 1 on problems.

- [ ] **Step 1: Write the failing tests**

```python
def test_summary_on_hand_built_log():  # 4 visitors, known shares and one error -> exact dict
def test_problems_flags_wrong_count_and_share():  # 5,999 visitors -> count problem; share_accept .60 at n=6000 -> share problem
def test_problems_ok_on_synthetic():  # generate(full cfg) -> problems == []
def test_client_id_sql_lists_ids():  # two ids in the log -> both quoted in the SQL, table name present, nulls skipped
```

- [ ] **Step 2: Run** `uv run pytest tests/test_simulator_check.py -q` — expected FAIL.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** — expected PASS. Generate and check the dataset: `uv run python -m simulator.synthetic_run` then `uv run python -m simulator.check_run simulator/output/ab_synthetic.jsonl --expected 6000` — expected `OK`.

- [ ] **Step 5: Commit** `feat: ground-truth acceptance checker`

---

### Task 6: Google Cloud and BigQuery export link (owner, guided)

Manual; the export does not backfill, so this comes before any real traffic.

- [ ] **Step 1:** Owner creates a Google Cloud project in sandbox mode (no billing account) and enables the BigQuery API.
- [ ] **Step 2:** In GA4 Admin → Product links → BigQuery links: link the project, **Daily** export only, events data, no streaming. Note the dataset name (`analytics_<property id>`).
- [ ] **Step 3:** In GA4 Admin → Data streams → Configure tag settings → Define internal traffic: confirm no rule matches the owner's IP; in Data filters, note the state of "Internal traffic" and "Developer traffic".
- [ ] **Step 4:** Fill `bigquery.project` and `bigquery.dataset` in `simulator/config.yaml`; record the link date and filter states in `docs/bigquery-export-notes.md` (new file, section "Setup").
- [ ] **Step 5: Commit** `docs: BigQuery export linked`

---

### Task 7: Pilot and real run

- [ ] **Step 1:** `uv run python -m simulator.browser_run --target 20`. Owner opens GA4 Realtime within 30 minutes: events from the run appear. If nothing appears, rerun the remaining visitors with `--headed` and record the switch in the notes.
- [ ] **Step 2:** `uv run python -m simulator.browser_run --target 500`, started early enough to finish before midnight in the GA4 property's time zone.
- [ ] **Step 3:** `uv run python -m simulator.check_run simulator/runs/real_run.jsonl --expected 500` — expected `OK`. If not, investigate before continuing (no rerun of logged visitors).
- [ ] **Step 4: Commit** `data: stage 4 real run ground truth` (`simulator/runs/real_run.jsonl` and the run date in the notes).

---

### Task 8: Export checks and close

The day after the run, once `events_YYYYMMDD` exists.

**Files:**
- Create: `warehouse/bigquery/01_events_by_consent.sql`, `02_cookieless_identity.sql`, `03_client_id_match.sql` (generated by `client_id_match_sql`)
- Modify: `docs/bigquery-export-notes.md`, `README.md`, `CLAUDE.md` (stage status only)

- [ ] **Step 1:** Write query 1 (count by `event_name`, `privacy_info.analytics_storage`) and query 2 (null `user_pseudo_id` count; for `analytics_storage = 'No'`: distinct `user_pseudo_id`, distinct (`user_pseudo_id`, `ga_session_id`), IDs spanning more than one session) over `events_*` with `_TABLE_SUFFIX` covering the run dates. Generate query 3 with `client_id_match_sql`.
- [ ] **Step 2:** Owner runs the three queries in the BigQuery console; results go into `docs/bigquery-export-notes.md` with the answers to the three spec questions, the real-run `cookieless_visitors` count next to query 2, and the limit that each simulated visitor has one session.
- [ ] **Step 3:** README marks stage 4 done with a short section (hybrid design, the cookieless-ping finding, 60-day sandbox expiry); `CLAUDE.md` notes stage 4 done.
- [ ] **Step 4:** `uv run pytest -q` — expected all pass.
- [ ] **Step 5: Commit** `docs: close stage 4`
