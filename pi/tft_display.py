"""ST7735 TFT status display -- big clock, status line underneath.

Uses a real TrueType font at a large size rather than PIL's tiny built-in
bitmap font, since the point of this display is to be readable across a
room, not just present.
"""
import config

try:
    from PIL import Image, ImageDraw, ImageFont
    import ST7735

    _disp = ST7735.ST7735(
        port=0, cs=ST7735.BG_SPI_CS_BACK,
        dc=config.TFT_DC_PIN, rst=config.TFT_RST_PIN,
        rotation=90, invert=False,
    )
    _disp.begin()
    _available = True
except Exception as e:
    print(f"[tft_display] ST7735 unavailable: {e}")
    _disp = None
    _available = False

_CLOCK_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _load_font(size):
    from PIL import ImageFont
    for path in _CLOCK_FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()  # last resort -- small, but never crashes


_clock_font = None
_status_font = None
_COLORS = {
    "SECURE": (0, 255, 140),
    "TAMPER ALERT!": (255, 60, 60),
    "SUCCESSFUL ENTRY": (0, 255, 140),
    "DEFAULT": (255, 255, 0),
}


def update(now, status_text="SECURE"):
    """Draws HH:MM:SS in large digits + a status line underneath."""
    if not _available:
        return
    global _clock_font, _status_font
    if _clock_font is None:
        _clock_font = _load_font(40)
        _status_font = _load_font(16)

    img = Image.new("RGB", (_disp.width, _disp.height), color=(10, 15, 30))
    draw = ImageDraw.Draw(img)

    time_str = now.strftime("%H:%M:%S")
    draw.text((10, 15), time_str, font=_clock_font, fill=(0, 220, 255))

    color = _COLORS.get(status_text, _COLORS["DEFAULT"])
    draw.text((10, 75), status_text, font=_status_font, fill=color)

    _disp.display(img)
