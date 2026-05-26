import os
import json
import pytest
from unittest.mock import patch
from data_manager import DataManager


@pytest.fixture
def dm(tmp_path):
    return DataManager(
        config_dir=str(tmp_path / "config"),
        queries_dir=str(tmp_path / "queries"),
        settings_file=str(tmp_path / "settings.json"),
    )


# ── директории ────────────────────────────────────────────────────────────────

def test_creates_dirs_on_init(tmp_path):
    dm = DataManager(
        config_dir=str(tmp_path / "config"),
        queries_dir=str(tmp_path / "queries"),
        settings_file=str(tmp_path / "settings.json"),
    )
    assert os.path.isdir(str(tmp_path / "config"))
    assert os.path.isdir(str(tmp_path / "queries"))


# ── подключения ───────────────────────────────────────────────────────────────

def test_add_db_creates_file(dm, tmp_path):
    ok = dm.add_new_db("mydb", {"database_type": "sqlite"})
    assert ok is True
    assert os.path.exists(str(tmp_path / "config" / "mydb.json"))


def test_add_db_duplicate_returns_false(dm):
    dm.add_new_db("mydb")
    assert dm.add_new_db("mydb") is False


def test_add_db_default_config(dm, tmp_path):
    dm.add_new_db("defaults")
    data = json.loads(open(str(tmp_path / "config" / "defaults.json")).read())
    assert "database_type" in data


def test_delete_db(dm, tmp_path):
    dm.add_new_db("todel")
    assert dm.delete_db("todel.json") is True
    assert not os.path.exists(str(tmp_path / "config" / "todel.json"))


def test_delete_db_missing_returns_false(dm):
    assert dm.delete_db("ghost.json") is False


# ── отображаемые имена БД ─────────────────────────────────────────────────────

def test_display_name_roundtrip(dm):
    dm.set_db_display_name("prod.json", "Production DB")
    assert dm.get_db_display_name("prod.json") == "Production DB"


def test_display_name_fallback(dm):
    assert dm.get_db_display_name("unnamed.json") == "unnamed"


def test_delete_db_name(dm):
    dm.set_db_display_name("tmp.json", "Temp")
    dm.delete_db_name("tmp.json")
    assert dm.get_db_display_name("tmp.json") == "tmp"


def test_db_display_name_persists(tmp_path):
    s = str(tmp_path / "settings.json")
    dm1 = DataManager(str(tmp_path / "c"), str(tmp_path / "q"), s)
    dm1.set_db_display_name("x.json", "Xander")

    dm2 = DataManager(str(tmp_path / "c"), str(tmp_path / "q"), s)
    assert dm2.get_db_display_name("x.json") == "Xander"


# ── запросы ───────────────────────────────────────────────────────────────────

def test_add_query_creates_file(dm, tmp_path):
    ok = dm.add_new_query("count_users", "SELECT COUNT(*) FROM users")
    assert ok is True
    path = str(tmp_path / "queries" / "count_users.sql")
    assert open(path).read() == "SELECT COUNT(*) FROM users"


def test_add_query_duplicate_returns_false(dm):
    dm.add_new_query("q", "SELECT 1")
    assert dm.add_new_query("q", "SELECT 2") is False


def test_delete_query(dm, tmp_path):
    dm.add_new_query("todel", "SELECT 1")
    assert dm.delete_query("todel.sql") is True
    assert not os.path.exists(str(tmp_path / "queries" / "todel.sql"))


def test_delete_query_missing_returns_false(dm):
    assert dm.delete_query("ghost.sql") is False


# ── отображаемые имена запросов ───────────────────────────────────────────────

def test_query_display_name_roundtrip(dm):
    dm.set_query_display_name("q.sql", "Кол-во юзеров")
    assert dm.get_query_display_name("q.sql") == "Кол-во юзеров"


def test_query_display_name_fallback(dm):
    assert dm.get_query_display_name("report.sql") == "report"


def test_delete_query_name(dm):
    dm.set_query_display_name("r.sql", "Report")
    dm.delete_query_name("r.sql")
    assert dm.get_query_display_name("r.sql") == "r"


# ── _sanitize_name ────────────────────────────────────────────────────────────

def test_sanitize_name_replaces_forbidden_chars():
    forbidden = r'/*?:"<>|\\'
    for ch in forbidden:
        result = DataManager._sanitize_name(f"name{ch}test")
        assert "_" in result, f"символ {ch!r} не заменён"
        assert ch not in result


def test_sanitize_name_safe_chars_unchanged():
    assert DataManager._sanitize_name("valid-name_123") == "valid-name_123"


def test_sanitize_name_empty_string():
    assert DataManager._sanitize_name("") == ""


# ── add_new_db: граничные случаи ─────────────────────────────────────────────

def test_add_db_empty_name_creates_dot_json(dm, tmp_path):
    ok = dm.add_new_db("")
    assert ok is True
    # _sanitize_name("") = "" → filename = ".json"
    assert os.path.exists(str(tmp_path / "config" / ".json"))


def test_add_db_user_config_overrides_defaults(dm, tmp_path):
    ok = dm.add_new_db("override_test", {"database_type": "postgresql", "port": 9999})
    assert ok is True
    data = json.loads(open(str(tmp_path / "config" / "override_test.json")).read())
    assert data["database_type"] == "postgresql"
    assert data["port"] == 9999


def test_add_db_defaults_fill_missing_fields(dm, tmp_path):
    dm.add_new_db("partial", {"database_type": "mysql"})
    data = json.loads(open(str(tmp_path / "config" / "partial.json")).read())
    # Поля, не переданные пользователем, заполнены дефолтами
    assert "host" in data
    assert "username" in data


# ── OSError-ветки (BUG-11 / BUG-33) ─────────────────────────────────────────

def test_add_db_oserror_on_open_returns_false(dm, tmp_path):
    with patch("builtins.open", side_effect=OSError("disk full")):
        result = dm.add_new_db("faildb")
    assert result is False
    assert not (tmp_path / "config" / "faildb.json").exists()
    assert not (tmp_path / "config" / "faildb.json.tmp").exists()


def test_add_query_oserror_on_replace_returns_false_and_cleans_tmp(dm, tmp_path):
    with patch("data_manager.os.replace", side_effect=OSError("replace failed")):
        result = dm.add_new_query("failq", "SELECT 1")
    assert result is False
    assert not (tmp_path / "queries" / "failq.sql").exists()
    assert not (tmp_path / "queries" / "failq.sql.tmp").exists()


def test_save_settings_oserror_does_not_propagate(dm):
    with patch("builtins.open", side_effect=OSError("no space")):
        dm._save_settings({"key": "value"})  # не должно бросать исключение


# ── add_new_query: отсутствующая директория ───────────────────────────────────

def test_add_query_creates_queries_dir_if_missing(tmp_path):
    queries_dir = str(tmp_path / "does_not_exist" / "queries")
    dm = DataManager(
        config_dir=str(tmp_path / "config"),
        queries_dir=queries_dir,
        settings_file=str(tmp_path / "settings.json"),
    )
    # queries_dir создаётся в __init__ через _ensure_directory
    assert os.path.isdir(queries_dir)
    ok = dm.add_new_query("q", "SELECT 1")
    assert ok is True
    assert os.path.exists(os.path.join(queries_dir, "q.sql"))
