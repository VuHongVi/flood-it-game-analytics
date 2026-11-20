"""Unit tests for the BigQuery runner (no network: dry_run / client are mocked)."""
import copy
import json

import pandas as pd
import pytest

from flood_it import bq
from flood_it.config import Config, load_config


@pytest.fixture
def cfg(tmp_path):
    raw = copy.deepcopy(load_config().raw)
    raw["paths"] = {k: str(tmp_path / v) for k, v in raw["paths"].items()}
    raw["paths"]["sql_dir"] = str(tmp_path / "sql")
    raw["bigquery"]["max_bytes_per_query"] = 1_000
    raw["bigquery"]["monthly_budget_bytes"] = 5_000
    return Config(raw)


def test_render_sql_substitutes_table(cfg):
    out = bq.render_sql("SELECT 1 FROM `{{ source_table }}`", cfg)
    assert cfg.bq["source_table"] in out


def test_render_sql_unknown_placeholder(cfg):
    with pytest.raises(KeyError):
        bq.render_sql("{{nope}}", cfg)


def test_hash_ignores_line_endings_but_not_params():
    a = bq.sql_hash("SELECT 1\r\nFROM t", {"x": 1})
    b = bq.sql_hash("SELECT 1\nFROM t", {"x": 1})
    c = bq.sql_hash("SELECT 1\nFROM t", {"x": 2})
    assert a == b and a != c


def test_guard_blocks_large_query(cfg, monkeypatch):
    r = bq.BigQueryRunner(cfg, mode="live")
    monkeypatch.setattr(r, "dry_run", lambda sql, p: 10_000)
    with pytest.raises(bq.QueryBlockedError):
        r.query("big", sql="SELECT 1 WHERE @start_suffix = ''")
    log = pd.read_csv(cfg.path("cost_log"))
    assert list(log["action"]) == ["dry_run", "blocked"]


def test_guard_blocks_monthly_budget(cfg, monkeypatch):
    r = bq.BigQueryRunner(cfg, mode="live")
    r._log_cost(query_name="prev", sql_hash="x", action="run", bytes_processed=4_900, bytes_billed=4_900)
    monkeypatch.setattr(r, "dry_run", lambda sql, p: 500)
    with pytest.raises(bq.QueryBlockedError, match="monthly"):
        r.query("q", sql="SELECT 1")


def test_cache_mode_reads_csv_and_detects_stale(cfg):
    r = bq.BigQueryRunner(cfg, mode="cache")
    sql = "SELECT 1 AS a WHERE _TABLE_SUFFIX >= @start_suffix"
    with pytest.raises(bq.CacheMissError, match="missing"):
        r.query("q", sql=sql)
    # write a cache entry with the right hash
    rendered = bq.render_sql(sql, cfg)
    h = bq.sql_hash(rendered, {"start_suffix": cfg.analysis["start_suffix"]})
    pd.DataFrame({"a": [1]}).to_csv(r.cache_dir / "q.csv", index=False)
    r.manifest_path.write_text(json.dumps({"q": {"sql_hash": h}}))
    assert r.query("q", sql=sql)["a"].tolist() == [1]
    # change SQL -> stale
    with pytest.raises(bq.CacheMissError, match="stale"):
        r.query("q", sql=sql + " AND 1=1")


def test_cache_mode_never_builds_client(cfg):
    r = bq.BigQueryRunner(cfg, mode="cache")
    with pytest.raises(RuntimeError):
        _ = r.client
