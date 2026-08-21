import json
import logging
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
import base64
import binascii
from datetime import datetime, timedelta

from flask import Flask, jsonify, redirect, render_template, request, url_for

from config import COMPANY_INFO, ensure_config_file, load_google_maps_api_key
from paths import data_path, resource_dir

ROUTES_MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
GEOCODE_URL = "https://geocode.googleapis.com/v4/geocode/address"
US_ZIP_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")

ensure_config_file()
load_google_maps_api_key()

app = Flask(
    __name__,
    template_folder=os.path.join(resource_dir(), "templates"),
    static_folder=os.path.join(resource_dir(), "static"),
    static_url_path="/static",
)


def _normalize_zip(zip_code: str) -> str:
    return (zip_code or "").strip()


def _zip_base(zip_code: str) -> str:
    return _normalize_zip(zip_code).split("-", 1)[0]


def _is_valid_us_zip_format(zip_code: str) -> bool:
    return bool(US_ZIP_PATTERN.match(_normalize_zip(zip_code)))


def _normalize_postal_code(postal_code: str) -> str:
    return re.sub(r"[\s-]", "", (postal_code or ""))[:5]


def _geocode_zip(zip_code: str, api_key: str) -> bool | None:
    zip_base = _zip_base(zip_code)
    query = urllib.parse.urlencode(
        {
            "address.postalCode": zip_base,
            "address.regionCode": "US",
        }
    )
    request_obj = urllib.request.Request(
        f"{GEOCODE_URL}?{query}",
        headers={"X-Goog-Api-Key": api_key},
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logging.getLogger(__name__).warning("Geocoding HTTP error for %s: %s %s", zip_base, exc.code, body)
        return None
    except Exception as exc:
        logging.getLogger(__name__).warning("Geocoding lookup failed for %s: %s", zip_base, exc)
        return None

    results = payload.get("results") or []
    if not results:
        return False

    expected = _normalize_postal_code(zip_base)
    for result in results:
        postal_address = result.get("postalAddress") or {}
        result_postal = _normalize_postal_code(postal_address.get("postalCode") or "")
        if result_postal == expected:
            return True

        for component in result.get("addressComponents") or []:
            if "postal_code" not in component.get("types", []):
                continue
            component_postal = _normalize_postal_code(
                component.get("longText") or component.get("shortText") or ""
            )
            if component_postal == expected:
                return True

    return False


def _zip_exists(zip_code: str, api_key: str) -> bool | None:
    if not _is_valid_us_zip_format(zip_code):
        return False

    geocoded = _geocode_zip(zip_code, api_key)
    if geocoded is not None:
        return geocoded

    return True


def _distance_lookup_error(origin_zip: str, destination_zip: str, api_key: str, fallback: str | None) -> str:
    origin_exists = _zip_exists(origin_zip, api_key)
    destination_exists = _zip_exists(destination_zip, api_key)

    if origin_exists is False and destination_exists is False:
        return "Origin and destination ZIP codes not found."
    if origin_exists is False:
        return "Origin ZIP Code not found."
    if destination_exists is False:
        return "Destination ZIP Code not found."
    return fallback or "Could not calculate distance for those ZIP codes."


def _routes_api_error_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return "Distance lookup failed. Check app.log for details."

    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return "Distance lookup failed. Check app.log for details."

    message = (error.get("message") or "").strip()
    if "Routes API has not been used" in message or "routes.googleapis.com" in message:
        return "Enable the Routes API in Google Cloud Console for this API key, then restart the app."
    if message:
        return message
    return "Distance lookup failed. Check app.log for details."


def _query_route_matrix(origin: str, destination: str, api_key: str) -> tuple[dict | None, str | None]:
    payload = {
        "origins": [{"waypoint": {"address": origin}}],
        "destinations": [{"waypoint": {"address": destination}}],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
        "units": "IMPERIAL",
    }
    request_obj = urllib.request.Request(
        ROUTES_MATRIX_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,status,condition",
        },
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logging.getLogger(__name__).warning("Routes API HTTP error %s: %s", exc.code, body)
        return None, _routes_api_error_message(body)
    except Exception as exc:
        logging.getLogger(__name__).warning("Routes API request failed: %s", exc)
        return None, "Distance lookup failed. Check app.log for details."

    if not isinstance(result, list) or not result:
        logging.getLogger(__name__).warning("Routes API returned unexpected response: %s", result)
        return None, "Distance lookup failed. Check app.log for details."

    return result[0], None


def compute_driving_distance_miles(origin_zip: str, destination_zip: str, api_key: str) -> tuple[int | None, str | None]:
    origin = _normalize_zip(origin_zip)
    destination = _normalize_zip(destination_zip)

    if not origin or not destination:
        return None, "Enter both ZIP codes."

    origin_exists = _zip_exists(origin, api_key)
    destination_exists = _zip_exists(destination, api_key)
    if origin_exists is False and destination_exists is False:
        return None, "Origin and destination ZIP codes not found."
    if origin_exists is False:
        return None, "Origin ZIP Code not found."
    if destination_exists is False:
        return None, "Destination ZIP Code not found."

    if _zip_base(origin) == _zip_base(destination):
        return 0, None

    element, api_error = _query_route_matrix(f"{origin}, USA", f"{destination}, USA", api_key)
    if api_error:
        return None, api_error
    if element is None:
        return None, "Distance lookup failed. Check app.log for details."

    status = element.get("status") or {}
    if status.get("code", 0) != 0:
        logging.getLogger(__name__).warning("Routes API element error: %s", status)
        message = (status.get("message") or "").strip()
        return None, _distance_lookup_error(origin, destination, api_key, message or None)

    if element.get("condition") != "ROUTE_EXISTS":
        logging.getLogger(__name__).warning("Routes API no route: %s", element)
        return None, _distance_lookup_error(origin, destination, api_key, None)

    meters = element.get("distanceMeters")
    if meters is None:
        return None, _distance_lookup_error(origin, destination, api_key, None)

    if meters == 0:
        return 0, None

    return math.ceil(meters * 0.000621371), None


class QuoteGenerator:
    def __init__(self, origin_city, origin_zip, destination_city, destination_zip, preview=False):
        self.origin_city = origin_city
        self.origin_zip = origin_zip
        self.destination_city = destination_city
        self.destination_zip = destination_zip
        self.company_name = COMPANY_INFO["company_name"]
        self.phone = COMPANY_INFO["phone"]
        self.email = COMPANY_INFO["email"]
        self.website = COMPANY_INFO["website"]
        self.dot_number = COMPANY_INFO["dot_number"]
        self.mc_number = COMPANY_INFO["mc_number"]
        self.quote_number = "PREVIEW" if preview else self._next_quote_number()

    def _next_quote_number(self):
        counter_file = data_path("quote_counter.json")
        if not os.path.exists(counter_file):
            with open(counter_file, "w", encoding="utf-8") as f:
                json.dump({"counter": 1}, f)
            return 1

        with open(counter_file, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data["counter"] += 1
            f.seek(0)
            json.dump(data, f)
            f.truncate()
            return data["counter"]

    def calculate_distance(self, origin_zip, destination_zip):
        api_key = load_google_maps_api_key()
        if not api_key:
            return -1

        miles, _error = compute_driving_distance_miles(origin_zip, destination_zip, api_key)
        return miles if miles is not None else -1

    def estimate_transit_time(self, miles):
        if miles <= 0:
            return "N/A"
        days = math.ceil((miles / 50) / 9)
        return f"{days} days"

    def create_pricing_tiers(self, tier_prices):
        return [
            {"name": "Single - 1 Pallet", "pallet_range": "1", "price_per_pallet": tier_prices["tier1"], "min_pallets": 1, "max_pallets": 1},
            {"name": "Small - 2-5 Pallets", "pallet_range": "2-5", "price_per_pallet": tier_prices["tier2"], "min_pallets": 2, "max_pallets": 5},
            {"name": "Medium - 6-10 Pallets", "pallet_range": "6-10", "price_per_pallet": tier_prices["tier3"], "min_pallets": 6, "max_pallets": 10},
            {"name": "Large - 11-14 Pallets", "pallet_range": "11-14", "price_per_pallet": tier_prices["tier4"], "min_pallets": 11, "max_pallets": 14},
        ]


DEFAULT_LTL_SCENARIOS = (
    {
        "title": "Scenario 1: E-Commerce Retailer (Steady Demand)",
        "desc": "Weekly demand of 8 pallets.",
        "pallets": 8,
        "current_frequency": 2,
        "current_pallets_per_ship": 4,
    },
    {
        "title": "Scenario 2: Seasonal Business (Bi-Weekly Demand)",
        "desc": "Bi-weekly shipment of 12 pallets.",
        "pallets": 12,
        "current_frequency": 3,
        "current_pallets_per_ship": 4,
    },
    {
        "title": "Scenario 3: Bulk Distribution Center (Monthly Replenishment)",
        "desc": "Monthly replenishment of 14 pallets.",
        "pallets": 14,
        "current_frequency": 2,
        "current_pallets_per_ship": 7,
    },
)


LTL_TIER_STEPS = (
    {"min_pallets": 1, "max_pallets": 1, "tier_key": "tier1", "label": "Single", "next_min": 2, "next_tier_key": "tier2"},
    {"min_pallets": 2, "max_pallets": 5, "tier_key": "tier2", "label": "Small", "next_min": 6, "next_tier_key": "tier3"},
    {"min_pallets": 6, "max_pallets": 10, "tier_key": "tier3", "label": "Medium", "next_min": 11, "next_tier_key": "tier4"},
    {"min_pallets": 11, "max_pallets": 14, "tier_key": "tier4", "label": "Large", "next_min": None, "next_tier_key": None},
)

TIER_DISPLAY_NAMES = {
    "tier1": "Single Volume Tier",
    "tier2": "Small Volume Tier",
    "tier3": "Medium Volume Tier",
    "tier4": "Large Volume Tier",
}

EOQ_WEEKLY_STORAGE_COLUMNS = (0.0, 24.0, 48.0, 72.0)

T_CRITICAL_90 = {
    1: 6.314,
    2: 2.920,
    3: 2.353,
    4: 2.132,
    5: 2.015,
    6: 1.943,
    7: 1.895,
    8: 1.860,
    9: 1.833,
    10: 1.812,
    11: 1.796,
    12: 1.782,
    13: 1.771,
    14: 1.761,
    15: 1.753,
    16: 1.746,
    17: 1.740,
    18: 1.734,
    19: 1.729,
    20: 1.725,
    21: 1.721,
    22: 1.717,
    23: 1.714,
    24: 1.711,
    25: 1.708,
    26: 1.706,
    27: 1.703,
    28: 1.701,
    29: 1.699,
    30: 1.697,
}


def t_critical_90(degrees_of_freedom):
    df = max(1, int(degrees_of_freedom))
    if df >= 30:
        return 1.645
    return T_CRITICAL_90.get(df, 1.697)


def reliability_rating_from_cv(cv):
    if cv is None:
        return "Insufficient Data"
    if cv < 0.15:
        return "Excellent"
    if cv < 0.25:
        return "Good"
    if cv < 0.40:
        return "Moderate"
    return "Variable"


def detect_phantom_consolidation(requested_volume, tier_prices):
    quantity = max(1, int(requested_volume))
    for step in LTL_TIER_STEPS:
        if step["min_pallets"] <= quantity <= step["max_pallets"]:
            if step["next_min"] is None:
                return {"show": False}
            current_price = tier_prices[step["tier_key"]]
            next_price = tier_prices[step["next_tier_key"]]
            current_total = quantity * current_price
            optimized_total = step["next_min"] * next_price
            if current_total <= optimized_total:
                return {"show": False}
            return {
                "show": True,
                "requested_volume": quantity,
                "current_total_cost": round(current_total, 2),
                "current_tier_label": TIER_DISPLAY_NAMES[step["tier_key"]],
                "optimized_volume": step["next_min"],
                "optimized_total_cost": round(optimized_total, 2),
                "optimized_tier_label": TIER_DISPLAY_NAMES[step["next_tier_key"]],
                "pallet_differential": step["next_min"] - quantity,
                "net_financial_savings": round(current_total - optimized_total, 2),
            }
    return {"show": False}


def norm_ppf(probability):
    """Standard normal inverse CDF (equivalent to scipy.stats.norm.ppf)."""
    p = max(1e-9, min(1 - 1e-9, float(probability)))
    return math.sqrt(2) * math.erfinv(2 * p - 1)


def lane_sample_std_dev(historical_lane_data):
    """Sample standard deviation from historical lane transit times."""
    values = [float(x) for x in historical_lane_data]
    count = len(values)
    if count < 2:
        return 0.0
    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / (count - 1)
    return math.sqrt(variance)


def calculate_buffer_days(desired_csl, std_dev=None, historical_lane_data=None):
    """
    Safety-stock buffer days for a single LTL shipment at the desired CSL.
    buffer_days = Z(CSL) × lane_standard_deviation
    """
    probability = float(desired_csl) / 100.0
    z_score = norm_ppf(probability)

    if historical_lane_data:
        lane_std = lane_sample_std_dev(historical_lane_data)
    else:
        lane_std = max(0.0, float(std_dev or 0.0))

    buffer_days = z_score * lane_std
    return {
        "buffer_days": round(buffer_days, 1),
        "z_score": round(z_score, 3),
        "lane_std_dev": round(lane_std, 2),
        "desired_csl": int(desired_csl),
    }


def calculate_transit_prediction(mean_days, std_dev, sample_size):
    sample_count = max(2, int(sample_size))
    mean = float(mean_days)
    std = max(0.0, float(std_dev))
    degrees_of_freedom = sample_count - 1
    margin = t_critical_90(degrees_of_freedom) * std * math.sqrt(1 + (1 / sample_count))
    lower = max(1, int(math.floor(mean - margin)))
    upper = max(lower, int(math.ceil(mean + margin)))
    coefficient_of_variation = round(std / mean, 3) if mean > 0 else None
    return {
        "mean_days": round(mean, 1),
        "std_dev": round(std, 2),
        "sample_size": sample_count,
        "lower_interval_days": lower,
        "upper_interval_days": upper,
        "margin_days": round(margin, 2),
        "coefficient_of_variation": coefficient_of_variation,
        "reliability_rating": reliability_rating_from_cv(coefficient_of_variation),
        "display_window": f"{lower} to {upper} Business Days",
    }


def map_eoq_to_recommendation(eoq_pallets):
    if eoq_pallets >= 11:
        return "Bulk (14 Plts)", "Monthly"
    if eoq_pallets >= 6:
        return "Med (8 Plts)", "Bi-Weekly"
    if eoq_pallets >= 2:
        return "Sm (4 Plts)", "Weekly"
    return "Single (1 Plt)", "Daily"


def calculate_eoq(annual_demand, annual_holding_cost, tier_prices, max_pallets=14):
    demand = max(1, int(annual_demand))
    cap = max(1, int(max_pallets))
    if annual_holding_cost <= 0:
        pallets = cap
        order_label, frequency = map_eoq_to_recommendation(pallets)
        return {
            "eoq_pallets": pallets,
            "order_label": order_label,
            "frequency": frequency,
            "calculated_eoq": float(cap),
            "shipment_cost": round(pallets * ltl_price_for_pallet_count(pallets, tier_prices), 2),
        }

    shipment_cost = cap * ltl_price_for_pallet_count(cap, tier_prices)
    eoq_value = math.sqrt(2 * demand * shipment_cost / annual_holding_cost)
    pallets = max(1, min(cap, round(eoq_value)))
    tier_price = ltl_price_for_pallet_count(pallets, tier_prices)
    shipment_cost = pallets * tier_price
    eoq_value = math.sqrt(2 * demand * shipment_cost / annual_holding_cost)
    pallets = max(1, min(cap, round(eoq_value)))
    order_label, frequency = map_eoq_to_recommendation(pallets)
    return {
        "eoq_pallets": pallets,
        "order_label": order_label,
        "frequency": frequency,
        "calculated_eoq": round(eoq_value, 1),
        "shipment_cost": round(pallets * ltl_price_for_pallet_count(pallets, tier_prices), 2),
    }


def build_eoq_matrix(form, tier_prices, analysis_config):
    annual_demand = analysis_config["annual_demand"]
    max_pallets = analysis_config["max_chart_pallets"]
    rows = []
    for weekly_cost in EOQ_WEEKLY_STORAGE_COLUMNS:
        annual_holding = weekly_cost * 52
        result = calculate_eoq(annual_demand, annual_holding, tier_prices, max_pallets)
        rows.append(
            {
                "weekly_storage_cost": weekly_cost,
                "weekly_storage_label": f"${weekly_cost:.2f} / wk",
                **result,
            }
        )
    return rows

def _parse_form_int(form, key, default, minimum=0):
    try:
        value = int(form.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def _parse_form_float(form, key, default, minimum=0.0):
    try:
        value = float(form.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def ltl_price_for_pallet_count(count, tier_prices):
    pallets = max(1, int(count))
    if pallets == 1:
        return tier_prices["tier1"]
    if pallets <= 5:
        return tier_prices["tier2"]
    if pallets <= 10:
        return tier_prices["tier3"]
    return tier_prices["tier4"]


def format_current_practice(frequency, pallets_per_ship):
    if frequency <= 0 or pallets_per_ship <= 0:
        return ""
    shipment_word = "shipment" if frequency == 1 else "shipments"
    pallet_word = "pallet" if pallets_per_ship == 1 else "pallets"
    return f"{frequency} {shipment_word} of {pallets_per_ship} {pallet_word} each"


def parse_ltl_analysis_config(form):
    return {
        "requested_volume": _parse_form_int(form, "requested_volume", 5, minimum=1),
        "annual_demand": _parse_form_int(form, "annual_demand", 416, minimum=1),
        "max_trailer_pallets": _parse_form_int(form, "max_trailer_pallets", 26, minimum=1),
        "max_chart_pallets": _parse_form_int(form, "max_chart_pallets", 14, minimum=1),
        "transit_mean_days": _parse_form_float(form, "transit_mean_days", 3.0, minimum=0.1),
        "transit_std_dev": _parse_form_float(form, "transit_std_dev", 0.5, minimum=0.0),
        "transit_sample_size": _parse_form_int(form, "transit_sample_size", 12, minimum=2),
        "carbon_baseline_trips": _parse_form_int(form, "carbon_baseline_trips", 2, minimum=1),
        "carbon_optimized_trips": _parse_form_int(form, "carbon_optimized_trips", 1, minimum=1),
        "emissions_factor": _parse_form_float(form, "emissions_factor", 0.000161, minimum=0.0),
    }


def build_ltl_scenarios(form, tier_prices):
    base_price = tier_prices["tier1"]
    scenarios = []
    for index, defaults in enumerate(DEFAULT_LTL_SCENARIOS, start=1):
        prefix = f"scenario_{index}_"
        title = (form.get(f"{prefix}title") or defaults["title"]).strip()
        desc = (form.get(f"{prefix}desc") or defaults["desc"]).strip()
        pallets = _parse_form_int(form, f"{prefix}pallets", defaults["pallets"], minimum=1)
        current_frequency = _parse_form_int(form, f"{prefix}current_frequency", defaults["current_frequency"], minimum=0)
        current_pallets_per_ship = _parse_form_int(
            form,
            f"{prefix}current_pallets_per_ship",
            defaults["current_pallets_per_ship"],
            minimum=0,
        )
        tier_price = ltl_price_for_pallet_count(pallets, tier_prices)
        recommended_cost = round(pallets * tier_price, 2)
        savings = round((pallets * base_price) - recommended_cost, 2)
        current_cost = None
        if current_frequency > 0 and current_pallets_per_ship > 0:
            current_tier_price = ltl_price_for_pallet_count(current_pallets_per_ship, tier_prices)
            current_cost = round(current_frequency * current_pallets_per_ship * current_tier_price, 2)
        scenarios.append(
            {
                "title": title,
                "desc": desc,
                "pallets": pallets,
                "recommended_cost": recommended_cost,
                "savings": savings,
                "optimal_volume": pallets,
                "current_practice": format_current_practice(current_frequency, current_pallets_per_ship),
                "current_cost": current_cost,
                "tier_price": tier_price,
            }
        )
    return scenarios


def calculate_ltl_supply_metrics(tier_prices, distance, analysis_config):
    tier4 = tier_prices["tier4"]
    tier1 = tier_prices["tier1"]
    max_pallets = analysis_config["max_chart_pallets"]
    capacity = analysis_config["max_trailer_pallets"]
    miles = distance if distance and distance > 0 else None
    emissions_factor = analysis_config["emissions_factor"]

    cost_per_pallet_mile = round(tier4 / miles, 2) if miles else None
    utilization_pct = round((max_pallets / capacity) * 100) if capacity > 0 else 0
    consolidation_multiplier = round(tier1 / tier4, 2) if tier4 > 0 else None

    baseline_trips = analysis_config["carbon_baseline_trips"]
    optimized_trips = min(analysis_config["carbon_optimized_trips"], baseline_trips)
    trip_reduction = max(0, baseline_trips - optimized_trips)
    carbon_reduction_pct = round((trip_reduction / baseline_trips) * 100) if baseline_trips > 0 else 0
    co2_saved_kg = round(trip_reduction * miles * emissions_factor, 2) if miles else None

    return {
        "cost_per_pallet_mile": cost_per_pallet_mile,
        "utilization_pallets": max_pallets,
        "utilization_pct": utilization_pct,
        "consolidation_multiplier": consolidation_multiplier,
        "carbon_reduction_pct": carbon_reduction_pct,
        "co2_saved_kg": co2_saved_kg,
        "max_trailer_pallets": capacity,
    }


NMFC_DENSITY_BRACKETS = (
    (50, 50),
    (35, 55),
    (30, 60),
    (22.5, 65),
    (15, 70),
    (13.5, 77.5),
    (12, 85),
    (10, 92.5),
    (8, 100),
    (6, 110),
    (4, 125),
    (2, 175),
    (0, 250),
)

SINGLE_ACCESSORIAL_DEFAULTS = {
    "liftgate": 75.0,
    "residential": 85.0,
    "appointment": 45.0,
    "limited_access": 65.0,
}


def nmfc_class_from_density(density):
    for min_density, nmfc_class in NMFC_DENSITY_BRACKETS:
        if density >= min_density:
            return nmfc_class
    return 250


def next_higher_nmfc_class(nmfc_class):
    ordered = [item[1] for item in reversed(NMFC_DENSITY_BRACKETS)]
    try:
        index = ordered.index(nmfc_class)
    except ValueError:
        return nmfc_class
    if index >= len(ordered) - 1:
        return nmfc_class
    return ordered[index + 1]


def parse_single_ltl_form(form):
    pallet_count = _parse_form_int(form, "pallet_count", 1, minimum=1)
    linehaul_cost = _parse_form_float(form, "linehaul_cost", 0.0)
    fuel_surcharge = _parse_form_float(form, "fuel_surcharge", 0.0)
    price_per_pallet_input = _parse_form_float(form, "price_per_pallet", 0.0)
    if linehaul_cost <= 0 and price_per_pallet_input > 0:
        estimated_total = price_per_pallet_input * pallet_count
        linehaul_cost = round(estimated_total * 0.82, 2)
        fuel_surcharge = round(estimated_total * 0.18, 2)
    elif linehaul_cost <= 0:
        linehaul_cost = price_per_pallet_input * pallet_count
    if fuel_surcharge <= 0 and linehaul_cost > 0:
        fuel_surcharge = round(linehaul_cost * 0.18, 2)

    accessorial_items = []
    accessorial_cost = 0.0
    accessorial_labels = []
    for key, label in (
        ("liftgate", "Liftgate"),
        ("residential", "Residential Delivery"),
        ("appointment", "Appointment Required"),
        ("limited_access", "Limited Access"),
    ):
        if form.get(f"accessorial_{key}") in ("on", "true", "1", "yes"):
            fee = _parse_form_float(form, f"fee_{key}", SINGLE_ACCESSORIAL_DEFAULTS[key])
            accessorial_cost += fee
            accessorial_items.append({"key": key, "label": label, "fee": round(fee, 2)})
            accessorial_labels.append(label)

    total_cost = round(linehaul_cost + fuel_surcharge + accessorial_cost, 2)
    price_per_pallet = round(total_cost / pallet_count, 2) if pallet_count > 0 else 0.0

    return {
        "pallet_count": pallet_count,
        "linehaul_cost": round(linehaul_cost, 2),
        "fuel_surcharge": round(fuel_surcharge, 2),
        "accessorial_cost": round(accessorial_cost, 2),
        "accessorial_items": accessorial_items,
        "accessorial_labels": accessorial_labels,
        "total_cost": total_cost,
        "price_per_pallet": price_per_pallet,
        "pallet_length": _parse_form_float(form, "pallet_length", 48.0, minimum=1.0),
        "pallet_width": _parse_form_float(form, "pallet_width", 48.0, minimum=1.0),
        "pallet_height": _parse_form_float(form, "pallet_height", 48.0, minimum=1.0),
        "cargo_weight": _parse_form_float(form, "cargo_weight", 1000.0, minimum=1.0),
        "commodity_value_per_pallet": _parse_form_float(form, "commodity_value_per_pallet", 5000.0, minimum=0.0),
        "transit_mean_days": _parse_form_float(form, "transit_mean_days", 3.0, minimum=0.1),
        "transit_std_dev": _parse_form_float(form, "transit_std_dev", 0.5, minimum=0.0),
        "desired_csl": _parse_form_int(form, "desired_csl", 95, minimum=90),
        "annual_holding_rate": _parse_form_float(form, "annual_holding_rate", 20.0, minimum=0.0),
        "reclassification_penalty": _parse_form_float(form, "reclassification_penalty", 125.0, minimum=0.0),
    }


def calculate_single_ltl_analytics(payload, miles):
    pallet_count = payload["pallet_count"]
    length = payload["pallet_length"]
    width = payload["pallet_width"]
    height = payload["pallet_height"]
    total_weight = payload["cargo_weight"]
    volume_per_pallet = (length * width * height) / 1728.0
    total_volume = max(volume_per_pallet * pallet_count, 0.01)
    calculated_density = round(total_weight / total_volume, 2)
    nmfc_class = nmfc_class_from_density(calculated_density)

    overhang = length > 48 or width > 48
    higher_nmfc_class = next_higher_nmfc_class(nmfc_class) if overhang else nmfc_class
    show_reclassification = overhang or length != 48 or width != 48 or height > 60

    mean_transit = payload["transit_mean_days"]
    std_dev = payload["transit_std_dev"]
    lane_cv = round(std_dev / mean_transit, 3) if mean_transit > 0 else None
    buffer = calculate_buffer_days(payload["desired_csl"], std_dev=std_dev)
    transit_prediction = calculate_transit_prediction(mean_transit, std_dev, 12)

    distance = miles if miles and miles > 0 else None
    total_cost = payload["total_cost"]
    cost_per_pallet_mile = round(total_cost / (pallet_count * distance), 2) if distance else None
    holding_rate = payload["annual_holding_rate"] / 100.0
    pipeline_inventory_cost = round(
        (payload["commodity_value_per_pallet"] * pallet_count) * (holding_rate / 365) * mean_transit,
        2,
    )
    equivalent_gallons = round(distance / 6.5, 1) if distance else None

    accessorial_summary = " / ".join(payload["accessorial_labels"]) if payload["accessorial_labels"] else "None"

    return {
        "calculated_density": calculated_density,
        "nmfc_class": nmfc_class,
        "higher_nmfc_class": higher_nmfc_class,
        "show_reclassification": show_reclassification,
        "penalty_fee": payload["reclassification_penalty"],
        "lane_cv": lane_cv,
        "avg_transit_days": round(mean_transit, 1),
        "safety_days": buffer["buffer_days"],
        "desired_csl": buffer["desired_csl"],
        "z_value": buffer["z_score"],
        "lane_std_dev": buffer["lane_std_dev"],
        "transit_prediction": transit_prediction,
        "cost_per_pallet_mile": cost_per_pallet_mile,
        "pipeline_inventory_cost": pipeline_inventory_cost,
        "equivalent_gallons": equivalent_gallons,
        "accessorial_summary": accessorial_summary,
        "ledger": {
            "distance_miles": distance,
            "linehaul_cost": payload["linehaul_cost"],
            "fuel_cost": payload["fuel_surcharge"],
            "accessorial_cost": payload["accessorial_cost"],
            "total_cost": total_cost,
        },
    }


def parse_international_payload(data):
    quote_name = data.get("quote_name", "International Freight Quote")
    origin_text = data.get("origin_text", "Origin")
    destination_text = data.get("destination_text", "Destination")
    try:
        example_pallets = int(data.get("example_pallets", 10))
    except (ValueError, TypeError):
        example_pallets = 10

    lanes = []
    for i, raw in enumerate(data.get("lanes", []), start=1):
        legs = []
        for leg in raw.get("legs", []):
            name = leg.get("name") or leg.get("leg_name") or ""
            try:
                cost = float(leg.get("costPerPallet", leg.get("cost", leg.get("leg_cost", 0)) or 0))
            except (ValueError, TypeError):
                cost = 0.0
            transit_days = None
            for key in ("transit_days", "transit"):
                if leg.get(key) in (None, ""):
                    continue
                try:
                    transit_days = int(leg.get(key))
                    break
                except (ValueError, TypeError):
                    transit_days = None
            if name or cost:
                legs.append({"name": name, "costPerPallet": cost, "transit_days": transit_days})

        lanes.append({
            "id": f"Lane {chr(64 + i)}",
            "description": raw.get("description", ""),
            "otherFees": float(raw.get("otherFees", raw.get("other_fees", 0) or 0)),
            "details": raw.get("details", raw.get("lane_details", "")) or "",
            "notes": raw.get("notes", raw.get("lane_notes", "")) or "",
            "legs": legs,
        })

    return {
        "quote_name": quote_name,
        "origin_text": origin_text,
        "destination_text": destination_text,
        "example_pallets": example_pallets,
        "quote_notes": data.get("quote_notes", ""),
        "valid_until": data.get("valid_until"),
        "preview": bool(data.get("preview", False)),
        "lanes": lanes,
    }


def lane_transit_total(lane: dict) -> int | None:
    total = 0
    has_transit = False
    for leg in lane.get("legs", []):
        days = leg.get("transit_days")
        if days is None:
            continue
        try:
            total += int(days)
            has_transit = True
        except (ValueError, TypeError):
            continue
    return total if has_transit else None


def summarize_international_transit(lanes: list[dict]) -> str:
    totals = [total for total in (lane_transit_total(lane) for lane in lanes) if total is not None]
    if not totals:
        return "N/A"

    low = min(totals)
    high = max(totals)
    if low == high:
        suffix = "day" if low == 1 else "days"
        return f"{low} {suffix}"
    return f"{low}-{high} days"


def finalize_international_lanes(lanes, example_pallets):
    pallets = example_pallets if example_pallets > 0 else 1
    for lane in lanes:
        legs_total = sum(leg.get("costPerPallet", 0) for leg in lane["legs"])
        lane["per_pallet_cost"] = (legs_total + lane.get("otherFees", 0)) / pallets
        lane["transit_total_days"] = lane_transit_total(lane)
    return max((lane["per_pallet_cost"] for lane in lanes), default=1)


@app.route("/")
def home():
    return render_template("mode_select.html")


@app.route("/ltl")
def ltl_quote_redirect():
    return redirect(url_for("ltl_tiered_quote"))


@app.route("/ltl/tiered", methods=["GET", "POST"])
def ltl_tiered_quote():
    if request.method == "GET":
        return render_template("ltl_quote_form.html")

    tier_prices = {
        "tier1": float(request.form["tier1_price"]),
        "tier2": float(request.form["tier2_price"]),
        "tier3": float(request.form["tier3_price"]),
        "tier4": float(request.form["tier4_price"]),
    }

    quote_generator = QuoteGenerator(
        request.form["origin_city"],
        request.form["origin_zip"],
        request.form["destination_city"],
        request.form["destination_zip"],
    )
    miles = quote_generator.calculate_distance(quote_generator.origin_zip, quote_generator.destination_zip)
    analysis_config = parse_ltl_analysis_config(request.form)
    if miles > 0:
        estimated_transit_days = max(1, math.ceil((miles / 50) / 9))
        if request.form.get("transit_mean_days") in (None, ""):
            analysis_config["transit_mean_days"] = float(estimated_transit_days)

    scenarios = build_ltl_scenarios(request.form, tier_prices)
    supply_metrics = calculate_ltl_supply_metrics(tier_prices, miles, analysis_config)
    phantom_consolidation = detect_phantom_consolidation(analysis_config["requested_volume"], tier_prices)
    transit_prediction = calculate_transit_prediction(
        analysis_config["transit_mean_days"],
        analysis_config["transit_std_dev"],
        analysis_config["transit_sample_size"],
    )
    eoq_matrix = build_eoq_matrix(request.form, tier_prices, analysis_config)

    valid_until_date = datetime.now() + timedelta(days=30)
    quote = {
        "quote_number": quote_generator.quote_number,
        "origin_city": quote_generator.origin_city,
        "origin_zip": quote_generator.origin_zip,
        "destination_city": quote_generator.destination_city,
        "destination_zip": quote_generator.destination_zip,
        "distance": miles,
        "transit_time": transit_prediction["display_window"],
        "pricing_tiers": quote_generator.create_pricing_tiers(tier_prices),
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        "valid_until": valid_until_date.strftime("%B %d, %Y").replace(" 0", " "),
        **COMPANY_INFO,
    }

    return render_template(
        "ltl_quote_output.html",
        quote=quote,
        tier_prices=json.dumps(tier_prices),
        analysis_config=json.dumps(analysis_config),
        scenarios=scenarios,
        supply_metrics=supply_metrics,
        phantom_consolidation=phantom_consolidation,
        transit_prediction=transit_prediction,
        eoq_matrix=eoq_matrix,
        current_year=datetime.now().year,
    )


@app.route("/ltl/single", methods=["GET", "POST"])
def ltl_single_quote():
    if request.method == "GET":
        return render_template("ltl_single_quote_form.html")

    try:
        payload = parse_single_ltl_form(request.form)
        if payload["total_cost"] <= 0:
            raise ValueError("invalid pricing")
    except (ValueError, KeyError, TypeError):
        return render_template("ltl_single_quote_form.html"), 400

    quote_generator = QuoteGenerator(
        request.form["origin_city"],
        request.form["origin_zip"],
        request.form["destination_city"],
        request.form["destination_zip"],
    )
    miles = quote_generator.calculate_distance(quote_generator.origin_zip, quote_generator.destination_zip)
    if miles > 0 and request.form.get("transit_mean_days") in (None, ""):
        payload["transit_mean_days"] = max(1.0, float(math.ceil((miles / 50) / 9)))

    analytics = calculate_single_ltl_analytics(payload, miles)
    transit_prediction = analytics["transit_prediction"]

    valid_until_date = datetime.now() + timedelta(days=30)
    quote = {
        "quote_number": quote_generator.quote_number,
        "origin_city": quote_generator.origin_city,
        "origin_zip": quote_generator.origin_zip,
        "destination_city": quote_generator.destination_city,
        "destination_zip": quote_generator.destination_zip,
        "distance": miles if miles >= 0 else None,
        "distance_display": f"{miles} miles" if miles >= 0 else "N/A",
        "transit_time": transit_prediction["display_window"],
        "pallet_count": payload["pallet_count"],
        "price_per_pallet": payload["price_per_pallet"],
        "total_cost": payload["total_cost"],
        "cost_per_pallet_mile": analytics["cost_per_pallet_mile"],
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        "valid_until": valid_until_date.strftime("%B %d, %Y").replace(" 0", " "),
        **COMPANY_INFO,
    }

    return render_template(
        "ltl_single_quote_output.html",
        quote=quote,
        payload=payload,
        analytics=analytics,
        transit_prediction=transit_prediction,
        current_year=datetime.now().year,
    )


@app.route("/ftl")
def ftl_quote():
    return render_template("coming_soon.html", mode="FTL")


@app.route("/dray")
def dray_quote():
    return render_template("coming_soon.html", mode="Dray")


@app.route("/international", methods=["GET", "POST"])
def international_quote():
    if request.method == "GET":
        return render_template("international_quote_form.html")

    data = request.get_json(silent=True)
    if not data and "payload" in request.form:
        try:
            data = json.loads(request.form.get("payload"))
        except json.JSONDecodeError:
            data = None

    if not data:
        return render_template("international_quote_form.html"), 400

    parsed = parse_international_payload(data)
    qg = QuoteGenerator("", "", "", "", preview=parsed["preview"])
    max_total_per_pallet = finalize_international_lanes(parsed["lanes"], parsed["example_pallets"])
    transit_time_display = summarize_international_transit(parsed["lanes"])

    quote = {
        "quote_number": qg.quote_number,
        **COMPANY_INFO,
        "title": parsed["quote_name"],
        "origin_text": parsed["origin_text"],
        "destination_text": parsed["destination_text"],
        "quote_notes": parsed["quote_notes"],
        "example_pallets": parsed["example_pallets"],
        "valid_until": parsed["valid_until"],
        "transit_time_display": transit_time_display,
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
    }

    return render_template(
        "international_quote_output.html",
        quote=quote,
        lanes=parsed["lanes"],
        example_pallets=parsed["example_pallets"],
        max_total_per_pallet=max_total_per_pallet,
        transit_time_display=transit_time_display,
        current_year=datetime.now().year,
    )


@app.route("/calculate_distance", methods=["POST"])
def calculate_distance_endpoint():
    data = request.get_json() or {}
    origin = data.get("origin_zip") or data.get("origin") or ""
    destination = data.get("destination_zip") or data.get("destination") or ""

    if not load_google_maps_api_key():
        return jsonify(success=False, error="missing_api_key")

    api_key = load_google_maps_api_key()
    miles, error_message = compute_driving_distance_miles(origin, destination, api_key)
    if miles is not None and miles >= 0:
        display_distance = "<1 mile" if miles == 0 else None
        return jsonify(success=True, miles=miles, display_distance=display_distance)
    return jsonify(success=False, error="distance_error", message=error_message or "Could not calculate distance for those ZIP codes.")


@app.route("/quote/prepare-pdf", methods=["POST"])
@app.route("/ltl/quote/prepare-pdf", methods=["POST"])
def prepare_ltl_quote_pdf():
    data = request.get_json() or {}
    pdf_base64 = (data.get("pdf_base64") or "").strip()
    if not pdf_base64:
        return jsonify(success=False, error="missing_pdf"), 400

    try:
        pdf_bytes = base64.b64decode(pdf_base64, validate=True)
    except (ValueError, binascii.Error):
        return jsonify(success=False, error="invalid_pdf"), 400

    token = uuid.uuid4().hex
    temp_path = data_path(f"quote-pdf-{token}.pdf")
    with open(temp_path, "wb") as pdf_file:
        pdf_file.write(pdf_bytes)

    return jsonify(success=True, token=token)


if __name__ == "__main__":
    app.run(debug=True)
