"""Shared online quote numbers via a Google Apps Script web app."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from config import load_config, save_config_values
from paths import data_path


USER_AGENT = "JerichoFreightQuoteGenerator/1.0"


class QuoteCounterError(Exception):
    pass


def load_quote_counter_settings() -> dict:
    cfg = load_config()
    block = cfg.get("quote_counter")
    if not isinstance(block, dict):
        block = {}
    return {
        "url": str(block.get("url") or cfg.get("quote_counter_url") or "").strip(),
        "secret": str(block.get("secret") or cfg.get("quote_counter_secret") or "").strip(),
    }


def save_quote_counter_settings(url: str, secret: str) -> dict:
    payload = {
        "url": (url or "").strip(),
        "secret": (secret or "").strip(),
    }
    save_config_values(quote_counter=payload)
    return payload


def next_local_quote_number() -> int:
    counter_file = data_path("quote_counter.json")
    if not os.path.exists(counter_file):
        with open(counter_file, "w", encoding="utf-8") as handle:
            json.dump({"counter": 1}, handle)
        return 1
    with open(counter_file, "r+", encoding="utf-8") as handle:
        data = json.load(handle)
        data["counter"] = int(data.get("counter") or 0) + 1
        handle.seek(0)
        json.dump(data, handle)
        handle.truncate()
        return int(data["counter"])


def next_quote_number(mode: str = "") -> int:
    settings = load_quote_counter_settings()
    if not settings["url"] or not settings["secret"]:
        raise QuoteCounterError(
            "Set up the shared quote counter in Settings before generating a quote."
        )
    payload = _request(settings["url"], {
        "action": "next",
        "secret": settings["secret"],
        "mode": mode or "",
    })
    if payload.get("error") == "bad_secret":
        raise QuoteCounterError(
            "The quote counter password does not match the Google script. Check Settings."
        )
    return _require_number(payload)


def _require_number(payload: dict) -> int:
    if not payload.get("ok"):
        raise QuoteCounterError(
            payload.get("error")
            or "The Google quote counter did not return a number."
        )
    try:
        value = int(payload.get("quote_number"))
    except (TypeError, ValueError):
        raise QuoteCounterError("The Google quote counter sent a value that is not a number.")
    if value < 1:
        raise QuoteCounterError("The Google quote counter returned an empty number.")
    return value


def _request(base_url: str, params: dict) -> dict:
    merged = dict(params or {})
    merged["_ts"] = f"{time.time_ns()}"
    url = _with_params(base_url, merged)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise QuoteCounterError(
            "Google did not accept the quote counter request. Try deploying the web app again."
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise QuoteCounterError(
            "Could not reach the Google quote counter. Check the web app URL and your internet."
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise QuoteCounterError(
            "The Google quote counter did not send a normal reply. Open the web app URL in a browser."
        ) from exc
    return data if isinstance(data, dict) else {}


def _with_params(base_url: str, params: dict) -> str:
    cleaned = {key: str(value) for key, value in params.items() if value not in (None, "")}
    if not cleaned:
        return base_url
    parsed = urllib.parse.urlsplit(base_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.update(cleaned)
    return urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        urllib.parse.urlencode(query),
        parsed.fragment,
    ))
