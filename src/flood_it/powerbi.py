"""Power BI handover package (export stage).

Writes powerbi/data/*.csv (tidy, ISO dates, snake_case, one grain per table), model.md,
measures.dax, layout.md, reconciliation.csv and PROMPT_POWERBI.md. Every expected value in
reconciliation.csv is read from results/metrics.json, and layout.md reuses narrative.py, so the
Power BI report and the Claude dashboard share titles, insights and numbers.
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from . import narrative as N
from .analysis.io import read_metrics

log = logging.getLogger(__name__)

TABLES: dict[str, dict] = {}  # name -> {grain, columns: {col: (type, description)}}


def _write(df: pd.DataFrame, name: str, grain: str, desc: dict[str, str], out) -> None:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == bool:
            df[c] = df[c].astype(int)
    df.to_csv(out / f"{name}.csv", index=False, lineterminator="\n", float_format="%.10g")
    types = {}
    for c in df.columns:
        if c in ("date", "cohort_week", "purchase_date") or c.endswith("_date") and df[c].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$").all():
            types[c] = "Date"
        elif pd.api.types.is_integer_dtype(df[c]):
            types[c] = "Whole number"
        elif pd.api.types.is_float_dtype(df[c]):
            types[c] = "Decimal number"
        else:
            types[c] = "Text"
    TABLES[name] = {"grain": grain, "rows": len(df), "columns": {c: (types[c], desc.get(c, "")) for c in df.columns}}


def build(ctx: dict) -> None:
    cfg = ctx["cfg"]
    d = cfg.path("data_dir")
    out = cfg.path("powerbi_dir") / "data"
    out.mkdir(parents=True, exist_ok=True)
    rd = lambda n: pd.read_csv(d / f"{n}.csv")  # noqa: E731
    m = read_metrics()
    flat = N.flatten({k: v for k, v in m.items() if k != "meta"})
    TABLES.clear()

    g = rd("p2_daily_growth").rename(columns={"activity_date": "date", "is_spike": "is_spike_day"})
    last_spike = pd.to_datetime(g.loc[g.is_spike_day, "date"]).max()
    g["clean_stickiness_window"] = (g["full_30d_window"] &
                                    (pd.to_datetime(g["date"]) > last_spike + pd.Timedelta(days=29)))
    g = g[["date", "dau", "installs", "first_seen_users", "returning_dau", "wau", "mau", "events",
           "events_per_dau", "is_spike_day", "full_7d_window", "full_30d_window", "clean_stickiness_window", "stickiness"]]
    _write(g, "fact_daily_activity", "one row per event_date", {
        "date": "event_date (property time zone)", "dau": "distinct players active", "installs": "players whose first_open is on the day",
        "first_seen_users": "players first seen in the window on the day (left-censored)", "returning_dau": "dau - first_seen_users",
        "wau": "distinct players in trailing 7 days", "mau": "distinct players in trailing 30 days", "events": "events in sample (always 50,000)",
        "is_spike_day": "1 = DAU > 1.5x period median (tracking/sampling artefact)",
        "clean_stickiness_window": "1 = full 30-day window with no spike day", "stickiness": "dau / mau when full_30d_window"}, out)

    dates = pd.to_datetime(g["date"])
    dim = pd.DataFrame({"date": g["date"], "year": dates.dt.year, "month_number": dates.dt.month,
                        "month": dates.dt.strftime("%Y-%m"), "week_start": (dates - pd.to_timedelta(dates.dt.day_of_week, unit="D")).dt.strftime("%Y-%m-%d"),
                        "day_of_week": dates.dt.day_name(), "is_spike_day": g["is_spike_day"]})
    _write(dim, "dim_date", "one row per date in the window", {"week_start": "ISO week start (Monday)"}, out)

    plat = pd.DataFrame({"platform": ["ANDROID", "IOS"]})
    _write(plat, "dim_platform", "one row per platform", {}, out)

    r = rd("p3_retention_by_cohort_week")[["cohort_week", "day_n", "cohort_users", "eligible_users", "retained_users", "retention"]]
    _write(r, "fact_retention_cohort", "cohort_week x day_n (1,3,7,14,30)", {
        "cohort_week": "ISO week (Monday) of install_date", "eligible_users": "installs with install_date + day_n <= 2018-10-03",
        "retained_users": "eligible installs active on install_date + day_n", "retention": "retained_users / eligible_users (reference only; use the measure)"}, out)
    c = rd("p3_retention_curve")[["day_n", "cohort_users", "eligible_users", "retained_users", "retention", "ci_low", "ci_high"]]
    _write(c, "fact_retention_curve", "day_n 0..30, all cohorts pooled", {"ci_low": "Wilson 95% lower bound", "ci_high": "Wilson 95% upper bound"}, out)
    rp = rd("p3_retention_by_platform")[["platform", "day_n", "cohort_users", "eligible_users", "retained_users", "retention"]]
    _write(rp, "fact_retention_platform", "platform x day_n", {}, out)

    k = rd("p4_monetization_kpis")
    k = k[k.platform != "ALL"][["platform", "active_users", "user_days", "payers", "purchases", "revenue_usd"]]
    _write(k, "fact_monetization_platform", "one row per platform (additive: a player has one platform)", {
        "user_days": "player x day pairs (= sum of daily DAU)", "revenue_usd": "IAP revenue, USD"}, out)
    t = rd("p4_iap_transactions").rename(columns={"activity_date": "purchase_date", "value_param": "local_value_micros"})
    t = t[["purchase_date", "user_id", "platform", "product_id", "currency", "local_value_micros", "event_value_in_usd", "revenue_usd", "revenue_source"]]
    _write(t, "fact_iap_transactions", "one row per in_app_purchase event", {
        "user_id": "MD5-truncated user_pseudo_id", "local_value_micros": "value param, local currency x 1e6",
        "revenue_source": "event_value_in_usd or value_param_usd fallback"}, out)
    lt = rd("p4_ltv_curve")[["day_n", "eligible_users", "payers", "revenue_usd", "ltv_usd"]]
    _write(lt, "fact_ltv_curve", "day_n 0..30, fixed population (installs observable 30 days)", {"ltv_usd": "revenue_usd / eligible_users"}, out)

    lv = rd("p5_level_funnel")[["level", "starts", "completes", "fails", "users_started", "users_completed", "users_failed",
                                "new_players_started", "new_players_last_level", "reach_rate", "completion_per_attempt", "quit_rate_at_level"]]
    _write(lv, "fact_level_funnel", "one row per progression level 1..30", {
        "new_players_started": "cohort (new) players who started the level", "new_players_last_level": "cohort players whose highest level started is this one",
        "quit_rate_at_level": "blank for level 30 (last level = finished)"}, out)
    q = rd("p5_quickplay_boards")
    _write(q, "fact_quickplay_boards", "one row per quickplay board size", {}, out)
    an = rd("p5_level_anomalies")
    _write(an, "fact_level_anomalies", "one row per invalid level value", {}, out)

    sg = rd("p6_day0_segments")
    _write(sg, "fact_day0_segments", "dimension x segment (install-day behaviour)", {"segment_order": "sort order within dimension"}, out)
    pv = rd("p6_payer_vs_nonpayer")
    _write(pv, "fact_payer_profile", "payer vs non-payer", {}, out)

    _write(rd("p7_model_performance"), "fact_churn_model_performance", "one row per model", {}, out)
    _write(rd("p7_feature_importance"), "fact_churn_feature_importance", "model x feature", {}, out)
    _write(rd("p7_roc_curve"), "fact_churn_roc", "model x fpr grid point", {}, out)
    _write(rd("p7_risk_deciles"), "fact_churn_risk_deciles", "risk decile (logistic regression, test set)", {}, out)
    _write(rd("p8_observational_tests"), "fact_ab_observational_tests", "comparison x metric", {}, out)
    _write(rd("p8_power_analysis"), "fact_ab_power_analysis", "one row per minimum detectable effect", {}, out)

    _write(rd("p1_event_catalog"), "fact_event_catalog", "one row per event_name", {}, out)
    _write(rd("p1_user_segments"), "fact_user_acquisition_segments", "one row per acquisition segment", {}, out)
    _write(rd("p1_traffic_source_by_platform"), "fact_traffic_source_platform", "platform x traffic_source", {}, out)
    _write(rd("p2_spike_event_mix"), "fact_spike_event_mix", "one row per event_name", {}, out)

    kp = pd.DataFrame([{"section": k.split(".")[0], "metric_key": k,
                        "value": float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else np.nan,
                        "value_text": v if isinstance(v, str) else (str(v) if isinstance(v, bool) else str(v))}
                       for k, v in flat.items() if v is not None])
    _write(kp, "kpi_metrics", "one row per scalar in results/metrics.json", {
        "metric_key": "dotted path in metrics.json (lists flattened with .0, .1, ...)", "value": "numeric value", "value_text": "text form"}, out)

    repo = (cfg.raw.get("links") or {}).get("repo_url") or "https://github.com/<user>/flood-it-game-analytics"
    raw_base = repo.replace("https://github.com/", "https://raw.githubusercontent.com/") + "/main/powerbi/data/"
    base = cfg.path("powerbi_dir")
    (base / "model.md").write_text(_model_md(raw_base), encoding="utf-8", newline="\n")
    (base / "measures.dax").write_text(MEASURES, encoding="utf-8", newline="\n")
    (base / "layout.md").write_text(_layout_md(flat), encoding="utf-8", newline="\n")
    rec = _reconciliation(flat)
    rec.to_csv(base / "reconciliation.csv", index=False, lineterminator="\n", float_format="%.10g")
    (base / "PROMPT_POWERBI.md").write_text(_prompt(raw_base, repo), encoding="utf-8", newline="\n")
    log.info("Power BI package: %d tables, %d reconciliation checks", len(TABLES), len(rec))


# ----------------------------------------------------------------------------- model.md
def _model_md(raw_base: str) -> str:
    lines = ["# Power BI data model", "",
             "Source: CSV files in `powerbi/data/` produced by `python -m flood_it run`. Load each with **Get data -> Web** "
             "using the raw link (public repo, no sign-in), or from the local folder. Dates are ISO `YYYY-MM-DD`; set the "
             "column type to Date with locale en-US. Booleans are 0/1 whole numbers.", "",
             "## Relationships (single direction, one-to-many)", "",
             "| From (one) | To (many) | Active |", "|---|---|---|",
             "| `dim_date[date]` | `fact_daily_activity[date]` | yes |",
             "| `dim_date[date]` | `fact_iap_transactions[purchase_date]` | yes |",
             "| `dim_platform[platform]` | `fact_monetization_platform[platform]` | yes |",
             "| `dim_platform[platform]` | `fact_retention_platform[platform]` | yes |",
             "| `dim_platform[platform]` | `fact_iap_transactions[platform]` | yes |", "",
             "All other tables are standalone (each visual uses one table), so no ambiguous paths. Mark `dim_date` as the date table.",
             "", "## Tables", ""]
    for name, t in TABLES.items():
        lines += [f"### {name}", "", f"- Grain: **{t['grain']}** ({t['rows']} rows)", f"- Raw CSV: {raw_base}{name}.csv", "",
                  "| Column | Type | Description |", "|---|---|---|"]
        lines += [f"| `{c}` | {typ} | {desc} |" for c, (typ, desc) in t["columns"].items()]
        lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- measures
MEASURES = r"""// =============================================================================
// Flood-It analytics - DAX measures. Definitions mirror src/flood_it/analysis/*.py
// exactly; expected values are in powerbi/reconciliation.csv.
// Create them in a dedicated table, e.g. `_Measures` (Enter data -> empty table).
// =============================================================================

