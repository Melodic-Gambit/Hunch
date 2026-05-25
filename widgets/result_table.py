import csv
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Optional
import theme_colors

_PAGE_SIZE = 100


class ResultTable(ctk.CTkFrame):
    """Таблица результатов SQL: заголовки из cursor.description, сортировка, копирование, pagination."""

    _last_applied_mode: str = ""
    _last_applied_accent: str = ""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._columns: list = []
        self._rows:    list = []
        self._sort_col: Optional[int] = None
        self._sort_rev: bool = False
        self._current_page: int = 0
        self._focused_col: Optional[str] = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self):
        ResultTable._apply_style()
        self._tree = ttk.Treeview(self, style="SS.Treeview",
                                   show="headings", selectmode="browse")
        self._vsb = ctk.CTkScrollbar(self, command=self._tree.yview)
        self._hsb = ctk.CTkScrollbar(self, orientation="horizontal",
                                      command=self._tree.xview)
        self._tree.configure(yscrollcommand=self._vsb.set,
                             xscrollcommand=self._hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._hsb.grid(row=1, column=0, sticky="ew")
        self._tree.bind("<Button-3>",      self._on_right_click)
        self._tree.bind("<Button-1>",      self._on_copy_click)
        self._tree.bind("<Button-1>",      self._on_cell_click, add="+")
        self._tree.bind("<Control-c>",     self._copy_row)
        self._tree.bind("<Control-C>",     self._copy_row)
        self._tree.bind("<Control-KeyPress>", self._on_ctrl_keypress)
        self._tree.bind("<Prior>", lambda e: self._page_prev()  or "break")
        self._tree.bind("<Next>",  lambda e: self._page_next()  or "break")
        self._tree.bind("<Home>",  lambda e: self._page_first() or "break")
        self._tree.bind("<End>",   lambda e: self._page_last()  or "break")

        # ── pagination bar (row=2, скрыта по умолчанию) ──────────────────────
        self._pag_bar = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self._pag_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(2, 2))
        self._pag_bar.grid_columnconfigure(1, weight=1)

        self._btn_prev = ctk.CTkButton(
            self._pag_bar, text="←", width=32, height=24,
            fg_color="transparent",
            hover_color=("gray70", "gray40"),
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._page_prev,
        )
        self._btn_prev.grid(row=0, column=0, padx=(0, 4))

        self._pag_label = ctk.CTkLabel(
            self._pag_bar, text="1 / 1",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray70"),
            anchor="center",
        )
        self._pag_label.grid(row=0, column=1)

        self._btn_next = ctk.CTkButton(
            self._pag_bar, text="→", width=32, height=24,
            fg_color="transparent",
            hover_color=("gray70", "gray40"),
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._page_next,
        )
        self._btn_next.grid(row=0, column=2, padx=(4, 0))

        self._pag_bar.grid_remove()

        self._empty_lbl = ctk.CTkLabel(
            self,
            text="(нет данных)",
            font=ctk.CTkFont(size=13),
            text_color=("#808080", theme_colors.accent()),
        )
        self._render()

    # ── стиль (обновляется при смене темы) ───────────────────────────────────

    @staticmethod
    def _apply_style():
        mode   = ctk.get_appearance_mode()
        accent = theme_colors.accent()
        if (mode   == ResultTable._last_applied_mode
                and accent == ResultTable._last_applied_accent):
            return
        ResultTable._last_applied_mode   = mode
        ResultTable._last_applied_accent = accent
        s = ttk.Style()
        try:
            if s.theme_use() in ('vista', 'xpnative', 'winnative'):
                s.theme_use('clam')
        except Exception:
            pass
        dark = mode == "Dark"
        bg   = "#2b2b2b" if dark else "#dbdbdb"
        fg   = "#dcddde" if dark else "#1a1a1a"
        hdr  = "#3a3a3a" if dark else "#c5c5c5"
        sel  = theme_colors.accent()
        s.configure("SS.Treeview",
                    background=bg, foreground=fg, fieldbackground=bg,
                    rowheight=24, borderwidth=0, font=("Segoe UI", 10))
        s.configure("SS.Treeview.Heading",
                    background=hdr, foreground=fg, relief="flat",
                    font=("Segoe UI", 10, "bold"), padding=(6, 3))
        s.map("SS.Treeview",
              background=[("selected", sel)],
              foreground=[("selected", "#ffffff")])
        s.map("SS.Treeview.Heading",
              background=[("active", sel)])

    def refresh_style(self):
        ResultTable._last_applied_mode = ""
        ResultTable._apply_style()
        self._render()

    def update_accent(self, new_accent: str):
        """Обновляет акцентный цвет при живой смене темы."""
        try:
            self._empty_lbl.configure(text_color=("#808080", new_accent))
        except Exception:
            pass
        ResultTable._last_applied_mode = ""
        ResultTable._apply_style()
        self._render()

    # ── данные ───────────────────────────────────────────────────────────────

    def set_data(self, rows: list, columns: list):
        self._rows    = [list(r) for r in rows]
        self._columns = list(columns)
        self._sort_col = None
        self._sort_rev = False
        self._current_page = 0
        self._render()

    def _total_pages(self) -> int:
        if not self._rows:
            return 1
        return max(1, (len(self._rows) + _PAGE_SIZE - 1) // _PAGE_SIZE)

    def _page_rows(self) -> list:
        start = self._current_page * _PAGE_SIZE
        return self._rows[start:start + _PAGE_SIZE]

    def _page_prev(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._render()

    def _page_next(self):
        if self._current_page < self._total_pages() - 1:
            self._current_page += 1
            self._render()

    def _page_first(self):
        if self._current_page != 0:
            self._current_page = 0
            self._render()

    def _page_last(self):
        last = self._total_pages() - 1
        if self._current_page != last:
            self._current_page = last
            self._render()

    def _render(self):
        self._tree.delete(*self._tree.get_children())
        if not self._columns:
            self._tree.grid_remove()
            self._vsb.grid_remove()
            self._hsb.grid_remove()
            self._pag_bar.grid_remove()
            self._empty_lbl.grid(row=0, column=0, columnspan=2, sticky="nsew")
            return

        ResultTable._apply_style()
        self._empty_lbl.grid_remove()
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._hsb.grid(row=1, column=0, sticky="ew")

        total = self._total_pages()
        if total > 1:
            self.grid_rowconfigure(2, weight=0)
            self._pag_bar.grid()
            cur = self._current_page
            start_row = cur * _PAGE_SIZE + 1
            end_row   = min((cur + 1) * _PAGE_SIZE, len(self._rows))
            self._pag_label.configure(
                text=f"стр. {cur + 1} / {total}  ({start_row}–{end_row} из {len(self._rows)})"
            )
            self._btn_prev.configure(
                state="normal" if cur > 0 else "disabled",
                text_color=("gray10", "gray90") if cur > 0 else ("gray60", "gray45"),
            )
            self._btn_next.configure(
                state="normal" if cur < total - 1 else "disabled",
                text_color=("gray10", "gray90") if cur < total - 1 else ("gray60", "gray45"),
            )
        else:
            self._pag_bar.grid_remove()

        col_ids = ["_copy_", "_row_"] + [f"c{i}" for i in range(len(self._columns))]
        self._tree["columns"] = col_ids

        self._tree.heading("_copy_", text="⎘")
        self._tree.column("_copy_", width=26, minwidth=26, stretch=False)

        self._tree.heading("_row_", text="№")
        self._tree.column("_row_", width=40, minwidth=30, stretch=False, anchor="e")

        page_rows = self._page_rows()
        for i, (cid, name) in enumerate(zip(col_ids[2:], self._columns)):
            arrow  = (" ▲" if not self._sort_rev else " ▼") if self._sort_col == i else ""
            self._tree.heading(cid, text=name + arrow,
                               command=lambda c=i: self._sort_by(c))
            sample = [str(r[i]) for r in page_rows[:80] if i < len(r)]
            chars  = max([len(name)] + [len(v) for v in sample], default=4)
            self._tree.column(cid, width=min(max(chars * 8 + 16, 60), 360),
                              minwidth=50, stretch=True)

        dark = ctk.get_appearance_mode() == "Dark"
        self._tree.tag_configure("r0", background="#2b2b2b" if dark else "#dbdbdb")
        self._tree.tag_configure("r1", background="#333333" if dark else "#d0d0d0")
        row_offset = self._current_page * _PAGE_SIZE
        for i, row in enumerate(page_rows):
            vals = ["⎘", str(row_offset + i + 1)] + ["NULL" if v is None else str(v) for v in row]
            self._tree.insert("", "end", values=vals, tags=(f"r{i % 2}",))

    # ── сортировка ────────────────────────────────────────────────────────────

    def _sort_by(self, col: int):
        self._sort_rev = (not self._sort_rev) if self._sort_col == col else False
        self._sort_col = col

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
        self._render()

    # ── копирование ───────────────────────────────────────────────────────────

    def _cell_value(self, event) -> Optional[str]:
        item = self._tree.identify_row(event.y)
        col  = self._tree.identify_column(event.x)
        if not item or not col:
            return None
        idx  = int(col.lstrip("#")) - 1
        if idx <= 1:  # _copy_ or _row_ column
            return None
        vals = self._tree.item(item, "values")
        return vals[idx] if idx < len(vals) else None

    def _on_right_click(self, event):
        item = self._tree.identify_row(event.y)
        if not item:
            return
        self._tree.selection_set(item)
        cell_val = self._cell_value(event)
        all_vals = self._tree.item(item, "values")
        row_text = "\t".join(str(v) for v in all_vals[2:])  # skip _copy_ and _row_ columns
        menu = tk.Menu(self, tearoff=0)
        if cell_val is not None:
            menu.add_command(label="Копировать ячейку",
                             command=lambda: self._clip(cell_val))
        menu.add_command(label="Копировать строку",
                         command=lambda: self._clip(row_text))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_copy_click(self, event):
        col = self._tree.identify_column(event.x)
        if col != "#1":
            return
        item = self._tree.identify_row(event.y)
        if not item:
            return
        self._copy_row_column_format(item)

    def _copy_row_column_format(self, item):
        vals = self._tree.item(item, "values")
        actual_vals = vals[2:]  # skip _copy_ and _row_ columns
        self._clip("\n".join(str(v) for v in actual_vals))
        try:
            self._tree.set(item, "_copy_", "✓")
            self.after(600, lambda: self._restore_copy_icon(item))
        except Exception:
            pass

    def _restore_copy_icon(self, item):
        try:
            if self._tree.exists(item):
                self._tree.set(item, "_copy_", "⎘")
        except Exception:
            pass

    def _on_cell_click(self, event):
        if self._tree.identify_region(event.x, event.y) == "cell":
            self._focused_col = self._tree.identify_column(event.x)

    def _on_ctrl_keypress(self, event):
        if event.keycode == 67:
            return self._copy_row(event)

    def _copy_row(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return "break"
        values = self._tree.item(sel[0], "values")
        if self._focused_col and self._focused_col not in ("#1", "#2"):
            col_idx = int(self._focused_col.lstrip("#")) - 1
            if 0 <= col_idx < len(values):
                self._clip(str(values[col_idx]))
                return "break"
        self._clip("\t".join(str(v) for v in values[2:]))  # skip _copy_ and _row_
        return "break"

    def _clip(self, text: str):
        top = self.winfo_toplevel()
        top.clipboard_clear()
        top.clipboard_append(str(text))

    def export_to_csv(self, filepath: str):
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(self._columns)
            for row in self._rows:
                writer.writerow(["" if v is None else v for v in row])

    def export_to_excel(self, filepath: str):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            tk.messagebox.showerror(
                "Ошибка экспорта",
                "Библиотека openpyxl не установлена.\n"
                "Выполните: pip install openpyxl",
            )
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Результаты"
        ws.append(list(self._columns))
        header_fill = PatternFill("solid", fgColor="0D9488")
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        for row in self._rows:
            ws.append(["" if v is None else v for v in row])
        for col in ws.columns:
            max_len = max((len(str(cell.value or "")) for cell in col), default=0)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 3, 50)
        ws.freeze_panes = "A2"
        wb.save(filepath)
