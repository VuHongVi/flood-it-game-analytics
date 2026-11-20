-- 20_daily_activity.sql
-- Purpose : daily growth metrics computed directly from raw events (SQL side of validation).
--           dau              = distinct players with >=1 event on the day
--           installs         = players whose first first_open event falls on the day
--           first_seen_users = players whose first event in the window is on the day
--           wau / mau        = distinct players active in the trailing 7 / 30 days (incl. day)
-- Grain   : activity_date (event_date, property time zone)
-- Params  : @start_suffix, @end_suffix
WITH ud AS (
  SELECT DISTINCT user_pseudo_id, PARSE_DATE('%Y%m%d', event_date) AS d
  FROM `{{source_table}}`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
),
fo AS (
  SELECT user_pseudo_id, MIN(PARSE_DATE('%Y%m%d', event_date)) AS d
  FROM `{{source_table}}`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
    AND event_name = 'first_open'
  GROUP BY user_pseudo_id
),
daily AS (SELECT d, COUNT(*) AS dau FROM ud GROUP BY d),
inst AS (SELECT d, COUNT(*) AS installs FROM fo GROUP BY d),
fs AS (
  SELECT d, COUNT(*) AS first_seen_users
  FROM (SELECT user_pseudo_id, MIN(d) AS d FROM ud GROUP BY user_pseudo_id)
  GROUP BY d
),
rolling AS (
  SELECT
    days.d,
    COUNT(DISTINCT IF(ud.d > DATE_SUB(days.d, INTERVAL 7 DAY), ud.user_pseudo_id, NULL)) AS wau,
    COUNT(DISTINCT ud.user_pseudo_id)                                                    AS mau
  FROM daily AS days
  JOIN ud ON ud.d BETWEEN DATE_SUB(days.d, INTERVAL 29 DAY) AND days.d
  GROUP BY days.d
)
SELECT
  FORMAT_DATE('%F', daily.d)          AS activity_date,
  daily.dau,
  COALESCE(inst.installs, 0)          AS installs,
  COALESCE(fs.first_seen_users, 0)    AS first_seen_users,
  rolling.wau,
  rolling.mau
FROM daily
LEFT JOIN inst USING (d)
LEFT JOIN fs USING (d)
JOIN rolling USING (d)
ORDER BY activity_date
