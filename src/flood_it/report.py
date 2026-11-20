"""Report stage: README.md and reports/report.md rendered from results/metrics.json.

No number is typed by hand: every figure below is a lookup into metrics.json (or a CSV in
data/) formatted by the helpers. Re-running the pipeline regenerates both documents.
"""
from __future__ import annotations

import logging

from .analysis.io import read_metrics
from .config import ROOT

log = logging.getLogger(__name__)


def pct(x, d=1):
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def pp(x, d=1):
    return "n/a" if x is None else f"{x * 100:+.{d}f} pp"


def num(x, d=0):
    return "n/a" if x is None else f"{x:,.{d}f}"


def usd(x, d=2):
    return "n/a" if x is None else f"${x:,.{d}f}"


def pval(p):
    return "n/a" if p is None else ("< 0.001" if p < 0.001 else f"{p:.3f}")


def insights(m: dict) -> list[str]:
    p, g, r, v, lv, s, c, st = (m[k] for k in ["profile", "growth", "retention", "revenue", "levels",
                                               "segments", "churn", "stats"])
    return [
        f"**The export is sampled, and DAU spikes are an artefact.** Every day holds exactly "
        f"{num(p['events_per_day_min'])} events. On {g['n_spike_days']} days DAU jumps to ~{num(g['spike_avg_dau'])} "
        f"(vs {num(g['avg_dau_excl_spikes'])} on normal days) with ~{num(g['spike_avg_installs'], 1)} installs: "
        f"`screen_view` volume falls to {pct(g['spike_screen_view_ratio'])} of normal, so the fixed event budget is "
        f"spread over more players ({num(g['spike_events_per_dau'])} vs {num(g['normal_events_per_dau'])} events per "
        f"active player). Ratios are reliable; absolute counts are not.",
        f"**Retention is steep and getting worse.** D1 {pct(r['d1_retention'])}, D7 {pct(r['d7_retention'])}, "
        f"D30 {pct(r['d30_retention'])} ({num(r['cohort_users'])} installs, right-censored players excluded). "
        f"D1 fell from {pct(r['d1_retention_cohorts_jun_jul'])} for June-July cohorts to "
        f"{pct(r['d1_retention_cohorts_sep'])} for September cohorts.",
        f"**The first session decides retention.** {pct(s['share_eng_lt1min'], 0)} of installs play less than 1 "
        f"minute on day 0; their D7 retention is {pct(s['d7_retention_eng_lt1min'])} vs "
        f"{pct(s['d7_retention_eng_15plus'])} for players with 15+ minutes. Day-0 engagement time is also the top "
        f"feature of the churn model (logistic regression test AUC {c['lr_test_auc']:.2f}).",
        f"**Level {lv['hardest_levels'][0]} is a difficulty wall.** Only {pct(lv['hardest_levels_completion'][0])} of "
        f"attempts succeed ({num(lv['level27_attempts_per_player'], 1)} attempts per player) and "
        f"{pct(lv['top_quit_rates'][0])} of new players who reach it stop there; levels "
        f"{lv['hardest_levels'][1]} and {lv['hardest_levels'][2]} follow. Only {pct(lv['reach_rate_level30'])} of "
        f"level-1 players ever start level 30.",
        f"**IAP monetisation is negligible; the game lives on ads.** {num(v['purchases'])} purchases from "
        f"{num(v['payers'])} payers ({pct(v['payer_rate'], 2)} payer rate, ARPPU {usd(v['arppu_usd'])}); "
        f"`remove_ads` is {pct(v['top_product_share'], 0)} of purchases. {num(v['ad_reward_events'])} rewarded-ad "
        f"events exist but carry no revenue value, so ad revenue cannot be measured from this export.",
        f"**Android and Google Play users retain better on D1 (observational).** Android D1 "
        f"{pct(st['d1_android'])} vs iOS {pct(st['d1_ios'])} (iOS - Android {pp(st['d1_platform_diff'])}, "
        f"p = {pval(st['d1_platform_p'])}, Cohen's h {st['d1_platform_cohens_h']:.2f} = small); within Android, "
        f"google-play installs beat (direct) by {pp(st['d1_source_diff'])} (p {pval(st['d1_source_p'])}). Not causal.",
        f"**A clean A/B test on D1 needs volume.** Detecting {pp(st['ab_mde_abs'], 0)} on a "
        f"{pct(st['ab_baseline_d1'])} baseline needs {num(st['ab_n_per_arm'])} players per arm, i.e. "
        f"~{num(st['ab_days_needed_at_sample_volume'])} days at the sampled install volume "
        f"({num(st['ab_sample_installs_per_day'], 1)}/day) - run it on full traffic or test bigger changes.",
    ]


