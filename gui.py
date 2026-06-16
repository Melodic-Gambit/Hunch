import customtkinter as ctk
from tkinter import simpledialog, filedialog
import dialogs as messagebox
import json
import tkinter as tk
import os
import sys
import ctypes
import datetime
import time
import re
import math
import threading
import functools
from typing import Optional
from data_manager import DataManager
from log_manager import LogManager
from db_manager import DatabaseManager
from settings import SettingsManager
from connection_dialog import DatabaseConnectionDialog
from query_dialog import QueryDialog
from utils import setup_paste_bindings
from widgets.tooltip import _Tooltip
from widgets.animated import (
    _viz_bg, _viz_fg, _VIZ_COLOR_MAP, _VIZ_TYPES,
    _AnimBase, CounterWidget, ProgressBarWidget, GaugeWidget,
    PulseTileWidget, HeatmapTileWidget, AnimatedPanel,
)
from widgets.result_table import ResultTable
from widgets.chart import _SimpleChartCanvas
from stats_manager import StatsManager
from reminders_manager import RemindersManager
from widgets.dashboard_layout_dialog import DashboardLayoutDialog, DASHBOARD_TEMPLATES
import theme_colors
from ui.tab_logs import LogsTabMixin
from ui.tab_reminders import RemindersTabMixin
from ui.tab_connections import ConnectionsTabMixin
from ui.tab_queries import QueriesTabMixin
from ui.tab_services import ServicesTabMixin
from ui.tab_settings import SettingsTabMixin
from ui.tab_dashboard import DashboardTabMixin

try:
    from PIL import Image, ImageDraw
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


try:
    from winotify import Notification as _WinNotification
    _WINOTIFY_OK = True
except ImportError:
    _WINOTIFY_OK = False



@functools.lru_cache(maxsize=8)
def _get_pin_ctk_image(size: int = 15) -> Optional["ctk.CTkImage"]:
    """Рендерит Bootstrap bi-pin SVG как CTkImage через PIL (кэшируется)."""
    if not _PIL_OK:
        return None
    # Рисуем на 4× и уменьшаем — получаем anti-aliasing
    big = size * 4
    sc  = big / 16.0

    def px(x, y):
        return (round(x * sc), round(y * sc))

    # Полигон, аппроксимирующий Bootstrap bi-pin (viewBox 0 0 16 16)
    pts = [
        px(4.5,  0.0),  px(11.5, 0.0),
        px(12.0, 0.5),  px(11.35, 2.0), px(11.0, 2.3),
        px(11.0, 6.7),  px(13.0, 9.5),
        px(8.5,  9.5),  px(8.5,  14.5),
        px(7.5,  14.5), px(7.5,  9.5),
        px(3.0,  9.5),  px(5.0,  6.7),
        px(5.0,  2.3),  px(4.65, 2.0),  px(4.0, 0.5),
    ]

    def _render(color):
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        ImageDraw.Draw(img).polygon(pts, fill=color)
        return img.resize((size, size), Image.LANCZOS)

    white = _render((255, 255, 255, 255))
    dark  = _render((40,  40,  40,  230))

    # light_image — для светлой темы (тёмный значок на светлом фоне)
    # dark_image  — для тёмной темы (белый значок на тёмном фоне)
    return ctk.CTkImage(light_image=dark, dark_image=white, size=(size, size))


def _make_clock_img(size: int, color: tuple, quarte: bool = False) -> "Image.Image":
    """Рисует значок часов через PIL (4× oversample → LANCZOS)."""
    import math
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    cx  = cy = big / 2
    r        = big / 2 - 1.5
    ring_w   = max(2, big // 11)
    lw_h     = max(2, big // 13)
    lw_m     = max(1, big // 17)

    if quarte:
        # Незамкнутая окружность — дуга от 295° до 245° по часовой (зазор у 12 часов)
        d.arc([cx - r, cy - r, cx + r, cy + r],
              start=295, end=245, fill=color, width=ring_w)
        # Стрелка на конце дуги (в точке 245°)
        tip_x = cx + r * math.cos(math.radians(245))
        tip_y = cy + r * math.sin(math.radians(245))
        tang  = math.radians(245 + 90)          # касательная по часовой
        as_   = max(3, big // 12)
        ax1   = tip_x + as_ * math.cos(tang + math.radians(140))
        ay1   = tip_y + as_ * math.sin(tang + math.radians(140))
        ax2   = tip_x + as_ * math.cos(tang - math.radians(140))
        ay2   = tip_y + as_ * math.sin(tang - math.radians(140))
        d.polygon([(int(tip_x), int(tip_y)), (int(ax1), int(ay1)),
                   (int(ax2), int(ay2))], fill=color)
    else:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=ring_w)

    # Центральная точка
    dot_r = max(1, big // 22)
    d.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=color)

    def pt(angle_from_12_deg: float, frac: float):
        a = math.radians(angle_from_12_deg)
        return (cx + r * frac * math.sin(a), cy - r * frac * math.cos(a))

    if quarte:
        hx, hy = pt(0,   0.52)   # 12 часов
        mx, my = pt(270, 0.68)   # 9 часов
    else:
        hx, hy = pt(300, 0.50)   # 10 часов
        mx, my = pt(60,  0.70)   # 2 часа

    d.line([(cx, cy), (hx, hy)], fill=color, width=lw_h)
    d.line([(cx, cy), (mx, my)], fill=color, width=lw_m)

    return img.resize((size, size), Image.LANCZOS)


@functools.lru_cache(maxsize=8)
def _get_time_ctk_image(size: int = 16) -> Optional["ctk.CTkImage"]:
    """Значок текущего времени (bi-clock) — кэшируется."""
    if not _PIL_OK:
        return None
    dark_img  = _make_clock_img(size, (40,  40,  40,  230), quarte=False)
    light_img = _make_clock_img(size, (255, 255, 255, 255), quarte=False)
    return ctk.CTkImage(light_image=dark_img, dark_image=light_img, size=(size, size))


@functools.lru_cache(maxsize=8)
def _get_time_quarte_ctk_image(size: int = 16) -> Optional["ctk.CTkImage"]:
    """Значок таймера обновления (bi-clock-history) — кэшируется."""
    if not _PIL_OK:
        return None
    dark_img  = _make_clock_img(size, (40,  40,  40,  230), quarte=True)
    light_img = _make_clock_img(size, (255, 255, 255, 255), quarte=True)
    return ctk.CTkImage(light_image=dark_img, dark_image=light_img, size=(size, size))


def _make_bell_img(size: int, body_color: tuple, badge: bool = False) -> "Image.Image":
    """Рендерит notification.svg через аппроксимацию кубических безье PIL."""
    big = size * 4
    sc  = big / 24.0
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    def sp(x, y):
        return (x * sc, y * sc)

    def cubic(p0, p1, p2, p3, n=24):
        pts = []
        for i in range(n + 1):
            t = i / n; mt = 1 - t
            pts.append(sp(
                mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0],
                mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1],
            ))
        return pts

    # ── Тело колокола (path 1, кривые Безье, заливка) ────────────────────────
    bell = (
        cubic((11.7009,7.14697),(9.62899,7.14697),(8.64717,8.38197),(7.66632,10.607))  +
        cubic((7.66632,10.607), (7.09252,12.1293),(6.80727,13.75),  (6.82587,15.382))  +
        cubic((6.82587,15.382), (8.24252,16.4412),(9.94777,17.0173),(11.7009,17.029))  +
        cubic((11.7009,17.029), (13.454, 17.0173),(15.1592,16.4412),(16.5759,15.382))  +
        cubic((16.5759,15.382), (16.5948,13.75),  (16.3099,12.1294),(15.7364,10.607))  +
        cubic((15.7364,10.607), (14.7546,8.38197),(13.7727,7.14697),(11.7009,7.14697))
    )
    d.polygon(bell, fill=body_color)

    # ── Язычок (path 2, sub-path 5) ──────────────────────────────────────────
    clapper = (
        cubic((13.6863,18.0775),(12.5041,18.9704),(10.8975,18.9704),(9.71536,18.0775)) +
        [sp(8.81131,19.2745)] +
        cubic((8.81131,19.2745),(10.5285,20.5714),(12.8732,20.5714),(14.5904,19.2745)) +
        [sp(13.6863,18.0775)]
    )
    d.polygon(clapper, fill=body_color)

    # ── Ушко сверху (path 2, прямоугольник) ──────────────────────────────────
    d.polygon([sp(10.8887,6.25), sp(12.513,6.25),
               sp(12.513,4.75),  sp(10.8887,4.75)], fill=body_color)

    # ── Красный бейдж (непрочитанное оповещение) ─────────────────────────────
    if badge:
        br = max(2, big // 8)
        bx = by = big - br - 1
        d.ellipse([bx - br, by - br, bx + br, by + br], fill=(220, 50, 50, 255))

    return img.resize((size, size), Image.LANCZOS)


@functools.lru_cache(maxsize=32)
def _get_bell_ctk_image(badge: bool = False, size: int = 18) -> Optional["ctk.CTkImage"]:
    """Значок оповещения — кэшируется по (badge, size) с ограничением в 32 записи."""
    if not _PIL_OK:
        return None
    dark_img  = _make_bell_img(size, (40,  40,  40,  230), badge=badge)
    light_img = _make_bell_img(size, (255, 255, 255, 255), badge=badge)
    return ctk.CTkImage(light_image=dark_img, dark_image=light_img, size=(size, size))


# ── Taskbar overlay badge (Windows ITaskbarList3::SetOverlayIcon) ─────────────

class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


def _parse_guid(s: str) -> _GUID:
    s = s.strip("{}")
    p = s.split("-")
    g = _GUID()
    g.Data1 = int(p[0], 16)
    g.Data2 = int(p[1], 16)
    g.Data3 = int(p[2], 16)
    d4 = bytes.fromhex(p[3] + p[4])
    g.Data4[:] = list(d4)
    return g


def _make_taskbar_badge_hicon() -> int:
    """Создаёт красный кружок 16×16 как HICON для оверлея панели задач Windows."""
    if sys.platform != "win32":
        return 0
    try:
        from ctypes import wintypes

        SIZE   = 16
        user32 = ctypes.windll.user32
        gdi32  = ctypes.windll.gdi32

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class ICONINFO(ctypes.Structure):
            _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD),
                        ("yHotspot", wintypes.DWORD), ("hbmMask", wintypes.HBITMAP),
                        ("hbmColor", wintypes.HBITMAP)]

        rc = RECT(0, 0, SIZE, SIZE)

        # Цветная битмапа: чёрный фон + красный эллипс
        screen_dc = user32.GetDC(None)
        mem_dc    = gdi32.CreateCompatibleDC(screen_dc)
        color_bmp = gdi32.CreateCompatibleBitmap(screen_dc, SIZE, SIZE)
        user32.ReleaseDC(None, screen_dc)
        old_obj = gdi32.SelectObject(mem_dc, color_bmp)
        user32.FillRect(mem_dc, ctypes.byref(rc), gdi32.GetStockObject(4))   # BLACK_BRUSH
        red_brush = gdi32.CreateSolidBrush(0x000000DC)   # COLORREF R=220 G=0 B=0
        gdi32.SelectObject(mem_dc, gdi32.GetStockObject(8))   # NULL_PEN
        gdi32.SelectObject(mem_dc, red_brush)
        gdi32.Ellipse(mem_dc, 1, 1, SIZE - 1, SIZE - 1)
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(red_brush)
        gdi32.DeleteDC(mem_dc)

        # Маска (1bpp): белая заливка (прозрачно) + чёрный эллипс (непрозрачно)
        mask_dc  = gdi32.CreateCompatibleDC(None)
        mask_bmp = gdi32.CreateBitmap(SIZE, SIZE, 1, 1, None)
        old_mask = gdi32.SelectObject(mask_dc, mask_bmp)
        user32.FillRect(mask_dc, ctypes.byref(rc), gdi32.GetStockObject(0))  # WHITE_BRUSH
        gdi32.SelectObject(mask_dc, gdi32.GetStockObject(4))   # BLACK_BRUSH
        gdi32.SelectObject(mask_dc, gdi32.GetStockObject(8))   # NULL_PEN
        gdi32.Ellipse(mask_dc, 1, 1, SIZE - 1, SIZE - 1)
        gdi32.SelectObject(mask_dc, old_mask)
        gdi32.DeleteDC(mask_dc)

        ii = ICONINFO()
        ii.fIcon    = 1
        ii.xHotspot = 0
        ii.yHotspot = 0
        ii.hbmMask  = mask_bmp
        ii.hbmColor = color_bmp
        hicon = user32.CreateIconIndirect(ctypes.byref(ii))
        gdi32.DeleteObject(color_bmp)
        gdi32.DeleteObject(mask_bmp)
        return hicon or 0
    except Exception:
        return 0


def _taskbar_set_overlay(hwnd: int, hicon: int, description: str = "") -> None:
    """Вызывает ITaskbarList3::SetOverlayIcon через COM vtable."""
    if sys.platform != "win32":
        return
    try:
        from ctypes import wintypes
        CLSID = "{56FDF344-FD6D-11D0-958A-006097C9A090}"
        IID   = "{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"

        ctypes.windll.ole32.CoInitialize(None)

        clsid = _parse_guid(CLSID)
        iid   = _parse_guid(IID)
        obj   = ctypes.c_void_p()
        hr    = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(clsid), None, 1,
            ctypes.byref(iid), ctypes.byref(obj))
        if hr < 0:
            return

        vtbl    = ctypes.cast(obj, ctypes.POINTER(ctypes.c_void_p))
        vtable  = ctypes.cast(vtbl[0], ctypes.POINTER(ctypes.c_void_p))

        # vtable[3] = HrInit
        HrInit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[3])
        HrInit(obj)

        # vtable[18] = SetOverlayIcon(hwnd, hIcon, pszDescription)
        SetOverlay = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p,
            wintypes.HWND, ctypes.c_void_p, ctypes.c_wchar_p)(vtable[18])
        SetOverlay(obj, hwnd, hicon or None, description or None)

        # vtable[2] = Release
        Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        Release(obj)
    except Exception:
        pass


