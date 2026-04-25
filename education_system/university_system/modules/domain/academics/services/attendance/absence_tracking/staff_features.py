"""
Staff / instructor features for the Absence Tracker.

Fifty-plus staff-facing utilities organised into service classes by domain:

    RollCallService               #1–10    take/correct attendance, sub mode, QR
    RosterService                 #11–15   roster views, search, groups, export
    RequestReviewService          #16–21   triage queue, decisions, SLA, routing
    AnalyticsService              #22–28   heatmap, drop-off, comparisons, profile
    CommunicationService          #29–34   email, announcements, parent outreach
    PastoralService               #35–39   pastoral flags, safeguarding, meetings
    AssessmentIntegrationService  #40–42   assignment / exam / lab safety links
    CollaborationService          #43–45   co-teacher, TA handoff, peer obs
    ConfigurationService          #46–48   policy, excuse range, seating chart
    ProductivityService           #49–50   personal KPIs, to-do list
    LeaveService                  #51      file a leave request

Every public method is wrapped with the shared ``@safe`` decorator (logged
traceback + friendly dialog) and additionally guards I/O and DB state-changes
with explicit ``try/except`` so a single bad row never leaves the connection
in a half-committed state. All output is routed through the central
``configure_logging`` helper so traceback lines land in
``university_system/logs/app.log`` alongside every other subsystem.
"""

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

# Route through the university system's central rotating file handler
# (logs/app.log) so this module's output joins every other subsystem's.
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="absence_tracker.staff")
except Exception:  # pragma: no cover — fall back if log_config unavailable
    logger = logging.getLogger("absence_tracker.staff")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)


# ===========================================================================
# Context + support tables
# ===========================================================================

@dataclass
class StaffContext:
    db: Any
    parent: tk.Misc
    user: dict

    @property
    def uid(self) -> int:
        return int(self.user.get("id") or 0)

    @property
    def username(self) -> str:
        return str(self.user.get("username") or "")

    def require_uid(self) -> Optional[int]:
        if not self.uid:
            messagebox.showerror(
                "Missing user id",
                "Your user account is not linked to a staff record.",
                parent=self.parent,
            )
            return None
        return self.uid


def ensure_staff_tables(db) -> None:
    """Create staff-side support tables if missing."""
    db.cur.executescript("""
        CREATE TABLE IF NOT EXISTS abs_tracker_session_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id   INTEGER, module_code TEXT, date TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_session_status (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, status TEXT,
            set_by      INTEGER, set_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(module_code, date)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_staff_prefs (
            user_id INTEGER, key TEXT, value TEXT,
            PRIMARY KEY (user_id, key)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, name TEXT, UNIQUE(module_code, name)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER, student_id TEXT, UNIQUE(group_id, student_id)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_session_qr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, code TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(module_code, date)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_staff_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, task TEXT, done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            done_at TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_intervention_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, student_id TEXT, action TEXT, outcome TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_peer_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observer_id INTEGER, subject_id INTEGER, module_code TEXT,
            date TEXT, notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_seating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, layout_json TEXT,
            UNIQUE(module_code, date)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_co_teachers (
            module_code TEXT, user_id INTEGER,
            PRIMARY KEY (module_code, user_id)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_ta_handoff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, ta_id INTEGER, module_code TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_request_route (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER, routed_to INTEGER, reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.conn.commit()


# ===========================================================================
# Preferences
# ===========================================================================

class StaffPrefs:
    """Typed accessor for per-user staff preferences."""

    def __init__(self, db) -> None:
        self.db = db

    def get(self, uid: int, key: str,
            default: Optional[str] = None) -> Optional[str]:
        try:
            r = self.db.cur.execute(
                "SELECT value FROM abs_tracker_staff_prefs WHERE user_id=? AND key=?",
                (uid, key)).fetchone()
            return r[0] if r else default
        except sqlite3.Error:
            logger.exception("StaffPrefs.get failed (uid=%s key=%s)", uid, key)
            return default

    def set(self, uid: int, key: str, value: Any) -> None:
        try:
            self.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_staff_prefs
                   (user_id, key, value) VALUES (?, ?, ?)""",
                (uid, key, str(value)))
            self.db.conn.commit()
        except sqlite3.Error:
            self.db.conn.rollback()
            logger.exception("StaffPrefs.set failed (uid=%s key=%s)", uid, key)
            raise


# ===========================================================================
# Dialog + validation helpers
# ===========================================================================

class Prompt:
    """Reusable Tk dialogs with validation."""

    @staticmethod
    def iso_date(parent, title: str = "Date",
                 prompt: str = "Date (YYYY-MM-DD):",
                 initial: Optional[str] = None) -> Optional[str]:
        initial = initial or date.today().isoformat()
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent,
                                       initialvalue=initial)
            if s is None:
                return None
            s = s.strip()
            try:
                datetime.strptime(s, "%Y-%m-%d")
                return s
            except ValueError:
                messagebox.showerror("Bad date",
                                     f"'{s}' is not a valid YYYY-MM-DD date.",
                                     parent=parent)
                initial = s

    @staticmethod
    def iso_datetime(parent, title: str, prompt: str,
                     initial: Optional[str] = None) -> Optional[str]:
        initial = initial or datetime.now().strftime("%Y-%m-%d %H:%M")
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent,
                                       initialvalue=initial)
            if s is None:
                return None
            s = s.strip()
            try:
                datetime.strptime(s, "%Y-%m-%d %H:%M")
                return s
            except ValueError:
                messagebox.showerror("Bad time",
                                     f"'{s}' is not 'YYYY-MM-DD HH:MM'.",
                                     parent=parent)
                initial = s

    @staticmethod
    def non_empty(parent, title: str, prompt: str,
                  min_len: int = 1) -> Optional[str]:
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent)
            if s is None:
                return None
            s = s.strip()
            if len(s) >= min_len:
                return s
            messagebox.showerror("Too short",
                                 f"Please give at least {min_len} character(s).",
                                 parent=parent)

    @staticmethod
    def confirm(parent, title: str, msg: str) -> bool:
        return bool(messagebox.askyesno(title, msg, parent=parent))


class ModulePicker:
    """Pick a module from the staff member's assigned list."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    def my_modules(self) -> list[tuple]:
        try:
            return self.ctx.db.get_courses(staff_id=self.ctx.uid) or []
        except Exception:
            logger.exception("get_courses failed for uid=%s", self.ctx.uid)
            return []

    def my_module_codes(self) -> list[str]:
        return [r[0] for r in self.my_modules()]

    def pick(self, prompt: str = "Pick one of your modules"
             ) -> Optional[tuple[str, str]]:
        mods = self.my_modules()
        if not mods:
            messagebox.showinfo("No modules",
                                "You are not assigned to any modules.",
                                parent=self.ctx.parent)
            return None
        m = {f"{r[1]} - {r[2]}": r[0] for r in mods}
        pick = _combo_dialog(self.ctx.parent, prompt, "Module:", list(m.keys()))
        if not pick:
            return None
        return m[pick], pick


class StaffPicker:
    """Pick another staff/instructor user."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    def pick(self, title: str, prompt: str,
             *, exclude_self: bool = True
             ) -> Optional[tuple[int, str]]:
        try:
            users = (self.ctx.db.get_users("instructor")
                     + self.ctx.db.get_users("staff"))
        except Exception:
            logger.exception("get_users failed")
            messagebox.showerror("Error", "Could not load staff list.",
                                 parent=self.ctx.parent)
            return None
        if not users:
            messagebox.showinfo("No staff", "No other staff users.",
                                parent=self.ctx.parent)
            return None
        m = {f"{r[3] or r[1]} ({r[1]})": r[0]
             for r in users
             if (not exclude_self) or r[0] != self.ctx.uid}
        if not m:
            messagebox.showinfo("No staff",
                                "No eligible staff users.",
                                parent=self.ctx.parent)
            return None
        pick = _combo_dialog(self.ctx.parent, title, prompt, list(m.keys()))
        if not pick:
            return None
        return m[pick], pick


