import os
import sys

APP_NAME = "FreightQuoteGenerator"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_dir() -> str:
    """Read-only bundled assets (templates, static, default configs)."""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def data_dir() -> str:
    """Writable user data directory (quote counter, templates, config)."""
    if is_frozen():
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return base


def data_path(filename: str) -> str:
    return os.path.join(data_dir(), filename)
