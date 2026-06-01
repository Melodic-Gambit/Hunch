"""Reminders tab — mixin для MainWindow.

Содержит все методы вкладки «Напоминания» и планировщика напоминаний.
Примешивается к MainWindow через множественное наследование:
    class MainWindow(RemindersTabMixin, ctk.CTk): ...
"""
from __future__ import annotations

import json
import datetime
import tkinter as tk
import customtkinter as ctk

try:
    from winotify import Notification as _WinNotification
    _WINOTIFY_OK = True
except Exception:
    _WINOTIFY_OK = False


class RemindersTabMixin:
    """Методы вкладки «Напоминания».  Примешиваются к MainWindow."""

    # ── Напоминания ───────────────────────────────────────────────────────────

    def setup_reminders_tab(self):
        f = self.frame_reminders
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)

        # Заголовок + кнопка «Добавить»
        hdr = ctk.CTkFrame(f, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Напоминания",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="+ Добавить", width=110, height=28,
                      command=lambda: self._open_add_reminder_dialog()
                      ).grid(row=0, column=1, padx=(8, 0))

        # Прокручиваемый список
        self._rem_scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        self._rem_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._rem_scroll.grid_columnconfigure(0, weight=1)

        self._rem_empty_lbl = ctk.CTkLabel(
            self._rem_scroll, text="Нет напоминаний",
            font=ctk.CTkFont(size=13),
            text_color=("gray55", "gray55"))

        self._refresh_reminders_list()

    def _refresh_reminders_list(self):
        if not hasattr(self, "_rem_scroll"):
            return
        for w in self._rem_scroll.winfo_children():
            w.destroy()

        items = self.reminders_manager.list_all()
        if not items:
            self._rem_empty_lbl = ctk.CTkLabel(
                self._rem_scroll, text="Нет напоминаний",
                font=ctk.CTkFont(size=13),
                text_color=("gray55", "gray55"))
            self._rem_empty_lbl.grid(row=0, column=0, pady=40)
            return

        for idx, r in enumerate(items):
            enabled = bool(r["enabled"])
            card = ctk.CTkFrame(self._rem_scroll,
                                corner_radius=8,
                                fg_color=("gray88", "gray22"))
            card.grid(row=idx, column=0, sticky="ew", padx=4, pady=(0, 4))
            card.grid_columnconfigure(1, weight=1)

            # Тип-иконка
            if r["type"] == "once":
                icon = "📅"
            elif r["type"] == "daily":
                icon = "🔁"
            else:
                icon = "🗓"
            ctk.CTkLabel(card, text=icon,
                         font=ctk.CTkFont(size=16)).grid(
                row=0, column=0, rowspan=2, padx=(10, 6), pady=6)

            # Комментарий
            color = ("gray10", "gray90") if enabled else ("gray55", "gray55")
            ctk.CTkLabel(card, text=r["comment"], anchor="w",
                         font=ctk.CTkFont(size=13),
                         text_color=color).grid(
                row=0, column=1, sticky="ew", padx=(0, 8), pady=(6, 0))

            # Время
            if r["type"] == "once":
                time_txt = r["once_dt"] or "—"
            elif r["type"] == "scheduled":
                try:
                    dts = json.loads(r.get("schedule_dts") or "[]")
                except Exception:
                    dts = []
                if dts:
                    time_txt = "По графику: " + ", ".join(dts)
                else:
                    time_txt = "По графику: —"
            else:
                time_txt = f'Ежедневно в {r["daily_hm"]}' if r["daily_hm"] else "—"
            if not enabled:
                time_txt += "  ✓ выполнено"
            ctk.CTkLabel(card, text=time_txt, anchor="w",
                         font=ctk.CTkFont(size=11),
                         text_color=("gray50", "gray55")).grid(
                row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))

            # Кнопки действий
            _rid = r["id"]
            _rdata = dict(r)
            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.grid(row=0, column=2, rowspan=2, padx=(0, 6), pady=6)
            ctk.CTkButton(btn_frame, text="✏", width=28, height=28,
                          fg_color="transparent",
                          hover_color=("gray70", "gray35"),
                          text_color=("gray40", "gray60"),
                          command=lambda d=_rdata: self._open_add_reminder_dialog(edit_data=d)
                          ).grid(row=0, column=0, padx=(0, 2))
            ctk.CTkButton(btn_frame, text="✕", width=28, height=28,
                          fg_color="transparent",
                          hover_color=("gray70", "gray35"),
                          text_color=("gray40", "gray60"),
                          command=lambda i=_rid: self._delete_reminder(i)
                          ).grid(row=0, column=1)

    def _delete_reminder(self, reminder_id: int):
        self.reminders_manager.delete(reminder_id)
        self._refresh_reminders_list()

    def _open_reminder_for_row(self, prefill_text: str):
        self._open_add_reminder_dialog(prefill_text=prefill_text)

    def _open_add_reminder_dialog(self, prefill_text: str = "", edit_data: dict | None = None):
        dlg = ctk.CTkToplevel(self)
        dlg.withdraw()
        dlg.title("Редактировать напоминание" if edit_data else "Добавить напоминание")
        dlg.resizable(False, False)
        dlg.transient(self)

        def _on_close():
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", _on_close)

        dlg.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dlg,
                     text="Редактировать напоминание" if edit_data else "Добавить напоминание",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, padx=20, pady=(16, 8), sticky="w")

        # Текст напоминания
        ctk.CTkLabel(dlg, text="Текст напоминания:", anchor="w"
                     ).grid(row=1, column=0, padx=20, pady=(0, 2), sticky="w")
        comment_entry = ctk.CTkEntry(dlg, width=340, placeholder_text="Введите текст…")
        comment_entry.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        if edit_data:
            comment_entry.insert(0, edit_data.get("comment", ""))
        elif prefill_text:
            comment_entry.insert(0, prefill_text)

        # Тип: однократно / ежедневно / по графику
        type_var = tk.StringVar(value=edit_data["type"] if edit_data else "once")
        type_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        type_frame.grid(row=3, column=0, padx=20, pady=(0, 6), sticky="w")
        ctk.CTkRadioButton(type_frame, text="Однократно", variable=type_var,
                           value="once").grid(row=0, column=0, padx=(0, 16))
        ctk.CTkRadioButton(type_frame, text="Ежедневно", variable=type_var,
                           value="daily").grid(row=0, column=1, padx=(0, 16))
        ctk.CTkRadioButton(type_frame, text="По графику", variable=type_var,
                           value="scheduled").grid(row=0, column=2)

        # Дата+время (для однократного)
        once_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        once_frame.grid(row=4, column=0, padx=20, pady=(0, 4), sticky="w")
        ctk.CTkLabel(once_frame, text="Дата и время (ГГГГ-ММ-ДД ЧЧ:ММ):",
                     anchor="w").grid(row=0, column=0, sticky="w")
        once_entry = ctk.CTkEntry(once_frame, width=200,
                                  placeholder_text="2026-12-31 09:00")
        once_entry.grid(row=1, column=0, sticky="w")

        # Время (для ежедневного)
        daily_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        daily_frame.grid(row=5, column=0, padx=20, pady=(0, 4), sticky="w")
        ctk.CTkLabel(daily_frame, text="Время (ЧЧ:ММ):",
                     anchor="w").grid(row=0, column=0, sticky="w")
        daily_entry = ctk.CTkEntry(daily_frame, width=100, placeholder_text="09:00")
        daily_entry.grid(row=1, column=0, sticky="w")

        # До 3 дат+времени (для "По графику")
        sched_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        sched_frame.grid(row=6, column=0, padx=20, pady=(0, 4), sticky="w")
        ctk.CTkLabel(sched_frame, text="Дата и время (ГГГГ-ММ-ДД ЧЧ:ММ):",
                     anchor="w").grid(row=0, column=0, columnspan=2, sticky="w")
        _sched_ph = "2026-12-31 09:00"
        sched_entries = []
        for _si in range(3):
            _lbl = ctk.CTkLabel(sched_frame,
                                text=f"{_si + 1}.",
                                width=18, anchor="e",
                                font=ctk.CTkFont(size=12))
            _lbl.grid(row=_si + 1, column=0, pady=(4, 0), sticky="e")
            _e = ctk.CTkEntry(sched_frame, width=200, placeholder_text=_sched_ph)
            _e.grid(row=_si + 1, column=1, padx=(6, 0), pady=(4, 0), sticky="w")
            sched_entries.append(_e)

        # Предзаполнение при редактировании
        if edit_data:
            if edit_data.get("once_dt"):
                once_entry.insert(0, edit_data["once_dt"])
            if edit_data.get("daily_hm"):
                daily_entry.insert(0, edit_data["daily_hm"])
            if edit_data.get("schedule_dts"):
                try:
                    _dts = json.loads(edit_data["schedule_dts"])
                except Exception:
                    _dts = []
                for _si, _dt in enumerate(_dts[:3]):
                    sched_entries[_si].insert(0, _dt)

        error_lbl = ctk.CTkLabel(dlg, text="", text_color=("#DC2626", "#F87171"),
                                 font=ctk.CTkFont(size=11), anchor="w")
        error_lbl.grid(row=7, column=0, padx=20, pady=(0, 4), sticky="w")

        def _toggle_type(*_):
            t = type_var.get()
            once_frame.grid_remove()
            daily_frame.grid_remove()
            sched_frame.grid_remove()
            if t == "once":
                once_frame.grid()
            elif t == "daily":
                daily_frame.grid()
            else:
                sched_frame.grid()

        type_var.trace_add("write", _toggle_type)
        _toggle_type()

        def _save():
            comment = comment_entry.get().strip()
            if not comment:
                error_lbl.configure(text="Введите текст напоминания.")
                return
            rtype = type_var.get()
            if rtype == "once":
                val = once_entry.get().strip()
                if not val:
                    error_lbl.configure(text="Укажите дату и время.")
                    return
                try:
                    dt = datetime.datetime.strptime(val, "%Y-%m-%d %H:%M")
                except ValueError:
                    error_lbl.configure(text="Формат: ГГГГ-ММ-ДД ЧЧ:ММ")
                    return
                if dt < datetime.datetime.now():
                    error_lbl.configure(text=f"Дата «{val}» уже в прошлом.")
                    return
                try:
                    if edit_data:
                        self.reminders_manager.update(
                            edit_data["id"], comment, "once", once_dt=val, reset_state=True)
                    else:
                        self.reminders_manager.add(comment, "once", once_dt=val)
                except Exception as e:
                    error_lbl.configure(text=f"Ошибка сохранения: {e}")
                    return
            elif rtype == "daily":
                val = daily_entry.get().strip()
                if not val:
                    error_lbl.configure(text="Укажите время.")
                    return
                try:
                    datetime.datetime.strptime(val, "%H:%M")
                except ValueError:
                    error_lbl.configure(text="Формат времени: ЧЧ:ММ")
                    return
                try:
                    if edit_data:
                        _reset = (edit_data.get("daily_hm") != val) or (not edit_data.get("enabled"))
                        self.reminders_manager.update(
                            edit_data["id"], comment, "daily", daily_hm=val, reset_state=_reset)
                    else:
                        self.reminders_manager.add(comment, "daily", daily_hm=val)
                except Exception as e:
                    error_lbl.configure(text=f"Ошибка сохранения: {e}")
                    return
            else:
                vals = []
                for _e in sched_entries:
                    v = _e.get().strip()
                    if not v:
                        continue
                    try:
                        dt = datetime.datetime.strptime(v, "%Y-%m-%d %H:%M")
                    except ValueError:
                        error_lbl.configure(
                            text=f"Неверный формат «{v}». Нужно: ГГГГ-ММ-ДД ЧЧ:ММ"
                        )
                        return
                    if dt < datetime.datetime.now():
                        error_lbl.configure(text=f"Дата «{v}» уже в прошлом.")
                        return
                    vals.append(v)
                if not vals:
                    error_lbl.configure(text="Укажите хотя бы одну дату и время.")
                    return
                try:
                    if edit_data:
                        try:
                            _old_dts = set(json.loads(edit_data.get("schedule_dts") or "[]"))
                        except Exception:
                            _old_dts = set()
                        _reset = (set(vals) != _old_dts) or (not edit_data.get("enabled"))
                        self.reminders_manager.update(
                            edit_data["id"], comment, "scheduled",
                            schedule_dts=json.dumps(vals),
                            reset_state=_reset,
                        )
                    else:
                        self.reminders_manager.add(
                            comment, "scheduled",
                            schedule_dts=json.dumps(vals),
                        )
                except Exception as e:
                    error_lbl.configure(text=f"Ошибка сохранения: {e}")
                    return
            self._refresh_reminders_list()
            _on_close()

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.grid(row=8, column=0, pady=(4, 16))
        ctk.CTkButton(btn_row, text="Сохранить", width=110, command=_save
                      ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(btn_row, text="Отмена", width=80,
                      fg_color=("gray60", "gray40"),
                      hover_color=("gray50", "gray30"),
                      command=_on_close).grid(row=0, column=1)

        dlg.bind("<Return>", lambda _: _save())
        dlg.bind("<Escape>", lambda _: _on_close())

        dlg.update_idletasks()
        pw = self.winfo_width()
        ph = self.winfo_height()
        w  = dlg.winfo_reqwidth()
        h  = dlg.winfo_reqheight()
        dlg.geometry(
            f"+{self.winfo_rootx() + (pw - w) // 2}"
            f"+{self.winfo_rooty() + (ph - h) // 2}"
        )
        dlg.deiconify()

        def _safe_grab():
            try:
                dlg.grab_set()
            except Exception:
                pass

        dlg.after(20, _safe_grab)
        dlg.lift()

    # ── Шедулер напоминаний ───────────────────────────────────────────────────

    def _start_reminder_check(self):
        if self._reminder_check_after_id:
            try:
                self.after_cancel(self._reminder_check_after_id)
            except Exception:
                pass
        self._check_reminders()

    def _check_reminders(self):
        try:
            due = self.reminders_manager.get_due()
        except Exception:
            due = []
        for r in due:
            try:
                self.reminders_manager.mark_fired(r["id"])
                self._fire_reminder(r["comment"])
            except Exception:
                pass
        self._reminder_check_after_id = self.after(30_000, self._check_reminders)

    def _reposition_toasts(self):
        try:
            margin     = 12
            title_bar  = 30
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            y_bottom = sh - margin
            for t in list(self._active_toasts):
                try:
                    t.update_idletasks()
                    tw = t.winfo_reqwidth()
                    th = t.winfo_reqheight()
                    if th <= 1:
                        th = 120
                    total_h = th + title_bar
                    x = sw - tw - margin
                    t.geometry(f"+{x}+{y_bottom - total_h}")
                    y_bottom -= total_h + margin
                except Exception:
                    pass
        except Exception:
            pass

    def _fire_reminder(self, comment: str):
        notified = False
        if _WINOTIFY_OK:
            try:
                n = _WinNotification(
                    app_id="Hunch",
                    title="⏰ Напоминание",
                    msg=comment,
                    duration="short",
                )
                n.show()
                notified = True
            except Exception:
                pass
        if not notified:
            toast = ctk.CTkToplevel(self)
            toast.title("⏰ Напоминание")
            toast.resizable(False, False)
            toast.attributes("-topmost", True)
            toast.withdraw()

            ctk.CTkLabel(
                toast, text="⏰ Напоминание",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(padx=16, pady=(14, 4))
            ctk.CTkLabel(toast, text=comment, wraplength=280).pack(
                padx=16, pady=(0, 8)
            )

            self._active_toasts.append(toast)

            def _close(t=toast):
                try:
                    self._active_toasts.remove(t)
                except ValueError:
                    pass
                try:
                    t.destroy()
                except Exception:
                    pass
                self._reposition_toasts()

            ctk.CTkButton(
                toast, text="Закрыть", width=80, command=_close
            ).pack(pady=(0, 12))

            def _place(t=toast, attempt=0):
                try:
                    t.update_idletasks()
                    if t.winfo_reqheight() <= 1 and attempt < 5:
                        t.after(30, lambda: _place(t, attempt + 1))
                        return
                    self._reposition_toasts()
                    t.deiconify()
                except Exception:
                    pass

            toast.after(50, _place)
            toast.after(5000, _close)
