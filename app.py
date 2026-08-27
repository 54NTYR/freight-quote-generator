import json
import logging
import math
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
import base64
import binascii
from datetime import datetime, timedelta

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

import analytics_core as ac
import dray as dray_mod
import ftl as ftl_mod
import intl as intl_mod
from admin_routes import admin_bp
from config import (
    COMPANY_INFO,
    ensure_config_file,
    load_config,
    load_google_maps_api_key,
    load_rep,
    rep_configured,
    save_rep,
)
from crm_bridge import crm_sync_ready, on_quote_issued
from customers import (
    all_customers,
    delete_customer,
    remember_customer,
    search_customers,
    update_customer,
)
from dray_history import list_quotes as list_dray_history, record_quote as record_dray_quote
from lane_stats import prediction_interval_days, resolve_lane_stats
from paths import data_path, resource_dir
from quote_history import list_quotes, record_quote
from sop_catalog import SOP_FILES, allowed_sop_filenames, sops_dir
from storage import init_db, save_quote
from terminals import (
    add_terminal,
    all_terminals,
    delete_terminal,
    find_terminal,
    search_terminals,
    update_terminal,
)

ROUTES_MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
GEOCODE_URL = "https://geocode.googleapis.com/v4/geocode/address"
PLACES_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/"
# Typical US 5-axle tractor + 40' / 53' trailer. Width is 8'6" rounded down so it stays legal.
TRUCK_VEHICLE_INFO = {
    "totalAxleCount": 5,
    "totalHeightMm": 4114,
    "totalLengthMm": 21945,
    "totalWidthMm": 2590,
    "totalWeightKg": 32658,
    "trailerInfo": [{"lengthMm": 16154}],
}
ROUTES_FIELD_MASK = (
    "originIndex,destinationIndex,distanceMeters,status,condition,"
    "travelAdvisory"
)
US_ZIP_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")

ensure_config_file()
load_google_maps_api_key()
config = load_config()
CONF_LEVEL = float(config.get("confidence_level", 0.90))

app = Flask(
    __name__,
    template_folder=os.path.join(resource_dir(), "templates"),
    static_folder=os.path.join(resource_dir(), "static"),
    static_url_path="/static",
)
app.register_blueprint(admin_bp)
init_db()

DRAY_SSL_LINES = [
    "No Info", "Maersk", "Sealand", "Hapag-Lloyd", "Hamburg Sud", "Cosco",
    "CMA", "ONE", "MSC", "Evergreen", "ZIM", "HMM", "King Ocean",
]
DRAY_CONTAINERS = [
    "20' ST", "20' RF", "40' ST", "40' HC", "40' RF", "40' OT", "40' FR",
    '53" DV', '53" RF',
]
CHASSIS_DAY_RATE = 50.0
CHASSIS_MIN_DAYS = 2
TRIAXLE_DAY_RATE = 100.0
CHASSIS_SPLIT_FEE = 150.0
REEFER_FEE = 150.0
HAZMAT_FEE = 150.0
OW_FEE = 150.0
LAYOVER_FEE = 300.0
STOP_OFF_FEE = 125.0
PREPULL_FEE = 150.0
RESIDENTIAL_FEE = 100.0
OVERWEIGHT_LBS_THRESHOLD = 44000
PREPULL_MILES_THRESHOLD = 150
DRAY_RATES = {
    "chassis_day": CHASSIS_DAY_RATE,
    "chassis_min_days": CHASSIS_MIN_DAYS,
    "triaxle_day": TRIAXLE_DAY_RATE,
    "chassis_split": CHASSIS_SPLIT_FEE,
    "reefer": REEFER_FEE,
    "hazmat": HAZMAT_FEE,
    "ow": OW_FEE,
    "layover": LAYOVER_FEE,
    "stop_off": STOP_OFF_FEE,
    "prepull": PREPULL_FEE,
    "residential": RESIDENTIAL_FEE,
    "overweight_lbs": OVERWEIGHT_LBS_THRESHOLD,
    "prepull_miles": PREPULL_MILES_THRESHOLD,
}


@app.context_processor
def inject_letterhead():
    return {"letterhead": COMPANY_INFO, "rep": load_rep()}


@app.before_request
def require_quoting_rep():
    if request.endpoint in (None, "static", "rep_setup"):
        return None
    if request.path.startswith("/static"):
        return None
    if not rep_configured():
        return redirect(url_for("rep_setup"))
    return None


@app.route("/settings/rep", methods=["GET", "POST"])
def rep_setup():
    if request.method == "POST":
        name = (request.form.get("rep_name") or "").strip()
        email = (request.form.get("rep_email") or "").strip()
        if name and email:
            save_rep(name, email)
            return redirect(url_for("home"))
        return render_template("rep_setup.html", error="Both fields are required.",
                               rep_name=name, rep_email=email), 400
    return render_template("rep_setup.html", **load_rep())


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


def _google_json(url: str, api_key: str, payload: dict | None = None,
                 field_mask: str | None = None, method: str | None = None):
    headers = {"X-Goog-Api-Key": api_key}
    data = None
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = method or "POST"
    request_obj = urllib.request.Request(
        url, data=data, method=method or "GET", headers=headers,
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=15) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logging.getLogger(__name__).warning("Google HTTP error %s %s: %s", exc.code, url, body)
        return None, body
    except Exception as exc:
        logging.getLogger(__name__).warning("Google request failed %s: %s", url, exc)
        return None, str(exc)


GEOCODE_PLACE_PREFIX = "geocode:"
# Places Autocomplete (New) uses CLDR region codes. Puerto Rico is `pr`, not `us`.
PLACES_REGION_CODES = ["us", "pr", "co"]


def _places_disabled(body: str | None) -> bool:
    raw = body or ""
    return "SERVICE_DISABLED" in raw or "has not been used in project" in raw


def _prediction_from_geocode(result: dict, fallback_name: str) -> dict | None:
    if not isinstance(result, dict):
        return None
    parsed = _parse_place_components(result.get("addressComponents"))
    formatted = (result.get("formattedAddress") or "").strip()
    if not parsed["address"] and formatted:
        parsed["address"] = formatted.split(",")[0].strip()
    if not parsed["zip"] and not (parsed["city"] and parsed["state"]):
        return None
    primary = parsed["address"] or formatted.split(",")[0].strip() or fallback_name
    secondary = ""
    if formatted and "," in formatted:
        secondary = ", ".join(part.strip() for part in formatted.split(",")[1:] if part.strip())
    elif parsed["city"] or parsed["state"] or parsed["zip"]:
        secondary = ", ".join(part for part in (parsed["city"], parsed["state"], parsed["zip"]) if part)
    return {
        "placeId": GEOCODE_PLACE_PREFIX + (formatted or primary),
        "primary": primary,
        "secondary": secondary,
        "name": primary,
        "address": parsed["address"] or primary,
        "city": parsed["city"],
        "state": parsed["state"],
        "zip": parsed["zip"],
    }


def _geocode_payload(query: str, api_key: str, region_code: str | None = None) -> dict | None:
    params = {"address.addressLines": query}
    if region_code:
        params["address.regionCode"] = region_code.upper()
    qs = urllib.parse.urlencode(params)
    payload, error = _google_json(f"{GEOCODE_URL}?{qs}", api_key)
    if error or not isinstance(payload, dict):
        return None
    return payload


