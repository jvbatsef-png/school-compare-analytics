-- Stage 4, export question 1: what arrived, by event and consent state.
-- Replace PROJECT.DATASET with BQ_PROJECT and BQ_DATASET from .env, and the dates with the run days
-- (GA4 property time zone). analytics_storage: 'Yes' granted, 'No' denied (cookieless pings), NULL unknown.
SELECT
  event_name,
  privacy_info.analytics_storage AS analytics_storage,
  COUNT(*) AS events,
  COUNT(DISTINCT user_pseudo_id) AS distinct_user_pseudo_ids
FROM `PROJECT.DATASET.events_*`
WHERE _TABLE_SUFFIX BETWEEN '20261107' AND '20261107'
GROUP BY event_name, analytics_storage
ORDER BY event_name, analytics_storage
