import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

_ROTATION_MAX_AGE_HOURS = 120


class LogManager:
    def __init__(self, log_file: str = "logs/app.log", settings_file: str = "settings.json"):
        self.log_file = log_file
        self.settings_file = settings_file
        self.logs: List[Dict[str, Any]] = []
        self._ensure_log_dir()
        self.load_logs()
        
    def _ensure_log_dir(self):
        """Создает директорию для логов, если её нет"""
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except Exception as e:
                print(f"Ошибка создания директории логов {log_dir}: {e}")

    def add_log(self, message: str, level: str = "INFO"):
        """Добавляет запись в лог"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.logs.append(log_entry)
        self.save_logs()
        logging.log(getattr(logging, level, logging.INFO), f"[{timestamp}] {level}: {message}")

    def get_logs(self) -> List[Dict[str, Any]]:
        """Возвращает все логи"""
        return self.logs

    def clear_logs(self):
        """Очищает все логи"""
        self.logs.clear()
        self.save_logs()

    def save_logs_to_file(self, filename: str):
        """Сохраняет логи в файл"""
        with open(filename, 'w', encoding='utf-8') as f:
            for entry in self.logs:
                f.write(f"[{entry['timestamp']}] {entry['level']}: {entry['message']}\n")

    def load_logs(self):
        """Загружает логи из файла при запуске"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    self.logs = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.add_log(f"Ошибка загрузки логов: {e}", "ERROR")

    def save_logs(self):
        """Сохраняет логи в файл"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logging.error(f"Ошибка сохранения логов: {e}")

    def rotate_old_logs(self, max_age_hours: int = _ROTATION_MAX_AGE_HOURS) -> int:
        """Удаляет записи старше max_age_hours. Возвращает количество удалённых записей."""
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
            self.save_logs()
        return removed

    def rotate_by_size(self, max_size_mb: float = 100.0) -> int:
        """Удаляет самые старые записи, пока файл не уменьшится ниже max_size_mb МБ.
        Возвращает количество удалённых записей."""
        if not self.logs:
            return 0
        max_bytes = int(max_size_mb * 1024 * 1024)
        try:
            file_size = os.path.getsize(self.log_file) if os.path.exists(self.log_file) else 0
        except OSError:
            file_size = 0
        if file_size <= max_bytes:
            return 0
        # Оставляем долю записей пропорционально лимиту (с запасом 20%)
        ratio = max_bytes / file_size * 0.8
        target_count = max(1, int(len(self.logs) * ratio))
        removed = len(self.logs) - target_count
        if removed > 0:
            self.logs = self.logs[-target_count:]
            self.save_logs()
        return removed

    def get_log_size_mb(self) -> float:
        """Возвращает размер файла логов в МБ."""
        try:
            return os.path.getsize(self.log_file) / (1024 * 1024) if os.path.exists(self.log_file) else 0.0
        except OSError:
            return 0.0