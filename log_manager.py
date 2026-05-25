import os
import json
import logging
import shutil
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

_ROTATION_MAX_AGE_HOURS = 120


class LogManager:
    def __init__(self, log_file: str = "logs/app.log", settings_file: str = "settings.json"):
        self.log_file = log_file
        self.settings_file = settings_file
        self.logs: List[Dict[str, Any]] = []
        self._flush_timer: Optional[threading.Timer] = None
        self._ensure_log_dir()
        self.load_logs()

    def _ensure_log_dir(self):
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except Exception as e:
                print(f"Ошибка создания директории логов {log_dir}: {e}")

    # ── отложенный flush ──────────────────────────────────────────────────────

    def _schedule_flush(self):
        if self._flush_timer is not None:
            self._flush_timer.cancel()
        self._flush_timer = threading.Timer(5.0, self._flush_logs)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _flush_logs(self):
        self._flush_timer = None
        self.save_logs()

    def _cancel_flush(self):
        if self._flush_timer is not None:
            self._flush_timer.cancel()
            self._flush_timer = None

    def flush(self):
        """Принудительно записывает буфер на диск (вызывать при завершении приложения)."""
        self._cancel_flush()
        self.save_logs()

    # ── основные операции ─────────────────────────────────────────────────────

    def add_log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.logs.append(log_entry)
        self._schedule_flush()
        logging.log(getattr(logging, level, logging.INFO), f"[{timestamp}] {level}: {message}")

    def get_logs(self) -> List[Dict[str, Any]]:
        return self.logs

    def clear_logs(self):
        self._cancel_flush()
        self.logs.clear()
        self.save_logs()

    def save_logs_to_file(self, filename: str):
        with open(filename, 'w', encoding='utf-8') as f:
            for entry in self.logs:
                f.write(f"[{entry['timestamp']}] {entry['level']}: {entry['message']}\n")

    def load_logs(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    self.logs = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                bak = self.log_file + ".bak"
                try:
                    shutil.copy2(self.log_file, bak)
                except Exception:
                    pass
                self.logs = []
                logging.error(f"Ошибка загрузки логов: {e}. Резервная копия сохранена: {bak}")

    def save_logs(self):
        try:
            tmp = self.log_file + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=4)
            os.replace(tmp, self.log_file)
        except OSError as e:
            logging.error(f"Ошибка сохранения логов: {e}")

    # ── ротация ───────────────────────────────────────────────────────────────

    def rotate_old_logs(self, max_age_hours: int = _ROTATION_MAX_AGE_HOURS) -> int:
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        before = len(self.logs)
        kept = []
        for e in self.logs:
            try:
                if datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S") > cutoff:
                    kept.append(e)
            except (ValueError, KeyError):
                kept.append(e)
        self.logs = kept
        removed = before - len(self.logs)
        if removed > 0:
            self._cancel_flush()
            self.save_logs()
        return removed

    def rotate_by_size(self, max_size_mb: float = 100.0) -> int:
        if not self.logs:
            return 0
        max_bytes = int(max_size_mb * 1024 * 1024)
        try:
            file_size = os.path.getsize(self.log_file) if os.path.exists(self.log_file) else 0
        except OSError:
            file_size = 0
        if file_size <= max_bytes:
            return 0
        ratio = max_bytes / file_size * 0.8
        target_count = max(1, int(len(self.logs) * ratio))
        removed = len(self.logs) - target_count
        if removed > 0:
            self.logs = self.logs[-target_count:]
            self._cancel_flush()
            self.save_logs()
        return removed

    def get_log_size_mb(self) -> float:
        try:
            return os.path.getsize(self.log_file) / (1024 * 1024) if os.path.exists(self.log_file) else 0.0
        except OSError:
            return 0.0
