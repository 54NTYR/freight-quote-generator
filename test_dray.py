from datetime import date
import dray


def test_lfd():
    assert dray.last_free_day("2025-03-01", 5) == "2025-03-06"
    assert dray.last_free_day(None) is None


def test_demurrage_accrual():
    e = dray.demurrage_exposure("2025-03-01", "2025-03-09", free_days=5,
                                demurrage_rate=150, per_diem_rate=40,
                                chassis_rate=35)
    assert e["days_late"] == 3          # LFD 03-06, pickup 03-09
    assert e["demurrage"] == 450.0 and e["per_diem"] == 120.0
    assert e["chassis_days"] == 8 and e["chassis_cost"] == 280.0


def test_demurrage_inside_free_time():
    e = dray.demurrage_exposure("2025-03-01", "2025-03-05", demurrage_rate=150)
    assert e["days_late"] == 0 and e["demurrage"] == 0.0


def test_breakeven_both_directions():
    # hold: 50000*0.20/365 = 27.40; daily = 150+40+35+27.40 = 252.40
    d = dray.delay_vs_prepull(50000, 150, per_diem_rate=40, prepull_cost=505)
    assert d["daily_delay_cost"] == 252.40
    assert d["prepull_justified_days"] == 2.0
    assert "demurrage exceeds" in d["inventory_vs_demurrage"]
    hi = dray.delay_vs_prepull(500000, 10)   # hold 274/day > demurrage 10
    assert "inventory cost exceeds" in hi["inventory_vs_demurrage"]


def test_turn_economics():
    t = dray.turn_economics(60, 60, rpm_loaded=3.0, fsc_pct=20,
                            chassis_days=2, accessorials=50)
    # linehaul = 60*3 + 60*2.55 = 333; fsc 66.60; chassis 70; +50
    assert t["total"] == 519.60
    assert t["deadhead_pct"] == 50.0
    m = dray.turn_economics(100, 0, rpm_loaded=3.0, revenue=500)
    assert m["margin"] == 200.0 and m["margin_pct"] == 40.0


def test_timeline_order_and_buffer():
    t = dray.timeline("2025-03-01", 5, cutoff_date="2025-02-27",
                      pickup_date="2025-03-05", congestion="heavy")
    dates = [e["date"] for e in t["events"]]
    assert dates == sorted(dates)
    assert t["buffer_days"] == 2
    assert t["recommended_pickup"] == "2025-03-04"   # LFD 03-06 minus 2
    assert t["events"][0]["label"] == "Rail/vessel cutoff"