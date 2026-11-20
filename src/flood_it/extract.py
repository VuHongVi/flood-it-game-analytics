"""Extract stage: run every registered SQL file through the guarded runner.

Each entry = (cache name, sql file, extra params). Adding a query = adding one line here.
"""
from __future__ import annotations

import pandas as pd

from .bq import BigQueryRunner

QUERIES: list[tuple[str, str, dict]] = [
    ("00_table_inventory", "00_table_inventory.sql", {}),
    ("01_event_counts", "01_event_counts.sql", {}),
    ("02_event_param_keys", "02_event_param_keys.sql", {}),
    ("10_users", "10_users.sql", {}),
    ("11_user_day", "11_user_day.sql", {}),
    ("12_iap", "12_iap.sql", {}),
    ("20_daily_activity", "20_daily_activity.sql", {}),
    ("21_spike_event_mix", "21_spike_event_mix.sql", {"spike_start": "SPIKE0", "spike_end": "SPIKE1"}),
    ("30_retention_cohort", "30_retention_cohort.sql", {"day_ns": "RETENTION_DAYS"}),
    ("40_revenue_summary", "40_revenue_summary.sql", {}),
    ("50_level_stats", "50_level_stats.sql", {}),
    ("51_user_level", "51_user_level.sql", {}),
]


def run_all(runner: BigQueryRunner) -> dict[str, pd.DataFrame]:
    out = {}
    a = runner.cfg.analysis
    for name, sql_file, params in QUERIES:
        sub = {"RETENTION_DAYS": a["retention_days"], "SPIKE0": a["spike_window"][0],
               "SPIKE1": a["spike_window"][1]}
        p = {k: sub.get(v, v) if isinstance(v, str) else v for k, v in params.items()}
        out[name] = runner.query(name, sql_file=sql_file, params=p)
    return out
