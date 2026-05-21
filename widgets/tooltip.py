import tkinter as tk
import customtkinter as ctk
from typing import Optional


def _monitor_work_area(x: int, y: int):
    """Возвращает (left, top, right, bottom) рабочей области монитора, содержащего точку (x, y).
    При ошибке (не Windows) возвращает None.
    """
    try:
        import ctypes
        import ctypes.wintypes as wt

        class _MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize",    wt.DWORD),
                ("rcMonitor", wt.RECT),
                ("rcWork",    wt.RECT),
                ("dwFlags",   wt.DWORD),
            ]

        MONITOR_DEFAULTTONEAREST = 2
        hmon = ctypes.windll.user32.MonitorFromPoint(
            wt.POINT(x, y), MONITOR_DEFAULTTONEAREST)
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcWork
        return r.left, r.top, r.right, r.bottom
    except Exception:
        return None


class _Tooltip:
    """Всплывающая подсказка для любого виджета tkinter/customtkinter."""

    def __init__(self, widget, text: str, delay: int = 500):
        self._widget   = widget
        self._text     = text
        self._delay    = delay
        self._after_id = None
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>",       self._on_enter, add="+")
        widget.bind("<Leave>",       self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._cancel()
        self._after_id = self._widget.after(self._delay, self._show)

    def _on_leave(self, _event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after_id:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip:
            return
        dark = ctk.get_appearance_mode() == "Dark"
        bg   = "#3c3c3c" if dark else "#f5f5f5"
        fg   = "#e0e0e0" if dark else "#1a1a1a"
        bd   = "#555555" if dark else "#bbbbbb"

        x = self._widget.winfo_rootx()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4

        tip = tk.Toplevel(self._widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)

        outer = tk.Frame(tip, background=bd)
        outer.pack(padx=1, pady=1)
        tk.Label(outer, text=self._text, background=bg, foreground=fg,
                 font=("Segoe UI", 9), padx=7, pady=4, bd=0,
                 justify="left", wraplength=300).pack()

        tip.update_idletasks()
        tw = tip.winfo_reqwidth()
        th = tip.winfo_reqheight()

        bounds = _monitor_work_area(x, y)
        if bounds:
            ml, mt, mr, mb = bounds
        else:
            ml, mt = 0, 0
            mr = tip.winfo_screenwidth()
            mb = tip.winfo_screenheight()

        if x + tw > mr:
            x = mr - tw - 6
        if y + th > mb:
            y = self._widget.winfo_rooty() - th - 4
        tip.geometry(f"+{max(ml, x)}+{max(mt, y)}")
        self._tip = tip

    def _hide(self):
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def update_text(self, text: str):
        self._text = text
