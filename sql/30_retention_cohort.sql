-- 30_retention_cohort.sql
-- Purpose : classic Day-N retention by weekly install cohort, fully in SQL.
--   Cohort population : players with a first_open event in the window AND whose
--                       user_first_touch_timestamp is not before the window
--                       (excludes re-installs of players acquired before the data starts).
--   install_date      : event_date of first_open (property time zone, same clock as activity).
--   retained on day N : active on install_date + N (exact day, not "N or later").
--   Right-censoring   : a player is ELIGIBLE for day N only if install_date + N <= last date
--                       of data; retention = retained / eligible (never / all installs).
-- Grain   : cohort_week (ISO week start, Monday) x day_n
-- Params  : @start_suffix, @end_suffix, @day_ns (ARRAY<INT64>)
WITH bounds AS (
  SELECT PARSE_DATE('%Y%m%d', @start_suffix) AS start_d, PARSE_DATE('%Y%m%d', @end_suffix) AS end_d
),
installs AS (
  SELECT
    user_pseudo_id,
    MIN(PARSE_DATE('%Y%m%d', event_date))                          AS install_date,
    MIN(DATE(TIMESTAMP_MICROS(user_first_touch_timestamp)))        AS first_touch_utc
  FROM `{{source_table}}`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
    AND event_name = 'first_open'
  GROUP BY user_pseudo_id
),
cohort AS (
  SELECT i.user_pseudo_id, i.install_date, DATE_TRUNC(i.install_date, ISOWEEK) AS cohort_week
  FROM installs i, bounds b
  WHERE i.first_touch_utc >= b.start_d
),
activity AS (
  SELECT DISTINCT user_pseudo_id, PARSE_DATE('%Y%m%d', event_date) AS d
  FROM `{{source_table}}`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
),
grid AS (
  SELECT c.*, n AS day_n, DATE_ADD(c.install_date, INTERVAL n DAY) AS target_d
  FROM cohort c CROSS JOIN UNNEST(@day_ns) AS n
)
SELECT
  FORMAT_DATE('%F', g.cohort_week)                                AS cohort_week,
  g.day_n,
  COUNT(DISTINCT g.user_pseudo_id)                                AS cohort_users,
  COUNT(DISTINCT IF(g.target_d <= b.end_d, g.user_pseudo_id, NULL))  AS eligible_users,
  COUNT(DISTINCT IF(g.target_d <= b.end_d AND a.user_pseudo_id IS NOT NULL, g.user_pseudo_id, NULL)) AS retained_users
FROM grid g
CROSS JOIN bounds b
LEFT JOIN activity a ON a.user_pseudo_id = g.user_pseudo_id AND a.d = g.target_d
GROUP BY cohort_week, day_n
ORDER BY cohort_week, day_n
