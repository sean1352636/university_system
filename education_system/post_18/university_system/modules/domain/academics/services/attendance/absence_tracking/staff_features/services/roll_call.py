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

from education_system.post_18.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
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

_DOW_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday",
              "Friday", "Saturday", "Sunday")
_DOW_INDEX = {n: i for i, n in enumerate(_DOW_NAMES)}


class RollCallService:
    """Take attendance, correct rolls, generate sessions, QR codes."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker,
                 staff_picker: StaffPicker) -> None:
        self.ctx = ctx
        self.picker = picker
        self.staff_picker = staff_picker

    # --- #1 -----------------------------------------------------------
    @safe("Today's classes")
    def show_today_dashboard(self) -> None:
        if self.ctx.require_uid() is None:
            return
        today = datetime.today().strftime("%A")
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ms.module_code, ms.start_time, ms.end_time, ms.room_id
                   FROM module_schedule ms
                   WHERE ms.instructor_id=? AND ms.day_of_week=?
                   ORDER BY ms.start_time""",
                (self.ctx.uid, today)).fetchall()
        except sqlite3.Error:
            logger.exception("today's classes fetch failed")
            messagebox.showerror("Error", "Could not load today's schedule.",
                                 parent=self.ctx.parent)
            return
        _show_table(self.ctx.parent, f"Today — {today}",
                    ("module", "start", "end", "room"), rows,
                    widths=[140, 100, 100, 120])
        audit(self.ctx, "staff.today", "module_schedule", self.ctx.uid, today)

    # --- #2 -----------------------------------------------------------
    @safe("Generate sessions")
    def generate_session_dates(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        start = Prompt.iso_date(self.ctx.parent, "From", "Start (YYYY-MM-DD):")
        if not start:
            return
        end = Prompt.iso_date(
            self.ctx.parent, "To", "End (YYYY-MM-DD):",
            initial=(date.today() + timedelta(days=84)).isoformat())
        if not end:
            return
        d0 = datetime.strptime(start, "%Y-%m-%d").date()
        d1 = datetime.strptime(end, "%Y-%m-%d").date()
        if d1 < d0:
            messagebox.showerror("Bad range",
                                 "End date is before start date.",
                                 parent=self.ctx.parent)
            return
        try:
            sched = self.ctx.db.cur.execute(
                "SELECT day_of_week, start_time FROM module_schedule "
                "WHERE module_code=?", (mc,)).fetchall()
        except sqlite3.Error:
            logger.exception("schedule fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load module schedule.",
                                 parent=self.ctx.parent)
            return
        out = []
        d = d0
        while d <= d1:
            for dow, t in sched:
                if d.weekday() == _DOW_INDEX.get(dow, -1):
                    out.append((d.isoformat(), mc, t))
            d += timedelta(days=1)
        _show_table(self.ctx.parent,
                    f"Upcoming sessions — {mc} ({len(out)})",
                    ("date", "module", "start"), out)

    # --- #3 -----------------------------------------------------------
    @safe("Session note")
    def add_session_note(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        note = Prompt.non_empty(self.ctx.parent, "Note", "Note:", min_len=2)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_session_notes
                   (staff_id, module_code, date, note) VALUES (?,?,?,?)""",
                (self.ctx.uid, mc, d, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("session note insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.note", "abs_tracker_session_notes",
              self.ctx.uid, f"{mc} {d}")
        messagebox.showinfo("Saved", "Session note saved.",
                            parent=self.ctx.parent)

    # --- #4 -----------------------------------------------------------
    @safe("Cancel session")
    def cancel_session(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, mlabel = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        reason = (simpledialog.askstring("Reason", "Reason:",
                                         parent=self.ctx.parent) or "Cancelled").strip()
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        if not Prompt.confirm(
                self.ctx.parent, "Confirm cancel",
                f"Cancel session?\n\nModule: {mlabel}\nDate: {d}\n"
                f"Will mark {len(roster)} student(s) excused."):
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_session_status
                   (module_code, date, status, set_by)
                   VALUES (?, ?, 'cancelled', ?)""",
                (mc, d, self.ctx.uid))
            for sid, *_ in roster:
                self.ctx.db.record_absence(sid, mc, d, "excused",
                                           f"[cancelled] {reason}")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("cancel session failed mc=%s d=%s", mc, d)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.cancel_session", "attendance", mc,
              f"{d} n={len(roster)}")
        messagebox.showinfo("Cancelled",
                            f"Session on {d} cancelled; "
                            f"{len(roster)} student(s) excused.",
                            parent=self.ctx.parent)

    # --- #5 -----------------------------------------------------------
    @safe("Substitute mode")
    def substitute_for_colleague(self) -> None:
        picked = self.staff_picker.pick("Substitute for", "Instructor:")
        if not picked:
            return
        their_uid, their_label = picked
        try:
            their_mods = self.ctx.db.get_courses(staff_id=their_uid)
        except Exception:
            logger.exception("colleague modules lookup failed uid=%s", their_uid)
            their_mods = []
        if not their_mods:
            messagebox.showinfo("No modules",
                                f"{their_label} has no modules.",
                                parent=self.ctx.parent)
            return
        mm = {f"{r[1]} - {r[2]}": r[0] for r in their_mods}
        mod_pick = _combo_dialog(self.ctx.parent, "Module",
                                 "Module:", list(mm.keys()))
        if not mod_pick:
            return
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        try:
            roster = self.ctx.db.get_course_students(mm[mod_pick])
        except Exception:
            logger.exception("roster fetch failed")
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        try:
            for sid, *_ in roster:
                self.ctx.db.record_absence(
                    sid, mm[mod_pick], d, "present",
                    f"[sub by {self.ctx.username}]")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("substitute mode failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.substitute", "attendance", their_uid,
              f"{mm[mod_pick]} {d} n={len(roster)}")
        messagebox.showinfo(
            "Recorded",
            f"Substituted for {their_label}: {len(roster)} marked present.",
            parent=self.ctx.parent)

    # --- #6 -----------------------------------------------------------
    @safe("All-present")
    def mark_all_present_except(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        excl = simpledialog.askstring(
            "Exclusions", "Student IDs absent (comma-separated):",
            parent=self.ctx.parent) or ""
        except_ids = {x.strip() for x in excl.split(",") if x.strip()}
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        try:
            for sid, *_ in roster:
                status = "absent" if sid in except_ids else "present"
                self.ctx.db.record_absence(sid, mc, d, status, "quick roll")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("all-present roll failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        present_n = len(roster) - len(except_ids & {r[0] for r in roster})
        audit(self.ctx, "staff.all_present", "attendance", mc,
              f"{d} except={','.join(sorted(except_ids))}")
        messagebox.showinfo(
            "Saved",
            f"Marked {present_n} present, {len(roster) - present_n} absent.",
            parent=self.ctx.parent)

    # --- #7 -----------------------------------------------------------
    @safe("Late log")
    def log_late_arrival(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed")
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        if not roster:
            messagebox.showinfo("Empty", "No students enrolled.",
                                parent=self.ctx.parent)
            return
        rm = {f"{r[1]} ({r[0]})": r[0] for r in roster}
        pick = _combo_dialog(self.ctx.parent, "Late",
                             "Student:", list(rm.keys()))
        if not pick:
            return
        mins = simpledialog.askinteger("Minutes late", "Minutes late:",
                                       parent=self.ctx.parent,
                                       minvalue=1, maxvalue=120)
        if not mins:
            return
        try:
            self.ctx.db.record_absence(
                rm[pick], mc, date.today().isoformat(),
                "late", f"late {mins}m")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("late log insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.late", "attendance", rm[pick], f"{mc} {mins}m")
        messagebox.showinfo("Recorded", f"{pick}: late {mins}m.",
                            parent=self.ctx.parent)

    # --- #8 -----------------------------------------------------------
    @safe("Early leave")
    def log_early_leave(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed")
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        if not roster:
            messagebox.showinfo("Empty", "No students enrolled.",
                                parent=self.ctx.parent)
            return
        rm = {f"{r[1]} ({r[0]})": r[0] for r in roster}
        pick = _combo_dialog(self.ctx.parent, "Early-leave",
                             "Student:", list(rm.keys()))
        if not pick:
            return
        note = Prompt.non_empty(self.ctx.parent, "Reason",
                                "Reason:", min_len=2)
        if not note:
            return
        try:
            self.ctx.db.record_absence(
                rm[pick], mc, date.today().isoformat(),
                "late", f"early-leave: {note}")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("early-leave insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.early_leave", "attendance", rm[pick], note[:80])
        messagebox.showinfo("Recorded", "Early-leave logged.",
                            parent=self.ctx.parent)

    # --- #9 -----------------------------------------------------------
    @safe("QR code")
    def generate_session_qr(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        d = date.today().isoformat()
        code = secrets.token_hex(4).upper()
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_session_qr
                   (module_code, date, code) VALUES (?, ?, ?)""",
                (mc, d, code))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("qr insert failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.qr", "abs_tracker_session_qr", mc, code)
        messagebox.showinfo(
            "QR code",
            f"Share this self-check-in code with your class:\n\n"
            f"Module: {mc}\nDate: {d}\nCode: {code}",
            parent=self.ctx.parent)

    # --- #10 ----------------------------------------------------------
    @safe("Correct roll")
    def correct_roll_row(self) -> None:
        rid = simpledialog.askinteger("Row id", "Attendance row id to edit:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            row = self.ctx.db.cur.execute(
                "SELECT status, reason, module_code FROM attendance WHERE id=?",
                (rid,)).fetchone()
        except sqlite3.Error:
            logger.exception("attendance row lookup failed rid=%s", rid)
            messagebox.showerror("Error", "Could not load row.",
                                 parent=self.ctx.parent)
            return
        if not row:
            messagebox.showerror("Not found", f"Row {rid} missing.",
                                 parent=self.ctx.parent)
            return
        mine = set(self.picker.my_module_codes())
        if row[2] not in mine:
            messagebox.showerror("Not yours",
                                 "That row isn't on one of your modules.",
                                 parent=self.ctx.parent)
            return
        new_status = simpledialog.askstring(
            "Status", f"New status (was {row[0]}):",
            parent=self.ctx.parent) or row[0]
        new_reason = simpledialog.askstring(
            "Reason", f"New reason (was {row[1] or ''}):",
            parent=self.ctx.parent) or row[1]
        try:
            self.ctx.db.cur.execute(
                "UPDATE attendance SET status=?, reason=? WHERE id=?",
                (new_status, new_reason, rid))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("attendance update failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.correct", "attendance", rid,
              f"{row[0]}→{new_status}")
        messagebox.showinfo("Updated", "Row updated.", parent=self.ctx.parent)

