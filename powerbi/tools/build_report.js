#!/usr/bin/env node
// Generates the Flood-It Power BI report pages (PBIR) from the approved spec in
// _brief/report-spec.md. Usage: node build_report.js <path-to-FloodIt.Report>
// Every number shown comes from a model measure/column; text is verbatim from powerbi/layout.md.
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const REPORT = path.resolve(process.argv[2] || 'FloodIt.Report');
const DEF = path.join(REPORT, 'definition');
if (!fs.existsSync(path.join(DEF, 'report.json'))) throw new Error('Not a .Report folder: ' + REPORT);

// ---------------------------------------------------------------- constants
const W = 1920, H = 1080, MARGIN = 32, GUTTER = 24, SNAP = 8, COLS = 12, ROWS = 12;
const C = {
  bg: '#FCFCFB', text: '#0B0B0B', muted: '#52514E', card: '#FFFFFF', line: '#E6E4DF',
  blue: '#2A78D6', orange: '#EB6834', aqua: '#1BAF7A', heatLo: '#CDE2FB', heatHi: '#0D366B',
  blueTint: '#EEF4FC', orangeTint: '#FDF0EA', ciBlue: '#8DB8EC',
};
const SCHEMA = {
  page: 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json',
  visual: 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json',
  pages: 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json',
};
const M = '_Measures';

// deterministic ids so re-running produces stable diffs
const hid = (s, n = 20) => crypto.createHash('sha1').update(s).digest('hex').slice(0, n);
const filterId = (s) => 'Filter' + hid('f:' + s, 24);

// ---------------------------------------------------------------- literal helpers
const lit = (v) => ({ expr: { Literal: { Value: v } } });
const str = (s) => lit(`'${String(s).replace(/'/g, "''")}'`);
const num = (n) => lit(`${n}D`);
const int = (n) => lit(`${n}L`);
const bool = (b) => lit(b ? 'true' : 'false');
const color = (hex) => ({ solid: { color: str(hex) } });

// ---------------------------------------------------------------- field helpers
const measure = (m, t = M) => ({ field: { Measure: { Expression: { SourceRef: { Entity: t } }, Property: m } }, queryRef: `${t}.${m}`, nativeQueryRef: m });
const column = (t, c) => ({ field: { Column: { Expression: { SourceRef: { Entity: t } }, Property: c } }, queryRef: `${t}.${c}`, nativeQueryRef: c });
const AGG = { Sum: 0, Avg: 1, Min: 3, Max: 4 };
const agg = (t, c, fn) => ({ field: { Aggregation: { Expression: { Column: { Expression: { SourceRef: { Entity: t } }, Property: c } }, Function: AGG[fn] } }, queryRef: `${fn}(${t}.${c})`, nativeQueryRef: `${fn === 'Avg' ? 'Average' : fn} of ${c}` });
const colRef = (t, c) => ({ Column: { Expression: { SourceRef: { Entity: t } }, Property: c } });

// ---------------------------------------------------------------- filters (visual level)
function catFilter(key, t, c, valueLiteral) {
  return {
    name: filterId(key), field: colRef(t, c), type: 'Categorical',
    filter: { Version: 2, From: [{ Name: 'f', Entity: t, Type: 0 }],
      Where: [{ Condition: { In: { Expressions: [{ Column: { Expression: { SourceRef: { Source: 'f' } }, Property: c } }], Values: [[{ Literal: { Value: valueLiteral } }]] } } }] },
    howCreated: 'User',
  };
}
function betweenFilter(key, t, c, lo, hi) {
  return {
    name: filterId(key), field: colRef(t, c), type: 'Advanced',
    filter: { Version: 2, From: [{ Name: 'f', Entity: t, Type: 0 }],
      Where: [{ Condition: { Between: { Expression: { Column: { Expression: { SourceRef: { Source: 'f' } }, Property: c } }, LowerBound: { Literal: { Value: lo } }, UpperBound: { Literal: { Value: hi } } } } }] },
    howCreated: 'User',
  };
}
function topNFilter(key, t, c, orderCol, n) {
  return {
    name: filterId(key), field: colRef(t, c), type: 'TopN',
    filter: { Version: 2,
      From: [
        { Name: 'subquery', Expression: { Subquery: { Query: { Version: 2, From: [{ Name: 'f', Entity: t, Type: 0 }],
          Select: [{ Column: { Expression: { SourceRef: { Source: 'f' } }, Property: c }, Name: 'field' }],
          OrderBy: [{ Direction: 2, Expression: { Aggregation: { Expression: { Column: { Expression: { SourceRef: { Source: 'f' } }, Property: orderCol } }, Function: 0 } } }],
          Top: n } } }, Type: 2 },
        { Name: 'g', Entity: t, Type: 0 },
      ],
      Where: [{ Condition: { In: { Expressions: [{ Column: { Expression: { SourceRef: { Source: 'g' } }, Property: c } }], Table: { SourceRef: { Source: 'subquery' } } } } }] },
    howCreated: 'User',
  };
}

// ---------------------------------------------------------------- layout
const cw = (W - 2 * MARGIN - (COLS - 1) * GUTTER) / COLS;
const rh = (H - 2 * MARGIN - (ROWS - 1) * GUTTER) / ROWS;
const snap = (v) => Math.round(v / SNAP) * SNAP;
function rect([c1, r1, c2, r2]) {
  const x = snap(MARGIN + (c1 - 1) * (cw + GUTTER));
  const y = snap(MARGIN + (r1 - 1) * (rh + GUTTER));
  const x2 = snap(MARGIN + (c2 - 1) * (cw + GUTTER) - GUTTER);
  const y2 = snap(MARGIN + (r2 - 1) * (rh + GUTTER) - GUTTER);
  return { x, y, width: x2 - x, height: y2 - y };
}
function slot(r, i, of) { // split along the longer axis
  if (r.width >= r.height) { const w = (r.width - (of - 1) * GUTTER) / of; return { ...r, x: snap(r.x + i * (w + GUTTER)), width: snap(w) }; }
  const h = (r.height - (of - 1) * GUTTER) / of; return { ...r, y: snap(r.y + i * (h + GUTTER)), height: snap(h) };
}

