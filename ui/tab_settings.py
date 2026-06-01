import os
import sys
import json
import ctypes
import datetime
import time
import threading
from typing import Optional
import tkinter as tk
import customtkinter as ctk
import theme_colors
import dialogs as messagebox
from tkinter import filedialog
from widgets.dashboard_layout_dialog import DashboardLayoutDialog, DASHBOARD_TEMPLATES
from widgets.result_table import ResultTable
from utils import setup_paste_bindings

try:
    import winsound as _winsound
    _WINSOUND_OK = True
except ImportError:
    _WINSOUND_OK = False

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_AUDIO_DIR = os.path.join(
    sys._MEIPASS if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__)),
    "audio-notification",
)

_NOTIF_SOUND_TYPES = [
    ("change_alert",          "Алерт при изменении результата"),
    ("threshold_alert",       "Пороговый алерт по столбцу"),
    ("signal",                "Сигнал"),
    ("widget_change",         "Изменение значения виджета"),
    ("query_result_change",   "Изменение результата запроса"),
    ("rotation_warning",      "Предупреждение о ротации логов"),
    ("rotation_done",         "Фактическая ротация логов"),
    ("service_notification",  "Сервисы"),
]


class SettingsTabMixin:
    """Методы вкладок «Настройки» и «Уведомления» (appearance, theme, config, notifications).
    Примешиваются к
    class MainWindow(LogsTabMixin, RemindersTabMixin, ConnectionsTabMixin,
                     QueriesTabMixin, ServicesTabMixin, SettingsTabMixin, ctk.CTk).
    """

    # ── Настройки ─────────────────────────────────────────────────────────────

    def setup_appearance_tab(self):
        self.frame_appearance.grid_columnconfigure(0, weight=1)
        self.frame_appearance.grid_rowconfigure(0, weight=1)

        content = ctk.CTkScrollableFrame(self.frame_appearance, fg_color="transparent")
        content.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)

        def _sep(row):
            ctk.CTkFrame(content, height=1, fg_color=("gray70", "gray35")).grid(
                row=row, column=0, sticky="ew", pady=(20, 12))

        def _section(row, text):
            ctk.CTkLabel(content, text=text,
                         font=ctk.CTkFont(size=16, weight="bold")).grid(
                row=row, column=0, pady=(0, 14), sticky="w")

        _LBL_W = 320  # фиксированная ширина метки — поля и кнопки выровнены по одной линии

        def _row(row_idx, label, pady=6):
            """Горизонтальный фрейм-строка: [подпись] [поле] [кнопка] — все рядом слева."""
            rf = ctk.CTkFrame(content, fg_color="transparent")
            rf.grid(row=row_idx, column=0, sticky="w", pady=pady)
            ctk.CTkLabel(rf, text=label, anchor="w", width=_LBL_W).pack(side="left")
            return rf

        # ── Управление фреймами ───────────────────────────────────────────────
        _section(0, "Управление фреймами")

        self._frames_table_container = ctk.CTkFrame(content, fg_color="transparent")
        self._frames_table_container.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        ctk.CTkButton(content, text="+ Добавить фрейм",
                      command=lambda: self._open_frame_edit_dialog(),
                      width=150, height=30).grid(row=2, column=0, pady=(0, 8), sticky="w")

        rf7 = _row(3, "Количество фреймов")
        self.panel_count_entry = ctk.CTkEntry(rf7, placeholder_text="1–6", width=70, height=32)
        saved_count = self.settings_manager.get_setting("dashboard", {}).get("panel_count", 3)
        self.panel_count_entry.insert(0, str(saved_count))
        self.panel_count_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(rf7, text="Применить", command=self._apply_panel_count,
                      width=110, height=32).pack(side="left")
        ctk.CTkButton(rf7, text="Шаблон…", command=self._open_layout_dialog,
                      width=100, height=32).pack(side="left", padx=(8, 0))
        ctk.CTkButton(rf7, text="Равные размеры", command=self._equalize_panel_sizes,
                      width=130, height=32,
                      fg_color=("gray75", "gray30"),
                      hover_color=("gray65", "gray25"),
                      ).pack(side="left", padx=(8, 0))

        self._refresh_frames_table()

        # ── Лимит строк результата ────────────────────────────────────────────
        _sep(4)
        _section(5, "Результаты запросов")

        rf10 = _row(6, "Лимит строк (0 = без лимита)")
        saved_max_rows = self.settings_manager.get_setting("max_rows", 1000)
        self.max_rows_entry = ctk.CTkEntry(rf10, placeholder_text="строк", width=70, height=32)
        self.max_rows_entry.insert(0, str(saved_max_rows))
        self.max_rows_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(rf10, text="Применить", command=self._apply_max_rows,
                      width=110, height=32).pack(side="left")

        rf_timeout = _row(7, "Таймаут SQL-запроса (сек., 0 = без лимита)")
        saved_timeout = self.settings_manager.get_setting("query_timeout_secs", 300)
        self.query_timeout_entry = ctk.CTkEntry(rf_timeout, placeholder_text="сек.", width=70, height=32)
        self.query_timeout_entry.insert(0, str(saved_timeout))
        self.query_timeout_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(rf_timeout, text="Применить", command=self._apply_query_timeout,
                      width=110, height=32).pack(side="left")

        # ── Ротация логов ─────────────────────────────────────────────────────
        _sep(8)
        _section(9, "Ротация логов")

        rf13 = _row(10, "Хранить логи (часов)")
        saved_hours = self.settings_manager.get_setting("log_rotation_hours", 120)
        self.rotation_hours_entry = ctk.CTkEntry(rf13, placeholder_text="часов", width=70, height=32)
        self.rotation_hours_entry.insert(0, str(saved_hours))
        self.rotation_hours_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(rf13, text="Применить", command=self._apply_rotation_hours,
                      width=110, height=32).pack(side="left")

        rf_log_size = _row(11, "Лимит размера логов (МБ, 0 = без лимита)")
        saved_log_mb = self.settings_manager.get_setting("log_rotation_max_mb", 100)
        self.log_size_entry = ctk.CTkEntry(rf_log_size, placeholder_text="МБ", width=70, height=32)
        self.log_size_entry.insert(0, str(saved_log_mb))
        self.log_size_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(rf_log_size, text="Применить", command=self._apply_log_size_limit,
                      width=110, height=32).pack(side="left")

        # ── Настройка уведомлений ─────────────────────────────────────────────
        _sep(12)
        _section(13, "Настройка уведомлений")

        rf16 = _row(14, "Ротация уведомлений (мин., 0 = выключено)")
        saved_notif_rot = self.settings_manager.get_setting("notif_rotation_minutes", 0)
        self.notif_rotation_entry = ctk.CTkEntry(rf16, placeholder_text="мин.", width=70, height=32)
        self.notif_rotation_entry.insert(0, str(saved_notif_rot))
        self.notif_rotation_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(rf16, text="Применить", command=self._apply_notif_rotation,
                      width=110, height=32).pack(side="left")

        rf_debounce = _row(15, "Дебаунс алертов (сек.)")
        saved_deb = self.settings_manager.get_setting("alert_debounce_secs", 10)
        self.alert_debounce_entry = ctk.CTkEntry(rf_debounce, placeholder_text="сек.", width=70, height=32)
        self.alert_debounce_entry.insert(0, str(saved_deb))
        self.alert_debounce_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(rf_debounce, text="Применить", command=self._apply_alert_debounce,
                      width=110, height=32).pack(side="left")

        rf_vol = _row(16, "Громкость уведомлений")
        saved_vol = self.settings_manager.get_setting("notification_volume", 100)
        self._vol_value_label = ctk.CTkLabel(rf_vol, text=f"{saved_vol}%", width=42, anchor="w")
        self.notif_volume_slider = ctk.CTkSlider(
            rf_vol,
            from_=0, to=100,
            number_of_steps=100,
            width=240, height=14,
            corner_radius=7,
            button_length=0,
            button_corner_radius=7,
            progress_color=theme_colors.accent(),
            button_color=(theme_colors.accent(), "gray60"),
            button_hover_color=(theme_colors.hover(), "gray50"),
            command=self._on_volume_slider_change,
        )
        self.notif_volume_slider.set(saved_vol)
        self.notif_volume_slider.pack(side="left", padx=(0, 10))
        self._vol_value_label.pack(side="left")

        ctk.CTkLabel(content, text="Список уведомлений:", anchor="w",
                     font=ctk.CTkFont(weight="bold")).grid(
            row=17, column=0, pady=(10, 4), sticky="w")

        self._notif_query_list_container = ctk.CTkFrame(content, fg_color="transparent")
        self._notif_query_list_container.grid(
            row=18, column=0, sticky="ew", pady=(0, 6))

        self._refresh_notif_query_checkboxes()

        # ── Управление виджетами ──────────────────────────────────────────────
        _sep(19)
        _section(20, "Управление виджетами")

        self._widgets_table_container = ctk.CTkFrame(content, fg_color="transparent")
        self._widgets_table_container.grid(row=21, column=0, sticky="ew", pady=(0, 6))
        self._refresh_widgets_table()

        # ── Цветовая тема ─────────────────────────────────────────────────────
        _sep(22)
        _section(23, "Цветовая тема")

        _THEME_PRESETS = {
            "Бирюзовый (по умолчанию)": {"accent": "#0D9488", "hover": "#0B7A72", "dark": "#096B62"},
            "Синий":     {"accent": "#2563EB", "hover": "#1D4ED8", "dark": "#1E40AF"},
            "Фиолетовый":{"accent": "#7C3AED", "hover": "#6D28D9", "dark": "#5B21B6"},
            "Зелёный":   {"accent": "#16A34A", "hover": "#15803D", "dark": "#166534"},
            "Красный":   {"accent": "#DC2626", "hover": "#B91C1C", "dark": "#991B1B"},
            "Оранжевый": {"accent": "#EA580C", "hover": "#C2410C", "dark": "#9A3412"},
        }

        saved_theme = self.settings_manager.get_setting("custom_theme", {})
        saved_accent = saved_theme.get("accent", "#0D9488") if saved_theme else "#0D9488"

        # Определяем текущий пресет по сохранённому цвету
        _preset_name_by_color = {v["accent"]: k for k, v in _THEME_PRESETS.items()}
        cur_preset = _preset_name_by_color.get(saved_accent, "Бирюзовый (по умолчанию)")

        rf_preset = _row(24, "Готовая схема")
        self._theme_preset_var = ctk.StringVar(value=cur_preset)
        preset_combo = ctk.CTkComboBox(
            rf_preset,
            values=list(_THEME_PRESETS.keys()),
            variable=self._theme_preset_var,
            width=240, height=32,
            state="readonly",
        )
        preset_combo.pack(side="left", padx=(0, 8))

        # Превью-плашка цвета
        self._theme_preview_lbl = ctk.CTkLabel(
            rf_preset, text="   ", width=40, height=28,
            corner_radius=6,
            fg_color=saved_accent,
        )
        self._theme_preview_lbl.pack(side="left", padx=(0, 8))

        def _on_preset_change(val):
            colors = _THEME_PRESETS.get(val)
            if colors:
                self._theme_preview_lbl.configure(fg_color=colors["accent"])
                self._theme_accent_var.set(colors["accent"])

        preset_combo.configure(command=_on_preset_change)

        rf_custom = _row(25, "Произвольный цвет (HEX)")
        self._theme_accent_var = ctk.StringVar(value=saved_accent)
        accent_entry = ctk.CTkEntry(rf_custom, textvariable=self._theme_accent_var,
                                    placeholder_text="#0D9488", width=100, height=32)
        accent_entry.pack(side="left", padx=(0, 8))

        def _pick_color():
            from tkinter.colorchooser import askcolor
            res = askcolor(color=self._theme_accent_var.get(), parent=self,
                           title="Выберите основной цвет темы")
            if res and res[1]:
                self._theme_accent_var.set(res[1])
                self._theme_preview_lbl.configure(fg_color=res[1])

        ctk.CTkButton(rf_custom, text="Выбрать…", width=90, height=32,
                      command=_pick_color).pack(side="left", padx=(0, 8))

        def _apply_theme():
            accent = self._theme_accent_var.get().strip()
            if not accent.startswith("#") or len(accent) not in (4, 7):
                messagebox.showerror("Ошибка", "Введите корректный HEX-цвет, например #0D9488", parent=self)
                return
            # Вычисляем hover и dark как затемнённые варианты
            preset = _THEME_PRESETS.get(self._theme_preset_var.get())
            if preset and preset["accent"] == accent:
                hover = preset["hover"]
                dark  = preset["dark"]
            else:
                # простое затемнение: уменьшаем каждый канал на 10% и 20%
                try:
                    r = int(accent[1:3], 16)
                    g = int(accent[3:5], 16)
                    b = int(accent[5:7], 16)
                    hover = "#{:02x}{:02x}{:02x}".format(max(0, int(r*0.88)), max(0, int(g*0.88)), max(0, int(b*0.88)))
                    dark  = "#{:02x}{:02x}{:02x}".format(max(0, int(r*0.76)), max(0, int(g*0.76)), max(0, int(b*0.76)))
                except Exception:
                    hover = accent
                    dark  = accent
            self._theme_preview_lbl.configure(fg_color=accent)
            self._apply_theme_live(accent, hover, dark)

        rf_apply_theme = _row(26, "")
        ctk.CTkButton(rf_apply_theme, text="Применить тему", width=140, height=32,
                      command=_apply_theme).pack(side="left", padx=(0, 16))
        ctk.CTkButton(rf_apply_theme, text="Экспорт темы…", width=130, height=32,
                      fg_color="transparent",
                      border_width=1,
                      border_color=("gray60", "gray40"),
                      text_color=("gray10", "gray90"),
                      hover_color=("gray80", "gray30"),
                      command=lambda: self._export_theme(_THEME_PRESETS)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(rf_apply_theme, text="Импорт темы…", width=130, height=32,
                      fg_color="transparent",
                      border_width=1,
                      border_color=("gray60", "gray40"),
                      text_color=("gray10", "gray90"),
                      hover_color=("gray80", "gray30"),
                      command=self._import_theme).pack(side="left")

        # ── Импорт / Экспорт конфигурации ────────────────────────────────────
        _sep(27)
        _section(28, "Импорт / Экспорт конфигурации")

        rf_exp = _row(29, "Экспорт конфигурации в ZIP-архив")
        ctk.CTkButton(rf_exp, text="Экспортировать…", width=150, height=32,
                      command=self._export_config).pack(side="left")

        rf_imp = _row(30, "Импорт конфигурации из ZIP-архива")
        ctk.CTkButton(rf_imp, text="Импортировать…", width=150, height=32,
                      command=self._import_config).pack(side="left")

        # ── Обновления ────────────────────────────────────────────────────────
        _sep(31)
        _section(32, "Обновления")

        rf_upd = _row(33, "Проверять обновления при запуске")
        _upd_on = self.settings_manager.get_setting("check_updates", True)
        self._update_check_switch = ctk.CTkSwitch(rf_upd, text="", width=46, height=24)
        if _upd_on:
            self._update_check_switch.select()
        self._update_check_switch.configure(
            command=lambda: self.settings_manager.set_setting(
                "check_updates", bool(self._update_check_switch.get())))
        self._update_check_switch.pack(side="left")

        setup_paste_bindings(content)

    def _apply_panel_count(self):
        val = self.panel_count_entry.get().strip()
        try:
            count = int(val)
            if not (1 <= count <= 6):
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число от 1 до 6")
            return
        self._rebuild_dashboard(count)   # template сохраняется из _current_template
        self._refresh_frames_table()
        self.log_manager.add_log(f"Количество фреймов изменено: {count}")

    def _open_layout_dialog(self):
        """Открывает диалог выбора шаблона компоновки (UX-10c)."""
        dlg = DashboardLayoutDialog(
            self,
            current_template=getattr(self, "_current_template", "auto"),
            panel_count=self._dashboard_panel_count,
        )
        self.wait_window(dlg)
        if not dlg.result:
            return
        template, count = dlg.result
        self._rebuild_dashboard(count, template)
        self._sync_panel_count_entry()
        self._refresh_frames_table()
        tmpl_label = next(
            (t[1] for t in DASHBOARD_TEMPLATES if t[0] == template), template)
        self.log_manager.add_log(
            f"Шаблон компоновки: «{tmpl_label}», фреймов: {count}")

    def _equalize_panel_sizes(self):
        """Устанавливает равные размеры для всех панелей (UX-10e)."""
        self.update_idletasks()
        for pw in getattr(self, "_paned_windows", {}).values():
            panes = pw.panes()
            n = len(panes)
            if n < 2:
                continue
            try:
                orient = str(pw.cget("orient"))
            except Exception:
                continue
            if orient == "horizontal":
                total = pw.winfo_width()
                if total < 2:
                    continue
                size = total // n
                for i in range(n - 1):
                    pw.sash_place(i, size * (i + 1), 0)
            else:
                total = pw.winfo_height()
                if total < 2:
                    continue
                size = total // n
                for i in range(n - 1):
                    pw.sash_place(i, 0, size * (i + 1))

    def _apply_rotation_hours(self):
        val = self.rotation_hours_entry.get().strip()
        try:
            h = int(val)
            if h < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 1")
            return
        self.settings_manager.set_setting("log_rotation_hours", h)
        self.log_manager.add_log(f"Порог ротации логов изменён: {h} ч.", "WARNING")
        # Перезапускаем проверку немедленно с новым порогом
        if self._rotation_warn_after_id is not None:
            try:
                self.after_cancel(self._rotation_warn_after_id)
            except Exception:
                pass
        self._rotation_warn_after_id = self.after(500, self._check_rotation_warning)

    def _apply_log_size_limit(self):
        val = self.log_size_entry.get().strip()
        try:
            mb = int(val)
            if mb < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 0")
            return
        self.settings_manager.set_setting("log_rotation_max_mb", mb)
        self.log_manager.add_log(
            f"Лимит размера логов: {'без лимита' if mb == 0 else f'{mb} МБ'}.", "WARNING")

    def _apply_alert_debounce(self):
        val = self.alert_debounce_entry.get().strip()
        try:
            secs = int(val)
            if secs < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 0")
            return
        self.settings_manager.set_setting("alert_debounce_secs", secs)
        self.log_manager.add_log(f"Дебаунс алертов: {secs} сек.")

    def _apply_max_rows(self):
        val = self.max_rows_entry.get().strip()
        try:
            n = int(val)
            if n < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 0")
            return
        self.settings_manager.set_setting("max_rows", n)

    def _apply_query_timeout(self):
        val = self.query_timeout_entry.get().strip()
        try:
            n = int(val)
            if n < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 0 (0 = без таймаута)")
            return
        self.settings_manager.set_setting("query_timeout_secs", n)
        self.log_manager.add_log(f"Таймаут SQL-запроса изменён: {n} сек.")

    # ── Живое применение цветовой темы ──────────────────────────────────────

    def _apply_theme_live(self, accent: str, hover: str, dark: str):
        """Применяет тему немедленно: прогресс-оверлей + обход всех виджетов."""
        old_a = theme_colors.accent()
        old_h = theme_colors.hover()
        old_d = theme_colors.dark()

        a_up = accent.strip().upper()
        h_up = hover.strip().upper()
        d_up = dark.strip().upper()

        self.settings_manager.set_setting("custom_theme", {"accent": a_up, "hover": h_up, "dark": d_up})
        theme_colors.update(a_up, h_up, d_up)

        # Регенерируем файл темы CTk
        theme_path = theme_colors.build_theme_file(a_up, h_up, d_up)
        ctk.set_default_color_theme(theme_path)

        old_map: dict = {}
        if old_a != a_up:
            old_map[old_a] = a_up
        if old_h != h_up:
            old_map[old_h] = h_up
        if old_d != d_up:
            old_map[old_d] = d_up

        if not old_map:
            return

        # ── Прогресс-оверлей ──────────────────────────────────────────────
        overlay = ctk.CTkFrame(self, fg_color=("gray80", "gray12"), corner_radius=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()

        card = ctk.CTkFrame(overlay, width=340, height=104, corner_radius=12)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(
            card, text="⏳  Применение цветовой темы…",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(pady=(20, 10), padx=20)

        pbar = ctk.CTkProgressBar(
            card, mode="indeterminate", width=296, height=8,
            progress_color=a_up,
        )
        pbar.pack(padx=22)
        pbar.start()
        self.update_idletasks()

        _t0 = time.monotonic()

        def _do_apply():
            try:
                self._recurse_update_colors(self, old_map)
                # Обновляем иконку «Обновить все панели» (нарисована PIL)
                import gui as _m
                _m._invalidate_image_caches()
                new_img = _m._get_play_ctk_image(24)
                if new_img and hasattr(self, "_refresh_all_btn"):
                    try:
                        self._refresh_all_btn.configure(image=new_img)
                    except Exception:
                        pass
            except Exception:
                pass
            elapsed_ms = int((time.monotonic() - _t0) * 1000)
            self.after(max(0, 650 - elapsed_ms), _close)

        def _close():
            try:
                pbar.stop()
                overlay.destroy()
            except Exception:
                pass

        self.after(40, _do_apply)
        self.log_manager.add_log(f"Цветовая тема изменена: {a_up}")

    # ── helpers для рекурсивного обновления цветов ────────────────────────

    @staticmethod
    def _swap_colors(val, old_map: dict):
        if isinstance(val, str):
            return old_map.get(val.upper(), val)
        if isinstance(val, (list, tuple)):
            return [SettingsTabMixin._swap_colors(v, old_map) for v in val]
        return val

    def _update_ctk_props(self, widget, old_map: dict, props: list):
        for prop in props:
            try:
                val = widget.cget(prop)
                new_val = SettingsTabMixin._swap_colors(val, old_map)
                if new_val != val:
                    widget.configure(**{prop: new_val})
            except Exception:
                pass

    def _recurse_update_colors(self, widget, old_map: dict):
        """Рекурсивно заменяет акцентные цвета во всём дереве виджетов."""
        if isinstance(widget, ResultTable):
            widget.update_accent(theme_colors.accent())
        elif isinstance(widget, ctk.CTkButton):
            self._update_ctk_props(widget, old_map,
                                   ["fg_color", "hover_color", "border_color", "text_color"])
        elif isinstance(widget, ctk.CTkSwitch):
            self._update_ctk_props(widget, old_map,
                                   ["progress_color", "button_color", "button_hover_color"])
        elif isinstance(widget, ctk.CTkSlider):
            self._update_ctk_props(widget, old_map,
                                   ["progress_color", "button_color", "button_hover_color"])
        elif isinstance(widget, ctk.CTkProgressBar):
            self._update_ctk_props(widget, old_map, ["progress_color"])
        elif isinstance(widget, ctk.CTkCheckBox):
            self._update_ctk_props(widget, old_map,
                                   ["fg_color", "hover_color", "border_color"])
        elif isinstance(widget, ctk.CTkLabel):
            self._update_ctk_props(widget, old_map, ["fg_color", "text_color"])
        elif isinstance(widget, (ctk.CTkFrame, ctk.CTkScrollableFrame)):
            self._update_ctk_props(widget, old_map, ["fg_color", "border_color"])
        elif isinstance(widget, ctk.CTkEntry):
            self._update_ctk_props(widget, old_map, ["border_color"])
        elif isinstance(widget, tk.Frame):
            try:
                bg = widget.cget("bg")
                if bg.upper() in old_map:
                    widget.configure(bg=old_map[bg.upper()])
            except Exception:
                pass
        elif isinstance(widget, tk.Label):
            try:
                for attr in ("bg", "fg"):
                    c = widget.cget(attr)
                    if isinstance(c, str) and c.upper() in old_map:
                        widget.configure(**{attr: old_map[c.upper()]})
            except Exception:
                pass

        for child in widget.winfo_children():
            self._recurse_update_colors(child, old_map)

    # ── Цветовые темы: экспорт / импорт ──────────────────────────────────────

    def _export_theme(self, presets: dict):
        accent = self._theme_accent_var.get().strip() if hasattr(self, "_theme_accent_var") else "#0D9488"
        preset_name = self._theme_preset_var.get() if hasattr(self, "_theme_preset_var") else "Бирюзовый (по умолчанию)"
        saved = self.settings_manager.get_setting("custom_theme", {})
        theme_data = {
            "name": preset_name,
            "accent": saved.get("accent", accent) if saved else accent,
            "hover":  saved.get("hover",  "#0B7A72") if saved else "#0B7A72",
            "dark":   saved.get("dark",   "#096B62") if saved else "#096B62",
        }
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON-тема", "*.json"), ("Все файлы", "*.*")],
            initialfile="hunch_theme.json",
            title="Экспорт темы",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(theme_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Тема экспортирована", f"Тема сохранена в:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e), parent=self)

    def _import_theme(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON-тема", "*.json"), ("Все файлы", "*.*")],
            title="Импорт темы",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            accent = data.get("accent", "")
            hover  = data.get("hover",  "")
            dark   = data.get("dark",   "")
            name   = data.get("name",   "Импортированная")
            if not (accent.startswith("#") and len(accent) in (4, 7)):
                messagebox.showerror("Ошибка", "Некорректный формат файла темы (нет поля accent).", parent=self)
                return
            if not hover:
                hover = accent
            if not dark:
                dark = accent
            if hasattr(self, "_theme_accent_var"):
                self._theme_accent_var.set(accent)
            if hasattr(self, "_theme_preview_lbl"):
                self._theme_preview_lbl.configure(fg_color=accent)
            self._apply_theme_live(accent, hover, dark)
            self.log_manager.add_log(f"Тема импортирована: {name} ({accent})")
        except json.JSONDecodeError:
            messagebox.showerror("Ошибка", "Файл не является корректным JSON.", parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e), parent=self)

    # ── Импорт / Экспорт конфигурации ────────────────────────────────────────

    def _export_config(self):
        import zipfile
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP-архив", "*.zip"), ("Все файлы", "*.*")],
            initialfile="hunch_config.zip",
            title="Экспорт конфигурации",
        )
        if not path:
            return
        try:
            cfg_dir = self.data_manager.config_dir
            qdir    = self.data_manager.queries_dir
            sf      = self.data_manager.settings_file
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                # settings.json
                if os.path.exists(sf):
                    zf.write(sf, "settings.json")
                # config/*.json
                if os.path.isdir(cfg_dir):
                    for fname in os.listdir(cfg_dir):
                        if fname.endswith(".json"):
                            zf.write(os.path.join(cfg_dir, fname),
                                     os.path.join("config", fname))
                # queries/*.sql
                if os.path.isdir(qdir):
                    for fname in os.listdir(qdir):
                        if fname.endswith(".sql"):
                            zf.write(os.path.join(qdir, fname),
                                     os.path.join("queries", fname))
            count_cfg = len([f for f in (os.listdir(cfg_dir) if os.path.isdir(cfg_dir) else []) if f.endswith(".json")])
            count_qry = len([f for f in (os.listdir(qdir) if os.path.isdir(qdir) else []) if f.endswith(".sql")])
            messagebox.showinfo(
                "Экспорт выполнен",
                f"Конфигурация сохранена в:\n{path}\n\n"
                f"Подключений: {count_cfg}\nЗапросов: {count_qry}",
                parent=self,
            )
            self.log_manager.add_log(f"Конфигурация экспортирована: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", str(e), parent=self)

    def _import_config(self):
        import zipfile
        path = filedialog.askopenfilename(
            filetypes=[("ZIP-архив", "*.zip"), ("Все файлы", "*.*")],
            title="Импорт конфигурации",
        )
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                # валидация: ожидаем только разрешённые пути
                allowed_prefixes = ("settings.json", "config/", "queries/")
                bad = [n for n in names if not any(n.startswith(p) for p in allowed_prefixes)]
                if bad:
                    messagebox.showerror(
                        "Ошибка импорта",
                        f"Архив содержит недопустимые файлы:\n{chr(10).join(bad[:5])}",
                        parent=self,
                    )
                    return
                count_cfg = sum(1 for n in names if n.startswith("config/") and n.endswith(".json"))
                count_qry = sum(1 for n in names if n.startswith("queries/") and n.endswith(".sql"))
                has_settings = "settings.json" in names

            confirm = messagebox.askyesno(
                "Импорт конфигурации",
                f"Будет импортировано:\n"
                f"  Подключений: {count_cfg}\n"
                f"  Запросов: {count_qry}\n"
                f"  settings.json: {'да' if has_settings else 'нет'}\n\n"
                "Существующие файлы будут перезаписаны. Продолжить?",
                parent=self,
            )
            if not confirm:
                return

            with zipfile.ZipFile(path, "r") as zf:
                appdata_dir = os.path.dirname(self.data_manager.config_dir)
                if count_cfg > 0:
                    os.makedirs(self.data_manager.config_dir, exist_ok=True)
                if count_qry > 0:
                    os.makedirs(self.data_manager.queries_dir, exist_ok=True)
                zf.extractall(appdata_dir)

            # перезагружаем settings и data_manager
            self.settings_manager.settings = self.settings_manager.load_settings()
            self.data_manager.load_names()
            messagebox.showinfo(
                "Импорт выполнен",
                f"Конфигурация успешно импортирована.\n"
                f"Некоторые изменения вступят в силу после перезапуска приложения.",
                parent=self,
            )
            self.log_manager.add_log(f"Конфигурация импортирована из: {path}")
        except zipfile.BadZipFile:
            messagebox.showerror("Ошибка импорта", "Файл не является корректным ZIP-архивом.", parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка импорта", str(e), parent=self)

    # ── Управление фреймами (таблица в настройках) ────────────────────────────

    def _refresh_frames_table(self):
        """Перестраивает динамическую таблицу фреймов в разделе Настроек."""
        if not hasattr(self, "_frames_table_container"):
            return
        container = self._frames_table_container
        for w in container.winfo_children():
            w.destroy()

        panels = getattr(self, "dash_panels", [])
        if not panels:
            ctk.CTkLabel(container, text="Нет фреймов на панели",
                         anchor="w").pack(anchor="w", pady=8)
            return

        _W_ID   = 80
        _W_NAME = 260
        _W_CONN = 180

        # Строка заголовков
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(hdr, text="Фрейм", font=ctk.CTkFont(weight="bold"),
                     width=_W_ID, anchor="w").pack(side="left")
        ctk.CTkLabel(hdr, text="Наименование запроса", font=ctk.CTkFont(weight="bold"),
                     width=_W_NAME, anchor="w").pack(side="left")
        ctk.CTkLabel(hdr, text="Подключение", font=ctk.CTkFont(weight="bold"),
                     width=_W_CONN, anchor="w").pack(side="left")

        ctk.CTkFrame(container, height=1,
                     fg_color=("gray70", "gray35")).pack(fill="x", pady=(0, 4))

        for i, panel in enumerate(panels):
            query_name = panel.get_query_name() or ""
            conn_name  = ""
            if query_name:
                qf = self._find_query_file(query_name)
                if qf:
                    conn_name = self._get_query_meta(qf).get("database", "")

            rf = ctk.CTkFrame(container, fg_color="transparent")
            rf.pack(fill="x", pady=2)
            ctk.CTkLabel(rf, text=f"Фрейм №{panel.panel_id}",
                         width=_W_ID, anchor="w").pack(side="left")
            ctk.CTkLabel(rf, text=query_name or "—",
                         width=_W_NAME, anchor="w").pack(side="left")
            ctk.CTkLabel(rf, text=conn_name or "—",
                         width=_W_CONN, anchor="w").pack(side="left")
            ctk.CTkButton(rf, text="Изменить", width=90, height=28,
                          command=lambda idx=i: self._open_frame_edit_dialog(idx)
                          ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(rf, text="⚙", width=34, height=28,
                          fg_color=("gray75", "gray30"),
                          hover_color=("gray65", "gray25"),
                          command=lambda idx=i: self._open_viz_settings_from_settings(idx)
                          ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(rf, text="Удалить", width=80, height=28,
                          fg_color=("#E53935", "#C62828"),
                          hover_color=("#C62828", "#B71C1C"),
                          command=lambda idx=i: self._delete_frame_from_settings(idx)
                          ).pack(side="left")

    # ── Виджеты в шапке ──────────────────────────────────────────────────────

    def _refresh_header_widgets(self):
        """Перестраивает полосу виджетов в шапке по запросам с is_widget=True."""
        from gui import _HeaderWidget
        if not hasattr(self, "_header_widget_bar"):
            return
        bar = self._header_widget_bar
        for w in bar.winfo_children():
            w.destroy()
        self._header_widgets.clear()
        self._gf_header_frame = None

        # ── GF.Scraping виджет ───────────────────────────────────────────────
        _gf_active = self.settings_manager.get_setting(
            "services_widget", {}).get("gf_scraping", False)
        _has_gf = False
        if _gf_active:
            gf_frame = ctk.CTkFrame(bar, fg_color="transparent", height=1)
            if getattr(self, "_gf_logo_pil", None):
                _logo_h = ctk.CTkImage(
                    light_image=self._gf_logo_pil,
                    dark_image=self._gf_logo_pil, size=(18, 18))
                ctk.CTkLabel(gf_frame, image=_logo_h, text="").pack(
                    side="left", padx=(6, 4), pady=4)
            _found = self.settings_manager.get_setting("gf_scraping_found_changes", {})
            self._gf_header_frame = ctk.CTkFrame(gf_frame, fg_color="transparent", height=1)
            self._gf_header_frame.pack(side="left", padx=(0, 8), pady=4)
            self._gf_populate_header_labels(self._gf_header_frame, _found)
            gf_frame.pack(side="left")
            _has_gf = True

        widget_files = []
        qdir = self.data_manager.queries_dir
        if os.path.exists(qdir):
            for f in sorted(os.listdir(qdir)):
                if f.endswith(".sql") and self._get_query_meta(f).get("is_widget"):
                    widget_files.append(f)

        if _has_gf and widget_files:
            ctk.CTkFrame(bar, width=1,
                         fg_color=("gray70", "gray40")).pack(
                side="left", fill="y", padx=4)

        for i, filename in enumerate(widget_files):
            meta  = self._get_query_meta(filename)
            cfg   = meta.get("widget_viz_config") or {}
            color = cfg.get("color", "#0D9488")
            label = self.data_manager.get_query_display_name(filename)

            if i > 0:
                ctk.CTkFrame(bar, width=1,
                             fg_color=("gray70", "gray40")).pack(
                    side="left", fill="y", padx=4)

            hw = _HeaderWidget(bar, label=label, color=color)
            hw.pack(side="left", padx=(0, 0))
            self._header_widgets[filename] = hw

            cached = self._query_results.get(filename)
            if cached:
                col_idx = cfg.get("column", 0)
                rows = cached.get("rows", [])
                if rows and col_idx < len(rows[0]):
                    _raw = rows[0][col_idx]
                    _raw_s = "" if _raw is None else str(_raw).strip()
                    self._widget_prev_values[filename] = _raw_s
                    hw.set_value(_raw, alert_color=self._check_widget_alert_color(cfg, _raw_s))
                else:
                    self._widget_prev_values[filename] = ""
            else:
                self._widget_prev_values.setdefault(filename, "")

        # Для виджетов без кэшированных данных запустить запрос немедленно
        for filename in widget_files:
            if not self._query_results.get(filename):
                self._execute_query_auto(filename)

    def _update_header_widget(self, filename: str, rows: list, cols: list):
        """Обновляет значение виджета в шапке; уведомляет об изменении."""
        hw = self._header_widgets.get(filename)
        if hw is None:
            return
        meta    = self._get_query_meta(filename)
        cfg     = meta.get("widget_viz_config") or {}
        col_idx = cfg.get("column", 0)

        new_raw = rows[0][col_idx] if (rows and col_idx < len(rows[0])) else None
        new_str = "" if new_raw is None else str(new_raw).strip()

        # Уведомление об изменении значения виджета
        old_str = self._widget_prev_values.get(filename)
        if old_str is not None and new_str != old_str:
            display_name = self.data_manager.get_query_display_name(filename)
            msg = (f"{display_name} - значение изменилось с "
                   f"{old_str or '—'} на {new_str or '—'}")
            self._play_sound("notification_message.wav", "widget_change")
            self._add_notification(display_name, message=msg)
        self._widget_prev_values[filename] = new_str

        # Пороговый аллерт
        alert_color = self._check_widget_alert_color(cfg, new_str)
        hw.set_value(new_raw, alert_color=alert_color)

    def _check_widget_alert_color(self, cfg: dict, value_str: str):
        """Возвращает цвет аллерта если пороговое условие выполнено, иначе None."""
        t_val = cfg.get("threshold_value", "").strip()
        t_op  = cfg.get("threshold_op", "")
        t_clr = cfg.get("threshold_alert_color", "")
        if not (t_val and t_op and t_clr):
            return None
        try:
            v = float(value_str.replace("\u00a0", "").replace(" ", "").replace(",", "."))
            t = float(t_val.replace(",", "."))
            triggered = (
                (t_op == ">"  and v > t) or
                (t_op == "<"  and v < t) or
                (t_op == "==" and abs(v - t) < 1e-9)
            )
        except (ValueError, TypeError):
            triggered = (t_op == "==" and value_str == t_val)
        return t_clr if triggered else None

    def _refresh_widgets_table(self):
        """Перестраивает таблицу виджетов в разделе Настроек."""
        if not hasattr(self, "_widgets_table_container"):
            return
        container = self._widgets_table_container
        for w in container.winfo_children():
            w.destroy()

        widget_files = []
        qdir = self.data_manager.queries_dir
        if os.path.exists(qdir):
            for f in sorted(os.listdir(qdir)):
                if f.endswith(".sql") and self._get_query_meta(f).get("is_widget"):
                    widget_files.append(f)

        if not widget_files:
            ctk.CTkLabel(
                container,
                text="Нет запросов-виджетов. "
                     "Установите флаг «Виджет» при создании или редактировании запроса.",
                anchor="w",
                text_color=("gray50", "gray60"),
            ).pack(anchor="w", pady=8)
            return

        _W_ID   = 90
        _W_NAME = 280

        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(hdr, text="Запрос", font=ctk.CTkFont(weight="bold"),
                     width=_W_ID, anchor="w").pack(side="left")
        ctk.CTkLabel(hdr, text="Наименование запроса", font=ctk.CTkFont(weight="bold"),
                     width=_W_NAME, anchor="w").pack(side="left")

        ctk.CTkFrame(container, height=1,
                     fg_color=("gray70", "gray35")).pack(fill="x", pady=(0, 4))

        for i, filename in enumerate(widget_files):
            name = self.data_manager.get_query_display_name(filename)
            rf = ctk.CTkFrame(container, fg_color="transparent")
            rf.pack(fill="x", pady=2)
            ctk.CTkLabel(rf, text=f"Запрос №{i + 1}",
                         width=_W_ID, anchor="w").pack(side="left")
            ctk.CTkLabel(rf, text=name or "—",
                         width=_W_NAME, anchor="w").pack(side="left")
            ctk.CTkButton(rf, text="⚙", width=34, height=28,
                          fg_color=("gray75", "gray30"),
                          hover_color=("gray65", "gray25"),
                          command=lambda fn=filename: self._open_widget_viz_settings(fn)
                          ).pack(side="left", padx=(0, 4))

    def _open_widget_viz_settings(self, filename: str):
        """Открывает диалог настройки визуализации виджета и сохраняет результат."""
        from gui import _WidgetVizDialog
        meta    = self._get_query_meta(filename)
        current = meta.get("widget_viz_config") or {}
        dialog  = _WidgetVizDialog(self, current)
        self.wait_window(dialog)
        if dialog.result:
            self._set_query_meta(filename, widget_viz_config=dialog.result)
            self._refresh_header_widgets()

    def _sync_panel_count_entry(self):
        """Синхронизирует поле «Количество фреймов» с реальным числом панелей."""
        if not hasattr(self, "panel_count_entry"):
            return
        count = len(getattr(self, "dash_panels", []))
        try:
            self.panel_count_entry.delete(0, "end")
            self.panel_count_entry.insert(0, str(count))
        except Exception:
            pass

    def _open_viz_settings_from_settings(self, panel_idx: int):
        """Открывает диалог настроек визуализации для фрейма из вкладки Настройки."""
        panels = getattr(self, "dash_panels", [])
        if panel_idx >= len(panels):
            return
        panels[panel_idx]._open_viz_settings()

    def _open_frame_edit_dialog(self, panel_idx: int = None):
        """Открывает FrameEditDialog для редактирования или добавления фрейма."""
        from gui import FrameEditDialog
        panels = getattr(self, "dash_panels", [])

        if panel_idx is None:
            if len(panels) >= 6:
                messagebox.showwarning("Ограничение",
                                       "Максимальное количество фреймов: 6")
                return
            current_query       = ""
            current_render      = "Таблица"
            current_timer_anim  = "Счётчик"
            current_timer_color = "(по умолчанию)"
        else:
            if panel_idx >= len(panels):
                return
            panel               = panels[panel_idx]
            current_query       = panel.get_query_name() or ""
            current_render      = getattr(panel, "_render_type", "Таблица")
            current_timer_anim  = getattr(panel, "_timer_anim", "Счётчик")
            current_timer_color = getattr(panel, "_timer_color", "(по умолчанию)")

        dlg = FrameEditDialog(self, self._get_query_names(),
                              current_query=current_query,
                              current_render_type=current_render,
                              current_timer_anim=current_timer_anim,
                              current_timer_color=current_timer_color)
        self.wait_window(dlg)
        if not dlg.result:
            return

        query_name, render_type, timer_anim, timer_color, run_now = dlg.result

        if panel_idx is None:
            # Добавляем новый фрейм
            states    = [p.get_state() for p in panels]
            new_count = len(states) + 1
            self._rebuild_dashboard(new_count)
            query_names_upd = self._get_query_names()
            for i, p in enumerate(self.dash_panels):
                p.set_queries(query_names_upd)
                if i < len(states):
                    p.set_state(states[i])
            new_panel = self.dash_panels[-1]
            new_panel.set_queries(query_names_upd)
            new_panel._render_type = render_type
            new_panel._timer_anim  = timer_anim
            new_panel.set_timer_color(timer_color)
            if query_name:
                new_panel.query_combo.set(query_name)
                new_panel.update_title(query_name)
            self._save_dashboard_state()
            self.log_manager.add_log(
                f"Добавлен фрейм №{new_count}. Количество фреймов: {new_count}")
        else:
            panel = self.dash_panels[panel_idx]
            panel._render_type = render_type
            panel._timer_anim  = timer_anim
            panel.set_timer_color(timer_color)
            # Применяем анимацию немедленно с текущим значением таймера
            panel.set_next_refresh_secs(
                panel._timer_remaining if panel._timer_remaining > 0 else None)
            if query_name:
                panel.query_combo.set(query_name)
                panel.update_title(query_name)
            self._save_dashboard_state()

        self._sync_panel_count_entry()
        self._refresh_frames_table()

        if run_now and query_name:
            target = self.dash_panels[-1] if panel_idx is None \
                     else self.dash_panels[panel_idx]
            self._run_panel_query(target)

    def _delete_frame_from_settings(self, panel_idx: int):
        """Удаляет фрейм по индексу и пересобирает приборную панель."""
        panels = getattr(self, "dash_panels", [])
        if not panels or panel_idx >= len(panels):
            return
        if len(panels) <= 1:
            messagebox.showwarning("Ограничение",
                                   "Должен остаться хотя бы один фрейм")
            return
        frame_num = panels[panel_idx].panel_id
        states    = [p.get_state() for p in panels]
        states.pop(panel_idx)
        new_count = len(states)
        self._rebuild_dashboard(new_count)
        query_names = self._get_query_names()
        for i, p in enumerate(self.dash_panels):
            p.set_queries(query_names)
            if i < len(states):
                p.set_state(states[i])
        self._save_dashboard_state()
        self._sync_panel_count_entry()
        self._refresh_frames_table()
        self.log_manager.add_log(
            f"Фрейм №{frame_num} удалён. Количество фреймов: {new_count}")

    def _apply_tab_text_color(self, theme: str):
        color = "black" if theme == "light" else ("gray90", "gray90")
        self.tab_nav.configure(text_color=color)
        if hasattr(self, "_hamburger_btns"):
            for btn in self._hamburger_btns.values():
                btn.configure(text_color=color)
        if hasattr(self, "_ham_night_switch"):
            self._sync_night_switch()

    def _toggle_night_mode(self):
        """Обработчик переключателя Ночного режима в гамбургер-меню."""
        is_on = self._ham_night_switch.get()  # 1 = включён (тёмная), 0 = выключен (светлая)
        self.change_theme("Тёмная" if is_on else "Светлая")

    def _sync_night_switch(self):
        """Синхронизирует состояние переключателя с текущей темой."""
        if not hasattr(self, "_ham_night_switch"):
            return
        is_dark = ctk.get_appearance_mode() == "Dark"
        if is_dark:
            self._ham_night_switch.select()
        else:
            self._ham_night_switch.deselect()

    def change_theme(self, value: str):
        import gui as _m
        _m._invalidate_image_caches()
        theme = {"Тёмная": "dark", "Светлая": "light"}.get(value, "dark")
        if getattr(self, "_theme_animating", False):
            self._apply_theme_changes(theme)
            return
        self._animate_theme(theme)

    def _refresh_titlebar(self, dark: bool):
        """Обновляет цвет заголовка окна Windows (DWM) немедленно после смены темы."""
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = self.winfo_id()
            value = wintypes.BOOL(dark)
            # Атрибут 20 — официальный DWMWA_USE_IMMERSIVE_DARK_MODE (Win10 1903+/Win11)
            # Атрибут 19 — undocumented, нужен для Win10 1809 (build 17763)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                )
            # SWP_FRAMECHANGED заставляет DWM немедленно перерисовать не-клиентскую область
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
        except Exception:
            pass

    def _apply_theme_changes(self, theme: str):
        # CTk внутри set_appearance_mode вызывает 'wm withdraw/deiconify' напрямую
        # через Tcl-интерпретатор, из-за чего Windows анимирует кнопку в таскбаре.
        # Временно подменяем команду 'wm' на уровне Tcl, игнорируя withdraw/iconify.
        _patched = False
        try:
            self.tk.eval("""
                rename wm __ss_wm_orig
                proc wm args {
                    set sub [lindex $args 0]
                    if {$sub eq "withdraw" || $sub eq "iconify"} { return }
                    __ss_wm_orig {*}$args
                }
            """)
            _patched = True
            ctk.set_appearance_mode(theme)
        finally:
            if _patched:
                self.tk.eval("""
                    rename wm {}
                    rename __ss_wm_orig wm
                """)

        self.settings_manager.set_setting("theme", theme)
        self._apply_tab_text_color(theme)
        self._refresh_titlebar(theme == "dark")
        if hasattr(self, "_paned_windows"):
            bg = self._get_theme_bg()
            for pw in self._paned_windows.values():
                try:
                    pw.configure(bg=bg)
                except Exception:
                    pass
        if hasattr(self, "logs_textbox"):
            _lc = self._get_logs_theme_colors()
            self.logs_textbox.configure(bg=_lc["bg"], fg=_lc["fg"])
            self.refresh_logs()
        if hasattr(self, "dash_panels"):
            for panel in self.dash_panels:
                panel.result_table.refresh_style()
                panel.refresh_theme(theme)

    def _animate_theme(self, theme: str):
        """Cross-dissolve: снимок текущего состояния → меняем тему → растворяем снимок."""
        _STEPS = 14
        _MS    = 18
        self._theme_animating = True

        _done = False

        if _PIL_OK:
            try:
                from PIL import ImageGrab, ImageTk as _ITk
                self.update_idletasks()
                x, y = self.winfo_rootx(), self.winfo_rooty()
                w, h  = self.winfo_width(),  self.winfo_height()
                shot  = ImageGrab.grab(bbox=(x, y, x + w, y + h))

                # Overlay-окно поверх главного: показывает старый снимок
                ov = tk.Toplevel(self)
                ov.overrideredirect(True)
                ov.geometry(f"{w}x{h}+{x}+{y}")
                ov.attributes("-topmost", True)
                ov.lift()

                _img = _ITk.PhotoImage(shot)
                tk.Label(ov, image=_img, bd=0).pack()
                ov._img = _img          # защита от GC

                # Меняем тему под оверлеем — пользователь видит снимок, а не перерисовку
                self._apply_theme_changes(theme)

                def _dissolve(s):
                    try:
                        ov.attributes("-alpha", 1.0 - s / _STEPS)
                        if s < _STEPS:
                            ov.after(_MS, lambda: _dissolve(s + 1))
                        else:
                            ov.destroy()
                            self._theme_animating = False
                    except Exception:
                        self._theme_animating = False

                ov.after(1, lambda: _dissolve(1))
                _done = True
            except Exception:
                pass

        if not _done:
            # Fallback: мгновенная смена без анимации
            self._apply_theme_changes(theme)
            self._theme_animating = False

    def _bulk_update_connections(self):
        val = self.bulk_conn_entry.get().strip()
        if not val:
            messagebox.showerror("Ошибка", "Введите значение в минутах")
            return
        try:
            interval = int(val)
            if interval < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 0")
            return
        cfg_dir = self.data_manager.config_dir
        if not os.path.exists(cfg_dir):
            return
        updated = 0
        for f in os.listdir(cfg_dir):
            if f.endswith(".json"):
                self._set_conn_meta(f, update_interval=interval)
                updated += 1
        self.refresh_connections_list()
        self.log_manager.add_log(
            f"Массовое обновление подключений: {interval} мин. ({updated} шт.)")
        messagebox.showinfo(
            "Готово",
            f"Интервал {interval} мин. применён ко всем подключениям ({updated} шт.)")
        self._restart_auto_timers()

    def _bulk_update_queries(self):
        val = self.bulk_query_entry.get().strip()
        if not val:
            messagebox.showerror("Ошибка", "Введите значение в минутах")
            return
        try:
            interval = int(val)
            if interval < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 0")
            return
        qdir = self.data_manager.queries_dir
        if not os.path.exists(qdir):
            return
        updated = 0
        for f in os.listdir(qdir):
            if f.endswith(".sql"):
                self._set_query_meta(f, update_interval=interval)
                updated += 1
        self.refresh_queries_list()
        self.log_manager.add_log(
            f"Массовое обновление запросов: {interval} мин. ({updated} шт.)")
        messagebox.showinfo(
            "Готово",
            f"Интервал {interval} мин. применён ко всем запросам ({updated} шт.)")
        self._restart_auto_timers()

    # ── утилиты ───────────────────────────────────────────────────────────────

    def get_listbox_selection(self, listbox: ctk.CTkTextbox) -> Optional[str]:
        """Возвращает имя элемента из строки под курсором.

        Поддерживает два формата:
        - Таблица (подключения): первая колонка — имя, строки-заголовок/разделитель пропускаются.
        - Пункты (запросы): '• Имя  |  SQL: ...'
        """
        _HEADER_NAMES = ("Название",)
        try:
            cursor_index = listbox.index("insert")
            cursor_line  = int(cursor_index.split(".")[0])
            all_lines    = listbox.get("1.0", "end").split("\n")

            def parse(line: str) -> Optional[str]:
                if not line.strip():
                    return None
                # Разделитель таблицы
                if set(line.strip()) <= {"-", " "}:
                    return None
                # Строка-заголовок таблицы
                first = line.split("  |  ")[0].strip()
                if first in _HEADER_NAMES:
                    return None
                # Пункт "• Имя  |  ..."
                if line.startswith("• "):
                    return line[2:].split("  |  ")[0].strip()
                # Строка таблицы — первая колонка
                if "  |  " in line:
                    return first
                return line.strip() or None

            # Строка под курсором
            cur_line = all_lines[cursor_line - 1] if cursor_line - 1 < len(all_lines) else ""
            result = parse(cur_line)
            if result:
                return result

            # Fallback — первая подходящая строка
            for line in all_lines:
                result = parse(line)
                if result:
                    return result
        except Exception:
            pass
        return None

    def get_filename_by_display_name(self, display_name: str,
                                     folder: str, ext: str) -> Optional[str]:
        if not os.path.exists(folder):
            self.log_manager.add_log(f"Папка {folder} не существует", "ERROR")
            return None
        try:
            for f in os.listdir(folder):
                if not f.endswith(ext):
                    continue
                dn = (self.data_manager.get_db_display_name(f) if ext == ".json"
                      else self.data_manager.get_query_display_name(f))
                if dn == display_name:
                    return f
            candidate = f"{display_name}{ext}"
            if os.path.exists(os.path.join(folder, candidate)):
                return candidate
        except Exception as e:
            self.log_manager.add_log(f"Ошибка папки {folder}: {e}", "ERROR")
        return None

    # ── Уведомления ───────────────────────────────────────────────────────────

    def _go_to_notifications(self):
        self._hamburger_select("🔔 Уведомления")

    def _should_notify(self, query_name: str) -> bool:
        enabled = self.settings_manager.get_setting("notif_enabled_queries", "ALL")
        if enabled == "ALL":
            return True
        return isinstance(enabled, list) and query_name in enabled

    def _is_sound_type_enabled(self, sound_type: str) -> bool:
        enabled = self.settings_manager.get_setting("notif_sound_types", "ALL")
        if enabled == "ALL":
            return True
        return isinstance(enabled, list) and sound_type in enabled

    def _play_sound(self, filename: str, sound_type: str = ""):
        if not _WINSOUND_OK:
            return
        if sound_type and not self._is_sound_type_enabled(sound_type):
            return
        path = os.path.join(_AUDIO_DIR, filename)
        if not os.path.isfile(path):
            return
        volume = self.settings_manager.get_setting("notification_volume", 100)

        def _play():
            try:
                vol = int(max(0, min(100, volume)) / 100 * 0xFFFF)
                ctypes.windll.winmm.waveOutSetVolume(0, vol | (vol << 16))
            except Exception:
                pass
            _winsound.PlaySound(path, _winsound.SND_FILENAME)

        threading.Thread(target=_play, daemon=True).start()

    def _add_notification(self, query_name: str, message: str = "", system: bool = False,
                          added: int = None, removed: int = None):
        if not system and not self._should_notify(query_name):
            return
        self._notification_counter += 1
        ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        entry = {
            "id":         self._notification_counter,
            "query_name": query_name,
            "timestamp":  ts,
            "read":       False,
            "message":    message,
        }
        if added is not None:
            entry["added"]   = added
            entry["removed"] = removed
        self._notifications.append(entry)
        self.set_notification_badge(True)
        self.refresh_notifications_list()
        self._schedule_notif_rotation()
        return self._notification_counter

    def _mark_notif_read(self, notif_id: int):
        self._highlight_notif_id = None  # не перезапускать мигание при нажатии «Прочитать»
        for n in self._notifications:
            if n["id"] == notif_id:
                n["read"] = True
                break
        if all(n["read"] for n in self._notifications):
            self.set_notification_badge(False)
        else:
            self.set_notification_badge(True)
        self._update_notif_read_state(notif_id)

    def _mark_notif_unread(self, notif_id: int):
        for n in self._notifications:
            if n["id"] == notif_id:
                n["read"] = False
                break
        self.set_notification_badge(True)
        self._update_notif_read_state(notif_id)

    def _update_notif_read_state(self, notif_id: int):
        """Быстрое обновление цвета строки и кнопки без пересоздания всего списка."""
        row_data = self._notif_row_widgets.get(notif_id)
        if not row_data:
            self.refresh_notifications_list()
            return
        widgets, bg = row_data
        n = next((x for x in self._notifications if x["id"] == notif_id), None)
        if not n:
            self.refresh_notifications_list()
            return

        read = n["read"]
        dim  = ("gray55", "gray65")
        norm = ("gray10", "white")

        # Для уведомлений с цветными (+/-) метками, при снятии прочтения
        # нужно восстанавливать green/red — делаем полный перерисов (редкий случай)
        if n.get("added") is not None and not read:
            self.refresh_notifications_list()
            return

        tc = dim if read else norm
        for w in widgets:
            try:
                w.configure(text_color=tc)
            except Exception:
                # CTkFrame (msg_frame для "added") — обновляем дочерние метки
                if isinstance(w, ctk.CTkFrame):
                    for child in w.winfo_children():
                        try:
                            child.configure(text_color=tc)
                        except Exception:
                            pass

        btn = self._notif_action_btns.get(notif_id)
        if btn:
            if read:
                btn.configure(
                    text="Не прочитано",
                    fg_color="transparent",
                    border_width=1,
                    border_color=("gray55", "gray45"),
                    hover_color=("gray80", "gray30"),
                    text_color=("gray50", "gray60"),
                    command=lambda nid=notif_id: self._mark_notif_unread(nid),
                )
            else:
                btn.configure(
                    text="◎ Прочитать",
                    fg_color=[theme_colors.accent(), theme_colors.hover()],
                    hover_color=[theme_colors.hover(), theme_colors.dark()],
                    text_color=("gray10", "white"),
                    border_width=0,
                    command=lambda nid=notif_id: self._mark_notif_read(nid),
                )

    def _mark_all_read(self):
        self._highlight_notif_id = None
        for n in self._notifications:
            n["read"] = True
        self.set_notification_badge(False)
        self.refresh_notifications_list()

    def _delete_all_notifications(self):
        self._highlight_notif_id = None
        self._notifications.clear()
        self.set_notification_badge(False)
        self.refresh_notifications_list()

    def _schedule_notif_rotation(self):
        minutes = self.settings_manager.get_setting("notif_rotation_minutes", 0)
        if not minutes or minutes <= 0:
            return
        if self._notif_rotation_after_id is not None:
            try:
                self.after_cancel(self._notif_rotation_after_id)
            except Exception:
                pass
        self._notif_rotation_after_id = self.after(
            minutes * 60_000, self._run_notif_rotation)

    def _run_notif_rotation(self):
        self._notif_rotation_after_id = None
        self._notifications.clear()
        self.set_notification_badge(False)
        self.refresh_notifications_list()

    def _apply_notif_rotation(self):
        val = self.notif_rotation_entry.get().strip()
        try:
            minutes = int(val) if val else 0
            if minutes < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 0")
            return
        self.settings_manager.set_setting("notif_rotation_minutes", minutes)
        self._schedule_notif_rotation()
        self.log_manager.add_log(
            f"Ротация уведомлений: {minutes if minutes else 'выключена'}"
            + (f" мин." if minutes else ""))

    def _on_volume_slider_change(self, value: float):
        vol = round(value)
        self.settings_manager.set_setting("notification_volume", vol)
        if hasattr(self, "_vol_value_label"):
            self._vol_value_label.configure(text=f"{vol}%")

    # ── Вкладка «Уведомления» ─────────────────────────────────────────────────

    def setup_notifications_tab(self):
        self.frame_notifications.grid_columnconfigure(0, weight=1)
        self.frame_notifications.grid_rowconfigure(1, weight=1)
        self.frame_notifications.grid_rowconfigure(2, weight=0)

        self._notif_copy_fn = None
        self._notif_focus_trap = tk.Text(
            self.frame_notifications, height=1, width=1,
            relief="flat", borderwidth=0,
        )
        self._notif_focus_trap.place(x=-200, y=-200)

        def _trap_copy(e=None):
            fn = self._notif_copy_fn
            if fn:
                fn(e)
            return "break"

        def _trap_copy_ru(e=None):
            if e and e.keycode == 67:  # physical C key — same as Russian С
                fn = self._notif_copy_fn
                if fn:
                    fn(e)
            return "break"

        self._notif_focus_trap.bind("<Control-c>", _trap_copy)
        self._notif_focus_trap.bind("<Control-C>", _trap_copy)
        self._notif_focus_trap.bind("<Control-KeyPress>", _trap_copy_ru)

        toolbar = ctk.CTkFrame(self.frame_notifications, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")

        ctk.CTkButton(
            toolbar, text="✓ Прочитать все",
            command=self._mark_all_read,
            width=140, height=32,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            toolbar, text="✕ Удалить все",
            command=self._delete_all_notifications,
            width=130, height=32,
            fg_color=("#E53935", "#C62828"),
            hover_color=("#C62828", "#B71C1C"),
        ).pack(side="left", padx=(0, 6))

        self._alert_hist_btn = ctk.CTkButton(
            toolbar, text="▼ История алертов",
            command=self._toggle_alert_history_panel,
            width=160, height=32,
        )
        self._alert_hist_btn.pack(side="left")

        self._notifications_scroll = ctk.CTkScrollableFrame(
            self.frame_notifications, fg_color="transparent")
        self._notifications_scroll.grid(
            row=1, column=0, padx=10, pady=10, sticky="nsew")
        self._notifications_scroll.grid_columnconfigure(0, weight=1)

        # ── История алертов (скрыта по умолчанию) ────────────────────────────
        self._alert_hist_visible = False
        self._alert_hist_frame = ctk.CTkFrame(
            self.frame_notifications, fg_color="transparent", height=1)
        self._alert_hist_frame.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="nsew")
        self._alert_hist_frame.grid_columnconfigure(0, weight=1)
        self._alert_hist_frame.grid_rowconfigure(1, weight=1)
        self._alert_hist_frame.grid_remove()

        hist_toolbar = ctk.CTkFrame(self._alert_hist_frame, fg_color="transparent", height=1)
        hist_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(
            hist_toolbar, text="История алертов",
            font=ctk.CTkFont(weight="bold", size=13),
        ).pack(side="left")
        ctk.CTkButton(
            hist_toolbar, text="✕ Очистить", command=self._clear_alert_history,
            width=100, height=26,
            fg_color=("#E53935", "#C62828"),
            hover_color=("#C62828", "#B71C1C"),
        ).pack(side="right")

        self._alert_hist_scroll = ctk.CTkScrollableFrame(
            self._alert_hist_frame, fg_color="transparent", height=200)
        self._alert_hist_scroll.grid(row=1, column=0, sticky="ew")
        self._alert_hist_scroll.grid_columnconfigure(0, weight=1)

        self._render_alert_history()
        self.refresh_notifications_list()

    def refresh_notifications_list(self):
        if not hasattr(self, "_notifications_scroll"):
            return
        scroll = self._notifications_scroll
        for w in scroll.winfo_children():
            w.destroy()

        if not self._notifications:
            ctk.CTkLabel(
                scroll,
                text="Нет уведомлений",
                font=ctk.CTkFont(size=14),
                text_color=("gray50", "gray60"),
            ).grid(row=0, column=0, padx=20, pady=40)
            return

        HDR_BG    = ("gray78", "gray25")
        bold      = ctk.CTkFont(weight="bold")
        N_HEADERS = ("ID уведомления", "SQL-запрос", "Сообщение", "Время", "")
        N_WEIGHTS = (0, 0, 1, 0, 0)
        N_MIN_W   = (130, 150, 250, 155, 110)

        tbl = ctk.CTkFrame(scroll, fg_color="transparent")
        tbl.grid(row=0, column=0, sticky="ew")
        scroll.grid_columnconfigure(0, weight=1)

        for i, (h, wt, mw) in enumerate(zip(N_HEADERS, N_WEIGHTS, N_MIN_W)):
            tbl.grid_columnconfigure(i, weight=wt, minsize=mw)
            ctk.CTkLabel(tbl, text=h, font=bold if h else None,
                         anchor="w", fg_color=HDR_BG).grid(
                row=0, column=i, padx=6, pady=5, sticky="nsew")

        self._notif_row_widgets.clear()
        self._notif_action_btns.clear()

        # ── копирование строки Ctrl+C / Ctrl+С (рус.) ────────────────────────
        _NOTIF_SEL = ("#B2DFDB", "#1A4A48")

        def _notif_text(n) -> str:
            if n.get("added") is not None:
                msg = (f"Изменение результата запроса {n['query_name']}, "
                       f"добавлено новых +{n['added']} записей, "
                       f"исключено -{n['removed']} записей")
            else:
                msg = n.get("message", "")
            return f"{n['id']}\t{n['query_name']}\t{msg}\t{n['timestamp']}"

        def _notif_copy(event=None):
            nid = self._selected_notif_id
            if nid is None:
                return "break"
            n = next((x for x in self._notifications if x["id"] == nid), None)
            if n:
                self.clipboard_clear()
                self.clipboard_append(_notif_text(n))
            return "break"

        self._notif_copy_fn = _notif_copy

        def _notif_select(nid, rws):
            prev = self._selected_notif_id
            if prev is not None and prev in self._notif_row_widgets:
                prev_ws, prev_bg = self._notif_row_widgets[prev]
                for w in prev_ws:
                    try:
                        w.configure(fg_color=prev_bg)
                    except Exception:
                        pass
            self._selected_notif_id = nid
            for w in rws:
                try:
                    w.configure(fg_color=_NOTIF_SEL)
                except Exception:
                    pass
            if hasattr(self, "_notif_focus_trap"):
                self._notif_focus_trap.focus_force()

        for row_idx, notif in enumerate(reversed(self._notifications)):
            r    = row_idx + 1
            bg   = ("gray88", "gray20") if row_idx % 2 == 0 else ("gray83", "gray17")
            read = notif["read"]
            dim  = ("gray55", "gray65")
            norm = ("gray10", "white")
            tc   = dim if read else norm
            row_ws = []

            lbl_id = ctk.CTkLabel(tbl, text=str(notif['id']),
                                  fg_color=bg, anchor="w", text_color=tc)
            lbl_id.grid(row=r, column=0, padx=6, pady=3, sticky="nsew")
            row_ws.append(lbl_id)

            lbl_qn = ctk.CTkLabel(tbl, text=notif["query_name"],
                                  fg_color=bg, anchor="w", text_color=tc)
            lbl_qn.grid(row=r, column=1, padx=6, pady=3, sticky="nsew")
            row_ws.append(lbl_qn)

            if notif.get("added") is not None:
                green = "#22C55E" if not read else dim
                red   = "#EF4444" if not read else dim
                msg_frame = ctk.CTkFrame(tbl, fg_color=bg)
                msg_frame.grid(row=r, column=2, padx=6, pady=3, sticky="nsew")
                row_ws.append(msg_frame)
                _lbl = lambda parent, text, color: ctk.CTkLabel(
                    parent, text=text, fg_color=bg, anchor="w", text_color=color)
                _lbl(msg_frame,
                     f"Изменение результата запроса {notif['query_name']}, добавлено новых ",
                     tc).grid(row=0, column=0, sticky="w")
                _lbl(msg_frame, f"+ {notif['added']}", green).grid(row=0, column=1, sticky="w")
                _lbl(msg_frame, " записей, исключено ", tc).grid(row=0, column=2, sticky="w")
                _lbl(msg_frame, f"- {notif['removed']}", red).grid(row=0, column=3, sticky="w")
                _lbl(msg_frame, " записей", tc).grid(row=0, column=4, sticky="w")
            else:
                lbl_msg = ctk.CTkLabel(tbl, text=notif.get("message", ""),
                                       fg_color=bg, anchor="w", text_color=tc,
                                       wraplength=0)
                lbl_msg.grid(row=r, column=2, padx=6, pady=3, sticky="nsew")
                row_ws.append(lbl_msg)

            lbl_ts = ctk.CTkLabel(tbl, text=notif["timestamp"],
                                  fg_color=bg, anchor="w", text_color=tc)
            lbl_ts.grid(row=r, column=3, padx=6, pady=3, sticky="nsew")
            row_ws.append(lbl_ts)

            self._notif_row_widgets[notif['id']] = (row_ws, bg)

            # клик по строке → выделение + Ctrl+C готов к копированию
            _sh = (lambda _nid=notif["id"], _rws=list(row_ws):
                   lambda e=None: _notif_select(_nid, _rws))()
            for _w in row_ws:
                if isinstance(_w, ctk.CTkFrame):
                    for _ch in _w.winfo_children():
                        try:
                            _ch.bind("<Button-1>", _sh)
                        except Exception:
                            pass
                try:
                    _w.bind("<Button-1>", _sh)
                except Exception:
                    pass

            if read:
                _action_btn = ctk.CTkButton(
                    tbl,
                    text="Не прочитано",
                    width=110, height=26,
                    fg_color="transparent",
                    border_width=1,
                    border_color=("gray55", "gray45"),
                    hover_color=("gray80", "gray30"),
                    text_color=("gray50", "gray60"),
                    command=lambda nid=notif["id"]: self._mark_notif_unread(nid),
                )
            else:
                _action_btn = ctk.CTkButton(
                    tbl,
                    text="◎ Прочитать",
                    width=110, height=26,
                    fg_color=[theme_colors.accent(), theme_colors.hover()],
                    hover_color=[theme_colors.hover(), theme_colors.dark()],
                    text_color=("gray10", "white"),
                    border_width=0,
                    command=lambda nid=notif["id"]: self._mark_notif_read(nid),
                )
            _action_btn.grid(row=r, column=4, padx=6, pady=3)
            self._notif_action_btns[notif["id"]] = _action_btn

        # восстанавливаем выделение если строка ещё существует после перерисовки
        if self._selected_notif_id is not None:
            if self._selected_notif_id in self._notif_row_widgets:
                for _w in self._notif_row_widgets[self._selected_notif_id][0]:
                    try:
                        _w.configure(fg_color=_NOTIF_SEL)
                    except Exception:
                        pass
            else:
                self._selected_notif_id = None

        if self._highlight_notif_id is not None:
            nid = self._highlight_notif_id
            self.after(80, lambda: self._blink_notif_row(nid, 12))

    def _blink_notif_row(self, notif_id: int, step: int):
        """Мигает строкой уведомления: 12 шагов × 250 мс = 3 секунды."""
        row_data = self._notif_row_widgets.get(notif_id)
        if not row_data:
            self._highlight_notif_id = None
            return
        widgets, orig_bg = row_data
        if step <= 0:
            for w in widgets:
                try:
                    w.configure(fg_color=orig_bg)
                except Exception:
                    pass
            self._highlight_notif_id = None
            return
        color = "#0D9488" if step % 2 == 0 else orig_bg
        for w in widgets:
            try:
                w.configure(fg_color=color)
            except Exception:
                pass
        self.after(500, lambda: self._blink_notif_row(notif_id, step - 1))

    # ── Настройка уведомлений: список запросов с чекбоксами ───────────────────

    def _refresh_notif_query_checkboxes(self):
        if not hasattr(self, "_notif_query_list_container"):
            return
        container = self._notif_query_list_container
        for w in container.winfo_children():
            w.destroy()

        row = 0

        # ── Список уведомлений (фиксированные типы) ───────────────────────────
        sound_enabled = self.settings_manager.get_setting("notif_sound_types", "ALL")
        sound_all     = (sound_enabled == "ALL")
        sound_list    = sound_enabled if isinstance(sound_enabled, list) else []

        for type_key, type_label in _NOTIF_SOUND_TYPES:
            checked = sound_all or type_key in sound_list
            var = ctk.BooleanVar(value=checked)

            def on_sound_toggle(key=type_key, v=var):
                cur = self.settings_manager.get_setting("notif_sound_types", "ALL")
                if cur == "ALL":
                    cur = [k for k, _ in _NOTIF_SOUND_TYPES]
                if not isinstance(cur, list):
                    cur = []
                if v.get():
                    if key not in cur:
                        cur.append(key)
                else:
                    cur = [x for x in cur if x != key]
                if set(cur) == {k for k, _ in _NOTIF_SOUND_TYPES}:
                    cur = "ALL"
                self.settings_manager.set_setting("notif_sound_types", cur)

            ctk.CTkCheckBox(
                container, text=type_label, variable=var,
                command=on_sound_toggle,
            ).grid(row=row, column=0, padx=(20, 8), pady=2, sticky="w")
            row += 1

        # ── Разделитель ────────────────────────────────────────────────────────
        ctk.CTkFrame(
            container, height=1, fg_color=("gray70", "gray35"),
        ).grid(row=row, column=0, sticky="ew", pady=(8, 6))
        row += 1

        # ── SQL-запросы ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            container, text="SQL-запросы (запись в панель уведомлений):",
            font=ctk.CTkFont(weight="bold"), anchor="w",
        ).grid(row=row, column=0, pady=(0, 4), sticky="w")
        row += 1

        enabled      = self.settings_manager.get_setting("notif_enabled_queries", "ALL")
        all_selected = (enabled == "ALL")
        self._notif_all_var = ctk.BooleanVar(value=all_selected)

        def on_all_toggle():
            if self._notif_all_var.get():
                self.settings_manager.set_setting("notif_enabled_queries", "ALL")
            else:
                self.settings_manager.set_setting("notif_enabled_queries", [])
            self._refresh_notif_query_checkboxes()

        ctk.CTkCheckBox(
            container, text="Все запросы",
            variable=self._notif_all_var,
            command=on_all_toggle,
        ).grid(row=row, column=0, padx=(0, 8), pady=(0, 4), sticky="w")
        row += 1

        query_names  = self._get_query_names()
        enabled_list = enabled if isinstance(enabled, list) else []

        for qname in query_names:
            checked = all_selected or qname in enabled_list
            var = ctk.BooleanVar(value=checked)

            def on_q_toggle(name=qname, v=var):
                cur = self.settings_manager.get_setting("notif_enabled_queries", [])
                if not isinstance(cur, list):
                    cur = []
                if v.get():
                    if name not in cur:
                        cur.append(name)
                else:
                    cur = [x for x in cur if x != name]
                self.settings_manager.set_setting("notif_enabled_queries", cur)

            cb = ctk.CTkCheckBox(
                container, text=qname, variable=var, command=on_q_toggle)
            if all_selected:
                cb.configure(state="disabled")
            cb.grid(row=row, column=0, padx=(20, 8), pady=2, sticky="w")
            row += 1