def _rows_from_geocode_payload(payload: dict | None, needle: str) -> list[dict]:
    rows = []
    seen = set()
    for result in (payload or {}).get("results") or []:
        row = _prediction_from_geocode(result, needle)
        if not row:
            continue
        key = (row["primary"], row["zip"], row["city"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def geocode_address_suggestions(query: str, api_key: str) -> list[dict]:
    needle = (query or "").strip()
    if len(needle) < 3:
        return []
    rows = _rows_from_geocode_payload(_geocode_payload(needle, api_key, None), needle)
    if rows:
        return rows
    merged = []
    seen = set()
    for region in PLACES_REGION_CODES:
        for row in _rows_from_geocode_payload(_geocode_payload(needle, api_key, region), needle):
            key = (row["primary"], row["zip"], row["city"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    return merged


def _parse_place_components(components) -> dict:
    city = state = zip_code = street_number = route = ""
    for part in components or []:
        if not isinstance(part, dict):
            continue
        types = part.get("types") or []
        long_t = (part.get("longText") or part.get("long_name") or "").strip()
        short_t = (part.get("shortText") or part.get("short_name") or "").strip()
        if "street_number" in types:
            street_number = long_t
        elif "route" in types:
            route = long_t
        elif "locality" in types:
            city = long_t
        elif "postal_town" in types and not city:
            city = long_t
        elif "administrative_area_level_2" in types and not city:
            city = long_t
        elif "sublocality_level_1" in types and not city:
            city = long_t
        elif "administrative_area_level_1" in types:
            state = short_t or long_t
        elif "country" in types and not state:
            state = short_t or long_t
        elif "postal_code" in types:
            zip_code = long_t.split("-", 1)[0]
    address = " ".join(part for part in (street_number, route) if part).strip()
    return {"address": address, "city": city, "state": state, "zip": zip_code}


def places_autocomplete(query: str, api_key: str) -> tuple[list[dict], str | None]:
    needle = (query or "").strip()
    if len(needle) < 3:
        return [], None
    payload, error = _google_json(
        PLACES_AUTOCOMPLETE_URL,
        api_key,
        payload={"input": needle, "includedRegionCodes": list(PLACES_REGION_CODES)},
        field_mask=(
            "suggestions.placePrediction.placeId,"
            "suggestions.placePrediction.text,"
            "suggestions.placePrediction.structuredFormat"
        ),
    )
    if not error and isinstance(payload, dict):
        rows = []
        for suggestion in payload.get("suggestions") or []:
            pred = (suggestion or {}).get("placePrediction") or {}
            place_id = (pred.get("placeId") or "").strip()
            if not place_id:
                continue
            fmt = pred.get("structuredFormat") or {}
            main = ((fmt.get("mainText") or {}).get("text") or "").strip()
            secondary = ((fmt.get("secondaryText") or {}).get("text") or "").strip()
            fallback = ((pred.get("text") or {}).get("text") or needle).strip()
            rows.append({
                "placeId": place_id,
                "primary": main or fallback,
                "secondary": secondary,
            })
        if rows:
            return rows, None
    geo_rows = geocode_address_suggestions(needle, api_key)
    if geo_rows:
        return geo_rows, None
    if error and _places_disabled(error):
        return [], "Address search needs a more complete street, city, or ZIP."
    return [], "Address search failed."


def _complete_place(name="", address="", city="", state="", zip_code="") -> dict:
    name = (name or "").strip()
    address = (address or "").strip()
    city = (city or "").strip()
    state = (state or "").strip()
    zip_code = (zip_code or "").strip()
    if not name:
        name = address
    if not address:
        address = name
    return {
        "name": name,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
    }


def _place_from_row(row: dict) -> dict:
    return _complete_place(
        row.get("name") or "",
        row.get("address") or "",
        row.get("city") or "",
        row.get("state") or "",
        row.get("zip") or "",
    )


def format_city_state_zip(city="", state="", zip_code="") -> str:
    city = (city or "").strip()
    state = (state or "").strip()
    zip_code = (zip_code or "").strip()
    locality = ", ".join(part for part in (city, state) if part)
    if locality and zip_code:
        return f"{locality} {zip_code}"
    return locality or zip_code


_FILE_LABEL_PREFIXES = ("DRAY-Q", "FTL-Q", "LTL-Q", "INTL-Q")
_FILE_LABEL_MODES = {
    "FTL": "FTL",
    "LTL": "LTL",
    "DRAY": "DRAY",
    "INTL": "INTL",
}


def quote_file_label(quote_number, mode="DRAY") -> str:
    prefix = _FILE_LABEL_MODES.get(str(mode or "DRAY").strip().upper(), "DRAY")
    raw = str(quote_number or "").strip()
    upper = raw.upper()
    for existing in _FILE_LABEL_PREFIXES:
        if upper.startswith(existing):
            raw = raw[len(existing):].strip()
            break
    else:
        if raw[:1].upper() == "Q":
            raw = raw[1:].strip()
    return f"{prefix}-Q{raw}"


def _record_quote_history(catalog, quote_number, form):
    try:
        record_quote(catalog, quote_number, form)
    except OSError:
        logging.exception("Could not save local quote history")


def place_details(place_id: str, api_key: str) -> tuple[dict | None, str | None]:
    pid = (place_id or "").strip()
    if pid.startswith(GEOCODE_PLACE_PREFIX):
        rows = geocode_address_suggestions(pid[len(GEOCODE_PLACE_PREFIX):], api_key)
        if not rows:
            return None, "Address not found."
        return _place_from_row(rows[0]), None
    if pid.startswith("places/"):
        pid = pid.split("/", 1)[1]
    if not pid:
        return None, "missing_place"
    payload, error = _google_json(
        PLACES_DETAILS_URL + urllib.parse.quote(pid, safe=""),
        api_key,
        field_mask="id,displayName,formattedAddress,addressComponents",
    )
    if error or not isinstance(payload, dict):
        rows = geocode_address_suggestions(pid, api_key)
        if rows:
            return _place_from_row(rows[0]), None
        return None, "Address not found."
    parsed = _parse_place_components(payload.get("addressComponents"))
    display = ((payload.get("displayName") or {}).get("text") or "").strip()
    formatted = (payload.get("formattedAddress") or "").strip()
    if not parsed["address"] and formatted:
        parsed["address"] = formatted.split(",")[0].strip()
    parsed["name"] = display or parsed["address"]
    if not parsed["zip"] or not parsed["city"] or not parsed["state"] or not parsed["address"]:
        geo_rows = geocode_address_suggestions(formatted or parsed["address"] or display, api_key)
        if geo_rows:
            geo = geo_rows[0]
            for key in ("address", "city", "state", "zip"):
                if not parsed.get(key):
                    parsed[key] = geo.get(key) or ""
            if not parsed.get("name"):
                parsed["name"] = geo.get("name") or parsed.get("address") or ""
    return _complete_place(
        parsed.get("name") or "",
        parsed.get("address") or "",
        parsed.get("city") or "",
        parsed.get("state") or "",
        parsed.get("zip") or "",
    ), None


def _route_matrix_payload(origin: str, destination: str, style: str) -> dict:
    if style == "lvr":
        return {
            "origins": [{
                "waypoint": {"address": origin},
                "routeModifiers": {"vehicleInfo": TRUCK_VEHICLE_INFO},
            }],
            "destinations": [{"waypoint": {"address": destination}}],
            "travelMode": "TRUCK",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            "units": "IMPERIAL",
        }
    return {
        "origins": [{"waypoint": {"address": origin}}],
        "destinations": [{"waypoint": {"address": destination}}],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
        "units": "IMPERIAL",
    }


def _post_route_matrix(payload: dict, api_key: str) -> tuple[dict | None, str | None]:
    request_obj = urllib.request.Request(
        ROUTES_MATRIX_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": ROUTES_FIELD_MASK,
        },
    )
    timeout = 20 if payload.get("travelMode") == "TRUCK" else 15
    try:
        with urllib.request.urlopen(request_obj, timeout=timeout) as response:
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


def _query_route_matrix(origin: str, destination: str, api_key: str) -> tuple[dict | None, str | None]:
    element, error = _post_route_matrix(_route_matrix_payload(origin, destination, "lvr"), api_key)
    if element is not None:
        return element, None
    logging.getLogger(__name__).warning(
        "Large vehicle routing failed (%s); falling back to car routing.", error
    )
    return _post_route_matrix(_route_matrix_payload(origin, destination, "drive"), api_key)


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
            return None

        miles, _error = compute_driving_distance_miles(origin_zip, destination_zip, api_key)
        return miles

    def estimate_transit_time(self, miles):
        if not miles:
            return "N/A"
        days = ac.drive_days_for_miles(miles)
        if not days:
            return "N/A"
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

# Used when lane history has fewer than 2 shipments or zero variance (σ = 0).
DEFAULT_LANE_STD_DEV = 0.5


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


def lane_sample_std_dev(historical_lane_data):
    """Sample standard deviation from historical lane transit times."""
    values = [float(x) for x in historical_lane_data]
    count = len(values)
    if count < 2:
        return None
    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / (count - 1)
    return math.sqrt(variance)


def resolve_lane_std_dev(std_dev=None, historical_lane_data=None):
    """
    Lane volatility (σ) for buffer-day math.
    Falls back to DEFAULT_LANE_STD_DEV when history is too thin or perfectly stable.
    """
    if historical_lane_data:
        computed = lane_sample_std_dev(historical_lane_data)
        if computed is None or computed <= 0:
            return DEFAULT_LANE_STD_DEV
        return computed

    lane_std = float(std_dev or 0.0)
    if lane_std <= 0:
        return DEFAULT_LANE_STD_DEV
    return lane_std


def calculate_buffer_days(desired_csl, std_dev=None, historical_lane_data=None):
    """
    Safety-stock buffer days for a single LTL shipment at the desired CSL.
    buffer_days = Z(CSL) × lane_standard_deviation
    """
    probability = float(desired_csl) / 100.0
    z_score = ac.norm_ppf(probability)
    lane_std = resolve_lane_std_dev(std_dev=std_dev, historical_lane_data=historical_lane_data)
    buffer_days = z_score * lane_std
    return {
        "buffer_days": round(buffer_days, 1),
        "z_score": round(z_score, 3),
        "lane_std_dev": round(lane_std, 2),
        "desired_csl": int(desired_csl),
    }


def calculate_transit_prediction(mean_days, std_dev, sample_size, conf=CONF_LEVEL):
    sample_count = max(2, int(sample_size))
    mean = float(mean_days)
    std = max(0.0, float(std_dev))
    degrees_of_freedom = sample_count - 1
    margin = ac.t_critical(conf, degrees_of_freedom) * std * math.sqrt(1 + (1 / sample_count))
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
        "confidence_pct": int(round(conf * 100)),
    }


def _form_dest_zip(form):
    return form.get("destination_zip") or form.get("dest_zip", "")


def _customer_ctx(source):
    include = _truthy_flag(source, "include_customer")
    name = (source.get("customer_name") or "").strip()
    email = (source.get("contact_email") or "").strip()
    if not include:
        return {"include_customer": False, "customer_name": "", "contact_email": ""}
    if name:
        try:
            remember_customer(name, email)
        except OSError:
            logging.exception("Could not save local customer catalog")
    return {"include_customer": True, "customer_name": name, "contact_email": email}


def _ltl_lane_stats_and_prediction(form, fallback_mu):
    stats = resolve_lane_stats(
        "LTL",
        form.get("origin_zip", ""),
        _form_dest_zip(form),
        fallback_mu=fallback_mu,
        fallback_sigma=_parse_form_float(form, "transit_std_dev", 0.5, minimum=0.0),
    )
    sample_n = stats["n"] if stats["n"] >= 2 else 2
    transit_prediction = calculate_transit_prediction(
        stats["mu"], stats["sigma"], sample_n, conf=CONF_LEVEL
    )
    prediction = prediction_interval_days(
        stats["mu"], stats["sigma"], stats["n"], stats["provenance"], conf=CONF_LEVEL
    )
    return stats, transit_prediction, prediction


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
    cargo_value = _optional_form_float(form, "cargo_value_per_pallet")
    rate = (float(form.get("holding_rate_pct") or form.get("annual_holding_rate") or 20.0)) / 100.0
    rows = []
    for weekly_cost in EOQ_WEEKLY_STORAGE_COLUMNS:
        hold_daily = ac.daily_holding_cost_per_pallet(
            cargo_value_per_pallet=cargo_value,
            storage_cost_weekly=weekly_cost or None,
            rate=rate,
        )
        annual_holding = hold_daily * 365 if hold_daily else 0
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


def _optional_form_float(form, key):
    raw = form.get(key) if form is not None else None
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


_pf = _optional_form_float


def _format_fsc_pct(pct) -> str:
    value = round(float(pct or 0), 1)
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"


def _format_thru_date(valid_until: str) -> str:
    raw = (valid_until or "").strip()
    for fmt, slen in (("%Y-%m-%d", 10), ("%m/%d/%Y", 10), ("%m/%d/%y", 8)):
        try:
            return datetime.strptime(raw[:slen], fmt).strftime("%m/%d/%y")
        except ValueError:
            continue
    return raw


def _parse_facilities(form) -> list[dict]:
    names = list(form.getlist("facility_name") or [])
    addresses = list(form.getlist("facility_address") or [])
    cities = list(form.getlist("facility_city") or [])
    states = list(form.getlist("facility_state") or [])
    zips = list(form.getlist("facility_zip") or [])
    if not any((n or "").strip() for n in names):
        names = [form.get("facility_name") or ""]
    if not any((a or "").strip() for a in addresses):
        addresses = [form.get("facility_address") or ""]
    if not any((c or "").strip() for c in cities):
        cities = [form.get("facility_city") or form.get("dest_city") or ""]
    if not any((s or "").strip() for s in states):
        states = [form.get("facility_state") or ""]
    if not any((z or "").strip() for z in zips):
        zips = [form.get("facility_zip") or form.get("dest_zip") or ""]
    rows = []
    count = max(len(names), len(addresses), len(cities), len(states), len(zips), 1)
    for i in range(count):
        row = {
            "name": (names[i] if i < len(names) else "").strip(),
            "address": (addresses[i] if i < len(addresses) else "").strip(),
            "city": (cities[i] if i < len(cities) else "").strip(),
            "state": (states[i] if i < len(states) else "").strip(),
            "zip": (zips[i] if i < len(zips) else "").strip(),
        }
        if any(row.values()):
            row["place_line"] = format_city_state_zip(row["city"], row["state"], row["zip"])
            rows.append(row)
    return rows


def _compute_leg_miles(zips: list[str]) -> tuple[int | None, int | None, str | None]:
    """Drive miles along zip waypoints. Returns (total, first_leg, error)."""
    cleaned = [_normalize_zip(z) for z in zips if _normalize_zip(z)]
    if len(cleaned) < 2:
        return None, None, None
    if app.config.get("TESTING"):
        return None, None, "testing"
    api_key = load_google_maps_api_key()
    if not api_key:
        return None, None, "missing_api_key"
    total = 0
    first = None
    for origin, dest in zip(cleaned, cleaned[1:]):
        miles, error = compute_driving_distance_miles(origin, dest, api_key)
        if miles is None:
            return None, first, error
        if first is None:
            first = miles
        total += miles
    return total, first, None


def _truthy_flag(data, key):
    raw = data.get(key) if data is not None else None
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("1", "true", "on", "yes")


def _quote_distance(form, origin_zip, dest_zip, maps_miles):
    """Posted miles from Calculate miles / override. Do not call Google here."""
    return ac.resolve_road_miles(
        maps_miles=maps_miles,
        manual_miles=form.get("manual_miles") if form is not None else None,
    )


def _enqueue_quote_issued(**kwargs):
    if not crm_sync_ready():
        return
    threading.Thread(
        target=on_quote_issued,
        kwargs=kwargs,
        daemon=True,
        name="crm-quote-issued",
    ).start()


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


def calculate_ltl_supply_metrics(tier_prices, distance, analysis_config, form=None):
    tier4 = tier_prices["tier4"]
    tier1 = tier_prices["tier1"]
    max_pallets = analysis_config["max_chart_pallets"]
    capacity = analysis_config["max_trailer_pallets"]
    miles = distance if distance else None

    cost_per_pallet_mile = round(tier4 / miles, 2) if miles else None
    utilization_pct = round((max_pallets / capacity) * 100) if capacity > 0 else 0
    consolidation_multiplier = round(tier1 / tier4, 2) if tier4 > 0 else None

    baseline_trips = analysis_config["carbon_baseline_trips"]
    optimized_trips = min(analysis_config["carbon_optimized_trips"], baseline_trips)
    trip_reduction = max(0, baseline_trips - optimized_trips)
    carbon_reduction_pct = round((trip_reduction / baseline_trips) * 100) if baseline_trips > 0 else 0
    weight_lb = _optional_form_float(form, "cargo_weight")
    pallet_count = analysis_config.get("requested_volume")
    co2_kg = ac.estimate_co2_kg(miles, weight_lb=weight_lb, pallet_count=pallet_count)

    return {
        "cost_per_pallet_mile": cost_per_pallet_mile,
        "utilization_pallets": max_pallets,
        "utilization_pct": utilization_pct,
        "consolidation_multiplier": consolidation_multiplier,
        "carbon_reduction_pct": carbon_reduction_pct,
        "co2_saved_kg": co2_kg,
        "co2_kg": co2_kg,
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
        "cargo_value_per_pallet": _optional_form_float(form, "cargo_value_per_pallet"),
        "transit_mean_days": _parse_form_float(form, "transit_mean_days", 3.0, minimum=0.1),
        "transit_std_dev": _parse_form_float(form, "transit_std_dev", 0.5, minimum=0.0),
        "desired_csl": _parse_form_int(form, "desired_csl", 95, minimum=90),
        "annual_holding_rate": _parse_form_float(form, "annual_holding_rate", 20.0, minimum=0.0),
        "holding_rate_pct": _optional_form_float(form, "holding_rate_pct"),
        "reclassification_penalty": _parse_form_float(form, "reclassification_penalty", 125.0, minimum=0.0),
    }


def calculate_single_ltl_analytics(payload, miles, sample_size):
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
    transit_prediction = calculate_transit_prediction(mean_transit, std_dev, sample_size)

    distance = miles if miles else None
    total_cost = payload["total_cost"]
    cost_per_pallet_mile = round(total_cost / (pallet_count * distance), 2) if distance else None
    cargo_value = payload.get("cargo_value_per_pallet")
    rate = (payload.get("holding_rate_pct") or payload.get("annual_holding_rate") or 20.0) / 100.0
    hold_daily = ac.daily_holding_cost_per_pallet(
        cargo_value_per_pallet=cargo_value,
        storage_cost_weekly=None,
        rate=rate,
    )
    if hold_daily is not None:
        pipeline_inventory_cost = round(mean_transit * hold_daily * pallet_count, 2)
    else:
        pipeline_inventory_cost = round(
            (payload["commodity_value_per_pallet"] * pallet_count) * (rate / 365) * mean_transit,
            2,
        )
    co2_kg = ac.estimate_co2_kg(distance, weight_lb=total_weight, pallet_count=pallet_count)

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
        "co2_kg": co2_kg,
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
        "incoterms_known": _truthy_flag(data, "incoterms_known"),
        "landed_known": _truthy_flag(data, "landed_known"),
        "transit_known": _truthy_flag(data, "transit_known"),
        "incoterm": (data.get("incoterm") or "").upper() if _truthy_flag(data, "incoterms_known") else "",
        "trade_role": (data.get("trade_role") or "importer").strip().lower() or "importer",
        "goods_value_fob": data.get("goods_value_fob"),
        "duty_rate_pct": data.get("duty_rate_pct"),
        "vat_rate_pct": data.get("vat_rate_pct"),
        "duty_basis": data.get("duty_basis") or "CIF",
        "marine_insurance": data.get("marine_insurance"),
        "origin_inland": data.get("origin_inland"),
        "origin_port": data.get("origin_port"),
        "ocean_freight": data.get("ocean_freight"),
        "dest_port": data.get("dest_port"),
        "dest_inland": data.get("dest_inland"),
        "transit_L": data.get("transit_L"),
        "transit_P1": data.get("transit_P1"),
        "transit_O": data.get("transit_O"),
        "transit_P2": data.get("transit_P2"),
        "transit_D": data.get("transit_D"),
        "container": data.get("container") or "40FT",
        "pallets": data.get("pallets"),
        "total_weight_kg": data.get("total_weight_kg"),
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


def _classify_intl_leg(name):
    text = (name or "").lower()
    if any(token in text for token in ("ocean", "sea", "vessel", "maritime", "water")):
        return "ocean"
    if any(token in text for token in ("customs", "discharge", "arrival", "destination", "dest ", "delivery", "dray", "last mile")):
        return "dest"
    if any(token in text for token in ("origin", "pickup", "inland", "truck")):
        return "origin"
    if "port" in text or "terminal" in text:
        return "dest" if any(token in text for token in ("dest", "discharge", "arrival")) else "origin"
    return "other"


def _intl_leg_totals(lanes):
    ocean, dest = 0.0, 0.0
    if not lanes:
        return ocean, dest
    for leg in lanes[0].get("legs", []):
        kind = _classify_intl_leg(leg.get("name"))
        cost = float(leg.get("costPerPallet") or 0)
        if kind == "ocean":
            ocean += cost
        elif kind == "dest":
            dest += cost
    return ocean, dest


def _quote_validity_days(valid_until, issue_date=None):
    """Days from issue date to the form's valid-until date."""
    issue = issue_date or datetime.now().date()
    raw = str(valid_until or "").strip()
    if not raw:
        return 15
    parsed = None
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(raw.replace("  ", " "), fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return 15
    return max(0, (parsed - issue).days)


@app.route("/")
def home():
    return render_template("mode_select.html")


@app.route("/customers")
def customers_editor():
    return render_template("customers_editor.html", customers=all_customers())


@app.route("/locations")
def locations_editor():
    return render_template("locations_editor.html", locations=all_terminals())


@app.route("/sops")
def sops_library():
    return render_template("sops_library.html", sops=SOP_FILES)


@app.route("/sops/<filename>")
def sop_file(filename):
    if filename not in allowed_sop_filenames():
        abort(404)
    folder = sops_dir()
    path = os.path.join(folder, filename)
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(folder, filename)


@app.route("/ltl")
def ltl_quote_redirect():
    return redirect(url_for("ltl_tiered_quote"))


@app.route("/ltl/tiered", methods=["GET", "POST"])
def ltl_tiered_quote():
    if request.method == "GET":
        return render_template("ltl_quote_form.html", previous_quotes=list_quotes("LTL_TIERED"))

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
    distance = _quote_distance(
        request.form, quote_generator.origin_zip, quote_generator.destination_zip, None
    )
    analysis_config = parse_ltl_analysis_config(request.form)
    if distance:
        estimated_transit_days = max(1, ac.drive_days_for_miles(distance) or 1)
        if request.form.get("transit_mean_days") in (None, ""):
            analysis_config["transit_mean_days"] = float(estimated_transit_days)

    _stats, transit_prediction, prediction = _ltl_lane_stats_and_prediction(
        request.form, analysis_config["transit_mean_days"]
    )
    analysis_config["transit_mean_days"] = _stats["mu"]
    analysis_config["transit_std_dev"] = _stats["sigma"]
    analysis_config["transit_sample_size"] = _stats["n"]

    scenarios = build_ltl_scenarios(request.form, tier_prices)
    supply_metrics = calculate_ltl_supply_metrics(tier_prices, distance, analysis_config, form=request.form)
    phantom_consolidation = detect_phantom_consolidation(analysis_config["requested_volume"], tier_prices)
    eoq_matrix = build_eoq_matrix(request.form, tier_prices, analysis_config)

    valid_until_date = datetime.now() + timedelta(days=30)
    quote = {
        "quote_number": quote_generator.quote_number,
        "origin_city": quote_generator.origin_city,
        "origin_zip": quote_generator.origin_zip,
        "destination_city": quote_generator.destination_city,
        "destination_zip": quote_generator.destination_zip,
        "distance": distance,
        "transit_time": transit_prediction["display_window"] if prediction else f"{_stats['mu']} days",
        "pricing_tiers": quote_generator.create_pricing_tiers(tier_prices),
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        "valid_until": valid_until_date.strftime("%B %d, %Y").replace(" 0", " "),
        **COMPANY_INFO,
        **_customer_ctx(request.form),
        **load_rep(),
    }

    quoted_cost = round(
        analysis_config["requested_volume"]
        * ltl_price_for_pallet_count(analysis_config["requested_volume"], tier_prices),
        2,
    )
    init_db()
    save_quote(
        quote_generator.quote_number,
        "LTL",
        request.form.get("origin_zip", ""),
        _form_dest_zip(request.form),
        quoted_transit_days=_stats["mu"],
        quoted_cost=quoted_cost,
        payload=quote,
    )
    _enqueue_quote_issued(customer_name=quote.get("customer_name", ""),
                    contact_email=quote.get("contact_email", ""),
                    quote_number=quote_generator.quote_number, mode="LTL",
                    total=quoted_cost, origin_zip=request.form.get("origin_zip", ""),
                    dest_zip=_form_dest_zip(request.form), transit_days=_stats["mu"])
    _record_quote_history("LTL_TIERED", quote_generator.quote_number, request.form)

    return render_template(
        "ltl_quote_output.html",
        quote=quote,
        quote_file_label=quote_file_label(quote_generator.quote_number, "LTL"),
        tier_prices=json.dumps(tier_prices),
        analysis_config=json.dumps(analysis_config),
        scenarios=scenarios,
        supply_metrics=supply_metrics,
        phantom_consolidation=phantom_consolidation,
        transit_prediction=transit_prediction,
        prediction=prediction,
        stats=_stats,
        eoq_matrix=eoq_matrix,
        current_year=datetime.now().year,
    )


@app.route("/ltl/single", methods=["GET", "POST"])
def ltl_single_quote():
    if request.method == "GET":
        return render_template(
            "ltl_single_quote_form.html",
            previous_quotes=list_quotes("LTL_SINGLE"),
        )

    try:
        payload = parse_single_ltl_form(request.form)
        if payload["total_cost"] <= 0:
            raise ValueError("invalid pricing")
    except (ValueError, KeyError, TypeError):
        return render_template(
            "ltl_single_quote_form.html",
            previous_quotes=list_quotes("LTL_SINGLE"),
        ), 400

    quote_generator = QuoteGenerator(
        request.form["origin_city"],
        request.form["origin_zip"],
        request.form["destination_city"],
        request.form["destination_zip"],
    )
    distance = _quote_distance(
        request.form, quote_generator.origin_zip, quote_generator.destination_zip, None
    )
    if distance and request.form.get("transit_mean_days") in (None, ""):
        payload["transit_mean_days"] = max(1.0, float(ac.drive_days_for_miles(distance) or 1))

    _stats, transit_prediction, prediction = _ltl_lane_stats_and_prediction(
        request.form, payload["transit_mean_days"]
    )
    payload["transit_mean_days"] = _stats["mu"]
    payload["transit_std_dev"] = _stats["sigma"]
    sample_n = _stats["n"] if _stats["n"] >= 2 else 2
    analytics = calculate_single_ltl_analytics(payload, distance, sample_size=sample_n)
    analytics["transit_prediction"] = transit_prediction

    valid_until_date = datetime.now() + timedelta(days=30)
    quote = {
        "quote_number": quote_generator.quote_number,
        "origin_city": quote_generator.origin_city,
        "origin_zip": quote_generator.origin_zip,
        "destination_city": quote_generator.destination_city,
        "destination_zip": quote_generator.destination_zip,
        "distance": distance,
        "distance_display": f"{int(distance)} miles" if distance else "N/A",
        "transit_time": transit_prediction["display_window"] if prediction else f"{_stats['mu']} days",
        "pallet_count": payload["pallet_count"],
        "price_per_pallet": payload["price_per_pallet"],
        "total_cost": payload["total_cost"],
        "cost_per_pallet_mile": analytics["cost_per_pallet_mile"],
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        "valid_until": valid_until_date.strftime("%B %d, %Y").replace(" 0", " "),
        **COMPANY_INFO,
        **_customer_ctx(request.form),
        **load_rep(),
    }

    init_db()
    save_quote(
        quote_generator.quote_number,
        "LTL",
        request.form.get("origin_zip", ""),
        _form_dest_zip(request.form),
        quoted_transit_days=_stats["mu"],
        quoted_cost=payload["total_cost"],
        payload=quote,
    )
    _enqueue_quote_issued(customer_name=quote.get("customer_name", ""),
                    contact_email=quote.get("contact_email", ""),
                    quote_number=quote_generator.quote_number, mode="LTL",
                    total=payload["total_cost"], origin_zip=request.form.get("origin_zip", ""),
                    dest_zip=_form_dest_zip(request.form), transit_days=_stats["mu"])
    _record_quote_history("LTL_SINGLE", quote_generator.quote_number, request.form)

    return render_template(
        "ltl_single_quote_output.html",
        quote=quote,
        quote_file_label=quote_file_label(quote_generator.quote_number, "LTL"),
        payload=payload,
        analytics=analytics,
        transit_prediction=transit_prediction,
        prediction=prediction,
        stats=_stats,
        current_year=datetime.now().year,
    )


@app.route("/ftl", methods=["GET", "POST"])
def ftl_quote():
    init_db()
    if request.method == "GET":
        return render_template("ftl_quote_form.html", previous_quotes=list_quotes("FTL"))

    form = request.form
    equipment = form.get("equipment", "V")
    if equipment not in ftl_mod.EQUIPMENT:
        equipment = "V"
    pallets, weight = _pf(form, "pallets"), _pf(form, "weight_lb")
    origin_zip = form.get("origin_zip", "")
    dest_zip = form.get("dest_zip", "")
    quote_generator = QuoteGenerator(
        form.get("origin_city", ""), origin_zip,
        form.get("dest_city", ""), dest_zip,
    )
    miles = _quote_distance(form, origin_zip, dest_zip, None)
    cost = ftl_mod.assemble_cost(
        equipment, miles, _pf(form, "linehaul_flat"), rpm=_pf(form, "rpm") or ftl_mod.DEFAULT_RPM,
        fsc_pct=_pf(form, "fsc_pct"), continuous_run=bool(form.get("continuous_run")),
        precool=bool(form.get("precool")), tarps=_pf(form, "tarps") or 0,
        detention_hours=_pf(form, "detention_hours") or 0,
        detention_rate=_pf(form, "detention_rate") or 75.0,
        misc_accessorial=_pf(form, "misc_accessorial") or 0)
    transit = ftl_mod.transit_estimate(miles, equipment,
                                       team=bool(form.get("team")), conf=CONF_LEVEL)
    stats = resolve_lane_stats("FTL", origin_zip, dest_zip,
                               fallback_mu=(transit or {}).get("mean_days", 3),
                               fallback_sigma=ftl_mod.EQUIPMENT[equipment]["sigma_days"])
    prediction = ac.prediction_interval_days(
        stats["mu"], stats["sigma"], stats["n"], stats["provenance"], conf=CONF_LEVEL)
    metrics = ftl_mod.cost_metrics(cost["total"], miles, pallets)
    co2 = ac.estimate_co2_kg(miles, weight_lb=weight, pallet_count=pallets)
    ltl_quotes = []
    if form.get("ltl_compare"):
        ltl_quotes = [{"label": form.get(f"cmp_label_{i}") or f"LTL option {i}",
                       "pallets_max": _pf(form, f"cmp_pallets_{i}"),
                       "total": _pf(form, f"cmp_total_{i}")}
                      for i in (1, 2, 3) if _pf(form, f"cmp_total_{i}")]
    xover = ftl_mod.crossover(cost["total"], "FTL (this quote)",
                              ltl_quotes, pallets) if ltl_quotes else None
    quote_number = quote_generator.quote_number
    valid_until = form.get("valid_until")
    if not valid_until:
        valid_until = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    validity_days = _quote_validity_days(valid_until)
    quote = {
        "quote_number": quote_number,
        **COMPANY_INFO,
        "title": "FTL Quote",
        "origin_city": form.get("origin_city", ""),
        "origin_zip": origin_zip,
        "destination_city": form.get("dest_city", ""),
        "destination_zip": dest_zip,
        "quote_notes": form.get("quote_notes", ""),
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        "valid_until": valid_until,
        **_customer_ctx(form),
        **load_rep(),
    }
    ctx = dict(
        quote=quote,
        miles=miles,
        pallets=pallets,
        equipment_label=ftl_mod.EQUIPMENT[equipment]["label"],
        util=ftl_mod.utilization(equipment, pallets, weight),
        cost=cost,
        transit=transit,
        stats=stats,
        prediction=prediction,
        co2=co2,
        xover=xover,
        cost_per_mile=(metrics or {}).get("cost_per_mile"),
        cost_per_position=(metrics or {}).get("cost_per_position"),
        current_year=datetime.now().year,
        validity_days=validity_days,
        quote_file_label=quote_file_label(quote_number, "FTL"),
    )
    save_quote(quote_number, "FTL", origin_zip, dest_zip,
               quoted_transit_days=(transit or {}).get("mean_days"),
               quoted_cost=cost["total"], payload={**quote, "miles": miles, "cost": cost})
    _enqueue_quote_issued(customer_name=quote.get("customer_name", ""),
                    contact_email=quote.get("contact_email", ""),
                    quote_number=quote_number, mode="FTL",
                    total=cost["total"], origin_zip=form.get("origin_zip", ""),
                    dest_zip=form.get("dest_zip", ""),
                    transit_days=(transit or {}).get("mean_days"))
    _record_quote_history("FTL", quote_number, form)
    return render_template("ftl_quote_output.html", **ctx)


def _dray_form_context(**extra):
    ctx = dict(
        ssl_lines=DRAY_SSL_LINES,
        containers=DRAY_CONTAINERS,
        overweight_lbs_threshold=int(OVERWEIGHT_LBS_THRESHOLD),
        prepull_miles_threshold=PREPULL_MILES_THRESHOLD,
        maps_api_key=load_google_maps_api_key() or "",
        previous_quotes=list_dray_history(),
        dray_rates=DRAY_RATES,
    )
    ctx.update(extra)
    return ctx


@app.route("/dray", methods=["GET", "POST"])
def dray_quote():
    init_db()
    if request.method == "GET":
        return render_template("dray_quote_form.html", **_dray_form_context())

    form = request.form
    origin_terminal = (form.get("origin_terminal") or form.get("terminal") or "").strip()
    if not origin_terminal:
        return render_template(
            "dray_quote_form.html",
            **_dray_form_context(form_error="Choose an origin terminal before generating the quote."),
        ), 400
    facilities = _parse_facilities(form)
    return_terminal = (form.get("return_terminal") or origin_terminal).strip()
    origin_match = find_terminal(origin_terminal, form.get("origin_zip", ""), form.get("origin_terminal_id", ""))
    return_match = find_terminal(return_terminal, form.get("return_zip", ""), form.get("return_terminal_id", ""))
    origin_zip = (origin_match or {}).get("zip") or form.get("origin_zip", "")
    origin_city = (origin_match or {}).get("city") or form.get("origin_city", "")
    origin_state = (origin_match or {}).get("state") or form.get("origin_state", "")
    return_zip = (return_match or {}).get("zip") or form.get("return_zip", "") or origin_zip
    return_city = (return_match or {}).get("city") or form.get("return_city", "")
    return_state = (return_match or {}).get("state") or form.get("return_state", "")
    if not return_city and return_terminal.lower() == origin_terminal.lower():
        return_city = origin_city
        return_state = return_state or origin_state
    dest_zip = (facilities[0]["zip"] if facilities else "") or form.get("dest_zip", "")
    dest_city = (facilities[0]["city"] if facilities else "") or form.get("dest_city", "")
    facility_name = (facilities[0]["name"] if facilities else "") or form.get("facility_name", "")
    origin_line = format_city_state_zip(origin_city, origin_state, origin_zip)
    return_line = format_city_state_zip(return_city, return_state, return_zip)
    quote_generator = QuoteGenerator(
        origin_city, origin_zip, dest_city, dest_zip,
    )
    quote_number = quote_generator.quote_number
    valid_until = form.get("valid_until")
    if not valid_until:
        valid_until = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    validity_days = _quote_validity_days(valid_until)
    linehaul = _pf(form, "linehaul")
    if linehaul is None:
        turn = dray_mod.turn_economics(
            _pf(form, "loaded_miles"), _pf(form, "empty_miles") or 0,
            _pf(form, "rpm_loaded") or 3.0, rpm_empty=_pf(form, "rpm_empty"),
            fsc_pct=_pf(form, "fsc_pct"), chassis_days=0, chassis_rate=0,
            linehaul_flat=_pf(form, "linehaul_flat"),
            accessorials=0)
        linehaul = round(float(turn.get("linehaul") or 0), 2)
        fsc_computed = round(float(turn.get("fsc") or 0), 2)
    else:
        linehaul = round(linehaul, 2)
        fsc_computed = None
    fsc_mode = (form.get("fsc_mode") or "amount").strip().lower()
    fsc_value = _pf(form, "fsc_value")
    if fsc_value is None:
        fsc_value = _pf(form, "fsc")
    if fsc_mode.startswith("percent"):
        fsc_pct = fsc_value or 0.0
        fsc = round(linehaul * fsc_pct / 100.0, 2)
    else:
        if fsc_value is not None:
            fsc = round(fsc_value, 2)
        else:
            fsc = fsc_computed or 0.0
        fsc_pct = (100.0 * fsc / linehaul) if linehaul else 0.0
    fsc_line = f"FSC ({_format_fsc_pct(fsc_pct)}% thru {_format_thru_date(valid_until)})"
    direction = form.get("direction", "import")
    container = form.get("container") or DRAY_CONTAINERS[2]
    ssl_line = form.get("ssl") or "No Info"
    reefer_on = _truthy_flag(form, "reefer")
    hazmat_on = _truthy_flag(form, "hazmat")
    triaxle_on = _truthy_flag(form, "triaxle")
    layover_on = _truthy_flag(form, "layover")
    stop_off_on = _truthy_flag(form, "stop_off")
    prepull_on = _truthy_flag(form, "prepull")
    residential_on = _truthy_flag(form, "residential")
    is_overweight = _truthy_flag(form, "overweight")
    load_weight_lbs = _pf(form, "load_weight_lbs")
    try:
        chassis_split_count = int(float(form.get("chassis_split") or 0))
    except (TypeError, ValueError):
        chassis_split_count = 0
    chassis_split_count = max(0, min(2, chassis_split_count))
    chassis_days = max(int(_pf(form, "chassis_days") or CHASSIS_MIN_DAYS), CHASSIS_MIN_DAYS)
    chassis_rate = TRIAXLE_DAY_RATE if (is_overweight or triaxle_on) else CHASSIS_DAY_RATE
    chassis_rental = round(chassis_rate * chassis_days, 2)
    chassis_split = round(CHASSIS_SPLIT_FEE * chassis_split_count, 2)
    chassis_subtotal = round(chassis_rental + chassis_split, 2)
    tolls = _pf(form, "tolls") or 0
    extra_acc = _pf(form, "accessorials") or 0
    acc_lines = []
    if tolls:
        acc_lines.append({"label": "Tolls", "amount": round(tolls, 2)})
    if reefer_on:
        acc_lines.append({"label": "Reefer", "amount": REEFER_FEE})
    if is_overweight:
        acc_lines.append({"label": "OW", "amount": OW_FEE})
    if hazmat_on:
        acc_lines.append({"label": "Hazmat", "amount": HAZMAT_FEE})
    if layover_on:
        acc_lines.append({"label": "Layover", "amount": LAYOVER_FEE})
    if stop_off_on:
        acc_lines.append({"label": "Stop-off", "amount": STOP_OFF_FEE})
    if prepull_on:
        acc_lines.append({"label": "Pre-Pull", "amount": PREPULL_FEE})
    if residential_on:
        acc_lines.append({"label": "Residential", "amount": RESIDENTIAL_FEE})
    if extra_acc:
        acc_lines.append({"label": "Other", "amount": round(extra_acc, 2)})
    acc_total = round(sum(row["amount"] for row in acc_lines), 2)
    quoted_total = round(linehaul + fsc + acc_total + chassis_subtotal, 2)
    facility_role = "Receiver" if direction == "import" else "Shipper"
    origin_label = "Full OUT" if direction == "import" else "Empty PU"
    return_label = "Empty IN" if direction == "import" else "Full IN"
    # Quote output does not display miles. Live prepull uses POST /api/dray/route_miles.
    route_miles, first_leg_miles = None, None
    quote = {
        "quote_number": quote_number,
        **COMPANY_INFO,
        "title": "Drayage Quote",
        "origin_city": origin_city,
        "origin_zip": origin_zip,
        "destination_city": dest_city,
        "destination_zip": dest_zip,
        "quote_notes": form.get("quote_notes", ""),
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        "valid_until": valid_until,
        **_customer_ctx(form),
        **load_rep(),
    }
    ctx = dict(
        quote=quote,
        direction=direction,
        container=container,
        ssl_line=ssl_line,
        reefer_on=reefer_on,
        hazmat_on=hazmat_on,
        triaxle_on=triaxle_on,
        load_weight_lbs=load_weight_lbs,
        is_overweight=is_overweight,
        origin_terminal=origin_terminal,
        return_terminal=return_terminal,
        origin_label=origin_label,
        return_label=return_label,
        origin_line=origin_line,
        return_line=return_line,
        facility_name=facility_name,
        facility_role=facility_role,
        facilities=facilities,
        route_miles=route_miles,
        first_leg_miles=first_leg_miles,
        linehaul=linehaul,
        fsc=fsc,
        fsc_line=fsc_line,
        acc_lines=acc_lines,
        acc_total=acc_total,
        chassis_split_count=chassis_split_count,
        chassis_split=chassis_split,
        chassis_days=chassis_days,
        chassis_rate=chassis_rate,
        chassis_rental=chassis_rental,
        chassis_label="Triaxle chassis" if (is_overweight or triaxle_on) else "Standard chassis",
        chassis_min_days=CHASSIS_MIN_DAYS,
        quoted_total=quoted_total,
        total_label=(
            "Total (LH+FSC+Acc+Chassis)"
            if (acc_lines or chassis_split_count)
            else "Total (LH+FSC+Chassis)"
        ),
        current_year=datetime.now().year,
        validity_days=validity_days,
        quote_file_label=quote_file_label(quote_number, "DRAY"),
    )
    save_quote(quote_number, "DRAY", origin_zip, dest_zip,
               quoted_transit_days=1,
               quoted_cost=quoted_total, payload={**quote, "quoted_total": quoted_total})
    try:
        record_dray_quote(quote_number, form)
    except OSError:
        logging.exception("Could not save local dray quote history")
    _enqueue_quote_issued(
        customer_name=quote.get("customer_name", ""),
        contact_email=quote.get("contact_email", ""),
        quote_number=quote_number,
        mode="DRAY",
        total=quoted_total,
        origin_zip=origin_zip,
        dest_zip=dest_zip,
        transit_days=1,
    )
    return render_template("dray_quote_output.html", **ctx)


@app.route("/api/terminals", methods=["GET", "POST"])
def api_terminals():
    if request.method == "GET":
        if request.args.get("all"):
            return jsonify(terminals=all_terminals())
        query = request.args.get("q") or request.args.get("query") or ""
        return jsonify(terminals=search_terminals(query))
    data = request.get_json(silent=True) or {}
    try:
        rec = add_terminal(
            data.get("name"),
            data.get("address") or "",
            data.get("city") or "",
            data.get("state") or "",
            data.get("zip") or data.get("zip_code") or "",
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True, terminal=rec)


@app.route("/api/terminals/<terminal_id>", methods=["PUT", "DELETE"])
def api_terminal_item(terminal_id):
    if request.method == "DELETE":
        if not delete_terminal(terminal_id):
            return jsonify(ok=False, error="Location not found."), 404
        return jsonify(ok=True)
    data = request.get_json(silent=True) or {}
    try:
        rec = update_terminal(
            terminal_id,
            data.get("name") or "",
            data.get("address") or "",
            data.get("city") or "",
            data.get("state") or "",
            data.get("zip") or data.get("zip_code") or "",
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    if rec is None:
        return jsonify(ok=False, error="Location not found."), 404
    return jsonify(ok=True, terminal=rec)


@app.route("/api/customers", methods=["GET", "POST"])
def api_customers():
    if request.method == "GET":
        if request.args.get("all"):
            return jsonify(customers=all_customers())
        query = request.args.get("q") or request.args.get("query") or ""
        return jsonify(customers=search_customers(query))
    data = request.get_json(silent=True) or {}
    rec = remember_customer(data.get("name") or "", data.get("email") or data.get("contact_email") or "")
    if rec is None:
        return jsonify(ok=False, error="Customer name is required."), 400
    return jsonify(ok=True, customer=rec)


@app.route("/api/customers/<customer_id>", methods=["PUT", "DELETE"])
def api_customer_item(customer_id):
    if request.method == "DELETE":
        if not delete_customer(customer_id):
            return jsonify(ok=False, error="Customer not found."), 404
        return jsonify(ok=True)
    data = request.get_json(silent=True) or {}
    try:
        rec = update_customer(
            customer_id,
            data.get("name") or "",
            data.get("email") or data.get("contact_email") or "",
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    if rec is None:
        return jsonify(ok=False, error="Customer not found."), 404
    return jsonify(ok=True, customer=rec)


@app.route("/api/dray/route_miles", methods=["POST"])
def api_dray_route_miles():
    data = request.get_json(silent=True) or {}
    origin = data.get("origin_zip") or ""
    dests = data.get("facility_zips") or []
    ret = data.get("return_zip") or origin
    if isinstance(dests, str):
        dests = [dests]
    total, first, error = _compute_leg_miles([origin] + list(dests) + [ret])
    if total is None:
        return jsonify(success=False, error=error or "distance_error")
    return jsonify(success=True, miles=total, first_leg_miles=first)


@app.route("/api/places/autocomplete")
def api_places_autocomplete():
    query = request.args.get("q") or request.args.get("query") or ""
    api_key = load_google_maps_api_key()
    if not api_key:
        return jsonify(predictions=[], error="missing_api_key")
    rows, error = places_autocomplete(query, api_key)
    return jsonify(predictions=rows, error=error)


@app.route("/api/places/details")
def api_places_details():
    place_id = request.args.get("place_id") or request.args.get("placeId") or ""
    api_key = load_google_maps_api_key()
    if not api_key:
        return jsonify(ok=False, error="missing_api_key")
    parsed, error = place_details(place_id, api_key)
    if parsed is None:
        return jsonify(ok=False, error=error or "details_error")
    return jsonify(ok=True, place=parsed)


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

    valid_until = parsed["valid_until"]
    if not valid_until:
        valid_until = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")

    incoterms_known = parsed.get("incoterms_known")
    landed_known = parsed.get("landed_known")
    transit_known = parsed.get("transit_known")
    incoterm = parsed["incoterm"] if incoterms_known else ""
    trade_role = parsed["trade_role"] if parsed["trade_role"] in ("importer", "exporter") else "importer"
    terms = intl_mod.INCOTERMS.get(incoterm) if incoterms_known else None
    pallets = _optional_form_float(parsed, "pallets") or parsed["example_pallets"]
    validity_days = _quote_validity_days(valid_until)

    wf_steps, wf_reason, wf_totals = None, None, None
    if landed_known:
        amounts = {
            "goods_value_fob": _optional_form_float(parsed, "goods_value_fob"),
            "duty_rate_pct": _optional_form_float(parsed, "duty_rate_pct") or 0,
            "vat_rate_pct": _optional_form_float(parsed, "vat_rate_pct") or 0,
            "marine_insurance": _optional_form_float(parsed, "marine_insurance"),
            "origin_inland": _optional_form_float(parsed, "origin_inland"),
            "origin_port": _optional_form_float(parsed, "origin_port"),
            "ocean_freight": _optional_form_float(parsed, "ocean_freight"),
            "dest_port": _optional_form_float(parsed, "dest_port"),
            "dest_inland": _optional_form_float(parsed, "dest_inland"),
        }
        wf_steps, wf_extra = intl_mod.role_waterfall(
            incoterm if incoterms_known else None,
            trade_role,
            amounts,
            duty_basis=parsed.get("duty_basis") or "CIF",
        )
        if wf_steps is None:
            wf_reason = wf_extra
            wf_totals = None
        else:
            wf_totals = wf_extra

    transit = None
    if transit_known:
        overrides = {}
        for code in ("L", "P1", "O", "P2", "D"):
            days = _optional_form_float(parsed, f"transit_{code}")
            if days is not None:
                overrides[code] = days
        if overrides:
            transit = intl_mod.leg_transit_plan(overrides=overrides, include_codes=list(overrides))

    container_stats = intl_mod.container_utilization(
        parsed.get("container") or "40FT",
        pallets,
        _optional_form_float(parsed, "total_weight_kg"),
    )

    quote = {
        "quote_number": qg.quote_number,
        **COMPANY_INFO,
        "title": parsed["quote_name"],
        "origin_text": parsed["origin_text"],
        "destination_text": parsed["destination_text"],
        "quote_notes": parsed["quote_notes"],
        "example_pallets": parsed["example_pallets"],
        "valid_until": valid_until,
        "transit_time_display": transit_time_display,
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        **_customer_ctx(data),
        **load_rep(),
    }

    example_n = parsed["example_pallets"] if parsed["example_pallets"] else 1
    quoted_cost = (
        wf_totals["landed_total"]
        if wf_totals
        else round(max_total_per_pallet * example_n, 2)
    )
    if not parsed["preview"]:
        init_db()
        save_quote(
            qg.quote_number,
            "INTL",
            parsed["origin_text"],
            parsed["destination_text"],
            quoted_transit_days=transit["mean_days"] if transit else None,
            quoted_cost=quoted_cost,
            payload={
                **quote,
                "incoterm": incoterm,
                "trade_role": trade_role,
                "waterfall": wf_steps,
                "waterfall_totals": wf_totals,
            },
        )
        _enqueue_quote_issued(customer_name=quote.get("customer_name", ""),
                        contact_email=quote.get("contact_email", ""),
                        quote_number=qg.quote_number, mode="INTL",
                        total=quoted_cost, origin_zip=parsed["origin_text"],
                        dest_zip=parsed["destination_text"],
                        transit_days=transit["mean_days"] if transit else None)

    return render_template(
        "international_quote_output.html",
        quote=quote,
        lanes=parsed["lanes"],
        example_pallets=parsed["example_pallets"],
        max_total_per_pallet=max_total_per_pallet,
        transit_time_display=transit_time_display,
        current_year=datetime.now().year,
        incoterm=incoterm,
        terms=terms,
        trade_role=trade_role,
        show_incoterms=bool(incoterms_known and terms),
        waterfall=wf_steps,
        waterfall_reason=wf_reason,
        waterfall_totals=wf_totals,
        transit=transit,
        container_stats=container_stats,
        pallets=pallets,
        validity_days=validity_days,
        quote_file_label=quote_file_label(qg.quote_number, "INTL"),
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
