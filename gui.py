import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
import hashlib
import os
import subprocess

import psutil
import sv_ttk
import win32con
import win32gui
import win32ui
from PIL import Image, ImageDraw, ImageFont, ImageTk

from config import APP_VERSION, CHANGELOG, HELP_TEXT, STARTUP_DIR, load_settings
from database import (
    get_all_app_names, get_all_process_info,
    get_daily_summary, get_daily_total, get_available_dates,
    get_daily_totals_for_range,
    get_range_summary, get_range_total,
)
from tracker import _friendly_name
from analysis import analyze_local, analyze_with_ai

BAT_NAME = "app_usage_tracker.bat"

# Bar-chart colours — cycle through for top apps
CHART_COLORS = [
    "#4A90D9", "#50B86C", "#F5A623", "#9B59B6",
    "#26A69A", "#EF5350", "#7E57C2", "#42A5F5",
    "#EC407A", "#66BB6A",
]


def _secs_to_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"


def _find_exe_path(friendly_name_str):
    """Find the executable path of a running process whose friendly name matches.

    Iterates all running processes, resolves each to a friendly name using
    the same logic as the tracker, and returns the exe path of the first
    match. Returns None if no matching running process is found.
    """
    for proc in psutil.process_iter(['pid']):
        try:
            friendly = _friendly_name(proc.pid)
            if friendly == friendly_name_str:
                exe = proc.exe()
                if exe and os.path.isfile(exe):
                    return exe
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _startup_bat_path():
    return os.path.join(STARTUP_DIR, BAT_NAME)


def _startup_enabled():
    return os.path.exists(_startup_bat_path())


def _set_startup(enable, script_path):
    bat_path = _startup_bat_path()
    if enable:
        pythonw = os.path.join(os.path.dirname(os.sys.executable), "pythonw.exe")
        with open(bat_path, "w") as f:
            f.write(f'@echo off\nstart "" /B "{pythonw}" "{script_path}"\n')
    else:
        if os.path.exists(bat_path):
            os.remove(bat_path)


# ──────────────────────── icon extraction ────────────────────────

# Caches survive across table refreshes so icons aren't re-extracted
_icon_pil_cache = {}   # exe_path → PIL.Image
_icon_tk_cache = {}    # app_name → ImageTk.PhotoImage (must stay alive)

_DEFAULT_ICON_COLORS = [
    (0x42, 0xA5, 0xF5),  # blue
    (0xEF, 0x53, 0x50),  # red
    (0x66, 0xBB, 0x6A),  # green
    (0xFF, 0xA7, 0x26),  # orange
    (0xAB, 0x47, 0xBC),  # purple
    (0x26, 0xA6, 0x9A),  # teal
    (0xEC, 0x40, 0x7A),  # pink
    (0x78, 0x90, 0x9C),  # blue-grey
]


def _build_process_exe_map():
    """Return {friendly_name: exe_path} for icon lookup.

    Starts with every app ever persisted by the tracker (so historical
    apps get their real icons even when not running), then overlays the
    current live process scan so freshly-installed paths win.
    """
    # Base: every app the tracker has ever seen
    result = get_all_process_info()

    # Overlay: currently running processes (freshest paths)
    for proc in psutil.process_iter(['pid']):
        try:
            friendly = _friendly_name(proc.pid)
            if friendly and friendly not in result:
                exe = proc.exe()
                if exe and os.path.isfile(exe):
                    result[friendly] = exe
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


def _extract_icon_from_exe(exe_path, size=20):
    """Extract the first icon from a Windows .exe and return a PIL Image.

    Uses ExtractIconEx + DrawIconEx to render the icon at *size* pixels.
    Returns None if extraction fails for any reason.
    """
    hSmall, hLarge = [], []
    try:
        hSmall, hLarge = win32gui.ExtractIconEx(exe_path, 0)
    except Exception:
        return None

    # Pick the first available handle
    hIcon = (hSmall or [None])[0] or (hLarge or [None])[0]
    if not hIcon:
        return None

    try:
        hdc = win32gui.GetDC(0)
        dc = win32ui.CreateDCFromHandle(hdc)
        memdc = dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(dc, size, size)
        memdc.SelectObject(bmp)
        win32gui.DrawIconEx(
            memdc.GetHandleOutput(), 0, 0, hIcon,
            size, size, 0, None, win32con.DI_NORMAL,
        )

        bmInfo = bmp.GetInfo()
        bits = bmp.GetBitmapBits(True)
        img = Image.frombuffer(
            "RGBA", (bmInfo["bmWidth"], bmInfo["bmHeight"]),
            bits, "raw", "BGRA", 0, 1,
        ).copy()  # detach from volatile buffer

        memdc.DeleteDC()
        win32gui.ReleaseDC(0, hdc)
        return img
    except Exception:
        return None
    finally:
        # Destroy all extracted icon handles
        for h in hSmall + hLarge:
            if h:
                try:
                    win32gui.DestroyIcon(h)
                except Exception:
                    pass


