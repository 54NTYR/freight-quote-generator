import pytest
import ftl


def test_transit_ceil_and_team():
    t = ftl.transit_estimate(1000, "V")
    assert t["mean_days"] == 1.7
    assert t["low"] < t["mean_days"] < t["high"]
    assert t["high"] - t["low"] < 1.0
    assert ftl.transit_estimate(600, "V")["mean_days"] == 1.0
    assert ftl.transit_estimate(616, "LB")["mean_days"] == 1.0
    lb = ftl.transit_estimate(616, "LB")
    assert lb["high"] - lb["low"] <= 1.0
    assert ftl.transit_estimate(1000, "V", team=True)["mean_days"] == 0.8
    assert ftl.transit_estimate(None) is None


def test_reefer_wider_than_van():
    v = ftl.transit_estimate(1000, "V")
    r = ftl.transit_estimate(1000, "R")
    assert r["high"] > v["high"]


def test_utilization_thresholds():
    u = ftl.utilization("V", 26, 50000)
    assert u["position_util_pct"] == 100.0 and not u["over_positions"]
    assert u["over_weight"] and u["weight_util_pct"] == 111.1
    assert ftl.utilization("V", 27)["over_positions"]


def test_cost_reefer_extras():
    c = ftl.assemble_cost("R", 1000, linehaul_flat=2000,
                          fsc_pct=20, continuous_run=True, precool=True)
    # 2000 + 400 fsc + 160 continuous + 75 precool
    assert c["total"] == 2635.0


def test_cost_flatbed_tarps_and_detention():
    c = ftl.assemble_cost("F", 500, linehaul_flat=1000, tarps=4,
                          detention_hours=2)
    assert c["total"] == 1350.0  # 1000 + 200 tarps + 150 detention


def test_crossover_both_directions():
    w = ftl.crossover(2000, "FTL", [{"label": "Tier 3", "pallets_max": 20,
                                     "total": 2400}], 20)
    assert w["ftl_wins"] and w["savings"] == 400.0
    assert w["breakeven_pallets"] == 16.7
    l = ftl.crossover(2600, "FTL", [{"label": "Tier 3", "pallets_max": 20,
                                     "total": 2400}], 20)
    assert not l["ftl_wins"] and l["cheapest"] == "Tier 3"


def test_cost_metrics():
    m = ftl.cost_metrics(2500, 1000, 20)
    assert m["cost_per_mile"] == 2.5 and m["cost_per_position"] == 125.0