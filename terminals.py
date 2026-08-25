"""Shared dray terminal catalog. Bundled file is git-tracked; local overlay is not."""
import json
import os
import uuid

from paths import data_path, is_frozen, resource_dir

BUNDLED_FILENAME = "terminals.json"
LOCAL_FILENAME = "terminals.local.json"


def _bundled_path() -> str:
    return os.path.join(resource_dir(), BUNDLED_FILENAME)


def _local_path() -> str:
    return data_path(LOCAL_FILENAME)


def _read_list(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("terminals") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if isinstance(row, dict) and (row.get("name") or "").strip():
            out.append(_normalize(row))
    return out


def _normalize(row: dict) -> dict:
    return {
        "id": (row.get("id") or "").strip() or uuid.uuid4().hex,
        "name": (row.get("name") or "").strip(),
        "address": (row.get("address") or "").strip(),
        "city": (row.get("city") or "").strip(),
        "state": (row.get("state") or "").strip(),
        "zip": (row.get("zip") or "").strip(),
    }


def all_terminals() -> list[dict]:
    merged = {}
    for row in _read_list(_bundled_path()) + _read_list(_local_path()):
        key = (row["name"].lower(), row["zip"])
        merged[key] = row
    return sorted(merged.values(), key=lambda row: row["name"].lower())


def search_terminals(query: str, limit: int = 20) -> list[dict]:
    needle = (query or "").strip().lower()
    rows = all_terminals()
    if not needle:
        return rows[:limit]
    hits = []
    for row in rows:
        blob = " ".join([row["name"], row["address"], row["city"], row["state"], row["zip"]]).lower()
        if needle in blob:
            hits.append(row)
        if len(hits) >= limit:
            break
    return hits


def find_terminal(name: str = "", zip_code: str = "", terminal_id: str = "") -> dict | None:
    tid = (terminal_id or "").strip()
    name_l = (name or "").strip().lower()
    zip_l = (zip_code or "").strip()
    for row in all_terminals():
        if tid and row["id"] == tid:
            return row
        if name_l and row["name"].lower() == name_l:
            if not zip_l or row["zip"] == zip_l:
                return row
    return None


def _write_list(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"terminals": rows}, handle, indent=2)
        handle.write("\n")


def add_terminal(name, address="", city="", state="", zip_code="") -> dict:
    rec = _normalize({
        "name": name,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
    })
    if not rec["name"]:
        raise ValueError("Terminal name is required.")
    existing = find_terminal(rec["name"], rec["zip"])
    if existing:
        return existing
    target = _local_path() if is_frozen() else _bundled_path()
    rows = _read_list(target)
    rows.append(rec)
    _write_list(target, rows)
    return rec
