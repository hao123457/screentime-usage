import sqlite3
import threading
import os
from config import DB_PATH

_local = threading.local()

# Path of old database (was in app directory) — checked once for migration
_OLD_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "usage.db"
)


def _conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH)
    return _local.conn


def init_db():
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            process_name TEXT NOT NULL,
            window_title TEXT,
            duration_seconds INTEGER NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_date ON usage_logs(date)
    """)
    c.commit()
    _migrate_old_db(c)


def _migrate_old_db(conn):
    """Copy data from old DB location to new unified location, one-time."""
    if not os.path.exists(_OLD_DB_PATH):
        return
    if _OLD_DB_PATH == DB_PATH:
        return

    try:
        old_conn = sqlite3.connect(_OLD_DB_PATH)
        rows = old_conn.execute(
            "SELECT id, date, process_name, window_title, duration_seconds, recorded_at FROM usage_logs"
        ).fetchall()
        old_conn.close()
        conn.executemany(
            "INSERT OR IGNORE INTO usage_logs (id, date, process_name, window_title, duration_seconds, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        os.rename(_OLD_DB_PATH, _OLD_DB_PATH + ".migrated")
    except Exception:
        pass


def add_usage(date, process_name, window_title, duration_seconds):
    if duration_seconds < 1:
        return
    c = _conn()
    c.execute(
        "INSERT INTO usage_logs (date, process_name, window_title, duration_seconds) VALUES (?, ?, ?, ?)",
        (date, process_name, window_title, duration_seconds),
    )
    c.commit()


def get_daily_summary(date):
    c = _conn()
    rows = c.execute(
        "SELECT process_name, SUM(duration_seconds) FROM usage_logs WHERE date = ? GROUP BY process_name ORDER BY SUM(duration_seconds) DESC",
        (date,),
    ).fetchall()
    return rows


def get_daily_total(date):
    c = _conn()
    row = c.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM usage_logs WHERE date = ?",
        (date,),
    ).fetchone()
    return row[0]


def get_available_dates():
    c = _conn()
    rows = c.execute(
        "SELECT DISTINCT date FROM usage_logs ORDER BY date DESC"
    ).fetchall()
    return [r[0] for r in rows]


def export_csv(filepath):
    import csv
    c = _conn()
    rows = c.execute(
        "SELECT date, process_name, window_title, duration_seconds, recorded_at FROM usage_logs ORDER BY date DESC, recorded_at DESC"
    )
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["日期", "应用名称", "窗口标题", "时长(秒)", "记录时间"])
        w.writerows(rows)
