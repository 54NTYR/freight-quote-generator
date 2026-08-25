import json
from unittest.mock import patch

from werkzeug.datastructures import ImmutableMultiDict

import app as appmod
import dray_history
import terminals


def test_add_and_search_terminals(tmp_path, monkeypatch):
    bundled = tmp_path / "terminals.json"
    bundled.write_text('{"terminals": []}', encoding="utf-8")
    monkeypatch.setattr(terminals, "resource_dir", lambda: str(tmp_path))
    monkeypatch.setattr(terminals, "data_path", lambda name: str(tmp_path / name))
    rec = terminals.add_terminal("Maher Terminal", "1210 Corbin St", "Elizabeth", "NJ", "07201")
    assert rec["name"] == "Maher Terminal"
    assert rec["zip"] == "07201"
    hits = terminals.search_terminals("maher")
    assert hits and hits[0]["city"] == "Elizabeth"
    assert terminals.find_terminal("Maher Terminal", "07201")["id"] == rec["id"]
    again = terminals.add_terminal("Maher Terminal", zip_code="07201")
    assert again["id"] == rec["id"]


def test_api_terminals_roundtrip(tmp_path, monkeypatch):
    bundled = tmp_path / "terminals.json"
    bundled.write_text('{"terminals": []}', encoding="utf-8")
    monkeypatch.setattr(terminals, "resource_dir", lambda: str(tmp_path))
    monkeypatch.setattr(terminals, "data_path", lambda name: str(tmp_path / name))
    appmod.app.config["TESTING"] = True
    with patch("app.rep_configured", return_value=True), patch("app.load_rep", return_value={}):
        client = appmod.app.test_client()
        created = client.post("/api/terminals", json={
            "name": "APMT",
            "address": "5080 McLester St",
            "city": "Elizabeth",
            "state": "NJ",
            "zip": "07201",
        })
        assert created.status_code == 200
        body = created.get_json()
        assert body["ok"] is True
        listed = client.get("/api/terminals?q=apmt")
        names = [row["name"] for row in listed.get_json()["terminals"]]
        assert "APMT" in names


def test_leg_miles_sum_waypoints(monkeypatch):
    monkeypatch.setattr(appmod, "load_google_maps_api_key", lambda: "test-key")

    def fake_miles(origin, dest, api_key):
        return {"07114|18101": 80, "18101|19601": 30, "19601|07114": 90}[f"{origin}|{dest}"], None

    monkeypatch.setattr(appmod, "compute_driving_distance_miles", fake_miles)
    appmod.app.config["TESTING"] = False
    try:
        total, first, error = appmod._compute_leg_miles(["07114", "18101", "19601", "07114"])
    finally:
        appmod.app.config["TESTING"] = True
    assert error is None
    assert first == 80
    assert total == 200


def test_dray_history_keeps_multi_facilities(tmp_path, monkeypatch):
    monkeypatch.setattr(dray_history, "data_path", lambda name: str(tmp_path / name))
    form = ImmutableMultiDict([
        ("origin_terminal", "Maher"),
        ("facility_name", "Acme DC"),
        ("facility_name", "Second Yard"),
        ("facility_zip", "18101"),
        ("facility_zip", "19601"),
        ("prepull", "on"),
    ])
    dray_history.record_quote(77, form)
    rows = dray_history.list_quotes()
    assert rows[0]["label"] == "Q77"
    assert rows[0]["fields"]["facility_name"] == ["Acme DC", "Second Yard"]
    assert rows[0]["fields"]["prepull"] == "on"


def test_places_autocomplete_parses_suggestions(monkeypatch):
    payload = {
        "suggestions": [{
            "placePrediction": {
                "placeId": "ChIJ123",
                "structuredFormat": {
                    "mainText": {"text": "1010 Mead Street"},
                    "secondaryText": {"text": "Washington Court House, OH, USA"},
                },
            }
        }]
    }
    monkeypatch.setattr(appmod, "_google_json", lambda *args, **kwargs: (payload, None))
    rows, error = appmod.places_autocomplete("1010 Mead", "key")
    assert error is None
    assert rows[0]["placeId"] == "ChIJ123"
    assert rows[0]["primary"] == "1010 Mead Street"
    assert "Ohio" in rows[0]["secondary"] or "OH" in rows[0]["secondary"]


def test_places_autocomplete_falls_back_to_geocode(monkeypatch):
    geo = {
        "results": [{
            "formattedAddress": "1010 Mead St, Washington Court House, OH 43160, USA",
            "addressComponents": [
                {"longText": "1010", "types": ["street_number"]},
                {"longText": "Mead Street", "types": ["route"]},
                {"longText": "Washington Court House", "types": ["locality"]},
                {"shortText": "OH", "longText": "Ohio", "types": ["administrative_area_level_1"]},
                {"longText": "43160", "types": ["postal_code"]},
            ],
        }]
    }

    def fake_google(url, *args, **kwargs):
        if "places:autocomplete" in url:
            return None, json.dumps({
                "error": {
                    "status": "PERMISSION_DENIED",
                    "message": "Places API (New) has not been used in project",
                }
            })
        return geo, None

    monkeypatch.setattr(appmod, "_google_json", fake_google)
    rows, error = appmod.places_autocomplete("1010 Mead St Ohio", "key")
    assert error is None
    assert rows[0]["zip"] == "43160"
    assert rows[0]["state"] == "OH"
    assert rows[0]["primary"].startswith("1010")


def test_place_details_parses_components(monkeypatch):
    payload = {
        "displayName": {"text": "Acme DC"},
        "formattedAddress": "123 Main St, Allentown, PA 18101, USA",
        "addressComponents": [
            {"longText": "123", "types": ["street_number"]},
            {"longText": "Main St", "types": ["route"]},
            {"longText": "Allentown", "types": ["locality"]},
            {"shortText": "PA", "longText": "Pennsylvania", "types": ["administrative_area_level_1"]},
            {"longText": "18101", "types": ["postal_code"]},
        ],
    }
    monkeypatch.setattr(appmod, "_google_json", lambda *args, **kwargs: (payload, None))
    parsed, error = appmod.place_details("ChIJ123", "key")
    assert error is None
    assert parsed["name"] == "Acme DC"
    assert parsed["address"] == "123 Main St"
    assert parsed["city"] == "Allentown"
    assert parsed["state"] == "PA"
    assert parsed["zip"] == "18101"


def test_format_city_state_zip():
    assert appmod.format_city_state_zip("Newark", "NJ", "07114") == "Newark, NJ 07114"
    assert appmod.format_city_state_zip("Allentown", "PA", "") == "Allentown, PA"
    assert appmod.format_city_state_zip("", "", "07114") == "07114"
    assert appmod.format_city_state_zip("Newark", "", "07114") == "Newark 07114"


def test_api_places_autocomplete_endpoint():
    appmod.app.config["TESTING"] = True
    with patch("app.rep_configured", return_value=True), \
            patch("app.load_rep", return_value={}), \
            patch("app.load_google_maps_api_key", return_value="key"), \
            patch("app.places_autocomplete", return_value=([{
                "placeId": "1", "primary": "1010 Mead Street", "secondary": "Ohio"
            }], None)):
        body = appmod.app.test_client().get("/api/places/autocomplete?q=1010").get_json()
    assert body["predictions"][0]["primary"] == "1010 Mead Street"
