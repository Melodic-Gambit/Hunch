"""Logs tab — mixin для MainWindow.

Содержит все методы вкладки «Логи».
Примешивается к MainWindow через множественное наследование:
    class MainWindow(LogsTabMixin, RemindersTabMixin, ConnectionsTabMixin, QueriesTabMixin, ctk.CTk): ...
"""
from __future__ import annotations

import datetime
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog

import dialogs as messagebox
from utils import setup_paste_bindings


class LogsTabMixin:
    """Методы вкладки «Логи».  Примешиваются к MainWindow."""

    # ── Логи ──────────────────────────────────────────────────────────────────

    def _get_logs_theme_colors(self) -> dict:
        if ctk.get_appearance_mode() == "Dark":
            return {"bg": "#2B2B2B", "fg": "lightgray",
                    "error_fg": "red", "info_fg": "lightgray", "other_fg": "cyan"}
        bg = self._get_theme_bg()
        return {"bg": bg, "fg": "#1a1a1a",
                "error_fg": "#cc0000", "info_fg": "#1a1a1a", "other_fg": "#0000AA"}

    def setup_logs_tab(self):
        self.frame_logs.grid_columnconfigure(0, weight=1)
        self.frame_logs.grid_rowconfigure(0, weight=1)

        logs_frame = ctk.CTkFrame(self.frame_logs, fg_color="transparent")
        logs_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(1, weight=1)

        # ── состояние фильтра и поиска ───────────────────────────────────────
        saved_levels = self.settings_manager.get_setting("log_filter_levels", {})
        self._log_filter_levels = {
            lvl: saved_levels.get(lvl, True)
            for lvl in ("INFO", "ERROR", "WARNING")
        }
        self._log_filter_btns: dict = {}
        self._log_search_var = tk.StringVar()
        self._log_search_var.trace_add("write", lambda *_: self._on_log_search_changed())

        # ── тулбар ──────────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(logs_frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, pady=(0, 6), sticky="ew")

        # левая сторона: действия
        ctk.CTkButton(toolbar, text="Очистить логи", command=self.clear_logs,
                      width=130, height=32,
                      fg_color=("#E53935", "#C62828"),
                      hover_color=("#C62828", "#B71C1C")).pack(side="left", padx=(0, 6))
        ctk.CTkButton(toolbar, text="Сохранить в файл", command=self.save_logs_to_file,
                      width=140, height=32).pack(side="left")

        # правая сторона: кнопки фильтра (правее всего → ERROR, WARNING, INFO)
        _LVL_COLORS = {
            "INFO":    ("#1F6AA5", "#144870"),
            "WARNING": ("#E67E22", "#b8641b"),
            "ERROR":   ("#E53935", "#C62828"),
        }
        _INACTIVE = ("gray55", "gray35")
        for lvl in ("ERROR", "WARNING", "INFO"):
            active = self._log_filter_levels[lvl]
            c = _LVL_COLORS[lvl] if active else _INACTIVE
            btn = ctk.CTkButton(
                toolbar, text=lvl, width=76, height=28,
                fg_color=c, hover_color=c,
                command=lambda l=lvl: self._toggle_log_level(l))
            btn.pack(side="right", padx=2)
            self._log_filter_btns[lvl] = btn

        ctk.CTkLabel(toolbar, text="Уровень:").pack(side="right", padx=(16, 4))

        # × — упакован до Entry (side="right"), поэтому на экране появляется справа от Entry
        self._log_clear_btn = ctk.CTkButton(
            toolbar, text="✕", width=24, height=28,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=self._clear_log_search)
        self._log_clear_btn.pack(side="right", padx=(0, 2))
        self._log_clear_btn.pack_forget()   # скрыт пока поле пустое

        ctk.CTkEntry(toolbar, textvariable=self._log_search_var,
                     placeholder_text="Поиск...",
                     width=190, height=28).pack(side="right", padx=(0, 0))

        ctk.CTkLabel(toolbar, text="🔍",
                     font=ctk.CTkFont(size=20)).pack(side="right", padx=(16, 6), pady=0, anchor="center")
        setup_paste_bindings(toolbar)

        _lc = self._get_logs_theme_colors()
        self.logs_textbox = tk.Text(
            logs_frame, font=("Consolas", 12),
            wrap="none", bg=_lc["bg"], fg=_lc["fg"],
            insertbackground="white", selectbackground="#4CAF50",
            cursor="arrow", bd=0, highlightthickness=0)
        self.logs_textbox.grid(row=1, column=0, sticky="nsew")

        # Только чтение: блокируем редактирование, разрешаем навигацию и Ctrl+C/A
        _NAV = frozenset(["Up", "Down", "Left", "Right", "Home", "End", "Prior", "Next",
                          "KP_Up", "KP_Down", "KP_Left", "KP_Right",
                          "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"])
        # Физические коды клавиш для nav-хоткеев (совпадают с _NAV_KEYCODE_MAP)
        _NAV_KC = {
            68: "📊 Приборная панель",
            76: "📋 Логи",
            75: "🔗 Подключения",
            81: "📝 Запросы",
            69: "⚙️ Настройки",
            78: "🔔 Уведомления",
            83: "🛠 Сервисы",
        }

        def _block_edit(e):
            if e.state & 4:   # Ctrl зажат
                ks = e.keysym.lower()
                kc = getattr(e, "keycode", -1)
                # Nav-хоткеи: перехватываем ДО class-binding Text-виджета
                nav_tab = _NAV_KC.get(kc)
                if nav_tab:
                    self._hamburger_select(nav_tab)
                    return "break"
                is_c = ks == "c" or (kc == 67 and ks not in ("c",))
                is_v = ks == "v" or (kc == 86 and ks not in ("v",))
                if is_c:
                    _copy()
                    return "break"
                if is_v:
                    return "break"  # блокируем Ctrl+V без копирования
                return None   # Ctrl+A и т.д. — стандартное поведение
            if e.keysym in _NAV:
                return None
            return "break"

        self.logs_textbox.bind("<Key>", _block_edit)

        # ── копирование: Ctrl+C и контекстное меню ──────────────────────────
        def _copy(e=None):
            try:
                self.logs_textbox.event_generate("<<Copy>>")
            except Exception:
                pass
            return "break"

        self.logs_textbox.bind("<Control-c>", _copy)
        self.logs_textbox.bind("<Control-C>", _copy)

        def _context_menu(event):
            has_sel = bool(self.logs_textbox.tag_ranges("sel"))
            menu = tk.Menu(self.logs_textbox, tearoff=0)
            menu.add_command(
                label="Копировать",
                state="normal" if has_sel else "disabled",
                command=_copy)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        self.logs_textbox.bind("<Button-3>", _context_menu)

        h_sb = ctk.CTkScrollbar(logs_frame, orientation="horizontal",
                                command=self.logs_textbox.xview)
        h_sb.grid(row=2, column=0, sticky="ew")
        self.logs_textbox.configure(xscrollcommand=h_sb.set)

        v_sb = ctk.CTkScrollbar(logs_frame, command=self.logs_textbox.yview)
        v_sb.grid(row=1, column=1, sticky="ns")
        self.logs_textbox.configure(yscrollcommand=v_sb.set)

        self._logs_shown = 0
        self.refresh_logs()
        self._poll_logs()

    def refresh_logs(self):
        self.logs_textbox.delete("1.0", "end")
        _lc = self._get_logs_theme_colors()
        self.logs_textbox.tag_configure("error", foreground=_lc["error_fg"])
        self.logs_textbox.tag_configure("info",  foreground=_lc["info_fg"])
        self.logs_textbox.tag_configure("other", foreground=_lc["other_fg"])
        filter_lvls = getattr(self, "_log_filter_levels",
                              {"INFO": True, "ERROR": True, "WARNING": True})
        term = getattr(self, "_log_search_var", None)
        term = term.get().strip().lower() if term else ""
        for entry in self.log_manager.get_logs():
            if not filter_lvls.get(entry["level"], True):
                continue
            if term:
                line = f"[{entry['timestamp']}] {entry['level']}: {entry['message']}"
                if term not in line.lower():
                    continue
            msg  = entry['message'].replace("\n", " ")
            text = f"[{entry['timestamp']}] {entry['level']}: {msg}\n"
            tag  = ("error" if entry["level"] == "ERROR"
                    else ("info" if entry["level"] == "INFO" else "other"))
            self.logs_textbox.insert("end", text, tag)
        self._logs_shown = len(self.log_manager.get_logs())
        self.logs_textbox.see("end")

    def _poll_logs(self):
        logs  = self.log_manager.get_logs()
        count = len(logs)
        if count > self._logs_shown:
            term = getattr(self, "_log_search_var", None)
            term = term.get().strip() if term else ""
            if term:
                self.refresh_logs()
            else:
                filter_lvls = getattr(self, "_log_filter_levels",
                                      {"INFO": True, "ERROR": True, "WARNING": True})
                added = 0
                for entry in logs[self._logs_shown:]:
                    if not filter_lvls.get(entry["level"], True):
                        continue
                    msg  = entry['message'].replace("\n", " ")
                    text = f"[{entry['timestamp']}] {entry['level']}: {msg}\n"
                    tag  = ("error" if entry["level"] == "ERROR"
                            else ("info" if entry["level"] == "INFO" else "other"))
                    self.logs_textbox.insert("end", text, tag)
                    added += 1
                self._logs_shown = count
                if added:
                    self.logs_textbox.see("end")
        self.after(500, self._poll_logs)


    def _on_log_search_changed(self):
        term = self._log_search_var.get()
        if hasattr(self, "_log_clear_btn"):
            if term:
                self._log_clear_btn.pack(side="right", padx=(0, 2))
            else:
                self._log_clear_btn.pack_forget()
        self.refresh_logs()

    def _clear_log_search(self):
        self._log_search_var.set("")

    def _apply_log_search(self):
        self.refresh_logs()

    def _toggle_log_level(self, level: str):
        self._log_filter_levels[level] = not self._log_filter_levels[level]
        active = self._log_filter_levels[level]
        _COLORS = {
            "INFO":    ("#1F6AA5", "#144870"),
            "WARNING": ("#E67E22", "#b8641b"),
            "ERROR":   ("#E53935", "#C62828"),
        }
        inactive = ("gray55", "gray35")
        btn = self._log_filter_btns[level]
        c = _COLORS[level] if active else inactive
        btn.configure(fg_color=c, hover_color=c)
        self.settings_manager.set_setting("log_filter_levels", dict(self._log_filter_levels))
        self.refresh_logs()

    def clear_logs(self):
        if messagebox.askyesno("Подтверждение", "Очистить все логи?"):
            self.log_manager.clear_logs()
            self.refresh_logs()
            self.log_manager.add_log("Логи очищены вручную")
            hours = self.settings_manager.get_setting("log_rotation_hours", 120)
            self._schedule_log_rotation(delay_ms=hours * 60 * 60 * 1000)

    def save_logs_to_file(self):
        default = f"sup.syst_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Сохранить логи",
            initialfile=default,
            defaultextension=".txt",
            filetypes=[("Текстовый файл", "*.txt"), ("Все файлы", "*.*")],
        )
        if not path:
            return
        self.log_manager.save_logs_to_file(path)
        messagebox.showinfo("Успех", f"Логи сохранены: {path}")
        self.log_manager.add_log(f"Логи сохранены: {path}")

    # ── Ротация логов ─────────────────────────────────────────────────────────

    def _run_log_rotation(self, startup: bool = False):
        """Удаляет записи старше настроенного порога и планирует следующую ротацию."""
        hours = self.settings_manager.get_setting("log_rotation_hours", 120)
        removed = self.log_manager.rotate_old_logs(hours)
        if removed > 0:
            src = "при запуске" if startup else "по расписанию"
            self.log_manager.add_log(
                f"Ротация логов ({src}): удалено {removed} записей старше {hours} ч.")
            self._play_sound("notification_delet_log.wav", "rotation_done")
            if not startup:
                self._add_notification(
                    "Ротация логов",
                    message=f"Выполнена ротация: удалено {removed} записей старше {hours} ч.",
                    system=True,
                )
        # Ротация по размеру файла
        max_mb = self.settings_manager.get_setting("log_rotation_max_mb", 100)
        removed_size = self.log_manager.rotate_by_size(max_mb)
        if removed_size > 0:
            self.log_manager.add_log(
                f"Ротация логов по размеру: удалено {removed_size} старых записей "
                f"(лимит {max_mb} МБ).")
            if not startup:
                self._add_notification(
                    "Ротация логов",
                    message=f"Размер превысил {max_mb} МБ: удалено {removed_size} записей.",
                    system=True,
                )
        self._schedule_log_rotation()

    def _schedule_log_rotation(self, delay_ms: int = None):
        """Планирует следующую ротацию.

        Если delay_ms не задан — на ближайшее 18:00.
        При вызове отменяет предыдущий таймер.
        """
        if self._rotation_after_id is not None:
            try:
                self.after_cancel(self._rotation_after_id)
            except Exception:
                pass
        if delay_ms is None:
            now    = datetime.datetime.now()
            target = now.replace(hour=18, minute=0, second=0, microsecond=0)
            if now >= target:
                target += datetime.timedelta(days=1)
            delay_ms = int((target - now).total_seconds() * 1000)
        self._rotation_after_id = self.after(delay_ms, self._run_log_rotation)

    def _check_rotation_warning(self):
        """Периодически (раз в 60 с) проверяет приближение ротации и добавляет WARNING."""
        self._rotation_warn_after_id = None

        max_age = self.settings_manager.get_setting("log_rotation_hours", 120)

        if max_age <= 8:
            warn_before_h = 0.5
            warn_text = "Через 30 минут будет произведена ротация логов"
        elif max_age <= 48:
            warn_before_h = 1.0
            warn_text = "Через 1 час будет произведена ротация логов"
        elif max_age <= 100:
            warn_before_h = 2.0
            warn_text = "Через 2 часа будет произведена ротация логов"
        else:
            warn_before_h = 3.0
            warn_text = "Через 3 часа будет произведена ротация логов"

        logs = self.log_manager.logs
        if logs:
            try:
                oldest_ts = min(
                    datetime.datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S")
                    for e in logs
                )
                age_h       = (datetime.datetime.now() - oldest_ts).total_seconds() / 3600
                remaining_h = max_age - age_h

                if 0 < remaining_h <= warn_before_h:
                    cutoff_dt = (datetime.datetime.now()
                                 - datetime.timedelta(hours=warn_before_h * 2))
                    already = any(
                        e.get("level") == "WARNING"
                        and "ротация логов" in e.get("message", "").lower()
                        and datetime.datetime.strptime(
                            e["timestamp"], "%Y-%m-%d %H:%M:%S") > cutoff_dt
                        for e in logs
                    )
                    if not already:
                        self.log_manager.add_log(warn_text, "WARNING")
                        self._play_sound("notification_delet_log.wav", "rotation_warning")
                        self._add_notification(
                            "Ротация логов",
                            message=warn_text,
                            system=True,
                        )
                        if hasattr(self, "logs_textbox"):
                            self.refresh_logs()
            except Exception:
                pass

        self._rotation_warn_after_id = self.after(60_000, self._check_rotation_warning)