# ===========================================================================
# RollCallService — features #1–#10
# ===========================================================================

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


# ===========================================================================
# RosterService — features #11–#15
# ===========================================================================

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


# ===========================================================================
# RequestReviewService — features #16–#21
# ===========================================================================

class RequestReviewService:
    """Triage queue, evidence preview, decisions, SLA, escalation."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    # --- #16 ----------------------------------------------------------
    @safe("Triage queue")
    def show_triage_queue(self) -> None:
        if self.ctx.require_uid() is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT r.id, r.student_id, r.module_code, r.date, r.reason,
                          r.submitted_at
                   FROM absence_requests r
                   JOIN instructor_modules im ON im.module_code = r.module_code
                   WHERE r.status='pending' AND im.instructor_id=?
                   ORDER BY r.submitted_at""",
                (self.ctx.uid,)).fetchall()
        except sqlite3.Error:
            logger.exception("triage queue fetch failed")
            messagebox.showerror("Error", "Could not load triage queue.",
                                 parent=self.ctx.parent)
            return
        _show_table(self.ctx.parent, f"Pending triage ({len(rows)})",
                    ("id", "student", "module", "date", "reason", "submitted"),
                    rows, widths=[60, 120, 110, 100, 320, 160])

    # --- #17 ----------------------------------------------------------
    @safe("Preview evidence")
    def preview_request_evidence(self) -> None:
        rid = simpledialog.askinteger("Request", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT file_path, uploaded_at
                   FROM abs_tracker_request_attachments WHERE request_id=?""",
                (rid,)).fetchall()
        except sqlite3.Error:
            logger.exception("evidence fetch failed rid=%s", rid)
            rows = []
        if not rows:
            messagebox.showinfo("None",
                                f"No evidence files for request {rid}.",
                                parent=self.ctx.parent)
            return
        _show_table(self.ctx.parent, f"Evidence for request {rid}",
                    ("path", "uploaded_at"), rows, widths=[560, 200])

    # --- #18 ----------------------------------------------------------
    @safe("Staff comment on decision")
    def decide_with_comment(self) -> None:
        rid = simpledialog.askinteger("Request", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        decision = _combo_dialog(self.ctx.parent, "Decision", "Decision:",
                                 ["approved", "rejected"])
        if not decision:
            return
        comment = Prompt.non_empty(self.ctx.parent, "Comment",
                                   "Staff comment:", min_len=3)
        if not comment:
            return
        try:
            self.ctx.db.update_request(rid, decision)
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_request_comments
                   (request_id, author, body) VALUES (?, ?, ?)""",
                (rid, self.ctx.username, comment))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("decision/comment failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.decision_comment", "absence_requests", rid,
              f"{decision}: {comment[:120]}")
        messagebox.showinfo("Done", f"Request {decision}.",
                            parent=self.ctx.parent)

    # --- #19 ----------------------------------------------------------
    @safe("Approve with modification")
    def approve_with_modification(self) -> None:
        rid = simpledialog.askinteger("Request", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            req = self.ctx.db.cur.execute(
                """SELECT student_id, module_code, date, reason
                   FROM absence_requests WHERE id=?""", (rid,)).fetchone()
        except sqlite3.Error:
            logger.exception("request fetch failed rid=%s", rid)
            messagebox.showerror("Error", "Could not load request.",
                                 parent=self.ctx.parent)
            return
        if not req:
            messagebox.showerror("Missing", "No such request.",
                                 parent=self.ctx.parent)
            return
        sid, mc, orig_date, reason = req
        new_date = Prompt.iso_date(self.ctx.parent, "Date",
                                   f"Date (was {orig_date}):",
                                   initial=orig_date) or orig_date
        new_status = _combo_dialog(
            self.ctx.parent, "Status", "Record as:",
            ["excused", "absent", "late", "present"]) or "excused"
        try:
            self.ctx.db.update_request(rid, "approved")
            self.ctx.db.record_absence(sid, mc, new_date, new_status,
                                       f"[Approved w/ mod] {reason}")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("approve-with-mod failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.approve_mod", "absence_requests", rid,
              f"{orig_date}→{new_date} {new_status}")
        messagebox.showinfo("Approved",
                            f"Approved; recorded as {new_status} on {new_date}.",
                            parent=self.ctx.parent)

    # --- #20 ----------------------------------------------------------
    @safe("SLA dashboard")
    def show_sla_dashboard(self) -> None:
        if self.ctx.require_uid() is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT r.id, r.student_id, r.module_code, r.submitted_at,
                          CAST((julianday('now') - julianday(r.submitted_at)) AS INT)
                   FROM absence_requests r
                   JOIN instructor_modules im ON im.module_code = r.module_code
                   WHERE r.status='pending' AND im.instructor_id=?
                   ORDER BY 5 DESC""", (self.ctx.uid,)).fetchall()
        except sqlite3.Error:
            logger.exception("SLA dashboard fetch failed")
            rows = []
        enriched = [
            (r[0], r[1], r[2], r[3], r[4],
             "BREACH" if r[4] >= 3 else "WARN" if r[4] >= 2 else "OK")
            for r in rows
        ]
        _show_table(self.ctx.parent, "Request SLA (target 3 days)",
                    ("id", "student", "module", "submitted", "age", "status"),
                    enriched)

    # --- #21 ----------------------------------------------------------
    @safe("Route to dept head")
    def route_to_department_head(self) -> None:
        rid = simpledialog.askinteger("Request", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            admins = self.ctx.db.get_users("admin")
        except Exception:
            logger.exception("admin lookup failed")
            admins = []
        if not admins:
            messagebox.showinfo("No admin", "No admin user to route to.",
                                parent=self.ctx.parent)
            return
        m = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in admins}
        pick = _combo_dialog(self.ctx.parent, "Route to",
                             "Route to:", list(m.keys()))
        if not pick:
            return
        reason = Prompt.non_empty(self.ctx.parent, "Reason",
                                  "Why escalate?", min_len=5)
        if not reason:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_request_route
                   (request_id, routed_to, reason) VALUES (?,?,?)""",
                (rid, m[pick], reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("route insert failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.route", "absence_requests", rid,
              f"→{m[pick]}: {reason[:80]}")
        messagebox.showinfo("Routed", f"Routed to {pick}.",
                            parent=self.ctx.parent)


# ===========================================================================
# AnalyticsService — features #22–#28
# ===========================================================================

class AnalyticsService:
    """Heatmap, drop-off detection, comparisons, profiles, correlations."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #22 ----------------------------------------------------------
    @safe("Heatmap")
    def show_my_heatmap(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            rows = self.ctx.db.cur.execute(
                f"""SELECT strftime('%Y-%W', date) AS week,
                           CASE strftime('%w', date)
                                WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue'
                                WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu'
                                WHEN '5' THEN 'Fri' END AS dow,
                           SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END)
                                AS absences
                    FROM attendance WHERE module_code IN ({ph})
                    GROUP BY week, dow
                    HAVING dow IS NOT NULL
                    ORDER BY week DESC""", mine).fetchall()
        except sqlite3.Error:
            logger.exception("heatmap query failed")
            rows = []
        _show_table(self.ctx.parent, "My modules — heatmap",
                    ("week", "day", "absences"), rows)

    # --- #23 ----------------------------------------------------------
    @safe("Drop-off")
    def show_dropoff_students(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        cutoff = (date.today() - timedelta(days=28)).isoformat()
        try:
            rows = self.ctx.db.cur.execute(
                f"""SELECT student_id, recent, prior
                    FROM (
                        SELECT student_id,
                               SUM(CASE WHEN status='present' AND date >= ?
                                        THEN 1 ELSE 0 END)*1.0 /
                                  NULLIF(SUM(CASE WHEN date >= ?
                                                  THEN 1 ELSE 0 END),0) * 100
                                  AS recent,
                               SUM(CASE WHEN status='present' AND date <  ?
                                        THEN 1 ELSE 0 END)*1.0 /
                                  NULLIF(SUM(CASE WHEN date <  ?
                                                  THEN 1 ELSE 0 END),0) * 100
                                  AS prior
                        FROM attendance
                        WHERE module_code IN ({ph})
                        GROUP BY student_id
                    )
                    WHERE recent IS NOT NULL AND prior IS NOT NULL
                      AND (prior - recent) > 20
                    ORDER BY (prior - recent) DESC""",
                (cutoff, cutoff, cutoff, cutoff, *mine)).fetchall()
        except sqlite3.Error:
            logger.exception("dropoff query failed")
            rows = []
        _show_table(self.ctx.parent, "Drop-off (>20%)",
                    ("student", "recent %", "prior %"),
                    [(s, f"{r:.1f}", f"{p:.1f}") for s, r, p in rows])

    # --- #24 ----------------------------------------------------------
    @safe("Compare my modules")
    def compare_my_modules(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            rows = self.ctx.db.cur.execute(
                f"""SELECT module_code,
                           SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100,
                           COUNT(*)
                    FROM attendance WHERE module_code IN ({ph})
                    GROUP BY module_code ORDER BY 2 DESC""", mine).fetchall()
        except sqlite3.Error:
            logger.exception("module comparison failed")
            rows = []
        _show_table(self.ctx.parent, "My modules compared",
                    ("module", "%", "sessions"),
                    [(m, f"{(p or 0):.1f}", n) for m, p, n in rows])

    # --- #25 ----------------------------------------------------------
    @safe("Historical cohort")
    def compare_terms_for_module(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            sems = self.ctx.db.cur.execute(
                """SELECT name, start_date, end_date FROM semesters
                   ORDER BY start_date DESC LIMIT 2""").fetchall()
        except sqlite3.Error:
            logger.exception("semesters fetch failed")
            sems = []
        out = []
        for name, s, e in sems:
            try:
                r = self.ctx.db.cur.execute(
                    """SELECT SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100
                       FROM attendance
                       WHERE module_code=? AND date BETWEEN ? AND ?""",
                    (mc, s, e)).fetchone()
            except sqlite3.Error:
                logger.exception("cohort query failed")
                r = (0,)
            out.append((name, s, e, f"{(r[0] or 0):.1f}"))
        _show_table(self.ctx.parent, f"{mc} — term compare",
                    ("semester", "start", "end", "%"), out)

    # --- #26 ----------------------------------------------------------
    @safe("Module report")
    def export_module_report(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            rows = self.ctx.db.get_absences(course_id=mc)
        except Exception:
            logger.exception("absences fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Empty", "No data for this module.",
                                parent=self.ctx.parent)
            return
        path = _export_rows_to_csv(
            rows, ("id", "student", "module_code", "module_name",
                   "date", "status", "reason"), self.ctx.parent)
        if path:
            audit(self.ctx, "staff.module_report", "attendance", mc, path)
            messagebox.showinfo("Saved",
                                f"Exported {len(rows)} rows → {path}",
                                parent=self.ctx.parent)

    # --- #27 ----------------------------------------------------------
    @safe("Student profile")
    def show_student_profile(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student ID",
                               "Student ID:", min_len=1)
        if not sid:
            return
        win = tk.Toplevel(self.ctx.parent)
        win.title(f"Profile — {sid}")
        win.geometry("920x620")
        nb = ttk.Notebook(win); nb.pack(fill="both", expand=True)
        try:
            sections = [
                ("Attendance",
                 self.ctx.db.cur.execute(
                    """SELECT date, module_code, status, COALESCE(reason,'')
                       FROM attendance WHERE student_id=?
                       ORDER BY date DESC""", (sid,)).fetchall(),
                 ("date", "module", "status", "reason")),
                ("Requests",
                 self.ctx.db.cur.execute(
                    """SELECT id, date, module_code, status, submitted_at
                       FROM absence_requests WHERE student_id=?
                       ORDER BY submitted_at DESC""", (sid,)).fetchall(),
                 ("id", "date", "module", "status", "submitted")),
                ("Risk",
                 self.ctx.db.cur.execute(
                    """SELECT assessment_date, risk_level, risk_score
                       FROM student_risk_assessment WHERE student_id=?
                       ORDER BY assessment_date DESC""", (sid,)).fetchall(),
                 ("date", "level", "score")),
            ]
        except sqlite3.Error:
            logger.exception("student profile fetch failed sid=%s", sid)
            messagebox.showerror("Error", "Could not load profile.",
                                 parent=win)
            return
        for label, rows, cols in sections:
            tab = ttk.Frame(nb); nb.add(tab, text=f"{label} ({len(rows)})")
            tree = ttk.Treeview(tab, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c)
                tree.column(c, width=180)
            tree.pack(fill="both", expand=True)
            for r in rows:
                tree.insert("", "end", values=r)
        audit(self.ctx, "staff.student_profile", "students", sid, "view")

    # --- #28 ----------------------------------------------------------
    @safe("Correlation")
    def show_attendance_vs_grade(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS student_grades (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT, module_code TEXT, grade TEXT)""")
            rows = self.ctx.db.cur.execute(
                f"""SELECT a.student_id, a.module_code,
                           SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100,
                           COALESCE((SELECT grade FROM student_grades g
                                     WHERE g.student_id=a.student_id
                                       AND g.module_code=a.module_code
                                     ORDER BY id DESC LIMIT 1),'')
                    FROM attendance a WHERE a.module_code IN ({ph})
                    GROUP BY a.student_id, a.module_code""", mine).fetchall()
        except sqlite3.Error:
            logger.exception("correlation query failed")
            rows = []
        _show_table(self.ctx.parent, "Attendance vs grade",
                    ("student", "module", "%", "grade"),
                    [(s, m, f"{(p or 0):.1f}", g) for s, m, p, g in rows])


