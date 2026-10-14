"""Chart and stat widgets, ported from the standalone Research Portal.

Plain Canvas drawing rather than a plotting dependency — the portal is
Tkinter-only and matplotlib is not in the production lock.
"""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

import tkinter.font as tkfont


class BarChart(tk.Canvas):
    """Horizontal bar chart that redraws itself on resize.

    Feed it ``[(label, value)]`` or ``[(label, value, colour)]``.
    """

    def __init__(self, master, height=200, accent=None, empty_text="No data yet"):
        super().__init__(
            master,
            bg=PALETTE["panel"],
            highlightthickness=0,
            height=height,
        )
        self.accent = accent or PALETTE["accent"]
        self.empty_text = empty_text
        self.data = []
        self.formatter = lambda v: f"{v:,.0f}"
        self.bind("<Configure>", lambda _e: self._draw())

    def set_data(self, data, formatter=None):
        self.data = [
            (str(d[0]), float(d[1] or 0), d[2] if len(d) > 2 else self.accent)
            for d in (data or [])
        ]
        if formatter:
            self.formatter = formatter
        self._draw()

    def _draw(self):
        self.delete("all")
        width = self.winfo_width()
        if width < 60:
            return
        height = self.winfo_height()
        if not self.data:
            self.create_text(
                width / 2,
                height / 2,
                text=self.empty_text,
                fill=PALETTE["muted"],
                font=("Segoe UI", 10),
            )
            return

        label_w, value_w, gap = 168, 92, 6
        rows = len(self.data)
        bar_h = min(24, max(12, (height - 16 - gap * (rows - 1)) / rows))
        block_h = rows * bar_h + gap * (rows - 1)
        top = max(8, (height - block_h) / 2)
        track_w = max(width - label_w - value_w - 16, 40)
        peak = max(v for _l, v, _c in self.data) or 1

        small = ("Segoe UI", 9)
        metrics = tkfont.Font(font=small)
        max_text = label_w - 24

        for i, (label, value, colour) in enumerate(self.data):
            y = top + i * (bar_h + gap)
            mid = y + bar_h / 2
            text = label
            if metrics.measure(text) > max_text:
                while text and metrics.measure(text + "…") > max_text:
                    text = text[:-1]
                text += "…"
            self.create_text(
                label_w - 12, mid, text=text, anchor="e",
                fill=PALETTE["text"], font=small,
            )
            self.create_rectangle(
                label_w, y, label_w + track_w, y + bar_h,
                fill=PALETTE["accent_soft"], outline="",
            )
            if value > 0:
                length = max(3, track_w * (value / peak))
                self.create_rectangle(
                    label_w, y, label_w + length, y + bar_h,
                    fill=colour, outline="",
                )
            self.create_text(
                label_w + track_w + 10, mid, text=self.formatter(value),
                anchor="w", fill=PALETTE["muted"], font=small,
            )


class StatCard(tk.Frame):
    """A headline number with a caption, an optional note and a top strip.

    ``note`` is the prototype's second line — a qualifier such as
    "4 this year" that would be misleading folded into the caption.
    """

    def __init__(self, master, caption, value="0", note="", colour=None):
        super().__init__(
            master,
            bg=PALETTE["panel"],
            highlightbackground=PALETTE["border"],
            highlightthickness=1,
        )
        strip = tk.Frame(self, bg=colour or PALETTE["accent"], height=4)
        strip.pack(fill="x")
        inner = tk.Frame(self, bg=PALETTE["panel"])
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        self.value_lbl = tk.Label(
            inner, text=str(value), bg=PALETTE["panel"],
            fg=PALETTE["text"], font=("Segoe UI", 20, "bold"), anchor="w",
        )
        self.value_lbl.pack(anchor="w")
        tk.Label(
            inner, text=caption, bg=PALETTE["panel"],
            fg=PALETTE["muted"], font=("Segoe UI", 9), anchor="w",
        ).pack(anchor="w")
        self.note_lbl = tk.Label(
            inner, text=note, bg=PALETTE["panel"],
            fg=PALETTE["muted"], font=("Segoe UI", 8), anchor="w",
        )
        if note:
            self.note_lbl.pack(anchor="w")

    def set(self, value, note=None):
        self.value_lbl.config(text=str(value))
        if note is not None:
            self.note_lbl.config(text=note)
            if note and not self.note_lbl.winfo_ismapped():
                self.note_lbl.pack(anchor="w")
            elif not note:
                self.note_lbl.pack_forget()


def money(value) -> str:
    """Format a GBP amount the way the portal's reports do."""
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return "£0"
    return f"£{amount:,.0f}"


__all__ = ["BarChart", "StatCard", "money"]
