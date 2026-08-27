"""Compatibility wrapper for dray quote history."""
from quote_history import (  # noqa: F401
    MULTI_KEYS,
    data_path,
    snapshot_form,
)
from quote_history import list_quotes as _list_quotes
from quote_history import record_quote as _record_quote


def list_quotes():
    return _list_quotes("DRAY")


def record_quote(quote_number, form) -> None:
    _record_quote("DRAY", quote_number, form)