# ===========================================================================
# CommunicationService — features #29–#34
# ===========================================================================

class CommunicationService:
    """Email, announcements, catch-ups, parent outreach, office hours."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #29 ----------------------------------------------------------
    @safe("Email student")
    def email_single_student(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student ID",
                               "Student ID:", min_len=1)
        if not sid:
            return
        subject = Prompt.non_empty(self.ctx.parent, "Subject",
                                   "Subject:", min_len=2)
        if not subject:
            return
        body = Prompt.non_empty(self.ctx.parent, "Body",
                                "Body:", min_len=2)
        if not body:
            return
        try:
            cur = self.ctx.db.cur.execute(
                """INSERT INTO emails (recipient, subject, body, sent_at, status)
                   SELECT email_address, ?, ?, CURRENT_TIMESTAMP, 'queued'
                   FROM students WHERE student_id=?""",
                (subject, body, sid))
            inserted = cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("email insert failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        if inserted == 0:
            messagebox.showwarning("Not found",
                                   f"No student record for '{sid}'.",
                                   parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.email", "emails", sid, subject[:80])
        messagebox.showinfo("Queued", "Email queued.",
                            parent=self.ctx.parent)

    # --- #30 ----------------------------------------------------------
    @safe("Email at-risk list")
    def email_at_risk_summary(self) -> None:
        to = simpledialog.askstring("Recipient", "Pastoral email:",
                                    parent=self.ctx.parent
                                    ) or "pastoral@university.edu"
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=75) or 75
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            # FIX: original used `HAVING 2 < ?` which is a literal-vs-literal
            # compare (always true if threshold>2). Aliased the aggregate so
            # the threshold actually filters by attendance percentage.
            rows = self.ctx.db.cur.execute(
                f"""SELECT student_id,
                           SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100 AS pct
                    FROM attendance WHERE module_code IN ({ph})
                    GROUP BY student_id
                    HAVING pct IS NOT NULL AND pct < ?""",
                (*mine, threshold)).fetchall()
        except sqlite3.Error:
            logger.exception("at-risk query failed")
            messagebox.showerror("Error", "Could not compute at-risk list.",
                                 parent=self.ctx.parent)
            return
        body = f"At-risk students (<{threshold:.0f}%):\n" + "\n".join(
            f"  {sid}: {p:.1f}%" for sid, p in rows)
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO emails (recipient, subject, body, sent_at, status)
                   VALUES (?, 'At-risk attendance', ?,
                           CURRENT_TIMESTAMP, 'queued')""", (to, body))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("at-risk email insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.email_at_risk", "emails", to, f"n={len(rows)}")
        messagebox.showinfo("Queued",
                            f"Emailed summary of {len(rows)} student(s) to {to}.",
                            parent=self.ctx.parent)

    # --- #31 ----------------------------------------------------------
    @safe("Announcement")
    def post_module_announcement(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        msg = Prompt.non_empty(self.ctx.parent, "Announcement",
                               "Message:", min_len=2)
        if not msg:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS announcements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_code TEXT, content TEXT,
                    author_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                """INSERT INTO announcements (module_code, content, author_id)
                   VALUES (?,?,?)""", (mc, msg, self.ctx.uid))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("announcement insert failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.announce", "announcements", mc, msg[:80])
        messagebox.showinfo("Posted", "Announcement posted.",
                            parent=self.ctx.parent)

    # --- #32 ----------------------------------------------------------
    @safe("Catch-up message")
    def send_catchup_to_absentees(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        d = Prompt.iso_date(self.ctx.parent, "Date", "Session date:")
        if not d:
            return
        msg = Prompt.non_empty(self.ctx.parent, "Message",
                               "Catch-up message:", min_len=5)
        if not msg:
            return
        try:
            absent = self.ctx.db.cur.execute(
                """SELECT a.student_id, s.email_address FROM attendance a
                   JOIN students s ON s.student_id = a.student_id
                   WHERE a.module_code=? AND a.date=?
                     AND a.status IN ('absent','late')""",
                (mc, d)).fetchall()
            for sid, email in absent:
                self.ctx.db.cur.execute(
                    """INSERT INTO emails
                       (recipient, subject, body, sent_at, status)
                       VALUES (?, 'Catch up', ?,
                               CURRENT_TIMESTAMP, 'queued')""",
                    (email or sid, msg))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("catchup batch failed mc=%s d=%s", mc, d)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.catchup", "emails", mc,
              f"{d} n={len(absent)}")
        messagebox.showinfo("Sent", f"Queued {len(absent)} email(s).",
                            parent=self.ctx.parent)

    # --- #33 ----------------------------------------------------------
    @safe("Parent outreach")
    def notify_parents_of_low_attendance(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=70) or 70
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            # FIX: replaced bogus `HAVING 2 < ?` with a real predicate over
            # the aggregated percentage column.
            low = self.ctx.db.cur.execute(
                f"""SELECT student_id,
                           SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100 AS pct
                    FROM attendance WHERE module_code IN ({ph})
                    GROUP BY student_id
                    HAVING pct IS NOT NULL AND pct < ?""",
                (*mine, threshold)).fetchall()
        except sqlite3.Error:
            logger.exception("parent outreach lookup failed")
            messagebox.showerror("Error",
                                 "Could not compute below-threshold list.",
                                 parent=self.ctx.parent)
            return
        n = 0
        try:
            for sid, pct in low:
                parents = self.ctx.db.cur.execute(
                    """SELECT parent_id FROM parent_student_links
                       WHERE student_id=?""", (sid,)).fetchall()
                for (pid,) in parents:
                    self.ctx.db.cur.execute(
                        """INSERT INTO parent_notifications
                           (parent_id, student_id, notification_type,
                            notification_content, created_date, read_status)
                           VALUES (?,?,?,?,?,0)""",
                        (str(pid), sid, "attendance_alert",
                         f"{sid} attendance {pct:.1f}% "
                         f"(below {threshold:.0f}%)",
                         datetime.now().isoformat(timespec="seconds")))
                    n += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("parent notification insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.parent_outreach", "parent_notifications", "",
              f"n={n} threshold={threshold}")
        messagebox.showinfo("Sent", f"Notified {n} parent(s).",
                            parent=self.ctx.parent)

    # --- #34 ----------------------------------------------------------
    @safe("Office hours")
    def publish_office_hours(self) -> None:
        slot = Prompt.non_empty(
            self.ctx.parent, "Slot",
            "Slot (e.g. 'Wed 14:00-15:00'):", min_len=3)
        if not slot:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS office_hours (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff_id INTEGER, slot TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                "INSERT INTO office_hours (staff_id, slot) VALUES (?,?)",
                (self.ctx.uid, slot))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("office hours insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.office_hours", "office_hours",
              self.ctx.uid, slot)
        messagebox.showinfo("Published", f"Office hours: {slot}",
                            parent=self.ctx.parent)


