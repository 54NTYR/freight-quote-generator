"""Shared dray terminal catalog. Bundled file is git-tracked; local overlay is not."""
import json
import os
import uuid

from paths import data_path, resource_dir

BUNDLED_FILENAME = "terminals.json"
LOCAL_FILENAME = "terminals.local.json"


def _bundled_path() -> str:
    return os.path.join(resource_dir(), BUNDLED_FILENAME)


def _local_path() -> str:
    return data_path(LOCAL_FILENAME)


def _read_json(path: str):
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("terminals") if isinstance(data, dict) else data
    return rows if isinstance(rows, list) else []


def _read_list(path: str) -> list[dict]:
    out = []
    for row in _read_json(path):
        if isinstance(row, dict) and (row.get("name") or "").strip() and not row.get("deleted"):
            out.append(_normalize(row))
    return out


def _read_local_raw() -> list[dict]:
    out = []
    for row in _read_json(_local_path()):
        if not isinstance(row, dict):
            continue
        tid = (row.get("id") or "").strip()
        if row.get("deleted"):
            if tid:
                out.append({"id": tid, "deleted": True, "name": (row.get("name") or "").strip()})
            continue
        if (row.get("name") or "").strip():
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
    merged = {row["id"]: row for row in _read_list(_bundled_path())}
    for row in _read_local_raw():
        if row.get("deleted"):
            merged.pop(row["id"], None)
            continue
        merged[row["id"]] = row
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


def _upsert_local(rec: dict) -> None:
    rows = []
    replaced = False
    for row in _read_local_raw():
        if row.get("id") == rec["id"]:
            if row.get("deleted"):
                continue
            rows.append(rec)
            replaced = True
        else:
            rows.append(row)
    if not replaced:
        rows.append(rec)
    _write_list(_local_path(), rows)


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
    _upsert_local(rec)
    return rec


def update_terminal(terminal_id: str, name, address="", city="", state="", zip_code="") -> dict | None:
    tid = (terminal_id or "").strip()
    if not tid:
        return None
    current = find_terminal(terminal_id=tid)
    if current is None:
        return None
    rec = _normalize({
        "id": tid,
        "name": name,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
    })
    rec["id"] = tid
    if not rec["name"]:
        raise ValueError("Terminal name is required.")
    other = find_terminal(rec["name"], rec["zip"])
    if other and other["id"] != tid:
        raise ValueError("Another location already uses that name and ZIP.")
    _upsert_local(rec)
    return rec


def delete_terminal(terminal_id: str) -> bool:
    tid = (terminal_id or "").strip()
    if not tid:
        return False
    current = find_terminal(terminal_id=tid)
    in_bundled = any(row["id"] == tid for row in _read_list(_bundled_path()))
    if current is None and not in_bundled:
        return False
    rows = [row for row in _read_local_raw() if row.get("id") != tid]
    if in_bundled:
        rows.append({"id": tid, "deleted": True, "name": (current or {}).get("name") or ""})
    _write_list(_local_path(), rows)
    return True
