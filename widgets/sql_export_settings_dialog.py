"""
Диалог настроек сервиса «SQL Выгрузка».
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import theme_colors

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


def _teal():
    return (theme_colors.accent(), theme_colors.hover())


def _teal_hvr():
    return (theme_colors.hover(), theme_colors.dark())


_GRAY_BTN = ("gray55", "gray35")
_GRAY_HVR = ("gray45", "gray25")
_DAYS_RU  = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class SqlExportSettingsDialog(ctk.CTkToplevel):
    """Диалог настройки сервиса SQL Выгрузка."""

    def __init__(self, parent, settings_manager, queries_dir: str,
                 connections: list, on_saved=None):
        super().__init__(parent)
        self.withdraw()
        self._sm         = settings_manager
        self._qdir       = queries_dir
        self._conns      = connections   # list of str (без .json)
        self._on_saved   = on_saved
        self._query_rows = []   # [{widgets}, ...]

        self.title("Настройки — SQL Выгрузка")
        self.resizable(False, False)
        self.transient(parent)
        # Делаем окно прозрачным и переводим в состояние "normal" ДО _build().
        # Это гарантирует, что CTkToplevel._windows_set_titlebar_color() сохранит
        # _state_before="normal" и _revert_withdraw вызовет deiconify(), а не
        # state("withdrawn"). Без этого тяжёлый _build() задерживает event loop,
        # и revert повторно скрывает окно уже после deiconify() в _center(),
        # из-за чего grab на скрытом окне вызывает зависание приложения.
        self.attributes("-alpha", 0)
        self.deiconify()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build()
        self.after(0, lambda: self._center(0))

    # ── centering ─────────────────────────────────────────────────────────────

    def _center(self, attempt: int = 0):
        self.update_idletasks()
        p = self.master
        p.update_idletasks()
        pw, ph = p.winfo_width(), p.winfo_height()
        px, py = p.winfo_rootx(), p.winfo_rooty()
        if pw <= 1 or ph <= 1:
            if attempt < 20:
                self.after(80, lambda: self._center(attempt + 1))
            else:
                self._deactivate_windows_window_header_manipulation = True
                self.attributes("-alpha", 1)
            return
        dw = self.winfo_reqwidth()
        dh = min(self.winfo_reqheight(), 820)
        x = px + max(0, (pw - dw) // 2)
        y = py + max(0, (ph - dh) // 2)
        self.geometry(f"{dw}x{dh}+{x}+{y}")
        self._deactivate_windows_window_header_manipulation = True
        self.attributes("-alpha", 1)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        cfg = self._sm.get_setting

        # ── заголовок диалога ──────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=("gray88", "gray20"), height=44,
                           corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📤  Настройки — SQL Выгрузка",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(side="left", padx=16)

        ctk.CTkFrame(self, height=1,
                     fg_color=("gray75", "gray30")).pack(fill="x")

        # ── скроллируемое тело ─────────────────────────────────────────────────
        body = ctk.CTkScrollableFrame(self, fg_color="transparent", width=580,
                                      height=580)
        body.pack(fill="both", expand=True, padx=0, pady=0)
        body.grid_columnconfigure(0, weight=1)

        # ── 1. SQL-запросы ─────────────────────────────────────────────────────
        s1 = self._section(body, "SQL-запросы", row=0)
        ctk.CTkLabel(s1,
                     text="Выберите запросы для выгрузки и подключение к БД для каждого:",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray40", "gray60"),
                     anchor="w").pack(fill="x", padx=12, pady=(4, 6))

        self._queries_frame = ctk.CTkFrame(s1, fg_color="transparent")
        self._queries_frame.pack(fill="x", padx=12)
        self._queries_frame.grid_columnconfigure(1, weight=1)

        # загружаем сохранённые + автоматически из queries/
        saved_qs = cfg("sql_export_queries", [])
        self._load_queries(saved_qs)

        ctk.CTkButton(
            s1, text="+ Добавить файл",
            command=self._add_file,
            width=130, height=28,
            fg_color=_GRAY_BTN, hover_color=_GRAY_HVR,
        ).pack(anchor="w", padx=12, pady=(6, 10))

        # ── 2. Файл выгрузки ───────────────────────────────────────────────────
        s2 = self._section(body, "Файл выгрузки", row=1)

        # Папка
        row_f = ctk.CTkFrame(s2, fg_color="transparent")
        row_f.pack(fill="x", padx=12, pady=(6, 4))
        row_f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row_f, text="Папка:", width=80, anchor="w").grid(
            row=0, column=0, sticky="w")
        self._folder_var = tk.StringVar(value=cfg("sql_export_folder", ""))
        ctk.CTkEntry(row_f, textvariable=self._folder_var,
                     placeholder_text=r"C:\Reports или \\server\share",
                     height=30).grid(row=0, column=1, sticky="ew", padx=(6, 4))
        ctk.CTkButton(row_f, text="📂", width=30, height=30,
                      command=self._browse_folder,
                      fg_color=_GRAY_BTN, hover_color=_GRAY_HVR,
                      ).grid(row=0, column=2, sticky="e")

        # Имя файла
        row_fn = ctk.CTkFrame(s2, fg_color="transparent")
        row_fn.pack(fill="x", padx=12, pady=(0, 2))
        row_fn.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row_fn, text="Имя файла:", width=80, anchor="w").grid(
            row=0, column=0, sticky="w")
        self._filename_var = tk.StringVar(
            value=cfg("sql_export_filename_template", "отчёт"))
        ctk.CTkEntry(row_fn, textvariable=self._filename_var,
                     placeholder_text="Отчёты ОСАС",
                     height=30).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ctk.CTkLabel(s2,
                     text="В ежедневном режиме перед именем добавляется дата (дд.мм.гггг.)",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray45", "gray55"),
                     anchor="w").pack(fill="x", padx=94, pady=(0, 4))

        # Режим файла
        row_fm = ctk.CTkFrame(s2, fg_color="transparent")
        row_fm.pack(fill="x", padx=12, pady=(4, 4))
        ctk.CTkLabel(row_fm, text="Режим:", width=80, anchor="w").pack(side="left")
        saved_fm = cfg("sql_export_file_mode", "daily")
        self._file_mode_var = tk.StringVar(value=saved_fm)
        for val, lbl in (("daily",      "Ежедневный файл с датой"),
                         ("cumulative", "Накопительный файл без даты")):
            ctk.CTkRadioButton(row_fm, text=lbl,
                               variable=self._file_mode_var, value=val,
                               fg_color=_teal(), hover_color=_teal_hvr(),
                               ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(s2,
                     text="Ежедневный: каждый день новый файл  ·  Накопительный: один файл, данные за каждый день добавляются",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray45", "gray55"),
                     anchor="w").pack(fill="x", padx=94, pady=(0, 10))

        # ── 3. Расписание ──────────────────────────────────────────────────────
        s3 = self._section(body, "Расписание", row=2)

        row_t = ctk.CTkFrame(s3, fg_color="transparent")
        row_t.pack(fill="x", padx=12, pady=(6, 4))
        ctk.CTkLabel(row_t, text="Время запуска:", width=110, anchor="w").pack(side="left")

        saved_h = cfg("sql_export_schedule_hour", 19)
        saved_m = cfg("sql_export_schedule_minute", 0)
        self._hour_var   = tk.StringVar(value=f"{saved_h:02d}")
        self._minute_var = tk.StringVar(value=f"{saved_m:02d}")

        ctk.CTkEntry(row_t, textvariable=self._hour_var,
                     width=52, height=30, justify="center").pack(side="left")
        ctk.CTkLabel(row_t, text=":", font=ctk.CTkFont(size=16),
                     width=10).pack(side="left")
        ctk.CTkEntry(row_t, textvariable=self._minute_var,
                     width=52, height=30, justify="center").pack(side="left")
        ctk.CTkLabel(row_t, text="(24-часовой формат)",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray45", "gray55")).pack(side="left", padx=(10, 0))

        row_d = ctk.CTkFrame(s3, fg_color="transparent")
        row_d.pack(fill="x", padx=12, pady=(2, 10))
        ctk.CTkLabel(row_d, text="Дни недели:", width=110, anchor="w").pack(side="left")

        saved_days = cfg("sql_export_schedule_days", [0, 1, 2, 3, 4])
        self._day_vars = []
        for i, day in enumerate(_DAYS_RU):
            var = tk.BooleanVar(value=(i in saved_days))
            self._day_vars.append(var)
            ctk.CTkCheckBox(row_d, text=day, variable=var,
                            width=50, height=24,
                            fg_color=_teal(), hover_color=_teal_hvr(),
                            checkbox_width=16, checkbox_height=16,
                            ).pack(side="left", padx=(4, 0))

        # ── 4. Структура Excel ─────────────────────────────────────────────────
        s4 = self._section(body, "Структура Excel", row=3)

        saved_sm = cfg("sql_export_sheet_mode", "per_query")
        self._sheet_mode_var = tk.StringVar(value=saved_sm)

        ctk.CTkRadioButton(
            s4,
            text="Отдельная вкладка на каждый запрос  (имя вкладки = имя запроса)",
            variable=self._sheet_mode_var, value="per_query",
            fg_color=_teal(), hover_color=_teal_hvr(),
        ).pack(anchor="w", padx=12, pady=(8, 4))

        ctk.CTkRadioButton(
            s4,
            text="Все результаты в одной вкладке  (с разделителями)",
            variable=self._sheet_mode_var, value="single",
            fg_color=_teal(), hover_color=_teal_hvr(),
        ).pack(anchor="w", padx=12, pady=(0, 4))

        ctk.CTkRadioButton(
            s4,
            text="Агрегировать числа — один лист со сводными данными",
            variable=self._sheet_mode_var, value="aggregate",
            fg_color=_teal(), hover_color=_teal_hvr(),
        ).pack(anchor="w", padx=12, pady=(0, 4))
        ctk.CTkLabel(
            s4,
            text="Числовые ячейки суммируются по всем подключениям, текст берётся из первого",
            font=ctk.CTkFont(size=10),
            text_color=("gray45", "gray55"),
            anchor="w",
        ).pack(fill="x", padx=28, pady=(0, 10))

        # ── разделитель + кнопки ───────────────────────────────────────────────
        ctk.CTkFrame(self, height=1,
                     fg_color=("gray75", "gray30")).pack(fill="x")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(10, 14))

        ctk.CTkButton(btn_row, text="Сохранить", command=self._save,
                      width=110, height=34,
                      fg_color=_teal(), hover_color=_teal_hvr(),
                      ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="Отмена", command=self.destroy,
                      width=90, height=34,
                      fg_color=_GRAY_BTN, hover_color=_GRAY_HVR,
                      ).pack(side="right")

    # ── section helper ─────────────────────────────────────────────────────────

    def _section(self, parent, title: str, row: int) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(parent, fg_color=("gray88", "gray18"), corner_radius=8)
        outer.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 10))
        outer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(outer, text=title,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("gray30", "gray70"),
                     anchor="w").pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkFrame(outer, height=1,
                     fg_color=("gray75", "gray30")).pack(fill="x", padx=12, pady=(0, 6))
        return outer

    # ── query rows ─────────────────────────────────────────────────────────────

    def _load_queries(self, saved_qs: list):
        """Заполняет таблицу запросов: сначала сохранённые, затем новые из queries/."""
        existing_paths = {q.get("filepath", "") for q in saved_qs}

        for q in saved_qs:
            # backward compat: старый формат "connection": str
            conns = q.get("connections") or ([q.get("connection")] if q.get("connection") else [])
            self._add_query_row(
                filepath=q.get("filepath", ""),
                display_name=q.get("display_name", ""),
                connections=conns,
                enabled=q.get("enabled", True),
            )

        if self._qdir and os.path.isdir(self._qdir):
            for fname in sorted(os.listdir(self._qdir)):
                if not fname.endswith(".sql"):
                    continue
                fpath = os.path.join(self._qdir, fname)
                if fpath in existing_paths:
                    continue
                self._add_query_row(
                    filepath=fpath,
                    display_name=os.path.splitext(fname)[0],
                    connections=[self._conns[0]] if self._conns else [],
                    enabled=False,
                )

    def _add_query_row(self, filepath: str, display_name: str,
                       connections: list, enabled: bool):
        """Добавляет одну строку запроса в таблицу."""
        f = self._queries_frame
        r = len(self._query_rows)

        row_frame = ctk.CTkFrame(f, fg_color=("gray82", "gray22"),
                                  corner_radius=6)
        row_frame.grid(row=r, column=0, columnspan=5, sticky="ew",
                       pady=(0, 4))
        row_frame.grid_columnconfigure(2, weight=1)

        # чекбокс
        enabled_var = tk.BooleanVar(value=enabled)
        cb = ctk.CTkCheckBox(row_frame, text="", variable=enabled_var,
                             width=24, height=24,
                             fg_color=_teal(), hover_color=_teal_hvr(),
                             checkbox_width=16, checkbox_height=16)
        cb.grid(row=0, column=0, padx=(8, 4), pady=6)

        # поле отображаемого имени
        name_var = tk.StringVar(value=display_name)
        name_entry = ctk.CTkEntry(row_frame, textvariable=name_var,
                                   width=160, height=26)
        name_entry.grid(row=0, column=1, padx=(0, 6), pady=6)

        # путь (сокращённо)
        short_path = self._shorten_path(filepath)
        path_lbl = ctk.CTkLabel(row_frame, text=short_path,
                                 font=ctk.CTkFont(size=10,
                                                   family="Courier New"),
                                 text_color=("gray40", "gray60"),
                                 anchor="w")
        path_lbl.grid(row=0, column=2, sticky="ew", padx=(0, 6), pady=6)
        path_lbl.bind("<Enter>",
                      lambda e, p=filepath: self._show_tooltip(e, p))
        path_lbl.bind("<Leave>", self._hide_tooltip)

        # мультиселект подключений
        conn_state = {"list": list(connections)}

        conn_frame = ctk.CTkFrame(row_frame, fg_color=("gray75", "gray28"),
                                   corner_radius=4, width=160, height=26)
        conn_frame.grid(row=0, column=3, padx=(0, 6), pady=6)
        conn_frame.grid_propagate(False)
        conn_frame.grid_columnconfigure(0, weight=1)

        conn_lbl = ctk.CTkLabel(conn_frame,
                                 text=self._conn_summary(conn_state["list"]),
                                 font=ctk.CTkFont(size=10), anchor="w")
        conn_lbl.grid(row=0, column=0, sticky="ew", padx=(6, 0))

        conn_btn = ctk.CTkButton(conn_frame, text="▾", width=22, height=22,
                                  fg_color=("gray65", "gray22"),
                                  hover_color=("gray55", "gray18"))
        conn_btn.configure(command=lambda cs=conn_state, cl=conn_lbl, cf=conn_frame:
                               self._open_conn_picker(cs, cl, cf))
        conn_btn.grid(row=0, column=1, padx=(0, 2), pady=2)

        # кнопка ×
        data = {
            "row_frame":   row_frame,
            "enabled_var": enabled_var,
            "name_var":    name_var,
            "conn_state":  conn_state,
            "filepath":    filepath,
        }

        del_btn = ctk.CTkButton(row_frame, text="×", width=26, height=26,
                                 fg_color=("gray60", "gray35"),
                                 hover_color=("#EF4444", "#DC2626"),
                                 command=lambda d=data: self._remove_query_row(d))
        del_btn.grid(row=0, column=4, padx=(0, 8), pady=6)

        self._query_rows.append(data)

    def _remove_query_row(self, data: dict):
        if data in self._query_rows:
            self._query_rows.remove(data)
        try:
            data["row_frame"].destroy()
        except Exception:
            pass
        # перегридить оставшиеся строки
        for i, d in enumerate(self._query_rows):
            d["row_frame"].grid(row=i, column=0, columnspan=5, sticky="ew",
                                pady=(0, 4))

    def _add_file(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Выберите SQL-файл",
            filetypes=[("SQL файлы", "*.sql"), ("Все файлы", "*.*")],
        )
        if not path:
            return
        display = os.path.splitext(os.path.basename(path))[0]
        self._add_query_row(
            filepath=path,
            display_name=display,
            connections=[self._conns[0]] if self._conns else [],
            enabled=True,
        )

    # ── connection helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _conn_summary(conn_list: list) -> str:
        """Краткое отображение выбранных подключений для chips-виджета."""
        if not conn_list:
            return "— нет"
        if len(conn_list) == 1:
            return conn_list[0]
        return f"{conn_list[0]} +{len(conn_list) - 1}"

    def _open_conn_picker(self, conn_state: dict, conn_lbl, trigger_widget):
        """Всплывающий чекбокс-список выбора подключений."""
        trigger_widget.update_idletasks()
        x = trigger_widget.winfo_rootx()
        y = trigger_widget.winfo_rooty() + trigger_widget.winfo_height() + 2

        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.wm_overrideredirect(True)
        popup.configure(bg="#1e1e1e")

        frame = ctk.CTkFrame(popup, fg_color=("gray85", "gray20"),
                              corner_radius=6, border_width=1,
                              border_color=("gray70", "gray35"))
        frame.pack(padx=1, pady=1)

        conn_names = self._conns if self._conns else []
        check_vars = {}
        for cname in conn_names:
            var = tk.BooleanVar(value=(cname in conn_state["list"]))
            check_vars[cname] = var
            ctk.CTkCheckBox(frame, text=cname, variable=var,
                            width=150, height=26,
                            fg_color=_teal(), hover_color=_teal_hvr(),
                            checkbox_width=14, checkbox_height=14,
                            ).pack(anchor="w", padx=8, pady=(4, 0))

        def on_ok():
            conn_state["list"] = [c for c, v in check_vars.items() if v.get()]
            conn_lbl.configure(text=self._conn_summary(conn_state["list"]))
            _close()

        def _close():
            try:
                popup.grab_release()
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass
            try:
                self.grab_set()
            except Exception:
                pass

        ctk.CTkButton(frame, text="OK", command=on_ok,
                      width=70, height=26,
                      fg_color=_teal(), hover_color=_teal_hvr(),
                      ).pack(pady=(6, 8))

        popup.geometry(f"+{x}+{y}")
        popup.deiconify()
        try:
            self.grab_release()
            popup.grab_set()
        except Exception:
            pass
        popup.bind("<Escape>", lambda e: _close())
        popup.protocol("WM_DELETE_WINDOW", _close)

    # ── file section ───────────────────────────────────────────────────────────

    def _browse_folder(self):
        path = filedialog.askdirectory(parent=self, title="Выберите папку для сохранения")
        if path:
            self._folder_var.set(path)

    # ── tooltip ────────────────────────────────────────────────────────────────

    def _show_tooltip(self, event, text: str):
        top = tk.Toplevel(self)
        top.wm_overrideredirect(True)
        top.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        tk.Label(top, text=text,
                  background="#1A1A2E", foreground="white",
                  relief="flat", bd=0,
                  font=("Segoe UI", 10), wraplength=480,
                  justify="left", padx=10, pady=6).pack()
        event.widget._tooltip = top

    def _hide_tooltip(self, event):
        t = getattr(event.widget, "_tooltip", None)
        if t:
            try:
                t.destroy()
            except Exception:
                pass
            event.widget._tooltip = None

    # ── save ───────────────────────────────────────────────────────────────────

    def _save(self):
        from tkinter import messagebox as _mb

        # Валидация расписания
        try:
            h = int(self._hour_var.get().strip())
            m = int(self._minute_var.get().strip())
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
        except ValueError:
            _mb.showerror("Ошибка",
                          "Время запуска: часы 0–23, минуты 0–59.",
                          parent=self)
            return

        active_days = [i for i, v in enumerate(self._day_vars) if v.get()]

        # Валидация запросов
        queries = []
        for d in self._query_rows:
            queries.append({
                "display_name": d["name_var"].get().strip() or "Query",
                "filepath":     d["filepath"],
                "connections":  list(d["conn_state"]["list"]),
                "enabled":      d["enabled_var"].get(),
            })

        enabled_count = sum(1 for q in queries if q["enabled"])
        if enabled_count == 0 and queries:
            _mb.showerror("Ошибка",
                          "Отметьте хотя бы один запрос для выгрузки.",
                          parent=self)
            return

        sm = self._sm
        sm.set_setting("sql_export_queries",           queries)
        sm.set_setting("sql_export_folder",            self._folder_var.get().strip())
        sm.set_setting("sql_export_filename_template", self._filename_var.get().strip()
                       or "отчёт")
        sm.set_setting("sql_export_file_mode",         self._file_mode_var.get())
        sm.set_setting("sql_export_sheet_mode",        self._sheet_mode_var.get())
        sm.set_setting("sql_export_schedule_hour",     h)
        sm.set_setting("sql_export_schedule_minute",   m)
        sm.set_setting("sql_export_schedule_days",     active_days)

        if self._on_saved:
            self._on_saved()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    # ── helper ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _shorten_path(path: str, max_len: int = 34) -> str:
        """Возвращает сокращённый путь вида …/filename.sql."""
        if not path:
            return "—"
        bn = os.path.basename(path)
        if len(path) <= max_len:
            return path
        return f"…/{bn}"
