import json
import logging
import os
import shutil
import sys
import threading
import time
import webbrowser

from paths import data_dir, data_path, resource_dir

APP_PORT = 17523


def setup_logging() -> None:
    log_file = os.path.join(data_dir(), "app.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8")],
    )


def ensure_user_data() -> None:
    config_file = data_path("config.json")
    if not os.path.exists(config_file):
        example = os.path.join(resource_dir(), "config.example.json")
        if os.path.exists(example):
            shutil.copy(example, config_file)
        else:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({"google_maps_api_key": ""}, f, indent=2)

    templates_file = data_path("pricing_templates.json")
    if not os.path.exists(templates_file):
        bundled = os.path.join(resource_dir(), "pricing_templates.json")
        if os.path.exists(bundled):
            shutil.copy(bundled, templates_file)
        else:
            with open(templates_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)


def load_api_key() -> None:
    config_file = data_path("config.json")
    if not os.path.exists(config_file):
        return

    try:
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    api_key = (config.get("google_maps_api_key") or "").strip()
    if api_key and api_key != "YOUR_GOOGLE_MAPS_API_KEY_HERE":
        os.environ["GOOGLE_MAPS_API_KEY"] = api_key


def open_browser(url: str) -> None:
    time.sleep(1.5)
    webbrowser.open(url)


def main() -> None:
    if getattr(sys, "frozen", False):
        setup_logging()

    ensure_user_data()
    load_api_key()
    os.chdir(data_dir())

    url = f"http://127.0.0.1:{APP_PORT}"
    print("Freight Quote Generator")
    print(f"Running at {url}")
    print(f"User data folder: {data_dir()}")
    print("Close this window to stop the app.")

    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    from app import app
    from waitress import serve

    serve(app, host="127.0.0.1", port=APP_PORT, threads=4)


if __name__ == "__main__":
    main()
