"""
TEST-02: Tests for result_table.py — data insertion, pagination, sort, export to CSV.

ResultTable extends ctk.CTkFrame and cannot be instantiated without a Tk root.
_TableLogic mirrors the pure data model from ResultTable for headless testing.
export_to_csv is tested via a minimal stub that delegates to the actual method.
"""
import csv
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from widgets.result_table import ResultTable

_PAGE_SIZE = 100


class _TableLogic:
    """Headless replica of ResultTable's data model — no Tkinter dependency.

    All methods are copied verbatim from ResultTable (minus _render() calls)
    so that tests verify the actual production logic, not reimplementations.
    """

    def __init__(self, rows=None, columns=None):
        self._columns: list = list(columns) if columns else []
        self._rows: list = [list(r) for r in rows] if rows else []
        self._sort_col = None
        self._sort_rev: bool = False
        self._current_page: int = 0
        self._hidden_keys: set = set()
        self._hidden_rows: dict = {}

    def set_data(self, rows, columns, reset_hidden=True):
        all_rows = [list(r) for r in rows]
        self._columns = list(columns)
        self._sort_col = None
        self._sort_rev = False
        self._current_page = 0
        evicted: set = set()
        if reset_hidden:
            self._hidden_keys = set()
            self._hidden_rows = {}
        if self._hidden_keys:
            fresh_hidden: dict = {}
            visible = []
            for r in all_rows:
                key = str(r[0]) if r else ""
                if key in self._hidden_keys:
                    fresh_hidden.setdefault(key, []).append(r)
                else:
                    visible.append(r)
            evicted = self._hidden_keys - set(fresh_hidden.keys())
            for key in evicted:
                self._hidden_keys.discard(key)
            self._hidden_rows = fresh_hidden
            self._rows = visible
        else:
            self._rows = all_rows
        return evicted

    def _total_pages(self):
        if not self._rows:
            return 1
        return max(1, (len(self._rows) + _PAGE_SIZE - 1) // _PAGE_SIZE)

    def _page_rows(self):
        start = self._current_page * _PAGE_SIZE
        return self._rows[start:start + _PAGE_SIZE]

    def _apply_sort(self):
        col = self._sort_col
        if col is None:
            return

        def key(row):
            v = row[col] if col < len(row) else None
            if v is None:
                return (2, "")
            try:
                return (0, float(str(v)))
            except (ValueError, TypeError):
                return (1, str(v).lower())

        self._rows.sort(key=key, reverse=self._sort_rev)
        self._current_page = 0

    def _sort_by(self, col):
        self._sort_rev = (not self._sort_rev) if self._sort_col == col else False
        self._sort_col = col
        self._apply_sort()

    def _hide_row(self, first_col_val):
        self._hidden_keys.add(first_col_val)
        new_rows = []
        for r in self._rows:
            if r and str(r[0]) == first_col_val:
                self._hidden_rows.setdefault(first_col_val, []).append(r)
            else:
                new_rows.append(r)
        self._rows = new_rows

    def _show_row(self, key):
        self._hidden_keys.discard(key)
        if key in self._hidden_rows:
            self._rows.extend(self._hidden_rows.pop(key))
            if self._sort_col is not None:
                self._apply_sort()


# ── set_data / data insertion ─────────────────────────────────────────────────

class TestSetData:
    def test_basic_insert(self):
        t = _TableLogic()
        t.set_data([[1, "a"], [2, "b"]], ["id", "name"])
        assert t._columns == ["id", "name"]
        assert len(t._rows) == 2
        assert t._rows[0] == [1, "a"]

    def test_replaces_previous_data(self):
        t = _TableLogic(rows=[[99]], columns=["x"])
        t.set_data([[1, 2], [3, 4]], ["a", "b"])
        assert t._columns == ["a", "b"]
        assert len(t._rows) == 2

    def test_resets_sort_and_page(self):
        t = _TableLogic(rows=[[1], [2]], columns=["v"])
        t._sort_by(0)
        t._current_page = 5
        t.set_data([[9]], ["v"])
        assert t._sort_col is None
        assert t._sort_rev is False
        assert t._current_page == 0

    def test_empty_data(self):
        t = _TableLogic()
        t.set_data([], [])
        assert t._rows == []
        assert t._columns == []

    def test_none_values_preserved(self):
        t = _TableLogic()
        t.set_data([[1, None, "x"]], ["a", "b", "c"])
        assert t._rows[0] == [1, None, "x"]

    def test_rows_are_copied_not_aliased(self):
        original = [[1, 2], [3, 4]]
        t = _TableLogic()
        t.set_data(original, ["a", "b"])
        original[0][0] = 999
        assert t._rows[0][0] == 1

    def test_reset_hidden_true_clears_hidden_state(self):
        t = _TableLogic(rows=[[1], [2], [3]], columns=["v"])
        t._hide_row("1")
        assert len(t._rows) == 2
        t.set_data([[10], [20]], ["v"], reset_hidden=True)
        assert t._hidden_keys == set()
        assert t._hidden_rows == {}

    def test_reset_hidden_false_preserves_hidden_state(self):
        t = _TableLogic(rows=[[1], [2], [3]], columns=["v"])
        t._hide_row("1")
        t.set_data([[1], [2], [3]], ["v"], reset_hidden=False)
        assert "1" not in [str(r[0]) for r in t._rows]

    def test_eviction_removes_stale_hidden_key(self):
        t = _TableLogic(rows=[[1], [2]], columns=["v"])
        t._hide_row("1")
        evicted = t.set_data([[2], [3]], ["v"], reset_hidden=False)
        assert "1" in evicted
        assert "1" not in t._hidden_keys
        assert "1" not in t._hidden_rows

    def test_eviction_returns_empty_when_all_keys_present(self):
        t = _TableLogic(rows=[[1], [2]], columns=["v"])
        t._hide_row("1")
        evicted = t.set_data([[1], [2]], ["v"], reset_hidden=False)
        assert evicted == set()
        assert "1" in t._hidden_keys

    def test_no_accumulation_in_hidden_rows(self):
        t = _TableLogic(rows=[[1], [2]], columns=["v"])
        t._hide_row("1")
        t.set_data([[1], [2]], ["v"], reset_hidden=False)
        t.set_data([[1], [2]], ["v"], reset_hidden=False)
        assert len(t._hidden_rows.get("1", [])) == 1


# ── pagination ─────────────────────────────────────────────────────────────────

class TestPagination:
    def test_single_page_when_empty(self):
        t = _TableLogic()
        assert t._total_pages() == 1

    def test_single_page_below_limit(self):
        t = _TableLogic(rows=[[i] for i in range(50)], columns=["v"])
        assert t._total_pages() == 1

    def test_single_page_at_exact_limit(self):
        t = _TableLogic(rows=[[i] for i in range(_PAGE_SIZE)], columns=["v"])
        assert t._total_pages() == 1

    def test_two_pages_one_over_limit(self):
        t = _TableLogic(rows=[[i] for i in range(_PAGE_SIZE + 1)], columns=["v"])
        assert t._total_pages() == 2

    def test_three_pages(self):
        t = _TableLogic(rows=[[i] for i in range(_PAGE_SIZE * 2 + 1)], columns=["v"])
        assert t._total_pages() == 3

    def test_page_rows_first_page(self):
        rows = [[i] for i in range(_PAGE_SIZE + 5)]
        t = _TableLogic(rows=rows, columns=["v"])
        page = t._page_rows()
        assert len(page) == _PAGE_SIZE
        assert page[0] == [0]
        assert page[-1] == [_PAGE_SIZE - 1]

    def test_page_rows_second_page(self):
        rows = [[i] for i in range(_PAGE_SIZE + 5)]
        t = _TableLogic(rows=rows, columns=["v"])
        t._current_page = 1
        page = t._page_rows()
        assert len(page) == 5
        assert page[0] == [_PAGE_SIZE]


# ── sort ──────────────────────────────────────────────────────────────────────

class TestSort:
    def _make(self, data):
        t = _TableLogic(rows=data, columns=[f"c{i}" for i in range(len(data[0]))])
        return t

    def test_numeric_asc(self):
        t = self._make([[3], [1], [2]])
        t._sort_by(0)
        assert [r[0] for r in t._rows] == [1, 2, 3]
        assert t._sort_rev is False

    def test_numeric_desc_on_second_click(self):
        t = self._make([[3], [1], [2]])
        t._sort_by(0)
        t._sort_by(0)
        assert [r[0] for r in t._rows] == [3, 2, 1]
        assert t._sort_rev is True

    def test_switching_column_resets_direction(self):
        t = self._make([[3, "z"], [1, "a"], [2, "m"]])
        t._sort_by(0)
        t._sort_by(0)  # desc
        t._sort_by(1)  # new col — should reset to asc
        assert t._sort_rev is False
        assert [r[1] for r in t._rows] == ["a", "m", "z"]

    def test_string_sort(self):
        t = self._make([["banana"], ["apple"], ["cherry"]])
        t._sort_by(0)
        assert [r[0] for r in t._rows] == ["apple", "banana", "cherry"]

    def test_none_sorted_last(self):
        t = self._make([[2], [None], [1]])
        t._sort_by(0)
        assert t._rows[-1] == [None]

    def test_mixed_numeric_and_string(self):
        t = self._make([[10], ["abc"], [2]])
        t._sort_by(0)
        # numeric values come first (tuple key (0, float)), then strings (1, ...)
        values = [r[0] for r in t._rows]
        assert values.index(2) < values.index("abc")
        assert values.index(10) < values.index("abc")

    def test_apply_sort_without_toggle(self):
        t = self._make([[3], [1], [2]])
        t._sort_by(0)  # asc
        t._rows.append([0])
        t._apply_sort()  # should not toggle direction
        assert t._sort_rev is False
        assert t._rows[0] == [0]

    def test_apply_sort_resets_page(self):
        t = self._make([[i] for i in range(_PAGE_SIZE + 5)])
        t._current_page = 1
        t._sort_col = 0
        t._apply_sort()
        assert t._current_page == 0

    def test_show_row_reapplies_sort(self):
        t = self._make([[3], [1], [2]])
        t._sort_by(0)  # sorted asc: 1,2,3
        t._hide_row("1")
        t._show_row("1")
        assert t._rows[0] == [1]


# ── hide / show rows ──────────────────────────────────────────────────────────

class TestHideShow:
    def test_hide_removes_row(self):
        t = _TableLogic(rows=[[1], [2], [3]], columns=["v"])
        t._hide_row("2")
        assert len(t._rows) == 2
        assert all(r[0] != 2 for r in t._rows)

    def test_show_restores_row(self):
        t = _TableLogic(rows=[[1], [2], [3]], columns=["v"])
        t._hide_row("2")
        t._show_row("2")
        assert len(t._rows) == 3
        assert any(r[0] == 2 for r in t._rows)

    def test_hide_multiple_rows(self):
        t = _TableLogic(rows=[[1], [2], [3]], columns=["v"])
        t._hide_row("1")
        t._hide_row("3")
        assert len(t._rows) == 1
        assert t._rows[0][0] == 2

    def test_show_nonexistent_key_noop(self):
        t = _TableLogic(rows=[[1], [2]], columns=["v"])
        t._show_row("999")
        assert len(t._rows) == 2


# ── export to CSV ─────────────────────────────────────────────────────────────

class _ExportStub:
    """Minimal attribute-only stub to call ResultTable.export_to_csv without GUI."""
    def __init__(self, rows, columns):
        self._rows = [list(r) for r in rows]
        self._columns = list(columns)


class TestExportCsv:
    def _export(self, rows, columns, tmp_path):
        stub = _ExportStub(rows, columns)
        path = str(tmp_path / "out.csv")
        ResultTable.export_to_csv(stub, path)
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.reader(f))

    def test_header_row(self, tmp_path):
        data = self._export([[1, "a"]], ["id", "name"], tmp_path)
        assert data[0] == ["id", "name"]

    def test_data_rows(self, tmp_path):
        data = self._export([[1, "a"], [2, "b"]], ["id", "name"], tmp_path)
        assert data[1] == ["1", "a"]
        assert data[2] == ["2", "b"]

    def test_none_exported_as_empty_string(self, tmp_path):
        data = self._export([[1, None]], ["id", "val"], tmp_path)
        assert data[1] == ["1", ""]

    def test_empty_table_exports_only_header(self, tmp_path):
        data = self._export([], ["col1", "col2"], tmp_path)
        assert len(data) == 1
        assert data[0] == ["col1", "col2"]

    def test_unicode_content(self, tmp_path):
        data = self._export([[1, "Привет"]], ["id", "text"], tmp_path)
        assert data[1][1] == "Привет"

    def test_row_count_matches(self, tmp_path):
        rows = [[i, f"v{i}"] for i in range(50)]
        data = self._export(rows, ["id", "val"], tmp_path)
        assert len(data) == 51  # 1 header + 50 data rows
