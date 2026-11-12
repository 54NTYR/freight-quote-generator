"""Rectangular load packer.

Origin is the nose, the left wall, and the floor. x runs toward the door,
y runs toward the right wall, and z runs up. A placement is the nose-left-floor
corner of the piece. See DOMAIN.md.

The search is bottom-left fill. It is deterministic: the same lines and
containers always produce the same placements. There is no random step.
Upright and turned-on-floor placements go in first. Side and end placements
are tried only for pieces that still do not fit, and only when that product
allows them.
"""
from __future__ import annotations

import math

EPS = 1e-4
SUPPORT_FACTOR = 0.75
PRIMARY_ORIENTATIONS = ("upright", "yaw90")
EXTRA_ORIENTATIONS = ("side", "side_turn", "end", "end_turn")
ORIENTATION_AXES = {
    "upright": (0, 1, 2),
    "yaw90": (1, 0, 2),
    "side": (0, 2, 1),
    "side_turn": (2, 0, 1),
    "end": (2, 1, 0),
    "end_turn": (1, 2, 0),
}
ORIENTATION_LABELS = {
    "upright": "Upright",
    "yaw90": "Turned on floor",
    "side": "On side",
    "side_turn": "On side, turned",
    "end": "On end",
    "end_turn": "On end, turned",
}
CYLINDER_LABELS = {
    "upright": "Along its length",
    "yaw90": "Across the trailer",
    "side": "Along its length",
    "side_turn": "Across the trailer",
    "end": "Standing",
    "end_turn": "Standing",
}


def optimize(plan: dict) -> dict:
    """Pack plan lines into the selected containers. Leftovers stay listed."""
    warnings = list(plan.get("warnings") or [])
    for box in plan["containers"]:
        if box.get("unusable_spaces"):
            warnings.append(
                f"{box['label']}: unusable spaces are saved on the request and were not applied."
            )
    remaining = _expand(plan["lines"])
    opened = []
    instance = 0
    for spec_index, spec in enumerate(plan["containers"]):
        if not remaining:
            break
        for _copy in range(spec["available"]):
            if not remaining:
                break
            placed, remaining = _pack_one(spec, remaining, "primary")
            if not placed:
                break
            instance += 1
            opened.append({
                "spec": spec,
                "spec_index": spec_index,
                "placed": placed,
                "instance": instance,
            })
    for entry in opened:
        if not _has_extra(remaining):
            break
        _added, remaining = _pack_one(entry["spec"], remaining, "extra", entry["placed"])
    for spec_index, spec in enumerate(plan["containers"]):
        if not _has_extra(remaining):
            break
        used = sum(1 for entry in opened if entry["spec_index"] == spec_index)
        for _copy in range(used, spec["available"]):
            if not _has_extra(remaining):
                break
            placed, remaining = _pack_one(spec, remaining, "extra")
            if not placed:
                break
            instance += 1
            opened.append({
                "spec": spec,
                "spec_index": spec_index,
                "placed": placed,
                "instance": instance,
            })
    loaded = [
        _container_result(entry["spec"], entry["placed"], entry["instance"], entry["spec_index"])
        for entry in opened
    ]
    line_rows = _line_rows(plan["lines"], loaded)
    used_volume = sum(row["metrics"]["used_volume_cu_in"] for row in loaded)
    used_weight = sum(row["metrics"]["used_weight_lb"] for row in loaded)
    capacity_volume = sum(row["metrics"]["capacity_volume_cu_in"] for row in loaded)
    capacity_weight = sum(row["metrics"]["capacity_weight_lb"] for row in loaded)
    ordered = sum(line["qty"] for line in plan["lines"])
    loaded_pieces = ordered - sum(line["leftover"] for line in line_rows)
    split = [
        line["name"] for line in line_rows
        if line["loaded"] and _line_container_count(line["line_index"], loaded) > 1
    ]
    if split:
        warnings.append("Some products were split across containers: " + ", ".join(split) + ".")
    return {
        "containers": loaded,
        "lines": line_rows,
        "warnings": _unique(warnings),
        "metrics": {
            "cube_util_pct": _pct(used_volume, capacity_volume),
            "weight_util_pct": _pct(used_weight, capacity_weight),
            "used_weight_lb": round(used_weight, 2),
            "used_volume_cu_in": round(used_volume, 2),
            "used_volume_cu_ft": round(used_volume / 1728.0, 2),
            "capacity_volume_cu_ft": round(capacity_volume / 1728.0, 2),
            "capacity_weight_lb": round(capacity_weight, 2),
            "ordered_pieces": ordered,
            "loaded_pieces": loaded_pieces,
            "leftover_pieces": ordered - loaded_pieces,
            "containers_used": len(loaded),
            "containers_available": sum(box["available"] for box in plan["containers"]),
        },
        "all_fit": all(line["leftover"] == 0 for line in line_rows),
        "coordinate_system": "Origin at the nose, left wall, and floor. x toward the door, y to the right, z up.",
    }


