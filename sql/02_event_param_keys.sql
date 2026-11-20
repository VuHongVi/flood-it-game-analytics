-- 02_event_param_keys.sql
-- Purpose : which keys each event carries in the event_params ARRAY<STRUCT<key, value>>
--           and in which typed slot (string/int/float/double) the value is stored.
--           Detects mixed-type params (e.g. `level` stored as int_value AND double_value).
-- Grain   : event_name x param key
-- Params  : @start_suffix, @end_suffix
SELECT
  e.event_name,
  p.key,
  COUNT(*)                                   AS n,
  COUNTIF(p.value.string_value IS NOT NULL)  AS n_string,
  COUNTIF(p.value.int_value    IS NOT NULL)  AS n_int,
  COUNTIF(p.value.float_value  IS NOT NULL)  AS n_float,
  COUNTIF(p.value.double_value IS NOT NULL)  AS n_double
FROM `{{source_table}}` AS e,
     UNNEST(e.event_params) AS p
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
GROUP BY e.event_name, p.key
ORDER BY e.event_name, n DESC
