"""Build the Claude dashboard (Data artifact type) from pipeline outputs.

    python -m flood_it.dashboard [--asset-url /_blob/<id>]

Writes dashboard/:
  data_bundle.json      every table the page uses, copied verbatim from powerbi/data/*.csv
  store/*.json          documents for the artifact store (dash/meta, datasets/<id>, files/index.html)
The page computes nothing: each number is drawn from one CSV row (kpi_metrics.csv holds every
scalar of results/metrics.json). Titles, definitions and insights come from narrative.py, the
same text the Power BI layout uses.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html import escape

import pandas as pd

from . import narrative as N
from .analysis.io import read_metrics
from .config import ROOT, load_config

DATASETS = {  # id: (powerbi/data table, title, description)
    "kpi": ("kpi_metrics", "Headline metrics", "Every scalar of results/metrics.json, one row per metric_key."),
    "daily": ("fact_daily_activity", "Daily activity", "DAU, installs, WAU, MAU and stickiness per event_date."),
    "ret_cohort": ("fact_retention_cohort", "Retention by install week", "Retained and eligible installs per weekly cohort and day N."),
    "ret_curve": ("fact_retention_curve", "Retention curve", "Pooled Day-N retention, days 0-30, with Wilson 95% bounds."),
    "monet": ("fact_monetization_platform", "Monetisation by platform", "Active players, player-days, payers, purchases and IAP revenue."),
    "ltv": ("fact_ltv_curve", "LTV curve", "Cumulative IAP revenue per install, fixed 30-day population."),
    "levels": ("fact_level_funnel", "Level funnel", "Starts, completes and new-player quits for progression levels 1-30."),
    "segments": ("fact_day0_segments", "Install-day segments", "Retention and churn by install-day engagement, sessions, levels and mode."),
    "model_perf": ("fact_churn_model_performance", "Churn model performance", "Cross-validated and test AUC per model."),
    "roc": ("fact_churn_roc", "Churn ROC curve", "True positive rate on a 51-point false-positive grid, test set."),
    "importance": ("fact_churn_feature_importance", "Churn feature importance", "Permutation AUC drop per feature and model."),
    "ab_tests": ("fact_ab_observational_tests", "Observational tests", "Two-proportion tests: platform and Android traffic source."),
    "power": ("fact_ab_power_analysis", "A/B sample size", "Players per arm and run time for a D1 retention test."),
}

# chart id -> (dataset ids, table spec: [(field, header, fmt)], row key)
TABLE_SPECS = {
    "dau": ("daily", [("date", "Date", "text"), ("dau", "DAU", "num0"), ("installs", "Installs", "num0"),
                      ("returning_dau", "Returning", "num0"), ("events_per_dau", "Events / DAU", "num1"),
                      ("is_spike_day", "Spike day", "flag")], "date"),
    "stickiness": ("daily", [("date", "Date", "text"), ("dau", "DAU", "num0"), ("mau", "MAU", "num0"),
                             ("stickiness", "Stickiness", "pct1"), ("clean_stickiness_window", "Spike-free window", "flag")], "date"),
    "heatmap": ("ret_cohort", [("cohort_week", "Cohort week", "text"), ("day_n", "Day", "num0"), ("cohort_users", "Installs", "num0"),
                               ("eligible_users", "Eligible", "num0"), ("retained_users", "Retained", "num0"),
                               ("retention", "Retention", "pct1")], "cohort_week,day_n"),
    "curve": ("ret_curve", [("day_n", "Day", "num0"), ("eligible_users", "Eligible", "num0"), ("retained_users", "Retained", "num0"),
                            ("retention", "Retention", "pct1"), ("ci_low", "CI low", "pct1"), ("ci_high", "CI high", "pct1")], "day_n"),
    "monet": ("monet", [("platform", "Platform", "text"), ("active_users", "Active players", "num0"), ("user_days", "Player-days", "num0"),
                        ("payers", "Payers", "num0"), ("purchases", "Purchases", "num0"), ("revenue_usd", "Revenue", "usd2")], "platform"),
    "ltv": ("ltv", [("day_n", "Day", "num0"), ("eligible_users", "Installs", "num0"), ("payers", "Payers", "num0"),
                    ("revenue_usd", "Revenue", "usd2"), ("ltv_usd", "LTV / install", "usd4")], "day_n"),
    "reach": ("levels", [("level", "Level", "num0"), ("users_started", "Players started", "num0"),
                         ("users_completed", "Players completed", "num0"), ("reach_rate", "Reach vs level 1", "pct1")], "level"),
    "difficulty": ("levels", [("level", "Level", "num0"), ("starts", "Attempts", "num0"), ("completes", "Completes", "num0"),
                              ("completion_per_attempt", "Completion / attempt", "pct1"), ("new_players_started", "New players started", "num0"),
                              ("new_players_last_level", "Stopped here", "num0"), ("quit_rate_at_level", "Quit rate", "pct1")], "level"),
    "seg_eng": ("segments", [("dimension", "Dimension", "text"), ("segment", "Segment", "text"), ("players", "Players", "num0"),
                             ("d1_retention", "D1", "pct1"), ("d7_retention", "D7", "pct1"), ("churn_rate", "Churn D7-30", "pct1")], "dimension,segment"),
    "seg_mode": ("segments", [("dimension", "Dimension", "text"), ("segment", "Segment", "text"), ("players", "Players", "num0"),
                              ("d1_retention", "D1", "pct1"), ("d7_retention", "D7", "pct1"), ("churn_rate", "Churn D7-30", "pct1")], "dimension,segment"),
    "roc": ("model_perf", [("model", "Model", "text"), ("cv_auc_mean", "CV AUC", "dec3"), ("cv_auc_std", "CV AUC sd", "dec3"),
                           ("test_auc", "Test AUC", "dec3"), ("test_n", "Test players", "num0"), ("test_churn_rate", "Test churn rate", "pct1")], "model"),
    "importance": ("importance", [("model", "Model", "text"), ("feature", "Feature", "text"),
                                  ("permutation_auc_drop", "AUC drop", "dec4"), ("std_coefficient", "Std. coefficient", "dec3"),
                                  ("gini_importance", "Tree importance", "dec3")], "model,feature"),
    "tests": ("ab_tests", [("comparison", "Comparison", "text"), ("metric", "Metric", "text"), ("group_a", "A", "text"),
                           ("n_a", "n A", "num0"), ("rate_a", "Rate A", "pct1"), ("group_b", "B", "text"), ("n_b", "n B", "num0"),
                           ("rate_b", "Rate B", "pct1"), ("diff_a_minus_b", "A - B", "pp1"), ("diff_ci_low", "CI low", "pp1"),
                           ("diff_ci_high", "CI high", "pp1"), ("p_value", "p", "p"), ("cohens_h", "Cohen's h", "dec3")], "comparison,metric"),
    "power": ("power", [("mde_abs", "MDE", "pp1"), ("mde_relative", "Relative MDE", "pct1"), ("n_per_arm", "Players / arm", "num0"),
                        ("total_n", "Total", "num0"), ("days_needed_at_sample_volume", "Days at sample volume", "num0")], "mde_abs"),
}
CHART_SOURCES = {"dau": "daily", "stickiness": "daily", "heatmap": "ret_cohort", "curve": "ret_curve", "monet": "monet",
                 "ltv": "ltv", "reach": "levels", "difficulty": "levels", "seg_eng": "segments", "seg_mode": "segments",
                 "roc": "roc model_perf", "importance": "importance", "tests": "ab_tests", "power": "power"}


def _table_html(chart_id: str) -> str:
    src, cols, key = TABLE_SPECS[chart_id]
    ths = "".join(f'<th data-field="{f}" data-fmt="{fmt}">{escape(h)}</th>' for f, h, fmt in cols)
    filt = ""
    if chart_id == "seg_eng":
        filt = ' data-filter="dimension=Day-0 engagement time"'
    if chart_id == "seg_mode":
        filt = ' data-filter="dimension=Day-0 game mode"'
    if chart_id == "importance":
        filt = ' data-filter="model=logistic_regression"'
    return (f'<details class="fi-details"><summary>Table view</summary><div class="fi-tw">'
            f'<table class="fi-table" data-source="{src}" data-row-key="{key}"{filt}><thead><tr>{ths}</tr></thead>'
            f'<tbody data-draw="tbl"></tbody></table></div></details>')


def build_html(flat: dict) -> str:
    sec_html = []
    for s in N.SECTIONS:
        if s["id"] == "overview":
            cards = "".join(
                f'<div class="fi-kpi" id="kpi-{escape(key.replace(".", "-"))}"><div class="fi-kpi-label">{escape(label)}</div>'
                f'<div class="fi-kpi-value"><span data-draw="kpi" data-source="kpi" data-field="value" data-where="metric_key={key}" data-fmt="{fmt}">—</span></div>'
                f'<div class="fi-kpi-def">{escape(d)}</div><div class="fi-src">kpi_metrics.csv · {escape(key)}</div></div>'
                for label, key, fmt, d in s["kpis"])
            sec_html.append(f'<section class="fi-section" id="overview"><h2>Overview</h2><div class="fi-kpis">{cards}</div></section>')
            continue
        charts = []
        for ch in s["charts"]:
            cid = ch["id"]
            charts.append(
                f'<article class="fi-card" id="{cid}"><h3>{escape(ch["title"])}</h3>'
                f'<p class="fi-def">{escape(ch["definition"])}</p>'
                f'<div class="fi-chart" data-draw="chart-{cid}" data-source="{CHART_SOURCES[cid]}"></div>'
                f'<p class="fi-insight">{N.render_html(ch["insight"], flat)}</p>'
                f'<p class="fi-src">Source: {escape(ch["source"])}</p>{_table_html(cid)}</article>')
        sec_html.append(f'<section class="fi-section" id="{s["id"]}"><h2>{escape(s["title"])}</h2><div class="fi-grid">{"".join(charts)}</div></section>')
    lim = "".join(f"<li>{N.render_html(t, flat)}</li>" for t in N.LIMITATIONS)
    sec_html.append(f'<section class="fi-section" id="limitations"><h2>Data limitations</h2><ul class="fi-lim">{lim}</ul>'
                    '<p class="fi-src">Pipeline, SQL and validation: github.com/VuHongVi/flood-it-game-analytics · '
                    'every number is a row of powerbi/data/*.csv (kpi_metrics.csv = results/metrics.json).</p></section>')
    nav = "".join(f'<a href="#{s["id"]}">{escape(s["title"])}</a>' for s in N.SECTIONS) + '<a href="#limitations">Limitations</a>'
    summary = N.render_html(N.SECTIONS[0]["summary"], flat)
    return HTML_HEAD + f"""
