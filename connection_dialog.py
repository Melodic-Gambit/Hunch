import threading
import customtkinter as ctk
import dialogs as messagebox
from typing import Optional
from utils import clipboard_get_text, setup_paste_bindings

try:
    import keyring as _keyring
    _KEYRING_OK = True
except Exception:
    _KEYRING_OK = False

_KEYRING_SERVICE = "hunch"


class DatabaseConnectionDialog(ctk.CTkToplevel):
    """
    Модальное окно подключения к БД.
    Если переданы initial_name / initial_config — работает в режиме редактирования.
    Если передан db_manager — показывает кнопку "Проверить".
    """

    _ANIM_FRAMES   = ("Проверяю", "Проверяю ·", "Проверяю · ·", "Проверяю · · ·")
    _SQLITE_HIDDEN = {"host", "port", "user", "password", "charset"}

    def __init__(self, parent, initial_name: str = None,
                 initial_config: dict = None, initial_interval: int = 0,
                 db_manager=None, settings_manager=None, log_manager=None):
        super().__init__(parent)
        self.withdraw()
        self._edit_mode        = initial_name is not None
        self._db_manager       = db_manager
        self._settings_manager = settings_manager
        self._log_manager      = log_manager
        self._anim_id          = None
        self._anim_idx         = 0
        self.result = None

        self.title("Изменить подключение" if self._edit_mode else "Новое подключение")
        self.resizable(True, True)
        self.minsize(440, 0)
        self.transient(parent)

        self._build(initial_name, initial_config or {}, initial_interval)
        self.after(50, self._center)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build(self, name: str, cfg: dict, initial_interval: int):
        pad = {"padx": 20}

        ctk.CTkLabel(self,
                     text="Изменить подключение" if self._edit_mode else "Новое подключение",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     anchor="w").grid(row=0, column=0, columnspan=2,
                                      **pad, pady=(18, 14), sticky="ew")

        self.grid_columnconfigure(1, weight=1)

        fields = [
            ("Имя подключения:",  "name"),
            ("Тип БД:",           "db_type"),
            ("Хост:",             "host"),
            ("Порт:",             "port"),
            ("Имя БД:",           "db_name"),
            ("Пользователь:",     "user"),
            ("Пароль:",           "password"),
            ("Кодировка:",        "charset"),
            ("Обновлять каждые (мин., 0 = не обновлять):", "interval"),
        ]

        self._field_labels: dict = {}
        for i, (label_text, key) in enumerate(fields):
            lbl = ctk.CTkLabel(self, text=label_text, anchor="w")
            lbl.grid(row=i + 1, column=0, padx=(20, 8), pady=4, sticky="w")
            self._field_labels[key] = lbl

        r = 1

        # Имя подключения
        _name_wrap = ctk.CTkFrame(self, fg_color="transparent", height=1)
        _name_wrap.grid(row=r, column=1, padx=(0, 20), pady=(4, 0), sticky="ew")
        _name_wrap.grid_columnconfigure(0, weight=1)
        self.name_entry = ctk.CTkEntry(_name_wrap, placeholder_text="my_database")
        if name:
            self.name_entry.insert(0, name)
        self.name_entry.grid(row=0, column=0, sticky="ew")
        self._hint_name = ctk.CTkLabel(
            _name_wrap, text="", text_color=("#EF4444", "#DC2626"),
            font=ctk.CTkFont(size=10), anchor="w", height=14)
        self._hint_name.grid(row=1, column=0, sticky="w", pady=(1, 0))
        self._hint_name.grid_remove()
        self.name_entry.bind("<FocusOut>", self._validate_name_inline)
        r += 1

        # Тип БД
        db_types = ["sqlite", "postgresql", "mysql", "oracle", "mssql"]
        self.db_type_combo = ctk.CTkComboBox(
            self, values=db_types, command=self._on_db_type_changed)
        self.db_type_combo.set(cfg.get("database_type", "sqlite"))
        self.db_type_combo.grid(row=r, column=1, padx=(0, 20), pady=4, sticky="ew")
        r += 1

        # Хост
        self.host_entry = ctk.CTkEntry(self, placeholder_text="localhost")
        host_val = cfg.get("host", "")
        if host_val:
            self.host_entry.insert(0, host_val)
        self.host_entry.grid(row=r, column=1, padx=(0, 20), pady=4, sticky="ew")
        r += 1

        # Порт
        self._port_wrap = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self._port_wrap.grid(row=r, column=1, padx=(0, 20), pady=(4, 0), sticky="ew")
        self._port_wrap.grid_columnconfigure(0, weight=1)
        self.port_entry = ctk.CTkEntry(self._port_wrap, placeholder_text="5432")
        port_val = cfg.get("port", "")
        if port_val:
            self.port_entry.insert(0, str(port_val))
        self.port_entry.grid(row=0, column=0, sticky="ew")
        self._hint_port = ctk.CTkLabel(
            self._port_wrap, text="", text_color=("#EF4444", "#DC2626"),
            font=ctk.CTkFont(size=10), anchor="w", height=14)
        self._hint_port.grid(row=1, column=0, sticky="w", pady=(1, 0))
        self._hint_port.grid_remove()
        self.port_entry.bind("<FocusOut>", self._validate_port_inline)
        r += 1

        # Имя БД
        self.db_name_entry = ctk.CTkEntry(self, placeholder_text="database_name")
        db_name_val = cfg.get("database_name", "")
        if db_name_val:
            self.db_name_entry.insert(0, db_name_val)
        self.db_name_entry.grid(row=r, column=1, padx=(0, 20), pady=4, sticky="ew")
        r += 1

        # Пользователь
        self.user_entry = ctk.CTkEntry(self, placeholder_text="username")
        user_val = cfg.get("username", "")
        if user_val:
            self.user_entry.insert(0, user_val)
        self.user_entry.grid(row=r, column=1, padx=(0, 20), pady=4, sticky="ew")
        r += 1

        # Пароль
        self.password_entry = ctk.CTkEntry(self, show="*", placeholder_text="••••••••")
        if cfg.get("password_in_keyring") and name and _KEYRING_OK:
            try:
                password_val = _keyring.get_password(_KEYRING_SERVICE, name) or ""
            except Exception:
                password_val = ""
        else:
            password_val = cfg.get("password", "")
        if password_val:
            self.password_entry.insert(0, password_val)
        self.password_entry.grid(row=r, column=1, padx=(0, 20), pady=4, sticky="ew")
        r += 1

        # Кодировка
        charsets = ["utf8", "utf8mb4", "latin1", "cp1251"]
        self.charset_combo = ctk.CTkComboBox(self, values=charsets)
        self.charset_combo.set(cfg.get("charset", "utf8"))
        self.charset_combo.grid(row=r, column=1, padx=(0, 20), pady=4, sticky="ew")
        r += 1

        # Обновлять каждые
        self.interval_entry = ctk.CTkEntry(self, placeholder_text="0")
        self.interval_entry.insert(0, str(initial_interval if initial_interval else 0))
        self.interval_entry.grid(row=r, column=1, padx=(0, 20), pady=4, sticky="ew")
        r += 1

        # ── Кнопки ───────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=r, column=0, columnspan=2, **pad, pady=14, sticky="ew")
        r += 1

        if self._db_manager is not None:
            btn_frame.grid_columnconfigure((0, 1, 2), weight=1)
            self._test_btn = ctk.CTkButton(
                btn_frame, text="Проверить", command=self._on_test)
            self._test_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")
            ok_col, cancel_col = 1, 2
            ok_px = (4, 4)
            cancel_px = (4, 0)
        else:
            btn_frame.grid_columnconfigure((0, 1), weight=1)
            ok_col, cancel_col = 0, 1
            ok_px = (0, 6)
            cancel_px = (6, 0)

        ok_text = "Сохранить" if self._edit_mode else "Подключить"
        ctk.CTkButton(btn_frame, text=ok_text, command=self._on_ok).grid(
            row=0, column=ok_col, padx=ok_px, sticky="ew")
        ctk.CTkButton(btn_frame, text="Отмена", command=self._on_cancel).grid(
            row=0, column=cancel_col, padx=cancel_px, sticky="ew")

        # ── Строка статуса (анимация / успех / заголовок ошибки) ─────────────
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.grid(row=r, column=0, columnspan=2,
                        padx=20, pady=(0, 2), sticky="ew")
        status_row.grid_columnconfigure(0, weight=1)

        self._test_status_lbl = ctk.CTkLabel(
            status_row, text="", anchor="w", font=ctk.CTkFont(size=12))
        self._test_status_lbl.grid(row=0, column=0, sticky="ew")

        self._copy_error_btn = ctk.CTkButton(
            status_row, text="📋 Копировать", width=115, height=26,
            fg_color="transparent",
            border_width=1,
            border_color=("gray60", "gray45"),
            text_color=("gray35", "gray75"),
            hover_color=("gray85", "gray28"),
            command=self._copy_error_text)
        self._copy_error_btn.grid(row=0, column=1, padx=(8, 0))
        self._copy_error_btn.grid_remove()
        r += 1

        # ── Блок полного текста ошибки (скрыт до первой ошибки) ──────────────
        self._test_error_box = ctk.CTkTextbox(
            self, wrap="word", height=90,
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled",
            border_width=1,
            activate_scrollbars=True,
        )
        self._test_error_box.grid(row=r, column=0, columnspan=2,
                                  padx=20, pady=(0, 14), sticky="ew")
        self._test_error_box.grid_remove()

        self._on_db_type_changed()
        self.name_entry.focus()
        self.bind("<Escape>",  lambda _: self._on_cancel())
        self.bind("<Return>",  lambda _: self._on_ok())
        self.bind("<Destroy>", self._save_size)
        self.bind("<Control-c>", self._copy_focused)
        self.bind("<Control-C>", self._copy_focused)
        self._setup_paste_bindings()

    # ── обработчики ──────────────────────────────────────────────────────────

    def _on_db_type_changed(self, value=None):
        is_sqlite = self.db_type_combo.get().strip().lower() == "sqlite"
        widget_map = {
            "host":     self.host_entry,
            "port":     self._port_wrap,
            "user":     self.user_entry,
            "password": self.password_entry,
            "charset":  self.charset_combo,
        }
        for key in self._SQLITE_HIDDEN:
            lbl = self._field_labels[key]
            wgt = widget_map[key]
            if is_sqlite:
                lbl.grid_remove()
                wgt.grid_remove()
            else:
                lbl.grid()
                wgt.grid()
        if self.winfo_ismapped():
            self.update_idletasks()
            new_h = self.winfo_reqheight()
            if new_h > 50:
                self.geometry(f"{self.winfo_width()}x{new_h}")

    def _validate_port(self, port_str: str) -> Optional[int]:
        if not port_str:
            messagebox.showerror("Ошибка", "Введите порт", parent=self)
            return None
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Порт — целое число от 1 до 65535", parent=self)
            return None
        return port

    def _build_config_from_form(self) -> Optional[dict]:
        db_type  = self.db_type_combo.get().strip().lower()
        host     = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()
        db_name  = self.db_name_entry.get().strip()
        user     = self.user_entry.get().strip()
        password = self.password_entry.get()
        charset  = self.charset_combo.get().strip()

        if db_type != "sqlite":
            port = self._validate_port(port_str)
            if port is None:
                return None
        else:
            port = 0

        return {
            "database_type": db_type,
            "host":          host or "localhost",
            "port":          port,
            "database_name": db_name,
            "username":      user,
            "password":      password,
            "charset":       charset,
        }

    def _on_test(self):
        config = self._build_config_from_form()
        if config is None:
            return
        name = self.name_entry.get().strip() or "(без имени)"
        self._test_btn.configure(state="disabled", text="Проверяю…")
        self._hide_error_box()
        self._start_anim()
        threading.Thread(target=self._bg_test, args=(config, name), daemon=True).start()

    def _bg_test(self, config: dict, name: str):
        ok, msg = self._db_manager.test_connection_raw(config)

        def _done():
            try:
                self._stop_anim()
                if ok:
                    self._test_status_lbl.configure(
                        text="✓ Подключение успешно",
                        text_color=("#22C55E", "#16A34A"))
                    self._hide_error_box()
                    if self._log_manager:
                        self._log_manager.add_log(
                            f"Проверка подключения '{name}': успешно")
                else:
                    self._test_status_lbl.configure(
                        text="✗ Ошибка подключения:",
                        text_color=("#EF4444", "#DC2626"))
                    self._show_error_box(msg)
                    if self._log_manager:
                        self._log_manager.add_log(
                            f"Проверка подключения '{name}': {msg}", "ERROR")
                self._test_btn.configure(state="normal", text="Проверить")
            except Exception:
                pass

        try:
            self.after(0, _done)
        except Exception:
            pass

    # ── анимация проверки ─────────────────────────────────────────────────────

    def _start_anim(self):
        self._anim_idx = 0
        self._test_status_lbl.configure(
            text=self._ANIM_FRAMES[0], text_color=("gray50", "gray60"))
        self._tick_anim()

    def _tick_anim(self):
        self._anim_idx += 1
        try:
            self._test_status_lbl.configure(
                text=self._ANIM_FRAMES[self._anim_idx % len(self._ANIM_FRAMES)],
                text_color=("gray50", "gray60"))
            self._anim_id = self.after(380, self._tick_anim)
        except Exception:
            self._anim_id = None

    def _stop_anim(self):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

    # ── блок ошибки ───────────────────────────────────────────────────────────

    def _show_error_box(self, text: str):
        self._test_error_box.configure(state="normal")
        self._test_error_box.delete("1.0", "end")
        self._test_error_box.insert("1.0", text)
        self._test_error_box.configure(state="disabled")
        self._test_error_box.grid()
        self._copy_error_btn.grid()
        self.update_idletasks()
        new_h = self.winfo_reqheight()
        if new_h > 50:
            self.geometry(f"{self.winfo_width()}x{new_h}")

    def _hide_error_box(self):
        was_shown = self._test_error_box.winfo_ismapped()
        if was_shown:
            self._test_error_box.grid_remove()
        if self._copy_error_btn.winfo_ismapped():
            self._copy_error_btn.grid_remove()
        if was_shown:
            self.update_idletasks()
            new_h = self.winfo_reqheight()
            if new_h > 50:
                self.geometry(f"{self.winfo_width()}x{new_h}")

    def _copy_error_text(self):
        try:
            text = self._test_error_box.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass

    # ── inline-валидация ─────────────────────────────────────────────────────

    def _validate_name_inline(self, event=None):
        if not self.name_entry.get().strip():
            self.name_entry.configure(border_color=("#EF4444", "#DC2626"))
            self._hint_name.configure(text="Обязательное поле")
            self._hint_name.grid()
        else:
            self.name_entry.configure(border_color=("gray70", "gray45"))
            self._hint_name.grid_remove()
        self._adjust_height()

    def _validate_port_inline(self, event=None):
        if self.db_type_combo.get().strip().lower() == "sqlite":
            return
        port_str = self.port_entry.get().strip()
        valid = False
        if port_str:
            try:
                valid = 1 <= int(port_str) <= 65535
            except ValueError:
                pass
        if not valid:
            self.port_entry.configure(border_color=("#EF4444", "#DC2626"))
            self._hint_port.configure(text="Порт: целое число от 1 до 65535")
            self._hint_port.grid()
        else:
            self.port_entry.configure(border_color=("gray70", "gray45"))
            self._hint_port.grid_remove()
        self._adjust_height()

    def _adjust_height(self):
        try:
            self.update_idletasks()
            new_h = self.winfo_reqheight()
            if new_h > 50:
                self.geometry(f"{self.winfo_width()}x{new_h}")
        except Exception:
            pass

    # ── прочие ───────────────────────────────────────────────────────────────

    def _on_ok(self):
        name = self.name_entry.get().strip()
        if not name:
            self._validate_name_inline()
            messagebox.showerror("Ошибка", "Введите имя подключения", parent=self)
            return

        db_type   = self.db_type_combo.get().strip().lower()
        host      = self.host_entry.get().strip()
        port_str  = self.port_entry.get().strip()
        db_name   = self.db_name_entry.get().strip()
        user      = self.user_entry.get().strip()
        password  = self.password_entry.get()
        charset   = self.charset_combo.get().strip()

        if db_type != "sqlite":
            self._validate_port_inline()
            port = self._validate_port(port_str)
            if port is None:
                return
        else:
            port = 0

        interval_str = self.interval_entry.get().strip()
        try:
            interval = int(interval_str) if interval_str else 0
            if interval < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Интервал — целое число ≥ 0", parent=self)
            return

        if _KEYRING_OK and password:
            try:
                _keyring.set_password(_KEYRING_SERVICE, name, password)
                password_in_keyring = True
                password = ""
            except Exception:
                password_in_keyring = False
        else:
            password_in_keyring = False

        config = {
            "database_type": db_type,
            "host":          host or "localhost",
            "port":          port,
            "database_name": db_name or name,
            "username":      user,
            "charset":       charset,
        }
        if password_in_keyring:
            config["password_in_keyring"] = True
        else:
            config["password"] = password

        self.result = (name, config, interval)
        self.destroy()

    def _on_cancel(self):
        self.destroy()

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
                self._settings_manager.set_setting("dialog_size_connection", [w, h])
        except Exception:
            pass

    # ── центрирование ─────────────────────────────────────────────────────────

    def _center(self):
        self.update_idletasks()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        saved  = (self._settings_manager.get_setting("dialog_size_connection")
                  if self._settings_manager else None)
        if saved and len(saved) == 2:
            w, h = saved
        else:
            w = self.winfo_reqwidth()
            h = self.winfo_reqheight()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.grab_set()