// ---------- Growth (fact_daily_activity, one row per event_date) ----------
// DAU on the current day(s). At day grain = distinct active players.
DAU = SUM ( fact_daily_activity[dau] )
// Mean DAU over the days in context (all 114 days by default).
Avg DAU = AVERAGE ( fact_daily_activity[dau] )
// Mean DAU excluding spike days (tracking/sampling artefacts).
Avg DAU excl Spikes = CALCULATE ( AVERAGE ( fact_daily_activity[dau] ), fact_daily_activity[is_spike_day] = 0 )
Installs = SUM ( fact_daily_activity[installs] )
Avg Daily Installs = AVERAGE ( fact_daily_activity[installs] )
// WAU / MAU are pre-computed distinct counts (trailing 7 / 30 days) - not additive across days.
WAU = SUM ( fact_daily_activity[wau] )
MAU = SUM ( fact_daily_activity[mau] )
// Stickiness on one day = DAU / MAU, only when a full 30-day window exists.
Stickiness =
    IF ( MAX ( fact_daily_activity[full_30d_window] ) = 1,
         DIVIDE ( SUM ( fact_daily_activity[dau] ), SUM ( fact_daily_activity[mau] ) ) )
// Headline: mean of daily DAU/MAU over spike-free 30-day windows.
Avg Stickiness Clean =
    AVERAGEX (
        FILTER ( fact_daily_activity, fact_daily_activity[clean_stickiness_window] = 1 ),
        DIVIDE ( fact_daily_activity[dau], fact_daily_activity[mau] ) )
