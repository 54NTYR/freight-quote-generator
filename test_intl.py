import pytest
import intl


def test_waterfall_mit_order():
    steps, tot = intl.landed_cost_waterfall(
        10000, ocean_freight=2000, insurance=100,
        duty_rate_pct=5, vat_rate_pct=20, duty_basis="CIF", dest_inland=500)
    labels = [s[0] for s in steps]
    assert labels[0] == "FOB value" and labels[3] == "= CIF value"
    assert labels[4].startswith("Dutiable value (CIF")
    # CIF=12100; duty=605; vat base=12705; vat=2541; total=12100+605+2541+500
    assert tot["landed_total"] == 15746.0
    assert tot["duty"] == 605.0 and tot["vat"] == 2541.0


def test_waterfall_fob_basis():
    _, tot = intl.landed_cost_waterfall(10000, ocean_freight=2000,
                                        duty_rate_pct=5, duty_basis="FOB")
    assert tot["duty"] == 500.0  # duty on 10000, not 12000


def test_waterfall_requires_value():
    steps, reason = intl.landed_cost_waterfall(None)
    assert steps is None and "value" in reason


def test_incoterm_legs():
    assert intl.INCOTERMS["FOB"]["importer_legs"] == ["O", "P2", "D"]
    assert intl.INCOTERMS["DDP"]["duty_payer"] == "seller"
    assert intl.INCOTERMS["EXW"]["exporter_legs"] == []


def test_leg_plan_aggregation():
    plan = intl.leg_transit_plan()
    assert plan["mean_days"] == 29.0  # 2+3+18+4+2
    # var = 1+4+4+6.25+0.25 = 15.5 -> sigma = 3.94
    assert plan["sigma_days"] == 3.94
    assert plan["low"] < plan["mean_days"] < plan["high"]
    o = intl.leg_transit_plan(overrides={"O": 30})
    assert o["mean_days"] == 41.0


def test_container_util():
    c = intl.container_utilization("40FT", pallets=24, total_weight_kg=20000)
    assert c["cube_util_pct"] == 71.6
    assert c["over_floor"] is True
    assert c["weight_util_pct"] == 69.4


def test_role_waterfall_fob_importer():
    steps, tot = intl.role_waterfall("FOB", "importer", {
        "origin_inland": 900,
        "ocean_freight": 3500,
        "dest_port": 200,
        "dest_inland": 450,
    })
    labels = [s[0] for s in steps]
    assert "+ Origin inland" not in labels
    assert labels == ["+ Ocean freight", "+ Dest port/customs", "+ Destination inland & handling"]
    assert tot["landed_total"] == 4150.0


def test_role_waterfall_exw_importer():
    steps, _ = intl.role_waterfall("EXW", "importer", {
        "origin_inland": 100, "origin_port": 80, "ocean_freight": 500,
        "dest_port": 60, "dest_inland": 40,
    })
    assert [s[0] for s in steps] == [
        "+ Origin inland", "+ Origin port", "+ Ocean freight",
        "+ Dest port/customs", "+ Destination inland & handling",
    ]


def test_role_waterfall_includes_goods_value():
    steps, tot = intl.role_waterfall("FOB", "importer", {
        "goods_value_fob": 45000,
        "ocean_freight": 3500,
        "dest_port": 200,
        "dest_inland": 450,
    })
    assert steps[0] == ("Goods value", 45000.0)
    assert "+ Origin inland" not in [s[0] for s in steps]
    assert tot["landed_total"] == 49150.0


def test_role_waterfall_ddp_importer_goods_only():
    steps, tot = intl.role_waterfall("DDP", "importer", {
        "goods_value_fob": 45000,
        "ocean_freight": 3500,
        "duty_rate_pct": 12,
    })
    assert steps == [("Goods value", 45000.0)]
    assert tot["landed_total"] == 45000.0


def test_role_waterfall_dap_importer_goods_and_duty():
    steps, tot = intl.role_waterfall("DAP", "importer", {
        "goods_value_fob": 10000,
        "duty_rate_pct": 10,
        "ocean_freight": 2000,
    })
    labels = [s[0] for s in steps]
    assert labels[0] == "Goods value"
    assert "+ Ocean freight" not in labels
    assert any(s.startswith("+ Duty") for s in labels)
    assert tot["landed_total"] == 11200.0


def test_role_waterfall_exw_exporter_hidden():
    steps, reason = intl.role_waterfall("EXW", "exporter", {"goods_value_fob": 45000})
    assert steps is None
    assert "does not apply" in reason


def test_transit_only_entered_legs():
    plan = intl.leg_transit_plan(overrides={"O": 12}, include_codes=["O"])
    assert plan["mean_days"] == 12.0
    assert len(plan["legs"]) == 1
    assert plan["buffer_hint"]


def test_dry_van_payload():
    limit = 44000 * intl.LB_TO_KG
    c = intl.container_utilization("53VAN", pallets=20, total_weight_kg=limit)
    assert c["container"] == "53' Dry Van"
    assert c["weight_util_pct"] == 100.0
    assert "cube_util_pct" not in c


def test_validity_days_from_until():
    from datetime import date
    from app import _quote_validity_days
    assert _quote_validity_days("2026-09-21", date(2026, 8, 23)) == 29
    assert _quote_validity_days("", date(2026, 8, 23)) == 15
    assert _quote_validity_days("September 21, 2026", date(2026, 8, 23)) == 29