<div class="fi">
  <header class="fi-head" id="top">
    <p class="fi-eyebrow">Firebase Analytics export · BigQuery · 2018-06-12 to 2018-10-03 · sampled</p>
    <h1>Flood-It Game Analytics</h1>
    <p class="fi-lede">{summary}</p>
    <nav class="fi-nav">{nav}</nav>
  </header>
  {''.join(sec_html)}
</div>
""" + HTML_SCRIPT


HTML_HEAD = """<meta name="dash-one-writer">
<style>
.fi{display:flex;flex-direction:column;gap:var(--cds-gap-xl);font-family:var(--font-anthropic-sans);color:var(--color-fg)}
.fi h1{font-family:var(--font-anthropic-serif);font-weight:400;font-size:var(--cds-font-size-title);margin:0;text-wrap:balance}
.fi h2{font-size:var(--cds-font-size-heading);font-weight:var(--cds-font-weight-medium);margin:0 0 var(--cds-gap-md)}
.fi h3{font-size:var(--cds-font-size-body);font-weight:var(--cds-font-weight-medium);margin:0}
.fi-eyebrow{margin:0 0 var(--cds-gap-xs);color:var(--color-fg-muted);font-size:var(--cds-font-size-caption);letter-spacing:.04em;text-transform:uppercase}
.fi-lede{max-width:70ch;margin:var(--cds-gap-sm) 0;font-size:var(--cds-font-size-body);line-height:1.5}
.fi-nav{display:flex;flex-wrap:wrap;gap:var(--cds-gap-sm) var(--cds-gap-md);font-size:var(--cds-font-size-caption)}
.fi-nav a{color:var(--color-fg-muted);text-decoration:none;border-bottom:1px solid var(--color-border-line)}
.fi-nav a:hover,.fi-nav a:focus-visible{color:var(--color-fg)}
.fi-kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:var(--cds-gap-md)}
.fi-kpi{background:var(--color-panel);border:1px solid var(--color-border-line);border-radius:var(--cds-radius);padding:var(--cds-pad-md);display:flex;flex-direction:column;gap:var(--cds-gap-xs);min-width:0}
.fi-kpi-label{font-size:var(--cds-font-size-caption);color:var(--color-fg-muted)}
.fi-kpi-value{font-family:var(--font-anthropic-serif);font-weight:400;font-size:var(--cds-font-size-title);font-variant-numeric:tabular-nums;line-height:1.1}
.fi-kpi-def{font-size:var(--cds-font-size-caption);color:var(--color-fg-muted);line-height:1.35}
.fi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:var(--cds-gap-lg)}
.fi-card{background:var(--color-panel);border:1px solid var(--color-border-line);border-radius:var(--cds-radius);padding:var(--cds-pad-lg);display:flex;flex-direction:column;gap:var(--cds-gap-sm);min-width:0}
.fi-def{margin:0;font-size:var(--cds-font-size-caption);color:var(--color-fg-muted);line-height:1.4}
.fi-chart{position:relative;min-height:260px;width:100%}
.fi-chart svg{display:block;width:100%;overflow:visible}
.fi-chart .axis text{fill:var(--cds-text-secondary);font-size:11px}
.fi-chart .axis path,.fi-chart .axis line{stroke:var(--cds-chart-axis)}
.fi-chart .grid line{stroke:var(--cds-chart-grid)}
.fi-chart .grid path{stroke:none}
.fi-chart .lbl{fill:var(--color-fg);font-size:11px}
.fi-chart .lbl-muted{fill:var(--cds-text-secondary);font-size:11px}
.fi-legend{display:flex;flex-wrap:wrap;gap:var(--cds-gap-md);font-size:var(--cds-font-size-caption);color:var(--color-fg-muted);margin-bottom:var(--cds-gap-xs)}
.fi-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.fi-tip{position:absolute;pointer-events:none;background:var(--cds-surface-popover);border:1px solid var(--cds-border);box-shadow:var(--cds-shadow-popover);border-radius:var(--cds-radius);padding:6px 8px;font-size:12px;line-height:1.4;white-space:nowrap;z-index:5}
.fi-tip b{font-weight:var(--cds-font-weight-medium)}
.fi-insight{margin:0;font-size:var(--cds-font-size-body);line-height:1.5}
.fi-insight .num,.fi-lede .num,.fi-lim .num{font-weight:var(--cds-font-weight-medium);font-variant-numeric:tabular-nums}
.fi-src{margin:0;font-size:var(--cds-font-size-caption);color:var(--color-fg-muted)}
.fi-details summary{cursor:pointer;font-size:var(--cds-font-size-caption);color:var(--color-fg-muted)}
.fi-tw{overflow:auto;max-height:320px;margin-top:var(--cds-gap-xs)}
.fi-table{border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums;width:100%}
.fi-table th,.fi-table td{padding:4px 8px;border-bottom:1px solid var(--color-border-line);text-align:right;white-space:nowrap}
.fi-table th:first-child,.fi-table td:first-child{text-align:left}
.fi-table th{position:sticky;top:0;background:var(--color-panel);font-weight:var(--cds-font-weight-medium)}
.fi-lim{margin:0;padding-left:1.2em;display:flex;flex-direction:column;gap:var(--cds-gap-xs);max-width:80ch;line-height:1.5}
.fi-empty{color:var(--color-fg-muted);font-size:var(--cds-font-size-caption);padding:var(--cds-pad-md) 0}
</style>
"""

HTML_SCRIPT = r"""
<script>
// ---- loaders: every dataset is one table of the bundle, copied verbatim from powerbi/data/*.csv
const FI_TABLES = __TABLES__;
Object.entries(FI_TABLES).forEach(([id, table]) => {
  dash.loader(id, {description: `Rows of powerbi/data/${table}.csv (copied verbatim into the bundle).`,
                   fn: ({answer}) => ({columns: answer.columns[table], rows: answer.tables[table]})});
});

