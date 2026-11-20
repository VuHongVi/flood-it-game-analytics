"""Sections 5-8: level funnel, segments, churn model, statistics / A-B design."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.inspection import permutation_importance
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize, proportions_ztest

from . import metrics as M
from .io import save_csv

_r = lambda x, nd=4: None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)  # noqa: E731


def _p(x):
    """p-values keep 3 significant digits (rounding to 6 decimals would print 0.0)."""
    return None if x is None or np.isnan(x) else float(f"{float(x):.3g}")


# ----------------------------------------------------------------------------- 5. levels
def level_stats_from_user_level(ul: pd.DataFrame) -> pd.DataFrame:
    """Per progression level: attempts, completes, fails and distinct players (Pandas path)."""
    p = ul[ul["mode"] == "progression"].copy()
    p = p[pd.to_numeric(p["level_key"], errors="coerce").notna()]
    p["level"] = p["level_key"].astype(float).astype(int)
    g = p.groupby("level").agg(
        starts=("starts", "sum"), completes=("completes", "sum"), fails=("fails", "sum"),
        users_started=("starts", lambda s: int((s > 0).sum())),
        users_completed=("completes", lambda s: int((s > 0).sum())),
        users_failed=("fails", lambda s: int((s > 0).sum())),
    ).reset_index()
    return g


def levels(raw: dict, cohort: pd.DataFrame) -> dict:
    ls_sql, ul = raw["50_level_stats"], raw["51_user_level"]
    g = level_stats_from_user_level(ul)
    valid = g[(g["level"] >= 1) & (g["level"] <= 30)].copy()
    first = valid.loc[valid["level"] == 1, "users_started"].iloc[0]
    valid["reach_rate"] = valid["users_started"] / first                     # funnel vs level 1
    valid["completion_per_attempt"] = valid["completes"] / valid["starts"]   # difficulty (attempt level)
    valid["player_pass_rate"] = valid["users_completed"] / valid["users_started"]
    valid["attempts_per_player"] = valid["starts"] / valid["users_started"]
    valid["fail_per_attempt"] = valid["fails"] / valid["starts"]

    # Drop-off among NEW players (cohort): last level started, and quit rate at each level
    p = ul[(ul["mode"] == "progression") & ul["user_id"].isin(cohort["user_id"])].copy()
    p = p[pd.to_numeric(p["level_key"], errors="coerce").notna()]
    p["level"] = p["level_key"].astype(float).astype(int)
    p = p[(p["level"] >= 1) & (p["level"] <= 30) & (p["starts"] > 0)]
    last = p.groupby("user_id")["level"].max()
    reached = p.groupby("level")["user_id"].nunique()
    stopped = last.value_counts().reindex(reached.index, fill_value=0)
    drop = pd.DataFrame({"level": reached.index, "new_players_started": reached.values,
                         "new_players_last_level": stopped.values})
    drop["quit_rate_at_level"] = drop["new_players_last_level"] / drop["new_players_started"]
    # level 30 is the last level: stopping there means finishing, not quitting
    drop.loc[drop["level"] == drop["level"].max(), "quit_rate_at_level"] = np.nan
    valid = valid.merge(drop, on="level", how="left")
    save_csv(valid, "p5_level_funnel")

    # anomalies (tracking issues) kept visible, not silently dropped
    anomalies = ls_sql[(ls_sql["level"].isna()) | (ls_sql["level"] < 1) | (ls_sql["level"] > 30)].copy()
    anomalies["level"] = anomalies["level"].astype("Int64").astype(str).replace("<NA>", "NULL")
    save_csv(anomalies, "p5_level_anomalies")

    # quickplay boards
    q = ul[ul["mode"] == "quickplay"].groupby("level_key").agg(
        starts=("starts", "sum"), completes=("completes", "sum"), fails=("fails", "sum"),
        players=("user_id", "nunique")).reset_index().rename(columns={"level_key": "board"})
    q["completion_per_attempt"] = q["completes"] / q["starts"]
    q["fail_per_attempt"] = q["fails"] / q["starts"]
    save_csv(q, "p5_quickplay_boards")

    # players by mode (all players with any level event)
    modes = ul.groupby("user_id")["mode"].agg(lambda s: "both" if s.nunique() > 1 else s.iloc[0])
    hard = valid[valid["level"] < 30].nsmallest(3, "completion_per_attempt")
    quit_ = valid[(valid["level"] < 30) & (valid["new_players_started"] >= 50)].nlargest(3, "quit_rate_at_level")
    lv = valid.set_index("level")
    return {
        "n_levels": int(len(valid)),
        "players_started_level1": int(first),
        "players_completed_level30": int(lv.loc[30, "users_completed"]),
        "reach_rate_level10": _r(lv.loc[10, "reach_rate"]),
        "reach_rate_level20": _r(lv.loc[20, "reach_rate"]),
        "reach_rate_level30": _r(lv.loc[30, "reach_rate"]),
        "hardest_levels": hard["level"].astype(int).tolist(),
        "hardest_levels_completion": [_r(x) for x in hard["completion_per_attempt"]],
        "level27_attempts": int(lv.loc[27, "starts"]), "level27_completes": int(lv.loc[27, "completes"]),
        "level27_attempts_per_player": _r(lv.loc[27, "attempts_per_player"], 2),
        "easiest_band": "11-16",
        "easiest_band_completion_min": _r(lv.loc[11:16, "completion_per_attempt"].min()),
        "top_quit_levels": quit_["level"].astype(int).tolist(),
        "top_quit_rates": [_r(x) for x in quit_["quit_rate_at_level"]],
        "level1_quit_rate_new": _r(lv.loc[1, "quit_rate_at_level"]),
        "anomaly_complete_without_level": int(ls_sql.loc[ls_sql["level"].isna(), "completes"].sum()),
        "anomaly_level0_fails": int(ls_sql.loc[ls_sql["level"] == 0, "fails"].sum()),
        "anomaly_level31_retries": int(ls_sql.loc[ls_sql["level"] == 31, "retries"].sum()),
        "quickplay_completion": {r.board: _r(r.completion_per_attempt) for r in q.itertuples()},
        "quickplay_share_of_starts": _r(q["starts"].sum() / (q["starts"].sum() + valid["starts"].sum())),
        "players_mode_quickplay_only": int((modes == "quickplay").sum()),
        "players_mode_progression_only": int((modes == "progression").sum()),
        "players_mode_both": int((modes == "both").sum()),
    }


# ----------------------------------------------------------------------------- day-0 features
FEATURES_NUM = ["d0_events", "d0_sessions", "d0_engagement_min", "d0_level_starts", "d0_level_completes",
                "d0_level_fails", "d0_quickplay_starts", "d0_quickplay_completes", "d0_quickplay_fails",
                "d0_max_level", "d0_post_scores", "d0_ad_rewards", "d0_virtual_spends", "d0_app_exceptions"]
FEATURES_CAT = ["is_ios", "is_us", "is_google_play"]


def day0_features(cohort: pd.DataFrame, user_day: pd.DataFrame) -> pd.DataFrame:
    """Behaviour on the install day only (event_date == install_date) -> no label leakage."""
    ud = user_day.copy()
    ud["activity_date"] = M.to_date(ud["activity_date"])
    d0 = cohort[["user_id", "install_date", "platform", "country", "traffic_source"]].merge(
        ud, left_on=["user_id", "install_date"], right_on=["user_id", "activity_date"], how="left")
    f = pd.DataFrame({"user_id": d0["user_id"], "install_date": d0["install_date"]})
    mapping = {"events": "d0_events", "sessions": "d0_sessions", "level_starts": "d0_level_starts",
               "level_completes": "d0_level_completes", "level_fails": "d0_level_fails",
               "quickplay_starts": "d0_quickplay_starts", "quickplay_completes": "d0_quickplay_completes",
               "quickplay_fails": "d0_quickplay_fails", "max_level": "d0_max_level",
               "post_scores": "d0_post_scores", "ad_rewards": "d0_ad_rewards",
               "virtual_spends": "d0_virtual_spends", "app_exceptions": "d0_app_exceptions"}
    for src, dst in mapping.items():
        f[dst] = d0[src].fillna(0).values
    f["d0_engagement_min"] = d0["engagement_msec"].fillna(0).values / 60000
    f["is_ios"] = (d0["platform"] == "IOS").astype(int).values
    f["is_us"] = (d0["country"] == "United States").astype(int).values
    f["is_google_play"] = (d0["traffic_source"] == "google-play").astype(int).values
    f["platform"] = d0["platform"].values
    f["traffic_source"] = d0["traffic_source"].values
    return f


def add_outcomes(f: pd.DataFrame, user_day: pd.DataFrame, end: pd.Timestamp, churn_window) -> pd.DataFrame:
    act = user_day[["user_id", "activity_date"]].copy()
    act["activity_date"] = M.to_date(act["activity_date"])
    a = act.merge(f[["user_id", "install_date"]], on="user_id")
    a["day"] = (a["activity_date"] - a["install_date"]).dt.days
    lo, hi = churn_window
    out = f.copy()
    days = a.groupby("user_id")["day"].apply(set)
    s = out["user_id"].map(days).apply(lambda x: x if isinstance(x, set) else set())
    out["active_d1"] = s.apply(lambda x: int(1 in x))
    out["active_d7"] = s.apply(lambda x: int(7 in x))
    out["active_d7_d30"] = s.apply(lambda x: int(any(lo <= d <= hi for d in x)))
    out["elig_d1"] = (out["install_date"] + pd.Timedelta(days=1) <= end).astype(int)
    out["elig_d7"] = (out["install_date"] + pd.Timedelta(days=7) <= end).astype(int)
    out["elig_churn"] = (out["install_date"] + pd.Timedelta(days=hi) <= end).astype(int)
    out["churned"] = 1 - out["active_d7_d30"]
    return out


# ----------------------------------------------------------------------------- 6. segments
def _seg_rows(df: pd.DataFrame, dim: str, col: str) -> list[dict]:
    rows = []
    for seg, d in df.groupby(col, observed=True):
        d1, d7, ch = d[d.elig_d1 == 1], d[d.elig_d7 == 1], d[d.elig_churn == 1]
        rows.append({"dimension": dim, "segment": str(seg), "players": len(d),
                     "d1_eligible": len(d1), "d1_retention": d1["active_d1"].mean() if len(d1) else np.nan,
                     "d7_eligible": len(d7), "d7_retention": d7["active_d7"].mean() if len(d7) else np.nan,
                     "churn_eligible": len(ch), "churn_rate": ch["churned"].mean() if len(ch) else np.nan})
    return rows


def segments(raw: dict, feat: pd.DataFrame) -> dict:
    f = feat.copy()
    f["seg_engagement"] = pd.cut(f["d0_engagement_min"], [-0.01, 1, 5, 15, np.inf],
                                 labels=["<1 min", "1-5 min", "5-15 min", "15+ min"])
    f["seg_sessions"] = pd.cut(f["d0_sessions"], [-1, 0, 1, 2, np.inf], labels=["0", "1", "2", "3+"])
    lvl = f["d0_level_starts"] + f["d0_quickplay_starts"]
    f["seg_levels_played"] = pd.cut(lvl, [-1, 0, 4, 9, np.inf], labels=["0", "1-4", "5-9", "10+"])
    prog, quick = f["d0_level_starts"] > 0, f["d0_quickplay_starts"] > 0
    f["seg_mode"] = np.select([prog & quick, prog, quick], ["both", "progression only", "quickplay only"], "no level played")
    f["seg_platform"] = f["platform"]
    rows = []
    for dim, col in [("Day-0 engagement time", "seg_engagement"), ("Day-0 sessions", "seg_sessions"),
                     ("Day-0 levels played", "seg_levels_played"), ("Day-0 game mode", "seg_mode"),
                     ("Platform", "seg_platform")]:
        rows += _seg_rows(f, dim, col)
    seg = pd.DataFrame(rows)
    save_csv(seg, "p6_day0_segments")

    # payer vs non-payer (all players, lifetime-in-window behaviour; only a few dozen payers)
    ud, iap, users = raw["11_user_day"], raw["12_iap"], raw["10_users"]
    per = ud.groupby("user_id").agg(active_days=("activity_date", "nunique"), events=("events", "sum"),
                                    sessions=("sessions", "sum"), engagement_min=("engagement_msec", lambda s: s.sum() / 60000),
                                    level_starts=("level_starts", "sum"), quickplay_starts=("quickplay_starts", "sum"),
                                    ad_rewards=("ad_rewards", "sum")).reset_index()
    per["segment"] = np.where(per["user_id"].isin(iap["user_id"]), "payer", "non-payer")
    pv = per.groupby("segment").agg(players=("user_id", "count"),
                                    median_active_days=("active_days", "median"),
                                    median_sessions=("sessions", "median"),
                                    median_engagement_min=("engagement_min", "median"),
                                    median_level_starts=("level_starts", "median"),
                                    median_quickplay_starts=("quickplay_starts", "median"),
                                    share_watched_rewarded_ad=("ad_rewards", lambda s: (s > 0).mean())).reset_index()
    save_csv(pv, "p6_payer_vs_nonpayer")
    mw = stats.mannwhitneyu(per.loc[per.segment == "payer", "active_days"],
                            per.loc[per.segment == "non-payer", "active_days"], alternative="greater")

    s = seg.set_index(["dimension", "segment"])
    eng = s.loc["Day-0 engagement time"]
    pvi = pv.set_index("segment")
    return {
        "d7_retention_eng_lt1min": _r(eng.loc["<1 min", "d7_retention"]),
        "d7_retention_eng_15plus": _r(eng.loc["15+ min", "d7_retention"]),
        "d1_retention_eng_lt1min": _r(eng.loc["<1 min", "d1_retention"]),
        "d1_retention_eng_15plus": _r(eng.loc["15+ min", "d1_retention"]),
        "share_eng_lt1min": _r(eng.loc["<1 min", "players"] / eng["players"].sum()),
        "d1_retention_by_mode": {k: _r(v) for k, v in s.loc["Day-0 game mode", "d1_retention"].items()},
        "payer_median_active_days": _r(pvi.loc["payer", "median_active_days"], 1),
        "nonpayer_median_active_days": _r(pvi.loc["non-payer", "median_active_days"], 1),
        "payer_median_engagement_min": _r(pvi.loc["payer", "median_engagement_min"], 1),
        "nonpayer_median_engagement_min": _r(pvi.loc["non-payer", "median_engagement_min"], 1),
        "payer_vs_nonpayer_active_days_mannwhitney_p": _p(mw.pvalue),
    }


# ----------------------------------------------------------------------------- 7. churn model
def churn_model(feat: pd.DataFrame, seed: int) -> dict:
    d = feat[feat["elig_churn"] == 1].reset_index(drop=True)
    X = d[FEATURES_NUM + FEATURES_CAT].astype(float)
    y = d["churned"].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=seed)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)

    num_idx = list(range(len(FEATURES_NUM)))
    logit = make_pipeline(
        FunctionTransformer(lambda a: np.c_[np.log1p(a[:, num_idx]), a[:, len(num_idx):]], validate=False),
        StandardScaler(),
        LogisticRegression(max_iter=2000, class_weight="balanced"))
    tree = DecisionTreeClassifier(max_depth=4, min_samples_leaf=40, class_weight="balanced", random_state=seed)

    rows, roc_rows, imp_rows = [], [], []
    fitted = {}
    for name, model in [("logistic_regression", logit), ("decision_tree", tree)]:
        cv_auc = cross_val_score(model, X_tr.values, y_tr.values, cv=cv, scoring="roc_auc")
        model.fit(X_tr.values, y_tr.values)
        p = model.predict_proba(X_te.values)[:, 1]
        auc = roc_auc_score(y_te, p)
        rows.append({"model": name, "cv_auc_mean": cv_auc.mean(), "cv_auc_std": cv_auc.std(),
                     "test_auc": auc, "train_n": len(y_tr), "test_n": len(y_te),
                     "test_churn_rate": y_te.mean()})
        fpr, tpr, _ = roc_curve(y_te, p)
        grid = np.linspace(0, 1, 51)
        roc_rows += [{"model": name, "fpr": g, "tpr": float(np.interp(g, fpr, tpr))} for g in grid]
        pi = permutation_importance(model, X_te.values, y_te.values, scoring="roc_auc",
                                    n_repeats=20, random_state=seed)
        for i, col in enumerate(X.columns):
            imp_rows.append({"model": name, "feature": col, "permutation_auc_drop": pi.importances_mean[i],
                             "permutation_auc_drop_std": pi.importances_std[i]})
        fitted[name] = (model, p)

    perf = pd.DataFrame(rows)
    save_csv(perf, "p7_model_performance")
    save_csv(pd.DataFrame(roc_rows), "p7_roc_curve")
    coefs = fitted["logistic_regression"][0][-1].coef_[0]
    imp = pd.DataFrame(imp_rows)
    coef_df = pd.DataFrame({"model": "logistic_regression", "feature": X.columns, "std_coefficient": coefs})
    imp = imp.merge(coef_df, on=["model", "feature"], how="left")
    tree_imp = pd.DataFrame({"model": "decision_tree", "feature": X.columns,
                             "gini_importance": fitted["decision_tree"][0].feature_importances_})
    imp = imp.merge(tree_imp, on=["model", "feature"], how="left")
    imp = imp.sort_values(["model", "permutation_auc_drop"], ascending=[True, False])
    save_csv(imp, "p7_feature_importance")

    # lift by risk decile (logistic regression, test set)
    p = fitted["logistic_regression"][1]
    dec = pd.DataFrame({"p": p, "y": y_te.values})
    dec["risk_decile"] = pd.qcut(dec["p"].rank(method="first"), 10, labels=range(1, 11)).astype(int)
    lift = dec.groupby("risk_decile").agg(players=("y", "size"), churn_rate=("y", "mean"),
                                          avg_predicted=("p", "mean")).reset_index()
    save_csv(lift, "p7_risk_deciles")

    rules = export_text(fitted["decision_tree"][0], feature_names=list(X.columns), max_depth=3)
    from ..config import load_config
    (load_config().path("results_dir") / "churn_tree_rules.txt").write_text(rules, encoding="utf-8", newline="\n")

    lr = perf.set_index("model").loc["logistic_regression"]
    dt = perf.set_index("model").loc["decision_tree"]
    top_lr = imp[imp.model == "logistic_regression"].head(5)
    top_dt = imp[imp.model == "decision_tree"].head(5)
    coef_lr = coef_df.set_index("feature")["std_coefficient"]
    return {
        "definition": "churned = no activity on day 7..30 after install; features = install-day behaviour only",
        "population": int(len(d)), "churn_rate": _r(y.mean()),
        "lr_cv_auc_mean": _r(lr.cv_auc_mean), "lr_cv_auc_std": _r(lr.cv_auc_std), "lr_test_auc": _r(lr.test_auc),
        "tree_cv_auc_mean": _r(dt.cv_auc_mean), "tree_cv_auc_std": _r(dt.cv_auc_std), "tree_test_auc": _r(dt.test_auc),
        "lr_top_features": top_lr["feature"].tolist(),
        "lr_top_features_coef": [_r(coef_lr[f], 3) for f in top_lr["feature"]],
        "tree_top_features": top_dt["feature"].tolist(),
        "top_decile_churn_rate": _r(lift.iloc[-1]["churn_rate"]),
        "bottom_decile_churn_rate": _r(lift.iloc[0]["churn_rate"]),
        "test_n": int(lr.test_n), "train_n": int(lr.train_n),
    }


# ----------------------------------------------------------------------------- 8. statistics
def two_prop_test(x1, n1, x2, n2, label1, label2, metric, comparison, note=""):
    p1, p2 = x1 / n1, x2 / n2
    z, p = proportions_ztest([x1, x2], [n1, n2])
    se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    diff = p1 - p2
    chi2, p_chi, _, _ = stats.chi2_contingency([[x1, n1 - x1], [x2, n2 - x2]], correction=False)
    return {"comparison": comparison, "metric": metric, "group_a": label1, "group_b": label2,
            "n_a": n1, "x_a": x1, "rate_a": p1, "n_b": n2, "x_b": x2, "rate_b": p2,
            "diff_a_minus_b": diff, "diff_ci_low": diff - 1.96 * se, "diff_ci_high": diff + 1.96 * se,
            "z": z, "p_value": p, "chi2": chi2, "chi2_p_value": p_chi,
            "cohens_h": 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2)),
            "relative_lift": diff / p2 if p2 else np.nan, "note": note}


def statistics_ab(feat: pd.DataFrame, growth: pd.DataFrame | None, retention_d1: float) -> dict:
    tests = []
    for metric, elig, act in [("D1 retention", "elig_d1", "active_d1"), ("D7 retention", "elig_d7", "active_d7")]:
        d = feat[feat[elig] == 1]
        a, b = d[d.platform == "IOS"], d[d.platform == "ANDROID"]
        tests.append(two_prop_test(int(a[act].sum()), len(a), int(b[act].sum()), len(b), "IOS", "ANDROID",
                                   metric, "Platform: iOS vs Android",
                                   "Observational: platforms differ in audience, store, app version"))
        and_ = d[d.platform == "ANDROID"]
        gp, dr = and_[and_.traffic_source == "google-play"], and_[and_.traffic_source == "(direct)"]
        tests.append(two_prop_test(int(gp[act].sum()), len(gp), int(dr[act].sum()), len(dr),
                                   "google-play", "(direct)", metric,
                                   "Traffic source (Android only): google-play vs (direct)",
                                   "Restricted to Android because iOS has no source other than (direct) - avoids platform confounding"))
    t = pd.DataFrame(tests)
    save_csv(t, "p8_observational_tests")

    # traffic source x platform (shows the confounder)
    conf = feat.assign(src=feat["traffic_source"].fillna("(null)")).groupby(["platform", "src"]).size() \
               .rename("cohort_players").reset_index().rename(columns={"src": "traffic_source"})
    save_csv(conf, "p8_source_platform_confounding")

    # ---- A/B test design: power analysis on D1 retention
    base = retention_d1
    installs_per_day = None
    if growth is not None:
        normal = growth[~growth["is_spike"]]
        installs_per_day = float(normal["installs"].mean())
    rows = []
    for mde_pp in [0.01, 0.02, 0.03, 0.05]:
        es = proportion_effectsize(base + mde_pp, base)
        n = NormalIndPower().solve_power(effect_size=es, alpha=0.05, power=0.8, ratio=1.0, alternative="two-sided")
        n = int(np.ceil(n))
        days = int(np.ceil(2 * n / installs_per_day)) if installs_per_day else None
        rows.append({"metric": "D1 retention", "baseline": base, "mde_abs": mde_pp,
                     "mde_relative": mde_pp / base, "alpha": 0.05, "power": 0.8,
                     "n_per_arm": n, "total_n": 2 * n,
                     "sample_installs_per_day": installs_per_day,
                     "days_needed_at_sample_volume": days,
                     "days_needed_incl_d1_lag": days + 1 if days else None})
    pw = pd.DataFrame(rows)
    save_csv(pw, "p8_power_analysis")

    tt = t.set_index(["comparison", "metric"])
    plat_d1 = tt.loc[("Platform: iOS vs Android", "D1 retention")]
    plat_d7 = tt.loc[("Platform: iOS vs Android", "D7 retention")]
    src_d1 = tt.loc[("Traffic source (Android only): google-play vs (direct)", "D1 retention")]
    src_d7 = tt.loc[("Traffic source (Android only): google-play vs (direct)", "D7 retention")]
    p2 = pw.set_index("mde_abs").loc[0.02]
    return {
        "d1_ios": _r(plat_d1.rate_a), "d1_android": _r(plat_d1.rate_b),
        "d1_platform_diff": _r(plat_d1.diff_a_minus_b), "d1_platform_ci": [_r(plat_d1.diff_ci_low), _r(plat_d1.diff_ci_high)],
        "d1_platform_p": _p(plat_d1.p_value), "d1_platform_cohens_h": _r(plat_d1.cohens_h, 3),
        "d7_platform_diff": _r(plat_d7.diff_a_minus_b), "d7_platform_p": _p(plat_d7.p_value),
        "d1_gp": _r(src_d1.rate_a), "d1_direct_android": _r(src_d1.rate_b),
        "d1_source_diff": _r(src_d1.diff_a_minus_b), "d1_source_ci": [_r(src_d1.diff_ci_low), _r(src_d1.diff_ci_high)],
        "d1_source_p": _p(src_d1.p_value), "d1_source_cohens_h": _r(src_d1.cohens_h, 3),
        "d7_source_diff": _r(src_d7.diff_a_minus_b), "d7_source_p": _p(src_d7.p_value),
        "n_gp_android": int(src_d1.n_a), "n_direct_android": int(src_d1.n_b),
        "ab_baseline_d1": _r(base), "ab_mde_abs": 0.02, "ab_n_per_arm": int(p2.n_per_arm),
        "ab_sample_installs_per_day": _r(installs_per_day, 1),
        "ab_days_needed_at_sample_volume": int(p2.days_needed_at_sample_volume),
    }


# ----------------------------------------------------------------------------- orchestrator
def run_all(ctx: dict, cohort: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    raw, a = ctx["raw"], ctx["cfg"].analysis
    feat = day0_features(cohort, raw["11_user_day"])
    feat = add_outcomes(feat, raw["11_user_day"], end, a["churn"]["churn_window"])
    ctx["features"] = feat
    growth = pd.read_csv(ctx["cfg"].path("data_dir") / "p2_daily_growth.csv")
    d1 = ctx.get("metrics_b_retention_d1")
    if d1 is None:
        d1 = M.retention_table(cohort, raw["11_user_day"], [1], end, by=None)["retention"].iloc[0]
    return {
        "levels": levels(raw, cohort),
        "segments": segments(raw, feat),
        "churn": churn_model(feat, a["random_seed"]),
        "stats": statistics_ab(feat, growth, float(d1)),
    }
