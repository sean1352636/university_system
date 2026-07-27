"""Tkinter view for the Daily Register (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``): a date entry + Load, a summary line and a Treeview of every active
child for that date (reusing the ``attendance_report`` domain via
``daily_register``). Not-marked rows show grey, absent/sick red, late amber.
Pick a status and "Set selected" to mark a child, or "Mark all present".
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.nursery.domain.academics.attendance.daily_register import (
    daily_register as data,
)

logger = logging.getLogger(__name__)


def open_manager(host) -> None:
    """Open the Daily Register in the GUI host's content pane."""
    try:
        host._clear_content()
        root = host.content_frame
        ttk.Label(root, text="Daily Register",
                  font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

        date_var = tk.StringVar(value=data.today())
        status_var = tk.StringVar(value=data.STATUSES[0])

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Date:").pack(side="left", padx=(0, 2))
        ttk.Entry(bar, textvariable=date_var, width=12).pack(side="left", padx=2)

        summary = ttk.Label(root, foreground="#555")

        cols = ("child", "room", "status", "arrival", "departure")
        tree = ttk.Treeview(root, columns=cols, show="headings", height=16)

        ttk.Button(bar, text="Load",
                   command=lambda: _refresh(tree, summary, date_var)).pack(
            side="left", padx=(10, 2))
        ttk.Button(bar, text="Refresh",
                   command=lambda: _refresh(tree, summary, date_var)).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Mark all present",
                   command=lambda: _mark_all(host, tree, summary, date_var)).pack(
            side="left", padx=2)

        summary.pack(anchor="w", pady=(0, 6))

        for c, label, w in [
            ("child", "Child", 200), ("room", "Room", 140),
            ("status", "Status", 100), ("arrival", "Arrival", 90),
            ("departure", "Departure", 90),
        ]:
            tree.heading(c, text=label)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("none", foreground="#888")
        tree.tag_configure("absent", foreground="#c0392b")
        tree.tag_configure("late", foreground="#b9770e")
        tree.pack(fill="both", expand=True, pady=(0, 8))

        setter = ttk.Frame(root)
        setter.pack(fill="x")
        ttk.Label(setter, text="Status:").pack(side="left", padx=(0, 2))
        ttk.Combobox(setter, textvariable=status_var, values=list(data.STATUSES),
                     width=12, state="readonly").pack(side="left", padx=2)
        ttk.Button(setter, text="Set selected",
                   command=lambda: _set_selected(
                       host, tree, summary, date_var, status_var)).pack(
            side="left", padx=4)

        _refresh(tree, summary, date_var)
        host.status_var.set("Daily register loaded")
    except Exception:
        logger.exception("open_manager (daily register) failed")
        try:
            messagebox.showerror(
                "Daily Register",
                "Could not open the Daily Register — see logs for details.",
                parent=getattr(host, "root", None))
        except Exception:
            logger.debug("Could not show error dialog", exc_info=True)


def _refresh(tree: ttk.Treeview, summary: ttk.Label,
             date_var: tk.StringVar) -> None:
    for i in tree.get_children():
        tree.delete(i)
    when = date_var.get()
    try:
        rows = data.register_for_date(when)
        s = data.day_summary(when)
    except data.ValidationError as e:
        messagebox.showerror("Daily Register", str(e))
        return
    except Exception:
        logger.exception("Could not refresh daily register")
        messagebox.showerror("Daily Register", "Could not load — see logs.")
        return
    for r in rows:
        st = r["status"]
        if st is None:
            tag = "none"
        elif st in ("absent", "sick"):
            tag = "absent"
        elif st == "late":
            tag = "late"
        else:
            tag = "ok"
        tree.insert("", "end", iid=r["pupil_id"], tags=(tag,), values=(
            r["name"], r["room"] or "-", st or "not marked",
            r["arrival_time"] or "-", r["departure_time"] or "-"))
    summary.config(text=(
        f"Present: {s['present']}   Late: {s['late']}   "
        f"Absent: {s['absent']}   Sick: {s['sick']}   "
        f"Holiday: {s['holiday']}   Not marked: {s['not_marked']}   "
        f"Total: {s['total']}"))


def _set_selected(host, tree: ttk.Treeview, summary: ttk.Label,
                  date_var: tk.StringVar, status_var: tk.StringVar) -> None:
    pid = tree.focus()
    if not pid:
        messagebox.showinfo("Daily Register", "Select a child to mark.",
                            parent=getattr(host, "root", None))
        return
    when = date_var.get()
    status = status_var.get()
    room = tree.set(pid, "room")
    try:
        data.mark(pid, when, status, room=None if room == "-" else room)
    except data.ValidationError as e:
        messagebox.showerror("Daily Register", str(e),
                             parent=getattr(host, "root", None))
        return
    _refresh(tree, summary, date_var)
    host.status_var.set(f"Marked {pid} {status} for {when}")


def _mark_all(host, tree: ttk.Treeview, summary: ttk.Label,
              date_var: tk.StringVar) -> None:
    when = date_var.get()
    try:
        count = data.mark_all_present(when)
    except data.ValidationError as e:
        messagebox.showerror("Daily Register", str(e),
                             parent=getattr(host, "root", None))
        return
    _refresh(tree, summary, date_var)
    host.status_var.set(f"Marked {count} unmarked child(ren) present for {when}")


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Daily Register",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open the Daily Register from the navigation menu."
              ).pack(anchor="w")
    return frame