def _make_tab_icon_img(shape: str, size: int,
                       color: tuple = (255, 140, 0, 255)) -> "Image.Image":
    """Рисует иконку вкладки заданным цветом через PIL."""
    import math
    big = size * 3
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    sc  = big / 16.0
    c   = color

    def b(x, y, w, h):
        d.rectangle([round(x*sc), round(y*sc),
                     round((x+w)*sc), round((y+h)*sc)], fill=c)

    if shape == "bars":                      # 📊 Приборная панель
        b(1.0, 11.0, 2.5,  5.0)
        b(4.5,  7.0, 2.5,  9.0)
        b(8.0,  9.0, 2.5,  7.0)
        b(11.5, 4.0, 2.5, 12.0)

    elif shape == "lines":                   # 📋 Логи
        b(1.0,  2.5, 14.0, 2.0)
        b(1.0,  7.0, 14.0, 2.0)
        b(1.0, 11.5, 10.0, 2.0)

    elif shape == "link":                    # 🔗 Подключения
        cr = round(2.8 * sc)
        for cx_, cy_ in [(3.5*sc, 8*sc), (12.5*sc, 8*sc)]:
            d.ellipse([cx_-cr, cy_-cr, cx_+cr, cy_+cr], fill=c)
        lw = max(2, round(2.0 * sc))
        d.line([(round(3.5*sc), round(8*sc)),
                (round(12.5*sc), round(8*sc))], fill=c, width=lw)

    elif shape == "doc":                     # 📝 Запросы
        body = [(round(x*sc), round(y*sc)) for x, y in
                [(2,1),(10,1),(14,5),(14,15),(2,15)]]
        d.polygon(body, fill=c)
        fold = [(round(x*sc), round(y*sc)) for x, y in [(10,1),(14,5),(10,5)]]
        d.polygon(fold, fill=(0, 0, 0, 0))
        for ly in [6.5, 9.0, 11.5]:
            d.rectangle([round(3.5*sc), round(ly*sc),
                         round(12*sc),  round((ly+1.4)*sc)], fill=(0, 0, 0, 0))

    elif shape == "gear":                    # ⚙️ Настройки
        n = 8
        ro, ri, rh = big*0.44, big*0.31, big*0.15
        cx_, cy_ = big/2, big/2
        pts = [(cx_ + (ro if i%2==0 else ri) * math.cos(math.radians(i*180/n - 90)),
                cy_ + (ro if i%2==0 else ri) * math.sin(math.radians(i*180/n - 90)))
               for i in range(n*2)]
        d.polygon(pts, fill=c)
        d.ellipse([cx_-rh, cy_-rh, cx_+rh, cy_+rh], fill=(0, 0, 0, 0))

    elif shape == "bell":                    # 🔔 Уведомления
        cx_, cy_ = big/2, big/2
        pts = [
            (round(4.0*sc), round(12.5*sc)),
            (round(3.0*sc), round(10.5*sc)),
            (round(4.0*sc),  round(6.5*sc)),
            (round(6.0*sc),  round(4.5*sc)),
            (round(7.5*sc),  round(3.5*sc)),
            (round(8.5*sc),  round(3.0*sc)),
            (round(8.5*sc),  round(2.0*sc)),
            (round(7.5*sc),  round(2.0*sc)),
            (round(7.5*sc),  round(3.5*sc)),
            (round(8.5*sc),  round(3.0*sc)),
            (round(9.5*sc),  round(3.0*sc)),
            (round(10.5*sc), round(3.5*sc)),
            (round(12.0*sc), round(4.5*sc)),
            (round(13.0*sc), round(6.5*sc)),
            (round(14.0*sc), round(10.5*sc)),
            (round(13.0*sc), round(12.5*sc)),
        ]
        body = [
            (round(4.0*sc),  round(12.5*sc)),
            (round(3.0*sc),  round(10.5*sc)),
            (round(4.2*sc),  round(6.8*sc)),
            (round(6.2*sc),  round(4.8*sc)),
            (round(7.8*sc),  round(3.8*sc)),
            (round(8.0*sc),  round(2.2*sc)),
            (round(9.0*sc),  round(2.0*sc)),
            (round(9.0*sc),  round(3.8*sc)),
            (round(10.2*sc), round(4.8*sc)),
            (round(12.0*sc), round(6.8*sc)),
            (round(13.0*sc), round(10.5*sc)),
            (round(12.0*sc), round(12.5*sc)),
        ]
        d.polygon(body, fill=c)
        clapper_r = round(1.3*sc)
        bx, by = round(8.5*sc), round(13.5*sc)
        d.ellipse([bx-clapper_r, by-clapper_r, bx+clapper_r, by+clapper_r], fill=c)

    elif shape == "grid":                    # 🛠 Сервисы (2×2 квадрата)
        b(1.0, 1.0, 6.0, 6.0)
        b(9.0, 1.0, 6.0, 6.0)
        b(1.0, 9.0, 6.0, 6.0)
        b(9.0, 9.0, 6.0, 6.0)

    elif shape == "clock":                   # ⏰ Напоминания
        lw = max(1, round(1.5 * sc))
        d.ellipse([round(1.5*sc), round(1.5*sc),
                   round(14.5*sc), round(14.5*sc)], outline=c, width=lw)
        cx_, cy_ = big / 2, big / 2
        # часовая стрелка (короткая, влево-вверх ~10:10)
        d.line([(cx_, cy_),
                (cx_ - round(2.5*sc), cy_ - round(3.0*sc))], fill=c, width=lw)
        # минутная стрелка (длинная, вверх)
        d.line([(cx_, cy_),
                (cx_, cy_ - round(5.0*sc))], fill=c, width=lw)
        # точка в центре
        r0 = max(1, round(0.8 * sc))
        d.ellipse([cx_-r0, cy_-r0, cx_+r0, cy_+r0], fill=c)

    return img.resize((size, size), Image.LANCZOS)


@functools.lru_cache(maxsize=32)
def _get_tab_icon(shape: str, size: int = 16) -> Optional["ctk.CTkImage"]:
    """Иконка вкладки — кэшируется по (shape, size) с ограничением в 32 записи."""
    if not _PIL_OK:
        return None
    light_gray = (200, 200, 200, 255)
    dark_gray  = (70,  70,  70, 255)
    light_img  = _make_tab_icon_img(shape, size, dark_gray)
    dark_img   = _make_tab_icon_img(shape, size, light_gray)
    return ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))


def _invalidate_image_caches() -> None:
    """Сбрасывает все кэши PIL-изображений (вызывается при смене темы)."""
    _get_pin_ctk_image.cache_clear()
    _get_time_ctk_image.cache_clear()
    _get_time_quarte_ctk_image.cache_clear()
    _get_load_ctk_image.cache_clear()
    _get_copy_ctk_image.cache_clear()
    _get_play_ctk_image.cache_clear()
    _get_bell_ctk_image.cache_clear()
    _get_tab_icon.cache_clear()


def _make_load_img(size: int, color: tuple) -> "Image.Image":
    """Иконка экспорта: стрелка вниз + дуга (load.svg)."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    sc   = size / 24.0
    lw   = max(1, round(2 * sc))

    # Шахта стрелки (прямоугольник x=[11,13], y=[4,13])
    draw.rectangle(
        [round(11*sc), round(4*sc), round(13*sc), round(13*sc)],
        fill=color)

    # Наконечник стрелки (треугольник вниз)
    ah = [
        (round(6.5*sc),  round(8.5*sc)),
        (round(17.5*sc), round(8.5*sc)),
        (round(12*sc),   round(14.5*sc)),
    ]
    draw.polygon(ah, fill=color)

    # Дуга снизу (тарелка экспорта) — от SVG: от (5.24,14.81) через (12,20) до (18.76,14.81)
    draw.arc(
        [round(4.5*sc), round(13*sc), round(19.5*sc), round(22*sc)],
        start=205, end=335, fill=color, width=lw)

    return img


def _make_copy_img(size: int, color: tuple) -> "Image.Image":
    """Иконка копирования: два перекрывающихся прямоугольника (copy.svg)."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    sc   = size / 24.0
    lw   = max(1, round(2 * sc))

    # Задний прямоугольник (правый верхний)
    draw.rectangle(
        [round(9*sc), round(3*sc), round(21*sc), round(15*sc)],
        outline=color, width=lw)

    # Передний прямоугольник (левый нижний)
    draw.rectangle(
        [round(3*sc), round(9*sc), round(15*sc), round(21*sc)],
        outline=color, width=lw)

    return img


@functools.lru_cache(maxsize=8)
def _get_load_ctk_image(size: int = 14) -> Optional["ctk.CTkImage"]:
    """Иконка экспорта (кэшируется)."""
    if not _PIL_OK:
        return None
    dark_color  = (255, 255, 255, 220)
    light_color = (40,  40,  40,  220)
    dark_img  = _make_load_img(size * 4, dark_color)
    light_img = _make_load_img(size * 4, light_color)
    return ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))


@functools.lru_cache(maxsize=8)
def _get_copy_ctk_image(size: int = 14) -> Optional["ctk.CTkImage"]:
    """Иконка копирования (кэшируется)."""
    if not _PIL_OK:
        return None
    dark_color  = (255, 255, 255, 220)
    light_color = (40,  40,  40,  220)
    dark_img  = _make_copy_img(size * 4, dark_color)
    light_img = _make_copy_img(size * 4, light_color)
    return ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))


@functools.lru_cache(maxsize=8)
def _get_play_ctk_image(size: int = 24) -> Optional["ctk.CTkImage"]:
    """Иконка play-треугольника в цвете акцентной темы (кэшируется)."""
    if not _PIL_OK:
        return None

    def _hex_to_rgba(h: str) -> tuple:
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)

    def _draw(color: tuple) -> "Image.Image":
        big = size * 4
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pad = big * 0.18
        draw.polygon([(pad, pad), (big - pad, big / 2), (pad, big - pad)], fill=color)
        return img.resize((size, size), Image.LANCZOS)

    light_img = _draw(_hex_to_rgba(theme_colors.accent()))
    dark_img  = _draw(_hex_to_rgba(theme_colors.hover()))
    return ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))