// ---------------------------------------------------------------- container styling
function chrome({ title, subtitle, alt, bg = C.card, border = true, pad = [12, 12, 16, 16] }) {
  const v = {
    background: [{ properties: { show: bool(true), color: color(bg), transparency: num(0) } }],
    border: [{ properties: { show: bool(border), color: color(C.line), radius: num(8), width: num(1) } }],
    padding: [{ properties: { top: num(pad[0]), bottom: num(pad[1]), left: num(pad[2]), right: num(pad[3]) } }],
    dropShadow: [{ properties: { show: bool(false) } }],
    title: [{ properties: title ? { show: bool(true), text: str(title), fontFamily: str('Segoe UI Semibold'), fontSize: num(14), fontColor: color(C.text), titleWrap: bool(true) } : { show: bool(false) } }],
    subTitle: [{ properties: subtitle ? { show: bool(true), text: str(subtitle), fontFamily: str('Segoe UI'), fontSize: num(11), fontColor: color(C.muted), titleWrap: bool(true) } : { show: bool(false) } }],
  };
  if (alt) v.general = [{ properties: { altText: str(alt) } }];
  return v;
}

// ---------------------------------------------------------------- visual builders
let z = 0;
function container(name, pos, visual, extra = {}) {
  z += 1000;
  return { $schema: SCHEMA.visual, name, position: { x: pos.x, y: pos.y, z, height: pos.height, width: pos.width, tabOrder: z }, visual, ...extra };
}
const run = (value, size, { font = 'Segoe UI', col = C.text, italic = false } = {}) => ({ value, textStyle: { fontFamily: font, fontSize: `${size}pt`, color: col, ...(italic ? { fontStyle: 'italic' } : {}) } });
function textbox(name, pos, paragraphs, { bg = null, alt = null } = {}) {
  const vco = {
    background: [{ properties: bg ? { show: bool(true), color: color(bg), transparency: num(0) } : { show: bool(false) } }],
    border: [{ properties: { show: bool(false) } }],
    padding: [{ properties: bg ? { top: num(14), bottom: num(14), left: num(18), right: num(18) } : { top: num(0), bottom: num(0), left: num(0), right: num(0) } }],
    dropShadow: [{ properties: { show: bool(false) } }],
  };
  if (alt) vco.general = [{ properties: { altText: str(alt) } }];
  return container(name, pos, { visualType: 'textbox', objects: { general: [{ properties: { paragraphs } }] }, visualContainerObjects: vco });
}
function accent(name, pos, hex) {
  return container(name, pos, {
    visualType: 'shape',
    objects: {
      shape: [{ properties: { tileShape: str('rectangle') }, selector: { id: 'default' } }],
      fill: [{ properties: { show: bool(true), fillColor: color(hex), transparency: num(0) }, selector: { id: 'default' } }],
      outline: [{ properties: { show: bool(false) }, selector: { id: 'default' } }],
    },
    visualContainerObjects: { background: [{ properties: { show: bool(false) } }], border: [{ properties: { show: bool(false) } }], padding: [{ properties: { top: num(0), bottom: num(0), left: num(0), right: num(0) } }], dropShadow: [{ properties: { show: bool(false) } }] },
  });
}
// insight card = accent bar + tinted textbox (insight sentence, then grey Source line)
function insight(key, r, text, source, hex = C.blue) {
  const tint = hex === C.orange ? C.orangeTint : C.blueTint;
  const bar = { ...r, width: 8 };
  const box = { ...r, x: r.x + 8, width: r.width - 8 };
  return [
    accent(hid(key + ':bar'), bar, hex),
    textbox(hid(key + ':txt'), box, [
      { textRuns: [run('What it shows', 10, { font: 'Segoe UI Semibold', col: hex })] },
      { textRuns: [run(text, r.width < 900 ? 13 : 14)] },
      { textRuns: [run(' ', 6)] },
      { textRuns: [run('Source: ' + source, 10, { col: C.muted, italic: true })] },
    ], { bg: tint, alt: text }),
  ];
}
function headline(pageKey, r, kicker, title) {
  return textbox(hid(pageKey + ':title'), r, [
    { textRuns: [run(kicker.toUpperCase(), 11, { font: 'Segoe UI Semibold', col: C.blue })] },
    { textRuns: [run(title, 22, { font: 'Segoe UI Semibold' })] },
  ]);
}
function navigator(pageKey, r) {
  const st = (state, fill, txt, bold) => ({ fill, txt, bold, state });
  const states = [st('default', C.card, C.muted, false), st('hover', C.blueTint, C.text, false), st('selected', C.blue, '#FFFFFF', true)];
  return container(hid(pageKey + ':nav'), r, {
    visualType: 'pageNavigator',
    objects: {
      layout: [{ properties: { orientation: num(0), rowCount: int(3), columnCount: int(3), cellPadding: int(2) } }],
      shape: [{ properties: { tileShape: str('rectangleRounded'), rectangleRoundedCurve: int(6) } }],
      fill: states.map((s) => ({ properties: { show: bool(true), fillColor: color(s.fill), transparency: num(0) }, selector: { id: s.state } })),
      text: states.map((s) => ({ properties: { fontFamily: str('Segoe UI'), fontSize: num(9), bold: bool(s.bold), fontColor: color(s.txt), topMargin: int(0), bottomMargin: int(0), leftMargin: int(4), rightMargin: int(4) }, selector: { id: s.state } })),
      outline: states.map((s) => ({ properties: { show: bool(true), lineColor: color(s.state === 'selected' ? C.blue : C.line), weight: num(1), transparency: num(0) }, selector: { id: s.state } })),
    },
    visualContainerObjects: { background: [{ properties: { show: bool(false) } }], border: [{ properties: { show: bool(false) } }], padding: [{ properties: { top: num(0), bottom: num(0), left: num(0), right: num(0) } }], dropShadow: [{ properties: { show: bool(false) } }], title: [{ properties: { show: bool(false) } }] },
  });
}
function kpiCard(key, r, label, measureName, definition) {
  return container(hid(key), r, {
    visualType: 'cardVisual',
    query: { queryState: { Data: { projections: [measure(measureName)] } } },
    objects: {
      value: [{ properties: { fontFamily: str('Segoe UI Semibold'), fontSize: num(34), fontColor: color(C.text), labelDisplayUnits: str('1') }, selector: { id: 'default' } }],
      label: [{ properties: { show: bool(false) }, selector: { id: 'default' } }],
      accentBar: [{ properties: { show: bool(true), position: str('Left'), color: color(C.blue), width: num(6) }, selector: { id: 'default' } }],
      outline: [{ properties: { show: bool(false) }, selector: { id: 'default' } }],
    },
    visualContainerObjects: chrome({ title: label, subtitle: definition, alt: `${label}: ${definition}`, pad: [14, 14, 18, 18] }),
  });
}
const axisFont = { fontFamily: str('Segoe UI'), fontSize: num(10), labelColor: color(C.muted) };
const gridY = { gridlineShow: bool(true), gridlineStyle: str('dotted'), gridlineColor: color(C.line) };

