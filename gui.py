import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
import os

from config import STARTUP_DIR, load_settings
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
    def __init__(self, root, script_path, tracker):
        self.root = root
        self.script_path = script_path
        self.tracker = tracker
        self.current_date = date.today()

        root.title("应用使用时间统计")
        root.geometry("600x450")
        root.resizable(True, True)

        # top bar: date nav (left) + search (right)
        top_bar = ttk.Frame(root)
        top_bar.pack(fill=tk.X, padx=10, pady=(10, 0))

        date_frame = ttk.Frame(top_bar)
        date_frame.pack(side=tk.LEFT)

        ttk.Button(date_frame, text="◀ 前一天", command=self._prev_day).pack(side=tk.LEFT, padx=5)
        self.date_label = tk.Label(date_frame, font=("", 12, "bold"), width=14)
        self.date_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(date_frame, text="后一天 ▶", command=self._next_day).pack(side=tk.LEFT, padx=5)

        search_frame = ttk.Frame(top_bar)
        search_frame.pack(side=tk.RIGHT)
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=18)
        self.search_entry.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(search_frame, text="设置", command=self._open_settings).pack(side=tk.LEFT, padx=(10, 0))

        # history dropdown
        sub_bar = ttk.Frame(root)
        sub_bar.pack(fill=tk.X, padx=10, pady=(5, 0))
        ttk.Label(sub_bar, text="跳转:").pack(side=tk.LEFT)
        self.history_var = tk.StringVar()
        self.history_combo = ttk.Combobox(sub_bar, textvariable=self.history_var, width=14, state="readonly")
        self.history_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.history_combo.bind("<<ComboboxSelected>>", self._on_history_select)

        # table
        table_frame = ttk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("应用名称", "占比", "使用时长")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("应用名称", text="应用名称")
        self.tree.heading("占比", text="占比")
        self.tree.heading("使用时长", text="使用时长")
        self.tree.column("应用名称", width=280)
        self.tree.column("占比", width=100, anchor=tk.CENTER)
        self.tree.column("使用时长", width=160, anchor=tk.CENTER)

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
        self._all_rows = get_daily_summary(str(d))
        self._total = get_daily_total(str(d))
        self.search_var.set("")
        self.total_label.config(text=f"当日总使用时间: {_secs_to_hms(self._total)}")

    def _apply_filter(self):
        text = self.search_var.get().lower()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for proc, secs in self._all_rows:
            if text and text not in proc.lower():
                continue
            pct = f"{secs / self._total * 100:.1f}%" if self._total > 0 else "—"
            self.tree.insert("", tk.END, values=(proc, pct, _secs_to_hms(secs)))

    def _toggle_startup(self):
        _set_startup(self.startup_var.get(), self.script_path)

    def _open_settings(self):
        SettingsWindow(self.root, self.tracker, self._refresh)


class SettingsWindow:
    def __init__(self, parent, tracker, on_save_callback):
        self.tracker = tracker
        self.on_save_callback = on_save_callback

        s = load_settings()
        self.result = dict(s)

        win = tk.Toplevel(parent)
        win.title("设置")
        win.geometry("360x280")
        win.resizable(False, False)
        win.transient(parent)
        win.grab_set()
        self.win = win

        frame = ttk.Frame(win, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # poll interval
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="轮询间隔 (秒):").pack(side=tk.LEFT)
        self.poll_var = tk.IntVar(value=s["poll_interval"])
        ttk.Spinbox(row1, from_=1, to=60, textvariable=self.poll_var, width=6).pack(side=tk.RIGHT)

        # idle threshold
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="空闲阈值 (分钟):").pack(side=tk.LEFT)
        self.idle_var = tk.IntVar(value=s["idle_threshold"] // 60)
        ttk.Spinbox(row2, from_=1, to=60, textvariable=self.idle_var, width=6).pack(side=tk.RIGHT)

        # start minimized
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=3)
        ttk.Label(row3, text="启动时最小化到托盘").pack(side=tk.LEFT)
        self.min_var = tk.BooleanVar(value=s["start_minimized"])
        ttk.Checkbutton(row3, variable=self.min_var).pack(side=tk.RIGHT)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # CSV export
        ttk.Button(frame, text="导出数据为 CSV...", command=self._export_csv).pack(pady=5)

        # save / cancel
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(20, 0))
        ttk.Button(btn_row, text="取消", command=win.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_row, text="保存", command=self._save).pack(side=tk.RIGHT)

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
