# Measurement plan: Compare button (A/B test)

Stage 1. Owner: product analyst (measurement), business analyst (question and sizing). Status: draft for owner review.

## 1. Business question

> Does showing the Compare button make more families request info from a school (more leads for paying school partners) without hurting the experience for families who search?

This is a two-sided marketplace. Each side needs something different:

- **Families (free side):** find the right school faster. Compare only matters to the business if it turns into action: an info request. A family that compares and leaves is activity, not an outcome.
- **School partners (paying side):** pay to be found (profile visibility) and to receive leads (info requests). Value for partners is more leads, of the same or better quality, without losing profile views.

What we would do if the result is flat: do not ship, keep the control, and revisit the design. This is decided before seeing data.

### Opportunity sizing (formula, assumptions only)

```
extra_leads_per_period = eligible_visitors x baseline_lead_rate x relative_lift
value_to_partners      = extra_leads_per_period x value_per_lead
```

| Input | Meaning | Source (to fill) |
|---|---|---|
| eligible_visitors | Visitors who see search results in the period | Assumption: traffic forecast |
| baseline_lead_rate | lead_rate in control | Assumption: current site data |
| relative_lift | Expected relative change in lead_rate from variant B | Assumption: see power report |
| value_per_lead | What a partner pays or earns per lead | Assumption: partner contracts |

Report the result as a range (low, base, high), never one number. Admissions season (September to January) is high-traffic and summer is low, so `eligible_visitors` must state the period it covers.

## 2. Hypothesis

If every search result card shows a Compare button, families can narrow a shortlist without opening each profile, so a larger share of visitors send at least one info request. Profile views and lead quality stay at least as good as control.

- H0: lead_rate in B equals lead_rate in A.
- H1: lead_rate in B differs from lead_rate in A (two-sided test).

## 3. Why we compare groups, not users

We compare **all visitors randomized to B** against **all visitors randomized to A** (intent-to-treat). We do not compare "users who used Compare" with "users who did not".

Families who choose to compare are already more engaged and more serious about applying. They would request info at a higher rate even without the feature. That gap is selection bias, and it would make the feature look better than it is. Randomization removes it: the two groups differ only by the button, so any difference in outcomes is caused by the button. Variant B includes visitors who never click Compare; that is intended, because the decision is about showing the button to everyone.

Randomization unit: **visitor**, assigned in the browser and persisted in localStorage. Metric denominators use the same unit.

## 4. Funnel

Unit: visitor. Every event carries `experiment_variant`.

| Step | Event | What it means |
|---|---|---|
| 1 | search | Visitor submits a school search. GA4 recommended event. |
| 2 | view_search_results | Visitor sees the results list. GA4 recommended event. |
| 3 | compare_add | Visitor adds a school to compare (variant B only). Needs 2 to 4 schools to continue. |
| 4 | compare_view | Visitor opens the side-by-side table (rating, tuition, distance, reviews). Variant B only. |
| 5 | school_profile_view | Visitor opens a school profile, from a card or from the comparison. |
| 6 | generate_lead | Visitor sends "Request info" to a school. GA4 recommended event. Carries boolean param `form_complete` (child's grade and phone both filled). |

Steps 3 and 4 exist only in B. Visitors can reach steps 5 and 6 without them, in both arms, so the funnel is not strictly linear.

## 5. Metrics

One definition per metric, used in the tracking spec, dbt and MetricFlow. All metrics are computed per variant.

| metric_id | type | definition | numerator | denominator | events_needed |
|---|---|---|---|---|---|
| lead_rate | primary | Share of visitors who send at least one info request | Visitors with at least one generate_lead | Visitors with at least one view_search_results | generate_lead, view_search_results |
| profile_view_rate | guardrail | Share of visitors who open at least one school profile. Partners pay for profile visibility and the comparison table could cannibalize it | Visitors with at least one school_profile_view | Visitors with at least one view_search_results | school_profile_view, view_search_results |
| complete_lead_share | guardrail | Share of info requests with the form complete (child's grade and phone filled). Lead quality: side-by-side could produce cold "request all four" leads | generate_lead events with form_complete true | All generate_lead events | generate_lead |
| compare_adoption | secondary | Share of variant B visitors who use Compare (add at least one school). Does not decide the test; helps interpret it | Variant B visitors with at least one compare_add | Variant B visitors with at least one view_search_results | compare_add, view_search_results |

Notes:

- Rates, not counts. Total comparisons or page views are vanity metrics and are not used.
- The denominator for visitor-level metrics is visitors who saw results, so visitors who never reached the feature do not dilute the rate. Assignment still happens at the visitor, and the analysis includes everyone in the assigned arm who reached results.
- `complete_lead_share` is a share of events, not visitors. Its unit differs from the other metrics; the analysis must account for several requests from the same visitor.
- Each `metric_id` must be computable from `tracking/events.yaml` (checked by `tests/test_tracking_spec.py`).

## 6. Decision rule

Alpha 0.05, two-sided. MDE and sample size are decided before launch: see power report (`analysis/power_report.md`).

| Outcome | Condition | Action |
|---|---|---|
| Ship | lead_rate in B is higher than A with statistical significance, AND neither guardrail (profile_view_rate, complete_lead_share) drops significantly | Roll out B to all visitors |
| Do not ship | lead_rate in B is significantly lower, OR any guardrail drops significantly | Keep A; investigate which side lost |
| Inconclusive | lead_rate difference is not significant and no guardrail drops significantly | Do not ship on this evidence; keep A. Decide next step (longer test or redesign) with the owner |

A significant lead_rate gain with a significant guardrail drop is "do not ship": more leads that hurt partners or lead quality are not a win. compare_adoption is read only after the decision, to explain it.

## 7. Known measurement limits

- **Consent and ad blockers** drop GA4 events. Some visitors and events are missing from GA4.
- **GA4 is not the source of truth for counts.** The ground-truth log (the simulator's backend record) is. GA4 is the tool under test, and reconciliation measures the gap.
- **Equal gap in both arms (assumption).** Randomization is independent of consent, so the loss should affect A and B equally and leave the comparison unbiased. This is an assumption to verify, not a fact: it is checked in stage 5 by comparing GA4 against the ground-truth log per variant.
- **Season.** The test runs in a single window with both arms in parallel, so season affects both equally. Do not compare results with other months.