// ---------------------------------------------------------------- page assembly
const pages = [];
function page(key, displayName, kicker, title, visualsFn) {
  z = 0;
  const id = hid('page:' + key);
  const hdr = rect([1, 1, 9, 2]);
  const navR = rect([9, 1, 13, 2]);
  const nav = { ...navR, y: navR.y - 8, height: navR.height + 16 };
  const visuals = [headline(key, hdr, kicker, title), navigator(key, nav), ...visualsFn()];
  pages.push({ id, displayName, visuals });
}

const RET_COH = 'fact_retention_cohort';
const DAILY = 'fact_daily_activity';

// 1. Overview -----------------------------------------------------------------
page('overview', 'Overview', '01 / 09 · Overview', 'Flood-It: new players leave fast, so retention is the lever', () => {
  const lead = rect([1, 2, 13, 3]);
  const row1 = rect([1, 3, 13, 7]);
  const row2 = rect([1, 7, 13, 11]);
  const foot = rect([1, 11, 13, 13]);
  const cards1 = [
    ['Players in window', 'Players in Window', 'Distinct user_pseudo_id with any event, 2018-06-12..2018-10-03.'],
    ['Installs in cohort', 'Cohort Installs', 'first_open in window; first touch not before the window.'],
    ['Avg DAU (excl. spike days)', 'Avg DAU excl Spikes', 'Mean distinct players per event_date, spike days removed.'],
    ['Stickiness', 'Avg Stickiness Clean', 'Mean DAU/MAU on days whose 30-day window has no spike day.'],
    ['D1 retention', 'Retention D1', 'Active on install day + 1 / eligible installs.'],
  ];
  const cards2 = [
    ['D7 retention', 'Retention D7', 'Active on install day + 7 / eligible installs.'],
    ['D30 retention', 'Retention D30', 'Active on install day + 30 / eligible installs.'],
    ['Payer rate', 'Payer Rate', 'Players with >= 1 in_app_purchase / active players.'],
    ['ARPPU', 'ARPPU', 'IAP revenue / payers.'],
    ['Churn model AUC', 'Churn LR Test AUC', 'Logistic regression, test set, install-day features.'],
  ];
  return [
    textbox(hid('overview:lead'), lead, [
      { textRuns: [run('New players leave fast (D1 21.5%, D30 2.1%); IAP is negligible (payer rate 0.18%), so retention and ad engagement are the levers.', 18, { col: C.text })] },
    ], { alt: 'Overview summary' }),
    ...cards1.map((c, i) => kpiCard('overview:k1:' + i, slot(row1, i, 5), ...c)),
    ...cards2.map((c, i) => kpiCard('overview:k2:' + i, slot(row2, i, 5), ...c)),
    textbox(hid('overview:foot'), foot, [
      { textRuns: [run('Use the section buttons (top right) to follow the story: growth, retention, revenue, levels, segments, churn model, testing and data limitations.', 13, { col: C.muted })] },
      { textRuns: [run('Source: kpi_metrics.csv, fact_retention_cohort.csv, fact_daily_activity.csv, fact_monetization_platform.csv (Firebase public export, 2018-06-12..2018-10-03).', 10, { col: C.muted, italic: true })] },
    ]),
  ];
});

