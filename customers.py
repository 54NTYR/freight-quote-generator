"""Local-only customer catalog. Never ship this file."""
import json
import os
import uuid

from paths import data_path

FILENAME = "customers.json"


def _path() -> str:
    return data_path(FILENAME)


def _normalize(row: dict) -> dict:
    return {
        "id": (row.get("id") or "").strip() or uuid.uuid4().hex,
        "name": (row.get("name") or "").strip(),
        "email": (row.get("email") or row.get("contact_email") or "").strip(),
    }


def _read() -> list[dict]:
    path = _path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("customers") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if isinstance(row, dict) and (row.get("name") or "").strip():
            out.append(_normalize(row))
    return out


def _write(rows: list[dict]) -> None:
    path = _path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"customers": rows}, handle, indent=2)
        handle.write("\n")


def all_customers() -> list[dict]:
    return sorted(_read(), key=lambda row: row["name"].lower())


def search_customers(query: str, limit: int = 20) -> list[dict]:
    needle = (query or "").strip().lower()
    rows = all_customers()
    if not needle:
        return rows[:limit]
    hits = []
    for row in rows:
        blob = " ".join([row["name"], row["email"]]).lower()
        if needle in blob:
            hits.append(row)
        if len(hits) >= limit:
            break
    return hits


def remember_customer(name, email="") -> dict | None:
    rec = _normalize({"name": name, "email": email})
    if not rec["name"]:
        return None
    rows = _read()
    for row in rows:
        if row["name"].lower() == rec["name"].lower():
            if rec["email"] and rec["email"] != row["email"]:
                row["email"] = rec["email"]
                _write(rows)
            return row
    rows.append(rec)
    _write(rows)
    return rec


def update_customer(customer_id: str, name, email="") -> dict | None:
    tid = (customer_id or "").strip()
    rec = _normalize({"id": tid, "name": name, "email": email})
    if not rec["name"]:
        raise ValueError("Customer name is required.")
    if not tid:
        return None
    rows = _read()
    found = None
    for row in rows:
        if row["id"] == tid:
            found = row
        elif row["name"].lower() == rec["name"].lower():
            raise ValueError("Another customer already uses that name.")
    if found is None:
        return None
    found["name"] = rec["name"]
    found["email"] = rec["email"]
    _write(rows)
    return found


def delete_customer(customer_id: str) -> bool:
    tid = (customer_id or "").strip()
    if not tid:
        return False
    rows = _read()
    kept = [row for row in rows if row["id"] != tid]
    if len(kept) == len(rows):
        return False
    _write(kept)
    return True
