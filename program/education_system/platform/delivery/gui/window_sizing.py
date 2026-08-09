"""Window geometry that respects the display it actually lands on.

The house convention across the systems is a 1400x900 window with a
1200x800 floor. That is right on a desktop monitor and wrong on a
laptop: on a 1366x768 screen the window opens 132 pixels taller than
the display, the bottom is never drawn, and — the part that turns an
annoyance into a fault — the ``minsize`` floor stops the user shrinking
the window to reach what fell off. Action buttons are packed last on
most screens, so what goes missing is the part that does the work. The
symptom users report is "the buttons aren't showing".

Ninety-odd windows hardcode a size larger than a 1366x768 screen, so
revising them one at a time would be a long sweep that the next
hardcoded ``geometry("1400x900")`` reopens. :func:`install` instead
wraps ``geometry`` and ``minsize`` once, at launcher startup, so every
window — including the ones nobody has opened in years — asks for its
preferred size and receives the largest size the screen can show.

Clamping only ever shrinks. On a display with room for the requested
size nothing here changes anything, which is what makes it safe to
apply globally rather than per window.
"""

from __future__ import annotations

import logging
import re
import tkinter as tk

logger = logging.getLogger(__name__)

# Room left for window furniture: the title bar the window manager draws
# above the frame, and a taskbar or dock along one edge. Tk cannot report
# the desktop work area portably, so this is a deliberate estimate — too
# generous by a few pixels costs nothing, too mean puts the buttons back
# under the taskbar.
SCREEN_INSET: tuple[int, int] = (16, 72)

# Never clamp below this. A window squeezed onto a very small display is
# already compromised; making it unusably narrow as well helps nobody.
FLOOR: tuple[int, int] = (640, 400)

# "1400x900", "1400x900+40+40", "+40+40" — size, position, or both.
_GEOMETRY_RE = re.compile(r"^(?:(\d+)x(\d+))?((?:[+-]\d+){0,2})$")

_installed = False
_original_geometry = None
_original_minsize = None


def usable_size(win: tk.Misc) -> tuple[int, int]:
    """The largest window the screen *win* is on can actually display."""
    try:
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
    except Exception:  # pragma: no cover - a window with no display
        return (0, 0)
    return (
        max(FLOOR[0], screen_w - SCREEN_INSET[0]),
        max(FLOOR[1], screen_h - SCREEN_INSET[1]),
    )


def clamp(win: tk.Misc, width: int, height: int) -> tuple[int, int]:
    """Shrink a requested size to what the screen can show."""
    usable_w, usable_h = usable_size(win)
    if not usable_w or not usable_h:
        return (width, height)
    return (min(width, usable_w), min(height, usable_h))


def fit(
    win: tk.Misc,
    geometry: str | None = None,
    minsize: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Apply a preferred *geometry* and *minsize*, both clamped to the screen.

    The explicit form, for code that would rather ask than rely on
    :func:`install` having been called. Returns the size actually applied.
    """
    applied = (0, 0)
    if geometry:
        parsed = _parse(geometry)
        if parsed is not None:
            width, height, position = parsed
            if width and height:
                applied = clamp(win, width, height)
                win.geometry(f"{applied[0]}x{applied[1]}{position}")
            elif position:
                win.geometry(position)
    if minsize:
        win.minsize(*clamp(win, minsize[0], minsize[1]))
    return applied


def install() -> None:
    """Clamp every ``geometry`` and ``minsize`` call to the screen.

    Both live on ``tk.Wm``, the window-manager mixin behind ``Tk`` and
    ``Toplevel``, and each has a ``wm_``-prefixed twin that is the same
    function under a second name. Both names are replaced, or code
    calling ``wm_geometry`` would quietly keep the unclamped version.

    Idempotent, so calling it from more than one entry point is safe.
    """
    global _installed, _original_geometry, _original_minsize
    if _installed:
        return

    _original_geometry = tk.Wm.wm_geometry
    _original_minsize = tk.Wm.wm_minsize

    def wm_geometry(self, newGeometry=None):  # noqa: N803 - matches Tk's signature
        # No argument is the getter; a position-only string carries no
        # size to clamp. Both pass straight through.
        if newGeometry is not None:
            parsed = _parse(newGeometry)
            if parsed is not None:
                width, height, position = parsed
                if width and height:
                    width, height = clamp(self, width, height)
                    newGeometry = f"{width}x{height}{position}"
        return _original_geometry(self, newGeometry)

    def wm_minsize(self, width=None, height=None):
        if width is not None and height is not None:
            width, height = clamp(self, int(width), int(height))
        return _original_minsize(self, width, height)

    tk.Wm.wm_geometry = tk.Wm.geometry = wm_geometry
    tk.Wm.wm_minsize = tk.Wm.minsize = wm_minsize
    _installed = True
    logger.debug("Window sizing clamped to the display")


def uninstall() -> None:
    """Restore Tk's own methods. For tests that assert on the raw behaviour."""
    global _installed
    if not _installed:
        return
    tk.Wm.wm_geometry = tk.Wm.geometry = _original_geometry
    tk.Wm.wm_minsize = tk.Wm.minsize = _original_minsize
    _installed = False


def _parse(geometry: object) -> tuple[int, int, str] | None:
    """Split a Tk geometry string into width, height and position.

    Returns None for anything unrecognised, which is then passed through
    untouched — a geometry this module does not understand is Tk's
    business, not something to guess at.
    """
    match = _GEOMETRY_RE.match(str(geometry).strip())
    if match is None:
        return None
    width, height, position = match.groups()
    return (int(width) if width else 0, int(height) if height else 0, position or "")
