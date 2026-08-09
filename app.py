import os
import json
import math
import googlemaps
from datetime import datetime
from flask import jsonify
from flask import Flask, render_template, request, redirect, url_for, send_file
from geopy.distance import geodesic
from paths import data_path, resource_dir

app = Flask(
    __name__,
    template_folder=os.path.join(resource_dir(), "templates"),
    static_folder=os.path.join(resource_dir(), "static"),
    static_url_path="/static",
)
app.secret_key = "jericho-freight-2024"

# ===============================
# Helper Classes & Functions
# ===============================

class QuoteGenerator:
    def __init__(self, origin_city, origin_zip, destination_city, destination_zip,
                 company_name, phone, email, website, dot_number, mc_number,
                 quote_number=None, preview=False):
        self.origin_city = origin_city
        self.origin_zip = origin_zip
        self.destination_city = destination_city
        self.destination_zip = destination_zip
        self.company_name = company_name
        self.phone = phone
        self.email = email
        self.website = website
        self.dot_number = dot_number
        self.mc_number = mc_number
        if quote_number is not None:
            self.quote_number = quote_number
        elif preview:
            self.quote_number = "PREVIEW"
        else:
            self.quote_number = self.get_next_quote_number()

        # Initialize Google Maps client. API key must be configured via environment.
        # Example:
        #   Windows PowerShell: $env:GOOGLE_MAPS_API_KEY = 'YOUR_API_KEY'
        #   macOS/Linux: export GOOGLE_MAPS_API_KEY='YOUR_API_KEY'
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if api_key:
            self.gmaps = googlemaps.Client(key=api_key)
        else:
            self.gmaps = None
            print("Warning: GOOGLE_MAPS_API_KEY is not set. Distance calculations will be unavailable.")

    def get_next_quote_number(self):
        counter_file = data_path("quote_counter.json")
        if not os.path.exists(counter_file):
            with open(counter_file, "w") as f:
                json.dump({"counter": 1}, f)
                f.truncate()
            return 1
        else:
            with open(counter_file, "r+") as f:
                data = json.load(f)
                data["counter"] += 1
                f.seek(0)
                json.dump(data, f)
                f.truncate()
                return data["counter"]

    def calculate_distance(self, origin_zip, destination_zip):
        try:
            if not self.gmaps:
                print("Google Maps API key not configured. Cannot calculate distance.")
                return -1
            result = self.gmaps.distance_matrix(
                origins=f"{origin_zip}, USA",
                destinations=f"{destination_zip}, USA",
                mode="driving",
                units="imperial"
            )

            if result["rows"][0]["elements"][0]["status"] == "OK":
                meters = result["rows"][0]["elements"][0]["distance"]["value"]
                miles = meters * 0.000621371  # meters → miles
                return math.ceil(miles)

            print("Google API Error:", result)
            return -1
        except Exception as e:
            print("Error in Google Distance API:", str(e))
            return -1

    def estimate_transit_time(self, miles):
        # Assume ~50 mph average speed, + buffer for stops
        hours = miles / 50
        days = math.ceil(hours / 9)  # 9 hrs driving/day allowed
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

        # Scenario 1: Steady demand - 8 pallets weekly
        pallets = 8
        price = tier_prices["tier3"]  # falls in 6-10 tier
        total_cost = pallets * price
        savings = (pallets * base_price) - total_cost
        scenarios.append({
            "title": "Scenario 1: E-Commerce Retailer (Steady Demand)",
            "desc": "Weekly demand of 8 pallets. Previously shipped in 2 orders of 4 pallets each.",
            "pallets": pallets,
            "recommended_cost": total_cost,
            "savings": savings,
            "optimal_volume": pallets
        })

        # Scenario 2: Seasonal Demand - 12 pallets bi-weekly
        pallets = 12
        price = tier_prices["tier4"]  # falls in 11-14 tier
        total_cost = pallets * price
        savings = (pallets * base_price) - total_cost
        scenarios.append({
            "title": "Scenario 2: Seasonal Business (Bi-Weekly Demand)",
            "desc": "Bi-weekly shipment of 12 pallets during seasonal peaks.",
            "pallets": pallets,
            "recommended_cost": total_cost,
            "savings": savings,
            "optimal_volume": pallets
        })

        # Scenario 3: Bulk replenishment - 14 pallets monthly
        pallets = 14
        price = tier_prices["tier4"]
        total_cost = pallets * price
        savings = (pallets * base_price) - total_cost
        scenarios.append({
            "title": "Scenario 3: Bulk Distribution Center (Monthly Replenishment)",
            "desc": "Monthly replenishment of 14 pallets to maximize truck efficiency.",
            "pallets": pallets,
            "recommended_cost": total_cost,
            "savings": savings,
            "optimal_volume": pallets
        })

        return scenarios


