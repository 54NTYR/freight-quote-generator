"""Load Planning routes. Registered beside the quote modes."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request, url_for
from markupsafe import Markup

from config import COMPANY_INFO
from customers import remember_customer
from load_planning.catalogs import (
    add_container,
    add_product,
    containers,
    products,
    remove_container,
    remove_product,
)
from load_planning.diagram import side_svg, top_svg
from load_planning.engine import optimize
from load_planning.models import PlanInputError, parse_plan
from load_planning.storage_lp import ensure_schema, get_plan, list_plans, next_plan_number, save_plan

load_planning_bp = Blueprint("load_planning", __name__, url_prefix="/load-planning")


def render_builder():
    ensure_schema()
    plans = list_plans()
    context = {
        "header_subtitle": "Load Planning",
        "previous_label": "Load Previous Plan",
        "previous_button": "Select a plan",
    }
    if plans:
        context["previous_quotes"] = plans
    return render_template("load_planning/builder.html", **context)


def _format_plan_date(value=None) -> str:
    moment = value or datetime.now()
    return f"{moment.strftime('%B')} {moment.day}, {moment.year}"


def _quote_view(record: dict) -> dict:
    return {
        "quote_number": record["plan_label"],
        "current_date": record["issued_on"],
        "valid_until": "",
        "include_customer": record.get("include_customer"),
        "customer_name": record.get("customer_name") or "",
        "contact_email": record.get("contact_email") or "",
        "company_name": COMPANY_INFO["company_name"],
        "dot_number": COMPANY_INFO["dot_number"],
        "mc_number": COMPANY_INFO["mc_number"],
        "phone": COMPANY_INFO["phone"],
        "email": COMPANY_INFO["email"],
        "website": COMPANY_INFO["website"],
    }


def _with_diagrams(record: dict) -> dict:
    result = record["result"]
    for box in result.get("containers") or []:
        box["diagram_top"] = Markup(top_svg(box))
        box["diagram_side"] = Markup(side_svg(box))
    return result


@load_planning_bp.post("/preview")
def preview_plan():
    """Pack the load for the 3D preview. Does not take a plan number."""
    ensure_schema()
    payload = request.get_json(silent=True) or {}
    try:
        plan = parse_plan(payload)
    except PlanInputError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True, result=optimize(plan))


@load_planning_bp.post("/optimize")
def optimize_plan():
    ensure_schema()
    payload = request.get_json(silent=True) or {}
    try:
        plan = parse_plan(payload)
    except PlanInputError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    result = optimize(plan)
    number = next_plan_number()
    issued_on = _format_plan_date()
    record = save_plan(number, plan, result, issued_on)
    if plan["include_customer"] and plan["customer_name"]:
        try:
            remember_customer(plan["customer_name"], plan["contact_email"])
        except OSError:
            logging.exception("Could not remember load planning customer")
    return jsonify(
        ok=True,
        plan_number=number,
        plan_label=record["plan_label"],
        url=url_for("load_planning.plan_output", number=number),
    )


@load_planning_bp.get("/plan/<int:number>")
def plan_output(number: int):
    record = get_plan(number)
    if not record:
        abort(404)
    result_json = json.dumps(record["result"]).replace("<", "\\u003c")
    return render_template(
        "load_planning/output.html",
        quote=_quote_view(record),
        quote_file_label=record["plan_label"],
        plan=record,
        result=_with_diagrams(record),
        result_json=result_json,
        current_year=datetime.now().year,
    )


@load_planning_bp.get("/plan/<int:number>/input")
def plan_input(number: int):
    record = get_plan(number)
    if not record:
        abort(404)
    return jsonify(record.get("input") or {})


@load_planning_bp.get("/plan/<int:number>/export")
def export_plan(number: int):
    record = get_plan(number)
    if not record:
        abort(404)
    return jsonify(record)


@load_planning_bp.get("/api/products")
def api_products():
    return jsonify(products=products())


@load_planning_bp.post("/api/products")
def api_add_product():
    try:
        row = add_product(request.get_json(silent=True) or {})
    except PlanInputError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True, product=row)


@load_planning_bp.delete("/api/products/<int:product_id>")
def api_delete_product(product_id: int):
    if not remove_product(product_id):
        abort(404)
    return jsonify(ok=True)


@load_planning_bp.get("/api/containers")
def api_containers():
    return jsonify(containers=containers())


@load_planning_bp.post("/api/containers")
def api_add_container():
    try:
        row = add_container(request.get_json(silent=True) or {})
    except PlanInputError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True, container=row)


@load_planning_bp.delete("/api/containers/<int:container_id>")
def api_delete_container(container_id: int):
    if not remove_container(container_id):
        abort(404)
    return jsonify(ok=True)
