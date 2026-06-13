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

class RosterService:
    """Roster views, search, group management, export."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #11 ----------------------------------------------------------
    @safe("Roster photos")
    def show_roster_with_contacts(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT s.student_id,
                          TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')),
                          COALESCE(s.email_address,''),
                          COALESCE(s.emergency_contact,'')
                   FROM student_modules sm
                   JOIN students s ON s.student_id = sm.student_id
                   WHERE sm.module_code=?
                   ORDER BY s.last_name""", (mc,)).fetchall()
        except sqlite3.Error:
            logger.exception("roster fetch failed mc=%s", mc)
            rows = []
        _show_table(self.ctx.parent, f"Roster — {mc}",
                    ("student_id", "name", "email", "emergency contact"),
                    rows, widths=[110, 240, 280, 260])

    # --- #12 ----------------------------------------------------------
    @safe("Search my students")
    def search_my_students(self) -> None:
        q = Prompt.non_empty(self.ctx.parent, "Search",
                             "Keyword:", min_len=2)
        if not q:
            return
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules to search.",
                                parent=self.ctx.parent)
            return
        like = f"%{q}%"
        placeholders = ",".join("?" * len(mine))
        try:
            rows = self.ctx.db.cur.execute(
                f"""SELECT DISTINCT s.student_id,
                           TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')),
                           s.email_address
                    FROM students s
                    JOIN student_modules sm ON sm.student_id = s.student_id
                    WHERE sm.module_code IN ({placeholders})
                      AND (s.student_id LIKE ? OR s.first_name LIKE ?
                           OR s.last_name LIKE ? OR s.email_address LIKE ?)""",
                (*mine, like, like, like, like)).fetchall()
        except sqlite3.Error:
            logger.exception("student search failed q=%s", q)
            rows = []
        _show_table(self.ctx.parent, f"Matches for '{q}' ({len(rows)})",
                    ("student_id", "name", "email"), rows,
                    widths=[110, 260, 300])

    # --- #13 ----------------------------------------------------------
    @safe("Filter by risk")
    def filter_students_by_risk(self) -> None:
        lvl = _combo_dialog(self.ctx.parent, "Risk", "Risk level:",
                            ["high", "medium", "low"])
        if not lvl:
            return
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            rows = self.ctx.db.cur.execute(
                f"""SELECT DISTINCT s.student_id,
                           TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')),
                           r.risk_level, r.risk_score
                    FROM student_risk_assessment r
                    JOIN students s ON s.student_id = r.student_id
                    JOIN student_modules sm ON sm.student_id = s.student_id
                    WHERE sm.module_code IN ({ph}) AND r.risk_level=?
                    ORDER BY r.risk_score DESC""",
                (*mine, lvl)).fetchall()
        except sqlite3.Error:
            logger.exception("risk filter query failed")
            rows = []
        _show_table(self.ctx.parent,
                    f"{lvl.title()} risk in my modules ({len(rows)})",
                    ("student", "name", "risk", "score"), rows)

    # --- #14 ----------------------------------------------------------
    @safe("Groups")
    def manage_module_groups(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        win = tk.Toplevel(self.ctx.parent)
        win.title(f"Groups — {mc}")
        win.geometry("640x420")
        tree = ttk.Treeview(win, columns=("id", "name", "members"),
                            show="headings")
        for c, w in zip(("id", "name", "members"), (60, 220, 360)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            try:
                tree.delete(*tree.get_children())
                for gid, name in self.ctx.db.cur.execute(
                        "SELECT id, name FROM abs_tracker_groups WHERE module_code=?",
                        (mc,)):
                    cnt = self.ctx.db.cur.execute(
                        "SELECT COUNT(*) FROM abs_tracker_group_members WHERE group_id=?",
                        (gid,)).fetchone()[0]
                    tree.insert("", "end",
                                values=(gid, name, f"{cnt} members"))
            except sqlite3.Error:
                logger.exception("group refresh failed")

        def add_group():
            name = Prompt.non_empty(win, "Group", "Group name:", min_len=1)
            if not name:
                return
            try:
                self.ctx.db.cur.execute(
                    """INSERT OR IGNORE INTO abs_tracker_groups
                       (module_code, name) VALUES (?,?)""",
                    (mc, name))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("group insert failed")
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "staff.group_add", "abs_tracker_groups", mc, name)
            refresh()

        def add_member():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select", "Pick a group first.", parent=win)
                return
            gid = tree.item(sel[0])["values"][0]
            sid = Prompt.non_empty(win, "Student", "Student ID:", min_len=1)
            if not sid:
                return
            try:
                self.ctx.db.cur.execute(
                    """INSERT OR IGNORE INTO abs_tracker_group_members
                       (group_id, student_id) VALUES (?,?)""", (gid, sid))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("group member insert failed")
                messagebox.showerror("Failed", str(e), parent=win)
                return
            refresh()

        bar = tk.Frame(win); bar.pack(fill="x", pady=6)
        tk.Button(bar, text="➕ Group", command=add_group, bg="#16a34a",
                  fg="white", relief="flat").pack(side="left", padx=6)
        tk.Button(bar, text="➕ Member", command=add_member, bg="#2563eb",
                  fg="white", relief="flat").pack(side="left", padx=6)
        refresh()

    # --- #15 ----------------------------------------------------------
    @safe("Roster export")
    def export_roster(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            rows = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Empty", "No students enrolled.",
                                parent=self.ctx.parent)
            return
        path = _export_rows_to_csv(
            rows, ("student_id", "name", "username", "email"),
            self.ctx.parent)
        if path:
            audit(self.ctx, "staff.roster_export", "students", mc, path)
            messagebox.showinfo("Exported",
                                f"{len(rows)} students → {path}",
                                parent=self.ctx.parent)