// 2. Growth -------------------------------------------------------------------
page('growth', 'Growth', '02 / 09 · Growth', 'The audience is flat; DAU spikes are a sampling artefact, not growth', () => {
  const spikeMarker = {
    properties: { fill: { solid: { color: { expr: { Conditional: { Cases: [
      { Condition: { Comparison: { ComparisonKind: 0, Left: { Aggregation: { Expression: colRef(DAILY, 'is_spike_day'), Function: 4 } }, Right: { Literal: { Value: '1L' } } } }, Value: { Literal: { Value: `'${C.orange}'` } } },
      { Condition: { Comparison: { ComparisonKind: 0, Left: { Aggregation: { Expression: colRef(DAILY, 'is_spike_day'), Function: 4 } }, Right: { Literal: { Value: '0L' } } } }, Value: { Literal: { Value: `'${C.blue}'` } } },
    ], DefaultValue: { Literal: { Value: `'${C.blue}'` } } } } } } } },
    selector: { data: [{ roles: ['Category'] }] },
  };
  const dateAxis = { categoryAxis: [{ properties: { ...axisFont, axisType: str('Scalar'), showAxisTitle: bool(false) } }] };
  return [
    container(hid('growth:dau'), rect([1, 2, 8, 7]), {
      visualType: 'lineChart',
      query: { queryState: { Category: { projections: [column(DAILY, 'date')] }, Y: { projections: [measure('DAU')] }, Tooltips: { projections: [measure('Spike Days'), measure('Installs')] } } },
      objects: {
        ...dateAxis,
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }],
        dataPoint: [{ properties: { defaultColor: color(C.blue) } }, spikeMarker],
        lineStyles: [{ properties: { strokeWidth: num(2), showMarker: bool(true), markerShape: str('circle'), markerSize: num(4) } }],
        legend: [{ properties: { show: bool(false) } }],
      },
      visualContainerObjects: chrome({ title: 'Daily active players and installs', subtitle: 'DAU = distinct players with >= 1 event on the event_date. Installs = players whose first_open falls on the day. Orange markers = spike days.', alt: 'Line chart of daily active players; spike days marked orange.' }),
    }),
    container(hid('growth:installs'), rect([1, 7, 8, 11]), {
      visualType: 'clusteredColumnChart',
      query: { queryState: { Category: { projections: [column(DAILY, 'date')] }, Y: { projections: [measure('Installs')] } } },
      objects: {
        ...dateAxis,
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false) } }],
        dataPoint: [{ properties: { defaultColor: color(C.orange) } }],
        legend: [{ properties: { show: bool(false) } }],
      },
      visualContainerObjects: chrome({ title: 'Installs per day', subtitle: 'Same date axis as DAU above.', alt: 'Column chart of daily installs.' }),
    }),
    ...insight('growth:i1', rect([1, 11, 8, 13]), 'DAU averages 471.4 on normal days. The 7 spike days (~1,229 DAU, ~1.6 installs) are an artefact: screen_view falls to 14.5% of normal and the fixed 50,000-event sample spreads over more players.', 'fact_daily_activity.csv (dau, installs, is_spike_day)'),
    container(hid('growth:stick'), rect([8, 2, 13, 11]), {
      visualType: 'lineChart',
      query: { queryState: { Category: { projections: [column(DAILY, 'date')] }, Y: { projections: [measure('Stickiness')] } } },
      objects: {
        ...dateAxis,
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0), end: num(0.15) } }],
        dataPoint: [{ properties: { defaultColor: color(C.blue) } }],
        lineStyles: [{ properties: { strokeWidth: num(2), showMarker: bool(false) } }],
        legend: [{ properties: { show: bool(false) } }],
      },
      visualContainerObjects: chrome({ title: 'Stickiness (DAU / MAU)', subtitle: 'DAU divided by distinct players active in the trailing 30 days; shown only once a full 30-day window exists.', alt: 'Line chart of daily stickiness from the first full 30-day window.' }),
    }, { filterConfig: { filters: [catFilter('growth:stick:full30', DAILY, 'full_30d_window', '1L')] } }),
    ...insight('growth:i2', rect([8, 11, 13, 13]), 'Average stickiness is 9.9% on spike-free windows (from 2018-07-31): roughly one in ten monthly players plays on a given day.', 'fact_daily_activity.csv (stickiness, clean_stickiness_window)'),
  ];
});

// 3. Retention ----------------------------------------------------------------
page('retention', 'Retention', '03 / 09 · Retention', 'Most new players never come back, and newer cohorts retain worse', () => {
  const retRef = measure('Retention');
  return [
    container(hid('retention:matrix'), rect([1, 2, 8, 11]), {
      visualType: 'pivotTable',
      query: { queryState: { Rows: { projections: [column(RET_COH, 'cohort_week')] }, Columns: { projections: [column(RET_COH, 'day_n')] }, Values: { projections: [retRef] } } },
      objects: {
        columnHeaders: [{ properties: { autoSizeColumnWidth: bool(true), columnAdjustment: str('growToFit'), fontFamily: str('Segoe UI Semibold'), fontSize: num(11), fontColor: color(C.text), backColor: color(C.card), alignment: str('Center') } }],
        rowHeaders: [{ properties: { fontFamily: str('Segoe UI'), fontSize: num(11), fontColor: color(C.muted) } }],
        values: [
          { properties: { fontFamily: str('Segoe UI'), fontSize: num(11) } },
          { properties: { backColor: { solid: { color: { expr: { FillRule: { Input: retRef.field, FillRule: { linearGradient2: { min: { color: { Literal: { Value: `'${C.heatLo}'` } } }, max: { color: { Literal: { Value: `'${C.heatHi}'` } } }, nullColoringStrategy: { strategy: { Literal: { Value: "'noColor'" } } } } } } } } } },
            fontColor: { solid: { color: { expr: { Conditional: { Cases: [
              { Condition: { Comparison: { ComparisonKind: 2, Left: retRef.field, Right: { Literal: { Value: '0.15D' } } } }, Value: { Literal: { Value: "'#FFFFFF'" } } },
              { Condition: { Comparison: { ComparisonKind: 3, Left: retRef.field, Right: { Literal: { Value: '0.15D' } } } }, Value: { Literal: { Value: `'${C.text}'` } } },
            ], DefaultValue: { Literal: { Value: `'${C.text}'` } } } } } } } },
            selector: { data: [{ dataViewWildcard: { matchingOption: 1 } }], metadata: retRef.queryRef } },
        ],
        subTotals: [
          { properties: { rowSubtotals: bool(true), columnSubtotals: bool(false) } },
          { properties: { rowSubtotals: bool(true) }, selector: { id: 'Row' } },
          { properties: { columnSubtotals: bool(false) }, selector: { id: 'Column' } },
        ],
      },
      visualContainerObjects: chrome({ title: 'Day-N retention by weekly install cohort', subtitle: 'Classic Day-N: share of a cohort active exactly N days after install. Only players with N days of data (eligible) count; empty cells are censored. Columns = day N.', alt: 'Heatmap of retention by weekly cohort and day N.' }),
    }),
    ...insight('retention:i1', rect([1, 11, 8, 13]), 'D1 fell from 26.3% for June-July cohorts to 14.8% for September cohorts; the 2018-06-25 week is small because installs are missing on spike days.', 'fact_retention_cohort.csv (retained_users / eligible_users)'),
    container(hid('retention:curve'), rect([8, 2, 13, 11]), {
      visualType: 'lineChart',
      query: { queryState: { Category: { projections: [column('fact_retention_curve', 'day_n')] }, Y: { projections: [measure('Retention Curve'), measure('Retention CI High'), measure('Retention CI Low')] } } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, axisType: str('Scalar'), showAxisTitle: bool(true), titleText: str('Days since install') } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }],
        dataPoint: [
          { properties: { fill: color(C.blue) }, selector: { metadata: `${M}.Retention Curve` } },
          { properties: { fill: color(C.ciBlue) }, selector: { metadata: `${M}.Retention CI High` } },
          { properties: { fill: color(C.ciBlue) }, selector: { metadata: `${M}.Retention CI Low` } },
        ],
        lineStyles: [
          { properties: { strokeWidth: num(3), showMarker: bool(true), markerSize: num(4) }, selector: { metadata: `${M}.Retention Curve` } },
          { properties: { strokeWidth: num(1), lineStyle: str('dashed'), showMarker: bool(false) }, selector: { metadata: `${M}.Retention CI High` } },
          { properties: { strokeWidth: num(1), lineStyle: str('dashed'), showMarker: bool(false) }, selector: { metadata: `${M}.Retention CI Low` } },
        ],
        legend: [{ properties: { show: bool(true), position: str('Top'), fontSize: num(10), labelColor: color(C.muted) } }],
      },
      visualContainerObjects: chrome({ title: 'Retention curve, all cohorts', subtitle: 'Pooled retained / eligible for each day since install, with a 95% Wilson interval (dashed band).', alt: 'Retention curve from day 1 to 30 with 95% Wilson band.' }),
    }, { filterConfig: { filters: [betweenFilter('retention:curve:days', 'fact_retention_curve', 'day_n', '1L', '30L')] } }),
    ...insight('retention:i2', rect([8, 11, 13, 13]), 'D1 21.5%, D7 5.5%, D30 2.1%. Excluding spike-day targets moves D1 only to 21.2%.', 'fact_retention_curve.csv'),
  ];
});

