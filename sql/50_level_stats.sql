-- 50_level_stats.sql
-- Purpose : progression-mode level funnel straight from events (SQL side of validation).
--           level = COALESCE(int_value, CAST(double_value AS INT64)) because the export stores
--           the same param in either slot depending on app version.
-- Grain   : level
-- Params  : @start_suffix, @end_suffix
WITH lv AS (
  SELECT
    user_pseudo_id,
    event_name,
    COALESCE(
      (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'level'),
      CAST((SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'level') AS INT64)
    ) AS level
  FROM `{{source_table}}`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
    AND event_name IN ('level_start', 'level_complete', 'level_fail', 'level_retry', 'level_reset')
)
SELECT
  level,
  COUNTIF(event_name = 'level_start')                                   AS starts,
  COUNTIF(event_name = 'level_complete')                                AS completes,
  COUNTIF(event_name = 'level_fail')                                    AS fails,
  COUNTIF(event_name = 'level_retry')                                   AS retries,
  COUNTIF(event_name = 'level_reset')                                   AS resets,
  COUNT(DISTINCT IF(event_name = 'level_start', user_pseudo_id, NULL))     AS users_started,
  COUNT(DISTINCT IF(event_name = 'level_complete', user_pseudo_id, NULL))  AS users_completed,
  COUNT(DISTINCT IF(event_name = 'level_fail', user_pseudo_id, NULL))      AS users_failed
FROM lv
GROUP BY level
ORDER BY level
