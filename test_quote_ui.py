from unittest.mock import patch

from werkzeug.datastructures import MultiDict

import app as appmod

FAKE_REP = {"rep_name": "Alex Rivera", "rep_email": "alex@jerichofreight.com"}


def _client():
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def test_rep_gate_redirects_home():
    with patch("app.rep_configured", return_value=False):
        response = _client().get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/settings/rep" in response.headers["Location"]


def test_mode_select_order_and_settings():
    with patch("app.rep_configured", return_value=True), patch("app.load_rep", return_value=FAKE_REP):
        html = _client().get("/").get_data(as_text=True)
    assert "Pick a live quote type" not in html
    assert html.index(">FTL<") < html.index(">LTL<") < html.index(">DRAY<") < html.index("International")
    assert "settings-cog" in html
    assert "Change User" in html
    assert 'aria-label="Settings"' in html


def test_forms_use_customer_optin():
    with patch("app.rep_configured", return_value=True), patch("app.load_rep", return_value=FAKE_REP):
        client = _client()
        pages = [
            client.get("/ltl/tiered").get_data(as_text=True),
            client.get("/ltl/single").get_data(as_text=True),
            client.get("/ftl").get_data(as_text=True),
            client.get("/dray").get_data(as_text=True),
            client.get("/international").get_data(as_text=True),
        ]
    for html in pages:
        assert "Include customer on quote" in html
        assert "id=\"customer_fields\"" in html
        assert "hidden" in html


def test_dray_form_fields():
    with patch("app.rep_configured", return_value=True), patch("app.load_rep", return_value=FAKE_REP):
        html = _client().get("/dray").get_data(as_text=True)
    assert "Maersk" in html
    assert "Hapag-Lloyd" in html
    assert "40&#39; ST" in html or "40' ST" in html
    assert "53&#34; DV" in html or "53&quot; DV" in html or '53" DV' in html
    assert 'name="origin_terminal"' in html
    assert 'name="load_weight_lbs"' in html
    assert 'name="chassis_split"' in html
    assert 'name="overweight"' in html
    assert 'name="layover"' in html
    assert 'name="stop_off"' in html
    assert 'name="prepull"' in html
    assert 'name="residential"' in html
    assert "Accessorials" in html
    assert "Shipment flags" not in html
    assert 'name="linehaul"' in html
    assert 'name="fsc_mode"' in html
    assert 'name="fsc_value"' in html
    assert "This load is overweight" in html
    assert "Load Previous Quote" in html
    assert "Full OUT" in html
    assert "Empty IN" in html
    assert "Origin city" not in html
    assert "Origin ZIP" not in html
    assert "consider prepull" in html
    assert 'id="add_terminal_btn"' in html
    assert 'name="facility_state"' in html
    assert 'name="facility_address"' in html
    assert 'name="facility_name"' in html
    assert 'id="drayLiveTotals"' in html
    assert 'id="live_total"' in html
    assert 'id="live_lh"' not in html
    assert 'id="prepull"' in html
    acc = html[html.index('class="accessorial-checks"'):]
    assert acc.find("Prepull") < acc.find("Reefer") < acc.find("Hazmat") < acc.find("Layover")
    assert acc.find("Layover") < acc.find("Stop-off") < acc.find("Residential") < acc.find("Overweight")
    assert acc.find("Overweight") < acc.find("Triaxle")
    assert html.find("Chassis days") < html.find("Chassis split")
    assert 'select id="reefer"' not in html
    assert "pageshow" in html


def test_dray_quote_output_layout_and_pricing():
    with patch("app.rep_configured", return_value=True), \
            patch("app.load_rep", return_value=FAKE_REP), \
            patch.object(appmod.QuoteGenerator, "_next_quote_number", return_value=4242), \
            patch("app.save_quote"), \
            patch("app.record_dray_quote"), \
            patch("app.on_quote_issued"):
        response = _client().post("/dray", data={
            "origin_zip": "07114",
            "origin_city": "Newark",
            "origin_state": "NJ",
            "dest_city": "Allentown",
            "dest_zip": "18101",
            "direction": "import",
            "container": "40' ST",
            "ssl": "Maersk",
            "origin_terminal": "Maher",
            "return_terminal": "Maher",
            "facility_name": "Acme DC",
            "facility_address": "1200 N Cedar Crest Blvd",
            "facility_city": "Allentown",
            "facility_state": "PA",
            "facility_zip": "18101",
            "linehaul": "450",
            "fsc_mode": "amount",
            "fsc_value": "90",
            "valid_until": "2026-08-31",
            "tolls": "25",
            "reefer": "yes",
            "hazmat": "no",
            "triaxle": "no",
            "chassis_days": "2",
            "include_customer": "on",
            "customer_name": "Acme Foods",
            "contact_email": "receiving@acme.com",
            "quote_notes": "",
        })
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Jericho Freight LLC" in html
    assert "2232 Dell Range Blvd" in html
    assert "Quoted By: Alex Rivera | alex@jerichofreight.com" in html
    assert "QUOTE MADE FOR" in html
    assert "Acme Foods" in html
    assert "Quote Details" in html
    assert "Pricing Details" in html
    assert "Accessorials" in html
    assert "ACCESSORIAL CHARGES THAT MAY APPLY" not in html
    assert "QUOTE ISSUED BY" not in html
    assert "Additional charges may apply" not in html
    assert "Maher" in html
    assert "Receiver" in html
    assert "Full OUT" in html
    assert "Empty IN" in html
    assert "Newark, NJ 07114" in html
    assert "Allentown, PA 18101" in html
    assert "Total (LH+FSC+Acc+Chassis)" in html
    assert "Subtotal chassis" not in html
    assert "/day ×" not in html
    assert "Standard chassis ($50/day, 2-day min)" in html
    assert "FSC (20% thru 08/31/26)" in html
    assert "jericho-freight-logo-compact.png" in html
    assert "jericho-freight-logo-blue.png" not in html
    assert html.find("quote-letterhead") < html.find("route-info") < html.find("section-details")
    assert "$450.00" in html
    assert "$90.00" in html
    assert "$25.00" in html
    assert "$150.00" in html  # reefer
    assert "$100.00" in html  # chassis 50*2
    # 450+90+25+150+100 = 815
    assert "$815.00" in html
    assert "Free-Time Countdown" not in html
    assert "Guaranteed All-In Freight Ledger" not in html