// 4. Revenue & LTV ------------------------------------------------------------
page('revenue', 'Revenue & LTV', '04 / 09 · Revenue & LTV', 'IAP revenue is negligible; the game lives on ads the export cannot measure', () => [
  container(hid('revenue:table'), rect([1, 2, 8, 5]), {
    visualType: 'tableEx',
    query: { queryState: { Values: { projections: [column('dim_platform', 'platform'), measure('Active Players'), measure('Payers'), measure('Revenue USD'), measure('Payer Rate'), measure('ARPU'), measure('ARPDAU'), measure('ARPPU')] } } },
    objects: {
      columnHeaders: [{ properties: { autoSizeColumnWidth: bool(true), columnAdjustment: str('growToFit'), fontFamily: str('Segoe UI Semibold'), fontSize: num(11), fontColor: color(C.text), backColor: color('#F3F2EF'), wordWrap: bool(true) } }],
      values: [{ properties: { fontFamily: str('Segoe UI'), fontSize: num(12), backColorPrimary: color(C.card), backColorSecondary: color('#F9F8F6') } }],
      total: [{ properties: { totals: bool(true), label: str('All platforms'), bold: bool(true), fontSize: num(12) } }],
    },
    visualContainerObjects: chrome({ title: 'Monetisation by platform', subtitle: 'Payer rate = payers / active players; ARPU = revenue / active players; ARPDAU = revenue / player-days; ARPPU = revenue / payers. IAP only.', alt: 'Table of players, payers, revenue and ARPU metrics by platform.' }),
  }),
  container(hid('revenue:bar'), rect([1, 5, 8, 11]), {
    visualType: 'clusteredBarChart',
    query: { queryState: { Category: { projections: [column('dim_platform', 'platform')] }, Y: { projections: [measure('Payer Rate')] } }, sortDefinition: { sort: [{ field: measure('Payer Rate').field, direction: 'Descending' }], isDefaultSort: false } },
    objects: {
      categoryAxis: [{ properties: { ...axisFont, fontSize: num(12), showAxisTitle: bool(false) } }],
      valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }],
      dataPoint: [{ properties: { defaultColor: color(C.blue) } }],
      labels: [{ properties: { show: bool(true), fontSize: num(12), color: color(C.text) } }],
      legend: [{ properties: { show: bool(false) } }],
    },
    visualContainerObjects: chrome({ title: 'Payer rate by platform', subtitle: 'Payers / active players on each platform.', alt: 'Bar chart of payer rate by platform.' }),
  }),
  ...insight('revenue:i1', rect([1, 11, 8, 13]), '27 purchases, $31.86 in total; remove_ads is 74% of purchases. Ad revenue is not in the export (1,912 rewarded-ad events carry no value).', 'fact_monetization_platform.csv'),
  kpiCard('revenue:ltv:d0', slot(rect([8, 2, 13, 4]), 0, 2), 'Earned on install day', 'LTV D0 Share of D30', 'Share of the 30-day IAP LTV already earned on day 0.'),
  kpiCard('revenue:ltv:payers', slot(rect([8, 2, 13, 4]), 1, 2), 'Payers behind LTV D30', 'LTV D30 Payers', 'Payers among the 2,955 installs observable for 30 days.'),
  container(hid('revenue:ltv'), rect([8, 4, 13, 11]), {
    visualType: 'lineChart',
    query: { queryState: { Category: { projections: [column('fact_ltv_curve', 'day_n')] }, Y: { projections: [measure('LTV')] }, Tooltips: { projections: [measure('LTV Payers')] } } },
    objects: {
      categoryAxis: [{ properties: { ...axisFont, axisType: str('Scalar'), showAxisTitle: bool(true), titleText: str('Days since install') } }],
      valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }],
      dataPoint: [{ properties: { defaultColor: color(C.blue) } }],
      lineStyles: [{ properties: { strokeWidth: num(3), lineChartType: str('step'), interpolationStep: str('after'), showMarker: bool(true), markerSize: num(4) } }],
      seriesLabels: [{ properties: { show: bool(true), textSize: num(11) } }],
      legend: [{ properties: { show: bool(false) } }],
    },
    visualContainerObjects: chrome({ title: 'Cumulative IAP LTV per install', subtitle: 'Revenue from days 0..N after install / installs observable for 30 days (the same players at every N). Hover a day for cumulative payers.', alt: 'Stepped line of cumulative IAP LTV per install, days 0 to 30.' }),
  }),
  ...insight('revenue:i2', rect([8, 11, 13, 13]), 'LTV D30 is $0.0027 per install, from only 8 payers among 2,955 installs: directional, not a basis for UA bids.', 'fact_ltv_curve.csv'),
]);

