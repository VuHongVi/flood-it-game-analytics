-- 00_table_inventory.sql
-- Purpose : list daily export tables in range, event counts and event_date bounds.
-- Grain   : one row per daily table (_TABLE_SUFFIX).
-- Params  : @start_suffix, @end_suffix (YYYYMMDD strings)
-- Columns scanned: event_date only (cheap).
SELECT
  _TABLE_SUFFIX            AS table_suffix,
  MIN(event_date)          AS min_event_date,
  MAX(event_date)          AS max_event_date,
  COUNT(*)                 AS events
FROM `{{source_table}}`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
GROUP BY table_suffix
ORDER BY table_suffix
