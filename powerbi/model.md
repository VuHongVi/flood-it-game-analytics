# Power BI data model

Source: CSV files in `powerbi/data/` produced by `python -m flood_it run`. Load each with **Get data -> Web** using the raw link (public repo, no sign-in), or from the local folder. Dates are ISO `YYYY-MM-DD`; set the column type to Date with locale en-US. Booleans are 0/1 whole numbers.

## Relationships (single direction, one-to-many)

| From (one) | To (many) | Active |
|---|---|---|
| `dim_date[date]` | `fact_daily_activity[date]` | yes |
| `dim_date[date]` | `fact_iap_transactions[purchase_date]` | yes |
| `dim_platform[platform]` | `fact_monetization_platform[platform]` | yes |
| `dim_platform[platform]` | `fact_retention_platform[platform]` | yes |
| `dim_platform[platform]` | `fact_iap_transactions[platform]` | yes |

All other tables are standalone (each visual uses one table), so no ambiguous paths. Mark `dim_date` as the date table.

## Tables

### fact_daily_activity

- Grain: **one row per event_date** (114 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_daily_activity.csv

| Column | Type | Description |
|---|---|---|
| `date` | Date | event_date (property time zone) |
| `dau` | Whole number | distinct players active |
| `installs` | Whole number | players whose first_open is on the day |
| `first_seen_users` | Whole number | players first seen in the window on the day (left-censored) |
| `returning_dau` | Whole number | dau - first_seen_users |
| `wau` | Whole number | distinct players in trailing 7 days |
| `mau` | Whole number | distinct players in trailing 30 days |
| `events` | Whole number | events in sample (always 50,000) |
| `events_per_dau` | Decimal number |  |
| `is_spike_day` | Whole number | 1 = DAU > 1.5x period median (tracking/sampling artefact) |
| `full_7d_window` | Whole number |  |
| `full_30d_window` | Whole number |  |
| `clean_stickiness_window` | Whole number | 1 = full 30-day window with no spike day |
| `stickiness` | Decimal number | dau / mau when full_30d_window |

### dim_date

- Grain: **one row per date in the window** (114 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/dim_date.csv

| Column | Type | Description |
|---|---|---|
| `date` | Date |  |
| `year` | Whole number |  |
| `month_number` | Whole number |  |
| `month` | Text |  |
| `week_start` | Text | ISO week start (Monday) |
| `day_of_week` | Text |  |
| `is_spike_day` | Whole number |  |

### dim_platform

- Grain: **one row per platform** (2 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/dim_platform.csv

| Column | Type | Description |
|---|---|---|
| `platform` | Text |  |

### fact_retention_cohort

- Grain: **cohort_week x day_n (1,3,7,14,30)** (85 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_retention_cohort.csv

| Column | Type | Description |
|---|---|---|
| `cohort_week` | Date | ISO week (Monday) of install_date |
| `day_n` | Whole number |  |
| `cohort_users` | Whole number |  |
| `eligible_users` | Whole number | installs with install_date + day_n <= 2018-10-03 |
| `retained_users` | Whole number | eligible installs active on install_date + day_n |
| `retention` | Decimal number | retained_users / eligible_users (reference only; use the measure) |

### fact_retention_curve

- Grain: **day_n 0..30, all cohorts pooled** (31 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_retention_curve.csv

| Column | Type | Description |
|---|---|---|
| `day_n` | Whole number |  |
| `cohort_users` | Whole number |  |
| `eligible_users` | Whole number |  |
| `retained_users` | Whole number |  |
| `retention` | Decimal number |  |
| `ci_low` | Decimal number | Wilson 95% lower bound |
| `ci_high` | Decimal number | Wilson 95% upper bound |

### fact_retention_platform

- Grain: **platform x day_n** (10 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_retention_platform.csv

| Column | Type | Description |
|---|---|---|
| `platform` | Text |  |
| `day_n` | Whole number |  |
| `cohort_users` | Whole number |  |
| `eligible_users` | Whole number |  |
| `retained_users` | Whole number |  |
| `retention` | Decimal number |  |

### fact_monetization_platform

- Grain: **one row per platform (additive: a player has one platform)** (2 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_monetization_platform.csv

| Column | Type | Description |
|---|---|---|
| `platform` | Text |  |
| `active_users` | Whole number |  |
| `user_days` | Whole number | player x day pairs (= sum of daily DAU) |
| `payers` | Whole number |  |
| `purchases` | Whole number |  |
| `revenue_usd` | Decimal number | IAP revenue, USD |

### fact_iap_transactions

- Grain: **one row per in_app_purchase event** (27 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_iap_transactions.csv

| Column | Type | Description |
|---|---|---|
| `purchase_date` | Date |  |
| `user_id` | Text | MD5-truncated user_pseudo_id |
| `platform` | Text |  |
| `product_id` | Text |  |
| `currency` | Text |  |
| `local_value_micros` | Whole number | value param, local currency x 1e6 |
| `event_value_in_usd` | Decimal number |  |
| `revenue_usd` | Decimal number |  |
| `revenue_source` | Text | event_value_in_usd or value_param_usd fallback |

### fact_ltv_curve

- Grain: **day_n 0..30, fixed population (installs observable 30 days)** (31 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_ltv_curve.csv

| Column | Type | Description |
|---|---|---|
| `day_n` | Whole number |  |
| `eligible_users` | Whole number |  |
| `payers` | Whole number |  |
| `revenue_usd` | Decimal number |  |
| `ltv_usd` | Decimal number | revenue_usd / eligible_users |

### fact_level_funnel

- Grain: **one row per progression level 1..30** (30 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_level_funnel.csv

| Column | Type | Description |
|---|---|---|
| `level` | Whole number |  |
| `starts` | Whole number |  |
| `completes` | Whole number |  |
| `fails` | Whole number |  |
| `users_started` | Whole number |  |
| `users_completed` | Whole number |  |
| `users_failed` | Whole number |  |
| `new_players_started` | Whole number | cohort (new) players who started the level |
| `new_players_last_level` | Whole number | cohort players whose highest level started is this one |
| `reach_rate` | Decimal number |  |
| `completion_per_attempt` | Decimal number |  |
| `quit_rate_at_level` | Decimal number | blank for level 30 (last level = finished) |

### fact_quickplay_boards

- Grain: **one row per quickplay board size** (3 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_quickplay_boards.csv

| Column | Type | Description |
|---|---|---|
| `board` | Text |  |
| `starts` | Whole number |  |
| `completes` | Whole number |  |
| `fails` | Whole number |  |
| `players` | Whole number |  |
| `completion_per_attempt` | Decimal number |  |
| `fail_per_attempt` | Decimal number |  |

### fact_level_anomalies

- Grain: **one row per invalid level value** (3 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_level_anomalies.csv

| Column | Type | Description |
|---|---|---|
| `level` | Decimal number |  |
| `starts` | Whole number |  |
| `completes` | Whole number |  |
| `fails` | Whole number |  |
| `retries` | Whole number |  |
| `resets` | Whole number |  |
| `users_started` | Whole number |  |
| `users_completed` | Whole number |  |
| `users_failed` | Whole number |  |

### fact_day0_segments

- Grain: **dimension x segment (install-day behaviour)** (18 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_day0_segments.csv

| Column | Type | Description |
|---|---|---|
| `dimension` | Text |  |
| `segment` | Text |  |
| `segment_order` | Whole number | sort order within dimension |
| `players` | Whole number |  |
| `d1_eligible` | Whole number |  |
| `d1_retained` | Whole number |  |
| `d1_retention` | Decimal number |  |
| `d7_eligible` | Whole number |  |
| `d7_retained` | Whole number |  |
| `d7_retention` | Decimal number |  |
| `churn_eligible` | Whole number |  |
| `churned` | Whole number |  |
| `churn_rate` | Decimal number |  |

### fact_payer_profile

- Grain: **payer vs non-payer** (2 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_payer_profile.csv

| Column | Type | Description |
|---|---|---|
| `segment` | Text |  |
| `players` | Whole number |  |
| `median_active_days` | Whole number |  |
| `median_sessions` | Whole number |  |
| `median_engagement_min` | Decimal number |  |
| `median_level_starts` | Whole number |  |
| `median_quickplay_starts` | Whole number |  |
| `share_watched_rewarded_ad` | Decimal number |  |

### fact_churn_model_performance

- Grain: **one row per model** (2 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_churn_model_performance.csv

| Column | Type | Description |
|---|---|---|
| `model` | Text |  |
| `cv_auc_mean` | Decimal number |  |
| `cv_auc_std` | Decimal number |  |
| `test_auc` | Decimal number |  |
| `train_n` | Whole number |  |
| `test_n` | Whole number |  |
| `test_churn_rate` | Decimal number |  |

### fact_churn_feature_importance

- Grain: **model x feature** (34 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_churn_feature_importance.csv

| Column | Type | Description |
|---|---|---|
| `model` | Text |  |
| `feature` | Text |  |
| `permutation_auc_drop` | Decimal number |  |
| `permutation_auc_drop_std` | Decimal number |  |
| `std_coefficient` | Decimal number |  |
| `gini_importance` | Decimal number |  |

### fact_churn_roc

- Grain: **model x fpr grid point** (102 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_churn_roc.csv

| Column | Type | Description |
|---|---|---|
| `model` | Text |  |
| `fpr` | Decimal number |  |
| `tpr` | Decimal number |  |

### fact_churn_risk_deciles

- Grain: **risk decile (logistic regression, test set)** (10 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_churn_risk_deciles.csv

| Column | Type | Description |
|---|---|---|
| `risk_decile` | Whole number |  |
| `players` | Whole number |  |
| `churned` | Whole number |  |
| `churn_rate` | Decimal number |  |
| `avg_predicted` | Decimal number |  |

### fact_ab_observational_tests

- Grain: **comparison x metric** (4 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_ab_observational_tests.csv

| Column | Type | Description |
|---|---|---|
| `comparison` | Text |  |
| `metric` | Text |  |
| `group_a` | Text |  |
| `group_b` | Text |  |
| `n_a` | Whole number |  |
| `x_a` | Whole number |  |
| `rate_a` | Decimal number |  |
| `n_b` | Whole number |  |
| `x_b` | Whole number |  |
| `rate_b` | Decimal number |  |
| `diff_a_minus_b` | Decimal number |  |
| `diff_ci_low` | Decimal number |  |
| `diff_ci_high` | Decimal number |  |
| `z` | Decimal number |  |
| `p_value` | Decimal number |  |
| `chi2` | Decimal number |  |
| `chi2_p_value` | Decimal number |  |
| `cohens_h` | Decimal number |  |
| `relative_lift` | Decimal number |  |
| `note` | Text |  |

### fact_ab_power_analysis

- Grain: **one row per minimum detectable effect** (4 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_ab_power_analysis.csv

| Column | Type | Description |
|---|---|---|
| `metric` | Text |  |
| `baseline` | Decimal number |  |
| `mde_abs` | Decimal number |  |
| `mde_relative` | Decimal number |  |
| `alpha` | Decimal number |  |
| `power` | Decimal number |  |
| `n_per_arm` | Whole number |  |
| `total_n` | Whole number |  |
| `sample_installs_per_day` | Decimal number |  |
| `days_needed_at_sample_volume` | Whole number |  |
| `days_needed_incl_d1_lag` | Whole number |  |

### fact_event_catalog

- Grain: **one row per event_name** (37 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_event_catalog.csv

| Column | Type | Description |
|---|---|---|
| `event_name` | Text |  |
| `events_android` | Whole number |  |
| `events_ios` | Whole number |  |
| `users_android` | Whole number |  |
| `users_ios` | Whole number |  |
| `events_total` | Whole number |  |
| `share_of_events` | Decimal number |  |
| `platform_coverage` | Text |  |

### fact_user_acquisition_segments

- Grain: **one row per acquisition segment** (4 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_user_acquisition_segments.csv

| Column | Type | Description |
|---|---|---|
| `segment` | Text |  |
| `users` | Whole number |  |
| `share` | Decimal number |  |

### fact_traffic_source_platform

- Grain: **platform x traffic_source** (12 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_traffic_source_platform.csv

| Column | Type | Description |
|---|---|---|
| `platform` | Text |  |
| `traffic_source` | Text |  |
| `users` | Whole number |  |

### fact_spike_event_mix

- Grain: **one row per event_name** (36 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_spike_event_mix.csv

| Column | Type | Description |
|---|---|---|
| `event_name` | Text |  |
| `avg_events_normal_day` | Decimal number |  |
| `avg_events_spike_day` | Decimal number |  |
| `ratio_spike_vs_normal` | Decimal number |  |

### kpi_metrics

- Grain: **one row per scalar in results/metrics.json** (276 rows)
- Raw CSV: https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/kpi_metrics.csv

| Column | Type | Description |
|---|---|---|
| `section` | Text |  |
| `metric_key` | Text | dotted path in metrics.json (lists flattened with .0, .1, ...) |
| `value` | Decimal number | numeric value |
| `value_text` | Text | text form |