def _default_app_icon(name, size=20):
    """Build a deterministic coloured icon with the app's initial letter.

    Uses a hash of *name* to pick a stable background colour so the same
    app always gets the same colour.
    """
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    r, g, b = _DEFAULT_ICON_COLORS[h % len(_DEFAULT_ICON_COLORS)]

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # rounded-rect background
    radius = max(size // 5, 2)
    draw.rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=radius, fill=(r, g, b, 255),
    )

    # first letter in white, centered
    letter = name[0].upper() if name else "?"
    try:
        font = ImageFont.truetype("segoeui.ttf", size * 3 // 5)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2, (size - th) / 2 - 1),
        letter, fill=(255, 255, 255, 255), font=font,
    )
    return img


def _get_app_icon(app_name, process_map, size=20):
    """Return a PhotoImage icon for *app_name*, caching at every level."""
    if app_name in _icon_tk_cache:
        return _icon_tk_cache[app_name]

    pil_img = None
    exe_path = process_map.get(app_name)

    if exe_path:
        if exe_path in _icon_pil_cache:
            pil_img = _icon_pil_cache[exe_path]
        else:
            pil_img = _extract_icon_from_exe(exe_path, size)
            if pil_img:
                _icon_pil_cache[exe_path] = pil_img

    if pil_img is None:
        pil_img = _default_app_icon(app_name, size)

    pil_img = pil_img.resize((size, size), Image.LANCZOS)
    photo = ImageTk.PhotoImage(pil_img)
    _icon_tk_cache[app_name] = photo
    return photo


