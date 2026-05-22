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
from widgets.gf_scraping_module import GFScrapingWindow, _gf_check_url_hash, _gf_fetch_latest_numbers
from stats_manager import StatsManager
from widgets.gf_service_settings_dialog import GFServiceSettingsDialog
from widgets.dashboard_layout_dialog import DashboardLayoutDialog, DASHBOARD_TEMPLATES
import theme_colors

try:
    from PIL import Image, ImageDraw
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    import winsound as _winsound
    _WINSOUND_OK = True
except ImportError:
    _WINSOUND_OK = False

try:
    from winotify import Notification as _WinNotification
    _WINOTIFY_OK = True
except ImportError:
    _WINOTIFY_OK = False

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
        self.result: Optional[dict] = None
        self._columns      = columns
        self._configs      = {c: dict(current_configs.get(c, {})) for c in columns}
        self._panel_config = dict(panel_config or {})
        self._col_widgets: dict = {}
        self._build()
        self.update_idletasks()          # layout вычислен пока окно скрыто
        self._place_center(parent)       # позиционируем сразу — без after()
        self.deiconify()
        self.after(20, self.grab_set)    # grab после отрисовки

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
            ctk.CTkButton(self, text="Закрыть", command=self.destroy).pack(pady=(0, 10))
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
                      command=self.destroy).grid(row=0, column=1, padx=6)
        self.bind("<Escape>", lambda _: self.destroy())
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
        self.destroy()


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
        self.after(20, self.grab_set)

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
                      command=self.destroy).grid(row=0, column=2, padx=4)
        self.bind("<Escape>", lambda _: self.destroy())

    def _query(self) -> Optional[str]:
        v = self._query_var.get()
        return None if v == "Выберите запрос" else v

    def _on_run(self):
        self.result = (self._query(), self._render_var.get(),
                       self._timer_anim_var.get(), self._timer_color_var.get(), True)
        self.destroy()

    def _on_save(self):
        self.result = (self._query(), self._render_var.get(),
                       self._timer_anim_var.get(), self._timer_color_var.get(), False)
        self.destroy()


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
            self._spin_idx    = 0
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
            self.title_lbl.configure(
                text=self._base_title(),
                text_color=self._title_default_color,
            )

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
        if self._query_timeout > 0 and self._elapsed_secs >= self._query_timeout:
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
            self.result_table.set_data(rows, columns)

    def _render_animated(self, rows: list, columns: list, delta_data: dict = None):
        self.result_table.grid_remove()
        if self._anim_panel is None or not self._anim_panel.winfo_exists():
            self._anim_panel = AnimatedPanel(self)
            self._anim_panel.grid(row=1, column=0, sticky="nsew")
        self._anim_panel.render(rows, columns, self._viz_configs,
                                self._display1_age, delta_data or {})

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
        ctk.CTkButton(btn_frame, text="Отмена", command=self.destroy).grid(
            row=0, column=1, padx=(6, 0), sticky="ew")

        self.grid_columnconfigure(1, weight=1)
        self.entry.focus()
        self.bind("<Return>", lambda _: self._on_ok())
        self.bind("<Escape>", lambda _: self.destroy())
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
        self.destroy()

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
        ctk.CTkButton(bf, text="Отмена", command=self.destroy).grid(
            row=0, column=1, padx=(6, 0), sticky="ew")

        self.bind("<Escape>", lambda _: self.destroy())
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
        self.destroy()

    def _center(self):
        self.update_idletasks()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        w, h   = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        self.deiconify()



# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(ctk.CTk):
    def __init__(self, version: str = "0.0.0"):
        super().__init__()
        self.withdraw()                    # скрываем на время сборки UI, показываем в конце __init__
        self._version = version
        self.title(f"Hunch v{version}")

        self.data_manager    = DataManager()
        self.log_manager     = LogManager()
        self.db_manager      = DatabaseManager()
        self.settings_manager = SettingsManager()
        self.stats_manager   = StatsManager()

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

        self._active_toasts:        list = []   # резерв (не используется)
        self._signal_last_played:   dict = {}  # {query_name: monotonic} дебаунс сигнала 10 с
        self._alert_last_fired:     dict = {}  # {(query_file, type): monotonic} дебаунс алертов
        self._alert_history:        list = []  # [{ts, query_name, query_file, type, detail}]
        self._notif_row_widgets:    dict = {}  # {notif_id: ([widgets], orig_bg)} для мерцания
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

        self._notifications:          list = []   # [{id, query_name, timestamp, read}]
        self._notification_counter:   int  = 0
        self._notif_rotation_after_id       = None

        # GF.Scraping scheduler after-IDs
        self._gf_daily_after_id = None
        self._gf_cal_after_id   = None
        self._gf_stop_event     = threading.Event()  # сигнал отмены фоновых потоков
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
        for f in (self.frame_dashboard, self.frame_connections, self.frame_queries,
                  self.frame_logs, self.frame_appearance, self.frame_notifications,
                  self.frame_services):
            f.grid(row=0, column=0, sticky="nsew")

        self.setup_dashboard_tab()
        self.setup_connections_tab()
        self.setup_queries_tab()
        self.setup_logs_tab()
        self.setup_appearance_tab()
        self.setup_notifications_tab()
        self.setup_services_tab()

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
        _saved_state    = self.settings_manager.get_setting("window_state", "zoomed")
        _saved_geometry = self.settings_manager.get_setting("window_geometry", None)
        if _saved_state != "zoomed" and _saved_geometry:
            self.geometry(_saved_geometry)
        self.deiconify()
        self._refresh_titlebar(cur_theme == "dark")
        if _saved_state == "zoomed":
            self.after(100, lambda: self.state('zoomed'))
        else:
            self.after(100, self.deiconify)

        if self.settings_manager.get_setting("check_updates", True):
            self.after(3000, self._check_for_updates)

    # ── обновления ────────────────────────────────────────────────────────────

    def _check_for_updates(self):
        """Запрашивает последний релиз с gitverse.ru в фоновом потоке."""
        import threading, urllib.request, json as _json

        _SPIN     = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        _spin_job = [None]

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
                    "User-Agent":         "Hunch-Desktop",
                    "Accept":             "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                })
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = _json.loads(resp.read().decode())
                if not data:
                    self.after(0, _stop_spin)
                    return
                latest_tag = data[0].get("tag_name", "").strip()
                if not latest_tag:
                    self.after(0, _stop_spin)
                    return
                installer_url = ""
                for _asset in data[0].get("assets", []):
                    if _asset.get("name", "").endswith("_installer.exe"):
                        installer_url = _asset.get("browser_download_url", "")
                        break
                if _parse_ver(latest_tag) > _parse_ver(
                        getattr(self, "_version", "0.0.0")):
                    self.after(0, lambda t=latest_tag, u=installer_url: self._show_update_toast(t, u))
                self.after(0, _stop_spin)
            except Exception:
                self.after(0, _stop_spin)

        _tick()
        threading.Thread(target=_fetch, daemon=True).start()

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

            if installer_url:
                def _do_install():
                    btn_row.pack_forget()
                    prog_frame.pack(padx=10, pady=(0, 12), fill="x")
                    toast.update_idletasks()
                    tw = toast.winfo_width()
                    th = toast.winfo_reqheight() + 6
                    cx = self.winfo_x() + (self.winfo_width()  - tw) // 2
                    cy = self.winfo_y() + (self.winfo_height() - th) // 2
                    toast.geometry(f"{tw}x{th}+{cx}+{cy}")

                    import tempfile, urllib.request, subprocess, os as _os
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
                                subprocess.Popen(
                                    [tmp_path, "/SILENT",
                                     "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"])
                                self.after(800, self.destroy)
                            self.after(0, _launch)
                        except Exception:
                            def _on_error():
                                if not toast.winfo_exists():
                                    return
                                prog_frame.pack_forget()
                                btn_row.pack(padx=10, pady=(0, 12), fill="x")
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

            # UX-10: по центру окна, 30 с
            toast.update_idletasks()
            w = 360 if installer_url else 310
            h = toast.winfo_reqheight() + 6
            x = self.winfo_x() + (self.winfo_width()  - w) // 2
            y = self.winfo_y() + (self.winfo_height() - h) // 2
            toast.geometry(f"{w}x{h}+{x}+{y}")
            toast.deiconify()
            toast.after(30_000, lambda: toast.destroy() if toast.winfo_exists() else None)
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
            _state = self.state()
            if _state == "iconic":
                _state = "normal"
            self.settings_manager.set_setting("window_state", _state)
            if _state != "zoomed":
                self.settings_manager.set_setting("window_geometry", self.geometry())
        except Exception:
            pass
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
            self.db_manager.close_all()
        except Exception:
            pass
        try:
            self.log_manager.flush()
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
        if not os.path.exists("queries"):
            return []
        try:
            return [self.data_manager.get_query_display_name(f)
                    for f in os.listdir("queries") if f.endswith(".sql")]
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
                return
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
                return
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

    # ── Строка состояния Приборной панели ────────────────────────────────────

    def _build_dash_status_bar(self):
        bar = self.dash_status_bar
        self._notification_has_badge = False

        # ── значок оповещений (col 0) ─────────────────────────────────────────
        bell_container = ctk.CTkFrame(bar, fg_color="transparent", width=40, height=33)
        bell_container.grid(row=0, column=0, padx=(4, 10))
        bell_container.grid_propagate(False)
        self._bell_container = bell_container

        bell_img = _get_bell_ctk_image(badge=False, size=29)
        self.notification_bell_lbl = ctk.CTkLabel(
            bell_container, image=bell_img, text="" if bell_img else "🔔",
            cursor="hand2", corner_radius=4)
        self.notification_bell_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.notification_bell_lbl.bind("<Button-1>", lambda e: self._go_to_notifications())
        self.notification_bell_lbl.bind(
            "<Enter>", lambda e: self.notification_bell_lbl.configure(
                fg_color=("gray78", "gray32")))
        self.notification_bell_lbl.bind(
            "<Leave>", lambda e: self.notification_bell_lbl.configure(
                fg_color="transparent"))
        _Tooltip(self.notification_bell_lbl, "Уведомления")

        self._notif_badge_lbl = ctk.CTkLabel(
            bell_container, text="",
            font=ctk.CTkFont(size=8, weight="bold"),
            text_color="white",
            fg_color="#EF4444",
            corner_radius=4,
            width=15, height=14)
        self._notif_badge_lbl.place(x=22, y=0)
        self._notif_badge_lbl.place_forget()

        # ── секция «Время обновления» (col 1-4) ──────────────────────────────
        tq_img = _get_time_quarte_ctk_image(16)
        tq_lbl = ctk.CTkLabel(bar, image=tq_img, text="" if tq_img else "↺", width=20)
        tq_lbl.grid(row=0, column=1, padx=(0, 2))
        _Tooltip(tq_lbl, "Время последнего обновления БД")

        ctk.CTkLabel(bar, text="Время обновления", anchor="w",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=2, padx=(0, 4))

        self.refresh_progress = ctk.CTkProgressBar(bar, width=90, height=8)
        self.refresh_progress.set(0.0)
        self.refresh_progress.grid(row=0, column=3, padx=(0, 4))

        self.refresh_last_time_lbl = ctk.CTkLabel(bar, text="—", anchor="w", width=58,
                                                   font=ctk.CTkFont(size=12))
        self.refresh_last_time_lbl.grid(row=0, column=4, padx=(0, 8))

        # ── кнопка «Обновить все» (col 5) — между «обновлением» и «часами» ───
        _play_img = _get_play_ctk_image(24)
        self._refresh_all_btn = ctk.CTkButton(
            bar, image=_play_img, text="", width=40, height=40,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=self._force_refresh_all)
        self._refresh_all_btn.grid(row=0, column=5, padx=(0, 8))
        _Tooltip(self._refresh_all_btn, "Обновить все панели")

        # ── секция «Текущее время» (col 6-7) ─────────────────────────────────
        t_img = _get_time_ctk_image(16)
        t_lbl = ctk.CTkLabel(bar, image=t_img, text="" if t_img else "🕐", width=20)
        t_lbl.grid(row=0, column=6, padx=(0, 2))
        _Tooltip(t_lbl, "Текущее время")

        self.clock_label = ctk.CTkLabel(bar, text="00:00", anchor="w",
                                        width=44, font=ctk.CTkFont(size=12))
        self.clock_label.grid(row=0, column=7)

        # ── header-toast (place()-оверлей, не влияет на grid) ────────────────
        self._header_toast_frame    = None
        self._header_toast_notif_id = None
        self._header_toast_after_id = None

        self._status_clock_after_id = None
        self._refresh_bar_after_id  = None
        self._update_status_clock()
        self._update_refresh_bar()

    def set_notification_badge(self, state: bool):
        """Включает/выключает бейдж с числом непрочитанных уведомлений."""
        self._notification_has_badge = state
        img = _get_bell_ctk_image(badge=state, size=29)
        if img:
            self.notification_bell_lbl.configure(image=img)
        else:
            self.notification_bell_lbl.configure(text="🔔●" if state else "🔔")
        if state and hasattr(self, "_notif_badge_lbl"):
            count = sum(1 for n in self._notifications if not n.get("read"))
            if count > 0:
                self._notif_badge_lbl.configure(
                    text=str(count) if count <= 99 else "99+")
                self._notif_badge_lbl.place(x=22, y=0)
                self._set_taskbar_badge(True)
                return
        if hasattr(self, "_notif_badge_lbl"):
            self._notif_badge_lbl.place_forget()
        self._set_taskbar_badge(state)

    def _set_taskbar_badge(self, has_unread: bool):
        """Показывает/убирает красный оверлей на иконке программы в панели задач Windows."""
        if sys.platform != "win32":
            return
        try:
            if not hasattr(self, "_badge_hicon"):
                self._badge_hicon = _make_taskbar_badge_hicon()
            hwnd  = self.winfo_id()
            hicon = self._badge_hicon if has_unread else 0
            desc  = "Непрочитанные уведомления" if has_unread else ""
            _taskbar_set_overlay(hwnd, hicon, desc)
        except Exception:
            pass

    # ── Toast-уведомления (inline в шапке) ───────────────────────────────────

    def _show_alert_toast(self, title: str, message: str, notif_id: int = None):
        """Показывает inline-тост в шапке программы слева от иконки колокола."""
        self.set_notification_badge(True)
        self._show_header_toast(title, message, notif_id)
        self._send_system_toast(title, message)

    def _send_system_toast(self, title: str, message: str):
        """Отправляет Windows-уведомление (toast) когда окно не в фокусе."""
        if not _WINOTIFY_OK:
            return
        try:
            is_minimized = self.state() in ("iconic", "withdrawn")
            has_focus    = self.focus_get() is not None
            if not is_minimized and has_focus:
                return
            threading.Thread(
                target=self._bg_send_toast,
                args=(title, message[:250]),
                daemon=True
            ).start()
        except Exception:
            pass

    def _bg_send_toast(self, title: str, message: str):
        try:
            toast = _WinNotification(app_id="Hunch", title=title, msg=message, duration="short")
            toast.show()
        except Exception:
            pass

    def _show_header_toast(self, title: str, message: str = "", notif_id: int = None):
        dark   = ctk.get_appearance_mode() == "Dark"
        accent = theme_colors.accent()
        fg     = "#ffffff" if dark else "#1a1a1a"
        # совпадаем с цветом фона шапки (main window fg_color)
        try:
            bg = self._apply_appearance_mode(self.cget("fg_color"))
        except Exception:
            bg = "#2b2b2b" if dark else "#ebebeb"
        bar = self.top_bar

        # отменить предыдущий таймер
        if self._header_toast_after_id:
            try:
                self.after_cancel(self._header_toast_after_id)
            except Exception:
                pass
            self._header_toast_after_id = None

        # уничтожить старый фрейм
        if self._header_toast_frame is not None:
            try:
                self._header_toast_frame.destroy()
            except Exception:
                pass
            self._header_toast_frame = None

        self._header_toast_notif_id = notif_id

        bar.update_idletasks()
        bell_left  = self._bell_container.winfo_rootx()
        bar_left   = self.top_bar.winfo_rootx()
        bh         = self.top_bar.winfo_height()
        toast_h    = int(max(bh - 4, 28) * 1.15)
        toast_w    = 333
        right_edge = bell_left - bar_left - 4   # правый край тоста — 4px от колокола
        toast_x    = right_edge - toast_w        # финальная позиция (левый край)

        # Обрезаем длинный текст, чтобы поместился в одну строку
        display_msg = message
        if len(display_msg) > 60:
            display_msg = display_msg[:57] + "…"

        outer = tk.Frame(bar, background=accent, bd=0, highlightthickness=0)
        self._header_toast_frame = outer

        # Левая акцентная полоса + фон совпадает с шапкой
        inner = tk.Frame(outer, background=bg, bd=0)
        inner.pack(fill="both", expand=True, padx=(3, 0), pady=(0, 2))

        title_row = tk.Frame(inner, background=bg)
        title_row.pack(fill="x", padx=6, pady=(4, 0))

        title_lbl = tk.Label(
            title_row, text=title, background=bg, foreground=accent,
            font=("Segoe UI", 9, "bold"), anchor="w", cursor="hand2")
        title_lbl.pack(side="left", fill="x", expand=True)

        def on_click(e=None):
            self._hide_header_toast()
            if notif_id is not None:
                self._navigate_to_notif_highlight(notif_id)
            else:
                self._go_to_notifications()

        for w in (outer, inner, title_row, title_lbl):
            w.bind("<Button-1>", on_click)

        tk.Button(
            title_row, text="×", background=bg, foreground=fg,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
            activebackground=accent, activeforeground="#ffffff",
            cursor="hand2", command=self._hide_header_toast,
        ).pack(side="right")

        if display_msg:
            msg_row = tk.Frame(inner, background=bg)
            msg_row.pack(fill="x", padx=6, pady=(1, 2))
            msg_lbl = tk.Label(
                msg_row, text=display_msg, background=bg, foreground=fg,
                font=("Segoe UI", 8), anchor="w", justify="left")
            msg_lbl.pack(side="left", fill="x", expand=True)
            msg_lbl.bind("<Button-1>", on_click)
            msg_row.bind("<Button-1>", on_click)

        pbar_c = accent
        _pw    = [toast_w]
        pbar   = tk.Canvas(inner, height=2, background=pbar_c, highlightthickness=0)
        pbar.pack(fill="x", padx=0, pady=(0, 0))

        # Начинаем с нулевой ширины у правого края (анимация появления справа налево)
        y_pos = max(2, (bh - toast_h) // 2)
        outer.place(x=right_edge, y=y_pos, width=0, height=toast_h)

        SLIDE_STEPS = 10
        SLIDE_MS    = 16
        STEPS       = 50
        STEP_MS     = 100

        def slide_in(step):
            try:
                if not outer.winfo_exists():
                    return
            except Exception:
                return
            t     = step / SLIDE_STEPS
            eased = 1 - (1 - t) ** 3
            cur_w = int(toast_w * eased)
            cur_x = right_edge - cur_w
            outer.place(x=cur_x, width=cur_w)
            if step < SLIDE_STEPS:
                self.after(SLIDE_MS, lambda: slide_in(step + 1))
            else:
                self._header_toast_after_id = self.after(150, lambda: countdown(STEPS))

        def countdown(step):
            try:
                if not outer.winfo_exists():
                    return
            except Exception:
                return
            if step <= 0:
                self._hide_header_toast()
                return
            try:
                cw = pbar.winfo_width()
                if cw > 1:
                    _pw[0] = cw
                fill_w = int(_pw[0] * step / STEPS)
                pbar.delete("all")
                pbar.create_rectangle(0, 0, fill_w, 2, fill=pbar_c, outline="")
                self._header_toast_after_id = self.after(
                    STEP_MS, lambda: countdown(step - 1))
            except Exception:
                pass

        self.after(10, lambda: slide_in(1))

    def _hide_header_toast(self):
        if self._header_toast_after_id:
            try:
                self.after_cancel(self._header_toast_after_id)
            except Exception:
                pass
            self._header_toast_after_id = None
        if self._header_toast_frame is not None:
            try:
                self._header_toast_frame.destroy()
            except Exception:
                pass
            self._header_toast_frame = None
        self._header_toast_notif_id = None

    def _navigate_to_notif_highlight(self, notif_id: int):
        """Переходит на вкладку Уведомления и мигает нужной строкой."""
        self._hamburger_select("🔔 Уведомления")
        # Устанавливаем ПОСЛЕ _hamburger_select: внутри него _mark_all_read() сбрасывает
        # _highlight_notif_id в None, поэтому нужно выставить значение уже после.
        self._highlight_notif_id = notif_id
        self.after(80, lambda: self._blink_notif_row(notif_id, 12))

    def _reposition_toasts(self):
        pass  # toast отображается inline в шапке — repositioning не нужен

    def _check_change_alert(self, query_file: str, new_rows: list, new_cols):
        """Сравнивает новый результат с кэшем; при изменении показывает toast."""
        meta = self._get_query_meta(query_file)
        if not meta.get("alert_on_change"):
            return
        with self._query_results_lock:
            old = self._query_results.get(query_file)
        if old is None:
            return
        new_rows_list = [list(r) for r in new_rows]
        if new_rows_list != old.get("rows", []) or \
                list(new_cols) != old.get("columns", []):
            debounce = self.settings_manager.get_setting("alert_debounce_secs", 10)
            now_mono = time.monotonic()
            key = (query_file, "change")
            if now_mono - self._alert_last_fired.get(key, 0) < debounce:
                return
            self._alert_last_fired[key] = now_mono
            name = self.data_manager.get_query_display_name(query_file)
            old_set = {tuple(r) for r in old.get("rows", [])}
            new_set = {tuple(r) for r in new_rows_list}
            n_added   = len(new_set - old_set)
            n_removed = len(old_set - new_set)
            nid = self._add_notification(name, message="", added=n_added, removed=n_removed)
            self._show_alert_toast("Результат изменился",
                                   f"Запрос «{name}» вернул новые данные",
                                   notif_id=nid)
            self._play_sound("notification_allert.wav", "change_alert")
            self._play_sound("notification_message.wav", "query_result_change")
            self._alert_history.append({
                "ts":         datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "query_name": name,
                "query_file": query_file,
                "type":       "Изменение",
                "detail":     f"+{n_added}, −{n_removed}",
            })
            self._save_alert_history()
            if getattr(self, "_alert_hist_visible", False):
                self._render_alert_history()

    def _check_threshold_alert(self, query_file: str, new_rows: list, new_cols):
        """Проверяет пороговое условие и показывает toast при его выполнении."""
        meta = self._get_query_meta(query_file)
        thr  = meta.get("alert_threshold")
        if not thr or not thr.get("enabled"):
            return
        col_idx = thr.get("column", 0)
        operator = thr.get("operator", ">")
        threshold = thr.get("value", 0)
        if not new_rows or col_idx >= len(new_rows[0]):
            return
        raw = new_rows[0][col_idx]
        try:
            val = float(str(raw))
        except (ValueError, TypeError):
            return
        ops = {
            ">":  val >  threshold,
            "<":  val <  threshold,
            ">=": val >= threshold,
            "<=": val <= threshold,
            "==": val == threshold,
            "!=": val != threshold,
        }
        if ops.get(operator, False):
            debounce = self.settings_manager.get_setting("alert_debounce_secs", 10)
            now_mono = time.monotonic()
            key = (query_file, "threshold")
            if now_mono - self._alert_last_fired.get(key, 0) < debounce:
                return
            self._alert_last_fired[key] = now_mono
            name     = self.data_manager.get_query_display_name(query_file)
            col_name = new_cols[col_idx] if col_idx < len(new_cols) else f"col{col_idx}"
            nid = self._add_notification(
                name,
                message=f"Пороговый алерт: {col_name} = {raw} {operator} {threshold}",
            )
            self._show_alert_toast("Пороговый алерт",
                                   f"«{name}»: {col_name} = {raw} {operator} {threshold}",
                                   notif_id=nid)
            self._play_sound("notification_allert.wav", "threshold_alert")
            self._alert_history.append({
                "ts":         datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "query_name": name,
                "query_file": query_file,
                "type":       "Порог",
                "detail":     f"{col_name} = {raw} {operator} {threshold}",
            })
            self._save_alert_history()
            if getattr(self, "_alert_hist_visible", False):
                self._render_alert_history()

    def _on_panel_signal_fired(self, panel: "DashboardPanel",
                               col_name: str, sig_text: str):
        """Вызывается когда сигнал впервые срабатывает в панели."""
        query_name = panel.get_query_name() or f"Панель {panel.panel_id}"
        ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        message = f"{sig_text} - сработал сигнал {ts}"
        now_mono = time.monotonic()
        if now_mono - self._signal_last_played.get(query_name, 0) >= 10:
            self._signal_last_played[query_name] = now_mono
            self._play_sound("notification_signal.wav", "signal")
        nid = self._add_notification(query_name, message=message)
        self._show_alert_toast("Сигнал", f"«{query_name}»: {sig_text}", notif_id=nid)

    def _update_status_clock(self):
        now = datetime.datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M"))

        # Обновляем индикатор обратного отсчёта на каждой панели
        for panel in getattr(self, "dash_panels", []):
            qn = panel.get_query_name()
            if not qn:
                panel.set_next_refresh_secs(None)
                continue
            pid    = id(panel)
            cached = self._panel_qf_cache.get(pid)
            if cached is None or cached[0] != qn:
                qf = self._find_query_file(qn)
                self._panel_qf_cache[pid] = (qn, qf)
            else:
                qf = cached[1]
            if not qf or qf not in self._query_scheduled_at:
                panel.set_next_refresh_secs(None)
                continue
            iv_min = self._query_intervals_cache.get(qf, 0)
            if iv_min <= 0:
                panel.set_next_refresh_secs(None)
                continue
            elapsed   = (now - self._query_scheduled_at[qf]).total_seconds()
            remaining = iv_min * 60 - elapsed
            panel.set_next_refresh_secs(max(0.0, remaining))

        self._status_clock_after_id = self.after(1000, self._update_status_clock)

    def _update_refresh_bar(self):
        progress, last_time = self._get_fastest_conn_progress()
        self.refresh_progress.set(progress)
        self.refresh_last_time_lbl.configure(text=last_time)
        self._refresh_bar_after_id = self.after(1000, self._update_refresh_bar)

    def _get_fastest_conn_progress(self) -> tuple:
        """Возвращает (прогресс 0–1, строка оставшегося времени) для
        самого быстрого подключения с ненулевым интервалом."""
        now  = datetime.datetime.now()
        best = None  # (interval_min, conn_file)

        if os.path.exists("config"):
            for f in os.listdir("config"):
                if not f.endswith(".json"):
                    continue
                iv = self._get_conn_meta(f).get("update_interval", 0)
                if iv > 0 and (best is None or iv < best[0]):
                    best = (iv, f)

        if best is None:
            return 0.0, "—"

        interval_min, conn_file = best
        total_secs = interval_min * 60
        last = self._conn_last_refresh.get(conn_file)

        if last is None:
            return 1.0, "—"

        elapsed   = (now - last).total_seconds()
        progress  = min(1.0, elapsed / total_secs)   # 0 → только обновилось, 1 → пора снова
        return progress, last.strftime("%H:%M:%S")

    # ── Приборная панель ──────────────────────────────────────────────────────

    def setup_dashboard_tab(self):
        self.frame_dashboard.grid_columnconfigure(0, weight=1)
        self.frame_dashboard.grid_rowconfigure(0, weight=1)
        self._pinned_sash_snapshot: dict = {}
        self._paned_windows:        dict = {}
        saved = self.settings_manager.get_setting("dashboard", {})
        count = saved.get("panel_count", 3)
        self._dashboard_panel_count = max(1, min(6, count))
        self._build_dashboard_panes(self._dashboard_panel_count)
        self.after(200, lambda: self._restore_dashboard_state(saved))

    def _build_dashboard_panes(self, count: int, template: str = None):
        """Создаёт PanedWindow и панели под count фреймов по выбранному шаблону."""
        bg = self._get_theme_bg()
        pw_kw = dict(bg=bg, sashwidth=6, sashrelief="flat", sashpad=0, handlesize=0)

        if template is None:
            template = self.settings_manager.get_setting(
                "dashboard", {}).get("template", "auto")
        _valid = {t[0] for t in DASHBOARD_TEMPLATES}
        if template not in _valid:
            template = "auto"
        self._current_template = template

        self.dash_panels: list[DashboardPanel] = []
        self._paned_windows: dict = {}
        query_names = self._get_query_names()
        try:
            win_color = self.cget("fg_color")
        except Exception:
            win_color = ("gray86", "gray17")

        def _wire(panel: DashboardPanel):
            panel.set_queries(query_names)
            panel.run_btn.configure(command=lambda p=panel: self._run_panel_query(p))
            panel.query_combo.configure(
                command=lambda v, p=panel: self._run_panel_query(p))
            panel.on_signal_fired = (
                lambda cn, st, p=panel: self._on_panel_signal_fired(p, cn, st))
            panel.on_history_click = (
                lambda p, _self=self: _self._show_panel_history(p))
            panel.bind_drag(
                lambda e, p=panel: self._drag_start(e, p),
                self._drag_motion,
                lambda e, p=panel: self._drag_end(e, p),
            )

        def _add(pw, idx):
            p = DashboardPanel(pw, panel_id=idx + 1,
                               on_pin_changed=self._on_panel_pin_changed,
                               fg_color=win_color)
            pw.add(p, stretch="always", minsize=80)
            self.dash_panels.append(p)
            _wire(p)
            return p

        if template == "col":
            # ── один столбец ──────────────────────────────────────────────────
            pw = tk.PanedWindow(self.frame_dashboard, orient="vertical", **pw_kw)
            pw.grid(row=0, column=0, sticky="nsew")
            self.h_paned = pw
            self._paned_windows["main"] = pw
            for i in range(count):
                _add(pw, i)

        elif template == "row":
            # ── одна строка ───────────────────────────────────────────────────
            pw = tk.PanedWindow(self.frame_dashboard, orient="horizontal", **pw_kw)
            pw.grid(row=0, column=0, sticky="nsew")
            self.h_paned = pw
            self._paned_windows["main"] = pw
            for i in range(count):
                _add(pw, i)

        elif template == "1+2" and count >= 2:
            # ── широкий сверху, N снизу ───────────────────────────────────────
            outer = tk.PanedWindow(self.frame_dashboard, orient="vertical", **pw_kw)
            outer.grid(row=0, column=0, sticky="nsew")
            inner = tk.PanedWindow(outer, orient="horizontal", **pw_kw)
            self.h_paned = outer
            self._paned_windows.update(outer=outer, inner=inner)
            _add(outer, 0)                          # панель 0 в верхний слот outer
            outer.add(inner, stretch="always", minsize=80)
            for i in range(1, count):               # панели 1..N-1 в inner
                _add(inner, i)

        elif template == "2+1" and count >= 2:
            # ── N сверху, широкий снизу ───────────────────────────────────────
            outer = tk.PanedWindow(self.frame_dashboard, orient="vertical", **pw_kw)
            outer.grid(row=0, column=0, sticky="nsew")
            inner = tk.PanedWindow(outer, orient="horizontal", **pw_kw)
            self.h_paned = outer
            self._paned_windows.update(outer=outer, inner=inner)
            outer.add(inner, stretch="always", minsize=80)
            for i in range(count - 1):              # панели 0..N-2 в inner
                _add(inner, i)
            _add(outer, count - 1)                  # последняя панель в нижний слот outer

        elif template == "2x2":
            # ── сетка: 2 столбца ──────────────────────────────────────────────
            outer = tk.PanedWindow(self.frame_dashboard, orient="horizontal", **pw_kw)
            outer.grid(row=0, column=0, sticky="nsew")
            left_pw  = tk.PanedWindow(outer, orient="vertical", **pw_kw)
            right_pw = tk.PanedWindow(outer, orient="vertical", **pw_kw)
            self.h_paned = outer
            self._paned_windows.update(h=outer, left=left_pw, right=right_pw)
            outer.add(left_pw,  stretch="always", minsize=120)
            outer.add(right_pw, stretch="always", minsize=120)
            left_c = max(1, count // 2)
            for i in range(count):
                pw = left_pw if i < left_c else right_pw
                _add(pw, i)

        else:
            # ── auto: текущее поведение (2 колонки) ───────────────────────────
            self._current_template = "auto"
            left_count  = max(1, count // 2)
            right_count = count - left_count
            self._left_count = left_count

            h_pw   = tk.PanedWindow(self.frame_dashboard, orient="horizontal", **pw_kw)
            h_pw.grid(row=0, column=0, sticky="nsew")
            left_pw = tk.PanedWindow(h_pw, orient="vertical", **pw_kw)
            self.h_paned = h_pw
            self._paned_windows.update(h=h_pw, left=left_pw)

            if right_count > 0:
                right_pw = tk.PanedWindow(h_pw, orient="vertical", **pw_kw)
                h_pw.add(left_pw,  stretch="always", minsize=120)
                h_pw.add(right_pw, stretch="always", minsize=120)
                self._paned_windows["right"] = right_pw
            else:
                right_pw = None
                h_pw.add(left_pw, stretch="always", minsize=120)

            for i in range(count):
                pw = right_pw if (right_pw and i >= left_count) else left_pw
                _add(pw, i)

        # ── совместимые алиасы ────────────────────────────────────────────────
        self.left_paned  = (self._paned_windows.get("left")
                            or self._paned_windows.get("main")
                            or self.h_paned)
        self.right_paned = self._paned_windows.get("right")

        # ── привязка восстановления заблокированных сашей ─────────────────────
        for pw in self._paned_windows.values():
            pw.bind("<ButtonRelease-1>",
                    lambda e: self.after(20, self._restore_pinned_sashes))

        self.after(50, self._bind_tab_to_canvas)

    def _run_panel_query(self, panel: DashboardPanel):
        query_name = panel.get_query_name()
        if not query_name:
            return
        panel.update_title(query_name)

        query_file = self._find_query_file(query_name)
        if not query_file:
            panel.set_result([], [])
            return

        try:
            with open(os.path.join("queries", query_file), encoding="utf-8") as fh:
                sql = fh.read()
        except Exception as e:
            panel.set_result([], [])
            return

        meta = self._get_query_meta(query_file)
        db_display = meta.get("database", "")
        conn_file = self._find_conn_file(db_display) if db_display else None
        if not conn_file:
            panel.set_result([], [])
            return

        db_name = os.path.splitext(conn_file)[0]

        _timeout = self.settings_manager.get_setting("query_timeout_secs", 300)
        panel.set_loading(True, timeout_secs=_timeout)
        panel.run_btn.configure(state="disabled")

        _cancelled = [False]

        def _on_cancel():
            _cancelled[0] = True

        panel._cancel_fn = _on_cancel

        def worker():
            try:
                rows, cols = self.db_manager.execute_query_with_columns(db_name, sql)
                try:
                    self.after(0, lambda r=rows, c=cols: done(r, c, None))
                except Exception:
                    pass
            except Exception as e:
                try:
                    self.after(0, lambda err=e: done([], [], err))
                except Exception:
                    pass

        def done(rows, cols, err):
            if not self.winfo_exists():
                return
            if _cancelled[0]:
                return
            panel.set_loading(False)
            panel.run_btn.configure(state="normal")
            if err:
                panel.set_result([], [])
                panel.set_row_notice("")
            else:
                self._check_change_alert(query_file, rows, cols)
                self._check_threshold_alert(query_file, rows, cols)
                max_rows = self.settings_manager.get_setting("max_rows", 1000)
                if max_rows and len(rows) > max_rows:
                    rows = rows[:max_rows]
                    panel.set_row_notice(f"Показаны первые {max_rows} строк")
                else:
                    panel.set_row_notice("")
                panel.set_result(rows, cols)
                panel._last_query_file = query_file
                _rows_list = [list(r) for r in rows]
                _cols_list = list(cols)
                with self._query_results_lock:
                    self._query_results[query_file] = {
                        "rows": _rows_list,
                        "columns": _cols_list,
                    }
                self._save_query_cache()
                ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                _hist = self._query_history.setdefault(query_file, [])
                _hist.append({"ts": ts, "rows": _rows_list, "columns": _cols_list})
                if len(_hist) > 10:
                    _hist.pop(0)
                _MAX_TOTAL = 100_000
                while len(_hist) > 1:
                    if sum(len(e["rows"]) for e in _hist) <= _MAX_TOTAL:
                        break
                    _hist.pop(0)
                self._set_query_meta(query_file, last_updated=ts)
                self._update_header_widget(query_file, _rows_list, _cols_list)
                self.refresh_queries_list()

        threading.Thread(target=worker, daemon=True).start()

    # ── drag-and-drop панелей ────────────────────────────────────────────────

    # ── Dashboard: сохранение / восстановление / перестройка ─────────────────

    def _save_dashboard_state(self):
        states = [p.get_state() for p in self.dash_panels]
        sashes = self._get_all_sash_positions()
        self.settings_manager.set_setting("dashboard", {
            "panel_count": self._dashboard_panel_count,
            "template":    getattr(self, "_current_template", "auto"),
            "panels":      states,
            "sashes":      sashes,
        })

    def _restore_dashboard_state(self, saved: dict):
        panels_data = saved.get("panels", [])
        query_names = self._get_query_names()
        for i, panel in enumerate(self.dash_panels):
            panel.set_queries(query_names)
            if i < len(panels_data):
                panel.set_state(panels_data[i])
        sashes = saved.get("sashes", {})
        self._set_all_sash_positions(sashes)
        # Повторное применение после 400 мс: перекрывает Configure-события от зума окна
        self.after(400, lambda s=sashes: self._set_all_sash_positions(s))
        self._rebuild_pinned_snapshot()

    def _rebuild_dashboard(self, count: int, template: str = None):
        states = [p.get_state() for p in self.dash_panels]
        self._dashboard_panel_count = count
        if template is None:
            template = getattr(self, "_current_template", "auto")
        self.h_paned.destroy()
        self.dash_panels = []
        self._pinned_sash_snapshot = {}
        self._paned_windows = {}
        self._build_dashboard_panes(count, template)
        query_names = self._get_query_names()
        for i, panel in enumerate(self.dash_panels):
            panel.set_queries(query_names)
            if i < len(states):
                panel.set_state(states[i])
        self._save_dashboard_state()

    # ── Dashboard: блокировка саша ────────────────────────────────────────────

    def _on_panel_pin_changed(self, panel: DashboardPanel):
        self._rebuild_pinned_snapshot()
        self._save_dashboard_state()

    def _rebuild_pinned_snapshot(self):
        """Блокирует все саши, если хотя бы одна панель закреплена."""
        self._pinned_sash_snapshot = {}
        if not any(p.is_pinned for p in self.dash_panels):
            return
        self._pinned_sash_snapshot = self._get_all_sash_positions()

    def _restore_pinned_sashes(self):
        if not self._pinned_sash_snapshot:
            return
        self._set_all_sash_positions(self._pinned_sash_snapshot)

    def _get_all_sash_positions(self) -> dict:
        result = {}
        for key, pw in getattr(self, "_paned_windows", {}).items():
            n = max(0, len(pw.panes()) - 1)
            try:
                orient = str(pw.cget("orient"))
                w = pw.winfo_width()
                h = pw.winfo_height()
                fracs = []
                for i in range(n):
                    x, y = pw.sash_coord(i)
                    if orient == "horizontal" and w > 1:
                        fracs.append(round(x / w, 4))
                    elif orient == "vertical" and h > 1:
                        fracs.append(round(y / h, 4))
                    else:
                        fracs.append(0.5)
                result[key] = fracs
            except Exception:
                result[key] = []
        return result

    def _set_all_sash_positions(self, positions: dict):
        self.update_idletasks()
        for key, pw in getattr(self, "_paned_windows", {}).items():
            if key not in positions or not positions[key]:
                continue
            fracs = positions[key]
            # Старый формат [[x,y],...] — пропустить
            if fracs and isinstance(fracs[0], (list, tuple)):
                continue
            try:
                orient = str(pw.cget("orient"))
                w = pw.winfo_width()
                h = pw.winfo_height()
            except Exception:
                continue
            for i, frac in enumerate(fracs):
                try:
                    if orient == "horizontal" and w > 1:
                        pw.sash_place(i, int(frac * w), 0)
                    elif orient == "vertical" and h > 1:
                        pw.sash_place(i, 0, int(frac * h))
                except Exception:
                    pass

    # ── drag-and-drop панелей ────────────────────────────────────────────────

    def _drag_start(self, event, panel: DashboardPanel):
        if panel.is_pinned:
            return
        self._drag_source = panel
        panel.highlight(True)
        self._drag_ghost = tk.Toplevel(self)
        self._drag_ghost.overrideredirect(True)
        self._drag_ghost.attributes("-alpha", 0.65)
        self._drag_ghost.attributes("-topmost", True)
        lbl = ctk.CTkLabel(self._drag_ghost,
                           text=f"Панель {panel.panel_id}", width=130, height=36)
        lbl.pack()
        self._drag_ghost.geometry(f"130x36+{event.x_root - 65}+{event.y_root - 18}")

    def _drag_motion(self, event):
        if self._drag_ghost:
            self._drag_ghost.geometry(f"130x36+{event.x_root - 65}+{event.y_root - 18}")

        new_target: Optional[DashboardPanel] = None
        for p in self.dash_panels:
            if p is self._drag_source:
                continue
            x1, y1 = p.winfo_rootx(), p.winfo_rooty()
            x2, y2 = x1 + p.winfo_width(), y1 + p.winfo_height()
            if x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2:
                new_target = p
                break

        if new_target is not self._drag_drop_target:
            if self._drag_drop_target:
                self._drag_drop_target.highlight(False)
            self._drag_drop_target = new_target
            if new_target and not new_target.is_pinned:
                new_target.highlight(True)

    def _drag_end(self, event, source: DashboardPanel):
        if self._drag_ghost:
            self._drag_ghost.destroy()
            self._drag_ghost = None

        if self._drag_drop_target:
            self._drag_drop_target.highlight(False)
            self._drag_drop_target = None

        if source:
            source.highlight(False)

        target: Optional[DashboardPanel] = None
        for p in self.dash_panels:
            if p is source:
                continue
            x1, y1 = p.winfo_rootx(), p.winfo_rooty()
            x2, y2 = x1 + p.winfo_width(), y1 + p.winfo_height()
            if x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2:
                target = p
                break

        if target and not target.is_pinned:
            s_state = source.get_state()
            t_state = target.get_state()
            source.set_state(t_state)
            target.set_state(s_state)
            self._save_dashboard_state()

        self._drag_source = None

    # ── Подключения ───────────────────────────────────────────────────────────

    _C_HEADERS  = ("●", "Название", "Тип БД", "Хост", "Порт",
                   "Имя БД", "Пользователь", "Пароль", "Кодировка",
                   "Обновлять панель каждые", "", "")
    # weight=0 → фиксированная колонка (статус/кнопки), >0 → пропорциональная
    _C_WEIGHTS  = (0,  3,  2,  3,  0,  3,  2,  1,  1,  2,  0,  0)
    _C_MIN_W    = (28, 100, 70, 90, 50, 90, 80, 60, 60, 90, 90, 90)

    def setup_connections_tab(self):
        self.frame_connections.grid_columnconfigure(0, weight=1)
        self.frame_connections.grid_rowconfigure(1, weight=1)

        # ── тулбар (row 0, аналог Логи) ───────────────────────────────────────
        conn_toolbar = ctk.CTkFrame(self.frame_connections, fg_color="transparent")
        conn_toolbar.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")

        self._conn_search_var = ctk.StringVar()
        self._conn_search_var.trace_add("write", lambda *_: self._on_conn_search_changed())

        self._conn_clear_btn = ctk.CTkButton(
            conn_toolbar, text="✕", width=24, height=28,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=lambda: self._conn_search_var.set(""))
        self._conn_clear_btn.pack(side="right", padx=(0, 2))
        self._conn_clear_btn.pack_forget()

        ctk.CTkEntry(conn_toolbar, textvariable=self._conn_search_var,
                     placeholder_text="Поиск...",
                     width=190, height=28).pack(side="right")

        ctk.CTkLabel(conn_toolbar, text="🔍",
                     font=ctk.CTkFont(size=20)).pack(side="right", padx=(16, 6), anchor="center")

        self._connections_scroll = ctk.CTkScrollableFrame(
            self.frame_connections, fg_color="transparent")
        self._connections_scroll.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self._connections_scroll.grid_columnconfigure(0, weight=1)

        self.refresh_connections_list()

    def refresh_connections_list(self):
        for w in self._connections_scroll.winfo_children():
            w.destroy()

        sort_col, sort_rev = self._conn_sort
        bold   = ctk.CTkFont(weight="bold")
        HDR_BG = ("gray78", "gray25")

        # ── предварительное чтение файлов ────────────────────────────────────
        _files = None        # None = папка не существует
        _read_error = None
        if os.path.exists("config"):
            try:
                _files = [f for f in os.listdir("config") if f.endswith(".json")]
            except Exception as e:
                _read_error = e
                self.log_manager.add_log(f"Ошибка чтения config: {e}", "ERROR")
        else:
            self.log_manager.add_log("Папка config не найдена", "ERROR")

        # ── фильтрация по поиску ──────────────────────────────────────────────
        _conn_sv = getattr(self, "_conn_search_var", None)
        _q = _conn_sv.get().strip().lower() if _conn_sv else ""
        if _q and _files:
            _files = [f for f in _files
                      if _q in self.data_manager.get_db_display_name(f).lower()]

        _conn_has_items = bool(_files)

        if _conn_has_items:
            # ── единый фрейм таблицы: заголовок + строки в одной сетке ──────
            tbl = ctk.CTkFrame(self._connections_scroll, fg_color="transparent")
            tbl.grid(row=0, column=0, sticky="ew")
            self._apply_col_config(tbl, self._C_WEIGHTS, self._C_MIN_W)

            # ── заголовок (строка 0 в tbl) ────────────────────────────────────
            for i, h in enumerate(self._C_HEADERS):
                if not h:
                    ctk.CTkLabel(tbl, text="", fg_color="transparent").grid(
                        row=0, column=i, padx=6, pady=5, sticky="nsew")
                    continue
                if self._C_WEIGHTS[i] == 0:
                    is_text = any(c.isalpha() for c in h)
                    lbl = ctk.CTkLabel(
                        tbl, text=h, fg_color=HDR_BG,
                        font=bold if is_text else None,
                        anchor="w" if is_text else "center")
                    lbl.grid(row=0, column=i, padx=6, pady=5, sticky="nsew")
                    continue
                arrow = (" ▲" if not sort_rev else " ▼") if sort_col == i else ""
                lbl = ctk.CTkLabel(tbl, text=h + arrow, font=bold,
                                   anchor="w", cursor="hand2", fg_color=HDR_BG)
                lbl.grid(row=0, column=i, padx=6, pady=5, sticky="nsew")
                lbl.bind("<Button-1>", lambda e, c=i: self._conn_sort_click(c))

            # ── строки данных ─────────────────────────────────────────────────
            for row_idx, f in enumerate(self._sorted_conn_files(_files)):
                r = row_idx + 1
                display_name = self.data_manager.get_db_display_name(f)
                try:
                    with open(os.path.join("config", f),
                              encoding="utf-8") as fh:
                        cfg = json.load(fh)
                except Exception:
                    cfg = {}
                pwd    = cfg.get("password", "")
                masked = "*" * len(pwd) if pwd else "—"
                bg = ("gray88", "gray20") if row_idx % 2 == 0 \
                    else ("gray83", "gray17")

                meta_c   = self._get_conn_meta(f)
                interval = meta_c.get("update_interval", 0)
                istr     = f"{interval} мин." if interval else "—"

                # ── индикатор статуса (col 0) ─────────────────────────────────
                status = self._conn_statuses.get(f)
                if status is True:
                    dot_color = ("#22C55E", "#16A34A")
                elif status is False:
                    dot_color = ("#EF4444", "#DC2626")
                else:
                    dot_color = ("gray60", "gray50")
                ctk.CTkLabel(tbl, text="●", text_color=dot_color,
                             fg_color=bg).grid(
                    row=r, column=0, padx=6, pady=3, sticky="nsew")

                if status is None and f not in self._conn_status_testing:
                    self._conn_status_testing.add(f)
                    threading.Thread(
                        target=self._bg_test_conn,
                        args=(f, dict(cfg)), daemon=True).start()

                # ── данные (col 1-9) ──────────────────────────────────────────
                for ci, val in enumerate((
                    display_name,
                    cfg.get("database_type", "—"),
                    cfg.get("host", "—"),
                    str(cfg.get("port", "—")),
                    cfg.get("database_name", "—"),
                    cfg.get("username", "—"),
                    masked,
                    cfg.get("charset", "—"),
                    istr,
                ), start=1):
                    ctk.CTkLabel(tbl, text=val, anchor="w",
                                 fg_color=bg).grid(
                        row=r, column=ci, padx=6, pady=3, sticky="nsew")

                # ── кнопки (col 10, 11) ───────────────────────────────────────
                ctk.CTkButton(
                    tbl, text="Изменить",
                    width=self._C_MIN_W[10], height=26,
                    command=lambda n=display_name: self._edit_db_by_name(n)
                ).grid(row=r, column=10, padx=6, pady=3)

                ctk.CTkButton(
                    tbl, text="Удалить",
                    width=self._C_MIN_W[11], height=26,
                    fg_color=("#E53935", "#C62828"),
                    hover_color=("#C62828", "#B71C1C"),
                    command=lambda n=display_name: self._delete_db_by_name(n)
                ).grid(row=r, column=11, padx=6, pady=3)

                # ── контекстное меню на строке ────────────────────────────────
                for child in tbl.grid_slaves(row=r):
                    child.bind(
                        "<Button-3>",
                        lambda e, n=display_name:
                            self._show_conn_ctx_menu(e, n),
                        add="+")

            # ── кнопка "Добавить подключение" после таблицы ───────────────────
            ctk.CTkButton(
                self._connections_scroll, text="+ Добавить подключение",
                command=self.add_new_db, height=32, anchor="w"
            ).grid(row=1, column=0, padx=6, pady=(6, 4), sticky="w")

        else:
            # ── пустое состояние или ошибка ───────────────────────────────────
            if _files is None:
                self._build_empty_state(
                    self._connections_scroll, 0,
                    "⚠️", "Папка config не найдена",
                    "Создайте папку config рядом с программой",
                    "+ Добавить подключение", self.add_new_db)
            elif _read_error is not None:
                ctk.CTkLabel(self._connections_scroll,
                             text=f"Ошибка: {_read_error}").grid(
                    row=0, column=0, padx=10, pady=5)
            else:
                self._build_empty_state(
                    self._connections_scroll, 0,
                    "🔌", "Нет подключений",
                    "Добавьте первое подключение к базе данных",
                    "+ Добавить подключение", self.add_new_db)

    # ── метаданные подключений ────────────────────────────────────────────────

    def _get_conn_meta(self, filename: str) -> dict:
        return dict(self.settings_manager.get_setting(
            "connections_meta", {}).get(filename, {}))

    def _set_conn_meta(self, filename: str, **kwargs):
        all_meta = dict(self.settings_manager.get_setting("connections_meta", {}))
        meta = dict(all_meta.get(filename, {}))
        meta.update(kwargs)
        all_meta[filename] = meta
        self.settings_manager.set_setting("connections_meta", all_meta)

    def _del_conn_meta(self, filename: str):
        all_meta = dict(self.settings_manager.get_setting("connections_meta", {}))
        all_meta.pop(filename, None)
        self.settings_manager.set_setting("connections_meta", all_meta)

    # ── редактирование / добавление подключения ───────────────────────────────

    def _edit_db_by_name(self, name: str):
        self._selected_connection_name = name
        filename = self.get_filename_by_display_name(name, "config", ".json")
        if not filename:
            messagebox.showwarning("Предупреждение", "Файл подключения не найден")
            return

        config_path = os.path.join("config", filename)
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить конфигурацию:\n{e}")
            return

        meta = self._get_conn_meta(filename)
        dialog = DatabaseConnectionDialog(
            self, initial_name=name, initial_config=config,
            initial_interval=meta.get("update_interval", 0),
            db_manager=self.db_manager,
            settings_manager=self.settings_manager,
            log_manager=self.log_manager)
        self.wait_window(dialog)
        if not dialog.result:
            return

        new_name, new_config, new_interval = dialog.result

        if new_name != name:
            new_filename = f"{new_name}.json"
            new_path = os.path.join("config", new_filename)
            if os.path.exists(new_path):
                messagebox.showerror("Ошибка", f"Подключение '{new_name}' уже существует")
                return
            os.remove(config_path)
            self.data_manager.delete_db_name(filename)
            self._del_conn_meta(filename)
        else:
            new_filename = filename
            new_path     = config_path

        with open(new_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=4)
        self.data_manager.set_db_display_name(new_filename, new_name)
        self._set_conn_meta(new_filename, update_interval=new_interval)

        if new_filename != filename:
            self._conn_statuses.pop(filename, None)
            self._conn_status_testing.discard(filename)
        else:
            # конфиг мог измениться — сбрасываем статус для повторной проверки
            self._conn_statuses.pop(new_filename, None)
            self._conn_status_testing.discard(new_filename)
        self._selected_connection_name = new_name
        self.refresh_connections_list()
        self.log_manager.add_log(f"Подключение изменено: {name} → {new_name}")
        self._restart_auto_timers()

    def add_new_db(self):
        dialog = DatabaseConnectionDialog(self, db_manager=self.db_manager,
                                          settings_manager=self.settings_manager,
                                          log_manager=self.log_manager)
        self.wait_window(dialog)
        if dialog.result:
            name, config, interval = dialog.result
            if self.data_manager.add_new_db(name, config):
                filename = f"{name}.json"
                self.data_manager.set_db_display_name(filename, name)
                self._set_conn_meta(filename, update_interval=interval)
                self.refresh_connections_list()
                self.log_manager.add_log(f"Добавлено подключение: {name}")
                messagebox.showinfo("Успех", f"Подключение '{name}' добавлено")
                self._restart_auto_timers()
            else:
                messagebox.showerror("Ошибка", f"'{name}' уже существует")

    def _delete_db_by_name(self, name: str):
        fname = self.get_filename_by_display_name(name, "config", ".json")
        if not fname:
            return
        if messagebox.askyesno("Подтверждение", f"Удалить '{name}'?"):
            if self.data_manager.delete_db(fname):
                self._del_conn_meta(fname)
                self._conn_statuses.pop(fname, None)
                self._conn_status_testing.discard(fname)
                if self._selected_connection_name == name:
                    self._selected_connection_name = None
                self.refresh_connections_list()
                self.log_manager.add_log(f"Удалено подключение: {name}")
                self._restart_auto_timers()
            else:
                messagebox.showerror("Ошибка", f"Не удалось удалить '{name}'")

    # ── Запросы ───────────────────────────────────────────────────────────────

    _Q_HEADERS  = ("Название", "SQL-запрос", "База данных",
                   "Последнее обновление", "Обновлять каждые", "", "")
    _Q_WEIGHTS  = (2,  4,  2,  2,  1,  0,  0)
    _Q_MIN_W    = (110, 140, 100, 120, 90, 90, 90)

    def _show_query_stats_dialog(self):
        """Диалог статистики выполнения запросов (топ-10 по среднему времени)."""
        dlg = ctk.CTkToplevel(self)
        dlg.withdraw()
        dlg.title("Статистика запросов")
        dlg.resizable(True, True)
        dlg.minsize(700, 380)
        dlg.transient(self)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

        # ── заголовок ─────────────────────────────────────────────────────────
        hdr_row = ctk.CTkFrame(dlg, fg_color="transparent")
        hdr_row.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(hdr_row,
                     text="Статистика выполнения запросов",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkLabel(hdr_row, text="• нажмите на строку для детализации",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray55")).pack(side="left", padx=(12, 0))
        ctk.CTkButton(hdr_row, text="Очистить", width=90, height=28,
                      fg_color=("gray55", "gray35"), hover_color=("gray45", "gray25"),
                      command=lambda: _refresh(clear=True)).pack(side="right")
        ctk.CTkButton(hdr_row, text="Экспорт CSV", width=110, height=28,
                      command=lambda: _export_csv()).pack(side="right", padx=(0, 8))

        # ── таблица ───────────────────────────────────────────────────────────
        HDRS = ("Запрос", "Запусков", "Ошибок", "Ср. время (мс)",
                "Макс. (мс)", "Ср. строк", "Последний запуск")
        WGTS = (1, 0, 0, 0, 0, 0, 0)
        MINS = (180, 70, 60, 110, 90, 80, 140)

        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        scroll.grid_columnconfigure(0, weight=1)

        def _show_detail(query_file: str, query_name: str):
            detail = ctk.CTkToplevel(dlg)
            detail.withdraw()
            detail.title(f"Детализация: {query_name}")
            detail.resizable(True, True)
            detail.minsize(520, 340)
            detail.transient(dlg)
            detail.protocol("WM_DELETE_WINDOW", detail.destroy)

            ctk.CTkLabel(
                detail,
                text=f"Последние запуски: {query_name}",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(fill="x", padx=16, pady=(14, 2))
            ctk.CTkLabel(
                detail,
                text=f"файл: {query_file}",
                font=ctk.CTkFont(size=11),
                text_color=("gray50", "gray55"),
                anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 6))

            D_HDRS = ("#", "Время запуска", "Длительность (мс)", "Строк", "Статус")
            D_WGTS = (0, 1, 0, 0, 0)
            D_MINS = (40, 160, 130, 70, 90)

            dscroll = ctk.CTkScrollableFrame(detail, fg_color="transparent")
            dscroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
            dscroll.grid_columnconfigure(0, weight=1)

            recent = self.stats_manager.get_recent(query_file, limit=20)
            dtbl = ctk.CTkFrame(dscroll, fg_color="transparent")
            dtbl.grid(row=0, column=0, sticky="ew")
            dscroll.grid_columnconfigure(0, weight=1)

            for i, (h, wt, mw) in enumerate(zip(D_HDRS, D_WGTS, D_MINS)):
                dtbl.grid_columnconfigure(i, weight=wt, minsize=mw)
                ctk.CTkLabel(
                    dtbl, text=h, anchor="w",
                    font=ctk.CTkFont(weight="bold"),
                    fg_color=("gray78", "gray25"),
                ).grid(row=0, column=i, padx=6, pady=4, sticky="nsew")

            if not recent:
                ctk.CTkLabel(dscroll, text="Нет данных",
                             text_color=("gray50", "gray60")).grid(
                    row=1, column=0, pady=20)
            else:
                dsm = ctk.CTkFont(size=12)
                for ri, r in enumerate(recent):
                    bg = ("gray88", "gray20") if ri % 2 == 0 else ("gray83", "gray17")
                    is_err = bool(r["is_error"])
                    dvals = [
                        str(ri + 1),
                        r["ts"],
                        f'{r["duration_ms"]:.0f}',
                        str(r["row_count"]),
                        "❌ Ошибка" if is_err else "✅ OK",
                    ]
                    for ci, val in enumerate(dvals):
                        lbl = ctk.CTkLabel(dtbl, text=val, anchor="w",
                                           fg_color=bg, font=dsm)
                        if ci == 4:
                            lbl.configure(
                                text_color=("#DC2626", "#F87171") if is_err
                                else ("#16A34A", "#4ADE80"))
                        lbl.grid(row=ri + 1, column=ci, padx=6, pady=2, sticky="nsew")

            def _dcenter():
                detail.update_idletasks()
                pw = dlg.winfo_width(); ph = dlg.winfo_height()
                px = dlg.winfo_rootx(); py = dlg.winfo_rooty()
                w  = detail.winfo_reqwidth()
                h  = detail.winfo_reqheight()
                detail.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
                detail.deiconify()
                detail.lift()

            detail.after(60, _dcenter)

        def _export_csv():
            import csv
            path = filedialog.asksaveasfilename(
                parent=dlg,
                defaultextension=".csv",
                filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
                title="Сохранить статистику как CSV",
            )
            if not path:
                return
            rows = self.stats_manager.get_summary(limit=50)
            dm = self.data_manager
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(HDRS)
                    for row in rows:
                        qname = dm.get_query_display_name(row["query_file"]) or row["query_file"]
                        writer.writerow([
                            qname,
                            row["total_runs"],
                            row["error_count"],
                            f'{row["avg_ms"]:.0f}',
                            f'{row["max_ms"]:.0f}',
                            f'{row["avg_rows"]:.0f}',
                            row["last_run"] or "",
                        ])
            except OSError as e:
                from dialogs import messagebox as _mb
                _mb.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}", parent=dlg)

        def _refresh(clear: bool = False):
            if clear:
                self.stats_manager.clear()
            for w in scroll.winfo_children():
                w.destroy()
            rows = self.stats_manager.get_summary(limit=50)
            tbl = ctk.CTkFrame(scroll, fg_color="transparent")
            tbl.grid(row=0, column=0, sticky="ew")
            scroll.grid_columnconfigure(0, weight=1)
            for i, (h, wt, mw) in enumerate(zip(HDRS, WGTS, MINS)):
                tbl.grid_columnconfigure(i, weight=wt, minsize=mw)
                ctk.CTkLabel(
                    tbl, text=h, anchor="w",
                    font=ctk.CTkFont(weight="bold"),
                    fg_color=("gray78", "gray25"),
                ).grid(row=0, column=i, padx=6, pady=4, sticky="nsew")
            if not rows:
                ctk.CTkLabel(scroll, text="Нет данных",
                             text_color=("gray50", "gray60")).grid(
                    row=1, column=0, pady=20)
                return
            dm = self.data_manager
            sm = ctk.CTkFont(size=12)
            for ri, row in enumerate(rows):
                bg = ("gray88", "gray20") if ri % 2 == 0 else ("gray83", "gray17")
                bg_hover = ("gray80", "gray28")
                qname = dm.get_query_display_name(row["query_file"]) or row["query_file"]
                vals = [
                    qname,
                    str(row["total_runs"]),
                    str(row["error_count"]),
                    f'{row["avg_ms"]:.0f}',
                    f'{row["max_ms"]:.0f}',
                    f'{row["avg_rows"]:.0f}',
                    row["last_run"] or "—",
                ]
                row_lbls = []
                for ci, val in enumerate(vals):
                    lbl = ctk.CTkLabel(tbl, text=val, anchor="w",
                                       fg_color=bg, font=sm, cursor="hand2")
                    lbl.grid(row=ri + 1, column=ci, padx=6, pady=2, sticky="nsew")
                    row_lbls.append(lbl)
                _qf, _qn = row["query_file"], qname
                for lbl in row_lbls:
                    lbl.bind("<Button-1>",
                             lambda e, f=_qf, n=_qn: _show_detail(f, n))
                    lbl.bind("<Enter>",
                             lambda e, ls=row_lbls: [l.configure(fg_color=bg_hover) for l in ls])
                    lbl.bind("<Leave>",
                             lambda e, ls=row_lbls, c=bg: [l.configure(fg_color=c) for l in ls])

        _refresh()

        def _center():
            dlg.update_idletasks()
            pw = self.winfo_width(); ph = self.winfo_height()
            px = self.winfo_rootx(); py = self.winfo_rooty()
            w  = dlg.winfo_reqwidth()
            h  = dlg.winfo_reqheight()
            dlg.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
            dlg.deiconify()
            dlg.grab_set()
            dlg.lift()

        dlg.after(60, _center)

    def setup_queries_tab(self):
        self.frame_queries.grid_columnconfigure(0, weight=1)
        self.frame_queries.grid_rowconfigure(1, weight=1)

        # ── тулбар (row 0, аналог Логи) ───────────────────────────────────────
        query_toolbar = ctk.CTkFrame(self.frame_queries, fg_color="transparent")
        query_toolbar.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")

        self._query_search_var = ctk.StringVar()
        self._query_search_var.trace_add("write", lambda *_: self._on_query_search_changed())

        self._query_clear_btn = ctk.CTkButton(
            query_toolbar, text="✕", width=24, height=28,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=lambda: self._query_search_var.set(""))
        self._query_clear_btn.pack(side="right", padx=(0, 2))
        self._query_clear_btn.pack_forget()

        ctk.CTkEntry(query_toolbar, textvariable=self._query_search_var,
                     placeholder_text="Поиск...",
                     width=190, height=28).pack(side="right")

        ctk.CTkLabel(query_toolbar, text="🔍",
                     font=ctk.CTkFont(size=20)).pack(side="right", padx=(16, 6), anchor="center")

        ctk.CTkButton(
            query_toolbar, text="📊 Статистика",
            command=self._show_query_stats_dialog,
            width=120, height=28,
        ).pack(side="left", padx=(0, 8))

        self._queries_scroll = ctk.CTkScrollableFrame(
            self.frame_queries, fg_color="transparent")
        self._queries_scroll.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self._queries_scroll.grid_columnconfigure(0, weight=1)

        self.refresh_queries_list()

    def refresh_queries_list(self):
        for w in self._queries_scroll.winfo_children():
            w.destroy()

        sort_col, sort_rev = self._query_sort
        bold   = ctk.CTkFont(weight="bold")
        HDR_BG = ("gray78", "gray25")

        # ── предварительное чтение файлов ────────────────────────────────────
        _files = None        # None = папка не существует
        _read_error = None
        if os.path.exists("queries"):
            try:
                _files = [f for f in os.listdir("queries") if f.endswith(".sql")]
            except Exception as e:
                _read_error = e
                self.log_manager.add_log(f"Ошибка чтения queries: {e}", "ERROR")

        # ── фильтрация по поиску ──────────────────────────────────────────────
        _qsearch = getattr(self, "_query_search_var", None)
        _qq = _qsearch.get().strip().lower() if _qsearch else ""
        if _qq and _files:
            _files = [f for f in _files
                      if _qq in self.data_manager.get_query_display_name(f).lower()]

        _query_has_items = bool(_files)

        if _query_has_items:
            # ── единый фрейм таблицы: заголовок + строки в одной сетке ──────
            tbl = ctk.CTkFrame(self._queries_scroll, fg_color="transparent")
            tbl.grid(row=0, column=0, sticky="ew")
            self._apply_col_config(tbl, self._Q_WEIGHTS, self._Q_MIN_W)

            # ── заголовок (строка 0 в tbl) ────────────────────────────────────
            for i, h in enumerate(self._Q_HEADERS):
                if self._Q_WEIGHTS[i] == 0:
                    ctk.CTkLabel(tbl, text="", fg_color="transparent").grid(
                        row=0, column=i, padx=6, pady=5, sticky="nsew")
                    continue
                arrow = (" ▲" if not sort_rev else " ▼") if sort_col == i else ""
                lbl = ctk.CTkLabel(tbl, text=h + arrow, font=bold,
                                   anchor="w", cursor="hand2", fg_color=HDR_BG)
                lbl.grid(row=0, column=i, padx=6, pady=5, sticky="nsew")
                lbl.bind("<Button-1>", lambda e, c=i: self._query_sort_click(c))

            # ── строки данных ─────────────────────────────────────────────────
            for row_idx, f in enumerate(self._sorted_query_files(_files)):
                r = row_idx + 1
                display_name = self.data_manager.get_query_display_name(f)
                try:
                    with open(os.path.join("queries", f),
                              encoding="utf-8") as fh:
                        raw = fh.read().replace("\n", " ").strip()
                    sql_preview = raw[:30] + ("..." if len(raw) > 30 else "")
                except Exception:
                    sql_preview = "—"

                meta     = self._get_query_meta(f)
                db_name  = meta.get("database", "—") or "—"
                last_upd = meta.get("last_updated", "—") or "—"
                interval = meta.get("update_interval", 0)
                cron_m   = meta.get("cron_schedule") or {}
                if cron_m.get("enabled"):
                    _days_map = {0:"Пн",1:"Вт",2:"Ср",3:"Чт",4:"Пт",5:"Сб",6:"Вс"}
                    _days = cron_m.get("days", [])
                    _dstr = ",".join(_days_map[d] for d in _days) if _days else "каждый день"
                    istr = f"⏰ {cron_m.get('time','?')} ({_dstr})"
                elif interval:
                    istr = f"{interval} мин."
                else:
                    istr = "—"
                bg = ("gray88", "gray20") if row_idx % 2 == 0 \
                    else ("gray83", "gray17")

                # ── данные (col 0-4) ──────────────────────────────────────────
                for ci, val in enumerate(
                        (display_name, sql_preview, db_name, last_upd, istr)):
                    ctk.CTkLabel(tbl, text=val, anchor="w",
                                 fg_color=bg).grid(
                        row=r, column=ci, padx=6, pady=3, sticky="nsew")

                # ── кнопки (col 5, 6) ─────────────────────────────────────────
                ctk.CTkButton(
                    tbl, text="Изменить",
                    width=self._Q_MIN_W[5], height=26,
                    command=lambda n=display_name: self._edit_query_by_name(n)
                ).grid(row=r, column=5, padx=6, pady=3)

                ctk.CTkButton(
                    tbl, text="Удалить",
                    width=self._Q_MIN_W[6], height=26,
                    fg_color=("#E53935", "#C62828"),
                    hover_color=("#C62828", "#B71C1C"),
                    command=lambda n=display_name: self._delete_query_by_name(n)
                ).grid(row=r, column=6, padx=6, pady=3)

                # ── контекстное меню на строке ────────────────────────────────
                for child in tbl.grid_slaves(row=r):
                    child.bind(
                        "<Button-3>",
                        lambda e, n=display_name:
                            self._show_query_ctx_menu(e, n),
                        add="+")

            # ── кнопка "Добавить" после таблицы ──────────────────────────────
            ctk.CTkButton(
                self._queries_scroll, text="+ Добавить запрос",
                command=self.add_new_query, height=32, anchor="w"
            ).grid(row=1, column=0, padx=6, pady=(6, 4), sticky="w")

        else:
            # ── пустое состояние или ошибка ───────────────────────────────────
            if _files is None:
                self._build_empty_state(
                    self._queries_scroll, 0,
                    "⚠️", "Папка queries не найдена",
                    "Создайте папку queries рядом с программой",
                    "+ Добавить запрос", self.add_new_query)
            elif _read_error is not None:
                ctk.CTkLabel(self._queries_scroll,
                             text=f"Ошибка: {_read_error}").grid(
                    row=0, column=0, padx=10, pady=5)
            else:
                self._build_empty_state(
                    self._queries_scroll, 0,
                    "📝", "Нет запросов",
                    "Добавьте первый SQL-запрос для дашборда",
                    "+ Добавить запрос", self.add_new_query)

        self._refresh_widgets_table()

    # ── метаданные запросов ───────────────────────────────────────────────────

    def _get_query_meta(self, filename: str) -> dict:
        return dict(self.settings_manager.get_setting(
            "queries_meta", {}).get(filename, {}))

    def _set_query_meta(self, filename: str, **kwargs):
        all_meta = dict(self.settings_manager.get_setting("queries_meta", {}))
        meta = dict(all_meta.get(filename, {}))
        meta.update(kwargs)
        all_meta[filename] = meta
        self.settings_manager.set_setting("queries_meta", all_meta)

    def _del_query_meta(self, filename: str):
        all_meta = dict(self.settings_manager.get_setting("queries_meta", {}))
        all_meta.pop(filename, None)
        self.settings_manager.set_setting("queries_meta", all_meta)

    # ── редактирование запроса ────────────────────────────────────────────────

    def _edit_query_by_name(self, name: str):
        self._selected_query_name = name
        filename = self.get_filename_by_display_name(name, "queries", ".sql")
        if not filename:
            messagebox.showwarning("Предупреждение", "Файл запроса не найден")
            return

        query_path = os.path.join("queries", filename)
        try:
            with open(query_path, encoding="utf-8") as f:
                sql = f.read()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить запрос:\n{e}")
            return

        meta     = self._get_query_meta(filename)
        db_names = self._get_db_names()
        dialog   = QueryDialog(
            self, db_names,
            initial_name=name,
            initial_db=meta.get("database", ""),
            initial_sql=sql,
            initial_interval=meta.get("update_interval", 0),
            initial_alert_on_change=meta.get("alert_on_change", False),
            initial_alert_threshold=meta.get("alert_threshold"),
            initial_is_widget=meta.get("is_widget", False),
            initial_cron_schedule=meta.get("cron_schedule"),
            db_manager=self.db_manager,
            db_name_map=self._get_db_name_map(),
            settings_manager=self.settings_manager,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return

        new_name, new_db, new_sql, new_interval, new_alert_on_change, \
            new_alert_threshold, new_is_widget, new_cron = dialog.result

        if new_name != name:
            new_filename = f"{new_name}.sql"
            new_path = os.path.join("queries", new_filename)
            if os.path.exists(new_path):
                messagebox.showerror("Ошибка", f"Запрос '{new_name}' уже существует")
                return
            os.remove(query_path)
            self.data_manager.delete_query_name(filename)
            old_meta = self._get_query_meta(filename)
            self._del_query_meta(filename)
        else:
            new_filename = filename
            new_path     = query_path
            old_meta     = meta

        with open(new_path, "w", encoding="utf-8") as f:
            f.write(new_sql)
        self.data_manager.set_query_display_name(new_filename, new_name)
        self._set_query_meta(new_filename,
                             database=new_db,
                             update_interval=new_interval,
                             cron_schedule=new_cron,
                             last_updated=old_meta.get("last_updated", "—"),
                             alert_on_change=new_alert_on_change,
                             alert_threshold=new_alert_threshold,
                             is_widget=new_is_widget,
                             widget_viz_config=old_meta.get("widget_viz_config"))

        self._selected_query_name = new_name
        self.refresh_queries_list()
        self._refresh_panel_query_lists()
        self._refresh_header_widgets()
        self.log_manager.add_log(f"Запрос изменён: {name} → {new_name}")
        self._restart_auto_timers()

    def add_new_query(self):
        db_names = self._get_db_names()
        dialog = QueryDialog(self, db_names,
                             db_manager=self.db_manager,
                             db_name_map=self._get_db_name_map(),
                             settings_manager=self.settings_manager)
        self.wait_window(dialog)
        if not dialog.result:
            return

        name, db, sql, interval, alert_on_change, alert_threshold, is_widget, cron = dialog.result
        if self.data_manager.add_new_query(name, sql):
            filename = f"{name}.sql"
            self.data_manager.set_query_display_name(filename, name)
            self._set_query_meta(filename,
                                 database=db,
                                 update_interval=interval,
                                 cron_schedule=cron,
                                 last_updated="—",
                                 alert_on_change=alert_on_change,
                                 alert_threshold=alert_threshold,
                                 is_widget=is_widget)
            self.refresh_queries_list()
            self._refresh_panel_query_lists()
            self._refresh_header_widgets()
            self.log_manager.add_log(f"Добавлен запрос: {name}")
            messagebox.showinfo("Успех", f"Запрос '{name}' добавлен")
            self._restart_auto_timers()
        else:
            messagebox.showerror("Ошибка", f"'{name}' уже существует")

    def _get_db_names(self) -> list:
        if not os.path.exists("config"):
            return []
        try:
            return [self.data_manager.get_db_display_name(f)
                    for f in os.listdir("config") if f.endswith(".json")]
        except Exception:
            return []

    def _get_db_name_map(self) -> dict:
        """Возвращает {display_name: config_name_без_расширения} для EXPLAIN-валидации."""
        if not os.path.exists("config"):
            return {}
        try:
            return {self.data_manager.get_db_display_name(f): f[:-5]
                    for f in os.listdir("config") if f.endswith(".json")}
        except Exception:
            return {}

    def _delete_query_by_name(self, name: str):
        fname = self.get_filename_by_display_name(name, "queries", ".sql")
        if not fname:
            return
        if messagebox.askyesno("Подтверждение", f"Удалить '{name}'?"):
            if self.data_manager.delete_query(fname):
                self._del_query_meta(fname)
                if self._selected_query_name == name:
                    self._selected_query_name = None
                self.refresh_queries_list()
                self._refresh_panel_query_lists()
                self.log_manager.add_log(f"Удалён запрос: {name}")
                self._restart_auto_timers()

    # ── общие вспомогательные методы списков ─────────────────────────────────

    def _apply_col_config(self, frame, weights: tuple, min_widths: tuple):
        """Применяет пропорциональные веса и минимальные ширины к колонкам фрейма."""
        for i, (w, mw) in enumerate(zip(weights, min_widths)):
            frame.grid_columnconfigure(i, weight=w, minsize=mw)

    def _build_empty_state(self, parent, row: int, icon: str,
                           title: str, desc: str, btn_text: str, btn_cmd):
        """Заглушка пустого списка: иконка + заголовок + описание + кнопка."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, pady=40, sticky="n")
        ctk.CTkLabel(frame, text=icon,
                     font=ctk.CTkFont(size=44)).pack(pady=(0, 8))
        ctk.CTkLabel(frame, text=title,
                     font=ctk.CTkFont(size=15, weight="bold")).pack()
        ctk.CTkLabel(frame, text=desc,
                     font=ctk.CTkFont(size=12),
                     text_color=("gray50", "gray60")).pack(pady=(4, 16))
        ctk.CTkButton(frame, text=btn_text, command=btn_cmd,
                      height=32).pack()

    # ── сортировка подключений ────────────────────────────────────────────────

    def _conn_sort_click(self, col: int):
        c, r = self._conn_sort
        self._conn_sort = (col, not r if col == c else False)
        self.refresh_connections_list()

    def _bg_test_conn(self, filename: str, config: dict):
        ok, _ = self.db_manager.test_connection_raw(config)

        def _apply():
            self._conn_statuses[filename] = ok
            self._conn_status_testing.discard(filename)
            self.refresh_connections_list()

        try:
            self.after(0, _apply)
        except Exception:
            pass

    def _sorted_conn_files(self, files: list) -> list:
        col, rev = self._conn_sort
        if col is None:
            return files

        def key(f):
            display = self.data_manager.get_db_display_name(f)
            try:
                with open(os.path.join("config", f), encoding="utf-8") as fh:
                    cfg = json.load(fh)
            except Exception:
                cfg = {}
            iv = self._get_conn_meta(f).get("update_interval", 0)
            vals = [display,
                    cfg.get("database_type", ""),
                    cfg.get("host", ""),
                    str(cfg.get("port", "")),
                    cfg.get("database_name", ""),
                    cfg.get("username", ""),
                    "",
                    cfg.get("charset", ""),
                    str(iv) if iv else ""]
            # col 0 — "●" (не сортируется), данные начинаются с col 1
            idx = col - 1
            v = vals[idx] if 0 <= idx < len(vals) else ""
            try:
                return (0, float(v))
            except (ValueError, TypeError):
                return (1, str(v).lower())

        return sorted(files, key=key, reverse=rev)

    # ── сортировка запросов ───────────────────────────────────────────────────

    def _query_sort_click(self, col: int):
        c, r = self._query_sort
        self._query_sort = (col, not r if col == c else False)
        self.refresh_queries_list()

    def _sorted_query_files(self, files: list) -> list:
        col, rev = self._query_sort
        if col is None:
            return files

        def key(f):
            display = self.data_manager.get_query_display_name(f)
            try:
                with open(os.path.join("queries", f), encoding="utf-8") as fh:
                    raw = fh.read().replace("\n", " ").strip()
                sql_preview = raw[:30]
            except Exception:
                sql_preview = ""
            meta = self._get_query_meta(f)
            db   = meta.get("database", "") or ""
            upd  = meta.get("last_updated", "") or ""
            iv   = meta.get("update_interval", 0)
            vals = [display, sql_preview, db, upd, str(iv) if iv else ""]
            v = vals[col] if col < len(vals) else ""
            try:
                return (0, float(v))
            except (ValueError, TypeError):
                return (1, str(v).lower())

        return sorted(files, key=key, reverse=rev)

    # ── контекстные меню ──────────────────────────────────────────────────────

    def _show_conn_ctx_menu(self, event, display_name: str):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Изменить",
                         command=lambda: self._edit_db_by_name(display_name))
        menu.add_command(label="Переподключить / Проверить",
                         command=lambda: self._retest_conn_by_name(display_name))
        menu.add_separator()
        menu.add_command(label="Удалить",
                         command=lambda: self._delete_db_by_name(display_name))
        menu.add_separator()
        menu.add_command(label="Копировать имя",
                         command=lambda: self._clip(display_name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _retest_conn_by_name(self, display_name: str):
        filename = self._find_conn_file(display_name)
        if not filename:
            return
        try:
            with open(os.path.join("config", filename), encoding="utf-8") as fh:
                config = json.load(fh)
        except Exception:
            return
        self._conn_statuses[filename] = None
        self._conn_status_testing.add(filename)
        self.refresh_connections_list()
        threading.Thread(
            target=self._bg_test_conn,
            args=(filename, config), daemon=True
        ).start()

    def _show_query_ctx_menu(self, event, display_name: str):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Изменить",
                         command=lambda: self._edit_query_by_name(display_name))
        menu.add_command(label="Удалить",
                         command=lambda: self._delete_query_by_name(display_name))
        menu.add_separator()
        menu.add_command(label="Просмотреть SQL",
                         command=lambda: self._show_sql_viewer(display_name))
        menu.add_command(label="История",
                         command=lambda: self._show_query_history(display_name))
        menu.add_separator()
        menu.add_command(label="Копировать имя",
                         command=lambda: self._clip(display_name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _clip(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(str(text))

    def _show_sql_viewer(self, display_name: str):
        """Read-only диалог с полным текстом SQL-запроса."""
        query_file = self._find_query_file(display_name)
        if not query_file:
            return
        try:
            with open(os.path.join("queries", query_file), encoding="utf-8") as fh:
                sql = fh.read()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"SQL — {display_name}")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("720x520")
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(0, weight=1)
        dlg.resizable(True, True)

        # Text-виджет (read-only, моноширинный)
        txt = tk.Text(
            dlg, wrap="none",
            font=("Courier New", 11),
            padx=10, pady=10,
            state="disabled",
            relief="flat", borderwidth=0)
        txt.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0))

        sb_y = ctk.CTkScrollbar(dlg, command=txt.yview)
        sb_y.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=(8, 0))
        sb_x = ctk.CTkScrollbar(dlg, orientation="horizontal", command=txt.xview)
        sb_x.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 4))
        txt.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        # Подстройка цветов под тему
        _is_dark = ctk.get_appearance_mode().lower() == "dark"
        txt.configure(
            background="#1e1e1e" if _is_dark else "#f8f8f8",
            foreground="#d4d4d4" if _is_dark else "#1e1e1e",
            selectbackground="#264f78" if _is_dark else "#b3d7ff")

        # Вставляем SQL и подсвечиваем ключевые слова
        txt.configure(state="normal")
        txt.insert("1.0", sql)
        _kw_color = "#569cd6" if _is_dark else "#0000ff"
        _fn_color  = "#dcdcaa" if _is_dark else "#795e26"
        txt.tag_configure("kw", foreground=_kw_color)
        txt.tag_configure("fn", foreground=_fn_color)
        _KEYWORDS = (
            r"\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|CROSS|ON|"
            r"GROUP\s+BY|ORDER\s+BY|HAVING|INSERT|INTO|UPDATE|SET|DELETE|"
            r"CREATE|ALTER|DROP|WITH|UNION|ALL|AS|AND|OR|NOT|IN|EXISTS|"
            r"CASE|WHEN|THEN|ELSE|END|DISTINCT|LIMIT|TOP|OFFSET|FETCH|"
            r"NULL|IS|BETWEEN|LIKE|ASC|DESC|BY|OVER|PARTITION)\b"
        )
        import re
        for m in re.finditer(_KEYWORDS, sql, re.IGNORECASE):
            s = f"1.0+{m.start()}c"
            e = f"1.0+{m.end()}c"
            txt.tag_add("kw", s, e)
        txt.configure(state="disabled")

        def _close_sql():
            dlg.destroy()
            try:
                self.focus_set()
            except Exception:
                pass

        ctk.CTkButton(dlg, text="Закрыть", command=_close_sql,
                      width=100).grid(row=2, column=0, columnspan=2, pady=(0, 8))
        dlg.bind("<Escape>", lambda _: _close_sql())
        dlg.bind("<Return>", lambda _: _close_sql())
        dlg.protocol("WM_DELETE_WINDOW", _close_sql)

        dlg.update_idletasks()
        w, h = 720, 520
        x = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def _show_query_history(self, display_name: str):
        """Диалог истории выполнения запроса: список N последних результатов."""
        query_file = self._find_query_file(display_name)
        if not query_file:
            return
        hist = self._query_history.get(query_file, [])
        if not hist:
            messagebox.showinfo("История", f"Нет сохранённых результатов для «{display_name}».\n"
                                           "История накапливается после каждого авто-запроса.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"История — {display_name}")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("900x580")
        dlg.resizable(True, True)
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        # ── заголовок с выбором записи ─────────────────────────────────────────
        top_f = ctk.CTkFrame(dlg, fg_color="transparent")
        top_f.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        top_f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top_f, text="Результат:", anchor="w").grid(
            row=0, column=0, padx=(0, 8))
        ts_values = [e["ts"] for e in reversed(hist)]   # новейшие первыми
        _sel_var  = ctk.StringVar(value=ts_values[0])
        ts_combo  = ctk.CTkComboBox(top_f, values=ts_values,
                                    variable=_sel_var, state="readonly", width=220)
        ts_combo.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(top_f, text=f"(всего {len(hist)} записей)",
                     anchor="w", text_color=("gray45", "gray60"),
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(12, 0))

        # ── фрейм результата ───────────────────────────────────────────────────
        result_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        result_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 4))
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_rowconfigure(0, weight=1)

        from widgets.result_table import ResultTable
        _tbl = ResultTable(result_frame, fg_color=result_frame.cget("fg_color"),
                           corner_radius=0)
        _tbl.grid(row=0, column=0, sticky="nsew")

        def _load(ts_str: str):
            entry = next((e for e in hist if e["ts"] == ts_str), None)
            if entry:
                _tbl.set_data(entry["rows"], entry["columns"])

        _load(ts_values[0])
        ts_combo.configure(command=_load)

        # ── кнопки ────────────────────────────────────────────────────────────
        btn_f = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_f.grid(row=2, column=0, pady=(0, 8))
        if len(hist) >= 2:
            ctk.CTkButton(btn_f, text="Сравнить...", width=110,
                          command=lambda: self._show_query_diff(display_name, hist)
                          ).pack(side="left", padx=(0, 8))
        def _close_hist():
            dlg.destroy()
            try:
                self.focus_set()
            except Exception:
                pass

        ctk.CTkButton(btn_f, text="Закрыть", command=_close_hist,
                      width=100).pack(side="left")
        dlg.bind("<Escape>", lambda _: _close_hist())
        dlg.protocol("WM_DELETE_WINDOW", _close_hist)

        dlg.update_idletasks()
        w, h = 900, 580
        x = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def _show_query_diff(self, display_name: str, hist: list):
        """Диалог сравнения двух исторических результатов одного запроса (diff)."""
        ts_values = [e["ts"] for e in reversed(hist)]

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Сравнение — {display_name}")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("1060x640")
        dlg.resizable(True, True)
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        # ── верхняя панель выбора ─────────────────────────────────────────────
        top_f = ctk.CTkFrame(dlg, fg_color="transparent")
        top_f.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        ctk.CTkLabel(top_f, text="Результат 1 (база):", anchor="w").pack(side="left", padx=(0, 4))
        v1 = ctk.StringVar(value=ts_values[-1] if len(ts_values) > 1 else ts_values[0])
        c1 = ctk.CTkComboBox(top_f, values=ts_values, variable=v1, state="readonly", width=200)
        c1.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(top_f, text="Результат 2 (новый):", anchor="w").pack(side="left", padx=(0, 4))
        v2 = ctk.StringVar(value=ts_values[0])
        c2 = ctk.CTkComboBox(top_f, values=ts_values, variable=v2, state="readonly", width=200)
        c2.pack(side="left", padx=(0, 16))

        summary_lbl = ctk.CTkLabel(top_f, text="", anchor="w",
                                    font=ctk.CTkFont(size=11),
                                    text_color=("gray40", "gray65"))
        summary_lbl.pack(side="left", padx=(4, 0))

        # ── таблица diff ──────────────────────────────────────────────────────
        table_f = ctk.CTkFrame(dlg, fg_color="transparent")
        table_f.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 4))
        table_f.grid_columnconfigure(0, weight=1)
        table_f.grid_rowconfigure(0, weight=1)

        import tkinter.ttk as _ttk
        style = _ttk.Style()
        style.configure("Diff.Treeview", rowheight=24)
        tree = _ttk.Treeview(table_f, show="headings", style="Diff.Treeview")

        vsb = _ttk.Scrollbar(table_f, orient="vertical",   command=tree.yview)
        hsb = _ttk.Scrollbar(table_f, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree.tag_configure("removed", background="#FFCDD2", foreground="#B71C1C")
        tree.tag_configure("added",   background="#C8E6C9", foreground="#1B5E20")
        tree.tag_configure("common",  background="")

        def _update():
            ts1, ts2 = v1.get(), v2.get()
            e1 = next((e for e in hist if e["ts"] == ts1), None)
            e2 = next((e for e in hist if e["ts"] == ts2), None)
            if not e1 or not e2:
                return
            cols = e1.get("columns") or e2.get("columns", [])

            tree["columns"] = ["_status"] + list(cols)
            tree.column("_status", width=120, anchor="center", stretch=False)
            tree.heading("_status", text="Статус")
            for c in cols:
                tree.column(c, width=130, anchor="w")
                tree.heading(c, text=c)

            def _row_key(r):
                return tuple("" if v is None else str(v) for v in r)

            rows1 = {_row_key(r) for r in e1.get("rows", [])}
            rows2 = {_row_key(r) for r in e2.get("rows", [])}
            removed = rows1 - rows2
            added   = rows2 - rows1
            common  = rows1 & rows2

            for item in tree.get_children():
                tree.delete(item)
            for r in sorted(common):
                tree.insert("", "end", values=("Без изменений",) + r, tags=("common",))
            for r in sorted(removed):
                tree.insert("", "end", values=("Удалено",) + r, tags=("removed",))
            for r in sorted(added):
                tree.insert("", "end", values=("Добавлено",) + r, tags=("added",))

            summary_lbl.configure(
                text=f"+ {len(added)} строк   − {len(removed)} строк   = {len(common)} без изменений")

        _update()
        c1.configure(command=lambda _: _update())
        c2.configure(command=lambda _: _update())

        # ── легенда ───────────────────────────────────────────────────────────
        leg_f = ctk.CTkFrame(dlg, fg_color="transparent")
        leg_f.grid(row=2, column=0, pady=(0, 2))
        for txt, fg in [("■ Добавлено", "#1B5E20"), ("■ Удалено", "#B71C1C")]:
            ctk.CTkLabel(leg_f, text=txt, text_color=fg,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=8)

        def _close_diff():
            dlg.destroy()
            try:
                self.focus_set()
            except Exception:
                pass

        ctk.CTkButton(dlg, text="Закрыть", command=_close_diff,
                      width=100).grid(row=3, column=0, pady=(0, 8))
        dlg.bind("<Escape>", lambda _: _close_diff())
        dlg.protocol("WM_DELETE_WINDOW", _close_diff)

        dlg.update_idletasks()
        w, h = 1060, 640
        x = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def _show_panel_history(self, panel):
        """Открывает историю запросов для конкретной панели дашборда."""
        query_name = panel.get_query_name() if panel else None
        if not query_name:
            import dialogs as _mb
            _mb.showinfo("История", "Выберите запрос в панели")
            return
        self._show_query_history(query_name)

    def _refresh_panel_query_lists(self):
        if hasattr(self, "dash_panels"):
            names = self._get_query_names()
            for p in self.dash_panels:
                p.set_queries(names)

    # ── Авто-обновление: кэш ──────────────────────────────────────────────────

    def _load_query_cache(self):
        try:
            if os.path.exists("query_cache.json"):
                with open("query_cache.json", "r", encoding="utf-8") as f:
                    self._query_results = json.load(f)
        except Exception as e:
            self.log_manager.add_log(f"Ошибка загрузки кэша: {e}", "ERROR")
            self._query_results = {}

    @staticmethod
    def _json_default(obj):
        import decimal
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return str(obj)
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return str(obj)

    def _save_query_cache(self):
        try:
            with self._query_results_lock:
                _snapshot = dict(self._query_results)
            with open("query_cache.json", "w", encoding="utf-8") as f:
                json.dump(_snapshot, f, ensure_ascii=False,
                          default=self._json_default)
        except Exception as e:
            self.log_manager.add_log(f"Ошибка сохранения кэша: {e}", "ERROR")

    # ── История алертов ───────────────────────────────────────────────────────

    def _load_alert_history(self):
        try:
            if os.path.exists("alert_history.json"):
                with open("alert_history.json", "r", encoding="utf-8") as f:
                    self._alert_history = json.load(f)
        except Exception:
            self._alert_history = []

    def _save_alert_history(self):
        try:
            with open("alert_history.json", "w", encoding="utf-8") as f:
                json.dump(self._alert_history[-500:], f, ensure_ascii=False)
        except Exception:
            pass

    def _toggle_alert_history_panel(self):
        visible = getattr(self, "_alert_hist_visible", False)
        self._alert_hist_visible = not visible
        if self._alert_hist_visible:
            self._alert_hist_frame.grid()
            self._alert_hist_btn.configure(text="▲ История алертов")
        else:
            self._alert_hist_frame.grid_remove()
            self._alert_hist_btn.configure(text="▼ История алертов")

    def _clear_alert_history(self):
        self._alert_history.clear()
        self._save_alert_history()
        self._render_alert_history()

    def _disable_alert_from_history(self, query_file: str):
        if not query_file:
            return
        meta = self._get_query_meta(query_file)
        thr = dict(meta.get("alert_threshold") or {})
        thr["enabled"] = False
        self._set_query_meta(query_file, alert_on_change=False, alert_threshold=thr)
        self._render_alert_history()

    def _render_alert_history(self):
        if not hasattr(self, "_alert_hist_scroll"):
            return
        scroll = self._alert_hist_scroll
        for w in scroll.winfo_children():
            w.destroy()

        if not self._alert_history:
            ctk.CTkLabel(
                scroll, text="Нет записей",
                text_color=("gray50", "gray60"),
            ).grid(row=0, column=0, pady=10, padx=10, sticky="w")
            return

        HDR_BG  = ("gray78", "gray25")
        bold    = ctk.CTkFont(weight="bold")
        sm_font = ctk.CTkFont(size=12)
        HDRS   = ("Время", "Запрос", "Тип", "Детали", "")
        WGTS   = (0, 1, 0, 1, 0)
        MINS   = (130, 150, 90, 200, 95)
        tbl = ctk.CTkFrame(scroll, fg_color="transparent")
        tbl.grid(row=0, column=0, sticky="ew")
        scroll.grid_columnconfigure(0, weight=1)
        for i, (h, wt, mw) in enumerate(zip(HDRS, WGTS, MINS)):
            tbl.grid_columnconfigure(i, weight=wt, minsize=mw)
            ctk.CTkLabel(tbl, text=h, font=bold, anchor="w", fg_color=HDR_BG).grid(
                row=0, column=i, padx=6, pady=4, sticky="nsew")

        for row_idx, entry in enumerate(reversed(self._alert_history[-100:])):
            r  = row_idx + 1
            bg = ("gray88", "gray20") if row_idx % 2 == 0 else ("gray83", "gray17")
            qf = entry.get("query_file", "")
            for col_i, val in enumerate([
                entry.get("ts", ""), entry.get("query_name", ""),
                entry.get("type", ""), entry.get("detail", ""),
            ]):
                ctk.CTkLabel(tbl, text=val, fg_color=bg, anchor="w",
                             font=sm_font).grid(
                    row=r, column=col_i, padx=6, pady=2, sticky="nsew")
            meta = self._get_query_meta(qf) if qf else {}
            alert_on = meta.get("alert_on_change", False) or \
                bool((meta.get("alert_threshold") or {}).get("enabled"))
            btn_text = "Откл. алерт" if alert_on else "✓ Откл."
            ctk.CTkButton(
                tbl, text=btn_text, width=88, height=22, font=sm_font,
                command=lambda f=qf: self._disable_alert_from_history(f),
            ).grid(row=r, column=4, padx=6, pady=2)

    # ── Авто-обновление: запуск и перезапуск таймеров ─────────────────────────

    def _start_auto_timers(self):
        """Немедленно выполняет все запросы, затем запускает таймеры."""
        if os.path.exists("queries"):
            for f in os.listdir("queries"):
                if f.endswith(".sql"):
                    self._execute_query_auto(f)
        self._refresh_all_dashboard_panels()
        # Фиксируем момент запуска как «последнее обновление» для подключений с интервалом
        now = datetime.datetime.now()
        if os.path.exists("config"):
            for f in os.listdir("config"):
                if f.endswith(".json") and \
                        self._get_conn_meta(f).get("update_interval", 0) > 0:
                    self._conn_last_refresh[f] = now
        self._schedule_all_timers()
        self._gf_schedule_start()

    def _restart_auto_timers(self):
        """Отменяет старые таймеры и перезапускает по актуальным настройкам."""
        for after_id in list(self._query_timers.values()):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        for after_id in list(self._conn_timers.values()):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self._query_timers.clear()
        self._conn_timers.clear()
        self._schedule_all_timers()

    def _schedule_all_timers(self):
        if os.path.exists("queries"):
            for f in os.listdir("queries"):
                if f.endswith(".sql"):
                    meta     = self._get_query_meta(f)
                    interval = meta.get("update_interval", 0)
                    cron     = meta.get("cron_schedule")
                    if cron and cron.get("enabled"):
                        self._schedule_query_cron(f, cron)
                    elif interval > 0:
                        self._schedule_query(f, interval)
        if os.path.exists("config"):
            for f in os.listdir("config"):
                if f.endswith(".json"):
                    interval = self._get_conn_meta(f).get("update_interval", 0)
                    if interval > 0:
                        self._schedule_conn_refresh(f, interval)

    # ── Авто-обновление: таймер запросов (интервальный) ───────────────────────

    def _schedule_query(self, query_file: str, interval_min: int):
        self._query_scheduled_at[query_file]    = datetime.datetime.now()
        self._query_intervals_cache[query_file] = interval_min
        after_id = self.after(
            interval_min * 60_000,
            lambda qf=query_file, iv=interval_min: self._query_tick(qf, iv))
        self._query_timers[query_file] = after_id

    def _query_tick(self, query_file: str, interval_min: int):
        self._execute_query_auto(query_file)
        self._schedule_query(query_file, interval_min)

    # ── Авто-обновление: cron-планировщик запросов ────────────────────────────

    @staticmethod
    def _cron_next_fire(now: datetime.datetime, hour: int, minute: int,
                        days: list) -> datetime.datetime:
        """Возвращает datetime следующего срабатывания cron (≥ now + 1 мин)."""
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += datetime.timedelta(days=1)
        # Прокручиваем вперёд до ближайшего разрешённого дня недели
        for _ in range(8):
            if not days or candidate.weekday() in days:
                return candidate
            candidate += datetime.timedelta(days=1)
        return candidate

    def _schedule_query_cron(self, query_file: str, cron: dict):
        try:
            h, m = map(int, cron.get("time", "09:00").split(":"))
        except Exception:
            h, m = 9, 0
        days = cron.get("days", [])
        next_fire = self._cron_next_fire(datetime.datetime.now(), h, m, days)
        delay_ms  = max(1000, int((next_fire - datetime.datetime.now()).total_seconds() * 1000))
        self._query_scheduled_at[query_file]    = datetime.datetime.now()
        self._query_intervals_cache[query_file] = 0
        after_id = self.after(
            delay_ms,
            lambda qf=query_file, c=cron: self._cron_tick(qf, c))
        self._query_timers[query_file] = after_id

    def _cron_tick(self, query_file: str, cron: dict):
        self._execute_query_auto(query_file)
        self._schedule_query_cron(query_file, cron)

    def _execute_query_auto(self, query_file: str):
        """Запускает SQL в фоне, сохраняет результат в кэш, обновляет панели дашборда."""
        if query_file in self._queries_in_progress:
            return
        try:
            meta = self._get_query_meta(query_file)
            db_display = meta.get("database", "")
            conn_file = self._find_conn_file(db_display) if db_display else None
            if not conn_file:
                return
            with open(os.path.join("queries", query_file), encoding="utf-8") as fh:
                sql = fh.read()
        except Exception as e:
            self.log_manager.add_log(
                f"Ошибка авто-запроса {query_file}: {e}", "ERROR")
            return

        db_name = os.path.splitext(conn_file)[0]
        self._queries_in_progress.add(query_file)

        # Показываем спиннер на всех панелях, привязанных к этому файлу
        for panel in getattr(self, "dash_panels", []):
            qf = self._find_query_file(panel.get_query_name() or "")
            if qf == query_file:
                panel.set_loading(True)

        def worker():
            _t0 = time.monotonic()
            try:
                rows, cols = self.db_manager.execute_query_with_columns(db_name, sql)
                _ms = (time.monotonic() - _t0) * 1000
                try:
                    self.after(0, lambda r=rows, c=cols, ms=_ms: done(r, c, None, ms))
                except Exception:
                    pass
            except Exception as e:
                _ms = (time.monotonic() - _t0) * 1000
                try:
                    self.after(0, lambda err=e, ms=_ms: done([], [], err, ms))
                except Exception:
                    pass

        def done(rows, cols, err, duration_ms: float = 0.0):
            if not self.winfo_exists():
                return
            self._queries_in_progress.discard(query_file)
            for panel in getattr(self, "dash_panels", []):
                qf = self._find_query_file(panel.get_query_name() or "")
                if qf == query_file:
                    panel.set_loading(False)
            if err:
                self.log_manager.add_log(
                    f"Ошибка авто-запроса {query_file}: {err}", "ERROR")
                try:
                    self.stats_manager.record(query_file, duration_ms, 0, is_error=True)
                except Exception:
                    pass
                return
            self._check_change_alert(query_file, rows, cols)
            self._check_threshold_alert(query_file, rows, cols)
            max_rows = self.settings_manager.get_setting("max_rows", 1000)
            if max_rows and len(rows) > max_rows:
                rows = rows[:max_rows]
            _rows_clean  = [list(r) for r in rows]
            _cols_clean  = list(cols)
            with self._query_results_lock:
                self._query_results[query_file] = {
                    "rows": _rows_clean,
                    "columns": _cols_clean,
                }
            self._save_query_cache()
            ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            self._set_query_meta(query_file, last_updated=ts)
            self._update_header_widget(query_file, _rows_clean, _cols_clean)

            # ── история запросов ─────────────────────────────────────────────
            # Лимит по количеству (10 записей) + по суммарному числу строк
            # (~100 000 ячеек на историю одного запроса ≈ ~10-20 МБ worst-case).
            _hist = self._query_history.setdefault(query_file, [])
            _hist.append({"ts": ts, "rows": _rows_clean, "columns": _cols_clean})
            if len(_hist) > 10:
                _hist.pop(0)
            _MAX_TOTAL_ROWS = 100_000
            while len(_hist) > 1:
                if sum(len(e["rows"]) for e in _hist) <= _MAX_TOTAL_ROWS:
                    break
                _hist.pop(0)

            self.refresh_queries_list()
            self.log_manager.add_log(
                f"Авто-запрос: {self.data_manager.get_query_display_name(query_file)}")
            for panel in getattr(self, "dash_panels", []):
                qf = self._find_query_file(panel.get_query_name() or "")
                if qf == query_file:
                    self._update_panel_from_cache(panel, query_file)
            try:
                self.stats_manager.record(query_file, duration_ms, len(_rows_clean))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    # ── Авто-обновление: таймер дашборда по подключению ───────────────────────

    def _schedule_conn_refresh(self, conn_file: str, interval_min: int):
        after_id = self.after(
            interval_min * 60_000,
            lambda cf=conn_file, iv=interval_min: self._conn_refresh_tick(cf, iv))
        self._conn_timers[conn_file] = after_id

    def _conn_refresh_tick(self, conn_file: str, interval_min: int):
        now = datetime.datetime.now()
        self._conn_last_refresh[conn_file] = now
        db_display = self.data_manager.get_db_display_name(conn_file)
        self._refresh_panels_for_db(db_display)
        self._schedule_conn_refresh(conn_file, interval_min)
        self.log_manager.add_log(
            f"Последнее время обновления: {now.strftime('%H:%M:%S')}")

    def _refresh_panels_for_db(self, db_display: str):
        """Обновляет панели дашборда, чьи запросы привязаны к данному подключению."""
        if not hasattr(self, "dash_panels"):
            return
        for panel in self.dash_panels:
            query_name = panel.get_query_name()
            if not query_name:
                continue
            query_file = self._find_query_file(query_name)
            if not query_file:
                continue
            if self._get_query_meta(query_file).get("database", "") == db_display:
                self._update_panel_from_cache(panel, query_file)

    def _force_refresh_all(self):
        """Принудительно перезапускает выполнение всех запросов."""
        if os.path.exists("queries"):
            for f in os.listdir("queries"):
                if f.endswith(".sql"):
                    self._execute_query_auto(f)

    def _refresh_all_dashboard_panels(self):
        """Обновляет все панели дашборда из кэша."""
        if not hasattr(self, "dash_panels"):
            return
        for panel in self.dash_panels:
            query_name = panel.get_query_name()
            if not query_name:
                continue
            query_file = self._find_query_file(query_name)
            if query_file:
                self._update_panel_from_cache(panel, query_file)

    def _update_panel_from_cache(self, panel: DashboardPanel, query_file: str):
        data = self._query_results.get(query_file)
        if data is None:
            return
        rows = data.get("rows", [])
        cols = data.get("columns", [])
        panel.set_result(rows, cols)
        meta = self._get_query_meta(query_file)
        last_upd = meta.get("last_updated", "")
        if last_upd and last_upd != "—":
            try:
                dt = datetime.datetime.strptime(last_upd, "%d.%m.%Y %H:%M:%S")
                panel.set_row_notice(f"Данные от {dt.strftime('%H:%M %d.%m')}")
            except Exception:
                panel.set_row_notice(f"Данные от {last_upd}")
        else:
            panel.set_row_notice("")

    # ── Авто-обновление: вспомогательные поисковики ───────────────────────────

    def _find_query_file(self, query_name: str) -> Optional[str]:
        if os.path.exists("queries"):
            for f in os.listdir("queries"):
                if f.endswith(".sql") and \
                        self.data_manager.get_query_display_name(f) == query_name:
                    return f
        return None

    def _find_conn_file(self, db_display: str) -> Optional[str]:
        if os.path.exists("config"):
            for f in os.listdir("config"):
                if f.endswith(".json") and \
                        self.data_manager.get_db_display_name(f) == db_display:
                    return f
        return None

    # ── Ротация логов ─────────────────────────────────────────────────────────

    def _run_log_rotation(self, startup: bool = False):
        """Удаляет записи старше настроенного порога и планирует следующую ротацию."""
        hours = self.settings_manager.get_setting("log_rotation_hours", 120)
        removed = self.log_manager.rotate_old_logs(hours)
        if removed > 0:
            src = "при запуске" if startup else "по расписанию"
            self.log_manager.add_log(
                f"Ротация логов ({src}): удалено {removed} записей старше {hours} ч.")
            self._play_sound("notification_delet_log.wav", "rotation_done")
            if not startup:
                self._add_notification(
                    "Ротация логов",
                    message=f"Выполнена ротация: удалено {removed} записей старше {hours} ч.",
                    system=True,
                )
        # Ротация по размеру файла
        max_mb = self.settings_manager.get_setting("log_rotation_max_mb", 100)
        removed_size = self.log_manager.rotate_by_size(max_mb)
        if removed_size > 0:
            self.log_manager.add_log(
                f"Ротация логов по размеру: удалено {removed_size} старых записей "
                f"(лимит {max_mb} МБ).")
            if not startup:
                self._add_notification(
                    "Ротация логов",
                    message=f"Размер превысил {max_mb} МБ: удалено {removed_size} записей.",
                    system=True,
                )
        self._schedule_log_rotation()

    def _schedule_log_rotation(self, delay_ms: int = None):
        """Планирует следующую ротацию.

        Если delay_ms не задан — на ближайшее 18:00.
        При вызове отменяет предыдущий таймер.
        """
        if self._rotation_after_id is not None:
            try:
                self.after_cancel(self._rotation_after_id)
            except Exception:
                pass
        if delay_ms is None:
            now    = datetime.datetime.now()
            target = now.replace(hour=18, minute=0, second=0, microsecond=0)
            if now >= target:
                target += datetime.timedelta(days=1)
            delay_ms = int((target - now).total_seconds() * 1000)
        self._rotation_after_id = self.after(delay_ms, self._run_log_rotation)

    def _check_rotation_warning(self):
        """Периодически (раз в 60 с) проверяет приближение ротации и добавляет WARNING."""
        self._rotation_warn_after_id = None

        max_age = self.settings_manager.get_setting("log_rotation_hours", 120)

        if max_age <= 8:
            warn_before_h = 0.5
            warn_text = "Через 30 минут будет произведена ротация логов"
        elif max_age <= 48:
            warn_before_h = 1.0
            warn_text = "Через 1 час будет произведена ротация логов"
        elif max_age <= 100:
            warn_before_h = 2.0
            warn_text = "Через 2 часа будет произведена ротация логов"
        else:
            warn_before_h = 3.0
            warn_text = "Через 3 часа будет произведена ротация логов"

        logs = self.log_manager.logs
        if logs:
            try:
                oldest_ts = min(
                    datetime.datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S")
                    for e in logs
                )
                age_h       = (datetime.datetime.now() - oldest_ts).total_seconds() / 3600
                remaining_h = max_age - age_h

                if 0 < remaining_h <= warn_before_h:
                    cutoff_dt = (datetime.datetime.now()
                                 - datetime.timedelta(hours=warn_before_h * 2))
                    already = any(
                        e.get("level") == "WARNING"
                        and "ротация логов" in e.get("message", "").lower()
                        and datetime.datetime.strptime(
                            e["timestamp"], "%Y-%m-%d %H:%M:%S") > cutoff_dt
                        for e in logs
                    )
                    if not already:
                        self.log_manager.add_log(warn_text, "WARNING")
                        self._play_sound("notification_delet_log.wav", "rotation_warning")
                        self._add_notification(
                            "Ротация логов",
                            message=warn_text,
                            system=True,
                        )
                        if hasattr(self, "logs_textbox"):
                            self.refresh_logs()
            except Exception:
                pass

        self._rotation_warn_after_id = self.after(60_000, self._check_rotation_warning)

    # ── Логи ──────────────────────────────────────────────────────────────────

    def _get_logs_theme_colors(self) -> dict:
        if ctk.get_appearance_mode() == "Dark":
            return {"bg": "#2B2B2B", "fg": "lightgray",
                    "error_fg": "red", "info_fg": "lightgray", "other_fg": "cyan"}
        bg = self._get_theme_bg()
        return {"bg": bg, "fg": "#1a1a1a",
                "error_fg": "#cc0000", "info_fg": "#1a1a1a", "other_fg": "#0000AA"}

    def setup_logs_tab(self):
        self.frame_logs.grid_columnconfigure(0, weight=1)
        self.frame_logs.grid_rowconfigure(0, weight=1)

        logs_frame = ctk.CTkFrame(self.frame_logs, fg_color="transparent")
        logs_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(1, weight=1)

        # ── состояние фильтра и поиска ───────────────────────────────────────
        saved_levels = self.settings_manager.get_setting("log_filter_levels", {})
        self._log_filter_levels = {
            lvl: saved_levels.get(lvl, True)
            for lvl in ("INFO", "ERROR", "WARNING")
        }
        self._log_filter_btns: dict = {}
        self._log_search_var = tk.StringVar()
        self._log_search_var.trace_add("write", lambda *_: self._on_log_search_changed())

        # ── тулбар ──────────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(logs_frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, pady=(0, 6), sticky="ew")

        # левая сторона: действия
        ctk.CTkButton(toolbar, text="Очистить логи", command=self.clear_logs,
                      width=130, height=32,
                      fg_color=("#E53935", "#C62828"),
                      hover_color=("#C62828", "#B71C1C")).pack(side="left", padx=(0, 6))
        ctk.CTkButton(toolbar, text="Сохранить в файл", command=self.save_logs_to_file,
                      width=140, height=32).pack(side="left")

        # правая сторона: кнопки фильтра (правее всего → ERROR, WARNING, INFO)
        _LVL_COLORS = {
            "INFO":    ("#1F6AA5", "#144870"),
            "WARNING": ("#E67E22", "#b8641b"),
            "ERROR":   ("#E53935", "#C62828"),
        }
        _INACTIVE = ("gray55", "gray35")
        for lvl in ("ERROR", "WARNING", "INFO"):
            active = self._log_filter_levels[lvl]
            c = _LVL_COLORS[lvl] if active else _INACTIVE
            btn = ctk.CTkButton(
                toolbar, text=lvl, width=76, height=28,
                fg_color=c, hover_color=c,
                command=lambda l=lvl: self._toggle_log_level(l))
            btn.pack(side="right", padx=2)
            self._log_filter_btns[lvl] = btn

        ctk.CTkLabel(toolbar, text="Уровень:").pack(side="right", padx=(16, 4))

        # × — упакован до Entry (side="right"), поэтому на экране появляется справа от Entry
        self._log_clear_btn = ctk.CTkButton(
            toolbar, text="✕", width=24, height=28,
            fg_color="transparent", hover_color=("gray70", "gray40"),
            command=self._clear_log_search)
        self._log_clear_btn.pack(side="right", padx=(0, 2))
        self._log_clear_btn.pack_forget()   # скрыт пока поле пустое

        ctk.CTkEntry(toolbar, textvariable=self._log_search_var,
                     placeholder_text="Поиск...",
                     width=190, height=28).pack(side="right", padx=(0, 0))

        ctk.CTkLabel(toolbar, text="🔍",
                     font=ctk.CTkFont(size=20)).pack(side="right", padx=(16, 6), pady=0, anchor="center")
        setup_paste_bindings(toolbar)

        _lc = self._get_logs_theme_colors()
        self.logs_textbox = tk.Text(
            logs_frame, font=("Consolas", 12),
            wrap="none", bg=_lc["bg"], fg=_lc["fg"],
            insertbackground="white", selectbackground="#4CAF50",
            cursor="arrow", bd=0, highlightthickness=0)
        self.logs_textbox.grid(row=1, column=0, sticky="nsew")

        # Только чтение: блокируем редактирование, разрешаем навигацию и Ctrl+C/A
        _NAV = frozenset(["Up","Down","Left","Right","Home","End","Prior","Next",
                          "KP_Up","KP_Down","KP_Left","KP_Right",
                          "Shift_L","Shift_R","Control_L","Control_R","Alt_L","Alt_R"])
        # Физические коды клавиш для nav-хоткеев (совпадают с _NAV_KEYCODE_MAP)
        _NAV_KC = {
            68: "📊 Приборная панель",
            76: "📋 Логи",
            75: "🔗 Подключения",
            81: "📝 Запросы",
            69: "⚙️ Настройки",
            78: "🔔 Уведомления",
            83: "🛠 Сервисы",
        }
        def _block_edit(e):
            if e.state & 4:   # Ctrl зажат
                ks = e.keysym.lower()
                kc = getattr(e, "keycode", -1)
                # Nav-хоткеи: перехватываем ДО class-binding Text-виджета
                nav_tab = _NAV_KC.get(kc)
                if nav_tab:
                    self._hamburger_select(nav_tab)
                    return "break"
                is_c = ks == "c" or (kc == 67 and ks not in ("c",))
                is_v = ks == "v" or (kc == 86 and ks not in ("v",))
                if is_c:
                    _copy()
                    return "break"
                if is_v:
                    return "break"  # блокируем Ctrl+V без копирования
                return None   # Ctrl+A и т.д. — стандартное поведение
            if e.keysym in _NAV:
                return None
            return "break"
        self.logs_textbox.bind("<Key>", _block_edit)

        # ── копирование: Ctrl+V, Ctrl+C и контекстное меню ──────────────────
        def _copy(e=None):
            try:
                self.logs_textbox.event_generate("<<Copy>>")
            except Exception:
                pass
            return "break"

        self.logs_textbox.bind("<Control-c>", _copy)
        self.logs_textbox.bind("<Control-C>", _copy)

        def _context_menu(event):
            has_sel = bool(self.logs_textbox.tag_ranges("sel"))
            menu = tk.Menu(self.logs_textbox, tearoff=0)
            menu.add_command(
                label="Копировать",
                state="normal" if has_sel else "disabled",
                command=_copy)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        self.logs_textbox.bind("<Button-3>", _context_menu)

        h_sb = ctk.CTkScrollbar(logs_frame, orientation="horizontal",
                                command=self.logs_textbox.xview)
        h_sb.grid(row=2, column=0, sticky="ew")
        self.logs_textbox.configure(xscrollcommand=h_sb.set)

        v_sb = ctk.CTkScrollbar(logs_frame, command=self.logs_textbox.yview)
        v_sb.grid(row=1, column=1, sticky="ns")
        self.logs_textbox.configure(yscrollcommand=v_sb.set)

        self._logs_shown = 0
        self.refresh_logs()
        self._poll_logs()

    def refresh_logs(self):
        self.logs_textbox.delete("1.0", "end")
        _lc = self._get_logs_theme_colors()
        self.logs_textbox.tag_configure("error", foreground=_lc["error_fg"])
        self.logs_textbox.tag_configure("info",  foreground=_lc["info_fg"])
        self.logs_textbox.tag_configure("other", foreground=_lc["other_fg"])
        filter_lvls = getattr(self, "_log_filter_levels",
                              {"INFO": True, "ERROR": True, "WARNING": True})
        term = getattr(self, "_log_search_var", None)
        term = term.get().strip().lower() if term else ""
        for entry in self.log_manager.get_logs():
            if not filter_lvls.get(entry["level"], True):
                continue
            if term:
                line = f"[{entry['timestamp']}] {entry['level']}: {entry['message']}"
                if term not in line.lower():
                    continue
            msg  = entry['message'].replace("\n", " ")
            text = f"[{entry['timestamp']}] {entry['level']}: {msg}\n"
            tag  = ("error" if entry["level"] == "ERROR"
                    else ("info" if entry["level"] == "INFO" else "other"))
            self.logs_textbox.insert("end", text, tag)
        self._logs_shown = len(self.log_manager.get_logs())
        self.logs_textbox.see("end")

    def _poll_logs(self):
        logs  = self.log_manager.get_logs()
        count = len(logs)
        if count > self._logs_shown:
            term = getattr(self, "_log_search_var", None)
            term = term.get().strip() if term else ""
            if term:
                self.refresh_logs()
            else:
                filter_lvls = getattr(self, "_log_filter_levels",
                                      {"INFO": True, "ERROR": True, "WARNING": True})
                added = 0
                for entry in logs[self._logs_shown:]:
                    if not filter_lvls.get(entry["level"], True):
                        continue
                    msg  = entry['message'].replace("\n", " ")
                    text = f"[{entry['timestamp']}] {entry['level']}: {msg}\n"
                    tag  = ("error" if entry["level"] == "ERROR"
                            else ("info" if entry["level"] == "INFO" else "other"))
                    self.logs_textbox.insert("end", text, tag)
                    added += 1
                self._logs_shown = count
                if added:
                    self.logs_textbox.see("end")
        self.after(500, self._poll_logs)

    def _on_conn_search_changed(self):
        term = self._conn_search_var.get()
        if hasattr(self, "_conn_clear_btn"):
            if term:
                self._conn_clear_btn.pack(side="right", padx=(0, 2))
            else:
                self._conn_clear_btn.pack_forget()
        self.refresh_connections_list()

    def _on_query_search_changed(self):
        term = self._query_search_var.get()
        if hasattr(self, "_query_clear_btn"):
            if term:
                self._query_clear_btn.pack(side="right", padx=(0, 2))
            else:
                self._query_clear_btn.pack_forget()
        self.refresh_queries_list()

    def _on_log_search_changed(self):
        """Вызывается при каждом изменении текста в поле поиска."""
        term = self._log_search_var.get()
        if hasattr(self, "_log_clear_btn"):
            if term:
                self._log_clear_btn.pack(side="right", padx=(0, 2))
            else:
                self._log_clear_btn.pack_forget()
        self.refresh_logs()

    def _clear_log_search(self):
        """Очищает поле поиска."""
        self._log_search_var.set("")

    def _apply_log_search(self):
        """Обновляет отображение логов с учётом текущего поискового запроса."""
        self.refresh_logs()

    def _toggle_log_level(self, level: str):
        """Переключает видимость строк заданного уровня."""
        self._log_filter_levels[level] = not self._log_filter_levels[level]
        active = self._log_filter_levels[level]
        _COLORS = {
            "INFO":    ("#1F6AA5", "#144870"),
            "WARNING": ("#E67E22", "#b8641b"),
            "ERROR":   ("#E53935", "#C62828"),
        }
        inactive = ("gray55", "gray35")
        btn = self._log_filter_btns[level]
        c = _COLORS[level] if active else inactive
        btn.configure(fg_color=c, hover_color=c)
        self.settings_manager.set_setting("log_filter_levels", dict(self._log_filter_levels))
        self.refresh_logs()

    def clear_logs(self):
        if messagebox.askyesno("Подтверждение", "Очистить все логи?"):
            self.log_manager.clear_logs()
            self.refresh_logs()
            self.log_manager.add_log("Логи очищены вручную")
            hours = self.settings_manager.get_setting("log_rotation_hours", 120)
            self._schedule_log_rotation(delay_ms=hours * 60 * 60 * 1000)

    def save_logs_to_file(self):
        default = f"sup.syst_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Сохранить логи",
            initialfile=default,
            defaultextension=".txt",
            filetypes=[("Текстовый файл", "*.txt"), ("Все файлы", "*.*")],
        )
        if not path:
            return
        self.log_manager.save_logs_to_file(path)
        messagebox.showinfo("Успех", f"Логи сохранены: {path}")
        self.log_manager.add_log(f"Логи сохранены: {path}")

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
                _invalidate_image_caches()
                new_img = _get_play_ctk_image(24)
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
            return [MainWindow._swap_colors(v, old_map) for v in val]
        return val

    def _update_ctk_props(self, widget, old_map: dict, props: list):
        for prop in props:
            try:
                val = widget.cget(prop)
                new_val = MainWindow._swap_colors(val, old_map)
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
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                # settings.json
                if os.path.exists("settings.json"):
                    zf.write("settings.json", "settings.json")
                # config/*.json
                if os.path.isdir("config"):
                    for fname in os.listdir("config"):
                        if fname.endswith(".json"):
                            zf.write(os.path.join("config", fname),
                                     os.path.join("config", fname))
                # queries/*.sql
                if os.path.isdir("queries"):
                    for fname in os.listdir("queries"):
                        if fname.endswith(".sql"):
                            zf.write(os.path.join("queries", fname),
                                     os.path.join("queries", fname))
            count_cfg = len([f for f in (os.listdir("config") if os.path.isdir("config") else []) if f.endswith(".json")])
            count_qry = len([f for f in (os.listdir("queries") if os.path.isdir("queries") else []) if f.endswith(".sql")])
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
                if count_cfg > 0:
                    os.makedirs("config", exist_ok=True)
                if count_qry > 0:
                    os.makedirs("queries", exist_ok=True)
                zf.extractall(".")

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
        if os.path.exists("queries"):
            for f in sorted(os.listdir("queries")):
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
        if os.path.exists("queries"):
            for f in sorted(os.listdir("queries")):
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
        _invalidate_image_caches()
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
        if not os.path.exists("config"):
            return
        updated = 0
        for f in os.listdir("config"):
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
        if not os.path.exists("queries"):
            return
        updated = 0
        for f in os.listdir("queries"):
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
        self.refresh_notifications_list()

    def _mark_notif_unread(self, notif_id: int):
        for n in self._notifications:
            if n["id"] == notif_id:
                n["read"] = False
                break
        self.set_notification_badge(True)
        self.refresh_notifications_list()

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

    # ── Вкладка «Сервисы» ─────────────────────────────────────────────────────

    def setup_services_tab(self):
        self.frame_services.grid_columnconfigure(0, weight=1)
        self.frame_services.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(
            self.frame_services, fg_color="transparent")
        scroll.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._svc_card_order  = []
        self._svc_card_frames = {}

        self._build_service_card_gf_scraping(scroll)
        self._build_service_card_instruktsiya(scroll)

        self.after(300, lambda: self._svc_setup_drag(scroll))


    def _build_service_card_gf_scraping(self, parent):
        # ── логотип ───────────────────────────────────────────────────────────
        _logo_img = None
        if _PIL_OK:
            try:
                _base = (sys._MEIPASS if getattr(sys, "frozen", False)
                         else os.path.dirname(os.path.abspath(__file__)))
                _pil = Image.open(os.path.join(_base, "gf_logo.png"))
                self._gf_logo_pil = _pil
                _logo_img = ctk.CTkImage(
                    light_image=_pil, dark_image=_pil, size=(29, 29))
            except Exception:
                pass

        # ── карточка ──────────────────────────────────────────────────────────
        card = ctk.CTkFrame(parent, corner_radius=10,
                            border_width=0,
                            border_color=[theme_colors.accent(), theme_colors.hover()])
        card.grid(row=0, column=0, padx=20, pady=(6, 3), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        def _hover_enter(e):
            card.configure(border_width=2)

        def _hover_leave(e):
            try:
                x, y = card.winfo_pointerx(), card.winfo_pointery()
                cx, cy = card.winfo_rootx(), card.winfo_rooty()
                if not (cx <= x < cx + card.winfo_width()
                        and cy <= y < cy + card.winfo_height()):
                    card.configure(border_width=0)
            except Exception:
                card.configure(border_width=0)

        def _bind_hover(w):
            try:
                w.bind("<Enter>", _hover_enter, add="+")
                w.bind("<Leave>", _hover_leave, add="+")
            except Exception:
                pass
            for ch in w.winfo_children():
                _bind_hover(ch)

        # ── title row ─────────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=16, pady=(7, 2), sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)

        if _logo_img:
            ctk.CTkLabel(title_row, image=_logo_img, text="").grid(
                row=0, column=0, padx=(0, 8))
        else:
            ctk.CTkLabel(title_row, text="🕸",
                         font=ctk.CTkFont(size=16)).grid(
                row=0, column=0, padx=(0, 8))

        ctk.CTkLabel(title_row, text="GF. Scraping",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w")

        # ── правый блок: v1.0 + ⚙ ────────────────────────────────────────────
        _v_row = ctk.CTkFrame(title_row, fg_color="transparent")
        _v_row.grid(row=0, column=2, padx=(8, 0), sticky="ne")
        ctk.CTkLabel(_v_row, text="v1.0",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60")).pack(side="left")
        ctk.CTkButton(
            _v_row, text="⚙", width=22, height=20,
            font=ctk.CTkFont(size=11),
            fg_color=[theme_colors.accent(), theme_colors.hover()],
            hover_color=[theme_colors.hover(), theme_colors.dark()],
            text_color="white",
            command=self._open_gf_service_settings,
        ).pack(side="left", padx=(5, 0))

        # ── ряд 1: описание (col 0) | поля (col 1) | переключатели (col 2) ──────
        _LBL_FNT = ctk.CTkFont(size=14)
        _VAL_FNT = ctk.CTkFont(size=14, weight="bold")
        _dot_on  = ("#22C55E", "#16A34A")
        _dot_off = ("gray60", "gray50")

        _saved_active = self.settings_manager.get_setting(
            "services_active", {}).get("gf_scraping", False)
        self._gf_active_var = tk.BooleanVar(value=_saved_active)

        _saved_notif = self.settings_manager.get_setting(
            "services_notifications", {}).get("gf_scraping", False)
        self._gf_notifications_var = tk.BooleanVar(value=_saved_notif)

        _saved_widget = self.settings_manager.get_setting(
            "services_widget", {}).get("gf_scraping", False)
        self._gf_widget_var = tk.BooleanVar(value=_saved_widget)

        # col 0: описание — напрямую в card с sticky="ew" (как у «Инструкции»)
        ctk.CTkLabel(
            card,
            text=("Сервис для парсинга данных изменений ОКПД/ОКВЭД с сайта classifikators.ru,\n"
                  "генерации SQL запросов для базы данных GOODFIN"),
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
            anchor="w",
            justify="left",
            wraplength=800,
        ).grid(row=1, column=0, padx=16, pady=(4, 4), sticky="ew")

        # ── ряд 2: кнопка + info-поля + переключатели (одна строка) ──────────
        last_row = ctk.CTkFrame(card, fg_color="transparent", height=1)
        last_row.grid(row=2, column=0, padx=16, pady=(4, 4), sticky="ew")

        # кнопка слева
        ctk.CTkButton(
            last_row, text="▶  Открыть",
            width=100, height=26,
            fg_color=[theme_colors.accent(), theme_colors.hover()],
            hover_color=[theme_colors.hover(), theme_colors.dark()],
            command=lambda: GFScrapingWindow.open(
                self,
                settings_manager=self.settings_manager,
                log_manager=self.log_manager,
                notify_cb=self._gf_service_notify,
                version=self._version,
            ),
        ).pack(side="left")

        # info-поля горизонтально (по центру)
        info_c = ctk.CTkFrame(last_row, fg_color="transparent", height=1)
        info_c.pack(side="left", padx=(20, 0))

        _latest = self.settings_manager.get_setting("gf_scraping_latest", {})
        ctk.CTkLabel(info_c, text="Последние изменения:",
                     font=_LBL_FNT, text_color=("gray50", "gray60"),
                     anchor="w").pack(side="left")
        self._gf_latest_frame = ctk.CTkFrame(info_c, fg_color="transparent", height=1)
        self._gf_latest_frame.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(info_c, text="  |  ", font=_LBL_FNT,
                     text_color=("gray60", "gray50")).pack(side="left")

        ctk.CTkLabel(info_c, text="Изменения найдены:",
                     font=_LBL_FNT, text_color=("gray50", "gray60"),
                     anchor="w").pack(side="left")
        self._gf_found_container = ctk.CTkFrame(info_c, fg_color="transparent", height=1)
        self._gf_found_container.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(info_c, text="  |  ", font=_LBL_FNT,
                     text_color=("gray60", "gray50")).pack(side="left")

        ctk.CTkLabel(info_c, text="Проверка:",
                     font=_LBL_FNT, text_color=("gray50", "gray60"),
                     anchor="w").pack(side="left")
        _saved_last_check = self.settings_manager.get_setting("gf_scraping_last_check", "")
        self._gf_last_check_lbl = ctk.CTkLabel(
            info_c, text=_saved_last_check, font=_VAL_FNT,
            text_color=("gray60", "gray50"), anchor="w")
        self._gf_last_check_lbl.pack(side="left", padx=(4, 0))

        _saved_found = self.settings_manager.get_setting("gf_scraping_found_changes", {})
        self.after(50, lambda: self._update_gf_found_changes_display(_saved_found))
        self.after(50, lambda: self._gf_populate_latest_labels(self._gf_latest_frame, _latest))

        # переключатели справа — вертикальный столбец
        sw_col = ctk.CTkFrame(last_row, fg_color="transparent", height=1)
        sw_col.pack(side="right")

        def _on_widget_toggle():
            val = self._gf_widget_var.get()
            d = dict(self.settings_manager.get_setting("services_widget", {}))
            d["gf_scraping"] = val
            self.settings_manager.set_setting("services_widget", d)
            self._refresh_header_widgets()

        ctk.CTkSwitch(
            sw_col,
            text="Виджет",
            variable=self._gf_widget_var,
            onvalue=True, offvalue=False,
            font=ctk.CTkFont(size=14),
            switch_width=32, switch_height=14,
            command=_on_widget_toggle,
        ).pack(side="top", anchor="w")

        ctk.CTkSwitch(
            sw_col,
            text="Уведомления",
            variable=self._gf_notifications_var,
            onvalue=True, offvalue=False,
            font=ctk.CTkFont(size=14),
            switch_width=32, switch_height=14,
            command=self._on_gf_notifications_toggle,
        ).pack(side="top", anchor="w")

        sw_active_row = ctk.CTkFrame(sw_col, fg_color="transparent", height=1)
        sw_active_row.pack(side="top", anchor="w")

        def _on_active_toggle():
            val = self._gf_active_var.get()
            dot_lbl.configure(text_color=_dot_on if val else _dot_off)
            d = dict(self.settings_manager.get_setting("services_active", {}))
            d["gf_scraping"] = val
            self.settings_manager.set_setting("services_active", d)
            if val:
                self._gf_stop_event.clear()
                self._gf_schedule_start()
            else:
                self._gf_stop_event.set()
                for _attr in ("_gf_daily_after_id", "_gf_cal_after_id"):
                    _aid = getattr(self, _attr, None)
                    if _aid is not None:
                        try:
                            self.after_cancel(_aid)
                        except Exception:
                            pass
                    setattr(self, _attr, None)

        ctk.CTkSwitch(
            sw_active_row, text="Активен",
            variable=self._gf_active_var,
            onvalue=True, offvalue=False,
            font=ctk.CTkFont(size=14),
            switch_width=32, switch_height=14,
            command=_on_active_toggle,
        ).pack(side="left")

        dot_lbl = ctk.CTkLabel(sw_active_row, text="●",
                               font=ctk.CTkFont(size=14),
                               text_color=_dot_on if _saved_active else _dot_off,
                               width=20)
        dot_lbl.pack(side="left", padx=(4, 0))

        # применяем hover ко всем дочерним виджетам карточки
        self.after(50, lambda: _bind_hover(card))

        self._svc_card_order.append("gf_scraping")
        self._svc_card_frames["gf_scraping"] = card

    # ── карточка «Инструкция» ─────────────────────────────────────────────────

    def _build_service_card_instruktsiya(self, parent):
        card = ctk.CTkFrame(parent, corner_radius=10,
                            border_width=0,
                            border_color=[theme_colors.accent(), theme_colors.hover()])
        card.grid(row=1, column=0, padx=20, pady=(3, 6), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        def _hover_enter(e):
            card.configure(border_width=2)

        def _hover_leave(e):
            try:
                x, y = card.winfo_pointerx(), card.winfo_pointery()
                cx, cy = card.winfo_rootx(), card.winfo_rooty()
                if not (cx <= x < cx + card.winfo_width()
                        and cy <= y < cy + card.winfo_height()):
                    card.configure(border_width=0)
            except Exception:
                card.configure(border_width=0)

        def _bind_hover(w):
            try:
                w.bind("<Enter>", _hover_enter, add="+")
                w.bind("<Leave>", _hover_leave, add="+")
            except Exception:
                pass
            for ch in w.winfo_children():
                _bind_hover(ch)

        # ── title row ─────────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=16, pady=(10, 2), sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(title_row, text="📖",
                     font=ctk.CTkFont(size=22)).grid(
            row=0, column=0, padx=(0, 8))

        ctk.CTkLabel(title_row, text="Инструкция",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w")

        today_str = datetime.date.today().strftime("%d.%m.%Y")
        ctk.CTkLabel(title_row, text=today_str,
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60")).grid(
            row=0, column=2, padx=(8, 0), sticky="e")

        # ── описание ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            card,
            text="Встроенная справка по использованию приложения Hunch:\nвкладки меню, горячие клавиши, уведомления, логи, сервисы",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(6, 4), sticky="ew")

        # ── кнопка «Открыть» ─────────────────────────────────────────────────
        last_row = ctk.CTkFrame(card, fg_color="transparent")
        last_row.grid(row=2, column=0, padx=16, pady=(4, 39), sticky="ew")

        ctk.CTkButton(
            last_row, text="▶  Открыть",
            width=100, height=26,
            fg_color=[theme_colors.accent(), theme_colors.hover()],
            hover_color=[theme_colors.hover(), theme_colors.dark()],
            command=self._open_instruktsiya_window,
        ).pack(side="left")

        self.after(50, lambda: _bind_hover(card))

        self._svc_card_order.append("instruktsiya")
        self._svc_card_frames["instruktsiya"] = card

    # ── drag-and-drop карточек сервисов (удержание 3 с) ──────────────────────

    def _svc_setup_drag(self, scroll):
        self._svc_scroll    = scroll
        self._svc_drag_key  = None
        self._svc_drag_hold = None
        self._svc_dragging  = False
        self._svc_ghost     = None
        self._svc_line      = None
        self._svc_target    = 0

        for key, card in self._svc_card_frames.items():
            self._svc_bind_press(key, card)

        self.bind_all("<B1-Motion>",       self._svc_on_motion,  add="+")
        self.bind_all("<ButtonRelease-1>", self._svc_on_release, add="+")

    def _svc_bind_press(self, key, card):
        def _bind(w):
            w.bind("<ButtonPress-1>",
                   lambda e, k=key: self._svc_on_press(k), add="+")
            for ch in w.winfo_children():
                _bind(ch)
        _bind(card)

    def _svc_on_press(self, key):
        if getattr(self, "_svc_drag_hold", None):
            self.after_cancel(self._svc_drag_hold)
        self._svc_drag_key  = key
        self._svc_drag_hold = self.after(
            3000, lambda k=key: self._svc_enter_drag(k))

    def _svc_enter_drag(self, key):
        self._svc_drag_hold = None
        self._svc_dragging  = True
        self._svc_target    = self._svc_card_order.index(key)

        card = self._svc_card_frames[key]
        cw = card.winfo_width()
        ch = card.winfo_height()
        cx = card.winfo_rootx()
        cy = card.winfo_rooty()

        # Ghost — полупрозрачный прямоугольник цвета карточки
        g = tk.Toplevel(self)
        g.overrideredirect(True)
        g.attributes("-alpha", 0.45)
        g.attributes("-topmost", True)
        g.geometry(f"{cw}x{ch}+{cx}+{cy}")
        tk.Frame(g, bg=theme_colors.accent()).pack(fill="both", expand=True)
        tk.Label(g, text="≡  Перетаскивание", bg=theme_colors.accent(), fg="white",
                 font=("Segoe UI", 13)).place(relx=0.5, rely=0.5, anchor="center")
        self._svc_ghost = g

        # Линия вставки
        l = tk.Toplevel(self)
        l.overrideredirect(True)
        l.attributes("-topmost", True)
        l.geometry(f"{cw}x4+{cx}+{cy}")
        tk.Frame(l, bg=theme_colors.accent()).pack(fill="both", expand=True)
        self._svc_line = l

    def _svc_on_motion(self, event):
        if not getattr(self, "_svc_dragging", False):
            return

        g = getattr(self, "_svc_ghost", None)
        if g:
            try:
                if g.winfo_exists():
                    gw = g.winfo_width()
                    gh = g.winfo_height()
                    g.geometry(f"+{event.x_root - gw // 2}+{event.y_root - gh // 2}")
            except Exception:
                pass

        key    = self._svc_drag_key
        others = [k for k in self._svc_card_order if k != key]
        if not others:
            return

        mouse_y  = event.y_root
        best_key = others[0]
        best_d   = float("inf")
        for k in others:
            c  = self._svc_card_frames[k]
            cy = c.winfo_rooty() + c.winfo_height() / 2
            d  = abs(mouse_y - cy)
            if d < best_d:
                best_d, best_key = d, k

        tc           = self._svc_card_frames[best_key]
        tc_y         = tc.winfo_rooty()
        tc_h         = tc.winfo_height()
        insert_after = mouse_y > tc_y + tc_h / 2
        base_idx     = self._svc_card_order.index(best_key)
        self._svc_target = base_idx + 1 if insert_after else base_idx

        l = getattr(self, "_svc_line", None)
        if l:
            try:
                if l.winfo_exists():
                    line_y = (tc_y + tc_h) if insert_after else tc_y
                    l.geometry(f"{tc.winfo_width()}x4+{tc.winfo_rootx()}+{line_y}")
            except Exception:
                pass

    def _svc_on_release(self, event):
        hold = getattr(self, "_svc_drag_hold", None)
        if hold:
            self.after_cancel(hold)
            self._svc_drag_hold = None

        was_dragging = getattr(self, "_svc_dragging", False)
        key          = getattr(self, "_svc_drag_key", None)
        self._svc_dragging = False
        self._svc_drag_key = None

        for attr in ("_svc_ghost", "_svc_line"):
            w = getattr(self, attr, None)
            try:
                if w and w.winfo_exists():
                    w.destroy()
            except Exception:
                pass
            setattr(self, attr, None)

        if not was_dragging or not key:
            return

        old_idx   = self._svc_card_order.index(key)
        new_idx   = getattr(self, "_svc_target", old_idx)
        self._svc_card_order.remove(key)
        insert_at = new_idx - 1 if new_idx > old_idx else new_idx
        insert_at = max(0, min(insert_at, len(self._svc_card_order)))
        self._svc_card_order.insert(insert_at, key)
        if old_idx != insert_at:
            self._svc_rebuild_cards()

    def _svc_rebuild_cards(self):
        n = len(self._svc_card_order)
        for i, key in enumerate(self._svc_card_order):
            card = self._svc_card_frames[key]
            pady = (6, 3) if i == 0 else ((3, 6) if i == n - 1 else (3, 3))
            card.grid(row=i, column=0, padx=20, pady=pady, sticky="ew")

    def _open_instruktsiya_window(self, scroll_to_hotkeys: bool = False):
        existing = getattr(self, "_instruktsiya_win", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_set()
                    if scroll_to_hotkeys:
                        existing.after(50, lambda: self._instruktsiya_scroll_hotkeys(existing))
                    return
            except Exception:
                pass

        win = ctk.CTkToplevel(self)
        self._instruktsiya_win = win
        win.withdraw()
        win.title("Инструкция — Hunch")
        win.geometry("760x660")
        win.transient(self)

        def _on_close():
            self._instruktsiya_win = None
            try:
                win.grab_release()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _on_close)

        _H1  = ctk.CTkFont(size=16, weight="bold")
        _H2  = ctk.CTkFont(size=13, weight="bold")
        _TXT = ctk.CTkFont(size=12)
        _SUB = ctk.CTkFont(size=12)
        _TC_MAIN = ("gray10", "white")
        _TC_DIM  = ("gray30", "gray70")
        _TC_TEAL = (theme_colors.accent(), "#2DD4BF")

        # ── реестр для поиска ─────────────────────────────────────────────────
        _search_sections: list = []   # [section_frame]
        _search_rows:     list = []   # [(section_frame, row_frame, text, pack_kw)]
        _search_var = ctk.StringVar()

        def _on_instr_search(*_):
            q = _search_var.get().strip().lower()
            if not q:
                for sf in _search_sections:
                    sf.pack(fill="x", padx=14, pady=(10, 0))
                for _, rf, _, kw in _search_rows:
                    rf.pack(**kw)
                return
            visible: set = set()
            for sf, rf, text, kw in _search_rows:
                if q in text:
                    rf.pack(**kw)
                    visible.add(id(sf))
                else:
                    rf.pack_forget()
            for sf in _search_sections:
                if id(sf) in visible:
                    sf.pack(fill="x", padx=14, pady=(10, 0))
                else:
                    sf.pack_forget()

        _search_var.trace_add("write", _on_instr_search)

        # ── шапка ─────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(win, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(hdr, text="📖", font=ctk.CTkFont(size=28)).pack(side="left")
        ctk.CTkLabel(hdr, text="  Инструкция по использованию Hunch",
                     font=_H1, text_color=_TC_MAIN).pack(side="left")

        # ── строка поиска ─────────────────────────────────────────────────────
        search_bar = ctk.CTkFrame(win, fg_color="transparent")
        search_bar.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkEntry(
            search_bar, textvariable=_search_var,
            placeholder_text="Поиск по инструкции…", height=32,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            search_bar, text="✕", width=32, height=32,
            fg_color="transparent", hover_color=("gray75", "gray30"),
            command=lambda: _search_var.set(""),
        ).pack(side="left", padx=(6, 0))

        ctk.CTkFrame(win, height=1,
                     fg_color=("gray75", "gray30")).pack(fill="x", padx=20, pady=(8, 0))

        # ── скролл ────────────────────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        scroll.grid_columnconfigure(0, weight=1)

        def section(title: str, icon: str = ""):
            f = ctk.CTkFrame(scroll, fg_color=("gray90", "gray18"), corner_radius=8)
            f.pack(fill="x", padx=14, pady=(10, 0))
            ctk.CTkLabel(f, text=f"{icon}  {title}" if icon else title,
                         font=_H2, text_color=_TC_TEAL, anchor="w").pack(
                fill="x", padx=14, pady=(10, 4))
            ctk.CTkFrame(f, height=1,
                         fg_color=("gray75", "gray32")).pack(fill="x", padx=14, pady=(0, 6))
            _search_sections.append(f)
            return f

        def row(parent, label: str, value: str = "", indent: int = 0):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            pack_kw = {"fill": "x", "padx": 14 + indent, "pady": 1}
            r.pack(**pack_kw)
            if value:
                ctk.CTkLabel(r, text=label, font=_TXT,
                             text_color=_TC_DIM, anchor="w",
                             width=220).pack(side="left")
                ctk.CTkLabel(r, text=value, font=_SUB,
                             text_color=_TC_MAIN, anchor="w",
                             wraplength=430, justify="left").pack(
                    side="left", fill="x", expand=True)
            else:
                ctk.CTkLabel(r, text=label, font=_TXT,
                             text_color=_TC_MAIN, anchor="w",
                             wraplength=660, justify="left").pack(
                    fill="x", pady=(0, 2))
            _search_rows.append((parent, r, (label + " " + value).lower(), pack_kw))

        def spacer(parent, h: int = 6):
            ctk.CTkFrame(parent, fg_color="transparent", height=h).pack()

        # ──────────────────────────────────────────────────────────────────────
        # 1. ВКЛАДКИ МЕНЮ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Вкладки меню", "🗂")

        row(s, "📊 Приборная панель",
            "Главный экран с фреймами данных. Каждый фрейм отображает результат SQL-запроса "
            "в виде таблицы, графика или анимированного виджета. Компоновка фреймов "
            "(1+2, 2+1, 2×2 и др.) настраивается через «Настройки → Шаблон…».")
        row(s, "🔗 Подключения",
            "Управление подключениями к базам данных. Поддерживаемые СУБД: Oracle, PostgreSQL, MySQL/MariaDB. "
            "Для каждого подключения задаются: имя, хост, порт, имя БД, логин, пароль. "
            "Кнопка «Проверить» тестирует соединение без сохранения.")
        row(s, "📝 Запросы",
            "Создание, редактирование и запуск SQL-запросов. Выбор активного подключения из списка. "
            "Кнопка «Выполнить» исполняет запрос и выводит результат в таблицу. "
            "Запросы сохраняются и могут запускаться вручную или по расписанию. "
            "При изменении результата относительно предыдущего выполнения формируется уведомление.")
        row(s, "📋 Логи",
            "Журнал всех событий приложения в реальном времени. "
            "Уровни: INFO (стандартный), WARNING (жёлтый), ERROR (красный). "
            "Записи сервиса GF.Scraping помечены префиксом [GF.Scraping]. "
            "Ctrl+C копирует выделенный текст. Кнопка «Очистить» очищает отображение.")
        row(s, "⚙️ Настройки",
            "Конфигурация приложения: список уведомлений с галочками, громкость, тема оформления, "
            "управление SQL-запросами для отслеживания, параметры подключений.")
        row(s, "🔔 Уведомления",
            "Журнал всех уведомлений. Непрочитанные — яркий цвет, прочитанные — приглушённый. "
            "«◎ Прочитать» отмечает одно уведомление. «Прочитать все» / «Удалить все» — массовые действия. "
            "Колокольчик (🔔) в шапке мигает при наличии непрочитанных уведомлений.")
        row(s, "🛠 Сервисы",
            "Модульные сервисы приложения. Каждый сервис — карточка с описанием и кнопкой «Открыть».")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 2. ГОРЯЧИЕ КЛАВИШИ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Горячие клавиши", "⌨")
        _hotkeys_section = s

        row(s, "Ctrl + D  /  Ctrl + В", "Перейти на «Приборная панель»")
        row(s, "Ctrl + L  /  Ctrl + Д", "Перейти на «Логи»")
        row(s, "Ctrl + K  /  Ctrl + Л", "Перейти на «Подключения»")
        row(s, "Ctrl + Q  /  Ctrl + Й", "Перейти на «Запросы»")
        row(s, "Ctrl + E  /  Ctrl + У", "Перейти на «Настройки»")
        row(s, "Ctrl + N  /  Ctrl + Т", "Перейти на «Уведомления»")
        row(s, "Ctrl + S  /  Ctrl + Ы", "Перейти на «Сервисы»")
        row(s, "F1", "Открыть справку (это окно) в разделе «Горячие клавиши»")
        row(s, "Tab", "Переключение между вкладками навигации (верхняя панель)")
        row(s, "Escape", "Закрыть активное диалоговое окно")
        row(s, "Enter", "Подтвердить / закрыть диалоговое окно подтверждения")
        row(s, "Ctrl + C", "Копировать выделенный текст в Логах")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 3. ТИПЫ УВЕДОМЛЕНИЙ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Типы уведомлений", "🔔")

        row(s, "", "Все типы уведомлений управляются в разделе «Настройки → Список уведомлений». "
            "Если галочка напротив типа снята — уведомления данного типа не записываются в журнал, "
            "не отображаются в виде push-тоста и не воспроизводят звуковой сигнал.")
        spacer(s, 4)
        row(s, "Алерт при изменении результата",
            "Срабатывает при изменении данных в результате SQL-запроса (добавлены или удалены строки).")
        row(s, "Пороговый алерт по столбцу",
            "Срабатывает, когда значение в отслеживаемом столбце SQL-запроса пересекает заданный порог.")
        row(s, "Сигнал",
            "Общий сигнальный тип уведомления.")
        row(s, "Изменение значения виджета",
            "Срабатывает при изменении значения виджета на приборной панели.")
        row(s, "Изменение результата запроса",
            "Общее уведомление об изменении результата любого отслеживаемого SQL-запроса.")
        row(s, "Предупреждение о ротации логов",
            "Лог-файл приближается к лимиту и скоро будет выполнена ротация.")
        row(s, "Фактическая ротация логов",
            "Выполнена ротация лог-файла (старый архивирован, создан новый).")
        row(s, "Сервисы",
            "Уведомления от модульных сервисов (GF.Scraping и др.).")
        spacer(s, 4)
        row(s, "", "Push-тост — всплывающий блок в правом верхнем углу шапки приложения. "
            "Появляется при новом уведомлении и исчезает автоматически. "
            "Клик по тосту переходит к соответствующему уведомлению в журнале.")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 4. ЗАПИСИ В ЛОГАХ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Записи в логах", "📋")

        row(s, "", "Уровни записей:")
        row(s, "INFO", "Стандартная информационная запись. Нормальная работа приложения.", indent=20)
        row(s, "WARNING", "Предупреждение. Действие выполнено с отклонением от нормы.", indent=20)
        row(s, "ERROR", "Ошибка. Действие не выполнено или прервано.", indent=20)
        spacer(s, 4)
        row(s, "", "Записи сервиса GF.Scraping (префикс [GF.Scraping]):")
        row(s, "[GF.Scraping] Фоновая проверка: запрос …",
            "Начало фоновой проверки — отправка HTTP-запроса к classifikators.ru.", indent=20)
        row(s, "[GF.Scraping] ОКВЭД: получено N номеров, макс=M, мин=K",
            "Успешно получены данные страницы обновлений ОКВЭД.", indent=20)
        row(s, "[GF.Scraping] ОКВЭД: базовый макс=M, новые: [список]",
            "Сравнение с базовой точкой. Если список пуст — новых записей нет.", indent=20)
        row(s, "[GF.Scraping] ОКВЭД: базовая точка не задана",
            "Ручной парсинг ещё не выполнялся — запустите сервис и откройте страницу ОКВЭД.", indent=20)
        row(s, "[GF.Scraping] ОКВЭД: таблица не найдена или пустая",
            "Сайт недоступен или структура страницы изменилась.", indent=20)
        row(s, "[GF.Scraping] Обнаружены новые изменения в справочниках: …",
            "Найдены новые номера — сформировано уведомление.", indent=20)
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 5. СЕРВИС GF.SCRAPING
        # ──────────────────────────────────────────────────────────────────────
        s = section("Сервис GF.Scraping", "🕸")

        row(s, "",
            "Сервис для парсинга изменений справочников ОКВЭД и ОКПД с сайта classifikators.ru "
            "и генерации SQL-запросов для базы данных GOODFIN.")
        spacer(s, 4)
        row(s, "Последние изменения",
            "Максимальный номер записи, установленный при последнем ручном парсинге. "
            "Служит базовой точкой сравнения для фоновой проверки.")
        row(s, "Найдены изменения",
            "Номера новых записей, обнаруженных при фоновой проверке (выше базовой точки). "
            "Отображаются зелёным цветом. Обновляются после каждой проверки.")
        row(s, "Проверка изменений",
            "Дата и время последней выполненной фоновой проверки.")
        row(s, "⚙ Настройка расписания",
            "Открывает диалог настройки расписания: ежедневно с заданным интервалом (мин) "
            "или по конкретным датам/числам месяца.")
        row(s, "Переключатель «Активен»",
            "Включает/выключает фоновую проверку по расписанию. "
            "Зелёная точка — активен, серая — отключён.")
        row(s, "Кнопка «Открыть»",
            "Открывает окно GF.Scraping для ручного парсинга страниц ОКВЭД/ОКПД "
            "и генерации SQL-запросов. Парсинг устанавливает базовую точку сравнения.")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 6. КОМПОНОВКА ПРИБОРНОЙ ПАНЕЛИ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Компоновка приборной панели", "⊞")

        row(s, "",
            "Расположение фреймов на приборной панели можно изменить в любой момент "
            "без перезапуска. Все настройки сохраняются автоматически в settings.json.")
        spacer(s, 4)
        row(s, "Выбор шаблона",
            "В «Настройки → Количество фреймов → Шаблон…» откроется диалог с карточками "
            "доступных шаблонов. В том же диалоге можно сразу изменить количество фреймов (1–6).")
        spacer(s, 4)
        row(s, "Авто", "Поведение по умолчанию: два равных столбца, фреймы распределяются "
            "автоматически.", indent=20)
        row(s, "Столбец", "Все фреймы расположены в одну вертикальную колонку.", indent=20)
        row(s, "Строка", "Все фреймы расположены в одну горизонтальную строку.", indent=20)
        row(s, "1 + 2", "Один широкий фрейм сверху, оставшиеся — в строку снизу.", indent=20)
        row(s, "2 + 1", "Фреймы в строку сверху, один широкий фрейм снизу.", indent=20)
        row(s, "2 × 2", "Сетка: два столбца, фреймы распределяются по обеим колонкам.", indent=20)
        spacer(s, 4)
        row(s, "Перетаскивание фреймов",
            "Захватите фрейм за иконку ⠿ в заголовке и перетащите на другой фрейм — "
            "их содержимое (запрос, данные, настройки визуализации) поменяется местами.")
        row(s, "Равные размеры",
            "Кнопка «Равные размеры» (рядом с «Шаблон…» в Настройках) мгновенно выравнивает "
            "все фреймы по размеру. Разделители между фреймами всегда можно перетащить мышью.")
        row(s, "Закрепление фрейма",
            "Кнопка 📌 в заголовке фрейма фиксирует его размер: разделители не сдвигаются, "
            "пока фрейм закреплён.")
        spacer(s)

        # ──────────────────────────────────────────────────────────────────────
        # 7. СОВЕТЫ
        # ──────────────────────────────────────────────────────────────────────
        s = section("Советы и рекомендации", "💡")

        row(s, "",
            "• Перед использованием GF.Scraping выполните хотя бы один ручной парсинг страниц ОКВЭД "
            "и ОКПД — это установит базовую точку для сравнения.")
        row(s, "",
            "• Если уведомления не приходят — проверьте галочки в «Настройки → Список уведомлений»: "
            "тип «Сервисы» должен быть включён.")
        row(s, "",
            "• Расписание GF.Scraping работает только при включённом переключателе «Активен» "
            "на карточке сервиса.")
        row(s, "",
            "• Для быстрой смены компоновки приборной панели используйте «Настройки → Шаблон…». "
            "Кнопка «Равные размеры» быстро выравнивает фреймы после изменения шаблона.")
        row(s, "",
            "• Порядок вкладок в боковом меню можно изменить перетаскиванием.")
        row(s, "",
            "• Тема оформления (светлая/тёмная) переключается в «Настройки».")
        spacer(s)

        # ── кнопка закрыть ────────────────────────────────────────────────────
        ctk.CTkFrame(win, height=1,
                     fg_color=("gray75", "gray30")).pack(fill="x", padx=20, pady=(4, 0))
        ctk.CTkButton(win, text="Закрыть", width=110, height=34,
                      fg_color=_TC_TEAL,
                      hover_color=(theme_colors.hover(), theme_colors.dark()),
                      command=win.destroy).pack(pady=(10, 16))

        def _center():
            try:
                self.update_idletasks()
                pw = self.winfo_width()
                ph = self.winfo_height()
                x = self.winfo_rootx() + max(0, (pw - 760) // 2)
                y = self.winfo_rooty() + max(0, (ph - 660) // 2)
                win.geometry(f"+{x}+{y}")
                win.deiconify()
                win.grab_set()
                win.lift()
            except Exception:
                pass

        def _scroll_hotkeys():
            self._instruktsiya_scroll_hotkeys(win, scroll, _hotkeys_section)

        win.after(50, _center)
        if scroll_to_hotkeys:
            win.after(200, _scroll_hotkeys)

    def _instruktsiya_scroll_hotkeys(self, win, scroll=None, section=None):
        try:
            win.update_idletasks()
            if scroll is None:
                return
            canvas = scroll._parent_canvas
            bbox = canvas.bbox("all")
            if not bbox:
                return
            total_h = bbox[3] - bbox[1]
            if total_h <= 0 or section is None:
                return
            sec_root_y    = section.winfo_rooty()
            canvas_root_y = canvas.winfo_rooty()
            scroll_top    = canvas.canvasy(0)
            sec_y = sec_root_y - canvas_root_y + scroll_top - 10
            canvas.yview_moveto(max(0.0, sec_y / total_h))
        except Exception:
            pass

    # ── service notifications & scheduling ────────────────────────────────────

    def _on_gf_notifications_toggle(self):
        notifs = dict(self.settings_manager.get_setting(
            "services_notifications", {}))
        notifs["gf_scraping"] = self._gf_notifications_var.get()
        self.settings_manager.set_setting("services_notifications", notifs)

    def _gf_service_notify(self, url: str, old_hash, new_hash: str,
                           count: int):
        """Вызывается при обнаружении изменений GF.Scraping (ручной или фоновый запуск).
        Всегда обновляет хэш; уведомляет только если данные реально изменились."""
        # Всегда обновляем сохранённый хэш
        hashes = dict(self.settings_manager.get_setting(
            "gf_scraping_hashes", {}))
        hashes[url] = new_hash
        self.settings_manager.set_setting("gf_scraping_hashes", hashes)

        # Обновляем «Последние изменения» — максимальный номер по каждому типу
        url_num = url.rstrip("/").split("/")[-1]
        if url_num.isdigit():
            page_type = ("okved" if "okved" in url.lower() else
                         "okpd"  if "okpd"  in url.lower() else None)
            if page_type:
                num    = int(url_num)
                latest = dict(self.settings_manager.get_setting("gf_scraping_latest", {}))
                if latest.get(page_type) is None or num > latest[page_type]:
                    latest[page_type] = num
                    self.settings_manager.set_setting("gf_scraping_latest", latest)
                self._update_gf_last_scan_display(latest)

        # Уведомляем только если хэш изменился (или первое сканирование не считается)
        if old_hash is None or old_hash == new_hash:
            return
        if not self._gf_notifications_var.get():
            return

        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        msg = (f"Обнаружены изменения в справочнике: {url}\n"
               f"Записей найдено: {count}")

        # Звук
        self._play_sound("service.wav", "service_notification")

        # Запись в «Уведомления»
        self._add_notification("GF. Scraping", message=msg, system=True)

        # Запись в «Логи»
        self.log_manager.add_log(
            f"[GF.Scraping] Изменения: {url} ({count} записей)", "INFO")
        self.after(100, self.refresh_logs)

        # Обновляем «Найдены изменения» — добавляем число из URL в найденные
        if url_num.isdigit():
            page_type = ("okved" if "okved" in url.lower() else
                         "okpd"  if "okpd"  in url.lower() else None)
            if page_type:
                found = dict(self.settings_manager.get_setting(
                    "gf_scraping_found_changes", {}))
                existing = found.get(page_type, [])
                if int(url_num) not in existing:
                    found[page_type] = [int(url_num)] + existing
                    self.settings_manager.set_setting(
                        "gf_scraping_found_changes", found)
                    self._update_gf_found_changes_display(found)

    # ── settings dialog ───────────────────────────────────────────────────────

    def _open_gf_service_settings(self):
        GFServiceSettingsDialog(
            self,
            settings_manager=self.settings_manager,
            on_saved=self._on_gf_sched_saved,
        )

    def _on_gf_sched_saved(self, sched: dict):
        """Вызывается после сохранения настроек расписания."""
        # Отменяем старые таймеры планировщика GF
        for attr in ("_gf_daily_after_id", "_gf_cal_after_id"):
            aid = getattr(self, attr, None)
            if aid is not None:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
            setattr(self, attr, None)
        self._gf_schedule_start()

    # ── background scheduler ──────────────────────────────────────────────────

    def _gf_schedule_start(self):
        """Инициализирует таймеры проверки изменений GF.Scraping на основе настроек."""
        # Таймеры работают только пока сервис активен
        if not self.settings_manager.get_setting(
                "services_active", {}).get("gf_scraping", False):
            return
        sched = self.settings_manager.get_setting("gf_sched", {})

        # Ежедневный (периодический) режим
        if sched.get("daily_enabled"):
            interval_min = max(1, int(sched.get("daily_interval_min", 60) or 60))
            self._gf_daily_after_id = self.after(
                interval_min * 60_000, self._gf_daily_tick)

        # Календарный режим
        if sched.get("calendar_enabled"):
            if sched.get("calendar_monthly"):
                # Ежемесячный: запуск по числам месяца в 00:00
                self._gf_schedule_next_monthly(sched)
            else:
                # Разовый: конкретная дата и время
                dt_str = sched.get("calendar_datetime", "")
                if dt_str:
                    try:
                        dt  = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                        now = datetime.datetime.now()
                        delay_ms = int((dt - now).total_seconds() * 1000)
                        if delay_ms > 0:
                            self._gf_cal_after_id = self.after(
                                delay_ms, self._gf_calendar_fire)
                    except Exception:
                        pass

    def _gf_schedule_next_monthly(self, sched=None):
        """Планирует следующий запуск в ежемесячном режиме (в 00:00 ближайшего числа из списка)."""
        if sched is None:
            sched = self.settings_manager.get_setting("gf_sched", {})
        days = sorted(set(sched.get("calendar_days", [])))
        if not days:
            return
        now = datetime.datetime.now()
        next_dt = None
        # Ищем в текущем месяце
        for day in days:
            try:
                candidate = now.replace(
                    day=day, hour=0, minute=0, second=0, microsecond=0)
                if candidate > now and (next_dt is None or candidate < next_dt):
                    next_dt = candidate
            except ValueError:
                pass
        # Если все числа текущего месяца прошли — ищем в следующем
        if next_dt is None:
            nm = now.month % 12 + 1
            ny = now.year + (1 if now.month == 12 else 0)
            for day in days:
                try:
                    candidate = datetime.datetime(ny, nm, day, 0, 0, 0)
                    if next_dt is None or candidate < next_dt:
                        next_dt = candidate
                except ValueError:
                    pass
        if next_dt:
            delay_ms = int((next_dt - now).total_seconds() * 1000)
            if delay_ms > 0:
                self._gf_cal_after_id = self.after(delay_ms, self._gf_monthly_fire)

    def _gf_active(self) -> bool:
        """Возвращает True если сервис GF.Scraping активен."""
        return self.settings_manager.get_setting(
            "services_active", {}).get("gf_scraping", False)

    def _gf_daily_tick(self):
        """Периодическая проверка изменений (ежедневный режим)."""
        if not self._gf_active():
            self._gf_daily_after_id = None
            return
        threading.Thread(target=self._gf_do_bg_check, daemon=True).start()
        self._gf_queue_sched_notif("daily")
        sched        = self.settings_manager.get_setting("gf_sched", {})
        interval_min = max(1, int(sched.get("daily_interval_min", 60) or 60))
        self._gf_daily_after_id = self.after(
            interval_min * 60_000, self._gf_daily_tick)

    def _gf_calendar_fire(self):
        """Однократный запуск проверки по расписанию календаря."""
        if not self._gf_active():
            return
        threading.Thread(target=self._gf_do_bg_check, daemon=True).start()
        self._gf_queue_sched_notif("calendar")
        # Отмечаем как выполненный (сбрасываем флаг)
        sched = dict(self.settings_manager.get_setting("gf_sched", {}))
        sched["calendar_enabled"] = False
        self.settings_manager.set_setting("gf_sched", sched)

    def _gf_monthly_fire(self):
        """Ежемесячный запуск проверки и перепланирование на следующее число."""
        self._gf_cal_after_id = None
        if not self._gf_active():
            return
        threading.Thread(target=self._gf_do_bg_check, daemon=True).start()
        self._gf_queue_sched_notif("calendar")
        self._gf_schedule_next_monthly()

    def _gf_queue_sched_notif(self, source: str):
        """Накапливает источники срабатывания расписания и объединяет в одно уведомление."""
        self._gf_pending_sched_sources.add(source)
        if self._gf_merge_notif_id is not None:
            try:
                self.after_cancel(self._gf_merge_notif_id)
            except Exception:
                pass
        # 2-секундное окно: если daily и calendar сработают почти одновременно — объединяем
        self._gf_merge_notif_id = self.after(2000, self._gf_flush_sched_notif)

    def _gf_flush_sched_notif(self):
        """Отправляет объединённое уведомление о выполнении расписания."""
        self._gf_merge_notif_id = None
        sources = self._gf_pending_sched_sources.copy()
        self._gf_pending_sched_sources.clear()
        if not sources:
            return

        svc = "GF. Scraping"
        now = datetime.datetime.now()
        date_str = now.strftime("%d.%m.%Y")
        time_str = now.strftime("%H:%M")

        daily_msg = (f"Обновление данных сервиса {svc} произведено по ежедневному графику "
                     f"{date_str} {time_str}")
        cal_msg   = (f"Обновление данных сервиса {svc} произведено по календарному графику "
                     f"{date_str} {time_str}")

        if "daily" in sources and "calendar" in sources:
            msg = f"{daily_msg} и {cal_msg}"
        elif "daily" in sources:
            msg = daily_msg
        else:
            msg = cal_msg

        self.log_manager.add_log(f"[GF.Scraping] {msg}", "INFO")
        if self._is_sound_type_enabled("service_notification"):
            notif_title = f"Обновление данных сервиса {svc}"
            nid = self._add_notification(notif_title, message=msg, system=True)
            self._show_alert_toast(notif_title, msg, notif_id=nid)
            self._play_sound("service.wav", "service_notification")
        self.after(100, self.refresh_logs)

    def _gf_do_bg_check(self):
        """Фоновый поток: проверяет индексные страницы ОКВЭД и ОКПД на новые номера.

        Уважает self._gf_stop_event: завершается досрочно при отмене сервиса или
        закрытии приложения, не дожидаясь окончания 11-секундного интервала.
        """
        results = {}
        for page_type in ("okved", "okpd"):
            # Проверяем сигнал отмены перед каждым сетевым запросом
            if self._gf_stop_event.is_set():
                return

            url = f"https://classifikators.ru/updates/{page_type}"
            lbl = "ОКВЭД" if page_type == "okved" else "ОКПД"
            try:
                self.after(0, lambda u=url:
                    self.log_manager.add_log(
                        f"[GF.Scraping] Фоновая проверка: запрос {u}", "INFO"))
                self.after(100, self.refresh_logs)
            except Exception:
                return

            _gf_timeout = int(self.settings_manager.get_setting(
                "gf_scraping_state", {}).get("timeout", 15))
            numbers = _gf_fetch_latest_numbers(page_type, timeout=_gf_timeout)

            if self._gf_stop_event.is_set():
                return

            if numbers:
                results[page_type] = numbers
                try:
                    self.after(0, lambda l=lbl, n=numbers:
                        self.log_manager.add_log(
                            f"[GF.Scraping] {l}: получено {len(n)} номеров, "
                            f"макс={max(n)}, мин={min(n)}", "INFO"))
                except Exception:
                    pass
            else:
                try:
                    self.after(0, lambda l=lbl, u=url:
                        self.log_manager.add_log(
                            f"[GF.Scraping] {l}: таблица не найдена или пустая — {u}",
                            "WARNING"))
                except Exception:
                    pass
            try:
                self.after(200, self.refresh_logs)
            except Exception:
                pass

            if page_type == "okved":
                # Прерываемый sleep: выходим раньше если поступил сигнал отмены
                if self._gf_stop_event.wait(11):
                    return

        if self._gf_stop_event.is_set():
            return

        ts = datetime.datetime.now().strftime("%H:%M %d.%m.%Y")
        try:
            self.after(0, lambda t=ts: self._update_gf_last_check(t))
            if results:
                self.after(0, lambda r=results: self._gf_process_bg_results(r))
            else:
                self.after(0, lambda:
                    self.log_manager.add_log(
                        "[GF.Scraping] Фоновая проверка: данные не получены", "WARNING"))
            self.after(300, self.refresh_logs)
        except Exception:
            pass

    def _gf_process_bg_results(self, results: dict):
        """Обрабатывает результаты фоновой проверки в главном потоке.

        Сравнивает с gf_scraping_latest (значения из «Последние изменения»
        — устанавливаются только ручным парсингом через _gf_service_notify).
        """
        latest = dict(self.settings_manager.get_setting("gf_scraping_latest", {}))
        found  = dict(self.settings_manager.get_setting("gf_scraping_found_changes", {}))
        has_new = False

        for page_type, numbers in results.items():
            lbl       = "ОКВЭД" if page_type == "okved" else "ОКПД"
            saved_max = latest.get(page_type)

            if saved_max is None:
                # Первое обнаружение — фиксируем базовую точку, found_changes не трогаем.
                # Базовую точку устанавливает только ручной парсинг («Запустить парсинг»);
                # фоновый мониторинг не должен показывать «найденными» номера старше baseline.
                baseline = max(numbers)
                latest[page_type] = baseline
                self.settings_manager.set_setting("gf_scraping_latest", latest)
                self._update_gf_last_scan_display(latest)
                self.log_manager.add_log(
                    f"[GF.Scraping] {lbl}: базовая точка установлена автоматически → {baseline}",
                    "INFO")
                continue

            new_nums = sorted([n for n in numbers if n > saved_max], reverse=True)
            self.log_manager.add_log(
                f"[GF.Scraping] {lbl}: базовый макс={saved_max}, "
                f"новые: {new_nums if new_nums else 'нет'}", "INFO")

            if new_nums:
                has_new = True
                found[page_type] = new_nums
                # Обновляем baseline чтобы следующая проверка не показывала те же числа повторно
                new_max = max(new_nums)
                if latest.get(page_type, 0) < new_max:
                    latest[page_type] = new_max
                    self.settings_manager.set_setting("gf_scraping_latest", latest)
                    self._update_gf_last_scan_display(latest)
            # else: новых нет — found_changes не трогаем

        # Сохраняем актуальное состояние и всегда обновляем отображение
        self.settings_manager.set_setting("gf_scraping_found_changes", found)
        self._update_gf_found_changes_display(found)

        if not has_new:
            self.after(100, self.refresh_logs)
            return

        # Toast + уведомление
        now   = datetime.datetime.now()
        title = (f"Обновление данных сервиса GF. Scraping "
                 f"произведено {now.strftime('%d.%m.%Y')} {now.strftime('%H:%M')}")
        parts = []
        for pt in ("okved", "okpd"):
            nums = found.get(pt)
            if not nums:
                continue
            lbl_pt = "ОКВЭД" if pt == "okved" else "ОКПД"
            parts.append(f"{lbl_pt}: {', '.join(str(n) for n in sorted(nums[:10]))}")
        detail = "Обнаружены новые изменения в справочниках: " + ", ".join(parts)

        self.log_manager.add_log(f"[GF.Scraping] {detail}", "INFO")
        if self._is_sound_type_enabled("service_notification"):
            nid = self._add_notification(title, message=detail, system=True)
            self._show_alert_toast(title, detail, notif_id=nid)
            self._play_sound("service.wav", "service_notification")

        self.after(100, self.refresh_logs)

    # ── display helpers ───────────────────────────────────────────────────────

    def _update_gf_found_changes_display(self, found_changes: dict):
        """Обновляет блок «Найдены изменения» на карточке GF.Scraping."""
        self._gf_refresh_header_widget_text()
        if not hasattr(self, "_gf_found_container"):
            return
        for w in self._gf_found_container.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        if not found_changes:
            return
        import webbrowser as _wb
        # Все типы в ОДНУ горизонтальную строку (side="left") чтобы не
        # выходить за пределы r1 с фиксированной высотой _LH=14px.
        first = True
        for page_type in ("okved", "okpd"):
            nums = found_changes.get(page_type)
            if not nums:
                continue
            label_name = "ОКВЭД" if page_type == "okved" else "ОКПД"
            nums_str   = ", ".join(str(n) for n in sorted(nums[:10]))
            link_url   = f"https://classifikators.ru/updates/{page_type}/"
            # разделитель между типами
            if not first:
                ctk.CTkLabel(self._gf_found_container, text="  ",
                             font=ctk.CTkFont(size=14)).pack(side="left")
            first = False
            ctk.CTkLabel(self._gf_found_container, text=f"{label_name}: ",
                         font=ctk.CTkFont(size=14),
                         text_color=("gray20", "white")).pack(side="left")
            nums_lbl = ctk.CTkLabel(
                self._gf_found_container, text=nums_str,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=("#0D9488", "#22C55E"),
                cursor="hand2")
            nums_lbl.pack(side="left")
            nums_lbl.bind("<Button-1>",
                          lambda e, u=link_url: _wb.open(u))
            ctx = tk.Menu(self, tearoff=0)
            ctx.add_command(
                label="Копировать",
                command=lambda t=nums_str: (
                    self.clipboard_clear(), self.clipboard_append(t)))
            nums_lbl.bind("<Button-3>",
                          lambda e, m=ctx: m.tk_popup(e.x_root, e.y_root))

    def _gf_populate_header_labels(self, frame: "ctk.CTkFrame", found: dict):
        """Заполняет фрейм шапки: ОКВЭД/ОКПД белым, номера зелёным."""
        for w in frame.winfo_children():
            w.destroy()
        _fnt   = ctk.CTkFont(size=14)
        _white = ("gray10", "white")
        _green = ("#0D9488", "#22C55E")
        parts = []
        for key, lbl in (("okved", "ОКВЭД"), ("okpd", "ОКПД")):
            nums = found.get(key)
            if nums:
                parts.append((lbl, ", ".join(str(n) for n in sorted(nums[:5]))))
        if not parts:
            ctk.CTkLabel(frame, text="нет данных", font=_fnt,
                         text_color=_white).pack(side="left")
            return
        for i, (lbl, nums_str) in enumerate(parts):
            if i > 0:
                ctk.CTkLabel(frame, text=" | ", font=_fnt,
                             text_color=_white).pack(side="left")
            ctk.CTkLabel(frame, text=f"{lbl}: ", font=_fnt,
                         text_color=_white).pack(side="left")
            ctk.CTkLabel(frame, text=nums_str, font=_fnt,
                         text_color=_green).pack(side="left")

    def _gf_refresh_header_widget_text(self):
        if not getattr(self, "_gf_header_frame", None):
            return
        try:
            found = self.settings_manager.get_setting("gf_scraping_found_changes", {})
            self._gf_populate_header_labels(self._gf_header_frame, found)
        except Exception:
            pass

    def _gf_format_latest(self, latest: dict) -> str:
        """Форматирует dict {okved: N, okpd: M} → 'ОКВЭД N, ОКПД M'."""
        parts = []
        if latest.get("okved") is not None:
            parts.append(f"ОКВЭД {latest['okved']}")
        if latest.get("okpd") is not None:
            parts.append(f"ОКПД {latest['okpd']}")
        return ", ".join(parts)

    def _gf_populate_latest_labels(self, frame, latest: dict):
        for w in frame.winfo_children():
            w.destroy()
        parts = []
        if latest.get("okved") is not None:
            parts.append(("ОКВЭД ", str(latest["okved"])))
        if latest.get("okpd") is not None:
            parts.append(("ОКПД ", str(latest["okpd"])))
        _fn = ctk.CTkFont(size=14)
        _fb = ctk.CTkFont(size=14, weight="bold")
        _tc = ("gray10", "white")
        for i, (prefix, num) in enumerate(parts):
            if i > 0:
                ctk.CTkLabel(frame, text=", ", font=_fn, text_color=_tc).pack(side="left")
            ctk.CTkLabel(frame, text=prefix, font=_fn, text_color=_tc).pack(side="left")
            ctk.CTkLabel(frame, text=num, font=_fb, text_color=_tc).pack(side="left")
        if not parts:
            ctk.CTkLabel(frame, text="—", font=_fn,
                         text_color=("gray50", "gray60")).pack(side="left")

    def _update_gf_last_scan_display(self, latest: dict):
        if not hasattr(self, "_gf_latest_frame"):
            return
        self._gf_populate_latest_labels(self._gf_latest_frame, latest)

    def _update_gf_last_check(self, ts: str):
        """Сохраняет и отображает время последней проверки изменений."""
        self.settings_manager.set_setting("gf_scraping_last_check", ts)
        if hasattr(self, "_gf_last_check_lbl"):
            self._gf_last_check_lbl.configure(text=ts)

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
                ctk.CTkButton(
                    tbl,
                    text="Не прочитано",
                    width=110, height=26,
                    fg_color="transparent",
                    border_width=1,
                    border_color=("gray55", "gray45"),
                    hover_color=("gray80", "gray30"),
                    text_color=("gray50", "gray60"),
                    command=lambda nid=notif["id"]: self._mark_notif_unread(nid),
                ).grid(row=r, column=4, padx=6, pady=3)
            else:
                ctk.CTkButton(
                    tbl,
                    text="◎ Прочитать",
                    width=110, height=26,
                    fg_color=[theme_colors.accent(), theme_colors.hover()],
                    hover_color=[theme_colors.hover(), theme_colors.dark()],
                    command=lambda nid=notif["id"]: self._mark_notif_read(nid),
                ).grid(row=r, column=4, padx=6, pady=3)

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
