"""Sections 1-4: data profiling, growth, retention, revenue.

Each function takes the extracted frames, writes tidy CSVs to data/ and returns a dict that
is merged into results/metrics.json. Every number shown anywhere downstream comes from here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics as M
from .io import save_csv


def _r(x, nd=4):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), nd)


# ----------------------------------------------------------------------------- 1. profile
def profile(raw: dict, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    inv, ev, pk, users = raw["00_table_inventory"], raw["01_event_counts"], raw["02_event_param_keys"], raw["10_users"]

    cat = ev.pivot_table(index="event_name", columns="platform", values="events", aggfunc="sum", fill_value=0)
    cat.columns = [f"events_{c.lower()}" for c in cat.columns]
    usr = ev.pivot_table(index="event_name", columns="platform", values="users", aggfunc="sum", fill_value=0)
    usr.columns = [f"users_{c.lower()}" for c in usr.columns]
    cat = cat.join(usr).reset_index()
    cat["events_total"] = cat["events_android"] + cat["events_ios"]
    cat["share_of_events"] = cat["events_total"] / cat["events_total"].sum()
    cat["platform_coverage"] = np.select(
        [cat["events_ios"].eq(0), cat["events_android"].eq(0)], ["ANDROID only", "IOS only"], "both")
    cat = cat.sort_values("events_total", ascending=False)
    save_csv(cat, "p1_event_catalog")

    # mixed-type params (trap: `level` in int_value AND double_value)
    pk = pk.copy()
    pk["n_typed_slots"] = (pk[["n_string", "n_int", "n_float", "n_double"]] > 0).sum(axis=1)
    mixed = pk[pk["n_typed_slots"] > 1].sort_values("n", ascending=False)
    save_csv(mixed, "p1_mixed_type_params")

    u = users.copy()
    u["first_touch_date_utc"] = M.to_date(u["first_touch_date_utc"])
    in_range = u["first_touch_date_utc"].between(start, end + pd.Timedelta(days=1))
    before = u["first_touch_date_utc"] < start
    has_fo = u["first_open_date"].notna()
    seg = pd.DataFrame({
        "segment": ["acquired_before_window", "acquired_in_window_with_first_open",
                    "acquired_in_window_missing_first_open", "other"],
        "users": [int(before.sum()), int((in_range & has_fo).sum()), int((in_range & ~has_fo).sum()),
                  int((~before & ~in_range).sum())],
    })
    seg["share"] = seg["users"] / seg["users"].sum()
    save_csv(seg, "p1_user_segments")

    # time-zone evidence: event_date (property tz) vs UTC first-touch date
    x = u[in_range & has_fo]
    tz_gap = (M.to_date(x["first_seen_date"]) - x["first_touch_date_utc"]).dt.days
    plat = u["platform"].value_counts()
    ts = (u.assign(traffic_source=u["traffic_source"].fillna("(null)"))
            .groupby(["platform", "traffic_source"]).size().rename("users").reset_index()
            .sort_values(["platform", "users"], ascending=[True, False]))
    save_csv(ts, "p1_traffic_source_by_platform")

    countries = u["country"].value_counts().head(10).rename_axis("country").reset_index(name="users")
    countries["share"] = countries["users"] / len(u)
    save_csv(countries, "p1_top_countries")

    events_per_day = inv["events"]
    return {
        "date_start": start.strftime("%Y-%m-%d"), "date_end": end.strftime("%Y-%m-%d"),
        "n_days": int(len(inv)),
        "total_events": int(events_per_day.sum()),
        "events_per_day_min": int(events_per_day.min()), "events_per_day_max": int(events_per_day.max()),
        "sampled_constant_daily_events": bool(events_per_day.nunique() == 1),
        "n_event_names": int(ev["event_name"].nunique()),
        "total_users": int(len(u)),
        "users_android": int(plat.get("ANDROID", 0)), "users_ios": int(plat.get("IOS", 0)),
        "users_acquired_before_window": int(before.sum()),
        "share_acquired_before_window": _r(before.mean()),
        "users_new_in_window": int(in_range.sum()),
        "users_new_with_first_open": int((in_range & has_fo).sum()),
        "users_new_missing_first_open": int((in_range & ~has_fo).sum()),
        "share_new_missing_first_open": _r((in_range & ~has_fo).sum() / in_range.sum()),
        "users_with_first_open_total": int(has_fo.sum()),
        "tz_event_date_one_day_before_utc_users": int((tz_gap == -1).sum()),
        "tz_event_date_same_as_utc_users": int((tz_gap == 0).sum()),
        "users_multi_platform": int((u["n_platforms"] > 1).sum()),
        "users_multi_traffic_source": int((u["n_traffic_sources"] > 1).sum()),
        "ios_users_direct_share": _r((u.loc[u.platform == "IOS", "traffic_source"] == "(direct)").mean()),
        "google_play_users": int((u["traffic_source"] == "google-play").sum()),
        "android_only_events": cat.loc[cat.platform_coverage == "ANDROID only", "event_name"].tolist(),
        "ios_only_events": cat.loc[cat.platform_coverage == "IOS only", "event_name"].tolist(),
        "mixed_type_level_events": sorted(mixed.loc[mixed.key == "level", "event_name"].tolist()),
        "top_country": countries.iloc[0]["country"], "top_country_share": _r(countries.iloc[0]["share"]),
    }


# ----------------------------------------------------------------------------- 2. growth
def growth(raw: dict) -> dict:
    g = M.daily_growth(raw["11_user_day"], raw["10_users"])
    g = M.flag_spikes(g)
    out = g.copy()
    out["activity_date"] = out["activity_date"].dt.strftime("%Y-%m-%d")
    save_csv(out, "p2_daily_growth")

    full = g[g["full_30d_window"]]
    spikes = g[g["is_spike"]].copy()
    spikes["new_share"] = spikes["first_seen_users"] / spikes["dau"]
    sp = spikes.assign(activity_date=spikes["activity_date"].dt.strftime("%Y-%m-%d"))
    save_csv(sp[["activity_date", "dau", "installs", "first_seen_users", "returning_dau",
                 "events_per_dau", "dau_vs_median", "new_share"]], "p2_dau_spikes")
    peak = g.loc[g["dau"].idxmax()]

    # Root cause of spikes: event mix on spike vs normal days inside the investigation window
    mix = raw["21_spike_event_mix"].copy()
    spike_dates = set(sp["activity_date"])
    mix["day_type"] = np.where(mix["activity_date"].isin(spike_dates), "spike", "normal")
    ndays = mix.groupby("day_type")["activity_date"].nunique()
    em = (mix.groupby(["day_type", "event_name"])["events"].sum().unstack("day_type").fillna(0)
             .div(ndays, axis=1).rename(columns={"normal": "avg_events_normal_day",
                                                 "spike": "avg_events_spike_day"}))
    em["ratio_spike_vs_normal"] = em["avg_events_spike_day"] / em["avg_events_normal_day"]
    em = em.sort_values("avg_events_normal_day", ascending=False).reset_index()
    save_csv(em, "p2_spike_event_mix")
    sv = em.set_index("event_name").loc["screen_view"]
    normal = g[~g["is_spike"]]
    return {
        "avg_dau": _r(g["dau"].mean(), 1), "median_dau": _r(g["dau"].median(), 1),
        "peak_dau": int(peak["dau"]), "peak_dau_date": peak["activity_date"].strftime("%Y-%m-%d"),
        "peak_dau_installs": int(peak["installs"]), "peak_dau_returning": int(peak["returning_dau"]),
        "avg_daily_installs": _r(g["installs"].mean(), 1),
        "total_installs_first_open": int(g["installs"].sum()),
        "avg_wau_full_window": _r(g.loc[g["full_7d_window"], "wau"].mean(), 1),
        "avg_mau_full_window": _r(full["mau"].mean(), 1),
        "avg_stickiness": _r(full["stickiness"].mean()),
        "stickiness_min": _r(full["stickiness"].min()), "stickiness_max": _r(full["stickiness"].max()),
        "n_spike_days": int(g["is_spike"].sum()),
        "spike_dates": sp["activity_date"].tolist(),
        "avg_dau_excl_spikes": _r(normal["dau"].mean(), 1),
        "spike_avg_dau": _r(spikes["dau"].mean(), 1),
        "spike_avg_installs": _r(spikes["installs"].mean(), 1),
        "spike_events_per_dau": _r(spikes["events_per_dau"].mean(), 1),
        "normal_events_per_dau": _r(normal["events_per_dau"].mean(), 1),
        "spike_screen_view_ratio": _r(sv["ratio_spike_vs_normal"], 3),
        "screen_view_avg_normal_day": _r(sv["avg_events_normal_day"], 0),
        "screen_view_avg_spike_day": _r(sv["avg_events_spike_day"], 0),
        "avg_new_share_of_dau": _r((g["first_seen_users"] / g["dau"]).mean()),
    }


# ----------------------------------------------------------------------------- 3. retention
def retention(raw: dict, cohort: pd.DataFrame, day_ns, end: pd.Timestamp) -> dict:
    ud = raw["11_user_day"]
    wk = M.retention_table(cohort, ud, day_ns, end, by="cohort_week")
    wk["cohort_week"] = wk["cohort_week"].dt.strftime("%Y-%m-%d")
    save_csv(wk, "p3_retention_by_cohort_week")

    curve = M.retention_table(cohort, ud, range(0, 31), end, by=None)
    save_csv(curve, "p3_retention_curve")

    plat = M.retention_table(cohort, ud, day_ns, end, by="platform")
    save_csv(plat, "p3_retention_by_platform")

    c = curve.set_index("day_n")
    sizes = cohort.groupby("cohort_week").size()
    out = {
        "cohort_users": int(len(cohort)),
        "cohort_weeks": int(cohort["cohort_week"].nunique()),
        "cohort_week_min_size": int(sizes.min()), "cohort_week_max_size": int(sizes.max()),
        "definition": "classic Day-N: active on install_date+N; rate over eligible (uncensored) players",
    }
    for n in day_ns:
        out[f"d{n}_retention"] = _r(c.loc[n, "retention"])
        out[f"d{n}_eligible"] = int(c.loc[n, "eligible_users"])
        out[f"d{n}_retained"] = int(c.loc[n, "retained_users"])
        out[f"d{n}_ci_low"] = _r(c.loc[n, "ci_low"])
        out[f"d{n}_ci_high"] = _r(c.loc[n, "ci_high"])
    # best / worst weekly cohort on D7 (only cohorts with >=100 eligible players)
    d7 = wk[(wk.day_n == 7) & (wk.eligible_users >= 100)]
    if len(d7):
        b, w = d7.loc[d7.retention.idxmax()], d7.loc[d7.retention.idxmin()]
        out.update({"d7_best_cohort": b.cohort_week, "d7_best_value": _r(b.retention),
                    "d7_worst_cohort": w.cohort_week, "d7_worst_value": _r(w.retention)})
    for _, r in plat.iterrows():
        out[f"d{int(r.day_n)}_retention_{r.platform.lower()}"] = _r(r.retention)
    return out


# ----------------------------------------------------------------------------- 4. revenue
def revenue(raw: dict, cohort: pd.DataFrame, ltv_days, end: pd.Timestamp) -> dict:
    iap = M.iap_revenue_usd(raw["12_iap"])
    save_csv(iap, "p4_iap_transactions")
    kpi = M.monetization_kpis(raw["11_user_day"], iap, raw["10_users"])
    save_csv(kpi, "p4_monetization_kpis")
    ltv = M.ltv_curve(cohort, iap, max(ltv_days), end, fixed_population=True)
    save_csv(ltv, "p4_ltv_curve")
    ltv_var = M.ltv_curve(cohort, iap, max(ltv_days), end, fixed_population=False)
    lv = ltv_var.set_index("day_n")

    ud = raw["11_user_day"]
    ads = ud["ad_rewards"].sum()
    all_ = kpi.set_index("platform").loc["ALL"]
    l = ltv.set_index("day_n")
    # user_ltv cross-check: rows where user_ltv.revenue disagrees with the per-event USD value
    mismatch = iap[(iap["user_ltv_revenue"] - iap["revenue_usd"]).abs() > 0.01]
    out = {
        "purchases": int(all_["purchases"]), "payers": int(all_["payers"]),
        "revenue_usd": _r(all_["revenue_usd"], 2),
        "payer_rate": _r(all_["payer_rate"], 6), "arpu_usd": _r(all_["arpu_usd"], 6),
        "arpdau_usd": _r(all_["arpdau_usd"], 6), "arppu_usd": _r(all_["arppu_usd"], 4),
        "iap_missing_event_value_in_usd": int(iap["event_value_in_usd"].isna().sum()),
        "iap_recovered_from_value_param": int((iap["revenue_source"] == "value_param_usd").sum()),
        "iap_non_usd_currency": int((iap["currency"] != "USD").sum()),
        "user_ltv_mismatch_rows": int(len(mismatch)),
        "top_product": iap["product_id"].value_counts().index[0],
        "top_product_share": _r(iap["product_id"].value_counts(normalize=True).iloc[0]),
        "ad_reward_events": int(ads),
        "ad_reward_users": int((ud.groupby("user_id")["ad_rewards"].sum() > 0).sum()),
    }
    for p in ["ANDROID", "IOS"]:
        r = kpi.set_index("platform").loc[p]
        out[f"payer_rate_{p.lower()}"] = _r(r["payer_rate"], 6)
        out[f"revenue_usd_{p.lower()}"] = _r(r["revenue_usd"], 2)
    # Headline LTV: fixed population = installs observable for the full 30 days (monotonic curve)
    for n in ltv_days:
        out[f"ltv_d{n}_usd"] = _r(l.loc[n, "ltv_usd"], 6)
        out[f"ltv_d{n}_payers"] = int(l.loc[n, "payers"])
        out[f"ltv_d{n}_revenue_usd"] = _r(l.loc[n, "revenue_usd"], 2)
    out["ltv_population_users"] = int(l.loc[max(ltv_days), "eligible_users"])
    # Sensitivity: each N on its own eligible population
    for n in ltv_days:
        out[f"ltv_d{n}_usd_own_population"] = _r(lv.loc[n, "ltv_usd"], 6)
        out[f"ltv_d{n}_own_population_users"] = int(lv.loc[n, "eligible_users"])
    cohort_payers_any = iap["user_id"].isin(cohort["user_id"]).sum()
    out["cohort_purchases_in_window"] = int(cohort_payers_any)
    return out