# ===============================
# Routes
# ===============================

@app.route("/", methods=["GET"])
def home():
    return render_template("mode_select.html")


@app.route("/ltl", methods=["GET", "POST"])
def ltl_quote():
    if request.method == "POST":
        origin_city = request.form["origin_city"]
        origin_zip = request.form["origin_zip"]
        destination_city = request.form["destination_city"]
        destination_zip = request.form["destination_zip"]

        tier_prices = {
            "tier1": float(request.form["tier1_price"]),
            "tier2": float(request.form["tier2_price"]),
            "tier3": float(request.form["tier3_price"]),
            "tier4": float(request.form["tier4_price"]),
        }

        company_info = {
            "company_name": "Jericho Freight",
            "phone": "(307) 218-8686",
            "email": "dispatch@jerichofreight.com",
            "website": "https://jerichofreight.com",
            "dot_number": "3807530",
            "mc_number": "1372791",
        }

        quote_generator = QuoteGenerator(origin_city, origin_zip, destination_city, destination_zip, **company_info)
        miles = quote_generator.calculate_distance(origin_zip, destination_zip)
        transit_time = quote_generator.estimate_transit_time(miles)
        pricing_tiers = quote_generator.create_pricing_tiers(tier_prices)
        base_price = tier_prices["tier1"]
        scenarios = quote_generator.calculate_scenarios(tier_prices, base_price)

        quote = {
            "quote_number": quote_generator.quote_number,
            "origin_city": origin_city,
            "origin_zip": origin_zip,
            "destination_city": destination_city,
            "destination_zip": destination_zip,
            "distance": miles,
            "transit_time": transit_time,
            "pricing_tiers": pricing_tiers,
            "company_name": company_info["company_name"],
            "phone": company_info["phone"],
            "email": company_info["email"],
            "website": company_info["website"],
            "dot_number": company_info["dot_number"],
            "mc_number": company_info["mc_number"],
        }

        return render_template(
            "quote_template.html",
            quote=quote,
            tier_prices=json.dumps(tier_prices),
            scenarios=scenarios,
            current_year=datetime.now().year,
        )

    return render_template("quote_form.html")


@app.route("/ftl", methods=["GET"])
def ftl_quote():
    return render_template("ftl_view.html")


@app.route("/dray", methods=["GET"])
def dray_quote():
    return render_template("dray_view.html")


@app.route('/international_preview')
def international_preview():
    sample_lanes = [
        {
            'id': 'Lane A',
            'description': 'Jerome → Oakland → Port Oakland → CTG',
            'legs': [
                {'name': 'Truck Jerome → Oakland', 'costPerPallet': 250},
                {'name': 'Transload & Dray to Port (Oakland)', 'costPerPallet': 80}
            ],
            'oceanPerPallet': 420,
            'otherFees': 45
        },
        {
            'id': 'Lane B',
            'description': 'Salt Lake City → Jerome (dray) → Ocean → CTG',
            'legs': [
                {'name': 'Dray SLC → Jerome', 'costPerPallet': 110},
                {'name': 'Return / reposition (if charged)', 'costPerPallet': 0}
            ],
            'oceanPerPallet': 480,
            'otherFees': 55
        },
        {
            'id': 'Lane C',
            'description': 'Jerome → Houston → Port Houston → CTG',
            'legs': [
                {'name': 'Truck Jerome → Houston', 'costPerPallet': 280},
                {'name': 'Transload & Dray to Port (Houston)', 'costPerPallet': 70}
            ],
            'oceanPerPallet': 400,
            'otherFees': 50
        }
    ]

    quote = {
        'quote_number': 'PREVIEW',
        'company_name': 'Jericho Freight',
        'phone': '(307) 218-8686',
        'email': 'dispatch@jerichofreight.com',
        'website': 'https://jerichofreight.com',
        'current_date': datetime.now().strftime('%B %d, %Y').replace(' 0', ' ')
    }
    for lane in sample_lanes:
        legs_total = sum((leg.get('costPerPallet', 0) or 0) for leg in lane['legs'])
        total_lane_cost = legs_total + (lane.get('otherFees', 0) or 0)
        pallets = 10 if 10 > 0 else 1
        lane['per_pallet_cost'] = total_lane_cost / pallets

    max_total_per_pallet = max((lane['per_pallet_cost'] for lane in sample_lanes), default=1)
    return render_template('quote_international.html', quote=quote, lanes=sample_lanes, example_pallets=10, max_total_per_pallet=max_total_per_pallet)


