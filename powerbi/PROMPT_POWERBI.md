# Prompt: rebuild the Flood-It report in Power BI (via Power BI MCP)

Copy everything below the line into Claude on the machine where Power BI Desktop and the Power BI MCP server run.

---

You are building a Power BI report that must match an existing analytics dashboard **100%**. Work through the Power BI
MCP tools; do not invent numbers or measures.

**Inputs (public GitHub repo https://github.com/VuHongVi/flood-it-game-analytics):**
- Data model spec: https://github.com/VuHongVi/flood-it-game-analytics/blob/main/powerbi/model.md
- DAX measures: https://github.com/VuHongVi/flood-it-game-analytics/blob/main/powerbi/measures.dax
- Page layout, titles and insight text: https://github.com/VuHongVi/flood-it-game-analytics/blob/main/powerbi/layout.md
- Expected values: https://github.com/VuHongVi/flood-it-game-analytics/blob/main/powerbi/reconciliation.csv

**CSV tables (load each with Web connector, no authentication):**
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_daily_activity.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/dim_date.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/dim_platform.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_retention_cohort.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_retention_curve.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_retention_platform.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_monetization_platform.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_iap_transactions.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_ltv_curve.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_level_funnel.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_quickplay_boards.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_level_anomalies.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_day0_segments.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_payer_profile.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_churn_model_performance.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_churn_feature_importance.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_churn_roc.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_churn_risk_deciles.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_ab_observational_tests.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_ab_power_analysis.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_event_catalog.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_user_acquisition_segments.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_traffic_source_platform.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/fact_spike_event_mix.csv
- https://raw.githubusercontent.com/VuHongVi/flood-it-game-analytics/main/powerbi/data/kpi_metrics.csv

**Steps**
1. Create a new report. Load every CSV above as a table with the same name. Set column types exactly as in model.md
   (dates as Date, en-US locale; 0/1 flags as Whole number).
2. Create the relationships listed in model.md (single direction, one-to-many). Mark `dim_date` as the date table.
3. Create a `_Measures` table and add every measure from measures.dax verbatim, with the formats: percentages 0.0%
   (payer rate 0.00%), currency $0.00 (ARPU/ARPDAU/LTV $0.0000), counts #,0.
4. Build the pages and visuals exactly as layout.md describes: one page per section, same order, same titles,
   definitions, insight sentences (verbatim) and source lines; colours from the theme line in layout.md.
5. Reconcile: for every row of reconciliation.csv evaluate `measure_or_field` under `filter_context` (DAX query via MCP,
   e.g. `EVALUATE ROW("v", CALCULATE([Retention D1]))`) and compare with `expected_value` within `tolerance`.
   Produce a table check_id | measure | expected | actual | abs diff | PASS/FAIL.
6. If any check FAILS: do not edit expected values. Find the cause (column type, relationship, filter, measure typo),
   fix it, and re-run all checks until every row PASSES. Report what you changed.
7. Finish with: number of pages, visuals, measures, and the final reconciliation table.

Rules: never hard-code a number in a visual or measure (except the filter constants already in measures.dax);
every number on a page must come from a measure or a column of these tables.