Spike Days = CALCULATE ( COUNTROWS ( fact_daily_activity ), fact_daily_activity[is_spike_day] = 1 )

// ---------- Retention (fact_retention_cohort: cohort_week x day_n) ----------
// Classic Day-N retention with right-censoring: retained / ELIGIBLE (never / all installs).
Retention = DIVIDE ( SUM ( fact_retention_cohort[retained_users] ), SUM ( fact_retention_cohort[eligible_users] ) )
Retention D1  = CALCULATE ( [Retention], fact_retention_cohort[day_n] = 1 )
Retention D3  = CALCULATE ( [Retention], fact_retention_cohort[day_n] = 3 )
Retention D7  = CALCULATE ( [Retention], fact_retention_cohort[day_n] = 7 )
Retention D14 = CALCULATE ( [Retention], fact_retention_cohort[day_n] = 14 )
Retention D30 = CALCULATE ( [Retention], fact_retention_cohort[day_n] = 30 )
// Cohort size (same for every day_n of a cohort -> take one day_n).
Cohort Installs = CALCULATE ( SUM ( fact_retention_cohort[cohort_users] ), fact_retention_cohort[day_n] = 1 )
// Curve (fact_retention_curve, day_n 0..30 pooled)
Retention Curve = DIVIDE ( SUM ( fact_retention_curve[retained_users] ), SUM ( fact_retention_curve[eligible_users] ) )
Retention CI Low = MAX ( fact_retention_curve[ci_low] )
Retention CI High = MAX ( fact_retention_curve[ci_high] )
Retention by Platform = DIVIDE ( SUM ( fact_retention_platform[retained_users] ), SUM ( fact_retention_platform[eligible_users] ) )

