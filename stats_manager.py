"""
Менеджер статистики выполнения SQL-запросов.
Хранит данные в SQLite-файле query_stats.db.
"""
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
    return os.path.join(base, "query_stats.db")


_DB_PATH = _default_db_path()


class StatsManager:
    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._lock    = threading.Lock()
        self._conn: sqlite3.Connection = None
        self._init_db()
        self._open_conn()
        self.rotate()
        self.rotate_by_size()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _open_conn(self):
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _init_db(self):
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS query_stats (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        query_file  TEXT NOT NULL,
                        ts          TEXT NOT NULL,
                        duration_ms REAL NOT NULL,
                        row_count   INTEGER NOT NULL DEFAULT 0,
                        is_error    INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_qf ON query_stats(query_file)")
                conn.commit()

    def rotate(self, max_age_days: int = 90) -> int:
        """Удаляет записи старше max_age_days дней. Возвращает число удалённых строк."""
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=max_age_days)).strftime(
            "%Y-%m-%d %H:%M:%S")
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM query_stats WHERE ts < ?", (cutoff,))
                conn.commit()
                return cur.rowcount

    def rotate_by_size(self, max_size_mb: float = 10.0) -> int:
        """Удаляет старейшие записи, пока файл не уменьшится ниже max_size_mb МБ.
        Возвращает число удалённых строк."""
        if self.get_db_size_kb() * 1024 <= max_size_mb * 1024 * 1024:
            return 0
        with self._lock:
            with self._connect() as conn:
                total = conn.execute("SELECT COUNT(*) FROM query_stats").fetchone()[0]
                if total == 0:
                    return 0
                keep    = max(1, total // 2)
                removed = total - keep
                conn.execute("""
                    DELETE FROM query_stats WHERE id NOT IN (
                        SELECT id FROM query_stats ORDER BY id DESC LIMIT ?
                    )
                """, (keep,))
                conn.commit()
                return removed

    def record(self, query_file: str, duration_ms: float,
               row_count: int = 0, is_error: bool = False):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self._conn.execute(
                "INSERT INTO query_stats (query_file, ts, duration_ms, row_count, is_error)"
                " VALUES (?, ?, ?, ?, ?)",
                (query_file, ts, duration_ms, row_count, int(is_error)),
            )
            self._conn.commit()

    def get_summary(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Возвращает агрегированную статистику по каждому запросу."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT
                        query_file,
                        COUNT(*)                          AS total_runs,
                        SUM(is_error)                     AS error_count,
                        ROUND(AVG(duration_ms), 0)        AS avg_ms,
                        ROUND(MAX(duration_ms), 0)        AS max_ms,
                        ROUND(MIN(duration_ms), 0)        AS min_ms,
                        ROUND(AVG(row_count), 0)          AS avg_rows,
                        MAX(ts)                           AS last_run
                    FROM query_stats
                    GROUP BY query_file
                    ORDER BY avg_ms DESC
                    LIMIT ?
                """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_recent(self, query_file: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Последние N запусков для конкретного файла."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT ts, duration_ms, row_count, is_error
                    FROM query_stats
                    WHERE query_file = ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (query_file, limit)).fetchall()
        return [dict(r) for r in rows]

    def clear(self):
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM query_stats")
                conn.commit()

    def get_db_size_kb(self) -> float:
        try:
            return os.path.getsize(self._db_path) / 1024.0
        except OSError:
            return 0.0
