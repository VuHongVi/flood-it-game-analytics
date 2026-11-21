# CV - Selected Projects

**Flood-It Mobile Game Analytics (Firebase/GA4, BigQuery, Python, Power BI)** - https://github.com/VuHongVi/flood-it-game-analytics

- Built an automated BigQuery + Python pipeline on 5,700,000 Firebase events / 15,175 players
  (cost-guarded dry-runs, cached and reproducible in CI) covering DAU/stickiness, cohort retention with right-censoring
  (D1 21.5%, D30 2.1%), ARPU/ARPPU/LTV and level funnels; cross-validated every
  headline metric in SQL vs Pandas (32/32 checks pass).
- Found that level 27 stops 45.7% of new players who reach it
  (4.5% completion per attempt) and that installs playing under 1 minute on day 0 keep
  2.3% on D7 vs 12.0% for 15+ minutes; built a churn model on
  install-day behaviour (logistic regression, test AUC 0.68) and an A/B test plan with power analysis
  (6,834 players per arm for +2 pp D1).
- Sized each recommendation: closing the first-minute gap is worth +5.7
  D7 players per 1,000 installs (+10% relative D7) and bringing level
  27 to a median quit rate keeps 394 more of every
  1,000 players who reach it; showed the churn model is a ranking tool (1.2x random
  in the riskiest 30%), not a personalisation tool.
- Diagnosed data-quality traps with SQL (sampled export, DAU spikes caused by missing screen_view events, mixed-type
  params, missing first_open) and delivered a 9-page Power BI report (DAX, TMDL/PBIR generated from code) reconciled
  to the pipeline row by row.
