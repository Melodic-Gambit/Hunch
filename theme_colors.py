"""Централизованный модуль акцентных цветов темы.

Читается из settings.json один раз при импорте.
Вызывайте update() после смены темы — все последующие обращения
к accent() / hover() / dark() вернут актуальные значения.
"""
import json
import os
import sys

_state: dict = {
    "accent": "#0D9488",
    "hover":  "#0B7A72",
    "dark":   "#085E58",
}


def _resource_path(filename: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)


def load_from_settings(path: str = "settings.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            ct = json.load(f).get("custom_theme") or {}
        a = (ct.get("accent") or "#0D9488").strip().upper()
        h = (ct.get("hover")  or "#0B7A72").strip().upper()
        d = (ct.get("dark")   or "#085E58").strip().upper()
        if a.startswith("#") and len(a) in (4, 7):
            _state["accent"] = a
        if h.startswith("#") and len(h) in (4, 7):
            _state["hover"] = h
        if d.startswith("#") and len(d) in (4, 7):
            _state["dark"] = d
    except Exception:
        pass


def update(a: str, h: str, d: str):
    _state["accent"] = a.strip().upper()
    _state["hover"]  = h.strip().upper()
    _state["dark"]   = d.strip().upper()


def accent() -> str:
    return _state["accent"]


def hover() -> str:
    return _state["hover"]


def dark() -> str:
    return _state["dark"]


def build_theme_file(a: str, h: str, d: str) -> str:
    """Генерирует _custom_theme.json из teal.json с новыми акцентными цветами."""
    _MAP = {
        "#0D9488": a.upper(),
        "#0B7A72": h.upper(),
        "#085E58": d.upper(),
        "#096B64": d.upper(),
        "#064E4A": d.upper(),
        "#096B62": d.upper(),
    }
    try:
        base = _resource_path("teal.json")
        with open(base, "r", encoding="utf-8") as f:
            content = f.read()
        for old, new in _MAP.items():
            content = content.replace(old, new)
        out = "_custom_theme.json"
        with open(out, "w", encoding="utf-8") as f:
            f.write(content)
        return out
    except Exception:
        return _resource_path("teal.json")


load_from_settings()