// ---- formatting only (no arithmetic beyond unit scaling for display)
window.fiFmt = (v, f) => {
  if (v === null || v === undefined || v === '' || (typeof v === 'number' && isNaN(v))) return '—';
  const n = +v;
  switch (f) {
    case 'pct0': return d3.format('.0%')(n);
    case 'pct1': return d3.format('.1%')(n);
    case 'pct2': return d3.format('.2%')(n);
    case 'pp1': return (n >= 0 ? '+' : '−') + d3.format('.1f')(Math.abs(n * 100)) + ' pp';
    case 'num0': return d3.format(',.0f')(n);
    case 'num1': return d3.format(',.1f')(n);
    case 'dec2': return d3.format('.2f')(n);
    case 'dec3': return d3.format('.3f')(n);
    case 'dec4': return d3.format('.4f')(n);
    case 'usd2': return '$' + d3.format(',.2f')(n);
    case 'usd4': return '$' + d3.format(',.4f')(n);
    case 'usd5': return '$' + d3.format(',.5f')(n);
    case 'p': return n < 0.001 ? '< 0.001' : d3.format('.3f')(n);
    case 'flag': return n ? 'yes' : '';
    default: return String(v);
  }
};
window.fiRows = (id) => { const d = dash.data(id); return d.status === 'ok' ? d.data : null; };
window.fiStatus = (el, ids) => {
  for (const id of ids) {
    const s = dash.data(id).status;
    if (s === 'error') { el.replaceChildren(Object.assign(document.createElement('p'), {className: 'fi-empty', textContent: 'This data failed to load.'})); return false; }
    if (s !== 'ok') { el.textContent = '—'; return false; }
  }
  return true;
};
window.fiParseDate = d3.utcParse('%Y-%m-%d');

// ---- KPI numbers inside text and cards
dash.draw('kpi', (el) => {
  const rows = fiRows('kpi');
  if (!rows) { el.textContent = '—'; return; }
  const key = (el.getAttribute('data-where') || '').replace('metric_key=', '');
  const r = rows.find((x) => x.metric_key === key);
  const f = el.getAttribute('data-fmt');
  el.textContent = r ? (f === 'text' ? r.value_text : fiFmt(r.value, f)) : '—';
});