class BarChart(tk.Canvas):
    """Horizontal bar chart drawn on a tkinter Canvas.

    Displays the top N apps from the current data set with coloured bars
    proportional to usage duration.  Supports light/dark themes.
    """

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("height", 220)
        super().__init__(
            parent,
            highlightthickness=0,
            **kwargs,
        )
        self._theme = "light"
        self._font = ("", 9)
        self.bind("<Configure>", lambda _: self._redraw())

        # data cache for resize redraws
        self._data = []
        self._total = 0

    def set_theme(self, theme):
        self._theme = theme
        self._redraw()

    def update_data(self, data, total):
        """Store data and redraw.  *data* is [(name, seconds), …]."""
        self._data = data[:10]  # top 10
        self._total = total
        self._redraw()

    def _redraw(self):
        self.delete("all")
        if not self._data or self._total <= 0:
            return

        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return  # not yet mapped

        # theme colours
        if self._theme == "dark":
            bg = "#1c1c1c"
            text_fg = "#c0c0c0"
        else:
            bg = "#f0f0f0"
            text_fg = "#333333"

        self.configure(bg=bg)

        n = len(self._data)
        bar_area_left = 130   # reserve for name label
        bar_area_right = w - 80  # reserve for percentage label
        bar_area_width = bar_area_right - bar_area_left
        row_h = min((h - 8) // max(n, 1), 20)
        bar_h = max(row_h - 3, 4)

        max_secs = max(s for _, s in self._data)

        for i, (name, secs) in enumerate(self._data):
            y = 4 + i * row_h
            color = CHART_COLORS[i % len(CHART_COLORS)]

            # app name (truncated)
            display_name = name if len(name) <= 14 else name[:13] + "…"
            self.create_text(
                bar_area_left - 6, y + bar_h / 2,
                text=display_name,
                anchor=tk.E,
                fill=text_fg,
                font=self._font,
            )

            # bar
            bar_w = int(bar_area_width * secs / max_secs) if max_secs > 0 else 0
            bar_w = max(bar_w, 2)  # minimum visible sliver
            self.create_rectangle(
                bar_area_left, y,
                bar_area_left + bar_w, y + bar_h,
                fill=color,
                outline="",
            )

            # percentage + duration inside/after bar
            pct = secs / self._total * 100
            label = f"{pct:.1f}%  {_secs_to_hms(secs)}"
            label_x = bar_area_left + bar_w + 4
            if label_x + 120 > w:
                # place inside bar if too wide
                label_x = bar_area_left + bar_w - 8
                anchor = tk.E
                label_fill = "#ffffff"
            else:
                anchor = tk.W
                label_fill = text_fg
            self.create_text(
                label_x, y + bar_h / 2,
                text=label,
                anchor=anchor,
                fill=label_fill,
                font=self._font,
            )


class UsageWindow:
    def __init__(self, root, script_path, tracker):
        self.root = root
        self.script_path = script_path
        self.tracker = tracker
        self.current_date = date.today()
        self._sort_col = "使用时长"
        self._sort_reverse = True

        # view mode: "day", "week", "month"
        self.view_mode = "day"
        # For week/month modes, self.current_date anchors the period
        # and _view_start / _view_end define the inclusive date range.

        # theme
        settings = load_settings()
        self.theme = settings.get("theme", "light")
        sv_ttk.set_theme(self.theme)

        root.title("应用使用时间统计")
        root.geometry("820x620")
        root.minsize(680, 420)
        root.resizable(True, True)

        # ── top bar: view-mode selector + date nav + search + settings ──
        top_bar = ttk.Frame(root)
        top_bar.pack(fill=tk.X, padx=10, pady=(10, 0))

        # view-mode segmented buttons
        mode_frame = ttk.Frame(top_bar)
        mode_frame.pack(side=tk.LEFT)

        self._mode_btns = {}
        for text, mode in [("日", "day"), ("周", "week"), ("月", "month")]:
            btn = ttk.Button(
                mode_frame,
                text=text,
                width=3,
                command=lambda m=mode: self._switch_mode(m),
            )
            btn.pack(side=tk.LEFT, padx=(0, 1))
            self._mode_btns[mode] = btn
        self._update_mode_button_style()

        # date nav
        date_frame = ttk.Frame(top_bar)
        date_frame.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(date_frame, text="◀", width=3, command=self._prev).pack(side=tk.LEFT, padx=1)
        self.date_label = tk.Label(date_frame, font=("", 11, "bold"), width=26, anchor=tk.CENTER)
        self.date_label.pack(side=tk.LEFT, padx=6)
        ttk.Button(date_frame, text="▶", width=3, command=self._next).pack(side=tk.LEFT, padx=1)

        # today / current-period jump
        ttk.Button(date_frame, text="今天", width=4, command=self._go_today).pack(side=tk.LEFT, padx=(6, 0))

        # theme toggle
        theme_text = "🌙" if self.theme == "light" else "☀️"
        self.theme_btn = ttk.Button(date_frame, text=theme_text, command=self._toggle_theme, width=3)
        self.theme_btn.pack(side=tk.LEFT, padx=(6, 0))

        # ── sub bar: history (left) + search & settings (right) ──
        sub_bar = ttk.Frame(root)
        sub_bar.pack(fill=tk.X, padx=10, pady=(5, 0))

        # left: history
        ttk.Label(sub_bar, text="跳转:").pack(side=tk.LEFT)
        self.history_var = tk.StringVar()
        self.history_combo = ttk.Combobox(sub_bar, textvariable=self.history_var, width=14, state="readonly")
        self.history_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.history_combo.bind("<<ComboboxSelected>>", self._on_history_select)

        # right: search + settings
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())

        search_frame = ttk.Frame(sub_bar)
        search_frame.pack(side=tk.RIGHT)
        ttk.Button(search_frame, text="⚙ 设置", command=self._open_settings, width=6).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(search_frame, text="🤖 AI 分析", command=self._open_ai_analysis, width=8).pack(side=tk.RIGHT, padx=(5, 0))
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=22)
        self.search_entry.pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Label(search_frame, text="搜索:").pack(side=tk.RIGHT)

        # ── table ──
        table_frame = ttk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("占比", "使用时长")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="tree headings", height=8)
        # tree column #0: icon + app name
        self.tree.heading("#0", text="应用名称  ⬍", command=lambda: self._on_column_click("应用名称"))
        self.tree.column("#0", width=280, minwidth=150)
        # data columns
        self.tree.heading("占比", text="占比  ⬍", command=lambda: self._on_column_click("占比"))
        self.tree.heading("使用时长", text="使用时长  ▼", command=lambda: self._on_column_click("使用时长"))
        self.tree.column("占比", width=100, anchor=tk.CENTER)
        self.tree.column("使用时长", width=160, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Button-3>", self._on_tree_right_click)

        # ── bar chart ──
        self.chart = BarChart(root, height=210)
        self.chart.pack(fill=tk.X, padx=10, pady=(0, 5))

        # ── total label ──
        self.total_label = tk.Label(root, font=("", 11, "bold"), anchor=tk.W)
        self.total_label.pack(pady=2, padx=10, fill=tk.X)

        # ── startup checkbox ──
        self.startup_var = tk.BooleanVar(value=_startup_enabled())
        startup_cb = ttk.Checkbutton(
            root, text="开机自启",
            variable=self.startup_var,
            command=self._toggle_startup
        )
        startup_cb.pack(pady=5)

        # ── keyboard shortcuts ──
        root.bind("<Left>", lambda _: self._prev())
        root.bind("<Right>", lambda _: self._next())
        root.bind("<Control-d>", lambda _: self._go_today())
        root.bind("<Control-f>", lambda _: self.search_entry.focus_set())
        root.bind("<Control-t>", lambda _: self._toggle_theme())
        root.bind("<Escape>", lambda _: self._clear_search())

        self._refresh()

    # ───────────────────────── view mode ─────────────────────────

    def _switch_mode(self, mode):
        if self.view_mode == mode:
            return
        self.view_mode = mode
        # anchor to today when switching modes
        self.current_date = date.today()
        self._sort_col = "使用时长"
        self._sort_reverse = True
        self._update_mode_button_style()
        self._refresh()

    def _update_mode_button_style(self):
        """Visually indicate which mode button is active."""
        for mode, btn in self._mode_btns.items():
            if mode == self.view_mode:
                btn.state(["pressed"])  # sv_ttk uses "pressed" for active
            else:
                btn.state(["!pressed"])

    @property
    def _view_start(self):
        """First date (inclusive) of the current view period."""
        if self.view_mode == "week":
            return self.current_date - timedelta(days=self.current_date.weekday())
        elif self.view_mode == "month":
            return self.current_date.replace(day=1)
        else:
            return self.current_date

    @property
    def _view_end(self):
        """Last date (inclusive) of the current view period."""
        if self.view_mode == "week":
            return self._view_start + timedelta(days=6)
        elif self.view_mode == "month":
            d = self.current_date
            if d.month == 12:
                return d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
            return d.replace(month=d.month + 1, day=1) - timedelta(days=1)
        else:
            return self.current_date

    # ──────────────────────── navigation ─────────────────────────

    def _prev(self):
        if self.view_mode == "week":
            self.current_date -= timedelta(days=7)
        elif self.view_mode == "month":
            d = self.current_date
            if d.month == 1:
                self.current_date = d.replace(year=d.year - 1, month=12, day=1)
            else:
                self.current_date = d.replace(month=d.month - 1, day=1)
        else:
            self.current_date -= timedelta(days=1)
        self._refresh()

    def _next(self):
        if self.view_mode == "week":
            self.current_date += timedelta(days=7)
        elif self.view_mode == "month":
            d = self.current_date
            if d.month == 12:
                self.current_date = d.replace(year=d.year + 1, month=1, day=1)
            else:
                self.current_date = d.replace(month=d.month + 1, day=1)
        else:
            self.current_date += timedelta(days=1)
        self._refresh()

    def _go_today(self):
        """Jump to today's view period."""
        self.current_date = date.today()
        self._refresh()

    def _clear_search(self):
        self.search_var.set("")

    def _on_history_select(self, _event):
        val = self.history_var.get()
        if val:
            self.current_date = date.fromisoformat(val)
            self.view_mode = "day"
            self._update_mode_button_style()
            self._refresh()

    # ──────────────────────── data loading ────────────────────────

    def _refresh(self):
        start = str(self._view_start)
        end = str(self._view_end)

        # update date label
        if self.view_mode == "week":
            self.date_label.config(text=f"{start}  ~  {end}")
        elif self.view_mode == "month":
            self.date_label.config(text=f"{self.current_date.year}年{self.current_date.month:02d}月")
        else:
            self.date_label.config(text=str(self.current_date))

        # history dropdown (always shows available days)
        dates = get_available_dates()
        self.history_combo["values"] = dates

        # fetch data
        if self.view_mode == "day":
            self._all_rows = get_daily_summary(start)
            self._total = get_daily_total(start)
        else:
            self._all_rows = get_range_summary(start, end)
            self._total = get_range_total(start, end)

        # total label text varies by mode
        mode_label = {"day": "当日", "week": "本周", "month": "本月"}
        self.total_label.config(
            text=f"{mode_label[self.view_mode]}总使用时间: {_secs_to_hms(self._total)}"
        )

        # reset sort to default (duration desc) on data refresh
        self._sort_col = "使用时长"
        self._sort_reverse = True
        self._update_heading_arrows()

        self.search_var.set("")  # triggers _apply_filter via trace

        # update chart
        self.chart.set_theme(self.theme)
        self.chart.update_data(self._all_rows, self._total)

    # ──────────────────────── table display ───────────────────────

    def _apply_filter(self):
        text = self.search_var.get().lower()
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Build process→exe map once per render pass (lazy, cached)
        process_map = _build_process_exe_map()

        for proc, secs in self._all_rows:
            if text and text not in proc.lower():
                continue
            pct = f"{secs / self._total * 100:.1f}%" if self._total > 0 else "—"
            photo = _get_app_icon(proc, process_map)
            self.tree.insert(
                "", tk.END,
                image=photo, text=proc,
                values=(pct, _secs_to_hms(secs)),
            )

    def _on_column_click(self, col):
        """Sort by the clicked column, toggling direction on repeat clicks."""
        if col == self._sort_col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False

        if col == "应用名称":
            key = lambda r: r[0].lower()
        else:
            key = lambda r: r[1]

        self._all_rows.sort(key=key, reverse=self._sort_reverse)
        self._apply_filter()

        self._update_heading_arrows()

    def _update_heading_arrows(self):
        """Sync heading arrow indicators with current sort state."""
        arrows = {"应用名称": "  ⬍", "占比": "  ⬍", "使用时长": "  ⬍"}
        arrows[self._sort_col] = "  ▼" if self._sort_reverse else "  ▲"
        # Map internal sort-col name → tree heading column id
        col_map = {"应用名称": "#0", "占比": "占比", "使用时长": "使用时长"}
        for label, col_id in col_map.items():
            self.tree.heading(col_id, text=label + arrows[label])

    # ──────────────────────── context menu ────────────────────────

    def _on_tree_right_click(self, event):
        """Show context menu on right-click in the Treeview."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label="查看应用位置",
            command=lambda: self._view_app_location(item)
        )
        menu.post(event.x_root, event.y_root)

    def _view_app_location(self, item_id):
        """Open Explorer to show the location of the selected app's executable."""
        app_name = self.tree.item(item_id, "text")
        if not app_name:
            return

        exe_path = _find_exe_path(app_name)
        if exe_path:
            try:
                subprocess.Popen(['explorer', '/select,', exe_path])
            except Exception:
                tk.messagebox.showerror("错误", f"无法打开文件位置:\n{exe_path}")
        else:
            tk.messagebox.showinfo(
                "未找到",
                f"应用 \"{app_name}\" 当前未运行，无法定位其可执行文件路径。"
            )

    # ──────────────────────── theme ───────────────────────────────

    def _toggle_theme(self):
        """Switch between light and dark themes, persist to settings."""
        from config import save_settings
        self.theme = "dark" if self.theme == "light" else "light"
        sv_ttk.set_theme(self.theme)
        self.theme_btn.config(text="☀️" if self.theme == "dark" else "🌙")
        # tk.Label widgets aren't styled by sv_ttk — update manually
        bg = "#1c1c1c" if self.theme == "dark" else "SystemButtonFace"
        fg = "#e0e0e0" if self.theme == "dark" else "black"
        self.date_label.config(bg=bg, fg=fg)
        self.total_label.config(bg=bg, fg=fg)
        # bar chart
        self.chart.set_theme(self.theme)
        # persist
        s = load_settings()
        s["theme"] = self.theme
        save_settings(s)

    # ──────────────────────── startup ─────────────────────────────

    def _toggle_startup(self):
        _set_startup(self.startup_var.get(), self.script_path)

    # ──────────────────────── settings ────────────────────────────

    def _open_settings(self):
        SettingsWindow(self.root, self.tracker, self._refresh)

    def _open_ai_analysis(self):
        AnalysisWindow(self.root, self.view_mode, self.current_date,
                       self.theme)


class SettingsWindow:
    def __init__(self, parent, tracker, on_save_callback):
        self.tracker = tracker
        self.on_save_callback = on_save_callback

        s = load_settings()
        self.result = dict(s)

        win = tk.Toplevel(parent)
        win.title("设置")
        win.geometry("500x420")
        win.minsize(420, 340)
        win.resizable(True, True)
        win.transient(parent)
        win.grab_set()
        self.win = win

        # ── tab container ──
        tab_control = ttk.Notebook(win)
        tab_control.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        # Tab 1: 设置
        tab_settings = ttk.Frame(tab_control, padding=15)
        tab_control.add(tab_settings, text="设置")
        self._build_settings_tab(tab_settings, s)

        # Tab 2: 帮助
        tab_help = ttk.Frame(tab_control, padding=10)
        tab_control.add(tab_help, text="帮助")
        self._build_help_tab(tab_help)

        # Tab 3: 更新日志
        tab_changelog = ttk.Frame(tab_control, padding=10)
        tab_control.add(tab_changelog, text="更新日志")
        self._build_changelog_tab(tab_changelog)

        # Tab 4: 关于
        tab_about = ttk.Frame(tab_control, padding=15)
        tab_control.add(tab_about, text="关于")
        self._build_about_tab(tab_about)


        # ── bottom buttons (persistent across tabs) ──
        ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=(10, 0))
        btn_row = ttk.Frame(win, padding=(10, 10))
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="取消", command=win.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_row, text="保存", command=self._save).pack(side=tk.RIGHT)

    # ── settings tab ──

    def _build_settings_tab(self, parent, s):
        # poll interval
        row1 = ttk.Frame(parent)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="轮询间隔 (秒):").pack(side=tk.LEFT)
        self.poll_var = tk.IntVar(value=s["poll_interval"])
        ttk.Spinbox(row1, from_=1, to=60, textvariable=self.poll_var, width=6).pack(side=tk.RIGHT)

        # idle threshold
        row2 = ttk.Frame(parent)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="空闲阈值 (分钟):").pack(side=tk.LEFT)
        self.idle_var = tk.IntVar(value=s["idle_threshold"] // 60)
        ttk.Spinbox(row2, from_=1, to=60, textvariable=self.idle_var, width=6).pack(side=tk.RIGHT)

        # start minimized
        row3 = ttk.Frame(parent)
        row3.pack(fill=tk.X, pady=3)
        ttk.Label(row3, text="启动时最小化到托盘").pack(side=tk.LEFT)
        self.min_var = tk.BooleanVar(value=s["start_minimized"])
        ttk.Checkbutton(row3, variable=self.min_var).pack(side=tk.RIGHT)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Button(parent, text="导出数据为 CSV...", command=self._export_csv).pack(pady=5)

    # ── help tab ──

    def _build_help_tab(self, parent):
        text = tk.Text(parent, wrap=tk.WORD, borderwidth=0,
                       padx=8, pady=8, font=("", 10))
        text.insert("1.0", HELP_TEXT)
        text.configure(state=tk.DISABLED)  # read-only

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ── changelog tab ──

    def _build_changelog_tab(self, parent):
        text = tk.Text(parent, wrap=tk.WORD, borderwidth=0,
                       padx=8, pady=8, font=("", 10))
        text.tag_configure("version", font=("", 11, "bold"), foreground="#4A90D9")
        text.tag_configure("date", font=("", 9), foreground="#888888")
        text.tag_configure("bullet", lmargin1=20, lmargin2=30, font=("", 10))

        for i, (ver, ver_date, changes) in enumerate(CHANGELOG):
            if i > 0:
                text.insert(tk.END, "\n")
            text.insert(tk.END, f"v{ver}", "version")
            text.insert(tk.END, f"    {ver_date}\n", "date")
            for c in changes:
                text.insert(tk.END, f"• {c}\n", "bullet")

        text.configure(state=tk.DISABLED)  # read-only

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ── about tab ──

    def _build_about_tab(self, parent):
        # App icon / title area
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, pady=(10, 20))

        name_label = tk.Label(title_frame, text="应用使用时间追踪器",
                              font=("", 16, "bold"))
        name_label.pack()

        ver_label = tk.Label(title_frame, text=f"v{APP_VERSION}",
                             font=("", 10), fg="#888888")
        ver_label.pack()

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Info section
        info_frame = ttk.Frame(parent, padding=(10, 5))
        info_frame.pack(fill=tk.X)

        rows = [
            ("技术栈", "Python 3.12 + tkinter + pystray"),
            ("数据存储", "SQLite"),
            ("系统支持", "Windows 10 / 11"),
            ("许可证", "MIT"),
        ]
        for label, value in rows:
            row_frame = ttk.Frame(info_frame)
            row_frame.pack(fill=tk.X, pady=2)
            ttk.Label(row_frame, text=label + "：", font=("", 10, "bold")).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=value, font=("", 10)).pack(side=tk.LEFT, padx=(5, 0))

        else:
            self._ai_endpoint_frame.pack_forget()
            self.ai_key_label.config(text="API Key:")
            self._ai_model_hint.config(text=f"留空则使用: {default_model}")


    # ── actions ──

    def _save(self):
        from config import save_settings
        self.result["poll_interval"] = self.poll_var.get()
        self.result["idle_threshold"] = self.idle_var.get() * 60
        self.result["start_minimized"] = self.min_var.get()
        save_settings(self.result)
        self.tracker.update_settings(self.result["poll_interval"], self.result["idle_threshold"])
        self.win.destroy()
        if self.on_save_callback:
            self.on_save_callback()

    def _export_csv(self):
        from tkinter import filedialog
        from database import export_csv
        path = filedialog.asksaveasfilename(
            parent=self.win,
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            title="导出 CSV",
        )
        if path:
            export_csv(path)


