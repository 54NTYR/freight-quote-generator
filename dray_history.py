"""Local-only previous dray quotes. Never ship this file."""
import json
import os
from datetime import datetime

from paths import data_path

FILENAME = "dray_quote_history.json"
MAX_ROWS = 80
MULTI_KEYS = {"facility_name", "facility_address", "facility_city", "facility_state", "facility_zip"}


def _path() -> str:
    return data_path(FILENAME)


def _read() -> list[dict]:
    path = _path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def list_quotes() -> list[dict]:
    rows = []
    for row in _read():
        number = row.get("quote_number")
        if number in (None, ""):
            continue
        rows.append({
            "quote_number": number,
            "label": f"Q{number}",
            "fields": row.get("fields") or {},
            "saved_at": row.get("saved_at") or "",
        })
    return rows


def snapshot_form(form) -> dict:
    raw = form.to_dict(flat=False) if form is not None else {}
    out = {}
    for key, values in raw.items():
        if not isinstance(values, list):
            out[key] = values
            continue
        if key in MULTI_KEYS or len(values) > 1:
            out[key] = values
        else:
            out[key] = values[0] if values else ""
    return out


def record_quote(quote_number, form) -> None:
    number = quote_number
    rows = [row for row in _read() if str(row.get("quote_number")) != str(number)]
    rows.insert(0, {
        "quote_number": number,
        "fields": snapshot_form(form),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    })
    with open(_path(), "w", encoding="utf-8") as handle:
        json.dump(rows[:MAX_ROWS], handle, indent=2)
