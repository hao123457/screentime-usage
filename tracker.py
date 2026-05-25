import threading
import time
from datetime import date
from ctypes import Structure, windll, c_uint, sizeof, byref

import psutil
import win32gui
import win32process

from config import POLL_INTERVAL, IDLE_THRESHOLD
from database import add_usage


class LASTINPUTINFO(Structure):
    _fields_ = [("cbSize", c_uint), ("dwTime", c_uint)]


def _idle_seconds():
    """Return seconds since last user input (keyboard/mouse)."""
    lii = LASTINPUTINFO()
    lii.cbSize = sizeof(LASTINPUTINFO)
    if windll.user32.GetLastInputInfo(byref(lii)):
        return (windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0
    return 0


def _foreground_process_name():
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None, None
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        name = psutil.Process(pid).name()
        title = win32gui.GetWindowText(hwnd)
        return name, title
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None, None


class Tracker:
    def __init__(self):
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        current_proc = None
        current_title = None
        accumulated = 0

        while self._running:
            time.sleep(POLL_INTERVAL)

            idle = _idle_seconds()
            if idle > IDLE_THRESHOLD:
                # flush current session if any
                if accumulated > 0 and current_proc:
                    add_usage(str(date.today()), current_proc, current_title, accumulated)
                    accumulated = 0
                    current_proc = None
                    current_title = None
                continue

            proc_name, win_title = _foreground_process_name()
            if proc_name is None:
                continue

            if proc_name == current_proc:
                accumulated += POLL_INTERVAL
            else:
                # flush previous
                if accumulated > 0 and current_proc:
                    add_usage(str(date.today()), current_proc, current_title, accumulated)
                current_proc = proc_name
                current_title = win_title
                accumulated = POLL_INTERVAL