// 5. Levels & difficulty ------------------------------------------------------
page('levels', 'Levels & difficulty', '05 / 09 · Levels & difficulty', "Level 27 is a difficulty wall that ends many players' progression", () => {
  const lvlAxis = { categoryAxis: [{ properties: { ...axisFont, axisType: str('Categorical'), showAxisTitle: bool(true), titleText: str('Level') } }] };
  const lvlSort = { sortDefinition: { sort: [{ field: column('fact_level_funnel', 'level').field, direction: 'Ascending' }], isDefaultSort: false } };
  return [
    container(hid('levels:funnel'), rect([1, 2, 7, 11]), {
      visualType: 'clusteredColumnChart',
      query: { queryState: { Category: { projections: [column('fact_level_funnel', 'level')] }, Y: { projections: [measure('Reach Rate')] } }, ...lvlSort },
      objects: { ...lvlAxis, valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }], dataPoint: [{ properties: { defaultColor: color(C.blue) } }], legend: [{ properties: { show: bool(false) } }] },
      visualContainerObjects: chrome({ title: 'Level funnel', subtitle: 'Players who started each level / players who started level 1 (progression mode, all players active in the window).', alt: 'Column chart of reach rate by level 1 to 30.' }),
    }),
    ...insight('levels:i1', rect([1, 11, 7, 13]), '27.8% of level-1 players reach level 10 and 7.8% reach level 30.', 'fact_level_funnel.csv (users_started)'),
    container(hid('levels:combo'), rect([7, 2, 13, 11]), {
      visualType: 'lineClusteredColumnComboChart',
      query: { queryState: { Category: { projections: [column('fact_level_funnel', 'level')] }, Y: { projections: [measure('Completion per Attempt')] }, Y2: { projections: [measure('Quit Rate')] } }, ...lvlSort },
      objects: {
        ...lvlAxis,
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0), end: num(1), secShow: bool(false), secStart: num(0), secEnd: num(1) } }],
        dataPoint: [
          { properties: { fill: color(C.blue) }, selector: { metadata: `${M}.Completion per Attempt` } },
          { properties: { fill: color(C.orange) }, selector: { metadata: `${M}.Quit Rate` } },
        ],
        lineStyles: [{ properties: { strokeWidth: num(3), showMarker: bool(true), markerSize: num(5), lineChartType: str('linear') } }],
        legend: [{ properties: { show: bool(true), position: str('Top'), fontSize: num(10), labelColor: color(C.muted) } }],
      },
      visualContainerObjects: chrome({ title: 'Completion per attempt and quit rate', subtitle: 'Completion per attempt = level_complete / level_start. Quit rate = new players whose last level started is L / new players who started L. One percentage axis.', alt: 'Columns of completion per attempt and line of quit rate by level.' }),
    }),
    ...insight('levels:i2', rect([7, 11, 13, 13]), 'Level 27 is a wall: 4.5% of attempts succeed and 45.7% of new players who reach it stop there; levels 29 and 9 follow.', 'fact_level_funnel.csv (completes, starts, new_players_last_level, new_players_started)', C.orange),
  ];
});

// 6. Player segments ----------------------------------------------------------
page('segments', 'Player segments', '06 / 09 · Player segments', 'The first session decides who stays', () => {
  const SEG = 'fact_day0_segments';
  const order = agg(SEG, 'segment_order', 'Min');
  return [
    container(hid('segments:eng'), rect([1, 2, 7, 11]), {
      visualType: 'clusteredColumnChart',
      query: { queryState: { Category: { projections: [column(SEG, 'segment')] }, Y: { projections: [measure('Segment D1 Retention'), measure('Segment D7 Retention')] }, Tooltips: { projections: [order] } },
        sortDefinition: { sort: [{ field: order.field, direction: 'Ascending' }], isDefaultSort: false } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, fontSize: num(12), showAxisTitle: bool(true), titleText: str('Day-0 engagement time') } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }],
        dataPoint: [
          { properties: { fill: color(C.blue) }, selector: { metadata: `${M}.Segment D1 Retention` } },
          { properties: { fill: color(C.orange) }, selector: { metadata: `${M}.Segment D7 Retention` } },
        ],
        labels: [{ properties: { show: bool(true), fontSize: num(10) } }],
        legend: [{ properties: { show: bool(true), position: str('Top'), fontSize: num(10), labelColor: color(C.muted) } }],
      },
      visualContainerObjects: chrome({ title: 'Retention by install-day engagement', subtitle: 'Players grouped by minutes of engagement (user_engagement.engagement_time_msec) on their install day.', alt: 'Clustered columns of D1 and D7 retention by day-0 engagement band.' }),
    }, { filterConfig: { filters: [catFilter('segments:eng:dim', SEG, 'dimension', "'Day-0 engagement time'")] } }),
    ...insight('segments:i1', rect([1, 11, 7, 13]), '29% of installs play under a minute on day 0; their D7 is 2.3% vs 12.0% for 15+ minutes.', 'fact_day0_segments.csv (dimension = Day-0 engagement time)'),
    container(hid('segments:mode'), rect([7, 2, 13, 11]), {
      visualType: 'clusteredBarChart',
      query: { queryState: { Category: { projections: [column(SEG, 'segment')] }, Y: { projections: [measure('Segment D1 Retention')] } },
        sortDefinition: { sort: [{ field: measure('Segment D1 Retention').field, direction: 'Descending' }], isDefaultSort: false } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, fontSize: num(12), showAxisTitle: bool(false) } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }],
        dataPoint: [{ properties: { defaultColor: color(C.blue) } }],
        labels: [{ properties: { show: bool(true), fontSize: num(11), color: color(C.text) } }],
        legend: [{ properties: { show: bool(false) } }],
      },
      visualContainerObjects: chrome({ title: 'D1 retention by day-0 game mode', subtitle: 'Mode played on install day: progression (levels), quickplay (boards) or both.', alt: 'Bar chart of D1 retention by day-0 game mode.' }),
    }, { filterConfig: { filters: [catFilter('segments:mode:dim', SEG, 'dimension', "'Day-0 game mode'")] } }),
    ...insight('segments:i2', rect([7, 11, 13, 13]), 'Players who tried both modes keep 29.1% on D1 vs 17.8% for quickplay only. Payers are active a median 3 days vs 1.', 'fact_day0_segments.csv (dimension = Day-0 game mode)'),
  ];
});

