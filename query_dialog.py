import re
import tkinter as tk
import customtkinter as ctk
import dialogs as messagebox
from typing import Optional
from utils import clipboard_get_text, setup_paste_bindings
from db_manager import DatabaseManager


# ── SQL highlighting ──────────────────────────────────────────────────────────

_SQL_PATTERNS: list = [
    # order matters: comments/strings win over keywords
    ("comment_block", re.compile(r"/\*[\s\S]*?\*/",  re.DOTALL)),
    ("comment_line",  re.compile(r"--[^\n]*")),
    ("string",        re.compile(r"'(?:[^'\\]|\\.)*'")),
    ("function",      re.compile(
        r"\b(COUNT|SUM|AVG|MIN|MAX|COALESCE|NULLIF|IFNULL|ISNULL|NVL|NVL2|"
        r"CAST|CONVERT|UPPER|LOWER|TRIM|LTRIM|RTRIM|LENGTH|LEN|SUBSTR|SUBSTRING|"
        r"REPLACE|CONCAT|NOW|CURRENT_DATE|CURRENT_TIMESTAMP|DATE_PART|EXTRACT|"
        r"ROUND|FLOOR|CEIL|CEILING|ABS|MOD|POWER|SQRT|TO_CHAR|TO_DATE|TO_NUMBER|"
        r"ROW_NUMBER|RANK|DENSE_RANK|NTILE|LAG|LEAD|FIRST_VALUE|LAST_VALUE|"
        r"OVER|PARTITION|GENERATE_SERIES|ARRAY_AGG|STRING_AGG|GROUP_CONCAT|"
        r"LISTAGG|STUFF|IIF|DECODE|GREATEST|LEAST|DATEDIFF|DATEADD|FORMAT)\s*(?=\()",
        re.IGNORECASE)),
    ("keyword",       re.compile(
        r"\b(SELECT|DISTINCT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|CROSS|"
        r"NATURAL|LATERAL|ON|USING|AS|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|TOP|"
        r"FETCH|NEXT|ROWS|ONLY|UNION|ALL|INTERSECT|EXCEPT|WITH|RECURSIVE|"
        r"INSERT|INTO|VALUES|UPDATE|SET|DELETE|MERGE|UPSERT|"
        r"CREATE|ALTER|DROP|TABLE|VIEW|INDEX|SEQUENCE|SCHEMA|DATABASE|"
        r"AND|OR|NOT|IN|EXISTS|BETWEEN|LIKE|ILIKE|REGEXP|SIMILAR|IS|"
        r"NULL|TRUE|FALSE|CASE|WHEN|THEN|ELSE|END|RETURNING|"
        r"ASC|DESC|NULLS|FIRST|LAST|"
        r"PRIMARY|KEY|UNIQUE|FOREIGN|REFERENCES|DEFAULT|CHECK|CONSTRAINT|"
        r"BEGIN|COMMIT|ROLLBACK|TRANSACTION|SAVEPOINT|EXPLAIN|ANALYZE|VERBOSE)\b",
        re.IGNORECASE)),
    ("number", re.compile(r"\b\d+(?:\.\d+)?\b")),
]

_TAG_COLORS = {
    "Dark": {
        "keyword":       "#569CD6",
        "function":      "#DCDCAA",
        "string":        "#CE9178",
        "comment_line":  "#6A9955",
        "comment_block": "#6A9955",
        "number":        "#B5CEA8",
    },
    "Light": {
        "keyword":       "#0000CC",
        "function":      "#7B5A21",
        "string":        "#A31515",
        "comment_line":  "#008000",
        "comment_block": "#008000",
        "number":        "#098658",
    },
}

# Priority: last tag_raise wins; comments/strings should override keywords
_RAISE_ORDER = ("keyword", "function", "number", "string", "comment_line", "comment_block")