// ---------- Monetisation (fact_monetization_platform; additive over platforms) ----------
Revenue USD = SUM ( fact_monetization_platform[revenue_usd] )
Active Players = SUM ( fact_monetization_platform[active_users] )
Player Days = SUM ( fact_monetization_platform[user_days] )
Payers = SUM ( fact_monetization_platform[payers] )
Purchases = SUM ( fact_monetization_platform[purchases] )
// Payer rate = payers / active players
Payer Rate = DIVIDE ( [Payers], [Active Players] )
// ARPU = revenue / active players (whole window)
ARPU = DIVIDE ( [Revenue USD], [Active Players] )
// ARPDAU = revenue / player-days (= revenue / sum of daily DAU)
ARPDAU = DIVIDE ( [Revenue USD], [Player Days] )
// ARPPU = revenue / payers
ARPPU = DIVIDE ( [Revenue USD], [Payers] )
// LTV (fact_ltv_curve, fixed population): cumulative revenue days 0..N / installs observable 30 days
LTV = DIVIDE ( SUM ( fact_ltv_curve[revenue_usd] ), SUM ( fact_ltv_curve[eligible_users] ) )
LTV D7  = CALCULATE ( [LTV], fact_ltv_curve[day_n] = 7 )
LTV D30 = CALCULATE ( [LTV], fact_ltv_curve[day_n] = 30 )
IAP Revenue (transactions) = SUM ( fact_iap_transactions[revenue_usd] )

// ---------- Levels (fact_level_funnel, one row per level 1..30) ----------
Level Starts = SUM ( fact_level_funnel[starts] )
// Difficulty: completion per attempt = completes / starts
Completion per Attempt = DIVIDE ( SUM ( fact_level_funnel[completes] ), SUM ( fact_level_funnel[starts] ) )
// Funnel: players who started the level / players who started level 1
Reach Rate =
    DIVIDE ( SUM ( fact_level_funnel[users_started] ),
             CALCULATE ( SUM ( fact_level_funnel[users_started] ), REMOVEFILTERS ( fact_level_funnel ), fact_level_funnel[level] = 1 ) )