def recommendations(m: dict) -> list[str]:
    lv, s = m["levels"], m["segments"]
    return [
        f"**Product - rebalance level {lv['hardest_levels'][0]}** (then {lv['hardest_levels'][1]} and "
        f"{lv['hardest_levels'][2]}) via an A/B test; primary metric: share of players passing the level, "
        f"guardrails: D7 retention, rewarded-ad views, extra-step purchases.",
        "**Product - fix the first minute.** Shorten time-to-first-win (tutorial board, easier first levels) and "
        "measure the share of installs reaching 1+ minute of play on day 0 as a leading indicator of D7.",
        f"**Product - surface progression mode.** Players who tried progression on day 0 retain better on D1 "
        f"({pct(s['d1_retention_by_mode']['progression only'])}) than quickplay-only players "
        f"({pct(s['d1_retention_by_mode']['quickplay only'])}); test a progression-first home screen.",
        "**LiveOps / CRM - target at-risk installs.** Score every install after day 0 with the churn model and send "
        "re-engagement pushes to the top risk deciles; measure with a holdout group.",
        "**Marketing - check channel and platform quality.** Compare D1/D7 and payer rate per channel with a "
        "holdout or geo test before shifting budget; the iOS gap deserves an app-version / device audit.",
        "**Data - fix instrumentation before scaling analysis.** Log ad revenue (impression-level `ad_impression` "
        "with value), populate `event_value_in_usd`, store `level` in one type, stop the `screen_view` drops, and "
        "export unsampled data.",
    ]


def limitations(m: dict) -> list[str]:
    p, g, v = m["profile"], m["growth"], m["revenue"]
    return [
        f"Sampled export ({num(p['events_per_day_min'])} events/day): absolute DAU, installs and revenue describe "
        "the sample, not the game. Retention, rates and model results are the reliable outputs.",
        f"{pct(p['share_acquired_before_window'], 0)} of players were acquired before the window; cohort and LTV "
        f"analysis uses only installs inside it ({num(m['retention']['cohort_users'])} players).",
        f"{pct(p['share_new_missing_first_open'], 0)} of new players have no `first_open` event and are excluded "
        f"from cohorts; installs on spike days are almost entirely missing.",
        f"`event_date` is the property time zone and is used everywhere; {num(p['tz_event_date_one_day_before_utc_users'])} "
        "new players have an event_date one day before their UTC first-touch date.",
        f"Revenue: only {num(v['purchases'])} purchases (LTV rests on {num(v['ltv_d30_payers'])} payers in the fixed "
        f"population) - directional only. Ad revenue is not in the export. `user_ltv` disagrees with the "
        f"per-purchase value on {num(v['user_ltv_mismatch_rows'])} row(s) and is not used.",
        "Traffic source is confounded with platform (iOS = (direct) only) and `app_remove` is Android-only, so neither "
        "is used as a churn label; platform/source comparisons are observational, not causal.",
        f"Spike days ({', '.join(g['spike_dates'])}) are flagged and tested for sensitivity (D1 "
        f"{pct(m['retention']['d1_retention_excl_spike_targets'])} when excluded vs {pct(m['retention']['d1_retention'])}).",
    ]


