"""Build and execute notebooks/flood_it_analysis.ipynb from pipeline outputs.

    python -m flood_it.notebook

The notebook only READS results/metrics.json, data/*.csv and figures/ - it never recomputes
or queries, so it always shows exactly what the pipeline produced.
"""
from __future__ import annotations

import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

from .config import ROOT

MD, CODE = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell


def build() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        MD("# Flood-It game analytics - presentation notebook\n\n"
           "Reads the outputs of `python -m flood_it run` (metrics.json, data/*.csv, figures/). "
           "No numbers are computed here, so the notebook always matches the README, report and dashboard."),
        CODE("import json, pandas as pd\nfrom pathlib import Path\nfrom IPython.display import Image, display, Markdown\n"
             "ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
             "m = json.loads((ROOT / 'results/metrics.json').read_text(encoding='utf-8'))\n"
             "csv = lambda n: pd.read_csv(ROOT / 'data' / f'{n}.csv')\n"
             "fig = lambda n: display(Image(filename=str(ROOT / 'figures' / f'{n}.png')))\n"
             "pd.set_option('display.max_columns', 20); pd.set_option('display.width', 160)"),
        MD("## 1. Data understanding\nThe export is sampled (constant events per day); most players were acquired "
           "before the window; some new players lack `first_open`."),
        CODE("pd.Series(m['profile']).to_frame('value').head(30)"),
        CODE("csv('p1_event_catalog').head(15)"),
        CODE("csv('p1_user_segments')"),
        CODE("csv('p1_traffic_source_by_platform')"),
        MD("## 2. Growth\nDAU spikes are an artefact: `screen_view` drops on those days and the fixed event "
           "budget is spread across more players."),
        CODE("fig('fig01_dau_installs'); fig('fig02_stickiness')"),
        CODE("display(csv('p2_dau_spikes')); csv('p2_spike_event_mix').head(10)"),
        MD("## 3. Retention (right-censored players excluded)"),
        CODE("fig('fig03_retention_heatmap'); fig('fig04_retention_curve')"),
        CODE("{k: v for k, v in m['retention'].items() if 'retention' in k}"),
        MD("## 4. Revenue & LTV"),
        CODE("display(csv('p4_monetization_kpis')); fig('fig05_ltv_curve')"),
        CODE("csv('p4_iap_transactions')[['activity_date','platform','currency','value_param','event_value_in_usd','revenue_usd','revenue_source','product_id']]"),
        MD("## 5. Levels"),
        CODE("fig('fig06_levels'); csv('p5_level_funnel')[['level','users_started','reach_rate','completion_per_attempt','quit_rate_at_level']]"),
        CODE("display(csv('p5_level_anomalies')); csv('p5_quickplay_boards')"),
        MD("## 6. Segments"),
        CODE("fig('fig07_day0_engagement'); display(csv('p6_day0_segments')); csv('p6_payer_vs_nonpayer')"),
        MD("## 7. Churn prediction\nChurned = no activity on day 7-30; features = install-day behaviour only."),
        CODE("fig('fig08_churn_model'); display(csv('p7_model_performance')); csv('p7_risk_deciles')"),
        CODE("print((ROOT / 'results/churn_tree_rules.txt').read_text())"),
        MD("## 8. Observational tests & A/B design\nObservational comparisons, not randomised experiments."),
        CODE("display(csv('p8_observational_tests')); fig('fig09_power'); csv('p8_power_analysis')"),
        MD("## 9. Validation"),
        CODE("display(Markdown((ROOT / 'results/validation_report.md').read_text(encoding='utf-8')))"),
    ]
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    return nb


def main() -> None:
    nb = build()
    ExecutePreprocessor(timeout=300, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT / "notebooks")}})
    out = ROOT / "notebooks" / "flood_it_analysis.ipynb"
    nbf.write(nb, out)
    print("written", out)


if __name__ == "__main__":
    main()
