import tkinter as tk
import customtkinter as ctk
from .animated import _viz_bg


class _SimpleChartCanvas(tk.Frame):
    """Линейный или столбчатый график через tkinter Canvas."""

    def __init__(self, parent, chart_type: str = "line", **kw):
        bg = _viz_bg()
        super().__init__(parent, bg=bg, **kw)
        self._chart_type = chart_type
        self._rows:      list = []
        self._columns:   list = []
        self._hover_pts: list = []  # [(canvas_x, canvas_y, value, x_label)]
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda _e: self._draw())
        self._canvas.bind("<Motion>",    self._on_hover)
        self._canvas.bind("<Leave>",     lambda _e: self._clear_tooltip())

    def set_data(self, rows: list, columns: list):
        self._rows    = rows
        self._columns = columns
        self._draw()

    def _clear_tooltip(self):
        self._canvas.delete("tooltip")

    def _on_hover(self, event):
        self._clear_tooltip()
        if not self._hover_pts:
            return
        mx, my = event.x, event.y
        best, best_d2 = None, float("inf")
        for item in self._hover_pts:
            px, py = item[0], item[1]
            d2 = (mx - px) ** 2 + (my - py) ** 2
            if d2 < best_d2:
                best_d2, best = d2, item
        if best is None or best_d2 > 625:  # порог: 25 px
            return
        _, _, val, lbl = best
        try:
            fmt_val = str(int(val)) if val == int(val) else f"{val:.4g}"
        except Exception:
            fmt_val = str(val)
        text = f"{lbl}\n{fmt_val}" if lbl else fmt_val
        self._draw_tooltip(event.x, event.y, text)

    def _draw_tooltip(self, mx: int, my: int, text: str):
        c    = self._canvas
        dark = ctk.get_appearance_mode() == "Dark"
        bg   = "#3c3c3c" if dark else "#f5f5f5"
        fg   = "#e0e0e0" if dark else "#1a1a1a"
        brd  = "#555555" if dark else "#cccccc"
        pad  = 5
        lines   = text.split("\n")
        est_w   = max(len(l) for l in lines) * 7 + pad * 2
        est_h   = len(lines) * 15 + pad * 2
        cw, ch  = c.winfo_width(), c.winfo_height()
        x1 = mx + 12
        y1 = my - est_h - 4
        if x1 + est_w > cw - 4:
            x1 = mx - est_w - 12
        if y1 < 4:
            y1 = my + 12
        x2, y2 = x1 + est_w, y1 + est_h
        c.create_rectangle(x1, y1, x2, y2, fill=bg, outline=brd, width=1, tags="tooltip")
        c.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=text,
                      fill=fg, font=("Segoe UI", 9), justify="center", tags="tooltip")

    def _draw(self):
        self._hover_pts = []
        c = self._canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20 or h < 20 or not self._rows:
            return

        # Первый числовой столбец
        num_col = -1
        for ci in range(len(self._columns)):
            try:
                float(str(self._rows[0][ci]).replace(",", "."))
                num_col = ci
                break
            except (ValueError, TypeError, IndexError):
                continue

        values:   list = []
        x_labels: list = []
        for row in self._rows:
            if num_col >= 0:
                try:
                    values.append(float(str(row[num_col]).replace(",", ".")))
                    x_labels.append(str(row[0]) if row else "")
                except (ValueError, TypeError):
                    pass

        if not values:
            c.create_text(w // 2, h // 2, text="Нет числовых данных",
                          fill="gray", font=("", 11))
            return

        accent = "#0D9488"
        fg     = "gray70"
        pl, pr, pt, pb = 48, 16, 16, 32
        chart_w = w - pl - pr
        chart_h = h - pt - pb
        min_v, max_v = min(values), max(values)
        if max_v == min_v:
            max_v = min_v + 1

        def to_x(i):
            return pl + i * chart_w / max(len(values) - 1, 1)

        def to_y(v):
            return pt + (1 - (v - min_v) / (max_v - min_v)) * chart_h

        c.create_line(pl, pt, pl, h - pb, fill=fg)
        c.create_line(pl, h - pb, w - pr, h - pb, fill=fg)
        c.create_text(pl - 4, h - pb, text=f"{min_v:.1f}", anchor="e", fill=fg, font=("", 8))
        c.create_text(pl - 4, pt,     text=f"{max_v:.1f}", anchor="e", fill=fg, font=("", 8))

        n = len(values)
        if self._chart_type == "bar":
            gap   = 4
            bar_w = max(2, chart_w // n - gap)
            for i, v in enumerate(values):
                x0  = pl + i * chart_w // n + gap // 2
                lbl = x_labels[i] if i < len(x_labels) else ""
                c.create_rectangle(x0, to_y(v), x0 + bar_w, h - pb, fill=accent, outline="")
                if chart_w // n > 24 and lbl:
                    c.create_text((x0 + x0 + bar_w) / 2, h - pb + 4,
                                  text=lbl[:8], anchor="n", fill=fg, font=("", 7))
                self._hover_pts.append(((x0 + x0 + bar_w) / 2, to_y(v), v, lbl))
        else:
            if n == 1:
                x, y = pl + chart_w / 2, to_y(values[0])
                c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=accent, outline="")
                lbl = x_labels[0] if x_labels else ""
                self._hover_pts.append((x, y, values[0], lbl))
            else:
                pts  = [(to_x(i), to_y(v)) for i, v in enumerate(values)]
                flat = [coord for p in pts for coord in p]
                c.create_line(*flat, fill=accent, width=2, smooth=True)
                for i, (x, y) in enumerate(pts):
                    c.create_oval(x - 3, y - 3, x + 3, y + 3,
                                  fill=accent, outline="white", width=1)
                    lbl = x_labels[i] if i < len(x_labels) else ""
                    self._hover_pts.append((x, y, values[i], lbl))
            step = max(1, n // 6)
            for i in range(0, n, step):
                if i < len(x_labels):
                    c.create_text(to_x(i), h - pb + 4, text=x_labels[i][:8],
                                  anchor="n", fill=fg, font=("", 7))
