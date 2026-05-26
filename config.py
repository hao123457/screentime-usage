import os
import sys

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(os.path.expanduser("~"), ".app_usage_tracker", "usage.db")

POLL_INTERVAL = 3       # seconds between active-window checks
IDLE_THRESHOLD = 300    # 5 minutes idle before pausing tracking
STARTUP_DIR = os.path.join(
    os.getenv("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup"
)
ICON_PATH = os.path.join(BASE_DIR, "testify2.png")
