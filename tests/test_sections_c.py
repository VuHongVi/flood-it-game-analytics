"""Tests for level, feature and statistics helpers (sections 5-8)."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from flood_it.analysis import sections_c as C


def test_level_stats_handles_float_keys_and_quickplay():
    ul = pd.DataFrame({
        "user_id": ["a", "a", "b", "b", "c"],
        "mode": ["progression", "progression", "progression", "quickplay", "progression"],
        "level_key": ["1", "2.0", "1", "S", None],
        "starts": [2, 1, 1, 5, 0], "completes": [1, 0, 0, 2, 3], "fails": [1, 1, 1, 3, 0],
    })
    g = C.level_stats_from_user_level(ul).set_index("level")
    assert list(g.index) == [1, 2]                    # "2.0" parsed, board 'S' and NULL excluded
    assert g.loc[1, "starts"] == 3 and g.loc[1, "users_started"] == 2
    assert g.loc[2, "users_completed"] == 0


def test_day0_features_use_install_day_only():
    cohort = pd.DataFrame({"user_id": ["a"], "install_date": [pd.Timestamp("2018-01-01")],
                           "platform": ["IOS"], "country": ["United States"], "traffic_source": ["(direct)"]})
    cols = dict(events=0, sessions=0, engagement_msec=0, level_starts=0, level_completes=0, level_fails=0,
                quickplay_starts=0, quickplay_completes=0, quickplay_fails=0, max_level=0, post_scores=0,
                ad_rewards=0, virtual_spends=0, app_exceptions=0)
    ud = pd.DataFrame([
        {"user_id": "a", "activity_date": "2018-01-01", **{**cols, "events": 10, "engagement_msec": 120000}},
        {"user_id": "a", "activity_date": "2018-01-09", **{**cols, "events": 999}},   # future: must not leak
    ])
    f = C.day0_features(cohort, ud)
    assert f.loc[0, "d0_events"] == 10 and f.loc[0, "d0_engagement_min"] == pytest.approx(2.0)
    out = C.add_outcomes(f, ud, end=pd.Timestamp("2018-02-15"), churn_window=(7, 30))
    assert out.loc[0, "churned"] == 0 and out.loc[0, "active_d1"] == 0 and out.loc[0, "elig_churn"] == 1


def test_two_prop_test_matches_chi_square():
    r = C.two_prop_test(30, 100, 20, 100, "A", "B", "m", "c")
    assert r["diff_a_minus_b"] == pytest.approx(0.10)
    # z^2 equals the uncorrected chi-square statistic for a 2x2 table
    assert r["z"] ** 2 == pytest.approx(r["chi2"], rel=1e-6)
    assert r["p_value"] == pytest.approx(r["chi2_p_value"], rel=1e-6)
    assert r["diff_ci_low"] < 0.10 < r["diff_ci_high"]
    expected_h = 2 * np.arcsin(np.sqrt(0.3)) - 2 * np.arcsin(np.sqrt(0.2))
    assert r["cohens_h"] == pytest.approx(expected_h)


def test_p_value_formatting_keeps_small_values():
    assert C._p(1.9e-9) == pytest.approx(1.9e-9)
    assert C._p(0.012345) == 0.0123
