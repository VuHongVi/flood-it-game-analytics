-- 40_revenue_summary.sql
-- Purpose : period monetisation KPIs in SQL (validation counterpart of analysis/revenue.py).
--   revenue_usd per purchase = event_value_in_usd, falling back to value/1e6 when the
--   currency is USD (event_value_in_usd is NULL for some purchases; `value` is in micros
--   of the local currency, so a non-USD fallback would need an FX table -> not done).
-- Grain   : platform (+ an 'ALL' row)
-- Params  : @start_suffix, @end_suffix
WITH ev AS (
  SELECT
    user_pseudo_id, platform, event_name, event_date,
    IF(event_name = 'in_app_purchase',
       COALESCE(event_value_in_usd,
                IF((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'currency') = 'USD',
                   (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'value') / 1e6,
                   NULL)),
       NULL) AS revenue_usd
  FROM `{{source_table}}`
  WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
),
by_platform AS (
  -- NB: the output alias must differ from the grouped column. With `AS platform`, BigQuery
  -- resolves ROLLUP(platform) to the alias (the COALESCE) and the total row stays NULL.
  SELECT
    COALESCE(ev.platform, 'ALL')                                       AS platform_group,
    COUNT(DISTINCT user_pseudo_id)                                     AS active_users,
    COUNT(DISTINCT CONCAT(user_pseudo_id, event_date))                 AS user_days,
    COUNT(DISTINCT IF(event_name = 'in_app_purchase', user_pseudo_id, NULL)) AS payers,
    COUNTIF(event_name = 'in_app_purchase')                            AS purchases,
    ROUND(SUM(revenue_usd), 6)                                         AS revenue_usd
  FROM ev
  GROUP BY ROLLUP(ev.platform)
)
SELECT platform_group AS platform, active_users, user_days, payers, purchases, revenue_usd
FROM by_platform
ORDER BY platform
