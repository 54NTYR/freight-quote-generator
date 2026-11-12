"""SQLite masters and saved plans for Load Planning. Additive tables only."""
from __future__ import annotations

import json
import os
from paths import data_path
from storage import get_conn

SCHEMA = """
CREATE TABLE IF NOT EXISTS lp_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    length_in REAL NOT NULL,
    width_in REAL NOT NULL,
    height_in REAL NOT NULL,
    weight_lb REAL NOT NULL,
    turn_on_floor INTEGER NOT NULL DEFAULT 1,
    stackable INTEGER NOT NULL DEFAULT 1,
    max_stack INTEGER,
    on_floor_only INTEGER NOT NULL DEFAULT 0,
    on_top_only INTEGER NOT NULL DEFAULT 0,
    supported_weight_lb REAL,
    stack_index INTEGER,
    notes TEXT,
    color TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS lp_containers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    type TEXT NOT NULL,
    length_in REAL NOT NULL,
    width_in REAL NOT NULL,
    height_in REAL NOT NULL,
    max_payload_lb REAL NOT NULL,
    load_direction TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS lp_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_number INTEGER UNIQUE,
    customer_name TEXT,
    contact_email TEXT,
    include_customer INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Interior sizes from published equipment sheets, rounded to 0.1 in.
# 53 ft and 48 ft dry vans: inside length and 110 in inside height, 98.5 in usable width.
# 20 ft standard and 40 ft high cube: ISO interior millimeters converted to inches.
SEED_CONTAINERS = (
    ("53 ft dry van", "truck", 630, 98.5, 110, 45000, "back_to_front"),
    ("48 ft dry van", "truck", 568, 98.5, 110, 44000, "back_to_front"),
    ("40 ft high cube", "ocean", 473.7, 92.6, 106.2, 58000, "back_to_front"),
    ("20 ft standard", "ocean", 232.2, 92.6, 94.2, 48000, "back_to_front"),
    ("48 x 40 pallet", "pallet", 48, 40, 60, 2500, "bottom_to_top"),
)
PREVIOUS_SEED_SIZES = {
    "53 ft dry van": (630, 98, 110),
    "48 ft dry van": (570, 98, 108),
    "40 ft high cube": (472, 92, 106),
    "20 ft standard": (232, 92, 93),
}
PRODUCT_COLUMNS = (
    ("shape", "TEXT"),
    ("orient_mode", "TEXT"),
    ("back_depth", "REAL"),
    ("seat_height", "REAL"),
    ("stem_width", "REAL"),
    ("bar_depth", "REAL"),
    ("allowed_orientations", "TEXT"),
)


def _add_columns(conn, table: str, columns: tuple[tuple[str, str], ...]) -> None:
    have = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, kind in columns:
        if name not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")


def ensure_schema() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _add_columns(conn, "lp_products", PRODUCT_COLUMNS)
        count = conn.execute("SELECT COUNT(*) AS n FROM lp_containers").fetchone()["n"]
        if not count:
            conn.executemany(
                """INSERT INTO lp_containers
                   (label, type, length_in, width_in, height_in, max_payload_lb, load_direction)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                SEED_CONTAINERS,
            )
            return
        current = {row[0]: row[1:] for row in SEED_CONTAINERS}
        for label, old in PREVIOUS_SEED_SIZES.items():
            new = current[label]
            conn.execute(
                """UPDATE lp_containers
                   SET length_in = ?, width_in = ?, height_in = ?
                   WHERE label = ? AND length_in = ? AND width_in = ? AND height_in = ?""",
                (new[1], new[2], new[3], label, old[0], old[1], old[2]),
            )


def next_plan_number() -> int:
    """Local PLAN sequence. Does not call the shared Google quote counter."""
    path = data_path("plan_counter.json")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"counter": 1}, handle)
        return 1
    with open(path, "r+", encoding="utf-8") as handle:
        data = json.load(handle)
        data["counter"] = int(data.get("counter") or 0) + 1
        handle.seek(0)
        json.dump(data, handle)
        handle.truncate()
        return int(data["counter"])


def _product_row(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "length_in": row["length_in"],
        "width_in": row["width_in"],
        "height_in": row["height_in"],
        "weight_lb": row["weight_lb"],
        "turn_on_floor": bool(row["turn_on_floor"]),
        "stackable": bool(row["stackable"]),
        "max_stack": row["max_stack"],
        "on_floor_only": bool(row["on_floor_only"]),
        "on_top_only": bool(row["on_top_only"]),
        "supported_weight_lb": row["supported_weight_lb"],
        "stack_index": row["stack_index"],
        "notes": row["notes"] or "",
        "color": row["color"] or "",
        "shape": row["shape"] or "box",
        "orient_mode": row["orient_mode"] or "",
        "back_depth": row["back_depth"],
        "seat_height": row["seat_height"],
        "stem_width": row["stem_width"],
        "bar_depth": row["bar_depth"],
        "allowed_orientations": [
            part for part in str(row["allowed_orientations"] or "").split(",") if part
        ],
    }


