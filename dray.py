"""Drayage analytics: free-time countdown, demurrage-vs-inventory breakeven,
round-trip turn economics, cut-time timeline (MIT SC3x §4.4.3 definitions:
dray = local haul to port; demurrage = penalty for extra days at dock).
Pure functions; degrade gracefully on missing inputs."""
from datetime import date, timedelta

from analytics_core import t_critical

CONGESTION = {"none": (0, "Normal operations"),
              "mild": (1, "Mild congestion — add 1 day pickup buffer"),
              "heavy": (2, "Heavy congestion — appointments scarce; add 2-day buffer")}
DEFAULT_FREE_DAYS = 5
DEFAULT_RETURN_DAYS = 3          # container return window after pickup
CHASSIS_DEFAULT = 35.0           # $/day
SIGMA_DAYS = 1.5                 # dray variance: appointments, congestion, chassis


def last_free_day(arrival_date, free_days=DEFAULT_FREE_DAYS):
    """LFD = arrival + free days. NOTE: terminal conventions vary on whether
    day 1 counts the arrival day — confirm per terminal; shown on quote."""
    if not arrival_date:
        return None
    a = date.fromisoformat(arrival_date)
    return (a + timedelta(days=int(free_days or DEFAULT_FREE_DAYS))).isoformat()


def demurrage_exposure(arrival_date, pickup_date, free_days=DEFAULT_FREE_DAYS,
                       demurrage_rate=0.0, per_diem_rate=0.0, chassis_rate=CHASSIS_DEFAULT):
    """Days late and accrued penalties. None-safe on missing dates."""
    lfd = last_free_day(arrival_date, free_days)
    if not (lfd and pickup_date):
        return {"lfd": lfd, "days_late": None, "demurrage": 0.0,
                "per_diem": 0.0, "chassis_days": None}
    late = max(0, (date.fromisoformat(pickup_date)
                   - date.fromisoformat(lfd)).days)
    chassis_days = max(1, (date.fromisoformat(pickup_date)
                           - date.fromisoformat(arrival_date)).days) \
        if arrival_date else None
    return {"lfd": lfd,
            "days_late": late,
            "demurrage": round(late * float(demurrage_rate or 0), 2),
            "per_diem": round(late * float(per_diem_rate or 0), 2),
            "chassis_days": chassis_days,
            "chassis_cost": round((chassis_days or 0) * float(chassis_rate or 0), 2)}


def delay_vs_prepull(container_value, demurrage_rate, per_diem_rate=0.0,
                     chassis_rate=CHASSIS_DEFAULT, prepull_cost=0.0,
                     holding_rate_pct=20.0):
    """Daily cost of letting the box sit vs paying to pull it early.
    Delay/day = penalties + chassis + cargo holding (MIT §2.3.2 relevant costs).
    Breakeven: prepull justified if prepull_cost < days_late x daily_delay_cost."""
    hold_daily = (float(container_value or 0) * float(holding_rate_pct or 0) / 100.0
                  / 365.0)
    daily = (float(demurrage_rate or 0) + float(per_diem_rate or 0)
             + float(chassis_rate or CHASSIS_DEFAULT) + hold_daily)
    out = {"hold_daily": round(hold_daily, 2), "daily_delay_cost": round(daily, 2)}
    if daily > 0 and prepull_cost and float(prepull_cost) > 0:
        out["prepull_justified_days"] = round(float(prepull_cost) / daily, 1)
    if container_value and demurrage_rate:
        out["inventory_vs_demurrage"] = (
            "inventory cost exceeds demurrage — pull promptly"
            if hold_daily > float(demurrage_rate)
            else "demurrage exceeds inventory carry — free time is cheap buffer")
    return out


def turn_economics(loaded_miles, empty_miles, rpm_loaded, rpm_empty=None,
                   fsc_pct=0.0, chassis_days=0, chassis_rate=CHASSIS_DEFAULT,
                   linehaul_flat=None, accessorials=0.0, revenue=None):
    """Round trip: cost, deadhead %, margin (utilization/productivity, MIT §3.7.4)."""
    rpm_empty = rpm_empty if rpm_empty is not None else float(rpm_loaded) * 0.85
    if linehaul_flat:
        linehaul = float(linehaul_flat)
    else:
        linehaul = (float(loaded_miles or 0) * float(rpm_loaded or 0)
                    + float(empty_miles or 0) * float(rpm_empty))
    fsc = linehaul * float(fsc_pct or 0) / 100.0
    chassis = float(chassis_days or 0) * float(chassis_rate)
    total = linehaul + fsc + chassis + float(accessorials or 0)
    tm, em = float(loaded_miles or 0), float(empty_miles or 0)
    deadhead = round(100 * em / (tm + em), 1) if (tm + em) > 0 else None
    out = {"linehaul": round(linehaul, 2), "fsc": round(fsc, 2),
           "chassis": round(chassis, 2), "total": round(total, 2),
           "deadhead_pct": deadhead}
    if revenue and float(revenue) > 0:
        out["margin"] = round(float(revenue) - total, 2)
        out["margin_pct"] = round(100 * (float(revenue) - total) / float(revenue), 1)
    return out


def timeline(arrival_date, free_days=DEFAULT_FREE_DAYS, cutoff_date=None,
             pickup_date=None, return_days=DEFAULT_RETURN_DAYS,
             congestion="none"):
    """Ordered events: cutoff -> arrival -> recommended pickup -> LFD -> return due.
    Recommended pickup pulls LFD in by the congestion buffer."""
    buf = CONGESTION.get(congestion, CONGESTION["none"])[0]
    lfd = last_free_day(arrival_date, free_days)
    rec = (date.fromisoformat(lfd) - timedelta(days=buf)).isoformat() if lfd else None
    ret = (date.fromisoformat(pickup_date)
           + timedelta(days=int(return_days or DEFAULT_RETURN_DAYS))).isoformat() \
        if pickup_date else None
    events = [("Rail/vessel cutoff", cutoff_date), ("Container available", arrival_date),
              ("Recommended pickup", rec), ("Last free day", lfd),
              ("Return due", ret)]
    events = [{"label": l, "date": d} for l, d in events if d]
    events.sort(key=lambda e: e["date"])
    return {"events": events, "buffer_days": buf, "lfd": lfd,
            "recommended_pickup": rec}


def transit_window(conf=0.90):
    """Appointment-driven dray window around the recommended pickup."""
    z = t_critical(conf, 30)
    return {"mean_days": 1, "sigma_days": SIGMA_DAYS,
            "low": round(1 - z * SIGMA_DAYS, 1), "high": round(1 + z * SIGMA_DAYS, 1),
            "confidence_pct": int(round(conf * 100))}