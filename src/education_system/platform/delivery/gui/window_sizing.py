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
# the desktop work area portably, so this is a deliberate estimate.
#
# The vertical 72px is real and needed: title bar plus a horizontal taskbar,
# the usual desktop layout. The horizontal figure is 0 because a *vertical*
# dock down one side is the unusual case, and reserving width for one that
# isn't there is not free — it leaves a visible strip of desktop down the
# right of every maximised-looking window, which is what it was previously
# doing on a 1366px display (window 1350 wide, 16px gap). A window that ends
# up marginally too wide for a side dock is the window manager's problem to
# resolve, and a far smaller annoyance than the gap.
SCREEN_INSET: tuple[int, int] = (0, 72)

# Never clamp below this. A window squeezed onto a very small display is
# already compromised; making it unusably narrow as well helps nobody.
FLOOR: tuple[int, int] = (640, 400)

# "1400x900", "1400x900+40+40", "+40+40" — size, position, or both.
#
# The offset value may itself be negative: centring maths like
# ``(screen_w - 1400) // 2`` on a 1366px display yields -17, and "%+d" style
# formatting turns that into "+-17". Tk accepts it, so this must too — it
# previously did not match, which meant the whole geometry (size included) was
# passed through with no clamping at all, on exactly the small displays the
# clamping exists for.
_GEOMETRY_RE = re.compile(r"^(?:(\d+)x(\d+))?((?:[+-]-?\d+){0,2})$")

# One "+x" or "-x" offset within a position string.
_OFFSET_RE = re.compile(r"([+-])(-?\d+)")

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


def clamp_position(position: str) -> str:
    """Pull a window back on screen if it was positioned off the top or left.

    Centring a window larger than the display gives negative offsets, which
    put the title bar and the first row of controls above the top of the
    screen where they cannot be clicked. A negative *offset from the left or
    top* is therefore clamped to zero.

    ``-x-y`` is left alone: in Tk that is not a negative position but the
    offset of the window's bottom-right corner from the screen's, which is a
    perfectly ordinary way to position a window.
    """
    if not position:
        return position

    def _fix(match: "re.Match[str]") -> str:
        sign, value = match.group(1), int(match.group(2))
        if sign == "+" and value < 0:
            return "+0"
        return f"{sign}{value}"

    return _OFFSET_RE.sub(_fix, position)


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


def center(win: "tk.Misc", width: int, height: int,
           minsize: "tuple[int, int] | None" = None) -> "tuple[int, int]":
    """Size *win* and place it in the middle of the screen, in one call.

    Setting only a size — ``win.geometry("1200x800")`` — leaves the position
    to whatever the window is currently thought to be, and a freshly created
    Toplevel is Tk's default 200x200. The window manager centres *that*, so
    the top-left corner lands near the middle of the display and a large
    window then hangs off the bottom-right. Passing size and position
    together, with the position computed from the clamped size, puts the
    window where it was meant to go.

    Returns the size actually applied.
    """
    width, height = clamp(win, int(width), int(height))
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    target = f"{width}x{height}+{x}+{y}"
    win.geometry(target)
    if minsize:
        win.minsize(*clamp(win, int(minsize[0]), int(minsize[1])))

    # Re-apply once the window has actually been realised.
    #
    # Before a window is mapped, a position is only a *request*. Window
    # managers routinely override it for a ``transient`` window — which every
    # dialog opened through ``make_toplevel`` is — placing it relative to its
    # owner instead, which is how these windows ended up in the bottom-right
    # corner. Setting the same geometry again after the window exists is
    # applied directly rather than negotiated, so it sticks.
    #
    # ``after_idle`` also puts this after the inner GUI's own constructor, so
    # a class that sets a size-only geometry on the window it was handed
    # cannot leave it somewhere else.
    def _reapply() -> None:
        try:
            if win.winfo_exists():
                win.geometry(target)
        except tk.TclError:
            pass

    try:
        win.after_idle(_reapply)
    except tk.TclError:
        pass
    return width, height


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
                position = clamp_position(position)
                if width and height:
                    width, height = clamp(self, width, height)
                    newGeometry = f"{width}x{height}{position}"
                elif position:
                    newGeometry = position
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
