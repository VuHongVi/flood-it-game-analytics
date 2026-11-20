"""Metric functions on tiny hand-checkable data."""
import numpy as np
import pandas as pd
import pytest

from flood_it.analysis import metrics as M

D = lambda s: pd.Timestamp(s)  # noqa: E731


@pytest.fixture
def toy():
    # 3 players installed 2018-01-01 (Mon); data ends 2018-01-08.
    users = pd.DataFrame({
        "user_id": ["a", "b", "c", "old"],
        "platform": ["IOS", "ANDROID", "IOS", "IOS"],
        "first_open_date": ["2018-01-01", "2018-01-01", "2018-01-07", None],
        "first_touch_date_utc": ["2018-01-01", "2017-12-31", "2018-01-07", "2017-05-01"],
    })
    ud = pd.DataFrame({
        "user_id":       ["a", "a", "a", "b", "b", "c", "old", "old"],
        "activity_date": ["2018-01-01", "2018-01-02", "2018-01-08", "2018-01-01", "2018-01-04",
                          "2018-01-07", "2018-01-01", "2018-01-08"],
        "events": [10, 5, 3, 8, 2, 4, 1, 1],
    })
    return users, ud


def test_install_cohort_excludes_old_and_preexisting(toy):
    users, _ = toy
    c = M.build_install_cohort(users, D("2018-01-01"))
    # b first-touched before window start -> excluded (re-install); old has no first_open
    assert sorted(c.user_id) == ["a", "c"]
    assert (c.cohort_week == D("2018-01-01")).all()


def test_retention_handles_right_censoring(toy):
    users, ud = toy
    c = M.build_install_cohort(users, D("2018-01-01"))
    r = M.retention_table(c, ud, [1, 7], end_date=D("2018-01-08"), by=None).set_index("day_n")
    # D1: a (installed 01-01, active 01-02) retained; c (installed 01-07) eligible for 01-08, not active
    assert r.loc[1, "eligible_users"] == 2 and r.loc[1, "retained_users"] == 1
    assert r.loc[1, "retention"] == pytest.approx(0.5)
    # D7: only a is eligible (01-08 <= end); c would need 01-14 -> censored, NOT counted as churned
    assert r.loc[7, "eligible_users"] == 1 and r.loc[7, "retained_users"] == 1
    assert r.loc[7, "retention"] == pytest.approx(1.0)


def test_daily_growth_dau_wau_mau_stickiness(toy):
    users, ud = toy
    g = M.daily_growth(ud, users).set_index("activity_date")
    assert g.loc[D("2018-01-01"), "dau"] == 3
    assert g.loc[D("2018-01-08"), "dau"] == 2
    # WAU on 01-08 = active in (01-01, 01-08] = a, b(01-04), c, old -> 4
    assert g.loc[D("2018-01-08"), "wau"] == 4
    assert g.loc[D("2018-01-01"), "installs"] == 2
    assert g.loc[D("2018-01-01"), "returning_dau"] == 0
    # stickiness undefined until a full 30-day window exists
    assert g["stickiness"].isna().all()


def test_flag_spikes_global_median():
    g = pd.DataFrame({"dau": [100, 100, 100, 300, 310, 100], "events": [1000] * 6})
    f = M.flag_spikes(g)
    assert f["is_spike"].tolist() == [False, False, False, True, True, False]
    assert f.loc[3, "events_per_dau"] == pytest.approx(1000 / 300)


def test_iap_revenue_fallback_only_for_usd():
    iap = pd.DataFrame({
        "event_value_in_usd": [np.nan, 0.99, np.nan],
        "currency": ["USD", "USD", "EUR"],
        "value_param": [4_990_000, 990_000, 1_000_000],
    })
    d = M.iap_revenue_usd(iap)
    assert d["revenue_usd"].iloc[0] == pytest.approx(4.99)
    assert d["revenue_usd"].iloc[1] == pytest.approx(0.99)
    assert np.isnan(d["revenue_usd"].iloc[2])          # no FX table -> stays missing, not invented
    assert d["revenue_source"].tolist() == ["value_param_usd", "event_value_in_usd", "missing"]


def test_monetization_kpis(toy):
    users, ud = toy
    iap = pd.DataFrame({"user_id": ["a", "a"], "activity_date": ["2018-01-01", "2018-01-02"],
                        "platform": ["IOS", "IOS"], "revenue_usd": [1.0, 2.0]})
    k = M.monetization_kpis(ud, iap, users).set_index("platform")
    all_ = k.loc["ALL"]
    assert all_.active_users == 4 and all_.payers == 1 and all_.revenue_usd == 3.0
    assert all_.payer_rate == pytest.approx(0.25)
    assert all_.arpu_usd == pytest.approx(0.75)
    assert all_.arppu_usd == pytest.approx(3.0)
    assert all_.arpdau_usd == pytest.approx(3.0 / 8)        # 8 user-days
    assert k.loc["ANDROID", "revenue_usd"] == 0


def test_ltv_curve_fixed_population_is_monotonic(toy):
    users, _ = toy
    c = M.build_install_cohort(users, D("2018-01-01"))
    iap = pd.DataFrame({"user_id": ["a", "a", "c"], "activity_date": ["2018-01-01", "2018-01-03", "2018-01-07"],
                        "revenue_usd": [1.0, 2.0, 5.0]})
    fixed = M.ltv_curve(c, iap, max_day=7, end_date=D("2018-01-08"), fixed_population=True)
    assert (fixed["eligible_users"] == 1).all()             # only `a` observable for 7 days
    assert fixed["ltv_usd"].is_monotonic_increasing
    assert fixed.set_index("day_n").loc[2, "ltv_usd"] == pytest.approx(3.0)
    own = M.ltv_curve(c, iap, max_day=7, end_date=D("2018-01-08"), fixed_population=False).set_index("day_n")
    assert own.loc[0, "eligible_users"] == 2 and own.loc[0, "ltv_usd"] == pytest.approx(3.0)  # (1+5)/2


def test_wilson_ci_bounds():
    lo, hi = M.wilson_ci(np.array([0, 50]), np.array([10, 100]))
    assert lo[0] == pytest.approx(0, abs=1e-12) and 0 < hi[0] < 0.35
    assert lo[1] < 0.5 < hi[1]
