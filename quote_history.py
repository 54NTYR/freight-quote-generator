"""Local-only previous quotes, split by mode catalog. Never ship these files."""
import json
import os
from datetime import datetime

from paths import data_path

MAX_ROWS = 80

CATALOGS = {
    "DRAY": {
        "filename": "dray_quote_history.json",
        "prefix": "DRAY",
        "multi_keys": {
            "facility_name",
            "facility_address",
            "facility_city",
            "facility_state",
            "facility_zip",
        },
    },
    "FTL": {
        "filename": "ftl_quote_history.json",
        "prefix": "FTL",
        "multi_keys": set(),
    },
    "LTL_TIERED": {
        "filename": "ltl_tiered_quote_history.json",
        "prefix": "LTL",
        "multi_keys": set(),
    },
    "LTL_SINGLE": {
        "filename": "ltl_single_quote_history.json",
        "prefix": "LTL",
        "multi_keys": set(),
    },
}

MULTI_KEYS = CATALOGS["DRAY"]["multi_keys"]


def _spec(catalog: str) -> dict:
    try:
        return CATALOGS[catalog]
    except KeyError as exc:
        raise KeyError(f"Unknown quote history catalog: {catalog}") from exc


def _path(catalog: str) -> str:
    return data_path(_spec(catalog)["filename"])


def _read(catalog: str) -> list[dict]:
    path = _path(catalog)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def snapshot_form(form, catalog="DRAY") -> dict:
    multi_keys = _spec(catalog)["multi_keys"] if catalog in CATALOGS else MULTI_KEYS
    raw = form.to_dict(flat=False) if form is not None else {}
    out = {}
    for key, values in raw.items():
        if not isinstance(values, list):
            out[key] = values
            continue
        if key in multi_keys or len(values) > 1:
            out[key] = values
        else:
            out[key] = values[0] if values else ""
    return out


def list_quotes(catalog: str) -> list[dict]:
    prefix = _spec(catalog)["prefix"]
    rows = []
    for row in _read(catalog):
        number = row.get("quote_number")
        if number in (None, ""):
            continue
        rows.append({
            "quote_number": number,
            "label": f"{prefix}-Q{number}",
            "fields": row.get("fields") or {},
            "saved_at": row.get("saved_at") or "",
        })
    return rows


def record_quote(catalog: str, quote_number, form) -> None:
    _spec(catalog)
    number = quote_number
    rows = [row for row in _read(catalog) if str(row.get("quote_number")) != str(number)]
    rows.insert(0, {
        "quote_number": number,
        "fields": snapshot_form(form, catalog),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    })
    with open(_path(catalog), "w", encoding="utf-8") as handle:
        json.dump(rows[:MAX_ROWS], handle, indent=2)
