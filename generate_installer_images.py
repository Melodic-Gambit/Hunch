"""
Generates installer BMP images for Inno Setup (FEAT-07).
  installer_banner.bmp  — 164x314 px  — left panel on Welcome/Finish pages
  installer_small.bmp   —  55x58  px  — top-right corner on other pages

Run standalone:  python generate_installer_images.py
Called by build.ps1 before the Inno Setup step.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

# ── Brand colors ──────────────────────────────────────────────────────────────
BG       = (28, 28, 30)       # #1C1C1E  dark background
TEAL     = (13, 148, 136)     # #0D9488  accent
TEAL_D   = (11, 122, 114)     # #0B7A72  hover
WHITE    = (255, 255, 255)
GRAY     = (160, 160, 170)

# ── Font helpers ──────────────────────────────────────────────────────────────
_FONT_PATHS = [
    r"C:\Windows\Fonts\segoeuib.ttf",   # Segoe UI Bold
    r"C:\Windows\Fonts\segoeui.ttf",
]
_FONT_REG_PATHS = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def _font(size: int, bold: bool = True):
    paths = _FONT_PATHS if bold else _FONT_REG_PATHS
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _center_x(draw, text, font, total_width: int, offset_x: int = 0) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return (total_width - (bb[2] - bb[0])) // 2 + offset_x - bb[0]


def _text_h(draw, text, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


# ── Banner (164 x 314) ────────────────────────────────────────────────────────
def make_banner(path: str, width: int = 164, height: int = 314) -> None:
    img  = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    STRIP   = 6          # left teal accent strip width
    TOP_H   = 88         # teal header block height
    BOT_H   = 4          # teal footer strip height

    # ── teal header block ──────────────────────────────────────────────────────
    draw.rectangle([0, 0, width, TOP_H], fill=TEAL)

    # large "H" centred in header
    f_h = _font(52, bold=True)
    tx  = _center_x(draw, "H", f_h, width, STRIP // 2)
    bb  = draw.textbbox((0, 0), "H", font=f_h)
    ty  = (TOP_H - (bb[3] - bb[1])) // 2 - bb[1]
    draw.text((tx, ty), "H", fill=WHITE, font=f_h)

    # ── left accent strip (over whole height, under header colour) ─────────────
    draw.rectangle([0, TOP_H, STRIP - 1, height], fill=TEAL)

    # ── "Hunch" title ──────────────────────────────────────────────────────────
    f_title = _font(20, bold=True)
    y_title = TOP_H + 18
    tx = _center_x(draw, "Hunch", f_title, width, STRIP // 2)
    draw.text((tx, y_title), "Hunch", fill=WHITE, font=f_title)

    # ── tagline ────────────────────────────────────────────────────────────────
    f_tag   = _font(10, bold=False)
    tagline = "Мониторинг данных"
    y_tag   = y_title + _text_h(draw, "Hunch", f_title) + 8
    tx = _center_x(draw, tagline, f_tag, width, STRIP // 2)
    draw.text((tx, y_tag), tagline, fill=TEAL_D, font=f_tag)

    # ── horizontal separator ───────────────────────────────────────────────────
    y_sep = y_tag + _text_h(draw, tagline, f_tag) + 14
    draw.rectangle([STRIP + 8, y_sep, width - 10, y_sep + 1], fill=TEAL_D)

    # ── bottom teal footer ─────────────────────────────────────────────────────
    draw.rectangle([0, height - BOT_H, width, height], fill=TEAL)

    img.save(path, "BMP")
    print(f"  installer_banner.bmp  created ({width}x{height}): {path}")


# ── Small image (55 x 58) ─────────────────────────────────────────────────────
def make_small(path: str, width: int = 55, height: int = 58) -> None:
    img  = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    PAD = 4
    # teal rounded inner square
    draw.rectangle([PAD, PAD, width - PAD, height - PAD], fill=TEAL)

    f = _font(28, bold=True)
    tx = _center_x(draw, "H", f, width)
    bb = draw.textbbox((0, 0), "H", font=f)
    ty = (height - (bb[3] - bb[1])) // 2 - bb[1]
    draw.text((tx, ty), "H", fill=WHITE, font=f)

    img.save(path, "BMP")
    print(f"  installer_small.bmp   created ({width}x{height}):  {path}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    make_banner(os.path.join(out_dir, "installer_banner.bmp"))
    make_small(os.path.join(out_dir, "installer_small.bmp"))
