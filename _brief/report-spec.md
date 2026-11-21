# Report Spec — Flood-It Game Analytics (Power BI)

## Report identity
- Report name: FloodIt (powerbi/FloodIt.pbip)
- Semantic model: FloodIt.SemanticModel (local, built via Power BI MCP; 25 tables, 5 relationships, 52 measures in `_Measures`)
- Audience: hiring managers / analytics leads reviewing a DA portfolio; secondarily product + LiveOps leads
- Primary purpose: tell the Flood-It story end to end (growth -> retention -> monetisation -> levels -> segments -> churn model -> testing -> caveats) and show the analyst can turn numbers into decisions
- Delivery target: local PBIP only (no Fabric publish in this build)

## Semantic model binding
- Entry mode: Local Model
- Model name: FloodIt
- connectionString: byPath ../FloodIt.SemanticModel (already set by Desktop)
- Data source: M parameter `CsvFolder` = `D:\Vi\DA_Game\flood-it-game-analytics\powerbi\data\` (local git clone)

## User decisions and constraints
- Scope: the 9 sections of `powerbi/layout.md`, same order, same chart titles, definitions, insight sentences (verbatim) and source lines
- Page count: 9
- Interactivity: page navigator (top right on every page); no slicers (every visual answers one fixed question; filters are baked into visual-level filters exactly as layout.md says); "Show as table" left available
- Design direction: "thật đẹp, kể chuyện bằng dữ liệu" — editorial analyst briefing
- Publishing: none
- Tooling: Power BI Desktop + MCP (model), PBIR files (report)
- Model edit permissions: no new measures beyond measures.dax; no hard-coded numbers in visuals or measures
- Accessibility: WCAG AA contrast, alt text on every chart, colour never the only signal (spike days also labelled in tooltip)
- Data caveats: sampled export; shown on every page via source lines and on the Data limitations page

## Narrative
- Core story: Flood-It loses most new players immediately; IAP is negligible, so retention (first session, level 27) is the lever, and testing it properly needs more traffic than the sample offers.
- Audience promise: every page opens with a one-line takeaway, every chart says what it measures (definition), what it shows (insight) and where it comes from (source).
- Key questions answered: Is the audience growing? How fast do players leave? Is there money? Where do players get stuck? Who stays? Can we predict churn? What can we test?

## Design identity
- Tone: Editorial analyst briefing — warm off-white page, near-black text, one accent per series, generous whitespace
- Signature: every page = **takeaway headline (left, 28pt semibold)** + charts whose subtitle is the metric definition + a matching **insight card with a coloured left accent bar** under each chart, ending in a grey `Source:` line

## Page plan
1. Overview — Executive Summary (variant A: lead + KPI wall). Lead text box; 10 KPI cards (2 x 5) each with its definition; source footer.
2. Growth — Analytical (variant B: stacked pair + side chart). DAU line above Installs columns (shared date axis, spike days in orange); Stickiness line; two insight cards.
3. Retention — Analytical (variant B). Cohort x day_n heatmap matrix (#CDE2FB -> #0D366B); pooled retention curve with Wilson 95% band; two insight cards.
4. Revenue & LTV — Analytical (variant B). Monetisation table by platform with totals + clustered bar (Payer Rate by platform); stepped LTV line; two insight cards.
5. Levels & difficulty — Comparative (variant A: halves). Reach-rate columns by level; Completion per attempt columns + Quit rate line on one % axis; two insight cards.
6. Player segments — Comparative (halves). D1/D7 by day-0 engagement (clustered columns, sorted by segment_order); D1 by day-0 game mode (bar); two insight cards.
7. Churn model — Analytical (halves). ROC curve by model + y = x reference; top-8 permutation importance bars (logistic regression); two insight cards.
8. A/B: observational tests and test design — Analytical (variant B). Observational tests table; sample-size line (log y, tooltip days needed); two insight cards.
9. Data limitations — Narrative (single text column). Verbatim bullet list.

## Design system summary
- Theme: `FloodItEditorial` — background #FCFCFB, text #0B0B0B, secondary text #52514E, dataColors [#2A78D6, #EB6834, #1BAF7A], heatmap #CDE2FB -> #0D366B, font Segoe UI
- Colour semantics: blue = primary metric of a chart (DAU, Retention, Reach, Completion, Payer rate, LTV, tpr logistic regression); orange = contrast/alert (spike days, Quit rate, Installs, D7, decision tree); aqua = third series only
- Typography: Segoe UI Semibold 28 (page headline), Segoe UI Semibold 14 (visual title), Segoe UI 11 (subtitle/definition), Segoe UI 12 (insight), 10 grey (source)
- Layout: 1920 x 1080, 12 x 12 grid, margin 32, gutter 24, snap 8; header row reserved
- Accessibility: AA contrast on #FCFCFB; alt text = chart title + insight; tooltips on every chart

## Model requirements
- Existing measures: all 52 from measures.dax (reconciliation 40/40 PASS)
- New measures: none
- New calculated columns: none
- Relationship/sort requirements: none new; segment axis sorted by `segment_order` via visual sort

## Canonical design contract

```yaml
Design Brief:
  generated_by: powerbi-report-cli
  contract_version: 1
  mode: greenfield
  design_identity:
    tone: "Editorial analyst briefing: warm off-white canvas, near-black type, three-colour series palette, generous whitespace"
    signature: "Takeaway headline per page + definition subtitles + accent-barred insight card under every chart ending in a grey Source line"
  archetype: Narrative Story
  navigation_model: page_navigator
  color_map:
    - { measure: "_Measures[DAU]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "_Measures[Installs]", color: "#EB6834", tint: "#FBE1D6" }
    - { measure: "_Measures[Stickiness]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "_Measures[Retention]", color: "#0D366B", tint: "#CDE2FB" }
    - { measure: "_Measures[Retention Curve]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "_Measures[Payer Rate]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "_Measures[LTV]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "_Measures[Reach Rate]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "_Measures[Completion per Attempt]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "_Measures[Quit Rate]", color: "#EB6834", tint: "#FBE1D6" }
    - { measure: "_Measures[Segment D1 Retention]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "_Measures[Segment D7 Retention]", color: "#EB6834", tint: "#FBE1D6" }
    - { measure: "_Measures[Permutation Importance]", color: "#2A78D6", tint: "#CDE2FB" }
    - { measure: "fact_ab_power_analysis[n_per_arm]", color: "#2A78D6", tint: "#CDE2FB" }
  pages:
    - name: Overview
      role: landing
      archetype: Executive
      layout_variant: A
      variant_rationale: "Ten headline scalars from metrics.json; a KPI wall with definitions is the whole page brief."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "Headline, verbatim lead text, 2 x 5 KPI cards with definitions, source footer."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:     [1, 1, 8, 2]
            nav:        [8, 1, 13, 2]
            lead:       [1, 2, 13, 4]
            kpis_row1:  [1, 4, 13, 8]
            kpis_row2:  [1, 8, 13, 12]
            footer:     [1, 12, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "Flood-It: new players leave fast, so retention is the lever" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: lead_text, region: lead, kind: textbox, text: "New players leave fast (D1 21.5%, D30 2.1%); IAP is negligible (payer rate 0.18%), so retention and ad engagement are the levers.", purpose: "Verbatim overview sentence from layout.md" }
          - { id: kpi_players, region: kpis_row1, kind: cardVisual, slot: 1, of: 5, field_bindings: "_Measures[Players in Window]", subtitle: "Distinct user_pseudo_id with any event, 2018-06-12..2018-10-03.", color_strategy: none, purpose: "Players in window" }
          - { id: kpi_installs, region: kpis_row1, kind: cardVisual, slot: 2, of: 5, field_bindings: "_Measures[Cohort Installs]", subtitle: "first_open in window; first touch not before the window.", color_strategy: none, purpose: "Installs in cohort" }
          - { id: kpi_dau, region: kpis_row1, kind: cardVisual, slot: 3, of: 5, field_bindings: "_Measures[Avg DAU excl Spikes]", subtitle: "Mean distinct players per event_date, spike days removed.", color_strategy: none, purpose: "Avg DAU (excl. spike days)" }
          - { id: kpi_stick, region: kpis_row1, kind: cardVisual, slot: 4, of: 5, field_bindings: "_Measures[Avg Stickiness Clean]", subtitle: "Mean DAU/MAU on days whose 30-day window has no spike day.", color_strategy: none, purpose: "Stickiness" }
          - { id: kpi_d1, region: kpis_row1, kind: cardVisual, slot: 5, of: 5, field_bindings: "_Measures[Retention D1]", subtitle: "Active on install day + 1 / eligible installs.", color_strategy: none, purpose: "D1 retention" }
          - { id: kpi_d7, region: kpis_row2, kind: cardVisual, slot: 1, of: 5, field_bindings: "_Measures[Retention D7]", subtitle: "Active on install day + 7 / eligible installs.", color_strategy: none, purpose: "D7 retention" }
          - { id: kpi_d30, region: kpis_row2, kind: cardVisual, slot: 2, of: 5, field_bindings: "_Measures[Retention D30]", subtitle: "Active on install day + 30 / eligible installs.", color_strategy: none, purpose: "D30 retention" }
          - { id: kpi_payer, region: kpis_row2, kind: cardVisual, slot: 3, of: 5, field_bindings: "_Measures[Payer Rate]", subtitle: "Players with >= 1 in_app_purchase / active players.", color_strategy: none, purpose: "Payer rate" }
          - { id: kpi_arppu, region: kpis_row2, kind: cardVisual, slot: 4, of: 5, field_bindings: "_Measures[ARPPU]", subtitle: "IAP revenue / payers.", color_strategy: none, purpose: "ARPPU" }
          - { id: kpi_auc, region: kpis_row2, kind: cardVisual, slot: 5, of: 5, field_bindings: "_Measures[Churn LR Test AUC]", subtitle: "Logistic regression, test set, install-day features.", color_strategy: none, purpose: "Churn model AUC" }
          - { id: source_footer, region: footer, kind: textbox, text: "Source: kpi_metrics.csv, fact_retention_cohort.csv, fact_daily_activity.csv, fact_monetization_platform.csv (Firebase public export, 2018-06-12..2018-10-03)." }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: kpis_row1, pct_of_content: 36 }
          balance_rationale: "Composite KPI treatment: ten cards each carry value + definition subtitle; lead sentence explains them; footer carries sources. No single card dominates."

    - name: Growth
      role: detail
      archetype: Analytical
      layout_variant: B
      variant_rationale: "Two questions (volume, stickiness) with the DAU/Installs pair needing a shared x-axis, so the pair stacks on the left."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "Left: DAU line over Installs columns + insight. Right: stickiness line + insight."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:          [1, 1, 8, 2]
            nav:             [8, 1, 13, 2]
            dau:             [1, 2, 8, 7]
            installs:        [1, 7, 8, 10]
            insight_growth:  [1, 10, 8, 13]
            stickiness:      [8, 2, 13, 10]
            insight_stick:   [8, 10, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "The audience is flat; DAU spikes are a sampling artefact, not growth" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: dau_line, region: dau, kind: lineChart, title: "Daily active players and installs", subtitle: "DAU = distinct players with >= 1 event on the event_date. Installs = players whose first_open falls on the day.", field_bindings: { Category: "fact_daily_activity[date]", Y: "_Measures[DAU]" }, color_strategy: measure_match, markers: "orange where fact_daily_activity[is_spike_day] = 1", purpose: "How many players are active each day, and which days are spikes?" }
          - { id: installs_col, region: installs, kind: clusteredColumnChart, title: "Installs per day", field_bindings: { Category: "fact_daily_activity[date]", Y: "_Measures[Installs]" }, sort_policy: natural_order, color_strategy: measure_match, purpose: "How many installs per day (same x-axis as DAU)?" }
          - { id: insight_growth, region: insight_growth, kind: textbox, text: "DAU averages 471.4 on normal days. The 7 spike days (~1,229 DAU, ~1.6 installs) are an artefact: screen_view falls to 14.5% of normal and the fixed 50,000-event sample spreads over more players.\nSource: fact_daily_activity.csv (dau, installs, is_spike_day)", insight_basis: "verbatim insight from layout.md" }
          - { id: stick_line, region: stickiness, kind: lineChart, title: "Stickiness (DAU / MAU)", subtitle: "DAU divided by distinct players active in the trailing 30 days; shown only once a full 30-day window exists.", field_bindings: { Category: "fact_daily_activity[date]", Y: "_Measures[Stickiness]" }, filters: "fact_daily_activity[full_30d_window] = 1", y_axis: "0 to 0.15", color_strategy: measure_match, purpose: "What share of monthly players play on a given day?" }
          - { id: insight_stick, region: insight_stick, kind: textbox, text: "Average stickiness is 9.9% on spike-free windows (from 2018-07-31): roughly one in ten monthly players plays on a given day.\nSource: fact_daily_activity.csv (stickiness, clean_stickiness_window)", insight_basis: "verbatim insight from layout.md" }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: stickiness, pct_of_content: 30 }
          balance_rationale: "DAU+Installs pair (56 cells) and stickiness (40 cells) get comparable space; insights sit directly under the chart they explain."

    - name: Retention
      role: detail
      archetype: Analytical
      layout_variant: B
      variant_rationale: "The 17-week x 5-day heatmap needs width and height; the pooled curve is a single series."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "Left: cohort heatmap + insight. Right: retention curve with CI + insight."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:         [1, 1, 8, 2]
            nav:            [8, 1, 13, 2]
            heatmap:        [1, 2, 8, 10]
            insight_heat:   [1, 10, 8, 13]
            curve:          [8, 2, 13, 10]
            insight_curve:  [8, 10, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "Most new players never come back, and newer cohorts retain worse" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: cohort_matrix, region: heatmap, kind: pivotTable, title: "Day-N retention by weekly install cohort", subtitle: "Classic Day-N: share of a cohort active exactly N days after install. Only players with N days of data (eligible) count; empty cells are censored.", field_bindings: { Rows: "fact_retention_cohort[cohort_week]", Columns: "fact_retention_cohort[day_n]", Values: "_Measures[Retention]" }, color_strategy: gradient, gradient: "#CDE2FB -> #0D366B", sort_policy: category_asc, purpose: "How does Day-N retention change across weekly cohorts?" }
          - { id: insight_heat, region: insight_heat, kind: textbox, text: "D1 fell from 26.3% for June-July cohorts to 14.8% for September cohorts; the 2018-06-25 week is small because installs are missing on spike days.\nSource: fact_retention_cohort.csv (retained_users / eligible_users)", insight_basis: "verbatim insight from layout.md" }
          - { id: retention_curve, region: curve, kind: lineChart, title: "Retention curve, all cohorts", subtitle: "Pooled retained / eligible for each day since install, with a 95% Wilson interval.", field_bindings: { Category: "fact_retention_curve[day_n]", Y: "_Measures[Retention Curve]", ErrorLower: "_Measures[Retention CI Low]", ErrorUpper: "_Measures[Retention CI High]" }, filters: "fact_retention_curve[day_n] between 1 and 30", color_strategy: measure_match, purpose: "How quickly does the pooled cohort decay?" }
          - { id: insight_curve, region: insight_curve, kind: textbox, text: "D1 21.5%, D7 5.5%, D30 2.1%. Excluding spike-day targets moves D1 only to 21.2%.\nSource: fact_retention_curve.csv", insight_basis: "verbatim insight from layout.md" }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: heatmap, pct_of_content: 42 }
          balance_rationale: "Heatmap has 85 cells of data and earns the larger half; curve remains 5 columns wide and readable."

    - name: Revenue & LTV
      role: detail
      archetype: Analytical
      layout_variant: B
      variant_rationale: "Monetisation is a 2-platform table plus a comparison bar; LTV is one stepped series."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "Left: monetisation table over payer-rate bar + insight. Right: LTV line + insight."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:         [1, 1, 8, 2]
            nav:            [8, 1, 13, 2]
            monet_table:    [1, 2, 8, 6]
            monet_bar:      [1, 6, 8, 10]
            insight_monet:  [1, 10, 8, 13]
            ltv:            [8, 2, 13, 10]
            insight_ltv:    [8, 10, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "IAP revenue is negligible; the game lives on ads the export cannot measure" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: monet_tbl, region: monet_table, kind: tableEx, title: "Monetisation by platform", subtitle: "Payer rate = payers / active players; ARPU = revenue / active players; ARPDAU = revenue / player-days; ARPPU = revenue / payers. IAP only.", field_bindings: ["dim_platform[platform]", "_Measures[Active Players]", "_Measures[Payers]", "_Measures[Revenue USD]", "_Measures[Payer Rate]", "_Measures[ARPU]", "_Measures[ARPDAU]", "_Measures[ARPPU]"], totals: true, sort_policy: category_asc, purpose: "How do players, payers and revenue split by platform?" }
          - { id: monet_bar, region: monet_bar, kind: clusteredBarChart, title: "Payer rate by platform", field_bindings: { Category: "dim_platform[platform]", X: "_Measures[Payer Rate]" }, sort_policy: value_desc, color_strategy: measure_match, purpose: "Which platform converts more players to payers?" }
          - { id: insight_monet, region: insight_monet, kind: textbox, text: "27 purchases, $31.86 in total; remove_ads is 74% of purchases. Ad revenue is not in the export (1,912 rewarded-ad events carry no value).\nSource: fact_monetization_platform.csv", insight_basis: "verbatim insight from layout.md" }
          - { id: ltv_line, region: ltv, kind: lineChart, title: "Cumulative IAP LTV per install", subtitle: "Revenue from days 0..N after install / installs observable for 30 days (the same players at every N).", field_bindings: { Category: "fact_ltv_curve[day_n]", Y: "_Measures[LTV]" }, line_style: stepped, color_strategy: measure_match, purpose: "How much IAP revenue does an install generate over 30 days?" }
          - { id: insight_ltv, region: insight_ltv, kind: textbox, text: "LTV D30 is $0.0027 per install, from only 8 payers among 2,955 installs: directional, not a basis for UA bids.\nSource: fact_ltv_curve.csv", insight_basis: "verbatim insight from layout.md" }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: ltv, pct_of_content: 30 }
          balance_rationale: "Table and bar share the left half equally; LTV gets the right half; insights under each."

    - name: Levels & difficulty
      role: detail
      archetype: Comparative
      layout_variant: A
      variant_rationale: "Two level-indexed charts of equal weight (funnel vs per-level difficulty)."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "Halves: reach-rate columns | completion columns + quit-rate line; insights under each."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:          [1, 1, 8, 2]
            nav:             [8, 1, 13, 2]
            funnel:          [1, 2, 7, 10]
            insight_funnel:  [1, 10, 7, 13]
            difficulty:      [7, 2, 13, 10]
            insight_diff:    [7, 10, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "Level 27 is a difficulty wall that ends many players' progression" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: funnel_col, region: funnel, kind: columnChart, title: "Level funnel", subtitle: "Players who started each level / players who started level 1 (progression mode, all players active in the window).", field_bindings: { Category: "fact_level_funnel[level]", Y: "_Measures[Reach Rate]" }, sort_policy: category_asc, color_strategy: measure_match, purpose: "What share of level-1 players reach each level?" }
          - { id: insight_funnel, region: insight_funnel, kind: textbox, text: "27.8% of level-1 players reach level 10 and 7.8% reach level 30.\nSource: fact_level_funnel.csv (users_started)", insight_basis: "verbatim insight from layout.md" }
          - { id: difficulty_combo, region: difficulty, kind: lineClusteredColumnComboChart, title: "Completion per attempt and quit rate", subtitle: "Completion per attempt = level_complete / level_start. Quit rate = new players whose last level started is L / new players who started L.", field_bindings: { Category: "fact_level_funnel[level]", ColumnY: "_Measures[Completion per Attempt]", LineY: "_Measures[Quit Rate]" }, single_axis: true, sort_policy: category_asc, color_strategy: measure_match, purpose: "Which levels are hardest and where do new players stop?" }
          - { id: insight_diff, region: insight_diff, kind: textbox, text: "Level 27 is a wall: 4.5% of attempts succeed and 45.7% of new players who reach it stop there; levels 29 and 9 follow.\nSource: fact_level_funnel.csv (completes, starts, new_players_last_level, new_players_started)", insight_basis: "verbatim insight from layout.md" }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: funnel, pct_of_content: 36 }
          balance_rationale: "Equal halves for two equally important level views."

    - name: Player segments
      role: detail
      archetype: Comparative
      layout_variant: A
      variant_rationale: "Two install-day segmentations of equal weight."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "Halves: D1/D7 by engagement | D1 by game mode; insights under each."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:        [1, 1, 8, 2]
            nav:           [8, 1, 13, 2]
            engagement:    [1, 2, 7, 10]
            insight_eng:   [1, 10, 7, 13]
            mode:          [7, 2, 13, 10]
            insight_mode:  [7, 10, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "The first session decides who stays" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: engagement_col, region: engagement, kind: clusteredColumnChart, title: "Retention by install-day engagement", subtitle: "Players grouped by minutes of engagement (user_engagement.engagement_time_msec) on their install day.", field_bindings: { Category: "fact_day0_segments[segment]", Y: ["_Measures[Segment D1 Retention]", "_Measures[Segment D7 Retention]"] }, filters: "fact_day0_segments[dimension] = 'Day-0 engagement time'", sort_policy: "natural_order (segment_order)", color_strategy: measure_match, purpose: "Does more play on day 0 mean better D1/D7?" }
          - { id: insight_eng, region: insight_eng, kind: textbox, text: "29% of installs play under a minute on day 0; their D7 is 2.3% vs 12.0% for 15+ minutes.\nSource: fact_day0_segments.csv (dimension = Day-0 engagement time)", insight_basis: "verbatim insight from layout.md" }
          - { id: mode_bar, region: mode, kind: clusteredBarChart, title: "D1 retention by day-0 game mode", subtitle: "Mode played on install day: progression (levels), quickplay (boards) or both.", field_bindings: { Category: "fact_day0_segments[segment]", X: "_Measures[Segment D1 Retention]" }, filters: "fact_day0_segments[dimension] = 'Day-0 game mode'", sort_policy: value_desc, color_strategy: measure_match, purpose: "Which day-0 mode mix retains best on D1?" }
          - { id: insight_mode, region: insight_mode, kind: textbox, text: "Players who tried both modes keep 29.1% on D1 vs 17.8% for quickplay only. Payers are active a median 3 days vs 1.\nSource: fact_day0_segments.csv (dimension = Day-0 game mode)", insight_basis: "verbatim insight from layout.md" }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: engagement, pct_of_content: 36 }
          balance_rationale: "Equal halves; each chart keeps its insight directly underneath."

    - name: Churn model
      role: detail
      archetype: Analytical
      layout_variant: A
      variant_rationale: "Model quality (ROC) and drivers (importance) are equal-weight questions."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "Halves: ROC curve with y = x | top-8 permutation importance; insights under each."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:       [1, 1, 8, 2]
            nav:          [8, 1, 13, 2]
            roc:          [1, 2, 7, 10]
            insight_roc:  [1, 10, 7, 13]
            importance:   [7, 2, 13, 10]
            insight_imp:  [7, 10, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "Install-day behaviour ranks churn risk, but only weakly" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: roc_line, region: roc, kind: lineChart, title: "Churn prediction: ROC curve", subtitle: "Churned = no activity on days 7-30 after install. Features = install-day behaviour only. 75/25 stratified split, 5-fold CV.", field_bindings: { Category: "fact_churn_roc[fpr] (continuous)", Y: "fact_churn_roc[tpr] (Max)", Series: "fact_churn_roc[model]" }, reference: "y = x diagonal drawn from fact_churn_roc[fpr] (no new measure); method verified in Desktop", color_strategy: unique, purpose: "How well does each model separate churners from stayers?" }
          - { id: insight_roc, region: insight_roc, kind: textbox, text: "Logistic regression reaches test AUC 0.68 (CV 0.62); the depth-4 tree 0.60. Churn rate is 72.1% of 2,955 installs.\nSource: fact_churn_roc.csv, fact_churn_model_performance.csv", insight_basis: "verbatim insight from layout.md" }
          - { id: importance_bar, region: importance, kind: barChart, title: "What predicts churn", subtitle: "Permutation importance: drop in test AUC when one feature is shuffled.", field_bindings: { Category: "fact_churn_feature_importance[feature]", X: "_Measures[Permutation Importance]" }, filters: "model = logistic_regression; Top N 8 by Permutation Importance", sort_policy: value_desc, color_strategy: measure_match, purpose: "Which install-day features drive the model?" }
          - { id: insight_imp, region: insight_imp, kind: textbox, text: "Install-day engagement time leads. The riskiest decile churns at 86.5% vs 51.3% for the safest: useful for ranking, weak for individual targeting.\nSource: fact_churn_feature_importance.csv (model = logistic_regression)", insight_basis: "verbatim insight from layout.md" }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: roc, pct_of_content: 36 }
          balance_rationale: "Equal halves; ROC needs a square-ish area which 6 x 8 cells provides."

    - name: "A/B: observational tests and test design"
      role: detail
      archetype: Analytical
      layout_variant: B
      variant_rationale: "Wide 11-column test table needs width; the power curve is one series."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "Left: observational tests table + insight. Right: sample-size line (log y) + insight."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:        [1, 1, 8, 2]
            nav:           [8, 1, 13, 2]
            tests:         [1, 2, 8, 10]
            insight_tests: [1, 10, 8, 13]
            power:         [8, 2, 13, 10]
            insight_power: [8, 10, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "Platform gaps are real but not causal; a clean D1 test needs far more traffic" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: tests_tbl, region: tests, kind: tableEx, title: "Observational comparisons (not randomised)", subtitle: "Two-proportion z-test (= chi-square 2x2), 95% CI of the difference, Cohen's h. Traffic source compared within Android only.", field_bindings: ["fact_ab_observational_tests[comparison]", "fact_ab_observational_tests[metric]", "fact_ab_observational_tests[group_a]", "fact_ab_observational_tests[rate_a]", "fact_ab_observational_tests[group_b]", "fact_ab_observational_tests[rate_b]", "fact_ab_observational_tests[diff_a_minus_b]", "fact_ab_observational_tests[diff_ci_low]", "fact_ab_observational_tests[diff_ci_high]", "fact_ab_observational_tests[p_value]", "fact_ab_observational_tests[cohens_h]"], sort_policy: none, purpose: "Which observed group differences are statistically significant?" }
          - { id: insight_tests, region: insight_tests, kind: textbox, text: "iOS D1 is -3.8 pp vs Android (p = 0.005, h -0.09); on Android, google-play installs lead (direct) by +6.8 pp (p < 0.001). Correlation, not causation.\nSource: fact_ab_observational_tests.csv", insight_basis: "verbatim insight from layout.md" }
          - { id: power_line, region: power, kind: lineChart, title: "Sample size for a D1 retention A/B test", subtitle: "Two-sided test, alpha 0.05, power 0.8, baseline = observed D1; run time = 2 x n / installs per day.", field_bindings: { Category: "fact_ab_power_analysis[mde_abs]", Y: "fact_ab_power_analysis[n_per_arm] (Sum)", Tooltips: "fact_ab_power_analysis[days_needed_at_sample_volume] (Sum)" }, y_axis: log, color_strategy: measure_match, purpose: "How many players per arm does each minimum detectable effect need?" }
          - { id: insight_power, region: insight_power, kind: textbox, text: "Detecting +2 pp needs 6,834 players per arm: about 340 days at the sampled 40.3 installs per day. Run on full traffic or test bigger changes.\nSource: fact_ab_power_analysis.csv", insight_basis: "verbatim insight from layout.md" }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: tests, pct_of_content: 42 }
          balance_rationale: "11-column table needs the wider half; power curve stays readable at 5 columns."

    - name: Data limitations
      role: detail
      archetype: Narrative
      layout_variant: A
      variant_rationale: "Text-only page by spec: six verbatim caveats."
      navigation:
        - { element: page_navigator, action: PageNavigation, label: "Sections" }
      page_background: "#FCFCFB"
      layout_summary: "One wide text block with the six caveats as bullets."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            header:       [1, 1, 8, 2]
            nav:          [8, 1, 13, 2]
            limitations:  [1, 2, 13, 13]
        placements:
          - { id: page_title, region: header, kind: textbox, text: "What this data can and cannot tell us" }
          - { id: nav, region: nav, kind: pageNavigator }
          - { id: limitations_text, region: limitations, kind: textbox, text: "- Sampled export: exactly 50,000 events per day. Absolute counts describe the sample; rates are reliable.\n- 60% of players were acquired before the window; cohorts and LTV use installs inside it only.\n- 29% of new players have no first_open and are excluded from cohorts.\n- Only 27 purchases and no ad revenue: monetisation figures are directional.\n- Traffic source is confounded with platform (iOS is (direct) only); app_remove exists only on Android and is not used as a churn label.\n- Platform and source comparisons are observational, not causal.", insight_basis: "verbatim list from layout.md" }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: limitations, pct_of_content: 100 }
          balance_rationale: "Narrative text page by spec; a single readable column at large type is the intended treatment."
  interaction_pattern:
    drill_targets: []
    cross_filter_rules: "None needed: each visual uses its own table; DAU line and Installs columns share fact_daily_activity and cross-highlight."
  accessibility:
    alt_text_strategy: "chart title + verbatim insight sentence"
    contrast_notes: "#0B0B0B / #52514E on #FCFCFB pass AA; orange #EB6834 used for marks only, never for small text"
  theme:
    base: "references/design/assets/base.json adapted to FloodItEditorial colours/fonts"
    user_overrides: "Colours fixed by layout.md theme line"
```

## Implementation notes
- Model changes: none (done; 40/40 reconciliation PASS)
- PBIR/report authoring: generate pages/visuals with the powerbi-report-author CLI into powerbi/FloodIt.Report; register custom theme
- Validation: CLI validate + Desktop reload + screenshot every page; re-run reconciliation after reload
- Publishing boundary: local only
- Risks: ROC y = x reference and log axis on the power chart need Desktop verification; Desktop must be saved and closed before PBIR files are rewritten, then reopened
