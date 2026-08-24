import json
import os
import shutil

from paths import data_path, resource_dir

PLACEHOLDER_KEY = "YOUR_GOOGLE_MAPS_API_KEY_HERE"
CONFIG_FILENAME = "config.json"

COMPANY_INFO = {
    "company_name": "Jericho Freight",
    "legal_name": "Jericho Freight LLC",
    "address": "2232 Dell Range Blvd, Ste 245-3746",
    "phone": "(307) 218-8686",
    "email": "dispatch@jerichofreight.com",
    "website": "https://jerichofreight.com",
    "dot_number": "3807530",
    "mc_number": "1372791",
}

REP_FILENAME = "rep.json"


def config_file_path() -> str:
    return data_path(CONFIG_FILENAME)


def ensure_config_file() -> str:
    path = config_file_path()
    if os.path.exists(path):
        return path

    example = os.path.join(resource_dir(), "config.example.json")
    if os.path.exists(example):
        shutil.copy(example, path)
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"google_maps_api_key": ""}, f, indent=2)

    return path


def load_config() -> dict:
    path = config_file_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_google_maps_api_key() -> str | None:
    env_key = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
    if env_key:
        return env_key

    path = config_file_path()
    if not os.path.exists(path):
        return None

    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    key = (config.get("google_maps_api_key") or "").strip()
    if not key or key == PLACEHOLDER_KEY:
        return None

    os.environ["GOOGLE_MAPS_API_KEY"] = key
    return key


def maps_api_configured() -> bool:
    return load_google_maps_api_key() is not None


def _rep_path() -> str:
    return data_path(REP_FILENAME)


def load_rep() -> dict:
    path = _rep_path()
    if not os.path.exists(path):
        return {"rep_name": "", "rep_email": ""}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"rep_name": "", "rep_email": ""}
    if not isinstance(data, dict):
        return {"rep_name": "", "rep_email": ""}
    return {
        "rep_name": (data.get("rep_name") or "").strip(),
        "rep_email": (data.get("rep_email") or "").strip(),
    }


def save_rep(rep_name: str, rep_email: str) -> dict:
    payload = {
        "rep_name": (rep_name or "").strip(),
        "rep_email": (rep_email or "").strip(),
    }
    with open(_rep_path(), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def rep_configured() -> bool:
    rep = load_rep()
    return bool(rep["rep_name"] and rep["rep_email"])
