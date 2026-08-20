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

    def calculate_scenarios(self, tier_prices, base_price):
        scenarios = []
        for title, desc, pallets, tier_key in (
            ("Scenario 1: E-Commerce Retailer (Steady Demand)", "Weekly demand of 8 pallets.", 8, "tier3"),
            ("Scenario 2: Seasonal Business (Bi-Weekly Demand)", "Bi-weekly shipment of 12 pallets.", 12, "tier4"),
            ("Scenario 3: Bulk Distribution Center (Monthly Replenishment)", "Monthly replenishment of 14 pallets.", 14, "tier4"),
        ):
            price = tier_prices[tier_key]
            total_cost = pallets * price
            scenarios.append({
                "title": title,
                "desc": desc,
                "pallets": pallets,
                "recommended_cost": total_cost,
                "savings": (pallets * base_price) - total_cost,
                "optimal_volume": pallets,
            })
        return scenarios


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
            if name or cost:
                legs.append({"name": name, "costPerPallet": cost})

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


def finalize_international_lanes(lanes, example_pallets):
    pallets = example_pallets if example_pallets > 0 else 1
    for lane in lanes:
        legs_total = sum(leg.get("costPerPallet", 0) for leg in lane["legs"])
        lane["per_pallet_cost"] = (legs_total + lane.get("otherFees", 0)) / pallets
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

    valid_until_date = datetime.now() + timedelta(days=30)
    quote = {
        "quote_number": quote_generator.quote_number,
        "origin_city": quote_generator.origin_city,
        "origin_zip": quote_generator.origin_zip,
        "destination_city": quote_generator.destination_city,
        "destination_zip": quote_generator.destination_zip,
        "distance": miles,
        "transit_time": quote_generator.estimate_transit_time(miles),
        "pricing_tiers": quote_generator.create_pricing_tiers(tier_prices),
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        "valid_until": valid_until_date.strftime("%B %d, %Y").replace(" 0", " "),
        **COMPANY_INFO,
    }

    return render_template(
        "ltl_quote_output.html",
        quote=quote,
        tier_prices=json.dumps(tier_prices),
        scenarios=quote_generator.calculate_scenarios(tier_prices, tier_prices["tier1"]),
        current_year=datetime.now().year,
    )


@app.route("/ltl/single", methods=["GET", "POST"])
def ltl_single_quote():
    if request.method == "GET":
        return render_template("ltl_single_quote_form.html")

    try:
        pallet_count = int(request.form["pallet_count"])
        if pallet_count < 1:
            raise ValueError("invalid pallet count")
    except (ValueError, KeyError, TypeError):
        return render_template("ltl_single_quote_form.html"), 400

    try:
        price_per_pallet = float(request.form["price_per_pallet"])
        if price_per_pallet < 0:
            raise ValueError("invalid price")
    except (ValueError, KeyError, TypeError):
        return render_template("ltl_single_quote_form.html"), 400

    quote_generator = QuoteGenerator(
        request.form["origin_city"],
        request.form["origin_zip"],
        request.form["destination_city"],
        request.form["destination_zip"],
    )
    miles = quote_generator.calculate_distance(quote_generator.origin_zip, quote_generator.destination_zip)
    total_cost = pallet_count * price_per_pallet
    cost_per_pallet_mile = None
    if miles > 0:
        cost_per_pallet_mile = round(price_per_pallet / miles, 2)

    valid_until_date = datetime.now() + timedelta(days=30)
    quote = {
        "quote_number": quote_generator.quote_number,
        "origin_city": quote_generator.origin_city,
        "origin_zip": quote_generator.origin_zip,
        "destination_city": quote_generator.destination_city,
        "destination_zip": quote_generator.destination_zip,
        "distance": miles if miles >= 0 else None,
        "distance_display": f"{miles} miles" if miles >= 0 else "N/A",
        "transit_time": quote_generator.estimate_transit_time(miles),
        "pallet_count": pallet_count,
        "price_per_pallet": price_per_pallet,
        "total_cost": total_cost,
        "cost_per_pallet_mile": cost_per_pallet_mile,
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
        "valid_until": valid_until_date.strftime("%B %d, %Y").replace(" 0", " "),
        **COMPANY_INFO,
    }

    return render_template(
        "ltl_single_quote_output.html",
        quote=quote,
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

    quote = {
        "quote_number": qg.quote_number,
        **COMPANY_INFO,
        "title": parsed["quote_name"],
        "origin_text": parsed["origin_text"],
        "destination_text": parsed["destination_text"],
        "quote_notes": parsed["quote_notes"],
        "example_pallets": parsed["example_pallets"],
        "valid_until": parsed["valid_until"],
        "current_date": datetime.now().strftime("%B %d, %Y").replace(" 0", " "),
    }

    return render_template(
        "international_quote_output.html",
        quote=quote,
        lanes=parsed["lanes"],
        example_pallets=parsed["example_pallets"],
        max_total_per_pallet=max_total_per_pallet,
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
