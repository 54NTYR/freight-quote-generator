from unittest.mock import patch

import app as appmod
import customers


def test_remember_search_update_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(customers, "data_path", lambda name: str(tmp_path / name))
    rec = customers.remember_customer("Acme Foods", "ops@acme.test")
    assert rec["name"] == "Acme Foods"
    assert rec["email"] == "ops@acme.test"
    hits = customers.search_customers("acme")
    assert hits and hits[0]["id"] == rec["id"]
    updated = customers.update_customer(rec["id"], "Acme Foods LLC", "billing@acme.test")
    assert updated["name"] == "Acme Foods LLC"
    assert updated["email"] == "billing@acme.test"
    assert customers.delete_customer(rec["id"]) is True
    assert customers.all_customers() == []


def test_update_customer_rejects_duplicate_name(tmp_path, monkeypatch):
    monkeypatch.setattr(customers, "data_path", lambda name: str(tmp_path / name))
    first = customers.remember_customer("Acme", "a@acme.test")
    customers.remember_customer("Beta", "b@beta.test")
    try:
        customers.update_customer(first["id"], "Beta", "a@acme.test")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "already uses" in str(exc)


def test_api_customers_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(customers, "data_path", lambda name: str(tmp_path / name))
    appmod.app.config["TESTING"] = True
    with patch("app.rep_configured", return_value=True), patch("app.load_rep", return_value={}):
        client = appmod.app.test_client()
        created = client.post("/api/customers", json={"name": "Harbor Co", "email": "ops@harbor.test"})
        assert created.status_code == 200
        rec = created.get_json()["customer"]
        listed = client.get("/api/customers?q=harbor")
        names = [row["name"] for row in listed.get_json()["customers"]]
        assert "Harbor Co" in names
        saved = client.put(f"/api/customers/{rec['id']}", json={"name": "Harbor Co", "email": "ap@harbor.test"})
        assert saved.get_json()["customer"]["email"] == "ap@harbor.test"
        deleted = client.delete(f"/api/customers/{rec['id']}")
        assert deleted.status_code == 200
        assert client.get("/api/customers?all=1").get_json()["customers"] == []
