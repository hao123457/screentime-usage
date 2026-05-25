import sqlite3
import threading
from config import DB_PATH

_local = threading.local()


def _conn():
    if not hasattr(_local, "conn") or _local.conn is None:
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
