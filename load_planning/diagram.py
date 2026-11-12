"""2D load diagrams. Top view and side view, nose on the left."""
from __future__ import annotations

import html


def top_svg(box: dict) -> str:
    return _draw(
        box,
        piece_cross="width_in",
        piece_up="y",
        flip_up=False,
        cross_size=box["width_in"],
        sort_key=lambda item: (item["z"], item["sequence"]),
        nose_label=_end_labels(box)[0],
        door_label=_end_labels(box)[1],
        caption="Top view",
    )


def side_svg(box: dict) -> str:
    return _draw(
        box,
        piece_cross="height_in",
        piece_up="z",
        flip_up=True,
        cross_size=box["height_in"],
        sort_key=lambda item: (item["y"], item["sequence"]),
        nose_label=_end_labels(box)[0],
        door_label=_end_labels(box)[1],
        caption="Side view",
    )


def _end_labels(box: dict) -> tuple[str, str]:
    if box.get("load_direction") == "bottom_to_top":
        return "Back", "Front"
    return "Nose", "Door"


def _draw(box, piece_cross, piece_up, flip_up, cross_size, sort_key, nose_label, door_label, caption) -> str:
    length = float(box["length_in"]) or 1
    cross = float(cross_size) or 1
    pad_l, pad_t, pad_r, pad_b = 8, 22, 8, 18
    scale = min(680 / length, 220 / cross)
    inner_w = length * scale
    inner_h = cross * scale
    width = pad_l + inner_w + pad_r
    height = pad_t + inner_h + pad_b
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" '
        f'role="img" aria-label="{html.escape(caption)} of {html.escape(box["label"])}">',
        f'<title>{html.escape(caption)} of {html.escape(box["label"])}</title>',
    ]
    parts.append(
        f'<rect x="{pad_l:.2f}" y="{pad_t:.2f}" width="{inner_w:.2f}" height="{inner_h:.2f}" '
        'fill="#f7f5f0" stroke="#1e3c72" stroke-width="1.5"/>'
    )
    door_x = pad_l + inner_w
    parts.append(
        f'<line x1="{door_x:.2f}" y1="{pad_t:.2f}" x2="{door_x:.2f}" y2="{pad_t + inner_h:.2f}" '
        'stroke="#c4a35a" stroke-width="3"/>'
    )
    for item in sorted(box.get("placements") or [], key=sort_key):
        px = pad_l + float(item["x"]) * scale
        size_along = float(item["length_in"]) * scale
        size_cross = float(item[piece_cross]) * scale
        if flip_up:
            py = pad_t + (cross - float(item[piece_up]) - float(item[piece_cross])) * scale
        else:
            py = pad_t + float(item[piece_up]) * scale
        color = html.escape(item.get("color") or "#1e3c72")
        parts.append(
            f'<rect x="{px:.2f}" y="{py:.2f}" width="{size_along:.2f}" height="{size_cross:.2f}" '
            f'fill="{color}" fill-opacity="0.88" stroke="#ffffff" stroke-width="0.6"/>'
        )
        if size_along >= 16 and size_cross >= 12:
            parts.append(
                f'<text x="{px + size_along / 2:.2f}" y="{py + size_cross / 2:.2f}" '
                'text-anchor="middle" dominant-baseline="middle" fill="#ffffff" '
                f'font-size="11" font-family="Segoe UI, sans-serif">{int(item["sequence"])}</text>'
            )
    parts.append(
        f'<text x="{pad_l:.2f}" y="14" fill="#1e3c72" font-size="11" '
        f'font-family="Segoe UI, sans-serif">{html.escape(nose_label)}</text>'
    )
    parts.append(
        f'<text x="{width - pad_r:.2f}" y="14" text-anchor="end" fill="#1e3c72" font-size="11" '
        f'font-family="Segoe UI, sans-serif">{html.escape(door_label)}</text>'
    )
    parts.append(
        f'<text x="{pad_l:.2f}" y="{height - 4:.2f}" fill="#5c6570" font-size="10" '
        f'font-family="Segoe UI, sans-serif">{html.escape(caption)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)