@app.route('/international', methods=['GET', 'POST'])
def international_quote():
    if request.method == 'GET':
        return render_template('international_view.html')

    # Support posted JSON in request body, or posted JSON as form field 'payload', or legacy form fields
    data = request.get_json(silent=True)
    if not data and 'payload' in request.form:
        try:
            data = json.loads(request.form.get('payload'))
        except Exception:
            data = None

    if data:
        quote_name = data.get('quote_name', 'International Freight Quote')
        origin_text = data.get('origin_text', 'Origin')
        destination_text = data.get('destination_text', 'Destination')
        try:
            example_pallets = int(data.get('example_pallets', 10))
        except (ValueError, TypeError):
            example_pallets = 10

        raw_lanes = data.get('lanes', [])
        lanes = []
        for i, raw in enumerate(raw_lanes, start=1):
            # normalize lane fields
            description = raw.get('description', '')
            other_fees = float(raw.get('otherFees', raw.get('other_fees', 0) or 0))
            details = raw.get('details', raw.get('lane_details', '')) or ''
            notes = raw.get('notes', raw.get('lane_notes', '')) or ''
            legs = []
            for leg in raw.get('legs', []):
                name = leg.get('name') or leg.get('leg_name') or ''
                try:
                    cost = float(leg.get('costPerPallet', leg.get('cost', leg.get('leg_cost', 0)) or 0))
                except (ValueError, TypeError):
                    cost = 0.0
                transit_days = None
                try:
                    transit_days = int(leg.get('transit_days')) if leg.get('transit_days') is not None else leg.get('transitDays')
                    if transit_days is None and 'transit_days' in leg:
                        transit_days = int(leg.get('transit_days'))
                except Exception:
                    transit_days = None
                if name or cost or transit_days:
                    leg_obj = {'name': name, 'costPerPallet': cost}
                    if transit_days is not None:
                        leg_obj['transit_days'] = transit_days
                    legs.append(leg_obj)

            lanes.append({
                'id': f'Lane {chr(64 + i)}',
                'description': description,
                # keep oceanPerPallet for backward compatibility but default to 0
                'oceanPerPallet': float(raw.get('oceanPerPallet', 0) or 0),
                'otherFees': other_fees,
                'details': details,
                'notes': notes,
                'legs': legs
            })

    else:
        # legacy form handling (for backward compatibility)
        quote_name = request.form.get('quote_name', 'International Freight Quote')
        origin_text = request.form.get('origin_text', 'Origin')
        destination_text = request.form.get('destination_text', 'Destination')
        try:
            example_pallets = int(request.form.get('example_pallets', 10))
        except ValueError:
            example_pallets = 10

        lanes = []
        # detect how many lane blocks present by scanning for laneN_description keys
        idx = 1
        while True:
            key = f'lane{idx}_description'
            if key not in request.form:
                break
            lane = {
                'id': f'Lane {chr(64 + idx)}',
                'description': request.form.get(f'lane{idx}_description', ''),
                'legs': [],
                'oceanPerPallet': float(request.form.get(f'lane{idx}_ocean_cost', 0) or 0),
                'otherFees': float(request.form.get(f'lane{idx}_other_fees', 0) or 0)
            }

            leg_idx = 1
            while True:
                lkey = f'lane{idx}_leg{leg_idx}_name'
                if lkey not in request.form:
                    break
                leg_name = request.form.get(lkey, '').strip()
                leg_cost_value = request.form.get(f'lane{idx}_leg{leg_idx}_cost', '0')
                try:
                    leg_cost = float(leg_cost_value or 0)
                except ValueError:
                    leg_cost = 0.0

                if leg_name:
                    lane['legs'].append({
                        'name': leg_name,
                        'costPerPallet': leg_cost
                    })
                leg_idx += 1

            lanes.append(lane)
            idx += 1

    company_info = {
        'company_name': 'Jericho Freight',
        'phone': '(307) 218-8686',
        'email': 'dispatch@jerichofreight.com',
        'website': 'https://jerichofreight.com',
        'dot_number': '3807530',
        'mc_number': '1372791'
    }

    # Determine if this render is a preview (should NOT consume the quote counter)
    preview_flag = False
    if data:
        preview_flag = bool(data.get('preview', False))
    else:
        preview_flag = str(request.form.get('preview', '')).lower() in ('1', 'true', 'yes', 'on')

    qg = QuoteGenerator(origin_city='', origin_zip='', destination_city='', destination_zip='', **company_info, preview=preview_flag)

    for lane in lanes:
        legs_total = sum((leg.get('costPerPallet', 0) or 0) for leg in lane['legs'])
        total_lane_cost = legs_total + (lane.get('otherFees', 0) or 0)
        pallets = example_pallets if example_pallets and example_pallets > 0 else 1
        lane['per_pallet_cost'] = total_lane_cost / pallets

    max_total_per_pallet = max((lane['per_pallet_cost'] for lane in lanes), default=1)

    quote = {
        'quote_number': qg.quote_number,
        'company_name': qg.company_name,
        'phone': qg.phone,
        'email': qg.email,
        'website': qg.website,
        'title': quote_name,
        'origin_text': origin_text,
        'destination_text': destination_text,
        'quote_notes': (data.get('quote_notes', '') if data else request.form.get('quote_notes', '')),
        'example_pallets': example_pallets,
        'valid_until': (data.get('valid_until') if data else request.form.get('valid_until')),
        'current_date': datetime.now().strftime('%B %d, %Y').replace(' 0', ' ')
    }

    return render_template('quote_international.html', quote=quote, lanes=lanes, example_pallets=example_pallets, max_total_per_pallet=max_total_per_pallet)