# ===========================================================================
# PastoralService — features #35–#39
# ===========================================================================

class PastoralService:
    """Pastoral flags, check-ins, safeguarding, meetings, intervention log."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    # --- #35 ----------------------------------------------------------
    @safe("Flag pastoral")
    def flag_pastoral_concern(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student",
                               "Student ID:", min_len=1)
        if not sid:
            return
        note = Prompt.non_empty(self.ctx.parent, "Concern",
                                "Concern:", min_len=5)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS early_warning_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, author_id INTEGER, content TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                """INSERT INTO early_warning_notifications
                   (student_id, author_id, content) VALUES (?,?,?)""",
                (sid, self.ctx.uid, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("pastoral flag insert failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.ew_flag", "early_warning_notifications",
              sid, note[:80])
        messagebox.showinfo("Flagged", "Pastoral team notified.",
                            parent=self.ctx.parent)

    # --- #36 ----------------------------------------------------------
    @safe("Check-in log")
    def log_checkin_conversation(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student",
                               "Student ID:", min_len=1)
        if not sid:
            return
        outcome = Prompt.non_empty(self.ctx.parent, "Notes",
                                   "Outcome / notes:", min_len=2)
        if not outcome:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_intervention_log
                   (staff_id, student_id, action, outcome)
                   VALUES (?,?,?,?)""",
                (self.ctx.uid, sid, "check-in", outcome))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("checkin insert failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.checkin", "abs_tracker_intervention_log",
              sid, outcome[:80])
        messagebox.showinfo("Logged", "Check-in saved.",
                            parent=self.ctx.parent)

    # --- #37 ----------------------------------------------------------
    @safe("Escalate safeguarding")
    def escalate_safeguarding_incident(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student",
                               "Student ID:", min_len=1)
        if not sid:
            return
        desc = Prompt.non_empty(self.ctx.parent, "Details",
                                "Details:", min_len=10)
        if not desc:
            return
        if not Prompt.confirm(self.ctx.parent, "Confirm",
                              "Escalate to safeguarding? "
                              "This is a high-priority alert."):
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, category TEXT, details TEXT,
                    raised_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                """INSERT INTO incidents
                   (student_id, category, details, raised_by)
                   VALUES (?, 'safeguarding', ?, ?)""",
                (sid, desc, self.ctx.uid))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("safeguarding escalation failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.safeguard", "incidents", sid, "(redacted)")
        messagebox.showinfo("Escalated",
                            "Safeguarding team has been notified.",
                            parent=self.ctx.parent)

    # --- #38 ----------------------------------------------------------
    @safe("Meeting scheduler")
    def schedule_student_meeting(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student",
                               "Student ID:", min_len=1)
        if not sid:
            return
        when = Prompt.iso_datetime(self.ctx.parent, "When",
                                   "Meeting time (YYYY-MM-DD HH:MM):")
        if not when:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS parent_conferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, staff_id INTEGER,
                    scheduled_for TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                """INSERT INTO parent_conferences
                   (student_id, staff_id, scheduled_for) VALUES (?,?,?)""",
                (sid, self.ctx.uid, when))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("meeting schedule failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.meeting", "parent_conferences", sid, when)
        messagebox.showinfo("Scheduled", f"Meeting {when} with {sid}.",
                            parent=self.ctx.parent)

    # --- #39 ----------------------------------------------------------
    @safe("Intervention tracker")
    def show_intervention_history(self) -> None:
        if self.ctx.require_uid() is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT created_at, student_id, action, outcome
                   FROM abs_tracker_intervention_log
                   WHERE staff_id=? ORDER BY created_at DESC""",
                (self.ctx.uid,)).fetchall()
        except sqlite3.Error:
            logger.exception("intervention list fetch failed")
            rows = []
        _show_table(self.ctx.parent, f"My interventions ({len(rows)})",
                    ("when", "student", "action", "outcome"), rows,
                    widths=[160, 120, 140, 420])


# ===========================================================================
# AssessmentIntegrationService — features #40–#42
# ===========================================================================

class AssessmentIntegrationService:
    """Link assignments / exams / lab safety to attendance state."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #40 ----------------------------------------------------------
    @safe("Assignment link")
    def show_pre_deadline_absence_risk(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY,
                    module_code TEXT, title TEXT, due_date TEXT)""")
            # FIX: previous query used `HAVING 4 >= 2` — a literal-only
            # comparison that's always true. Now requires ≥2 absences in
            # the 14 days before the assignment due date.
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id, ass.title, ass.due_date,
                          SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END)
                              AS absences
                   FROM attendance a
                   JOIN assignments ass ON ass.module_code = a.module_code
                     AND ass.due_date >= date('now')
                   WHERE a.module_code=?
                     AND a.date BETWEEN date(ass.due_date,'-14 days')
                                    AND ass.due_date
                   GROUP BY a.student_id, ass.id
                   HAVING absences >= 2
                   ORDER BY ass.due_date""", (mc,)).fetchall()
        except sqlite3.Error:
            logger.exception("assignment link query failed mc=%s", mc)
            rows = []
        _show_table(self.ctx.parent, "Pre-deadline absence risk",
                    ("student", "assignment", "due", "absences in 14d"), rows)

    # --- #41 ----------------------------------------------------------
    @safe("Exam eligibility")
    def show_exam_ineligible_students(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            thr_row = self.ctx.db.cur.execute(
                """SELECT min_percent FROM abs_tracker_module_policy
                   WHERE module_code=?""", (mc,)).fetchone()
        except sqlite3.Error:
            logger.exception("policy fetch failed mc=%s", mc)
            thr_row = None
        thr = thr_row[0] if thr_row else float(
            _get_setting(self.ctx.db, "default_min_pct", 80) or 80)
        try:
            # FIX: `HAVING 2 < ?` was a literal compare. Now correctly
            # checks the aggregate attendance percentage.
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100 AS pct
                   FROM attendance a WHERE a.module_code=?
                   GROUP BY a.student_id
                   HAVING pct IS NOT NULL AND pct < ?""",
                (mc, thr)).fetchall()
        except sqlite3.Error:
            logger.exception("exam eligibility query failed mc=%s", mc)
            rows = []
        _show_table(self.ctx.parent, f"Ineligible (<{thr:.0f}%) — {mc}",
                    ("student", "%"),
                    [(s, f"{p:.1f}") for s, p in rows])

    # --- #42 ----------------------------------------------------------
    @safe("Lab safety")
    def show_missing_safety_briefing(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT sm.student_id
                   FROM student_modules sm
                   WHERE sm.module_code=?
                     AND sm.student_id NOT IN (
                         SELECT DISTINCT student_id FROM attendance
                         WHERE module_code=?
                           AND COALESCE(reason,'') LIKE '%safety%'
                           AND status='present')""",
                (mc, mc)).fetchall()
        except sqlite3.Error:
            logger.exception("lab safety query failed mc=%s", mc)
            rows = []
        _show_table(self.ctx.parent, f"{mc} — missed safety briefing",
                    ("student",), rows, widths=[180])


