import pytest


@pytest.fixture(autouse=True)
def isolate_customer_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr("customers.data_path", lambda name: str(tmp_path / name))


@pytest.fixture(autouse=True)
def isolate_quote_history(tmp_path, monkeypatch):
    monkeypatch.setattr("quote_history.data_path", lambda name: str(tmp_path / name))
