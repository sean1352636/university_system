"""Split from staff_features.py — see package __init__.py for public API."""
from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.staff")
except Exception:
    logger = logging.getLogger("absence_tracker.staff")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from ..context import StaffContext, ensure_staff_tables
from ..prefs import StaffPrefs
from ..widgets.prompt import Prompt
from ..widgets.module_picker import ModulePicker
from ..widgets.staff_picker import StaffPicker

class ProductivityService:
    """Personal KPIs and to-do list."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #49 ----------------------------------------------------------
    @safe("My KPIs")
    def show_my_kpis(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No data.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            sessions = self.ctx.db.cur.execute(
                f"""SELECT COUNT(DISTINCT date) FROM attendance
                    WHERE module_code IN ({ph})""", mine).fetchone()[0]
            rolls = self.ctx.db.cur.execute(
                f"""SELECT COUNT(*) FROM attendance
                    WHERE module_code IN ({ph})""", mine).fetchone()[0]
            pending = self.ctx.db.cur.execute(
                f"""SELECT COUNT(*) FROM absence_requests
                    WHERE module_code IN ({ph}) AND status='pending'""",
                mine).fetchone()[0]
            decided = self.ctx.db.cur.execute(
                f"""SELECT AVG(julianday('now') - julianday(submitted_at))
                    FROM absence_requests
                    WHERE module_code IN ({ph}) AND status<>'pending'""",
                mine).fetchone()[0] or 0
        except sqlite3.Error:
            logger.exception("KPI fetch failed")
            messagebox.showerror("Error", "Could not compute KPIs.",
                                 parent=self.ctx.parent)
            return
        _show_table(self.ctx.parent, "My KPIs",
                    ("metric", "value"),
                    [("sessions held", sessions),
                     ("attendance rows", rolls),
                     ("pending requests", pending),
                     ("avg decision time (days)", f"{decided:.1f}")],
                    widths=[260, 200])

    # --- #50 ----------------------------------------------------------
    @safe("My to-do list")
    def show_my_todo_list(self) -> None:
        if self.ctx.require_uid() is None:
            return
        win = tk.Toplevel(self.ctx.parent)
        win.title("My to-do list")
        win.geometry("640x460")
        lst = ttk.Treeview(win, columns=("id", "task", "done", "when"),
                           show="headings")
        for c, w in zip(("id", "task", "done", "when"), (60, 400, 70, 160)):
            lst.heading(c, text=c)
            lst.column(c, width=w)
        lst.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            try:
                lst.delete(*lst.get_children())
                for row in self.ctx.db.cur.execute(
                        """SELECT id, task,
                                  CASE done WHEN 1 THEN '✓' ELSE '' END,
                                  COALESCE(done_at, created_at)
                           FROM abs_tracker_staff_tasks
                           WHERE staff_id=?
                           ORDER BY done, created_at DESC""",
                        (self.ctx.uid,)):
                    lst.insert("", "end", values=row)
            except sqlite3.Error:
                logger.exception("todo refresh failed")

        def add():
            t = Prompt.non_empty(win, "Task", "Task:", min_len=1)
            if not t:
                return
            try:
                self.ctx.db.cur.execute(
                    """INSERT INTO abs_tracker_staff_tasks (staff_id, task)
                       VALUES (?,?)""", (self.ctx.uid, t))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("todo insert failed")
                messagebox.showerror("Failed", str(e), parent=win)
                return
            refresh()

        def toggle():
            sel = lst.selection()
            if not sel:
                messagebox.showinfo("Select", "Pick a task first.",
                                    parent=win)
                return
            tid = lst.item(sel[0])["values"][0]
            try:
                self.ctx.db.cur.execute(
                    """UPDATE abs_tracker_staff_tasks
                       SET done = 1 - done,
                           done_at = CASE WHEN done = 0 THEN CURRENT_TIMESTAMP
                                          ELSE NULL END
                       WHERE id=?""", (tid,))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("todo toggle failed")
                messagebox.showerror("Failed", str(e), parent=win)
                return
            refresh()

        bar = tk.Frame(win); bar.pack(fill="x", pady=6)
        tk.Button(bar, text="➕ Add", command=add, bg="#16a34a", fg="white",
                  relief="flat", padx=10).pack(side="left", padx=6)
        tk.Button(bar, text="✓ Toggle", command=toggle, bg="#2563eb",
                  fg="white", relief="flat", padx=10
                  ).pack(side="left", padx=6)
        refresh()
