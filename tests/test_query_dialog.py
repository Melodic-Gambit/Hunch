"""
TEST-05: Tests for SQL validation, cron schedule, and threshold alert logic.

SQL validation tested via DatabaseManager._validate_query directly (no display needed).
Cron and threshold logic tested via helper functions that mirror QueryDialog._on_ok.
"""
import pytest
from db_manager import DatabaseManager


# ── SQL validation ────────────────────────────────────────────────────────────

class TestValidateQuery:
    def test_empty_query(self):
        ok, reason = DatabaseManager._validate_query("")
        assert ok is False
        assert reason

    def test_whitespace_only(self):
        ok, _ = DatabaseManager._validate_query("   \n\t  ")
        assert ok is False

    def test_comments_only_single_line(self):
        ok, _ = DatabaseManager._validate_query("-- just a comment")
        assert ok is False

    def test_comments_only_block(self):
        ok, _ = DatabaseManager._validate_query("/* block comment */")
        assert ok is False

    def test_select_simple(self):
        ok, _ = DatabaseManager._validate_query("SELECT 1")
        assert ok is True

    def test_select_lowercase(self):
        ok, _ = DatabaseManager._validate_query("select * from t")
        assert ok is True

    def test_select_with_inline_comment(self):
        ok, _ = DatabaseManager._validate_query("SELECT 1 -- trailing comment")
        assert ok is True

    def test_with_cte(self):
        ok, _ = DatabaseManager._validate_query(
            "WITH cte AS (SELECT 1 AS n) SELECT n FROM cte")
        assert ok is True

    def test_with_lowercase(self):
        ok, _ = DatabaseManager._validate_query("with x as (select 1) select * from x")
        assert ok is True

    def test_trailing_semicolon_allowed(self):
        ok, _ = DatabaseManager._validate_query("SELECT 1;")
        assert ok is True

    def test_insert_rejected(self):
        ok, reason = DatabaseManager._validate_query("INSERT INTO t VALUES (1)")
        assert ok is False

    def test_update_rejected(self):
        ok, _ = DatabaseManager._validate_query("UPDATE t SET x = 1")
        assert ok is False

    def test_delete_rejected(self):
        ok, _ = DatabaseManager._validate_query("DELETE FROM t")
        assert ok is False

    def test_drop_rejected(self):
        ok, _ = DatabaseManager._validate_query("DROP TABLE t")
        assert ok is False

    def test_create_rejected(self):
        ok, _ = DatabaseManager._validate_query("CREATE TABLE t (id INT)")
        assert ok is False

    def test_pragma_rejected(self):
        ok, _ = DatabaseManager._validate_query("PRAGMA table_info(t)")
        assert ok is False

    def test_multistatement_rejected(self):
        ok, reason = DatabaseManager._validate_query("SELECT 1; SELECT 2")
        assert ok is False
        assert reason

    def test_blocked_keyword_in_string_literal_allowed(self):
        # 'delete' inside a string literal must NOT trigger the blacklist
        ok, _ = DatabaseManager._validate_query("SELECT 'delete this row' FROM t")
        assert ok is True

    def test_insert_in_string_literal_allowed(self):
        ok, _ = DatabaseManager._validate_query("SELECT 'INSERT is a word' FROM t")
        assert ok is True

    def test_select_with_subquery(self):
        ok, _ = DatabaseManager._validate_query(
            "SELECT id FROM (SELECT id FROM users WHERE active = 1) sub")
        assert ok is True

    def test_random_string_rejected(self):
        ok, _ = DatabaseManager._validate_query("FOOBAR 123")
        assert ok is False


# ── Cron schedule validation logic ───────────────────────────────────────────

def _validate_cron_time(hour_str: str, min_str: str):
    """Mirrors the cron time validation in QueryDialog._on_ok."""
    try:
        h = int(hour_str)
        m = int(min_str)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return True, h, m
    except (ValueError, TypeError):
        return False, None, None


class TestCronValidation:
    def test_valid_midnight(self):
        ok, h, m = _validate_cron_time("0", "0")
        assert ok is True and h == 0 and m == 0

    def test_valid_max(self):
        ok, h, m = _validate_cron_time("23", "59")
        assert ok is True

    def test_valid_midday(self):
        ok, h, m = _validate_cron_time("12", "30")
        assert ok is True and h == 12 and m == 30

    def test_hour_boundary_exceeded(self):
        ok, _, _ = _validate_cron_time("24", "0")
        assert ok is False

    def test_minute_boundary_exceeded(self):
        ok, _, _ = _validate_cron_time("0", "60")
        assert ok is False

    def test_negative_hour(self):
        ok, _, _ = _validate_cron_time("-1", "0")
        assert ok is False

    def test_negative_minute(self):
        ok, _, _ = _validate_cron_time("0", "-1")
        assert ok is False

    def test_non_numeric_hour(self):
        ok, _, _ = _validate_cron_time("abc", "0")
        assert ok is False

    def test_non_numeric_minute(self):
        ok, _, _ = _validate_cron_time("12", "xx")
        assert ok is False

    def test_empty_strings(self):
        ok, _, _ = _validate_cron_time("", "")
        assert ok is False

    def test_no_days_selected_produces_empty_list(self):
        # QueryDialog allows cron with no days (produces empty days list, no error raised)
        day_flags = [False, False, False, False, False, False, False]
        days = [i for i, v in enumerate(day_flags) if v]
        assert days == []


# ── Threshold alert validation logic ─────────────────────────────────────────

def _validate_threshold(col_str: str, val_str: str, op: str = ">"):
    """Mirrors the threshold validation in QueryDialog._on_ok."""
    try:
        col = int(col_str) if col_str else 0
        if col < 0:
            raise ValueError
    except (ValueError, TypeError):
        return False, "column"
    try:
        thr_val = float(val_str) if val_str else 0.0
    except (ValueError, TypeError):
        return False, "value"
    return True, {"column": col, "operator": op, "value": thr_val}


class TestThresholdValidation:
    def test_valid_threshold(self):
        ok, result = _validate_threshold("2", "100.5", ">")
        assert ok is True
        assert result["column"] == 2
        assert result["value"] == pytest.approx(100.5)
        assert result["operator"] == ">"

    def test_column_zero(self):
        ok, result = _validate_threshold("0", "0", "==")
        assert ok is True and result["column"] == 0

    def test_empty_col_defaults_to_zero(self):
        ok, result = _validate_threshold("", "5", ">=")
        assert ok is True and result["column"] == 0

    def test_empty_val_defaults_to_zero(self):
        ok, result = _validate_threshold("1", "", "<=")
        assert ok is True and result["value"] == 0.0

    def test_negative_column_rejected(self):
        ok, field = _validate_threshold("-1", "0", ">")
        assert ok is False and field == "column"

    def test_non_numeric_column_rejected(self):
        ok, field = _validate_threshold("abc", "0", ">")
        assert ok is False and field == "column"

    def test_non_numeric_value_rejected(self):
        ok, field = _validate_threshold("0", "not_a_number", ">")
        assert ok is False and field == "value"

    def test_float_value_accepted(self):
        ok, result = _validate_threshold("0", "3.14", "!=")
        assert ok is True and result["value"] == pytest.approx(3.14)

    def test_negative_value_accepted(self):
        ok, result = _validate_threshold("0", "-10", "<")
        assert ok is True and result["value"] == pytest.approx(-10.0)

    def test_all_operators(self):
        for op in (">", "<", ">=", "<=", "==", "!="):
            ok, result = _validate_threshold("0", "1", op)
            assert ok is True and result["operator"] == op