class AnalysisWindow:
    """Popup window showing AI/local usage analysis report."""

    PROVIDERS = ["anthropic", "openai", "deepseek", "ollama", "custom"]
    PROVIDER_LABELS = {
        "anthropic": "Anthropic (Claude)",
        "openai": "OpenAI (GPT)",
        "deepseek": "DeepSeek",
        "ollama": "Ollama (本地)",
        "custom": "自定义兼容",
    }
    CATEGORY_OPTIONS = ["", "工作", "学习", "社交", "娱乐", "游戏", "工具", "其他"]

    def __init__(self, parent, view_mode, anchor_date, theme):
        self.view_mode = view_mode
        self.anchor_date = anchor_date
        self.theme = theme
        self._ai_categories = {}

        s = load_settings()

        win = tk.Toplevel(parent)
        win.title("AI 分析报告")
        win.geometry("600x680")
        win.minsize(480, 500)
        win.resizable(True, True)
        win.transient(parent)
        win.grab_set()
        self.win = win

        # ── AI settings section ──
        ai_frame = ttk.LabelFrame(win, text="AI 设置", padding=10)
        ai_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        # row 0: provider
        row0 = ttk.Frame(ai_frame)
        row0.pack(fill=tk.X, pady=2)
        ttk.Label(row0, text="API 提供商:").pack(side=tk.LEFT)
        provider_val = s.get("api_provider", "anthropic")
        display_val = f"{provider_val} — {self.PROVIDER_LABELS.get(provider_val, provider_val)}"
        self.ai_provider_var = tk.StringVar(value=display_val)
        provider_combo = ttk.Combobox(
            row0, textvariable=self.ai_provider_var,
            values=[f"{v} — {self.PROVIDER_LABELS[v]}" for v in self.PROVIDERS],
            width=24, state="readonly",
        )
        provider_combo.pack(side=tk.RIGHT)
        provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)
        self._provider_combo = provider_combo

        # row 1: API key
        row1 = ttk.Frame(ai_frame)
        row1.pack(fill=tk.X, pady=2)
        self.ai_key_label = ttk.Label(row1, text="API Key:")
        self.ai_key_label.pack(side=tk.LEFT)
        self.ai_api_key_var = tk.StringVar(value=s.get("api_key", ""))
        self.ai_key_entry = ttk.Entry(row1, textvariable=self.ai_api_key_var, width=40, show="*")
        self.ai_key_entry.pack(side=tk.RIGHT)

        ttk.Label(ai_frame, text="留空则仅使用本地分析", font=("", 8)).pack(anchor=tk.E, pady=(0, 3))

        # row 2: model (optional)
        row_model = ttk.Frame(ai_frame)
        row_model.pack(fill=tk.X, pady=2)
        ttk.Label(row_model, text="模型 (可选):").pack(side=tk.LEFT)
        self.ai_model_var = tk.StringVar(value=s.get("api_model", ""))
        ttk.Entry(row_model, textvariable=self.ai_model_var, width=40).pack(side=tk.RIGHT)
        self._ai_model_hint = ttk.Label(ai_frame, text="", font=("", 8))
        self._ai_model_hint.pack(anchor=tk.E, pady=(0, 3))

        # row 3: custom endpoint (hidden unless provider=custom)
        self._ai_endpoint_frame = ttk.Frame(ai_frame)
        ttk.Label(self._ai_endpoint_frame, text="API 端点:").pack(side=tk.LEFT)
        self.ai_endpoint_var = tk.StringVar(value=s.get("api_endpoint", ""))
        ttk.Entry(self._ai_endpoint_frame, textvariable=self.ai_endpoint_var, width=40).pack(side=tk.RIGHT)
        self._endpoint_hint = ttk.Label(ai_frame, text="例如: https://api.openai.com", font=("", 8))

        # ── App categories ──
        cat_lf = ttk.LabelFrame(win, text="应用分类（用于分析报告中分类统计）", padding=8)
        cat_lf.pack(fill=tk.X, padx=10, pady=(8, 0))

        cat_outer = ttk.Frame(cat_lf)
        cat_outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(cat_outer, highlightthickness=0, height=120)
        cat_scrollbar = ttk.Scrollbar(cat_outer, orient=tk.VERTICAL, command=canvas.yview)
        self._cat_scroll_frame = ttk.Frame(canvas)

        self._cat_scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._cat_scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=cat_scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._ai_categories = dict(s.get("app_categories", {}))
        self._ai_cat_vars = {}
        self._build_category_rows()

        # ── period + action buttons ──
        action_frame = ttk.Frame(win, padding=(10, 10, 10, 5))
        action_frame.pack(fill=tk.X)

        ttk.Label(action_frame, text="分析周期:").pack(side=tk.LEFT)
        self.period_var = tk.StringVar(value={"day": "今天", "week": "本周", "month": "本月"}[view_mode])
        period_combo = ttk.Combobox(action_frame, textvariable=self.period_var,
                                    values=["今天", "本周", "本月"], width=6, state="readonly")
        period_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(action_frame, text="生成分析", command=self._run_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="保存设置", command=self._save_ai_settings).pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(action_frame, text="")
        self.status_label.pack(side=tk.RIGHT)

        ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10)

        # ── report text ──
        text_frame = ttk.Frame(win, padding=(10, 5, 10, 10))
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.report = tk.Text(text_frame, wrap=tk.WORD, borderwidth=0,
                              padx=10, pady=10, font=("", 10))
        self.report.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.report.yview)
        self.report.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.report.tag_configure("h1", font=("", 13, "bold"), foreground="#4A90D9")
        self.report.tag_configure("h2", font=("", 11, "bold"))
        self.report.tag_configure("ai", font=("", 10), foreground="#2E7D32",
                                  lmargin1=10, lmargin2=10)
        self.report.tag_configure("hint", font=("", 9), foreground="#888888",
                                  lmargin1=10, lmargin2=10)

        # Apply initial provider visibility
        self._on_provider_change()

        # Auto-generate if API key is configured; otherwise show hint
        if s.get("api_key", ""):
            self._run_analysis()
        else:
            self._show_no_api_key_hint()

    # ── AI settings helpers ──

    def _on_provider_change(self, *_):
        """Show/hide endpoint field and update model hint."""
        provider = self.ai_provider_var.get()
        provider = provider.split(" —")[0] if " —" in provider else provider

        from analysis import _PROVIDER_PRESETS
        default_models = {k: v[1] for k, v in _PROVIDER_PRESETS.items()}
        default_model = default_models.get(provider, "gpt-4o-mini")

        if provider == "custom":
            self._ai_endpoint_frame.pack(fill=tk.X, pady=2)
            self._endpoint_hint.pack(anchor=tk.E, pady=(0, 3))
            self.ai_key_label.config(text="API Key:")
            self._ai_model_hint.config(text="留空则使用: gpt-4o-mini")
        elif provider == "ollama":
            self._ai_endpoint_frame.pack_forget()
            self._endpoint_hint.pack_forget()
            self.ai_key_label.config(text="API Key (可选):")
            self._ai_model_hint.config(text=f"留空则使用: {default_model}")
        else:
            self._ai_endpoint_frame.pack_forget()
            self._endpoint_hint.pack_forget()
            self.ai_key_label.config(text="API Key:")
            self._ai_model_hint.config(text=f"留空则使用: {default_model}")

    def _on_category_change(self, app_name, var):
        val = var.get()
        if val:
            self._ai_categories[app_name] = val
        else:
            self._ai_categories.pop(app_name, None)

    def _build_category_rows(self):
        for w in self._cat_scroll_frame.winfo_children():
            w.destroy()
        self._ai_cat_vars.clear()
        for app_name in get_all_app_names():
            row = ttk.Frame(self._cat_scroll_frame)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=app_name, width=22, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value=self._ai_categories.get(app_name, ""))
            self._ai_cat_vars[app_name] = var
            combo = ttk.Combobox(row, textvariable=var, values=self.CATEGORY_OPTIONS, width=6, state="readonly")
            combo.pack(side=tk.RIGHT)
            combo.bind("<<ComboboxSelected>>",
                       lambda e, n=app_name, v=var: self._on_category_change(n, v))

    def _get_provider_raw(self):
        provider_raw = self.ai_provider_var.get()
        return provider_raw.split(" —")[0] if " —" in provider_raw else provider_raw

    def _save_ai_settings(self):
        """Save AI settings to config without closing the window."""
        from config import save_settings
        s = load_settings()
        s["api_key"] = self.ai_api_key_var.get()
        s["api_provider"] = self._get_provider_raw()
        s["api_endpoint"] = self.ai_endpoint_var.get()
        s["api_model"] = self.ai_model_var.get()
        s["app_categories"] = self._ai_categories
        save_settings(s)
        self.status_label.config(text="设置已保存 ✓")

    # ── analysis ──

    def _show_no_api_key_hint(self):
        self.report.configure(state=tk.NORMAL)
        self.report.delete("1.0", tk.END)
        self.report.insert(tk.END,
            "💡 提示：在上方 AI 设置中配置 API Key，点击「保存设置」后再点击「生成分析」，即可解锁 AI 深度分析。",
            "hint")
        self.report.configure(state=tk.DISABLED)
        self.status_label.config(text="未配置 API Key")

    def _run_analysis(self):
        self.report.configure(state=tk.NORMAL)
        self.report.delete("1.0", tk.END)
        self.status_label.config(text="分析中...")

        # Reload settings (may have been saved since window opened)
        from config import load_settings
        settings = load_settings()

        # Map selected period to actual date range
        period_map = {"今天": "day", "本周": "week", "本月": "month"}
        mode = period_map[self.period_var.get()]

        today = date.today()
        if mode == "day":
            cur_start = cur_end = today
            prev_start = prev_end = today - timedelta(days=1)
            period_label = f"今天 ({today})"
            prev_label = "昨天"
        elif mode == "week":
            weekday = today.weekday()
            cur_start = today - timedelta(days=weekday)
            cur_end = cur_start + timedelta(days=6)
            prev_start = cur_start - timedelta(days=7)
            prev_end = cur_start - timedelta(days=1)
            period_label = f"本周 ({cur_start} ~ {cur_end})"
            prev_label = "上周"
        else:
            cur_start = today.replace(day=1)
            if today.month == 12:
                cur_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                cur_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            prev_start = (cur_start - timedelta(days=1)).replace(day=1)
            prev_end = cur_start - timedelta(days=1)
            period_label = f"本月 ({today.year}年{today.month}月)"
            prev_label = "上月"

        # Fetch data
        current = get_range_summary(str(cur_start), str(cur_end))
        previous = get_range_summary(str(prev_start), str(prev_end))
        daily_totals = get_daily_totals_for_range(
            str(today - timedelta(days=6)), str(today)
        )

        categories = settings.get("app_categories", {})

        data = {
            "current": current,
            "previous": previous,
            "daily_totals": daily_totals,
            "categories": categories,
        }

        # ── Local analysis (always) ──
        self.report.insert(tk.END, "本地分析报告", "h1")
        self.report.insert(tk.END, "\n\n")
        local_report = analyze_local(data, period_label)
        self.report.insert(tk.END, local_report)

        # ── AI analysis (if API key configured) ──
        api_key = settings.get("api_key", "")
        if api_key:
            self.report.insert(tk.END, "\n\n")
            self.report.insert(tk.END, "🤖 AI 洞察", "h1")
            self.report.insert(tk.END, "\n\n")

            provider = settings.get("api_provider", "anthropic")
            endpoint = settings.get("api_endpoint", "")
            model = settings.get("api_model", "")

            try:
                ai_result = analyze_with_ai(
                    data, period_label, api_key,
                    provider=provider, endpoint=endpoint, model=model,
                )
                if ai_result:
                    self.report.insert(tk.END, ai_result, "ai")
                    self.status_label.config(text="分析完成 ✓")
                else:
                    self.report.insert(tk.END, "AI 分析请求失败，请检查网络连接和 API Key。", "hint")
                    self.status_label.config(text="AI 请求失败")
            except Exception as e:
                self.report.insert(tk.END, f"AI 分析出错: {e}", "hint")
                self.status_label.config(text="AI 出错")
            finally:
                self.report.configure(state=tk.DISABLED)
        else:
            self.report.insert(tk.END, "\n\n")
            self.report.insert(tk.END,
                "💡 提示：在上方 AI 设置中配置 API Key，点击「保存设置」后再点击「生成分析」，即可解锁 AI 深度分析。",
                "hint")
            self.status_label.config(text="本地分析完成 ✓")
            self.report.configure(state=tk.DISABLED)
