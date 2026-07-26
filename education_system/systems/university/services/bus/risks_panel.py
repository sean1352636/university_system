"""Reusable Tk widget for showing risks linked to a reference_id.

Used by module-scheduling, trip-management, course-management,
research, and student-affairs GUIs as a single read-side window onto
the cross-domain risk register. Pure read — wraps
``risk_bus.list_risks_for``.

Usage::

    from education_system.systems.university.services.bus.risks_panel \
        import show_risks_for
    show_risks_for(parent_window, reference_id="module:CS101",
                   title="Risks for CS101")
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox

logger = logging.getLogger(__name__)


_STATUS_COLORS = {
    "Open":   "#a00",
    "open":   "#a00",
    "case_closed": "#070",
    "closed": "#070",
    "review": "#a60",
}


def show_risks_for(parent: tk.Misc, reference_id: str,
                   *, title: str | None = None) -> None:
    """Open a Toplevel listing every risks row linked to
    ``reference_id`` (e.g. ``module:CS101``, ``trip:42``,
    ``course:CS-BSC``). Read-only."""
    if not reference_id:
        messagebox.showwarning("Risks", "No reference id supplied.")
        return
    try:
        from education_system.systems.university.services.bus import (
            risk_bus,
        )
    except Exception as exc:
        messagebox.showerror("Risks", f"risk_bus unavailable: {exc}")
        return

    rows = risk_bus.list_risks_for(reference_id) or []

    win = tk.Toplevel(parent)
    win.title(title or f"Risks — {reference_id}")
    win.geometry("780x420")
    try:
        win.transient(parent.winfo_toplevel())
    except Exception:
        pass

    header = ttk.Frame(win, padding=10)
    header.pack(fill="x")
    ttk.Label(
        header,
        text=f"Risk register entries for {reference_id}",
        font=("TkDefaultFont", 11, "bold"),
    ).pack(side="left")
    ttk.Label(header,
              text=f"({len(rows)} row(s))",
              foreground="#555").pack(side="left", padx=8)

    if not rows:
        ttk.Label(
            win,
            text=("No risks raised against this reference. "
                  "Risks raised by cases_bus / cohort attendance / "
                  "trip-bus / research-bus that name this id will "
                  "appear here."),
            wraplength=720, foreground="#666",
            padding=20,
        ).pack(fill="x")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)
        return

    cols = ("id", "title", "category", "status", "score",
            "owner", "review", "expires")
    tv = ttk.Treeview(win, columns=cols, show="headings", height=14)
    widths = {"id": 50, "title": 240, "category": 90, "status": 80,
              "score": 60, "owner": 100, "review": 100, "expires": 100}
    headings = {"id": "ID", "title": "Title", "category": "Category",
                "status": "Status", "score": "L×I", "owner": "Owner",
                "review": "Next review", "expires": "Expires"}
    for c in cols:
        tv.heading(c, text=headings[c])
        tv.column(c, width=widths[c], anchor="w")
    tv.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    for r in rows:
        score = (int(r.get("likelihood") or 0)
                 * int(r.get("impact") or 0))
        status = str(r.get("status") or "")
        tv.insert("", "end", values=(
            r.get("id"), r.get("title"), r.get("category"),
            status, score, r.get("owner") or "—",
            r.get("next_review_date") or "—",
            r.get("expires_at") or "—",
        ), tags=(status.lower(),))
    for status, color in _STATUS_COLORS.items():
        try:
            tv.tag_configure(status.lower(), foreground=color)
        except Exception:
            pass

    ttk.Button(win, text="Close",
               command=win.destroy).pack(pady=8)


__all__ = ["show_risks_for"]