// Quit rate among NEW players; blank at level 30 (last level = finished, not quit)
Quit Rate =
    IF ( MAX ( fact_level_funnel[level] ) = 30, BLANK (),
         DIVIDE ( SUM ( fact_level_funnel[new_players_last_level] ), SUM ( fact_level_funnel[new_players_started] ) ) )
Attempts per Player = DIVIDE ( SUM ( fact_level_funnel[starts] ), SUM ( fact_level_funnel[users_started] ) )
Quickplay Completion = DIVIDE ( SUM ( fact_quickplay_boards[completes] ), SUM ( fact_quickplay_boards[starts] ) )

// ---------- Segments (fact_day0_segments: dimension x segment) ----------
Segment Players = SUM ( fact_day0_segments[players] )
Segment D1 Retention = DIVIDE ( SUM ( fact_day0_segments[d1_retained] ), SUM ( fact_day0_segments[d1_eligible] ) )
Segment D7 Retention = DIVIDE ( SUM ( fact_day0_segments[d7_retained] ), SUM ( fact_day0_segments[d7_eligible] ) )
Segment Churn Rate = DIVIDE ( SUM ( fact_day0_segments[churned] ), SUM ( fact_day0_segments[churn_eligible] ) )

// ---------- Churn model ----------
Decile Churn Rate = DIVIDE ( SUM ( fact_churn_risk_deciles[churned] ), SUM ( fact_churn_risk_deciles[players] ) )
Test AUC = MAX ( fact_churn_model_performance[test_auc] )
CV AUC = MAX ( fact_churn_model_performance[cv_auc_mean] )
Permutation Importance = MAX ( fact_churn_feature_importance[permutation_auc_drop] )

