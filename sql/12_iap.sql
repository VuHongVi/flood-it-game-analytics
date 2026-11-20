-- 12_iap.sql
-- Purpose : every in_app_purchase event with all revenue fields side by side, to check
--           event_value_in_usd against the value / price / currency params and user_ltv.
-- Grain   : one in_app_purchase event (only a few dozen exist in the sample)
-- Params  : @start_suffix, @end_suffix
SELECT
  SUBSTR(TO_HEX(MD5(user_pseudo_id)), 1, 16)                                     AS user_id,
  FORMAT_DATE('%F', PARSE_DATE('%Y%m%d', event_date))                            AS activity_date,
  platform,
  event_value_in_usd,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'currency')   AS currency,
  (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'value')      AS value_param,
  (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'price')      AS price_param,
  (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'quantity')   AS quantity,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'product_id') AS product_id,
  (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'validated')  AS validated,
  user_ltv.revenue                                                               AS user_ltv_revenue,
  user_ltv.currency                                                              AS user_ltv_currency
FROM `{{source_table}}`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
  AND event_name = 'in_app_purchase'
ORDER BY activity_date, user_id
