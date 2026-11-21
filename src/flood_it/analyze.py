"""Analyze stage: runs every section and writes results/metrics.json."""
from __future__ import annotations

import logging

import pandas as pd

from .analysis import metrics as M
from .analysis import sections_b
from .analysis.io import write_metrics

log = logging.getLogger(__name__)


def run_all(ctx: dict) -> dict:
    cfg, raw = ctx["cfg"], ctx["raw"]
    a = cfg.analysis
    start = pd.Timestamp(a["start_suffix"])
    end = pd.Timestamp(a["end_suffix"])
    cohort = M.build_install_cohort(raw["10_users"], start)
    ctx["cohort"] = cohort

    metrics: dict = {"meta": {
        "source_table": cfg.bq["source_table"], "date_start": str(start.date()), "date_end": str(end.date()),
        "day_convention": "event_date (property time zone)",
        "note": "All counts are from a SAMPLED export (constant 50,000 events/day); ratios are the reliable outputs.",
    }}
    metrics["profile"] = sections_b.profile(raw, start, end)
    metrics["growth"] = sections_b.growth(raw)
    metrics["retention"] = sections_b.retention(raw, cohort, a["retention_days"], end,
                                                 metrics["growth"]["spike_dates"])
    metrics["revenue"] = sections_b.revenue(raw, cohort, a["ltv_days"], end)
    # later sections (levels, segments, churn, stats) are registered in stage C
    from .analysis import sections_c
    ctx["metrics_b_retention_d1"] = metrics["retention"]["d1_retention"]
    ctx["metrics_b_retention_d7"] = metrics["retention"]["d7_retention"]
    metrics.update(sections_c.run_all(ctx, cohort, start, end))
    if "validation" in ctx:
        metrics["validation"] = ctx["validation"]["summary"]
    p = write_metrics(metrics)
    log.info("metrics written to %s", p)
    return metrics
