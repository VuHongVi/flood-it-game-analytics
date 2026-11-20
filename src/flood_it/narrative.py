"""Single source of chart titles, definitions, sources and insight sentences.

Used by BOTH the Claude dashboard (dashboard.py) and the Power BI handover (powerbi.py), so the
two reports carry the same words and numbers. Insight templates reference metrics with
`{metric.key|fmt}`; every key is a row of powerbi/data/kpi_metrics.csv (flattened metrics.json).
"""
from __future__ import annotations

import re

FMT = {
    "pct0": lambda v: f"{v * 100:.0f}%", "pct1": lambda v: f"{v * 100:.1f}%", "pct2": lambda v: f"{v * 100:.2f}%",
    "pp1": lambda v: f"{v * 100:+.1f} pp", "num0": lambda v: f"{v:,.0f}", "num1": lambda v: f"{v:,.1f}",
    "dec2": lambda v: f"{v:.2f}", "usd2": lambda v: f"${v:,.2f}", "usd4": lambda v: f"${v:,.4f}",
    "usd5": lambda v: f"${v:,.5f}", "p": lambda v: "< 0.001" if v < 0.001 else f"{v:.3f}", "text": lambda v: str(v),
}
TOKEN = re.compile(r"\{([\w.]+)\|(\w+)\}")


def flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, (dict, list)):
                    continue
                out[f"{key}.{i}"] = x
        else:
            out[key] = v
    return out


def render_text(tpl: str, flat: dict) -> str:
    return TOKEN.sub(lambda m: FMT[m.group(2)](flat[m.group(1)]), tpl)


def render_html(tpl: str, flat: dict) -> str:
    """Numbers become marked, script-drawn spans tied to a kpi_metrics row."""
    def rep(m):
        key, fmt = m.group(1), m.group(2)
        _ = flat[key]  # fail loudly on a missing key
        field = "value_text" if fmt == "text" else "value"
        return (f'<b class="num" data-draw="kpi" data-source="kpi" data-field="{field}" '
                f'data-where="metric_key={key}" data-fmt="{fmt}">—</b>')
    return TOKEN.sub(rep, tpl)


