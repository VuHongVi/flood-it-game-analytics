-- 01_event_counts.sql
-- Purpose : event catalogue - volume and reach of every event_name, split by platform.
-- Grain   : event_name x platform
-- Params  : @start_suffix, @end_suffix
SELECT
  event_name,
  platform,
  COUNT(*)                       AS events,
  COUNT(DISTINCT user_pseudo_id) AS users,
  MIN(event_date)                AS first_date,
  MAX(event_date)                AS last_date
FROM `{{source_table}}`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
GROUP BY event_name, platform
ORDER BY events DESC
