"""Connections tab — mixin для MainWindow.

Содержит все методы вкладки «Подключения», включая диалоги,
поиск, сортировку, контекстное меню и вспомогательные методы списков.
Примешивается к MainWindow через множественное наследование.
"""
from __future__ import annotations

import json
import os
import re
import threading
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog

import dialogs as messagebox
from connection_dialog import DatabaseConnectionDialog


class ConnectionsTabMixin:
    """Методы вкладки «Подключения».  Примешиваются к MainWindow."""

    # ── Подключения ───────────────────────────────────────────────────────────

    _C_HEADERS  = ("●", "Название", "Тип БД", "Хост", "Порт",
                   "Имя БД", "Пользователь", "Пароль", "Кодировка",
                   "Обновлять панель каждые", "", "", "")
    # weight=0 → фиксированная колонка (статус/кнопки), >0 → пропорциональная
    _C_WEIGHTS  = (0,  3,  2,  3,  0,  3,  2,  1,  1,  2,  0,  0,  0)
    _C_MIN_W    = (28, 100, 70, 90, 50, 90, 80, 60, 60, 90, 90, 90, 90)

    def setup_connections_tab(self):
        self.frame_connections.grid_columnconfigure(0, weight=1)
        self.frame_connections.grid_rowconfigure(1, weight=1)

        # ── тулбар (row 0, аналог Логи) ───────────────────────────────────────
        conn_toolbar = ctk.CTkFrame(self.frame_connections, fg_color="transparent")
        conn_toolbar.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")

        self._conn_search_var = ctk.StringVar()
        self._conn_search_var.trace_add("write", lambda *_: self._on_conn_search_changed())

        self._conn_clear_btn = ctk.CTkButton(
            conn_toolbar, text="✕", width=24, height=28,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=lambda: self._conn_search_var.set(""))
        self._conn_clear_btn.pack(side="right", padx=(0, 2))
        self._conn_clear_btn.pack_forget()

        ctk.CTkEntry(conn_toolbar, textvariable=self._conn_search_var,
                     placeholder_text="Поиск...",
                     width=190, height=28).pack(side="right")

        ctk.CTkLabel(conn_toolbar, text="🔍",
                     font=ctk.CTkFont(size=20)).pack(side="right", padx=(16, 6), anchor="center")

        ctk.CTkButton(conn_toolbar, text="📥 Импорт", width=100, height=28,
                      fg_color=("gray55", "gray35"), hover_color=("gray45", "gray25"),
                      command=self._import_connection).pack(side="left", padx=(0, 8))

        self._connections_scroll = ctk.CTkScrollableFrame(
            self.frame_connections, fg_color="transparent")
        self._connections_scroll.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self._connections_scroll.grid_columnconfigure(0, weight=1)

        self.refresh_connections_list()

    def refresh_connections_list(self):
        for w in self._connections_scroll.winfo_children():
            w.destroy()

        sort_col, sort_rev = self._conn_sort
        bold   = ctk.CTkFont(weight="bold")
        HDR_BG = ("gray78", "gray25")

        # ── предварительное чтение файлов ────────────────────────────────────
        _files = None        # None = папка не существует
        _read_error = None
        _cfg_dir = self.data_manager.config_dir
        if os.path.exists(_cfg_dir):
            try:
                _files = [f for f in os.listdir(_cfg_dir) if f.endswith(".json")]
            except Exception as e:
                _read_error = e
                self.log_manager.add_log(f"Ошибка чтения config: {e}", "ERROR")
        else:
            self.log_manager.add_log("Папка config не найдена", "ERROR")

        # ── фильтрация по поиску ──────────────────────────────────────────────
        _conn_sv = getattr(self, "_conn_search_var", None)
        _q = _conn_sv.get().strip().lower() if _conn_sv else ""
        if _q and _files:
            _files = [f for f in _files
                      if _q in self.data_manager.get_db_display_name(f).lower()]

        _conn_has_items = bool(_files)

        if _conn_has_items:
            # ── единый фрейм таблицы: заголовок + строки в одной сетке ──────
            tbl = ctk.CTkFrame(self._connections_scroll, fg_color="transparent")
            tbl.grid(row=0, column=0, sticky="ew")
            self._apply_col_config(tbl, self._C_WEIGHTS, self._C_MIN_W)

            # ── заголовок (строка 0 в tbl) ────────────────────────────────────
            for i, h in enumerate(self._C_HEADERS):
                if not h:
                    ctk.CTkLabel(tbl, text="", fg_color="transparent").grid(
                        row=0, column=i, padx=6, pady=5, sticky="nsew")
                    continue
                if self._C_WEIGHTS[i] == 0:
                    is_text = any(c.isalpha() for c in h)
                    lbl = ctk.CTkLabel(
                        tbl, text=h, fg_color=HDR_BG,
                        font=bold if is_text else None,
                        anchor="w" if is_text else "center")
                    lbl.grid(row=0, column=i, padx=6, pady=5, sticky="nsew")
                    continue
                arrow = (" ▲" if not sort_rev else " ▼") if sort_col == i else ""
                lbl = ctk.CTkLabel(tbl, text=h + arrow, font=bold,
                                   anchor="w", cursor="hand2", fg_color=HDR_BG)
                lbl.grid(row=0, column=i, padx=6, pady=5, sticky="nsew")
                lbl.bind("<Button-1>", lambda e, c=i: self._conn_sort_click(c))

            # ── строки данных ─────────────────────────────────────────────────
            for row_idx, f in enumerate(self._sorted_conn_files(_files)):
                r = row_idx + 1
                display_name = self.data_manager.get_db_display_name(f)
                try:
                    with open(os.path.join(_cfg_dir, f),
                              encoding="utf-8") as fh:
                        cfg = json.load(fh)
                except Exception:
                    cfg = {}
                if cfg.get("password_in_keyring"):
                    cfg["password"] = self.db_manager.get_keyring_password(
                        display_name)
                pwd    = cfg.get("password", "")
                masked = "*" * len(pwd) if pwd else "—"
                bg = ("gray88", "gray20") if row_idx % 2 == 0 \
                    else ("gray83", "gray17")

                meta_c   = self._get_conn_meta(f)
                interval = meta_c.get("update_interval", 0)
                istr     = f"{interval} мин." if interval else "—"

                # ── индикатор статуса (col 0) ─────────────────────────────────
                status = self._conn_statuses.get(f)
                if status is True:
                    dot_color = ("#22C55E", "#16A34A")
                elif status is False:
                    dot_color = ("#EF4444", "#DC2626")
                else:
                    dot_color = ("gray60", "gray50")
                ctk.CTkLabel(tbl, text="●", text_color=dot_color,
                             fg_color=bg).grid(
                    row=r, column=0, padx=6, pady=3, sticky="nsew")

                if status is None and f not in self._conn_status_testing:
                    self._conn_status_testing.add(f)
                    threading.Thread(
                        target=self._bg_test_conn,
                        args=(f, dict(cfg)), daemon=True).start()

                # ── данные (col 1-9) ──────────────────────────────────────────
                for ci, val in enumerate((
                    display_name,
                    cfg.get("database_type", "—"),
                    cfg.get("host", "—"),
                    str(cfg.get("port", "—")),
                    cfg.get("database_name", "—"),
                    cfg.get("username", "—"),
                    masked,
                    cfg.get("charset", "—"),
                    istr,
                ), start=1):
                    ctk.CTkLabel(tbl, text=val, anchor="w",
                                 fg_color=bg).grid(
                        row=r, column=ci, padx=6, pady=3, sticky="nsew")

                # ── кнопки (col 10, 11) ───────────────────────────────────────
                ctk.CTkButton(
                    tbl, text="Изменить",
                    width=self._C_MIN_W[10], height=26,
                    command=lambda n=display_name: self._edit_db_by_name(n)
                ).grid(row=r, column=10, padx=6, pady=3)

                ctk.CTkButton(
                    tbl, text="Удалить",
                    width=self._C_MIN_W[11], height=26,
                    fg_color=("#E53935", "#C62828"),
                    hover_color=("#C62828", "#B71C1C"),
                    command=lambda n=display_name: self._delete_db_by_name(n)
                ).grid(row=r, column=11, padx=6, pady=3)

                ctk.CTkButton(
                    tbl, text="Экспорт",
                    width=self._C_MIN_W[12], height=26,
                    fg_color=("gray55", "gray35"),
                    hover_color=("gray45", "gray25"),
                    command=lambda n=display_name: self._export_connection(n)
                ).grid(row=r, column=12, padx=6, pady=3)

                # ── контекстное меню на строке ────────────────────────────────
                for child in tbl.grid_slaves(row=r):
                    child.bind(
                        "<Button-3>",
                        lambda e, n=display_name:
                            self._show_conn_ctx_menu(e, n),
                        add="+")

            # ── кнопка "Добавить подключение" после таблицы ───────────────────
            ctk.CTkButton(
                self._connections_scroll, text="+ Добавить подключение",
                command=self.add_new_db, height=32, anchor="w"
            ).grid(row=1, column=0, padx=6, pady=(6, 4), sticky="w")

        else:
            # ── пустое состояние или ошибка ───────────────────────────────────
            if _files is None:
                self._build_empty_state(
                    self._connections_scroll, 0,
                    "⚠️", "Папка config не найдена",
                    "Создайте папку config рядом с программой",
                    "+ Добавить подключение", self.add_new_db)
            elif _read_error is not None:
                ctk.CTkLabel(self._connections_scroll,
                             text=f"Ошибка: {_read_error}").grid(
                    row=0, column=0, padx=10, pady=5)
            else:
                self._build_empty_state(
                    self._connections_scroll, 0,
                    "🔌", "Нет подключений",
                    "Добавьте первое подключение к базе данных",
                    "+ Добавить подключение", self.add_new_db)

    # ── метаданные подключений ────────────────────────────────────────────────

    def _get_conn_meta(self, filename: str) -> dict:
        return dict(self.settings_manager.get_setting(
            "connections_meta", {}).get(filename, {}))

    def _set_conn_meta(self, filename: str, **kwargs):
        all_meta = dict(self.settings_manager.get_setting("connections_meta", {}))
        meta = dict(all_meta.get(filename, {}))
        meta.update(kwargs)
        all_meta[filename] = meta
        self.settings_manager.set_setting("connections_meta", all_meta)

    def _del_conn_meta(self, filename: str):
        all_meta = dict(self.settings_manager.get_setting("connections_meta", {}))
        all_meta.pop(filename, None)
        self.settings_manager.set_setting("connections_meta", all_meta)

    # ── редактирование / добавление подключения ───────────────────────────────

    def _edit_db_by_name(self, name: str):
        self._selected_connection_name = name
        filename = self.get_filename_by_display_name(name, self.data_manager.config_dir, ".json")
        if not filename:
            messagebox.showwarning("Предупреждение", "Файл подключения не найден")
            return

        config_path = os.path.join(self.data_manager.config_dir, filename)
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить конфигурацию:\n{e}")
            return

        meta = self._get_conn_meta(filename)
        dialog = DatabaseConnectionDialog(
            self, initial_name=name, initial_config=config,
            initial_interval=meta.get("update_interval", 0),
            db_manager=self.db_manager,
            settings_manager=self.settings_manager,
            log_manager=self.log_manager)
        self.wait_window(dialog)
        if not dialog.result:
            return

        new_name, new_config, new_interval = dialog.result

        if new_name != name:
            new_filename = f"{new_name}.json"
            new_path = os.path.join(self.data_manager.config_dir, new_filename)
            if os.path.exists(new_path):
                messagebox.showerror("Ошибка", f"Подключение '{new_name}' уже существует")
                return
            os.remove(config_path)
            self.data_manager.delete_db_name(filename)
            self._del_conn_meta(filename)
        else:
            new_filename = filename
            new_path     = config_path

        with open(new_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=4)
        self.data_manager.set_db_display_name(new_filename, new_name)
        self._set_conn_meta(new_filename, update_interval=new_interval)

        if new_filename != filename:
            self._conn_statuses.pop(filename, None)
            self._conn_status_testing.discard(filename)
        else:
            # конфиг мог измениться — сбрасываем статус для повторной проверки
            self._conn_statuses.pop(new_filename, None)
            self._conn_status_testing.discard(new_filename)
        self._selected_connection_name = new_name
        self.refresh_connections_list()
        self.log_manager.add_log(f"Подключение изменено: {name} → {new_name}")
        self._restart_auto_timers()

    def add_new_db(self):
        dialog = DatabaseConnectionDialog(self, db_manager=self.db_manager,
                                          settings_manager=self.settings_manager,
                                          log_manager=self.log_manager)
        self.wait_window(dialog)
        if dialog.result:
            name, config, interval = dialog.result
            if self.data_manager.add_new_db(name, config):
                filename = f"{name}.json"
                self.data_manager.set_db_display_name(filename, name)
                self._set_conn_meta(filename, update_interval=interval)
                self.refresh_connections_list()
                self.log_manager.add_log(f"Добавлено подключение: {name}")
                messagebox.showinfo("Успех", f"Подключение '{name}' добавлено")
                self._restart_auto_timers()
            else:
                messagebox.showerror("Ошибка", f"'{name}' уже существует")

    def _delete_db_by_name(self, name: str):
        fname = self.get_filename_by_display_name(name, self.data_manager.config_dir, ".json")
        if not fname:
            return
        if messagebox.askyesno("Подтверждение", f"Удалить '{name}'?"):
            if self.data_manager.delete_db(fname):
                self._del_conn_meta(fname)
                self._conn_statuses.pop(fname, None)
                self._conn_status_testing.discard(fname)
                if self._selected_connection_name == name:
                    self._selected_connection_name = None
                self.refresh_connections_list()
                self.log_manager.add_log(f"Удалено подключение: {name}")
                self._restart_auto_timers()
            else:
                messagebox.showerror("Ошибка", f"Не удалось удалить '{name}'")

    def _export_connection(self, name: str):
        filename = self._find_conn_file(name)
        if not filename:
            messagebox.showwarning("Предупреждение", "Файл подключения не найден")
            return
        config_path = os.path.join(self.data_manager.config_dir, filename)
        try:
            with open(config_path, encoding="utf-8") as fh:
                config = json.load(fh)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать конфигурацию:\n{e}")
            return
        export_config = {k: v for k, v in config.items()
                         if k not in ("password", "password_in_keyring")}
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".json",
            initialfile=filename,
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")],
            title=f"Экспорт подключения «{name}»",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(export_config, fh, ensure_ascii=False, indent=4)
            messagebox.showinfo("Экспорт", f"Подключение «{name}» сохранено:\n{path}")
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

    def _import_connection(self):
        path = filedialog.askopenfilename(
            parent=self,
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")],
            title="Импорт подключения из файла",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                config = json.load(fh)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{e}")
            return
        if not isinstance(config, dict):
            messagebox.showerror("Ошибка",
                                 "Неверный формат файла (ожидается JSON-объект)")
            return

        default_name = os.path.splitext(os.path.basename(path))[0]

        dlg = ctk.CTkToplevel(self)
        dlg.withdraw()
        dlg.title("Импорт подключения")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dlg, text="Имя подключения:", anchor="w"
                     ).grid(row=0, column=0, padx=(16, 8), pady=(16, 4), sticky="w")
        name_entry = ctk.CTkEntry(dlg, width=260)
        name_entry.insert(0, default_name)
        name_entry.grid(row=0, column=1, padx=(0, 16), pady=(16, 4), sticky="ew")

        ctk.CTkLabel(dlg, text="Пароль:", anchor="w"
                     ).grid(row=1, column=0, padx=(16, 8), pady=(0, 4), sticky="w")
        pwd_entry = ctk.CTkEntry(dlg, width=260, show="*",
                                  placeholder_text="Оставьте пустым, если не требуется")
        pwd_entry.grid(row=1, column=1, padx=(0, 16), pady=(0, 4), sticky="ew")

        error_lbl = ctk.CTkLabel(dlg, text="", text_color=("#DC2626", "#F87171"),
                                  font=ctk.CTkFont(size=11), anchor="w")
        error_lbl.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 2), sticky="w")

        _result = [None]
        _INVALID_CONN = re.compile(r'[\\/*?:"<>|]')

        def _ok():
            n = name_entry.get().strip()
            if not n:
                error_lbl.configure(text="Введите имя подключения.")
                return
            if _INVALID_CONN.search(n):
                error_lbl.configure(text='Нельзя: \\ / * ? : " < > |')
                return
            _result[0] = (n, pwd_entry.get())
            _close()

        def _close():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", _close)
        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.grid(row=3, column=0, columnspan=2, pady=(8, 16))
        ctk.CTkButton(btn_row, text="Импортировать", width=140,
                      command=_ok).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(btn_row, text="Отмена", width=90,
                      fg_color=("gray60", "gray40"),
                      hover_color=("gray50", "gray30"),
                      command=_close).grid(row=0, column=1)

        dlg.bind("<Return>", lambda e: _ok())

        dlg.update_idletasks()
        pw = self.winfo_width(); ph = self.winfo_height()
        px = self.winfo_rootx(); py = self.winfo_rooty()
        w = dlg.winfo_reqwidth(); h = dlg.winfo_reqheight()
        dlg.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        dlg.deiconify()
        name_entry.focus()

        def _safe_grab():
            try:
                dlg.grab_set()
            except Exception:
                pass
        dlg.after(20, _safe_grab)
        dlg.lift()
        self.wait_window(dlg)

        if not _result[0]:
            return

        name, password = _result[0]
        filename = f"{name}.json"
        dest_path = os.path.join(self.data_manager.config_dir, filename)
        if os.path.exists(dest_path):
            if not messagebox.askyesno(
                    "Подтверждение",
                    f"Подключение «{name}» уже существует. Перезаписать?"):
                return

        config.pop("password_in_keyring", None)
        config.pop("password", None)
        if password:
            config["password"] = password

        try:
            os.makedirs(self.data_manager.config_dir, exist_ok=True)
            with open(dest_path, "w", encoding="utf-8") as fh:
                json.dump(config, fh, ensure_ascii=False, indent=4)
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")
            return

        self.data_manager.set_db_display_name(filename, name)
        self.refresh_connections_list()
        self.log_manager.add_log(f"Импортировано подключение: {name}")
        messagebox.showinfo("Импорт",
                            f"Подключение «{name}» успешно импортировано")
        self._restart_auto_timers()

    # ── общие вспомогательные методы списков ─────────────────────────────────

    def _apply_col_config(self, frame, weights: tuple, min_widths: tuple):
        """Применяет пропорциональные веса и минимальные ширины к колонкам фрейма."""
        for i, (w, mw) in enumerate(zip(weights, min_widths)):
            frame.grid_columnconfigure(i, weight=w, minsize=mw)

    def _build_empty_state(self, parent, row: int, icon: str,
                           title: str, desc: str, btn_text: str, btn_cmd):
        """Заглушка пустого списка: иконка + заголовок + описание + кнопка."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, pady=40, sticky="n")
        ctk.CTkLabel(frame, text=icon,
                     font=ctk.CTkFont(size=44)).pack(pady=(0, 8))
        ctk.CTkLabel(frame, text=title,
                     font=ctk.CTkFont(size=15, weight="bold")).pack()
        ctk.CTkLabel(frame, text=desc,
                     font=ctk.CTkFont(size=12),
                     text_color=("gray50", "gray60")).pack(pady=(4, 16))
        ctk.CTkButton(frame, text=btn_text, command=btn_cmd,
                      height=32).pack()

    # ── сортировка подключений ────────────────────────────────────────────────

    def _conn_sort_click(self, col: int):
        c, r = self._conn_sort
        self._conn_sort = (col, not r if col == c else False)
        self.refresh_connections_list()

    def _bg_test_conn(self, filename: str, config: dict):
        ok, _ = self.db_manager.test_connection_raw(config)

        def _apply():
            self._conn_statuses[filename] = ok
            self._conn_status_testing.discard(filename)
            self.refresh_connections_list()

        try:
            self.after(0, _apply)
        except Exception:
            pass

    def _test_conn_file_async(self, conn_file: str) -> bool:
        """Запускает фоновый тест одного подключения. Возвращает False если уже тестируется."""
        if conn_file in self._conn_status_testing:
            return False
        try:
            cfg_path = os.path.join(self.data_manager.config_dir, conn_file)
            with open(cfg_path, encoding="utf-8") as fh:
                config = json.load(fh)
        except Exception:
            return False
        if config.get("password_in_keyring"):
            display_name = self.data_manager.get_db_display_name(conn_file)
            config["password"] = self.db_manager.get_keyring_password(display_name)
        self._conn_status_testing.add(conn_file)
        threading.Thread(
            target=self._bg_test_conn,
            args=(conn_file, config), daemon=True
        ).start()
        return True

    def _test_all_connections_async(self):
        """Запускает фоновую проверку всех подключений для обновления индикаторов."""
        cfg_dir = self.data_manager.config_dir
        if not os.path.exists(cfg_dir):
            return
        for f in os.listdir(cfg_dir):
            if f.endswith(".json"):
                self._test_conn_file_async(f)

    def _sorted_conn_files(self, files: list) -> list:
        col, rev = self._conn_sort
        if col is None:
            return files

        def key(f):
            display = self.data_manager.get_db_display_name(f)
            try:
                with open(os.path.join(self.data_manager.config_dir, f), encoding="utf-8") as fh:
                    cfg = json.load(fh)
            except Exception:
                cfg = {}
            iv = self._get_conn_meta(f).get("update_interval", 0)
            vals = [display,
                    cfg.get("database_type", ""),
                    cfg.get("host", ""),
                    str(cfg.get("port", "")),
                    cfg.get("database_name", ""),
                    cfg.get("username", ""),
                    "",
                    cfg.get("charset", ""),
                    str(iv) if iv else ""]
            # col 0 — "●" (не сортируется), данные начинаются с col 1
            idx = col - 1
            v = vals[idx] if 0 <= idx < len(vals) else ""
            try:
                return (0, float(v))
            except (ValueError, TypeError):
                return (1, str(v).lower())

        return sorted(files, key=key, reverse=rev)

    # ── контекстные меню ──────────────────────────────────────────────────────

    def _show_conn_ctx_menu(self, event, display_name: str):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Изменить",
                         command=lambda: self._edit_db_by_name(display_name))
        menu.add_command(label="Переподключить / Проверить",
                         command=lambda: self._retest_conn_by_name(display_name))
        menu.add_separator()
        menu.add_command(label="Экспорт",
                         command=lambda: self._export_connection(display_name))
        menu.add_command(label="Удалить",
                         command=lambda: self._delete_db_by_name(display_name))
        menu.add_separator()
        menu.add_command(label="Копировать имя",
                         command=lambda: self._clip(display_name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _retest_conn_by_name(self, display_name: str):
        filename = self._find_conn_file(display_name)
        if not filename:
            return
        self._conn_statuses[filename] = None
        self.refresh_connections_list()
        self._test_conn_file_async(filename)

    def _on_conn_search_changed(self):
        term = self._conn_search_var.get()
        if hasattr(self, "_conn_clear_btn"):
            if term:
                self._conn_clear_btn.pack(side="right", padx=(0, 2))
            else:
                self._conn_clear_btn.pack_forget()
        self.refresh_connections_list()
