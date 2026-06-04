"""Queries tab — mixin для MainWindow.

Содержит все методы вкладки «Запросы», авто-обновления, кэширования,
статистики, истории алертов и вспомогательных таймеров.
Примешивается к MainWindow через множественное наследование.
"""
from __future__ import annotations

import json
import os
import re
import datetime
import time
import threading
from typing import Optional
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog

import dialogs as messagebox
from query_dialog import QueryDialog


class QueriesTabMixin:
    """Методы вкладки «Запросы».  Примешиваются к MainWindow."""

    # ── Запросы ───────────────────────────────────────────────────────────────

    _Q_HEADERS  = ("Название", "SQL-запрос", "База данных",
                   "Последнее обновление", "Обновлять каждые", "", "")
    _Q_WEIGHTS  = (2,  4,  2,  2,  1,  0,  0)
    _Q_MIN_W    = (110, 140, 100, 120, 90, 90, 90)

    def _show_query_stats_dialog(self):
        """Диалог статистики выполнения запросов (топ-10 по среднему времени)."""
        dlg = ctk.CTkToplevel(self)
        dlg.withdraw()
        dlg.title("Статистика запросов")
        dlg.resizable(True, True)
        dlg.minsize(700, 380)
        dlg.transient(self)

        def _on_close():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()
        dlg.protocol("WM_DELETE_WINDOW", _on_close)

        # ── заголовок ─────────────────────────────────────────────────────────
        hdr_row = ctk.CTkFrame(dlg, fg_color="transparent")
        hdr_row.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(hdr_row,
                     text="Статистика выполнения запросов",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkLabel(hdr_row, text="• нажмите на строку для детализации",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray55")).pack(side="left", padx=(12, 0))
        ctk.CTkButton(hdr_row, text="Очистить", width=90, height=28,
                      fg_color=("gray55", "gray35"), hover_color=("gray45", "gray25"),
                      command=lambda: _refresh(clear=True)).pack(side="right")
        ctk.CTkButton(hdr_row, text="Экспорт CSV", width=110, height=28,
                      command=lambda: _export_csv()).pack(side="right", padx=(0, 8))

        # ── таблица ───────────────────────────────────────────────────────────
        HDRS = ("Запрос", "Запусков", "Ошибок", "Ср. время (мс)",
                "Макс. (мс)", "Ср. строк", "Последний запуск")
        WGTS = (1, 0, 0, 0, 0, 0, 0)
        MINS = (180, 70, 60, 110, 90, 80, 140)

        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        scroll.grid_columnconfigure(0, weight=1)

        def _show_detail(query_file: str, query_name: str):
            detail = ctk.CTkToplevel(dlg)
            detail.withdraw()
            detail.title(f"Детализация: {query_name}")
            detail.resizable(True, True)
            detail.minsize(520, 340)
            detail.transient(dlg)
            detail.protocol("WM_DELETE_WINDOW", detail.destroy)

            ctk.CTkLabel(
                detail,
                text=f"Последние запуски: {query_name}",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(fill="x", padx=16, pady=(14, 2))
            ctk.CTkLabel(
                detail,
                text=f"файл: {query_file}",
                font=ctk.CTkFont(size=11),
                text_color=("gray50", "gray55"),
                anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 6))

            D_HDRS = ("#", "Время запуска", "Длительность (мс)", "Строк", "Статус")
            D_WGTS = (0, 1, 0, 0, 0)
            D_MINS = (40, 160, 130, 70, 90)

            dscroll = ctk.CTkScrollableFrame(detail, fg_color="transparent")
            dscroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
            dscroll.grid_columnconfigure(0, weight=1)

            recent = self.stats_manager.get_recent(query_file, limit=20)
            dtbl = ctk.CTkFrame(dscroll, fg_color="transparent")
            dtbl.grid(row=0, column=0, sticky="ew")
            dscroll.grid_columnconfigure(0, weight=1)

            for i, (h, wt, mw) in enumerate(zip(D_HDRS, D_WGTS, D_MINS)):
                dtbl.grid_columnconfigure(i, weight=wt, minsize=mw)
                ctk.CTkLabel(
                    dtbl, text=h, anchor="w",
                    font=ctk.CTkFont(weight="bold"),
                    fg_color=("gray78", "gray25"),
                ).grid(row=0, column=i, padx=6, pady=4, sticky="nsew")

            if not recent:
                ctk.CTkLabel(dscroll, text="Нет данных",
                             text_color=("gray50", "gray60")).grid(
                    row=1, column=0, pady=20)
            else:
                dsm = ctk.CTkFont(size=12)
                for ri, r in enumerate(recent):
                    bg = ("gray88", "gray20") if ri % 2 == 0 else ("gray83", "gray17")
                    is_err = bool(r["is_error"])
                    dvals = [
                        str(ri + 1),
                        r["ts"],
                        f'{r["duration_ms"]:.0f}',
                        str(r["row_count"]),
                        "❌ Ошибка" if is_err else "✅ OK",
                    ]
                    for ci, val in enumerate(dvals):
                        lbl = ctk.CTkLabel(dtbl, text=val, anchor="w",
                                           fg_color=bg, font=dsm)
                        if ci == 4:
                            lbl.configure(
                                text_color=("#DC2626", "#F87171") if is_err
                                else ("#16A34A", "#4ADE80"))
                        lbl.grid(row=ri + 1, column=ci, padx=6, pady=2, sticky="nsew")

            def _dcenter():
                detail.update_idletasks()
                pw = dlg.winfo_width(); ph = dlg.winfo_height()
                px = dlg.winfo_rootx(); py = dlg.winfo_rooty()
                w  = detail.winfo_reqwidth()
                h  = detail.winfo_reqheight()
                detail.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
                detail.deiconify()
                detail.lift()

            detail.after(60, _dcenter)

        def _export_csv():
            import csv
            path = filedialog.asksaveasfilename(
                parent=dlg,
                defaultextension=".csv",
                filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
                title="Сохранить статистику как CSV",
            )
            if not path:
                return
            rows = self.stats_manager.get_summary(limit=50)
            dm = self.data_manager
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(HDRS)
                    for row in rows:
                        qname = dm.get_query_display_name(row["query_file"]) or row["query_file"]
                        writer.writerow([
                            qname,
                            row["total_runs"],
                            row["error_count"],
                            f'{row["avg_ms"]:.0f}',
                            f'{row["max_ms"]:.0f}',
                            f'{row["avg_rows"]:.0f}',
                            row["last_run"] or "",
                        ])
            except OSError as e:
                import dialogs as _mb
                _mb.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}", parent=dlg)

        def _refresh(clear: bool = False):
            if clear:
                self.stats_manager.clear()
            for w in scroll.winfo_children():
                w.destroy()
            rows = self.stats_manager.get_summary(limit=50)
            tbl = ctk.CTkFrame(scroll, fg_color="transparent")
            tbl.grid(row=0, column=0, sticky="ew")
            scroll.grid_columnconfigure(0, weight=1)
            for i, (h, wt, mw) in enumerate(zip(HDRS, WGTS, MINS)):
                tbl.grid_columnconfigure(i, weight=wt, minsize=mw)
                ctk.CTkLabel(
                    tbl, text=h, anchor="w",
                    font=ctk.CTkFont(weight="bold"),
                    fg_color=("gray78", "gray25"),
                ).grid(row=0, column=i, padx=6, pady=4, sticky="nsew")
            if not rows:
                ctk.CTkLabel(scroll, text="Нет данных",
                             text_color=("gray50", "gray60")).grid(
                    row=1, column=0, pady=20)
                return
            dm = self.data_manager
            sm = ctk.CTkFont(size=12)
            for ri, row in enumerate(rows):
                bg = ("gray88", "gray20") if ri % 2 == 0 else ("gray83", "gray17")
                bg_hover = ("gray80", "gray28")
                qname = dm.get_query_display_name(row["query_file"]) or row["query_file"]
                vals = [
                    qname,
                    str(row["total_runs"]),
                    str(row["error_count"]),
                    f'{row["avg_ms"]:.0f}',
                    f'{row["max_ms"]:.0f}',
                    f'{row["avg_rows"]:.0f}',
                    row["last_run"] or "—",
                ]
                row_lbls = []
                for ci, val in enumerate(vals):
                    lbl = ctk.CTkLabel(tbl, text=val, anchor="w",
                                       fg_color=bg, font=sm, cursor="hand2")
                    lbl.grid(row=ri + 1, column=ci, padx=6, pady=2, sticky="nsew")
                    row_lbls.append(lbl)
                _qf, _qn = row["query_file"], qname
                for lbl in row_lbls:
                    lbl.bind("<Button-1>",
                             lambda e, f=_qf, n=_qn: _show_detail(f, n))
                    lbl.bind("<Enter>",
                             lambda e, ls=row_lbls: [l.configure(fg_color=bg_hover) for l in ls])
                    lbl.bind("<Leave>",
                             lambda e, ls=row_lbls, c=bg: [l.configure(fg_color=c) for l in ls])

        _refresh()

        dlg.update_idletasks()
        pw = self.winfo_width(); ph = self.winfo_height()
        px = self.winfo_rootx(); py = self.winfo_rooty()
        w  = dlg.winfo_reqwidth()
        h  = dlg.winfo_reqheight()
        dlg.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        dlg.deiconify()

        def _safe_grab():
            try:
                dlg.grab_set()
            except Exception:
                pass
        dlg.after(20, _safe_grab)
        dlg.lift()

    def setup_queries_tab(self):
        self.frame_queries.grid_columnconfigure(0, weight=1)
        self.frame_queries.grid_rowconfigure(1, weight=1)

        # ── тулбар (row 0, аналог Логи) ───────────────────────────────────────
        query_toolbar = ctk.CTkFrame(self.frame_queries, fg_color="transparent")
        query_toolbar.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")

        self._query_search_var = ctk.StringVar()
        self._query_search_var.trace_add("write", lambda *_: self._on_query_search_changed())

        self._query_clear_btn = ctk.CTkButton(
            query_toolbar, text="✕", width=24, height=28,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=lambda: self._query_search_var.set(""))
        self._query_clear_btn.pack(side="right", padx=(0, 2))
        self._query_clear_btn.pack_forget()

        ctk.CTkEntry(query_toolbar, textvariable=self._query_search_var,
                     placeholder_text="Поиск...",
                     width=190, height=28).pack(side="right")

        ctk.CTkLabel(query_toolbar, text="🔍",
                     font=ctk.CTkFont(size=20)).pack(side="right", padx=(16, 6), anchor="center")

        ctk.CTkButton(
            query_toolbar, text="📊 Статистика",
            command=self._show_query_stats_dialog,
            width=120, height=28,
        ).pack(side="left", padx=(0, 8))

        self._queries_scroll = ctk.CTkScrollableFrame(
            self.frame_queries, fg_color="transparent")
        self._queries_scroll.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self._queries_scroll.grid_columnconfigure(0, weight=1)

        self.refresh_queries_list()

    def refresh_queries_list(self):
        for w in self._queries_scroll.winfo_children():
            w.destroy()

        sort_col, sort_rev = self._query_sort
        bold   = ctk.CTkFont(weight="bold")
        HDR_BG = ("gray78", "gray25")

        # ── предварительное чтение файлов ────────────────────────────────────
        _files = None        # None = папка не существует
        _read_error = None
        _qry_dir = self.data_manager.queries_dir
        if os.path.exists(_qry_dir):
            try:
                _files = [f for f in os.listdir(_qry_dir) if f.endswith(".sql")]
            except Exception as e:
                _read_error = e
                self.log_manager.add_log(f"Ошибка чтения queries: {e}", "ERROR")

        # ── фильтрация по поиску ──────────────────────────────────────────────
        _qsearch = getattr(self, "_query_search_var", None)
        _qq = _qsearch.get().strip().lower() if _qsearch else ""
        if _qq and _files:
            _files = [f for f in _files
                      if _qq in self.data_manager.get_query_display_name(f).lower()]

        _query_has_items = bool(_files)

        if _query_has_items:
            # ── единый фрейм таблицы: заголовок + строки в одной сетке ──────
            tbl = ctk.CTkFrame(self._queries_scroll, fg_color="transparent")
            tbl.grid(row=0, column=0, sticky="ew")
            self._apply_col_config(tbl, self._Q_WEIGHTS, self._Q_MIN_W)

            # ── заголовок (строка 0 в tbl) ────────────────────────────────────
            for i, h in enumerate(self._Q_HEADERS):
                if self._Q_WEIGHTS[i] == 0:
                    ctk.CTkLabel(tbl, text="", fg_color="transparent").grid(
                        row=0, column=i, padx=6, pady=5, sticky="nsew")
                    continue
                arrow = (" ▲" if not sort_rev else " ▼") if sort_col == i else ""
                lbl = ctk.CTkLabel(tbl, text=h + arrow, font=bold,
                                   anchor="w", cursor="hand2", fg_color=HDR_BG)
                lbl.grid(row=0, column=i, padx=6, pady=5, sticky="nsew")
                lbl.bind("<Button-1>", lambda e, c=i: self._query_sort_click(c))

            # ── строки данных ─────────────────────────────────────────────────
            for row_idx, f in enumerate(self._sorted_query_files(_files)):
                r = row_idx + 1
                display_name = self.data_manager.get_query_display_name(f)
                try:
                    with open(os.path.join(_qry_dir, f),
                              encoding="utf-8") as fh:
                        raw = fh.read().replace("\n", " ").strip()
                    sql_preview = raw[:30] + ("..." if len(raw) > 30 else "")
                except Exception:
                    sql_preview = "—"

                meta     = self._get_query_meta(f)
                db_name  = meta.get("database", "—") or "—"
                last_upd = meta.get("last_updated", "—") or "—"
                interval = meta.get("update_interval", 0)
                cron_m   = meta.get("cron_schedule") or {}
                if cron_m.get("enabled"):
                    _days_map = {0:"Пн",1:"Вт",2:"Ср",3:"Чт",4:"Пт",5:"Сб",6:"Вс"}
                    _days = cron_m.get("days", [])
                    _dstr = ",".join(_days_map[d] for d in _days) if _days else "каждый день"
                    istr = f"⏰ {cron_m.get('time','?')} ({_dstr})"
                elif interval:
                    istr = f"{interval} мин."
                else:
                    istr = "—"
                bg = ("gray88", "gray20") if row_idx % 2 == 0 \
                    else ("gray83", "gray17")

                # ── данные (col 0-4) ──────────────────────────────────────────
                for ci, val in enumerate(
                        (display_name, sql_preview, db_name, last_upd, istr)):
                    ctk.CTkLabel(tbl, text=val, anchor="w",
                                 fg_color=bg).grid(
                        row=r, column=ci, padx=6, pady=3, sticky="nsew")

                # ── кнопки (col 5, 6) ─────────────────────────────────────────
                ctk.CTkButton(
                    tbl, text="Изменить",
                    width=self._Q_MIN_W[5], height=26,
                    command=lambda n=display_name: self._edit_query_by_name(n)
                ).grid(row=r, column=5, padx=6, pady=3)

                ctk.CTkButton(
                    tbl, text="Удалить",
                    width=self._Q_MIN_W[6], height=26,
                    fg_color=("#E53935", "#C62828"),
                    hover_color=("#C62828", "#B71C1C"),
                    command=lambda n=display_name: self._delete_query_by_name(n)
                ).grid(row=r, column=6, padx=6, pady=3)

                # ── контекстное меню на строке ────────────────────────────────
                for child in tbl.grid_slaves(row=r):
                    child.bind(
                        "<Button-3>",
                        lambda e, n=display_name:
                            self._show_query_ctx_menu(e, n),
                        add="+")

            # ── кнопка "Добавить" после таблицы ──────────────────────────────
            ctk.CTkButton(
                self._queries_scroll, text="+ Добавить запрос",
                command=self.add_new_query, height=32, anchor="w"
            ).grid(row=1, column=0, padx=6, pady=(6, 4), sticky="w")

        else:
            # ── пустое состояние или ошибка ───────────────────────────────────
            if _files is None:
                self._build_empty_state(
                    self._queries_scroll, 0,
                    "⚠️", "Папка queries не найдена",
                    "Создайте папку queries рядом с программой",
                    "+ Добавить запрос", self.add_new_query)
            elif _read_error is not None:
                ctk.CTkLabel(self._queries_scroll,
                             text=f"Ошибка: {_read_error}").grid(
                    row=0, column=0, padx=10, pady=5)
            else:
                self._build_empty_state(
                    self._queries_scroll, 0,
                    "📝", "Нет запросов",
                    "Добавьте первый SQL-запрос для дашборда",
                    "+ Добавить запрос", self.add_new_query)

        self._refresh_widgets_table()

    # ── метаданные запросов ───────────────────────────────────────────────────

    def _get_query_meta(self, filename: str) -> dict:
        return dict(self.settings_manager.get_setting(
            "queries_meta", {}).get(filename, {}))

    def _set_query_meta(self, filename: str, **kwargs):
        all_meta = dict(self.settings_manager.get_setting("queries_meta", {}))
        meta = dict(all_meta.get(filename, {}))
        meta.update(kwargs)
        all_meta[filename] = meta
        self.settings_manager.set_setting("queries_meta", all_meta)

    def _del_query_meta(self, filename: str):
        all_meta = dict(self.settings_manager.get_setting("queries_meta", {}))
        all_meta.pop(filename, None)
        self.settings_manager.set_setting("queries_meta", all_meta)

    # ── редактирование запроса ────────────────────────────────────────────────

    def _edit_query_by_name(self, name: str):
        self._selected_query_name = name
        filename = self.get_filename_by_display_name(name, self.data_manager.queries_dir, ".sql")
        if not filename:
            messagebox.showwarning("Предупреждение", "Файл запроса не найден")
            return

        query_path = os.path.join(self.data_manager.queries_dir, filename)
        try:
            with open(query_path, encoding="utf-8") as f:
                sql = f.read()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить запрос:\n{e}")
            return

        meta     = self._get_query_meta(filename)
        db_names = self._get_db_names()
        dialog   = QueryDialog(
            self, db_names,
            initial_name=name,
            initial_db=meta.get("database", ""),
            initial_sql=sql,
            initial_interval=meta.get("update_interval", 0),
            initial_alert_on_change=meta.get("alert_on_change", False),
            initial_alert_threshold=meta.get("alert_threshold"),
            initial_is_widget=meta.get("is_widget", False),
            initial_cron_schedule=meta.get("cron_schedule"),
            db_manager=self.db_manager,
            db_name_map=self._get_db_name_map(),
            settings_manager=self.settings_manager,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return

        new_name, new_db, new_sql, new_interval, new_alert_on_change, \
            new_alert_threshold, new_is_widget, new_cron = dialog.result

        if new_name != name:
            new_filename = f"{new_name}.sql"
            new_path = os.path.join(self.data_manager.queries_dir, new_filename)
            if os.path.exists(new_path):
                messagebox.showerror("Ошибка", f"Запрос '{new_name}' уже существует")
                return
            os.remove(query_path)
            self.data_manager.delete_query_name(filename)
            old_meta = self._get_query_meta(filename)
            self._del_query_meta(filename)
        else:
            new_filename = filename
            new_path     = query_path
            old_meta     = meta

        with open(new_path, "w", encoding="utf-8") as f:
            f.write(new_sql)
        self.data_manager.set_query_display_name(new_filename, new_name)
        self._set_query_meta(new_filename,
                             database=new_db,
                             update_interval=new_interval,
                             cron_schedule=new_cron,
                             last_updated=old_meta.get("last_updated", "—"),
                             alert_on_change=new_alert_on_change,
                             alert_threshold=new_alert_threshold,
                             is_widget=new_is_widget,
                             widget_viz_config=old_meta.get("widget_viz_config"))

        self._selected_query_name = new_name
        self.refresh_queries_list()
        self._refresh_panel_query_lists()
        self._refresh_header_widgets()
        self.log_manager.add_log(f"Запрос изменён: {name} → {new_name}")
        self._restart_auto_timers()

    def add_new_query(self):
        db_names = self._get_db_names()
        dialog = QueryDialog(self, db_names,
                             db_manager=self.db_manager,
                             db_name_map=self._get_db_name_map(),
                             settings_manager=self.settings_manager)
        self.wait_window(dialog)
        if not dialog.result:
            return

        name, db, sql, interval, alert_on_change, alert_threshold, is_widget, cron = dialog.result
        if self.data_manager.add_new_query(name, sql):
            filename = f"{name}.sql"
            self.data_manager.set_query_display_name(filename, name)
            self._set_query_meta(filename,
                                 database=db,
                                 update_interval=interval,
                                 cron_schedule=cron,
                                 last_updated="—",
                                 alert_on_change=alert_on_change,
                                 alert_threshold=alert_threshold,
                                 is_widget=is_widget)
            self.refresh_queries_list()
            self._refresh_panel_query_lists()
            self._refresh_header_widgets()
            self.log_manager.add_log(f"Добавлен запрос: {name}")
            messagebox.showinfo("Успех", f"Запрос '{name}' добавлен")
            self._restart_auto_timers()
        else:
            messagebox.showerror("Ошибка", f"'{name}' уже существует")

    def _get_db_names(self) -> list:
        _dir = self.data_manager.config_dir
        if not os.path.exists(_dir):
            return []
        try:
            return [self.data_manager.get_db_display_name(f)
                    for f in os.listdir(_dir) if f.endswith(".json")]
        except Exception:
            return []

    def _get_db_name_map(self) -> dict:
        """Возвращает {display_name: config_name_без_расширения} для EXPLAIN-валидации."""
        _dir = self.data_manager.config_dir
        if not os.path.exists(_dir):
            return {}
        try:
            return {self.data_manager.get_db_display_name(f): f[:-5]
                    for f in os.listdir(_dir) if f.endswith(".json")}
        except Exception:
            return {}

    def _delete_query_by_name(self, name: str):
        fname = self.get_filename_by_display_name(name, self.data_manager.queries_dir, ".sql")
        if not fname:
            return
        if messagebox.askyesno("Подтверждение", f"Удалить '{name}'?"):
            if self.data_manager.delete_query(fname):
                self._del_query_meta(fname)
                if self._selected_query_name == name:
                    self._selected_query_name = None
                self.refresh_queries_list()
                self._refresh_panel_query_lists()
                self.log_manager.add_log(f"Удалён запрос: {name}")
                self._restart_auto_timers()

    # ── сортировка запросов ───────────────────────────────────────────────────

    def _query_sort_click(self, col: int):
        c, r = self._query_sort
        self._query_sort = (col, not r if col == c else False)
        self.refresh_queries_list()

    def _sorted_query_files(self, files: list) -> list:
        col, rev = self._query_sort
        if col is None:
            return files

        def key(f):
            display = self.data_manager.get_query_display_name(f)
            try:
                with open(os.path.join(self.data_manager.queries_dir, f), encoding="utf-8") as fh:
                    raw = fh.read().replace("\n", " ").strip()
                sql_preview = raw[:30]
            except Exception:
                sql_preview = ""
            meta = self._get_query_meta(f)
            db   = meta.get("database", "") or ""
            upd  = meta.get("last_updated", "") or ""
            iv   = meta.get("update_interval", 0)
            vals = [display, sql_preview, db, upd, str(iv) if iv else ""]
            v = vals[col] if col < len(vals) else ""
            try:
                return (0, float(v))
            except (ValueError, TypeError):
                return (1, str(v).lower())

        return sorted(files, key=key, reverse=rev)

    def _show_query_ctx_menu(self, event, display_name: str):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Изменить",
                         command=lambda: self._edit_query_by_name(display_name))
        menu.add_command(label="Удалить",
                         command=lambda: self._delete_query_by_name(display_name))
        menu.add_separator()
        menu.add_command(label="Просмотреть SQL",
                         command=lambda: self._show_sql_viewer(display_name))
        menu.add_command(label="История",
                         command=lambda: self._show_query_history(display_name))
        menu.add_separator()
        menu.add_command(label="Копировать имя",
                         command=lambda: self._clip(display_name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _clip(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(str(text))

    def _show_sql_viewer(self, display_name: str):
        """Read-only диалог с полным текстом SQL-запроса."""
        query_file = self._find_query_file(display_name)
        if not query_file:
            return
        try:
            with open(os.path.join(self.data_manager.queries_dir, query_file), encoding="utf-8") as fh:
                sql = fh.read()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"SQL — {display_name}")
        dlg.transient(self)
        def _safe_grab_sql():
            try:
                dlg.grab_set()
            except Exception:
                pass
        dlg.after(20, _safe_grab_sql)
        dlg.geometry("720x520")
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(0, weight=1)
        dlg.resizable(True, True)

        # Text-виджет (read-only, моноширинный)
        txt = tk.Text(
            dlg, wrap="none",
            font=("Courier New", 11),
            padx=10, pady=10,
            state="disabled",
            relief="flat", borderwidth=0)
        txt.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0))

        sb_y = ctk.CTkScrollbar(dlg, command=txt.yview)
        sb_y.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=(8, 0))
        sb_x = ctk.CTkScrollbar(dlg, orientation="horizontal", command=txt.xview)
        sb_x.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 4))
        txt.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        # Подстройка цветов под тему
        _is_dark = ctk.get_appearance_mode().lower() == "dark"
        txt.configure(
            background="#1e1e1e" if _is_dark else "#f8f8f8",
            foreground="#d4d4d4" if _is_dark else "#1e1e1e",
            selectbackground="#264f78" if _is_dark else "#b3d7ff")

        # Вставляем SQL и подсвечиваем ключевые слова
        txt.configure(state="normal")
        txt.insert("1.0", sql)
        _kw_color = "#569cd6" if _is_dark else "#0000ff"
        _fn_color  = "#dcdcaa" if _is_dark else "#795e26"
        txt.tag_configure("kw", foreground=_kw_color)
        txt.tag_configure("fn", foreground=_fn_color)
        _KEYWORDS = (
            r"\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|CROSS|ON|"
            r"GROUP\s+BY|ORDER\s+BY|HAVING|INSERT|INTO|UPDATE|SET|DELETE|"
            r"CREATE|ALTER|DROP|WITH|UNION|ALL|AS|AND|OR|NOT|IN|EXISTS|"
            r"CASE|WHEN|THEN|ELSE|END|DISTINCT|LIMIT|TOP|OFFSET|FETCH|"
            r"NULL|IS|BETWEEN|LIKE|ASC|DESC|BY|OVER|PARTITION)\b"
        )
        import re
        for m in re.finditer(_KEYWORDS, sql, re.IGNORECASE):
            s = f"1.0+{m.start()}c"
            e = f"1.0+{m.end()}c"
            txt.tag_add("kw", s, e)
        txt.configure(state="disabled")

        def _close_sql():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()
            try:
                self.focus_set()
            except Exception:
                pass

        ctk.CTkButton(dlg, text="Закрыть", command=_close_sql,
                      width=100).grid(row=2, column=0, columnspan=2, pady=(0, 8))
        dlg.bind("<Escape>", lambda _: _close_sql())
        dlg.bind("<Return>", lambda _: _close_sql())
        dlg.protocol("WM_DELETE_WINDOW", _close_sql)

        dlg.update_idletasks()
        w, h = 720, 520
        x = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def _show_query_history(self, display_name: str):
        """Диалог истории выполнения запроса: список N последних результатов."""
        query_file = self._find_query_file(display_name)
        if not query_file:
            return
        hist = self._query_history.get(query_file, [])
        if not hist:
            messagebox.showinfo("История", f"Нет сохранённых результатов для «{display_name}».\n"
                                           "История накапливается после каждого авто-запроса.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"История — {display_name}")
        dlg.transient(self)
        def _safe_grab_hist():
            try:
                dlg.grab_set()
            except Exception:
                pass
        dlg.after(20, _safe_grab_hist)
        dlg.geometry("900x580")
        dlg.resizable(True, True)
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        # ── заголовок с выбором записи ─────────────────────────────────────────
        top_f = ctk.CTkFrame(dlg, fg_color="transparent")
        top_f.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        top_f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top_f, text="Результат:", anchor="w").grid(
            row=0, column=0, padx=(0, 8))
        ts_values = [e["ts"] for e in reversed(hist)]   # новейшие первыми
        _sel_var  = ctk.StringVar(value=ts_values[0])
        ts_combo  = ctk.CTkComboBox(top_f, values=ts_values,
                                    variable=_sel_var, state="readonly", width=220)
        ts_combo.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(top_f, text=f"(всего {len(hist)} записей)",
                     anchor="w", text_color=("gray45", "gray60"),
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(12, 0))

        # ── фрейм результата ───────────────────────────────────────────────────
        result_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        result_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 4))
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_rowconfigure(0, weight=1)

        from widgets.result_table import ResultTable
        _tbl = ResultTable(result_frame, fg_color=result_frame.cget("fg_color"),
                           corner_radius=0)
        _tbl.grid(row=0, column=0, sticky="nsew")

        def _load(ts_str: str):
            entry = next((e for e in hist if e["ts"] == ts_str), None)
            if entry:
                _tbl.set_data(entry["rows"], entry["columns"])

        _load(ts_values[0])
        ts_combo.configure(command=_load)

        # ── кнопки ────────────────────────────────────────────────────────────
        btn_f = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_f.grid(row=2, column=0, pady=(0, 8))
        if len(hist) >= 2:
            ctk.CTkButton(btn_f, text="Сравнить...", width=110,
                          command=lambda: self._show_query_diff(display_name, hist)
                          ).pack(side="left", padx=(0, 8))
        def _close_hist():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()
            try:
                self.focus_set()
            except Exception:
                pass

        ctk.CTkButton(btn_f, text="Закрыть", command=_close_hist,
                      width=100).pack(side="left")
        dlg.bind("<Escape>", lambda _: _close_hist())
        dlg.protocol("WM_DELETE_WINDOW", _close_hist)

        dlg.update_idletasks()
        w, h = 900, 580
        x = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def _show_query_diff(self, display_name: str, hist: list):
        """Диалог сравнения двух исторических результатов одного запроса (diff)."""
        ts_values = [e["ts"] for e in reversed(hist)]

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Сравнение — {display_name}")
        dlg.transient(self)
        def _safe_grab_diff():
            try:
                dlg.grab_set()
            except Exception:
                pass
        dlg.after(20, _safe_grab_diff)
        dlg.geometry("1060x640")
        dlg.resizable(True, True)
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        # ── верхняя панель выбора ─────────────────────────────────────────────
        top_f = ctk.CTkFrame(dlg, fg_color="transparent")
        top_f.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        ctk.CTkLabel(top_f, text="Результат 1 (база):", anchor="w").pack(side="left", padx=(0, 4))
        v1 = ctk.StringVar(value=ts_values[-1] if len(ts_values) > 1 else ts_values[0])
        c1 = ctk.CTkComboBox(top_f, values=ts_values, variable=v1, state="readonly", width=200)
        c1.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(top_f, text="Результат 2 (новый):", anchor="w").pack(side="left", padx=(0, 4))
        v2 = ctk.StringVar(value=ts_values[0])
        c2 = ctk.CTkComboBox(top_f, values=ts_values, variable=v2, state="readonly", width=200)
        c2.pack(side="left", padx=(0, 16))

        summary_lbl = ctk.CTkLabel(top_f, text="", anchor="w",
                                    font=ctk.CTkFont(size=11),
                                    text_color=("gray40", "gray65"))
        summary_lbl.pack(side="left", padx=(4, 0))

        # ── таблица diff ──────────────────────────────────────────────────────
        table_f = ctk.CTkFrame(dlg, fg_color="transparent")
        table_f.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 4))
        table_f.grid_columnconfigure(0, weight=1)
        table_f.grid_rowconfigure(0, weight=1)

        import tkinter.ttk as _ttk
        style = _ttk.Style()
        style.configure("Diff.Treeview", rowheight=24)
        tree = _ttk.Treeview(table_f, show="headings", style="Diff.Treeview")

        vsb = _ttk.Scrollbar(table_f, orient="vertical",   command=tree.yview)
        hsb = _ttk.Scrollbar(table_f, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree.tag_configure("removed", background="#FFCDD2", foreground="#B71C1C")
        tree.tag_configure("added",   background="#C8E6C9", foreground="#1B5E20")
        tree.tag_configure("common",  background="")

        def _update():
            ts1, ts2 = v1.get(), v2.get()
            e1 = next((e for e in hist if e["ts"] == ts1), None)
            e2 = next((e for e in hist if e["ts"] == ts2), None)
            if not e1 or not e2:
                return
            cols = e1.get("columns") or e2.get("columns", [])

            tree["columns"] = ["_status"] + list(cols)
            tree.column("_status", width=120, anchor="center", stretch=False)
            tree.heading("_status", text="Статус")
            for c in cols:
                tree.column(c, width=130, anchor="w")
                tree.heading(c, text=c)

            def _row_key(r):
                return tuple("" if v is None else str(v) for v in r)

            rows1 = {_row_key(r) for r in e1.get("rows", [])}
            rows2 = {_row_key(r) for r in e2.get("rows", [])}
            removed = rows1 - rows2
            added   = rows2 - rows1
            common  = rows1 & rows2

            for item in tree.get_children():
                tree.delete(item)
            for r in sorted(common):
                tree.insert("", "end", values=("Без изменений",) + r, tags=("common",))
            for r in sorted(removed):
                tree.insert("", "end", values=("Удалено",) + r, tags=("removed",))
            for r in sorted(added):
                tree.insert("", "end", values=("Добавлено",) + r, tags=("added",))

            summary_lbl.configure(
                text=f"+ {len(added)} строк   − {len(removed)} строк   = {len(common)} без изменений")

        _update()
        c1.configure(command=lambda _: _update())
        c2.configure(command=lambda _: _update())

        # ── легенда ───────────────────────────────────────────────────────────
        leg_f = ctk.CTkFrame(dlg, fg_color="transparent")
        leg_f.grid(row=2, column=0, pady=(0, 2))
        for txt, fg in [("■ Добавлено", "#1B5E20"), ("■ Удалено", "#B71C1C")]:
            ctk.CTkLabel(leg_f, text=txt, text_color=fg,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=8)

        def _close_diff():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()
            try:
                self.focus_set()
            except Exception:
                pass

        ctk.CTkButton(dlg, text="Закрыть", command=_close_diff,
                      width=100).grid(row=3, column=0, pady=(0, 8))
        dlg.bind("<Escape>", lambda _: _close_diff())
        dlg.protocol("WM_DELETE_WINDOW", _close_diff)

        dlg.update_idletasks()
        w, h = 1060, 640
        x = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def _show_panel_history(self, panel):
        """Открывает историю запросов для конкретной панели дашборда."""
        query_name = panel.get_query_name() if panel else None
        if not query_name:
            import dialogs as _mb
            _mb.showinfo("История", "Выберите запрос в панели")
            return
        self._show_query_history(query_name)

    def _refresh_panel_query_lists(self):
        if hasattr(self, "dash_panels"):
            names = self._get_query_names()
            for p in self.dash_panels:
                p.set_queries(names)

    # ── Авто-обновление: кэш ──────────────────────────────────────────────────

    def _cache_path(self) -> str:
        base = self._appdata_dir or ""
        return os.path.join(base, "query_cache.json") if base else "query_cache.json"

    def _alert_history_path(self) -> str:
        base = self._appdata_dir or ""
        return os.path.join(base, "alert_history.json") if base else "alert_history.json"

    def _load_query_cache(self):
        try:
            path = self._cache_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self._query_results = json.load(f)
        except Exception as e:
            self.log_manager.add_log(f"Ошибка загрузки кэша: {e}", "ERROR")
            self._query_results = {}

    @staticmethod
    def _json_default(obj):
        import decimal
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return str(obj)
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return str(obj)

    def _save_query_cache(self):
        try:
            with self._query_results_lock:
                _snapshot = dict(self._query_results)
            with open(self._cache_path(), "w", encoding="utf-8") as f:
                json.dump(_snapshot, f, ensure_ascii=False,
                          default=self._json_default)
        except Exception as e:
            self.log_manager.add_log(f"Ошибка сохранения кэша: {e}", "ERROR")

    # ── История алертов ───────────────────────────────────────────────────────

    def _load_alert_history(self):
        try:
            path = self._alert_history_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self._alert_history = json.load(f)
        except Exception:
            self._alert_history = []

    def _save_alert_history(self):
        try:
            with open(self._alert_history_path(), "w", encoding="utf-8") as f:
                json.dump(self._alert_history[-500:], f, ensure_ascii=False)
        except Exception:
            pass

    def _toggle_alert_history_panel(self):
        visible = getattr(self, "_alert_hist_visible", False)
        self._alert_hist_visible = not visible
        if self._alert_hist_visible:
            self._alert_hist_frame.grid()
            self._alert_hist_btn.configure(text="▲ История алертов")
        else:
            self._alert_hist_frame.grid_remove()
            self._alert_hist_btn.configure(text="▼ История алертов")

    def _clear_alert_history(self):
        self._alert_history.clear()
        self._save_alert_history()
        self._render_alert_history()

    def _disable_alert_from_history(self, query_file: str):
        if not query_file:
            return
        meta = self._get_query_meta(query_file)
        thr = dict(meta.get("alert_threshold") or {})
        thr["enabled"] = False
        self._set_query_meta(query_file, alert_on_change=False, alert_threshold=thr)
        self._render_alert_history()

    def _render_alert_history(self):
        if not hasattr(self, "_alert_hist_scroll"):
            return
        scroll = self._alert_hist_scroll
        for w in scroll.winfo_children():
            w.destroy()

        if not self._alert_history:
            ctk.CTkLabel(
                scroll, text="Нет записей",
                text_color=("gray50", "gray60"),
            ).grid(row=0, column=0, pady=10, padx=10, sticky="w")
            return

        HDR_BG  = ("gray78", "gray25")
        bold    = ctk.CTkFont(weight="bold")
        sm_font = ctk.CTkFont(size=12)
        HDRS   = ("Время", "Запрос", "Тип", "Детали", "")
        WGTS   = (0, 1, 0, 1, 0)
        MINS   = (130, 150, 90, 200, 95)
        tbl = ctk.CTkFrame(scroll, fg_color="transparent")
        tbl.grid(row=0, column=0, sticky="ew")
        scroll.grid_columnconfigure(0, weight=1)
        for i, (h, wt, mw) in enumerate(zip(HDRS, WGTS, MINS)):
            tbl.grid_columnconfigure(i, weight=wt, minsize=mw)
            ctk.CTkLabel(tbl, text=h, font=bold, anchor="w", fg_color=HDR_BG).grid(
                row=0, column=i, padx=6, pady=4, sticky="nsew")

        for row_idx, entry in enumerate(reversed(self._alert_history[-100:])):
            r  = row_idx + 1
            bg = ("gray88", "gray20") if row_idx % 2 == 0 else ("gray83", "gray17")
            qf = entry.get("query_file", "")
            for col_i, val in enumerate([
                entry.get("ts", ""), entry.get("query_name", ""),
                entry.get("type", ""), entry.get("detail", ""),
            ]):
                ctk.CTkLabel(tbl, text=val, fg_color=bg, anchor="w",
                             font=sm_font).grid(
                    row=r, column=col_i, padx=6, pady=2, sticky="nsew")
            meta = self._get_query_meta(qf) if qf else {}
            alert_on = meta.get("alert_on_change", False) or \
                bool((meta.get("alert_threshold") or {}).get("enabled"))
            btn_text = "Откл. алерт" if alert_on else "✓ Откл."
            ctk.CTkButton(
                tbl, text=btn_text, width=88, height=22, font=sm_font,
                command=lambda f=qf: self._disable_alert_from_history(f),
            ).grid(row=r, column=4, padx=6, pady=2)

    # ── Авто-обновление: запуск и перезапуск таймеров ─────────────────────────

    def _start_auto_timers(self):
        """Немедленно выполняет все запросы, затем запускает таймеры."""
        qdir = self.data_manager.queries_dir
        if os.path.exists(qdir):
            for f in os.listdir(qdir):
                if f.endswith(".sql"):
                    self._execute_query_auto(f)
        self._refresh_all_dashboard_panels()
        # Фиксируем момент запуска как «последнее обновление» для подключений с интервалом
        now = datetime.datetime.now()
        cfg_dir = self.data_manager.config_dir
        if os.path.exists(cfg_dir):
            for f in os.listdir(cfg_dir):
                if f.endswith(".json") and \
                        self._get_conn_meta(f).get("update_interval", 0) > 0:
                    self._conn_last_refresh[f] = now
        self._schedule_all_timers()
        self._test_all_connections_async()
        self._gf_schedule_start()
        self._start_reminder_check()

    def _restart_auto_timers(self):
        """Отменяет старые таймеры и перезапускает по актуальным настройкам."""
        for after_id in list(self._query_timers.values()):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        for after_id in list(self._conn_timers.values()):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self._query_timers.clear()
        self._conn_timers.clear()
        self._schedule_all_timers()

    def _schedule_all_timers(self):
        qdir = self.data_manager.queries_dir
        if os.path.exists(qdir):
            for f in os.listdir(qdir):
                if f.endswith(".sql"):
                    meta     = self._get_query_meta(f)
                    interval = meta.get("update_interval", 0)
                    cron     = meta.get("cron_schedule")
                    if cron and cron.get("enabled"):
                        self._schedule_query_cron(f, cron)
                    elif interval > 0:
                        self._schedule_query(f, interval)
        cfg_dir = self.data_manager.config_dir
        if os.path.exists(cfg_dir):
            for f in os.listdir(cfg_dir):
                if f.endswith(".json"):
                    interval = self._get_conn_meta(f).get("update_interval", 0)
                    if interval > 0:
                        self._schedule_conn_refresh(f, interval)

    # ── Авто-обновление: таймер запросов (интервальный) ───────────────────────

    def _schedule_query(self, query_file: str, interval_min: int):
        self._query_scheduled_at[query_file]    = datetime.datetime.now()
        self._query_intervals_cache[query_file] = interval_min
        after_id = self.after(
            interval_min * 60_000,
            lambda qf=query_file, iv=interval_min: self._query_tick(qf, iv))
        self._query_timers[query_file] = after_id

    def _query_tick(self, query_file: str, interval_min: int):
        self._execute_query_auto(query_file)
        self._schedule_query(query_file, interval_min)

    # ── Авто-обновление: cron-планировщик запросов ────────────────────────────

    @staticmethod
    def _cron_next_fire(now: datetime.datetime, hour: int, minute: int,
                        days: list) -> datetime.datetime:
        """Возвращает datetime следующего срабатывания cron (≥ now + 1 мин)."""
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += datetime.timedelta(days=1)
        # Прокручиваем вперёд до ближайшего разрешённого дня недели
        for _ in range(8):
            if not days or candidate.weekday() in days:
                return candidate
            candidate += datetime.timedelta(days=1)
        return candidate

    def _schedule_query_cron(self, query_file: str, cron: dict):
        try:
            h, m = map(int, cron.get("time", "09:00").split(":"))
        except Exception:
            h, m = 9, 0
        days = cron.get("days", [])
        next_fire = self._cron_next_fire(datetime.datetime.now(), h, m, days)
        delay_ms  = max(1000, int((next_fire - datetime.datetime.now()).total_seconds() * 1000))
        self._query_scheduled_at[query_file]    = datetime.datetime.now()
        self._query_intervals_cache[query_file] = 0
        after_id = self.after(
            delay_ms,
            lambda qf=query_file, c=cron: self._cron_tick(qf, c))
        self._query_timers[query_file] = after_id

    def _cron_tick(self, query_file: str, cron: dict):
        self._execute_query_auto(query_file)
        self._schedule_query_cron(query_file, cron)

    def _execute_query_auto(self, query_file: str):
        """Запускает SQL в фоне, сохраняет результат в кэш, обновляет панели дашборда."""
        if query_file in self._queries_in_progress:
            return
        try:
            meta = self._get_query_meta(query_file)
            db_display = meta.get("database", "")
            conn_file = self._find_conn_file(db_display) if db_display else None
            if not conn_file:
                self.log_manager.add_log(
                    f"Авто-запрос {query_file}: подключение '{db_display}' не найдено", "WARNING")
                return
            with open(os.path.join(self.data_manager.queries_dir, query_file), encoding="utf-8") as fh:
                sql = fh.read()
        except Exception as e:
            self.log_manager.add_log(
                f"Ошибка авто-запроса {query_file}: {e}", "ERROR")
            return

        db_name = os.path.splitext(conn_file)[0]
        self._queries_in_progress.add(query_file)

        # Показываем спиннер на всех панелях, привязанных к этому файлу
        for panel in getattr(self, "dash_panels", []):
            qf = self._find_query_file(panel.get_query_name() or "")
            if qf == query_file:
                panel.set_loading(True)

        def worker():
            _t0 = time.monotonic()
            try:
                rows, cols = self.db_manager.execute_query_with_columns(db_name, sql)
                _ms = (time.monotonic() - _t0) * 1000
                try:
                    self.after(0, lambda r=rows, c=cols, ms=_ms: done(r, c, None, ms))
                except Exception:
                    self._queries_in_progress.discard(query_file)
            except Exception as e:
                _ms = (time.monotonic() - _t0) * 1000
                try:
                    self.after(0, lambda err=e, ms=_ms: done([], [], err, ms))
                except Exception:
                    self._queries_in_progress.discard(query_file)

        def done(rows, cols, err, duration_ms: float = 0.0):
            self._queries_in_progress.discard(query_file)
            if not self.winfo_exists():
                return
            for panel in getattr(self, "dash_panels", []):
                qf = self._find_query_file(panel.get_query_name() or "")
                if qf == query_file:
                    panel.set_loading(False)
            if err:
                self.log_manager.add_log(
                    f"Ошибка авто-запроса {query_file}: {err}", "ERROR")
                try:
                    self.stats_manager.record(query_file, duration_ms, 0, is_error=True)
                except Exception:
                    pass
                if self._conn_statuses.get(conn_file) is not False:
                    self._conn_statuses[conn_file] = False
                    self.refresh_connections_list()
                return
            self._check_change_alert(query_file, rows, cols)
            self._check_threshold_alert(query_file, rows, cols)
            max_rows = self.settings_manager.get_setting("max_rows", 1000)
            if max_rows and len(rows) > max_rows:
                rows = rows[:max_rows]
            _rows_clean  = [list(r) for r in rows]
            _cols_clean  = list(cols)
            with self._query_results_lock:
                self._query_results[query_file] = {
                    "rows": _rows_clean,
                    "columns": _cols_clean,
                }
            self._save_query_cache()
            ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            self._set_query_meta(query_file, last_updated=ts)
            self._update_header_widget(query_file, _rows_clean, _cols_clean)

            # ── история запросов ─────────────────────────────────────────────
            # Лимит по количеству (10 записей) + по суммарному числу строк
            # (~100 000 ячеек на историю одного запроса ≈ ~10-20 МБ worst-case).
            _hist = self._query_history.setdefault(query_file, [])
            _hist.append({"ts": ts, "rows": _rows_clean, "columns": _cols_clean})
            if len(_hist) > 10:
                _hist.pop(0)
            _MAX_TOTAL_ROWS = 100_000
            while len(_hist) > 1:
                if sum(len(e["rows"]) for e in _hist) <= _MAX_TOTAL_ROWS:
                    break
                _hist.pop(0)

            self.refresh_queries_list()
            self.log_manager.add_log(
                f"Авто-запрос: {self.data_manager.get_query_display_name(query_file)}")
            for panel in getattr(self, "dash_panels", []):
                qf = self._find_query_file(panel.get_query_name() or "")
                if qf == query_file:
                    self._update_panel_from_cache(panel, query_file)
            try:
                self.stats_manager.record(query_file, duration_ms, len(_rows_clean))
            except Exception:
                pass
            if self._conn_statuses.get(conn_file) is not True:
                self._conn_statuses[conn_file] = True
                self.refresh_connections_list()

        threading.Thread(target=worker, daemon=True).start()

    # ── Авто-обновление: таймер дашборда по подключению ───────────────────────

    def _schedule_conn_refresh(self, conn_file: str, interval_min: int):
        after_id = self.after(
            interval_min * 60_000,
            lambda cf=conn_file, iv=interval_min: self._conn_refresh_tick(cf, iv))
        self._conn_timers[conn_file] = after_id

    def _conn_refresh_tick(self, conn_file: str, interval_min: int):
        now = datetime.datetime.now()
        self._conn_last_refresh[conn_file] = now
        db_display = self.data_manager.get_db_display_name(conn_file)
        self._refresh_panels_for_db(db_display)
        self._schedule_conn_refresh(conn_file, interval_min)
        self.log_manager.add_log(
            f"Последнее время обновления: {now.strftime('%H:%M:%S')}")
        self._test_conn_file_async(conn_file)

    def _refresh_panels_for_db(self, db_display: str):
        """Обновляет панели дашборда, чьи запросы привязаны к данному подключению."""
        if not hasattr(self, "dash_panels"):
            return
        for panel in self.dash_panels:
            query_name = panel.get_query_name()
            if not query_name:
                continue
            query_file = self._find_query_file(query_name)
            if not query_file:
                continue
            if self._get_query_meta(query_file).get("database", "") == db_display:
                self._update_panel_from_cache(panel, query_file)

    def _force_refresh_all(self):
        """Принудительно перезапускает выполнение всех запросов."""
        qdir = self.data_manager.queries_dir
        if os.path.exists(qdir):
            for f in os.listdir(qdir):
                if f.endswith(".sql"):
                    self._execute_query_auto(f)

    def _refresh_all_dashboard_panels(self):
        """Обновляет все панели дашборда из кэша."""
        if not hasattr(self, "dash_panels"):
            return
        for panel in self.dash_panels:
            query_name = panel.get_query_name()
            if not query_name:
                continue
            query_file = self._find_query_file(query_name)
            if query_file:
                self._update_panel_from_cache(panel, query_file)

    def _update_panel_from_cache(self, panel: DashboardPanel, query_file: str):
        data = self._query_results.get(query_file)
        if data is None:
            return
        rows = data.get("rows", [])
        cols = data.get("columns", [])
        panel.set_result(rows, cols)
        meta = self._get_query_meta(query_file)
        last_upd = meta.get("last_updated", "")
        if last_upd and last_upd != "—":
            try:
                dt = datetime.datetime.strptime(last_upd, "%d.%m.%Y %H:%M:%S")
                panel.set_row_notice(f"Данные от {dt.strftime('%H:%M %d.%m')}")
            except Exception:
                panel.set_row_notice(f"Данные от {last_upd}")
        else:
            panel.set_row_notice("")

    # ── Авто-обновление: вспомогательные поисковики ───────────────────────────

    def _find_query_file(self, query_name: str) -> Optional[str]:
        qdir = self.data_manager.queries_dir
        if os.path.exists(qdir):
            for f in os.listdir(qdir):
                if f.endswith(".sql") and \
                        self.data_manager.get_query_display_name(f) == query_name:
                    return f
        return None

    def _find_conn_file(self, db_display: str) -> Optional[str]:
        cfg_dir = self.data_manager.config_dir
        if os.path.exists(cfg_dir):
            for f in os.listdir(cfg_dir):
                if f.endswith(".json") and \
                        self.data_manager.get_db_display_name(f) == db_display:
                    return f
        return None

    def _on_query_search_changed(self):
        term = self._query_search_var.get()
        if hasattr(self, "_query_clear_btn"):
            if term:
                self._query_clear_btn.pack(side="right", padx=(0, 2))
            else:
                self._query_clear_btn.pack_forget()
        self.refresh_queries_list()
