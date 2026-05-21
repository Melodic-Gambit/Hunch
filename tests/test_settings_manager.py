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

    sm2 = SettingsManager(settings_file=f)
    assert sm2.get_setting("color") == "blue"


def test_defaults_on_missing_file(tmp_path):
    sm = SettingsManager(settings_file=str(tmp_path / "new.json"))
    assert sm.get_setting("theme") == "dark"


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
