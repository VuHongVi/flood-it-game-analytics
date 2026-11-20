"""Small I/O helpers shared by analysis modules (LF endings, stable float formatting)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import load_config


def save_csv(df: pd.DataFrame, name: str, subdir: str | None = None) -> Path:
    base = load_config().path("data_dir")
    p = (base / subdir if subdir else base) / f"{name}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, lineterminator="\n", float_format="%.6g")
    return p


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return o.strftime("%Y-%m-%d")
    raise TypeError(type(o))


def write_metrics(metrics: dict) -> Path:
    p = load_config().path("results_dir") / "metrics.json"
    p.write_text(json.dumps(metrics, indent=2, default=_default, ensure_ascii=False) + "\n",
                 encoding="utf-8", newline="\n")
    return p


def read_metrics() -> dict:
    p = load_config().path("results_dir") / "metrics.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