def test_dray_split_and_accessorial_pricing():
    with patch("app.rep_configured", return_value=True), \
            patch("app.load_rep", return_value=FAKE_REP), \
            patch.object(appmod.QuoteGenerator, "_next_quote_number", return_value=4244), \
            patch("app.save_quote"), \
            patch("app.record_dray_quote"), \
            patch("app.on_quote_issued"):
        html = _client().post("/dray", data={
            "origin_zip": "07114",
            "direction": "import",
            "linehaul": "500",
            "fsc": "100",
            "overweight": "yes",
            "load_weight_lbs": "45000",
            "chassis_split": "2",
            "layover": "yes",
            "stop_off": "yes",
            "prepull": "yes",
            "residential": "yes",
            "chassis_days": "2",
        }).get_data(as_text=True)
    assert "Weight" in html
    assert "45000 lbs" in html
    assert "Overweight" in html
    assert "Layover" in html and "$300.00" in html
    assert "Stop-off" in html and "$125.00" in html
    assert "Pre-Pull" in html and "$150.00" in html
    assert "Residential" in html and "$100.00" in html
    assert "Chassis Split (2)" in html
    assert "$300.00" in html  # two splits
    # OW 150 + layover 300 + stop 125 + prepull 150 + residential 100 = 825 acc
    # chassis triaxle because OW: 100*2 = 200, split 300
    # total 500+100+825+200+300 = 1925
    assert "$1,925.00" in html
    assert "Triaxle chassis ($100/day, 2-day min)" in html
    assert "FSC (20% thru" in html


def test_dray_fsc_percent_mode():
    with patch("app.rep_configured", return_value=True), \
            patch("app.load_rep", return_value=FAKE_REP), \
            patch.object(appmod.QuoteGenerator, "_next_quote_number", return_value=4245), \
            patch("app.save_quote"), \
            patch("app.record_dray_quote"), \
            patch("app.on_quote_issued"):
        html = _client().post("/dray", data={
            "origin_zip": "07114",
            "linehaul": "800",
            "fsc_mode": "percent",
            "fsc_value": "25",
            "valid_until": "2026-09-15",
        }).get_data(as_text=True)
    assert "FSC (25% thru 09/15/26)" in html
    assert "$200.00" in html


def test_customer_omitted_when_unchecked():
    with patch("app.rep_configured", return_value=True), \
            patch("app.load_rep", return_value=FAKE_REP), \
            patch.object(appmod.QuoteGenerator, "_next_quote_number", return_value=4243), \
            patch("app.save_quote"), \
            patch("app.record_dray_quote"), \
            patch("app.on_quote_issued"):
        html = _client().post("/dray", data={
            "origin_zip": "07114",
            "direction": "export",
            "container": "40' HC",
            "ssl": "No Info",
            "origin_terminal": "APMT",
            "facility_name": "Shipper Yard",
            "linehaul": "300",
            "fsc": "40",
            "customer_name": "Hidden Co",
            "contact_email": "hidden@example.com",
        }).get_data(as_text=True)
    assert "Hidden Co" not in html
    assert "QUOTE MADE FOR" not in html
    assert "Shipper" in html
    assert "Empty PU" in html
    assert "Full IN" in html
    assert "Total (LH+FSC+Chassis)" in html
    assert "Standard chassis ($50/day, 2-day min)" in html


def test_dray_multi_facility_output():
    with patch("app.rep_configured", return_value=True), \
            patch("app.load_rep", return_value=FAKE_REP), \
            patch.object(appmod.QuoteGenerator, "_next_quote_number", return_value=4246), \
            patch("app.save_quote"), \
            patch("app.record_dray_quote"), \
            patch("app.on_quote_issued"):
        html = _client().post("/dray", data=MultiDict([
            ("origin_zip", "07114"),
            ("origin_city", "Newark"),
            ("origin_state", "NJ"),
            ("direction", "import"),
            ("linehaul", "400"),
            ("fsc_mode", "amount"),
            ("fsc_value", "80"),
            ("origin_terminal", "Maher"),
            ("return_terminal", "Maher"),
            ("facility_name", "Acme DC"),
            ("facility_name", "Second Yard"),
            ("facility_address", "1200 N Cedar Crest Blvd"),
            ("facility_address", "401 N 9th St"),
            ("facility_city", "Allentown"),
            ("facility_city", "Reading"),
            ("facility_state", "PA"),
            ("facility_state", "PA"),
            ("facility_zip", "18101"),
            ("facility_zip", "19601"),
        ])).get_data(as_text=True)
    assert "Acme DC" in html
    assert "Second Yard" in html
    assert "Receiver 1" in html
    assert "Receiver 2" in html
    assert "Newark, NJ 07114" in html
    assert "Allentown, PA 18101" in html
    assert "Reading, PA 19601" in html