def render_readme(m: dict, links: dict) -> str:
    p, g, r, v, lv, s, c, st, val = (m[k] for k in ["profile", "growth", "retention", "revenue", "levels",
                                                    "segments", "churn", "stats", "validation"])
    dash = links.get("dashboard_url")
    dash_line = f"**Interactive dashboard:** {dash}" if dash else "**Interactive dashboard:** link added after publishing (stage E)."
    ins = "\n".join(f"{i}. {t}" for i, t in enumerate(insights(m), 1))
    rec = "\n".join(f"- {t}" for t in recommendations(m))
    lim = "\n".join(f"- {t}" for t in limitations(m))
    return f"""# Flood-It Mobile Game Analytics - Firebase / GA4 export on BigQuery

End-to-end, reproducible analytics pipeline on the public Firebase Analytics export of the
puzzle game **Flood-It** (`{m['meta']['source_table']}`, {p['date_start']} to {p['date_end']}):
growth, cohort retention, monetisation, level difficulty, player segments, churn prediction,
statistical testing and A/B-test design. Every number in this README is generated from
`results/metrics.json` by the pipeline - nothing is typed by hand.

{dash_line}
**Short report:** [reports/report.md](reports/report.md) - **Validation:** [results/validation_report.md](results/validation_report.md) ({val['passed']}/{val['checks']} checks PASS)

## Key numbers

| Metric | Value | Definition |
|---|---|---|
| Players in window | {num(p['total_users'])} | distinct `user_pseudo_id` |
| Installs in cohort | {num(r['cohort_users'])} | `first_open` in window, first touch not before window |
| Avg DAU (excl. spike days) | {num(g['avg_dau_excl_spikes'])} | distinct players per `event_date` |
| Stickiness (DAU/MAU) | {pct(g['avg_stickiness_clean_window'])} | days with a spike-free 30-day window |
| D1 / D7 / D30 retention | {pct(r['d1_retention'])} / {pct(r['d7_retention'])} / {pct(r['d30_retention'])} | active on install day + N, eligible players only |
| Payer rate | {pct(v['payer_rate'], 2)} | payers / active players |
| ARPU / ARPDAU / ARPPU | {usd(v['arpu_usd'], 4)} / {usd(v['arpdau_usd'], 5)} / {usd(v['arppu_usd'])} | IAP revenue / players, player-days, payers |
| IAP LTV D30 | {usd(v['ltv_d30_usd'], 4)} | cumulative revenue per install, fixed population |
| Churn model AUC | {c['lr_test_auc']:.2f} (CV {c['lr_cv_auc_mean']:.2f} +/- {c['lr_cv_auc_std']:.2f}) | logistic regression, install-day features |

## Insights

{ins}

## Recommendations

{rec}

## Data

Firebase Analytics -> BigQuery export, one table per day (`events_YYYYMMDD`), one row per event.
`event_params` / `user_properties` are `ARRAY<STRUCT<key, value>>` and must be `UNNEST`-ed;
values sit in `string_value`, `int_value`, `float_value` or `double_value`.
{num(p['n_days'])} daily tables, {num(p['total_events'])} events, {p['n_event_names']} event names,
{num(p['total_users'])} players ({num(p['users_android'])} Android / {num(p['users_ios'])} iOS).

**Data traps verified with queries (not assumed):**
- constant {num(p['events_per_day_min'])} events/day -> sampled export;
- {pct(p['share_acquired_before_window'], 0)} of players acquired before the window;
- {pct(p['share_new_missing_first_open'], 0)} of new players without `first_open`;
- `level` stored as `int_value` and `double_value` ({', '.join(p['mixed_type_level_events'])});
- `event_value_in_usd` NULL on {v['iap_missing_event_value_in_usd']} purchases (recovered from `value` when currency = USD);
- traffic source `google-play` only on Android, iOS {pct(p['ios_users_direct_share'])} `(direct)`; Android-only events: {', '.join(p['android_only_events'])};
- {lv['anomaly_complete_without_level']:,} `level_complete` events without a level, level 0 fails and level 31 retries (tracking bugs).

## Pipeline architecture

```
config/config.yaml   date range, source table, cost guard (single source of parameters)
sql/NN_*.sql         parameterised BigQuery SQL: @start_suffix/@end_suffix, {{{{source_table}}}}
src/flood_it/
  bq.py              runner: mandatory dry-run -> block above max bytes / monthly budget ->
                     run with maximum_bytes_billed -> log to data/query_cost_log.csv -> CSV cache
  extract.py         runs every SQL file (cache keyed by SQL+params hash)
  validate.py        SQL vs Pandas re-computation + invariants -> results/validation_report.md
  analysis/          metrics.py (pure, unit-tested), sections_b.py (1-4), sections_c.py (5-8)
  figures.py         PNG charts -> figures/
  report.py          README.md + reports/report.md from results/metrics.json
  export.py          Power BI-ready tidy CSVs -> powerbi/data/
  pipeline.py        python -m flood_it run --mode live|cache
tests/               pytest for metric functions, runner guard and cache
notebooks/           presentation notebook reading pipeline outputs
.github/workflows/   CI: tests + full pipeline in cache mode + drift check
```

`extract -> validate -> analyze -> figures -> report -> export`. Cache mode never touches
BigQuery, so anyone can reproduce every number for free.

## Methodology

- **Day convention:** `event_date` (property time zone) for activity, installs and cohorts.
- **Install cohort:** players with `first_open` in the window whose UTC first touch is not before it.
- **Retention:** classic Day-N (active on install day + N); rate = retained / eligible, eligible = install day + N <= last data day (right-censoring). Wilson 95% CIs.
- **DAU/WAU/MAU:** distinct players per day / trailing 7 / trailing 30 days; stickiness only on days with a full window.
- **Revenue:** `event_value_in_usd`, falling back to `value / 1e6` only when currency = USD; LTV curve on a fixed population (installs observable for 30 days).
- **Levels:** completion per attempt (completes / starts) and quit rate (new players whose last level started is L / new players who started L).
- **Churn:** no activity on days 7-30 after install; features = install-day behaviour only (no leakage); logistic regression and depth-4 decision tree, stratified 75/25 split + 5-fold CV, permutation importance.
- **Statistics:** two-proportion z-test (= chi-square 2x2), 95% CI of the difference, Cohen's h; traffic source tested within Android only. Power analysis with statsmodels.
- **Validation:** each headline metric computed by SQL on raw events and by Pandas on extracts; {val['passed']}/{val['checks']} checks PASS. AI mistakes caught during the build: [docs/ai_corrections.md](docs/ai_corrections.md).

## Limitations

{lim}

## Reproduce

```bash
python -m venv .venv
.venv\\Scripts\\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt && pip install -e .
python -m flood_it run --mode cache   # free, offline: rebuilds every CSV, figure and document
python -m pytest -q
# live mode (needs `gcloud auth application-default login` and your project in config/config.yaml)
python -m flood_it run --mode live
python -m flood_it cost               # bytes scanned so far
```

## Figures

![DAU and installs](figures/fig01_dau_installs.png)
![Retention heatmap](figures/fig03_retention_heatmap.png)
![Levels](figures/fig06_levels.png)
![Day-0 engagement](figures/fig07_day0_engagement.png)
![Churn model](figures/fig08_churn_model.png)
"""


