"""
Диалог настройки расписания сервиса GF. Scraping.
"""
import datetime
import os
import sys
import tkinter as tk
import customtkinter as ctk

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

import theme_colors


def _teal():
    return (theme_colors.accent(), theme_colors.hover())


def _teal_hvr():
    return (theme_colors.hover(), theme_colors.dark())
_GRAY_BTN = ("gray55", "gray35")
_GRAY_HVR = ("gray45", "gray25")
_CARD_BG  = ("gray92", "gray18")

_MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


class GFServiceSettingsDialog(ctk.CTkToplevel):
    """Настройка расписания проверки изменений для GF. Scraping."""

    def __init__(self, parent, settings_manager, on_saved=None):
        super().__init__(parent)
        self.withdraw()
        self._sm       = settings_manager
        self._on_saved = on_saved

        self.title("Настройка сервиса GF. Scraping")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build()
        self.after(60, lambda: self._center(0))

    # ── layout ────────────────────────────────────────────────────────────────

    def _center(self, attempt: int = 0):
        self.update_idletasks()
        p = self.master
        p.update_idletasks()
        pw = p.winfo_width()
        ph = p.winfo_height()
        px = p.winfo_rootx()
        py = p.winfo_rooty()
        if pw <= 1 or ph <= 1:
            if attempt < 20:
                self.after(80, lambda: self._center(attempt + 1))
            else:
                self.deiconify()
            return
        dw = self.winfo_width()
        dh = self.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        self.geometry(f"+{x}+{y}")
        self.deiconify()

    def _build(self):
        sched = self._sm.get_setting("gf_sched", {})

        # ── logo / header ─────────────────────────────────────────────────────
        _logo_img = None
        if _PIL_OK:
            try:
                if getattr(sys, "frozen", False):
                    _base = sys._MEIPASS
                else:
                    # dialog is in widgets/, app.png is one level up
                    _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                _logo_path = os.path.join(_base, "app.png")
                if os.path.exists(_logo_path):
                    _pil = Image.open(_logo_path)
                    _logo_img = ctk.CTkImage(
                        light_image=_pil, dark_image=_pil, size=(96, 96))
            except Exception:
                pass

        if _logo_img:
            ctk.CTkLabel(self, image=_logo_img, text="").pack(pady=(16, 6))
        else:
            ctk.CTkLabel(
                self, text="Настройка сервиса GF. Scraping",
                font=ctk.CTkFont(size=16, weight="bold"), anchor="w",
            ).pack(fill="x", padx=20, pady=(18, 4))

        ctk.CTkFrame(self, height=1,
                     fg_color=("gray80", "gray30")).pack(fill="x", padx=20, pady=(0, 10))

        # ── container (grid для show/hide секций) ─────────────────────────────
        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(fill="x", padx=20)
        cont.grid_columnconfigure(0, weight=1)

        # ── секция 1: ежедневно ───────────────────────────────────────────────
        self._daily_var = tk.BooleanVar(value=sched.get("daily_enabled", False))
        ctk.CTkSwitch(
            cont, text="По графику ежедневно",
            variable=self._daily_var,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_daily,
            progress_color=_teal(),
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))

        self._daily_sub = ctk.CTkFrame(cont, fg_color=_CARD_BG, corner_radius=8)
        self._daily_sub.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self._daily_sub.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(self._daily_sub, text="Обновлять каждые:",
                     font=ctk.CTkFont(size=12),
                     ).grid(row=0, column=0, sticky="w", padx=(12, 0), pady=10)
        self._interval_entry = ctk.CTkEntry(
            self._daily_sub, width=70, height=32,
            placeholder_text="60",
            font=ctk.CTkFont(size=13),
            border_color=_teal())
        self._interval_entry.grid(row=0, column=1, padx=(8, 6), sticky="w", pady=10)
        ctk.CTkLabel(self._daily_sub, text="мин",
                     font=ctk.CTkFont(size=12),
                     ).grid(row=0, column=2, sticky="w", pady=10)

        saved_interval = sched.get("daily_interval_min", 60)
        if saved_interval:
            self._interval_entry.insert(0, str(saved_interval))

        # ── секция 2: по календарю ────────────────────────────────────────────
        self._cal_var = tk.BooleanVar(value=sched.get("calendar_enabled", False))
        ctk.CTkSwitch(
            cont, text="По графику календаря",
            variable=self._cal_var,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_calendar,
            progress_color=_teal(),
        ).grid(row=2, column=0, sticky="w", pady=(4, 4))

        self._cal_sub = ctk.CTkFrame(cont, fg_color="transparent")
        self._cal_sub.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        # чекбокс «Каждое число месяца»
        self._monthly_var = tk.BooleanVar(value=sched.get("calendar_monthly", False))
        self._cal_sub.grid_columnconfigure(0, weight=1)
        ctk.CTkCheckBox(
            self._cal_sub, text="Каждое число месяца",
            variable=self._monthly_var,
            command=self._toggle_monthly,
            checkbox_width=18, checkbox_height=18,
            fg_color=_teal(), hover_color=_teal_hvr(),
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # стильная карточка даты
        date_card = ctk.CTkFrame(self._cal_sub, fg_color=_CARD_BG, corner_radius=10)
        date_card.grid(row=1, column=0, sticky="ew")
        date_card.grid_columnconfigure(0, weight=1)

        # Контейнер строки числа (содержимое меняется в зависимости от режима)
        day_section = ctk.CTkFrame(date_card, fg_color="transparent")
        day_section.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))

        # Режим «разовая дата»: одно поле
        self._day_single = ctk.CTkFrame(day_section, fg_color="transparent")
        ctk.CTkLabel(self._day_single, text="Число:",
                     font=ctk.CTkFont(size=12), width=64, anchor="w").pack(side="left")
        self._day_entry = ctk.CTkEntry(
            self._day_single, width=60, height=34,
            placeholder_text="ДД",
            font=ctk.CTkFont(size=14),
            border_color=_teal())
        self._day_entry.pack(side="left", padx=(6, 0))

        # Режим «каждое число»: до 5 полей
        self._day_multi = ctk.CTkFrame(day_section, fg_color="transparent")
        ctk.CTkLabel(self._day_multi, text="Числа:",
                     font=ctk.CTkFont(size=12), width=64, anchor="w").pack(side="left")
        self._day_entries = []
        for _i in range(5):
            _e = ctk.CTkEntry(
                self._day_multi, width=50, height=34,
                placeholder_text="—",
                font=ctk.CTkFont(size=13),
                border_color=_teal())
            _e.pack(side="left", padx=(0 if _i == 0 else 6, 0))
            self._day_entries.append(_e)

        # Строка «Месяц + Год» (скрывается при "Каждое число месяца")
        self._month_year_row = ctk.CTkFrame(date_card, fg_color="transparent")
        self._month_year_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))

        ctk.CTkLabel(self._month_year_row, text="Месяц:",
                     font=ctk.CTkFont(size=12), width=64, anchor="w").pack(side="left")
        saved_m_idx = sched.get("calendar_month", datetime.date.today().month) - 1
        self._month_var = tk.StringVar(
            value=_MONTHS_RU[max(0, min(11, saved_m_idx))])
        ctk.CTkOptionMenu(
            self._month_year_row,
            values=_MONTHS_RU,
            variable=self._month_var,
            width=148, height=34,
            font=ctk.CTkFont(size=12),
            fg_color=("gray80", "gray28"),
            button_color=("gray70", "gray22"),
            button_hover_color=_teal_hvr(),
            dropdown_fg_color=("gray92", "gray22"),
            dropdown_hover_color=_teal_hvr(),
        ).pack(side="left", padx=(6, 10))

        self._year_entry = ctk.CTkEntry(
            self._month_year_row, width=78, height=34,
            placeholder_text="ГГГГ",
            font=ctk.CTkFont(size=14),
            border_color=_teal())
        self._year_entry.pack(side="left")

        # Строка «Время» (скрывается при "Каждое число месяца")
        self._time_row = ctk.CTkFrame(date_card, fg_color="transparent")
        self._time_row.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        ctk.CTkLabel(self._time_row, text="Время:",
                     font=ctk.CTkFont(size=12), width=64, anchor="w").pack(side="left")
        self._time_entry = ctk.CTkEntry(
            self._time_row, width=96, height=34,
            placeholder_text="ЧЧ:ММ",
            font=ctk.CTkFont(size=14),
            border_color=_teal())
        self._time_entry.pack(side="left", padx=(6, 0))

        # Восстановление сохранённых значений
        if self._monthly_var.get():
            saved_days = sched.get("calendar_days", [])
            if not saved_days:
                old_day = sched.get("calendar_day", "")
                saved_days = [old_day] if old_day else []
            for _i, _d in enumerate(saved_days[:5]):
                self._day_entries[_i].insert(0, str(_d))
        else:
            saved_dt = sched.get("calendar_datetime", "")
            if saved_dt:
                try:
                    d = datetime.datetime.strptime(saved_dt, "%Y-%m-%d %H:%M")
                    self._day_entry.insert(0, str(d.day))
                    self._year_entry.insert(0, str(d.year))
                    self._month_var.set(_MONTHS_RU[d.month - 1])
                    self._time_entry.insert(0, d.strftime("%H:%M"))
                except Exception:
                    pass
            else:
                now = datetime.datetime.now()
                self._day_entry.insert(0, str(now.day))
                self._year_entry.insert(0, str(now.year))
                self._month_var.set(_MONTHS_RU[now.month - 1])

        # Начальная видимость
        if not self._daily_var.get():
            self._daily_sub.grid_remove()
        if not self._cal_var.get():
            self._cal_sub.grid_remove()
        if self._monthly_var.get():
            self._day_multi.pack(fill="x")
            self._month_year_row.grid_remove()
            self._time_row.grid_remove()
        else:
            self._day_single.pack(fill="x")

        # ── разделитель + кнопки ──────────────────────────────────────────────
        ctk.CTkFrame(self, height=1,
                     fg_color=("gray80", "gray30")).pack(fill="x", padx=20, pady=(8, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(10, 18))

        ctk.CTkButton(btn_row, text="Сохранить", command=self._save,
                      width=110, height=34,
                      fg_color=_teal(), hover_color=_teal_hvr(),
                      ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="Отмена", command=self.destroy,
                      width=90, height=34,
                      fg_color=_GRAY_BTN, hover_color=_GRAY_HVR,
                      ).pack(side="right")

    # ── toggle visibility ─────────────────────────────────────────────────────

    def _toggle_daily(self):
        if self._daily_var.get():
            self._daily_sub.grid()
        else:
            self._daily_sub.grid_remove()

    def _toggle_calendar(self):
        if self._cal_var.get():
            self._cal_sub.grid()
        else:
            self._cal_sub.grid_remove()

    def _toggle_monthly(self):
        if self._monthly_var.get():
            self._day_single.pack_forget()
            self._day_multi.pack(fill="x")
            self._month_year_row.grid_remove()
            self._time_row.grid_remove()
        else:
            self._day_multi.pack_forget()
            self._day_single.pack(fill="x")
            self._month_year_row.grid()
            self._time_row.grid()

    # ── save ──────────────────────────────────────────────────────────────────

    def _save(self):
        sched = dict(self._sm.get_setting("gf_sched", {}))

        # Ежедневно
        sched["daily_enabled"] = self._daily_var.get()
        try:
            interval = int(self._interval_entry.get().strip() or "0")
            sched["daily_interval_min"] = max(1, interval)
        except ValueError:
            sched["daily_interval_min"] = 60

        # По календарю
        sched["calendar_enabled"] = self._cal_var.get()
        sched["calendar_monthly"] = self._monthly_var.get()

        if self._monthly_var.get():
            days = []
            for _e in self._day_entries:
                txt = _e.get().strip()
                if txt:
                    try:
                        _d = int(txt)
                        if 1 <= _d <= 31:
                            days.append(_d)
                    except ValueError:
                        pass
            days = sorted(set(days))[:5]
            sched["calendar_days"] = days
            sched["calendar_day"] = days[0] if days else 1
            sched["calendar_datetime"] = ""
        else:
            try:
                day      = int(self._day_entry.get().strip())
                month    = _MONTHS_RU.index(self._month_var.get()) + 1
                year     = int(self._year_entry.get().strip())
                time_str = (self._time_entry.get().strip() or "00:00")
                hh, mm   = [int(x) for x in time_str.split(":")]
                dt       = datetime.datetime(year, month, day, hh, mm)
                sched["calendar_datetime"] = dt.strftime("%Y-%m-%d %H:%M")
                sched["calendar_month"]    = month
            except (ValueError, IndexError):
                tk.messagebox.showerror(
                    "Ошибка",
                    "Неверный формат даты или времени.\n"
                    "Проверьте поля числа, месяца, года и времени (ЧЧ:ММ).",
                    parent=self,
                )
                return

        self._sm.set_setting("gf_sched", sched)
        if self._on_saved:
            self._on_saved(sched)
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
