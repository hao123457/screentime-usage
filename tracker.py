import os
from datetime import date
from ctypes import Structure, windll, c_uint, sizeof, byref
from functools import lru_cache

import psutil
import win32api
import win32gui
import win32process

from config import load_settings, get_friendly_name
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


@lru_cache(maxsize=256)
def _get_file_description(exe_path):
    """Extract FileDescription from a Windows executable's version info.

    Returns the human-readable description string (e.g. "Microsoft Edge",
    "Visual Studio Code"), or None if unavailable.
    """
    if not exe_path or not os.path.isfile(exe_path):
        return None
    try:
        translations = win32api.GetFileVersionInfo(
            exe_path, r"\VarFileInfo\Translation"
        )
        if not translations:
            return None
        lang, codepage = translations[0]
        subblock = f"\\StringFileInfo\\{lang:04X}{codepage:04X}\\FileDescription"
        return win32api.GetFileVersionInfo(exe_path, subblock).strip()
    except Exception:
        return None


def _friendly_name(pid):
    """Resolve a PID to a human-friendly application name.

    Fallback chain:
      1. FileDescription from the exe's version info (same as Task Manager)
      2. Static PROCESS_NAME_MAP lookup
      3. Process name stripped of .exe
    """
    try:
        proc = psutil.Process(pid)
        exe_path = proc.exe()
        raw_name = proc.name().removesuffix(".exe")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    # 1. Prefer FileDescription from exe version info
    if exe_path:
        desc = _get_file_description(exe_path)
        if desc:
            return desc

    # 2. Fall back to static mapping (for system processes lacking version info)
    friendly = get_friendly_name(raw_name)
    if friendly != raw_name:
        return friendly

    # 3. Return raw process name
    return raw_name


def _foreground_process_name():
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None, None
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        title = win32gui.GetWindowText(hwnd)
        name = _friendly_name(pid) or title or "Unknown"
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
        s = load_settings()
        self.poll_interval = s["poll_interval"]
        self.idle_threshold = s["idle_threshold"]

    def start(self, root):
        self._running = True
        self._current_proc = None
        self._current_title = None
        self._accumulated = 0
        self._schedule(root)

    def stop(self):
        self._running = False

    def update_settings(self, poll_interval, idle_threshold):
        self.poll_interval = poll_interval
        self.idle_threshold = idle_threshold

    def _schedule(self, root):
        if not self._running:
            return
        self._after_id = root.after(self.poll_interval * 1000, lambda: self._poll(root))

    def _poll(self, root):
        if not self._running:
            return

        idle = _idle_seconds()
        if idle > self.idle_threshold:
            if self._accumulated > 0 and self._current_proc:
                add_usage(str(date.today()), self._current_proc, self._current_title, self._accumulated)
                self._accumulated = 0
                self._current_proc = None
                self._current_title = None
        else:
            proc_name, win_title = _foreground_process_name()
            if proc_name is not None:
                if proc_name == self._current_proc:
                    self._accumulated += self.poll_interval
                else:
                    if self._accumulated > 0 and self._current_proc:
                        add_usage(str(date.today()), self._current_proc, self._current_title, self._accumulated)
                    self._current_proc = proc_name
                    self._current_title = win_title
                    self._accumulated = self.poll_interval

        self._schedule(root)
