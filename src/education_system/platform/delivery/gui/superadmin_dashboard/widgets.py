"""Reusable card, scroll and sparkline widgets.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CARD_BG,
    CONTENT_BG,
    DEFAULT_SYSTEM_COLOR,
    SYSTEM_COLORS,
    TEXT_DARK,
    TEXT_MUTED,
)


class WidgetsMixin:
    # ------------------------------------------------------------------
    # Helper: scrollable frame
    # ------------------------------------------------------------------

    def _make_scrollable(self, parent):
        """Return a (canvas, scrollable_frame) tuple inside *parent*."""
        canvas = tk.Canvas(parent, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg=CONTENT_BG)

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux)

        return canvas, inner

    # ------------------------------------------------------------------
    # Helper: stat card
    # ------------------------------------------------------------------

    def _make_stat_card(self, parent, title, value, color=None, subtitle=None, width=160):
        card = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)
        if color:
            accent = tk.Frame(card, bg=color, height=4)
            accent.pack(fill=tk.X, side=tk.TOP)
        tk.Label(
            card,
            text=str(title),
            font=("Segoe UI", 9),
            bg=CARD_BG,
            fg=TEXT_MUTED,
        ).pack(padx=12, pady=(10, 0), anchor=tk.W)
        tk.Label(
            card,
            text=str(value),
            font=("Segoe UI", 22, "bold"),
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(padx=12, anchor=tk.W)
        if subtitle:
            tk.Label(
                card,
                text=str(subtitle),
                font=("Segoe UI", 8),
                bg=CARD_BG,
                fg=TEXT_MUTED,
            ).pack(padx=12, pady=(0, 8), anchor=tk.W)
        else:
            tk.Frame(card, bg=CARD_BG, height=8).pack()
        return card

    # ------------------------------------------------------------------
    # Helper: system card with status
    # ------------------------------------------------------------------

    def _make_system_card(self, parent, info):
        """Build a card for a system using a health info dict."""
        sys_key = info.get("system", "")
        color = SYSTEM_COLORS.get(sys_key, DEFAULT_SYSTEM_COLOR)
        label = info.get("label", sys_key.title())

        card = tk.Frame(parent, bg=CARD_BG, relief=tk.RAISED, bd=1)

        # Color accent bar
        accent = tk.Frame(card, bg=color, height=6)
        accent.pack(fill=tk.X, side=tk.TOP)

        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        # Title row with status dot
        title_row = tk.Frame(body, bg=CARD_BG)
        title_row.pack(fill=tk.X)

        tk.Label(
            title_row,
            text=label,
            font=("Segoe UI", 12, "bold"),
            bg=CARD_BG,
            fg=TEXT_DARK,
        ).pack(side=tk.LEFT)

        status = info.get("status", "offline")
        dot_color = "#2ecc71" if status == "online" else (
            "#e74c3c" if status == "error" else "#95a5a6"
        )
        dot = tk.Canvas(title_row, width=14, height=14, bg=CARD_BG, highlightthickness=0)
        dot.create_oval(2, 2, 12, 12, fill=dot_color, outline="")
        dot.pack(side=tk.RIGHT)

        # Stats
        stats = [
            ("Students", info.get("student_count", 0)),
            ("Staff", info.get("staff_count", 0)),
            ("DB Size", f"{info.get('db_size_mb', 0)} MB"),
        ]
        for stat_label, stat_val in stats:
            row = tk.Frame(body, bg=CARD_BG)
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row,
                text=stat_label,
                font=("Segoe UI", 9),
                bg=CARD_BG,
                fg=TEXT_MUTED,
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=str(stat_val),
                font=("Segoe UI", 9, "bold"),
                bg=CARD_BG,
                fg=TEXT_DARK,
            ).pack(side=tk.RIGHT)

        # Hint that the card is openable
        tk.Label(
            body,
            text="Double-click to open  →",
            font=("Segoe UI", 8),
            bg=CARD_BG,
            fg=TEXT_MUTED,
        ).pack(anchor=tk.W, pady=(6, 0))

        # Double-click anywhere on the card launches that system (same as the
        # Quick Launch section). Bind recursively because the card has nested
        # child widgets that would otherwise swallow the event.
        if sys_key:
            def _open(_e=None, sk=sys_key):
                self._launch_system(sk)

            def _bind_recursive(widget):
                widget.bind("<Double-Button-1>", _open)
                try:
                    widget.configure(cursor="hand2")
                except tk.TclError:
                    pass
                for child in widget.winfo_children():
                    _bind_recursive(child)

            _bind_recursive(card)

        return card

    def _draw_sparkline(self, parent, values, color, width=150, height=36):
        """Draw a small line chart of *values* onto a canvas and return it."""
        canvas = tk.Canvas(
            parent, width=width, height=height, bg=CARD_BG, highlightthickness=0,
        )
        canvas.pack(anchor=tk.W, pady=(4, 0))
        if len(values) < 2:
            return canvas

        vmin, vmax = min(values), max(values)
        span = (vmax - vmin) or 1
        n = len(values)
        pad = 4

        def point(i, v):
            x = pad + (width - 2 * pad) * i / (n - 1)
            y = (height - pad) - (height - 2 * pad) * (v - vmin) / span
            return x, y

        coords = []
        for i, v in enumerate(values):
            coords.extend(point(i, v))
        canvas.create_line(*coords, fill=color, width=2, smooth=True)

        lx, ly = point(n - 1, values[-1])
        canvas.create_oval(lx - 2.5, ly - 2.5, lx + 2.5, ly + 2.5,
                           fill=color, outline=color)
        return canvas
