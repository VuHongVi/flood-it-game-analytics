"""Emulate every DAX measure in reconciliation.csv on powerbi/data/*.csv.

If this passes, a Power BI model built from model.md + measures.dax reproduces metrics.json:
the CSVs carry enough (counts, not only rates) for the measures to recompute every KPI.
"""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PB = ROOT / "powerbi" / "data"
pytestmark = pytest.mark.skipif(not (ROOT / "powerbi" / "reconciliation.csv").exists(), reason="run the pipeline first")


def t(name):
    return pd.read_csv(PB / f"{name}.csv")


def div(a, b):
    return a / b if b else float("nan")


def measure(name: str, ctx: str) -> float:
    da, rc, mp = t("fact_daily_activity"), t("fact_retention_cohort"), t("fact_monetization_platform")
    lv, sg, rp = t("fact_level_funnel"), t("fact_day0_segments"), t("fact_retention_platform")
    kpi = t("kpi_metrics").set_index("metric_key")["value"]
    plat = "ANDROID" if "ANDROID" in ctx else "IOS" if "IOS" in ctx else None
    if plat:
        mp = mp[mp.platform == plat]
    lvl = int(ctx.split("level=")[1]) if "level=" in ctx else None
    seg = ctx.split("segment='")[1].rstrip("'") if "segment='" in ctx else None
    dim = ctx.split("dimension='")[1].split("'")[0] if "dimension='" in ctx else None
    if dim:
        sg = sg[(sg.dimension == dim) & (sg.segment == seg)]
    ret = lambda d: div(d.retained_users.sum(), d.eligible_users.sum())  # noqa: E731
    table = {
        "[Players in Window]": lambda: kpi["profile.total_users"],
        "[Cohort Installs]": lambda: rc[rc.day_n == 1].cohort_users.sum(),
        "[Avg DAU excl Spikes]": lambda: da[da.is_spike_day == 0].dau.mean(),
        "[Avg DAU]": lambda: da.dau.mean(),
        "[Avg Stickiness Clean]": lambda: (da[da.clean_stickiness_window == 1].eval("dau / mau")).mean(),
        "[Installs]": lambda: da.installs.sum(),
        "[Spike Days]": lambda: (da.is_spike_day == 1).sum(),
        "[Retention by Platform]": lambda: ret(rp[(rp.platform == plat) & (rp.day_n == 1)]),
        "[Revenue USD]": lambda: mp.revenue_usd.sum(),
        "[Payers]": lambda: mp.payers.sum(),
        "[Purchases]": lambda: mp.purchases.sum(),
        "[Payer Rate]": lambda: div(mp.payers.sum(), mp.active_users.sum()),
        "[ARPU]": lambda: div(mp.revenue_usd.sum(), mp.active_users.sum()),
        "[ARPDAU]": lambda: div(mp.revenue_usd.sum(), mp.user_days.sum()),
        "[ARPPU]": lambda: div(mp.revenue_usd.sum(), mp.payers.sum()),
        "[LTV D7]": lambda: (lambda r: div(r.revenue_usd.sum(), r.eligible_users.sum()))(t("fact_ltv_curve").query("day_n == 7")),
        "[LTV D30]": lambda: (lambda r: div(r.revenue_usd.sum(), r.eligible_users.sum()))(t("fact_ltv_curve").query("day_n == 30")),
        "[Reach Rate]": lambda: div(lv[lv.level == lvl].users_started.sum(), lv[lv.level == 1].users_started.sum()),
        "[Completion per Attempt]": lambda: div(lv[lv.level == lvl].completes.sum(), lv[lv.level == lvl].starts.sum()),
        "[Quit Rate]": lambda: div(lv[lv.level == lvl].new_players_last_level.sum(), lv[lv.level == lvl].new_players_started.sum()),
        "[Attempts per Player]": lambda: div(lv[lv.level == lvl].starts.sum(), lv[lv.level == lvl].users_started.sum()),
        "[Segment D7 Retention]": lambda: div(sg.d7_retained.sum(), sg.d7_eligible.sum()),
        "[Segment D1 Retention]": lambda: div(sg.d1_retained.sum(), sg.d1_eligible.sum()),
    }
    for n in [1, 3, 7, 14, 30]:
        table[f"[Retention D{n}]"] = (lambda n=n: ret(rc[rc.day_n == n]))
    if name == "[Test AUC]":
        perf = t("fact_churn_model_performance").set_index("model")
        return perf.loc[ctx.split("model=")[1], "test_auc"]
    if name == "[Decile Churn Rate]":
        dec = t("fact_churn_risk_deciles").set_index("risk_decile")
        r = dec.loc[int(ctx.split("risk_decile=")[1])]
        return div(r.churned, r.players)
    if name in ("rate_a", "rate_b"):
        ob = t("fact_ab_observational_tests")
        row = ob[(ob.comparison == "Platform: iOS vs Android") & (ob.metric == "D1 retention")].iloc[0]
        return row[name]
    if name == "n_per_arm":
        pw = t("fact_ab_power_analysis")
        return pw[pw.mde_abs == 0.02].n_per_arm.iloc[0]
    return table[name]()


def test_every_reconciliation_row_is_reproducible_from_powerbi_csvs():
    rec = pd.read_csv(ROOT / "powerbi" / "reconciliation.csv")
    failures = []
    for r in rec.itertuples():
        actual = float(measure(r.measure_or_field, r.filter_context))
        # metrics.json stores rounded values: allow the rounding step plus the declared tolerance
        tol = r.tolerance + 1e-12
        if abs(actual - r.expected_value) > tol:
            failures.append((r.check_id, r.measure_or_field, r.filter_context, r.expected_value, actual))
    assert not failures, failures
