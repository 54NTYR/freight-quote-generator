"""Product and container masters for Load Planning."""
from __future__ import annotations

from load_planning.models import PlanInputError, _parse_container, _parse_line
from load_planning.storage_lp import (
    delete_container,
    delete_product,
    list_containers,
    list_products,
    save_container,
    save_product,
)


def products() -> list[dict]:
    return list_products()


def containers() -> list[dict]:
    return list_containers()


def add_product(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise PlanInputError("Product data was not a form.")
    row = dict(payload)
    row.setdefault("qty", 1)
    return save_product(_parse_line(row, 0))


def remove_product(product_id: int) -> bool:
    return delete_product(product_id)


def add_container(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise PlanInputError("Container data was not a form.")
    row = dict(payload)
    row.setdefault("available", 1)
    parsed = _parse_container(row, 0)
    parsed["notes"] = ""
    return save_container(parsed)


def remove_container(container_id: int) -> bool:
    return delete_container(container_id)
