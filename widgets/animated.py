import tkinter as tk
import tkinter.font as tkfont
import customtkinter as ctk
import math
import datetime
from typing import Optional


_VIZ_COLOR_MAP = {
    "Бирюзовый":      "#0D9488",
    "Оранжевый":      "#E67E22",
    "Синий":          "#2E86C1",
    "Зелёный":        "#27AE60",
    "Красный":        "#C0392B",
    "Светлый/Тёмный": "auto",
}
_VIZ_TYPES = ["Стандартный", "Индикатор 2 (Тепловой)",
               "Индикатор 1", "Индикатор 2", "Индикатор - круги", "Светофор",
               "Секундомер", "Волна", "Пламя", "ЭКГ", "Кольца"]


def _viz_bg() -> str:
    return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#e8e8e8"


def _viz_fg() -> str:
    return "#e0e0e0" if ctk.get_appearance_mode() == "Dark" else "#1a1a1a"


class _AnimBase(tk.Frame):
    """Базовый анимированный виджет на Canvas (ease-out, ~60 fps)."""
    W, H = 200, 150

    def __init__(self, parent, label: str, color: str, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._label    = label
        self._color    = color
        self._target   = 0.0
        self._cur      = 0.0
        self._after_id = None
        self._canvas   = tk.Canvas(self, width=self.W, height=self.H,
                                   bg=bg, highlightthickness=0)
        self._canvas.pack()
        self._draw()

    def set_value(self, raw):
        try:
            self._target = float(str(raw).replace(",", "."))
        except (ValueError, TypeError):
            self._target = 0.0
        self._start_anim()

    def _start_anim(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._tick()

    def _tick(self):
        self._cur += (self._target - self._cur) * 0.12
        if abs(self._cur - self._target) < 0.01:
            self._cur = self._target
        self._draw()
        if abs(self._cur - self._target) > 0.01:
            self._after_id = self.after(16, self._tick)

    def _draw(self):
        pass

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class CounterWidget(_AnimBase):
    def _draw(self):
        c = self._canvas
        c.delete("all")
        bg = _viz_bg()
        c.configure(bg=bg)
        c.create_text(self.W // 2, 14, text=self._label, fill=_viz_fg(),
                      font=("Segoe UI", 9), anchor="n")
        c.create_text(self.W // 2, self.H // 2 + 12,
                      text=str(int(round(self._cur))),
                      fill=self._color, font=("Segoe UI", 36, "bold"), anchor="center")


class ProgressBarWidget(_AnimBase):
    def __init__(self, parent, label, color, min_val=0, max_val=100, **kw):
        self._min = float(min_val)
        self._max = float(max_val)
        super().__init__(parent, label, color, **kw)

    def _draw(self):
        c = self._canvas
        c.delete("all")
        bg = _viz_bg()
        c.configure(bg=bg)
        c.create_text(self.W // 2, 14, text=self._label, fill=_viz_fg(),
                      font=("Segoe UI", 9), anchor="n")
        pad = 18
        bx1, by1, bx2, by2 = pad, self.H // 2 - 12, self.W - pad, self.H // 2 + 12
        bar_bg = "#444444" if ctk.get_appearance_mode() == "Dark" else "#cccccc"
        c.create_rectangle(bx1, by1, bx2, by2, fill=bar_bg, outline="")
        rng  = max(self._max - self._min, 1.0)
        frac = max(0.0, min(1.0, (self._cur - self._min) / rng))
        if frac > 0:
            c.create_rectangle(bx1, by1, bx1 + frac * (bx2 - bx1), by2,
                                fill=self._color, outline="")
        c.create_text(self.W // 2, self.H // 2 + 26,
                      text=f"{self._cur:.0f}  ({frac*100:.0f}%)",
                      fill=self._color, font=("Segoe UI", 10, "bold"), anchor="n")


class GaugeWidget(_AnimBase):
    def __init__(self, parent, label, color, min_val=0, max_val=100, **kw):
        self._min = float(min_val)
        self._max = float(max_val)
        super().__init__(parent, label, color, **kw)

    def _draw(self):
        c = self._canvas
        c.delete("all")
        bg = _viz_bg()
        c.configure(bg=bg)
        c.create_text(self.W // 2, 10, text=self._label, fill=_viz_fg(),
                      font=("Segoe UI", 9), anchor="n")
        cx, cy = self.W // 2, self.H - 22
        r = min(cx - 8, cy - 4)
        track_col = "#444444" if ctk.get_appearance_mode() == "Dark" else "#cccccc"
        c.create_arc(cx - r, cy - r, cx + r, cy + r,
                     start=225, extent=-270, style="arc", outline=track_col, width=8)
        rng  = max(self._max - self._min, 1.0)
        frac = max(0.0, min(1.0, (self._cur - self._min) / rng))
        sweep = frac * 270
        if sweep > 0.5:
            c.create_arc(cx - r, cy - r, cx + r, cy + r,
                         start=225, extent=-sweep, style="arc",
                         outline=self._color, width=8)
        angle_deg = 225 - frac * 270
        angle_rad = math.radians(angle_deg)
        nr = r - 14
        nx = cx + nr * math.cos(angle_rad)
        ny = cy - nr * math.sin(angle_rad)
        c.create_line(cx, cy, nx, ny, fill=self._color, width=3)
        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=self._color, outline="")
        c.create_text(cx, cy - r // 2, text=f"{self._cur:.0f}",
                      fill=self._color, font=("Segoe UI", 18, "bold"), anchor="center")


class PulseTileWidget(tk.Frame):
    """Пульсирующая плитка — синусоидальный scale шрифта."""
    W, H = 200, 150
    # ~2 полных цикла синуса: 2 * 2π / 0.06 ≈ 209 тиков
    _PULSE_TICKS = 210

    def __init__(self, parent, label: str, color: str, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._label      = label
        self._color      = color
        self._value_str  = "—"
        self._phase      = 0.0
        self._after_id   = None
        self._tick_count = 0
        self._canvas     = tk.Canvas(self, width=self.W, height=self.H,
                                     bg=bg, highlightthickness=0)
        self._canvas.pack()
        self._draw()

    def set_value(self, raw):
        try:
            v = float(str(raw).replace(",", "."))
            self._value_str = str(int(v)) if v == int(v) else f"{v:.2f}"
        except (ValueError, TypeError):
            self._value_str = str(raw) if raw is not None else "—"
        self._tick_count = 0
        if not self._after_id:
            self._tick()

    def _tick(self):
        self._phase += 0.06
        self._tick_count += 1
        self._draw()
        if self._tick_count < self._PULSE_TICKS:
            self._after_id = self.after(16, self._tick)
        else:
            self._after_id = None
            self._phase = 0.0
            self._draw()

    def _draw(self):
        c = self._canvas
        c.delete("all")
        bg = _viz_bg()
        c.configure(bg=bg)
        c.create_text(self.W // 2, 14, text=self._label, fill=_viz_fg(),
                      font=("Segoe UI", 9), anchor="n")
        scale = 1.0 + 0.08 * math.sin(self._phase)
        size  = max(8, int(36 * scale))
        c.create_text(self.W // 2, self.H // 2 + 12, text=self._value_str,
                      fill=self._color, font=("Segoe UI", size, "bold"), anchor="center")

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class HeatmapTileWidget(tk.Frame):
    """Тепловая плитка — фон плавно меняется по порогам зелёный→жёлтый→красный."""
    W, H = 200, 150

    def __init__(self, parent, label: str, color: str, warn=50, crit=80, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._label     = label
        self._warn      = float(warn)
        self._crit      = float(crit)
        self._value_str = "—"
        self._cur_rgb   = (39, 174, 96)
        self._tgt_rgb   = (39, 174, 96)
        self._after_id  = None
        self._canvas    = tk.Canvas(self, width=self.W, height=self.H,
                                    bg=bg, highlightthickness=0)
        self._canvas.pack()
        self._draw()

    @staticmethod
    def _lerp(a, b, t):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    def set_value(self, raw):
        try:
            v = float(str(raw).replace(",", "."))
            self._value_str = str(int(v)) if v == int(v) else f"{v:.2f}"
            if v < self._warn:
                frac = max(0.0, v / max(self._warn, 1))
                self._tgt_rgb = self._lerp((39, 174, 96), (230, 126, 34), frac)
            elif v < self._crit:
                frac = (v - self._warn) / max(self._crit - self._warn, 1)
                self._tgt_rgb = self._lerp((230, 126, 34), (192, 57, 43), frac)
            else:
                self._tgt_rgb = (192, 57, 43)
        except (ValueError, TypeError):
            self._value_str = str(raw) if raw is not None else "—"
        if not self._after_id:
            self._tick()

    def _tick(self):
        cr, cg, cb = self._cur_rgb
        tr, tg, tb = self._tgt_rgb
        nr, ng, nb = cr + (tr - cr) * 0.08, cg + (tg - cg) * 0.08, cb + (tb - cb) * 0.08
        self._cur_rgb = (nr, ng, nb)
        self._draw()
        if abs(nr - tr) + abs(ng - tg) + abs(nb - tb) > 0.5:
            self._after_id = self.after(16, self._tick)
        else:
            self._cur_rgb = self._tgt_rgb
            self._after_id = None
            self._draw()

    def _draw(self):
        c = self._canvas
        c.delete("all")
        r, g, b = (int(x) for x in self._cur_rgb)
        bg_hex = f"#{r:02x}{g:02x}{b:02x}"
        c.configure(bg=bg_hex)
        c.create_rectangle(0, 0, self.W, self.H, fill=bg_hex, outline="")
        c.create_text(self.W // 2, 14, text=self._label, fill="#ffffff",
                      font=("Segoe UI", 9), anchor="n")
        c.create_text(self.W // 2, self.H // 2 + 12, text=self._value_str,
                      fill="#ffffff", font=("Segoe UI", 36, "bold"), anchor="center")

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class Display1Widget(tk.Frame):
    """Строчная анимация: значение + ■■■ (заполненные) и мигающий □ блок."""

    _BW = 10   # ширина одного блока, px
    _BH = 10   # высота блока, px
    _BG = 3    # зазор между блоками, px
    _CH = 24   # высота Canvas

    def __init__(self, parent, color: str = "#0D9488", max_blocks: int = 10,
                 speed: int = 650, text_offset: int = 0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._color       = color
        self._max_blocks  = max(1, int(max_blocks))
        self._blink_ms    = max(100, int(speed))
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._age         = 0
        self._blink_on    = True
        self._after_id    = None
        self._canvas      = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda _e: self._draw())
        self._tick()

    def set_value_and_age(self, value, age: int):
        self._value_str = "" if value is None else str(value)
        self._age = max(0, int(age))
        self._draw()

    def _effective_color(self) -> str:
        if self._color == "auto":
            return "#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a"
        return self._color

    def _tick(self):
        self._blink_on = not self._blink_on
        self._draw()
        try:
            self._after_id = self.after(self._blink_ms, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas
        c.delete("all")
        bg = _viz_bg()
        c.configure(bg=bg)
        color = self._effective_color()
        fg    = _viz_fg()
        cy    = self._CH // 2

        tid  = c.create_text(6, cy, text=self._value_str, anchor="w",
                             fill=fg, font=("Segoe UI", 10))
        if self._text_offset > 0:
            x = self._text_offset
        else:
            bbox = c.bbox(tid)
            x    = (bbox[2] + 10) if bbox else 70

        filled = min(self._age, self._max_blocks)
        by1    = cy - self._BH // 2
        by2    = cy + self._BH // 2

        for _ in range(filled):
            c.create_rectangle(x, by1, x + self._BW, by2, fill=color, outline="")
            x += self._BW + self._BG

        if self._blink_on:
            c.create_rectangle(x, by1, x + self._BW, by2, fill=color, outline="")
        else:
            c.create_rectangle(x, by1, x + self._BW, by2, fill="", outline=color, width=1)

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class Indicator2Widget(tk.Frame):
    """Горизонтальная полоса заполнения, растущая со временем."""
    _CH = 24

    def __init__(self, parent, color="#0D9488", max_units=10,
                 speed=650, text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._color       = color
        self._max_units   = max(1, int(max_units))
        self._blink_ms    = max(100, int(speed))
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._age         = 0
        self._blink_on    = True
        self._after_id    = None
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c
        self._tick()

    def set_value_and_age(self, value, age):
        self._value_str = "" if value is None else str(value)
        self._age = max(0, int(age))
        self._draw()

    def _eff_color(self):
        return ("#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a") \
               if self._color == "auto" else self._color

    def _tick(self):
        self._blink_on = not self._blink_on
        self._draw()
        try:
            self._after_id = self.after(self._blink_ms, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas; c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg)
        color = self._eff_color(); fg = _viz_fg()
        cy = self._CH // 2; cw = c.winfo_width()
        if cw < 20:
            return
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        bx = self._text_offset if self._text_offset > 0 else \
             ((c.bbox(tid)[2] + 8) if c.bbox(tid) else 70)
        bw = cw - bx - 6
        if bw < 8:
            return
        bh = 8; by1, by2 = cy - bh // 2, cy + bh // 2
        track = "#444" if ctk.get_appearance_mode() == "Dark" else "#ccc"
        c.create_rectangle(bx, by1, bx + bw, by2, fill=track, outline="")
        filled = min(self._age, self._max_units)
        fx = bx + int(bw * filled / self._max_units)
        if fx > bx:
            c.create_rectangle(bx, by1, fx, by2, fill=color, outline="")
        seg = max(4, bw // self._max_units)
        if fx + seg <= bx + bw:
            if self._blink_on:
                c.create_rectangle(fx, by1, fx + seg, by2, fill=color, outline="")
            else:
                c.create_rectangle(fx, by1, fx + seg, by2, fill="", outline=color, width=1)

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class TrafficWidget(tk.Frame):
    """Светофор: три кружка циклически мерцают по очереди."""
    _CH     = 24
    _LIGHTS = ["#27AE60", "#F39C12", "#C0392B"]  # зелёный, жёлтый, красный

    def __init__(self, parent, color="#0D9488", speed=500, interval_min=1.0,
                 text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._speed       = max(100, int(speed))
        self._interval_ms = max(1000, int(float(interval_min) * 60000))
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._phase       = 0    # 0=зелёный, 1=жёлтый, 2=красный
        self._blink_on    = True
        self._blink_id    = None
        self._phase_id    = None
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c
        self._tick_blink()
        self._tick_phase()

    def set_value(self, value):
        self._value_str = "" if value is None else str(value)
        self._draw()

    def set_value_and_elapsed(self, value, elapsed_minutes):
        self.set_value(value)

    def _tick_blink(self):
        self._blink_on = not self._blink_on
        self._draw()
        try:
            self._blink_id = self.after(self._speed, self._tick_blink)
        except Exception:
            pass

    def _tick_phase(self):
        self._phase = (self._phase + 1) % 3
        self._draw()
        try:
            self._phase_id = self.after(self._interval_ms, self._tick_phase)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas
        c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg)
        fg = _viz_fg()
        cy = self._CH // 2
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        x = self._text_offset if self._text_offset > 0 else \
            ((c.bbox(tid)[2] + 10) if c.bbox(tid) else 70)
        dim = "#555" if ctk.get_appearance_mode() == "Dark" else "#bbb"
        r = 5
        for i, bright in enumerate(self._LIGHTS):
            if i == self._phase:
                col = bright if self._blink_on else dim
            else:
                col = dim
            c.create_oval(x, cy - r, x + r * 2, cy + r, fill=col, outline="")
            x += r * 2 + 4

    def destroy(self):
        for aid in (self._blink_id, self._phase_id):
            if aid:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
        super().destroy()


class IndicatorCirclesWidget(tk.Frame):
    """Строчная анимация: значение + ●●● (заполненные кружки) и мигающий ○ кружок."""

    _BW = 10   # диаметр одного кружка, px
    _BG = 3    # зазор между кружками, px
    _CH = 24   # высота Canvas

    def __init__(self, parent, color: str = "#0D9488", max_blocks: int = 10,
                 speed: int = 650, text_offset: int = 0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._color       = color
        self._max_blocks  = max(1, int(max_blocks))
        self._blink_ms    = max(100, int(speed))
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._age         = 0
        self._blink_on    = True
        self._after_id    = None
        self._canvas      = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda _e: self._draw())
        self._tick()

    def set_value_and_age(self, value, age: int):
        self._value_str = "" if value is None else str(value)
        self._age = max(0, int(age))
        self._draw()

    def _effective_color(self) -> str:
        if self._color == "auto":
            return "#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a"
        return self._color

    def _tick(self):
        self._blink_on = not self._blink_on
        self._draw()
        try:
            self._after_id = self.after(self._blink_ms, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas
        c.delete("all")
        bg = _viz_bg()
        c.configure(bg=bg)
        color = self._effective_color()
        fg    = _viz_fg()
        cy    = self._CH // 2
        r     = self._BW // 2

        tid  = c.create_text(6, cy, text=self._value_str, anchor="w",
                             fill=fg, font=("Segoe UI", 10))
        if self._text_offset > 0:
            x = self._text_offset
        else:
            bbox = c.bbox(tid)
            x    = (bbox[2] + 10) if bbox else 70

        filled = min(self._age, self._max_blocks)

        for _ in range(filled):
            c.create_oval(x, cy - r, x + self._BW, cy + r, fill=color, outline="")
            x += self._BW + self._BG

        if self._blink_on:
            c.create_oval(x, cy - r, x + self._BW, cy + r, fill=color, outline="")
        else:
            c.create_oval(x, cy - r, x + self._BW, cy + r,
                          fill="", outline=color, width=1)

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class HeatTimeWidget(tk.Frame):
    """Индикатор 2 (Тепловой): полоса растёт со временем, цвет переходит холодный→тёплый→критический."""
    _CH = 24

    def __init__(self, parent, cold_color="#27AE60", warm_color="#E67E22",
                 crit_color="#C0392B", age_cold=10.0, age_warm=20.0, age_crit=40.0,
                 text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._cold        = cold_color
        self._warm        = warm_color
        self._crit        = crit_color
        self._age_cold    = max(0.1, float(age_cold))
        self._age_warm    = max(self._age_cold + 0.01, float(age_warm))
        self._age_crit    = max(self._age_warm + 0.01, float(age_crit))
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._elapsed     = 0.0
        self._first_seen: Optional[datetime.datetime] = None
        self._blink_on    = True
        self._after_id    = None
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c
        self._tick()

    def set_value_and_elapsed(self, value, elapsed_minutes,
                              first_seen: Optional[datetime.datetime] = None):
        self._value_str  = "" if value is None else str(value)
        self._elapsed    = max(0.0, float(elapsed_minutes))
        self._first_seen = first_seen
        self._draw()

    @staticmethod
    def _hex_to_rgb(hex_color):
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    @staticmethod
    def _blend(c1, c2, t):
        r1, g1, b1 = HeatTimeWidget._hex_to_rgb(c1)
        r2, g2, b2 = HeatTimeWidget._hex_to_rgb(c2)
        return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"

    def _color_at(self, elapsed):
        if elapsed <= self._age_cold:
            return self._cold
        if elapsed <= self._age_warm:
            t = (elapsed - self._age_cold) / (self._age_warm - self._age_cold)
            return self._blend(self._cold, self._warm, t)
        if elapsed <= self._age_crit:
            t = (elapsed - self._age_warm) / (self._age_crit - self._age_warm)
            return self._blend(self._warm, self._crit, t)
        return self._crit

    def _tick(self):
        self._blink_on = not self._blink_on
        self._draw()
        try:
            self._after_id = self.after(500, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas
        c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg)
        fg = _viz_fg()
        cy = self._CH // 2
        cw = c.winfo_width()
        if cw < 20:
            return
        elapsed = ((datetime.datetime.now() - self._first_seen).total_seconds() / 60.0
                   if self._first_seen is not None else self._elapsed)
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        bx = self._text_offset if self._text_offset > 0 else \
             ((c.bbox(tid)[2] + 8) if c.bbox(tid) else 70)
        bw = cw - bx - 6
        if bw < 8:
            return
        bh = 8
        by1, by2 = cy - bh // 2, cy + bh // 2
        track = "#444" if ctk.get_appearance_mode() == "Dark" else "#ccc"
        c.create_rectangle(bx, by1, bx + bw, by2, fill=track, outline="")
        progress   = min(1.0, elapsed / self._age_crit) if self._age_crit > 0 else 0.0
        fill_w     = int(bw * progress)
        fill_color = self._color_at(elapsed)
        if fill_w > 0:
            c.create_rectangle(bx, by1, bx + fill_w, by2, fill=fill_color, outline="")
        seg = max(4, bw // 20)
        cx0 = bx + fill_w
        if cx0 + seg <= bx + bw:
            if self._blink_on:
                c.create_rectangle(cx0, by1, cx0 + seg, by2, fill=fill_color, outline="")
            else:
                c.create_rectangle(cx0, by1, cx0 + seg, by2, fill="", outline=fill_color, width=1)

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class StopwatchWidget(tk.Frame):
    """Секундомер: значение + живой счётчик времени нахождения в фрейме."""
    _CH = 24

    def __init__(self, parent, color="#0D9488", first_seen=None,
                 age_threshold=0.0, age_color="", text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._base_color  = color
        self._first_seen  = first_seen
        self._age_thr     = float(age_threshold)
        self._age_cname   = age_color
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._after_id    = None
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c
        self._tick()

    def set_value(self, value):
        self._value_str = "" if value is None else str(value)
        self._draw()

    def _resolve_color(self):
        elapsed = (datetime.datetime.now() - self._first_seen).total_seconds() / 60.0 \
                  if self._first_seen else 0.0
        color = self._base_color
        if (self._age_thr > 0 and self._age_cname and self._age_cname != "(нет)"
                and self._first_seen and elapsed >= self._age_thr):
            color = _VIZ_COLOR_MAP.get(self._age_cname, color)
        return ("#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a") \
               if color == "auto" else color

    def _tick(self):
        self._draw()
        try:
            self._after_id = self.after(1000, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas; c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg); fg = _viz_fg()
        color = self._resolve_color(); cy = self._CH // 2
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        x = self._text_offset if self._text_offset > 0 else \
            ((c.bbox(tid)[2] + 8) if c.bbox(tid) else 70)
        if self._first_seen:
            es = int((datetime.datetime.now() - self._first_seen).total_seconds())
            h, r = divmod(es, 3600); m, s = divmod(r, 60)
            ts = f"+{h:02d}:{m:02d}:{s:02d}" if h else f"+{m:02d}:{s:02d}"
        else:
            ts = "+00:00"
        c.create_text(x, cy, text=ts, anchor="w",
                      fill=color, font=("Segoe UI", 10, "bold"))

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class WaveWidget(tk.Frame):
    """Волна: анимированная синусоида, амплитуда растёт со временем."""
    _CH = 28

    def __init__(self, parent, color="#0D9488", max_amplitude=10,
                 speed=40, age=0, text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._color       = color
        self._max_amp     = max(2, int(max_amplitude))
        self._speed_ms    = max(20, int(speed))
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._age         = max(0, int(age))
        self._phase       = 0.0
        self._after_id    = None
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c
        self._tick()

    def set_value_and_age(self, value, age):
        self._value_str = "" if value is None else str(value)
        self._age = max(0, int(age))

    def _eff_color(self):
        return ("#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a") \
               if self._color == "auto" else self._color

    def _tick(self):
        self._phase += 0.18
        self._draw()
        try:
            self._after_id = self.after(self._speed_ms, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas; c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg)
        color = self._eff_color(); fg = _viz_fg()
        cy = self._CH // 2; cw = c.winfo_width()
        if cw < 20:
            return
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        wx = self._text_offset if self._text_offset > 0 else \
             ((c.bbox(tid)[2] + 8) if c.bbox(tid) else 70)
        ww = cw - wx - 4
        if ww < 10:
            return
        amp = max(1, int(self._max_amp * min(1.0, (self._age + 1) / max(self._max_amp, 1))))
        steps = max(ww // 2, 4)
        pts = []
        for i in range(steps + 1):
            x = wx + i * ww // steps
            y = cy + int(amp * math.sin(self._phase + i * 2 * math.pi * 2 / steps))
            pts.extend([x, y])
        if len(pts) >= 4:
            c.create_line(*pts, fill=color, width=2, smooth=True)

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class FlameWidget(tk.Frame):
    """Пламя: символы ░▒▓█ накапливаются со временем, последний мерцает."""
    _CHARS = "░▒▓█"
    _CH    = 24

    def __init__(self, parent, color="#E67E22", max_chars=10,
                 speed=500, text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._color       = color
        self._max_chars   = max(1, int(max_chars))
        self._blink_ms    = max(100, int(speed))
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._age         = 0
        self._blink_on    = True
        self._after_id    = None
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c
        self._tick()

    def set_value_and_age(self, value, age):
        self._value_str = "" if value is None else str(value)
        self._age = max(0, int(age))
        self._draw()

    def _eff_color(self):
        return ("#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a") \
               if self._color == "auto" else self._color

    def _tick(self):
        self._blink_on = not self._blink_on
        self._draw()
        try:
            self._after_id = self.after(self._blink_ms, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas; c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg)
        color = self._eff_color(); fg = _viz_fg(); cy = self._CH // 2
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        x = self._text_offset if self._text_offset > 0 else \
            ((c.bbox(tid)[2] + 8) if c.bbox(tid) else 70)
        filled = min(self._age, self._max_chars)
        body   = self._CHARS[-1] * filled
        tip    = self._CHARS[-1] if self._blink_on else self._CHARS[-2]
        c.create_text(x, cy, text=body + tip, anchor="w",
                      fill=color, font=("Consolas", 11))

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class EcgWidget(tk.Frame):
    """ЭКГ: анимированная пульс-линия, постепенно затухает со временем."""
    _CH   = 28
    _HIST = 50

    def __init__(self, parent, color="#0D9488", speed=40, fade_minutes=10.0,
                 first_seen=None, text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._color        = color
        self._speed_ms     = max(20, int(speed))
        self._fade_min     = max(0.1, float(fade_minutes))
        self._first_seen   = first_seen
        self._text_offset  = max(0, int(text_offset))
        self._value_str    = ""
        self._phase        = 0.0
        self._hist         = [0.0] * self._HIST
        self._after_id     = None
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c
        self._tick()

    def set_value(self, value):
        self._value_str = "" if value is None else str(value)

    def _eff_color(self):
        return ("#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a") \
               if self._color == "auto" else self._color

    def _tick(self):
        self._phase += 0.3
        cycle = int(self._phase * 4) % 25
        val   = 1.0 if cycle == 12 else (-0.5 if cycle == 13 else
                (0.25 if cycle == 14 else math.sin(self._phase * 0.4) * 0.08))
        self._hist.append(val)
        self._hist = self._hist[-self._HIST:]
        self._draw()
        try:
            self._after_id = self.after(self._speed_ms, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas; c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg); fg = _viz_fg()
        cy = self._CH // 2; cw = c.winfo_width()
        if cw < 20:
            return
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        wx = self._text_offset if self._text_offset > 0 else \
             ((c.bbox(tid)[2] + 8) if c.bbox(tid) else 70)
        ww = cw - wx - 4
        if ww < 10:
            return
        alpha = 1.0
        if self._first_seen:
            el = (datetime.datetime.now() - self._first_seen).total_seconds() / 60.0
            alpha = max(0.05, 1.0 - el / self._fade_min)
        color = self._eff_color()
        try:
            bgi = tuple(int(bg[i:i+2], 16) for i in (1, 3, 5))
            ci  = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
            rc  = tuple(int(ci[j] * alpha + bgi[j] * (1 - alpha)) for j in range(3))
            faded = f"#{rc[0]:02x}{rc[1]:02x}{rc[2]:02x}"
        except Exception:
            faded = color
        n = len(self._hist)
        pts = []
        for i, v in enumerate(self._hist):
            pts.extend([wx + i * ww // max(n - 1, 1),
                        cy - int(v * 11)])
        if len(pts) >= 4:
            c.create_line(*pts, fill=faded, width=2)

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class RingsWidget(tk.Frame):
    """Кольца: концентрические кольца, новое появляется каждый интервал."""
    _CH = 30

    def __init__(self, parent, color="#0D9488", max_rings=5,
                 speed=80, age=0, text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._color       = color
        self._max_rings   = max(1, int(max_rings))
        self._speed_ms    = max(20, int(speed))
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._age         = max(0, int(age))
        self._t           = 0
        self._after_id    = None
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c
        self._tick()

    def set_value_and_age(self, value, age):
        self._value_str = "" if value is None else str(value)
        self._age = max(0, int(age))

    def _eff_color(self):
        return ("#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a") \
               if self._color == "auto" else self._color

    def _tick(self):
        self._t += 1
        self._draw()
        try:
            self._after_id = self.after(self._speed_ms, self._tick)
        except Exception:
            pass

    def _draw(self):
        c = self._canvas; c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg); fg = _viz_fg()
        cy = self._CH // 2; cw = c.winfo_width()
        if cw < 20:
            return
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        cx0 = (self._text_offset + 14) if self._text_offset > 0 else \
              ((c.bbox(tid)[2] + 18) if c.bbox(tid) else 84)
        color = self._eff_color()
        n = min(self._age + 1, self._max_rings + 1)
        period = 40
        for i in range(n):
            phase = (self._t + i * (period // max(n, 1))) % period
            r     = max(2, int((phase / period) * (cy - 2)))
            alpha = max(0.0, 1.0 - phase / period)
            try:
                bgi = tuple(int(bg[j:j+2], 16)    for j in (1, 3, 5))
                ci  = tuple(int(color[j:j+2], 16)  for j in (1, 3, 5))
                rc  = tuple(int(ci[k] * alpha + bgi[k] * (1 - alpha)) for k in range(3))
                clr = f"#{rc[0]:02x}{rc[1]:02x}{rc[2]:02x}"
            except Exception:
                clr = color
            c.create_oval(cx0 - r, cy - r, cx0 + r, cy + r,
                          outline=clr, width=1, fill="")

    def destroy(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


class DeltaWidget(tk.Frame):
    """Дельта: значение + стрелка изменения ▲ / ▼ / — относительно прошлого обновления."""
    _CH = 24

    def __init__(self, parent, color_up="#27AE60", color_down="#C0392B",
                 color_same="#808080", text_offset=0, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._color_up    = color_up
        self._color_down  = color_down
        self._color_same  = color_same
        self._text_offset = max(0, int(text_offset))
        self._value_str   = ""
        self._delta       = 0
        c = tk.Canvas(self, bg=bg, highlightthickness=0, height=self._CH)
        c.pack(fill="both", expand=True)
        c.bind("<Configure>", lambda _e: self._draw())
        self._canvas = c

    def set_value_and_delta(self, value, delta: int):
        self._value_str = "" if value is None else str(value)
        self._delta = delta
        self._draw()

    def _draw(self):
        c = self._canvas; c.delete("all")
        bg = _viz_bg(); c.configure(bg=bg); fg = _viz_fg()
        cy = self._CH // 2
        tid = c.create_text(6, cy, text=self._value_str, anchor="w",
                            fill=fg, font=("Segoe UI", 10))
        x = self._text_offset if self._text_offset > 0 else \
            ((c.bbox(tid)[2] + 8) if c.bbox(tid) else 70)
        if self._delta > 0:
            arrow, color = "▲", self._color_up
        elif self._delta < 0:
            arrow, color = "▼", self._color_down
        else:
            arrow, color = "—", self._color_same
        if color == "auto":
            color = "#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a"
        c.create_text(x, cy, text=arrow, anchor="w",
                      fill=color, font=("Segoe UI", 12, "bold"))


def _make_compact_cell(parent, vtype: str, color: str, value, cfg: dict):
    """Компактный виджет для одной ячейки строки в AnimatedPanel."""
    if color == "auto":
        color = "#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a"
    val_str = "NULL" if value is None else str(value)

    if vtype == "Счётчик":
        return ctk.CTkLabel(parent, text=val_str, anchor="w",
                            text_color=color, font=ctk.CTkFont(size=11, weight="bold"))

    elif vtype == "Прогресс-бар":
        min_v, max_v = cfg.get("min", 0), cfg.get("max", 100)
        try:
            v    = float(str(value).replace(",", "."))
            frac = max(0.0, min(1.0, (v - min_v) / max(max_v - min_v, 1)))
        except (ValueError, TypeError):
            frac = 0.0
        filled = int(frac * 8)
        bar    = "█" * filled + "░" * (8 - filled)
        return ctk.CTkLabel(parent, text=f"{bar}  {val_str}", anchor="w",
                            text_color=color, font=ctk.CTkFont(family="Consolas", size=10))

    elif vtype in ("Спидометр", "Пульс"):
        return ctk.CTkLabel(parent, text=val_str, anchor="w",
                            text_color=color, font=ctk.CTkFont(size=11, weight="bold"))

    elif vtype == "Индикатор 2 (Тепловой)":
        return ctk.CTkLabel(parent, text=val_str, anchor="w",
                            font=ctk.CTkFont(size=10))

    else:
        return ctk.CTkLabel(parent, text=val_str, anchor="w",
                            font=ctk.CTkFont(size=10))


def _cancel_widget_timers(widget):
    """Рекурсивно отменяет all after_id у виджета и его потомков."""
    if hasattr(widget, '_after_id') and widget._after_id:
        try:
            widget.after_cancel(widget._after_id)
        except Exception:
            pass
        widget._after_id = None
    try:
        for child in widget.winfo_children():
            _cancel_widget_timers(child)
    except Exception:
        pass


def _bind_cell_select(widget, value: str, panel: "AnimatedPanel") -> None:
    """Рекурсивно привязывает <ButtonPress-1> к виджету и его потомкам.
    При клике сохраняет значение ячейки в panel._selected_value (BUG-66)."""
    def _on_click(event=None, v=value, p=panel):
        p._selected_value = v
        if p._cell_info_lbl is not None:
            try:
                display = v[:60] + ("…" if len(v) > 60 else "")
                p._cell_info_lbl.configure(
                    text=("> " + display) if display else "> (пусто)")
            except Exception:
                pass
    widget.bind("<ButtonPress-1>", _on_click, add="+")
    try:
        for child in widget.winfo_children():
            _bind_cell_select(child, value, panel)
    except Exception:
        pass


class AnimatedPanel(tk.Frame):
    """Прокручиваемая таблица с визуализацией по всем строкам результата."""

    _MAX_ROWS = 50

    def __init__(self, parent, **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._sf = None
        self._selected_value = None   # str | None; None — ячейка не выбрана
        self._cell_info_lbl = None
        self._top_bound = False

    def render(self, rows: list, columns: list, viz_configs: dict,
               age_data: dict = None, delta_data: dict = None):
        if self._sf is not None:
            _cancel_widget_timers(self._sf)
            try:
                self._sf.destroy()
            except Exception:
                pass
            self._sf = None
        self._selected_value = None
        self._cell_info_lbl = None

        bg = _viz_bg()
        self.configure(bg=bg)
        if not columns:
            return

        age_data      = age_data or {}
        delta_data    = delta_data or {}
        display_rows  = rows[:self._MAX_ROWS]
        ncols         = len(columns)

        sf = ctk.CTkScrollableFrame(self, fg_color=("gray87", "#272727"))
        sf.grid(row=0, column=0, sticky="nsew")
        self._sf = sf
        # col 0 = bulb (FEAT-18), col 1 = №, cols 2..ncols+1 = data, col ncols+2 = copy
        sf.grid_columnconfigure(0, weight=0, minsize=24)
        sf.grid_columnconfigure(1, weight=0, minsize=40)
        for ci in range(ncols):
            sf.grid_columnconfigure(ci + 2, weight=1)
        sf.grid_columnconfigure(ncols + 2, weight=0, minsize=32)

        # Строка заголовков
        ctk.CTkLabel(sf, text="", anchor="center",
                     font=ctk.CTkFont(size=10)
                     ).grid(row=0, column=0, padx=(2, 1), pady=(4, 1))
        ctk.CTkLabel(sf, text="№", anchor="e",
                     font=ctk.CTkFont(size=10, weight="bold")
                     ).grid(row=0, column=1, sticky="ew", padx=(2, 4), pady=(4, 1))
        for ci, col_name in enumerate(columns):
            ctk.CTkLabel(sf, text=col_name, anchor="w",
                         font=ctk.CTkFont(size=10, weight="bold")
                         ).grid(row=0, column=ci + 2, sticky="ew", padx=(6, 2), pady=(4, 1))
        ctk.CTkLabel(sf, text="⎘", anchor="center",
                     font=ctk.CTkFont(size=11)
                     ).grid(row=0, column=ncols + 2, padx=(2, 4), pady=(4, 1))

        ctk.CTkFrame(sf, height=1, fg_color=("gray65", "gray40")
                     ).grid(row=1, column=0, columnspan=ncols + 3,
                            sticky="ew", padx=4, pady=(0, 2))

        if not display_rows:
            ctk.CTkLabel(sf, text="Нет данных", font=ctk.CTkFont(size=10)
                         ).grid(row=2, column=0, columnspan=ncols + 3, padx=8, pady=8)
            return

        _OFFSET_TYPES = {"Индикатор 1", "Индикатор 2", "Индикатор - круги",
                         "Индикатор 2 (Тепловой)", "Светофор", "Секундомер",
                         "Волна", "Пламя", "ЭКГ", "Кольца", "Дельта"}

        # Вычислить выравнивание текста для анимированных колонок
        col_text_offsets: dict = {}
        try:
            _fnt = tkfont.Font(family="Segoe UI", size=10)
            for ci, col_name in enumerate(columns):
                _cfgci = viz_configs.get(col_name, {})
                if (_cfgci.get("type") in _OFFSET_TYPES
                        or _cfgci.get("signal", {}).get("type_name") in _OFFSET_TYPES):
                    max_w = max(
                        (_fnt.measure("NULL" if (ci >= len(r) or r[ci] is None) else str(r[ci]))
                         for r in display_rows),
                        default=0,
                    )
                    col_text_offsets[ci] = 6 + max_w + 10
        except Exception:
            pass

        def _delayed_hide(lbl, flag):
            if not flag[0]:
                try:
                    lbl.configure(text="")
                except Exception:
                    pass

        def _make_bulb_menu(row_data):
            def _show(event):
                first_val = str(row_data[0]) if row_data else ""
                row_text  = "\n".join("" if v is None else str(v) for v in row_data)
                menu = tk.Menu(sf, tearoff=0)
                top = sf.winfo_toplevel()
                if hasattr(top, "_open_reminder_for_row"):
                    menu.add_command(
                        label="💡 Напомнить",
                        command=lambda: top._open_reminder_for_row(first_val),
                    )
                menu.add_command(
                    label="📋 Копировать стр",
                    command=lambda: (
                        top.clipboard_clear(),
                        top.clipboard_append(row_text),
                    ),
                )
                menu.add_command(label="👁 Следить", state="disabled")
                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()
            return _show

        # Строки данных
        now = datetime.datetime.now()
        for ri, row in enumerate(display_rows):
            # Лампочка (col 0)
            bulb_lbl = ctk.CTkLabel(sf, text="", width=24, anchor="center",
                                    cursor="hand2",
                                    font=ctk.CTkFont(size=11))
            bulb_lbl.grid(row=ri + 2, column=0, padx=(2, 1), pady=1, sticky="ew")

            # № (col 1)
            row_num_lbl = ctk.CTkLabel(sf, text=str(ri + 1), anchor="e",
                                       font=ctk.CTkFont(size=9),
                                       text_color=("gray50", "gray60"))
            row_num_lbl.grid(row=ri + 2, column=1, sticky="ew", padx=(2, 4), pady=1)

            _flag = [False]

            def _enter(e, lbl=bulb_lbl, f=_flag):
                f[0] = True
                lbl.configure(text="💡")

            def _leave(e, lbl=bulb_lbl, f=_flag):
                f[0] = False
                lbl.after(60, lambda: _delayed_hide(lbl, f))

            bulb_lbl.bind("<Enter>", _enter)
            bulb_lbl.bind("<Leave>", _leave)
            row_num_lbl.bind("<Enter>", _enter)
            row_num_lbl.bind("<Leave>", _leave)
            bulb_lbl.bind("<Button-1>", _make_bulb_menu(row))

            for ci, col_name in enumerate(columns):
                cfg   = viz_configs.get(col_name, {})
                vtype = cfg.get("type", "Стандартный")
                color = cfg.get("color", "#0D9488")
                raw   = row[ci] if ci < len(row) else None

                sig       = cfg.get("signal", {})
                sig_texts = [t.strip() for t in sig.get("text", "").split(",") if t.strip()]
                if (sig_texts and raw is not None
                        and all(t.lower() in str(raw).lower() for t in sig_texts)):
                    vtype = sig.get("type_name", vtype)
                    color = sig.get("color", color)

                if vtype in ("Индикатор 1", "Индикатор 2", "Индикатор - круги", "Пламя"):
                    val_str      = "NULL" if raw is None else str(raw)
                    first_seen   = age_data.get((col_name, val_str))
                    interval_min = max(0.01, float(cfg.get("interval_min", 1.0)))
                    if first_seen is None:
                        elapsed = 0.0
                        age     = 0
                    else:
                        elapsed = (now - first_seen).total_seconds() / 60.0
                        age     = int(elapsed / interval_min)
                    effective_color = color
                    age_thr   = float(cfg.get("age_threshold", 0.0))
                    age_cname = cfg.get("age_color", "")
                    if (age_thr > 0 and age_cname and age_cname != "(нет)"
                            and first_seen is not None and elapsed >= age_thr):
                        effective_color = _VIZ_COLOR_MAP.get(age_cname, color)
                    toff = col_text_offsets.get(ci, 0)
                    if vtype == "Индикатор 1":
                        w = Display1Widget(sf, color=effective_color,
                                           max_blocks=max(1, int(cfg.get("max_blocks", 10))),
                                           speed=max(100, int(cfg.get("speed", 650))),
                                           text_offset=toff)
                    elif vtype == "Индикатор 2":
                        w = Indicator2Widget(sf, color=effective_color,
                                             max_units=max(1, int(cfg.get("max_blocks", 10))),
                                             speed=max(100, int(cfg.get("speed", 650))),
                                             text_offset=toff)
                    elif vtype == "Индикатор - круги":
                        w = IndicatorCirclesWidget(sf, color=effective_color,
                                                   max_blocks=max(1, int(cfg.get("max_blocks", 10))),
                                                   speed=max(100, int(cfg.get("speed", 650))),
                                                   text_offset=toff)
                    else:  # Пламя
                        w = FlameWidget(sf, color=effective_color,
                                        max_chars=max(1, int(cfg.get("max_blocks", 10))),
                                        speed=max(100, int(cfg.get("speed", 500))),
                                        text_offset=toff)
                    w.set_value_and_age(raw, age)

                elif vtype == "Светофор":
                    w = TrafficWidget(sf,
                                      color=color,
                                      speed=max(100, int(cfg.get("speed", 500))),
                                      interval_min=max(0.01, float(cfg.get("interval_min", 1.0))),
                                      text_offset=col_text_offsets.get(ci, 0))
                    w.set_value(raw)

                elif vtype == "Секундомер":
                    val_str    = "NULL" if raw is None else str(raw)
                    first_seen = age_data.get((col_name, val_str))
                    w = StopwatchWidget(sf, color=color, first_seen=first_seen,
                                        age_threshold=float(cfg.get("age_threshold", 0.0)),
                                        age_color=cfg.get("age_color", ""),
                                        text_offset=col_text_offsets.get(ci, 0))
                    w.set_value(raw)

                elif vtype == "Волна":
                    val_str      = "NULL" if raw is None else str(raw)
                    first_seen   = age_data.get((col_name, val_str))
                    interval_min = max(0.01, float(cfg.get("interval_min", 1.0)))
                    if first_seen is None:
                        elapsed = 0.0
                        age     = 0
                    else:
                        elapsed = (now - first_seen).total_seconds() / 60.0
                        age     = int(elapsed / interval_min)
                    effective_color = color
                    age_thr   = float(cfg.get("age_threshold", 0.0))
                    age_cname = cfg.get("age_color", "")
                    if (age_thr > 0 and age_cname and age_cname != "(нет)"
                            and first_seen is not None and elapsed >= age_thr):
                        effective_color = _VIZ_COLOR_MAP.get(age_cname, color)
                    w = WaveWidget(sf, color=effective_color,
                                   max_amplitude=max(2, int(cfg.get("max_amplitude", 10))),
                                   speed=max(20, int(cfg.get("speed", 40))),
                                   age=age,
                                   text_offset=col_text_offsets.get(ci, 0))
                    w.set_value_and_age(raw, age)

                elif vtype == "ЭКГ":
                    val_str    = "NULL" if raw is None else str(raw)
                    first_seen = age_data.get((col_name, val_str))
                    effective_color = color
                    age_thr   = float(cfg.get("age_threshold", 0.0))
                    age_cname = cfg.get("age_color", "")
                    if (first_seen and age_thr > 0 and age_cname and age_cname != "(нет)"):
                        if (now - first_seen).total_seconds() / 60.0 >= age_thr:
                            effective_color = _VIZ_COLOR_MAP.get(age_cname, color)
                    w = EcgWidget(sf, color=effective_color,
                                  speed=max(20, int(cfg.get("speed", 40))),
                                  fade_minutes=max(0.1, float(cfg.get("fade_minutes", 10.0))),
                                  first_seen=first_seen,
                                  text_offset=col_text_offsets.get(ci, 0))
                    w.set_value(raw)

                elif vtype == "Кольца":
                    val_str      = "NULL" if raw is None else str(raw)
                    first_seen   = age_data.get((col_name, val_str))
                    interval_min = max(0.01, float(cfg.get("interval_min", 1.0)))
                    if first_seen is None:
                        elapsed = 0.0
                        age     = 0
                    else:
                        elapsed = (now - first_seen).total_seconds() / 60.0
                        age     = int(elapsed / interval_min)
                    effective_color = color
                    age_thr   = float(cfg.get("age_threshold", 0.0))
                    age_cname = cfg.get("age_color", "")
                    if (age_thr > 0 and age_cname and age_cname != "(нет)"
                            and first_seen is not None and elapsed >= age_thr):
                        effective_color = _VIZ_COLOR_MAP.get(age_cname, color)
                    w = RingsWidget(sf, color=effective_color,
                                    max_rings=max(1, int(cfg.get("max_rings", 5))),
                                    speed=max(20, int(cfg.get("speed", 80))),
                                    age=age,
                                    text_offset=col_text_offsets.get(ci, 0))
                    w.set_value_and_age(raw, age)

                elif vtype == "Индикатор 2 (Тепловой)":
                    val_str    = "NULL" if raw is None else str(raw)
                    first_seen = age_data.get((col_name, val_str))
                    elapsed    = ((now - first_seen).total_seconds() / 60.0
                                  if first_seen else 0.0)
                    cold_c = _VIZ_COLOR_MAP.get(cfg.get("cold_color", "Зелёный"), "#27AE60")
                    warm_c = _VIZ_COLOR_MAP.get(cfg.get("warm_color", "Оранжевый"), "#E67E22")
                    crit_c = _VIZ_COLOR_MAP.get(cfg.get("crit_color", "Красный"), "#C0392B")
                    if cold_c == "auto": cold_c = "#27AE60"
                    if warm_c == "auto": warm_c = "#E67E22"
                    if crit_c == "auto": crit_c = "#C0392B"
                    w = HeatTimeWidget(
                        sf,
                        cold_color=cold_c, warm_color=warm_c, crit_color=crit_c,
                        age_cold=max(0.1, float(cfg.get("age_cold", 10.0))),
                        age_warm=max(0.2, float(cfg.get("age_warm", 20.0))),
                        age_crit=max(0.3, float(cfg.get("age_crit", 40.0))),
                        text_offset=col_text_offsets.get(ci, 0),
                    )
                    w.set_value_and_elapsed(raw, elapsed, first_seen)

                elif vtype == "Дельта":
                    delta_val = 0
                    old = delta_data.get((col_name, ri))
                    if old is not None:
                        try:
                            c_v = float(str(raw).replace(",", ".")) if raw is not None else 0.0
                            o_v = float(str(old).replace(",", "."))
                            delta_val = 1 if c_v > o_v else (-1 if c_v < o_v else 0)
                        except (ValueError, TypeError):
                            delta_val = 0 if str(raw) == str(old) else 1
                    cu = _VIZ_COLOR_MAP.get(cfg.get("color_up",   "Зелёный"),  "#27AE60")
                    cd = _VIZ_COLOR_MAP.get(cfg.get("color_down", "Красный"),  "#C0392B")
                    cs = _VIZ_COLOR_MAP.get(cfg.get("color_same", "Светлый/Тёмный"), "auto")
                    if cs == "auto":
                        cs = "#808080"
                    w = DeltaWidget(sf, color_up=cu, color_down=cd, color_same=cs,
                                    text_offset=col_text_offsets.get(ci, 0))
                    w.set_value_and_delta(raw, delta_val)

                else:
                    w = _make_compact_cell(sf, vtype, color, raw, cfg)

                w.grid(row=ri + 2, column=ci + 2, sticky="ew", padx=(6, 2), pady=1)
                _bind_cell_select(w, "" if raw is None else str(raw), self)

            def _do_copy(r=row):
                text = "\n".join("" if v is None else str(v) for v in r)
                top = sf.winfo_toplevel()
                top.clipboard_clear()
                top.clipboard_append(text)

            ctk.CTkButton(
                sf, text="⎘", width=26, height=24,
                font=ctk.CTkFont(size=11),
                fg_color="transparent",
                hover_color=("gray75", "gray35"),
                command=_do_copy,
            ).grid(row=ri + 2, column=ncols + 2, padx=(2, 4), pady=1)

        if len(rows) > self._MAX_ROWS:
            ctk.CTkLabel(sf,
                         text=f"… первые {self._MAX_ROWS} из {len(rows)} строк",
                         font=ctk.CTkFont(size=9),
                         text_color=("gray50", "gray55")
                         ).grid(row=len(display_rows) + 2, column=0, columnspan=ncols + 3,
                                sticky="w", padx=6, pady=(2, 4))

        # ── строка выделения ячейки (BUG-66) ──────────────────────────────────
        info_f = ctk.CTkFrame(sf, fg_color=("gray83", "gray22"), corner_radius=4)
        info_f.grid(row=999, column=0, columnspan=ncols + 3,
                    sticky="ew", padx=4, pady=(2, 4))
        info_f.grid_columnconfigure(0, weight=1)
        self._cell_info_lbl = ctk.CTkLabel(
            info_f, text="Нажмите на ячейку — Ctrl+C скопирует значение",
            anchor="w", font=ctk.CTkFont(size=9),
            text_color=("gray50", "gray55"),
        )
        self._cell_info_lbl.grid(row=0, column=0, sticky="ew", padx=(6, 2), pady=2)
        ctk.CTkButton(
            info_f, text="⎘", width=26, height=20,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=("gray75", "gray35"),
            command=self._copy_selected_cell,
        ).grid(row=0, column=1, padx=(0, 4), pady=2)
        if not self._top_bound:
            try:
                top = self.winfo_toplevel()
                top.bind("<Control-c>", self._copy_selected_cell, add="+")
                top.bind("<Control-C>", self._copy_selected_cell, add="+")
                self._top_bound = True
            except Exception:
                pass

    def _copy_selected_cell(self, event=None):
        try:
            if not self.winfo_ismapped():
                return
        except Exception:
            return
        if self._selected_value is not None:
            try:
                top = self.winfo_toplevel()
                top.clipboard_clear()
                top.clipboard_append(self._selected_value)
            except Exception:
                pass
            return "break"