# ===========================================================================
# CollaborationService — features #43–#45
# ===========================================================================

class CollaborationService:
    """Co-teacher grants, TA handoff notes, peer observations."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker,
                 staff_picker: StaffPicker) -> None:
        self.ctx = ctx
        self.picker = picker
        self.staff_picker = staff_picker

    # --- #43 ----------------------------------------------------------
    @safe("Co-teacher")
    def grant_co_teacher_access(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        sp = self.staff_picker.pick("Co-teacher", "Grant to:")
        if not sp:
            return
        co_uid, co_label = sp
        try:
            self.ctx.db.cur.execute(
                """INSERT OR IGNORE INTO abs_tracker_co_teachers
                   (module_code, user_id) VALUES (?,?)""", (mc, co_uid))
            # Mirror into instructor_modules so the rest of the tracker
            # respects the grant.
            self.ctx.db.cur.execute(
                """INSERT OR IGNORE INTO instructor_modules
                   (instructor_id, module_code) VALUES (?,?)""",
                (co_uid, mc))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("co-teacher grant failed mc=%s uid=%s",
                             mc, co_uid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.co_teacher", "abs_tracker_co_teachers",
              mc, str(co_uid))
        messagebox.showinfo("Granted",
                            f"{co_label} can now take roll on {mc}.",
                            parent=self.ctx.parent)

    # --- #44 ----------------------------------------------------------
    @safe("TA handoff")
    def leave_ta_handoff_note(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        sp = self.staff_picker.pick("TA", "TA:")
        if not sp:
            return
        ta_uid, _ = sp
        note = Prompt.non_empty(self.ctx.parent, "Handoff",
                                "Note to TA:", min_len=2)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_ta_handoff
                   (staff_id, ta_id, module_code, note) VALUES (?,?,?,?)""",
                (self.ctx.uid, ta_uid, mc, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("ta handoff insert failed mc=%s ta=%s",
                             mc, ta_uid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.ta_handoff", "abs_tracker_ta_handoff",
              mc, note[:80])
        messagebox.showinfo("Saved", "TA handoff saved.",
                            parent=self.ctx.parent)

    # --- #45 ----------------------------------------------------------
    @safe("Peer observation")
    def log_peer_observation(self) -> None:
        sp = self.staff_picker.pick("Observed", "Who did you observe?")
        if not sp:
            return
        sub_uid, _ = sp
        mc = Prompt.non_empty(self.ctx.parent, "Module",
                              "Module code:", min_len=1)
        if not mc:
            return
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        notes = Prompt.non_empty(self.ctx.parent, "Notes",
                                 "Notes:", min_len=10)
        if not notes:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_peer_observations
                   (observer_id, subject_id, module_code, date, notes)
                   VALUES (?,?,?,?,?)""",
                (self.ctx.uid, sub_uid, mc, d, notes))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("peer obs insert failed sub=%s mc=%s",
                             sub_uid, mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.peer_obs", "abs_tracker_peer_observations",
              sub_uid, f"{mc} {d}")
        messagebox.showinfo("Saved", "Peer observation recorded.",
                            parent=self.ctx.parent)


# ===========================================================================
# ConfigurationService — features #46–#48
# ===========================================================================

class ConfigurationService:
    """Module policy, range-excuses, seating chart import."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #46 ----------------------------------------------------------
    @safe("Module policy quick-edit")
    def edit_module_policy(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        pct = simpledialog.askfloat(
            "Min %", "Minimum attendance % (0-100):",
            parent=self.ctx.parent,
            initialvalue=80, minvalue=0, maxvalue=100)
        if pct is None:
            return
        grace = simpledialog.askinteger(
            "Grace", "Grace minutes for late→present:",
            parent=self.ctx.parent,
            initialvalue=5, minvalue=0, maxvalue=60)
        if grace is None:
            grace = 0
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_module_policy
                   (module_code, min_percent, late_as_absent, grace_minutes,
                    notes)
                   VALUES (?, ?, 0, ?, ?)""",
                (mc, pct, grace,
                 f"edited by {self.ctx.username}"))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("policy save failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.policy", "abs_tracker_module_policy", mc,
              f"pct={pct} grace={grace}")
        messagebox.showinfo("Saved", f"{mc}: ≥{pct}%, grace={grace}m",
                            parent=self.ctx.parent)

    # --- #47 ----------------------------------------------------------
    @safe("Excuse range")
    def excuse_date_range(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, mlabel = picked
        rng = pick_date_range(self.ctx.parent, "Excuse date range")
        if not rng:
            return
        start, end = rng
        reason = (simpledialog.askstring("Reason", "Reason:",
                                         parent=self.ctx.parent
                                         ) or "field trip").strip()
        try:
            d0 = datetime.strptime(start, "%Y-%m-%d").date()
            d1 = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError as e:
            messagebox.showerror("Bad date", str(e), parent=self.ctx.parent)
            return
        if d1 < d0:
            messagebox.showerror("Bad range",
                                 "End date is before start date.",
                                 parent=self.ctx.parent)
            return
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        days = (d1 - d0).days + 1
        if not Prompt.confirm(
                self.ctx.parent, "Confirm",
                f"Excuse {len(roster)} student(s) for {days} day(s) "
                f"on {mlabel}?"):
            return
        n = 0
        try:
            d = d0
            while d <= d1:
                for sid, *_ in roster:
                    self.ctx.db.record_absence(
                        sid, mc, d.isoformat(), "excused", reason)
                    n += 1
                d += timedelta(days=1)
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("excuse range failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.excuse_range", "attendance", mc,
              f"{start}..{end} n={n}")
        messagebox.showinfo("Excused",
                            f"{n} rows written {start} → {end}.",
                            parent=self.ctx.parent)

    # --- #48 ----------------------------------------------------------
    @safe("Seating chart")
    def import_seating_chart(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        path = filedialog.askopenfilename(
            parent=self.ctx.parent,
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            messagebox.showerror("Missing", f"File not found:\n{path}",
                                 parent=self.ctx.parent)
            return
        try:
            layout = p.read_text(encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Read failed", str(e),
                                 parent=self.ctx.parent)
            return
        # Validate JSON early so we don't store garbage that breaks
        # downstream consumers.
        try:
            json.loads(layout)
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Not valid JSON: {e}",
                                 parent=self.ctx.parent)
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_seating
                   (module_code, date, layout_json) VALUES (?,?,?)""",
                (mc, d, layout))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("seating chart save failed mc=%s d=%s", mc, d)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.seating", "abs_tracker_seating", mc,
              f"{d} {p.name}")
        messagebox.showinfo("Saved", "Seating plan saved.",
                            parent=self.ctx.parent)


