"""International analytics: Incoterms 2020 responsibilities, landed-cost
waterfall (MIT SC3x §4.4.2 order), leg-level transit variability, container
utilization. Pure functions; degrade gracefully on missing inputs."""
import math

# --- Incoterms 2020 ---------------------------------------------------------
# Legs: L=origin inland, P1=origin port, O=ocean, P2=dest port/customs, D=dest inland
INCOTERMS = {
    "EXW": {"main_payer": "buyer", "duty_payer": "buyer", "risk": "Seller's premises",
            "importer_legs": ["L", "P1", "O", "P2", "D"], "exporter_legs": []},
    "FCA": {"main_payer": "buyer", "duty_payer": "buyer", "risk": "Handover to carrier",
            "importer_legs": ["P1", "O", "P2", "D"], "exporter_legs": ["L"]},
    "FAS": {"main_payer": "buyer", "duty_payer": "buyer", "risk": "Alongside vessel",
            "importer_legs": ["P1", "O", "P2", "D"], "exporter_legs": ["L"]},
    "FOB": {"main_payer": "buyer", "duty_payer": "buyer", "risk": "On board vessel",
            "importer_legs": ["O", "P2", "D"], "exporter_legs": ["L", "P1"]},
    "CFR": {"main_payer": "seller", "duty_payer": "buyer", "risk": "On board vessel",
            "importer_legs": ["P2", "D"], "exporter_legs": ["L", "P1", "O"]},
    "CIF": {"main_payer": "seller", "duty_payer": "buyer", "risk": "On board vessel",
            "importer_legs": ["P2", "D"], "exporter_legs": ["L", "P1", "O"]},
    "CPT": {"main_payer": "seller", "duty_payer": "buyer", "risk": "Handover to 1st carrier",
            "importer_legs": ["P2", "D"], "exporter_legs": ["L", "P1", "O"]},
    "CIP": {"main_payer": "seller", "duty_payer": "buyer", "risk": "Handover to 1st carrier",
            "importer_legs": ["P2", "D"], "exporter_legs": ["L", "P1", "O"]},
    "DAP": {"main_payer": "seller", "duty_payer": "buyer", "risk": "Named destination",
            "importer_legs": [], "exporter_legs": ["L", "P1", "O", "P2", "D"]},
    "DPU": {"main_payer": "seller", "duty_payer": "buyer", "risk": "Destination, unloaded",
            "importer_legs": [], "exporter_legs": ["L", "P1", "O", "P2", "D"]},
    "DDP": {"main_payer": "seller", "duty_payer": "seller", "risk": "Destination, duty paid",
            "importer_legs": [], "exporter_legs": ["L", "P1", "O", "P2", "D"]},
}

# --- Landed-cost waterfall: exact MIT §4.4.2 order ---------------------------

def landed_cost_waterfall(goods_value_fob, ocean_freight=0.0, insurance=0.0,
                          duty_rate_pct=0.0, vat_rate_pct=0.0,
                          duty_basis="CIF", dest_inland=0.0, seller_pays_duty=False):
    """Returns (steps, totals) or (None, reason). Steps are (label, amount)."""
    if not goods_value_fob or float(goods_value_fob) <= 0:
        return None, "Cargo value required for duty/VAT calculation"
    fob = float(goods_value_fob)
    ocean, ins = float(ocean_freight or 0), float(insurance or 0)
    cif = fob + ocean + ins
    basis = (duty_basis or "CIF").upper()
    dutiable = cif if basis == "CIF" else fob
    duty = dutiable * float(duty_rate_pct or 0) / 100.0
    vat_base = dutiable + duty
    vat = vat_base * float(vat_rate_pct or 0) / 100.0
    dest = float(dest_inland or 0)
    steps = [
        ("FOB value", round(fob, 2)),
        ("+ Ocean freight", round(ocean, 2)),
        ("+ Marine insurance", round(ins, 2)),
        ("= CIF value", round(cif, 2)),
        (f"Dutiable value ({basis} basis)", round(dutiable, 2)),
        (f"+ Duty @ {duty_rate_pct or 0}%", round(duty, 2)),
        ("= VAT/GST taxable value", round(vat_base, 2)),
        (f"+ VAT/GST @ {vat_rate_pct or 0}%", round(vat, 2)),
        ("+ Destination inland & handling", round(dest, 2)),
    ]
    return steps, {
        "landed_total": round(cif + duty + vat + dest, 2),
        "duty": round(duty, 2), "vat": round(vat, 2),
        "duty_payer": "Seller (DDP)" if seller_pays_duty else "Buyer",
    }

