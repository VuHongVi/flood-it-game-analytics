-- 10_users.sql
-- Purpose : one row per player with acquisition attributes and lifetime bounds.
--           Attributes come from the FIRST observed event of the player
--           (ARRAY_AGG ... ORDER BY event_timestamp LIMIT 1), never ANY_VALUE, and we also
--           count distinct values to prove whether they are constant per user.
-- Grain   : user_id (16-hex MD5 of user_pseudo_id: shorter, no raw IDs in the repo)
-- Params  : @start_suffix, @end_suffix
-- Conventions: "day" = event_date (property time zone). user_first_touch_timestamp is UTC.
WITH ev AS (
  SELECT
    user_pseudo_id, event_date, event_timestamp, event_name, platform,
    geo.country AS country,
    traffic_source.name AS ts_name,
    traffic_source.medium AS ts_medium,
    traffic_source.source AS ts_source,
    user_first_touch_timestamp
  FROM `{{source_table}}`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
),
agg AS (
  SELECT
    user_pseudo_id,
    ARRAY_AGG(STRUCT(platform, country, ts_name, ts_medium, ts_source)
              ORDER BY event_timestamp LIMIT 1)[OFFSET(0)]            AS first_ev,
    COUNT(DISTINCT platform)                                          AS n_platforms,
    COUNT(DISTINCT ts_source)                                         AS n_traffic_sources,
    COUNT(DISTINCT user_first_touch_timestamp)                        AS n_first_touch_values,
    MIN(user_first_touch_timestamp)                                   AS first_touch_ts,
    MIN(IF(event_name = 'first_open', event_date, NULL))              AS first_open_date,
    MIN(event_date)                                                   AS first_seen_date,
    MAX(event_date)                                                   AS last_seen_date,
    COUNT(DISTINCT event_date)                                        AS active_days,
    COUNT(*)                                                          AS events
  FROM ev
  GROUP BY user_pseudo_id
)
SELECT
  SUBSTR(TO_HEX(MD5(user_pseudo_id)), 1, 16)                          AS user_id,
  first_ev.platform                                                   AS platform,
  first_ev.country                                                    AS country,
  first_ev.ts_source                                                  AS traffic_source,
  first_ev.ts_medium                                                  AS traffic_medium,
  first_ev.ts_name                                                    AS traffic_name,
  n_platforms,
  n_traffic_sources,
  n_first_touch_values,
  FORMAT_DATE('%F', DATE(TIMESTAMP_MICROS(first_touch_ts)))           AS first_touch_date_utc,
  FORMAT_DATE('%F', PARSE_DATE('%Y%m%d', first_open_date))            AS first_open_date,
  FORMAT_DATE('%F', PARSE_DATE('%Y%m%d', first_seen_date))            AS first_seen_date,
  FORMAT_DATE('%F', PARSE_DATE('%Y%m%d', last_seen_date))             AS last_seen_date,
  active_days,
  events
FROM agg
