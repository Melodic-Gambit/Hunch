import os
import sys
import sqlite3
import datetime
import threading
from typing import List, Dict, Any


def _default_db_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "reminders.db")


_DB_PATH = _default_db_path()


class RemindersManager:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        comment    TEXT NOT NULL,
                        type       TEXT NOT NULL DEFAULT 'once',
                        once_dt    TEXT,
                        daily_hm   TEXT,
                        enabled    INTEGER NOT NULL DEFAULT 1,
                        last_fired TEXT
                    )
                """)
                conn.commit()

    def add(self, comment: str, rtype: str,
            once_dt: str = None, daily_hm: str = None) -> int:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO reminders (comment, type, once_dt, daily_hm)"
                    " VALUES (?, ?, ?, ?)",
                    (comment, rtype, once_dt, daily_hm),
                )
                conn.commit()
                return cur.lastrowid

    def delete(self, reminder_id: int):
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
                conn.commit()

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM reminders ORDER BY id DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def mark_fired(self, reminder_id: int):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE reminders SET last_fired = ? WHERE id = ?",
                    (ts, reminder_id),
                )
                conn.execute(
                    "UPDATE reminders SET enabled = 0"
                    " WHERE id = ? AND type = 'once'",
                    (reminder_id,),
                )
                conn.commit()

    def get_due(self) -> List[Dict[str, Any]]:
        """Returns reminders that are due to fire in the current minute."""
        now = datetime.datetime.now()
        now_str   = now.strftime("%Y-%m-%d %H:%M")
        now_hm    = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")
        result = []
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE enabled = 1"
                ).fetchall()
        for r in rows:
            r = dict(r)
            if r["type"] == "once" and r["once_dt"]:
                if r["once_dt"][:16] == now_str:
                    if not r["last_fired"] or r["last_fired"][:16] != now_str:
                        result.append(r)
            elif r["type"] == "daily" and r["daily_hm"]:
                if r["daily_hm"] == now_hm:
                    if not r["last_fired"] or r["last_fired"][:10] != today_str:
                        result.append(r)
        return result
