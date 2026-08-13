import json
import os
import shutil

from paths import data_path, resource_dir

PLACEHOLDER_KEY = "YOUR_GOOGLE_MAPS_API_KEY_HERE"
CONFIG_FILENAME = "config.json"

COMPANY_INFO = {
    "company_name": "Jericho Freight",
    "phone": "(307) 218-8686",
    "email": "dispatch@jerichofreight.com",
    "website": "https://jerichofreight.com",
    "dot_number": "3807530",
    "mc_number": "1372791",
}


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
