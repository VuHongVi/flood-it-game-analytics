"""Pure metric functions (unit-tested in tests/). No I/O here.

Conventions
-----------
* A "day" is event_date (property time zone). Every date column is a pandas Timestamp.
* Install cohort = players with a first_open event in the window whose UTC first-touch is not
  before the window start (re-installs of older players are excluded).
* Day-N retention is "classic/exact": active on install_date + N. Right-censoring is handled
  by computing the rate over ELIGIBLE players only (install_date + N <= last data date).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ----------------------------------------------------------------------------- helpers
def to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")


def wilson_ci(successes, n, alpha: float = 0.05):
    """Wilson score interval for a binomial proportion (works for small n / p near 0)."""
    successes = np.asarray(successes, dtype=float)
    n = np.asarray(n, dtype=float)
    z = stats.norm.ppf(1 - alpha / 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = successes / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


# ----------------------------------------------------------------------------- cohort
def build_install_cohort(users: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """Players eligible for cohort / LTV analysis (see module docstring)."""
    u = users.copy()
    u["first_open_date"] = to_date(u["first_open_date"])
    u["first_touch_date_utc"] = to_date(u["first_touch_date_utc"])
    c = u[u["first_open_date"].notna() & (u["first_touch_date_utc"] >= start)].copy()
    c["install_date"] = c["first_open_date"]
    # ISO week starting Monday
    c["cohort_week"] = c["install_date"] - pd.to_timedelta(c["install_date"].dt.day_of_week, unit="D")
    return c


# ----------------------------------------------------------------------------- growth
def daily_growth(user_day: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    """DAU, installs, new/returning split, WAU (7d), MAU (30d), stickiness = DAU/MAU."""
    ud = user_day[["user_id", "activity_date"]].copy()
    ud["activity_date"] = to_date(ud["activity_date"])
    days = pd.Index(sorted(ud["activity_date"].unique()), name="activity_date")
    dau = ud.groupby("activity_date")["user_id"].nunique().reindex(days, fill_value=0)
    if "events" in user_day:
        ev = user_day.assign(activity_date=to_date(user_day["activity_date"])) \
                     .groupby("activity_date")["events"].sum().reindex(days, fill_value=0)
    else:
        ev = pd.Series(np.nan, index=days)

    fo = to_date(users["first_open_date"]).value_counts().reindex(days, fill_value=0)
    first_seen = ud.groupby("user_id")["activity_date"].min().value_counts().reindex(days, fill_value=0)

    def rolling_distinct(window: int) -> pd.Series:
        out = {}
        for d in days:
            m = (ud["activity_date"] > d - pd.Timedelta(days=window)) & (ud["activity_date"] <= d)
            out[d] = ud.loc[m, "user_id"].nunique()
        return pd.Series(out).reindex(days)

    wau, mau = rolling_distinct(7), rolling_distinct(30)
    df = pd.DataFrame({
        "dau": dau.values, "installs": fo.values, "first_seen_users": first_seen.values,
        "wau": wau.values, "mau": mau.values, "events": ev.values,
    }, index=days).reset_index()
    df["returning_dau"] = df["dau"] - df["first_seen_users"]
    start = days.min()
    # WAU/MAU only meaningful once the trailing window is fully inside the data
    df["full_7d_window"] = df["activity_date"] >= start + pd.Timedelta(days=6)
    df["full_30d_window"] = df["activity_date"] >= start + pd.Timedelta(days=29)
    df["stickiness"] = np.where(df["full_30d_window"], df["dau"] / df["mau"], np.nan)
    return df


def flag_spikes(growth: pd.DataFrame, threshold: float = 1.5) -> pd.DataFrame:
    """Flag days whose DAU exceeds `threshold` x the period median DAU.

    A global median is used on purpose: the spikes cluster in consecutive days, which
    contaminates a rolling median. Also exposes events-per-active-user: in a sample capped at a
    fixed number of events per day, a drop in events/user mechanically inflates DAU.
    """
    g = growth.copy()
    g["dau_vs_median"] = g["dau"] / g["dau"].median()
    g["is_spike"] = g["dau_vs_median"] > threshold
    if "events" in g:
        g["events_per_dau"] = g["events"] / g["dau"]
    return g


# ----------------------------------------------------------------------------- retention
def retention_table(cohort: pd.DataFrame, user_day: pd.DataFrame, day_ns, end_date: pd.Timestamp,
                    by: str | None = "cohort_week") -> pd.DataFrame:
    """Long table: [by] x day_n with cohort_users, eligible_users, retained_users, retention."""
    act = user_day[["user_id", "activity_date"]].copy()
    act["activity_date"] = to_date(act["activity_date"])
    act = act.drop_duplicates()
    act_set = set(zip(act["user_id"], act["activity_date"]))
    rows = []
    keys = [by] if by else []
    base = cohort[["user_id", "install_date"] + keys].copy()
    for n in day_ns:
        t = base["install_date"] + pd.Timedelta(days=int(n))
        eligible = t <= end_date
        retained = eligible & np.array([(u, d) in act_set for u, d in zip(base["user_id"], t)])
        tmp = base.assign(day_n=int(n), eligible=eligible, retained=retained)
        rows.append(tmp)
    long = pd.concat(rows, ignore_index=True)
    g = long.groupby(keys + ["day_n"], dropna=False).agg(
        cohort_users=("user_id", "nunique"),
        eligible_users=("eligible", "sum"),
        retained_users=("retained", "sum"),
    ).reset_index()
    g["retention"] = np.where(g["eligible_users"] > 0, g["retained_users"] / g["eligible_users"], np.nan)
    lo, hi = wilson_ci(g["retained_users"], g["eligible_users"].replace(0, np.nan))
    g["ci_low"], g["ci_high"] = lo, hi
    return g


# ----------------------------------------------------------------------------- revenue
def iap_revenue_usd(iap: pd.DataFrame) -> pd.DataFrame:
    """event_value_in_usd, falling back to value/1e6 only when currency == USD."""
    d = iap.copy()
    fallback = np.where(d["currency"].eq("USD"), d["value_param"] / 1e6, np.nan)
    d["revenue_usd"] = d["event_value_in_usd"].where(d["event_value_in_usd"].notna(), fallback)
    d["revenue_source"] = np.where(d["event_value_in_usd"].notna(), "event_value_in_usd",
                                   np.where(d["currency"].eq("USD"), "value_param_usd", "missing"))
    return d


def monetization_kpis(user_day: pd.DataFrame, iap: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    """Period KPIs per platform + ALL.

    payer_rate = payers / active users
    ARPU       = revenue / active users              (whole period)
    ARPDAU     = revenue / user-days (= sum of daily DAU), i.e. average revenue per daily user
    ARPPU      = revenue / payers
    """
    ud = user_day.merge(users[["user_id", "platform"]], on="user_id", how="left")
    rev = iap.merge(users[["user_id", "platform"]], on="user_id", how="left", suffixes=("_iap", ""))
    out = []
    for plat in ["ALL", "ANDROID", "IOS"]:
        u = ud if plat == "ALL" else ud[ud["platform"] == plat]
        r = rev if plat == "ALL" else rev[rev["platform"] == plat]
        active = u["user_id"].nunique()
        user_days = len(u[["user_id", "activity_date"]].drop_duplicates())
        payers = r["user_id"].nunique()
        revenue = float(r["revenue_usd"].sum())
        out.append({
            "platform": plat, "active_users": active, "user_days": user_days, "payers": payers,
            "purchases": len(r), "revenue_usd": round(revenue, 6),
            "payer_rate": payers / active if active else np.nan,
            "arpu_usd": revenue / active if active else np.nan,
            "arpdau_usd": revenue / user_days if user_days else np.nan,
            "arppu_usd": revenue / payers if payers else np.nan,
        })
    return pd.DataFrame(out)


def ltv_curve(cohort: pd.DataFrame, iap: pd.DataFrame, max_day: int, end_date: pd.Timestamp,
              fixed_population: bool = True) -> pd.DataFrame:
    """Cumulative IAP LTV per install: revenue on days 0..N / eligible players.

    fixed_population=True  -> the SAME players (those observable for `max_day` days) at every N,
                              so the curve is monotonic and comparable across N.
    fixed_population=False -> players eligible for each N separately (larger n for small N,
                              but the population changes along the curve).
    """
    rev = iap.merge(cohort[["user_id", "install_date"]], on="user_id", how="inner")
    rev["day"] = (to_date(rev["activity_date"]) - rev["install_date"]).dt.days
    rows = []
    for n in range(max_day + 1):
        horizon = max_day if fixed_population else n
        elig = cohort[cohort["install_date"] + pd.Timedelta(days=horizon) <= end_date]
        r = rev[rev["user_id"].isin(elig["user_id"]) & (rev["day"] <= n) & (rev["day"] >= 0)]
        e = len(elig)
        rows.append({
            "day_n": n, "eligible_users": e, "payers": r["user_id"].nunique(),
            "revenue_usd": round(float(r["revenue_usd"].sum()), 6),
            "ltv_usd": float(r["revenue_usd"].sum()) / e if e else np.nan,
            "payer_rate": r["user_id"].nunique() / e if e else np.nan,
        })
    return pd.DataFrame(rows)
