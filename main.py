import multiprocessing
import subprocess
import customtkinter as ctk
from gui import MainWindow
import os
import sys
import theme_colors
from settings import SettingsManager


def resource_path(filename: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)


def _read_version() -> str:
    import re
    _cwd = os.path.dirname(os.path.abspath(__file__))

    if not getattr(sys, "frozen", False):
        # 1. Имя текущей ветки: task/#25/V.4.0.0 → "4.0.0"
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=3, cwd=_cwd,
            )
            if r.returncode == 0:
                m = re.search(r"V\.(\d+\.\d+(?:\.\d+)*)", r.stdout.strip(), re.IGNORECASE)
                if m:
                    return m.group(1)
        except Exception:
            pass
        # 2. Git-тег (если теги есть)
        try:
            r = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True, text=True, timeout=3, cwd=_cwd,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().lstrip("v")
        except Exception:
            pass

    # 3. EXE-режим или git недоступен — bundled version.txt
    try:
        with open(resource_path("version.txt"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


if __name__ == "__main__":
    multiprocessing.freeze_support()  # обязателен для PyInstaller + multiprocessing/matplotlib
    from setup_dirs import create_directories
    create_directories()
    _settings = SettingsManager()
    ctk.set_appearance_mode(_settings.get_setting("theme", "dark"))

    a = theme_colors.accent()
    if a != "#0D9488":
        theme_path = theme_colors.build_theme_file(a, theme_colors.hover(), theme_colors.dark())
    else:
        theme_path = resource_path("teal.json")
    ctk.set_default_color_theme(theme_path)

    VERSION = _read_version()
    app = MainWindow(version=VERSION)
    try:
        app.iconbitmap(resource_path("Hunch.ico"))
    except Exception:
        pass
    app.mainloop()
