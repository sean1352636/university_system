"""Small presentation widgets ported from the UniGuard prototype.

Colour is reserved for risk here, the way the prototype used it: a red row
means the same thing on the dashboard, in the case list and in the register.
Everything else stays in the portal's existing neutral palette so these drop
into the current screens without restyling them.
"""

import logging
import tkinter as tk
import tkinter.font as tkfont

logger = logging.getLogger(__name__)

# Portal palette (matches the existing safeguarding screens).
INK = "#1f3a5f"
INK_SOFT = "#4a5461"
LINE = "#d8dde3"
SURFACE = "#ffffff"
CANVAS_BG = "#f4f6fa"
ACCENT = "#2b6a72"

# Severity → (row background, row foreground). Softer than the solid
# SEVERITY_COLOUR fills so long lists stay readable.
RISK_ROW_COLOURS = {
    "CRITICAL": ("#fadcdc", "#8f1d1d"),
    "HIGH": ("#fde9dd", "#8a3d10"),
    "MEDIUM": ("#fdf3dd", "#7a5410"),
    "LOW": ("#e8f3ec", "#1f5c38"),
    "NONE": ("#eef1f4", "#4a5461"),
}


def preferred_font(widget) -> str:
    """First installed family from the prototype's preference order."""
    try:
        available = set(tkfont.families(widget))
    except tk.TclError:
        return "TkDefaultFont"
    for family in (
        "Segoe UI",
        "SF Pro Text",
        "Helvetica Neue",
        "Inter",
        "Ubuntu",
        "DejaVu Sans",
        "Helvetica",
        "Arial",
    ):
        if family in available:
            return family
    return "TkDefaultFont"


def configure_risk_tags(tree) -> None:
    """Tag a Treeview for risk-coloured rows.

    Adds one tag per severity plus ``closed`` (greyed) and ``BREACH``. Safe
    to call on a tree that already has ``SEVERITY_COLOUR`` tags — the names
    here are lowercase, so they do not collide.
    """
    for severity, (background, foreground) in RISK_ROW_COLOURS.items():
        tree.tag_configure(
            severity.lower(), background=background, foreground=foreground
        )
    tree.tag_configure("closed", foreground="#8a929c")
    tree.tag_configure("breach", background="#5b0011", foreground="white")


def row_tag(severity, status=None, breached=False) -> str:
    """Pick the single tag a case row should carry."""
    if breached:
        return "breach"
    if (status or "") == "Closed":
        return "closed"
    return (severity or "NONE").lower()


class StatCard(tk.Frame):
    """A single number with a caption beneath it."""

    def __init__(self, master, caption, value="0", accent=INK, font="Segoe UI"):
        super().__init__(
            master,
            bg=SURFACE,
            highlightbackground=LINE,
            highlightthickness=1,
            padx=18,
            pady=14,
        )
        self.value_lbl = tk.Label(
            self,
            text=str(value),
            bg=SURFACE,
            fg=accent,
            font=(font, 26, "bold"),
            anchor="w",
        )
        self.value_lbl.pack(anchor="w")
        tk.Label(
            self,
            text=str(caption).upper(),
            bg=SURFACE,
            fg=INK_SOFT,
            font=(font, 8),
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

    def set(self, value) -> None:
        self.value_lbl.config(text=str(value))


class BarChart(tk.Canvas):
    """Horizontal bar chart on a plain Canvas — no plotting dependency.

    Feed it ``[(label, count), ...]``; it redraws itself on resize.
    """

    def __init__(
        self,
        master,
        height=280,
        accent=ACCENT,
        font="Segoe UI",
        label_width=168,
        empty_text="No data to display.",
        **kw,
    ):
        super().__init__(
            master, bg=SURFACE, highlightthickness=0, height=height, **kw
        )
        self._accent = accent
        self._font = font
        self._label_width = label_width
        self._empty_text = empty_text
        self._data = []
        self.bind("<Configure>", lambda _e: self._draw())

    def set_data(self, data) -> None:
        self._data = list(data or [])
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        if not self._data:
            self.create_text(
                14,
                20,
                anchor="w",
                fill=INK_SOFT,
                font=(self._font, 9),
                text=self._empty_text,
            )
            return

        width = max(self.winfo_width(), 320)
        largest = max(n for _label, n in self._data) or 1
        bar_h, gap, top = 16, 12, 8
        label_w = self._label_width
        track = max(width - label_w - 40, 60)

        for i, (label, n) in enumerate(self._data):
            y = top + i * (bar_h + gap)
            text = label if len(label) <= 26 else label[:24].rstrip() + "…"
            self.create_text(
                0,
                y + bar_h / 2,
                anchor="w",
                text=text,
                fill=INK_SOFT,
                font=(self._font, 8),
            )
            length = max(int(track * n / largest), 3)
            self.create_rectangle(
                label_w, y, label_w + track, y + bar_h, fill=CANVAS_BG, outline=""
            )
            self.create_rectangle(
                label_w, y, label_w + length, y + bar_h, fill=self._accent, outline=""
            )
            self.create_text(
                label_w + length + 8,
                y + bar_h / 2,
                anchor="w",
                text=str(n),
                fill=INK,
                font=(self._font, 8, "bold"),
            )


__all__ = [
    "ACCENT",
    "BarChart",
    "CANVAS_BG",
    "INK",
    "INK_SOFT",
    "LINE",
    "RISK_ROW_COLOURS",
    "SURFACE",
    "StatCard",
    "configure_risk_tags",
    "preferred_font",
    "row_tag",
]
