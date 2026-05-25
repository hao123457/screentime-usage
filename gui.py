import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
import os

from config import STARTUP_DIR
from database import get_daily_summary, get_daily_total, get_available_dates

BAT_NAME = "app_usage_tracker.bat"


def _secs_to_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"


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


class UsageWindow:
    def __init__(self, root, script_path):
        self.root = root
        self.script_path = script_path
        self.current_date = date.today()

        root.title("应用使用时间统计")
        root.geometry("600x450")
        root.resizable(True, True)

        # date bar
        date_frame = ttk.Frame(root)
        date_frame.pack(pady=10)

        ttk.Button(date_frame, text="◀ 前一天", command=self._prev_day).pack(side=tk.LEFT, padx=5)
        self.date_label = tk.Label(date_frame, font=("", 12, "bold"), width=14)
        self.date_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(date_frame, text="后一天 ▶", command=self._next_day).pack(side=tk.LEFT, padx=5)

        # history dropdown
        ttk.Label(date_frame, text="  跳转:").pack(side=tk.LEFT, padx=(20, 5))
        self.history_var = tk.StringVar()
        self.history_combo = ttk.Combobox(date_frame, textvariable=self.history_var, width=12, state="readonly")
        self.history_combo.pack(side=tk.LEFT)
        self.history_combo.bind("<<ComboboxSelected>>", self._on_history_select)

        # table
        table_frame = ttk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("应用名称", "使用时长（秒）", "使用时长")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("应用名称", text="应用名称")
        self.tree.heading("使用时长（秒）", text="时长（秒）")
        self.tree.heading("使用时长", text="使用时长")
        self.tree.column("应用名称", width=280)
        self.tree.column("使用时长（秒）", width=120, anchor=tk.CENTER)
        self.tree.column("使用时长", width=140, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # total label
        self.total_label = tk.Label(root, font=("", 11, "bold"), anchor=tk.W)
        self.total_label.pack(pady=5, padx=10, fill=tk.X)

        # startup checkbox
        self.startup_var = tk.BooleanVar(value=_startup_enabled())
        startup_cb = ttk.Checkbutton(
            root, text="开机自启",
            variable=self.startup_var,
            command=self._toggle_startup
        )
        startup_cb.pack(pady=5)

        self._refresh()

    def _prev_day(self):
        self.current_date -= timedelta(days=1)
        self._refresh()

    def _next_day(self):
        self.current_date += timedelta(days=1)
        self._refresh()

    def _on_history_select(self, _event):
        val = self.history_var.get()
        if val:
            self.current_date = date.fromisoformat(val)
            self._refresh()

    def _refresh(self):
        d = self.current_date
        self.date_label.config(text=str(d))

        # update history dropdown
        dates = get_available_dates()
        self.history_combo["values"] = dates

        # update table
        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = get_daily_summary(str(d))
        for proc, secs in rows:
            self.tree.insert("", tk.END, values=(proc, secs, _secs_to_hms(secs)))

        total = get_daily_total(str(d))
        self.total_label.config(text=f"当日总使用时间: {_secs_to_hms(total)}  ({total} 秒)")

    def _toggle_startup(self):
        _set_startup(self.startup_var.get(), self.script_path)
