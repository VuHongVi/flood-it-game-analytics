"""Validate stage: every headline metric is computed twice and compared automatically.

Method A = SQL straight from raw events (sql/20, 30, 40, 50, 00, 01).
Method B = Pandas from the player-level extracts (sql/10, 11, 12, 51) via analysis/metrics.py.
Plus sanity / invariant checks. Output: results/validation_checks.csv and
results/validation_report.md with PASS/FAIL per check.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .analysis import metrics as M
from .analysis.sections_c import level_stats_from_user_level

log = logging.getLogger(__name__)


@dataclass
class Check:
    area: str
    check: str
    method_a: str
    method_b: str
    value_a: str
    value_b: str
    max_abs_diff: float
    tolerance: float
    status: str


def _compare(area, name, a_desc, b_desc, a: pd.Series, b: pd.Series, tol=0.0) -> Check:
    a = pd.to_numeric(a, errors="coerce").reset_index(drop=True)
    b = pd.to_numeric(b, errors="coerce").reset_index(drop=True)
    if len(a) != len(b):
        return Check(area, name, a_desc, b_desc, f"{len(a)} rows", f"{len(b)} rows", np.inf, tol, "FAIL")
    diff = float((a - b).abs().max()) if len(a) else 0.0
    status = "PASS" if diff <= tol else "FAIL"
    va = f"sum={a.sum():,.6g}" if len(a) > 1 else f"{a.iloc[0]:,.6g}"
    vb = f"sum={b.sum():,.6g}" if len(b) > 1 else f"{b.iloc[0]:,.6g}"
    return Check(area, name, a_desc, b_desc, va, vb, diff, tol, status)


def _assert(area, name, desc, ok: bool, detail: str) -> Check:
    return Check(area, name, desc, "invariant", detail, "", 0.0, 0.0, "PASS" if ok else "FAIL")


def run_all(ctx: dict) -> dict:
    raw, cfg = ctx["raw"], ctx["cfg"]
    a = cfg.analysis
    start, end = pd.Timestamp(a["start_suffix"]), pd.Timestamp(a["end_suffix"])
    users, ud, iap = raw["10_users"], raw["11_user_day"], raw["12_iap"]
    checks: list[Check] = []

    # --- volume reconciliation
    inv_total = raw["00_table_inventory"]["events"].sum()
    checks.append(_compare("Data", "Total events: table inventory vs event catalogue",
                           "SQL 00 COUNT(*) per table", "SQL 01 events by name",
                           pd.Series([inv_total]), pd.Series([raw["01_event_counts"]["events"].sum()])))
    checks.append(_compare("Data", "Total events: raw vs player-day extract",
                           "SQL 00", "Pandas sum(user_day.events)",
                           pd.Series([inv_total]), pd.Series([ud["events"].sum()])))
    checks.append(_compare("Data", "Distinct players: users table vs player-day table",
                           "SQL 10 rows", "Pandas nunique(user_day.user_id)",
                           pd.Series([len(users)]), pd.Series([ud["user_id"].nunique()])))

    # --- growth
    g_pd = M.daily_growth(ud, users)
    g_pd["activity_date"] = g_pd["activity_date"].dt.strftime("%Y-%m-%d")
    g_sql = raw["20_daily_activity"]
    x = g_sql.merge(g_pd, on="activity_date", suffixes=("_sql", "_pd"), how="outer")
    for col in ["dau", "installs", "first_seen_users", "wau", "mau"]:
        checks.append(_compare("Growth", f"Daily {col.upper()} (114 days)", "SQL 20 from raw events",
                               "Pandas daily_growth(user_day)", x[f"{col}_sql"], x[f"{col}_pd"]))

    # --- retention
    cohort = M.build_install_cohort(users, start)
    r_pd = M.retention_table(cohort, ud, a["retention_days"], end, by="cohort_week")
    r_pd["cohort_week"] = r_pd["cohort_week"].dt.strftime("%Y-%m-%d")
    r_sql = raw["30_retention_cohort"]
    y = r_sql.merge(r_pd, on=["cohort_week", "day_n"], suffixes=("_sql", "_pd"), how="outer")
    for col in ["cohort_users", "eligible_users", "retained_users"]:
        checks.append(_compare("Retention", f"Cohort-week x day-N {col} ({len(y)} cells)",
                               "SQL 30 from raw events", "Pandas retention_table", y[f"{col}_sql"], y[f"{col}_pd"]))
    for n in a["retention_days"]:
        s = y[y.day_n == n]
        checks.append(_compare("Retention", f"Pooled D{n} retention", "SQL 30 sum(retained)/sum(eligible)",
                               "Pandas", pd.Series([s.retained_users_sql.sum() / s.eligible_users_sql.sum()]),
                               pd.Series([s.retained_users_pd.sum() / s.eligible_users_pd.sum()]), tol=1e-12))

    # --- revenue
    iap_usd = M.iap_revenue_usd(iap)
    k_pd = M.monetization_kpis(ud, iap_usd, users)
    k_sql = raw["40_revenue_summary"]
    z = k_sql.merge(k_pd, on="platform", suffixes=("_sql", "_pd"), how="outer").sort_values("platform")
    for col, tol in [("active_users", 0), ("user_days", 0), ("payers", 0), ("purchases", 0), ("revenue_usd", 1e-4)]:
        checks.append(_compare("Revenue", f"{col} by platform (ALL/ANDROID/IOS)", "SQL 40 from raw events",
                               "Pandas monetization_kpis", z[f"{col}_sql"], z[f"{col}_pd"], tol))

    # --- levels
    l_pd = level_stats_from_user_level(raw["51_user_level"])
    l_sql = raw["50_level_stats"].dropna(subset=["level"])
    l_sql = l_sql[l_sql["level"].between(1, 30)]
    w = l_sql.merge(l_pd[l_pd["level"].between(1, 30)], on="level", suffixes=("_sql", "_pd"), how="outer")
    for col in ["starts", "completes", "fails", "users_started", "users_completed"]:
        checks.append(_compare("Levels", f"Level 1-30 {col}", "SQL 50 from raw events",
                               "Pandas from player x level (SQL 51)", w[f"{col}_sql"], w[f"{col}_pd"]))

    # --- invariants / sanity
    curve = M.retention_table(cohort, ud, range(0, 31), end, by=None)
    checks.append(_assert("Sanity", "D0 retention = 100% (every cohort player active on install day)",
                          "retention curve", bool(np.isclose(curve.iloc[0]["retention"], 1.0)),
                          f"D0={curve.iloc[0]['retention']:.4f}"))
    checks.append(_assert("Sanity", "Eligible players never increase with N (right-censoring)",
                          "retention curve", bool(curve["eligible_users"].is_monotonic_decreasing),
                          f"{int(curve.eligible_users.iloc[0])} -> {int(curve.eligible_users.iloc[-1])}"))
    ltv = M.ltv_curve(cohort, iap_usd, max(a["ltv_days"]), end, fixed_population=True)
    checks.append(_assert("Sanity", "Fixed-population LTV curve is non-decreasing",
                          "ltv_curve", bool(ltv["ltv_usd"].is_monotonic_increasing),
                          f"D0={ltv.ltv_usd.iloc[0]:.6f}, D30={ltv.ltv_usd.iloc[-1]:.6f}"))
    checks.append(_assert("Sanity", "Every cohort player has install date inside the window",
                          "cohort", bool(cohort["install_date"].between(start, end).all()),
                          f"{cohort.install_date.min().date()}..{cohort.install_date.max().date()}"))
    checks.append(_assert("Sanity", "Every purchase has a USD value (event_value_in_usd or USD fallback)",
                          "12_iap", bool(iap_usd["revenue_usd"].notna().all()),
                          f"missing={int(iap_usd.revenue_usd.isna().sum())}"))
    feat = ctx.get("features")
    rates_ok = bool(((g_pd["dau"] <= g_pd["wau"]) & (g_pd["wau"] <= g_pd["mau"])).all())
    checks.append(_assert("Sanity", "DAU <= WAU <= MAU every day", "daily growth", rates_ok, "all 114 days"))

    df = pd.DataFrame([c.__dict__ for c in checks])
    out_dir = cfg.path("results_dir")
    df.to_csv(out_dir / "validation_checks.csv", index=False, lineterminator="\n")
    n_pass = int((df.status == "PASS").sum())
    lines = ["# Validation report", "",
             "Every headline metric is computed **twice** - (A) SQL directly on raw Firebase events and "
             "(B) Pandas on player-level extracts - and compared automatically by `src/flood_it/validate.py`. "
             "Invariant checks catch logic errors that both methods could share.", "",
             f"**Result: {n_pass} / {len(df)} checks PASS.**", "",
             "| Area | Check | Method A | Method B | Value A | Value B | Max abs diff | Status |",
             "|---|---|---|---|---|---|---|---|"]
    for c in checks:
        lines.append(f"| {c.area} | {c.check} | {c.method_a} | {c.method_b} | {c.value_a} | {c.value_b} | "
                     f"{c.max_abs_diff:.3g} | {'PASS' if c.status == 'PASS' else '**FAIL**'} |")
    lines += ["", "AI-assisted development: mistakes caught during the build are logged in "
              "[docs/ai_corrections.md](../docs/ai_corrections.md).", ""]
    (out_dir / "validation_report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    summary = {"checks": len(df), "passed": n_pass, "failed": len(df) - n_pass,
               "failed_checks": df.loc[df.status == "FAIL", "check"].tolist()}
    log.info("validation: %s/%s PASS", n_pass, len(df))
    if summary["failed"]:
        log.warning("FAILED checks: %s", summary["failed_checks"])
    return {"summary": summary, "table": df}
