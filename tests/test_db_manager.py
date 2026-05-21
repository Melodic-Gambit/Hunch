import json
import os
import pytest
from db_manager import DatabaseManager


@pytest.fixture
def cfg_dir(tmp_path):
    return tmp_path / "config"


@pytest.fixture
def dm(cfg_dir):
    cfg_dir.mkdir()
    return DatabaseManager(config_dir=str(cfg_dir))


def _write_sqlite_config(cfg_dir, name: str, db_path: str):
    cfg = {"database_type": "sqlite", "database_name": db_path}
    with open(str(cfg_dir / f"{name}.json"), "w") as f:
        json.dump(cfg, f)


# ── load_config ───────────────────────────────────────────────────────────────

def test_load_config_ok(dm, cfg_dir, tmp_path):
    _write_sqlite_config(cfg_dir, "mydb", str(tmp_path / "my.db"))
    cfg = dm.load_config("mydb")
    assert cfg["database_type"] == "sqlite"


def test_load_config_missing_raises(dm):
    with pytest.raises(FileNotFoundError):
        dm.load_config("ghost")


def test_load_config_bad_json(dm, cfg_dir):
    bad = cfg_dir / "bad.json"
    bad.write_text("not json")
    with pytest.raises(ValueError):
        dm.load_config("bad")


# ── test_connection_raw ───────────────────────────────────────────────────────

def test_sqlite_connection_ok(tmp_path):
    cfg = {"database_type": "sqlite", "database_name": str(tmp_path / "test.db")}
    dm = DatabaseManager()
    ok, msg = dm.test_connection_raw(cfg)
    assert ok is True
    assert msg == ""


def test_bad_db_type_fails(tmp_path):
    cfg = {"database_type": "unknown_db"}
    dm = DatabaseManager()
    ok, msg = dm.test_connection_raw(cfg)
    assert ok is False
    assert msg != ""


# ── execute_query_with_columns / _run ─────────────────────────────────────────

def test_execute_simple_select(dm, cfg_dir, tmp_path):
    db_path = str(tmp_path / "test.db")
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'Alice')")
    conn.commit()
    conn.close()

    _write_sqlite_config(cfg_dir, "testdb", db_path)
    rows, cols = dm.execute_query_with_columns("testdb", "SELECT id, name FROM t")
    assert cols == ["id", "name"]
    assert list(rows[0]) == [1, "Alice"]


def test_execute_returns_empty_for_no_rows(dm, cfg_dir, tmp_path):
    db_path = str(tmp_path / "empty.db")
    import sqlite3
    sqlite3.connect(db_path).execute(
        "CREATE TABLE e (x INTEGER)").connection.commit()

    _write_sqlite_config(cfg_dir, "emptydb", db_path)
    rows, cols = dm.execute_query_with_columns("emptydb", "SELECT x FROM e")
    assert cols == ["x"]
    assert rows == []


def test_execute_invalid_sql_raises(dm, cfg_dir, tmp_path):
    db_path = str(tmp_path / "err.db")
    import sqlite3
    sqlite3.connect(db_path).close()

    _write_sqlite_config(cfg_dir, "errdb", db_path)
    with pytest.raises(RuntimeError):
        dm.execute_query_with_columns("errdb", "SELECT * FROM nonexistent_table")


# ── close_all ─────────────────────────────────────────────────────────────────

def test_close_all_clears_connections(dm, cfg_dir, tmp_path):
    db_path = str(tmp_path / "c.db")
    import sqlite3
    sqlite3.connect(db_path).close()
    _write_sqlite_config(cfg_dir, "cdb", db_path)

    dm.execute_query_with_columns("cdb", "SELECT 1")
    assert "cdb" in dm.connections

    dm.close_all()
    assert dm.connections == {}