// ---- generic table view
dash.draw('tbl', (tbody) => {
  const table = tbody.closest('table');
  const id = table.getAttribute('data-source');
  let rows = fiRows(id);
  tbody.replaceChildren();
  if (!rows) return;
  const filt = table.getAttribute('data-filter');
  if (filt) { const [k, v] = filt.split('='); rows = rows.filter((r) => String(r[k]) === v); }
  const keys = table.getAttribute('data-row-key').split(',');
  const ths = [...table.querySelectorAll('th')];
  rows.forEach((r) => {
    const tr = document.createElement('tr');
    tr.setAttribute('data-key', keys.map((k) => encodeURIComponent(String(r[k]))).join(','));
    ths.forEach((th) => {
      const td = document.createElement('td');
      td.textContent = fiFmt(r[th.getAttribute('data-field')], th.getAttribute('data-fmt'));
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
});

// ---- chart helpers
window.fiTip = (el) => {
  let tip = el.querySelector('.fi-tip');
  if (!tip) { tip = document.createElement('div'); tip.className = 'fi-tip'; tip.hidden = true; el.appendChild(tip); }
  return {
    show(ev, lines) {
      tip.replaceChildren();
      lines.forEach(([k, v], i) => { const div = document.createElement('div'); if (i === 0) { const b = document.createElement('b'); b.textContent = k; div.appendChild(b); } else { div.textContent = `${k}: ${v}`; } tip.appendChild(div); });
      tip.hidden = false;
      const box = el.getBoundingClientRect();
      let x = ev.clientX - box.left + 12, y = ev.clientY - box.top + 12;
      if (x + tip.offsetWidth > box.width) x = Math.max(0, ev.clientX - box.left - tip.offsetWidth - 12);
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    },
    hide() { tip.hidden = true; },
  };
};
window.fiLegend = (el, items) => {
  const lg = document.createElement('div'); lg.className = 'fi-legend';
  items.forEach(([label, color, shape]) => { const s = document.createElement('span'); const i = document.createElement('i'); i.style.background = color; if (shape === 'line') { i.style.height = '2px'; i.style.verticalAlign = '3px'; } s.appendChild(i); s.appendChild(document.createTextNode(label)); lg.appendChild(s); });
  el.appendChild(lg);
};
window.fiSvg = (el, height, m) => {
  const w = Math.max(280, el.clientWidth);
  const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${w} ${height}`).attr('height', height).attr('role', 'img');
  return {svg, w, h: height, iw: w - m.l - m.r, ih: height - m.t - m.b, g: svg.append('g').attr('transform', `translate(${m.l},${m.t})`)};
};
window.fiAxes = (c, x, y, {xTicks, yFmt, xFmt, yTicks = 5}) => {
  c.g.append('g').attr('class', 'grid').call(d3.axisLeft(y).ticks(yTicks).tickSize(-c.iw).tickFormat(''));
  const xa = d3.axisBottom(x); if (xTicks) xa.ticks(xTicks); if (xFmt) xa.tickFormat(xFmt);
  c.g.append('g').attr('class', 'axis').attr('transform', `translate(0,${c.ih})`).call(xa);
  c.g.append('g').attr('class', 'axis').call(d3.axisLeft(y).ticks(yTicks).tickFormat(yFmt));
};

// ---- Growth
dash.draw('chart-dau', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['daily'])) return;
  const rows = fiRows('daily').map((r) => ({...r, d: fiParseDate(r.date)}));
  const C = dash.colors;
  fiLegend(el, [['DAU', C[0], 'line'], ['Spike day (artefact)', C[1]], ['Installs', C[2]]]);
  const m = {t: 8, r: 12, b: 24, l: 44};
  const c = fiSvg(el, 200, m);
  c.svg.attr('aria-label', 'Daily active players with spike days marked');
  const x = d3.scaleUtc().domain(d3.extent(rows, (r) => r.d)).range([0, c.iw]);
  const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.dau)]).nice().range([c.ih, 0]);
  fiAxes(c, x, y, {xTicks: 5, yFmt: d3.format(',')});
  c.g.append('path').datum(rows).attr('fill', 'none').style('stroke', C[0]).attr('stroke-width', 2).attr('d', d3.line().x((r) => x(r.d)).y((r) => y(r.dau)));
  c.g.selectAll('.sp').data(rows.filter((r) => +r.is_spike_day === 1)).join('circle').attr('r', 4.5).attr('cx', (r) => x(r.d)).attr('cy', (r) => y(r.dau)).style('fill', C[1]).style('stroke', 'var(--color-panel)').attr('stroke-width', 2);
  const m2 = {t: 6, r: 12, b: 24, l: 44};
  const c2 = fiSvg(el, 110, m2);
  c2.svg.attr('aria-label', 'Installs per day');
  const y2 = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.installs)]).nice().range([c2.ih, 0]);
  fiAxes(c2, x, y2, {xTicks: 5, yFmt: d3.format(','), yTicks: 3});
  const bw = Math.max(1, c2.iw / rows.length - 1);
  c2.g.selectAll('rect').data(rows).join('rect').attr('x', (r) => x(r.d) - bw / 2).attr('width', bw).attr('y', (r) => y2(r.installs)).attr('height', (r) => c2.ih - y2(r.installs)).style('fill', C[2]);
  const tip = fiTip(el);
  const fmtD = d3.utcFormat('%a %d %b %Y');
  [c, c2].forEach((cc) => {
    cc.svg.on('mousemove', (ev) => {
      const [px] = d3.pointer(ev, cc.g.node());
      const d0 = x.invert(px); const i = d3.bisector((r) => r.d).center(rows, d0); const r = rows[i];
      tip.show(ev, [[fmtD(r.d)], ['DAU', fiFmt(r.dau, 'num0')], ['Installs', fiFmt(r.installs, 'num0')], ['Events per DAU', fiFmt(r.events_per_dau, 'num1')], ...(+r.is_spike_day ? [['Spike day', 'yes']] : [])]);
    }).on('mouseleave', () => tip.hide());
  });
});

dash.draw('chart-stickiness', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['daily'])) return;
  const rows = fiRows('daily').filter((r) => +r.full_30d_window === 1).map((r) => ({...r, d: fiParseDate(r.date)}));
  const C = dash.colors;
  fiLegend(el, [['Stickiness (DAU / MAU)', C[0], 'line'], ['Window contains a spike day', 'var(--cds-chart-muted)', 'line']]);
  const c = fiSvg(el, 240, {t: 8, r: 12, b: 24, l: 44});
  c.svg.attr('aria-label', 'Daily stickiness');
  const x = d3.scaleUtc().domain(d3.extent(rows, (r) => r.d)).range([0, c.iw]);
  const y = d3.scaleLinear().domain([0, Math.max(0.15, d3.max(rows, (r) => r.stickiness))]).nice().range([c.ih, 0]);
  fiAxes(c, x, y, {xTicks: 5, yFmt: d3.format('.0%')});
  const line = d3.line().x((r) => x(r.d)).y((r) => y(r.stickiness));
  c.g.append('path').datum(rows).attr('fill', 'none').style('stroke', 'var(--cds-chart-muted)').attr('stroke-width', 2).attr('d', line);
  c.g.append('path').datum(rows.filter((r) => +r.clean_stickiness_window === 1)).attr('fill', 'none').style('stroke', C[0]).attr('stroke-width', 2).attr('d', line);
  const tip = fiTip(el); const fmtD = d3.utcFormat('%d %b %Y');
  c.svg.on('mousemove', (ev) => { const [px] = d3.pointer(ev, c.g.node()); const r = rows[d3.bisector((q) => q.d).center(rows, x.invert(px))]; tip.show(ev, [[fmtD(r.d)], ['Stickiness', fiFmt(r.stickiness, 'pct1')], ['DAU', fiFmt(r.dau, 'num0')], ['MAU', fiFmt(r.mau, 'num0')]]); }).on('mouseleave', () => tip.hide());
});

// ---- Retention
dash.draw('chart-heatmap', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['ret_cohort'])) return;
  const rows = fiRows('ret_cohort');
  const weeks = [...new Set(rows.map((r) => r.cohort_week))];
  const days = [...new Set(rows.map((r) => +r.day_n))].sort((a, b) => a - b);
  const sizes = new Map(rows.filter((r) => +r.day_n === days[0]).map((r) => [r.cohort_week, r.cohort_users]));
  const m = {t: 22, r: 8, b: 4, l: 124};
  const rowH = 20;
  const c = fiSvg(el, m.t + m.b + rowH * weeks.length, m);
  c.svg.attr('aria-label', 'Retention heatmap by weekly install cohort');
  const x = d3.scaleBand().domain(days).range([0, c.iw]).padding(0.06);
  const y = d3.scaleBand().domain(weeks).range([0, c.ih]).padding(0.08);
  const maxR = d3.max(rows, (r) => (r.retention === '' || r.retention === null ? 0 : +r.retention)) || 1;
  c.g.selectAll('.hx').data(days).join('text').attr('class', 'lbl-muted').attr('x', (d) => x(d) + x.bandwidth() / 2).attr('y', -8).attr('text-anchor', 'middle').text((d) => `D${d}`);
  c.g.selectAll('.hy').data(weeks).join('text').attr('class', 'lbl-muted').attr('x', -8).attr('y', (w) => y(w) + y.bandwidth() / 2 + 4).attr('text-anchor', 'end').text((w) => `${w} (n=${fiFmt(sizes.get(w), 'num0')})`);
  const tip = fiTip(el);
  const cells = c.g.selectAll('.cell').data(rows).join('g').attr('transform', (r) => `translate(${x(+r.day_n)},${y(r.cohort_week)})`);
  const has = (r) => r.retention !== '' && r.retention !== null && r.retention !== undefined && !isNaN(+r.retention) && +r.eligible_users > 0;
  cells.append('rect').attr('width', x.bandwidth()).attr('height', y.bandwidth()).attr('rx', 3)
    .style('fill', (r) => (has(r) ? dash.colors[0] : 'var(--color-border-line)')).style('fill-opacity', (r) => (has(r) ? 0.12 + 0.88 * (+r.retention / maxR) : 0.35));
  cells.append('text').attr('x', x.bandwidth() / 2).attr('y', y.bandwidth() / 2 + 4).attr('text-anchor', 'middle').style('font-size', '10.5px')
    .style('fill', (r) => (has(r) && +r.retention / maxR > 0.55 ? 'var(--color-bg)' : 'var(--color-fg)')).text((r) => (has(r) ? fiFmt(r.retention, 'pct1') : 'censored'));
  cells.on('mousemove', (ev, r) => tip.show(ev, [[`Cohort ${r.cohort_week}, day ${r.day_n}`], ['Retention', has(r) ? fiFmt(r.retention, 'pct1') : 'censored'], ['Retained', fiFmt(r.retained_users, 'num0')], ['Eligible', fiFmt(r.eligible_users, 'num0')]])).on('mouseleave', () => tip.hide());
});

dash.draw('chart-curve', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['ret_curve'])) return;
  const rows = fiRows('ret_curve').filter((r) => +r.day_n >= 1);
  const C = dash.colors;
  fiLegend(el, [['Retention', C[0], 'line'], ['95% interval', C[0]]]);
  const c = fiSvg(el, 240, {t: 8, r: 12, b: 28, l: 44});
  c.svg.attr('aria-label', 'Retention curve days 1 to 30');
  const x = d3.scaleLinear().domain([1, d3.max(rows, (r) => +r.day_n)]).range([0, c.iw]);
  const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => +r.ci_high)]).nice().range([c.ih, 0]);
  fiAxes(c, x, y, {xTicks: 6, yFmt: d3.format('.0%'), xFmt: (d) => `D${d}`});
  c.g.append('path').datum(rows).style('fill', C[0]).style('fill-opacity', 0.15).attr('d', d3.area().x((r) => x(+r.day_n)).y0((r) => y(+r.ci_low)).y1((r) => y(+r.ci_high)));
  c.g.append('path').datum(rows).attr('fill', 'none').style('stroke', C[0]).attr('stroke-width', 2).attr('d', d3.line().x((r) => x(+r.day_n)).y((r) => y(+r.retention)));
  const tip = fiTip(el);
  c.svg.on('mousemove', (ev) => { const [px] = d3.pointer(ev, c.g.node()); const n = Math.round(x.invert(px)); const r = rows.find((q) => +q.day_n === n); if (!r) return; tip.show(ev, [[`Day ${r.day_n}`], ['Retention', fiFmt(r.retention, 'pct1')], ['95% CI', `${fiFmt(r.ci_low, 'pct1')} – ${fiFmt(r.ci_high, 'pct1')}`], ['Eligible', fiFmt(r.eligible_users, 'num0')]]); }).on('mouseleave', () => tip.hide());
});

// ---- Revenue
window.fiBars = (el, rows, {label, series, yFmt, aria, height = 240, labelFmt}) => {
  const C = dash.colors;
  if (series.length > 1) fiLegend(el, series.map((s, i) => [s.name, C[s.color ?? i]]));
  const c = fiSvg(el, height, {t: 14, r: 8, b: 34, l: 48});
  c.svg.attr('aria-label', aria);
  const x0 = d3.scaleBand().domain(rows.map(label)).range([0, c.iw]).padding(0.25);
  const x1 = d3.scaleBand().domain(series.map((s) => s.key)).range([0, x0.bandwidth()]).padding(0.08);
  const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => d3.max(series, (s) => +r[s.key] || 0))]).nice().range([c.ih, 0]);
  fiAxes(c, x0, y, {yFmt});
  const tip = fiTip(el);
  const g = c.g.selectAll('.grp').data(rows).join('g').attr('transform', (r) => `translate(${x0(label(r))},0)`);
  series.forEach((s, i) => {
    g.append('rect').attr('x', x1(s.key)).attr('width', x1.bandwidth()).attr('y', (r) => y(+r[s.key] || 0)).attr('height', (r) => c.ih - y(+r[s.key] || 0)).attr('rx', 3).style('fill', C[s.color ?? i])
      .on('mousemove', (ev, r) => tip.show(ev, [[label(r)], [s.name, fiFmt(r[s.key], s.fmt)], ...(s.extra ? s.extra(r) : [])])).on('mouseleave', () => tip.hide());
    if (labelFmt) g.append('text').attr('class', 'lbl').attr('x', x1(s.key) + x1.bandwidth() / 2).attr('y', (r) => y(+r[s.key] || 0) - 4).attr('text-anchor', 'middle').text((r) => fiFmt(r[s.key], s.fmt));
  });
  return c;
};

dash.draw('chart-monet', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['monet'])) return;
  const rows = fiRows('monet');
  fiBars(el, rows, {label: (r) => r.platform, aria: 'IAP revenue by platform', yFmt: (v) => '$' + d3.format(',.0f')(v), labelFmt: true,
    series: [{key: 'revenue_usd', name: 'IAP revenue', fmt: 'usd2', extra: (r) => [['Payers', fiFmt(r.payers, 'num0')], ['Active players', fiFmt(r.active_users, 'num0')], ['Purchases', fiFmt(r.purchases, 'num0')]]}]});
});

dash.draw('chart-ltv', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['ltv'])) return;
  const rows = fiRows('ltv');
  const C = dash.colors;
  const c = fiSvg(el, 240, {t: 8, r: 12, b: 28, l: 56});
  c.svg.attr('aria-label', 'Cumulative LTV per install');
  const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => +r.day_n)]).range([0, c.iw]);
  const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => +r.ltv_usd)]).nice().range([c.ih, 0]);
  fiAxes(c, x, y, {xTicks: 6, yFmt: (v) => '$' + d3.format('.4f')(v), xFmt: (d) => `D${d}`});
  c.g.append('path').datum(rows).attr('fill', 'none').style('stroke', C[0]).attr('stroke-width', 2).attr('d', d3.line().curve(d3.curveStepAfter).x((r) => x(+r.day_n)).y((r) => y(+r.ltv_usd)));
  const tip = fiTip(el);
  c.svg.on('mousemove', (ev) => { const [px] = d3.pointer(ev, c.g.node()); const n = Math.max(0, Math.round(x.invert(px))); const r = rows.find((q) => +q.day_n === n); if (!r) return; tip.show(ev, [[`Day ${r.day_n}`], ['LTV / install', fiFmt(r.ltv_usd, 'usd4')], ['Revenue', fiFmt(r.revenue_usd, 'usd2')], ['Payers', fiFmt(r.payers, 'num0')], ['Installs', fiFmt(r.eligible_users, 'num0')]]); }).on('mouseleave', () => tip.hide());
});

// ---- Levels
dash.draw('chart-reach', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['levels'])) return;
  const rows = fiRows('levels');
  fiBars(el, rows, {label: (r) => String(r.level), aria: 'Share of level-1 players starting each level', yFmt: d3.format('.0%'),
    series: [{key: 'reach_rate', name: 'Reach vs level 1', fmt: 'pct1', extra: (r) => [['Players started', fiFmt(r.users_started, 'num0')]]}]});
});

dash.draw('chart-difficulty', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['levels'])) return;
  const rows = fiRows('levels');
  const C = dash.colors;
  fiLegend(el, [['Completion per attempt', C[2]], ['Quit rate of new players', C[1], 'line']]);
  const c = fiSvg(el, 240, {t: 8, r: 8, b: 34, l: 44});
  c.svg.attr('aria-label', 'Completion per attempt and quit rate by level');
  const x = d3.scaleBand().domain(rows.map((r) => String(r.level))).range([0, c.iw]).padding(0.2);
  const y = d3.scaleLinear().domain([0, 1]).range([c.ih, 0]);
  fiAxes(c, x, y, {yFmt: d3.format('.0%')});
  const tip = fiTip(el);
  c.g.selectAll('rect').data(rows).join('rect').attr('x', (r) => x(String(r.level))).attr('width', x.bandwidth()).attr('y', (r) => y(+r.completion_per_attempt)).attr('height', (r) => c.ih - y(+r.completion_per_attempt)).attr('rx', 2).style('fill', C[2])
    .on('mousemove', (ev, r) => tip.show(ev, [[`Level ${r.level}`], ['Completion / attempt', fiFmt(r.completion_per_attempt, 'pct1')], ['Quit rate', fiFmt(r.quit_rate_at_level, 'pct1')], ['Attempts', fiFmt(r.starts, 'num0')]])).on('mouseleave', () => tip.hide());
  const q = rows.filter((r) => r.quit_rate_at_level !== '' && r.quit_rate_at_level !== null && !isNaN(+r.quit_rate_at_level) && r.quit_rate_at_level !== undefined);
  c.g.append('path').datum(q).attr('fill', 'none').style('stroke', C[1]).attr('stroke-width', 2).attr('d', d3.line().x((r) => x(String(r.level)) + x.bandwidth() / 2).y((r) => y(+r.quit_rate_at_level)));
  c.g.selectAll('.qd').data(q).join('circle').attr('r', 3).attr('cx', (r) => x(String(r.level)) + x.bandwidth() / 2).attr('cy', (r) => y(+r.quit_rate_at_level)).style('fill', C[1]);
});

// ---- Segments
dash.draw('chart-seg_eng', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['segments'])) return;
  const rows = fiRows('segments').filter((r) => r.dimension === 'Day-0 engagement time').sort((a, b) => a.segment_order - b.segment_order);
  fiBars(el, rows, {label: (r) => r.segment, aria: 'D1 and D7 retention by install-day engagement time', yFmt: d3.format('.0%'), labelFmt: true,
    series: [{key: 'd1_retention', name: 'D1 retention', fmt: 'pct1', extra: (r) => [['Players', fiFmt(r.players, 'num0')]]},
             {key: 'd7_retention', name: 'D7 retention', fmt: 'pct1', extra: (r) => [['Players', fiFmt(r.players, 'num0')]]}]});
});

dash.draw('chart-seg_mode', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['segments'])) return;
  const rows = fiRows('segments').filter((r) => r.dimension === 'Day-0 game mode').sort((a, b) => b.d1_retention - a.d1_retention);
  fiBars(el, rows, {label: (r) => r.segment, aria: 'D1 retention by install-day game mode', yFmt: d3.format('.0%'), labelFmt: true,
    series: [{key: 'd1_retention', name: 'D1 retention', fmt: 'pct1', extra: (r) => [['Players', fiFmt(r.players, 'num0')], ['D7', fiFmt(r.d7_retention, 'pct1')]]}]});
});

// ---- Churn
dash.draw('chart-roc', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['roc', 'model_perf'])) return;
  const rows = fiRows('roc'); const perf = fiRows('model_perf');
  const C = dash.colors;
  const models = ['logistic_regression', 'decision_tree'];
  const auc = (mm) => fiFmt((perf.find((p) => p.model === mm) || {}).test_auc, 'dec2');
  fiLegend(el, [[`Logistic regression (AUC ${auc(models[0])})`, C[0], 'line'], [`Decision tree (AUC ${auc(models[1])})`, C[1], 'line'], ['Random', 'var(--cds-chart-reference)', 'line']]);
  const c = fiSvg(el, 260, {t: 8, r: 12, b: 32, l: 44});
  c.svg.attr('aria-label', 'ROC curves of the churn models');
  const x = d3.scaleLinear().domain([0, 1]).range([0, c.iw]); const y = d3.scaleLinear().domain([0, 1]).range([c.ih, 0]);
  fiAxes(c, x, y, {xTicks: 5, yFmt: d3.format('.0%'), xFmt: d3.format('.0%')});
  c.g.append('line').attr('x1', 0).attr('y1', c.ih).attr('x2', c.iw).attr('y2', 0).style('stroke', 'var(--cds-chart-reference)').attr('stroke-dasharray', '4 4');
  models.forEach((mm, i) => c.g.append('path').datum(rows.filter((r) => r.model === mm)).attr('fill', 'none').style('stroke', C[i]).attr('stroke-width', 2).attr('d', d3.line().x((r) => x(+r.fpr)).y((r) => y(+r.tpr))));
  const tip = fiTip(el);
  c.svg.on('mousemove', (ev) => { const [px] = d3.pointer(ev, c.g.node()); const f = Math.round(x.invert(px) * 50) / 50; const pts = models.map((mm) => rows.find((r) => r.model === mm && Math.abs(+r.fpr - f) < 1e-9)); if (!pts[0]) return; tip.show(ev, [[`False positive rate ${fiFmt(f, 'pct0')}`], ['Logistic TPR', fiFmt(pts[0].tpr, 'pct1')], ['Tree TPR', fiFmt(pts[1] && pts[1].tpr, 'pct1')]]); }).on('mouseleave', () => tip.hide());
});

dash.draw('chart-importance', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['importance'])) return;
  const rows = fiRows('importance').filter((r) => r.model === 'logistic_regression').sort((a, b) => b.permutation_auc_drop - a.permutation_auc_drop).slice(0, 8);
  const C = dash.colors;
  const rowH = 26; const m = {t: 4, r: 56, b: 24, l: 150};
  const c = fiSvg(el, m.t + m.b + rowH * rows.length, m);
  c.svg.attr('aria-label', 'Top churn features by permutation importance');
  const y = d3.scaleBand().domain(rows.map((r) => r.feature)).range([0, c.ih]).padding(0.25);
  const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => +r.permutation_auc_drop)]).nice().range([0, c.iw]);
  c.g.append('g').attr('class', 'grid').attr('transform', `translate(0,${c.ih})`).call(d3.axisBottom(x).ticks(4).tickSize(-c.ih).tickFormat(''));
  c.g.append('g').attr('class', 'axis').attr('transform', `translate(0,${c.ih})`).call(d3.axisBottom(x).ticks(4).tickFormat(d3.format('.3f')));
  c.g.selectAll('.fl').data(rows).join('text').attr('class', 'lbl-muted').attr('x', -8).attr('y', (r) => y(r.feature) + y.bandwidth() / 2 + 4).attr('text-anchor', 'end').text((r) => r.feature);
  const tip = fiTip(el);
  c.g.selectAll('rect').data(rows).join('rect').attr('x', 0).attr('y', (r) => y(r.feature)).attr('height', y.bandwidth()).attr('width', (r) => Math.max(0, x(+r.permutation_auc_drop))).attr('rx', 3).style('fill', C[0])
    .on('mousemove', (ev, r) => tip.show(ev, [[r.feature], ['AUC drop', fiFmt(r.permutation_auc_drop, 'dec4')], ['Std. coefficient', fiFmt(r.std_coefficient, 'dec3')]])).on('mouseleave', () => tip.hide());
  c.g.selectAll('.vl').data(rows).join('text').attr('class', 'lbl').attr('x', (r) => Math.max(0, x(+r.permutation_auc_drop)) + 6).attr('y', (r) => y(r.feature) + y.bandwidth() / 2 + 4).text((r) => fiFmt(r.permutation_auc_drop, 'dec3'));
});

// ---- A/B
dash.draw('chart-tests', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['ab_tests'])) return;
  const rows = fiRows('ab_tests');
  const C = dash.colors;
  const lab = (r) => `${r.comparison.replace('Traffic source (Android only): ', 'Android: ').replace('Platform: ', '')} · ${r.metric}`;
  const rowH = 36; const m = {t: 10, r: 16, b: 28, l: 200};
  const c = fiSvg(el, m.t + m.b + rowH * rows.length, m);
  c.svg.attr('aria-label', 'Differences in retention with 95% confidence intervals');
  const lo = d3.min(rows, (r) => +r.diff_ci_low), hi = d3.max(rows, (r) => +r.diff_ci_high);
  const x = d3.scaleLinear().domain([Math.min(lo, 0), Math.max(hi, 0)]).nice().range([0, c.iw]);
  const y = d3.scaleBand().domain(rows.map(lab)).range([0, c.ih]).padding(0.4);
  c.g.append('g').attr('class', 'axis').attr('transform', `translate(0,${c.ih})`).call(d3.axisBottom(x).ticks(5).tickFormat((v) => d3.format('+.0f')(v * 100) + ' pp'));
  c.g.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', 0).attr('y2', c.ih).style('stroke', 'var(--cds-chart-reference)');
  c.g.selectAll('.tl').data(rows).join('text').attr('class', 'lbl-muted').attr('x', -8).attr('y', (r) => y(lab(r)) + y.bandwidth() / 2 + 4).attr('text-anchor', 'end').text(lab);
  const tip = fiTip(el);
  const g = c.g.selectAll('.ci').data(rows).join('g');
  g.append('line').attr('x1', (r) => x(+r.diff_ci_low)).attr('x2', (r) => x(+r.diff_ci_high)).attr('y1', (r) => y(lab(r)) + y.bandwidth() / 2).attr('y2', (r) => y(lab(r)) + y.bandwidth() / 2).style('stroke', C[0]).attr('stroke-width', 2);
  g.append('circle').attr('r', 5).attr('cx', (r) => x(+r.diff_a_minus_b)).attr('cy', (r) => y(lab(r)) + y.bandwidth() / 2).style('fill', C[0]).style('stroke', 'var(--color-panel)').attr('stroke-width', 2);
  g.on('mousemove', (ev, r) => tip.show(ev, [[lab(r)], [`${r.group_a}`, fiFmt(r.rate_a, 'pct1')], [`${r.group_b}`, fiFmt(r.rate_b, 'pct1')], ['Difference', fiFmt(r.diff_a_minus_b, 'pp1')], ['95% CI', `${fiFmt(r.diff_ci_low, 'pp1')} to ${fiFmt(r.diff_ci_high, 'pp1')}`], ['p', fiFmt(r.p_value, 'p')]])).on('mouseleave', () => tip.hide());
});

dash.draw('chart-power', (el) => {
  el.replaceChildren();
  if (!fiStatus(el, ['power'])) return;
  const rows = fiRows('power');
  const C = dash.colors;
  const c = fiSvg(el, 240, {t: 18, r: 24, b: 30, l: 56});
  c.svg.attr('aria-label', 'Players per arm needed by minimum detectable effect');
  const x = d3.scaleLinear().domain(d3.extent(rows, (r) => +r.mde_abs)).range([0, c.iw]);
  const y = d3.scaleLog().domain([d3.min(rows, (r) => +r.n_per_arm) * 0.7, d3.max(rows, (r) => +r.n_per_arm) * 1.4]).range([c.ih, 0]);
  fiAxes(c, x, y, {yFmt: d3.format('~s'), xFmt: (v) => '+' + d3.format('.0f')(v * 100) + ' pp', xTicks: rows.length, yTicks: 4});
  c.g.append('path').datum(rows).attr('fill', 'none').style('stroke', C[0]).attr('stroke-width', 2).attr('d', d3.line().x((r) => x(+r.mde_abs)).y((r) => y(+r.n_per_arm)));
  c.g.selectAll('.pt').data(rows).join('circle').attr('r', 4.5).attr('cx', (r) => x(+r.mde_abs)).attr('cy', (r) => y(+r.n_per_arm)).style('fill', C[0]).style('stroke', 'var(--color-panel)').attr('stroke-width', 2);
  c.g.selectAll('.pl').data(rows).join('text').attr('class', 'lbl').attr('x', (r) => x(+r.mde_abs)).attr('y', (r) => y(+r.n_per_arm) - 10).attr('text-anchor', (r, i) => (i === rows.length - 1 ? 'end' : 'start')).text((r) => `${fiFmt(r.n_per_arm, 'num0')} / arm`);
  const tip = fiTip(el);
  c.g.selectAll('.pt').on('mousemove', (ev, r) => tip.show(ev, [[`MDE ${fiFmt(r.mde_abs, 'pp1')}`], ['Players per arm', fiFmt(r.n_per_arm, 'num0')], ['Days at sample volume', fiFmt(r.days_needed_at_sample_volume, 'num0')]])).on('mouseleave', () => tip.hide());
});
</script>
"""


def build(asset_url: str | None) -> None:
    cfg = load_config()
    pb = cfg.path("powerbi_dir") / "data"
    out = ROOT / "dashboard"
    (out / "store").mkdir(parents=True, exist_ok=True)
    tables, columns = {}, {}
    for _, (table, _, _) in DATASETS.items():
        df = pd.read_csv(pb / f"{table}.csv", keep_default_na=False, na_values=[""])
        df = df.astype(object).where(df.notna(), None)
        tables[table] = df.to_dict(orient="records")
        columns[table] = list(df.columns)
    (out / "data_bundle.json").write_text(json.dumps({"generated_from": "powerbi/data/*.csv", "tables": tables,
                                                      "columns": columns}, separators=(",", ":"), allow_nan=False),
                                          encoding="utf-8", newline="\n")
    flat = N.flatten({k: v for k, v in read_metrics().items() if k != "meta"})
    html = build_html(flat).replace("__TABLES__", json.dumps({k: v[0] for k, v in DATASETS.items()}))
    (out / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (out / "store" / "files_index.json").write_text(json.dumps({"text": html}), encoding="utf-8", newline="\n")
    (out / "store" / "dash_meta.json").write_text(json.dumps({"title": "Flood-It Game Analytics", "lang": "en"}), encoding="utf-8", newline="\n")
    if asset_url:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for did, (table, title, desc) in DATASETS.items():
            doc = {"title": title, "description": f"{desc} File: powerbi/data/{table}.csv.",
                   "source": {"kind": "file", "url": asset_url, "name": "data_bundle.json", "format": "json"},
                   "updated": {"at": now, "by": "flood_it pipeline (python -m flood_it run)"}, "fixed": True}
            (out / "store" / f"dataset_{did}.json").write_text(json.dumps(doc), encoding="utf-8", newline="\n")
    print("dashboard built:", out, f"html {len(html)/1024:.0f} KB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset-url")
    build(ap.parse_args().asset_url)


if __name__ == "__main__":
    main()
