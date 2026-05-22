import os
import datetime
import pytest
from stats_manager import StatsManager


@pytest.fixture
def sm(tmp_path):
    return StatsManager(db_path=str(tmp_path / "test_stats.db"))


# ── record / get_summary ──────────────────────────────────────────────────────

def test_record_creates_row(sm):
    sm.record("q1.sql", duration_ms=123.0, row_count=5)
    rows = sm.get_summary()
    assert len(rows) == 1
    assert rows[0]["query_file"] == "q1.sql"
    assert rows[0]["total_runs"] == 1
    assert rows[0]["avg_rows"] == 5


def test_record_error_flag(sm):
    sm.record("q1.sql", duration_ms=10.0, is_error=True)
    rows = sm.get_summary()
    assert rows[0]["error_count"] == 1


def test_get_summary_aggregates_multiple_runs(sm):
    sm.record("q1.sql", duration_ms=100.0)
    sm.record("q1.sql", duration_ms=200.0)
    rows = sm.get_summary()
    assert rows[0]["total_runs"] == 2
    assert rows[0]["avg_ms"] == pytest.approx(150.0, abs=1)
    assert rows[0]["max_ms"] == pytest.approx(200.0, abs=1)
    assert rows[0]["min_ms"] == pytest.approx(100.0, abs=1)


def test_get_summary_limit(sm):
    for i in range(10):
        sm.record(f"q{i}.sql", duration_ms=float(i))
    rows = sm.get_summary(limit=5)
    assert len(rows) == 5


def test_get_summary_empty(sm):
    assert sm.get_summary() == []


# ── get_recent ────────────────────────────────────────────────────────────────

def test_get_recent_returns_rows_for_file(sm):
    sm.record("q1.sql", duration_ms=50.0, row_count=3)
    sm.record("q1.sql", duration_ms=70.0, row_count=7)
    sm.record("q2.sql", duration_ms=10.0)
    recent = sm.get_recent("q1.sql")
    assert len(recent) == 2
    assert all(r["duration_ms"] in (50.0, 70.0) for r in recent)


def test_get_recent_limit(sm):
    for _ in range(25):
        sm.record("q1.sql", duration_ms=1.0)
    recent = sm.get_recent("q1.sql", limit=10)
    assert len(recent) == 10


def test_get_recent_empty_for_unknown_file(sm):
    sm.record("q1.sql", duration_ms=1.0)
    assert sm.get_recent("unknown.sql") == []


# ── clear ─────────────────────────────────────────────────────────────────────

def test_clear_removes_all(sm):
    sm.record("q1.sql", duration_ms=1.0)
    sm.clear()
    assert sm.get_summary() == []


# ── rotate ────────────────────────────────────────────────────────────────────

def test_rotate_removes_old_records(sm):
    # Вставляем запись с датой 100 дней назад напрямую через _connect
    old_ts = (datetime.datetime.now() - datetime.timedelta(days=100)).strftime(
        "%Y-%m-%d %H:%M:%S")
    with sm._connect() as conn:
        conn.execute(
            "INSERT INTO query_stats (query_file, ts, duration_ms, row_count, is_error)"
            " VALUES (?, ?, ?, ?, ?)",
            ("old.sql", old_ts, 1.0, 0, 0),
        )
        conn.commit()
    sm.record("new.sql", duration_ms=1.0)
    deleted = sm.rotate(max_age_days=90)
    assert deleted == 1
    files = {r["query_file"] for r in sm.get_summary()}
    assert "old.sql" not in files
    assert "new.sql" in files


def test_rotate_keeps_fresh_records(sm):
    sm.record("q1.sql", duration_ms=1.0)
    deleted = sm.rotate(max_age_days=90)
    assert deleted == 0
    assert len(sm.get_summary()) == 1


# ── rotate_by_size ────────────────────────────────────────────────────────────

def test_rotate_by_size_no_action_when_small(sm):
    sm.record("q1.sql", duration_ms=1.0)
    removed = sm.rotate_by_size(max_size_mb=10.0)
    assert removed == 0


def test_rotate_by_size_removes_half_when_large(sm):
    for i in range(100):
        sm.record(f"q{i}.sql", duration_ms=float(i))
    # принудительно вызываем с порогом 0 байт
    removed = sm.rotate_by_size(max_size_mb=0.0)
    assert removed > 0
    assert len(sm.get_summary()) < 100


# ── get_db_size_kb ────────────────────────────────────────────────────────────

def test_get_db_size_kb_positive_after_record(sm):
    sm.record("q1.sql", duration_ms=1.0)
    assert sm.get_db_size_kb() > 0


def test_get_db_size_kb_zero_for_missing_path(sm):
    sm._db_path = "/definitely/does/not/exist/stats.db"
    assert sm.get_db_size_kb() == pytest.approx(0.0)