# --- API endpoint: calculate distance (used by quote_form.js) ---
TEMPLATES_FILE = data_path("pricing_templates.json")

@app.route("/calculate_distance", methods=["POST"])
def calculate_distance_endpoint():
    data = request.get_json() or {}
    origin = data.get("origin_zip") or data.get("origin") or ""
    destination = data.get("destination_zip") or data.get("destination") or ""

    # Use a minimal QuoteGenerator instance to call calculate_distance without consuming a quote counter
    qg = QuoteGenerator(origin_city="", origin_zip=origin, destination_city="", destination_zip=destination,
                        company_name="Jericho Freight", phone="", email="", website="", dot_number="", mc_number="",
                        preview=True)
    miles = qg.calculate_distance(origin, destination)
    if miles is not None and miles >= 0:
        return jsonify(success=True, miles=miles)
    return jsonify(success=False, error="distance_error")


# --- API endpoint: save pricing template (used by quote_form.js) ---
@app.route("/save_template", methods=["POST"])
def save_template():
    template_name = request.form.get("template_name")
    try:
        tier1 = float(request.form.get("tier1_price", 0))
        tier2 = float(request.form.get("tier2_price", 0))
        tier3 = float(request.form.get("tier3_price", 0))
        tier4 = float(request.form.get("tier4_price", 0))
    except ValueError:
        return jsonify(success=False, error="invalid_price_values")

    if not template_name:
        return jsonify(success=False, error="missing_template_name")

    templates = {}
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r") as f:
                templates = json.load(f)
        except Exception:
            templates = {}

    templates[template_name] = {
        "tier1_price": tier1,
        "tier2_price": tier2,
        "tier3_price": tier3,
        "tier4_price": tier4
    }

    try:
        with open(TEMPLATES_FILE, "w") as f:
            json.dump(templates, f, indent=2)
    except Exception as e:
        return jsonify(success=False, error=str(e))

    return jsonify(success=True)



if __name__ == "__main__":
    app.run(debug=True)
