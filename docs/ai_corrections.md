# AI-assisted analysis: errors caught and fixed

This project was built with an AI coding assistant. Every metric is cross-checked (SQL vs
Pandas, unit tests, sanity checks), and the mistakes the assistant made — and how they were
caught — are logged here. Keeping this log is part of the method: AI output is treated as a
draft that must be verified.

| # | Where | What the AI wrote | How it was caught | Fix |
|---|-------|-------------------|-------------------|-----|
| 1 | `sql/40_revenue_summary.sql` | `COALESCE(platform,'ALL') AS platform ... GROUP BY ROLLUP(platform)` | SQL-vs-Pandas check: the `ALL` row did not join; SQL returned a NULL platform | BigQuery resolves `ROLLUP(platform)` to the SELECT **alias**, so the total row stays NULL. Renamed the alias and grouped by `ev.platform`. |
| 2 | `analysis/metrics.py::ltv_curve` | Cumulative LTV with a different eligible population at each day N | Sanity check: LTV D30 ($0.0027) < LTV D7 ($0.0035), impossible for a cumulative metric | Headline curve now uses a **fixed population** (installs observable for 30 days); the per-N population version is kept as a labelled sensitivity. |
| 3 | `analysis/metrics.py::flag_spikes` | Spike = DAU > 1.3 x centred 7-day rolling median | Manual review of the daily table: 2018-06-28 (DAU 1,219, 0 installs) was not flagged because neighbouring spike days inflated the rolling median | Spike = DAU > 1.5 x **period** median; added events-per-DAU to expose the sampling mechanism. |
| 5 | `analysis/sections_b.py::growth` | "New-player share of DAU" = first-seen players / DAU (24%) | Review of stage B: the share was 47% in the first 14 days vs 20% later - players acquired before the window are "first seen" at its start (left-censoring) | Replaced by `first_open` installs / DAU on non-spike days (8.5%). |
| 6 | `analysis/sections_c.py::levels` | Quit rate at level 30 = 100% | Visual check of the level chart | Level 30 is the last level: stopping there is finishing, so its quit rate is blanked. |
| 7 | `drift.py` (CI reproducibility check) | String columns compared with `astype(str)` | The check reported drift on a file that `git status` showed unchanged | pandas 3 string dtype keeps NaN after `astype(str)` and NaN != NaN; missing values are now filled before comparing. |
| 4 | `sql/20_daily_activity.sql` (first draft) | Correlated scalar sub-queries in the SELECT list | Code review before running (BigQuery cannot de-correlate this pattern reliably) | Rewritten as pre-aggregated CTEs + joins; result validated against Pandas (0 difference on 114 days). |
| 8 | `dashboard.py::chart-power` | Log-scale y-axis and x-axis with automatic d3 ticks | Dashboard self-check reported `labels_overlap` (log ticks 800, 900, 1k... and x ticks every 0.5 pp printed as duplicate "+2 pp") | Explicit tick values (MDE values on x; 1k/3k/10k/30k on y) and shorter point labels. |
