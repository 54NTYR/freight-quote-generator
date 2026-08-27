import json
from unittest.mock import patch

from werkzeug.datastructures import ImmutableMultiDict

import app as appmod
import dray_history
import quote_history
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
    monkeypatch.setattr(quote_history, "data_path", lambda name: str(tmp_path / name))
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
    assert rows[0]["label"] == "DRAY-Q77"
    assert rows[0]["fields"]["facility_name"] == ["Acme DC", "Second Yard"]
    assert rows[0]["fields"]["prepull"] == "on"


def test_quote_history_is_mode_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(quote_history, "data_path", lambda name: str(tmp_path / name))
    quote_history.record_quote("FTL", 1, ImmutableMultiDict([("origin_city", "Cheyenne")]))
    quote_history.record_quote("LTL_TIERED", 1, ImmutableMultiDict([("origin_city", "Medley")]))
    quote_history.record_quote("LTL_SINGLE", 1, ImmutableMultiDict([("origin_city", "Dallas")]))
    quote_history.record_quote("DRAY", 1, ImmutableMultiDict([("origin_city", "Newark")]))

    ftl_rows = quote_history.list_quotes("FTL")
    assert len(ftl_rows) == 1
    assert ftl_rows[0]["label"] == "FTL-Q1"
    assert ftl_rows[0]["fields"]["origin_city"] == "Cheyenne"
    assert all(row["label"].startswith("FTL-Q") for row in ftl_rows)

    tiered_rows = quote_history.list_quotes("LTL_TIERED")
    assert len(tiered_rows) == 1
    assert tiered_rows[0]["label"] == "LTL-Q1"
    origins = [row["fields"].get("origin_city") for row in tiered_rows]
    assert "Medley" in origins
    assert "Dallas" not in origins
    assert "Cheyenne" not in origins
    assert "Newark" not in origins

    single_rows = quote_history.list_quotes("LTL_SINGLE")
    assert single_rows[0]["fields"]["origin_city"] == "Dallas"
    dray_rows = quote_history.list_quotes("DRAY")
    assert dray_rows[0]["label"] == "DRAY-Q1"
    assert dray_rows[0]["fields"]["origin_city"] == "Newark"


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


def test_places_autocomplete_includes_puerto_rico_and_colombia(monkeypatch):
    captured = {}

    def fake_google(url, api_key, payload=None, **kwargs):
        captured["payload"] = payload
        return {"suggestions": []}, None

    monkeypatch.setattr(appmod, "_google_json", fake_google)
    monkeypatch.setattr(appmod, "geocode_address_suggestions", lambda *args, **kwargs: [])
    rows, error = appmod.places_autocomplete("San Juan", "key")
    assert rows == []
    assert error == "Address search failed."
    assert captured["payload"]["includedRegionCodes"] == ["us", "pr", "co"]


def test_parse_place_components_puerto_rico_and_colombia():
    pr = appmod._parse_place_components([
        {"longText": "100", "types": ["street_number"]},
        {"longText": "Avenida Ashford", "types": ["route"]},
        {"longText": "San Juan", "types": ["locality"]},
        {"shortText": "PR", "longText": "Puerto Rico", "types": ["administrative_area_level_1"]},
        {"longText": "00907", "types": ["postal_code"]},
    ])
    assert pr["city"] == "San Juan"
    assert pr["state"] == "PR"
    assert pr["zip"] == "00907"
    assert pr["address"] == "100 Avenida Ashford"

    co = appmod._parse_place_components([
        {"longText": "Cra. 7", "types": ["route"]},
        {"longText": "Bogota", "types": ["administrative_area_level_2"]},
        {"shortText": "Cundinamarca", "longText": "Cundinamarca", "types": ["administrative_area_level_1"]},
        {"shortText": "CO", "longText": "Colombia", "types": ["country"]},
        {"longText": "110111", "types": ["postal_code"]},
    ])
    assert co["city"] == "Bogota"
    assert co["state"] == "Cundinamarca"
    assert co["zip"] == "110111"