def _container_row(row) -> dict:
    return {
        "id": row["id"],
        "label": row["label"],
        "type": row["type"],
        "length_in": row["length_in"],
        "width_in": row["width_in"],
        "height_in": row["height_in"],
        "max_payload_lb": row["max_payload_lb"],
        "load_direction": row["load_direction"],
        "notes": row["notes"] or "",
    }


def list_products() -> list[dict]:
    ensure_schema()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM lp_products ORDER BY name COLLATE NOCASE, id").fetchall()
    return [_product_row(row) for row in rows]


def save_product(fields: dict) -> dict:
    ensure_schema()
    with get_conn() as conn:
        allowed = ",".join(fields.get("allowed_orientations") or [])
        cur = conn.execute(
            """INSERT INTO lp_products
               (name, length_in, width_in, height_in, weight_lb, turn_on_floor, stackable,
                max_stack, on_floor_only, on_top_only, supported_weight_lb, stack_index, notes, color,
                shape, orient_mode, back_depth, seat_height, stem_width, bar_depth, allowed_orientations)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fields["name"], fields["length_in"], fields["width_in"], fields["height_in"],
                fields["weight_lb"], int(fields["turn_on_floor"]), int(fields["stackable"]),
                fields["max_stack"], int(fields["on_floor_only"]), int(fields["on_top_only"]),
                fields["supported_weight_lb"], fields["stack_index"], fields["notes"], fields["color"],
                fields.get("shape") or "box", fields.get("orient_mode") or "",
                fields.get("back_depth"), fields.get("seat_height"),
                fields.get("stem_width"), fields.get("bar_depth"), allowed,
            ),
        )
        row = conn.execute("SELECT * FROM lp_products WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _product_row(row)


def delete_product(product_id: int) -> bool:
    ensure_schema()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM lp_products WHERE id = ?", (product_id,))
        return cur.rowcount > 0


def list_containers() -> list[dict]:
    ensure_schema()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM lp_containers ORDER BY label COLLATE NOCASE, id"
        ).fetchall()
    return [_container_row(row) for row in rows]


def save_container(fields: dict) -> dict:
    ensure_schema()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO lp_containers
               (label, type, length_in, width_in, height_in, max_payload_lb, load_direction, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fields["label"], fields["type"], fields["length_in"], fields["width_in"],
                fields["height_in"], fields["max_payload_lb"], fields["load_direction"],
                fields.get("notes") or "",
            ),
        )
        row = conn.execute("SELECT * FROM lp_containers WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _container_row(row)


def delete_container(container_id: int) -> bool:
    ensure_schema()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM lp_containers WHERE id = ?", (container_id,))
        return cur.rowcount > 0


def save_plan(plan_number: int, plan: dict, result: dict, issued_on: str) -> dict:
    ensure_schema()
    include = 1 if plan["include_customer"] else 0
    payload = {
        "plan_number": plan_number,
        "plan_label": f"PLAN-Q{plan_number}",
        "issued_on": issued_on,
        "include_customer": plan["include_customer"],
        "customer_name": plan["customer_name"] if plan["include_customer"] else "",
        "contact_email": plan["contact_email"] if plan["include_customer"] else "",
        "notes": plan["notes"],
        "input": {
            "include_customer": plan["include_customer"],
            "customer_name": plan["customer_name"],
            "contact_email": plan["contact_email"],
            "notes": plan["notes"],
            "lines": plan["lines"],
            "containers": plan["containers"],
        },
        "result": result,
    }
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO lp_plans
               (plan_number, customer_name, contact_email, include_customer, notes, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                plan_number,
                payload["customer_name"],
                payload["contact_email"],
                include,
                plan["notes"],
                json.dumps(payload),
            ),
        )
    return payload


def get_plan(plan_number: int) -> dict | None:
    ensure_schema()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payload_json FROM lp_plans WHERE plan_number = ?",
            (plan_number,),
        ).fetchone()
    if not row:
        return None
    data = json.loads(row["payload_json"])
    return data if isinstance(data, dict) else None


def list_plans(limit: int = 80) -> list[dict]:
    ensure_schema()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT plan_number, customer_name, created_at
               FROM lp_plans ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    listed = []
    for row in rows:
        number = row["plan_number"]
        label = f"PLAN-Q{number}"
        customer = (row["customer_name"] or "").strip()
        if customer:
            label = f"{label} {customer}"
        listed.append({
            "quote_number": str(number),
            "label": label,
            "saved_at": row["created_at"] or "",
        })
    return listed
