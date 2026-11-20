-- 51_user_level.sql
-- Purpose : player x level progression facts, used for drop-off ("last level started"),
--           difficulty and day-0 features. Also carries quickplay board activity.
-- Grain   : user_id x mode x level_key
--           mode = 'progression' (level_* events, level_key = level number)
--                | 'quickplay'   (level_*_quickplay events, level_key = board size S/M/L)
-- Params  : @start_suffix, @end_suffix
WITH ev AS (
  SELECT
    user_pseudo_id,
    event_date,
    event_timestamp,
    event_name,
    IF(ENDS_WITH(event_name, '_quickplay'), 'quickplay', 'progression') AS mode,
    REGEXP_REPLACE(event_name, '_quickplay$', '')                       AS action,
    COALESCE(
      CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'level') AS STRING),
      CAST(CAST((SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'level') AS INT64) AS STRING),
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'board')
    ) AS level_key
  FROM `{{source_table}}`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
    AND event_name IN ('level_start', 'level_complete', 'level_fail',
                       'level_start_quickplay', 'level_complete_quickplay', 'level_fail_quickplay')
)
SELECT
  SUBSTR(TO_HEX(MD5(user_pseudo_id)), 1, 16)                                AS user_id,
  mode,
  level_key,
  COUNTIF(action = 'level_start')                                           AS starts,
  COUNTIF(action = 'level_complete')                                        AS completes,
  COUNTIF(action = 'level_fail')                                            AS fails,
  FORMAT_DATE('%F', PARSE_DATE('%Y%m%d', MIN(event_date)))                  AS first_date,
  FORMAT_DATE('%F', PARSE_DATE('%Y%m%d', MIN(IF(action = 'level_complete', event_date, NULL)))) AS first_complete_date
FROM ev
GROUP BY user_id, mode, level_key
