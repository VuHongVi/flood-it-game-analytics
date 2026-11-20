"""Single entry point: extract -> validate -> analyze -> figures -> report -> export.

Usage
-----
    python -m flood_it run --mode live      # query BigQuery (dry-run + guard), refresh cache
    python -m flood_it run --mode cache     # 100% offline, reproduces everything from data/cache
    python -m flood_it cost                 # summary of data/query_cost_log.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Callable

import pandas as pd

from .bq import BigQueryRunner, human_bytes
from .config import load_config

log = logging.getLogger("flood_it")

STAGES = ["extract", "validate", "analyze", "figures", "report", "export"]


def _stage_extract(ctx: dict) -> None:
    from . import extract
    ctx["raw"] = extract.run_all(ctx["runner"])


def _stage_validate(ctx: dict) -> None:
    from . import validate
    ctx["validation"] = validate.run_all(ctx)


def _stage_analyze(ctx: dict) -> None:
    from . import analyze
    ctx["metrics"] = analyze.run_all(ctx)


def _stage_figures(ctx: dict) -> None:
    from . import figures
    figures.run_all(ctx)


def _stage_report(ctx: dict) -> None:
    from . import report
    report.run_all(ctx)


def _stage_export(ctx: dict) -> None:
    from . import export
    export.run_all(ctx)


STAGE_FUNCS: dict[str, Callable[[dict], None]] = {
    "extract": _stage_extract, "validate": _stage_validate, "analyze": _stage_analyze,
    "figures": _stage_figures, "report": _stage_report, "export": _stage_export,
}


def run(mode: str, refresh: bool, stages: list[str]) -> dict:
    cfg = load_config()
    ctx: dict = {"cfg": cfg, "mode": mode, "runner": BigQueryRunner(cfg, mode=mode, refresh=refresh)}
    for s in STAGES:
        if s in stages:
            log.info("=== stage: %s ===", s)
            STAGE_FUNCS[s](ctx)
    return ctx


def cost_summary() -> None:
    cfg = load_config()
    p = cfg.path("cost_log")
    if not p.exists():
        print("No cost log yet.")
        return
    df = pd.read_csv(p)
    runs = df[df["action"] == "run"]
    print(f"Real runs: {len(runs)} | bytes billed: {human_bytes(runs['bytes_billed'].sum())} "
          f"| reference cost: ${runs['ref_cost_usd'].sum():.4f} (Sandbox = free)")
    print(df.groupby("action").size().to_string())


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser(prog="flood_it")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the pipeline")
    r.add_argument("--mode", choices=["live", "cache"], default="cache")
    r.add_argument("--refresh", action="store_true", help="ignore cache hits in live mode")
    r.add_argument("--stages", default=",".join(STAGES),
                   help=f"comma list, subset of {STAGES}")
    sub.add_parser("cost", help="show query cost summary")
    a = ap.parse_args(argv)
    if a.cmd == "cost":
        cost_summary()
        return
    stages = [s.strip() for s in a.stages.split(",") if s.strip()]
    bad = set(stages) - set(STAGES)
    if bad:
        sys.exit(f"Unknown stages: {bad}")
    run(a.mode, a.refresh, stages)


if __name__ == "__main__":
    main()
