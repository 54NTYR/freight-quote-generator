"""Quoted-vs-actual variance per lane (MAD, MAPE, bias, on-time %)."""
import statistics

from storage import get_conn


def lane_variance(mode, origin_zip, dest_zip):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT q.quoted_transit_days, q.quoted_cost,
                      s.actual_transit_days, s.actual_cost, s.delivery_date
               FROM shipments s
               JOIN quotes q ON q.id = s.quote_id
               WHERE s.mode = ? AND s.origin_zip = ? AND s.dest_zip = ?
                 AND s.actual_transit_days IS NOT NULL
               ORDER BY s.delivery_date DESC LIMIT 60""",
            (mode, origin_zip, dest_zip)).fetchall()
    rows = [dict(r) for r in rows]

    out = {"mode": mode, "origin_zip": origin_zip, "dest_zip": dest_zip,
           "n": len(rows), "transit": None, "cost": None, "on_time_pct": None}
    if not rows:
        return out

    def summarize(pairs):  # (quoted, actual)
        pairs = [(q, a) for q, a in pairs if q]
        if not pairs:
            return None
        errs = [a - q for q, a in pairs]
        return {"mad": round(statistics.mean(abs(e) for e in errs), 2),
                "bias": round(statistics.mean(errs), 2),
                "mape_pct": round(100 * statistics.mean(
                    abs(a - q) / q for q, a in pairs), 1)}

    out["transit"] = summarize(
        [(r["quoted_transit_days"], r["actual_transit_days"]) for r in rows])
    out["cost"] = summarize(
        [(r["quoted_cost"], r["actual_cost"]) for r in rows])
    t_rows = [r for r in rows if r["quoted_transit_days"]]
    if t_rows:
        out["on_time_pct"] = round(100 * sum(
            1 for r in t_rows
            if r["actual_transit_days"] <= r["quoted_transit_days"])
            / len(t_rows), 1)
    return out