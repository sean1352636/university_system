"""Split from student_features.py — see package __init__.py for public API."""
from __future__ import annotations

import calendar
import csv
import functools
import json
import logging
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
    logger = configure_logging(name="absence_tracker.student")
except Exception:
    logger = logging.getLogger("absence_tracker.student")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from ..context import StudentContext, ensure_student_tables
from ..prefs import StudentPrefs
from ..gauge import GaugeThresholds, _load_gauge_thresholds
from ..timeline_filter import _TimelineFilter
from ..widgets.prompt import Prompt
from ..widgets.module_picker import ModulePicker
from ..widgets.calendar_window import _CalendarWindow
from ..widgets.wheel_bind import _bind_wheel, _unbind_wheel

class SocialService:
    """Study groups, peer note sharing, badges, weekly digest."""

    def __init__(self, ctx: StudentContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #36 -----------------------------------------------------------
    @safe("Find study group")
    def find_or_create_study_group(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, _ = picked
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS study_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_code TEXT, name TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            # Must match the canonical definition in
            # modules/domain/academics/study_matching/services/study_matching_service.py
            # — this stub previously created a 3-column table that
            # masked the real 7-column schema (membership_id PK,
            # role, joined_at, contribution_score, attendance_count).
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS study_group_members (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    role TEXT DEFAULT 'Member',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    contribution_score INTEGER DEFAULT 0,
                    attendance_count INTEGER DEFAULT 0,
                    FOREIGN KEY (group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
                    UNIQUE(group_id, student_id))""")
            rows = self.ctx.db.cur.execute(
                "SELECT id, name FROM study_groups WHERE module_code=?",
                (mcode,)).fetchall()
            if not rows:
                self.ctx.db.cur.execute(
                    "INSERT INTO study_groups (module_code, name) VALUES (?,?)",
                    (mcode, f"{mcode} Study Group"))
                gid = self.ctx.db.cur.lastrowid
            else:
                gid = rows[0][0]
            self.ctx.db.cur.execute(
                """INSERT OR IGNORE INTO study_group_members
                   (group_id, student_id) VALUES (?,?)""", (gid, sid))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.study_group", "study_group_members",
              sid, f"gid={gid} {mcode}")
        messagebox.showinfo("Joined", f"Joined study group #{gid}.",
                            parent=self.ctx.parent)

    # --- #37 -----------------------------------------------------------
    @safe("Note share")
    def share_or_browse_notes(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, _ = picked
        action = _combo_dialog(self.ctx.parent, "Action",
                               "Do what?", ["upload", "browse"])
        if not action:
            return
        if action == "upload":
            title = Prompt.non_empty(self.ctx.parent, "Title",
                                     "Notes title:", min_len=2)
            if not title:
                return
            d = Prompt.iso_date(self.ctx.parent, "Date", "Session date:")
            if not d:
                return
            path = filedialog.askopenfilename(parent=self.ctx.parent)
            if not path:
                return
            if not Path(path).is_file():
                messagebox.showerror("Missing", f"File not found:\n{path}",
                                     parent=self.ctx.parent)
                return
            try:
                self.ctx.db.cur.execute(
                    """INSERT INTO abs_tracker_note_share
                       (owner_id, module_code, date, file_path, title)
                       VALUES (?,?,?,?,?)""",
                    (sid, mcode, d, str(Path(path).resolve()), title))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
                return
            audit(self.ctx, "student.note_upload",
                  "abs_tracker_note_share", sid, title)
            messagebox.showinfo("Uploaded", "Notes shared.",
                                parent=self.ctx.parent)
        else:
            try:
                rows = self.ctx.db.cur.execute(
                    """SELECT date, title, owner_id, file_path
                       FROM abs_tracker_note_share
                       WHERE module_code=? ORDER BY date DESC""",
                    (mcode,)).fetchall()
            except sqlite3.Error:
                logger.exception("note browse failed")
                rows = []
            _show_table(self.ctx.parent, f"Shared notes — {mcode}",
                        ("date", "title", "owner", "path"), rows,
                        widths=[100, 260, 140, 360])

    # --- #38 -----------------------------------------------------------
    @safe("Attendance badge")
    def claim_attendance_badges(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                "SELECT date, status FROM attendance WHERE student_id=? ORDER BY date",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("badge fetch failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return
        longest = cur = 0
        for _d, st in rows:
            if st == "present":
                cur += 1
                longest = max(longest, cur)
            else:
                cur = 0
        badges: list[str] = []
        thresholds = [(5, "5-day streak"), (10, "10-day streak"),
                      (20, "20-day streak"), (30, "perfect month")]
        try:
            for thresh, badge in thresholds:
                if longest >= thresh:
                    badges.append(badge)
                    self.ctx.db.cur.execute(
                        """INSERT OR IGNORE INTO abs_tracker_student_badges
                           (student_id, badge) VALUES (?,?)""",
                        (sid, badge))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.badges", "abs_tracker_student_badges",
              sid, ",".join(badges))
        if badges:
            messagebox.showinfo("Badges", "You earned:\n" + "\n".join(badges),
                                parent=self.ctx.parent)
        else:
            messagebox.showinfo("Badges",
                                "No streak badges yet — keep showing up!",
                                parent=self.ctx.parent)

    # --- #39 -----------------------------------------------------------
    @safe("Weekly digest")
    def show_weekly_digest(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        since = (date.today() - timedelta(days=7)).isoformat()
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, module_code, status FROM attendance
                   WHERE student_id=? AND date >= ?
                   ORDER BY date DESC""", (sid, since)).fetchall()
        except sqlite3.Error:
            logger.exception("digest fetch failed")
            rows = []
        present = sum(1 for r in rows if r[2] == "present")
        absent = sum(1 for r in rows if r[2] == "absent")
        late = sum(1 for r in rows if r[2] == "late")
        win = tk.Toplevel(self.ctx.parent)
        win.title("Weekly digest")
        win.geometry("540x400")
        name = self.ctx.user.get("name", "—")
        tk.Label(win, text=f"Last 7 days — {name}",
                 font=("Arial", 13, "bold")).pack(pady=8)
        tk.Label(win, text=f"Present: {present} | Absent: {absent} | Late: {late}",
                 font=("Arial", 11)).pack(pady=4)
        lst = tk.Listbox(win)
        lst.pack(fill="both", expand=True, padx=10, pady=10)
        for d, mc, st in rows:
            lst.insert("end", f"{d}  {mc}  {st}")


# ===========================================================================
# AppealsService — features #40–#42
# ===========================================================================

