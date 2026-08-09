"""Extracted class implementation."""

from .. import taxi_booking_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ModernStyle:
    """Modern styling configuration"""

    # Color palette - Warm amber and slate theme
    BG_PRIMARY = "#1a1a2e"
    BG_SECONDARY = "#16213e"
    BG_CARD = "#0f3460"
    ACCENT = "#e94560"
    ACCENT_HOVER = "#ff6b6b"
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0aec0"
    SUCCESS = "#48bb78"
    WARNING = "#f6ad55"
    BORDER = "#2d3748"

    # Fonts
    FONT_FAMILY = "Segoe UI"
    FONT_TITLE = (FONT_FAMILY, 24, "bold")
    FONT_SUBTITLE = (FONT_FAMILY, 14, "bold")
    FONT_BODY = (FONT_FAMILY, 11)
    FONT_SMALL = (FONT_FAMILY, 10)
    FONT_BUTTON = (FONT_FAMILY, 11, "bold")