def test_geocode_fallback_does_not_force_us_region(monkeypatch):
    captured = []
    geo = {
        "results": [{
            "formattedAddress": "Cra. 7, Bogota, Cundinamarca, Colombia",
            "addressComponents": [
                {"longText": "Cra. 7", "types": ["route"]},
                {"longText": "Bogota", "types": ["administrative_area_level_2"]},
                {"shortText": "Cundinamarca", "types": ["administrative_area_level_1"]},
                {"longText": "110111", "types": ["postal_code"]},
            ],
        }]
    }

    def fake_google(url, *args, **kwargs):
        captured.append(url)
        return geo, None

    monkeypatch.setattr(appmod, "_google_json", fake_google)
    rows = appmod.geocode_address_suggestions("Cra. 7 Bogota", "key")
    assert rows[0]["city"] == "Bogota"
    assert rows[0]["zip"] == "110111"
    assert "address.regionCode=US" not in captured[0]


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


def test_add_terminal_writes_local_overlay(tmp_path, monkeypatch):
    bundled = tmp_path / "terminals.json"
    bundled.write_text('{"terminals": []}', encoding="utf-8")
    monkeypatch.setattr(terminals, "resource_dir", lambda: str(tmp_path))
    monkeypatch.setattr(terminals, "data_path", lambda name: str(tmp_path / name))
    rec = terminals.add_terminal("Maher Terminal", "1210 Corbin St", "Elizabeth", "NJ", "07201")
    local = json.loads((tmp_path / "terminals.local.json").read_text(encoding="utf-8"))
    assert local["terminals"][0]["id"] == rec["id"]
    assert '"Maher Terminal"' not in bundled.read_text(encoding="utf-8")


def test_update_and_delete_bundled_terminal_uses_overlay(tmp_path, monkeypatch):
    bundled = tmp_path / "terminals.json"
    bundled.write_text(json.dumps({"terminals": [{
        "id": "abc123",
        "name": "Maher Terminal",
        "address": "1210 Corbin St",
        "city": "Elizabeth",
        "state": "NJ",
        "zip": "07201",
    }]}), encoding="utf-8")
    monkeypatch.setattr(terminals, "resource_dir", lambda: str(tmp_path))
    monkeypatch.setattr(terminals, "data_path", lambda name: str(tmp_path / name))
    updated = terminals.update_terminal("abc123", "Maher", "1210 Corbin St", "Elizabeth", "NJ", "07201")
    assert updated["name"] == "Maher"
    assert terminals.find_terminal(terminal_id="abc123")["name"] == "Maher"
    assert terminals.delete_terminal("abc123") is True
    assert terminals.find_terminal(terminal_id="abc123") is None
    overlay = json.loads((tmp_path / "terminals.local.json").read_text(encoding="utf-8"))
    assert overlay["terminals"][0]["deleted"] is True


def test_api_terminal_update_delete(tmp_path, monkeypatch):
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
        rec = created.get_json()["terminal"]
        saved = client.put(f"/api/terminals/{rec['id']}", json={
            "name": "APMT Elizabeth",
            "address": "5080 McLester St",
            "city": "Elizabeth",
            "state": "NJ",
            "zip": "07201",
        })
        assert saved.get_json()["terminal"]["name"] == "APMT Elizabeth"
        deleted = client.delete(f"/api/terminals/{rec['id']}")
        assert deleted.status_code == 200
        assert client.get("/api/terminals?all=1").get_json()["terminals"] == []


def test_lvr_payload_uses_truck_vehicle_info_on_origin():
    payload = appmod._route_matrix_payload("07114, USA", "18101, USA", "lvr")
    assert payload["travelMode"] == "TRUCK"
    assert payload["routingPreference"] == "TRAFFIC_AWARE_OPTIMAL"
    info = payload["origins"][0]["routeModifiers"]["vehicleInfo"]
    assert info["totalAxleCount"] == 5
    assert "vehicleInfo" not in payload


def test_query_route_matrix_falls_back_to_drive(monkeypatch):
    calls = []

    def fake_post(payload, api_key):
        calls.append(payload["travelMode"])
        if payload["travelMode"] == "TRUCK":
            return None, "not provisioned"
        return {"distanceMeters": 1609, "condition": "ROUTE_EXISTS", "status": {}}, None

    monkeypatch.setattr(appmod, "_post_route_matrix", fake_post)
    element, error = appmod._query_route_matrix("07114, USA", "18101, USA", "key")
    assert error is None
    assert calls == ["TRUCK", "DRIVE"]
    assert element["distanceMeters"] == 1609

