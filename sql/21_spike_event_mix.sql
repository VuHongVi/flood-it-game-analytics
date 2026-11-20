-- 21_spike_event_mix.sql
-- Purpose : explain DAU spikes that are NOT driven by installs: compare the event mix and
--           events-per-user by day and platform around the spike period.
-- Grain   : activity_date x platform x event_name
-- Params  : @spike_start, @spike_end (YYYYMMDD) - a short window around the spikes
SELECT
  FORMAT_DATE('%F', PARSE_DATE('%Y%m%d', event_date)) AS activity_date,
  platform,
  event_name,
  COUNT(*)                       AS events,
  COUNT(DISTINCT user_pseudo_id) AS users
FROM `{{source_table}}`
WHERE _TABLE_SUFFIX BETWEEN @spike_start AND @spike_end
GROUP BY activity_date, platform, event_name
ORDER BY activity_date, platform, events DESC
