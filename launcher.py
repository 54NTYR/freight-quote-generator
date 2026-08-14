import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request

from desktop_api import DesktopApi
from config import ensure_config_file, load_google_maps_api_key
from paths import data_dir, resource_dir

APP_PORT = 17523
APP_TITLE = "Freight Quote Generator"


def setup_logging() -> None:
    log_file = os.path.join(data_dir(), "app.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8")],
    )


def start_server() -> None:
    from app import app
    from waitress import serve

    serve(app, host="127.0.0.1", port=APP_PORT, threads=4)


def wait_for_server(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.2)
    return False


def icon_path() -> str | None:
    path = os.path.join(resource_dir(), "img", "app-icon.png")
    return path if os.path.exists(path) else None


def open_desktop_window(url: str) -> None:
    import webview

    window_kwargs = {
        "title": APP_TITLE,
        "url": url,
        "width": 1280,
        "height": 860,
        "min_size": (960, 640),
    }
    app_icon = icon_path()
    if app_icon:
        window_kwargs["icon"] = app_icon

    webview.create_window(**window_kwargs, js_api=DesktopApi())
    webview.start()


def main() -> None:
    if getattr(sys, "frozen", False):
        setup_logging()

    ensure_config_file()
    load_google_maps_api_key()
    os.chdir(data_dir())

    url = f"http://127.0.0.1:{APP_PORT}/"
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    if not wait_for_server(url):
        raise RuntimeError("The quote generator server did not start.")

    open_desktop_window(url)


if __name__ == "__main__":
    main()
