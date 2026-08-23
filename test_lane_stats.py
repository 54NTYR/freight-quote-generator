import storage
import lane_stats
from datetime import date, timedelta
from pathlib import Path

# Seed dates must fall inside HISTORY_WINDOW_DAYS (180).
_DELIVERY = (date.today() - timedelta(days=7)).isoformat()


def setup_module(_):
    storage.DB_FILE = "test_lane_stats.db"  # get_conn resolves per-call
    path = Path(storage._db_path())
    if path.exists():
        path.unlink()
    storage.init_db()


def setup_function(_):
    storage.init_db()
    with storage.get_conn() as conn:
        conn.execute("DELETE FROM shipments")
        conn.execute("DELETE FROM quotes")


def teardown_module(_):
    path = Path(storage._db_path())
    if path.exists():
        path.unlink()


def _seed(n, mu=5.0):
    for i in range(n):
        storage.save_shipment("LTL", "60601", "10001",
                              actual_transit_days=mu + (i % 3) * 0.5,
                              delivery_date=_DELIVERY)


def test_estimate_provenance_without_history():
    s = lane_stats.resolve_lane_stats("LTL", "99999", "88888", 4.0, 0.5)
    assert s["provenance"] == "estimate" and s["n"] == 0


def test_history_provenance_at_threshold():
    _seed(3)
    s = lane_stats.resolve_lane_stats("LTL", "60601", "10001", 4.0, 0.5)
    assert s["provenance"] == "history" and s["n"] == 3


def test_interval_suppressed_without_history():
    assert lane_stats.prediction_interval_days(4.0, 0.5, 0, "estimate") is None


def test_interval_present_with_history():
    _seed(3)
    s = lane_stats.resolve_lane_stats("LTL", "60601", "10001", 4.0, 0.5)
    pi = lane_stats.prediction_interval_days(s["mu"], s["sigma"], s["n"], "history")
    assert pi and pi["low"] < s["mu"] < pi["high"]
