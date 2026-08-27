import logging

import requests

import crm_bridge
from crm_bridge import crm_sync_ready, on_quote_issued
from twenty_client import amount_micros


def setup_function():
    crm_bridge._offline_until = 0.0


def test_amount_micros():
    assert amount_micros(12.34) == 12340000
    assert amount_micros("100") == 100000000
    assert amount_micros(None) is None
    assert amount_micros("") is None


def test_on_quote_issued_noop_without_api_key(monkeypatch):
    monkeypatch.setattr(crm_bridge, "load_config", lambda: {"crm": {"api_key": ""}})
    assert on_quote_issued(
        "Acme", "a@acme.com", "Q-1", "LTL", 100, "33178", "32524", 3
    ) is None
    assert crm_sync_ready() is False


def test_on_quote_issued_quiet_when_crm_offline(monkeypatch, caplog):
    monkeypatch.setattr(crm_bridge, "load_config", lambda: {
        "crm": {"base_url": "http://localhost:3000", "api_key": "test-key"},
    })

    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(crm_bridge.requests, "post", boom)
    monkeypatch.setattr("twenty_client.requests.post", boom)

    with caplog.at_level(logging.WARNING, logger="crm_bridge"):
        assert on_quote_issued(
            "Acme", "a@acme.com", 1, "FTL", 100, "82001", "80202", 2
        ) is None
    assert "CRM is not running at http://localhost:3000" in caplog.text
    assert "Traceback" not in caplog.text
    assert crm_sync_ready() is False

    caplog.clear()
    assert on_quote_issued(
        "Acme", "a@acme.com", 2, "FTL", 100, "82001", "80202", 2
    ) is None
    assert caplog.text == ""
