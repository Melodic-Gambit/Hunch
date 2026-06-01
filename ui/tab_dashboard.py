from __future__ import annotations

import os
import sys
import datetime
import time
import threading
from typing import Optional
import tkinter as tk
import customtkinter as ctk

import theme_colors
from widgets.tooltip import _Tooltip
from widgets.dashboard_layout_dialog import DASHBOARD_TEMPLATES


class DashboardTabMixin:
    """Methods for the "Dashboard" tab: status bar, toasts, panels, drag-and-drop.
    Mixed into
    class MainWindow(LogsTabMixin, RemindersTabMixin, ConnectionsTabMixin,
                     QueriesTabMixin, ServicesTabMixin, SettingsTabMixin, DashboardTabMixin, ctk.CTk).
    """

    # ── Строка состояния Приборной панели ────────────────────────────────────

    def _build_dash_status_bar(self):
        from gui import _get_bell_ctk_image, _get_time_quarte_ctk_image, _get_play_ctk_image, _get_time_ctk_image
        bar = self.dash_status_bar
        self._notification_has_badge = False

        # ── значок оповещений (col 0) ─────────────────────────────────────────
        bell_container = ctk.CTkFrame(bar, fg_color="transparent", width=40, height=33)
        bell_container.grid(row=0, column=0, padx=(4, 10))
        bell_container.grid_propagate(False)
        self._bell_container = bell_container

        bell_img = _get_bell_ctk_image(badge=False, size=29)
        self.notification_bell_lbl = ctk.CTkLabel(
            bell_container, image=bell_img, text="" if bell_img else "🔔",
            cursor="hand2", corner_radius=4)
        self.notification_bell_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.notification_bell_lbl.bind("<Button-1>", lambda e: self._go_to_notifications())
        self.notification_bell_lbl.bind(
            "<Enter>", lambda e: self.notification_bell_lbl.configure(
                fg_color=("gray78", "gray32")))
        self.notification_bell_lbl.bind(
            "<Leave>", lambda e: self.notification_bell_lbl.configure(
                fg_color="transparent"))
        _Tooltip(self.notification_bell_lbl, "Уведомления")

        self._notif_badge_lbl = ctk.CTkLabel(
            bell_container, text="",
            font=ctk.CTkFont(size=8, weight="bold"),
            text_color="white",
            fg_color="#EF4444",
            corner_radius=4,
            width=15, height=14)
        self._notif_badge_lbl.place(x=22, y=0)
        self._notif_badge_lbl.place_forget()

        # ── секция «Время обновления» (col 1-4) ──────────────────────────────
        tq_img = _get_time_quarte_ctk_image(16)
        tq_lbl = ctk.CTkLabel(bar, image=tq_img, text="" if tq_img else "↺", width=20)
        tq_lbl.grid(row=0, column=1, padx=(0, 2))
        _Tooltip(tq_lbl, "Время последнего обновления БД")

        ctk.CTkLabel(bar, text="Время обновления", anchor="w",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=2, padx=(0, 4))

        self.refresh_progress = ctk.CTkProgressBar(bar, width=90, height=8)
        self.refresh_progress.set(0.0)
        self.refresh_progress.grid(row=0, column=3, padx=(0, 4))

        self.refresh_last_time_lbl = ctk.CTkLabel(bar, text="—", anchor="w", width=58,
                                                   font=ctk.CTkFont(size=12))
        self.refresh_last_time_lbl.grid(row=0, column=4, padx=(0, 8))

        # ── кнопка «Обновить все» (col 5) — между «обновлением» и «часами» ───
        _play_img = _get_play_ctk_image(24)
        self._refresh_all_btn = ctk.CTkButton(
            bar, image=_play_img, text="", width=40, height=40,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=self._force_refresh_all)
        self._refresh_all_btn.grid(row=0, column=5, padx=(0, 8))
        _Tooltip(self._refresh_all_btn, "Обновить все панели")

        # ── секция «Текущее время» (col 6-7) ─────────────────────────────────
        t_img = _get_time_ctk_image(16)
        t_lbl = ctk.CTkLabel(bar, image=t_img, text="" if t_img else "🕐", width=20)
        t_lbl.grid(row=0, column=6, padx=(0, 2))
        _Tooltip(t_lbl, "Текущее время")

        self.clock_label = ctk.CTkLabel(bar, text="00:00", anchor="w",
                                        width=44, font=ctk.CTkFont(size=12))
        self.clock_label.grid(row=0, column=7)

        # ── header-toast (place()-оверлей, не влияет на grid) ────────────────
        self._header_toast_frame    = None
        self._header_toast_notif_id = None
        self._header_toast_after_id = None

        self._status_clock_after_id = None
        self._refresh_bar_after_id  = None
        self._update_status_clock()
        self._update_refresh_bar()

    def set_notification_badge(self, state: bool):
        """Включает/выключает бейдж с числом непрочитанных уведомлений."""
        from gui import _get_bell_ctk_image
        self._notification_has_badge = state
        img = _get_bell_ctk_image(badge=state, size=29)
        if img:
            self.notification_bell_lbl.configure(image=img)
        else:
            self.notification_bell_lbl.configure(text="🔔●" if state else "🔔")
        if state and hasattr(self, "_notif_badge_lbl"):
            count = sum(1 for n in self._notifications if not n.get("read"))
            if count > 0:
                self._notif_badge_lbl.configure(
                    text=str(count) if count <= 99 else "99+")
                self._notif_badge_lbl.place(x=22, y=0)
                self._set_taskbar_badge(True)
                return
        if hasattr(self, "_notif_badge_lbl"):
            self._notif_badge_lbl.place_forget()
        self._set_taskbar_badge(state)

    def _set_taskbar_badge(self, has_unread: bool):
        """Показывает/убирает красный оверлей на иконке программы в панели задач Windows."""
        from gui import _make_taskbar_badge_hicon, _taskbar_set_overlay
        if sys.platform != "win32":
            return
        try:
            if not hasattr(self, "_badge_hicon"):
                self._badge_hicon = _make_taskbar_badge_hicon()
            hwnd  = self.winfo_id()
            hicon = self._badge_hicon if has_unread else 0
            desc  = "Непрочитанные уведомления" if has_unread else ""
            _taskbar_set_overlay(hwnd, hicon, desc)
        except Exception:
            pass

    # ── Toast-уведомления (inline в шапке) ───────────────────────────────────

    def _show_alert_toast(self, title: str, message: str, notif_id: int = None):
        """Показывает inline-тост в шапке программы слева от иконки колокола."""
        self.set_notification_badge(True)
        self._show_header_toast(title, message, notif_id)
        self._send_system_toast(title, message)

    def _send_system_toast(self, title: str, message: str):
        """Отправляет Windows-уведомление (toast) когда окно не в фокусе."""
        from gui import _WINOTIFY_OK
        if not _WINOTIFY_OK:
            return
        try:
            is_minimized = self.state() in ("iconic", "withdrawn")
            has_focus    = self.focus_get() is not None
            if not is_minimized and has_focus:
                return
            threading.Thread(
                target=self._bg_send_toast,
                args=(title, message[:250]),
                daemon=True
            ).start()
        except Exception:
            pass

    def _bg_send_toast(self, title: str, message: str):
        from gui import _WinNotification
        try:
            toast = _WinNotification(app_id="Hunch", title=title, msg=message, duration="short")
            toast.show()
        except Exception:
            pass

    def _show_header_toast(self, title: str, message: str = "", notif_id: int = None):
        dark   = ctk.get_appearance_mode() == "Dark"
        accent = theme_colors.accent()
        fg     = "#ffffff" if dark else "#1a1a1a"
        # совпадаем с цветом фона шапки (main window fg_color)
        try:
            bg = self._apply_appearance_mode(self.cget("fg_color"))
        except Exception:
            bg = "#2b2b2b" if dark else "#ebebeb"
        bar = self.top_bar

        # отменить предыдущий таймер
        if self._header_toast_after_id:
            try:
                self.after_cancel(self._header_toast_after_id)
            except Exception:
                pass
            self._header_toast_after_id = None

        # уничтожить старый фрейм
        if self._header_toast_frame is not None:
            try:
                self._header_toast_frame.destroy()
            except Exception:
                pass
            self._header_toast_frame = None

        self._header_toast_notif_id = notif_id

        bar.update_idletasks()
        bell_left  = self._bell_container.winfo_rootx()
        bar_left   = self.top_bar.winfo_rootx()
        bh         = self.top_bar.winfo_height()
        toast_h    = int(max(bh - 4, 28) * 1.15)
        toast_w    = 333
        right_edge = bell_left - bar_left - 4   # правый край тоста — 4px от колокола
        toast_x    = right_edge - toast_w        # финальная позиция (левый край)

        # Обрезаем длинный текст, чтобы поместился в одну строку
        display_msg = message
        if len(display_msg) > 60:
            display_msg = display_msg[:57] + "…"

        outer = tk.Frame(bar, background=accent, bd=0, highlightthickness=0)
        self._header_toast_frame = outer

        # Левая акцентная полоса + фон совпадает с шапкой
        inner = tk.Frame(outer, background=bg, bd=0)
        inner.pack(fill="both", expand=True, padx=(3, 0), pady=(0, 2))

        title_row = tk.Frame(inner, background=bg)
        title_row.pack(fill="x", padx=6, pady=(4, 0))

        title_lbl = tk.Label(
            title_row, text=title, background=bg, foreground=accent,
            font=("Segoe UI", 9, "bold"), anchor="w", cursor="hand2")
        title_lbl.pack(side="left", fill="x", expand=True)

        def on_click(e=None):
            self._hide_header_toast()
            if notif_id is not None:
                self._navigate_to_notif_highlight(notif_id)
            else:
                self._go_to_notifications()

        for w in (outer, inner, title_row, title_lbl):
            w.bind("<Button-1>", on_click)

        tk.Button(
            title_row, text="×", background=bg, foreground=fg,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            activebackground=accent, activeforeground="#ffffff",
            cursor="hand2", command=self._hide_header_toast,
        ).pack(side="right")

        if display_msg:
            msg_row = tk.Frame(inner, background=bg)
            msg_row.pack(fill="x", padx=6, pady=(1, 2))
            msg_lbl = tk.Label(
                msg_row, text=display_msg, background=bg, foreground=fg,
                font=("Segoe UI", 8), anchor="w", justify="left")
            msg_lbl.pack(side="left", fill="x", expand=True)
            msg_lbl.bind("<Button-1>", on_click)
            msg_row.bind("<Button-1>", on_click)

        pbar_c = accent
        _pw    = [toast_w]
        pbar   = tk.Canvas(inner, height=2, background=pbar_c, highlightthickness=0)
        pbar.pack(fill="x", padx=0, pady=(0, 0))

        # Начинаем с нулевой ширины у правого края (анимация появления справа налево)
        y_pos = max(2, (bh - toast_h) // 2)
        outer.place(x=right_edge, y=y_pos, width=0, height=toast_h)

        SLIDE_STEPS = 10
        SLIDE_MS    = 16
        STEPS       = 50
        STEP_MS     = 100

        def slide_in(step):
            try:
                if not outer.winfo_exists():
                    return
            except Exception:
                return
            t     = step / SLIDE_STEPS
            eased = 1 - (1 - t) ** 3
            cur_w = int(toast_w * eased)
            cur_x = right_edge - cur_w
            outer.place(x=cur_x, width=cur_w)
            if step < SLIDE_STEPS:
                self.after(SLIDE_MS, lambda: slide_in(step + 1))
            else:
                self._header_toast_after_id = self.after(150, lambda: countdown(STEPS))

        def countdown(step):
            try:
                if not outer.winfo_exists():
                    return
            except Exception:
                return
            if step <= 0:
                self._hide_header_toast()
                return
            try:
                cw = pbar.winfo_width()
                if cw > 1:
                    _pw[0] = cw
                fill_w = int(_pw[0] * step / STEPS)
                pbar.delete("all")
                pbar.create_rectangle(0, 0, fill_w, 2, fill=pbar_c, outline="")
                self._header_toast_after_id = self.after(
                    STEP_MS, lambda: countdown(step - 1))
            except Exception:
                pass

        self.after(10, lambda: slide_in(1))

    def _hide_header_toast(self):
        if self._header_toast_after_id:
            try:
                self.after_cancel(self._header_toast_after_id)
            except Exception:
                pass
            self._header_toast_after_id = None
        if self._header_toast_frame is not None:
            try:
                self._header_toast_frame.destroy()
            except Exception:
                pass
            self._header_toast_frame = None
        self._header_toast_notif_id = None

    def _navigate_to_notif_highlight(self, notif_id: int):
        """Переходит на вкладку Уведомления и мигает нужной строкой."""
        self._hamburger_select("🔔 Уведомления")
        # Устанавливаем ПОСЛЕ _hamburger_select: внутри него _mark_all_read() сбрасывает
        # _highlight_notif_id в None, поэтому нужно выставить значение уже после.
        self._highlight_notif_id = notif_id
        self.after(80, lambda: self._blink_notif_row(notif_id, 12))

    def _check_change_alert(self, query_file: str, new_rows: list, new_cols):
        """Сравнивает новый результат с кэшем; при изменении показывает toast."""
        meta = self._get_query_meta(query_file)
        if not meta.get("alert_on_change"):
            return
        with self._query_results_lock:
            old = self._query_results.get(query_file)
        if old is None:
            return
        new_rows_list = [list(r) for r in new_rows]
        if new_rows_list != old.get("rows", []) or \
                list(new_cols) != old.get("columns", []):
            debounce = self.settings_manager.get_setting("alert_debounce_secs", 10)
            now_mono = time.monotonic()
            key = (query_file, "change")
            if now_mono - self._alert_last_fired.get(key, 0) < debounce:
                return
            self._alert_last_fired[key] = now_mono
            name = self.data_manager.get_query_display_name(query_file)
            old_set = {tuple(r) for r in old.get("rows", [])}
            new_set = {tuple(r) for r in new_rows_list}
            n_added   = len(new_set - old_set)
            n_removed = len(old_set - new_set)
            nid = self._add_notification(name, message="", added=n_added, removed=n_removed)
            self._show_alert_toast("Результат изменился",
                                   f"Запрос «{name}» вернул новые данные",
                                   notif_id=nid)
            self._play_sound("notification_allert.wav", "change_alert")
            self._play_sound("notification_message.wav", "query_result_change")
            self._alert_history.append({
                "ts":         datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "query_name": name,
                "query_file": query_file,
                "type":       "Изменение",
                "detail":     f"+{n_added}, −{n_removed}",
            })
            self._save_alert_history()
            if getattr(self, "_alert_hist_visible", False):
                self._render_alert_history()

    def _check_threshold_alert(self, query_file: str, new_rows: list, new_cols):
        """Проверяет пороговое условие и показывает toast при его выполнении."""
        meta = self._get_query_meta(query_file)
        thr  = meta.get("alert_threshold")
        if not thr or not thr.get("enabled"):
            return
        col_idx = thr.get("column", 0)
        operator = thr.get("operator", ">")
        threshold = thr.get("value", 0)
        if not new_rows or col_idx >= len(new_rows[0]):
            return
        raw = new_rows[0][col_idx]
        try:
            val = float(str(raw))
        except (ValueError, TypeError):
            return
        ops = {
            ">":  val >  threshold,
            "<":  val <  threshold,
            ">=": val >= threshold,
            "<=": val <= threshold,
            "==": val == threshold,
            "!=": val != threshold,
        }
        if ops.get(operator, False):
            debounce = self.settings_manager.get_setting("alert_debounce_secs", 10)
            now_mono = time.monotonic()
            key = (query_file, "threshold")
            if now_mono - self._alert_last_fired.get(key, 0) < debounce:
                return
            self._alert_last_fired[key] = now_mono
            name     = self.data_manager.get_query_display_name(query_file)
            col_name = new_cols[col_idx] if col_idx < len(new_cols) else f"col{col_idx}"
            nid = self._add_notification(
                name,
                message=f"Пороговый алерт: {col_name} = {raw} {operator} {threshold}",
            )
            self._show_alert_toast("Пороговый алерт",
                                   f"«{name}»: {col_name} = {raw} {operator} {threshold}",
                                   notif_id=nid)
            self._play_sound("notification_allert.wav", "threshold_alert")
            self._alert_history.append({
                "ts":         datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "query_name": name,
                "query_file": query_file,
                "type":       "Порог",
                "detail":     f"{col_name} = {raw} {operator} {threshold}",
            })
            self._save_alert_history()
            if getattr(self, "_alert_hist_visible", False):
                self._render_alert_history()

    def _on_panel_signal_fired(self, panel: "DashboardPanel",
                               col_name: str, sig_text: str):
        """Вызывается когда сигнал впервые срабатывает в панели."""
        query_name = panel.get_query_name() or f"Панель {panel.panel_id}"
        ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        message = f"{sig_text} - сработал сигнал {ts}"
        now_mono = time.monotonic()
        if now_mono - self._signal_last_played.get(query_name, 0) >= 10:
            self._signal_last_played[query_name] = now_mono
            self._play_sound("notification_signal.wav", "signal")
        nid = self._add_notification(query_name, message=message)
        self._show_alert_toast("Сигнал", f"«{query_name}»: {sig_text}", notif_id=nid)

    def _update_status_clock(self):
        now = datetime.datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M"))

        # Обновляем индикатор обратного отсчёта на каждой панели
        for panel in getattr(self, "dash_panels", []):
            qn = panel.get_query_name()
            if not qn:
                panel.set_next_refresh_secs(None)
                continue
            pid    = id(panel)
            cached = self._panel_qf_cache.get(pid)
            if cached is None or cached[0] != qn:
                qf = self._find_query_file(qn)
                self._panel_qf_cache[pid] = (qn, qf)
            else:
                qf = cached[1]
            if not qf or qf not in self._query_scheduled_at:
                panel.set_next_refresh_secs(None)
                continue
            iv_min = self._query_intervals_cache.get(qf, 0)
            if iv_min <= 0:
                panel.set_next_refresh_secs(None)
                continue
            elapsed   = (now - self._query_scheduled_at[qf]).total_seconds()
            remaining = iv_min * 60 - elapsed
            panel.set_next_refresh_secs(max(0.0, remaining))

        self._status_clock_after_id = self.after(1000, self._update_status_clock)

    def _update_refresh_bar(self):
        progress, last_time = self._get_fastest_conn_progress()
        self.refresh_progress.set(progress)
        self.refresh_last_time_lbl.configure(text=last_time)
        self._refresh_bar_after_id = self.after(1000, self._update_refresh_bar)

    def _get_fastest_conn_progress(self) -> tuple:
        """Возвращает (прогресс 0–1, строка оставшегося времени) для
        самого быстрого подключения с ненулевым интервалом."""
        now  = datetime.datetime.now()
        best = None  # (interval_min, conn_file)

        cfg_dir = self.data_manager.config_dir
        if os.path.exists(cfg_dir):
            for f in os.listdir(cfg_dir):
                if not f.endswith(".json"):
                    continue
                iv = self._get_conn_meta(f).get("update_interval", 0)
                if iv > 0 and (best is None or iv < best[0]):
                    best = (iv, f)

        if best is None:
            return 0.0, "—"

        interval_min, conn_file = best
        total_secs = interval_min * 60
        last = self._conn_last_refresh.get(conn_file)

        if last is None:
            return 1.0, "—"

        elapsed   = (now - last).total_seconds()
        progress  = min(1.0, elapsed / total_secs)   # 0 → только обновилось, 1 → пора снова
        return progress, last.strftime("%H:%M:%S")

    # ── Приборная панель ──────────────────────────────────────────────────────

    def setup_dashboard_tab(self):
        self.frame_dashboard.grid_columnconfigure(0, weight=1)
        self.frame_dashboard.grid_rowconfigure(0, weight=1)
        self._pinned_sash_snapshot: dict = {}
        self._paned_windows:        dict = {}
        saved = self.settings_manager.get_setting("dashboard", {})
        count = saved.get("panel_count", 3)
        self._dashboard_panel_count = max(1, min(6, count))
        self._build_dashboard_panes(self._dashboard_panel_count)
        self.after(200, lambda: self._restore_dashboard_state(saved))

    def _build_dashboard_panes(self, count: int, template: str = None):
        """Создаёт PanedWindow и панели под count фреймов по выбранному шаблону."""
        from gui import DashboardPanel
        bg = self._get_theme_bg()
        pw_kw = dict(bg=bg, sashwidth=6, sashrelief="flat", sashpad=0, handlesize=0)

        if template is None:
            template = self.settings_manager.get_setting(
                "dashboard", {}).get("template", "auto")
        _valid = {t[0] for t in DASHBOARD_TEMPLATES}
        if template not in _valid:
            template = "auto"
        self._current_template = template

        self.dash_panels: list[DashboardPanel] = []
        self._paned_windows: dict = {}
        query_names = self._get_query_names()
        try:
            win_color = self.cget("fg_color")
        except Exception:
            win_color = ("gray86", "gray17")

        def _wire(panel: DashboardPanel):
            panel.set_queries(query_names)
            panel.run_btn.configure(command=lambda p=panel: self._run_panel_query(p))
            panel.query_combo.configure(
                command=lambda v, p=panel: self._run_panel_query(p))
            panel.on_signal_fired = (
                lambda cn, st, p=panel: self._on_panel_signal_fired(p, cn, st))
            panel.on_history_click = (
                lambda p, _self=self: _self._show_panel_history(p))
            panel.bind_drag(
                lambda e, p=panel: self._drag_start(e, p),
                self._drag_motion,
                lambda e, p=panel: self._drag_end(e, p),
            )

        def _add(pw, idx):
            p = DashboardPanel(pw, panel_id=idx + 1,
                               on_pin_changed=self._on_panel_pin_changed,
                               fg_color=win_color)
            pw.add(p, stretch="always", minsize=80)
            self.dash_panels.append(p)
            _wire(p)
            return p

        if template == "col":
            # ── один столбец ──────────────────────────────────────────────────
            pw = tk.PanedWindow(self.frame_dashboard, orient="vertical", **pw_kw)
            pw.grid(row=0, column=0, sticky="nsew")
            self.h_paned = pw
            self._paned_windows["main"] = pw
            for i in range(count):
                _add(pw, i)

        elif template == "row":
            # ── одна строка ───────────────────────────────────────────────────
            pw = tk.PanedWindow(self.frame_dashboard, orient="horizontal", **pw_kw)
            pw.grid(row=0, column=0, sticky="nsew")
            self.h_paned = pw
            self._paned_windows["main"] = pw
            for i in range(count):
                _add(pw, i)

        elif template == "1+2" and count >= 2:
            # ── широкий сверху, N снизу ───────────────────────────────────────
            outer = tk.PanedWindow(self.frame_dashboard, orient="vertical", **pw_kw)
            outer.grid(row=0, column=0, sticky="nsew")
            inner = tk.PanedWindow(outer, orient="horizontal", **pw_kw)
            self.h_paned = outer
            self._paned_windows.update(outer=outer, inner=inner)
            _add(outer, 0)                          # панель 0 в верхний слот outer
            outer.add(inner, stretch="always", minsize=80)
            for i in range(1, count):               # панели 1..N-1 в inner
                _add(inner, i)

        elif template == "2+1" and count >= 2:
            # ── N сверху, широкий снизу ───────────────────────────────────────
            outer = tk.PanedWindow(self.frame_dashboard, orient="vertical", **pw_kw)
            outer.grid(row=0, column=0, sticky="nsew")
            inner = tk.PanedWindow(outer, orient="horizontal", **pw_kw)
            self.h_paned = outer
            self._paned_windows.update(outer=outer, inner=inner)
            outer.add(inner, stretch="always", minsize=80)
            for i in range(count - 1):              # панели 0..N-2 в inner
                _add(inner, i)
            _add(outer, count - 1)                  # последняя панель в нижний слот outer

        elif template == "2x2":
            # ── сетка: 2 столбца ──────────────────────────────────────────────
            outer = tk.PanedWindow(self.frame_dashboard, orient="horizontal", **pw_kw)
            outer.grid(row=0, column=0, sticky="nsew")
            left_pw  = tk.PanedWindow(outer, orient="vertical", **pw_kw)
            right_pw = tk.PanedWindow(outer, orient="vertical", **pw_kw)
            self.h_paned = outer
            self._paned_windows.update(h=outer, left=left_pw, right=right_pw)
            outer.add(left_pw,  stretch="always", minsize=120)
            outer.add(right_pw, stretch="always", minsize=120)
            left_c = max(1, count // 2)
            for i in range(count):
                pw = left_pw if i < left_c else right_pw
                _add(pw, i)

        else:
            # ── auto: текущее поведение (2 колонки) ───────────────────────────
            self._current_template = "auto"
            left_count  = max(1, count // 2)
            right_count = count - left_count
            self._left_count = left_count

            h_pw   = tk.PanedWindow(self.frame_dashboard, orient="horizontal", **pw_kw)
            h_pw.grid(row=0, column=0, sticky="nsew")
            left_pw = tk.PanedWindow(h_pw, orient="vertical", **pw_kw)
            self.h_paned = h_pw
            self._paned_windows.update(h=h_pw, left=left_pw)

            if right_count > 0:
                right_pw = tk.PanedWindow(h_pw, orient="vertical", **pw_kw)
                h_pw.add(left_pw,  stretch="always", minsize=120)
                h_pw.add(right_pw, stretch="always", minsize=120)
                self._paned_windows["right"] = right_pw
            else:
                right_pw = None
                h_pw.add(left_pw, stretch="always", minsize=120)

            for i in range(count):
                pw = right_pw if (right_pw and i >= left_count) else left_pw
                _add(pw, i)

        # ── совместимые алиасы ────────────────────────────────────────────────
        self.left_paned  = (self._paned_windows.get("left")
                            or self._paned_windows.get("main")
                            or self.h_paned)
        self.right_paned = self._paned_windows.get("right")

        # ── привязка восстановления заблокированных сашей ─────────────────────
        for pw in self._paned_windows.values():
            pw.bind("<ButtonRelease-1>",
                    lambda e: self.after(20, self._restore_pinned_sashes))

        self.after(50, self._bind_tab_to_canvas)

    def _run_panel_query(self, panel: DashboardPanel):
        query_name = panel.get_query_name()
        if not query_name:
            return
        panel.update_title(query_name)

        query_file = self._find_query_file(query_name)
        if not query_file:
            panel.set_result([], [])
            return

        try:
            with open(os.path.join(self.data_manager.queries_dir, query_file), encoding="utf-8") as fh:
                sql = fh.read()
        except Exception:
            panel.set_result([], [])
            return

        meta = self._get_query_meta(query_file)
        db_display = meta.get("database", "")
        conn_file = self._find_conn_file(db_display) if db_display else None
        if not conn_file:
            panel.set_result([], [])
            return

        db_name = os.path.splitext(conn_file)[0]

        _timeout = self.settings_manager.get_setting("query_timeout_secs", 300)
        panel.set_loading(True, timeout_secs=_timeout)
        panel.run_btn.configure(state="disabled")

        _cancelled = [False]

        def _on_cancel():
            _cancelled[0] = True

        panel._cancel_fn = _on_cancel

        def worker():
            try:
                rows, cols = self.db_manager.execute_query_with_columns(db_name, sql)
                try:
                    self.after(0, lambda r=rows, c=cols: done(r, c, None))
                except Exception:
                    pass
            except Exception as e:
                try:
                    self.after(0, lambda err=e: done([], [], err))
                except Exception:
                    pass

        def done(rows, cols, err):
            if not self.winfo_exists():
                return
            if _cancelled[0]:
                return
            panel.set_loading(False)
            panel.run_btn.configure(state="normal")
            if err:
                panel.set_result([], [])
                panel.set_row_notice("")
            else:
                self._check_change_alert(query_file, rows, cols)
                self._check_threshold_alert(query_file, rows, cols)
                max_rows = self.settings_manager.get_setting("max_rows", 1000)
                if max_rows and len(rows) > max_rows:
                    rows = rows[:max_rows]
                    panel.set_row_notice(f"Показаны первые {max_rows} строк")
                else:
                    panel.set_row_notice("")
                panel.set_result(rows, cols)
                panel._last_query_file = query_file
                _rows_list = [list(r) for r in rows]
                _cols_list = list(cols)
                with self._query_results_lock:
                    self._query_results[query_file] = {
                        "rows": _rows_list,
                        "columns": _cols_list,
                    }
                self._save_query_cache()
                ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                _hist = self._query_history.setdefault(query_file, [])
                _hist.append({"ts": ts, "rows": _rows_list, "columns": _cols_list})
                if len(_hist) > 10:
                    _hist.pop(0)
                _MAX_TOTAL = 100_000
                while len(_hist) > 1:
                    if sum(len(e["rows"]) for e in _hist) <= _MAX_TOTAL:
                        break
                    _hist.pop(0)
                self._set_query_meta(query_file, last_updated=ts)
                self._update_header_widget(query_file, _rows_list, _cols_list)
                self.refresh_queries_list()

        threading.Thread(target=worker, daemon=True).start()

    # ── drag-and-drop панелей ────────────────────────────────────────────────

    # ── Dashboard: сохранение / восстановление / перестройка ─────────────────

    def _save_dashboard_state(self):
        states = [p.get_state() for p in self.dash_panels]
        sashes = self._get_all_sash_positions()
        self.settings_manager.set_setting("dashboard", {
            "panel_count": self._dashboard_panel_count,
            "template":    getattr(self, "_current_template", "auto"),
            "panels":      states,
            "sashes":      sashes,
        })

    def _restore_dashboard_state(self, saved: dict):
        panels_data = saved.get("panels", [])
        query_names = self._get_query_names()
        for i, panel in enumerate(self.dash_panels):
            panel.set_queries(query_names)
            if i < len(panels_data):
                panel.set_state(panels_data[i])
        sashes = saved.get("sashes", {})
        self._set_all_sash_positions(sashes)
        # Повторное применение после 400 мс: перекрывает Configure-события от зума окна
        self.after(400, lambda s=sashes: self._set_all_sash_positions(s))
        self._rebuild_pinned_snapshot()

    def _rebuild_dashboard(self, count: int, template: str = None):
        states = [p.get_state() for p in self.dash_panels]
        self._dashboard_panel_count = count
        if template is None:
            template = getattr(self, "_current_template", "auto")
        self.h_paned.destroy()
        self.dash_panels = []
        self._pinned_sash_snapshot = {}
        self._paned_windows = {}
        self._build_dashboard_panes(count, template)
        query_names = self._get_query_names()
        for i, panel in enumerate(self.dash_panels):
            panel.set_queries(query_names)
            if i < len(states):
                panel.set_state(states[i])
        self._save_dashboard_state()
        self.after(50, self._bind_tab_to_canvas)

    # ── Dashboard: блокировка саша ────────────────────────────────────────────

    def _on_panel_pin_changed(self, panel: DashboardPanel):
        self._rebuild_pinned_snapshot()
        self._save_dashboard_state()

    def _rebuild_pinned_snapshot(self):
        """Блокирует все саши, если хотя бы одна панель закреплена."""
        self._pinned_sash_snapshot = {}
        if not any(p.is_pinned for p in self.dash_panels):
            return
        self._pinned_sash_snapshot = self._get_all_sash_positions()

    def _restore_pinned_sashes(self):
        if not self._pinned_sash_snapshot:
            return
        self._set_all_sash_positions(self._pinned_sash_snapshot)

    def _get_all_sash_positions(self) -> dict:
        result = {}
        for key, pw in getattr(self, "_paned_windows", {}).items():
            n = max(0, len(pw.panes()) - 1)
            try:
                orient = str(pw.cget("orient"))
                w = pw.winfo_width()
                h = pw.winfo_height()
                fracs = []
                for i in range(n):
                    x, y = pw.sash_coord(i)
                    if orient == "horizontal" and w > 1:
                        fracs.append(round(x / w, 4))
                    elif orient == "vertical" and h > 1:
                        fracs.append(round(y / h, 4))
                    else:
                        fracs.append(0.5)
                result[key] = fracs
            except Exception:
                result[key] = []
        return result

    def _set_all_sash_positions(self, positions: dict):
        self.update_idletasks()
        for key, pw in getattr(self, "_paned_windows", {}).items():
            if key not in positions or not positions[key]:
                continue
            fracs = positions[key]
            # Старый формат [[x,y],...] — пропустить
            if fracs and isinstance(fracs[0], (list, tuple)):
                continue
            try:
                orient = str(pw.cget("orient"))
                w = pw.winfo_width()
                h = pw.winfo_height()
            except Exception:
                continue
            for i, frac in enumerate(fracs):
                try:
                    if orient == "horizontal" and w > 1:
                        pw.sash_place(i, int(frac * w), 0)
                    elif orient == "vertical" and h > 1:
                        pw.sash_place(i, 0, int(frac * h))
                except Exception:
                    pass

    # ── drag-and-drop панелей ────────────────────────────────────────────────

    def _drag_start(self, event, panel: DashboardPanel):
        if panel.is_pinned:
            return
        self._drag_source = panel
        panel.highlight(True)
        self._drag_ghost = tk.Toplevel(self)
        self._drag_ghost.overrideredirect(True)
        self._drag_ghost.attributes("-alpha", 0.65)
        self._drag_ghost.attributes("-topmost", True)
        lbl = ctk.CTkLabel(self._drag_ghost,
                           text=f"Панель {panel.panel_id}", width=130, height=36)
        lbl.pack()
        self._drag_ghost.geometry(f"130x36+{event.x_root - 65}+{event.y_root - 18}")

    def _drag_motion(self, event):
        if self._drag_ghost:
            self._drag_ghost.geometry(f"130x36+{event.x_root - 65}+{event.y_root - 18}")

        new_target: Optional[DashboardPanel] = None
        for p in self.dash_panels:
            if p is self._drag_source:
                continue
            x1, y1 = p.winfo_rootx(), p.winfo_rooty()
            x2, y2 = x1 + p.winfo_width(), y1 + p.winfo_height()
            if x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2:
                new_target = p
                break

        if new_target is not self._drag_drop_target:
            if self._drag_drop_target:
                self._drag_drop_target.highlight(False)
            self._drag_drop_target = new_target
            if new_target and not new_target.is_pinned:
                new_target.highlight(True)

    def _drag_end(self, event, source: DashboardPanel):
        if self._drag_ghost:
            self._drag_ghost.destroy()
            self._drag_ghost = None

        if self._drag_drop_target:
            self._drag_drop_target.highlight(False)
            self._drag_drop_target = None

        if source:
            source.highlight(False)

        target: Optional[DashboardPanel] = None
        for p in self.dash_panels:
            if p is source:
                continue
            x1, y1 = p.winfo_rootx(), p.winfo_rooty()
            x2, y2 = x1 + p.winfo_width(), y1 + p.winfo_height()
            if x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2:
                target = p
                break

        if target and not target.is_pinned:
            s_state = source.get_state()
            t_state = target.get_state()
            source.set_state(t_state)
            target.set_state(s_state)
            self._save_dashboard_state()

        self._drag_source = None

