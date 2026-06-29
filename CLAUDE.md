# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: App Usage Tracker (`app_usage_tracker/`)

A Windows desktop application time tracker. Runs in the background (system tray), polls the active foreground window every 3 seconds, logs per-app usage duration to a local SQLite database, and provides a tkinter GUI for viewing daily statistics with date navigation.

### Build & Run

No build system. Run directly with Python 3.12:

```bash
pip install -r requirements.txt
python app_usage_tracker/main.py
```

To build a standalone exe:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name AppUsageTracker app_usage_tracker/main.py
```

### Architecture

Entry point: `main.py` → initializes DB, starts the tracker thread, creates the tkinter root + GUI + system tray.

Module responsibility:

- **`main.py`** — Entry point. Wires together tracker, GUI, and tray icon. Hides the root window on startup; tray left-click/right-click→"open" shows it via `root.deiconify()`. Close button hides to tray (`WM_DELETE_WINDOW` → `root.withdraw()`), does not exit.
- **`tracker.py`** — Daemon thread. Every 3s, polls the foreground window via `win32gui.GetForegroundWindow()` + `psutil.Process(pid).name()`. Accumulates seconds per process name. Flushes a session to `add_usage()` when the user switches apps or goes idle. Idle detection via `GetLastInputInfo` — if no keyboard/mouse input for 5 minutes, the current session is flushed and tracking pauses until input resumes.
- **`database.py`** — SQLite layer with thread-local connections (`threading.local()`). Schema: `usage_logs(id, date, process_name, window_title, duration_seconds, recorded_at)`. Index on `date`. Key queries: `add_usage()`, `get_daily_summary(date)` returns `(process_name, total_seconds)` grouped/sorted desc, `get_daily_total(date)`, `get_available_dates()`.
- **`gui.py`** — tkinter `UsageWindow` class. Date navigation (prev/next day buttons, history dropdown combobox). Treeview table showing app name + duration (seconds + formatted h/m/s). Daily total label. Startup checkbox (writes/removes a `.bat` shortcut in the Windows Startup folder pointing to `pythonw.exe`).
- **`tray_icon.py`** — System tray via `pystray`. Loads `app.ico` from `ICON_PATH`, crops to square, resizes to 64×64 for the tray icon. Menu: 打开统计面板 (default/left-click), 设置..., 退出. Runs on a daemon thread (`tray.run()`). Dependencies: `pystray`, `PIL` (Pillow).
- **`config.py`** — Constants and settings. `DB_PATH` / `SETTINGS_PATH` under `~/.app_usage_tracker/`. `ICON_PATH` = `app.ico` alongside source. Settings persisted as JSON: `poll_interval`, `idle_threshold`, `start_minimized`, `theme`, `api_key`, `api_provider`, `api_endpoint`, `api_model`, `app_categories`. Functions: `load_settings()`, `save_settings()`, `get_friendly_name()`.

### Key details

- **Idle handling**: When idle > 5 min, the tracker flushes the current accumulated session to the DB and resets. On resume, a new session starts with the foreground app. This means crossing an idle boundary splits one app's usage into multiple rows.
- **Sub-second rounding**: `add_usage()` discards sessions < 1 second. All durations are integer seconds.
- **Timezone**: Uses `date.today()` (local system date). No UTC handling — usage crossing midnight is logged under the date when the session was flushed, which may be off by one day for sessions spanning midnight.
- **Thread safety**: DB connections are thread-local. The tracker thread and GUI thread each get their own SQLite connection. Writes and reads on different connections are safe with SQLite's WAL mode (default in Python 3.12's sqlite3), but no explicit WAL pragma is set.
- **`test.py`** at the repo root is unrelated scaffolding (`print("hello")`). Not part of the tracker.
- **Dependencies** (actual, from imports): `psutil`, `pywin32` (`win32gui`, `win32process`, `win32con`, `win32api`, `win32ui`), `pystray`, `Pillow` (`PIL`), `sv_ttk`. Built-in: `tkinter`, `sqlite3`, `ctypes`, `threading`, `hashlib`.
- **Startup mechanism**: The "boot on startup" checkbox creates `app_usage_tracker.bat` in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`. The bat invokes `pythonw.exe` (no console window) with the absolute path to `main.py`. Removal deletes the bat file.
- **Window management**: The root tkinter window is created hidden (`root.withdraw()` before `mainloop`). Tray left-click or menu "open" calls `root.deiconify()`. The window close button (X) hides to tray rather than exiting. Actual exit only via tray right-click → "退出".
- **Settings UI**: Settings window accessible via tray menu "设置..." or the ⚙ button in the main window. Supports configuring poll interval, idle threshold, start-minimized toggle, and CSV export. Settings persisted to `~/.app_usage_tracker/settings.json`.
- **AI Analysis**: Analysis window (🤖 AI 分析 button) provides local analysis reports. With an API key configured, supports AI-powered deep analysis via Anthropic, OpenAI, DeepSeek, Ollama, or custom OpenAI-compatible endpoints.
- **Window icon (taskbar) — critical ordering**: On Windows, the taskbar icon requires TWO things: (1) `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("hao.app_usage_tracker.v1")` called **BEFORE** `tk.Tk()` — this separates the window from `python.exe` in the taskbar; (2) `root.iconbitmap()` called **immediately after** `tk.Tk()`, before any widgets are created — this sets the window-class icon that the taskbar reads. `root.iconphoto()` alone only sets the title-bar / Alt+Tab icon, not the taskbar icon. If `iconbitmap` is called after widgets are packed, the taskbar shows the default Python icon.
