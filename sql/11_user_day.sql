-- 11_user_day.sql
-- Purpose : player x day activity table - base for DAU/WAU/MAU, retention, monetisation
--           and day-0 behavioural features (the Pandas side of the SQL-vs-Pandas validation).
-- Grain   : user_id x activity_date (event_date, property time zone)
-- Params  : @start_suffix, @end_suffix
-- Notes   : `level` is stored in int_value OR double_value -> COALESCE of both.
--           engagement_time_msec comes from user_engagement events (int_value).
--           event_value_in_usd is (almost) always NULL in this export, so IAP fields are
--           extracted separately in 12_iap.sql.
SELECT
  SUBSTR(TO_HEX(MD5(user_pseudo_id)), 1, 16)                          AS user_id,
  FORMAT_DATE('%F', PARSE_DATE('%Y%m%d', event_date))                 AS activity_date,
  COUNT(*)                                                            AS events,
  COUNTIF(event_name = 'session_start')                               AS sessions,
  SUM(IF(event_name = 'user_engagement',
         (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec'),
         0))                                                          AS engagement_msec,
  COUNTIF(event_name = 'level_start')                                 AS level_starts,
  COUNTIF(event_name = 'level_complete')                              AS level_completes,
  COUNTIF(event_name = 'level_fail')                                  AS level_fails,
  COUNTIF(event_name = 'level_start_quickplay')                       AS quickplay_starts,
  COUNTIF(event_name = 'level_complete_quickplay')                    AS quickplay_completes,
  COUNTIF(event_name = 'level_fail_quickplay')                        AS quickplay_fails,
  MAX(IF(event_name IN ('level_start', 'level_complete', 'level_up'),
         COALESCE(
           (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'level'),
           CAST((SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'level') AS INT64)),
         NULL))                                                       AS max_level,
  COUNTIF(event_name = 'post_score')                                  AS post_scores,
  COUNTIF(event_name = 'ad_reward')                                   AS ad_rewards,
  COUNTIF(event_name = 'spend_virtual_currency')                      AS virtual_spends,
  COUNTIF(event_name = 'in_app_purchase')                             AS iap_events,
  COUNTIF(event_name = 'app_exception')                               AS app_exceptions
FROM `{{source_table}}`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
GROUP BY user_id, activity_date