// ---------- KPI lookup (any scalar of results/metrics.json) ----------
// Used for cards whose value is a model or test statistic, e.g. KPI("churn.lr_test_auc").
// Create one measure per card, e.g.:
Churn LR Test AUC = CALCULATE ( MAX ( kpi_metrics[value] ), kpi_metrics[metric_key] = "churn.lr_test_auc" )
Churn Rate = CALCULATE ( MAX ( kpi_metrics[value] ), kpi_metrics[metric_key] = "churn.churn_rate" )
Players in Window = CALCULATE ( MAX ( kpi_metrics[value] ), kpi_metrics[metric_key] = "profile.total_users" )
AB N per Arm = CALCULATE ( MAX ( kpi_metrics[value] ), kpi_metrics[metric_key] = "stats.ab_n_per_arm" )
"""


# ----------------------------------------------------------------------------- layout.md
VISUALS = {
    "dau": ("Line chart (DAU) above a clustered column chart (Installs), same x-axis; spike days as orange markers",
            "Axis: fact_daily_activity[date]; Values: [DAU] and, separately, [Installs]; conditional marker colour by is_spike_day"),
    "stickiness": ("Line chart", "Axis: date (filter full_30d_window = 1); Values: [Stickiness]; y-axis 0-15%"),
    "heatmap": ("Matrix with background colour scale (light blue -> dark blue)",
                "Rows: cohort_week; Columns: day_n; Values: [Retention] formatted 0.0%; blank = censored"),
    "curve": ("Line chart with error band", "Axis: fact_retention_curve[day_n] (1-30); Values: [Retention Curve]; error bars [Retention CI Low]/[Retention CI High]"),
    "monet": ("Table + clustered bar", "Rows: platform; Values: [Active Players], [Payers], [Revenue USD], [Payer Rate], [ARPU], [ARPDAU], [ARPPU]; totals row on"),
    "ltv": ("Line chart (stepped)", "Axis: fact_ltv_curve[day_n]; Values: [LTV] (format $0.0000)"),
    "reach": ("Column chart", "Axis: fact_level_funnel[level]; Values: [Reach Rate]"),
    "difficulty": ("Column chart (Completion per Attempt) + line (Quit Rate) on ONE percentage axis",
                   "Axis: level; Column: [Completion per Attempt]; Line: [Quit Rate]"),
    "seg_eng": ("Clustered column", "Axis: fact_day0_segments[segment] (filter dimension = 'Day-0 engagement time', sort by segment_order); Values: [Segment D1 Retention], [Segment D7 Retention]"),
    "seg_mode": ("Bar chart", "Axis: segment (filter dimension = 'Day-0 game mode'); Values: [Segment D1 Retention]"),
    "roc": ("Line chart", "Axis: fact_churn_roc[fpr]; Values: tpr; Legend: model; add a y = x reference line"),
    "importance": ("Bar chart (horizontal)", "Axis: feature (filter model = logistic_regression, top 8 by permutation_auc_drop); Values: [Permutation Importance]"),
    "tests": ("Table", "fact_ab_observational_tests: comparison, metric, group_a, rate_a, group_b, rate_b, diff_a_minus_b, diff_ci_low, diff_ci_high, p_value, cohens_h"),
    "power": ("Line chart (log y-axis)", "Axis: fact_ab_power_analysis[mde_abs]; Values: n_per_arm; tooltip days_needed_at_sample_volume"),
}


def _layout_md(flat: dict) -> str:
    L = ["# Power BI report layout", "",
         "One page per section, in this order, mirroring the Claude dashboard. Titles and insight sentences are copied "
         "verbatim from the dashboard (generated by `src/flood_it/narrative.py`).", "",
         "**Theme:** background #FCFCFB, text #0B0B0B / #52514E, series colours in this fixed order: "
         "#2A78D6 (blue), #EB6834 (orange), #1BAF7A (aqua); heatmap sequential #CDE2FB -> #0D366B. Font Segoe UI. "
         "Every visual: title = chart title below, subtitle = definition, a text box under it with the insight and "
         "`Source: <file>`. Turn on 'Show as table' availability for each visual.", ""]
    for s in N.SECTIONS:
        L += [f"## Page: {s['title']}", ""]
        if s["id"] == "overview":
            L += [f"Text box (top): {N.render_text(s['summary'], flat)}", "",
                  "KPI cards (2 rows x 5, card visual):", "", "| Card | Measure / key | Expected | Definition |", "|---|---|---|---|"]
            for label, key, fmt, definition in s["kpis"]:
                L.append(f"| {label} | `{key}` | {N.FMT[fmt](flat[key])} | {definition} |")
            L.append("")
            continue
        for ch in s["charts"]:
            vis, fields = VISUALS[ch["id"]]
            L += [f"### {ch['title']}", "", f"- Visual: {vis}", f"- Fields: {fields}",
                  f"- Definition: {ch['definition']}", f"- Source: `{ch['source']}`",
                  f"- Insight (verbatim): {N.render_text(ch['insight'], flat)}", ""]
    L += ["## Page: Data limitations", "", "Text box, bullet list (verbatim):", ""]
    L += [f"- {N.render_text(t, flat)}" for t in N.LIMITATIONS]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- reconciliation
def _reconciliation(flat: dict) -> pd.DataFrame:
    rows = []

    def add(page, visual, measure, context, key, tol=1e-6):
        rows.append({"check_id": len(rows) + 1, "page": page, "visual": visual, "measure_or_field": measure,
                     "filter_context": context, "expected_value": flat[key], "metrics_json_key": key, "tolerance": tol})

    add("Overview", "KPI card", "[Players in Window]", "none", "profile.total_users", 0)
    add("Overview", "KPI card", "[Cohort Installs]", "all cohort_week", "retention.cohort_users", 0)
    add("Overview", "KPI card", "[Avg DAU excl Spikes]", "all dates", "growth.avg_dau_excl_spikes", 0.05)
    add("Overview", "KPI card", "[Avg DAU]", "all dates", "growth.avg_dau", 0.05)
    add("Overview", "KPI card", "[Avg Stickiness Clean]", "all dates", "growth.avg_stickiness_clean_window", 1e-4)
    for n in [1, 3, 7, 14, 30]:
        add("Overview / Retention", "KPI card", f"[Retention D{n}]", "all cohort_week", f"retention.d{n}_retention", 1e-4)
    add("Retention", "Retention by platform", "[Retention by Platform]", "platform=ANDROID, day_n=1", "retention.d1_retention_android", 1e-4)
    add("Retention", "Retention by platform", "[Retention by Platform]", "platform=IOS, day_n=1", "retention.d1_retention_ios", 1e-4)
    add("Growth", "DAU", "[Installs]", "all dates", "growth.total_installs_first_open", 0)
    add("Growth", "DAU", "[Spike Days]", "all dates", "growth.n_spike_days", 0)
    add("Revenue", "Monetisation", "[Revenue USD]", "all platforms", "revenue.revenue_usd", 0.005)
    add("Revenue", "Monetisation", "[Payers]", "all platforms", "revenue.payers", 0)
    add("Revenue", "Monetisation", "[Purchases]", "all platforms", "revenue.purchases", 0)
    add("Overview / Revenue", "KPI card", "[Payer Rate]", "all platforms", "revenue.payer_rate", 1e-6)
    add("Revenue", "Monetisation", "[ARPU]", "all platforms", "revenue.arpu_usd", 1e-6)
    add("Revenue", "Monetisation", "[ARPDAU]", "all platforms", "revenue.arpdau_usd", 1e-6)
    add("Overview / Revenue", "KPI card", "[ARPPU]", "all platforms", "revenue.arppu_usd", 1e-4)
    add("Revenue", "Monetisation", "[Payer Rate]", "platform=ANDROID", "revenue.payer_rate_android", 1e-6)
    add("Revenue", "Monetisation", "[Payer Rate]", "platform=IOS", "revenue.payer_rate_ios", 1e-6)
    add("Revenue", "LTV", "[LTV D7]", "none", "revenue.ltv_d7_usd", 1e-6)
    add("Revenue", "LTV", "[LTV D30]", "none", "revenue.ltv_d30_usd", 1e-6)
    add("Levels", "Level funnel", "[Reach Rate]", "level=10", "levels.reach_rate_level10", 1e-4)
    add("Levels", "Level funnel", "[Reach Rate]", "level=30", "levels.reach_rate_level30", 1e-4)
    add("Levels", "Difficulty", "[Completion per Attempt]", "level=27", "levels.hardest_levels_completion.0", 1e-4)
    add("Levels", "Difficulty", "[Quit Rate]", "level=27", "levels.top_quit_rates.0", 1e-4)
    add("Levels", "Difficulty", "[Attempts per Player]", "level=27", "levels.level27_attempts_per_player", 0.005)
    add("Segments", "Engagement", "[Segment D7 Retention]", "dimension='Day-0 engagement time', segment='<1 min'", "segments.d7_retention_eng_lt1min", 1e-4)
    add("Segments", "Engagement", "[Segment D7 Retention]", "dimension='Day-0 engagement time', segment='15+ min'", "segments.d7_retention_eng_15plus", 1e-4)
    add("Segments", "Mode", "[Segment D1 Retention]", "dimension='Day-0 game mode', segment='both'", "segments.d1_retention_by_mode.both", 1e-4)
    add("Churn", "ROC", "[Test AUC]", "model=logistic_regression", "churn.lr_test_auc", 1e-4)
    add("Churn", "ROC", "[Test AUC]", "model=decision_tree", "churn.tree_test_auc", 1e-4)
    add("Churn", "Risk deciles", "[Decile Churn Rate]", "risk_decile=10", "churn.top_decile_churn_rate", 1e-4)
    add("Churn", "Risk deciles", "[Decile Churn Rate]", "risk_decile=1", "churn.bottom_decile_churn_rate", 1e-4)
    add("A/B", "Observational tests", "rate_a", "comparison='Platform: iOS vs Android', metric='D1 retention'", "stats.d1_ios", 1e-4)
    add("A/B", "Observational tests", "rate_b", "comparison='Platform: iOS vs Android', metric='D1 retention'", "stats.d1_android", 1e-4)
    add("A/B", "Power analysis", "n_per_arm", "mde_abs=0.02", "stats.ab_n_per_arm", 0)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- prompt
def _prompt(raw_base: str, repo: str) -> str:
    files = "\n".join(f"- {raw_base}{n}.csv" for n in TABLES)
    return f"""# Prompt: rebuild the Flood-It report in Power BI (via Power BI MCP)

Copy everything below the line into Claude on the machine where Power BI Desktop and the Power BI MCP server run.

---

You are building a Power BI report that must match an existing analytics dashboard **100%**. Work through the Power BI
MCP tools; do not invent numbers or measures.

**Inputs (public GitHub repo {repo}):**
- Data model spec: {repo}/blob/main/powerbi/model.md
- DAX measures: {repo}/blob/main/powerbi/measures.dax
- Page layout, titles and insight text: {repo}/blob/main/powerbi/layout.md
- Expected values: {repo}/blob/main/powerbi/reconciliation.csv

**CSV tables (load each with Web connector, no authentication):**
{files}

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
"""