# Each section = a dashboard section = a Power BI page.
SECTIONS = [
    {"id": "overview", "title": "Overview", "summary":
        "New players leave fast (D1 {retention.d1_retention|pct1}, D30 {retention.d30_retention|pct1}); "
        "IAP is negligible (payer rate {revenue.payer_rate|pct2}), so retention and ad engagement are the levers.",
     "kpis": [
         ("Players in window", "profile.total_users", "num0", "Distinct user_pseudo_id with any event, 2018-06-12..2018-10-03."),
         ("Installs in cohort", "retention.cohort_users", "num0", "first_open in window; first touch not before the window."),
         ("Avg DAU (excl. spike days)", "growth.avg_dau_excl_spikes", "num1", "Mean distinct players per event_date, spike days removed."),
         ("Stickiness", "growth.avg_stickiness_clean_window", "pct1", "Mean DAU/MAU on days whose 30-day window has no spike day."),
         ("D1 retention", "retention.d1_retention", "pct1", "Active on install day + 1 / eligible installs."),
         ("D7 retention", "retention.d7_retention", "pct1", "Active on install day + 7 / eligible installs."),
         ("D30 retention", "retention.d30_retention", "pct1", "Active on install day + 30 / eligible installs."),
         ("Payer rate", "revenue.payer_rate", "pct2", "Players with >= 1 in_app_purchase / active players."),
         ("ARPPU", "revenue.arppu_usd", "usd2", "IAP revenue / payers."),
         ("Churn model AUC", "churn.lr_test_auc", "dec2", "Logistic regression, test set, install-day features."),
     ]},
    {"id": "growth", "title": "Growth", "charts": [
        {"id": "dau", "title": "Daily active players and installs",
         "definition": "DAU = distinct players with >= 1 event on the event_date. Installs = players whose first_open falls on the day.",
         "source": "fact_daily_activity.csv (dau, installs, is_spike_day)",
         "insight": "DAU averages {growth.avg_dau_excl_spikes|num1} on normal days. The {growth.n_spike_days|num0} spike days "
                    "(~{growth.spike_avg_dau|num0} DAU, ~{growth.spike_avg_installs|num1} installs) are an artefact: screen_view falls to "
                    "{growth.spike_screen_view_ratio|pct1} of normal and the fixed 50,000-event sample spreads over more players."},
        {"id": "stickiness", "title": "Stickiness (DAU / MAU)",
         "definition": "DAU divided by distinct players active in the trailing 30 days; shown only once a full 30-day window exists.",
         "source": "fact_daily_activity.csv (stickiness, clean_stickiness_window)",
         "insight": "Average stickiness is {growth.avg_stickiness_clean_window|pct1} on spike-free windows (from "
                    "{growth.clean_window_first_date|text}): roughly one in ten monthly players plays on a given day."},
    ]},
    {"id": "retention", "title": "Retention", "charts": [
        {"id": "heatmap", "title": "Day-N retention by weekly install cohort",
         "definition": "Classic Day-N: share of a cohort active exactly N days after install. Only players with N days of data (eligible) count; empty cells are censored.",
         "source": "fact_retention_cohort.csv (retained_users / eligible_users)",
         "insight": "D1 fell from {retention.d1_retention_cohorts_jun_jul|pct1} for June-July cohorts to "
                    "{retention.d1_retention_cohorts_sep|pct1} for September cohorts; the {retention.smallest_cohort_week|text} week is small because installs are missing on spike days."},
        {"id": "curve", "title": "Retention curve, all cohorts",
         "definition": "Pooled retained / eligible for each day since install, with a 95% Wilson interval.",
         "source": "fact_retention_curve.csv",
         "insight": "D1 {retention.d1_retention|pct1}, D7 {retention.d7_retention|pct1}, D30 {retention.d30_retention|pct1}. "
                    "Excluding spike-day targets moves D1 only to {retention.d1_retention_excl_spike_targets|pct1}."},
    ]},
    {"id": "revenue", "title": "Revenue & LTV", "charts": [
        {"id": "monet", "title": "Monetisation by platform",
         "definition": "Payer rate = payers / active players; ARPU = revenue / active players; ARPDAU = revenue / player-days; ARPPU = revenue / payers. IAP only.",
         "source": "fact_monetization_platform.csv",
         "insight": "{revenue.purchases|num0} purchases, {revenue.revenue_usd|usd2} in total; remove_ads is "
                    "{revenue.top_product_share|pct0} of purchases. Ad revenue is not in the export ({revenue.ad_reward_events|num0} rewarded-ad events carry no value)."},
        {"id": "ltv", "title": "Cumulative IAP LTV per install",
         "definition": "Revenue from days 0..N after install / installs observable for 30 days (the same players at every N).",
         "source": "fact_ltv_curve.csv",
         "insight": "LTV D30 is {revenue.ltv_d30_usd|usd4} per install, from only {revenue.ltv_d30_payers|num0} payers among "
                    "{revenue.ltv_population_users|num0} installs: directional, not a basis for UA bids."},
    ]},
    {"id": "levels", "title": "Levels & difficulty", "charts": [
        {"id": "reach", "title": "Level funnel",
         "definition": "Players who started each level / players who started level 1 (progression mode, all players active in the window).",
         "source": "fact_level_funnel.csv (users_started)",
         "insight": "{levels.reach_rate_level10|pct1} of level-1 players reach level 10 and {levels.reach_rate_level30|pct1} reach level 30."},
        {"id": "difficulty", "title": "Completion per attempt and quit rate",
         "definition": "Completion per attempt = level_complete / level_start. Quit rate = new players whose last level started is L / new players who started L.",
         "source": "fact_level_funnel.csv (completes, starts, new_players_last_level, new_players_started)",
         "insight": "Level {levels.hardest_levels.0|num0} is a wall: {levels.hardest_levels_completion.0|pct1} of attempts succeed and "
                    "{levels.top_quit_rates.0|pct1} of new players who reach it stop there; levels {levels.hardest_levels.1|num0} and {levels.hardest_levels.2|num0} follow."},
    ]},
    {"id": "segments", "title": "Player segments", "charts": [
        {"id": "seg_eng", "title": "Retention by install-day engagement",
         "definition": "Players grouped by minutes of engagement (user_engagement.engagement_time_msec) on their install day.",
         "source": "fact_day0_segments.csv (dimension = Day-0 engagement time)",
         "insight": "{segments.share_eng_lt1min|pct0} of installs play under a minute on day 0; their D7 is "
                    "{segments.d7_retention_eng_lt1min|pct1} vs {segments.d7_retention_eng_15plus|pct1} for 15+ minutes."},
        {"id": "seg_mode", "title": "D1 retention by day-0 game mode",
         "definition": "Mode played on install day: progression (levels), quickplay (boards) or both.",
         "source": "fact_day0_segments.csv (dimension = Day-0 game mode)",
         "insight": "Players who tried both modes keep {segments.d1_retention_by_mode.both|pct1} on D1 vs "
                    "{segments.d1_retention_by_mode.quickplay_only|pct1} for quickplay only. Payers are active a median "
                    "{segments.payer_median_active_days|num0} days vs {segments.nonpayer_median_active_days|num0}."},
    ]},
    {"id": "churn", "title": "Churn model", "charts": [
        {"id": "roc", "title": "Churn prediction: ROC curve",
         "definition": "Churned = no activity on days 7-30 after install. Features = install-day behaviour only. 75/25 stratified split, 5-fold CV.",
         "source": "fact_churn_roc.csv, fact_churn_model_performance.csv",
         "insight": "Logistic regression reaches test AUC {churn.lr_test_auc|dec2} (CV {churn.lr_cv_auc_mean|dec2}); the depth-4 tree "
                    "{churn.tree_test_auc|dec2}. Churn rate is {churn.churn_rate|pct1} of {churn.population|num0} installs."},
        {"id": "importance", "title": "What predicts churn",
         "definition": "Permutation importance: drop in test AUC when one feature is shuffled.",
         "source": "fact_churn_feature_importance.csv (model = logistic_regression)",
         "insight": "Install-day engagement time leads. The riskiest decile churns at {churn.top_decile_churn_rate|pct1} vs "
                    "{churn.bottom_decile_churn_rate|pct1} for the safest: useful for ranking, weak for individual targeting."},
    ]},
    {"id": "ab", "title": "A/B: observational tests and test design", "charts": [
        {"id": "tests", "title": "Observational comparisons (not randomised)",
         "definition": "Two-proportion z-test (= chi-square 2x2), 95% CI of the difference, Cohen's h. Traffic source compared within Android only.",
         "source": "fact_ab_observational_tests.csv",
         "insight": "iOS D1 is {stats.d1_platform_diff|pp1} vs Android (p = {stats.d1_platform_p|p}, h {stats.d1_platform_cohens_h|dec2}); on Android, "
                    "google-play installs lead (direct) by {stats.d1_source_diff|pp1} (p {stats.d1_source_p|p}). Correlation, not causation."},
        {"id": "power", "title": "Sample size for a D1 retention A/B test",
         "definition": "Two-sided test, alpha 0.05, power 0.8, baseline = observed D1; run time = 2 x n / installs per day.",
         "source": "fact_ab_power_analysis.csv",
         "insight": "Detecting +2 pp needs {stats.ab_n_per_arm|num0} players per arm: about {stats.ab_days_needed_at_sample_volume|num0} days at the "
                    "sampled {stats.ab_sample_installs_per_day|num1} installs per day. Run on full traffic or test bigger changes."},
    ]},
]

LIMITATIONS = [
    "Sampled export: exactly {profile.events_per_day_min|num0} events per day. Absolute counts describe the sample; rates are reliable.",
    "{profile.share_acquired_before_window|pct0} of players were acquired before the window; cohorts and LTV use installs inside it only.",
    "{profile.share_new_missing_first_open|pct0} of new players have no first_open and are excluded from cohorts.",
    "Only {revenue.purchases|num0} purchases and no ad revenue: monetisation figures are directional.",
    "Traffic source is confounded with platform (iOS is (direct) only); app_remove exists only on Android and is not used as a churn label.",
    "Platform and source comparisons are observational, not causal.",
]
