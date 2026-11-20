# Validation report

Every headline metric is computed **twice** - (A) SQL directly on raw Firebase events and (B) Pandas on player-level extracts - and compared automatically by `src/flood_it/validate.py`. Invariant checks catch logic errors that both methods could share.

**Result: 32 / 32 checks PASS.**

| Area | Check | Method A | Method B | Value A | Value B | Max abs diff | Status |
|---|---|---|---|---|---|---|---|
| Data | Total events: table inventory vs event catalogue | SQL 00 COUNT(*) per table | SQL 01 events by name | 5.7e+06 | 5.7e+06 | 0 | PASS |
| Data | Total events: raw vs player-day extract | SQL 00 | Pandas sum(user_day.events) | 5.7e+06 | 5.7e+06 | 0 | PASS |
| Data | Distinct players: users table vs player-day table | SQL 10 rows | Pandas nunique(user_day.user_id) | 15,175 | 15,175 | 0 | PASS |
| Growth | Daily DAU (114 days) | SQL 20 from raw events | Pandas daily_growth(user_day) | sum=59,037 | sum=59,037 | 0 | PASS |
| Growth | Daily INSTALLS (114 days) | SQL 20 from raw events | Pandas daily_growth(user_day) | sum=4,319 | sum=4,319 | 0 | PASS |
| Growth | Daily FIRST_SEEN_USERS (114 days) | SQL 20 from raw events | Pandas daily_growth(user_day) | sum=15,175 | sum=15,175 | 0 | PASS |
| Growth | Daily WAU (114 days) | SQL 20 from raw events | Pandas daily_growth(user_day) | sum=230,380 | sum=230,380 | 0 | PASS |
| Growth | Daily MAU (114 days) | SQL 20 from raw events | Pandas daily_growth(user_day) | sum=579,323 | sum=579,323 | 0 | PASS |
| Retention | Cohort-week x day-N cohort_users (85 cells) | SQL 30 from raw events | Pandas retention_table | sum=21,535 | sum=21,535 | 0 | PASS |
| Retention | Cohort-week x day-N eligible_users (85 cells) | SQL 30 from raw events | Pandas retention_table | sum=19,019 | sum=19,019 | 0 | PASS |
| Retention | Cohort-week x day-N retained_users (85 cells) | SQL 30 from raw events | Pandas retention_table | sum=1,759 | sum=1,759 | 0 | PASS |
| Retention | Pooled D1 retention | SQL 30 sum(retained)/sum(eligible) | Pandas | 0.214673 | 0.214673 | 0 | PASS |
| Retention | Pooled D3 retention | SQL 30 sum(retained)/sum(eligible) | Pandas | 0.104373 | 0.104373 | 0 | PASS |
| Retention | Pooled D7 retention | SQL 30 sum(retained)/sum(eligible) | Pandas | 0.0554441 | 0.0554441 | 0 | PASS |
| Retention | Pooled D14 retention | SQL 30 sum(retained)/sum(eligible) | Pandas | 0.0362162 | 0.0362162 | 0 | PASS |
| Retention | Pooled D30 retention | SQL 30 sum(retained)/sum(eligible) | Pandas | 0.0209814 | 0.0209814 | 0 | PASS |
| Revenue | active_users by platform (ALL/ANDROID/IOS) | SQL 40 from raw events | Pandas monetization_kpis | sum=30,350 | sum=30,350 | 0 | PASS |
| Revenue | user_days by platform (ALL/ANDROID/IOS) | SQL 40 from raw events | Pandas monetization_kpis | sum=118,074 | sum=118,074 | 0 | PASS |
| Revenue | payers by platform (ALL/ANDROID/IOS) | SQL 40 from raw events | Pandas monetization_kpis | sum=54 | sum=54 | 0 | PASS |
| Revenue | purchases by platform (ALL/ANDROID/IOS) | SQL 40 from raw events | Pandas monetization_kpis | sum=54 | sum=54 | 0 | PASS |
| Revenue | revenue_usd by platform (ALL/ANDROID/IOS) | SQL 40 from raw events | Pandas monetization_kpis | sum=63.7126 | sum=63.7126 | 0 | PASS |
| Levels | Level 1-30 starts | SQL 50 from raw events | Pandas from player x level (SQL 51) | sum=74,417 | sum=74,417 | 0 | PASS |
| Levels | Level 1-30 completes | SQL 50 from raw events | Pandas from player x level (SQL 51) | sum=32,714 | sum=32,714 | 0 | PASS |
| Levels | Level 1-30 fails | SQL 50 from raw events | Pandas from player x level (SQL 51) | sum=17,210 | sum=17,210 | 0 | PASS |
| Levels | Level 1-30 users_started | SQL 50 from raw events | Pandas from player x level (SQL 51) | sum=35,181 | sum=35,181 | 0 | PASS |
| Levels | Level 1-30 users_completed | SQL 50 from raw events | Pandas from player x level (SQL 51) | sum=26,505 | sum=26,505 | 0 | PASS |
| Sanity | D0 retention = 100% (every cohort player active on install day) | retention curve | invariant | D0=1.0000 |  | 0 | PASS |
| Sanity | Eligible players never increase with N (right-censoring) | retention curve | invariant | 4307 -> 2955 |  | 0 | PASS |
| Sanity | Fixed-population LTV curve is non-decreasing | ltv_curve | invariant | D0=0.002366, D30=0.002701 |  | 0 | PASS |
| Sanity | Every cohort player has install date inside the window | cohort | invariant | 2018-06-12..2018-10-03 |  | 0 | PASS |
| Sanity | Every purchase has a USD value (event_value_in_usd or USD fallback) | 12_iap | invariant | missing=0 |  | 0 | PASS |
| Sanity | DAU <= WAU <= MAU every day | daily growth | invariant | all 114 days |  | 0 | PASS |

AI-assisted development: mistakes caught during the build are logged in [docs/ai_corrections.md](../docs/ai_corrections.md).
