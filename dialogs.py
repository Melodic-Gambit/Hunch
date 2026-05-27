"""Themed dialogs — drop-in replacement for tkinter.messagebox."""
import tkinter as _tk
import customtkinter as ctk


class _StyledDialog(ctk.CTkToplevel):
    _ICONS = {
        "error":    ("✕", ("#DC2626", "#EF4444")),
        "warning":  ("⚠", ("#D97706", "#F59E0B")),
        "info":     ("ℹ", ("#2563EB", "#3B82F6")),
        "question": ("?", ("#7C3AED", "#8B5CF6")),
    }

    def __init__(self, parent, title: str, message: str,
                 kind: str = "info", buttons: list = None):
        if buttons is None:
            buttons = [("OK", True)]

        if parent is None:
            parent = _tk._default_root

        super().__init__(parent)
        self.withdraw()
        self.result = None
        self.title(title)
        self.resizable(False, False)
        self.minsize(380, 0)
        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass

        symbol, color = self._ICONS.get(kind, ("ℹ", ("#2563EB", "#3B82F6")))

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(padx=28, pady=(24, 20), fill="both", expand=True)

        msg_row = ctk.CTkFrame(outer, fg_color="transparent")
        msg_row.pack(fill="x")

        ctk.CTkLabel(
            msg_row, text=symbol,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=color, width=36, anchor="n",
        ).pack(side="left", padx=(0, 14), anchor="nw", pady=(2, 0))

        ctk.CTkLabel(
            msg_row, text=message,
            font=ctk.CTkFont(size=13),
            wraplength=300, justify="left", anchor="w",
        ).pack(side="left", fill="x", expand=True)

        btn_row = ctk.CTkFrame(outer, fg_color="transparent")
        btn_row.pack(pady=(20, 0), anchor="e")

        for i, (label, primary) in enumerate(buttons):
            ctk.CTkButton(
                btn_row, text=label, width=100,
                fg_color=("gray75", "gray30") if not primary else None,
                hover_color=("gray65", "gray40") if not primary else None,
                text_color=("gray10", "gray90") if not primary else None,
                command=lambda l=label: self._close(l),
            ).pack(side="left", padx=(0 if i == 0 else 10, 0))

        self.bind("<Return>", lambda _: self._close(buttons[0][0]))
        self.bind("<Escape>", lambda _: self._close(None))
        self.after(60, self._center)

    def _close(self, value):
        self.result = value
        self.destroy()

    def _center(self):
        self.update_idletasks()
        m = self.master
        if m and m.winfo_exists():
            x = m.winfo_rootx() + (m.winfo_width()  - self.winfo_reqwidth())  // 2
            y = m.winfo_rooty() + (m.winfo_height() - self.winfo_reqheight()) // 2
        else:
            x = (self.winfo_screenwidth()  - self.winfo_reqwidth())  // 2
            y = (self.winfo_screenheight() - self.winfo_reqheight()) // 2
        self.geometry(f"+{x}+{y}")
        self.deiconify()


def _run(parent, title: str, message: str, kind: str, buttons: list):
    dlg = _StyledDialog(parent, title, message, kind, buttons)
    dlg.wait_window()
    return dlg.result


def showerror(title: str, message: str, parent=None) -> None:
    _run(parent, title, message, "error", [("OK", True)])


def showinfo(title: str, message: str, parent=None) -> None:
    _run(parent, title, message, "info", [("OK", True)])


def showwarning(title: str, message: str, parent=None) -> None:
    _run(parent, title, message, "warning", [("OK", True)])


def askyesno(title: str, message: str, parent=None) -> bool:
    return _run(parent, title, message, "question",
                [("Да", True), ("Нет", False)]) == "Да"


def askokcancel(title: str, message: str, parent=None) -> bool:
    return _run(parent, title, message, "question",
                [("ОК", True), ("Отмена", False)]) == "ОК"