# ─────────────────────────────────────────────────────────────────────────────
class VisualizationSettingsDialog(ctk.CTkToplevel):
    """Модальное окно настройки типов визуализации по колонкам."""

    _HEAT_T   = {"Индикатор 2 (Тепловой)"}
    _IND_FULL = {"Индикатор 1", "Индикатор 2", "Индикатор - круги", "Пламя"}
    _HEADER_COLORS = ["(по умолчанию)"] + list(_VIZ_COLOR_MAP.keys())
    _MARKER_SHAPES = ["Нет", "Круг", "Квадрат", "Треугольник", "Ромб"]
    _SVET_T   = {"Светофор"}
    _CLOCK_T  = {"Секундомер"}
    _WAVE_T   = {"Волна"}
    _ECG_T    = {"ЭКГ"}
    _RINGS_T  = {"Кольца"}
    _TIMER_ANIM_TYPES = ["Счётчик", "Прогресс-бар"]
    _TIMER_COLORS     = ["(по умолчанию)"] + list(_VIZ_COLOR_MAP.keys())

    def __init__(self, parent, columns: list, current_configs: dict,
                 panel_config: dict = None):
        super().__init__(parent)
        self.withdraw()
        self.title("Настройки визуализации")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.result: Optional[dict] = None
        self._columns      = columns
        self._configs      = {c: dict(current_configs.get(c, {})) for c in columns}
        self._panel_config = dict(panel_config or {})
        self._col_widgets: dict = {}
        self._build()
        self.update_idletasks()          # layout вычислен пока окно скрыто
        self._place_center(parent)       # позиционируем сразу — без after()
        self.deiconify()
        def _safe_grab():
            try:
                self.grab_set()
            except Exception:
                pass
        self.after(20, _safe_grab)       # grab после отрисовки

    def _place_center(self, parent):
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        if w < 50:
            w = self.winfo_width()
        if h < 50:
            h = self.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x  = px + (pw - w) // 2
        y  = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _center_popup(self, popup):
        popup.update_idletasks()
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        w,  h  = popup.winfo_width(), popup.winfo_height()
        popup.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _open_col_picker(self, btn, text_fn):
        if not self._columns:
            return
        popup = ctk.CTkToplevel(self)
        popup.title("Видимость колонок")
        popup.transient(self)
        popup.grab_set()
        popup.resizable(False, False)

        btn_f = ctk.CTkFrame(popup, fg_color="transparent")
        btn_f.pack(padx=10, pady=(10, 4), fill="x")
        ctk.CTkButton(btn_f, text="Выбрать все", width=100, height=26,
                      command=lambda: [v.set(True)
                                       for v in self._visible_vars.values()]).grid(
            row=0, column=0, padx=(0, 6))
        ctk.CTkButton(btn_f, text="Снять все", width=90, height=26,
                      fg_color=("gray70", "gray30"),
                      command=lambda: [v.set(False)
                                       for v in self._visible_vars.values()]).grid(
            row=0, column=1)

        h = min(320, len(self._columns) * 36 + 16)
        cf = ctk.CTkScrollableFrame(popup, width=240, height=h)
        cf.pack(padx=10, pady=4, fill="both", expand=True)
        for col, var in self._visible_vars.items():
            ctk.CTkCheckBox(cf, text=col, variable=var).pack(anchor="w", pady=3)

        def _close():
            btn.configure(text=text_fn())
            popup.destroy()

        ctk.CTkButton(popup, text="OK", width=90, height=30,
                      fg_color=[theme_colors.accent(), theme_colors.hover()],
                      hover_color=[theme_colors.hover(), theme_colors.dark()],
                      command=_close).pack(pady=(4, 10))
        popup.protocol("WM_DELETE_WINDOW", _close)
        popup.after(60, lambda: self._center_popup(popup))

    def _build(self):
        # ── Настройки панели (заголовок + маркер) ────────────────────────────
        pf = ctk.CTkFrame(self, corner_radius=8)
        pf.pack(padx=12, pady=(10, 4), fill="x")
        ctk.CTkLabel(pf, text="Настройки панели",
                     font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=0, columnspan=6, sticky="w", padx=8, pady=(6, 4))

        _PW = 130
        ctk.CTkLabel(pf, text="Цвет заголовка:", anchor="w").grid(
            row=1, column=0, sticky="w", padx=(8, 4), pady=(2, 6))
        self._header_color_var = ctk.StringVar(
            value=self._panel_config.get("header_color", "(по умолчанию)"))
        ctk.CTkComboBox(pf, values=self._HEADER_COLORS,
                        variable=self._header_color_var,
                        state="readonly", width=_PW).grid(
            row=1, column=1, sticky="w", padx=(0, 16), pady=(2, 6))

        ctk.CTkLabel(pf, text="Форма маркера:", anchor="w").grid(
            row=1, column=2, sticky="w", padx=(8, 4), pady=(2, 6))
        self._marker_shape_var = ctk.StringVar(
            value=self._panel_config.get("marker_shape", "Нет"))
        ctk.CTkComboBox(pf, values=self._MARKER_SHAPES,
                        variable=self._marker_shape_var,
                        state="readonly", width=_PW).grid(
            row=1, column=3, sticky="w", padx=(0, 16), pady=(2, 6))

        ctk.CTkLabel(pf, text="Цвет маркера:", anchor="w").grid(
            row=1, column=4, sticky="w", padx=(8, 4), pady=(2, 6))
        self._marker_color_var = ctk.StringVar(
            value=self._panel_config.get("marker_color", "Бирюзовый"))
        ctk.CTkComboBox(pf, values=list(_VIZ_COLOR_MAP.keys()),
                        variable=self._marker_color_var,
                        state="readonly", width=_PW).grid(
            row=1, column=5, sticky="w", padx=(0, 8), pady=(2, 6))

        # ── Видимость колонок ────────────────────────────────────────────────
        ctk.CTkLabel(pf, text="Отображать колонки:", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(8, 4), pady=(2, 8))
        _saved_vis = set(self._panel_config.get("visible_columns") or [])
        if not _saved_vis:
            _saved_vis = set(self._columns)
        self._visible_vars = {
            col: ctk.BooleanVar(value=(col in _saved_vis))
            for col in self._columns
        }

        def _col_btn_text():
            if not self._columns:
                return "—"
            n = sum(1 for v in self._visible_vars.values() if v.get())
            return "Все" if n == len(self._columns) else f"{n} из {len(self._columns)}"

        self._col_vis_btn = ctk.CTkButton(
            pf, text=_col_btn_text(), width=110, height=26,
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            text_color=("gray10", "gray90"),
            command=lambda: self._open_col_picker(self._col_vis_btn, _col_btn_text))
        self._col_vis_btn.grid(row=2, column=1, columnspan=2, sticky="w",
                               padx=(0, 16), pady=(2, 8))

        ctk.CTkLabel(pf, text="Анимация счётчика:", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(8, 4), pady=(2, 8))
        self._timer_anim_var = ctk.StringVar(
            value=self._panel_config.get("timer_anim", "Счётчик"))
        ctk.CTkSegmentedButton(pf, values=self._TIMER_ANIM_TYPES,
                               variable=self._timer_anim_var).grid(
            row=3, column=1, columnspan=2, sticky="w", padx=(0, 16), pady=(2, 8))

        ctk.CTkLabel(pf, text="Цвет счётчика:", anchor="w").grid(
            row=3, column=4, sticky="w", padx=(8, 4), pady=(2, 8))
        self._timer_color_var = ctk.StringVar(
            value=self._panel_config.get("timer_color", "(по умолчанию)"))
        ctk.CTkComboBox(pf, values=self._TIMER_COLORS,
                        variable=self._timer_color_var,
                        state="readonly", width=_PW).grid(
            row=3, column=5, sticky="w", padx=(0, 8), pady=(2, 8))

        if not self._columns:
            ctk.CTkLabel(self, text="Нет колонок. Сначала выполните запрос.",
                         wraplength=300).pack(padx=20, pady=20)
            ctk.CTkButton(self, text="Закрыть", command=self._close).pack(pady=(0, 10))
            return

        scroll_h = min(520, len(self._columns) * 220 + 20)
        sf = ctk.CTkScrollableFrame(self, width=480, height=scroll_h)
        sf.pack(padx=12, pady=(4, 10), fill="both", expand=True)
        sf.grid_columnconfigure(0, weight=1)
        for i, col in enumerate(self._columns):
            self._build_col_row(sf, col, i)

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.pack(pady=(0, 10))
        ctk.CTkButton(btn, text="Сохранить", width=110,
                      fg_color=["#0D9488", "#0B7A72"],
                      hover_color=["#0B7A72", "#085E58"],
                      command=self._save).grid(row=0, column=0, padx=6)
        ctk.CTkButton(btn, text="Отмена", width=90,
                      fg_color=("gray70", "gray30"),
                      command=self._close).grid(row=0, column=1, padx=6)
        self.bind("<Escape>", lambda _: self._close())
        self.after(0, lambda: setup_paste_bindings(self))

    def _build_col_row(self, parent, col: str, idx: int):
        cfg   = self._configs.get(col, {})
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=idx, column=0, sticky="ew", padx=4, pady=4)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text=f'Колонка: "{col}"',
                     font=ctk.CTkFont(weight="bold"), anchor="w"
                     ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(6, 2))

        ctk.CTkLabel(frame, text="Тип:").grid(row=1, column=0, sticky="w", padx=(8, 4), pady=2)
        type_var = ctk.StringVar(value=cfg.get("type", "Стандартный"))
        ctk.CTkComboBox(frame, values=_VIZ_TYPES, variable=type_var,
                        state="readonly", width=160
                        ).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        color_lbl = ctk.CTkLabel(frame, text="Цвет:")
        color_lbl.grid(row=1, column=2, sticky="w", padx=(8, 4), pady=2)
        cur_name  = next((k for k, v in _VIZ_COLOR_MAP.items()
                          if v == cfg.get("color", "#0D9488")), "Бирюзовый")
        color_var = ctk.StringVar(value=cur_name)
        color_cb  = ctk.CTkComboBox(frame, values=list(_VIZ_COLOR_MAP.keys()),
                                    variable=color_var, state="readonly", width=130)
        color_cb.grid(row=1, column=3, sticky="w", padx=(4, 8), pady=2)

        extra = ctk.CTkFrame(frame, fg_color="transparent")
        extra.grid(row=2, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 4))

        cold_color_var    = ctk.StringVar(value=cfg.get("cold_color",          "Зелёный"))
        warm_color_var    = ctk.StringVar(value=cfg.get("warm_color",          "Оранжевый"))
        crit_color_var    = ctk.StringVar(value=cfg.get("crit_color",          "Красный"))
        age_cold_var      = ctk.StringVar(value=str(cfg.get("age_cold",        "10")))
        age_warm_var      = ctk.StringVar(value=str(cfg.get("age_warm",        "20")))
        age_crit_var      = ctk.StringVar(value=str(cfg.get("age_crit",        "40")))
        max_blocks_var    = ctk.StringVar(value=str(cfg.get("max_blocks",     "10")))
        speed_var         = ctk.StringVar(value=str(cfg.get("speed",          "650")))
        interval_min_var  = ctk.StringVar(value=str(cfg.get("interval_min",   "1")))
        age_threshold_var = ctk.StringVar(value=str(cfg.get("age_threshold",  "0")))
        age_color_var     = ctk.StringVar(value=cfg.get("age_color",          "(нет)"))
        max_amplitude_var = ctk.StringVar(value=str(cfg.get("max_amplitude",  "10")))
        fade_minutes_var  = ctk.StringVar(value=str(cfg.get("fade_minutes",   "10")))
        max_rings_var     = ctk.StringVar(value=str(cfg.get("max_rings",      "5")))

        _LW = 175

        def _age_rows(parent, row_start):
            ctk.CTkFrame(parent, height=1, fg_color=("gray65", "gray40")).grid(
                row=row_start, column=0, columnspan=2, sticky="ew", pady=(6, 4))
            ctk.CTkLabel(parent, text="Возраст записи > (мин):", anchor="w",
                         width=_LW).grid(row=row_start + 1, column=0, sticky="w",
                                         padx=(0, 6), pady=2)
            ctk.CTkEntry(parent, textvariable=age_threshold_var, width=70).grid(
                row=row_start + 1, column=1, sticky="w", pady=2)
            ctk.CTkLabel(parent, text="Цвет возраста:", anchor="w",
                         width=_LW).grid(row=row_start + 2, column=0, sticky="w",
                                         padx=(0, 6), pady=2)
            ctk.CTkComboBox(parent, values=["(нет)"] + list(_VIZ_COLOR_MAP.keys()),
                            variable=age_color_var, state="readonly", width=130).grid(
                row=row_start + 2, column=1, sticky="w", pady=2)

        heat_f = ctk.CTkFrame(extra, fg_color="transparent")
        _color_opts = list(_VIZ_COLOR_MAP.keys())
        ctk.CTkLabel(heat_f, text="Холодный цвет:", anchor="w", width=_LW).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkComboBox(heat_f, values=_color_opts, variable=cold_color_var,
                        state="readonly", width=130).grid(row=0, column=1, sticky="w", pady=2)
        ctk.CTkLabel(heat_f, text="Тёплый цвет:", anchor="w", width=_LW).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkComboBox(heat_f, values=_color_opts, variable=warm_color_var,
                        state="readonly", width=130).grid(row=1, column=1, sticky="w", pady=2)
        ctk.CTkLabel(heat_f, text="Критический цвет:", anchor="w", width=_LW).grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkComboBox(heat_f, values=_color_opts, variable=crit_color_var,
                        state="readonly", width=130).grid(row=2, column=1, sticky="w", pady=2)
        ctk.CTkFrame(heat_f, height=1, fg_color=("gray65", "gray40")).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(6, 4))
        ctk.CTkLabel(heat_f, text="Возраст записи > (мин):", anchor="w", width=_LW).grid(
            row=4, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkLabel(heat_f, text="Возраст Холодный (мин):", anchor="w", width=_LW).grid(
            row=5, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(heat_f, textvariable=age_cold_var, width=70).grid(
            row=5, column=1, sticky="w", pady=2)
        ctk.CTkLabel(heat_f, text="Возраст Тёплый (мин):", anchor="w", width=_LW).grid(
            row=6, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(heat_f, textvariable=age_warm_var, width=70).grid(
            row=6, column=1, sticky="w", pady=2)
        ctk.CTkLabel(heat_f, text="Возраст Критический (мин):", anchor="w", width=_LW).grid(
            row=7, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(heat_f, textvariable=age_crit_var, width=70).grid(
            row=7, column=1, sticky="w", pady=2)

        mb_f = ctk.CTkFrame(extra, fg_color="transparent")
        ctk.CTkLabel(mb_f, text="Макс. блоков:", anchor="w", width=_LW).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(mb_f, textvariable=max_blocks_var, width=70).grid(
            row=0, column=1, sticky="w", pady=2)
        ctk.CTkLabel(mb_f, text="Скорость (мс):", anchor="w", width=_LW).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(mb_f, textvariable=speed_var, width=70).grid(
            row=1, column=1, sticky="w", pady=2)
        ctk.CTkLabel(mb_f, text="Интервал (мин):", anchor="w", width=_LW).grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(mb_f, textvariable=interval_min_var, width=70).grid(
            row=2, column=1, sticky="w", pady=2)
        _age_rows(mb_f, 3)

        sv_f = ctk.CTkFrame(extra, fg_color="transparent")
        ctk.CTkLabel(sv_f, text="Скорость (мс):", anchor="w", width=_LW).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(sv_f, textvariable=speed_var, width=70).grid(
            row=0, column=1, sticky="w", pady=2)
        ctk.CTkLabel(sv_f, text="Интервал (мин):", anchor="w", width=_LW).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(sv_f, textvariable=interval_min_var, width=70).grid(
            row=1, column=1, sticky="w", pady=2)

        clock_f = ctk.CTkFrame(extra, fg_color="transparent")
        ctk.CTkLabel(clock_f, text="Возраст записи > (мин):", anchor="w",
                     width=_LW).grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(clock_f, textvariable=age_threshold_var, width=70).grid(
            row=0, column=1, sticky="w", pady=2)
        ctk.CTkLabel(clock_f, text="Цвет возраста:", anchor="w",
                     width=_LW).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkComboBox(clock_f, values=["(нет)"] + list(_VIZ_COLOR_MAP.keys()),
                        variable=age_color_var, state="readonly", width=130).grid(
            row=1, column=1, sticky="w", pady=2)

        wave_f = ctk.CTkFrame(extra, fg_color="transparent")
        ctk.CTkLabel(wave_f, text="Макс. амплитуда:", anchor="w", width=_LW).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(wave_f, textvariable=max_amplitude_var, width=70).grid(
            row=0, column=1, sticky="w", pady=2)
        ctk.CTkLabel(wave_f, text="Скорость (мс):", anchor="w", width=_LW).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(wave_f, textvariable=speed_var, width=70).grid(
            row=1, column=1, sticky="w", pady=2)
        ctk.CTkLabel(wave_f, text="Интервал (мин):", anchor="w", width=_LW).grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(wave_f, textvariable=interval_min_var, width=70).grid(
            row=2, column=1, sticky="w", pady=2)
        _age_rows(wave_f, 3)

        ecg_f = ctk.CTkFrame(extra, fg_color="transparent")
        ctk.CTkLabel(ecg_f, text="Скорость (мс):", anchor="w", width=_LW).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(ecg_f, textvariable=speed_var, width=70).grid(
            row=0, column=1, sticky="w", pady=2)
        ctk.CTkLabel(ecg_f, text="Затухание (мин):", anchor="w", width=_LW).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(ecg_f, textvariable=fade_minutes_var, width=70).grid(
            row=1, column=1, sticky="w", pady=2)
        _age_rows(ecg_f, 2)

        rings_f = ctk.CTkFrame(extra, fg_color="transparent")
        ctk.CTkLabel(rings_f, text="Макс. колец:", anchor="w", width=_LW).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(rings_f, textvariable=max_rings_var, width=70).grid(
            row=0, column=1, sticky="w", pady=2)
        ctk.CTkLabel(rings_f, text="Скорость (мс):", anchor="w", width=_LW).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(rings_f, textvariable=speed_var, width=70).grid(
            row=1, column=1, sticky="w", pady=2)
        ctk.CTkLabel(rings_f, text="Интервал (мин):", anchor="w", width=_LW).grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(rings_f, textvariable=interval_min_var, width=70).grid(
            row=2, column=1, sticky="w", pady=2)
        _age_rows(rings_f, 3)

        # ── Сигнал (коллапсируемый блок) ─────────────────────────────────────
        sig_cfg = cfg.get("signal", {})
        ctk.CTkFrame(frame, height=1, fg_color=("gray65", "gray40")).grid(
            row=3, column=0, columnspan=4, sticky="ew", padx=8, pady=(6, 2))

        sig_text_var  = ctk.StringVar(value=sig_cfg.get("text", ""))
        sig_type_var  = ctk.StringVar(value=sig_cfg.get("type_name", "Стандартный"))
        _sig_cn       = next((k for k, v in _VIZ_COLOR_MAP.items()
                              if v == sig_cfg.get("color", "#0D9488")), "Бирюзовый")
        sig_color_var = ctk.StringVar(value=_sig_cn)
        sig_f = ctk.CTkFrame(frame, fg_color="transparent")
        sig_f.grid(row=5, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 8))

        _sig_has_value = bool(sig_cfg.get("text", "").strip())
        _sig_open      = [_sig_has_value]

        def _toggle_sig(btn=None, f=sig_f, flag=_sig_open):
            flag[0] = not flag[0]
            if flag[0]:
                f.grid()
                if btn:
                    btn.configure(text="▾ Сигнал")
            else:
                f.grid_remove()
                if btn:
                    btn.configure(text="▸ Сигнал")

        sig_toggle_btn = ctk.CTkButton(
            frame,
            text="▾ Сигнал" if _sig_has_value else "▸ Сигнал",
            anchor="w", width=90, height=22,
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(weight="bold"),
            command=lambda: _toggle_sig(sig_toggle_btn))
        sig_toggle_btn.grid(row=4, column=0, columnspan=4, sticky="w",
                            padx=8, pady=(2, 2))

        if not _sig_has_value:
            sig_f.grid_remove()
        ctk.CTkLabel(sig_f, text="Текст (поиск):", anchor="w", width=_LW).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkEntry(sig_f, textvariable=sig_text_var, width=200).grid(
            row=0, column=1, columnspan=3, sticky="w", pady=2)
        ctk.CTkLabel(sig_f, text="Анимация:", anchor="w", width=_LW).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkComboBox(sig_f, values=_VIZ_TYPES, variable=sig_type_var,
                        state="readonly", width=160).grid(
            row=1, column=1, sticky="w", padx=(0, 8), pady=2)
        ctk.CTkLabel(sig_f, text="Цвет:", anchor="w").grid(
            row=1, column=2, sticky="w", padx=(0, 4), pady=2)
        ctk.CTkComboBox(sig_f, values=list(_VIZ_COLOR_MAP.keys()),
                        variable=sig_color_var, state="readonly", width=130).grid(
            row=1, column=3, sticky="w", pady=2)

        def _refresh(*_):
            for _f in (heat_f, mb_f, sv_f, clock_f, wave_f, ecg_f, rings_f):
                _f.grid_forget()
            t = type_var.get()
            if t == "Стандартный":
                color_lbl.grid_remove()
                color_cb.grid_remove()
            else:
                if t in self._HEAT_T:
                    color_lbl.grid_remove()
                    color_cb.grid_remove()
                    heat_f.grid(row=0, column=0)
                else:
                    color_lbl.grid()
                    color_cb.grid()
                    if t in self._IND_FULL:
                        mb_f.grid(row=0, column=0)
                    elif t in self._SVET_T:
                        sv_f.grid(row=0, column=0)
                    elif t in self._CLOCK_T:
                        clock_f.grid(row=0, column=0)
                    elif t in self._WAVE_T:
                        wave_f.grid(row=0, column=0)
                    elif t in self._ECG_T:
                        ecg_f.grid(row=0, column=0)
                    elif t in self._RINGS_T:
                        rings_f.grid(row=0, column=0)

        type_var.trace_add("write", _refresh)
        _refresh()

        self._col_widgets[col] = {
            "type": type_var, "color": color_var,
            "cold_color": cold_color_var, "warm_color": warm_color_var,
            "crit_color": crit_color_var,
            "age_cold": age_cold_var, "age_warm": age_warm_var, "age_crit": age_crit_var,
            "max_blocks": max_blocks_var, "speed": speed_var,
            "interval_min": interval_min_var,
            "age_threshold": age_threshold_var, "age_color": age_color_var,
            "max_amplitude": max_amplitude_var, "fade_minutes": fade_minutes_var,
            "max_rings": max_rings_var,
            "signal_text": sig_text_var, "signal_type": sig_type_var, "signal_color": sig_color_var,
        }

    def _save(self):
        _vis = [c for c, v in self._visible_vars.items() if v.get()]
        result = {
            "__panel__": {
                "header_color":    self._header_color_var.get(),
                "marker_shape":    self._marker_shape_var.get(),
                "marker_color":    self._marker_color_var.get(),
                "visible_columns": [] if len(_vis) == len(self._columns) else _vis,
                "timer_anim":      self._timer_anim_var.get(),
                "timer_color":     self._timer_color_var.get(),
            }
        }
        for col, w in self._col_widgets.items():
            t = w["type"].get()
            if t == "Стандартный":
                continue
            entry = {"type": t}
            entry["color"] = _VIZ_COLOR_MAP.get(w["color"].get(), "#0D9488")

            def _flt(key, default, mn=0.0):
                try:
                    return max(mn, float(w[key].get().replace(",", ".")))
                except (ValueError, KeyError):
                    return default

            def _int(key, default, mn=1):
                try:
                    return max(mn, int(w[key].get()))
                except (ValueError, KeyError):
                    return default

            def _age():
                entry["age_threshold"] = _flt("age_threshold", 0.0, 0.0)
                ac = w["age_color"].get()
                if ac and ac != "(нет)":
                    entry["age_color"] = ac

            if t in self._HEAT_T:
                entry["cold_color"] = w["cold_color"].get()
                entry["warm_color"] = w["warm_color"].get()
                entry["crit_color"] = w["crit_color"].get()
                entry["age_cold"]   = _flt("age_cold", 10.0, 0.1)
                entry["age_warm"]   = _flt("age_warm", 20.0, 0.2)
                entry["age_crit"]   = _flt("age_crit", 40.0, 0.3)
            elif t in self._IND_FULL:
                entry["max_blocks"]   = _int("max_blocks", 10)
                entry["speed"]        = _int("speed", 650, 100)
                entry["interval_min"] = _flt("interval_min", 1.0, 0.01)
                _age()
            elif t in self._SVET_T:
                entry["speed"]        = _int("speed", 500, 100)
                entry["interval_min"] = _flt("interval_min", 1.0, 0.01)
            elif t in self._CLOCK_T:
                _age()
            elif t in self._WAVE_T:
                entry["max_amplitude"] = _int("max_amplitude", 10, 2)
                entry["speed"]         = _int("speed", 40, 20)
                entry["interval_min"]  = _flt("interval_min", 1.0, 0.01)
                _age()
            elif t in self._ECG_T:
                entry["speed"]        = _int("speed", 40, 20)
                entry["fade_minutes"] = _flt("fade_minutes", 10.0, 0.1)
                _age()
            elif t in self._RINGS_T:
                entry["max_rings"]    = _int("max_rings", 5)
                entry["speed"]        = _int("speed", 80, 20)
                entry["interval_min"] = _flt("interval_min", 1.0, 0.01)
                _age()

            sig_text = w["signal_text"].get().strip()
            if sig_text:
                entry["signal"] = {
                    "text":      sig_text,
                    "type_name": w["signal_type"].get(),
                    "color":     _VIZ_COLOR_MAP.get(w["signal_color"].get(), "#0D9488"),
                }

            result[col] = entry
        self.result = result
        self._close()

    def _close(self):
        _master = self.master
        self.destroy()
        try:
            _master.focus_set()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
class FrameEditDialog(ctk.CTkToplevel):
    """Модальное окно редактирования фрейма приборной панели."""

    _RENDER_TYPES = ["Таблица", "Строчный график", "Столбчатый график"]
    _TIMER_ANIM_TYPES = ["Счётчик", "Прогресс-бар"]
    _TIMER_COLORS = ["(по умолчанию)"] + list(_VIZ_COLOR_MAP.keys())

    def __init__(self, parent, query_names: list,
                 current_query: str = "", current_render_type: str = "Таблица",
                 current_timer_anim: str = "Счётчик",
                 current_timer_color: str = "(по умолчанию)"):
        super().__init__(parent)
        self.withdraw()
        self.title("Настройки фрейма")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.result = None  # (query_name, render_type, timer_anim, timer_color, run_now: bool) | None
        self._query_names        = query_names
        self._current_query      = current_query
        self._current_render     = current_render_type
        self._current_timer_anim = current_timer_anim
        self._current_timer_color = current_timer_color
        self._build()
        self.update_idletasks()
        self._place_center(parent)
        self.deiconify()
        def _safe_grab():
            try:
                self.grab_set()
            except Exception:
                pass
        self.after(20, _safe_grab)

    def _place_center(self, parent):
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        if w < 50:
            w = self.winfo_width()
        if h < 50:
            h = self.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x  = px + (pw - w) // 2
        y  = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Запрос:", anchor="w").grid(
            row=0, column=0, padx=20, pady=(20, 4), sticky="w")
        vals = ["Выберите запрос"] + self._query_names
        init = self._current_query if self._current_query in self._query_names \
               else "Выберите запрос"
        self._query_var = ctk.StringVar(value=init)
        ctk.CTkComboBox(self, values=vals, variable=self._query_var,
                        state="readonly", width=320).grid(
            row=1, column=0, padx=20, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(self, text="Тип отрисовки:", anchor="w").grid(
            row=2, column=0, padx=20, pady=(4, 4), sticky="w")
        self._render_var = ctk.StringVar(value=self._current_render)
        ctk.CTkSegmentedButton(self, values=self._RENDER_TYPES,
                               variable=self._render_var).grid(
            row=3, column=0, padx=20, pady=(0, 16), sticky="ew")

        ctk.CTkLabel(self, text="Анимация счётчика обновления:", anchor="w").grid(
            row=4, column=0, padx=20, pady=(4, 4), sticky="w")
        self._timer_anim_var = ctk.StringVar(value=self._current_timer_anim)
        ctk.CTkSegmentedButton(self, values=self._TIMER_ANIM_TYPES,
                               variable=self._timer_anim_var).grid(
            row=5, column=0, padx=20, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(self, text="Цвет счётчика:", anchor="w").grid(
            row=6, column=0, padx=20, pady=(4, 4), sticky="w")
        self._timer_color_var = ctk.StringVar(value=self._current_timer_color)
        ctk.CTkComboBox(self, values=self._TIMER_COLORS,
                        variable=self._timer_color_var,
                        state="readonly", width=320).grid(
            row=7, column=0, padx=20, pady=(0, 20), sticky="ew")

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.grid(row=8, column=0, padx=20, pady=(0, 20))
        ctk.CTkButton(btn_f, text="▶ Запустить", width=120,
                      fg_color=[theme_colors.accent(), theme_colors.hover()],
                      hover_color=[theme_colors.hover(), theme_colors.dark()],
                      command=self._on_run).grid(row=0, column=0, padx=4)
        ctk.CTkButton(btn_f, text="Сохранить", width=100,
                      command=self._on_save).grid(row=0, column=1, padx=4)
        ctk.CTkButton(btn_f, text="Отмена", width=90,
                      fg_color=("gray70", "gray30"),
                      command=self._close).grid(row=0, column=2, padx=4)
        self.bind("<Escape>", lambda _: self._close())

    def _query(self) -> Optional[str]:
        v = self._query_var.get()
        return None if v == "Выберите запрос" else v

    def _on_run(self):
        self.result = (self._query(), self._render_var.get(),
                       self._timer_anim_var.get(), self._timer_color_var.get(), True)
        self._close()

    def _on_save(self):
        self.result = (self._query(), self._render_var.get(),
                       self._timer_anim_var.get(), self._timer_color_var.get(), False)
        self._close()

    def _close(self):
        _master = self.master
        self.destroy()
        try:
            _master.focus_set()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
class DashboardPanel(ctk.CTkFrame):
    """Одна панель дашборда: заголовок-ручка + ResultTable + выбор запроса."""

    _SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, parent, panel_id: int, on_pin_changed=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.panel_id    = panel_id
        self.is_pinned   = False
        self._loading    = False
        self._spin_idx   = 0
        self._spin_id    = None
        self._on_pin_changed = on_pin_changed
        self._viz_configs:      dict = {}
        self._viz_mode:         bool = False
        self._display1_age:     dict = {}   # {(col_name, val_str): first_seen datetime}
        self._delta_prev:       dict = {}   # {(col_name, row_idx): prev_value}
        self._last_columns:     list = []   # колонки до фильтрации visible_columns
        self._anim_rows:        list = []   # кеш строк последнего _render_animated
        self._anim_cols:        list = []   # кеш колонок последнего _render_animated (после фильтрации)
        self._panel_viz_config: dict = {}   # {header_color, marker_shape, marker_color}
        self._active_signals:   set  = set()  # {(col_name, sig_text)} активных сигналов
        self.on_signal_fired         = None   # callback(col_name, sig_text)
        self._anim_panel         = None
        self._render_type: str   = "Таблица"
        self._chart_canvas       = None
        self._timer_anim: str    = "Счётчик"
        self._timer_color: str   = "(по умолчанию)"
        self._timer_total: int   = 0
        self._timer_remaining: int = 0
        self._elapsed_secs:  int   = 0
        self._elapsed_id           = None
        self._cancel_fn            = None
        self._query_timeout: int   = 0
        self.on_history_click      = None
        self._last_query_file: str = ""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self):
        # ── заголовок-ручка ──────────────────────────────────────────────────
        self.header = ctk.CTkFrame(self, height=30, corner_radius=0, cursor="fleur",
                                   fg_color=("gray79", "gray24"))
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(2, weight=1)

        # Маркер (цветная фигура в левом верхнем углу)
        self._marker_lbl = ctk.CTkLabel(self.header, text="", width=16,
                                         fg_color="transparent", cursor="fleur")
        self._marker_lbl.grid(row=0, column=0, padx=(4, 0))
        self._marker_lbl.grid_remove()

        self.drag_icon = ctk.CTkLabel(self.header, text="⠿", width=22, cursor="fleur")
        self.drag_icon.grid(row=0, column=1, padx=(2, 0))
        _Tooltip(self.drag_icon, "Перетащите для изменения порядка панелей")

        self.title_lbl = ctk.CTkLabel(self.header, text=f"Панель {self.panel_id}", anchor="w")
        self.title_lbl.grid(row=0, column=2, sticky="ew", padx=4)
        self._title_default_color = self.title_lbl.cget("text_color")

        # Индикатор следующего авто-обновления (перед кнопкой настроек)
        self._timer_lbl = ctk.CTkLabel(
            self.header, text="", width=60,
            font=ctk.CTkFont(size=10),
            text_color=("gray40", "gray65"))
        self._timer_lbl.grid(row=0, column=3, padx=(0, 2))
        self._timer_tooltip = _Tooltip(self._timer_lbl, "")

        self._timer_bar = ctk.CTkProgressBar(
            self.header, width=60, height=8)
        self._timer_bar.set(0.0)
        self._timer_bar_tooltip = _Tooltip(self._timer_bar, "")
        # bar hidden by default, shown when anim == "Прогресс-бар"

        self.viz_btn = ctk.CTkButton(
            self.header,
            text="⚙", width=28, height=22,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            text_color=("gray10", "gray90"),
            command=self._open_viz_settings)
        self.viz_btn.grid(row=0, column=4, padx=(0, 2))
        _Tooltip(self.viz_btn, "Настройки визуализации")

        _load_img = _get_load_ctk_image(14)
        self.export_btn = ctk.CTkButton(
            self.header,
            image=_load_img, text="" if _load_img else "⬇",
            width=28, height=22,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=self._export_data)
        self.export_btn.grid(row=0, column=5, padx=(0, 2))
        _Tooltip(self.export_btn, "Экспорт CSV / XLSX")

        self.history_btn = ctk.CTkButton(
            self.header,
            text="🕐", width=28, height=22,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", hover_color=("gray70", "gray40"),
            text_color=("gray20", "gray85"),
            command=self._on_history_click)
        self.history_btn.grid(row=0, column=6, padx=(0, 2))
        _Tooltip(self.history_btn, "История запросов")

        _pin_img = _get_pin_ctk_image(14)
        self.pin_btn = ctk.CTkButton(
            self.header,
            image=_pin_img, text="" if _pin_img else "📌",
            width=28, height=22,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=self._toggle_pin)
        self.pin_btn.grid(row=0, column=7, padx=(0, 4))
        self._pin_tooltip = _Tooltip(self.pin_btn, "Закрепить панель")

        # ── таблица результата ───────────────────────────────────────────────
        self.result_table = ResultTable(self, fg_color=self.cget("fg_color"),
                                        corner_radius=0)
        self.result_table.grid(row=1, column=0, sticky="nsew")

        # ── уведомление о лимите строк ───────────────────────────────────────
        self._row_notice_lbl = ctk.CTkLabel(
            self, text="", anchor="w",
            font=ctk.CTkFont(size=10),
            text_color=("gray45", "gray65"))
        self._row_notice_lbl.grid(row=2, column=0, sticky="ew", padx=8, pady=(1, 0))
        self._row_notice_lbl.grid_remove()

        # ── строка выбора запроса ────────────────────────────────────────────
        self.sel = ctk.CTkFrame(self, fg_color="transparent", height=34)
        self.sel.grid(row=3, column=0, sticky="ew", padx=4, pady=(2, 4))
        self.sel.grid_columnconfigure(0, weight=1)
        self.sel.grid_propagate(False)

        self.query_combo = ctk.CTkComboBox(self.sel, values=["Выберите запрос"],
                                           state="readonly")
        self.query_combo.set("Выберите запрос")
        self.query_combo.grid(row=0, column=0, sticky="ew")

        self.run_btn = ctk.CTkButton(self.sel, text="▶", width=30)
        self.run_btn.grid(row=0, column=1, padx=(3, 2))

        self._cancel_btn = ctk.CTkButton(
            self.sel, text="✕", width=30,
            fg_color=("#E53935", "#C62828"),
            hover_color=("#C62828", "#B71C1C"),
            command=self._on_cancel)
        self._cancel_btn.grid(row=0, column=2, padx=(0, 2))
        self._cancel_btn.grid_remove()

    # ── спиннер загрузки ──────────────────────────────────────────────────────

    def set_loading(self, state: bool, timeout_secs: int = 0):
        self._loading = state
        if state:
            # Отменяем старые таймеры перед новым запуском — иначе дублирующиеся
            # after()-колбэки удваивают _elapsed_secs и преждевременно триггерят отмену.
            if self._spin_id:
                try:
                    self.after_cancel(self._spin_id)
                except Exception:
                    pass
                self._spin_id = None
            if self._elapsed_id:
                try:
                    self.after_cancel(self._elapsed_id)
                except Exception:
                    pass
                self._elapsed_id = None
            self._spin_idx     = 0
            self._elapsed_secs = 0
            self._query_timeout = timeout_secs
            self.title_lbl.configure(text_color=theme_colors.accent())
            self._do_spin()
            self._do_elapsed()
            self._cancel_btn.grid()
        else:
            if self._spin_id:
                try:
                    self.after_cancel(self._spin_id)
                except Exception:
                    pass
                self._spin_id = None
            if self._elapsed_id:
                try:
                    self.after_cancel(self._elapsed_id)
                except Exception:
                    pass
                self._elapsed_id = None
            self._cancel_btn.grid_remove()
            self._cancel_fn = None
            self.title_lbl.configure(text=self._base_title())
            self._apply_panel_viz_config()

    def _do_spin(self):
        if not self._loading:
            return
        frame = self._SPINNER[self._spin_idx % len(self._SPINNER)]
        secs  = self._elapsed_secs
        suf   = f" {secs}с" if secs > 0 else ""
        self.title_lbl.configure(text=f"{frame} {self._base_title()}{suf}")
        self._spin_idx += 1
        self._spin_id = self.after(80, self._do_spin)

    def _do_elapsed(self):
        if not self._loading:
            return
        self._elapsed_secs += 1
        tmo = self._query_timeout or 0
        if tmo > 0 and self._elapsed_secs >= tmo:
            self._on_cancel()
            return
        self._elapsed_id = self.after(1000, self._do_elapsed)

    def _on_cancel(self):
        if self._cancel_fn:
            self._cancel_fn()
        self.set_loading(False)
        self.run_btn.configure(state="normal")

    def _base_title(self) -> str:
        q = self.query_combo.get()
        return q if q and q != "Выберите запрос" else f"Панель {self.panel_id}"

    def set_next_refresh_secs(self, secs):
        """Обновляет индикатор обратного отсчёта до следующего авто-обновления."""
        if secs is None:
            self._timer_lbl.configure(text="")
            self._timer_tooltip.update_text("")
            self._timer_lbl.grid(row=0, column=3, padx=(0, 2))
            self._timer_bar.grid_remove()
            self._timer_remaining = 0
            return
        total = int(secs)
        # Обнаруживаем начало нового цикла (таймер сбросился вверх)
        if total > self._timer_remaining:
            self._timer_total = total
        self._timer_remaining = total
        mins, s = divmod(total, 60)
        tooltip_txt = f"Следующее обновление через {mins}м {s:02d}с"

        if self._timer_anim == "Прогресс-бар":
            self._timer_lbl.grid_remove()
            self._timer_bar.grid(row=0, column=3, padx=(0, 4))
            if self._timer_total > 0:
                progress = max(0.0, min(1.0, 1.0 - total / self._timer_total))
            else:
                progress = 0.0
            self._timer_bar.set(progress)
            self._timer_bar_tooltip.update_text(tooltip_txt)
        else:
            self._timer_bar.grid_remove()
            self._timer_lbl.grid(row=0, column=3, padx=(0, 2))
            txt = f"⏱ {mins}м{s:02d}с" if mins > 0 else f"⏱ {total}с"
            self._timer_lbl.configure(text=txt)
            self._timer_tooltip.update_text(tooltip_txt)

    def set_timer_color(self, color_name: str):
        self._timer_color = color_name
        if color_name == "(по умолчанию)":
            hex_color = ("gray40", "gray65")
            bar_color = ("#3B8ED0", "#1F6AA5")
        else:
            hex_color = _VIZ_COLOR_MAP.get(color_name, "#0D9488")
            bar_color = hex_color
        self._timer_lbl.configure(text_color=hex_color)
        self._timer_bar.configure(progress_color=bar_color)

    # ── pin ───────────────────────────────────────────────────────────────────

    def _toggle_pin(self):
        self.pin(not self.is_pinned)
        if self._on_pin_changed:
            self._on_pin_changed(self)

    def pin(self, state: bool):
        self.is_pinned = state
        if state:
            self.pin_btn.configure(fg_color=[theme_colors.accent(), theme_colors.hover()],
                                   hover_color=[theme_colors.hover(), theme_colors.dark()])
            self.sel.grid_remove()
            self._pin_tooltip.update_text("Открепить панель")
        else:
            self.pin_btn.configure(fg_color="transparent",
                                   hover_color=("gray70", "gray40"))
            self.sel.grid()
            self._pin_tooltip.update_text("Закрепить панель")

    # ── публичный API ─────────────────────────────────────────────────────────

    def set_queries(self, names: list):
        vals = ["Выберите запрос"] + names
        cur  = self.query_combo.get()
        self.query_combo.configure(values=vals)
        if cur not in vals:
            self.query_combo.set("Выберите запрос")

    def get_query_name(self) -> Optional[str]:
        v = self.query_combo.get()
        return None if v == "Выберите запрос" else v

    def set_result(self, rows: list, columns: list, update_age: bool = True):
        self._last_columns = list(columns)
        old_delta = dict(self._delta_prev)
        if update_age:
            self._update_display1_age(rows, columns)
            self._update_delta_prev(rows, columns)
        if self._viz_configs:
            self._check_signals(rows, columns)
        # Фильтрация колонок по настройке visible_columns (после трекинга возраста)
        _vis = self._panel_viz_config.get("visible_columns") or []
        if _vis:
            _vis_set = set(_vis)
            _ci = [i for i, c in enumerate(columns) if c in _vis_set]
            if _ci and len(_ci) < len(columns):
                columns = [columns[i] for i in _ci]
                rows = [[row[i] for i in _ci if i < len(row)] for row in rows]
        if self._render_type in ("Строчный график", "Столбчатый график"):
            if self._anim_panel and self._anim_panel.winfo_exists():
                self._anim_panel.grid_remove()
            self.result_table.grid_remove()
            chart_type = "line" if self._render_type == "Строчный график" else "bar"
            if (self._chart_canvas is None or not self._chart_canvas.winfo_exists()
                    or self._chart_canvas._chart_type != chart_type):
                if self._chart_canvas and self._chart_canvas.winfo_exists():
                    self._chart_canvas.destroy()
                self._chart_canvas = _SimpleChartCanvas(self, chart_type=chart_type)
                self._chart_canvas.grid(row=1, column=0, sticky="nsew")
            self._chart_canvas.set_data(rows, columns)
        elif self._viz_mode and self._viz_configs:
            if self._chart_canvas and self._chart_canvas.winfo_exists():
                self._chart_canvas.grid_remove()
            self._render_animated(rows, columns, old_delta)
        else:
            if self._anim_panel and self._anim_panel.winfo_exists():
                self._anim_panel.grid_remove()
            if self._chart_canvas and self._chart_canvas.winfo_exists():
                self._chart_canvas.grid_remove()
            self.result_table.grid()
            evicted = self.result_table.set_data(rows, columns, reset_hidden=False)
            self._log_evicted_hidden(evicted)

    def _render_animated(self, rows: list, columns: list, delta_data: dict = None):
        self._anim_rows = rows
        self._anim_cols = columns
        self.result_table.grid_remove()
        evicted = self.result_table.set_data(rows, columns, reset_hidden=False)
        self._log_evicted_hidden(evicted)
        if self._anim_panel is None or not self._anim_panel.winfo_exists():
            self._anim_panel = AnimatedPanel(self)
            self._anim_panel.grid(row=1, column=0, sticky="nsew")
        try:
            font_size = self.winfo_toplevel()._dashboard_frame_font_size
            if not isinstance(font_size, int) or not (8 <= font_size <= 14):
                font_size = 10
        except Exception:
            font_size = 10
        self._anim_panel.render(rows, columns, self._viz_configs,
                                self._display1_age, delta_data or {}, font_size=font_size)

    def _log_evicted_hidden(self, evicted: set) -> None:
        if not evicted:
            return
        top = self.winfo_toplevel()
        if not hasattr(top, "log_manager"):
            return
        for key in sorted(evicted):
            top.log_manager.add_log(
                f"Скрытая строка {key} исключена из данных SQL-запроса"
            )

    def rerender_font(self) -> None:
        """Перерендер AnimatedPanel с новым font_size без обращения к БД."""
        if not (self._viz_mode and self._viz_configs):
            return
        if not self._anim_cols:
            return
        self._render_animated(self._anim_rows, self._anim_cols)

    _AGE_ANIM_TYPES = {"Индикатор 1", "Индикатор 2", "Индикатор - круги",
                       "Индикатор 2 (Тепловой)", "Светофор",
                       "Секундомер", "Волна", "Пламя", "ЭКГ", "Кольца"}

    def _update_display1_age(self, rows: list, columns: list):
        if not self._viz_configs:
            return
        age_cols = [
            (ci, col) for ci, col in enumerate(columns)
            if (self._viz_configs.get(col, {}).get("type") in self._AGE_ANIM_TYPES
                or self._viz_configs.get(col, {}).get("signal", {}).get("type_name")
                in self._AGE_ANIM_TYPES)
        ]
        if not age_cols:
            return
        now = datetime.datetime.now()
        current_keys: set = set()
        for ci, col_name in age_cols:
            for row in rows:
                val_str = "NULL" if (ci >= len(row) or row[ci] is None) else str(row[ci])
                key = (col_name, val_str)
                current_keys.add(key)
                if key not in self._display1_age:
                    self._display1_age[key] = now
        self._display1_age = {k: v for k, v in self._display1_age.items()
                               if k in current_keys}

    def _update_delta_prev(self, rows: list, columns: list):
        for ci, col_name in enumerate(columns):
            col_cfg = self._viz_configs.get(col_name, {})
            if (col_cfg.get("type") == "Дельта"
                    or col_cfg.get("signal", {}).get("type_name") == "Дельта"):
                for ri, row in enumerate(rows):
                    self._delta_prev[(col_name, ri)] = row[ci] if ci < len(row) else None

    def _check_signals(self, rows: list, columns: list):
        """Детектирует новые срабатывания сигналов и вызывает on_signal_fired."""
        now_active: set = set()
        for ci, col_name in enumerate(columns):
            cfg = self._viz_configs.get(col_name, {})
            sig_text = cfg.get("signal", {}).get("text", "").strip()
            if not sig_text:
                continue
            sig_terms = [t.strip() for t in sig_text.split(",") if t.strip()]
            for row in rows:
                raw = row[ci] if ci < len(row) else None
                if raw is not None and all(
                        t.lower() in str(raw).lower() for t in sig_terms):
                    now_active.add((col_name, sig_text))
                    break
        new_signals = now_active - self._active_signals
        self._active_signals = now_active
        if new_signals and self.on_signal_fired:
            for col_name, sig_text in new_signals:
                self.on_signal_fired(col_name, sig_text)

    _MARKER_CHARS = {"Круг": "●", "Квадрат": "■", "Треугольник": "▲", "Ромб": "◆"}

    def _apply_panel_viz_config(self):
        cfg = self._panel_viz_config

        hc_name = cfg.get("header_color", "(по умолчанию)")
        if not hc_name or hc_name == "(по умолчанию)":
            self.title_lbl.configure(text_color=self._title_default_color)
        else:
            hc = _VIZ_COLOR_MAP.get(hc_name, "#0D9488")
            if hc == "auto":
                hc = "#d0d0d0" if ctk.get_appearance_mode() == "Dark" else "#2a2a2a"
            self.title_lbl.configure(text_color=hc)

        shape   = cfg.get("marker_shape", "Нет")
        mc_name = cfg.get("marker_color", "Бирюзовый")
        if not shape or shape == "Нет":
            self._marker_lbl.grid_remove()
        else:
            mc = _VIZ_COLOR_MAP.get(mc_name, "#0D9488")
            if mc == "auto":
                mc = "#0D9488"
            char = self._MARKER_CHARS.get(shape, "●")
            self._marker_lbl.configure(text=char, text_color=mc,
                                        font=ctk.CTkFont(size=13))
            self._marker_lbl.grid()

    def _open_viz_settings(self):
        cols = self._last_columns or self.result_table._columns or []
        panel_cfg = {
            **self._panel_viz_config,
            "timer_anim":  self._timer_anim,
            "timer_color": self._timer_color,
        }
        dlg = VisualizationSettingsDialog(self.winfo_toplevel(), cols,
                                          self._viz_configs, panel_cfg)
        self.wait_window(dlg)
        if dlg.result is not None:
            panel = dlg.result.pop("__panel__", {})
            ta = panel.pop("timer_anim", None)
            tc = panel.pop("timer_color", None)
            self._panel_viz_config = panel
            self._viz_configs      = dlg.result
            self._viz_mode         = bool(self._viz_configs)
            if ta is not None:
                self._timer_anim = ta
            if tc is not None:
                self.set_timer_color(tc)
            self._apply_panel_viz_config()
            rows = list(self.result_table._rows)
            cols = list(self.result_table._columns)
            self.set_result(rows, cols, update_age=False)

    @staticmethod
    def _safe_val(v):
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v)

    def get_state(self) -> dict:
        safe_rows = [[self._safe_val(v) for v in r]
                     for r in self.result_table._rows]
        age_data = [
            [k[0], k[1], v.isoformat()]
            for k, v in self._display1_age.items()
        ]
        return {
            "query":            self.query_combo.get(),
            "rows":             safe_rows,
            "columns":          list(self.result_table._columns),
            "pinned":           self.is_pinned,
            "viz_configs":      self._viz_configs,
            "viz_mode":         self._viz_mode,
            "render_type":      self._render_type,
            "panel_viz_config": self._panel_viz_config,
            "timer_anim":       self._timer_anim,
            "timer_color":      self._timer_color,
            "age_data":         age_data,
        }

    def set_row_notice(self, text: str):
        if text:
            self._row_notice_lbl.configure(text=text)
            self._row_notice_lbl.grid()
        else:
            self._row_notice_lbl.grid_remove()

    def update_title(self, query_name: str):
        if not self._loading:
            text = query_name if query_name and query_name != "Выберите запрос" \
                   else f"Панель {self.panel_id}"
            self.title_lbl.configure(text=text)

    def set_state(self, state: dict):
        vals = self.query_combo.cget("values")
        q = state.get("query", "Выберите запрос")
        if q not in vals:
            q = "Выберите запрос"
        self.query_combo.set(q)
        self.update_title(q)
        viz_configs = state.get("viz_configs", {})
        for col_cfg in viz_configs.values():
            if isinstance(col_cfg, dict) and col_cfg.get("type") == "Тепловая":
                col_cfg["type"] = "Индикатор 2 (Тепловой)"
        self._viz_configs  = viz_configs
        self._viz_mode     = state.get("viz_mode", False)
        self._render_type  = state.get("render_type", "Таблица")
        self._timer_anim   = state.get("timer_anim", "Счётчик")
        self.set_timer_color(state.get("timer_color", "(по умолчанию)"))
        rows    = state.get("rows", [])
        columns = state.get("columns", [])
        self._panel_viz_config = state.get("panel_viz_config", {})
        self._apply_panel_viz_config()
        for triple in state.get("age_data", []):
            try:
                col, val, iso = triple
                self._display1_age[(col, val)] = datetime.datetime.fromisoformat(iso)
            except Exception:
                pass
        self.set_result(rows, columns)
        self.pin(state.get("pinned", False))

    def bind_drag(self, press_cb, motion_cb, release_cb):
        for w in (self.header, self.drag_icon, self.title_lbl, self._marker_lbl):
            w.bind("<ButtonPress-1>",   press_cb)
            w.bind("<B1-Motion>",       motion_cb)
            w.bind("<ButtonRelease-1>", release_cb)

    def highlight(self, on: bool):
        color = "#1f6aa5" if on else None
        self.header.configure(fg_color=color if on else ("gray79", "gray24"))

    def refresh_theme(self, theme: str):
        """Обновляет цвет иконки ⚙ под текущую тему."""
        color = "gray10" if theme == "light" else "gray90"
        self.viz_btn.configure(text_color=color)

    # ── экспорт и копирование ─────────────────────────────────────────────────

    def _copy_selected_row(self):
        sel = self.result_table._tree.selection()
        if sel:
            vals = self.result_table._tree.item(sel[0], "values")
            self.result_table._clip("\t".join(str(v) for v in vals[1:]))
        elif self.result_table._rows:
            self.result_table._clip(
                "\t".join("" if v is None else str(v) for v in self.result_table._rows[0]))

    def _on_history_click(self):
        if callable(self.on_history_click):
            self.on_history_click(self)

    def _export_data(self):
        if not self.result_table._columns:
            messagebox.showinfo("Экспорт", "Нет данных для экспорта")
            return
        query   = self.get_query_name() or f"panel_{self.panel_id}"
        safe    = "".join(c if c.isalnum() or c in " _-" else "_" for c in query)
        filepath = filedialog.asksaveasfilename(
            title="Экспорт данных",
            defaultextension=".csv",
            filetypes=[("CSV файл", "*.csv"), ("Excel файл", "*.xlsx"),
                       ("Все файлы", "*.*")],
            initialfile=f"{safe}.csv")
        if not filepath:
            return
        try:
            if filepath.lower().endswith(".xlsx"):
                self.result_table.export_to_excel(filepath)
            else:
                self.result_table.export_to_csv(filepath)
            messagebox.showinfo("Экспорт", f"Данные сохранены:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")


# ─────────────────────────────────────────────────────────────────────────────
class BulkIntervalDialog(ctk.CTkToplevel):
    """Модальное окно массового обновления интервала (мин.) для всех объектов."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[int] = None
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grab_set()
        self._build(title)
        self.after(50, self._center)

    def _build(self, title: str):
        pad = {"padx": 24}

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=15, weight="bold"),
                     anchor="w").grid(row=0, column=0, columnspan=2,
                                      **pad, pady=(20, 14), sticky="ew")

        ctk.CTkLabel(self, text="Установить значение (мин.):", anchor="w").grid(
            row=1, column=0, padx=(24, 10), pady=4, sticky="w")

        self.entry = ctk.CTkEntry(self, placeholder_text="0", width=110)
        self.entry.grid(row=1, column=1, padx=(0, 24), pady=4, sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, **pad, pady=(14, 18), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(btn_frame, text="Применить", command=self._on_ok).grid(
            row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(btn_frame, text="Отмена", command=self._close).grid(
            row=0, column=1, padx=(6, 0), sticky="ew")

        self.grid_columnconfigure(1, weight=1)
        self.entry.focus()
        self.bind("<Return>", lambda _: self._on_ok())
        self.bind("<Escape>", lambda _: self._close())
        setup_paste_bindings(self)

    def _on_ok(self):
        val = self.entry.get().strip()
        if not val:
            messagebox.showerror("Ошибка", "Поле не может быть пустым", parent=self)
            return
        try:
            n = int(val)
            if n < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите целое число ≥ 0", parent=self)
            return
        self.result = n
        self._close()

    def _close(self):
        _master = self.master
        self.destroy()
        try:
            _master.focus_set()
        except Exception:
            pass

    def _center(self):
        self.update_idletasks()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        w, h   = self.winfo_width(), self.winfo_height()
        fx = px + (pw - w) // 2
        fy = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{fx}+{fy}")


# ─────────────────────────────────────────────────────────────────────────────
class _TabBar(ctk.CTkFrame):
    """Горизонтальная панель вкладок с оранжевыми PIL-иконками."""

    _SHAPES = {
        "📊 Приборная панель": "bars",
        "📋 Логи":             "lines",
        "🔗 Подключения":      "link",
        "📝 Запросы":          "doc",
        "⚙️ Настройки":        "gear",
        "⏰ Напоминания":      "clock",
        "🔔 Уведомления":      "bell",
        "🛠 Сервисы":          "grid",
    }

    def __init__(self, parent, values: list, command, height: int = 40, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._command = command
        self._buttons: dict = {}
        self._active:  Optional[str] = None

        for i, val in enumerate(values):
            shape = self._SHAPES.get(val)
            icon  = _get_tab_icon(shape, 16) if shape else None
            label = val.split(" ", 1)[1] if " " in val else val

            btn = ctk.CTkButton(
                self,
                text=label,
                image=icon,
                compound="left",
                height=height,
                anchor="center",
                fg_color=("gray75", "gray30"),
                hover_color=("gray68", "gray35"),
                text_color=("gray10", "gray90"),
                corner_radius=6,
                command=lambda v=val: self._on_click(v),
            )
            btn.grid(row=0, column=i, padx=(0, 2))
            self._buttons[val] = btn

        # Выравниваем ширину всех кнопок по самой широкой после рендера
        self.after(80, self._sync_widths)

    def _sync_widths(self):
        self.update_idletasks()
        max_w = max((b.winfo_reqwidth() for b in self._buttons.values()), default=140)
        for b in self._buttons.values():
            b.configure(width=max_w)

    def set(self, value: str):
        if value not in self._buttons:
            return
        if self._active and self._active in self._buttons:
            self._buttons[self._active].configure(fg_color=("gray75", "gray30"))
        self._active = value
        self._buttons[value].configure(fg_color=[theme_colors.accent(), theme_colors.hover()])

    def _on_click(self, value: str):
        self.set(value)
        self._command(value)

    def configure(self, require_redraw=False, **kwargs):
        if "text_color" in kwargs:
            color = kwargs.pop("text_color")
            for btn in self._buttons.values():
                btn.configure(text_color=color)
        if kwargs:
            super().configure(require_redraw=require_redraw, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
class _HeaderWidget(ctk.CTkFrame):
    """Виджет в шапке: «Имя запроса  Значение» в одну строку."""

    def __init__(self, parent, label: str, color: str = "#0D9488"):
        super().__init__(parent, fg_color="transparent")
        self._normal_color = color
        self._cur      = 0.0
        self._target   = 0.0
        self._after_id = None

        self._name_lbl = ctk.CTkLabel(
            self, text=label[:28],
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray55"),
            anchor="w",
        )
        self._name_lbl.pack(side="left", padx=(6, 2), pady=4)

        self._val_lbl = ctk.CTkLabel(
            self, text="—",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=color, anchor="w",
        )
        self._val_lbl.pack(side="left", padx=(0, 8), pady=4)

    def set_value(self, raw, alert_color: str = None):
        color = alert_color if alert_color else self._normal_color
        self._val_lbl.configure(text_color=color)
        s = "" if raw is None else str(raw).strip()
        if not s:
            self._stop()
            self._val_lbl.configure(text="—")
            return
        try:
            v = float(s.replace("\u00a0", "").replace(" ", "").replace(",", "."))
            self._target = v
            self._start()
        except (ValueError, TypeError):
            self._stop()
            self._val_lbl.configure(text=s[:30])

    def _start(self):
        self._stop()
        self._tick()

    def _stop(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self):
        diff = self._target - self._cur
        if abs(diff) < 0.5:
            self._cur = self._target
            self._val_lbl.configure(text=self._fmt(self._cur))
            self._after_id = None
        else:
            self._cur += diff * 0.18
            self._val_lbl.configure(text=self._fmt(self._cur))
            self._after_id = self.after(16, self._tick)

    @staticmethod
    def _fmt(v: float) -> str:
        if abs(v - round(v)) < 1e-9:
            return f"{int(round(v)):,}".replace(",", " ")
        return f"{v:,.2f}".replace(",", " ")


# ─────────────────────────────────────────────────────────────────────────────
class _WidgetVizDialog(ctk.CTkToplevel):
    """Настройка отображения виджета в шапке (столбец, цвет, пороговый аллерт)."""

    _COLORS = {k: v for k, v in _VIZ_COLOR_MAP.items() if v != "auto"}

    def __init__(self, parent, current_config: dict):
        super().__init__(parent)
        self.withdraw()
        self.result = None
        self.title("Настройка виджета")
        self.resizable(False, False)
        self.minsize(400, 360)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)

        pad = {"padx": 20}
        ctk.CTkLabel(self, text="Настройка виджета",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").grid(row=0, column=0, **pad, pady=(16, 12), sticky="ew")

        rf1 = ctk.CTkFrame(self, fg_color="transparent")
        rf1.grid(row=1, column=0, **pad, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(rf1, text="Столбец №", width=140, anchor="w").pack(side="left")
        self._col_entry = ctk.CTkEntry(rf1, width=60)
        self._col_entry.insert(0, str(current_config.get("column", 0)))
        self._col_entry.pack(side="left")

        rf2 = ctk.CTkFrame(self, fg_color="transparent")
        rf2.grid(row=2, column=0, **pad, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(rf2, text="Цвет", width=140, anchor="w").pack(side="left")
        color_names = list(self._COLORS.keys())
        self._color_combo = ctk.CTkComboBox(rf2, values=color_names,
                                            state="readonly", width=190)
        saved_cn = current_config.get("color_name", "Бирюзовый")
        self._color_combo.set(saved_cn if saved_cn in color_names else color_names[0])
        self._color_combo.pack(side="left")

        rf3 = ctk.CTkFrame(self, fg_color="transparent")
        rf3.grid(row=3, column=0, **pad, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(rf3, text="Пороговый аллерт", width=140, anchor="w").pack(side="left")
        self._threshold_entry = ctk.CTkEntry(rf3, width=90, placeholder_text="Значение")
        self._threshold_entry.insert(0, current_config.get("threshold_value", ""))
        self._threshold_entry.pack(side="left", padx=(0, 6))
        ops = [">", "<", "=="]
        self._op_combo = ctk.CTkComboBox(rf3, values=ops, state="readonly", width=70)
        self._op_combo.set(current_config.get("threshold_op", ">"))
        self._op_combo.pack(side="left")

        rf4 = ctk.CTkFrame(self, fg_color="transparent")
        rf4.grid(row=4, column=0, **pad, pady=(0, 8), sticky="ew")
        ctk.CTkLabel(rf4, text="Цвет аллерт", width=140, anchor="w").pack(side="left")
        self._alert_color_combo = ctk.CTkComboBox(rf4, values=color_names,
                                                   state="readonly", width=190)
        saved_acn = current_config.get("threshold_alert_color_name", "Красный")
        self._alert_color_combo.set(saved_acn if saved_acn in color_names else "Красный")
        self._alert_color_combo.pack(side="left")

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=5, column=0, **pad, pady=16, sticky="ew")
        bf.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(bf, text="Сохранить", command=self._ok).grid(
            row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(bf, text="Отмена", command=self._close).grid(
            row=0, column=1, padx=(6, 0), sticky="ew")

        self.bind("<Escape>", lambda _: self._close())
        self.after(50, self._center)

    def _ok(self):
        try:
            col = int(self._col_entry.get().strip())
            if col < 0:
                raise ValueError
        except ValueError:
            import dialogs as _mb
            _mb.showerror("Ошибка", "Столбец — целое число ≥ 0", parent=self)
            return
        cn  = self._color_combo.get()
        acn = self._alert_color_combo.get()
        self.result = {
            "column":                       col,
            "color_name":                  cn,
            "color":                       self._COLORS.get(cn, "#0D9488"),
            "threshold_value":             self._threshold_entry.get().strip(),
            "threshold_op":                self._op_combo.get(),
            "threshold_alert_color_name":  acn,
            "threshold_alert_color":       self._COLORS.get(acn, "#C0392B"),
        }
        self._close()

    def _close(self):
        _master = self.master
        self.destroy()
        try:
            _master.focus_set()
        except Exception:
            pass

    def _center(self):
        self.update_idletasks()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        w, h   = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        self.deiconify()



# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(LogsTabMixin, RemindersTabMixin, ConnectionsTabMixin, QueriesTabMixin, ServicesTabMixin, SettingsTabMixin, DashboardTabMixin, ctk.CTk):
    def __init__(self, version: str = "0.0.0", appdata_dir: str = None):
        super().__init__()
        self.withdraw()                    # скрываем на время сборки UI, показываем в конце __init__
        self._version = version
        self.title(f"Hunch v{version}")
        self._appdata_dir = appdata_dir

        _d = appdata_dir or ""
        _p = lambda *parts: os.path.join(_d, *parts) if _d else os.path.join(*parts)

        self.data_manager    = DataManager(
            config_dir=_p("config"),
            queries_dir=_p("queries"),
            settings_file=_p("settings.json"),
        )
        self.log_manager     = LogManager(
            log_file=_p("logs", "app.log"),
        )
        self.db_manager      = DatabaseManager(
            config_dir=_p("config"),
        )
        self.settings_manager = SettingsManager(
            settings_file=_p("settings.json"),
        )
        self.stats_manager   = StatsManager(
            db_path=_p("query_stats.db"),
        )
        self.reminders_manager = RemindersManager(
            db_path=_p("reminders.db"),
        )

        self._rotation_after_id      = None   # after-id текущего таймера ротации
        self._rotation_warn_after_id = None   # after-id таймера предупреждения о ротации

        # Ротация при запуске (обрабатывает пропущенные ротации пока программа была закрыта)
        self._run_log_rotation(startup=True)
        # Запускаем периодическую проверку приближения ротации (через 10 с после старта)
        self._rotation_warn_after_id = self.after(10_000, self._check_rotation_warning)

        self._drag_source:      Optional[DashboardPanel] = None
        self._drag_ghost:       Optional[tk.Toplevel]    = None
        self._drag_drop_target: Optional[DashboardPanel] = None
        self._selected_query_name: Optional[str]     = None
        self._selected_connection_name: Optional[str] = None

        self._signal_last_played:   dict = {}  # {query_name: monotonic} дебаунс сигнала 10 с
        self._alert_last_fired:     dict = {}  # {(query_file, type): monotonic} дебаунс алертов
        self._alert_history:        list = []  # [{ts, query_name, query_file, type, detail}]
        self._notif_row_widgets:    dict = {}  # {notif_id: ([widgets], orig_bg)} для мерцания
        self._notif_action_btns:    dict = {}  # {notif_id: CTkButton} кнопка действия строки
        self._highlight_notif_id:   Optional[int] = None  # строка для мерцания
        self._selected_notif_id:    Optional[int] = None  # выделенная строка для копирования
        self._query_results:        dict = {}   # {filename: {"rows": [...], "columns": [...]}}
        self._query_results_lock = threading.RLock()   # защита concurrent-доступа
        self._widget_prev_values:  dict = {}   # {filename: str} предыдущее значение виджета
        self._query_timers:         dict = {}   # {filename: after_id}
        self._conn_timers:          dict = {}   # {conn_filename: after_id}
        self._conn_last_refresh:    dict = {}   # {conn_filename: datetime}
        self._queries_in_progress:  set  = set()  # файлы, выполняемых сейчас
        self._query_scheduled_at:   dict = {}   # {filename: datetime} момент планирования
        self._query_intervals_cache: dict = {}  # {filename: interval_min}
        self._panel_qf_cache:        dict = {}  # {id(panel): (last_qn, qf)}
        self._query_history:        dict = {}   # {filename: [{"ts":..,"rows":..,"columns":..}]}
        self._conn_statuses: dict = {}          # {filename: True/False/None}
        self._conn_status_testing: set = set()  # файлы, тестируемые прямо сейчас
        _cached_statuses = self.settings_manager.get_setting("conn_status_cache", {})
        if isinstance(_cached_statuses, dict):
            self._conn_statuses.update(
                {k: v for k, v in _cached_statuses.items() if isinstance(v, bool)}
            )

        self._notifications:          list = []   # [{id, query_name, timestamp, read}]
        self._notification_counter:   int  = 0
        self._notif_rotation_after_id       = None

        self._reminder_check_after_id = None
        self._active_toasts: list     = []

        # GF.Scraping scheduler after-IDs
        self._gf_daily_after_id = None
        self._gf_cal_after_id   = None
        self._gf_stop_event     = threading.Event()  # сигнал отмены фоновых потоков

        # SQL Выгрузка scheduler after-ID
        self._sql_export_after_id = None
        # Объединение уведомлений расписания (daily + calendar в одно сообщение)
        self._gf_pending_sched_sources: set  = set()
        self._gf_merge_notif_id:        object = None

        self._conn_sort:  tuple = (None, False)   # (col_idx, reversed)
        self._query_sort: tuple = (None, False)   # (col_idx, reversed)

        self._load_query_cache()
        self._load_alert_history()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── верхняя панель (row 0) ────────────────────────────────────────────
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.grid(row=0, column=0, padx=10, pady=(6, 0), sticky="ew")
        self.top_bar.grid_columnconfigure(3, weight=1)

        self.hamburger_button = ctk.CTkButton(
            self.top_bar, text="☰", width=40, height=40, command=self.toggle_tabview)
        self.hamburger_button.grid(row=0, column=0, padx=(0, 5), pady=5)
        _Tooltip(self.hamburger_button,
                 "Tab — открыть меню\n"
                 "Ctrl+D / Ctrl+В — Приборная панель\n"
                 "Ctrl+L / Ctrl+Д — Логи\n"
                 "Ctrl+K / Ctrl+Л — Подключения\n"
                 "Ctrl+Q / Ctrl+Й — Запросы\n"
                 "Ctrl+E / Ctrl+У — Настройки\n"
                 "Ctrl+N / Ctrl+Т — Уведомления\n"
                 "Ctrl+S / Ctrl+Ы — Сервисы")

        # ── хлебные крошки: 🏠 > Активная вкладка ───────────────────────────
        self._breadcrumb_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self._breadcrumb_frame.grid(row=0, column=1, padx=(0, 5), pady=5, sticky="w")

        _home_icon = _get_tab_icon("bars", 16)
        self._home_btn = ctk.CTkButton(
            self._breadcrumb_frame,
            text="" if _home_icon else "📊",
            image=_home_icon,
            width=40, height=35,
            fg_color="transparent",
            hover_color=("gray75", "gray30"),
            text_color=("gray10", "gray90"),
            command=lambda: self._hamburger_select("📊 Приборная панель"),
        )
        self._home_btn.grid(row=0, column=0, padx=(0, 0))
        _Tooltip(self._home_btn, "Перейти на Приборную панель")

        self._breadcrumb_sep = ctk.CTkLabel(
            self._breadcrumb_frame,
            text=">",
            text_color=("gray55", "gray60"),
            font=ctk.CTkFont(size=15),
            width=15,
        )
        self._breadcrumb_sep.grid(row=0, column=1, padx=(2, 4))

        self._active_tab_label = ctk.CTkLabel(
            self._breadcrumb_frame,
            text="Приборная панель",
            anchor="w",
            font=ctk.CTkFont(size=16),
        )
        self._active_tab_label.grid(row=0, column=2, padx=(0, 0))
        # При старте активна Приборная панель — скрываем кнопку «домой» и «>»
        self._home_btn.grid_remove()
        self._breadcrumb_sep.grid_remove()

        self.tab_nav = _TabBar(
            self.top_bar,
            values=["📊 Приборная панель", "📋 Логи",
                    "🔗 Подключения", "📝 Запросы", "⚙️ Настройки"],
            command=self.on_tab_selected,
            height=40,
        )
        # tab_nav не отображается в top_bar — навигация через выпадающее меню ☰
        self.tab_nav.set("📊 Приборная панель")

        # тулбары (col 2) — переключаются по вкладке
        self.toolbars: dict[str, ctk.CTkFrame] = {}
        for tab_name in ("🔗 Подключения", "📝 Запросы", "📋 Логи", "⚙️ Настройки"):
            tb = ctk.CTkFrame(self.top_bar, fg_color="transparent")
            tb.grid(row=0, column=2, pady=5, padx=(10, 0), sticky="w")
            tb.grid_remove()
            self.toolbars[tab_name] = tb

        # Полоса виджетов (col 3, между тулбарами и статус-баром)
        self._header_widget_bar = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self._header_widget_bar.place(relx=0.5, rely=0.5, anchor="center")
        self._header_widgets: dict = {}  # {filename: _HeaderWidget}

        # строка состояния Приборной панели (col 4, справа)
        self.dash_status_bar = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.dash_status_bar.grid(row=0, column=4, pady=5, padx=(0, 8), sticky="e")
        self._build_dash_status_bar()

        # ── область контента ─────────────────────────────────────────────────
        # transparent — сливается с фоном приложения
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.frame_dashboard       = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.frame_connections     = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.frame_queries         = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.frame_logs            = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.frame_appearance      = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.frame_notifications   = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.frame_services        = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.frame_reminders       = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        for f in (self.frame_dashboard, self.frame_connections, self.frame_queries,
                  self.frame_logs, self.frame_appearance, self.frame_notifications,
                  self.frame_services, self.frame_reminders):
            f.grid(row=0, column=0, sticky="nsew")

        self.setup_dashboard_tab()
        self.setup_connections_tab()
        self.setup_queries_tab()
        self.setup_logs_tab()
        self.setup_appearance_tab()
        self.setup_notifications_tab()
        self.setup_services_tab()
        self.setup_reminders_tab()

        self._refresh_header_widgets()

        self.is_tabview_visible = False
        self._active_tab = "📊 Приборная панель"
        self.frame_dashboard.tkraise()

        cur_theme = self.settings_manager.get_setting("theme", "dark")
        self._apply_tab_text_color(cur_theme)
        if hasattr(self, "dash_panels"):
            for panel in self.dash_panels:
                panel.refresh_theme(cur_theme)

        self._build_hamburger_menu()
        self.bind_all("<Button-1>", self._on_global_click, add="+")
        self.bind("<Tab>", self._on_tab_hotkey, add="+")   # когда фокус на самом окне
        self.after(500, self._bind_tab_to_canvas)           # для Canvas-виджетов внутри окна

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(300, self._start_auto_timers)
        self.bind("<Alt-F4>", lambda e: self.on_closing(), add="+")
        self.deiconify()
        self._refresh_titlebar(cur_theme == "dark")
        self.after(100, lambda: self.state('zoomed'))

        if self.settings_manager.get_setting("check_updates", True):
            self.after(3000, self._check_for_updates)

    # ── обновления ────────────────────────────────────────────────────────────

    def _check_for_updates(self):
        """Запрашивает последний релиз с GitHub в фоновом потоке."""
        import threading, urllib.request, json as _json, queue as _queue

        _SPIN     = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        _spin_job = [None]
        _q        = _queue.SimpleQueue()

        def _tick(i: int = 0):
            if not hasattr(self, "_ham_ver_lbl"):
                return
            try:
                self._ham_ver_lbl.configure(
                    text=f"{_SPIN[i % len(_SPIN)]} Проверка обновлений…\nВерсия {self._version}")
            except Exception:
                return
            _spin_job[0] = self.after(120, lambda: _tick(i + 1))

        def _stop_spin():
            if _spin_job[0]:
                try:
                    self.after_cancel(_spin_job[0])
                except Exception:
                    pass
                _spin_job[0] = None
            try:
                if hasattr(self, "_ham_ver_lbl"):
                    self._ham_ver_lbl.configure(
                        text=f"Hunch Desktop\nВерсия {self._version}")
            except Exception:
                pass

        def _parse_ver(v: str):
            try:
                return tuple(int(x) for x in v.strip().lstrip("v").split("."))
            except Exception:
                return (0,)

        def _fetch():
            try:
                url = "https://api.github.com/repos/Melodic-Gambit/Hunch/releases"
                req = urllib.request.Request(url, headers={
                    "User-Agent":           "Hunch-Desktop",
                    "Accept":               "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                })
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = _json.loads(resp.read().decode())
                if not data:
                    _q.put(("done", None, None))
                    return
                latest_tag = data[0].get("tag_name", "").strip()
                if not latest_tag:
                    _q.put(("done", None, None))
                    return
                installer_url = ""
                for _asset in data[0].get("assets", []):
                    if _asset.get("name", "").endswith("_installer.exe"):
                        installer_url = _asset.get("browser_download_url", "")
                        break
                if _parse_ver(latest_tag) > _parse_ver(
                        getattr(self, "_version", "0.0.0")):
                    _q.put(("update", latest_tag, installer_url))
                else:
                    _q.put(("done", None, None))
            except Exception as _err:
                _q.put(("error",
                        f"Проверка обновлений не выполнена: {type(_err).__name__}: {_err}",
                        None))

        def _poll():
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return
            try:
                item = _q.get_nowait()
            except _queue.Empty:
                self.after(150, _poll)
                return
            _stop_spin()
            if item[0] == "update":
                try:
                    self._show_update_toast(item[1], item[2])
                except Exception:
                    pass
            elif item[0] == "error":
                try:
                    self._add_notification("Система", message=item[1], system=True)
                except Exception:
                    pass

        _tick()
        threading.Thread(target=_fetch, daemon=True).start()
        self.after(150, _poll)

    def _show_update_toast(self, new_version: str, installer_url: str = ""):
        """Показывает уведомление об обновлении по центру окна."""
        import webbrowser, threading as _thr

        # FEAT-11: дублируем в вкладку «Уведомления»
        try:
            cur = getattr(self, "_version", "?")
            self._add_notification(
                "Система",
                message=f"Доступно обновление {new_version}. Установлена версия {cur}.",
                system=True,
            )
        except Exception:
            pass

        try:
            toast = ctk.CTkToplevel(self)
            toast.withdraw()
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)

            outer = ctk.CTkFrame(
                toast, corner_radius=10,
                border_width=1, border_color=("gray60", "gray40"))
            outer.pack(padx=2, pady=2, fill="both", expand=True)

            ctk.CTkLabel(
                outer,
                text=f"Доступно обновление  {new_version}",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).pack(padx=14, pady=(12, 4), fill="x")

            ctk.CTkLabel(
                outer,
                text="Новая версия доступна на GitHub",
                font=ctk.CTkFont(size=11),
                text_color=("gray50", "gray55"),
                anchor="w",
            ).pack(padx=14, pady=(0, 10), fill="x")

            btn_row = ctk.CTkFrame(outer, fg_color="transparent")
            btn_row.pack(padx=10, pady=(0, 12), fill="x")

            # Прогресс-блок (скрыт до нажатия «Установить»)
            prog_frame = ctk.CTkFrame(outer, fg_color="transparent")
            prog_bar = ctk.CTkProgressBar(prog_frame, height=10)
            prog_bar.set(0)
            prog_bar.pack(padx=14, pady=(0, 4), fill="x")
            prog_lbl = ctk.CTkLabel(
                prog_frame, text="Загрузка…",
                font=ctk.CTkFont(size=10), text_color=("gray50", "gray55"), anchor="w")
            prog_lbl.pack(padx=14, pady=(0, 8), fill="x")

            ctk.CTkButton(
                btn_row, text="Открыть", width=90, height=28,
                command=lambda: (
                    webbrowser.open("https://github.com/Melodic-Gambit/Hunch/releases"),
                    toast.destroy()),
            ).pack(side="left", padx=(0, 6))

            _auto_close_job = [None]

            if installer_url:
                def _do_install():
                    # Отменяем автозакрытие — пользователь начал установку
                    if _auto_close_job[0]:
                        try:
                            self.after_cancel(_auto_close_job[0])
                        except Exception:
                            pass
                        _auto_close_job[0] = None

                    btn_row.pack_forget()
                    prog_frame.pack(padx=10, pady=(0, 12), fill="x")
                    toast.update_idletasks()
                    tw = toast.winfo_width()
                    th = toast.winfo_reqheight() + 6
                    cx = self.winfo_x() + (self.winfo_width()  - tw) // 2
                    cy = self.winfo_y() + (self.winfo_height() - th) // 2
                    toast.geometry(f"{tw}x{th}+{cx}+{cy}")

                    import tempfile, urllib.request, ctypes as _ct, os as _os
                    tmp_path = _os.path.join(
                        tempfile.gettempdir(), f"Hunch_{new_version}_installer.exe")

                    def _reporthook(blk, blk_sz, total):
                        if total <= 0:
                            return
                        frac   = min(blk * blk_sz / total, 1.0)
                        done_m = blk * blk_sz / 1_048_576
                        tot_m  = total / 1_048_576
                        def _ui(f=frac, d=done_m, t=tot_m):
                            if not toast.winfo_exists():
                                return
                            prog_bar.set(f)
                            prog_lbl.configure(text=f"Загрузка… {d:.1f} / {t:.1f} МБ")
                        self.after(0, _ui)

                    def _fetch_and_run():
                        try:
                            urllib.request.urlretrieve(installer_url, tmp_path, _reporthook)
                            def _launch():
                                if toast.winfo_exists():
                                    prog_lbl.configure(text="Запуск установщика…")
                                # Non-daemon поток: живёт после destroy(), запускает
                                # установщик через 3 с — Hunch.exe уже освобождён
                                import threading as _thr2, time as _time2
                                def _run_after_close():
                                    _time2.sleep(3)
                                    _ct.windll.shell32.ShellExecuteW(
                                        None, "runas", tmp_path,
                                        "/SILENT /RESTARTAPPLICATIONS",
                                        None, 1)
                                _thr2.Thread(target=_run_after_close,
                                             daemon=False).start()
                                self.after(300, self.destroy)
                            self.after(0, _launch)
                        except Exception as _err:
                            def _on_error(e=_err):
                                if not toast.winfo_exists():
                                    return
                                prog_bar.set(0)
                                prog_lbl.configure(
                                    text=f"Ошибка: {e}",
                                    text_color=("#DC2626", "#EF4444"))
                            self.after(0, _on_error)

                    _thr.Thread(target=_fetch_and_run, daemon=True).start()

                ctk.CTkButton(
                    btn_row, text="Установить", width=100, height=28,
                    fg_color=theme_colors.accent(),
                    hover_color=theme_colors.hover(),
                    command=_do_install,
                ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                btn_row, text="Закрыть", width=80, height=28,
                fg_color=("gray65", "gray35"),
                hover_color=("gray55", "gray25"),
                command=toast.destroy,
            ).pack(side="left")

            # UX-10: по центру окна, 30 с (отменяется если пользователь нажал «Установить»)
            toast.update_idletasks()
            w = 360 if installer_url else 310
            h = toast.winfo_reqheight() + 6
            x = self.winfo_x() + (self.winfo_width()  - w) // 2
            y = self.winfo_y() + (self.winfo_height() - h) // 2
            toast.geometry(f"{w}x{h}+{x}+{y}")
            toast.deiconify()
            _auto_close_job[0] = toast.after(
                30_000, lambda: toast.destroy() if toast.winfo_exists() else None)
        except Exception:
            pass

    # ── служебные ─────────────────────────────────────────────────────────────

    # ── системный трей ────────────────────────────────────────────────────────

    def _ensure_tray_icon(self) -> bool:
        if getattr(self, "_tray_icon", None) is not None:
            return True
        try:
            import pystray
            from PIL import Image as _PILImg
            import threading as _thr

            _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            _ico  = os.path.join(_base, "Hunch.ico")
            try:
                _img = _PILImg.open(_ico)
            except Exception:
                _img = _PILImg.new("RGBA", (64, 64), (13, 148, 136, 255))

            _menu = pystray.Menu(
                pystray.MenuItem(
                    "Открыть",
                    lambda i, item: self.after(0, self._tray_restore),
                    default=True,
                ),
                pystray.MenuItem(
                    "Настройки",
                    lambda i, item: self.after(0, self._tray_open_settings),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Выйти",
                    lambda i, item: self.after(0, self._tray_quit),
                ),
            )
            self._tray_icon = pystray.Icon("Hunch", _img, "Hunch", _menu)
            _thr.Thread(target=self._tray_icon.run, daemon=True).start()
            return True
        except Exception:
            self._tray_icon = None
            return False

    def _tray_restore(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_open_settings(self):
        self._tray_restore()
        try:
            self.tabview.set("⚙️ Настройки")
        except Exception:
            pass

    def _tray_quit(self):
        self._quitting = True
        if getattr(self, "_tray_icon", None):
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self.on_closing()

    def on_closing(self):
        # При закрытии через × сворачиваемся в трей (если pystray доступен)
        if not getattr(self, "_quitting", False):
            if self._ensure_tray_icon():
                try:
                    if hasattr(self, "dash_panels"):
                        self._save_dashboard_state()
                except Exception:
                    pass
                try:
                    statuses_to_save = {k: v for k, v in self._conn_statuses.items()
                                        if v is not None}
                    self.settings_manager.set_setting("conn_status_cache", statuses_to_save)
                    self.settings_manager.flush()
                except Exception:
                    pass
                self.withdraw()
                return

        from widgets.animated import _cancel_widget_timers
        # Отменяем все after-таймеры перед уничтожением окна
        for _id in list(getattr(self, "_query_timers", {}).values()):
            try: self.after_cancel(_id)
            except Exception: pass
        for _id in list(getattr(self, "_conn_timers", {}).values()):
            try: self.after_cancel(_id)
            except Exception: pass
        for _attr in ("_rotation_after_id", "_rotation_warn_after_id",
                      "_notif_rotation_after_id",
                      "_status_clock_after_id", "_refresh_bar_after_id"):
            _id = getattr(self, _attr, None)
            if _id:
                try: self.after_cancel(_id)
                except Exception: pass
        # Отменяем таймеры анимированных виджетов в панелях дашборда
        for _panel in getattr(self, "dash_panels", []):
            try:
                _cancel_widget_timers(_panel)
            except Exception:
                pass
        # Каждое сохранение в отдельном try — гарантируем, что все выполнятся
        try:
            self._save_query_cache()
        except Exception:
            pass
        try:
            self._save_alert_history()
        except Exception:
            pass
        try:
            if hasattr(self, "dash_panels"):
                self._save_dashboard_state()
        except Exception:
            pass
        try:
            statuses_to_save = {k: v for k, v in self._conn_statuses.items()
                                if v is not None}
            self.settings_manager.set_setting("conn_status_cache", statuses_to_save)
        except Exception:
            pass
        try:
            self.db_manager.close_all()
        except Exception:
            pass
        try:
            self.log_manager.flush()
        except Exception:
            pass
        try:
            self.settings_manager.flush()
        except Exception:
            pass
        # Сигнал остановки GF.Scraping фоновым потокам
        try:
            self._gf_stop_event.set()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    def _get_theme_bg(self) -> str:
        """Возвращает HEX фона CTk-окна для текущей темы."""
        idx = 1 if ctk.get_appearance_mode() == "Dark" else 0
        try:
            c = ctk.ThemeManager.theme["CTk"]["fg_color"]
            return c[idx] if isinstance(c, (list, tuple)) else c
        except Exception:
            return "#212121" if ctk.get_appearance_mode() == "Dark" else "#ebebeb"

    def _get_query_names(self) -> list[str]:
        qdir = self.data_manager.queries_dir
        if not os.path.exists(qdir):
            return []
        try:
            return [self.data_manager.get_query_display_name(f)
                    for f in os.listdir(qdir) if f.endswith(".sql")]
        except Exception:
            return []

    def toggle_tabview(self):
        if self.is_tabview_visible:
            self._hide_hamburger_menu()
        else:
            self._show_hamburger_menu()

    # ── анимация боковой панели ──────────────────────────────────────────────
    _ANIM_STEPS = 10
    _ANIM_MS    = 16   # ~60 fps

    def _build_hamburger_menu(self):
        """Создаёт боковую панель навигации (слайд слева, как в Telegram)."""
        _BTN_W = 242          # +5 % от предыдущего значения 230
        _PAD   = 6
        self._ham_width = _BTN_W + _PAD * 2 + 2

        _is_dark = ctk.get_appearance_mode() == "Dark"
        _ham_bg  = "gray18" if _is_dark else "gray88"
        self._ham_container = tk.Frame(self, bd=0, highlightthickness=0, bg=_ham_bg)

        self._hamburger_menu = ctk.CTkFrame(
            self._ham_container,
            corner_radius=0,
            fg_color=("gray88", "gray18"),
            border_width=1,
            border_color=("gray70", "gray35"),
        )
        self._hamburger_menu.pack(fill="both", expand=True)

        self._ham_tabs = [
            "📊 Приборная панель",
            "📋 Логи",
            "🔗 Подключения",
            "📝 Запросы",
            "⚙️ Настройки",
            "⏰ Напоминания",
            "🔔 Уведомления",
            "🛠 Сервисы",
        ]
        self._hamburger_btns: dict = {}
        n = len(self._ham_tabs)
        self._hamburger_menu.grid_columnconfigure(0, weight=1)
        for i, tab in enumerate(self._ham_tabs):
            shape = _TabBar._SHAPES.get(tab)
            icon  = _get_tab_icon(shape, 16) if shape else None
            label = tab.split(" ", 1)[1] if " " in tab else tab
            pady  = (6, 2) if i == 0 else (2, 2)
            # "Приборная панель" — обычная команда (не перетаскивается)
            # остальные вкладки — command=None, навигация через _ham_btn_release
            # ВАЖНО: условие вычисляется здесь (снаружи лямбды), а не в момент вызова
            cmd = (lambda t=tab: self._hamburger_select(t)) if tab == "📊 Приборная панель" else None
            btn = ctk.CTkButton(
                self._hamburger_menu,
                text=label,
                image=icon,
                compound="left",
                anchor="w",
                height=36,
                width=_BTN_W,
                font=ctk.CTkFont(size=16),
                fg_color="transparent",
                hover_color=("gray75", "gray30"),
                text_color=("gray10", "gray90"),
                corner_radius=6,
                command=cmd,
            )
            btn.grid(row=i, column=0, padx=_PAD, pady=pady, sticky="ew")
            self._hamburger_btns[tab] = btn

        # ── Разделитель + Ночной режим ────────────────────────────────────────
        self._ham_sep = ctk.CTkFrame(
            self._hamburger_menu, height=1,
            fg_color=("gray70", "gray35"))
        self._ham_sep.grid(row=n, column=0, padx=_PAD * 2, pady=(8, 2), sticky="ew")

        self._ham_night_frame = ctk.CTkFrame(
            self._hamburger_menu, fg_color="transparent")
        self._ham_night_frame.grid(row=n + 1, column=0, padx=_PAD, pady=(2, 6), sticky="ew")
        self._ham_night_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._ham_night_frame, text="🌙",
            font=ctk.CTkFont(size=16),
            text_color=("gray10", "gray90"),
        ).grid(row=0, column=0, padx=(6, 8), sticky="w")

        ctk.CTkLabel(
            self._ham_night_frame, text="Ночной режим",
            anchor="w", font=ctk.CTkFont(size=16),
            text_color=("gray10", "gray90"),
        ).grid(row=0, column=1, sticky="w")

        is_dark = ctk.get_appearance_mode() == "Dark"
        self._ham_night_switch = ctk.CTkSwitch(
            self._ham_night_frame, text="",
            width=46, height=24,
            progress_color=theme_colors.accent(),
            button_color=(theme_colors.accent(), "gray60"),
            button_hover_color=(theme_colors.hover(), "gray50"),
            command=self._toggle_night_mode,
        )
        if is_dark:
            self._ham_night_switch.select()
        else:
            self._ham_night_switch.deselect()
        self._ham_night_switch.grid(row=0, column=2, padx=(0, 4))

        self._hamburger_menu.grid_rowconfigure(n + 2, weight=1)
        self._ham_spacer = ctk.CTkFrame(
            self._hamburger_menu, fg_color="transparent", height=1)
        self._ham_spacer.grid(row=n + 2, column=0, sticky="nsew")
        self._ham_ver_lbl = ctk.CTkLabel(
            self._hamburger_menu,
            text=f"Hunch Desktop\nВерсия {self._version}",
            font=ctk.CTkFont(size=13),
            text_color=("gray50", "gray55"),
            justify="center",
            anchor="center",
        )
        self._ham_ver_lbl.grid(row=n + 3, column=0, padx=_PAD, pady=(4, 14), sticky="ew")

        self._update_hamburger_active(self._active_tab)

        # ── инициализация состояния drag-and-drop ────────────────────────────
        self._ham_dragging = False
        self._ham_hold_id  = None
        self._ham_ghost       = None
        self._ham_insert_line = None
        self._ham_drag_tab    = None
        self._ham_drag_target = 0

        # привязываем drag к кнопкам после отрисовки
        self.update_idletasks()
        for tab, btn in self._hamburger_btns.items():
            if tab != "📊 Приборная панель":
                self._ham_bind_drag(btn, tab)

        # глобальные события движения и отпускания мышки
        self.bind_all("<B1-Motion>",       self._ham_motion,      add="+")
        self.bind_all("<ButtonRelease-1>", self._ham_btn_release, add="+")

        # Tab-хоткей: применяем после отрисовки
        self.after(50, lambda: self._bind_tab_to_canvas(self._ham_container))
        # Ctrl-хоткеи для быстрой навигации по вкладкам
        self.after(100, self._bind_nav_hotkeys)

    # ── drag-and-drop вкладок меню ────────────────────────────────────────────

    def _ham_bind_drag(self, btn, tab):
        """Привязывает события зажатия к кнопке и её дочерним виджетам."""
        press = lambda e, t=tab: self._ham_press(e, t)
        for w in [btn] + list(btn.winfo_children()):
            w.bind("<ButtonPress-1>", press, add="+")

    def _ham_press(self, event, tab):
        """Запускает таймер 500 мс; если удержан — начинается перетаскивание."""
        self._ham_cancel_hold()
        self._ham_drag_tab = tab
        self._ham_hold_id  = self.after(500, lambda: self._ham_enter_drag(tab))

    def _ham_cancel_hold(self):
        if self._ham_hold_id:
            self.after_cancel(self._ham_hold_id)
            self._ham_hold_id = None

    def _ham_enter_drag(self, tab):
        """Переходит в режим перетаскивания после 3 с удержания."""
        self._ham_hold_id  = None
        self._ham_dragging = True
        draggable = [t for t in self._ham_tabs if t != "📊 Приборная панель"]
        self._ham_drag_target = draggable.index(tab)

        # призрак — полупрозрачная копия кнопки, следует за курсором
        label = tab.split(" ", 1)[1] if " " in tab else tab
        btn   = self._hamburger_btns[tab]
        ghost_y = btn.winfo_rooty() - self._ham_container.winfo_rooty()
        self._ham_ghost = tk.Label(
            self._ham_container,
            text=f"  {label}",
            bg=theme_colors.accent(), fg="white",
            font=("Segoe UI", 14),
            anchor="w", relief="flat",
        )
        self._ham_ghost.place(x=4, y=ghost_y,
                              width=self._ham_width - 8, height=36)
        self._ham_ghost.lift()

        # линия-индикатор вставки
        self._ham_insert_line = tk.Frame(
            self._ham_container, bg=theme_colors.accent(), height=3)
        self._ham_insert_line.lift()

        # притушить перетаскиваемую кнопку
        btn.configure(fg_color=("gray75", "gray30"))

    def _ham_motion(self, event):
        """Перемещает призрак и пересчитывает позицию вставки."""
        if not self._ham_dragging:
            return

        # двигаем призрак за курсором
        y_rel = event.y_root - self._ham_container.winfo_rooty()
        self._ham_ghost.place(x=4, y=max(0, y_rel - 18),
                              width=self._ham_width - 8, height=36)

        # определяем ближайший слот среди остальных перетаскиваемых вкладок
        draggable = [t for t in self._ham_tabs if t != "📊 Приборная панель"]
        best_idx, best_dist = self._ham_drag_target, float("inf")
        for i, t in enumerate(draggable):
            if t == self._ham_drag_tab:
                continue
            b   = self._hamburger_btns[t]
            cy  = b.winfo_rooty() - self._ham_container.winfo_rooty() + b.winfo_height() / 2
            dist = abs(y_rel - cy)
            if dist < best_dist:
                best_dist, best_idx = dist, i

        self._ham_drag_target = best_idx

        # показываем линию-индикатор над целевой кнопкой
        target_tab = draggable[best_idx]
        tb  = self._hamburger_btns[target_tab]
        ty  = tb.winfo_rooty() - self._ham_container.winfo_rooty()
        # вставляем ДО или ПОСЛЕ в зависимости от половины кнопки
        if y_rel > ty + tb.winfo_height() / 2:
            ty += tb.winfo_height()
        self._ham_insert_line.place(x=4, y=ty - 1,
                                    width=self._ham_width - 8)
        self._ham_insert_line.lift()

    def _ham_btn_release(self, event):
        """Отпускание мышки: навигация (короткое нажатие) или завершение перетаскивания."""
        was_holding = self._ham_hold_id is not None
        tab_pressed = self._ham_drag_tab
        self._ham_cancel_hold()

        if self._ham_dragging:
            # ── завершение drag-and-drop ─────────────────────────────────────
            self._ham_dragging = False
            if self._ham_ghost:
                self._ham_ghost.destroy()
                self._ham_ghost = None
            if self._ham_insert_line:
                self._ham_insert_line.destroy()
                self._ham_insert_line = None
            draggable = [t for t in self._ham_tabs if t != "📊 Приборная панель"]
            draggable.remove(tab_pressed)
            draggable.insert(self._ham_drag_target, tab_pressed)
            self._ham_tabs = ["📊 Приборная панель"] + draggable
            self._ham_drag_tab = None
            self._ham_rebuild()

        elif was_holding and tab_pressed:
            # ── обычный клик (отпустили раньше 3 с) → навигация ─────────────
            self._ham_drag_tab = None
            self._hamburger_select(tab_pressed)

    def _ham_rebuild(self):
        """Перерасставляет кнопки в grid согласно текущему порядку _ham_tabs."""
        _PAD = 6
        n    = len(self._ham_tabs)
        for i, tab in enumerate(self._ham_tabs):
            pady = (6, 2) if i == 0 else (2, 2)
            self._hamburger_btns[tab].grid(
                row=i, column=0, padx=_PAD, pady=pady, sticky="ew")
        self._ham_sep.grid(row=n, column=0, padx=_PAD * 2, pady=(8, 2), sticky="ew")
        self._ham_night_frame.grid(row=n + 1, column=0, padx=_PAD, pady=(2, 6), sticky="ew")
        self._hamburger_menu.grid_rowconfigure(n + 2, weight=1)
        self._ham_spacer.grid(row=n + 2,  column=0, sticky="nsew")
        self._ham_ver_lbl.grid(row=n + 3, column=0,
                               padx=_PAD, pady=(4, 14), sticky="ew")
        self._update_hamburger_active(self._active_tab)

    def _animate_slide(self, show: bool, step: int, h: int):
        """Анимирует выдвижение/скрытие боковой панели (ease-out/ease-in)."""
        t = step / self._ANIM_STEPS
        if show:
            ease = 1 - (1 - t) ** 2          # ease-out
            x = int(-self._ham_width * (1 - ease))
        else:
            ease = t ** 2                      # ease-in
            x = int(-self._ham_width * ease)
        self._ham_container.place(x=x, y=0, height=h, width=self._ham_width)
        if step < self._ANIM_STEPS:
            self.after(self._ANIM_MS, lambda: self._animate_slide(show, step + 1, h))
        elif not show:
            self._ham_container.place_forget()

    def _show_hamburger_menu(self):
        """Выдвигает боковую панель слева."""
        h = self.winfo_height()
        self._ham_container.place(x=-self._ham_width, y=0,
                                  height=h, width=self._ham_width)
        self._ham_container.lift()
        self.is_tabview_visible = True
        self._animate_slide(show=True, step=0, h=h)

    def _hide_hamburger_menu(self):
        """Убирает боковую панель влево."""
        if not self.is_tabview_visible:
            return
        self.is_tabview_visible = False
        h = self._ham_container.winfo_height()
        self._animate_slide(show=False, step=0, h=h)

    def _hamburger_select(self, tab_name: str):
        """Обрабатывает выбор вкладки из выпадающего меню."""
        self._active_tab = tab_name
        self._update_hamburger_active(tab_name)
        self.tab_nav.set(tab_name)
        self.on_tab_selected(tab_name)
        self._hide_hamburger_menu()

    def _update_hamburger_active(self, active: str):
        """Подсвечивает активную вкладку в выпадающем меню."""
        if not hasattr(self, "_hamburger_btns"):
            return
        for name, btn in self._hamburger_btns.items():
            btn.configure(
                fg_color=[theme_colors.accent(), theme_colors.hover()] if name == active else "transparent"
            )

    def _on_global_click(self, event):
        """Закрывает выпадающее меню при клике вне его области."""
        if not self.is_tabview_visible or getattr(self, '_ham_dragging', False):
            return
        widget = event.widget
        while widget is not None:
            if widget in (self._hamburger_menu, self._ham_container,
                          self.hamburger_button):
                return
            widget = getattr(widget, "master", None)
        self._hide_hamburger_menu()

    def _on_tab_hotkey(self, event):
        """Разворачивает/сворачивает меню ☰ по клавише Tab (кроме полей ввода и диалогов)."""
        w = event.widget
        if isinstance(w, (tk.Entry, tk.Text)):
            return
        try:
            if w.winfo_toplevel() is not self:
                if self.grab_current() is not None:
                    return  # модальный диалог блокирует хоткей
                self.focus_set()  # немодальное окно — перехватываем фокус
        except Exception:
            return
        self.toggle_tabview()
        return "break"

    def _bind_tab_to_canvas(self, root=None):
        """Добавляет Tab-хоткей на уровне instance-binding всех Canvas в окне.

        Instance-binding срабатывает ДО class-binding, который возвращает 'break'
        и поглощает Tab до того, как событие дойдёт до Toplevel.
        """
        if root is None:
            root = self
        if isinstance(root, tk.Canvas):
            root.bind("<Tab>", self._on_tab_hotkey)  # без add="+" — instance, перед class
        for child in root.winfo_children():
            self._bind_tab_to_canvas(child)

    # ── Ctrl-хоткеи быстрой навигации (EN + RU раскладки) ───────────────────
    # EN: Ctrl+D/L/K/Q/E/N/S   RU: Ctrl+В/Д/Л/Й/У/Т/Ы
    _NAV_HOTKEYS = {
        "d": "📊 Приборная панель",
        "l": "📋 Логи",
        "k": "🔗 Подключения",
        "q": "📝 Запросы",
        "e": "⚙️ Настройки",
        "n": "🔔 Уведомления",
        "s": "🛠 Сервисы",
    }

    # Карта физических кодов клавиш (Windows VK, layout-независимые) → вкладка.
    # Работает для любой раскладки: EN (D/L/K/Q/E/N/S) и RU (В/Д/Л/Й/У/Т/Ы).
    _NAV_KEYCODE_MAP = {
        68: "📊 Приборная панель",   # D / В
        76: "📋 Логи",               # L / Д
        75: "🔗 Подключения",        # K / Л
        81: "📝 Запросы",            # Q / Й
        69: "⚙️ Настройки",          # E / У
        78: "🔔 Уведомления",        # N / Т
        83: "🛠 Сервисы",            # S / Ы
    }

    def _bind_nav_hotkeys(self):
        # Явные биндинги для английской раскладки (резервный путь)
        for key, tab in self._NAV_HOTKEYS.items():
            for seq in (f"<Control-{key}>", f"<Control-{key.upper()}>"):
                self.bind_all(seq,
                              lambda e, t=tab: self._on_nav_hotkey(e, t),
                              add="+")
        # Catch-all через keycode — работает при любой раскладке клавиатуры
        self.bind_all("<Control-KeyPress>", self._on_ctrl_keypress_ru, add="+")
        # F1 — открыть инструкцию с прокруткой к разделу «Горячие клавиши»
        self.bind_all("<F1>", self._on_f1_hotkey, add="+")

    def _on_f1_hotkey(self, event):
        w = event.widget
        if isinstance(w, (tk.Entry, tk.Text)):
            return
        try:
            if w.winfo_toplevel() is not self:
                return
        except Exception:
            return
        self._open_instruktsiya_window(scroll_to_hotkeys=True)
        return "break"

    def _on_ctrl_keypress_ru(self, event):
        """Навигация по keycode — layout-независимо (EN и RU раскладки)."""
        tab = self._NAV_KEYCODE_MAP.get(event.keycode)
        if tab:
            return self._on_nav_hotkey(event, tab)

    def _on_nav_hotkey(self, event, tab_name: str):
        """Переходит на вкладку tab_name по Ctrl-хоткею."""
        w = event.widget
        try:
            if w.winfo_toplevel() is not self:
                if self.grab_current() is not None:
                    return  # модальный диалог блокирует хоткей
                self.focus_set()  # немодальное окно — перехватываем фокус
        except Exception:
            return
        # Если фокус был в поле ввода — снимаем его перед переходом
        if isinstance(w, (tk.Entry, tk.Text)):
            self.focus_set()
        self._hamburger_select(tab_name)
        return "break"

    def on_tab_selected(self, value):
        frame_map = {
            "📊 Приборная панель": self.frame_dashboard,
            "📋 Логи":            self.frame_logs,
            "🔗 Подключения":     self.frame_connections,
            "📝 Запросы":         self.frame_queries,
            "⚙️ Настройки":       self.frame_appearance,
            "⏰ Напоминания":      self.frame_reminders,
            "🔔 Уведомления":     self.frame_notifications,
            "🛠 Сервисы":         self.frame_services,
        }
        if value in frame_map:
            frame_map[value].tkraise()
        if value == "⚙️ Настройки":
            self.after(0, self._refresh_frames_table)
            self.after(0, self._refresh_notif_query_checkboxes)
        if value == "🔔 Уведомления":
            self._mark_all_read()
        if value == "⏰ Напоминания":
            self._refresh_reminders_list()
        for name, tb in self.toolbars.items():
            if name == value and tb.winfo_children():
                tb.grid()
            else:
                tb.grid_remove()
        # обновить хлебные крошки
        if hasattr(self, "_active_tab_label"):
            label = value.split(" ", 1)[1] if " " in value else value
            self._active_tab_label.configure(text=label)
            is_dashboard = (value == "📊 Приборная панель")
            if is_dashboard:
                self._home_btn.grid_remove()
                self._breadcrumb_sep.grid_remove()
            else:
                self._home_btn.grid()
                self._breadcrumb_sep.grid()