# ===========================================================================
# ProductivityService — features #49–#50
# ===========================================================================

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


# ===========================================================================
# LeaveService — feature #51
# ===========================================================================

_DEFAULT_LEAVE_TYPES = [
    (1, "Annual leave"),
    (2, "Sick leave"),
    (3, "Personal"),
    (4, "Bereavement"),
    (5, "Training"),
]


class LeaveService:
    """File a staff leave request via leave_requests."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    def _ensure_default_types(self) -> None:
        try:
            self.ctx.db.cur.executemany(
                """INSERT OR IGNORE INTO leave_types
                   (leave_type_id, name, requires_approval, is_active)
                   VALUES (?, ?, 1, 1)""", _DEFAULT_LEAVE_TYPES)
            self.ctx.db.conn.commit()
        except sqlite3.Error:
            self.ctx.db.conn.rollback()
            logger.exception("leave_types seed failed")

    @safe("Request time off")
    def request_time_off(self) -> None:
        if self.ctx.require_uid() is None:
            return
        self._ensure_default_types()
        try:
            types = self.ctx.db.cur.execute(
                """SELECT leave_type_id, name FROM leave_types
                   WHERE is_active=1 ORDER BY name""").fetchall()
        except sqlite3.Error:
            logger.exception("leave_types fetch failed")
            messagebox.showerror("Error", "Could not load leave types.",
                                 parent=self.ctx.parent)
            return
        if not types:
            messagebox.showinfo("None", "No active leave types.",
                                parent=self.ctx.parent)
            return
        tmap = {r[1]: r[0] for r in types}
        tpick = _combo_dialog(self.ctx.parent, "Leave type",
                              "Type:", list(tmap.keys()))
        if not tpick:
            return
        rng = pick_date_range(self.ctx.parent, "Leave dates")
        if not rng:
            return
        start, end = rng
        try:
            d0 = datetime.strptime(start, "%Y-%m-%d").date()
            d1 = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError as e:
            messagebox.showerror("Bad date", str(e), parent=self.ctx.parent)
            return
        if d1 < d0:
            messagebox.showerror("Bad range",
                                 "End date is before start date.",
                                 parent=self.ctx.parent)
            return
        reason = (simpledialog.askstring("Reason", "Reason:",
                                         parent=self.ctx.parent) or "").strip()
        total = (d1 - d0).days + 1
        now = datetime.now().isoformat(timespec="seconds")
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO leave_requests
                   (user_id, leave_type_id, start_date, end_date,
                    total_days, reason, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (str(self.ctx.uid), tmap[tpick], start, end, total, reason,
                 now, now))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("leave request insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.request_time_off", "leave_requests",
              self.ctx.uid, f"{tpick} {start}..{end} ({total}d)")
        messagebox.showinfo(
            "Submitted",
            f"Leave request ({tpick}, {total} day{'s' if total != 1 else ''}) "
            f"submitted for {start} → {end}.",
            parent=self.ctx.parent)


# ===========================================================================
# Service container + feature registry
# ===========================================================================

@dataclass
class StaffServices:
    """Aggregates every service the Staff Tools tab needs."""
    roll_call: RollCallService
    roster: RosterService
    requests: RequestReviewService
    analytics: AnalyticsService
    communication: CommunicationService
    pastoral: PastoralService
    assessment: AssessmentIntegrationService
    collaboration: CollaborationService
    configuration: ConfigurationService
    productivity: ProductivityService
    leave: LeaveService

    @classmethod
    def for_context(cls, ctx: StaffContext) -> "StaffServices":
        picker = ModulePicker(ctx)
        staff_picker = StaffPicker(ctx)
        return cls(
            roll_call     = RollCallService(ctx, picker, staff_picker),
            roster        = RosterService(ctx, picker),
            requests      = RequestReviewService(ctx),
            analytics     = AnalyticsService(ctx, picker),
            communication = CommunicationService(ctx, picker),
            pastoral      = PastoralService(ctx),
            assessment    = AssessmentIntegrationService(ctx, picker),
            collaboration = CollaborationService(ctx, picker, staff_picker),
            configuration = ConfigurationService(ctx, picker),
            productivity  = ProductivityService(ctx, picker),
            leave         = LeaveService(ctx),
        )


@dataclass(frozen=True)
class FeatureSpec:
    number: int
    category: str
    label: str
    method: Callable[[StaffServices], Callable[[], None]]


def _build_feature_registry() -> list[FeatureSpec]:
    return [
        # Roll-call
        FeatureSpec( 1, "Roll-call", "Today's classes",
                    lambda s: s.roll_call.show_today_dashboard),
        FeatureSpec( 2, "Roll-call", "Generate sessions",
                    lambda s: s.roll_call.generate_session_dates),
        FeatureSpec( 3, "Roll-call", "Session notes",
                    lambda s: s.roll_call.add_session_note),
        FeatureSpec( 4, "Roll-call", "Cancel session",
                    lambda s: s.roll_call.cancel_session),
        FeatureSpec( 5, "Roll-call", "Substitute mode",
                    lambda s: s.roll_call.substitute_for_colleague),
        FeatureSpec( 6, "Roll-call", "All-present (with excepts)",
                    lambda s: s.roll_call.mark_all_present_except),
        FeatureSpec( 7, "Roll-call", "Late log",
                    lambda s: s.roll_call.log_late_arrival),
        FeatureSpec( 8, "Roll-call", "Early-leave log",
                    lambda s: s.roll_call.log_early_leave),
        FeatureSpec( 9, "Roll-call", "Session QR code",
                    lambda s: s.roll_call.generate_session_qr),
        FeatureSpec(10, "Roll-call", "Correct roll after session",
                    lambda s: s.roll_call.correct_roll_row),

        # Roster
        FeatureSpec(11, "Roster", "Roster (+ contacts)",
                    lambda s: s.roster.show_roster_with_contacts),
        FeatureSpec(12, "Roster", "Search my students",
                    lambda s: s.roster.search_my_students),
        FeatureSpec(13, "Roster", "Filter by risk",
                    lambda s: s.roster.filter_students_by_risk),
        FeatureSpec(14, "Roster", "Groups",
                    lambda s: s.roster.manage_module_groups),
        FeatureSpec(15, "Roster", "Roster export",
                    lambda s: s.roster.export_roster),

        # Requests
        FeatureSpec(16, "Requests", "Triage queue",
                    lambda s: s.requests.show_triage_queue),
        FeatureSpec(17, "Requests", "Preview evidence",
                    lambda s: s.requests.preview_request_evidence),
        FeatureSpec(18, "Requests", "Staff comment + decide",
                    lambda s: s.requests.decide_with_comment),
        FeatureSpec(19, "Requests", "Approve with modification",
                    lambda s: s.requests.approve_with_modification),
        FeatureSpec(20, "Requests", "SLA dashboard",
                    lambda s: s.requests.show_sla_dashboard),
        FeatureSpec(21, "Requests", "Route to dept head",
                    lambda s: s.requests.route_to_department_head),

        # Analytics
        FeatureSpec(22, "Analytics", "My heatmap",
                    lambda s: s.analytics.show_my_heatmap),
        FeatureSpec(23, "Analytics", "Drop-off detector",
                    lambda s: s.analytics.show_dropoff_students),
        FeatureSpec(24, "Analytics", "Compare my modules",
                    lambda s: s.analytics.compare_my_modules),
        FeatureSpec(25, "Analytics", "Historical cohort",
                    lambda s: s.analytics.compare_terms_for_module),
        FeatureSpec(26, "Analytics", "Module report export",
                    lambda s: s.analytics.export_module_report),
        FeatureSpec(27, "Analytics", "Student profile",
                    lambda s: s.analytics.show_student_profile),
        FeatureSpec(28, "Analytics", "Attendance vs grade",
                    lambda s: s.analytics.show_attendance_vs_grade),

        # Communication
        FeatureSpec(29, "Communication", "Email student",
                    lambda s: s.communication.email_single_student),
        FeatureSpec(30, "Communication", "Email at-risk list",
                    lambda s: s.communication.email_at_risk_summary),
        FeatureSpec(31, "Communication", "Module announcement",
                    lambda s: s.communication.post_module_announcement),
        FeatureSpec(32, "Communication", "Catch-up message (absent)",
                    lambda s: s.communication.send_catchup_to_absentees),
        FeatureSpec(33, "Communication", "Parent outreach",
                    lambda s: s.communication.notify_parents_of_low_attendance),
        FeatureSpec(34, "Communication", "Publish office hours",
                    lambda s: s.communication.publish_office_hours),

        # Pastoral
        FeatureSpec(35, "Pastoral", "Flag pastoral",
                    lambda s: s.pastoral.flag_pastoral_concern),
        FeatureSpec(36, "Pastoral", "Check-in log",
                    lambda s: s.pastoral.log_checkin_conversation),
        FeatureSpec(37, "Pastoral", "Escalate safeguarding",
                    lambda s: s.pastoral.escalate_safeguarding_incident),
        FeatureSpec(38, "Pastoral", "Meeting scheduler",
                    lambda s: s.pastoral.schedule_student_meeting),
        FeatureSpec(39, "Pastoral", "Intervention tracker",
                    lambda s: s.pastoral.show_intervention_history),

        # Assessment
        FeatureSpec(40, "Assessment", "Assignment ↔ absence",
                    lambda s: s.assessment.show_pre_deadline_absence_risk),
        FeatureSpec(41, "Assessment", "Exam eligibility",
                    lambda s: s.assessment.show_exam_ineligible_students),
        FeatureSpec(42, "Assessment", "Lab safety briefing check",
                    lambda s: s.assessment.show_missing_safety_briefing),

        # Collaboration
        FeatureSpec(43, "Collaboration", "Co-teacher",
                    lambda s: s.collaboration.grant_co_teacher_access),
        FeatureSpec(44, "Collaboration", "TA handoff note",
                    lambda s: s.collaboration.leave_ta_handoff_note),
        FeatureSpec(45, "Collaboration", "Peer observation",
                    lambda s: s.collaboration.log_peer_observation),

        # Config
        FeatureSpec(46, "Config", "Module policy quick-edit",
                    lambda s: s.configuration.edit_module_policy),
        FeatureSpec(47, "Config", "Excuse date range",
                    lambda s: s.configuration.excuse_date_range),
        FeatureSpec(48, "Config", "Seating chart",
                    lambda s: s.configuration.import_seating_chart),

        # Productivity
        FeatureSpec(49, "Productivity", "My KPIs",
                    lambda s: s.productivity.show_my_kpis),
        FeatureSpec(50, "Productivity", "My to-do list",
                    lambda s: s.productivity.show_my_todo_list),

        # Leave
        FeatureSpec(51, "Requests", "Request time off (date picker)",
                    lambda s: s.leave.request_time_off),
    ]


FEATURES: list[FeatureSpec] = _build_feature_registry()


# ===========================================================================
# Tab renderer
# ===========================================================================

def build_staff_tab(notebook: ttk.Notebook, ctx: StaffContext) -> None:
    """Render all 50 staff features into a dedicated notebook tab."""
    try:
        ensure_support_tables(ctx.db)
        ensure_staff_tables(ctx.db)
    except sqlite3.Error:
        logger.exception("could not ensure staff tables")
        messagebox.showerror(
            "Staff Tools",
            "Could not initialise staff-tools tables. See log.",
            parent=ctx.parent)
        return

    services = StaffServices.for_context(ctx)

    frame = ttk.Frame(notebook)
    notebook.add(frame, text="🧑‍🏫 Staff Tools (50)")

    canvas = tk.Canvas(frame, bg="#f0f4f8", highlightthickness=0)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    inner = tk.Frame(canvas, bg="#f0f4f8")
    canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    by_cat: dict[str, list[FeatureSpec]] = {}
    for spec in FEATURES:
        by_cat.setdefault(spec.category, []).append(spec)

    for cat, items in by_cat.items():
        box = tk.LabelFrame(inner, text=cat, padx=10, pady=8,
                            font=("Arial", 11, "bold"), bg="#f0f4f8",
                            fg="#1e3a5f")
        box.pack(fill="x", padx=12, pady=8)
        cols = 3
        for i, spec in enumerate(items):
            try:
                callback = spec.method(services)
            except Exception:
                logger.exception("feature %d binding failed", spec.number)
                continue
            btn = tk.Button(
                box, text=f"{spec.number:02d}. {spec.label}",
                command=callback,
                bg="#7c3aed", fg="white", activebackground="#6d28d9",
                relief="flat", cursor="hand2",
                width=32, anchor="w", padx=8, pady=6,
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="w")

    logger.info("staff tools tab built (%d features)", len(FEATURES))


# ===========================================================================
# Backwards-compat: keep module-level callable aliases for any external caller
# that imported the old `stf_NN_*` names directly.
# ===========================================================================

def _wrap(method_picker: Callable[[StaffServices], Callable[[], None]]
          ) -> Callable[[StaffContext], None]:
    def runner(ctx: StaffContext) -> None:
        services = StaffServices.for_context(ctx)
        method_picker(services)()
    return runner


_LEGACY_ALIASES: dict[str, Callable] = {
    "stf_01_today_dashboard":     _wrap(lambda s: s.roll_call.show_today_dashboard),
    "stf_02_generate_sessions":   _wrap(lambda s: s.roll_call.generate_session_dates),
    "stf_03_session_note":        _wrap(lambda s: s.roll_call.add_session_note),
    "stf_04_cancel_session":      _wrap(lambda s: s.roll_call.cancel_session),
    "stf_05_substitute_mode":     _wrap(lambda s: s.roll_call.substitute_for_colleague),
    "stf_06_all_present_except":  _wrap(lambda s: s.roll_call.mark_all_present_except),
    "stf_07_late_log":            _wrap(lambda s: s.roll_call.log_late_arrival),
    "stf_08_early_leave":         _wrap(lambda s: s.roll_call.log_early_leave),
    "stf_09_session_qr":          _wrap(lambda s: s.roll_call.generate_session_qr),
    "stf_10_correct_roll":        _wrap(lambda s: s.roll_call.correct_roll_row),
    "stf_11_roster_with_photos":  _wrap(lambda s: s.roster.show_roster_with_contacts),
    "stf_12_search_my_students":  _wrap(lambda s: s.roster.search_my_students),
    "stf_13_filter_by_risk":      _wrap(lambda s: s.roster.filter_students_by_risk),
    "stf_14_groups":              _wrap(lambda s: s.roster.manage_module_groups),
    "stf_15_roster_export":       _wrap(lambda s: s.roster.export_roster),
    "stf_16_triage_queue":        _wrap(lambda s: s.requests.show_triage_queue),
    "stf_17_preview_evidence":    _wrap(lambda s: s.requests.preview_request_evidence),
    "stf_18_decision_comment":    _wrap(lambda s: s.requests.decide_with_comment),
    "stf_19_approve_with_mod":    _wrap(lambda s: s.requests.approve_with_modification),
    "stf_20_sla_dashboard":       _wrap(lambda s: s.requests.show_sla_dashboard),
    "stf_21_route_to_dept":       _wrap(lambda s: s.requests.route_to_department_head),
    "stf_22_my_heatmap":          _wrap(lambda s: s.analytics.show_my_heatmap),
    "stf_23_dropoff":             _wrap(lambda s: s.analytics.show_dropoff_students),
    "stf_24_compare_my_modules":  _wrap(lambda s: s.analytics.compare_my_modules),
    "stf_25_historical_cohort":   _wrap(lambda s: s.analytics.compare_terms_for_module),
    "stf_26_module_report":       _wrap(lambda s: s.analytics.export_module_report),
    "stf_27_student_profile":     _wrap(lambda s: s.analytics.show_student_profile),
    "stf_28_correlation":         _wrap(lambda s: s.analytics.show_attendance_vs_grade),
    "stf_29_email_student":       _wrap(lambda s: s.communication.email_single_student),
    "stf_30_email_at_risk":       _wrap(lambda s: s.communication.email_at_risk_summary),
    "stf_31_announcement":        _wrap(lambda s: s.communication.post_module_announcement),
    "stf_32_catchup_message":     _wrap(lambda s: s.communication.send_catchup_to_absentees),
    "stf_33_parent_outreach":     _wrap(lambda s: s.communication.notify_parents_of_low_attendance),
    "stf_34_office_hours":        _wrap(lambda s: s.communication.publish_office_hours),
    "stf_35_flag_pastoral":       _wrap(lambda s: s.pastoral.flag_pastoral_concern),
    "stf_36_checkin_log":         _wrap(lambda s: s.pastoral.log_checkin_conversation),
    "stf_37_escalate_safeguarding": _wrap(lambda s: s.pastoral.escalate_safeguarding_incident),
    "stf_38_meeting_scheduler":   _wrap(lambda s: s.pastoral.schedule_student_meeting),
    "stf_39_intervention_tracker": _wrap(lambda s: s.pastoral.show_intervention_history),
    "stf_40_assignment_link":     _wrap(lambda s: s.assessment.show_pre_deadline_absence_risk),
    "stf_41_exam_eligibility":    _wrap(lambda s: s.assessment.show_exam_ineligible_students),
    "stf_42_lab_safety":          _wrap(lambda s: s.assessment.show_missing_safety_briefing),
    "stf_43_co_teacher":          _wrap(lambda s: s.collaboration.grant_co_teacher_access),
    "stf_44_ta_handoff":          _wrap(lambda s: s.collaboration.leave_ta_handoff_note),
    "stf_45_peer_observation":    _wrap(lambda s: s.collaboration.log_peer_observation),
    "stf_46_policy_quick_edit":   _wrap(lambda s: s.configuration.edit_module_policy),
    "stf_47_excuse_range":        _wrap(lambda s: s.configuration.excuse_date_range),
    "stf_48_seating_chart":       _wrap(lambda s: s.configuration.import_seating_chart),
    "stf_49_my_kpis":             _wrap(lambda s: s.productivity.show_my_kpis),
    "stf_50_todo":                _wrap(lambda s: s.productivity.show_my_todo_list),
    "stf_51_request_time_off":    _wrap(lambda s: s.leave.request_time_off),
}
globals().update(_LEGACY_ALIASES)
