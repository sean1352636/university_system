"""Shared plumbing for the office-hours screens: run a rule from
``university/application/teaching/office_hours`` in its own transaction, send the
emails it returns, and turn a refusal into a dialog."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

logger = logging.getLogger(__name__)
PAD = {"padx": 6, "pady": 3}


def call(fn, *args, write=False, parent=None, quiet_errors=(), **kwargs):
    """``fn(conn, ...)``; returns its result (True for None), or None after
    showing why it was refused. Exception types in *quiet_errors* are re-raised."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        if write:
            conn.commit()
    except quiet_errors:
        conn.rollback()
        raise
    except ValueError as exc:
        conn.rollback()
        messagebox.showerror("Office hours", str(exc), parent=parent)
        return None
    except Exception as exc:
        conn.rollback()
        logger.exception("office hours action failed")
        messagebox.showerror("Office hours", f"That did not work: {exc}", parent=parent)
        return None
    finally:
        conn.close()
    emails = result.get("emails") if isinstance(result, dict) else None
    if write and emails:
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def tree(parent, columns, widths, height=7):
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True, **PAD)
    view = ttk.Treeview(frame, columns=[c for c, _t in columns], show="headings", height=height)
    for (key, title), width in zip(columns, widths):
        view.heading(key, text=title)
        view.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=view.yview)
    view.configure(yscrollcommand=bar.set)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return view


def fill(view, rows, values, iid):
    view.delete(*view.get_children())
    for row in rows:
        view.insert("", tk.END, iid=str(iid(row)), values=values(row))


def selected(view):
    sel = view.selection()
    return sel[0] if sel else None


def username(auth):
    user = getattr(auth, "current_user", None) or {}
    if not isinstance(user, dict):
        user = {"username": getattr(user, "username", None), "role": getattr(user, "role", "")}
    return user.get("username") or "", str(user.get("role") or "").lower()


def where(row):
    mode = row.get("mode") or row.get("block_mode") or "in_person"
    if mode == "online":
        return "Online"
    if mode == "either":
        return f"{row.get('location')} or online"
    return row.get("location") or ""


def save_ics(parent, content, name="office-hours.ics"):
    from tkinter import filedialog
    path = filedialog.asksaveasfilename(parent=parent, defaultextension=".ics",
                                        filetypes=[("iCalendar", "*.ics")], initialfile=name)
    if path:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        messagebox.showinfo("Calendar", f"Saved to {path}", parent=parent)