class QueryDialog(ctk.CTkToplevel):
    """Модальное окно добавления / редактирования SQL-запроса."""

    _deactivate_windows_window_header_manipulation = True

    def __init__(self, parent, db_names: list,
                 initial_name:     str  = None,
                 initial_db:       str  = None,
                 initial_sql:      str  = None,
                 initial_interval: int  = 0,
                 initial_alert_on_change: bool = False,
                 initial_alert_threshold: dict = None,
                 initial_is_widget: bool = False,
                 initial_cron_schedule: dict = None,
                 db_manager             = None,
                 db_name_map:      dict = None,
                 settings_manager       = None):
        super().__init__(parent)
        self.withdraw()
        self._edit_mode        = initial_name is not None
        self._db_manager       = db_manager
        self._db_name_map      = db_name_map or {}
        self._settings_manager = settings_manager
        self._hl_after_id      = None

        self.title("Изменить запрос" if self._edit_mode else "Новый SQL-запрос")
        self.resizable(True, True)
        self.minsize(520, 460)
        self.result = None

        self.transient(parent)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        self._build(db_names, initial_name, initial_db, initial_sql, initial_interval,
                    initial_alert_on_change, initial_alert_threshold or {},
                    initial_is_widget, initial_cron_schedule or {})
        self.after(50, self._center)

    # ── построение UI ────────────────────────────────────────────────────────

    def _build(self, db_names, initial_name, initial_db, initial_sql, initial_interval,
               initial_alert_on_change=False, initial_alert_threshold=None,
               initial_is_widget=False, initial_cron_schedule=None):
        pad = {"padx": 20}
        cron = initial_cron_schedule or {}
        title_text = "Изменить запрос" if self._edit_mode else "Новый SQL-запрос"

        ctk.CTkLabel(self, text=title_text,
                     font=ctk.CTkFont(size=16, weight="bold"),
                     anchor="w").grid(row=0, column=0, **pad, pady=(18, 14), sticky="ew")

        # Имя запроса
        ctk.CTkLabel(self, text="Имя запроса", anchor="w").grid(
            row=1, column=0, **pad, pady=(0, 4), sticky="ew")
        self.name_entry = ctk.CTkEntry(self, placeholder_text="Например: Кол-во пользователей")
        if initial_name:
            self.name_entry.insert(0, initial_name)
        self.name_entry.grid(row=2, column=0, **pad, sticky="ew")

        # База данных
        ctk.CTkLabel(self, text="База данных", anchor="w").grid(
            row=3, column=0, **pad, pady=(12, 4), sticky="ew")
        values = db_names if db_names else ["— нет подключений —"]
        self.db_combo = ctk.CTkComboBox(self, values=values, state="readonly")
        if initial_db and initial_db in values:
            self.db_combo.set(initial_db)
        else:
            self.db_combo.set(values[0])
        self.db_combo.grid(row=4, column=0, **pad, sticky="ew")

        # SQL-редактор (tk.Text с подсветкой синтаксиса)
        ctk.CTkLabel(self, text="SQL-запрос (только SELECT)", anchor="w").grid(
            row=5, column=0, **pad, pady=(12, 4), sticky="new")

        sql_outer = ctk.CTkFrame(self, corner_radius=6)
        sql_outer.grid(row=5, column=0, **pad, pady=(32, 0), sticky="nsew")
        sql_outer.grid_columnconfigure(0, weight=1)
        sql_outer.grid_rowconfigure(0, weight=1)

        dark = ctk.get_appearance_mode() == "Dark"
        self._sql_text = tk.Text(
            sql_outer, wrap="none", font=("Consolas", 13),
            background="#1e1e1e" if dark else "#f5f5f5",
            foreground="#d4d4d4" if dark else "#1a1a1a",
            insertbackground="#aeafad" if dark else "#000000",
            selectbackground="#264f78" if dark else "#add6ff",
            selectforeground="#ffffff",
            relief="flat", padx=8, pady=6, undo=True,
        )
        vsb = ctk.CTkScrollbar(sql_outer, command=self._sql_text.yview)
        hsb = ctk.CTkScrollbar(sql_outer, orientation="horizontal",
                               command=self._sql_text.xview)
        self._sql_text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._sql_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._sql_text.insert("1.0", initial_sql if initial_sql else "SELECT * FROM table;")
        self._configure_sql_tags()
        self._highlight_sql()

        self._sql_text.bind("<KeyRelease>", lambda e: self._schedule_highlight())
        self._sql_text.bind("<Control-a>",  self._select_all)
        self._sql_text.bind("<Control-A>",  self._select_all)
        self._sql_text.bind("<Button-3>",   self._show_sql_context_menu)

        # ── Секция настроек (прокручиваемая) ─────────────────────────────────
        _sf = ctk.CTkScrollableFrame(self, fg_color="transparent", height=260)
        _sf.grid(row=6, column=0, padx=20, pady=(8, 0), sticky="ew")
        _sf.grid_columnconfigure(0, weight=1)
        ipad = {"padx": 8}

        # ── Расписание обновления ─────────────────────────────────────────────
        ctk.CTkLabel(_sf, text="Расписание обновления", anchor="w").grid(
            row=0, column=0, **ipad, pady=(4, 4), sticky="ew")

        sched_frame = ctk.CTkFrame(_sf, fg_color="transparent")
        sched_frame.grid(row=1, column=0, **ipad, sticky="ew")

        # Режим: Интервал / По расписанию
        _sched_initial = "cron" if cron.get("enabled") else "interval"
        self._sched_mode_var = ctk.StringVar(value=_sched_initial)

        ctk.CTkRadioButton(
            sched_frame, text="Интервал (мин.)",
            variable=self._sched_mode_var, value="interval",
            command=self._update_sched_mode,
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ctk.CTkRadioButton(
            sched_frame, text="По расписанию (cron)",
            variable=self._sched_mode_var, value="cron",
            command=self._update_sched_mode,
        ).grid(row=0, column=1, sticky="w")

        # Интервал
        self._interval_frame = ctk.CTkFrame(sched_frame, fg_color="transparent")
        self._interval_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.interval_entry = ctk.CTkEntry(self._interval_frame, placeholder_text="0", width=90)
        self.interval_entry.insert(0, str(initial_interval if initial_interval else 0))
        self.interval_entry.pack(side="left")
        ctk.CTkLabel(self._interval_frame, text="(0 = не обновлять)",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left", padx=8)

        # Cron-расписание
        self._cron_frame = ctk.CTkFrame(sched_frame, fg_color="transparent")
        self._cron_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        # Время
        time_row = ctk.CTkFrame(self._cron_frame, fg_color="transparent")
        time_row.pack(anchor="w")
        ctk.CTkLabel(time_row, text="Время запуска:", anchor="w", width=115).pack(side="left")
        _cron_time = cron.get("time", "09:00")
        _ch, _cm   = (_cron_time.split(":") + ["00"])[:2]
        self._cron_hour_var = ctk.StringVar(value=_ch.zfill(2))
        self._cron_min_var  = ctk.StringVar(value=_cm.zfill(2))
        ctk.CTkEntry(time_row, textvariable=self._cron_hour_var, width=44).pack(side="left")
        ctk.CTkLabel(time_row, text=":").pack(side="left", padx=2)
        ctk.CTkEntry(time_row, textvariable=self._cron_min_var, width=44).pack(side="left")
        ctk.CTkLabel(time_row, text="(ЧЧ:ММ)",
                     text_color="gray", font=ctk.CTkFont(size=10)).pack(side="left", padx=6)

        # Дни недели
        days_row = ctk.CTkFrame(self._cron_frame, fg_color="transparent")
        days_row.pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(days_row, text="Дни недели:", anchor="w", width=115).pack(side="left")
        _DAY_LABELS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
        _cron_days  = cron.get("days", [])
        self._cron_day_vars = []
        for i, lbl in enumerate(_DAY_LABELS):
            v = ctk.BooleanVar(value=(not _cron_days or i in _cron_days))
            self._cron_day_vars.append(v)
            ctk.CTkCheckBox(days_row, text=lbl, variable=v, width=50).pack(side="left")
        ctk.CTkLabel(days_row, text="(нет — каждый день)",
                     text_color="gray", font=ctk.CTkFont(size=10)).pack(side="left", padx=4)

        self._update_sched_mode()

        # ── Мониторинг и оповещения ──────────────────────────────────────────────
        ctk.CTkFrame(_sf, height=1, fg_color=("gray70", "gray35")).grid(
            row=2, column=0, **ipad, pady=(14, 0), sticky="ew")

        ctk.CTkLabel(_sf, text="Мониторинг и оповещения",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").grid(row=3, column=0, **ipad, pady=(6, 6), sticky="ew")

        # Алерт при изменении результата
        self._alert_on_change_var = ctk.BooleanVar(value=bool(initial_alert_on_change))
        ctk.CTkCheckBox(
            _sf, text="Алерт при изменении результата",
            variable=self._alert_on_change_var,
        ).grid(row=4, column=0, **ipad, pady=(0, 6), sticky="w")

        # Пороговый алерт
        thr = initial_alert_threshold or {}
        thr_frame = ctk.CTkFrame(_sf, fg_color="transparent")
        thr_frame.grid(row=5, column=0, **ipad, pady=(0, 4), sticky="ew")
        thr_frame.grid_columnconfigure(4, weight=1)

        self._threshold_enabled_var = ctk.BooleanVar(
            value=bool(thr.get("enabled", False)))
        ctk.CTkCheckBox(
            thr_frame, text="Пороговый алерт: столбец №",
            variable=self._threshold_enabled_var,
            command=self._update_threshold_state,
        ).grid(row=0, column=0, padx=(0, 4), sticky="w")

        self._threshold_col_entry = ctk.CTkEntry(thr_frame, width=44,
                                                 placeholder_text="0")
        self._threshold_col_entry.insert(0, str(thr.get("column", 0)))
        self._threshold_col_entry.grid(row=0, column=1, padx=(0, 6))

        self._threshold_op_combo = ctk.CTkComboBox(
            thr_frame, values=[">", "<", ">=", "<=", "==", "!="],
            state="readonly", width=70)
        self._threshold_op_combo.set(thr.get("operator", ">"))
        self._threshold_op_combo.grid(row=0, column=2, padx=(0, 6))

        self._threshold_val_entry = ctk.CTkEntry(thr_frame, width=100,
                                                 placeholder_text="0")
        val_str = str(thr.get("value", "")) if thr.get("value") is not None else ""
        if val_str and val_str != "None":
            self._threshold_val_entry.insert(0, val_str)
        self._threshold_val_entry.grid(row=0, column=3, padx=(0, 4))

        ctk.CTkLabel(thr_frame, text="(строка 0)", anchor="w",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray50", "gray60")).grid(
            row=0, column=4, padx=(2, 0), sticky="w")

        self._update_threshold_state()

        # ── Виджет ───────────────────────────────────────────────────────────
        ctk.CTkFrame(_sf, height=1, fg_color=("gray70", "gray35")).grid(
            row=6, column=0, **ipad, pady=(14, 0), sticky="ew")
        self._is_widget_var = ctk.BooleanVar(value=bool(initial_is_widget))
        ctk.CTkCheckBox(
            _sf, text="Виджет  (показывать результат запроса в шапке программы)",
            variable=self._is_widget_var,
        ).grid(row=7, column=0, **ipad, pady=(8, 8), sticky="w")

        # ── Кнопки (вне прокрутки, закреплены снизу) ─────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=7, column=0, **pad, pady=(8, 16), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ok_text = "Сохранить" if self._edit_mode else "Добавить"
        ctk.CTkButton(btn_frame, text=ok_text, command=self._on_ok).grid(
            row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(btn_frame, text="Отмена", command=self._on_cancel).grid(
            row=0, column=1, padx=(6, 0), sticky="ew")

        if self._edit_mode:
            self._sql_text.focus_set()
        else:
            self.name_entry.focus()
        self.bind("<Escape>",          lambda _: self._on_cancel())
        self.bind("<Control-Return>",  lambda _: self._on_ok())
        # Return on individual entries (not SQL editor) submits the form
        self.name_entry.bind("<Return>",    lambda _: self._on_ok())
        self.interval_entry.bind("<Return>", lambda _: self._on_ok())
        self.bind("<Destroy>", self._save_size)
        self.bind("<Control-c>", self._copy_focused)
        self.bind("<Control-C>", self._copy_focused)
        self._setup_paste_bindings()

    # ── переключатель режима расписания ──────────────────────────────────────

    def _update_sched_mode(self):
        mode = self._sched_mode_var.get()
        if mode == "interval":
            self._interval_frame.grid()
            self._cron_frame.grid_remove()
        else:
            self._interval_frame.grid_remove()
            self._cron_frame.grid()

    # ── алерты: состояние порогового ввода ───────────────────────────────────

    def _update_threshold_state(self):
        enabled = self._threshold_enabled_var.get()
        state   = "normal" if enabled else "disabled"
        op_state = "readonly" if enabled else "disabled"
        self._threshold_col_entry.configure(state=state)
        self._threshold_op_combo.configure(state=op_state)
        self._threshold_val_entry.configure(state=state)

    # ── подсветка синтаксиса ──────────────────────────────────────────────────

    def _configure_sql_tags(self):
        mode   = ctk.get_appearance_mode()
        colors = _TAG_COLORS.get(mode, _TAG_COLORS["Dark"])
        for tag in _RAISE_ORDER:
            self._sql_text.tag_configure(tag, foreground=colors.get(tag, "#d4d4d4"))
        for tag in _RAISE_ORDER:
            self._sql_text.tag_raise(tag)

    def _schedule_highlight(self):
        if self._hl_after_id:
            try:
                self.after_cancel(self._hl_after_id)
            except Exception:
                pass
        self._hl_after_id = self.after(100, self._highlight_sql)

    def _highlight_sql(self):
        content = self._sql_text.get("1.0", "end-1c")
        for tag, _ in _SQL_PATTERNS:
            self._sql_text.tag_remove(tag, "1.0", "end")
        for tag, rx in _SQL_PATTERNS:
            for m in rx.finditer(content):
                self._sql_text.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        for tag in _RAISE_ORDER:
            self._sql_text.tag_raise(tag)

    def _select_all(self, event=None):
        self._sql_text.tag_add("sel", "1.0", "end")
        return "break"

    def _show_sql_context_menu(self, event=None):
        has_sel = bool(self._sql_text.tag_ranges("sel"))
        menu = tk.Menu(self._sql_text, tearoff=0)
        menu.add_command(
            label="Вырезать",
            command=lambda: self._sql_text.event_generate("<<Cut>>"),
            state="normal" if has_sel else "disabled",
        )
        menu.add_command(
            label="Копировать",
            command=lambda: self._sql_text.event_generate("<<Copy>>"),
            state="normal" if has_sel else "disabled",
        )
        menu.add_command(
            label="Вставить",
            command=lambda: self._sql_text.event_generate("<<Paste>>"),
        )
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=self._select_all)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ── обработчики ──────────────────────────────────────────────────────────

    def _on_ok(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Ошибка", "Введите имя запроса", parent=self)
            return

        db  = self.db_combo.get()
        sql = self._sql_text.get("1.0", "end-1c").strip()
        if not sql:
            messagebox.showerror("Ошибка", "Введите SQL-запрос", parent=self)
            return
        # Полная валидация через db_manager (whitelist + multi-statement + blacklist)
        ok, reason = DatabaseManager._validate_query(sql)
        if not ok:
            messagebox.showerror(
                "Ошибка",
                f"Недопустимый SQL-запрос:\n{reason}\n\nДопускаются только SELECT-запросы.",
                parent=self,
            )
            return

        # EXPLAIN-валидация: безопасный метод, валидирует SQL перед отправкой в БД
        if self._db_manager and db in self._db_name_map:
            config_name = self._db_name_map[db]
            try:
                db_type = self._db_manager.load_config(config_name).get(
                    "database_type", "sqlite").lower()
            except Exception:
                db_type = "sqlite"
            if db_type not in ("oracle", "mssql"):
                try:
                    self._db_manager.explain_query(config_name, sql, db_type)
                except NotImplementedError:
                    pass
                except ValueError as ex:
                    # explain_query отклонил SQL — показываем ошибку и не сохраняем
                    messagebox.showerror(
                        "Ошибка", f"SQL не прошёл проверку безопасности:\n{ex}",
                        parent=self)
                    return
                except Exception as ex:
                    short = str(ex)[:300]
                    if not messagebox.askokcancel(
                        "Предупреждение",
                        f"EXPLAIN вернул ошибку:\n{short}\n\nСохранить запрос всё равно?",
                        parent=self,
                    ):
                        return

        # ── расписание ────────────────────────────────────────────────────────
        cron_schedule = None
        interval      = 0
        if self._sched_mode_var.get() == "cron":
            try:
                h = int(self._cron_hour_var.get())
                m = int(self._cron_min_var.get())
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Время cron — ЧЧ (0–23) : ММ (0–59)",
                                     parent=self)
                return
            days = [i for i, v in enumerate(self._cron_day_vars) if v.get()]
            cron_schedule = {
                "enabled": True,
                "time":    f"{h:02d}:{m:02d}",
                "days":    days,
            }
        else:
            interval_str = self.interval_entry.get().strip()
            try:
                interval = int(interval_str) if interval_str else 0
                if interval < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Интервал — целое число ≥ 0", parent=self)
                return

        alert_on_change = self._alert_on_change_var.get()

        alert_threshold = None
        if self._threshold_enabled_var.get():
            col_str = self._threshold_col_entry.get().strip()
            val_str = self._threshold_val_entry.get().strip()
            op      = self._threshold_op_combo.get()
            try:
                col = int(col_str) if col_str else 0
                if col < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Индекс столбца — целое число ≥ 0",
                                     parent=self)
                return
            try:
                thr_val = float(val_str) if val_str else 0.0
            except ValueError:
                messagebox.showerror("Ошибка", "Пороговое значение — число",
                                     parent=self)
                return
            alert_threshold = {"enabled": True, "column": col,
                               "operator": op, "value": thr_val}

        self.result = (name, db, sql, interval, alert_on_change, alert_threshold,
                       self._is_widget_var.get(), cron_schedule)
        _master = self.master
        self.destroy()
        try:
            _master.focus_set()
        except Exception:
            pass

    def _on_cancel(self):
        _master = self.master
        self.destroy()
        try:
            _master.focus_set()
        except Exception:
            pass

    def _copy_focused(self, event=None):
        w = self.focus_get()
        if w is not None:
            try:
                w.event_generate("<<Copy>>")
            except Exception:
                pass
        return "break"

    def _setup_paste_bindings(self):
        setup_paste_bindings(self)

    def _save_size(self, event):
        if event.widget is not self or not self._settings_manager:
            return
        try:
            w, h = self.winfo_width(), self.winfo_height()
            if w > 10 and h > 10:
                self._settings_manager.set_setting("dialog_size_query", [w, h])
        except Exception:
            pass

    # ── центрирование ─────────────────────────────────────────────────────────

    def _center(self):
        self.update_idletasks()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        saved  = (self._settings_manager.get_setting("dialog_size_query")
                  if self._settings_manager else None)
        if saved and len(saved) == 2:
            w, h = saved
        else:
            w = self.winfo_reqwidth()
            h = int(self.winfo_reqheight() * 0.8)
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.grab_set()
