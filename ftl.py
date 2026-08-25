"""FTL analytics: equipment specs, utilization, HOS-aware transit, cost
assembly, LTL crossover (MIT SC1x §2.4.3 mode selection; §2.4.6 direct-mode
economics — 1:1, strong scope, lane-based procurement)."""
import math

from analytics_core import t_critical

EQUIPMENT = {
    "R":   {"label": "(R) Reefer", "positions": 26, "payload_lb": 43500, "sigma_days": 1.0},
    "V":   {"label": "(V) Van", "positions": 26, "payload_lb": 45000, "sigma_days": 0.5},
    "SB":  {"label": "(SB) Boxtruck", "positions": 12, "payload_lb": 10000, "sigma_days": 0.5},
    "F":   {"label": "(F) Flatbed", "positions": 24, "payload_lb": 48000, "sigma_days": 0.75},
    "SD":  {"label": "(SD) Stepdeck", "positions": 24, "payload_lb": 48000, "sigma_days": 0.75},
    "HS":  {"label": "(HS) Hotshot", "positions": 10, "payload_lb": 12000, "sigma_days": 0.75},
    "RGN": {"label": "(RGN) Removable Gooseneck", "positions": 20, "payload_lb": 48000, "sigma_days": 1.0},
    "LB":  {"label": "(LB) Low-boy", "positions": 16, "payload_lb": 48000, "sigma_days": 1.0},
}
REEFER_CODES = {"R"}
OPEN_DECK_CODES = {"F", "SD", "HS", "RGN", "LB"}
REEFER_SURCHARGES = {"continuous_run_pct": 0.08, "precool_fee": 75.0}
FLATBED_TARP_FEE = 50.0      # per tarp
DEFAULT_RPM = 2.50           # fallback $/mile when no flat rate given


def utilization(equipment, pallets=None, weight_lb=None):
    spec = EQUIPMENT.get(equipment, EQUIPMENT["V"])
    out = {"equipment": spec["label"], "positions": spec["positions"],
           "payload_lb": spec["payload_lb"]}
    if pallets and float(pallets) > 0:
        p = float(pallets)
        out["position_util_pct"] = round(100 * p / spec["positions"], 1)
        out["over_positions"] = p > spec["positions"]
    if weight_lb and float(weight_lb) > 0:
        out["weight_util_pct"] = round(100 * float(weight_lb) / spec["payload_lb"], 1)
        out["over_weight"] = float(weight_lb) > spec["payload_lb"]
    return out


def transit_estimate(miles, equipment="V", team=False, conf=0.90):
    """Expected days = miles / (600 × drivers). Window scales with trip
    length (equipment CV), not a fixed ±1-day band."""
    if not miles or float(miles) <= 0:
        return None
    spec = EQUIPMENT.get(equipment, EQUIPMENT["V"])
    drivers = 2 if team else 1
    drive = float(miles) / (600.0 * drivers)
    mean = round(drive, 1)
    if mean <= 0:
        return None
    cv = {0.5: 0.10, 0.75: 0.12, 1.0: 0.15}.get(spec["sigma_days"], 0.12)
    sigma = min(max(mean * cv, 0.15), max(mean * 0.25, 0.15))
    z = t_critical(conf, 30)
    buffer = z * sigma
    low = max(0.5, round(mean - buffer, 1))
    high = round(mean + buffer, 1)
    if high <= low:
        high = round(low + 0.2, 1)
    return {"mean_days": mean, "drive_days": mean, "team": bool(team),
            "sigma_days": round(sigma, 2),
            "buffer_days": round(buffer, 1),
            "low": low, "high": high,
            "confidence_pct": int(round(conf * 100))}


def assemble_cost(equipment, miles, linehaul_flat=None, rpm=DEFAULT_RPM,
                  fsc_pct=0.0, continuous_run=False, precool=False, tarps=0,
                  detention_hours=0, detention_rate=75.0, misc_accessorial=0.0):
    linehaul = float(linehaul_flat) if linehaul_flat \
        else float(rpm) * (float(miles) if miles else 0)
    fsc = linehaul * float(fsc_pct or 0) / 100.0
    extras, lines = 0.0, [("Linehaul", round(linehaul, 2)),
                          ("Fuel surcharge", round(fsc, 2))]
    if equipment in REEFER_CODES:
        if precool:
            extras += REEFER_SURCHARGES["precool_fee"]
            lines.append(("Pre-cool", REEFER_SURCHARGES["precool_fee"]))
    if equipment in OPEN_DECK_CODES and tarps:
        t = float(tarps) * FLATBED_TARP_FEE
        extras += t
        lines.append((f"Tarps x{int(tarps)}", round(t, 2)))
    if detention_hours:
        d = float(detention_hours) * float(detention_rate)
        extras += d
        lines.append((f"Detention {int(detention_hours)}h @ ${int(detention_rate)}/h",
                      round(d, 2)))
    if misc_accessorial:
        extras += float(misc_accessorial)
        lines.append(("Other accessorials", round(float(misc_accessorial), 2)))
    total = linehaul + fsc + extras
    lines.append(("All-in total", round(total, 2)))
    return {"lines": lines, "total": round(total, 2)}


def cost_metrics(total_cost, miles=None, pallets=None):
    if not total_cost or float(total_cost) <= 0:
        return None
    out = {"total": round(float(total_cost), 2)}
    if miles and float(miles) > 0:
        out["cost_per_mile"] = round(float(total_cost) / float(miles), 3)
    if pallets and float(pallets) > 0:
        out["cost_per_position"] = round(float(total_cost) / float(pallets), 2)
    return out


def crossover(ftl_total, ftl_label, ltl_quotes, pallets):
    """ltl_quotes: [{'label', 'pallets_max', 'total'}, ...] from form or the
    existing LTL tiered calculator. Positive savings = FTL cheaper."""
    if not ltl_quotes:
        return None
    pp = (round(float(ftl_total) / float(pallets), 2) if pallets else None)
    rows = [{"mode": ftl_label, "pallets": pallets,
             "total": round(float(ftl_total), 2), "per_pallet": pp}]
    for q in ltl_quotes:
        q_pallets = q.get("pallets_max")
        q_total = float(q["total"])
        q_pp = (round(q_total / float(q_pallets), 2) if q_pallets else None)
        rows.append({"mode": q.get("label", "LTL"),
                     "pallets": q_pallets,
                     "total": round(q_total, 2), "per_pallet": q_pp})
    best = min(rows, key=lambda r: r["total"])
    alts = [r for r in rows if r["mode"] != ftl_label]
    best_alt = min(alts, key=lambda r: r["total"])
    rates = [r["per_pallet"] for r in alts if r["per_pallet"]]
    breakeven = (round(float(ftl_total) / min(rates), 1)
                 if rates and min(rates) > 0 else None)
    return {"rows": rows, "cheapest": best["mode"],
            "ftl_wins": best["mode"] == ftl_label,
            "savings": round(float(best_alt["total"]) - float(ftl_total), 2),
            "breakeven_pallets": breakeven}