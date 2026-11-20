"""Figures stage: static PNG charts for README / report, read only from data/*.csv.

Palette = validated reference categorical order (blue, orange, aqua) + single-hue blue
sequential ramp for the heatmap. One y-axis per chart (no dual axes).
"""
from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

log = logging.getLogger(__name__)

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SEQ = LinearSegmentedColormap.from_list("blue_seq", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "legend.frameon": False, "lines.linewidth": 2,
})


def _save(fig, cfg, name):
    p = cfg.path("figures_dir") / f"{name}.png"
    fig.tight_layout()
    fig.savefig(p, dpi=130, metadata={"Software": None})
    plt.close(fig)
    return p


def run_all(ctx: dict) -> None:
    cfg = ctx["cfg"]
    d = cfg.path("data_dir")
    rd = lambda n: pd.read_csv(d / f"{n}.csv")  # noqa: E731

    # 1. DAU + installs (two panels, shared x - not a dual axis)
    g = rd("p2_daily_growth")
    g["activity_date"] = pd.to_datetime(g["activity_date"])
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.5), sharex=True, height_ratios=[2, 1])
    a1.plot(g.activity_date, g.dau, color=BLUE, label="DAU")
    sp = g[g.is_spike]
    a1.scatter(sp.activity_date, sp.dau, s=36, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=2,
               label="Spike day (tracking/sampling artefact)")
    a1.set_title("Daily active players (sampled export)")
    a1.set_ylabel("Players")
    a1.legend(loc="upper right")
    a2.bar(g.activity_date, g.installs, color=AQUA, width=0.8)
    a2.set_title("Installs per day (first_open)")
    a2.set_ylabel("Installs")
    _save(fig, cfg, "fig01_dau_installs")

    # 2. stickiness
    s = g[g.full_30d_window]
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(s.activity_date, s.stickiness * 100, color=BLUE)
    ax.set_title("Stickiness = DAU / MAU (days with a full 30-day window)")
    ax.set_ylabel("%")
    ax.set_ylim(0, max(15, s.stickiness.max() * 110))
    _save(fig, cfg, "fig02_stickiness")

    # 3. retention heatmap
    r = rd("p3_retention_by_cohort_week")
    pv = r.pivot(index="cohort_week", columns="day_n", values="retention") * 100
    n = r[r.day_n == r.day_n.min()].set_index("cohort_week")["cohort_users"]
    fig, ax = plt.subplots(figsize=(7.5, 7))
    ax.grid(False)
    im = ax.imshow(pv.values, cmap=SEQ, aspect="auto", vmin=0, vmax=np.nanmax(pv.values))
    ax.set_xticks(range(len(pv.columns)), [f"D{c}" for c in pv.columns])
    ax.set_yticks(range(len(pv.index)), [f"{w}  (n={n[w]})" for w in pv.index])
    for i in range(pv.shape[0]):
        for j in range(pv.shape[1]):
            v = pv.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8,
                        color="white" if v > np.nanmax(pv.values) * 0.55 else INK)
            else:
                ax.text(j, i, "censored", ha="center", va="center", fontsize=7, color=INK2)
    ax.set_title("Day-N retention (%) by weekly install cohort")
    fig.colorbar(im, ax=ax, shrink=0.6, label="Retention %")
    _save(fig, cfg, "fig03_retention_heatmap")

    # 4. retention curve with CI
    c = rd("p3_retention_curve")
    c = c[c.day_n >= 1]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.fill_between(c.day_n, c.ci_low * 100, c.ci_high * 100, color=BLUE, alpha=0.15, linewidth=0, label="95% CI (Wilson)")
    ax.plot(c.day_n, c.retention * 100, color=BLUE, label="Retention")
    ax.set_title("Retention curve, all install cohorts (eligible players only)")
    ax.set_xlabel("Days since install")
    ax.set_ylabel("%")
    ax.legend()
    _save(fig, cfg, "fig04_retention_curve")

    # 5. LTV curve
    lt = rd("p4_ltv_curve")
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.step(lt.day_n, lt.ltv_usd * 1000, where="post", color=BLUE)
    ax.set_title(f"Cumulative IAP LTV per install (fixed population, n={int(lt.eligible_users.iloc[0])})")
    ax.set_xlabel("Days since install")
    ax.set_ylabel("USD per 1,000 installs")
    _save(fig, cfg, "fig05_ltv_curve")

    # 6. level funnel and difficulty (two panels)
    lv = rd("p5_level_funnel")
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    a1.bar(lv.level, lv.reach_rate * 100, color=BLUE, width=0.75)
    a1.set_title("Level funnel: share of level-1 players who start each level")
    a1.set_ylabel("% of level-1 players")
    a2.bar(lv.level, lv.completion_per_attempt * 100, color=AQUA, width=0.75, label="Completion per attempt")
    a2.plot(lv.level, lv.quit_rate_at_level * 100, color=ORANGE, marker="o", markersize=4,
            label="Quit rate of new players at level")
    a2.set_title("Difficulty: completion per attempt vs quit rate")
    a2.set_ylabel("%")
    a2.set_xlabel("Level")
    a2.legend(loc="upper left")
    a2.set_xticks(lv.level)
    _save(fig, cfg, "fig06_levels")

    # 7. day-0 engagement segments
    sg = rd("p6_day0_segments")
    e = sg[sg.dimension == "Day-0 engagement time"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = np.arange(len(e))
    ax.bar(x - 0.2, e.d1_retention * 100, 0.38, color=BLUE, label="D1 retention")
    ax.bar(x + 0.2, e.d7_retention * 100, 0.38, color=ORANGE, label="D7 retention")
    ax.set_xticks(x, [f"{s}\n(n={p})" for s, p in zip(e.segment, e.players)])
    ax.set_title("Retention by install-day engagement time")
    ax.set_ylabel("%")
    ax.legend()
    _save(fig, cfg, "fig07_day0_engagement")

    # 8. churn model: ROC + importance
    roc = rd("p7_roc_curve")
    imp = rd("p7_feature_importance")
    perf = rd("p7_model_performance").set_index("model")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    for m, col in [("logistic_regression", BLUE), ("decision_tree", ORANGE)]:
        rr = roc[roc.model == m]
        a1.plot(rr.fpr, rr.tpr, color=col, label=f"{m.replace('_', ' ')} (test AUC {perf.loc[m, 'test_auc']:.2f})")
    a1.plot([0, 1], [0, 1], color=INK2, linewidth=1, linestyle="--", label="random")
    a1.set_title("Churn model ROC (test set)")
    a1.set_xlabel("False positive rate")
    a1.set_ylabel("True positive rate")
    a1.legend(loc="lower right", fontsize=8)
    top = imp[imp.model == "logistic_regression"].nlargest(8, "permutation_auc_drop").iloc[::-1]
    a2.barh(top.feature, top.permutation_auc_drop, color=BLUE, height=0.6)
    a2.set_title("Top features (logistic regression)")
    a2.set_xlabel("AUC drop when shuffled (permutation importance)")
    _save(fig, cfg, "fig08_churn_model")

    # 9. power analysis
    pw = rd("p8_power_analysis")
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(pw.mde_abs * 100, pw.n_per_arm, color=BLUE, marker="o", markersize=6)
    for _, row in pw.iterrows():
        ax.annotate(f"{int(row.n_per_arm):,}/arm", (row.mde_abs * 100, row.n_per_arm), textcoords="offset points",
                    xytext=(6, 6), fontsize=8, color=INK2)
    ax.set_title(f"A/B sample size for D1 retention (baseline {pw.baseline.iloc[0]*100:.1f}%, alpha 0.05, power 0.8)")
    ax.set_xlabel("Minimum detectable effect (percentage points)")
    ax.set_ylabel("Players per arm")
    ax.set_yscale("log")
    _save(fig, cfg, "fig09_power")
    log.info("figures written")
