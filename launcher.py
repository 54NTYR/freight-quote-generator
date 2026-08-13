import logging
import os
import sys
import threading
import time
import webbrowser

from config import ensure_config_file, load_google_maps_api_key
from paths import data_dir

APP_PORT = 17523


def setup_logging() -> None:
    log_file = os.path.join(data_dir(), "app.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8")],
    )


def open_browser(url: str) -> None:
    time.sleep(1.5)
    webbrowser.open(url)


def main() -> None:
    if getattr(sys, "frozen", False):
        setup_logging()

    ensure_config_file()
    load_google_maps_api_key()
    os.chdir(data_dir())

    url = f"http://127.0.0.1:{APP_PORT}"
    print("Freight Quote Generator")
    print(f"Running at {url}")
    print(f"Config file: {os.path.join(data_dir(), 'config.json')}")
    print("Close this window to stop the app.")

    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    from app import app
    from waitress import serve

    serve(app, host="127.0.0.1", port=APP_PORT, threads=4)


if __name__ == "__main__":
    main()
