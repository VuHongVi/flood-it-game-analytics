# Flood-It Game Analytics (Firebase / GA4 → BigQuery → Python)

> Work in progress — this README is regenerated from `results/metrics.json` at the end of the pipeline.

## Pipeline architecture

```
config/config.yaml      single source of parameters (date range, source table, cost guard)
sql/NN_*.sql            parameterised BigQuery SQL (@start_suffix, @end_suffix, {{source_table}})
src/flood_it/
  bq.py                 BigQuery runner: mandatory dry-run, byte guard, maximum_bytes_billed,
                        cost log (data/query_cost_log.csv), CSV cache keyed by SQL hash
  extract.py            runs every SQL file -> data/cache/*.csv
  validate.py           SQL vs Pandas cross-checks -> results/validation_report.md (PASS/FAIL)
  analysis/             one module per section (growth, retention, revenue, levels, churn, stats)
  figures.py            matplotlib charts -> figures/
  report.py             README / report / CV bullets rendered from results/metrics.json
  export.py             tidy, Power BI-ready CSVs -> powerbi/data/
  pipeline.py           one command: extract -> validate -> analyze -> figures -> report -> export
tests/                  pytest (metric functions, runner guard, cache mode)
notebooks/              presentation notebook reading pipeline outputs
```

## Run

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements.txt && pip install -e .
python -m flood_it run --mode cache                  # free, offline reproduction
python -m flood_it run --mode live                   # query BigQuery (needs gcloud ADC)
python -m flood_it cost                              # bytes scanned so far
```
