-- Stage 4, export question 2: identity of cookieless (analytics_storage = 'No') traffic.
-- Replace PROJECT.DATASET with BQ_PROJECT and BQ_DATASET from .env, and the dates with the run days.
-- Compare denied_distinct_ids with cookieless_visitors from
-- `uv run python -m simulator.check_run simulator/runs/real_run.jsonl --expected 500`.
-- Each simulated visitor has one session, so the run can show one ID per session,
-- not one visitor split across sessions.
WITH events AS (
  SELECT
    user_pseudo_id,
    privacy_info.analytics_storage AS analytics_storage,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id
  FROM `PROJECT.DATASET.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20261107' AND '20261107'
),
denied AS (
  SELECT user_pseudo_id, COUNT(DISTINCT ga_session_id) AS sessions
  FROM events
  WHERE analytics_storage = 'No' AND user_pseudo_id IS NOT NULL
  GROUP BY user_pseudo_id
)
SELECT
  (SELECT COUNTIF(user_pseudo_id IS NULL) FROM events) AS null_user_pseudo_id_events,
  (SELECT COUNTIF(analytics_storage = 'No') FROM events) AS denied_events,
  (SELECT COUNT(*) FROM denied) AS denied_distinct_ids,
  (SELECT COUNT(DISTINCT TO_JSON_STRING(STRUCT(user_pseudo_id, ga_session_id)))
     FROM events WHERE analytics_storage = 'No') AS denied_distinct_id_sessions,
  (SELECT COUNTIF(sessions > 1) FROM denied) AS denied_ids_spanning_sessions
