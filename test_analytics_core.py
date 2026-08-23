import math
import pytest
from statistics import NormalDist
import analytics_core as ac


def test_norm_ppf_matches_stdlib():
    assert ac.norm_ppf(0.95) == pytest.approx(NormalDist().inv_cdf(0.95))


def test_t_critical_z_at_df30():
    assert ac.t_critical(0.90, 30) == pytest.approx(1.6449, abs=1e-3)
    assert ac.t_critical(0.95, 30) == pytest.approx(1.9600, abs=1e-3)


def test_t_critical_small_df_fatter_tails():
    assert ac.t_critical(0.90, 3) > ac.t_critical(0.90, 10) > 1.6449


def test_conf95_interval_wider_than_conf90():
    s90 = ac.prediction_interval_days(5, 0.8, 12, "history", conf=0.90)
    s95 = ac.prediction_interval_days(5, 0.8, 12, "history", conf=0.95)
    assert (s95["high"] - s95["low"]) > (s90["high"] - s90["low"])


def test_estimate_provenance_still_suppresses():
    assert ac.prediction_interval_days(5, 0.8, 99, "estimate") is None


def test_haversine_one_degree_equator():
    assert ac.haversine_miles(0, 0, 0, 1) == pytest.approx(69.09, abs=0.2)


def test_resolve_priority_and_fallback():
    assert ac.resolve_road_miles(None, 350) == 350
    assert ac.resolve_road_miles(320, 350) == 350
    d = ac.resolve_road_miles(None, None,
                              origin_coords=(41.88, -87.63),
                              dest_coords=(40.71, -74.01))
    assert d == pytest.approx(round(ac.haversine_miles(
        41.88, -87.63, 40.71, -74.01) * ac.K_CIRCUITRY), abs=1)
    assert ac.resolve_road_miles() is None


def test_co2_units():
    # 0.5 short tons x 1000 mi x 0.162 kg/ton-mi = 81.0 kg
    assert ac.estimate_co2_kg(1000, weight_lb=1000) == 81.0
    assert ac.estimate_co2_kg(1000, pallet_count=2) == 81.0
    assert ac.estimate_co2_kg(-1, weight_lb=1000) is None
    assert ac.estimate_co2_kg(100) is None


def test_drive_days_600_per_driver():
    assert ac.MILES_PER_DAY == 600.0
    assert ac.drive_days_for_miles(600) == 1
    assert ac.drive_days_for_miles(601) == 2
    assert ac.drive_days_for_miles(1200, drivers=2) == 1
    assert ac.drive_days_for_miles(None) is None


def test_daily_holding_prefers_value_based():
    v = ac.daily_holding_cost_per_pallet(3650, 12.0)      # 3650*0.20/365 = 2.00
    assert v == 2.0
    f = ac.daily_holding_cost_per_pallet(None, 7.0)       # 7/7 = 1.00
    assert f == 1.0
    assert ac.daily_holding_cost_per_pallet(None, None) is None