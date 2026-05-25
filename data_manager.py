import os
import re
import json
from typing import List, Dict, Any, Optional


class DataManager:
    def __init__(self, config_dir: str = "config", queries_dir: str = "queries", settings_file: str = "settings.json"):
        self.config_dir = config_dir
        self.queries_dir = queries_dir
        self.settings_file = settings_file
        self.db_names: Dict[str, str] = {}  # internal_name -> display_name
        self.query_names: Dict[str, str] = {}  # internal_name -> display_name
        self.load_names()
        
        # Убедимся, что директории существуют
        self._ensure_directory(config_dir)
        self._ensure_directory(queries_dir)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Заменяет символы, недопустимые в именах файлов Windows."""
        return re.sub(r'[\\/*?:"<>|]', '_', name)

    def _ensure_directory(self, directory: str):
        """Создаёт директорию, если её не существует"""
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                raise RuntimeError(f"Не удалось создать директорию {directory}: {e}")

    def load_names(self):
        """Загружает отображаемые имена из настроек"""
        settings = self._load_settings()
        self.db_names = settings.get("db_display_names", {})
        self.query_names = settings.get("query_display_names", {})

    def _load_settings(self) -> Dict[str, Any]:
        """Загружает настройки из файла"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_settings(self, settings: Dict[str, Any]):
        """Сохраняет настройки в файл"""
        tmp = self.settings_file + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        os.replace(tmp, self.settings_file)

    def get_db_display_name(self, internal_name: str) -> str:
        """Возвращает отображаемое имя для базы данных"""
        if not internal_name.endswith('.json'):
            internal_name += '.json'
        return self.db_names.get(internal_name, internal_name.replace('.json', ''))

    def set_db_display_name(self, internal_name: str, display_name: str):
        """Устанавливает отображаемое имя для базы данных"""
        if not internal_name.endswith('.json'):
            internal_name += '.json'
        self.db_names[internal_name] = display_name
        settings = self._load_settings()
        settings["db_display_names"] = self.db_names
        self._save_settings(settings)

    def delete_db_name(self, internal_name: str):
        """Удаляет отображаемое имя базы данных"""
        if not internal_name.endswith('.json'):
            internal_name += '.json'
        if internal_name in self.db_names:
            del self.db_names[internal_name]
            settings = self._load_settings()
            settings["db_display_names"] = self.db_names
            self._save_settings(settings)

    def get_query_display_name(self, internal_name: str) -> str:
        """Возвращает отображаемое имя для запроса"""
        if not internal_name.endswith('.sql'):
            internal_name += '.sql'
        return self.query_names.get(internal_name, internal_name.replace('.sql', ''))

    def set_query_display_name(self, internal_name: str, display_name: str):
        """Устанавливает отображаемое имя для запроса"""
        if not internal_name.endswith('.sql'):
            internal_name += '.sql'
        self.query_names[internal_name] = display_name
        settings = self._load_settings()
        settings["query_display_names"] = self.query_names
        self._save_settings(settings)

    def delete_query_name(self, internal_name: str):
        """Удаляет отображаемое имя запроса"""
        if not internal_name.endswith('.sql'):
            internal_name += '.sql'
        if internal_name in self.query_names:
            del self.query_names[internal_name]
            settings = self._load_settings()
            settings["query_display_names"] = self.query_names
            self._save_settings(settings)

    def add_new_db(self, name: str, config: dict = None) -> bool:
        """Создает новый файл конфигурации базы данных с указанными параметрами"""
        filename = f"{self._sanitize_name(name)}.json"
        filepath = os.path.join(self.config_dir, filename)
        if os.path.exists(filepath):
            return False
        
        # Если конфигурация не передана, используем значения по умолчанию
        if config is None:
            config = {
                "database_type": "sqlite",
                "host": "localhost",
                "port": 5432,
                "database_name": name,
                "username": "your_username",
                "password": "your_password",
                "charset": "utf8"
            }
        
        # Гарантируем наличие всех необходимых полей
        default_config = {
            "database_type": "sqlite",
            "host": "localhost",
            "port": 5432,
            "database_name": name,
            "username": "your_username",
            "password": "your_password",
            "charset": "utf8"
        }
        config = {**default_config, **config}
        
        # Создаем директорию config, если её нет
        self._ensure_directory(self.config_dir)
        
        tmp = filepath + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        os.replace(tmp, filepath)
        return True

    def delete_db(self, name: str) -> bool:
        """Удаляет файл конфигурации базы данных"""
        if not name.endswith('.json'):
            name += '.json'
        filepath = os.path.join(self.config_dir, name)
        if not os.path.exists(filepath):
            return False
        try:
            os.remove(filepath)
            self.delete_db_name(name)
            return True
        except OSError:
            return False

    def add_new_query(self, name: str, query: str) -> bool:
        """Создает новый SQL-запрос"""
        filename = f"{self._sanitize_name(name)}.sql"
        filepath = os.path.join(self.queries_dir, filename)
        if os.path.exists(filepath):
            return False
        self._ensure_directory(self.queries_dir)
        tmp = filepath + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(query)
        os.replace(tmp, filepath)
        return True

    def delete_query(self, name: str) -> bool:
        """Удаляет SQL-запрос"""
        if not name.endswith('.sql'):
            name += '.sql'
        filepath = os.path.join(self.queries_dir, name)
        if not os.path.exists(filepath):
            return False
        try:
            os.remove(filepath)
            self.delete_query_name(name)
            return True
        except OSError:
            return False