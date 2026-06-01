import json
import os
import datetime
import decimal
import threading
from typing import Dict, Any, Optional


class _SafeEncoder(json.JSONEncoder):
    """Сериализует типы, которые стандартный json не поддерживает."""
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


class SettingsManager:
    def __init__(self, settings_file: str = "settings.json"):
        self.settings_file = settings_file
        self.settings = self.load_settings()
        self._save_timer: Optional[threading.Timer] = None
    
    def load_settings(self) -> Dict[str, Any]:
        """Загружает настройки из файла"""
        defaults: Dict[str, Any] = {
            "refresh_interval": 180,
            "query_intervals": {},
            "theme": "dark",
            "color_scheme": "blue",
            "check_updates": True,
            "db_display_names": {},
            "query_display_names": {},
        }
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                return {**defaults, **loaded}
            except (json.JSONDecodeError, IOError):
                pass
        return defaults
    
    def save_settings(self):
        """Сохраняет настройки в файл"""
        import logging
        tmp = self.settings_file + ".tmp"
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False,
                          cls=_SafeEncoder)
            os.replace(tmp, self.settings_file)
        except OSError as e:
            logging.error(f"Ошибка сохранения настроек: {e}")
            try:
                os.remove(tmp)
            except OSError:
                pass
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Получает значение настройки"""
        return self.settings.get(key, default)
    
    def set_setting(self, key: str, value: Any):
        """Устанавливает значение настройки"""
        self.settings[key] = value
        self._schedule_save()
    
    def set_query_interval(self, query_name: str, interval: int):
        """Устанавливает интервал обновления для конкретного запроса"""
        if "query_intervals" not in self.settings:
            self.settings["query_intervals"] = {}
        self.settings["query_intervals"][query_name] = interval
        self._schedule_save()

    def _schedule_save(self):
        if self._save_timer is not None:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(0.5, self.save_settings)
        self._save_timer.daemon = True
        self._save_timer.start()

    def flush(self):
        """Немедленно сохраняет настройки, отменяя отложенный таймер."""
        if self._save_timer is not None:
            self._save_timer.cancel()
            self._save_timer = None
        self.save_settings()
    
    def get_query_interval(self, query_name: str, default: int = 300) -> int:
        """Получает интервал обновления для запроса"""
        return self.settings.get("query_intervals", {}).get(query_name, default)