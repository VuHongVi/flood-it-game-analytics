"""BigQuery runner with a mandatory cost guard and a CSV result cache.

Every query goes through `BigQueryRunner.query()`:

1. Render the SQL template: ``{{source_table}}`` is substituted from config (a table
   name cannot be a query parameter); dates and other values are passed as real
   BigQuery query parameters (``@start_suffix``, ``@end_suffix``, ...).
2. Cache lookup: the cache key is a hash of (rendered SQL + params). If a CSV with a
   matching hash exists we reuse it (live mode) or load it (cache mode).
3. Dry-run (mandatory): the estimated bytes are logged; the query is BLOCKED if it is
   above ``max_bytes_per_query`` or would push this month's total above
   ``monthly_budget_bytes``.
4. Real run with ``maximum_bytes_billed`` as a server-side hard cap.
5. Log bytes processed/billed to data/query_cost_log.csv and save the result CSV.

Mode ``cache`` never creates a BigQuery client, so the pipeline can be reproduced for
free (and in GitHub Actions) from the committed CSVs.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import ROOT, Config, load_config

log = logging.getLogger(__name__)

COST_LOG_FIELDS = [
    "timestamp_utc", "query_name", "sql_hash", "action", "bytes_processed",
    "bytes_billed", "ref_cost_usd", "rows", "job_id", "note",
]


class QueryBlockedError(RuntimeError):
    """Raised when the dry-run estimate violates the cost guard."""


class CacheMissError(RuntimeError):
    """Raised in cache mode when a result is missing or stale."""


# --------------------------------------------------------------------------- helpers
def render_sql(template: str, cfg: Config) -> str:
    """Substitute ``{{name}}`` placeholders that cannot be query parameters."""
    replacements = {"source_table": cfg.bq["source_table"]}

    def _sub(m: re.Match) -> str:
        key = m.group(1).strip()
        if key not in replacements:
            raise KeyError(f"Unknown SQL placeholder {{{{{key}}}}}")
        return replacements[key]

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", _sub, template)


def sql_hash(sql: str, params: dict[str, Any]) -> str:
    # Normalise line endings so the hash is identical on Windows and Linux (CI).
    norm = sql.replace("\r\n", "\n").strip()
    payload = norm + "\n" + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def human_bytes(n: float | None) -> str:
    if n is None:
        return "n/a"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1000:
            return f"{n:,.1f} {unit}"
        n /= 1000
    return f"{n:,.1f} PB"


def _bq_param(name: str, value: Any):
    from google.cloud import bigquery

    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError(f"Empty array parameter {name}")
        t = "INT64" if isinstance(value[0], int) else "FLOAT64" if isinstance(value[0], float) else "STRING"
        return bigquery.ArrayQueryParameter(name, t, list(value))
    if isinstance(value, bool):
        return bigquery.ScalarQueryParameter(name, "BOOL", value)
    if isinstance(value, int):
        return bigquery.ScalarQueryParameter(name, "INT64", value)
    if isinstance(value, float):
        return bigquery.ScalarQueryParameter(name, "FLOAT64", value)
    return bigquery.ScalarQueryParameter(name, "STRING", str(value))


# --------------------------------------------------------------------------- runner
class BigQueryRunner:
    def __init__(self, cfg: Config | None = None, mode: str = "live", refresh: bool = False):
        if mode not in {"live", "cache"}:
            raise ValueError("mode must be 'live' or 'cache'")
        self.cfg = cfg or load_config()
        self.mode = mode
        self.refresh = refresh
        self.cache_dir = self.cfg.path("cache_dir")
        self.manifest_path = self.cache_dir / "manifest.json"
        self.cost_log = self.cfg.path("cost_log")
        self._client = None

    # -- lazy client: cache mode never touches Google credentials
    @property
    def client(self):
        if self.mode == "cache":
            raise RuntimeError("BigQuery client requested in cache mode")
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.cfg.bq["project_id"],
                                           location=self.cfg.bq["location"])
        return self._client

    # -- manifest
    def _manifest(self) -> dict[str, Any]:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {}

    def _save_manifest(self, m: dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")

    # -- cost log
    def _log_cost(self, **row: Any) -> None:
        new = not self.cost_log.exists()
        row.setdefault("timestamp_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        b = row.get("bytes_billed") or row.get("bytes_processed") or 0
        row.setdefault("ref_cost_usd", round(b / 2**40 * self.cfg.bq["reference_usd_per_tib"], 6))
        with open(self.cost_log, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COST_LOG_FIELDS)
            if new:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in COST_LOG_FIELDS})

    def month_bytes_billed(self) -> int:
        """Bytes billed by real runs in the current calendar month (from the log)."""
        if not self.cost_log.exists():
            return 0
        df = pd.read_csv(self.cost_log)
        if df.empty:
            return 0
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        df = df[(df["action"] == "run") & df["timestamp_utc"].astype(str).str.startswith(month)]
        return int(pd.to_numeric(df["bytes_billed"], errors="coerce").fillna(0).sum())

    # -- public API
    def load_sql(self, sql_file: str) -> str:
        return (self.cfg.path("sql_dir") / sql_file).read_text(encoding="utf-8")

    def dry_run(self, sql: str, params: dict[str, Any]) -> int:
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False,
            query_parameters=[_bq_param(k, v) for k, v in params.items()],
        )
        job = self.client.query(sql, job_config=job_config)
        return int(job.total_bytes_processed or 0)

    def query(self, name: str, sql_file: str | None = None, sql: str | None = None,
              params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Run (or load from cache) a query and return a DataFrame."""
        if (sql_file is None) == (sql is None):
            raise ValueError("Pass exactly one of sql_file / sql")
        template = self.load_sql(sql_file) if sql_file else sql
        p = {**self.cfg.default_params(), **(params or {})}
        # Only send parameters actually referenced in the SQL (BigQuery rejects unused ones? no,
        # but keeping the hash stable and minimal is cleaner).
        rendered = render_sql(template, self.cfg)
        p = {k: v for k, v in p.items() if re.search(rf"@{k}\b", rendered)}
        h = sql_hash(rendered, p)
        csv_path = self.cache_dir / f"{name}.csv"
        manifest = self._manifest()
        entry = manifest.get(name, {})
        cache_ok = csv_path.exists() and entry.get("sql_hash") == h

        if self.mode == "cache":
            if not cache_ok:
                reason = "missing" if not csv_path.exists() else "stale (SQL/params changed)"
                raise CacheMissError(f"Cache for '{name}' is {reason}. Re-run in live mode.")
            log.info("[cache] %s <- %s", name, csv_path.name)
            return pd.read_csv(csv_path)

        if cache_ok and not self.refresh:
            log.info("[cache-hit] %s (hash %s), no BigQuery call", name, h)
            self._log_cost(query_name=name, sql_hash=h, action="cache_hit",
                           bytes_processed=0, bytes_billed=0, rows=entry.get("rows"))
            return pd.read_csv(csv_path)

        # 1) mandatory dry-run + guard
        est = self.dry_run(rendered, p)
        self._log_cost(query_name=name, sql_hash=h, action="dry_run", bytes_processed=est,
                       bytes_billed=0, ref_cost_usd=0)
        limit = int(self.cfg.bq["max_bytes_per_query"])
        budget = int(self.cfg.bq["monthly_budget_bytes"])
        used = self.month_bytes_billed()
        log.info("[dry-run] %s will scan %s (limit %s, month used %s / %s)", name,
                 human_bytes(est), human_bytes(limit), human_bytes(used), human_bytes(budget))
        if est > limit:
            self._log_cost(query_name=name, sql_hash=h, action="blocked", bytes_processed=est,
                           bytes_billed=0, ref_cost_usd=0, note="over max_bytes_per_query")
            raise QueryBlockedError(f"{name}: estimate {human_bytes(est)} > limit {human_bytes(limit)}")
        if used + est > budget:
            self._log_cost(query_name=name, sql_hash=h, action="blocked", bytes_processed=est,
                           bytes_billed=0, ref_cost_usd=0, note="over monthly budget")
            raise QueryBlockedError(f"{name}: monthly budget would be exceeded")

        # 2) real run with a server-side cap
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=int(self.cfg.bq["maximum_bytes_billed"]),
            query_parameters=[_bq_param(k, v) for k, v in p.items()],
        )
        job = self.client.query(rendered, job_config=job_config)
        df = job.result().to_dataframe(create_bqstorage_client=False)
        self._log_cost(query_name=name, sql_hash=h, action="run",
                       bytes_processed=job.total_bytes_processed,
                       bytes_billed=job.total_bytes_billed, rows=len(df), job_id=job.job_id)
        log.info("[run] %s: %s rows, billed %s", name, len(df), human_bytes(job.total_bytes_billed))

        df.to_csv(csv_path, index=False, lineterminator="\n")
        manifest[name] = {
            "sql_hash": h, "sql_file": sql_file, "rows": len(df),
            "bytes_processed": job.total_bytes_processed,
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._save_manifest(manifest)
        return pd.read_csv(csv_path)  # re-read so live and cache modes return identical dtypes
