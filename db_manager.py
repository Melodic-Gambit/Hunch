import json
import logging
import os
import re
import threading
import time
from typing import Dict, Any, List, Tuple, Optional

try:
    import keyring as _keyring
    _KEYRING_OK = True
except Exception:
    _KEYRING_OK = False

_KEYRING_SERVICE = "hunch"

_logger = logging.getLogger(__name__)

try:
    import sqlite3
except ImportError:
    sqlite3 = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    import pymysql
except ImportError:
    pymysql = None

try:
    import oracledb
except ImportError:
    oracledb = None

try:
    import cx_Oracle
except ImportError:
    cx_Oracle = None

try:
    import pyodbc
except ImportError:
    pyodbc = None


_INVALID_CONN_NAME_RE = re.compile(r'[\\/:*?"<>|]')


class DatabaseManager:
    # Соединение переиспользуется, пока простаивает не дольше этого порога (секунды).
    _CONN_TTL: float = 30.0

    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.connections: Dict[str, Any] = {}
        self._conn_last_used: Dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def get_keyring_password(conn_name: str) -> str:
        if not _KEYRING_OK:
            return ""
        try:
            return _keyring.get_password(_KEYRING_SERVICE, conn_name) or ""
        except Exception:
            return ""

    @staticmethod
    def set_keyring_password(conn_name: str, password: str):
        if not _KEYRING_OK:
            return
        try:
            _keyring.set_password(_KEYRING_SERVICE, conn_name, password)
        except Exception:
            pass

    @staticmethod
    def delete_keyring_password(conn_name: str):
        if not _KEYRING_OK:
            return
        try:
            _keyring.delete_password(_KEYRING_SERVICE, conn_name)
        except Exception:
            pass

    def load_config(self, config_name: str) -> Dict[str, Any]:
        if _INVALID_CONN_NAME_RE.search(config_name):
            raise ValueError(
                f"Имя подключения содержит недопустимые символы Windows FS: {config_name!r}")
        config_path = os.path.join(self.config_dir, f"{config_name}.json")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Конфигурационный файл {config_path} не найден")
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка парсинга JSON в файле {config_path}: {e}")

        if config.get("password_in_keyring"):
            config["password"] = self.get_keyring_password(config_name)
        elif "password" not in config:
            config["password"] = ""

        return config

    # Таймаут установки TCP-соединения (секунды). Защищает от зависания при
    # недоступном хосте — без этого ОС ждёт до ~2 минут (SYN-таймаут).
    _CONNECT_TIMEOUT: int = 30

    def _open_connection(self, config: Dict[str, Any]) -> Any:
        """Открывает соединение по словарю конфигурации (без сохранения)."""
        db_type = config.get("database_type", "sqlite").lower()
        ct = self._CONNECT_TIMEOUT

        if db_type == "sqlite":
            if sqlite3 is None:
                raise ImportError("sqlite3 недоступен")
            db_path = config.get("database_name", "database.db")
            conn = sqlite3.connect(db_path, check_same_thread=False)
            # Принцип минимальных привилегий: запрещаем любые изменения на уровне соединения
            conn.execute("PRAGMA query_only = ON")
            return conn

        elif db_type == "postgresql":
            if psycopg2 is None:
                raise ImportError("psycopg2 не установлен (pip install psycopg2-binary)")
            conn = psycopg2.connect(
                host=config["host"], port=config["port"],
                database=config["database_name"],
                user=config["username"], password=config["password"],
                connect_timeout=ct,
                options="-c default_transaction_read_only=on")
            conn.autocommit = True  # не держим открытую транзакцию
            return conn

        elif db_type == "mysql":
            if pymysql is None:
                raise ImportError("pymysql не установлен (pip install pymysql)")
            conn = pymysql.connect(
                host=config["host"], port=config["port"],
                database=config["database_name"],
                user=config["username"], password=config["password"],
                charset=config.get("charset", "utf8"),
                connect_timeout=ct,
                read_timeout=ct)
            conn.autocommit(True)
            return conn

        elif db_type == "oracle":
            dsn = f"{config['host']}:{config['port']}/{config['database_name']}"
            if oracledb is not None:
                conn = oracledb.connect(
                    user=config["username"], password=config["password"], dsn=dsn)
            elif cx_Oracle is not None:
                conn = cx_Oracle.connect(
                    user=config["username"], password=config["password"], dsn=dsn)
            else:
                raise ImportError(
                    "Драйвер Oracle не установлен (pip install oracledb или cx_Oracle)")
            conn.autocommit = True
            return conn

        elif db_type == "mssql":
            if pyodbc is None:
                raise ImportError("pyodbc не установлен (pip install pyodbc)")
            cs = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={config['host']},{config['port']};"
                f"DATABASE={config['database_name']};"
                f"UID={config['username']};PWD={config['password']};"
                f"LOGIN_TIMEOUT={ct};"
            )
            conn = pyodbc.connect(cs)
            conn.autocommit = True
            return conn

        else:
            raise ValueError(f"Неподдерживаемый тип базы данных: {db_type}")

    def connect(self, config_name: str) -> Any:
        config = self.load_config(config_name)
        try:
            conn = self._open_connection(config)
            self.connections[config_name] = conn
            return conn
        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к {config_name}: {e}")

    def test_connection_raw(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Проверяет подключение по словарю конфигурации. Возвращает (успех, сообщение)."""
        try:
            conn = self._open_connection(config)
            conn.close()
            return True, ""
        except Exception as e:
            return False, str(e)

    def ping(self, config_name: str) -> Tuple[bool, str]:
        """Проверяет соединение по имени конфига без выполнения пользовательского запроса."""
        try:
            config = self.load_config(config_name)
            return self.test_connection_raw(config)
        except Exception as e:
            return False, str(e)

    # ── внутренний метод выполнения ────────────────────────────────────────────

    def _evict_if_stale(self, config_name: str):
        """Закрывает и удаляет соединение, если оно простаивало дольше TTL."""
        last = self._conn_last_used.get(config_name)
        if last is not None and (time.monotonic() - last) > self._CONN_TTL:
            try:
                self.connections[config_name].close()
            except Exception:
                pass
            self.connections.pop(config_name, None)
            self._conn_last_used.pop(config_name, None)

    def _run(self, config_name: str, query: str) -> Tuple[List[tuple], List[str]]:
        """Выполняет запрос (уже проверенный на SELECT), возвращает (rows, columns).
        Использует блокировку — безопасно вызывать из фонового потока."""
        with self._lock:
            self._evict_if_stale(config_name)
            if config_name not in self.connections:
                self.connect(config_name)
            cursor = None
            try:
                cursor = self.connections[config_name].cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                cols = [d[0] for d in (cursor.description or [])]
                self._conn_last_used[config_name] = time.monotonic()
                return rows, cols
            except Exception:
                try:
                    if cursor is not None:
                        try:
                            cursor.close()
                        except Exception:
                            pass
                        cursor = None
                    self.connections.pop(config_name, None)
                    self._conn_last_used.pop(config_name, None)
                    self.connect(config_name)
                    cursor = self.connections[config_name].cursor()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    cols = [d[0] for d in (cursor.description or [])]
                    self._conn_last_used[config_name] = time.monotonic()
                    return rows, cols
                except Exception as e:
                    raise RuntimeError(f"Ошибка выполнения запроса: {e}")
            finally:
                if cursor is not None:
                    try:
                        cursor.close()
                    except Exception:
                        pass

    # ── публичные методы ───────────────────────────────────────────────────────

    # Допустимые начальные ключевые слова (whitelist) для пользовательского SQL
    _ALLOWED_STMTS = {"SELECT", "WITH"}

    # Опасные конструкции запрещены в структурной части запроса.
    # Проверяется на SQL БЕЗ строковых литералов и комментариев —
    # слова внутри 'строк' и /* комментариев */ не вызывают ложных срабатываний.
    _BLOCKED_KEYWORDS = re.compile(
        r"\b(?:"
        r"PRAGMA|EXEC(?:UTE)?\b|CALL\b|DECLARE\b|"
        r"INSERT\b|UPDATE\b|DELETE\b|MERGE\b|UPSERT\b|REPLACE\s+INTO\b|"
        r"DROP\b|CREATE\b|ALTER\b|TRUNCATE\b|RENAME\b|"
        r"GRANT\b|REVOKE\b|DENY\b|"
        r"ATTACH\b|DETACH\b|LOAD_EXTENSION\b|IMPORT\b|"
        r"COPY\s+(?:FROM|TO|INTO)\b|BULK\b|"
        r"COMMIT\b|ROLLBACK\b|SAVEPOINT\b|BEGIN\b|"
        r"LOCK\s+TABLE\b|UNLOCK\s+TABLE\b|FLUSH\b|KILL\b|SHUTDOWN\b|"
        r"SLEEP\s*\(|BENCHMARK\s*\("
        r")",
        re.IGNORECASE,
    )

    # Удаление однострочных и блочных комментариев
    _COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/|--[^\n]*", re.MULTILINE)
    # Удаление строковых литералов (включая экранирование '' и \')
    _STRING_LITERAL_RE = re.compile(r"'(?:[^'\\]|\\.|'')*'", re.DOTALL)

    @classmethod
    def _strip_comments(cls, sql: str) -> str:
        """Удаляет SQL-комментарии перед анализом структуры запроса."""
        return cls._COMMENT_RE.sub(" ", sql)

    @classmethod
    def _strip_literals(cls, sql: str) -> str:
        """Удаляет комментарии и строковые литералы — для blacklist-проверки."""
        no_comments = cls._COMMENT_RE.sub(" ", sql)
        return cls._STRING_LITERAL_RE.sub("''", no_comments)

    @classmethod
    def _validate_query(cls, query: str) -> Tuple[bool, str]:
        """Возвращает (ok, reason). Причина непустая только при отказе."""
        stripped = query.strip()
        if not stripped:
            return False, "пустой запрос"

        # 1. Снимаем комментарии для проверки первого слова и multi-statement
        clean = cls._strip_comments(stripped).strip()
        if not clean:
            return False, "запрос состоит только из комментариев"

        # 2. Whitelist: только SELECT и WITH (CTE) разрешены как первое слово
        first_word = re.split(r"\s", clean, maxsplit=1)[0].upper()
        if first_word not in cls._ALLOWED_STMTS:
            return False, f"запрещённый тип запроса: {first_word!r}"

        # 3. Multi-statement: точка с запятой запрещена внутри запроса
        body = clean.rstrip(";")
        if ";" in body:
            return False, "multi-statement запрос (точка с запятой внутри)"

        # 4. Blacklist: проверяем SQL БЕЗ строковых литералов и комментариев,
        #    чтобы слова вроде 'delete' или 'copy' в строковых значениях не блокировали
        structural = cls._strip_literals(stripped)
        match = cls._BLOCKED_KEYWORDS.search(structural)
        if match:
            return False, f"запрещённая конструкция: {match.group(0).strip()!r}"

        return True, ""

    @classmethod
    def _is_select_query(cls, query: str) -> bool:
        ok, _ = cls._validate_query(query)
        return ok

    def execute_query(self, config_name: str, query: str) -> List[tuple]:
        """SELECT/CTE-запрос → список строк (без имён колонок)."""
        ok, reason = self._validate_query(query)
        if not ok:
            _logger.warning("execute_query отклонён [%s]: %s", config_name, reason)
            return []
        rows, _ = self._run(config_name, query)
        return rows

    def execute_query_with_columns(self, config_name: str,
                                   query: str) -> Tuple[List[tuple], List[str]]:
        """SELECT/CTE-запрос → (rows, column_names)."""
        ok, reason = self._validate_query(query)
        if not ok:
            _logger.warning("execute_query_with_columns отклонён [%s]: %s", config_name, reason)
            return [], []
        return self._run(config_name, query)

    def explain_query(self, config_name: str, sql: str,
                      db_type: str = "sqlite") -> Tuple[List[tuple], List[str]]:
        """Безопасный EXPLAIN: сначала валидирует пользовательский SQL,
        затем запускает EXPLAIN с системным префиксом (не из пользовательского ввода)."""
        ok, reason = self._validate_query(sql)
        if not ok:
            _logger.warning("explain_query отклонён [%s]: %s", config_name, reason)
            raise ValueError(f"Недопустимый SQL: {reason}")
        if db_type == "sqlite":
            explain_sql = "EXPLAIN QUERY PLAN " + sql
        elif db_type in ("oracle", "mssql"):
            # Эти СУБД не поддерживают стандартный EXPLAIN через этот метод
            raise NotImplementedError(f"EXPLAIN не поддерживается для {db_type}")
        else:
            explain_sql = "EXPLAIN " + sql
        return self._run(config_name, explain_sql)

    def close_all(self):
        with self._lock:
            for conn in self.connections.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self.connections.clear()
            self._conn_last_used.clear()