// 7. Churn model --------------------------------------------------------------
page('churn', 'Churn model', '07 / 09 · Churn model', 'Install-day behaviour ranks churn risk, but only weakly', () => {
  const ROC = 'fact_churn_roc', FI = 'fact_churn_feature_importance';
  return [
    container(hid('churn:roc'), rect([1, 2, 7, 11]), {
      visualType: 'lineChart',
      query: { queryState: { Category: { projections: [column(ROC, 'fpr')] }, Y: { projections: [measure('TPR Logistic Regression'), measure('TPR Decision Tree'), measure('Random Classifier TPR')] } } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, axisType: str('Scalar'), start: num(0), end: num(1), showAxisTitle: bool(true), titleText: str('False positive rate') } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, start: num(0), end: num(1), showAxisTitle: bool(true), titleText: str('True positive rate') } }],
        dataPoint: [
          { properties: { fill: color(C.blue) }, selector: { metadata: `${M}.TPR Logistic Regression` } },
          { properties: { fill: color(C.orange) }, selector: { metadata: `${M}.TPR Decision Tree` } },
          { properties: { fill: color('#9A9893') }, selector: { metadata: `${M}.Random Classifier TPR` } },
        ],
        lineStyles: [
          { properties: { strokeWidth: num(3), showMarker: bool(false) } },
          { properties: { strokeWidth: num(1), lineStyle: str('dashed'), showMarker: bool(false) }, selector: { metadata: `${M}.Random Classifier TPR` } },
        ],
        legend: [{ properties: { show: bool(true), position: str('Top'), fontSize: num(10), labelColor: color(C.muted) } }],
      },
      visualContainerObjects: chrome({ title: 'Churn prediction: ROC curve', subtitle: 'Churned = no activity on days 7-30 after install. Features = install-day behaviour only. 75/25 stratified split, 5-fold CV. Dashed grey = random model (y = x, AUC 0.5).', alt: 'ROC curves of logistic regression and decision tree against the y = x random baseline.' }),
    }),
    ...insight('churn:i1', rect([1, 11, 7, 13]), 'Logistic regression reaches test AUC 0.68 (CV 0.62); the depth-4 tree 0.60. Churn rate is 72.1% of 2,955 installs.', 'fact_churn_roc.csv, fact_churn_model_performance.csv'),
    container(hid('churn:imp'), rect([7, 2, 13, 11]), {
      visualType: 'barChart',
      query: { queryState: { Category: { projections: [column(FI, 'feature')] }, Y: { projections: [measure('Permutation Importance')] } },
        sortDefinition: { sort: [{ field: measure('Permutation Importance').field, direction: 'Descending' }], isDefaultSort: false } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, fontSize: num(11), showAxisTitle: bool(false) } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(true), titleText: str('Drop in test AUC'), start: num(0) } }],
        dataPoint: [{ properties: { defaultColor: color(C.blue) } }],
        labels: [{ properties: { show: bool(true), fontSize: num(10), color: color(C.text) } }],
        legend: [{ properties: { show: bool(false) } }],
      },
      visualContainerObjects: chrome({ title: 'What predicts churn', subtitle: 'Permutation importance: drop in test AUC when one feature is shuffled. Logistic regression, top 8 features.', alt: 'Bar chart of the top 8 churn-model features by permutation importance.' }),
    }, { filterConfig: { filters: [catFilter('churn:imp:model', FI, 'model', "'logistic_regression'"), topNFilter('churn:imp:top8', FI, 'feature', 'permutation_auc_drop', 8)] } }),
    ...insight('churn:i2', rect([7, 11, 13, 13]), 'Install-day engagement time leads. The riskiest decile churns at 86.5% vs 51.3% for the safest: useful for ranking, weak for individual targeting.', 'fact_churn_feature_importance.csv (model = logistic_regression)'),
  ];
});

// 8. A/B ----------------------------------------------------------------------
page('ab', 'A/B: observational tests and test design', '08 / 09 · A/B tests', 'Platform gaps are real but not causal; a clean D1 test needs far more traffic', () => {
  const T = 'fact_ab_observational_tests', P = 'fact_ab_power_analysis';
  const cols = ['comparison', 'metric', 'group_a', 'rate_a', 'group_b', 'rate_b', 'diff_a_minus_b', 'diff_ci_low', 'diff_ci_high', 'p_value', 'cohens_h'];
  return [
    container(hid('ab:tests'), rect([1, 2, 9, 11]), {
      visualType: 'tableEx',
      query: { queryState: { Values: { projections: cols.map((c) => column(T, c)) } } },
      objects: {
        columnHeaders: [{ properties: { autoSizeColumnWidth: bool(true), columnAdjustment: str('growToFit'), fontFamily: str('Segoe UI Semibold'), fontSize: num(11), fontColor: color(C.text), backColor: color('#F3F2EF'), wordWrap: bool(true) } }],
        values: [{ properties: { fontFamily: str('Segoe UI'), fontSize: num(11), wordWrap: bool(true), backColorPrimary: color(C.card), backColorSecondary: color('#F9F8F6') } }],
        total: [{ properties: { totals: bool(false) } }],
      },
      visualContainerObjects: chrome({ title: 'Observational comparisons (not randomised)', subtitle: "Two-proportion z-test (= chi-square 2x2), 95% CI of the difference, Cohen's h. Traffic source compared within Android only.", alt: 'Table of observational group comparisons with differences, confidence intervals and p-values.' }),
    }),
    ...insight('ab:i1', rect([1, 11, 9, 13]), "iOS D1 is -3.8 pp vs Android (p = 0.005, h -0.09); on Android, google-play installs lead (direct) by +6.8 pp (p < 0.001). Correlation, not causation.", 'fact_ab_observational_tests.csv'),
    container(hid('ab:power'), rect([9, 2, 13, 11]), {
      visualType: 'lineChart',
      query: { queryState: { Category: { projections: [column(P, 'mde_abs')] }, Y: { projections: [agg(P, 'n_per_arm', 'Sum')] }, Tooltips: { projections: [agg(P, 'days_needed_at_sample_volume', 'Sum')] } } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, axisType: str('Categorical'), showAxisTitle: bool(true), titleText: str('Minimum detectable effect (absolute, D1)') } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, logAxisScale: bool(true), showAxisTitle: bool(true), titleText: str('Players per arm (log scale)') } }],
        dataPoint: [{ properties: { defaultColor: color(C.blue) } }],
        lineStyles: [{ properties: { strokeWidth: num(3), showMarker: bool(true), markerSize: num(7) } }],
        labels: [{ properties: { show: bool(true), fontSize: num(11), color: color(C.text) } }],
        legend: [{ properties: { show: bool(false) } }],
      },
      visualContainerObjects: chrome({ title: 'Sample size for a D1 retention A/B test', subtitle: 'Two-sided test, alpha 0.05, power 0.8, baseline = observed D1; run time = 2 x n / installs per day (see tooltip).', alt: 'Line chart of players per arm needed for each minimum detectable effect, log scale.' }),
    }),
    ...insight('ab:i2', rect([9, 11, 13, 13]), 'Detecting +2 pp needs 6,834 players per arm: about 340 days at the sampled 40.3 installs per day. Run on full traffic or test bigger changes.', 'fact_ab_power_analysis.csv'),
  ];
});

