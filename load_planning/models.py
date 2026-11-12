"""Normalize a load-planning request into products, lines, and containers."""
from __future__ import annotations

PALETTE = (
    "#e6194b",
    "#3cb44b",
    "#ffe119",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#42d4f4",
    "#f032e6",
    "#bfef45",
    "#fabed4",
    "#469990",
    "#dcbeff",
    "#9a6324",
    "#fffac8",
    "#800000",
    "#aaffc3",
    "#808000",
    "#ffd8b1",
    "#000075",
    "#a9a9a9",
)

CONTAINER_TYPES = ("truck", "ocean", "pallet", "box", "railcar", "rectangular")
LOAD_DIRECTIONS = ("back_to_front", "bottom_to_top")
SHAPES = ("box", "cylinder", "pallet", "l_shape", "t_shape")
ORIENT_MODES = ("as_defined", "turned", "all_six", "standing", "custom")
ORIENTATION_NAMES = ("upright", "yaw90", "side", "side_turn", "end", "end_turn")
MAX_PIECES = 400


class PlanInputError(ValueError):
    """The builder sent a plan that cannot be packed yet."""


def color_for(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def _color(value, index: int) -> str:
    text = str(value or "").strip()
    if len(text) == 7 and text[0] == "#" and all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
        return "#" + text[1:].lower()
    return color_for(index)


def _text(value, field: str, limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        text = text[:limit].rstrip()
    return text


def _number(value, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PlanInputError(f"{field} must be a number.") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise PlanInputError(f"{field} must be a number.")
    return number


def _non_negative(value, field: str) -> float:
    number = _number(value, field)
    if number < 0:
        raise PlanInputError(f"{field} cannot be negative.")
    return number


def _positive(value, field: str) -> float:
    number = _number(value, field)
    if number <= 0:
        raise PlanInputError(f"{field} must be greater than zero.")
    return number


def _whole(value, field: str, minimum: int = 1) -> int:
    number = _number(value, field)
    whole = int(round(number))
    if abs(number - whole) > 1e-6:
        raise PlanInputError(f"{field} must be a whole number.")
    if whole < minimum:
        raise PlanInputError(f"{field} must be at least {minimum}.")
    return whole


def _optional_number(value, field: str):
    if value is None or value == "":
        return None
    return _number(value, field)


def _flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _optional_positive(value, field: str):
    if value is None or value == "":
        return None
    number = _number(value, field)
    if number <= 0:
        raise PlanInputError(f"{field} must be greater than zero.")
    return number


def _shape(row: dict) -> str:
    shape = str(row.get("shape") or "box").strip().lower()
    return shape if shape in SHAPES else "box"


def _cylinder_diameter(row: dict, label: str) -> tuple[float, float]:
    raw = row.get("diameter_in")
    if raw not in (None, ""):
        diameter = _positive(raw, f"{label} diameter")
        return diameter, diameter
    width = row.get("width_in")
    height = row.get("height_in")
    if width not in (None, "") and height not in (None, ""):
        width_n = _positive(width, f"{label} diameter")
        height_n = _positive(height, f"{label} diameter")
        if abs(width_n - height_n) > 1e-6:
            raise PlanInputError(f"{label} cylinder needs a length and one diameter.")
        return width_n, height_n
    if width not in (None, ""):
        diameter = _positive(width, f"{label} diameter")
        return diameter, diameter
    raise PlanInputError(f"{label} needs a diameter.")


def _orient_mode(row: dict) -> str:
    mode = str(row.get("orient_mode") or "").strip().lower()
    return mode if mode in ORIENT_MODES else ""


def _allowed_orientations(row: dict) -> list[str]:
    raw = row.get("allowed_orientations") or []
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",")]
    if not isinstance(raw, list):
        return []
    return [name for name in ORIENTATION_NAMES if name in raw]


def _turn_on_floor(row: dict) -> bool:
    mode = _orient_mode(row)
    if mode in {"as_defined", "standing"}:
        return False
    if mode in {"turned", "all_six"}:
        return True
    if mode == "custom":
        return "yaw90" in _allowed_orientations(row)
    return _flag(row.get("turn_on_floor", True))


def parse_plan(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise PlanInputError("Plan data was not a form.")
    lines_in = payload.get("lines") or []
    boxes_in = payload.get("containers") or []
    if not isinstance(lines_in, list) or not lines_in:
        raise PlanInputError("Add at least one product.")
    if not isinstance(boxes_in, list) or not boxes_in:
        raise PlanInputError("Add at least one container.")

    lines = [_parse_line(row, index) for index, row in enumerate(lines_in)]
    containers = [_parse_container(row, index) for index, row in enumerate(boxes_in)]
    pieces = sum(line["qty"] for line in lines)
    if pieces > MAX_PIECES:
        raise PlanInputError(
            f"This plan has {pieces} pieces. Keep a plan at {MAX_PIECES} pieces or fewer."
        )
    unusable = payload.get("unusable_spaces") or []
    warnings = []
    if unusable:
        warnings.append("Unusable spaces were sent and were not applied.")
    return {
        "include_customer": _flag(payload.get("include_customer")),
        "customer_name": _text(payload.get("customer_name"), "Customer name", 160),
        "contact_email": _text(payload.get("contact_email"), "Contact email", 160),
        "notes": _text(payload.get("notes"), "Notes", 4000),
        "lines": lines,
        "containers": containers,
        "warnings": warnings,
    }


def _parse_line(row: dict, index: int) -> dict:
    if not isinstance(row, dict):
        raise PlanInputError(f"Product {index + 1} is incomplete.")
    label = f"Product {index + 1}"
    name = _text(row.get("name"), f"{label} name")
    if not name:
        raise PlanInputError(f"{label} needs a name.")
    max_stack = row.get("max_stack")
    stack_index = row.get("stack_index")
    supported = _optional_number(row.get("supported_weight_lb"), f"{label} supported weight")
    if supported is not None and supported < 0:
        raise PlanInputError(f"{label} supported weight cannot be negative.")
    parsed_stack = None
    if max_stack not in (None, ""):
        parsed_stack = _whole(max_stack, f"{label} max stack", minimum=1)
    parsed_index = None
    if stack_index not in (None, ""):
        parsed_index = _whole(stack_index, f"{label} stack index", minimum=0)
    shape = _shape(row)
    length_in = _positive(row.get("length_in"), f"{label} length")
    if shape == "cylinder":
        width_in, height_in = _cylinder_diameter(row, label)
    else:
        width_in = _positive(row.get("width_in"), f"{label} width")
        height_in = _positive(row.get("height_in"), f"{label} height")
    return {
        "line_index": index,
        "product_id": _text(row.get("product_id"), "product id", 40),
        "name": name,
        "length_in": length_in,
        "width_in": width_in,
        "height_in": height_in,
        "weight_lb": _non_negative(row.get("weight_lb") or 0, f"{label} weight"),
        "qty": _whole(row.get("qty"), f"{label} quantity", minimum=1),
        "turn_on_floor": _turn_on_floor(row),
        "orient_mode": _orient_mode(row),
        "allowed_orientations": _allowed_orientations(row),
        "shape": shape,
        "back_depth": _optional_positive(row.get("back_depth"), f"{label} back depth"),
        "seat_height": _optional_positive(row.get("seat_height"), f"{label} seat height"),
        "stem_width": _optional_positive(row.get("stem_width"), f"{label} stem width"),
        "bar_depth": _optional_positive(row.get("bar_depth"), f"{label} bar depth"),
        "stackable": _flag(row.get("stackable", True)),
        "max_stack": parsed_stack,
        "on_floor_only": _flag(row.get("on_floor_only")),
        "on_top_only": _flag(row.get("on_top_only")),
        "supported_weight_lb": supported,
        "stack_index": parsed_index,
        "notes": _text(row.get("notes"), f"{label} notes", 500),
        "plan_text": _text(row.get("plan_text"), f"{label} load plan text", 16),
        "color": _color(row.get("color"), index),
    }


def _parse_container(row: dict, index: int) -> dict:
    if not isinstance(row, dict):
        raise PlanInputError(f"Container {index + 1} is incomplete.")
    label = f"Container {index + 1}"
    name = _text(row.get("label"), f"{label} name")
    if not name:
        raise PlanInputError(f"{label} needs a name.")
    kind = _text(row.get("type") or "truck", f"{label} type", 40).lower()
    if kind not in CONTAINER_TYPES:
        raise PlanInputError(f"{label} type is not supported.")
    direction = _text(row.get("load_direction") or "back_to_front", f"{label} load direction", 40)
    if direction not in LOAD_DIRECTIONS:
        raise PlanInputError(f"{label} load direction must be nose to door or floor to top.")
    spaces = row.get("unusable_spaces") or []
    return {
        "container_id": _text(row.get("container_id"), "container id", 40),
        "label": name,
        "type": kind,
        "length_in": _positive(row.get("length_in"), f"{label} length"),
        "width_in": _positive(row.get("width_in"), f"{label} width"),
        "height_in": _positive(row.get("height_in"), f"{label} height"),
        "max_payload_lb": _positive(row.get("max_payload_lb"), f"{label} payload"),
        "load_direction": direction,
        "available": _whole(row.get("available") or 1, f"{label} available count", minimum=1),
        "unusable_spaces": spaces if isinstance(spaces, list) else [],
    }
