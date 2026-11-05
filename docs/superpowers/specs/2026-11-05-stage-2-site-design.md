# Stage 2 — Site and dataLayer: design

Status: approved in conversation on 2026-11-05; awaiting owner review of this document.
Parent spec: `2026-11-05-school-compare-analytics-design.md` (sections 3, 5, 8, 9).

## 1. Goal

A static school-search site where every interaction defined in `tracking/events.yaml` produces the matching `dataLayer.push`, published on GitHub Pages. This is a portfolio demo: the point is to show the techniques (dataLayer contract, Consent Mode v2, client-side A/B assignment, automated tracking QA). The data only needs to be plausible and to stay consistent through later stages.

Done means:

- Every event in `tracking/events.yaml` fires on the right interaction with all required parameters and no others, and the "must not fire" cases do not fire (automated Playwright test, part of `uv run pytest`).
- The site is live on GitHub Pages and the owner has seen the pushes in the browser console.

Out of scope for this stage: GTM and GA4 (stage 3; the page keeps an empty slot for the GTM snippet), the traffic simulator (stage 4), CI test runs on GitHub.

## 2. Decisions

- **Plain HTML, CSS and JavaScript, no framework, no build step.** Every `dataLayer.push` is readable in the source.
- **Three real pages** rather than a single-page app, so each page view is a natural page view for GA4 in stage 3 without history-change triggers:
  - `index.html`: search form, result cards, compare tray and side-by-side comparison (tray and comparison exist in variant B only).
  - `school.html?id=sch_042`: school profile with the "Request info" form.
  - `privacy.html`: short cookie notice linked from the banner.
- **A/B assignment** (as in the parent spec): the site draws A or B with probability 0.5 on the first visit, stores it in `localStorage` and reuses it on every later page and visit. The simulator does not choose the variant; it reads the stored value and writes it to the ground-truth log. There is no URL override.
- **Visual style:** clean, neutral, minimal. One stylesheet, system fonts, no images.
- **Schools:** about 200 fake schools in `site/data/schools.json`, generated once by a Python script with a fixed seed and committed. Fields: `id` (`sch_001`…), `name`, `city`, `state`, `level` (`elementary`, `middle`, `high`), `type` (`public`, `private`, `charter`), `rating` (1–10), `students`, `tuition` (0 for public).

## 3. Components

| File | Responsibility |
|---|---|
| `site/js/experiment.js` | `getVariant()`: returns the stored variant or draws and stores one. Storage key `sca_variant`. |
| `site/js/track.js` | `track(event, params)`: the only code that writes to `window.dataLayer`. Adds `experiment_variant` to every event except `consent_update`, then pushes `{event, ...params}`. |
| `site/js/consent.js` | Cookie banner ("Accept all", "Reject all", link to the privacy page). On save: `gtag('consent', 'update', …)`, stores the choice under `sca_consent`, hides the banner, then `track('consent_update', …)`. A stored choice is re-applied on load without a new event. |
| `site/js/search.js` | Search, result cards, compare tray (max 3), comparison table. |
| `site/js/profile.js` | Profile page and "Request info" form. |
| `site/css/style.css` | All styling. |
| `site/data/schools.json` | School data. |
| `scripts/make_schools.py` | Generates `schools.json` (fixed seed). |
| `.github/workflows/pages.yml` | Publishes `site/` to GitHub Pages on every push to `main`. |

Order inside every page's `<head>`:

1. Define `window.dataLayer` and `gtag()`, then `gtag('consent', 'default', …)` with the four values from `events.yaml` (all `denied`).
2. Empty, commented GTM slot (filled in stage 3).
3. Site scripts.

## 4. Interaction rules

| Interaction | Event(s) | Rule |
|---|---|---|
| Submit search | `search`, then `view_search_results` | Parameters come from the form (`search_term`, `school_level`, `location` as `"City, ST"` or state) and the result count. The query goes into the URL (`?q=&level=&location=`) with `history.replaceState`. Reloading or coming back from a profile re-renders the list from the URL **without** firing either event. |
| Click "Compare" on a card (B) | `compare_add` | `list_position` is 1-based in the shown list; `compare_count` is the tray size after the add. A 4th school is rejected with a message and fires nothing. Removing a school fires nothing. |
| Open the comparison (B) | `compare_view` | Fires once per opening; `school_ids` is comma-joined in tray order. Changing the tray while it is open does not fire again. Needs at least 2 schools. |
| Profile page shown | `school_profile_view` | `source` = `results` (from a card), `compare` (from the comparison) or `direct` (no source), passed as `&src=` in the link. Fires once per page load. |
| Submit "Request info" | `generate_lead` | Fields: email (required), grade, start year, message (optional). No field value ever reaches the dataLayer. Invalid email → error message, no event. Valid → button locked, short simulated delay, "Request sent", one event. `form_complete` = all three optional fields filled. `source` = the profile's source. `lead_type` = `info_request`. |
| Save a consent choice | `consent_update` | `analytics_storage` and `ad_storage` = `granted` (Accept all) or `denied` (Reject all). |

## 5. Testing

Playwright (Python, `pytest-playwright`) runs inside the existing `uv run pytest`. A session fixture serves `site/` on a local port; Chromium is installed once with `uv run playwright install chromium`.

A shared helper validates every captured push against `tracking/events.yaml`, loaded through `tracking.spec.load_spec`: the event name exists, required parameters are present, types match (`string`, `int`, `bool`), and no undeclared parameter appears.

Cases:

- Each of the 7 events fires on its interaction and passes the validator.
- Must-not-fire cases: reload of the results page, back from a profile, 4th compare add, removing from the tray, double click on submit, submit with invalid email, re-render of an open comparison.
- Variant: stable across pages and reloads; variant A has no Compare button; a fresh browser context with a stubbed `Math.random` gets each variant.
- Consent: default is `denied` before any choice; the update happens before `consent_update` is pushed; a stored choice does not show the banner again.
- Existing check `test_repo_has_no_personal_context` covers the new files.

## 6. Publishing

1. Owner-approved (2026-11-05): create the public repository `jvbatsef-png/school-compare-analytics` with `gh` and push `main`, only after the full suite passes, including the personal-context check.
2. **[OWNER]** Settings → Pages → Source: GitHub Actions (guided step by step).
3. **[OWNER]** Open the live site, open DevTools (F12) → Console, type `dataLayer`, and watch pushes appear while clicking through the funnel in both variants (guided step by step; switching variant = clearing `sca_variant` in Application → Local Storage).
4. README gets a "Stage 2" section with the live link.

The pre-rewrite backup folder sits outside the repository and does not affect the push. It is deleted after the public repository is verified clean.

## 7. Parent spec fix

The architecture diagram in the parent spec lists "A/B variant" among the things the simulator draws. Change it to say the simulator reads the variant the site assigned, matching the A/B assignment decision.
