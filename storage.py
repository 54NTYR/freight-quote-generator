"""SQLite persistence: quotes, shipments, lane history. Lives in data/."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

try:
    from paths import data_dir
except ImportError:
    def data_dir():
        return str(Path(__file__).parent)

DB_FILE = "freight_history.db"


def _db_path():
    folder = Path(data_dir()) / "data"
    folder.mkdir(parents=True, exist_ok=True)
    new_path = folder / DB_FILE
    old_path = Path(data_dir()) / DB_FILE
    if DB_FILE == "freight_history.db" and not new_path.exists() and old_path.is_file():
        old_path.replace(new_path)
    return str(new_path)

SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_number TEXT UNIQUE,
    mode TEXT NOT NULL,
    origin_zip TEXT,
    dest_zip TEXT,
    quoted_transit_days REAL,
    quoted_cost REAL,
    payload_json TEXT NOT NULL,
    issued_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS shipments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER REFERENCES quotes(id) ON DELETE SET NULL,
    mode TEXT NOT NULL,
    origin_zip TEXT,
    dest_zip TEXT,
    carrier TEXT,
    pickup_date TEXT,
    delivery_date TEXT,
    actual_transit_days REAL,
    actual_cost REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_shipments_lane
    ON shipments (mode, origin_zip, dest_zip, delivery_date);
CREATE INDEX IF NOT EXISTS idx_quotes_lane
    ON quotes (mode, origin_zip, dest_zip, issued_at);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def save_quote(quote_number, mode, origin_zip, dest_zip,
               quoted_transit_days, quoted_cost, payload):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO quotes (quote_number, mode, origin_zip, dest_zip,
               quoted_transit_days, quoted_cost, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (quote_number, mode, origin_zip, dest_zip,
             quoted_transit_days, quoted_cost,
             json.dumps(payload, default=str)))
        return cur.lastrowid


def save_shipment(mode, origin_zip, dest_zip, carrier=None,
                  pickup_date=None, delivery_date=None,
                  actual_transit_days=None, actual_cost=None, quote_id=None):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO shipments (quote_id, mode, origin_zip, dest_zip,
               carrier, pickup_date, delivery_date,
               actual_transit_days, actual_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (quote_id, mode, origin_zip, dest_zip, carrier,
             pickup_date, delivery_date, actual_transit_days, actual_cost))
        return cur.lastrowid


def resolve_quote_id(quote_ref=None, mode=None, origin_zip=None, dest_zip=None):
    """Map a quote number (or row id) to quotes.id; else latest quote on the lane."""
    with get_conn() as conn:
        if quote_ref not in (None, ""):
            ref = str(quote_ref).strip()
            row = conn.execute(
                "SELECT id FROM quotes WHERE quote_number = ?", (ref,)
            ).fetchone()
            if row:
                return row["id"]
            if ref.isdigit():
                row = conn.execute(
                    "SELECT id FROM quotes WHERE id = ?", (int(ref),)
                ).fetchone()
                if row:
                    return row["id"]
        if mode and origin_zip is not None and dest_zip is not None:
            row = conn.execute(
                """SELECT id FROM quotes
                   WHERE mode = ? AND origin_zip = ? AND dest_zip = ?
                   ORDER BY issued_at DESC, id DESC LIMIT 1""",
                (mode, origin_zip, dest_zip),
            ).fetchone()
            if row:
                return row["id"]
    return None
