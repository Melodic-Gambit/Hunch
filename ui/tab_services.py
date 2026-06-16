import os
import sys
import datetime
import threading
import tkinter as tk
import customtkinter as ctk
import theme_colors
from widgets.gf_scraping_module import GFScrapingWindow, _gf_fetch_latest_numbers
from widgets.gf_service_settings_dialog import GFServiceSettingsDialog
from widgets.sql_export_service import SqlExportService, SQL_EXPORT_VERSION
from widgets.sql_export_settings_dialog import SqlExportSettingsDialog

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


class ServicesTabMixin:
    """Методы вкладки «Сервисы» (GF.Scraping, карточки, drag-drop).
    Примешиваются к
    class MainWindow(LogsTabMixin, RemindersTabMixin, ConnectionsTabMixin,
                     QueriesTabMixin, ServicesTabMixin, ctk.CTk).
    """

    # ── Вкладка «Сервисы» ─────────────────────────────────────────────────────

    def setup_services_tab(self):
        self.frame_services.grid_columnconfigure(0, weight=1)
        self.frame_services.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(
            self.frame_services, fg_color="transparent")
        scroll.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._svc_card_order  = []
        self._svc_card_frames = {}

        self._build_service_card_gf_scraping(scroll)
        self._build_service_card_sql_export(scroll)
        self._build_service_card_instruktsiya(scroll)

        self.after(300, lambda: self._svc_setup_drag(scroll))

    def _build_service_card_gf_scraping(self, parent):
        # ── логотип ───────────────────────────────────────────────────────────
        _logo_img = None
        if _PIL_OK:
            try:
                _base = (sys._MEIPASS if getattr(sys, "frozen", False)
                         else os.path.dirname(os.path.abspath(__file__)))
                _pil = Image.open(os.path.join(_base, "gf_logo.png"))
                self._gf_logo_pil = _pil
                _logo_img = ctk.CTkImage(
                    light_image=_pil, dark_image=_pil, size=(29, 29))
            except Exception:
                pass

        # ── карточка ──────────────────────────────────────────────────────────
        card = ctk.CTkFrame(parent, corner_radius=10,
                            border_width=0,
                            border_color=[theme_colors.accent(), theme_colors.hover()])
        card.grid(row=0, column=0, padx=20, pady=(6, 3), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        def _hover_enter(e):
            card.configure(border_width=2)

        def _hover_leave(e):
            try:
                x, y = card.winfo_pointerx(), card.winfo_pointery()
                cx, cy = card.winfo_rootx(), card.winfo_rooty()
                if not (cx <= x < cx + card.winfo_width()
                        and cy <= y < cy + card.winfo_height()):
                    card.configure(border_width=0)
            except Exception:
                card.configure(border_width=0)

        def _bind_hover(w):
            try:
                w.bind("<Enter>", _hover_enter, add="+")
                w.bind("<Leave>", _hover_leave, add="+")
            except Exception:
                pass
            for ch in w.winfo_children():
                _bind_hover(ch)

        # ── title row ─────────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=16, pady=(7, 2), sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)

        if _logo_img:
            ctk.CTkLabel(title_row, image=_logo_img, text="").grid(
                row=0, column=0, padx=(0, 8))
        else:
            ctk.CTkLabel(title_row, text="🕸",
                         font=ctk.CTkFont(size=16)).grid(
                row=0, column=0, padx=(0, 8))

        ctk.CTkLabel(title_row, text="GF. Scraping",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w")

        # ── правый блок: v1.0 + ⚙ ────────────────────────────────────────────
        _v_row = ctk.CTkFrame(title_row, fg_color="transparent")
        _v_row.grid(row=0, column=2, padx=(8, 0), sticky="ne")
        ctk.CTkLabel(_v_row, text="v1.0",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60")).pack(side="left")
        ctk.CTkButton(
            _v_row, text="⚙", width=22, height=20,
            font=ctk.CTkFont(size=11),
            fg_color=[theme_colors.accent(), theme_colors.hover()],
            hover_color=[theme_colors.hover(), theme_colors.dark()],
            text_color="white",
            command=self._open_gf_service_settings,
        ).pack(side="left", padx=(5, 0))

        # ── ряд 1: описание (col 0) | поля (col 1) | переключатели (col 2) ──────
        _LBL_FNT = ctk.CTkFont(size=14)
        _VAL_FNT = ctk.CTkFont(size=14, weight="bold")
        _dot_on  = ("#22C55E", "#16A34A")
        _dot_off = ("gray60", "gray50")

        _saved_active = self.settings_manager.get_setting(
            "services_active", {}).get("gf_scraping", False)
        self._gf_active_var = tk.BooleanVar(value=_saved_active)

        _saved_notif = self.settings_manager.get_setting(
            "services_notifications", {}).get("gf_scraping", False)
        self._gf_notifications_var = tk.BooleanVar(value=_saved_notif)

        _saved_widget = self.settings_manager.get_setting(
            "services_widget", {}).get("gf_scraping", False)
        self._gf_widget_var = tk.BooleanVar(value=_saved_widget)

        # col 0: описание — напрямую в card с sticky="ew" (как у «Инструкции»)
        ctk.CTkLabel(
            card,
            text=("Сервис для парсинга данных изменений ОКПД/ОКВЭД с сайта classifikators.ru,\n"
                  "генерации SQL запросов для базы данных GOODFIN"),
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
            anchor="w",
            justify="left",
            wraplength=800,
        ).grid(row=1, column=0, padx=16, pady=(4, 4), sticky="ew")

        # ── ряд 2: кнопка + info-поля + переключатели (одна строка) ──────────
        last_row = ctk.CTkFrame(card, fg_color="transparent", height=1)
        last_row.grid(row=2, column=0, padx=16, pady=(4, 4), sticky="ew")

        # кнопка слева
        ctk.CTkButton(
            last_row, text="▶  Открыть",
            width=100, height=26,
            fg_color=[theme_colors.accent(), theme_colors.hover()],
            hover_color=[theme_colors.hover(), theme_colors.dark()],
            command=lambda: GFScrapingWindow.open(
                self,
                settings_manager=self.settings_manager,
                log_manager=self.log_manager,
                notify_cb=self._gf_service_notify,
                version=self._version,
            ),
        ).pack(side="left")

        # info-поля горизонтально (по центру)
        info_c = ctk.CTkFrame(last_row, fg_color="transparent", height=1)
        info_c.pack(side="left", padx=(20, 0))

        _latest = self.settings_manager.get_setting("gf_scraping_latest", {})
        ctk.CTkLabel(info_c, text="Последние изменения:",
                     font=_LBL_FNT, text_color=("gray50", "gray60"),
                     anchor="w").pack(side="left")
        self._gf_latest_frame = ctk.CTkFrame(info_c, fg_color="transparent", height=1)
        self._gf_latest_frame.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(info_c, text="  |  ", font=_LBL_FNT,
                     text_color=("gray60", "gray50")).pack(side="left")

        ctk.CTkLabel(info_c, text="Изменения найдены:",
                     font=_LBL_FNT, text_color=("gray50", "gray60"),
                     anchor="w").pack(side="left")
        self._gf_found_container = ctk.CTkFrame(info_c, fg_color="transparent", height=1)
        self._gf_found_container.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(info_c, text="  |  ", font=_LBL_FNT,
                     text_color=("gray60", "gray50")).pack(side="left")

        ctk.CTkLabel(info_c, text="Проверка:",
                     font=_LBL_FNT, text_color=("gray50", "gray60"),
                     anchor="w").pack(side="left")
        _saved_last_check = self.settings_manager.get_setting("gf_scraping_last_check", "")
        self._gf_last_check_lbl = ctk.CTkLabel(
            info_c, text=_saved_last_check, font=_VAL_FNT,
            text_color=("gray60", "gray50"), anchor="w")
        self._gf_last_check_lbl.pack(side="left", padx=(4, 0))

        _saved_found = self.settings_manager.get_setting("gf_scraping_found_changes", {})
        self.after(50, lambda: self._update_gf_found_changes_display(_saved_found))
        self.after(50, lambda: self._gf_populate_latest_labels(self._gf_latest_frame, _latest))

        # переключатели справа — вертикальный столбец
        sw_col = ctk.CTkFrame(last_row, fg_color="transparent", height=1)
        sw_col.pack(side="right")

        def _on_widget_toggle():
            val = self._gf_widget_var.get()
            d = dict(self.settings_manager.get_setting("services_widget", {}))
            d["gf_scraping"] = val
            self.settings_manager.set_setting("services_widget", d)
            self._refresh_header_widgets()

        ctk.CTkSwitch(
            sw_col,
            text="Виджет",
            variable=self._gf_widget_var,
            onvalue=True, offvalue=False,
            font=ctk.CTkFont(size=14),
            switch_width=32, switch_height=14,
            command=_on_widget_toggle,
        ).pack(side="top", anchor="w")

        ctk.CTkSwitch(
            sw_col,
            text="Уведомления",
            variable=self._gf_notifications_var,
            onvalue=True, offvalue=False,
            font=ctk.CTkFont(size=14),
            switch_width=32, switch_height=14,
            command=self._on_gf_notifications_toggle,
        ).pack(side="top", anchor="w")

        sw_active_row = ctk.CTkFrame(sw_col, fg_color="transparent", height=1)
        sw_active_row.pack(side="top", anchor="w")

        def _on_active_toggle():
            val = self._gf_active_var.get()
            dot_lbl.configure(text_color=_dot_on if val else _dot_off)
            d = dict(self.settings_manager.get_setting("services_active", {}))
            d["gf_scraping"] = val
            self.settings_manager.set_setting("services_active", d)
            if val:
                self._gf_stop_event.clear()
                self._gf_schedule_start()
            else:
                self._gf_stop_event.set()
                for _attr in ("_gf_daily_after_id", "_gf_cal_after_id"):
                    _aid = getattr(self, _attr, None)
                    if _aid is not None:
                        try:
                            self.after_cancel(_aid)
                        except Exception:
                            pass
                    setattr(self, _attr, None)

        ctk.CTkSwitch(
            sw_active_row, text="Активен",
            variable=self._gf_active_var,
            onvalue=True, offvalue=False,
            font=ctk.CTkFont(size=14),
            switch_width=32, switch_height=14,
            command=_on_active_toggle,
        ).pack(side="left")

        dot_lbl = ctk.CTkLabel(sw_active_row, text="●",
                               font=ctk.CTkFont(size=14),
                               text_color=_dot_on if _saved_active else _dot_off,
                               width=20)
        dot_lbl.pack(side="left", padx=(4, 0))

        # применяем hover ко всем дочерним виджетам карточки
        self.after(50, lambda: _bind_hover(card))

        self._svc_card_order.append("gf_scraping")
        self._svc_card_frames["gf_scraping"] = card

    # ── карточка «Инструкция» ─────────────────────────────────────────────────

    def _build_service_card_instruktsiya(self, parent):
        card = ctk.CTkFrame(parent, corner_radius=10,
                            border_width=0,
                            border_color=[theme_colors.accent(), theme_colors.hover()])
        card.grid(row=2, column=0, padx=20, pady=(3, 6), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        def _hover_enter(e):
            card.configure(border_width=2)

        def _hover_leave(e):
            try:
                x, y = card.winfo_pointerx(), card.winfo_pointery()
                cx, cy = card.winfo_rootx(), card.winfo_rooty()
                if not (cx <= x < cx + card.winfo_width()
                        and cy <= y < cy + card.winfo_height()):
                    card.configure(border_width=0)
            except Exception:
                card.configure(border_width=0)

        def _bind_hover(w):
            try:
                w.bind("<Enter>", _hover_enter, add="+")
                w.bind("<Leave>", _hover_leave, add="+")
            except Exception:
                pass
            for ch in w.winfo_children():
                _bind_hover(ch)

        # ── title row ─────────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=16, pady=(10, 2), sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(title_row, text="📖",
                     font=ctk.CTkFont(size=22)).grid(
            row=0, column=0, padx=(0, 8))

        ctk.CTkLabel(title_row, text="Инструкция",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w")

        today_str = datetime.date.today().strftime("%d.%m.%Y")
        ctk.CTkLabel(title_row, text=today_str,
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60")).grid(
            row=0, column=2, padx=(8, 0), sticky="e")

        # ── описание ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            card,
            text="Встроенная справка по использованию приложения Hunch:\nвкладки меню, горячие клавиши, уведомления, логи, сервисы",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(6, 4), sticky="ew")

        # ── кнопка «Открыть» ─────────────────────────────────────────────────
        last_row = ctk.CTkFrame(card, fg_color="transparent")
        last_row.grid(row=2, column=0, padx=16, pady=(4, 39), sticky="ew")

        ctk.CTkButton(
            last_row, text="▶  Открыть",
            width=100, height=26,
            fg_color=[theme_colors.accent(), theme_colors.hover()],
            hover_color=[theme_colors.hover(), theme_colors.dark()],
            command=self._open_instruktsiya_window,
        ).pack(side="left")

        self.after(50, lambda: _bind_hover(card))

        self._svc_card_order.append("instruktsiya")
        self._svc_card_frames["instruktsiya"] = card

    # ── drag-and-drop карточек сервисов (удержание 3 с) ──────────────────────

    def _svc_setup_drag(self, scroll):
        self._svc_scroll    = scroll
        self._svc_drag_key  = None
        self._svc_drag_hold = None
        self._svc_dragging  = False
        self._svc_ghost     = None
        self._svc_line      = None
        self._svc_target    = 0

        for key, card in self._svc_card_frames.items():
            self._svc_bind_press(key, card)

        self.bind_all("<B1-Motion>",       self._svc_on_motion,  add="+")
        self.bind_all("<ButtonRelease-1>", self._svc_on_release, add="+")

    def _svc_bind_press(self, key, card):
        def _bind(w):
            w.bind("<ButtonPress-1>",
                   lambda e, k=key: self._svc_on_press(k), add="+")
            for ch in w.winfo_children():
                _bind(ch)
        _bind(card)

    def _svc_on_press(self, key):
        if getattr(self, "_svc_drag_hold", None):
            self.after_cancel(self._svc_drag_hold)
        self._svc_drag_key  = key
        self._svc_drag_hold = self.after(
            3000, lambda k=key: self._svc_enter_drag(k))

    def _svc_enter_drag(self, key):
        self._svc_drag_hold = None
        self._svc_dragging  = True
        self._svc_target    = self._svc_card_order.index(key)

        card = self._svc_card_frames[key]
        cw = card.winfo_width()
        ch = card.winfo_height()
        cx = card.winfo_rootx()
        cy = card.winfo_rooty()

        # Ghost — полупрозрачный прямоугольник цвета карточки
        g = tk.Toplevel(self)
        g.overrideredirect(True)
        g.attributes("-alpha", 0.45)
        g.attributes("-topmost", True)
        g.geometry(f"{cw}x{ch}+{cx}+{cy}")
        tk.Frame(g, bg=theme_colors.accent()).pack(fill="both", expand=True)
        tk.Label(g, text="≡  Перетаскивание", bg=theme_colors.accent(), fg="white",
                 font=("Segoe UI", 13)).place(relx=0.5, rely=0.5, anchor="center")
        self._svc_ghost = g

        # Линия вставки
        l = tk.Toplevel(self)
        l.overrideredirect(True)
        l.attributes("-topmost", True)
        l.geometry(f"{cw}x4+{cx}+{cy}")
        tk.Frame(l, bg=theme_colors.accent()).pack(fill="both", expand=True)
        self._svc_line = l

    def _svc_on_motion(self, event):
        if not getattr(self, "_svc_dragging", False):
            return

        g = getattr(self, "_svc_ghost", None)
        if g:
            try:
                if g.winfo_exists():
                    gw = g.winfo_width()
                    gh = g.winfo_height()
                    g.geometry(f"+{event.x_root - gw // 2}+{event.y_root - gh // 2}")
            except Exception:
                pass

        key    = self._svc_drag_key
        others = [k for k in self._svc_card_order if k != key]
        if not others:
            return

        mouse_y  = event.y_root
        best_key = others[0]
        best_d   = float("inf")
        for k in others:
            c  = self._svc_card_frames[k]
            cy = c.winfo_rooty() + c.winfo_height() / 2
            d  = abs(mouse_y - cy)
            if d < best_d:
                best_d, best_key = d, k

        tc           = self._svc_card_frames[best_key]
        tc_y         = tc.winfo_rooty()
        tc_h         = tc.winfo_height()
        insert_after = mouse_y > tc_y + tc_h / 2
        base_idx     = self._svc_card_order.index(best_key)
        self._svc_target = base_idx + 1 if insert_after else base_idx

        l = getattr(self, "_svc_line", None)
        if l:
            try:
                if l.winfo_exists():
                    line_y = (tc_y + tc_h) if insert_after else tc_y
                    l.geometry(f"{tc.winfo_width()}x4+{tc.winfo_rootx()}+{line_y}")
            except Exception:
                pass

    def _svc_on_release(self, event):
        hold = getattr(self, "_svc_drag_hold", None)
        if hold:
            self.after_cancel(hold)
            self._svc_drag_hold = None

        was_dragging = getattr(self, "_svc_dragging", False)
        key          = getattr(self, "_svc_drag_key", None)
        self._svc_dragging = False
        self._svc_drag_key = None

        for attr in ("_svc_ghost", "_svc_line"):
            w = getattr(self, attr, None)
            try:
                if w and w.winfo_exists():
                    w.destroy()
            except Exception:
                pass
            setattr(self, attr, None)

        if not was_dragging or not key:
            return

        old_idx   = self._svc_card_order.index(key)
        new_idx   = getattr(self, "_svc_target", old_idx)
        self._svc_card_order.remove(key)
        insert_at = new_idx - 1 if new_idx > old_idx else new_idx
        insert_at = max(0, min(insert_at, len(self._svc_card_order)))
        self._svc_card_order.insert(insert_at, key)
        if old_idx != insert_at:
            self._svc_rebuild_cards()

    def _svc_rebuild_cards(self):
        n = len(self._svc_card_order)
        for i, key in enumerate(self._svc_card_order):
            card = self._svc_card_frames[key]
            pady = (6, 3) if i == 0 else ((3, 6) if i == n - 1 else (3, 3))
            card.grid(row=i, column=0, padx=20, pady=pady, sticky="ew")

    def _open_instruktsiya_window(self, scroll_to_hotkeys: bool = False):
        existing = getattr(self, "_instruktsiya_win", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_set()
                    if scroll_to_hotkeys:
                        existing.after(50, lambda: self._instruktsiya_scroll_hotkeys(existing))
                    return
            except Exception:
                pass

        win = ctk.CTkToplevel(self)
        self._instruktsiya_win = win
        win.withdraw()
        win.title("Инструкция — Hunch")
        win.geometry("760x660")
        win.transient(self)

        def _on_close():
            self._instruktsiya_win = None
            try:
                win.grab_release()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _on_close)

        _H1  = ctk.CTkFont(size=16, weight="bold")
        _H2  = ctk.CTkFont(size=13, weight="bold")
        _TXT = ctk.CTkFont(size=12)
        _SUB = ctk.CTkFont(size=12)
        _TC_MAIN = ("gray10", "white")
        _TC_DIM  = ("gray30", "gray70")
        _TC_TEAL = (theme_colors.accent(), "#2DD4BF")

        # ── реестр для поиска ─────────────────────────────────────────────────
        _search_sections: list = []   # [section_frame]
        _search_rows:     list = []   # [(section_frame, row_frame, text, pack_kw)]
        _search_var = ctk.StringVar()

        def _on_instr_search(*_):
            q = _search_var.get().strip().lower()
            if not q:
                for sf in _search_sections:
                    sf.pack(fill="x", padx=14, pady=(10, 0))
                for _, rf, _, kw in _search_rows:
                    rf.pack(**kw)
                return
            visible: set = set()
            for sf, rf, text, kw in _search_rows:
                if q in text:
                    rf.pack(**kw)
                    visible.add(id(sf))
                else:
                    rf.pack_forget()
            for sf in _search_sections:
                if id(sf) in visible:
                    sf.pack(fill="x", padx=14, pady=(10, 0))
                else:
                    sf.pack_forget()

        _search_var.trace_add("write", _on_instr_search)

        # ── шапка ─────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(win, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(hdr, text="📖", font=ctk.CTkFont(size=28)).pack(side="left")
        ctk.CTkLabel(hdr, text="  Инструкция по использованию Hunch",
                     font=_H1, text_color=_TC_MAIN).pack(side="left")

        # ── строка поиска ─────────────────────────────────────────────────────
        search_bar = ctk.CTkFrame(win, fg_color="transparent")
        search_bar.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkEntry(
            search_bar, textvariable=_search_var,
            placeholder_text="Поиск по инструкции…", height=32,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            search_bar, text="✕", width=32, height=32,
            fg_color="transparent", hover_color=("gray75", "gray30"),
            command=lambda: _search_var.set(""),
        ).pack(side="left", padx=(6, 0))

        ctk.CTkFrame(win, height=1,
                     fg_color=("gray75", "gray30")).pack(fill="x", padx=20, pady=(8, 0))

        # ── скролл ────────────────────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        scroll.grid_columnconfigure(0, weight=1)

        def section(title: str, icon: str = ""):
            f = ctk.CTkFrame(scroll, fg_color=("gray90", "gray18"), corner_radius=8)
            f.pack(fill="x", padx=14, pady=(10, 0))
            ctk.CTkLabel(f, text=f"{icon}  {title}" if icon else title,
                         font=_H2, text_color=_TC_TEAL, anchor="w").pack(
                fill="x", padx=14, pady=(10, 4))
            ctk.CTkFrame(f, height=1,
                         fg_color=("gray75", "gray32")).pack(fill="x", padx=14, pady=(0, 6))
            _search_sections.append(f)
            return f

        def row(parent, label: str, value: str = "", indent: int = 0):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            pack_kw = {"fill": "x", "padx": 14 + indent, "pady": 1}
            r.pack(**pack_kw)
            if value:
                ctk.CTkLabel(r, text=label, font=_TXT,
                             text_color=_TC_DIM, anchor="w",
                             width=220).pack(side="left")
                ctk.CTkLabel(r, text=value, font=_SUB,
                             text_color=_TC_MAIN, anchor="w",
                             wraplength=430, justify="left").pack(
                    side="left", fill="x", expand=True)
            else:
                ctk.CTkLabel(r, text=label, font=_TXT,
                             text_color=_TC_MAIN, anchor="w",
                             wraplength=660, justify="left").pack(
                    fill="x", pady=(0, 2))
            _search_rows.append((parent, r, (label + " " + value).lower(), pack_kw))

        def spacer(parent, h: int = 6):
            ctk.CTkFrame(parent, fg_color="transparent", height=h).pack()

        # ──────────────────────────────────────────────────────────────────────
        # 1. ВКЛАДКИ МЕНЮ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Вкладки меню", "🗂")

        row(s, "📊 Приборная панель",
            "Главный экран с фреймами данных. Каждый фрейм отображает результат SQL-запроса "
            "в виде таблицы, графика или анимированного виджета. Компоновка фреймов "
            "(1+2, 2+1, 2×2 и др.) настраивается через «Настройки → Шаблон…».")
        row(s, "🔗 Подключения",
            "Управление подключениями к базам данных. Поддерживаемые СУБД: Oracle, PostgreSQL, MySQL/MariaDB. "
            "Для каждого подключения задаются: имя, хост, порт, имя БД, логин, пароль. "
            "Кнопка «Проверить» тестирует соединение без сохранения.")
        row(s, "📝 Запросы",
            "Создание, редактирование и запуск SQL-запросов. Выбор активного подключения из списка. "
            "Кнопка «Выполнить» исполняет запрос и выводит результат в таблицу. "
            "Запросы сохраняются и могут запускаться вручную или по расписанию. "
            "При изменении результата относительно предыдущего выполнения формируется уведомление.")
        row(s, "📋 Логи",
            "Журнал всех событий приложения в реальном времени. "
            "Уровни: INFO (стандартный), WARNING (жёлтый), ERROR (красный). "
            "Записи сервиса GF.Scraping помечены префиксом [GF.Scraping]. "
            "Ctrl+C копирует выделенный текст. Кнопка «Очистить» очищает отображение.")
        row(s, "⚙️ Настройки",
            "Конфигурация приложения: список уведомлений с галочками, громкость, тема оформления, "
            "управление SQL-запросами для отслеживания, параметры подключений.")
        row(s, "🔔 Уведомления",
            "Журнал всех уведомлений. Непрочитанные — яркий цвет, прочитанные — приглушённый. "
            "«◎ Прочитать» отмечает одно уведомление. «Прочитать все» / «Удалить все» — массовые действия. "
            "Колокольчик (🔔) в шапке мигает при наличии непрочитанных уведомлений.")
        row(s, "🛠 Сервисы",
            "Модульные сервисы приложения. Каждый сервис — карточка с описанием и кнопкой «Открыть».")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 2. ГОРЯЧИЕ КЛАВИШИ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Горячие клавиши", "⌨")
        _hotkeys_section = s

        row(s, "Ctrl + D  /  Ctrl + В", "Перейти на «Приборная панель»")
        row(s, "Ctrl + L  /  Ctrl + Д", "Перейти на «Логи»")
        row(s, "Ctrl + K  /  Ctrl + Л", "Перейти на «Подключения»")
        row(s, "Ctrl + Q  /  Ctrl + Й", "Перейти на «Запросы»")
        row(s, "Ctrl + E  /  Ctrl + У", "Перейти на «Настройки»")
        row(s, "Ctrl + N  /  Ctrl + Т", "Перейти на «Уведомления»")
        row(s, "Ctrl + S  /  Ctrl + Ы", "Перейти на «Сервисы»")
        row(s, "F1", "Открыть справку (это окно) в разделе «Горячие клавиши»")
        row(s, "Tab", "Переключение между вкладками навигации (верхняя панель)")
        row(s, "Escape", "Закрыть активное диалоговое окно")
        row(s, "Enter", "Подтвердить / закрыть диалоговое окно подтверждения")
        row(s, "Ctrl + C", "Копировать выделенный текст в Логах")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 3. ТИПЫ УВЕДОМЛЕНИЙ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Типы уведомлений", "🔔")

        row(s, "", "Все типы уведомлений управляются в разделе «Настройки → Список уведомлений». "
            "Если галочка напротив типа снята — уведомления данного типа не записываются в журнал, "
            "не отображаются в виде push-тоста и не воспроизводят звуковой сигнал.")
        spacer(s, 4)
        row(s, "Алерт при изменении результата",
            "Срабатывает при изменении данных в результате SQL-запроса (добавлены или удалены строки).")
        row(s, "Пороговый алерт по столбцу",
            "Срабатывает, когда значение в отслеживаемом столбце SQL-запроса пересекает заданный порог.")
        row(s, "Сигнал",
            "Общий сигнальный тип уведомления.")
        row(s, "Изменение значения виджета",
            "Срабатывает при изменении значения виджета на приборной панели.")
        row(s, "Изменение результата запроса",
            "Общее уведомление об изменении результата любого отслеживаемого SQL-запроса.")
        row(s, "Предупреждение о ротации логов",
            "Лог-файл приближается к лимиту и скоро будет выполнена ротация.")
        row(s, "Фактическая ротация логов",
            "Выполнена ротация лог-файла (старый архивирован, создан новый).")
        row(s, "Сервисы",
            "Уведомления от модульных сервисов (GF.Scraping и др.).")
        spacer(s, 4)
        row(s, "", "Push-тост — всплывающий блок в правом верхнем углу шапки приложения. "
            "Появляется при новом уведомлении и исчезает автоматически. "
            "Клик по тосту переходит к соответствующему уведомлению в журнале.")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 4. ЗАПИСИ В ЛОГАХ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Записи в логах", "📋")

        row(s, "", "Уровни записей:")
        row(s, "INFO", "Стандартная информационная запись. Нормальная работа приложения.", indent=20)
        row(s, "WARNING", "Предупреждение. Действие выполнено с отклонением от нормы.", indent=20)
        row(s, "ERROR", "Ошибка. Действие не выполнено или прервано.", indent=20)
        spacer(s, 4)
        row(s, "", "Записи сервиса GF.Scraping (префикс [GF.Scraping]):")
        row(s, "[GF.Scraping] Фоновая проверка: запрос …",
            "Начало фоновой проверки — отправка HTTP-запроса к classifikators.ru.", indent=20)
        row(s, "[GF.Scraping] ОКВЭД: получено N номеров, макс=M, мин=K",
            "Успешно получены данные страницы обновлений ОКВЭД.", indent=20)
        row(s, "[GF.Scraping] ОКВЭД: базовый макс=M, новые: [список]",
            "Сравнение с базовой точкой. Если список пуст — новых записей нет.", indent=20)
        row(s, "[GF.Scraping] ОКВЭД: базовая точка не задана",
            "Ручной парсинг ещё не выполнялся — запустите сервис и откройте страницу ОКВЭД.", indent=20)
        row(s, "[GF.Scraping] ОКВЭД: таблица не найдена или пустая",
            "Сайт недоступен или структура страницы изменилась.", indent=20)
        row(s, "[GF.Scraping] Обнаружены новые изменения в справочниках: …",
            "Найдены новые номера — сформировано уведомление.", indent=20)
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 5. СЕРВИС GF.SCRAPING
        # ──────────────────────────────────────────────────────────────────────
        s = section("Сервис GF.Scraping", "🕸")

        row(s, "",
            "Сервис для парсинга изменений справочников ОКВЭД и ОКПД с сайта classifikators.ru "
            "и генерации SQL-запросов для базы данных GOODFIN.")
        spacer(s, 4)
        row(s, "Последние изменения",
            "Максимальный номер записи, установленный при последнем ручном парсинге. "
            "Служит базовой точкой сравнения для фоновой проверки.")
        row(s, "Найдены изменения",
            "Номера новых записей, обнаруженных при фоновой проверке (выше базовой точки). "
            "Отображаются зелёным цветом. Обновляются после каждой проверки.")
        row(s, "Проверка изменений",
            "Дата и время последней выполненной фоновой проверки.")
        row(s, "⚙ Настройка расписания",
            "Открывает диалог настройки расписания: ежедневно с заданным интервалом (мин) "
            "или по конкретным датам/числам месяца.")
        row(s, "Переключатель «Активен»",
            "Включает/выключает фоновую проверку по расписанию. "
            "Зелёная точка — активен, серая — отключён.")
        row(s, "Кнопка «Открыть»",
            "Открывает окно GF.Scraping для ручного парсинга страниц ОКВЭД/ОКПД "
            "и генерации SQL-запросов. Парсинг устанавливает базовую точку сравнения.")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 6. КОМПОНОВКА ПРИБОРНОЙ ПАНЕЛИ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Компоновка приборной панели", "⊞")

        row(s, "",
            "Расположение фреймов на приборной панели можно изменить в любой момент "
            "без перезапуска. Все настройки сохраняются автоматически в settings.json.")
        spacer(s, 4)
        row(s, "Выбор шаблона",
            "В «Настройки → Количество фреймов → Шаблон…» откроется диалог с карточками "
            "доступных шаблонов. В том же диалоге можно сразу изменить количество фреймов (1–8).")
        spacer(s, 4)
        row(s, "Авто", "Поведение по умолчанию: два равных столбца, фреймы распределяются "
            "автоматически.", indent=20)
        row(s, "Столбец", "Все фреймы расположены в одну вертикальную колонку.", indent=20)
        row(s, "Строка", "Все фреймы расположены в одну горизонтальную строку.", indent=20)
        row(s, "1 + 2", "Один широкий фрейм сверху, оставшиеся — в строку снизу.", indent=20)
        row(s, "2 + 1", "Фреймы в строку сверху, один широкий фрейм снизу.", indent=20)
        row(s, "2 × 2", "Сетка: два столбца, фреймы распределяются по обеим колонкам.", indent=20)
        spacer(s, 4)
        row(s, "Перетаскивание фреймов",
            "Захватите фрейм за иконку ⠿ в заголовке и перетащите на другой фрейм — "
            "их содержимое (запрос, данные, настройки визуализации) поменяется местами.")
        row(s, "Равные размеры",
            "Кнопка «Равные размеры» (рядом с «Шаблон…» в Настройках) мгновенно выравнивает "
            "все фреймы по размеру. Разделители между фреймами всегда можно перетащить мышью.")
        row(s, "Закрепление фрейма",
            "Кнопка 📌 в заголовке фрейма фиксирует его размер: разделители не сдвигаются, "
            "пока фрейм закреплён.")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 7. СОВЕТЫ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Советы и рекомендации", "💡")

        row(s, "",
            "• Перед использованием GF.Scraping выполните хотя бы один ручной парсинг страниц ОКВЭД "
            "и ОКПД — это установит базовую точку для сравнения.")
        row(s, "",
            "• Если уведомления не приходят — проверьте галочки в «Настройки → Список уведомлений»: "
            "тип «Сервисы» должен быть включён.")
        row(s, "",
            "• Расписание GF.Scraping работает только при включённом переключателе «Активен» "
            "на карточке сервиса.")
        row(s, "",
            "• Для быстрой смены компоновки приборной панели используйте «Настройки → Шаблон…». "
            "Кнопка «Равные размеры» быстро выравнивает фреймы после изменения шаблона.")
        row(s, "",
            "• Порядок вкладок в боковом меню можно изменить перетаскиванием.")
        row(s, "",
            "• Тема оформления (светлая/тёмная) переключается в «Настройки».")
        spacer(s)

        # ── кнопка закрыть ────────────────────────────────────────────────────
        ctk.CTkFrame(win, height=1,
                     fg_color=("gray75", "gray30")).pack(fill="x", padx=20, pady=(4, 0))
        ctk.CTkButton(win, text="Закрыть", width=110, height=34,
                      fg_color=_TC_TEAL,
                      hover_color=(theme_colors.hover(), theme_colors.dark()),
                      command=win.destroy).pack(pady=(10, 16))

        def _center():
            try:
                self.update_idletasks()
                pw = self.winfo_width()
                ph = self.winfo_height()
                x = self.winfo_rootx() + max(0, (pw - 760) // 2)
                y = self.winfo_rooty() + max(0, (ph - 660) // 2)
                win.geometry(f"+{x}+{y}")
                win.deiconify()
                win.grab_set()
                win.lift()
            except Exception:
                pass

        def _scroll_hotkeys():
            self._instruktsiya_scroll_hotkeys(win, scroll, _hotkeys_section)

        win.after(50, _center)
        if scroll_to_hotkeys:
            win.after(200, _scroll_hotkeys)

    def _instruktsiya_scroll_hotkeys(self, win, scroll=None, section=None):
        try:
            win.update_idletasks()
            if scroll is None:
                return
            canvas = scroll._parent_canvas
            bbox = canvas.bbox("all")
            if not bbox:
                return
            total_h = bbox[3] - bbox[1]
            if total_h <= 0 or section is None:
                return
            sec_root_y    = section.winfo_rooty()
            canvas_root_y = canvas.winfo_rooty()
            scroll_top    = canvas.canvasy(0)
            sec_y = sec_root_y - canvas_root_y + scroll_top - 10
            canvas.yview_moveto(max(0.0, sec_y / total_h))
        except Exception:
            pass

    # ── service notifications & scheduling ────────────────────────────────────

    def _on_gf_notifications_toggle(self):
        notifs = dict(self.settings_manager.get_setting(
            "services_notifications", {}))
        notifs["gf_scraping"] = self._gf_notifications_var.get()
        self.settings_manager.set_setting("services_notifications", notifs)

    def _gf_service_notify(self, url: str, old_hash, new_hash: str,
                           count: int):
        """Вызывается при обнаружении изменений GF.Scraping (ручной или фоновый запуск).
        Всегда обновляет хэш; уведомляет только если данные реально изменились."""
        # Всегда обновляем сохранённый хэш
        hashes = dict(self.settings_manager.get_setting(
            "gf_scraping_hashes", {}))
        hashes[url] = new_hash
        self.settings_manager.set_setting("gf_scraping_hashes", hashes)

        # Обновляем «Последние изменения» — номер из текущего URL
        url_num = url.rstrip("/").split("/")[-1]
        if url_num.isdigit():
            page_type = ("okved" if "okved" in url.lower() else
                         "okpd"  if "okpd"  in url.lower() else None)
            if page_type:
                num    = int(url_num)
                latest = dict(self.settings_manager.get_setting("gf_scraping_latest", {}))
                latest[page_type] = num
                self.settings_manager.set_setting("gf_scraping_latest", latest)
                self._update_gf_last_scan_display(latest)
                # Синхронизируем фоновый cursor: числа ≤ num уже учтены вручную
                bg_base = dict(self.settings_manager.get_setting(
                    "gf_scraping_bg_baseline", {}))
                if bg_base.get(page_type, 0) < num:
                    bg_base[page_type] = num
                    self.settings_manager.set_setting("gf_scraping_bg_baseline", bg_base)

        # Уведомляем только если хэш изменился (или первое сканирование не считается)
        if old_hash is None or old_hash == new_hash:
            return
        if not self._gf_notifications_var.get():
            return

        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        msg = (f"Обнаружены изменения в справочнике: {url}\n"
               f"Записей найдено: {count}")

        # Звук
        self._play_sound("service.wav", "service_notification")

        # Запись в «Уведомления»
        self._add_notification("GF. Scraping", message=msg, system=True)

        # Запись в «Логи»
        self.log_manager.add_log(
            f"[GF.Scraping] Изменения: {url} ({count} записей)", "INFO")
        self.after(100, self.refresh_logs)

        # Обновляем «Найдены изменения» — добавляем число из URL в найденные
        if url_num.isdigit():
            page_type = ("okved" if "okved" in url.lower() else
                         "okpd"  if "okpd"  in url.lower() else None)
            if page_type:
                found = dict(self.settings_manager.get_setting(
                    "gf_scraping_found_changes", {}))
                existing = found.get(page_type, [])
                if int(url_num) not in existing:
                    found[page_type] = [int(url_num)] + existing
                    self.settings_manager.set_setting(
                        "gf_scraping_found_changes", found)
                    self._update_gf_found_changes_display(found)

    # ── settings dialog ───────────────────────────────────────────────────────

    def _open_gf_service_settings(self):
        GFServiceSettingsDialog(
            self,
            settings_manager=self.settings_manager,
            on_saved=self._on_gf_sched_saved,
        )

    def _on_gf_sched_saved(self, sched: dict):
        """Вызывается после сохранения настроек расписания."""
        # Отменяем старые таймеры планировщика GF
        for attr in ("_gf_daily_after_id", "_gf_cal_after_id"):
            aid = getattr(self, attr, None)
            if aid is not None:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
            setattr(self, attr, None)
        self._gf_schedule_start()

    # ── background scheduler ──────────────────────────────────────────────────

    def _gf_schedule_start(self):
        """Инициализирует таймеры проверки изменений GF.Scraping на основе настроек."""
        # Таймеры работают только пока сервис активен
        if not self.settings_manager.get_setting(
                "services_active", {}).get("gf_scraping", False):
            return
        sched = self.settings_manager.get_setting("gf_sched", {})

        # Ежедневный (периодический) режим
        if sched.get("daily_enabled"):
            interval_min = max(1, int(sched.get("daily_interval_min", 60) or 60))
            self._gf_daily_after_id = self.after(
                interval_min * 60_000, self._gf_daily_tick)

        # Календарный режим
        if sched.get("calendar_enabled"):
            if sched.get("calendar_monthly"):
                # Ежемесячный: запуск по числам месяца в 00:00
                self._gf_schedule_next_monthly(sched)
            else:
                # Разовый: конкретная дата и время
                dt_str = sched.get("calendar_datetime", "")
                if dt_str:
                    try:
                        dt  = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                        now = datetime.datetime.now()
                        delay_ms = int((dt - now).total_seconds() * 1000)
                        if delay_ms > 0:
                            self._gf_cal_after_id = self.after(
                                delay_ms, self._gf_calendar_fire)
                    except Exception:
                        pass

    def _gf_schedule_next_monthly(self, sched=None):
        """Планирует следующий запуск в ежемесячном режиме (в 00:00 ближайшего числа из списка)."""
        if sched is None:
            sched = self.settings_manager.get_setting("gf_sched", {})
        days = sorted(set(sched.get("calendar_days", [])))
        if not days:
            return
        now = datetime.datetime.now()
        next_dt = None
        # Ищем в текущем месяце
        for day in days:
            try:
                candidate = now.replace(
                    day=day, hour=0, minute=0, second=0, microsecond=0)
                if candidate > now and (next_dt is None or candidate < next_dt):
                    next_dt = candidate
            except ValueError:
                pass
        # Если все числа текущего месяца прошли — ищем в следующем
        if next_dt is None:
            nm = now.month % 12 + 1
            ny = now.year + (1 if now.month == 12 else 0)
            for day in days:
                try:
                    candidate = datetime.datetime(ny, nm, day, 0, 0, 0)
                    if next_dt is None or candidate < next_dt:
                        next_dt = candidate
                except ValueError:
                    pass
        if next_dt:
            delay_ms = int((next_dt - now).total_seconds() * 1000)
            if delay_ms > 0:
                self._gf_cal_after_id = self.after(delay_ms, self._gf_monthly_fire)

    def _gf_active(self) -> bool:
        """Возвращает True если сервис GF.Scraping активен."""
        return self.settings_manager.get_setting(
            "services_active", {}).get("gf_scraping", False)

    def _gf_daily_tick(self):
        """Периодическая проверка изменений (ежедневный режим)."""
        if not self._gf_active():
            self._gf_daily_after_id = None
            return
        threading.Thread(target=self._gf_do_bg_check, daemon=True).start()
        self._gf_queue_sched_notif("daily")
        sched        = self.settings_manager.get_setting("gf_sched", {})
        interval_min = max(1, int(sched.get("daily_interval_min", 60) or 60))
        self._gf_daily_after_id = self.after(
            interval_min * 60_000, self._gf_daily_tick)

    def _gf_calendar_fire(self):
        """Однократный запуск проверки по расписанию календаря."""
        if not self._gf_active():
            return
        threading.Thread(target=self._gf_do_bg_check, daemon=True).start()
        self._gf_queue_sched_notif("calendar")
        # Отмечаем как выполненный (сбрасываем флаг)
        sched = dict(self.settings_manager.get_setting("gf_sched", {}))
        sched["calendar_enabled"] = False
        self.settings_manager.set_setting("gf_sched", sched)

    def _gf_monthly_fire(self):
        """Ежемесячный запуск проверки и перепланирование на следующее число."""
        self._gf_cal_after_id = None
        if not self._gf_active():
            return
        threading.Thread(target=self._gf_do_bg_check, daemon=True).start()
        self._gf_queue_sched_notif("calendar")
        self._gf_schedule_next_monthly()

    def _gf_queue_sched_notif(self, source: str):
        """Накапливает источники срабатывания расписания и объединяет в одно уведомление."""
        self._gf_pending_sched_sources.add(source)
        if self._gf_merge_notif_id is not None:
            try:
                self.after_cancel(self._gf_merge_notif_id)
            except Exception:
                pass
        # 2-секундное окно: если daily и calendar сработают почти одновременно — объединяем
        self._gf_merge_notif_id = self.after(2000, self._gf_flush_sched_notif)

    def _gf_flush_sched_notif(self):
        """Отправляет объединённое уведомление о выполнении расписания."""
        self._gf_merge_notif_id = None
        sources = self._gf_pending_sched_sources.copy()
        self._gf_pending_sched_sources.clear()
        if not sources:
            return

        svc = "GF. Scraping"
        now = datetime.datetime.now()
        date_str = now.strftime("%d.%m.%Y")
        time_str = now.strftime("%H:%M")

        daily_msg = (f"Обновление данных сервиса {svc} произведено по ежедневному графику "
                     f"{date_str} {time_str}")
        cal_msg   = (f"Обновление данных сервиса {svc} произведено по календарному графику "
                     f"{date_str} {time_str}")

        if "daily" in sources and "calendar" in sources:
            msg = f"{daily_msg} и {cal_msg}"
        elif "daily" in sources:
            msg = daily_msg
        else:
            msg = cal_msg

        self.log_manager.add_log(f"[GF.Scraping] {msg}", "INFO")
        if self._is_sound_type_enabled("service_notification"):
            notif_title = f"Обновление данных сервиса {svc}"
            nid = self._add_notification(notif_title, message=msg, system=True)
            self._show_alert_toast(notif_title, msg, notif_id=nid)
            self._play_sound("service.wav", "service_notification")
        self.after(100, self.refresh_logs)

    def _gf_do_bg_check(self):
        """Фоновый поток: проверяет индексные страницы ОКВЭД и ОКПД на новые номера.

        Уважает self._gf_stop_event: завершается досрочно при отмене сервиса или
        закрытии приложения, не дожидаясь окончания 11-секундного интервала.
        """
        results = {}
        for page_type in ("okved", "okpd"):
            # Проверяем сигнал отмены перед каждым сетевым запросом
            if self._gf_stop_event.is_set():
                return

            url = f"https://classifikators.ru/updates/{page_type}"
            lbl = "ОКВЭД" if page_type == "okved" else "ОКПД"
            try:
                self.after(0, lambda u=url:
                    self.log_manager.add_log(
                        f"[GF.Scraping] Фоновая проверка: запрос {u}", "INFO"))
                self.after(100, self.refresh_logs)
            except Exception:
                return

            _gf_timeout = int(self.settings_manager.get_setting(
                "gf_scraping_state", {}).get("timeout", 15))
            numbers = _gf_fetch_latest_numbers(page_type, timeout=_gf_timeout)

            if self._gf_stop_event.is_set():
                return

            if numbers:
                results[page_type] = numbers
                try:
                    self.after(0, lambda l=lbl, n=numbers:
                        self.log_manager.add_log(
                            f"[GF.Scraping] {l}: получено {len(n)} номеров, "
                            f"макс={max(n)}, мин={min(n)}", "INFO"))
                except Exception:
                    pass
            else:
                try:
                    self.after(0, lambda l=lbl, u=url:
                        self.log_manager.add_log(
                            f"[GF.Scraping] {l}: таблица не найдена или пустая — {u}",
                            "WARNING"))
                except Exception:
                    pass
            try:
                self.after(200, self.refresh_logs)
            except Exception:
                pass

            if page_type == "okved":
                # Прерываемый sleep: выходим раньше если поступил сигнал отмены
                if self._gf_stop_event.wait(11):
                    return

        if self._gf_stop_event.is_set():
            return

        ts = datetime.datetime.now().strftime("%H:%M %d.%m.%Y")
        try:
            self.after(0, lambda t=ts: self._update_gf_last_check(t))
            if results:
                self.after(0, lambda r=results: self._gf_process_bg_results(r))
            else:
                self.after(0, lambda:
                    self.log_manager.add_log(
                        "[GF.Scraping] Фоновая проверка: данные не получены", "WARNING"))
            self.after(300, self.refresh_logs)
        except Exception:
            pass

    def _gf_process_bg_results(self, results: dict):
        """Обрабатывает результаты фоновой проверки в главном потоке.

        Порог сравнения = max(gf_scraping_latest, gf_scraping_bg_baseline).
        gf_scraping_latest трогает ТОЛЬКО _gf_service_notify (ручной запуск).
        gf_scraping_bg_baseline — внутренний cursor фонового сканера, дисплей не меняет.
        """
        latest  = dict(self.settings_manager.get_setting("gf_scraping_latest", {}))
        bg_base = dict(self.settings_manager.get_setting("gf_scraping_bg_baseline", {}))
        found   = dict(self.settings_manager.get_setting("gf_scraping_found_changes", {}))
        has_new = False

        for page_type, numbers in results.items():
            lbl = "ОКВЭД" if page_type == "okved" else "ОКПД"
            # Порог = наибольший из ручного baseline и фонового cursor
            _cands   = [x for x in (latest.get(page_type), bg_base.get(page_type))
                        if x is not None]
            saved_max = max(_cands) if _cands else None

            if saved_max is None:
                # Первое обнаружение — фиксируем фоновый cursor, «Последние изменения» не трогаем.
                # Числа старше baseline не считаются «найденными».
                baseline = max(numbers)
                bg_base[page_type] = baseline
                self.settings_manager.set_setting("gf_scraping_bg_baseline", bg_base)
                self.log_manager.add_log(
                    f"[GF.Scraping] {lbl}: базовая точка установлена автоматически → {baseline}",
                    "INFO")
                continue

            new_nums = sorted([n for n in numbers if n > saved_max], reverse=True)
            self.log_manager.add_log(
                f"[GF.Scraping] {lbl}: базовый макс={saved_max}, "
                f"новые: {new_nums if new_nums else 'нет'}", "INFO")

            if new_nums:
                has_new = True
                found[page_type] = new_nums
                # Обновляем фоновый cursor чтобы следующая проверка не показывала те же числа
                new_max = max(new_nums)
                if bg_base.get(page_type, 0) < new_max:
                    bg_base[page_type] = new_max
                    self.settings_manager.set_setting("gf_scraping_bg_baseline", bg_base)
            # else: новых нет — found_changes не трогаем

        # Сохраняем актуальное состояние и всегда обновляем отображение
        self.settings_manager.set_setting("gf_scraping_found_changes", found)
        self._update_gf_found_changes_display(found)

        if not has_new:
            self.after(100, self.refresh_logs)
            return

        # Toast + уведомление
        now   = datetime.datetime.now()
        title = (f"Обновление данных сервиса GF. Scraping "
                 f"произведено {now.strftime('%d.%m.%Y')} {now.strftime('%H:%M')}")
        parts = []
        for pt in ("okved", "okpd"):
            nums = found.get(pt)
            if not nums:
                continue
            lbl_pt = "ОКВЭД" if pt == "okved" else "ОКПД"
            parts.append(f"{lbl_pt}: {', '.join(str(n) for n in sorted(nums[:10]))}")
        detail = "Обнаружены новые изменения в справочниках: " + ", ".join(parts)

        self.log_manager.add_log(f"[GF.Scraping] {detail}", "INFO")
        if self._is_sound_type_enabled("service_notification"):
            nid = self._add_notification(title, message=detail, system=True)
            self._show_alert_toast(title, detail, notif_id=nid)
            self._play_sound("service.wav", "service_notification")

        self.after(100, self.refresh_logs)

    # ── display helpers ───────────────────────────────────────────────────────

    def _update_gf_found_changes_display(self, found_changes: dict):
        """Обновляет блок «Найдены изменения» на карточке GF.Scraping."""
        self._gf_refresh_header_widget_text()
        if not hasattr(self, "_gf_found_container"):
            return
        for w in self._gf_found_container.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        if not found_changes:
            return
        import webbrowser as _wb
        # Все типы в ОДНУ горизонтальную строку (side="left") чтобы не
        # выходить за пределы r1 с фиксированной высотой _LH=14px.
        first = True
        for page_type in ("okved", "okpd"):
            nums = found_changes.get(page_type)
            if not nums:
                continue
            label_name = "ОКВЭД" if page_type == "okved" else "ОКПД"
            nums_str   = ", ".join(str(n) for n in sorted(nums[:10]))
            link_url   = f"https://classifikators.ru/updates/{page_type}/"
            # разделитель между типами
            if not first:
                ctk.CTkLabel(self._gf_found_container, text="  ",
                             font=ctk.CTkFont(size=14)).pack(side="left")
            first = False
            ctk.CTkLabel(self._gf_found_container, text=f"{label_name}: ",
                         font=ctk.CTkFont(size=14),
                         text_color=("gray20", "white")).pack(side="left")
            nums_lbl = ctk.CTkLabel(
                self._gf_found_container, text=nums_str,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=("#0D9488", "#22C55E"),
                cursor="hand2")
            nums_lbl.pack(side="left")
            nums_lbl.bind("<Button-1>",
                          lambda e, u=link_url: _wb.open(u))
            ctx = tk.Menu(self, tearoff=0)
            ctx.add_command(
                label="Копировать",
                command=lambda t=nums_str: (
                    self.clipboard_clear(), self.clipboard_append(t)))
            nums_lbl.bind("<Button-3>",
                          lambda e, m=ctx: m.tk_popup(e.x_root, e.y_root))

    def _gf_populate_header_labels(self, frame: "ctk.CTkFrame", found: dict):
        """Заполняет фрейм шапки: ОКВЭД/ОКПД белым, номера зелёным."""
        for w in frame.winfo_children():
            w.destroy()
        _fnt   = ctk.CTkFont(size=14)
        _white = ("gray10", "white")
        _green = ("#0D9488", "#22C55E")
        parts = []
        for key, lbl in (("okved", "ОКВЭД"), ("okpd", "ОКПД")):
            nums = found.get(key)
            if nums:
                parts.append((lbl, ", ".join(str(n) for n in sorted(nums[:5]))))
        if not parts:
            ctk.CTkLabel(frame, text="нет данных", font=_fnt,
                         text_color=_white).pack(side="left")
            return
        for i, (lbl, nums_str) in enumerate(parts):
            if i > 0:
                ctk.CTkLabel(frame, text=" | ", font=_fnt,
                             text_color=_white).pack(side="left")
            ctk.CTkLabel(frame, text=f"{lbl}: ", font=_fnt,
                         text_color=_white).pack(side="left")
            ctk.CTkLabel(frame, text=nums_str, font=_fnt,
                         text_color=_green).pack(side="left")

    def _gf_refresh_header_widget_text(self):
        if not getattr(self, "_gf_header_frame", None):
            return
        try:
            found = self.settings_manager.get_setting("gf_scraping_found_changes", {})
            self._gf_populate_header_labels(self._gf_header_frame, found)
        except Exception:
            pass

    def _gf_format_latest(self, latest: dict) -> str:
        """Форматирует dict {okved: N, okpd: M} → 'ОКВЭД N, ОКПД M'."""
        parts = []
        if latest.get("okved") is not None:
            parts.append(f"ОКВЭД {latest['okved']}")
        if latest.get("okpd") is not None:
            parts.append(f"ОКПД {latest['okpd']}")
        return ", ".join(parts)

    def _gf_populate_latest_labels(self, frame, latest: dict):
        for w in frame.winfo_children():
            w.destroy()
        parts = []
        if latest.get("okved") is not None:
            parts.append(("ОКВЭД ", str(latest["okved"])))
        if latest.get("okpd") is not None:
            parts.append(("ОКПД ", str(latest["okpd"])))
        _fn = ctk.CTkFont(size=14)
        _fb = ctk.CTkFont(size=14, weight="bold")
        _tc = ("gray10", "white")
        for i, (prefix, num) in enumerate(parts):
            if i > 0:
                ctk.CTkLabel(frame, text=", ", font=_fn, text_color=_tc).pack(side="left")
            ctk.CTkLabel(frame, text=prefix, font=_fn, text_color=_tc).pack(side="left")
            ctk.CTkLabel(frame, text=num, font=_fb, text_color=_tc).pack(side="left")
        if not parts:
            ctk.CTkLabel(frame, text="—", font=_fn,
                         text_color=("gray50", "gray60")).pack(side="left")

    def _update_gf_last_scan_display(self, latest: dict):
        if not hasattr(self, "_gf_latest_frame"):
            return
        self._gf_populate_latest_labels(self._gf_latest_frame, latest)

    def _update_gf_last_check(self, ts: str):
        """Сохраняет и отображает время последней проверки изменений."""
        self.settings_manager.set_setting("gf_scraping_last_check", ts)
        if hasattr(self, "_gf_last_check_lbl"):
            self._gf_last_check_lbl.configure(text=ts)

    # ══════════════════════════════════════════════════════════════════════════
    # Сервис «SQL Выгрузка»
    # ══════════════════════════════════════════════════════════════════════════

    def _build_service_card_sql_export(self, parent):
        """Строит карточку сервиса «SQL Выгрузка» на вкладке Сервисы."""
        _dot_on  = ("#22C55E", "#16A34A")
        _dot_off = ("gray60", "gray50")
        _LBL_FNT = ctk.CTkFont(size=13)
        _VAL_FNT = ctk.CTkFont(size=13, weight="bold")

        # ── читаем сохранённые настройки ─────────────────────────────────────
        cfg = self.settings_manager.get_setting
        _saved_active = cfg("sql_export_active", False)
        _saved_notif  = cfg("sql_export_notifications", True)

        self._sql_export_active_var = tk.BooleanVar(value=_saved_active)
        self._sql_export_notif_var  = tk.BooleanVar(value=_saved_notif)

        # ── создаём SqlExportService ──────────────────────────────────────────
        self._sql_export_service = SqlExportService(
            db_manager=self.db_manager,
            log_cb=self.log_manager.add_log,
        )

        # ── иконка ───────────────────────────────────────────────────────────
        _icon_img = None
        if _PIL_OK:
            try:
                _base = (sys._MEIPASS if getattr(sys, "frozen", False)
                         else os.path.dirname(os.path.abspath(__file__)))
                _icon_path = os.path.join(_base, "sql_export.png")
                if os.path.exists(_icon_path):
                    _pil = Image.open(_icon_path)
                    _icon_img = ctk.CTkImage(
                        light_image=_pil, dark_image=_pil, size=(29, 29))
            except Exception:
                pass

        # ── карточка ─────────────────────────────────────────────────────────
        card = ctk.CTkFrame(parent, corner_radius=10,
                            border_width=0,
                            border_color=[theme_colors.accent(), theme_colors.hover()])
        card.grid(row=1, column=0, padx=20, pady=(3, 3), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        def _hover_enter(e):
            card.configure(border_width=2)

        def _hover_leave(e):
            try:
                x, y = card.winfo_pointerx(), card.winfo_pointery()
                cx, cy = card.winfo_rootx(), card.winfo_rooty()
                if not (cx <= x < cx + card.winfo_width()
                        and cy <= y < cy + card.winfo_height()):
                    card.configure(border_width=0)
            except Exception:
                card.configure(border_width=0)

        def _bind_hover(w):
            try:
                w.bind("<Enter>", _hover_enter, add="+")
                w.bind("<Leave>", _hover_leave, add="+")
            except Exception:
                pass
            for ch in w.winfo_children():
                _bind_hover(ch)

        # ── title row ─────────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=16, pady=(7, 2), sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)

        if _icon_img:
            ctk.CTkLabel(title_row, image=_icon_img, text="").grid(
                row=0, column=0, padx=(0, 8))
        else:
            ctk.CTkLabel(title_row, text="📤",
                         font=ctk.CTkFont(size=20)).grid(
                row=0, column=0, padx=(0, 8))

        ctk.CTkLabel(title_row, text="SQL Выгрузка",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w")

        _v_row = ctk.CTkFrame(title_row, fg_color="transparent")
        _v_row.grid(row=0, column=2, padx=(8, 0), sticky="ne")
        ctk.CTkLabel(_v_row, text=SQL_EXPORT_VERSION,
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60")).pack(side="left")
        ctk.CTkButton(
            _v_row, text="⚙", width=22, height=20,
            font=ctk.CTkFont(size=11),
            fg_color=[theme_colors.accent(), theme_colors.hover()],
            hover_color=[theme_colors.hover(), theme_colors.dark()],
            text_color="white",
            command=self._open_sql_export_settings,
        ).pack(side="left", padx=(5, 0))

        # ── описание ──────────────────────────────────────────────────────────
        ctk.CTkLabel(
            card,
            text=("Автоматическая выгрузка SQL-запросов в Excel по расписанию.\n"
                  "Результаты сохраняются на сетевой диск в XLSX-файл"
                  " с отдельной вкладкой на каждый запрос."),
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
            anchor="w",
            justify="left",
            wraplength=800,
        ).grid(row=1, column=0, padx=16, pady=(4, 4), sticky="ew")

        # ── нижняя строка: кнопка + info + переключатели ──────────────────────
        last_row = ctk.CTkFrame(card, fg_color="transparent", height=1)
        last_row.grid(row=2, column=0, padx=16, pady=(4, 8), sticky="ew")

        # ── кнопка «Выгрузить сейчас» + hint ─────────────────────────────────
        btn_col = ctk.CTkFrame(last_row, fg_color="transparent")
        btn_col.pack(side="left")

        self._sql_export_btn = ctk.CTkButton(
            btn_col, text="▶  Выгрузить сейчас",
            width=160, height=28,
            fg_color=[theme_colors.accent(), theme_colors.hover()],
            hover_color=[theme_colors.hover(), theme_colors.dark()],
            command=self._sql_export_run_now,
        )
        self._sql_export_btn.pack(anchor="w")

        self._sql_export_hint_lbl = ctk.CTkLabel(
            btn_col, text=self._sql_export_next_run_text(),
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray55"),
            anchor="w")
        self._sql_export_hint_lbl.pack(anchor="w", pady=(2, 0))

        # ── info-поля ─────────────────────────────────────────────────────────
        info_c = ctk.CTkFrame(last_row, fg_color="transparent", height=1)
        info_c.pack(side="left", padx=(24, 0))

        ctk.CTkLabel(info_c, text="Последняя выгрузка:",
                     font=_LBL_FNT, text_color=("gray50", "gray60"),
                     anchor="w").pack(side="left")

        _saved_last_run = cfg("sql_export_last_run", None)
        _last_run_text  = _saved_last_run if _saved_last_run else "— не выполнялась —"
        self._sql_export_last_run_lbl = ctk.CTkLabel(
            info_c, text=_last_run_text,
            font=_VAL_FNT,
            text_color=("gray50", "gray60") if not _saved_last_run
                       else ("gray20", "white"),
            anchor="w")
        self._sql_export_last_run_lbl.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(info_c, text="  |  ",
                     font=_LBL_FNT, text_color=("gray60", "gray50")).pack(side="left")

        ctk.CTkLabel(info_c, text="Запросов:",
                     font=_LBL_FNT, text_color=("gray50", "gray60")).pack(side="left")
        _saved_qs    = cfg("sql_export_queries", [])
        _active_cnt  = sum(1 for q in _saved_qs if q.get("enabled", True))
        self._sql_export_queries_lbl = ctk.CTkLabel(
            info_c,
            text=f"{_active_cnt} активных" if _saved_qs else "не настроены",
            font=_VAL_FNT,
            text_color=("gray20", "white") if _saved_qs else ("gray50", "gray60"),
            anchor="w")
        self._sql_export_queries_lbl.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(info_c, text="  |  ",
                     font=_LBL_FNT, text_color=("gray60", "gray50")).pack(side="left")

        ctk.CTkLabel(info_c, text="Файл:",
                     font=_LBL_FNT, text_color=("gray50", "gray60")).pack(side="left")
        _tpl = cfg("sql_export_filename_template", "отчёт")
        _tpl_short = _tpl if len(_tpl) <= 22 else _tpl[:19] + "…"
        self._sql_export_file_lbl = ctk.CTkLabel(
            info_c, text=_tpl_short,
            font=_VAL_FNT,
            text_color=("gray20", "white"),
            anchor="w")
        self._sql_export_file_lbl.pack(side="left", padx=(4, 0))

        # ── переключатели ─────────────────────────────────────────────────────
        sw_col = ctk.CTkFrame(last_row, fg_color="transparent", height=1)
        sw_col.pack(side="right")

        def _on_notif_toggle():
            self.settings_manager.set_setting(
                "sql_export_notifications", self._sql_export_notif_var.get())

        ctk.CTkSwitch(
            sw_col, text="Уведомления",
            variable=self._sql_export_notif_var,
            onvalue=True, offvalue=False,
            font=ctk.CTkFont(size=14),
            switch_width=32, switch_height=14,
            command=_on_notif_toggle,
        ).pack(side="top", anchor="w")

        sw_active_row = ctk.CTkFrame(sw_col, fg_color="transparent", height=1)
        sw_active_row.pack(side="top", anchor="w")

        def _on_active_toggle():
            val = self._sql_export_active_var.get()
            dot_lbl.configure(text_color=_dot_on if val else _dot_off)
            self.settings_manager.set_setting("sql_export_active", val)
            if val:
                self._sql_export_schedule_next()
            else:
                aid = getattr(self, "_sql_export_after_id", None)
                if aid is not None:
                    try:
                        self.after_cancel(aid)
                    except Exception:
                        pass
                    self._sql_export_after_id = None
                self._sql_export_hint_lbl.configure(
                    text="Расписание отключено")

        ctk.CTkSwitch(
            sw_active_row, text="Активен",
            variable=self._sql_export_active_var,
            onvalue=True, offvalue=False,
            font=ctk.CTkFont(size=14),
            switch_width=32, switch_height=14,
            command=_on_active_toggle,
        ).pack(side="left")

        dot_lbl = ctk.CTkLabel(sw_active_row, text="●",
                               font=ctk.CTkFont(size=14),
                               text_color=_dot_on if _saved_active else _dot_off,
                               width=20)
        dot_lbl.pack(side="left", padx=(4, 0))

        self.after(50, lambda: _bind_hover(card))

        self._svc_card_order.append("sql_export")
        self._svc_card_frames["sql_export"] = card

    # ── настройки ─────────────────────────────────────────────────────────────

    def _open_sql_export_settings(self):
        """Открывает диалог настроек SQL Выгрузки."""
        conns = []
        cfg_dir = getattr(self.db_manager, "config_dir", "config")
        if os.path.isdir(cfg_dir):
            conns = sorted(
                f[:-5] for f in os.listdir(cfg_dir) if f.endswith(".json"))

        qdir = getattr(self.data_manager, "queries_dir", "queries")

        SqlExportSettingsDialog(
            self,
            settings_manager=self.settings_manager,
            queries_dir=qdir,
            connections=conns,
            on_saved=self._on_sql_export_settings_saved,
        )

    def _on_sql_export_settings_saved(self):
        """Вызывается после сохранения настроек сервиса."""
        self._sql_export_update_card_labels()
        # Перезапускаем планировщик если сервис активен
        if self._sql_export_active_var.get():
            aid = getattr(self, "_sql_export_after_id", None)
            if aid is not None:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
                self._sql_export_after_id = None
            self._sql_export_schedule_next()

    def _sql_export_update_card_labels(self):
        """Обновляет метки карточки из текущих настроек."""
        cfg = self.settings_manager.get_setting
        qs  = cfg("sql_export_queries", [])
        cnt = sum(1 for q in qs if q.get("enabled", True))
        if hasattr(self, "_sql_export_queries_lbl"):
            self._sql_export_queries_lbl.configure(
                text=f"{cnt} активных" if qs else "не настроены",
                text_color=("gray20", "white") if qs else ("gray50", "gray60"),
            )
        tpl = cfg("sql_export_filename_template", "отчёт")
        tpl_short = tpl if len(tpl) <= 22 else tpl[:19] + "…"
        if hasattr(self, "_sql_export_file_lbl"):
            self._sql_export_file_lbl.configure(text=tpl_short)
        if hasattr(self, "_sql_export_hint_lbl"):
            self._sql_export_hint_lbl.configure(
                text=self._sql_export_next_run_text())

    # ── планировщик ───────────────────────────────────────────────────────────

    def _sql_export_schedule_next(self):
        """Вычисляет время до следующего запуска и ставит after()."""
        if not self.settings_manager.get_setting("sql_export_active", False):
            return

        cfg  = self.settings_manager.get_setting
        hour = int(cfg("sql_export_schedule_hour", 19))
        minute = int(cfg("sql_export_schedule_minute", 0))
        days  = cfg("sql_export_schedule_days", [0, 1, 2, 3, 4])

        now    = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute,
                             second=0, microsecond=0)

        # ищем ближайший разрешённый день
        for offset in range(8):
            candidate = target + datetime.timedelta(days=offset)
            if candidate <= now:
                continue
            # weekday(): 0=Пн … 6=Вс  — совпадает с нашим форматом
            if candidate.weekday() in days:
                delay_ms = int((candidate - now).total_seconds() * 1000)
                if delay_ms > 0:
                    self._sql_export_after_id = self.after(
                        delay_ms, self._sql_export_tick)
                    if hasattr(self, "_sql_export_hint_lbl"):
                        self._sql_export_hint_lbl.configure(
                            text=self._sql_export_next_run_text(candidate))
                return

        # Ни одного разрешённого дня — не планируем
        if hasattr(self, "_sql_export_hint_lbl"):
            self._sql_export_hint_lbl.configure(text="Нет активных дней")

    def _sql_export_tick(self):
        """Срабатывание планировщика: запуск выгрузки + планирование следующего."""
        self._sql_export_after_id = None
        if not self.settings_manager.get_setting("sql_export_active", False):
            return
        self._sql_export_do_export()
        self._sql_export_schedule_next()

    def _sql_export_next_run_text(self, dt: datetime.datetime = None) -> str:
        """Возвращает текст 'Следующий запуск: ...' для hint-метки."""
        if not self.settings_manager.get_setting("sql_export_active", False):
            return "Расписание отключено"
        if dt is None:
            return "Следующий запуск: вычисляется…"
        now = datetime.datetime.now()
        if dt.date() == now.date():
            return f"Следующий запуск: {dt.strftime('%H:%M')}"
        return f"Следующий запуск: {dt.strftime('%d.%m %H:%M')}"

    # ── выгрузка ──────────────────────────────────────────────────────────────

    def _sql_export_run_now(self):
        """Ручной запуск выгрузки."""
        if self._sql_export_service.is_running():
            return
        self._sql_export_do_export()

    def _sql_export_do_export(self):
        """Запускает выгрузку в фоновом потоке; обновляет кнопку на время работы."""
        cfg = self.settings_manager.get_setting
        queries  = cfg("sql_export_queries", [])
        folder   = cfg("sql_export_folder", "")
        tpl       = cfg("sql_export_filename_template", "отчёт")
        file_mode = cfg("sql_export_file_mode", "daily")
        smode     = cfg("sql_export_sheet_mode", "per_query")

        if not folder:
            if hasattr(self, "_sql_export_hint_lbl"):
                self._sql_export_hint_lbl.configure(
                    text="⚠ Укажите папку в настройках (⚙)")
            return

        if hasattr(self, "_sql_export_btn"):
            try:
                self._sql_export_btn.configure(
                    text="⏳  Выполняется…", state="disabled")
            except Exception:
                pass
        if hasattr(self, "_sql_export_hint_lbl"):
            self._sql_export_hint_lbl.configure(text="Подключение к БД…")

        def _on_done(filename: str, error: str):
            self.after(0, lambda: self._sql_export_on_done(filename, error))

        started = self._sql_export_service.start(
            queries=queries, folder=folder, filename_tpl=tpl,
            file_mode=file_mode, sheet_mode=smode,
            on_done=_on_done,
        )
        if not started:
            if hasattr(self, "_sql_export_btn"):
                try:
                    self._sql_export_btn.configure(
                        text="▶  Выгрузить сейчас", state="normal")
                except Exception:
                    pass
            if hasattr(self, "_sql_export_hint_lbl"):
                self._sql_export_hint_lbl.configure(text="Выгрузка уже выполняется…")

    def _sql_export_on_done(self, filename: str, error: str):
        """Вызывается в главном потоке после завершения выгрузки."""
        try:
            self._sql_export_btn.configure(
                text="▶  Выгрузить сейчас", state="normal")
        except Exception:
            pass

        if error:
            hint = f"⚠ {error}"
            if hasattr(self, "_sql_export_hint_lbl"):
                self._sql_export_hint_lbl.configure(text=hint)
            if self._sql_export_notif_var.get():
                msg = f"SQL Выгрузка: ошибка — {error}"
                nid = self._add_notification("SQL Выгрузка", message=msg, system=True)
                self._show_alert_toast("SQL Выгрузка", msg, notif_id=nid)
                self._play_sound("service.wav", "service_notification")
            self.log_manager.add_log(
                f"[SQL Выгрузка] Ошибка: {error}", "ERROR")
        else:
            now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            # сохраняем время последнего запуска
            self.settings_manager.set_setting("sql_export_last_run", now_str)
            self.settings_manager.set_setting("sql_export_last_file", filename)

            if hasattr(self, "_sql_export_last_run_lbl"):
                self._sql_export_last_run_lbl.configure(
                    text=now_str, text_color=("gray20", "white"))
            if hasattr(self, "_sql_export_hint_lbl"):
                self._sql_export_hint_lbl.configure(
                    text=f"✓ Сохранено: {filename}")
                self.after(4000, lambda: self._sql_export_hint_lbl.configure(
                    text=self._sql_export_next_run_text()) if hasattr(
                        self, "_sql_export_hint_lbl") else None)

            if self._sql_export_notif_var.get():
                msg = f"SQL Выгрузка: файл сохранён — {filename}"
                nid = self._add_notification("SQL Выгрузка",
                                             message=msg, system=True)
                self._show_alert_toast("SQL Выгрузка", msg, notif_id=nid)
                self._play_sound("service.wav", "service_notification")

            self.log_manager.add_log(
                f"[SQL Выгрузка] Файл сохранён: {filename}", "INFO")

        self.after(100, self.refresh_logs)