def render_report(m: dict) -> str:
    v, r, val = m["revenue"], m["retention"], m["validation"]
    ins = "\n\n".join(f"{i}. {t}" for i, t in enumerate(insights(m), 1))
    rec = "\n".join(f"- {t}" for t in recommendations(m))
    lim = "\n".join(f"- {t}" for t in limitations(m)[:4])
    return f"""# Flood-It: player behaviour & monetisation - short report

*Data: Firebase Analytics export of Flood-It, {m['meta']['date_start']} to {m['meta']['date_end']} (sampled).
All figures generated by the pipeline from `results/metrics.json`; {val['passed']}/{val['checks']} validation checks PASS.*

## Bottom line

New players leave fast - D1 {pct(r['d1_retention'])}, D30 {pct(r['d30_retention'])} - and the decision is made in the
first session and at a few difficulty walls. IAP brings almost nothing (payer rate {pct(v['payer_rate'], 2)}), so
retention and ad engagement are the levers. The two highest-value actions are a level-difficulty rebalance and a
better first minute, each validated by an A/B test.

## Insights

{ins}

## Recommendations

{rec}

## Caveats

{lim}
"""


def run_all(ctx: dict) -> None:
    m = read_metrics()
    links = ctx["cfg"].raw.get("links", {}) or {}
    (ROOT / "README.md").write_text(render_readme(m, links), encoding="utf-8", newline="\n")
    rp = ctx["cfg"].path("reports_dir") / "report.md"
    rp.write_text(render_report(m), encoding="utf-8", newline="\n")
    log.info("README.md and %s written", rp.name)
