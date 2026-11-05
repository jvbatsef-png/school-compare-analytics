# Tracking spec

Generated from `tracking/events.yaml` by `tracking/spec.py`. Do not edit by hand.

## Consent defaults

- `analytics_storage`: denied
- `ad_storage`: denied
- `ad_user_data`: denied
- `ad_personalization`: denied

## dataLayer contract

```js
// One push per event. Names and param keys must match this spec exactly. No personal data.
window.dataLayer.push({
  event: "compare_add",
  experiment_variant: "B",
  school_id: "sch_042",
  list_position: 3,
  compare_count: 2
});
```

## `search`

**Fires when:** Fires once when the visitor submits a school search; it must not fire again on re-render or when the same results page reloads.
**Funnel step:** yes

| parameter | type | required | example |
|---|---|---|---|
| experiment_variant | string | yes | B |
| search_term | string | no | montessori |
| school_level | string | no | elementary |
| location | string | no | Austin, TX |

## `view_search_results`

**Fires when:** Fires once per results list shown after a search; it must not fire again when the visitor scrolls, filters in place or returns by back button without a new search.
**Funnel step:** yes

| parameter | type | required | example |
|---|---|---|---|
| experiment_variant | string | yes | B |
| search_term | string | no | montessori |
| results_count | int | yes | 24 |

## `compare_add`

**Fires when:** Fires each time the visitor adds a school to the compare tray (variant B only); it must not fire when a school is removed or when the add is rejected because the tray is full.
**Funnel step:** yes

| parameter | type | required | example |
|---|---|---|---|
| experiment_variant | string | yes | B |
| school_id | string | yes | sch_042 |
| list_position | int | yes | 3 |
| compare_count | int | yes | 2 |

## `compare_view`

**Fires when:** Fires once each time the side-by-side table opens (variant B only); it must not fire again on re-render or when the visitor only changes tray contents while it is open.
**Funnel step:** yes

| parameter | type | required | example |
|---|---|---|---|
| experiment_variant | string | yes | B |
| compare_count | int | yes | 3 |
| school_ids | string | yes | sch_042,sch_077,sch_103 |

## `school_profile_view`

**Fires when:** Fires once when a school profile page is shown, from a card, from the comparison or by direct link; it must not fire again on tab switches within the same profile.
**Funnel step:** yes

| parameter | type | required | example |
|---|---|---|---|
| experiment_variant | string | yes | A |
| school_id | string | yes | sch_042 |
| source | string | yes | results |

## `generate_lead`

**Fires when:** Fires once per "Request info" form that is successfully submitted to a school; it must not fire on failed submissions or on double clicks of the same submit.
**Funnel step:** yes

| parameter | type | required | example |
|---|---|---|---|
| experiment_variant | string | yes | B |
| school_id | string | yes | sch_042 |
| source | string | yes | compare |
| form_complete | bool | yes | True |
| lead_type | string | no | info_request |

## `consent_update`

**Fires when:** Fires once each time the visitor saves a choice in the consent banner, after Consent Mode is updated.
**Funnel step:** no

| parameter | type | required | example |
|---|---|---|---|
| analytics_storage | string | yes | granted |
| ad_storage | string | yes | denied |