def _expand(lines: list[dict]) -> list[dict]:
    units = []
    for line in lines:
        for unit_index in range(line["qty"]):
            units.append({"line": line, "unit_index": unit_index})
    units.sort(key=_unit_sort)
    return units


def _unit_sort(unit: dict):
    line = unit["line"]
    volume = line["length_in"] * line["width_in"] * line["height_in"]
    return (
        0 if line["on_floor_only"] else 1,
        -volume,
        -line["weight_lb"],
        line["name"].lower(),
        line["line_index"],
        unit["unit_index"],
    )


def _pack_one(spec: dict, units: list[dict], phase: str, placed: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    if placed is None:
        placed = []
    still = []
    for unit in units:
        spot = _find_spot(spec, placed, unit["line"], _orients_for(unit["line"], phase))
        if spot is None:
            still.append(unit)
            continue
        spot["line_index"] = unit["line"]["line_index"]
        spot["sequence"] = len(placed) + 1
        _apply_weight(spot.pop("_shares"))
        placed.append(spot)
    return placed, still


def _has_extra(units: list[dict]) -> bool:
    return any(_orients_for(unit["line"], "extra") for unit in units)


def _find_spot(spec: dict, placed: list[dict], line: dict, orients: list[tuple[str, float, float, float]]):
    if not orients:
        return None
    if line["weight_lb"] > spec["max_payload_lb"] - _used_weight(placed) + EPS:
        return None
    if not any(_fits_container(spec, length, width, height) for _name, length, width, height in orients):
        return None
    points = sorted(_candidate_points(spec, placed), key=lambda point: _point_key(point, spec["load_direction"]))
    for point in points:
        for rotation, length, width, height in orients:
            spot = _try_place(spec, placed, line, point, rotation, length, width, height)
            if spot is not None:
                return spot
    return None


def _allowed_names(line: dict) -> list[str]:
    mode = str(line.get("orient_mode") or "").strip()
    if mode == "as_defined":
        names = ["upright"]
    elif mode == "turned":
        names = ["upright", "yaw90"]
    elif mode == "standing":
        names = ["end"]
    elif mode == "all_six":
        names = list(PRIMARY_ORIENTATIONS + EXTRA_ORIENTATIONS)
    elif mode == "custom":
        allowed = set(line.get("allowed_orientations") or [])
        names = [name for name in PRIMARY_ORIENTATIONS + EXTRA_ORIENTATIONS if name in allowed] or ["upright"]
    else:
        names = ["upright"]
        if line.get("turn_on_floor", True):
            names.append("yaw90")
    if line.get("shape") == "cylinder":
        names = [name for name in names if name in ("upright", "yaw90", "end")] or ["upright"]
    return names


def _orients_for(line: dict, phase: str) -> list[tuple[str, float, float, float]]:
    names = _allowed_names(line)
    primary = [name for name in names if name in PRIMARY_ORIENTATIONS]
    extra = [name for name in names if name in EXTRA_ORIENTATIONS]
    if phase == "primary":
        chosen = primary or extra
    elif primary:
        chosen = extra
    else:
        chosen = []
    found = []
    seen = set()
    for name in chosen:
        dims = _oriented_dims(line, name)
        if dims[1:] in seen:
            continue
        seen.add(dims[1:])
        found.append(dims)
    return found


def _oriented_dims(line: dict, name: str) -> tuple[str, float, float, float]:
    source = ORIENTATION_AXES[name]
    base = (line["length_in"], line["width_in"], line["height_in"])
    return (name, base[source[0]], base[source[1]], base[source[2]])


def _fits_container(spec, length, width, height) -> bool:
    return (
        length <= spec["length_in"] + EPS
        and width <= spec["width_in"] + EPS
        and height <= spec["height_in"] + EPS
    )


def _candidate_points(spec: dict, placed: list[dict]) -> list[tuple[float, float, float]]:
    points = {(0.0, 0.0, 0.0)}
    for item in placed:
        for part in _solids(item):
            x0 = part["x"]
            y0 = part["y"]
            z0 = part["z"]
            x1 = _round(x0 + part["length_in"])
            y1 = _round(y0 + part["width_in"])
            z1 = _round(z0 + part["height_in"])
            for x, y, z in ((x1, y0, z0), (x0, y1, z0), (x0, y0, z1)):
                points.add((x, y, z))
                # Also try the same edge against the nose, the left wall, and the floor,
                # so a gap beside a piece is not skipped for a single file further along.
                points.add((0.0, y, z))
                points.add((x, 0.0, z))
                points.add((x, y, 0.0))
    kept = []
    for x, y, z in points:
        if x < -EPS or y < -EPS or z < -EPS:
            continue
        if x >= spec["length_in"] - EPS or y >= spec["width_in"] - EPS or z >= spec["height_in"] - EPS:
            continue
        kept.append((x, y, z))
    return kept


def _point_key(point, direction: str):
    x, y, z = point
    if direction == "bottom_to_top":
        return (z, x, y)
    return (x, z, y)


def _try_place(spec, placed, line, point, rotation, length, width, height):
    x, y, z = point
    if x + length > spec["length_in"] + EPS:
        return None
    if y + width > spec["width_in"] + EPS:
        return None
    if z + height > spec["height_in"] + EPS:
        return None
    draft = {
        "x": _round(x),
        "y": _round(y),
        "z": _round(z),
        "length_in": length,
        "width_in": width,
        "height_in": height,
    }
    draft["shape"] = line.get("shape") or "box"
    draft["cylinder_axis"] = _cylinder_axis(rotation) if draft["shape"] == "cylinder" else ""
    draft["_parts"] = _placed_parts(line, (draft["x"], draft["y"], draft["z"]), rotation)
    if any(_overlaps(draft, item) for item in placed):
        return None
    draft["stackable"] = line["stackable"]
    draft["on_top_only"] = line["on_top_only"]
    draft["_product_key"] = _product_key(line)
    if _column_blocked(draft, placed):
        return None
    supporters, support_area = _supporters(draft, placed)
    footprint = _footprint_area(draft)
    if draft["z"] > EPS:
        if footprint <= EPS or support_area < SUPPORT_FACTOR * footprint - EPS:
            return None
        if line["on_floor_only"] and any(item["_product_key"] != _product_key(line) for item in supporters):
            return None
        if not _stack_allowed(line, supporters):
            return None
    shares = _weight_shares(draft, line, supporters)
    if shares is None:
        return None
    depth = _stack_depth(line, supporters)
    if line["max_stack"] is not None and depth > line["max_stack"]:
        return None
    return {
        "product_id": line["product_id"],
        "name": line["name"],
        "x": draft["x"],
        "y": draft["y"],
        "z": draft["z"],
        "length_in": length,
        "width_in": width,
        "height_in": height,
        "weight_lb": round(line["weight_lb"], 4),
        "rotation": rotation,
        "shape": draft["shape"],
        "cylinder_axis": draft["cylinder_axis"],
        "_parts": draft["_parts"],
        "color": line["color"],
        "plan_text": line.get("plan_text") or "",
        "stack_depth": depth,
        "stack_index": line["stack_index"],
        "stackable": line["stackable"],
        "on_top_only": line["on_top_only"],
        "max_stack": line["max_stack"],
        "supported_weight_lb": line["supported_weight_lb"],
        "weight_above_lb": 0.0,
        "_shares": shares,
        "_product_key": _product_key(line),
    }


def _product_key(line: dict) -> str:
    if line["product_id"]:
        return f"id:{line['product_id']}"
    return f"line:{line['line_index']}"


def _solids(item: dict) -> list[dict]:
    parts = item.get("_parts")
    if parts:
        return parts
    return [item]


def _overlaps(a, b) -> bool:
    if a.get("shape") == "cylinder" or b.get("shape") == "cylinder":
        return _cylinder_overlaps(a, b)
    for left in _solids(a):
        for right in _solids(b):
            if _box_overlaps(left, right):
                return True
    return False


def _box_overlaps(a, b) -> bool:
    return (
        a["x"] < b["x"] + b["length_in"] - EPS
        and a["x"] + a["length_in"] > b["x"] + EPS
        and a["y"] < b["y"] + b["width_in"] - EPS
        and a["y"] + a["width_in"] > b["y"] + EPS
        and a["z"] < b["z"] + b["height_in"] - EPS
        and a["z"] + a["height_in"] > b["z"] + EPS
    )


def _cylinder_overlaps(a, b) -> bool:
    if a.get("shape") == "cylinder" and b.get("shape") == "cylinder":
        first = _cylinder_metrics(a)
        second = _cylinder_metrics(b)
        if first["axis"] != second["axis"]:
            return _box_overlaps(a, b)
        if not _ranges_overlap(first["origin"], first["length"], second["origin"], second["length"]):
            return False
        du = first["cu"] - second["cu"]
        dv = first["cv"] - second["cv"]
        reach = first["radius"] + second["radius"]
        return du * du + dv * dv < reach * reach - EPS
    drum = a if a.get("shape") == "cylinder" else b
    other = b if drum is a else a
    metrics = _cylinder_metrics(drum)
    along = {"x": "x", "y": "y", "z": "z"}[metrics["axis"]]
    size = {"x": "length_in", "y": "width_in", "z": "height_in"}[metrics["axis"]]
    for part in _solids(other):
        if _ranges_overlap(metrics["origin"], metrics["length"], part[along], part[size]) and _circle_hits_rect(drum, part):
            return True
    return False


def _ranges_overlap(origin_a, size_a, origin_b, size_b) -> bool:
    return origin_a < origin_b + size_b - EPS and origin_a + size_a > origin_b + EPS


_AXIS_FIELDS = {
    "x": ("x", "length_in", "y", "width_in", "z", "height_in"),
    "y": ("y", "width_in", "x", "length_in", "z", "height_in"),
    "z": ("z", "height_in", "x", "length_in", "y", "width_in"),
}


def _cylinder_axis(rotation: str) -> str:
    source = ORIENTATION_AXES[rotation]
    return ("x", "y", "z")[source.index(0)]


def _cylinder_metrics(item: dict) -> dict:
    axis = item.get("cylinder_axis") or "x"
    along, along_size, u_name, u_size, v_name, v_size = _AXIS_FIELDS[axis]
    return {
        "axis": axis,
        "origin": item[along],
        "length": item[along_size],
        "u": u_name,
        "u_size": u_size,
        "v": v_name,
        "v_size": v_size,
        "cu": item[u_name] + item[u_size] / 2,
        "cv": item[v_name] + item[v_size] / 2,
        "radius": min(item[u_size], item[v_size]) / 2,
    }


def _circle_hits_rect(drum: dict, rect: dict) -> bool:
    metrics = _cylinder_metrics(drum)
    u0 = rect[metrics["u"]]
    u1 = u0 + rect[metrics["u_size"]]
    v0 = rect[metrics["v"]]
    v1 = v0 + rect[metrics["v_size"]]
    nearest_u = min(max(metrics["cu"], u0), u1)
    nearest_v = min(max(metrics["cv"], v0), v1)
    du = metrics["cu"] - nearest_u
    dv = metrics["cv"] - nearest_v
    radius = metrics["radius"]
    return du * du + dv * dv < radius * radius - EPS


def _notch_size(value, limit: float) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    if EPS < number < limit - EPS:
        return number
    if limit > 2:
        return limit / 2
    return 0.0


def _local_parts(line: dict) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    length = line["length_in"]
    width = line["width_in"]
    height = line["height_in"]
    full = ((0.0, 0.0, 0.0), (length, width, height))
    shape = line.get("shape") or "box"
    if shape == "l_shape":
        back = _notch_size(line.get("back_depth"), width)
        seat = _notch_size(line.get("seat_height"), height)
        if back > EPS and seat > EPS:
            return [
                ((0.0, 0.0, 0.0), (length, back, height)),
                ((0.0, back, 0.0), (length, width - back, seat)),
            ]
    if shape == "t_shape":
        stem = _notch_size(line.get("stem_width"), width)
        bar = _notch_size(line.get("bar_depth"), length)
        if stem > EPS and bar > EPS:
            return [
                ((0.0, 0.0, 0.0), (bar, width, height)),
                ((bar, (width - stem) / 2, 0.0), (length - bar, stem, height)),
            ]
    return [full]


def _placed_parts(line: dict, origin: tuple[float, float, float], rotation: str) -> list[dict]:
    source = ORIENTATION_AXES[rotation]
    parts = []
    for local_origin, local_size in _local_parts(line):
        parts.append({
            "x": _round(origin[0] + local_origin[source[0]]),
            "y": _round(origin[1] + local_origin[source[1]]),
            "z": _round(origin[2] + local_origin[source[2]]),
            "length_in": local_size[source[0]],
            "width_in": local_size[source[1]],
            "height_in": local_size[source[2]],
        })
    if len(parts) == 1 and (line.get("shape") or "box") in ("box", "cylinder", "pallet"):
        return []
    return parts


def _footprint_area(item: dict) -> float:
    return sum(part["length_in"] * part["width_in"] for part in _bottom_parts(item))


def _bottom_parts(item: dict) -> list[dict]:
    parts = _solids(item)
    base = item["z"]
    bottoms = [part for part in parts if abs(part["z"] - base) <= EPS]
    return bottoms or parts


def _solid_volume(item: dict) -> float:
    if item.get("shape") == "cylinder":
        metrics = _cylinder_metrics(item)
        return math.pi * metrics["radius"] * metrics["radius"] * metrics["length"]
    return sum(part["length_in"] * part["width_in"] * part["height_in"] for part in _solids(item))


def _overlap_area(a, b) -> float:
    ox = min(a["x"] + a["length_in"], b["x"] + b["length_in"]) - max(a["x"], b["x"])
    oy = min(a["y"] + a["width_in"], b["y"] + b["width_in"]) - max(a["y"], b["y"])
    if ox <= EPS or oy <= EPS:
        return 0.0
    return ox * oy


def _supporters(draft, placed):
    found = []
    area = 0.0
    bottoms = _bottom_parts(draft)
    top = draft["z"]
    for item in placed:
        shared = 0.0
        for part in _solids(item):
            if abs((part["z"] + part["height_in"]) - top) > EPS:
                continue
            for bottom in bottoms:
                shared += _overlap_area(bottom, part)
        if shared <= EPS:
            continue
        found.append(item)
        area += shared
    return found, area


def _occupies_above(upper, lower) -> bool:
    for base in _solids(lower):
        ceiling = base["z"] + base["height_in"]
        for cap in _solids(upper):
            if cap["z"] + EPS < ceiling:
                continue
            if _overlap_area(cap, base) > EPS:
                return True
    return False


def _column_blocked(draft, placed) -> bool:
    for item in placed:
        if _occupies_above(item, draft):
            if not draft["stackable"]:
                return True
            if draft["on_top_only"] and item["_product_key"] != draft["_product_key"]:
                return True
        if _occupies_above(draft, item):
            if not item["stackable"]:
                return True
            if item["on_top_only"] and item["_product_key"] != draft["_product_key"]:
                return True
    return False


def _stack_allowed(line, supporters) -> bool:
    key = _product_key(line)
    for item in supporters:
        if not item["stackable"]:
            return False
        if item["on_top_only"] and item["_product_key"] != key:
            return False
        upper = line["stack_index"]
        lower = item["stack_index"]
        if upper is not None and lower is not None and upper > lower:
            return False
    return True


def _stack_depth(line, supporters) -> int:
    key = _product_key(line)
    same = [item["stack_depth"] for item in supporters if item["_product_key"] == key]
    if not same:
        return 1
    return 1 + max(same)


def _weight_shares(draft, line, supporters):
    if not supporters:
        return []
    areas = []
    total = 0.0
    for item in supporters:
        area = _overlap_area(draft, item)
        areas.append((item, area))
        total += area
    if total <= EPS:
        return []
    shares = []
    for item, area in areas:
        added = line["weight_lb"] * (area / total)
        if not _can_carry(item, added):
            return None
        shares.append((item, added))
    return shares


def _can_carry(item, added) -> bool:
    limit = item["supported_weight_lb"]
    if limit is None:
        return True
    return item["weight_above_lb"] + added <= limit + EPS


def _apply_weight(shares):
    for item, added in shares:
        item["weight_above_lb"] = round(item["weight_above_lb"] + added, 4)


def _used_weight(placed) -> float:
    return sum(item["weight_lb"] for item in placed)


def _round(value: float) -> float:
    return round(float(value), 4)


def _container_result(spec: dict, placed: list[dict], instance: int, spec_index: int = 0) -> dict:
    public = [_public_placement(item) for item in placed]
    used_volume = sum(_solid_volume(item) for item in placed)
    used_weight = sum(item["weight_lb"] for item in public)
    capacity_volume = spec["length_in"] * spec["width_in"] * spec["height_in"]
    return {
        "instance": instance,
        "spec_index": spec_index,
        "container_id": spec["container_id"],
        "label": spec["label"],
        "type": spec["type"],
        "length_in": spec["length_in"],
        "width_in": spec["width_in"],
        "height_in": spec["height_in"],
        "max_payload_lb": spec["max_payload_lb"],
        "load_direction": spec["load_direction"],
        "placements": public,
        "metrics": {
            "cube_util_pct": _pct(used_volume, capacity_volume),
            "weight_util_pct": _pct(used_weight, spec["max_payload_lb"]),
            "used_weight_lb": round(used_weight, 2),
            "used_volume_cu_in": round(used_volume, 2),
            "used_volume_cu_ft": round(used_volume / 1728.0, 2),
            "capacity_volume_cu_in": round(capacity_volume, 2),
            "capacity_volume_cu_ft": round(capacity_volume / 1728.0, 2),
            "capacity_weight_lb": spec["max_payload_lb"],
            "loaded_pieces": len(public),
        },
    }


def _public_placement(item: dict) -> dict:
    return {
        "line_index": item["line_index"],
        "product_id": item["product_id"],
        "name": item["name"],
        "x": item["x"],
        "y": item["y"],
        "z": item["z"],
        "length_in": item["length_in"],
        "width_in": item["width_in"],
        "height_in": item["height_in"],
        "weight_lb": item["weight_lb"],
        "rotation": item["rotation"],
        "rotation_label": (CYLINDER_LABELS if item.get("shape") == "cylinder" else ORIENTATION_LABELS).get(item["rotation"], "Upright"),
        "shape": item.get("shape") or "box",
        "cylinder_axis": item.get("cylinder_axis") or "",
        "parts": [
            {
                "x": part["x"],
                "y": part["y"],
                "z": part["z"],
                "length_in": part["length_in"],
                "width_in": part["width_in"],
                "height_in": part["height_in"],
            }
            for part in item.get("_parts") or []
        ],
        "color": item["color"],
        "plan_text": item.get("plan_text") or "",
        "sequence": item["sequence"],
        "stack_depth": item["stack_depth"],
    }


def _line_rows(lines: list[dict], loaded: list[dict]) -> list[dict]:
    counts = {line["line_index"]: 0 for line in lines}
    for box in loaded:
        for item in box["placements"]:
            counts[item["line_index"]] = counts.get(item["line_index"], 0) + 1
    rows = []
    for line in lines:
        loaded_count = counts.get(line["line_index"], 0)
        rows.append({
            "line_index": line["line_index"],
            "product_id": line["product_id"],
            "name": line["name"],
            "ordered": line["qty"],
            "loaded": loaded_count,
            "leftover": line["qty"] - loaded_count,
            "length_in": line["length_in"],
            "width_in": line["width_in"],
            "height_in": line["height_in"],
            "weight_lb": line["weight_lb"],
            "turn_on_floor": line["turn_on_floor"],
            "color": line["color"],
            "notes": line["notes"],
        })
    return rows


def _line_container_count(line_index: int, loaded: list[dict]) -> int:
    return sum(
        1 for box in loaded
        if any(item["line_index"] == line_index for item in box["placements"])
    )


def _pct(used: float, capacity: float) -> float:
    if capacity <= EPS:
        return 0.0
    return round(used / capacity * 100.0, 1)


def _unique(items: list[str]) -> list[str]:
    seen = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen
