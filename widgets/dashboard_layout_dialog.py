"""
Диалог выбора шаблона компоновки приборной панели (UX-10c).
"""
import tkinter as tk
import customtkinter as ctk

import theme_colors

# (template_id, label, ascii-preview, min_panels)
DASHBOARD_TEMPLATES = [
    ("auto", "Авто",    "┌──┬──┐\n│  │  │\n├──┤  │\n│  │  │\n└──┴──┘", 1),
    ("col",  "Столбец", "┌────┐\n│    │\n├────┤\n│    │\n└────┘",         1),
    ("row",  "Строка",  "┌──┬──┐\n│  │  │\n└──┴──┘",                     1),
    ("1+2",  "1 + 2",   "┌────┐\n│ 1  │\n├──┬─┤\n│2 │3│\n└──┴─┘",       2),
    ("2+1",  "2 + 1",   "┌──┬─┐\n│1 │2│\n├──┴─┤\n│ 3  │\n└────┘",       2),
    ("2x2",  "2 × 2",   "┌──┬──┐\n│1 │2 │\n├──┼──┤\n│3 │4 │\n└──┴──┘",  2),
]


class DashboardLayoutDialog(ctk.CTkToplevel):
    """Выбор шаблона компоновки и количества фреймов приборной панели."""

    def __init__(self, parent, current_template: str = "auto", panel_count: int = 3):
        super().__init__(parent)
        self.withdraw()
        self.result = None          # (template_str, count_int) или None

        self._selected = current_template
        self._btn_refs: dict = {}

        self.title("Компоновка приборной панели")
        self.resizable(False, False)
        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build(panel_count)
        self.after(60, self._center)

    # ── centering ─────────────────────────────────────────────────────────────

    def _center(self):
        self.update_idletasks()
        p = self.master
        p.update_idletasks()
        pw, ph = p.winfo_width(), p.winfo_height()
        px, py = p.winfo_rootx(), p.winfo_rooty()
        if pw <= 1 or ph <= 1:
            self.after(80, self._center)
            return
        dw, dh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")
        self.deiconify()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self, panel_count: int):
        ctk.CTkLabel(
            self,
            text="Шаблон компоновки приборной панели",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(18, 4))

        ctk.CTkFrame(self, height=1,
                     fg_color=("gray80", "gray30")).pack(fill="x", padx=20, pady=(0, 12))

        # ── карточки шаблонов ─────────────────────────────────────────────────
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(padx=20)

        for col, (tid, tlabel, tart, _) in enumerate(DASHBOARD_TEMPLATES):
            cell = ctk.CTkFrame(cards, fg_color="transparent")
            cell.grid(row=0, column=col, padx=5, pady=4)

            btn = ctk.CTkButton(
                cell,
                text=tart,
                width=88, height=88,
                font=ctk.CTkFont(family="Courier New", size=10),
                fg_color=self._card_bg(tid),
                hover_color=(theme_colors.hover(), theme_colors.hover()),
                text_color=("gray10", "gray90"),
                border_width=2,
                border_color=self._card_border(tid),
                command=lambda t=tid: self._select(t),
            )
            btn.pack()
            ctk.CTkLabel(cell, text=tlabel,
                         font=ctk.CTkFont(size=11)).pack(pady=(4, 0))
            self._btn_refs[tid] = btn

        # ── количество фреймов ────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1,
                     fg_color=("gray80", "gray30")).pack(fill="x", padx=20, pady=(14, 0))

        cnt_row = ctk.CTkFrame(self, fg_color="transparent")
        cnt_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(cnt_row, text="Количество фреймов:",
                     width=180, anchor="w").pack(side="left")
        self._count_entry = ctk.CTkEntry(cnt_row, placeholder_text="1–8",
                                         width=60, height=32)
        self._count_entry.insert(0, str(panel_count))
        self._count_entry.pack(side="left")

        # ── кнопки ────────────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1,
                     fg_color=("gray80", "gray30")).pack(fill="x", padx=20)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(10, 18))

        ctk.CTkButton(
            btn_row, text="Применить", command=self._apply,
            width=110, height=34,
            fg_color=(theme_colors.accent(), theme_colors.accent()),
            hover_color=(theme_colors.hover(), theme_colors.hover()),
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            btn_row, text="Отмена", command=self.destroy,
            width=90, height=34,
            fg_color=("gray55", "gray35"),
            hover_color=("gray45", "gray25"),
        ).pack(side="right")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _card_bg(self, tid: str):
        a = theme_colors.accent()
        return (a, a) if tid == self._selected else ("gray80", "gray25")

    def _card_border(self, tid: str):
        a = theme_colors.accent()
        return (a, a) if tid == self._selected else ("gray60", "gray40")

    def _select(self, tid: str):
        prev = self._selected
        if prev == tid:
            return
        self._selected = tid
        for t in (prev, tid):
            btn = self._btn_refs.get(t)
            if btn:
                btn.configure(fg_color=self._card_bg(t),
                              border_color=self._card_border(t))

    def _apply(self):
        try:
            count = int(self._count_entry.get().strip())
            if not (1 <= count <= 8):
                raise ValueError
        except ValueError:
            from tkinter import messagebox as _mb
            _mb.showerror("Ошибка",
                          "Количество фреймов: целое число от 1 до 8",
                          parent=self)
            return
        self.result = (self._selected, count)
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
