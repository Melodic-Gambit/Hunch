import json
import pytest
from settings import SettingsManager


@pytest.fixture
def sm(tmp_path):
    return SettingsManager(settings_file=str(tmp_path / "settings.json"))


# ── базовые операции ──────────────────────────────────────────────────────────

def test_get_missing_key_returns_default(sm):
    assert sm.get_setting("no_such_key") is None
    assert sm.get_setting("no_such_key", 42) == 42


def test_set_and_get(sm):
    sm.set_setting("theme", "light")
    assert sm.get_setting("theme") == "light"


def test_overwrite(sm):
    sm.set_setting("x", 1)
    sm.set_setting("x", 2)
    assert sm.get_setting("x") == 2


# ── персистентность ───────────────────────────────────────────────────────────

def test_persists_across_instances(tmp_path):
    f = str(tmp_path / "settings.json")
    sm1 = SettingsManager(settings_file=f)
    sm1.set_setting("color", "blue")
    sm1.flush()

    sm2 = SettingsManager(settings_file=f)
    assert sm2.get_setting("color") == "blue"


def test_defaults_on_missing_file(tmp_path):
    sm = SettingsManager(settings_file=str(tmp_path / "new.json"))
    assert sm.get_setting("theme") == "dark"


def test_defaults_include_check_updates(tmp_path):
    sm = SettingsManager(settings_file=str(tmp_path / "new.json"))
    assert sm.get_setting("check_updates") is True


def test_new_default_key_backfilled_into_existing_file(tmp_path):
    f = str(tmp_path / "settings.json")
    # simulate old settings.json without check_updates
    with open(f, "w", encoding="utf-8") as fh:
        json.dump({"theme": "light", "refresh_interval": 60}, fh)
    sm = SettingsManager(settings_file=f)
    assert sm.get_setting("check_updates") is True


def test_existing_value_overrides_default(tmp_path):
    f = str(tmp_path / "settings.json")
    with open(f, "w", encoding="utf-8") as fh:
        json.dump({"check_updates": False}, fh)
    sm = SettingsManager(settings_file=f)
    assert sm.get_setting("check_updates") is False


def test_backfill_is_in_memory_only_not_written_to_disk(tmp_path):
    # load_settings() merges defaults in memory but never persists them back;
    # the file on disk stays unchanged until the next set_setting() call.
    f = str(tmp_path / "settings.json")
    with open(f, "w", encoding="utf-8") as fh:
        json.dump({"theme": "light", "refresh_interval": 60}, fh)
    SettingsManager(settings_file=f)
    with open(f, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert "check_updates" not in on_disk


# ── интервалы запросов ────────────────────────────────────────────────────────

def test_set_and_get_query_interval(sm):
    sm.set_query_interval("my_query", 60)
    assert sm.get_query_interval("my_query") == 60


def test_query_interval_default(sm):
    assert sm.get_query_interval("unknown", default=300) == 300


# ── сложные значения ──────────────────────────────────────────────────────────

def test_dict_value(sm):
    sm.set_setting("meta", {"a": 1, "b": [1, 2]})
    assert sm.get_setting("meta") == {"a": 1, "b": [1, 2]}


def test_list_value(sm):
    sm.set_setting("items", [1, 2, 3])
    assert sm.get_setting("items") == [1, 2, 3]
