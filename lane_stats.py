"""Lane μ/σ with provenance. Replaces fabricated defaults (n=12, σ=0.5).

Behavior change: prediction intervals are ONLY issued when provenance
is 'history'. With no history the quote shows a labelled estimate.
"""
import statistics

from analytics_core import prediction_interval_days  # noqa: F401 (re-export)
from storage import get_conn

MIN_HISTORY_N = 3
HISTORY_WINDOW_DAYS = 180


def lane_history(mode, origin_zip, dest_zip, window_days=HISTORY_WINDOW_DAYS):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT actual_transit_days, actual_cost, delivery_date
               FROM shipments
               WHERE mode = ? AND origin_zip = ? AND dest_zip = ?
                 AND delivery_date >= date('now', ?)
                 AND actual_transit_days IS NOT NULL
               ORDER BY delivery_date ASC""",
            (mode, origin_zip, dest_zip, f"-{window_days} days")).fetchall()
    return [dict(r) for r in rows]


def resolve_lane_stats(mode, origin_zip, dest_zip,
                       fallback_mu, fallback_sigma):
    """Returns dict(mu, sigma, n, provenance, window_days).

    provenance: 'history' | 'estimate'
    """
    hist = lane_history(mode, origin_zip, dest_zip)
    transits = [r["actual_transit_days"] for r in hist]

    if len(transits) >= MIN_HISTORY_N:
        sigma = statistics.stdev(transits)  # sample stdev (n-1)
        return {"mu": round(statistics.mean(transits), 2),
                "sigma": round(max(sigma, 0.1), 2),
                "n": len(transits), "provenance": "history",
                "window_days": HISTORY_WINDOW_DAYS}

    return {"mu": fallback_mu, "sigma": fallback_sigma,
            "n": 0, "provenance": "estimate",
            "window_days": HISTORY_WINDOW_DAYS}