"""Pure analytics primitives. Replaces math.erfinv, hardcoded T_CRITICAL_90,
broken carbon units, and adds distance/holding-cost fallbacks."""
import math
from statistics import NormalDist

# ---- Distribution helpers -------------------------------------------------

def norm_ppf(p):
    """Inverse standard-normal CDF. Stdlib, replaces math.erfinv."""
    return NormalDist().inv_cdf(p)


def t_critical(conf, df):
    """Two-sided critical value for a prediction interval at confidence `conf`.
    Uses embedded Student-t table for df < 30, z beyond (CLT, n>=30 rule)."""
    conf = float(min(max(conf, 0.50), 0.99))
    # [df][conf] -> critical value; keys sorted ascending by df
    _T = {
        0.90: {1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015,
               6: 1.943, 7: 1.895, 8: 1.860, 9: 1.833, 10: 1.812,
               11: 1.796, 12: 1.782, 13: 1.771, 14: 1.761, 15: 1.753,
               16: 1.746, 17: 1.740, 18: 1.734, 19: 1.729, 20: 1.725,
               21: 1.721, 22: 1.717, 23: 1.714, 24: 1.711, 25: 1.708,
               26: 1.706, 27: 1.703, 28: 1.701, 29: 1.699},
        0.95: {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
               6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
               11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
               16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
               21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
               26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045},
    }
    if df >= 30:
        return round(norm_ppf(1 - (1 - conf) / 2), 4)
    table = min(_T.keys(), key=lambda c: abs(c - conf))
    df_key = min((d for d in _T[table]), key=lambda d: abs(d - df))
    return _T[table][df_key]


def prediction_interval_days(mu, sigma, n, provenance, conf=0.90):
    """t-interval for ONE future shipment. None unless history-backed."""
    if provenance != "history" or n < 2:
        return None
    margin = t_critical(conf, min(n - 1, 30)) * sigma * math.sqrt(1.0 + 1.0 / n)
    return {"low": round(mu - margin, 1), "high": round(mu + margin, 1),
            "margin": round(margin, 1),
            "confidence_pct": int(round(conf * 100))}

# ---- Distance -------------------------------------------------------------

K_CIRCUITRY = 1.18          # road-network factor, MIT SC0x §1.9.10 range 1.15-1.20
MILES_PER_DAY = 600.0       # per driver; used for every road-transit estimate


def drive_days_for_miles(miles, drivers=1):
    """Calendar drive days = ceil(miles / (600 × drivers)). None if no miles."""
    if not miles or float(miles) <= 0:
        return None
    n = max(1, int(drivers or 1))
    return math.ceil(float(miles) / (MILES_PER_DAY * n))


def haversine_miles(lat1, lng1, lat2, lng2):
    r = 3959.0  # earth radius, statute miles (MIT great-circle formula)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def resolve_road_miles(maps_miles=None, manual_miles=None,
                       origin_coords=None, dest_coords=None):
    """Priority: operator entry > Maps > great-circle x k > None.
    origin/dest_coords are (lat, lng) tuples, e.g. from the existing
    geocoder. Kills the -1 sentinel path."""
    if manual_miles and float(manual_miles) > 0:
        return round(float(manual_miles), 0)
    if maps_miles and float(maps_miles) > 0:
        return round(float(maps_miles), 0)
    if origin_coords and dest_coords:
        gc = haversine_miles(*origin_coords, *dest_coords)
        return round(gc * K_CIRCUITRY, 0)
    return None

# ---- Holding cost (value-based, falls back to storage-based) --------------

DEFAULT_HOLDING_RATE = 0.20  # annual % of cargo value: capital+ops+risk


def daily_holding_cost_per_pallet(cargo_value_per_pallet=None,
                                  storage_cost_weekly=None,
                                  rate=DEFAULT_HOLDING_RATE):
    """Prefer value-based (MIT §3.6.6); legacy storage $/pallet-wk only
    when cargo value is unknown. Returns $/pallet/day or None."""
    if cargo_value_per_pallet and cargo_value_per_pallet > 0:
        return round(cargo_value_per_pallet * rate / 365.0, 4)
    if storage_cost_weekly and storage_cost_weekly > 0:
        return round(storage_cost_weekly / 7.0, 4)
    return None

# ---- Carbon (corrected units) ---------------------------------------------

EF_KG_CO2_PER_TON_MILE = 0.162   # EPA: 161.8 g CO2e/ton-mile, med/heavy truck
DEFAULT_PALLET_LB = 500.0


def estimate_co2_kg(distance_miles, weight_lb=None, pallet_count=None,
                    ef=EF_KG_CO2_PER_TON_MILE):
    """kg CO2e = miles x short tons x EF. Ton-mile EF already embeds
    average trailer utilization, so no manual apportioning needed.
    Weight unknown -> pallets x DEFAULT_PALLET_LB. Returns None if
    neither distance nor any mass proxy exists."""
    if not distance_miles or distance_miles <= 0:
        return None
    if weight_lb and weight_lb > 0:
        tons = weight_lb / 2000.0
    elif pallet_count and pallet_count > 0:
        tons = pallet_count * DEFAULT_PALLET_LB / 2000.0
    else:
        return None
    return round(distance_miles * tons * ef, 1)