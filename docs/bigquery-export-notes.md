# BigQuery export notes (stage 4)

Answers to the three export questions of the stage 4 spec (section 7), with the query results.
The project and dataset names stay out of git: they live in `.env` as `BQ_PROJECT` and `BQ_DATASET`.
Queries in `warehouse/bigquery/` use the placeholder `` `PROJECT.DATASET.events_*` ``.

## Setup

- 2026-11-06: Google Cloud project created in BigQuery sandbox mode (no billing account). Sandbox tables expire after 60 days.
- 2026-11-06: GA4 property linked to BigQuery. Events export **daily** only; streaming off (needs billing); user-data export off; advertising identifiers off; no events excluded; data location US.
- Internal traffic rules (tag settings): none defined, so no hit is marked internal.
- Data filters: "Internal Traffic" (exclude) in **Testing** state, which only labels hits. No developer-traffic filter exists; the simulator never turns debug mode on.
- GA4 showed "data collection is not active" on the web stream on the link date: the site had almost no real traffic (live tests abort every hit, stage 3 QA ran in debug mode). The pilot checks Realtime.
