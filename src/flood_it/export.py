"""Export stage: Power BI-ready tidy CSVs (filled in stage E)."""
from __future__ import annotations


def run_all(ctx: dict) -> None:
    try:
        from .powerbi import build
    except ImportError:
        return
    build(ctx)
