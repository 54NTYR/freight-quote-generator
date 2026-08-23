"""Admin: log shipment actuals + lane variance report."""
from flask import Blueprint, request, render_template, redirect, url_for

from storage import init_db, resolve_quote_id, save_shipment
from variance import lane_variance

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/log-shipment", methods=["GET", "POST"])
def log_shipment():
    init_db()
    if request.method == "POST":
        f = request.form
        mode = f["mode"].strip()
        origin_zip = f["origin_zip"].strip()
        dest_zip = f["dest_zip"].strip()
        save_shipment(
            mode=mode,
            origin_zip=origin_zip,
            dest_zip=dest_zip,
            carrier=f.get("carrier", "").strip() or None,
            pickup_date=f.get("pickup_date") or None,
            delivery_date=f.get("delivery_date") or None,
            actual_transit_days=float(f["actual_transit_days"]),
            actual_cost=(float(f["actual_cost"])
                         if f.get("actual_cost") else None),
            quote_id=resolve_quote_id(
                quote_ref=f.get("quote_id"),
                mode=mode,
                origin_zip=origin_zip,
                dest_zip=dest_zip,
            ))
        return redirect(url_for("admin.lane_report", mode=f["mode"],
                                origin_zip=f["origin_zip"],
                                dest_zip=f["dest_zip"]))
    return render_template("log_shipment.html")


@admin_bp.route("/lane-report")
def lane_report():
    init_db()
    mode = request.args.get("mode", "")
    origin_zip = request.args.get("origin_zip", "")
    dest_zip = request.args.get("dest_zip", "")
    report = (lane_variance(mode, origin_zip, dest_zip) if mode else None)
    return render_template("lane_report.html", report=report, mode=mode,
                           origin_zip=origin_zip, dest_zip=dest_zip)