// 9. Data limitations ---------------------------------------------------------
page('limits', 'Data limitations', '09 / 09 · Data limitations', 'What this data can and cannot tell us', () => {
  const items = [
    'Sampled export: exactly 50,000 events per day. Absolute counts describe the sample; rates are reliable.',
    '60% of players were acquired before the window; cohorts and LTV use installs inside it only.',
    '29% of new players have no first_open and are excluded from cohorts.',
    'Only 27 purchases and no ad revenue: monetisation figures are directional.',
    'Traffic source is confounded with platform (iOS is (direct) only); app_remove exists only on Android and is not used as a churn label.',
    'Platform and source comparisons are observational, not causal.',
  ];
  const r = rect([1, 2, 13, 13]);
  return [
    accent(hid('limits:bar'), { ...r, width: 8 }, C.orange),
    textbox(hid('limits:text'), { ...r, x: r.x + 8, width: r.width - 8 }, items.flatMap((t, i) => [...(i ? [{ textRuns: [run(' ', 12)] }] : []), { textRuns: [run(t, 22)], listType: 'bullet', indent: 1 }]), { bg: C.card, alt: 'Data limitations' }),
  ];
});

// ---------------------------------------------------------------- theme
const THEME_NAME = 'FloodItEditorial';
const themeFile = `${THEME_NAME}-${hid('theme-v3', 8)}.json`;
const theme = {
  name: themeFile,
  dataColors: [C.blue, C.orange, C.aqua, '#0D366B', '#8DB8EC', '#52514E'],
  foreground: C.text, foregroundNeutralSecondary: C.muted, background: C.bg, backgroundLight: C.card, tableAccent: C.blue,
  maximum: C.heatHi, minimum: C.heatLo, center: '#6D9BD8',
  good: C.aqua, neutral: '#D9B300', bad: C.orange,
  textClasses: {
    callout: { fontSize: 34, fontFace: 'Segoe UI Semibold', color: C.text },
    title: { fontSize: 12, fontFace: 'Segoe UI Semibold', color: C.text },
    header: { fontSize: 12, fontFace: 'Segoe UI Semibold', color: C.text },
    label: { fontSize: 10, fontFace: 'Segoe UI', color: C.text },
  },
  visualStyles: {
    '*': { '*': {
      dropShadow: [{ show: false }],
      categoryAxis: [{ gridlineStyle: 'dotted', gridlineColor: { solid: { color: C.line } } }],
      valueAxis: [{ gridlineStyle: 'dotted', gridlineColor: { solid: { color: C.line } } }],
    } },
    page: { '*': { background: [{ color: { solid: { color: C.bg } }, transparency: 0 }], outspace: [{ color: { solid: { color: C.bg } } }] } },
  },
};

// ---------------------------------------------------------------- write files
const pagesDir = path.join(DEF, 'pages');
for (const d of fs.readdirSync(pagesDir)) { const p = path.join(pagesDir, d); if (fs.statSync(p).isDirectory()) fs.rmSync(p, { recursive: true, force: true }); }
const write = (f, o) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, JSON.stringify(o, null, 2) + '\n', 'utf8'); };
let visualCount = 0;
for (const p of pages) {
  write(path.join(pagesDir, p.id, 'page.json'), {
    $schema: SCHEMA.page, name: p.id, displayName: p.displayName, displayOption: 'FitToPage', height: H, width: W,
    objects: { background: [{ properties: { color: color(C.bg), transparency: num(0) } }], outspace: [{ properties: { color: color(C.bg), transparency: num(0) } }] },
  });
  for (const v of p.visuals) { write(path.join(pagesDir, p.id, 'visuals', v.name, 'visual.json'), v); visualCount++; }
}
write(path.join(pagesDir, 'pages.json'), { $schema: SCHEMA.pages, pageOrder: pages.map((p) => p.id), activePageName: pages[0].id });

// theme registration
const regDir = path.join(REPORT, 'StaticResources', 'RegisteredResources');
fs.mkdirSync(regDir, { recursive: true });
for (const f of fs.readdirSync(regDir)) if (f.startsWith(THEME_NAME + '-')) fs.rmSync(path.join(regDir, f));
write(path.join(regDir, themeFile), theme);
const reportJson = JSON.parse(fs.readFileSync(path.join(DEF, 'report.json'), 'utf8'));
const base = reportJson.themeCollection.baseTheme;
reportJson.themeCollection.customTheme = { name: themeFile, reportVersionAtImport: base.reportVersionAtImport, type: 'RegisteredResources' };
reportJson.resourcePackages = (reportJson.resourcePackages || []).filter((r) => r.type !== 'RegisteredResources');
reportJson.resourcePackages.push({ name: 'RegisteredResources', type: 'RegisteredResources', items: [{ name: themeFile, path: themeFile, type: 'CustomTheme' }] });
write(path.join(DEF, 'report.json'), reportJson);

console.log(JSON.stringify({ report: REPORT, pages: pages.length, visuals: visualCount, theme: themeFile }));
