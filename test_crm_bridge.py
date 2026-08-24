from crm_bridge import on_quote_issued
from twenty_client import amount_micros


def test_amount_micros():
    assert amount_micros(12.34) == 12340000
    assert amount_micros("100") == 100000000
    assert amount_micros(None) is None
    assert amount_micros("") is None


def test_on_quote_issued_noop_without_api_key():
    assert on_quote_issued(
        "Acme", "a@acme.com", "Q-1", "LTL", 100, "33178", "32524", 3
    ) is None
