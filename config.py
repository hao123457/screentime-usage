import os
import sys
import json

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".app_usage_tracker")
DB_PATH = os.path.join(CONFIG_DIR, "usage.db")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")

STARTUP_DIR = os.path.join(
    os.getenv("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup"
)
ICON_PATH = os.path.join(BASE_DIR, "testify2.png")

_DEFAULTS = {
    "poll_interval": 3,
    "idle_threshold": 300,
    "start_minimized": False,
}


def load_settings():
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return {k: data.get(k, v) for k, v in _DEFAULTS.items()}


def save_settings(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump({k: data[k] for k in _DEFAULTS}, f, indent=2)


_settings = load_settings()
POLL_INTERVAL = _settings["poll_interval"]
IDLE_THRESHOLD = _settings["idle_threshold"]
START_MINIMIZED = _settings["start_minimized"]
