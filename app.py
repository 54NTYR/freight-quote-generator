import json
import logging
import math
import os
from datetime import datetime

import googlemaps
from flask import Flask, jsonify, render_template, request

from config import COMPANY_INFO, ensure_config_file, load_google_maps_api_key
from paths import data_path, resource_dir

ensure_config_file()
load_google_maps_api_key()

app = Flask(
    __name__,
    template_folder=os.path.join(resource_dir(), "templates"),
    static_folder=os.path.join(resource_dir(), "static"),
    static_url_path="/static",
)


def get_maps_client():
    api_key = load_google_maps_api_key()
    return googlemaps.Client(key=api_key) if api_key else None


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
        self.gmaps = get_maps_client()

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
        if not self.gmaps:
            return -1

        try:
            result = self.gmaps.distance_matrix(
                origins=f"{origin_zip}, USA",
                destinations=f"{destination_zip}, USA",
                mode="driving",
                units="imperial",
            )
            element = result["rows"][0]["elements"][0]
            if element["status"] == "OK":
                meters = element["distance"]["value"]
                return math.ceil(meters * 0.000621371)
        except Exception as exc:
            logging.getLogger(__name__).warning("Distance lookup failed: %s", exc)

        return -1

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


@app.route("/ltl", methods=["GET", "POST"])
def ltl_quote():
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

    quote = {
        "quote_number": quote_generator.quote_number,
        "origin_city": quote_generator.origin_city,
        "origin_zip": quote_generator.origin_zip,
        "destination_city": quote_generator.destination_city,
        "destination_zip": quote_generator.destination_zip,
        "distance": miles,
        "transit_time": quote_generator.estimate_transit_time(miles),
        "pricing_tiers": quote_generator.create_pricing_tiers(tier_prices),
        **COMPANY_INFO,
    }

    return render_template(
        "ltl_quote_form.html",
        quote=quote,
        tier_prices=json.dumps(tier_prices),
        scenarios=quote_generator.calculate_scenarios(tier_prices, tier_prices["tier1"]),
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
    )


@app.route("/calculate_distance", methods=["POST"])
def calculate_distance_endpoint():
    data = request.get_json() or {}
    origin = data.get("origin_zip") or data.get("origin") or ""
    destination = data.get("destination_zip") or data.get("destination") or ""

    if not load_google_maps_api_key():
        return jsonify(success=False, error="missing_api_key")

    miles = QuoteGenerator("", origin, "", destination, preview=True).calculate_distance(origin, destination)
    if miles >= 0:
        return jsonify(success=True, miles=miles)
    return jsonify(success=False, error="distance_error")


if __name__ == "__main__":
    app.run(debug=True)
