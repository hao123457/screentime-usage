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
        name = psutil.Process(pid).name().removesuffix(".exe")
        title = win32gui.GetWindowText(hwnd)
        return name, title
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None, None


class Tracker:
    def __init__(self):
        self._running = False
        self._after_id = None
        self._current_proc = None
        self._current_title = None
        self._accumulated = 0

    def start(self, root):
        self._running = True
        self._current_proc = None
        self._current_title = None
        self._accumulated = 0
        self._schedule(root)

    def stop(self):
        self._running = False
        if self._after_id is not None:
            try:
                # after_cancel may fail if called after the callback fired
                pass  # _poll will check self._running and stop scheduling
            except Exception:
                pass

    def _schedule(self, root):
        if not self._running:
            return
        self._after_id = root.after(POLL_INTERVAL * 1000, lambda: self._poll(root))

    def _poll(self, root):
        if not self._running:
            return

        idle = _idle_seconds()
        if idle > IDLE_THRESHOLD:
            if self._accumulated > 0 and self._current_proc:
                add_usage(str(date.today()), self._current_proc, self._current_title, self._accumulated)
                self._accumulated = 0
                self._current_proc = None
                self._current_title = None
        else:
            proc_name, win_title = _foreground_process_name()
            if proc_name is not None:
                if proc_name == self._current_proc:
                    self._accumulated += POLL_INTERVAL
                else:
                    if self._accumulated > 0 and self._current_proc:
                        add_usage(str(date.today()), self._current_proc, self._current_title, self._accumulated)
                    self._current_proc = proc_name
                    self._current_title = win_title
                    self._accumulated = POLL_INTERVAL

        self._schedule(root)
