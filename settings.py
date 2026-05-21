import json
import os
import datetime
import decimal
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
    
    def load_settings(self) -> Dict[str, Any]:
        """Загружает настройки из файла"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        # Настройки по умолчанию
        return {
            "refresh_interval": 180,  # 3 минуты
            "query_intervals": {},      # Интервалы для каждого запроса
            "theme": "dark",
            "color_scheme": "blue",
            "db_display_names": {},       # Отображаемые имена баз данных
            "query_display_names": {}     # Отображаемые имена запросов
        }
    
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
        self.save_settings()
    
    def set_query_interval(self, query_name: str, interval: int):
        """Устанавливает интервал обновления для конкретного запроса"""
        if "query_intervals" not in self.settings:
            self.settings["query_intervals"] = {}
        self.settings["query_intervals"][query_name] = interval
        self.save_settings()
    
    def get_query_interval(self, query_name: str, default: int = 300) -> int:
        """Получает интервал обновления для запроса"""
        return self.settings.get("query_intervals", {}).get(query_name, default)