# --- Leg-level transit plan ---------------------------------------------------
# Defaults: ports and origin inland carry the widest variability bands (MIT §4.4.4)
LEG_DEFAULTS = {
    "L":  ("Origin inland trucking", 2.0, 1.0),
    "P1": ("Origin port / terminal dwell", 3.0, 2.0),
    "O":  ("Ocean transit", 18.0, 2.0),
    "P2": ("Destination customs & port", 4.0, 2.5),
    "D":  ("Destination inland delivery", 2.0, 0.5),
}

def leg_transit_plan(overrides=None, conf_z=1.645, include_codes=None):
    """Total sigma = sqrt(sum of variances) — independent-leg aggregation
    (MIT SC1x §2.2.2). Window = mean ± conf_z·sigma. overrides: {code: mean_days}.
    include_codes limits which legs enter the plan."""
    overrides = overrides or {}
    if include_codes is not None:
        codes = [c for c in LEG_DEFAULTS if c in include_codes]
        if not codes:
            return None
    else:
        codes = list(LEG_DEFAULTS)
    legs, mean, var = [], 0.0, 0.0
    for code in codes:
        label, d, s = LEG_DEFAULTS[code]
        days = float(overrides.get(code, d))
        legs.append({"code": code, "label": label, "days": days, "sigma": s})
        mean += days
        var += s * s
    sigma = math.sqrt(var)
    widest = max(legs, key=lambda row: row["sigma"])
    wide_labels = [row["label"] for row in legs if row["sigma"] == widest["sigma"]]
    if len(wide_labels) == 1:
        buffer_hint = f"Widest band sits at {wide_labels[0]} — schedule buffers there."
    else:
        buffer_hint = (
            "Widest bands sit at " + " and ".join(wide_labels)
            + " — schedule buffers there."
        )
    return {"legs": legs, "mean_days": round(mean, 1),
            "sigma_days": round(sigma, 2),
            "low": round(mean - conf_z * sigma, 1),
            "high": round(mean + conf_z * sigma, 1),
            "confidence_pct": 90 if abs(conf_z - 1.645) < 0.01 else int(round(conf_z * 100)),
            "buffer_hint": buffer_hint}

# --- Container utilization (MIT §2.4.2 capacities) ----------------------------

LB_TO_KG = 0.45359237
CONTAINERS = {
    "20FT": {"label": "20' (TEU)", "cube_m3": 33.0, "payload_kg": 24800, "floor_pallets": 9},
    "40FT": {"label": "40' (FEU)", "cube_m3": 67.0, "payload_kg": 28800, "floor_pallets": 20},
    "40HC": {"label": "40' High Cube", "cube_m3": 76.0, "payload_kg": 28800, "floor_pallets": 23},
    "53VAN": {"label": "53' Dry Van", "payload_kg": 44000 * LB_TO_KG, "floor_pallets": 26},
    "53REEFER": {"label": "53' Reefer", "payload_kg": 42000 * LB_TO_KG, "floor_pallets": 24},
    "48FLAT": {"label": "48' Flatbed", "payload_kg": 48000 * LB_TO_KG, "floor_pallets": 24},
    "53FLAT": {"label": "53' Flatbed", "payload_kg": 48000 * LB_TO_KG, "floor_pallets": 26},
}
PALLET_CUBE_M3 = 2.0  # 48x40in pallet, ~62 in stacked

LEG_COST_FIELDS = {
    "L": ("+ Origin inland", "origin_inland"),
    "P1": ("+ Origin port", "origin_port"),
    "O": ("+ Ocean freight", "ocean_freight"),
    "P2": ("+ Dest port/customs", "dest_port"),
    "D": ("+ Destination inland & handling", "dest_inland"),
}


