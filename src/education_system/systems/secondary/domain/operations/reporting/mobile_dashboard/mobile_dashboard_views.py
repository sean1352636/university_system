"""Tkinter views for the Secondary School Mobile Dashboard.

The 'mobile' aspect is rendered as a phone-shaped column inside the
desktop window — tiles up top, scrolling feed below. Sticks to the
project's GUI conventions for window sizing (1400x900 / minsize 1200x800)
to match the other system windows.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform import branding
from education_system.systems.secondary.domain.operations.reporting.mobile_dashboard import (
    mobile_dashboard as data,
)
from education_system.systems.secondary.domain.operations.reporting.mobile_dashboard.mobile_dashboard import (
    FeedItem,
    Tile,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_PHONE_WIDTH = 380

_SEV_BG = {
    "info":  "#eceff1",
    "ok":    "#c8e6c9",
    "warn":  "#ffe0b2",
    "alert": "#ffcdd2",
}
_SEV_FG = {
    "info":  "#263238",
    "ok":    "#1b5e20",
    "warn":  "#bf360c",
    "alert": "#b71c1c",
}


def open_mobile_dashboard_window(parent=None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Mobile Dashboard — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    outer = ttk.Frame(win)
    outer.pack(fill="both", expand=True, padx=10, pady=10)

    bar = ttk.Frame(outer)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Mobile Dashboard",
                font=("TkDefaultFont", 14, "bold")).pack(side="left")
    refresh_btn = ttk.Button(bar, text="Refresh")
    refresh_btn.pack(side="right")
    status_lbl = ttk.Label(bar, text="")
    status_lbl.pack(side="right", padx=(0, 10))

    body = ttk.Frame(outer)
    body.pack(fill="both", expand=True)

    # Phone-shaped column (centered)
    phone = ttk.LabelFrame(body, text=" ▒ Mobile view ▒ ",
                              padding=8)
    phone.pack(side="left", fill="y", padx=(0, 10))
    phone.configure(width=_PHONE_WIDTH)

    tiles_frame = ttk.Frame(phone)
    tiles_frame.pack(fill="x")
    feed_canvas = tk.Canvas(phone, width=_PHONE_WIDTH - 24,
                              highlightthickness=0)
    feed_scroll = ttk.Scrollbar(phone, orient="vertical",
                                  command=feed_canvas.yview)
    feed_canvas.configure(yscrollcommand=feed_scroll.set)
    feed_canvas.pack(side="left", fill="both", expand=True, pady=(8, 0))
    feed_scroll.pack(side="right", fill="y", pady=(8, 0))
    feed_inner = ttk.Frame(feed_canvas)
    feed_window = feed_canvas.create_window((0, 0), window=feed_inner,
                                              anchor="nw")

    def _resize_feed(_e=None) -> None:
        feed_canvas.configure(scrollregion=feed_canvas.bbox("all"))
        feed_canvas.itemconfigure(feed_window,
                                    width=feed_canvas.winfo_width())
    feed_inner.bind("<Configure>", _resize_feed)
    feed_canvas.bind("<Configure>", _resize_feed)

    # Detail / full-feed panel on the right (desktop-side affordance)
    detail = ttk.LabelFrame(body, text="Detail",
                                padding=8)
    detail.pack(side="left", fill="both", expand=True)

    detail_nb = ttk.Notebook(detail)
    detail_nb.pack(fill="both", expand=True)

    def _make_feed_tab(label: str) -> tuple[ttk.Frame, tk.Listbox]:
        frame = ttk.Frame(detail_nb)
        detail_nb.add(frame, text=label)
        lb = tk.Listbox(frame, font=("TkFixedFont", 10),
                          activestyle="none")
        sb = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return frame, lb

    _, today_lb = _make_feed_tab("Today")
    _, upcoming_lb = _make_feed_tab("Upcoming")
    _, ann_lb = _make_feed_tab("Announcements")
    _, overdue_lb = _make_feed_tab("Overdue Targets")
    _, risk_lb = _make_feed_tab("High Risk")
    _, alerts_lb = _make_feed_tab("Alerts")

    def _render_tiles(tiles: list[Tile]) -> None:
        for w in tiles_frame.winfo_children():
            w.destroy()
        for i, t in enumerate(tiles):
            row, col = divmod(i, 2)
            cell = tk.Frame(tiles_frame,
                              bg=_SEV_BG.get(t.severity, "#eceff1"),
                              padx=8, pady=8, bd=1, relief="solid")
            cell.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
            tk.Label(cell, text=t.title, bg=cell["bg"],
                      fg=_SEV_FG.get(t.severity, "#263238"),
                      font=("TkDefaultFont", 9)).pack(anchor="w")
            tk.Label(cell, text=t.value, bg=cell["bg"],
                      fg=_SEV_FG.get(t.severity, "#263238"),
                      font=("TkDefaultFont", 18, "bold")
                      ).pack(anchor="w")
            if t.subtitle:
                tk.Label(cell, text=t.subtitle, bg=cell["bg"],
                          fg=_SEV_FG.get(t.severity, "#263238"),
                          font=("TkDefaultFont", 8)).pack(anchor="w")
        tiles_frame.columnconfigure(0, weight=1)
        tiles_frame.columnconfigure(1, weight=1)

    def _render_feed_strip(items: list[tuple[str, list[FeedItem]]]) -> None:
        """Stacked one-line feed shown in the phone column."""
        for w in feed_inner.winfo_children():
            w.destroy()
        for section, rows in items:
            hdr = tk.Label(feed_inner,
                            text=f"  {section}  ({len(rows)})",
                            font=("TkDefaultFont", 9, "bold"),
                            anchor="w", bg="#37474f", fg="white",
                            padx=4, pady=2)
            hdr.pack(fill="x", pady=(8, 0))
            if not rows:
                tk.Label(feed_inner, text="    (nothing)",
                          anchor="w",
                          font=("TkDefaultFont", 9),
                          fg="#607d8b").pack(fill="x")
                continue
            for it in rows[:5]:
                bg = _SEV_BG.get(it.severity, "#eceff1")
                fg = _SEV_FG.get(it.severity, "#263238")
                row = tk.Frame(feed_inner, bg=bg, padx=6, pady=3)
                row.pack(fill="x", pady=1)
                title = (it.when or "—")[:10] + "   " + it.title[:38]
                tk.Label(row, text=title, bg=bg, fg=fg,
                          anchor="w", justify="left",
                          font=("TkDefaultFont", 9, "bold")
                          ).pack(fill="x")
                if it.detail:
                    tk.Label(row, text=it.detail[:48], bg=bg, fg=fg,
                              anchor="w",
                              font=("TkDefaultFont", 8)).pack(fill="x")
            if len(rows) > 5:
                tk.Label(feed_inner,
                          text=f"    … and {len(rows) - 5} more",
                          anchor="w",
                          font=("TkDefaultFont", 8, "italic"),
                          fg="#607d8b").pack(fill="x")

    def _fill_listbox(lb: tk.Listbox, items: list[FeedItem]) -> None:
        lb.delete(0, "end")
        if not items:
            lb.insert("end", "  (nothing)")
            return
        for it in items:
            when = (it.when or "—")[:10]
            lb.insert("end", f"  {when}  {it.title}")
            if it.detail:
                lb.insert("end", f"            ↳ {it.detail}")

    def refresh() -> None:
        try:
            d = data.build_dashboard()
        except Exception as e:
            logger.exception("Mobile dashboard refresh failed")
            messagebox.showerror("Mobile Dashboard", str(e))
            return
        _render_tiles(d.tiles)
        _render_feed_strip([
            ("Today", d.today_events),
            ("Upcoming", d.upcoming_events),
            ("Announcements", d.announcements),
            ("Overdue Targets", d.overdue_targets),
            ("High Risk", d.high_risk_students),
            ("Alerts", d.open_alerts),
        ])
        _fill_listbox(today_lb, d.today_events)
        _fill_listbox(upcoming_lb, d.upcoming_events)
        _fill_listbox(ann_lb, d.announcements)
        _fill_listbox(overdue_lb, d.overdue_targets)
        _fill_listbox(risk_lb, d.high_risk_students)
        _fill_listbox(alerts_lb, d.open_alerts)
        status_lbl.configure(text=f"Generated {d.generated_on}")

    refresh_btn.configure(command=refresh)
    refresh()
