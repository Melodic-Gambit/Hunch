import datetime
import pytest
from log_manager import LogManager


@pytest.fixture
def lm(tmp_path):
    return LogManager(
        log_file=str(tmp_path / "logs" / "app.log"),
        settings_file=str(tmp_path / "settings.json"),
    )


# ── базовые операции ──────────────────────────────────────────────────────────

def test_add_and_get(lm):
    lm.add_log("hello", "INFO")
    logs = lm.get_logs()
    assert len(logs) == 1
    assert logs[0]["message"] == "hello"
    assert logs[0]["level"] == "INFO"


def test_default_level_is_info(lm):
    lm.add_log("no level")
    assert lm.get_logs()[0]["level"] == "INFO"


def test_multiple_levels(lm):
    lm.add_log("i", "INFO")
    lm.add_log("e", "ERROR")
    lm.add_log("w", "WARNING")
    levels = {e["level"] for e in lm.get_logs()}
    assert levels == {"INFO", "ERROR", "WARNING"}


def test_clear(lm):
    lm.add_log("a")
    lm.add_log("b")
    lm.clear_logs()
    assert lm.get_logs() == []


# ── персистентность ───────────────────────────────────────────────────────────

def test_persistence(tmp_path):
    log_file = str(tmp_path / "logs" / "app.log")
    settings = str(tmp_path / "settings.json")

    lm1 = LogManager(log_file=log_file, settings_file=settings)
    lm1.add_log("persist me")
    lm1.flush()  # запись теперь отложена — форсируем сброс на диск

    lm2 = LogManager(log_file=log_file, settings_file=settings)
    assert any(e["message"] == "persist me" for e in lm2.get_logs())


def test_clear_persists(tmp_path):
    log_file = str(tmp_path / "logs" / "app.log")
    settings = str(tmp_path / "settings.json")

    lm1 = LogManager(log_file=log_file, settings_file=settings)
    lm1.add_log("gone")
    lm1.clear_logs()

    lm2 = LogManager(log_file=log_file, settings_file=settings)
    assert lm2.get_logs() == []


# ── ротация ───────────────────────────────────────────────────────────────────

def test_rotate_removes_old(lm):
    old_ts = (datetime.datetime.now() - datetime.timedelta(hours=200)) \
        .strftime("%Y-%m-%d %H:%M:%S")
    lm.logs.append({"timestamp": old_ts, "level": "INFO", "message": "old"})
    lm.save_logs()

    removed = lm.rotate_old_logs(max_age_hours=100)
    assert removed == 1
    assert all(e["message"] != "old" for e in lm.get_logs())


def test_rotate_keeps_recent(lm):
    lm.add_log("recent")
    removed = lm.rotate_old_logs(max_age_hours=1)
    assert removed == 0
    assert len(lm.get_logs()) == 1


def test_rotate_returns_zero_when_nothing_old(lm):
    lm.add_log("fresh")
    assert lm.rotate_old_logs(max_age_hours=9999) == 0


# ── сохранение в файл ─────────────────────────────────────────────────────────

def test_save_to_file(lm, tmp_path):
    lm.add_log("export me", "ERROR")
    out = str(tmp_path / "out.txt")
    lm.save_logs_to_file(out)
    content = open(out, encoding="utf-8").read()
    assert "export me" in content
    assert "ERROR" in content