def role_legs(incoterm, trade_role="importer"):
    terms = INCOTERMS.get((incoterm or "").upper())
    if not terms:
        return None
    if (trade_role or "importer").lower() == "exporter":
        return list(terms["exporter_legs"])
    return list(terms["importer_legs"])


def _duty_vat(amounts, duty_basis="CIF"):
    fob = float(amounts.get("goods_value_fob") or 0)
    if fob <= 0:
        return 0.0, 0.0
    ocean = float(amounts.get("ocean_freight") or 0)
    ins = float(amounts.get("marine_insurance") or 0)
    cif = fob + ocean + ins
    basis = cif if (duty_basis or "CIF").upper() == "CIF" else fob
    duty = basis * float(amounts.get("duty_rate_pct") or 0) / 100.0
    vat = (basis + duty) * float(amounts.get("vat_rate_pct") or 0) / 100.0
    return round(duty, 2), round(vat, 2)


def role_waterfall(incoterm, trade_role, amounts, duty_basis="CIF"):
    """Build only the cost lines the selected role pays under this Incoterm.
    The importer always pays goods value. Returns (steps, totals) or (None, reason)."""
    legs = role_legs(incoterm, trade_role)
    if legs is None:
        legs = ["L", "P1", "O", "P2", "D"]
    terms = INCOTERMS.get((incoterm or "").upper()) or {}
    duty_payer = terms.get("duty_payer", "buyer")
    role = (trade_role or "importer").lower()
    pays_duty = (duty_payer == "buyer" and role == "importer") or (
        duty_payer == "seller" and role == "exporter")
    include_goods = role == "importer" or bool(legs)
    if role == "exporter" and not legs:
        return None, "Landed cost does not apply for this Incoterm and role"
    amounts = amounts or {}
    steps = []
    total = 0.0
    fob = float(amounts.get("goods_value_fob") or 0)
    if include_goods and fob:
        steps.append(("Goods value", round(fob, 2)))
        total += fob
    added_duty = False

    def _append_duty():
        nonlocal total, added_duty
        if added_duty or not pays_duty:
            return
        duty, vat = _duty_vat(amounts, duty_basis)
        if duty:
            rate = amounts.get("duty_rate_pct") or 0
            steps.append((f"+ Duty @ {rate}%", duty))
            total += duty
        if vat:
            rate = amounts.get("vat_rate_pct") or 0
            steps.append((f"+ VAT/GST @ {rate}%", vat))
            total += vat
        added_duty = True

    for code in ("L", "P1", "O", "P2", "D"):
        if code not in legs:
            continue
        label, key = LEG_COST_FIELDS[code]
        amt = float(amounts.get(key) or 0)
        if amt:
            steps.append((label, round(amt, 2)))
            total += amt
        if code == "O":
            ins = float(amounts.get("marine_insurance") or 0)
            if ins:
                steps.append(("+ Marine insurance", round(ins, 2)))
                total += ins
        if code == "P2":
            _append_duty()
    _append_duty()
    if not steps:
        return None, "No landed-cost amounts entered"
    payer = "Seller (DDP)" if duty_payer == "seller" else "Buyer"
    return steps, {
        "landed_total": round(total, 2),
        "duty_payer": payer,
    }


def container_utilization(container="40FT", pallets=None, total_weight_kg=None):
    spec = CONTAINERS.get(container, CONTAINERS["40FT"])
    out = {"container": spec["label"]}
    if pallets and float(pallets) > 0:
        p = float(pallets)
        if spec.get("cube_m3"):
            out["cube_util_pct"] = round(100 * p * PALLET_CUBE_M3 / spec["cube_m3"], 1)
        out["floor_positions"] = spec["floor_pallets"]
        out["over_floor"] = p > spec["floor_pallets"]
    if total_weight_kg and float(total_weight_kg) > 0 and spec.get("payload_kg"):
        out["weight_util_pct"] = round(100 * float(total_weight_kg) / spec["payload_kg"], 1)
    return out