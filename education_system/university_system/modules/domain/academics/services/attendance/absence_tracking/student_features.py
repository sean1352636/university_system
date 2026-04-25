"""
Student features for the Absence Tracker.

Fifty-plus student-facing utilities organised into service classes by domain:

    AttendanceVisibilityService   #1–8     read-only views of my attendance
    RequestService                #9–16,51 absence requests (submit / withdraw / etc.)
    NotificationService           #17–22   reminders, channels, DND
    PlanningService               #23–28   goals, budgets, ICS export
    SupportService                #29–35   notes, office hours, wellbeing
    SocialService                 #36–39   study groups, peer notes, badges
    AppealsService                #40–42   disputes and appeals
    IntegrationsService           #43–47   timetable, grades, library, exams
    CustomisationService          #48–50   accessibility, language, layout

Every public method is wrapped with the shared ``@safe`` decorator (logged
traceback + friendly dialog on failure) and additionally guards I/O and DB
state-changes with explicit ``try/except`` so a single bad row never leaves
the connection in a half-committed state.
"""

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

# Route through the university system's central rotating file handler
# (core/logs/app.log) so this module's traceback/info lines land alongside
# every other subsystem's output.
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="absence_tracker.student")
except Exception:  # pragma: no cover — fall back to stderr if log_config unavailable
    logger = logging.getLogger("absence_tracker.student")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)


# ===========================================================================
# Context + support tables
# ===========================================================================

@dataclass
class StudentContext:
    db: Any
    parent: tk.Misc
    user: dict

    @property
    def sid(self) -> Optional[str]:
        return self.user.get("student_id")

    def require_sid(self) -> Optional[str]:
        if not self.sid:
            messagebox.showerror(
                "Missing student_id",
                "Your user account is not linked to a student record.",
                parent=self.parent,
            )
            return None
        return self.sid


def ensure_student_tables(db) -> None:
    """Create student-side support tables if missing."""
    db.cur.executescript("""
        CREATE TABLE IF NOT EXISTS abs_tracker_student_goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT, target_pct REAL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, module_code)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_student_drafts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT, date TEXT, reason TEXT,
            saved_at    TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_student_prefs (
            student_id TEXT, key TEXT, value TEXT,
            PRIMARY KEY(student_id, key)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_attendance_disputes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    TEXT, attendance_id INTEGER, reason TEXT,
            status        TEXT DEFAULT 'open',
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at   TEXT, outcome TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_note_requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id TEXT, module_code TEXT, date TEXT,
            status       TEXT DEFAULT 'open',
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            fulfiller_id TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_study_buddies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, module_code)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_wellbeing_flags (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, attendance_id INTEGER, note TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_note_share (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id     TEXT, module_code TEXT, date TEXT,
            file_path    TEXT, title TEXT,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_student_badges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, badge TEXT, awarded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, badge)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_appeals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, request_id INTEGER, reason TEXT,
            status      TEXT DEFAULT 'open',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.conn.commit()


# ===========================================================================
# Preferences (typed wrapper around abs_tracker_student_prefs)
# ===========================================================================

class StudentPrefs:
    """Typed accessor for per-student key/value preferences."""

    def __init__(self, db) -> None:
        self.db = db

    def get(self, sid: str, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            r = self.db.cur.execute(
                "SELECT value FROM abs_tracker_student_prefs WHERE student_id=? AND key=?",
                (sid, key),
            ).fetchone()
            return r[0] if r else default
        except sqlite3.Error:
            logger.exception("StudentPrefs.get failed (sid=%s key=%s)", sid, key)
            return default

    def set(self, sid: str, key: str, value: Any) -> None:
        try:
            self.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_student_prefs
                   (student_id, key, value) VALUES (?, ?, ?)""",
                (sid, key, str(value)),
            )
            self.db.conn.commit()
        except sqlite3.Error:
            self.db.conn.rollback()
            logger.exception("StudentPrefs.set failed (sid=%s key=%s)", sid, key)
            raise

    def get_int(self, sid: str, key: str, default: int = 0) -> int:
        try:
            return int(self.get(sid, key, str(default)))
        except (TypeError, ValueError):
            return default

    def get_float(self, sid: str, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(sid, key, str(default)))
        except (TypeError, ValueError):
            return default


# ===========================================================================
# Dialog + validation helpers
# ===========================================================================

class Prompt:
    """Reusable Tk dialogs with validation."""

    @staticmethod
    def iso_date(parent, title: str = "Date",
                 prompt: str = "Date (YYYY-MM-DD):",
                 initial: Optional[str] = None) -> Optional[str]:
        """Re-prompts on invalid input until the user enters a valid ISO date or cancels."""
        initial = initial or date.today().isoformat()
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent, initialvalue=initial)
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
    def hhmm(parent, title: str, prompt: str,
             initial: str = "00:00") -> Optional[str]:
        """Validates HH:MM 24-hour input."""
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent, initialvalue=initial)
            if s is None:
                return None
            s = s.strip()
            try:
                datetime.strptime(s, "%H:%M")
                return s
            except ValueError:
                messagebox.showerror("Bad time",
                                     f"'{s}' is not a valid HH:MM (24h) time.",
                                     parent=parent)
                initial = s

    @staticmethod
    def non_empty(parent, title: str, prompt: str,
                  min_len: int = 1) -> Optional[str]:
        """Strips whitespace; rejects values shorter than `min_len`."""
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
    """Pick a module from a student's enrolments."""

    def __init__(self, ctx: StudentContext) -> None:
        self.ctx = ctx

    def pick(self, sid: str, title: str = "Module"
             ) -> Optional[tuple[str, str]]:
        """Return (module_code, label) or None if the student has none / cancels."""
        try:
            modules = self.ctx.db.get_courses(student_id=sid)
        except Exception:
            logger.exception("get_courses failed for sid=%s", sid)
            messagebox.showerror("Error",
                                 "Could not load your enrolments.",
                                 parent=self.ctx.parent)
            return None
        if not modules:
            messagebox.showinfo("No modules",
                                "You are not enrolled in any modules.",
                                parent=self.ctx.parent)
            return None
        mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
        pick = _combo_dialog(self.ctx.parent, title, "Module:", list(mmap.keys()))
        if not pick:
            return None
        return mmap[pick], pick


# ===========================================================================
# Calendar window (#1)
# ===========================================================================

_STATUS_COLOURS = {
    "present": "#86efac",
    "absent":  "#fca5a5",
    "late":    "#fcd34d",
    "excused": "#bfdbfe",
}
_IN_MONTH_BG = "#f3f4f6"
_OFF_MONTH_BG = "#e5e7eb"
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class _CalendarWindow:
    """Toplevel month-calendar view with prev/next navigation."""

    def __init__(self, ctx: StudentContext, sid: str):
        self.ctx = ctx
        self.sid = sid
        today = date.today()
        self.year = today.year
        self.month = today.month
        self._cal = calendar.Calendar(firstweekday=0)

    def show(self) -> None:
        self.win = tk.Toplevel(self.ctx.parent)
        self.win.title("My attendance")
        self.win.geometry("620x460")
        self.win.transient(self.ctx.parent)

        self._build_header()
        self._build_legend()
        self._grid = tk.Frame(self.win)
        self._grid.pack(padx=10, pady=10)
        self._render_grid()

        self.win.bind("<Left>",  lambda _e: self._shift(-1))
        self.win.bind("<Right>", lambda _e: self._shift(+1))
        self.win.bind("<Home>",  lambda _e: self._goto_today())

    def current_month_str(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def _build_header(self) -> None:
        bar = tk.Frame(self.win)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        tk.Button(bar, text="◀", width=3,
                  command=lambda: self._shift(-1)).pack(side="left")
        self._title_var = tk.StringVar(value=self._title_text())
        tk.Label(bar, textvariable=self._title_var,
                 font=("Arial", 14, "bold")).pack(side="left", expand=True)
        tk.Button(bar, text="▶", width=3,
                  command=lambda: self._shift(+1)).pack(side="right")
        tk.Button(bar, text="Today",
                  command=self._goto_today).pack(side="right", padx=6)

    def _build_legend(self) -> None:
        legend = tk.Frame(self.win)
        legend.pack(fill="x", padx=10, pady=4)
        for status, colour in _STATUS_COLOURS.items():
            chip = tk.Frame(legend, bg=colour, width=14, height=14,
                            relief="solid", borderwidth=1)
            chip.pack(side="left", padx=(8, 4))
            chip.pack_propagate(False)
            tk.Label(legend, text=status.capitalize(),
                     font=("Arial", 9)).pack(side="left")

    def _title_text(self) -> str:
        return f"{calendar.month_name[self.month]} {self.year}"

    def _fetch_month(self) -> dict[str, str]:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, status FROM attendance
                   WHERE student_id = ?
                     AND strftime('%Y-%m', date) = ?""",
                (self.sid, self.current_month_str()),
            ).fetchall()
            return dict(rows)
        except sqlite3.Error:
            logger.exception("calendar fetch failed")
            return {}

    def _render_grid(self) -> None:
        for child in self._grid.winfo_children():
            child.destroy()
        for c, wd in enumerate(_WEEKDAYS):
            tk.Label(self._grid, text=wd, width=8,
                     font=("Arial", 10, "bold")).grid(row=0, column=c)

        by_day = self._fetch_month()
        today_iso = date.today().isoformat()

        for r, week in enumerate(self._cal.monthdatescalendar(
                self.year, self.month), start=1):
            for c, d in enumerate(week):
                in_month = d.month == self.month
                status = by_day.get(d.isoformat(), "") if in_month else ""
                bg = _STATUS_COLOURS.get(
                    status, _IN_MONTH_BG if in_month else _OFF_MONTH_BG)
                fg = "#111827" if in_month else "#9ca3af"
                borderwidth = 2 if d.isoformat() == today_iso else 1
                tk.Label(self._grid,
                         text=f"{d.day}\n{status}",
                         width=8, height=3,
                         bg=bg, fg=fg,
                         relief="solid", borderwidth=borderwidth,
                         font=("Arial", 9)
                         ).grid(row=r, column=c, padx=1, pady=1)

    def _shift(self, delta: int) -> None:
        m = self.month + delta
        y = self.year
        while m < 1:
            m += 12; y -= 1
        while m > 12:
            m -= 12; y += 1
        self.year, self.month = y, m
        self._title_var.set(self._title_text())
        self._render_grid()

    def _goto_today(self) -> None:
        today = date.today()
        self.year, self.month = today.year, today.month
        self._title_var.set(self._title_text())
        self._render_grid()


# ===========================================================================
# Gauge thresholds (#2)
# ===========================================================================

@dataclass(frozen=True)
class GaugeThresholds:
    good: float = 85.0
    warn: float = 70.0

    def band(self, pct: float) -> str:
        if pct >= self.good:
            return "good"
        if pct >= self.warn:
            return "warn"
        return "poor"


_GAUGE_COLOURS = {"good": "#16a34a", "warn": "#f59e0b", "poor": "#dc2626"}
_GAUGE_LABELS = {"good": "On track", "warn": "At risk", "poor": "Below threshold"}


def _load_gauge_thresholds(db) -> GaugeThresholds:
    try:
        good = float(_get_setting(db, "gauge.good_pct", "85"))
        warn = float(_get_setting(db, "gauge.warn_pct", "70"))
        if 0 < warn < good <= 100:
            return GaugeThresholds(good=good, warn=warn)
    except Exception:
        logger.debug("gauge thresholds settings unreadable, using defaults",
                     exc_info=True)
    return GaugeThresholds()


def _bind_wheel(canvas: tk.Canvas) -> None:
    canvas.bind_all("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
    canvas.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
    canvas.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(+1, "units"))


def _unbind_wheel(canvas: tk.Canvas) -> None:
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        canvas.unbind_all(seq)


# ===========================================================================
# Filter dataclass for the timeline (#4)
# ===========================================================================

@dataclass
class _TimelineFilter:
    status: Optional[str] = None
    start:  Optional[str] = None
    end:    Optional[str] = None
    module: Optional[str] = None

    def get(self, key: str):
        return getattr(self, key, None)


# ===========================================================================
# AttendanceVisibilityService — features #1–#8
# ===========================================================================

_PRESENT_ONLY = {"present"}
_ATTENDED = {"present", "late", "excused"}
_WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DOW_REMAP = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}


class AttendanceVisibilityService:
    """Read-only views of the student's own attendance (#1–#8)."""

    def __init__(self, ctx: StudentContext, prefs: StudentPrefs) -> None:
        self.ctx = ctx
        self.prefs = prefs

    # --- #1 calendar -----------------------------------------------------
    @safe("Calendar")
    def show_calendar(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        win = _CalendarWindow(self.ctx, sid)
        win.show()
        audit(self.ctx, "student.calendar", "attendance", sid,
              win.current_month_str())

    # --- #2 gauges -------------------------------------------------------
    @safe("Attendance gauge")
    def show_gauges(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        thresholds = _load_gauge_thresholds(self.ctx.db)
        rows = self._fetch_module_attendance(sid)

        win = tk.Toplevel(self.ctx.parent)
        win.title("Attendance gauge")
        win.geometry("680x520")
        win.transient(self.ctx.parent)

        if not rows:
            tk.Label(win, text="No attendance data yet.",
                     fg="#6b7280", font=("Arial", 11)).pack(pady=40)
            audit(self.ctx, "student.gauge", "attendance", sid, "empty")
            return

        self._build_summary(win, rows, thresholds)
        self._build_module_list(win, rows, thresholds)
        audit(self.ctx, "student.gauge", "attendance", sid,
              f"modules={len(rows)}")

    def _fetch_module_attendance(self, sid: str) -> list[tuple]:
        try:
            return self.ctx.db.cur.execute(
                """SELECT m.module_code,
                          COALESCE(m.module_name, m.module_code),
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS present,
                          SUM(CASE WHEN a.status='late'    THEN 1 ELSE 0 END) AS late,
                          SUM(CASE WHEN a.status='excused' THEN 1 ELSE 0 END) AS excused,
                          SUM(CASE WHEN a.status='absent'  THEN 1 ELSE 0 END) AS absent,
                          COUNT(a.id) AS total,
                          CASE WHEN COUNT(a.id) = 0 THEN NULL
                               ELSE SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                                    * 100.0 / COUNT(a.id)
                          END AS pct_present,
                          CASE WHEN COUNT(a.id) = 0 THEN NULL
                               ELSE SUM(CASE WHEN a.status IN ('present','late','excused')
                                             THEN 1 ELSE 0 END)
                                    * 100.0 / COUNT(a.id)
                          END AS pct_attended
                   FROM modules m
                   JOIN student_modules sm ON sm.module_code = m.module_code
                   LEFT JOIN attendance a
                     ON a.module_code = m.module_code
                    AND a.student_id  = sm.student_id
                   WHERE sm.student_id = ?
                   GROUP BY m.module_code, m.module_name
                   ORDER BY pct_attended ASC NULLS LAST, m.module_code""",
                (sid,),
            ).fetchall()
        except sqlite3.Error:
            logger.exception("module attendance query failed sid=%s", sid)
            return []

    def _build_summary(self, parent, rows, thresholds: GaugeThresholds) -> None:
        counts = {"good": 0, "warn": 0, "poor": 0, "none": 0}
        for *_, total, _pct_present, pct_attended in rows:
            if not total:
                counts["none"] += 1
            else:
                counts[thresholds.band(pct_attended)] += 1

        bar = tk.Frame(parent, bg="#f8fafc")
        bar.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(bar, text="Summary",
                 font=("Arial", 11, "bold"), bg="#f8fafc").pack(side="left")
        for band in ("good", "warn", "poor"):
            tk.Label(bar, text=f"  {_GAUGE_LABELS[band]}: {counts[band]}",
                     fg="white", bg=_GAUGE_COLOURS[band], padx=8, pady=2,
                     font=("Arial", 10, "bold")).pack(side="left", padx=4)
        if counts["none"]:
            tk.Label(bar, text=f"  No data: {counts['none']}",
                     fg="#6b7280", bg="#f8fafc",
                     padx=8, pady=2).pack(side="left", padx=4)

    def _build_module_list(self, parent, rows,
                           thresholds: GaugeThresholds) -> None:
        outer = tk.Frame(parent)
        outer.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        inner = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Enter>", lambda _e: _bind_wheel(canvas))
        canvas.bind("<Leave>", lambda _e: _unbind_wheel(canvas))

        for code, name, present, late, excused, absent, total, \
                _pct_present, pct_attended in rows:
            self._render_module_row(inner, code, name, present, late, excused,
                                    absent, total, pct_attended, thresholds)

    def _render_module_row(self, parent, code, name, present, late,
                           excused, absent, total, pct_attended,
                           thresholds: GaugeThresholds) -> None:
        row = tk.Frame(parent, bd=1, relief="solid")
        row.pack(fill="x", pady=3)
        title = tk.Frame(row); title.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(title, text=f"{code} — {name}",
                 font=("Arial", 11, "bold"), anchor="w").pack(side="left")
        if not total:
            tk.Label(title, text="no sessions yet", fg="#6b7280").pack(side="right")
            tk.Frame(row, height=4).pack(fill="x")
            return
        band = thresholds.band(pct_attended)
        colour = _GAUGE_COLOURS[band]
        tk.Label(title, text=f"{pct_attended:.1f}%",
                 fg="white", bg=colour, padx=10, pady=2,
                 font=("Arial", 11, "bold")).pack(side="right")
        bar_wrap = tk.Frame(row, bg="#e5e7eb", height=10)
        bar_wrap.pack(fill="x", padx=8, pady=2)
        bar_wrap.pack_propagate(False)
        fill = tk.Frame(bar_wrap, bg=colour)
        fill.place(relx=0, rely=0,
                   relwidth=max(0.0, min(1.0, pct_attended / 100)), relheight=1)
        breakdown = (f"{total} sessions  ·  present {present}  ·  late {late}  ·  "
                     f"excused {excused}  ·  absent {absent}")
        tk.Label(row, text=breakdown, fg="#6b7280", anchor="w",
                 font=("Arial", 9)).pack(fill="x", padx=8, pady=(0, 6))

    # --- #3 streak -------------------------------------------------------
    @safe("Streak")
    def show_streak(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, status FROM attendance
                   WHERE student_id = ? AND status IS NOT NULL
                   ORDER BY date""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("streak query failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return

        if not rows:
            messagebox.showinfo("Streak", "No attendance recorded yet.",
                                parent=self.ctx.parent)
            audit(self.ctx, "student.streak", "attendance", sid, "empty")
            return

        present_now,  present_best,  _ = self._streaks(rows, _PRESENT_ONLY)
        attended_now, attended_best, _ = self._streaks(rows, _ATTENDED)
        last_date, last_status = rows[-1]
        msg = (f"Present-only streak\n"
               f"   current: {present_now}   best: {present_best}\n\n"
               f"Attended streak (present + late + excused)\n"
               f"   current: {attended_now}   best: {attended_best}\n\n"
               f"Last record: {last_date} — {last_status}")
        messagebox.showinfo("Streak", msg, parent=self.ctx.parent)
        audit(self.ctx, "student.streak", "attendance", sid,
              f"present_now={present_now} attended_now={attended_now}")

    @staticmethod
    def _streaks(rows: list[tuple[str, str]],
                 counted: set[str]) -> tuple[int, int, Optional[str]]:
        longest = cur = 0
        last_in_run: Optional[str] = None
        for d, st in rows:
            if st in counted:
                cur += 1
                longest = max(longest, cur)
                last_in_run = d
            else:
                cur = 0
                last_in_run = None
        return cur, longest, last_in_run

    # --- #4 timeline -----------------------------------------------------
    @safe("Timeline")
    def show_timeline(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        flt = self._ask_timeline_filters()
        if flt is None:
            return
        rows = self._fetch_timeline(sid, flt)
        title = f"My timeline ({len(rows)} rows)" + self._filter_suffix(flt)
        _show_table(self.ctx.parent, title,
                    ("date", "module", "status", "reason"), rows,
                    widths=[110, 140, 90, 360])
        audit(self.ctx, "student.timeline", "attendance", sid,
              f"n={len(rows)} status={flt.status or 'all'}")

    def _ask_timeline_filters(self) -> Optional[_TimelineFilter]:
        dlg = tk.Toplevel(self.ctx.parent)
        dlg.title("Timeline filters")
        dlg.transient(self.ctx.parent)
        dlg.grab_set()
        dlg.geometry("420x260")

        tk.Label(dlg, text="Filter my timeline",
                 font=("Arial", 11, "bold")).pack(pady=(10, 6))
        body = tk.Frame(dlg)
        body.pack(padx=14, pady=4, fill="x")

        tk.Label(body, text="Status:").grid(row=0, column=0, sticky="w", pady=4)
        status_var = tk.StringVar(value="(all)")
        ttk.Combobox(body, textvariable=status_var, state="readonly", width=20,
                     values=["(all)", "present", "absent", "late", "excused"]
                     ).grid(row=0, column=1, sticky="w", pady=4)

        tk.Label(body, text="Module:").grid(row=1, column=0, sticky="w", pady=4)
        try:
            enrolments = self.ctx.db.cur.execute(
                """SELECT m.module_code,
                          COALESCE(m.module_name, m.module_code)
                   FROM modules m
                   JOIN student_modules sm ON sm.module_code = m.module_code
                   WHERE sm.student_id = ?
                   ORDER BY m.module_code""",
                (self.ctx.sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("enrolments lookup failed")
            enrolments = []
        mod_label_to_code = {"(all)": None}
        for code, name in enrolments:
            mod_label_to_code[f"{code} — {name}"] = code
        mod_var = tk.StringVar(value="(all)")
        ttk.Combobox(body, textvariable=mod_var, state="readonly", width=30,
                     values=list(mod_label_to_code)
                     ).grid(row=1, column=1, sticky="w", pady=4)

        range_var = tk.StringVar(value="(no range)")
        tk.Label(body, text="Date range:").grid(row=2, column=0, sticky="w", pady=4)
        tk.Label(body, textvariable=range_var, fg="#374151"
                 ).grid(row=2, column=1, sticky="w", pady=4)
        chosen = {"start": None, "end": None}

        def pick_range():
            rng = pick_date_range(dlg, "Timeline date range")
            if rng:
                chosen["start"], chosen["end"] = rng
                range_var.set(f"{rng[0]}  →  {rng[1]}")

        def clear_range():
            chosen["start"] = chosen["end"] = None
            range_var.set("(no range)")

        btns = tk.Frame(body); btns.grid(row=3, column=0, columnspan=2, pady=6)
        tk.Button(btns, text="Pick…", command=pick_range,
                  relief="flat", bg="#2563eb", fg="white",
                  padx=10, pady=2).pack(side="left", padx=4)
        tk.Button(btns, text="Clear", command=clear_range,
                  relief="flat", bg="#6b7280", fg="white",
                  padx=10, pady=2).pack(side="left", padx=4)

        result: dict = {}

        def ok():
            result["filter"] = _TimelineFilter(
                status=None if status_var.get() == "(all)" else status_var.get(),
                module=mod_label_to_code.get(mod_var.get()),
                start=chosen["start"], end=chosen["end"])
            dlg.destroy()

        foot = tk.Frame(dlg); foot.pack(pady=10)
        tk.Button(foot, text="Apply", command=ok, bg="#2563eb", fg="white",
                  relief="flat", padx=18, pady=4).pack(side="left", padx=6)
        tk.Button(foot, text="Cancel", command=dlg.destroy, bg="#6b7280",
                  fg="white", relief="flat", padx=18, pady=4
                  ).pack(side="left", padx=6)
        dlg.wait_window()
        return result.get("filter")

    def _fetch_timeline(self, sid: str,
                        flt: _TimelineFilter) -> list[tuple]:
        q = ["""SELECT a.date,
                       COALESCE(m.module_name, a.module_code) AS module,
                       a.status,
                       COALESCE(a.reason, '') AS reason
                FROM attendance a
                LEFT JOIN modules m ON m.module_code = a.module_code
                WHERE a.student_id = ?"""]
        p: list = [sid]
        if flt.status: q.append("AND a.status = ?"); p.append(flt.status)
        if flt.module: q.append("AND a.module_code = ?"); p.append(flt.module)
        if flt.start:  q.append("AND a.date >= ?"); p.append(flt.start)
        if flt.end:    q.append("AND a.date <= ?"); p.append(flt.end)
        q.append("ORDER BY a.date DESC")
        try:
            return self.ctx.db.cur.execute(" ".join(q), p).fetchall()
        except sqlite3.Error:
            logger.exception("timeline fetch failed")
            return []

    @staticmethod
    def _filter_suffix(flt: _TimelineFilter) -> str:
        parts = []
        if flt.status: parts.append(flt.status)
        if flt.module: parts.append(flt.module)
        if flt.start or flt.end:
            parts.append(f"{flt.start or '…'}→{flt.end or '…'}")
        return f"  [{', '.join(parts)}]" if parts else ""

    # --- #5 export -------------------------------------------------------
    @safe("Export my data")
    def export_my_data(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        fmt = _combo_dialog(self.ctx.parent, "Export format",
                            "Format:", ["CSV", "JSON"])
        if not fmt:
            return
        try:
            attendance = self.ctx.db.get_absences(student_id=sid)
            requests = self.ctx.db.cur.execute(
                """SELECT id, module_code, date, reason, status, submitted_at
                   FROM absence_requests WHERE student_id = ?
                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("export query failed")
            messagebox.showerror("Error", "Could not load your data.",
                                 parent=self.ctx.parent)
            return
        att_hdr = ("id", "student", "module_code", "module_name",
                   "date", "status", "reason")
        req_hdr = ("id", "module_code", "date", "reason", "status", "submitted_at")
        try:
            if fmt == "CSV":
                path = self._write_two_csv(sid, att_hdr, attendance,
                                           req_hdr, requests)
            else:
                path = self._write_json(sid, att_hdr, attendance,
                                        req_hdr, requests)
        except OSError as e:
            messagebox.showerror("Write failed", str(e), parent=self.ctx.parent)
            return
        if not path:
            return
        audit(self.ctx, "student.export", "attendance", sid,
              f"{fmt.lower()} att={len(attendance)} req={len(requests)} -> {path}")
        messagebox.showinfo("Exported",
                            f"{len(attendance)} attendance row(s)\n"
                            f"{len(requests)} request row(s)\n\nSaved to:\n{path}",
                            parent=self.ctx.parent)

    def _write_two_csv(self, sid, att_hdr, att, req_hdr,
                       req) -> Optional[str]:
        path = filedialog.asksaveasfilename(
            parent=self.ctx.parent, defaultextension=".csv",
            initialfile=f"my_attendance_{sid}.csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return None
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["# Attendance"]); w.writerow(att_hdr); w.writerows(att)
            w.writerow([])
            w.writerow(["# Absence requests"]); w.writerow(req_hdr); w.writerows(req)
        return path

    def _write_json(self, sid, att_hdr, att, req_hdr,
                    req) -> Optional[str]:
        path = filedialog.asksaveasfilename(
            parent=self.ctx.parent, defaultextension=".json",
            initialfile=f"my_attendance_{sid}.json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return None
        payload = {
            "student_id": sid,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "attendance": [dict(zip(att_hdr, row)) for row in att],
            "absence_requests": [dict(zip(req_hdr, row)) for row in req],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
        return path

    # --- #6 compare-to-module -------------------------------------------
    @safe("Compare to module")
    def compare_to_module_average(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        rows = self._fetch_module_comparison(sid)
        if not rows:
            messagebox.showinfo("Compare to module",
                                "No attendance data to compare yet.",
                                parent=self.ctx.parent)
            return
        table = []
        for code, name, mine, module_avg, my_n, mod_n in rows:
            delta = (mine - module_avg) if mine is not None else None
            table.append((
                code, name,
                "—" if mine is None else f"{mine:.1f}",
                f"{module_avg:.1f}" if module_avg is not None else "—",
                "—" if delta is None else f"{delta:+.1f}",
                f"{my_n}/{mod_n}",
            ))
        _show_table(self.ctx.parent, "Me vs module average",
                    ("module", "name", "my %", "module avg %", "Δ",
                     "my sessions / total"),
                    table, widths=[100, 220, 80, 120, 80, 160])
        audit(self.ctx, "student.compare_module_avg", "attendance", sid,
              f"modules={len(rows)}")

    def _fetch_module_comparison(self, sid: str) -> list[tuple]:
        try:
            return self.ctx.db.cur.execute(
                """SELECT m.module_code,
                          COALESCE(m.module_name, m.module_code) AS name,
                          CASE
                            WHEN SUM(CASE WHEN a.student_id = ? THEN 1 ELSE 0 END) = 0
                            THEN NULL
                            ELSE SUM(CASE WHEN a.student_id = ?
                                           AND a.status IN ('present','late','excused')
                                          THEN 1 ELSE 0 END) * 100.0
                               / SUM(CASE WHEN a.student_id = ? THEN 1 ELSE 0 END)
                          END AS mine,
                          CASE
                            WHEN COUNT(a.id) = 0 THEN NULL
                            ELSE SUM(CASE WHEN a.status IN ('present','late','excused')
                                          THEN 1 ELSE 0 END) * 100.0
                               / COUNT(a.id)
                          END AS module_avg,
                          SUM(CASE WHEN a.student_id = ? THEN 1 ELSE 0 END) AS my_n,
                          COUNT(a.id) AS mod_n
                   FROM modules m
                   JOIN student_modules sm ON sm.module_code = m.module_code
                   LEFT JOIN attendance a  ON a.module_code  = m.module_code
                   WHERE sm.student_id = ?
                   GROUP BY m.module_code, m.module_name
                   HAVING my_n > 0
                   ORDER BY (mine - module_avg) ASC NULLS LAST, m.module_code""",
                (sid, sid, sid, sid, sid)).fetchall()
        except sqlite3.Error:
            logger.exception("module comparison failed")
            return []

    # --- #7 projection ---------------------------------------------------
    @safe("Projection")
    def project_absence_budget(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        threshold = self._ask_projection_threshold(sid)
        if threshold is None:
            return
        rows = self._fetch_module_attendance(sid)
        if not rows:
            messagebox.showinfo("Projection",
                                "No attendance data yet — nothing to project.",
                                parent=self.ctx.parent)
            return
        table = []
        for code, name, present, late, excused, absent, total, \
                _pct_present, pct_attended in rows:
            if not total:
                table.append((code, name, "—", "—", "—", "no sessions yet"))
                continue
            attended = present + late + excused
            budget = self._absence_budget(attended, total, threshold)
            verdict = self._budget_verdict(pct_attended, threshold, budget)
            table.append((
                code, name,
                f"{pct_attended:.1f}%",
                f"{threshold:.0f}%",
                "—" if budget is None else str(budget),
                verdict,
            ))
        _show_table(self.ctx.parent,
                    f"Absence budget (keep ≥ {threshold:.0f}%)",
                    ("module", "name", "current", "target", "can miss", "status"),
                    table, widths=[100, 220, 90, 80, 90, 200])
        audit(self.ctx, "student.projection", "attendance", sid,
              f"threshold={threshold} modules={len(rows)}")

    def _ask_projection_threshold(self, sid: str) -> Optional[float]:
        initial = self.prefs.get_float(sid, "projection.threshold", 80.0)
        val = simpledialog.askfloat(
            "Threshold", "Stay above what %? (1–100)",
            parent=self.ctx.parent,
            initialvalue=initial, minvalue=1.0, maxvalue=100.0)
        if val is None:
            return None
        try:
            self.prefs.set(sid, "projection.threshold", val)
        except sqlite3.Error:
            pass
        return val

    @staticmethod
    def _absence_budget(attended: int, total: int,
                        threshold_pct: float) -> Optional[int]:
        if attended * 100 < threshold_pct * total:
            return None
        if threshold_pct <= 0:
            return 10_000
        k = int((attended * 100) / threshold_pct) - total
        return max(k, 0)

    @staticmethod
    def _budget_verdict(pct_attended: float, threshold: float,
                        budget: Optional[int]) -> str:
        if budget is None:
            return f"already below {threshold:.0f}%"
        if budget == 0:
            return "at the limit"
        if pct_attended < threshold + 5:
            return "tight margin"
        return "comfortable"

    # --- #8 personal heatmap --------------------------------------------
    @safe("Personal heatmap")
    def show_personal_heatmap(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            raw = self.ctx.db.cur.execute(
                """SELECT CAST(strftime('%w', date) AS INTEGER) AS dow,
                          status, COUNT(*)
                   FROM attendance
                   WHERE student_id = ? AND status IS NOT NULL
                   GROUP BY dow, status""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("heatmap query failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return

        buckets: list[dict[str, int]] = [
            {"present": 0, "late": 0, "excused": 0, "absent": 0}
            for _ in _WEEKDAY_NAMES
        ]
        for dow, status, n in raw:
            idx = _DOW_REMAP.get(dow)
            if idx is None or status not in buckets[idx]:
                continue
            buckets[idx][status] = n

        if not any(sum(b.values()) for b in buckets):
            messagebox.showinfo("Personal heatmap",
                                "No attendance records yet.",
                                parent=self.ctx.parent)
            return

        self._show_heatmap_window(buckets)
        audit(self.ctx, "student.heatmap", "attendance", sid,
              f"sessions={sum(sum(b.values()) for b in buckets)}")

    def _show_heatmap_window(self, buckets: list[dict[str, int]]) -> None:
        win = tk.Toplevel(self.ctx.parent)
        win.title("My attendance by day-of-week")
        win.geometry("680x360")
        win.transient(self.ctx.parent)
        tk.Label(win, text="Attendance pattern by day of week",
                 font=("Arial", 12, "bold")).pack(pady=(10, 4))

        worst = self._worst_day(buckets)
        if worst is not None:
            tk.Label(win,
                     text=f"Most absences fall on {_WEEKDAY_NAMES[worst]}.",
                     fg="#6b7280").pack(pady=(0, 8))

        grid = tk.Frame(win); grid.pack(padx=12, pady=4, fill="x")
        headers = ("day", "present", "late", "excused", "absent",
                   "total", "attended %")
        for c, h in enumerate(headers):
            tk.Label(grid, text=h, font=("Arial", 10, "bold"),
                     width=10, anchor="center"
                     ).grid(row=0, column=c, padx=2, pady=2)
        for r, day in enumerate(_WEEKDAY_NAMES, start=1):
            b = buckets[r - 1]
            total = sum(b.values())
            attended = b["present"] + b["late"] + b["excused"]
            pct = (attended / total * 100) if total else None
            absent_rate = (b["absent"] / total) if total else 0
            bg = self._absence_rate_bg(absent_rate, has_data=bool(total))
            tk.Label(grid, text=day, width=10, bg=bg,
                     font=("Arial", 10, "bold")
                     ).grid(row=r, column=0, padx=2, pady=2, sticky="ew")
            for c, key in enumerate(("present", "late", "excused", "absent"),
                                    start=1):
                tk.Label(grid, text=str(b[key]), width=10, bg=bg
                         ).grid(row=r, column=c, padx=2, pady=2, sticky="ew")
            tk.Label(grid, text=str(total) if total else "—",
                     width=10, bg=bg
                     ).grid(row=r, column=5, padx=2, pady=2, sticky="ew")
            tk.Label(grid, text="—" if pct is None else f"{pct:.0f}%",
                     width=10, bg=bg, font=("Arial", 10, "bold")
                     ).grid(row=r, column=6, padx=2, pady=2, sticky="ew")

    @staticmethod
    def _worst_day(buckets: list[dict[str, int]]) -> Optional[int]:
        worst_idx, worst_rate = None, -1.0
        for i, b in enumerate(buckets):
            tot = sum(b.values())
            if not tot:
                continue
            rate = b["absent"] / tot
            if rate > worst_rate:
                worst_rate, worst_idx = rate, i
        return worst_idx if worst_rate > 0 else None

    @staticmethod
    def _absence_rate_bg(rate: float, *, has_data: bool) -> str:
        if not has_data:
            return "#f3f4f6"
        if rate <= 0.05: return "#dcfce7"
        if rate <= 0.15: return "#fef9c3"
        if rate <= 0.30: return "#fed7aa"
        return "#fecaca"


# ===========================================================================
# RequestService — features #9–#16, #51
# ===========================================================================

class RequestService:
    """Submit, attach, withdraw, resubmit, draft, and bulk-request absences."""

    def __init__(self, ctx: StudentContext, prefs: StudentPrefs,
                 picker: ModulePicker) -> None:
        self.ctx = ctx
        self.prefs = prefs
        self.picker = picker

    # internal helpers
    def _existing_active_dates(self, sid: str, module_code: str,
                               iso_dates: Iterable[str]) -> set[str]:
        iso_dates = list(iso_dates)
        if not iso_dates:
            return set()
        try:
            placeholders = ",".join("?" * len(iso_dates))
            rows = self.ctx.db.cur.execute(
                f"""SELECT date FROM absence_requests
                    WHERE student_id=? AND module_code=?
                      AND status NOT IN ('rejected','withdrawn')
                      AND date IN ({placeholders})""",
                [sid, module_code, *iso_dates]).fetchall()
            return {r[0] for r in rows}
        except sqlite3.Error:
            logger.exception("dup-date lookup failed")
            return set()

    # --- #9 quick-submit -------------------------------------------------
    @safe("Quick-submit")
    def quick_submit_from_template(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            templates = self.ctx.db.cur.execute(
                "SELECT name, body FROM abs_tracker_request_templates ORDER BY name"
            ).fetchall()
        except sqlite3.Error:
            logger.exception("template fetch failed")
            messagebox.showerror("Error", "Could not load templates.",
                                 parent=self.ctx.parent)
            return
        if not templates:
            messagebox.showinfo("No templates",
                                "Ask an admin to create request templates first.",
                                parent=self.ctx.parent)
            return
        tmap = {r[0]: r[1] for r in templates}
        tpl = _combo_dialog(self.ctx.parent, "Template",
                            "Pick template:", list(tmap.keys()))
        if not tpl:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        if self._existing_active_dates(sid, mcode, [d]):
            messagebox.showwarning("Duplicate",
                                   f"You already have a request for {mlabel} on {d}.",
                                   parent=self.ctx.parent)
            return
        body = tmap[tpl]
        if not Prompt.confirm(self.ctx.parent, "Confirm",
                              f"Submit absence request?\n\nModule: {mlabel}\n"
                              f"Date: {d}\nTemplate: {tpl}\n\n{body[:300]}"):
            return
        try:
            self.ctx.db.submit_request(sid, mcode, d, body)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", f"Could not submit: {e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.quick_submit", "absence_requests", sid, tpl)
        messagebox.showinfo("Submitted", "Request submitted.",
                            parent=self.ctx.parent)

    # --- #10 attach evidence --------------------------------------------
    @safe("Attach evidence")
    def attach_evidence(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT r.id, r.date, r.module_code, r.status,
                          (SELECT COUNT(*) FROM abs_tracker_request_attachments
                           WHERE request_id=r.id)
                   FROM absence_requests r
                   WHERE r.student_id=? ORDER BY r.id DESC""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("requests fetch failed")
            messagebox.showerror("Error", "Could not load your requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("No requests", "You have no requests.",
                                parent=self.ctx.parent)
            return
        m = {f"#{r[0]} {r[1]} {r[2]} [{r[3]}] ({r[4]} attached)": r[0]
             for r in rows}
        pick = _combo_dialog(self.ctx.parent, "Request",
                             "Pick request:", list(m.keys()))
        if not pick:
            return
        rid = m[pick]
        path = filedialog.askopenfilename(
            parent=self.ctx.parent,
            filetypes=[("Documents", "*.pdf *.doc *.docx *.txt *.png *.jpg *.jpeg"),
                       ("All files", "*.*")])
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            messagebox.showerror("Missing", f"File not found:\n{path}",
                                 parent=self.ctx.parent)
            return
        try:
            size = p.stat().st_size
        except OSError as e:
            messagebox.showerror("Error", f"Cannot read file: {e}",
                                 parent=self.ctx.parent)
            return
        if size > 25 * 1024 * 1024:
            messagebox.showerror("Too large",
                                 f"File is {size/1024/1024:.1f} MB (max 25 MB).",
                                 parent=self.ctx.parent)
            return
        try:
            self.ctx.db.cur.execute(
                "INSERT INTO abs_tracker_request_attachments (request_id, file_path) VALUES (?, ?)",
                (rid, str(p.resolve())))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Could not save attachment: {e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.attach", "absence_requests", rid, p.name)
        messagebox.showinfo("Attached",
                            f"Attached {p.name} ({size/1024:.0f} KB).",
                            parent=self.ctx.parent)

    # --- #11 status tracker ---------------------------------------------
    @safe("Status tracker")
    def show_status_tracker(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, date, module_code, status, submitted_at,
                          substr(reason,1,60)
                   FROM absence_requests WHERE student_id=?
                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("status tracker fetch failed")
            messagebox.showerror("Error", "Could not load your requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("No requests",
                                "You have no absence requests yet.",
                                parent=self.ctx.parent)
            return
        counts: dict[str, int] = {}
        for r in rows:
            counts[r[3] or "?"] = counts.get(r[3] or "?", 0) + 1
        summary = " | ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        _show_table(self.ctx.parent,
                    f"My request statuses — {len(rows)} total ({summary})",
                    ("id", "date", "module", "status", "submitted", "reason"),
                    rows, widths=[60, 100, 110, 90, 150, 360])

    # --- #12 withdraw ---------------------------------------------------
    @safe("Withdraw")
    def withdraw_pending(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, date, module_code FROM absence_requests
                   WHERE student_id=? AND status='pending'
                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("pending fetch failed")
            messagebox.showerror("Error", "Could not load pending requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("No pending", "Nothing to withdraw.",
                                parent=self.ctx.parent)
            return
        m = {f"#{r[0]} {r[1]} {r[2]}": r[0] for r in rows}
        pick = _combo_dialog(self.ctx.parent, "Withdraw",
                             "Which?", list(m.keys()))
        if not pick:
            return
        rid = m[pick]
        if not Prompt.confirm(self.ctx.parent, "Confirm withdrawal",
                              f"Withdraw request {pick}?\nThis cannot be undone."):
            return
        try:
            self.ctx.db.cur.execute(
                """UPDATE absence_requests
                   SET status='withdrawn',
                       reason = CASE
                           WHEN reason LIKE '%[withdrawn]%' THEN reason
                           ELSE COALESCE(reason,'') || ' [withdrawn]'
                       END
                   WHERE id=? AND status='pending'""", (rid,))
            changed = self.ctx.db.cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Could not withdraw: {e}",
                                 parent=self.ctx.parent)
            return
        if changed == 0:
            messagebox.showwarning("Already actioned",
                                   "This request is no longer pending.",
                                   parent=self.ctx.parent)
            return
        audit(self.ctx, "student.withdraw", "absence_requests", rid, "")
        messagebox.showinfo("Withdrawn", "Request withdrawn.",
                            parent=self.ctx.parent)

    # --- #13 resubmit ---------------------------------------------------
    @safe("Resubmit")
    def resubmit_rejected(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, date, module_code, reason FROM absence_requests
                   WHERE student_id=? AND status='rejected'
                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("rejected fetch failed")
            messagebox.showerror("Error", "Could not load rejected requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("None", "No rejected requests.",
                                parent=self.ctx.parent)
            return
        m = {f"#{r[0]} {r[1]} {r[2]}": r for r in rows}
        pick = _combo_dialog(self.ctx.parent, "Resubmit",
                             "Which?", list(m.keys()))
        if not pick:
            return
        rid, d, mc, old = m[pick]
        if self._existing_active_dates(sid, mc, [d]):
            messagebox.showwarning("Duplicate",
                                   f"Active request already exists for {mc} on {d}.",
                                   parent=self.ctx.parent)
            return
        new = Prompt.non_empty(self.ctx.parent, "New reason",
                               f"(was: {old or '—'})\n\nNew reason (min 5 chars):",
                               min_len=5)
        if not new:
            return
        try:
            self.ctx.db.submit_request(sid, mc, d, new + " [resubmitted]")
        except sqlite3.Error as e:
            messagebox.showerror("Failed", f"Could not resubmit: {e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.resubmit", "absence_requests", rid, new[:80])
        messagebox.showinfo("Submitted", "Resubmitted.", parent=self.ctx.parent)

    # --- #14 bulk request -----------------------------------------------
    @safe("Bulk request")
    def bulk_multi_day_request(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        start = Prompt.iso_date(self.ctx.parent, "Start", "Start (YYYY-MM-DD):")
        if not start:
            return
        days = simpledialog.askinteger(
            "Days", "How many consecutive days?",
            parent=self.ctx.parent, minvalue=1, maxvalue=30)
        if not days:
            return
        skip_weekends = Prompt.confirm(self.ctx.parent, "Weekends",
                                       "Skip Saturdays and Sundays?")
        reason = Prompt.non_empty(self.ctx.parent, "Reason",
                                  "Reason (min 5 chars):", min_len=5)
        if not reason:
            return
        d0 = datetime.strptime(start, "%Y-%m-%d").date()
        candidate = [d0 + timedelta(days=k) for k in range(days)]
        if skip_weekends:
            candidate = [d for d in candidate if d.weekday() < 5]
        if not candidate:
            messagebox.showinfo("Nothing to submit",
                                "All selected dates were weekends.",
                                parent=self.ctx.parent)
            return
        iso = [d.isoformat() for d in candidate]
        dupes = self._existing_active_dates(sid, mcode, iso)
        to_submit = [d for d in iso if d not in dupes]
        if not to_submit:
            messagebox.showinfo("All duplicates",
                                "All selected dates already have active requests.",
                                parent=self.ctx.parent)
            return
        msg = (f"Submit {len(to_submit)} request(s) for {mlabel}?\n"
               f"Range: {to_submit[0]} → {to_submit[-1]}")
        if dupes:
            msg += f"\n\nSkipping {len(dupes)} duplicate date(s)."
        if not Prompt.confirm(self.ctx.parent, "Confirm bulk", msg):
            return
        try:
            for d in to_submit:
                self.ctx.db.cur.execute(
                    """INSERT INTO absence_requests
                       (student_id, module_code, date, reason)
                       VALUES (?, ?, ?, ?)""", (sid, mcode, d, reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Bulk submit failed:\n{e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.bulk_request", "absence_requests", sid,
              f"{mcode} {to_submit[0]}..{to_submit[-1]} x{len(to_submit)}")
        extra = f" ({len(dupes)} skipped)" if dupes else ""
        messagebox.showinfo("Submitted",
                            f"Submitted {len(to_submit)} request(s){extra}.",
                            parent=self.ctx.parent)

    # --- #15 save draft -------------------------------------------------
    @safe("Save draft")
    def save_draft(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        reason = (simpledialog.askstring("Reason", "Reason (optional):",
                                         parent=self.ctx.parent) or "").strip()
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_student_drafts
                   (student_id, module_code, date, reason) VALUES (?,?,?,?)""",
                (sid, mcode, d, reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Could not save draft: {e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.draft", "abs_tracker_student_drafts", sid, mcode)
        messagebox.showinfo("Saved", f"Draft saved for {mlabel} on {d}.",
                            parent=self.ctx.parent)

    # --- #16 history export ---------------------------------------------
    @safe("Request history export")
    def export_request_history(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            statuses = [r[0] for r in self.ctx.db.cur.execute(
                """SELECT DISTINCT COALESCE(status,'?') FROM absence_requests
                   WHERE student_id=? ORDER BY 1""", (sid,)).fetchall()]
        except sqlite3.Error:
            logger.exception("history status fetch failed")
            messagebox.showerror("Error", "Could not load your history.",
                                 parent=self.ctx.parent)
            return
        if not statuses:
            messagebox.showinfo("Nothing to export", "You have no requests.",
                                parent=self.ctx.parent)
            return
        choice = _combo_dialog(self.ctx.parent, "Filter", "Status:",
                               ["(all)"] + statuses)
        if choice is None:
            return
        try:
            if choice == "(all)":
                rows = self.ctx.db.cur.execute(
                    """SELECT id, date, module_code, status, submitted_at, reason
                       FROM absence_requests WHERE student_id=?
                       ORDER BY submitted_at DESC""", (sid,)).fetchall()
            else:
                rows = self.ctx.db.cur.execute(
                    """SELECT id, date, module_code, status, submitted_at, reason
                       FROM absence_requests
                       WHERE student_id=? AND COALESCE(status,'?')=?
                       ORDER BY submitted_at DESC""", (sid, choice)).fetchall()
        except sqlite3.Error:
            logger.exception("history rows fetch failed")
            messagebox.showerror("Error", "Could not load rows.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Empty", f"No requests with status '{choice}'.",
                                parent=self.ctx.parent)
            return
        path = _export_rows_to_csv(
            rows, ("id", "date", "module", "status", "submitted", "reason"),
            self.ctx.parent)
        if path:
            audit(self.ctx, "student.history_export", "absence_requests", sid,
                  f"{choice}:{len(rows)}:{path}")
            messagebox.showinfo("Saved",
                                f"Exported {len(rows)} row(s) to:\n{path}",
                                parent=self.ctx.parent)

    # --- #51 request time off (date picker) -----------------------------
    @safe("Request time off")
    def request_time_off(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        rng = pick_date_range(self.ctx.parent, "Time-off dates")
        if not rng:
            return
        start, end = rng
        reason = Prompt.non_empty(self.ctx.parent, "Reason",
                                  "Reason for time off (min 3 chars):", min_len=3)
        if not reason:
            return
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
        candidate = [(d0 + timedelta(days=k)).isoformat()
                     for k in range((d1 - d0).days + 1)]
        dupes = self._existing_active_dates(sid, mcode, candidate)
        to_submit = [d for d in candidate if d not in dupes]
        if not to_submit:
            messagebox.showinfo("All duplicates",
                                "All selected dates already have active requests.",
                                parent=self.ctx.parent)
            return
        try:
            for d in to_submit:
                self.ctx.db.cur.execute(
                    """INSERT INTO absence_requests
                       (student_id, module_code, date, reason)
                       VALUES (?, ?, ?, ?)""", (sid, mcode, d, reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Submit failed:\n{e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.request_time_off", "absence_requests", sid,
              f"{mcode} {start}..{end} ({len(to_submit)})")
        extra = f" ({len(dupes)} skipped)" if dupes else ""
        messagebox.showinfo("Submitted",
                            f"{len(to_submit)} request(s) submitted{extra}.",
                            parent=self.ctx.parent)


# ===========================================================================
# NotificationService — features #17–#22
# ===========================================================================

class NotificationService:
    """Reminders, alerts, channel preferences, and DND hours."""

    def __init__(self, ctx: StudentContext, prefs: StudentPrefs) -> None:
        self.ctx = ctx
        self.prefs = prefs

    # --- #17 -----------------------------------------------------------
    @safe("Class reminder")
    def set_class_reminder(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        current = self.prefs.get_int(sid, "reminder_mins", 0)
        mins = simpledialog.askinteger(
            "Minutes",
            f"Remind me how many minutes before class? (current {current})",
            parent=self.ctx.parent, minvalue=0, maxvalue=240)
        if mins is None:
            return
        try:
            self.prefs.set(sid, "reminder_mins", mins)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.reminder", "prefs", sid, f"mins={mins}")
        messagebox.showinfo("Saved",
                            f"Reminder = {mins} min before class.",
                            parent=self.ctx.parent)

    # --- #18 -----------------------------------------------------------
    @safe("Low-attendance alert")
    def set_low_attendance_alert(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        current = self.prefs.get_float(sid, "self_threshold", 80.0)
        pct = simpledialog.askfloat(
            "Threshold",
            f"Alert me if I drop below %? (current {current:g})",
            parent=self.ctx.parent, minvalue=0, maxvalue=100)
        if pct is None:
            return
        try:
            self.prefs.set(sid, "self_threshold", pct)
            row = self.ctx.db.cur.execute(
                """SELECT SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0
                          /NULLIF(COUNT(*),0)*100
                   FROM attendance WHERE student_id=?""", (sid,)).fetchone()
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        current_pct = row[0] if row and row[0] is not None else None
        msg = f"Self-threshold saved: {pct}%"
        if current_pct is not None and current_pct < pct:
            msg += f"\n⚠ Already below: {current_pct:.1f}%"
        audit(self.ctx, "student.self_threshold", "prefs", sid, str(pct))
        messagebox.showinfo("Saved", msg, parent=self.ctx.parent)

    # --- #19 -----------------------------------------------------------
    @safe("Deadline alerts")
    def show_upcoming_deadlines(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, name, event_type FROM academic_calendar_events
                   WHERE date >= date('now') ORDER BY date LIMIT 30"""
            ).fetchall()
        except sqlite3.Error:
            logger.exception("deadlines fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Upcoming deadlines",
                    ("date", "name", "type"), rows, widths=[110, 500, 160])

    # --- #20 -----------------------------------------------------------
    @safe("Parent notifications log")
    def show_parent_notifications_log(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT created_date, notification_type,
                          notification_content, read_status
                   FROM parent_notifications WHERE student_id=?
                   ORDER BY created_date DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("parent notifs fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Notifications sent about me",
                    ("when", "type", "content", "read?"), rows,
                    widths=[160, 140, 450, 80])

    # --- #21 -----------------------------------------------------------
    @safe("Notification preferences")
    def edit_channel_preferences(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        win = tk.Toplevel(self.ctx.parent)
        win.title("Notification channels")
        win.geometry("320x220")
        vars_: dict[str, tk.IntVar] = {}
        for key, label in [("notif_email", "Email"),
                           ("notif_inapp", "In-app"),
                           ("notif_sms", "SMS")]:
            v = tk.IntVar(value=self.prefs.get_int(sid, key, 1))
            vars_[key] = v
            tk.Checkbutton(win, text=label, variable=v
                           ).pack(anchor="w", padx=20, pady=4)

        def save():
            try:
                for k, v in vars_.items():
                    self.prefs.set(sid, k, v.get())
            except sqlite3.Error as e:
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "student.notif_prefs", "prefs", sid,
                  json.dumps({k: v.get() for k, v in vars_.items()}))
            messagebox.showinfo("Saved", "Preferences updated.", parent=win)
            win.destroy()

        tk.Button(win, text="Save", command=save, bg="#2563eb", fg="white",
                  relief="flat", padx=20, pady=6).pack(pady=10)

    # --- #22 -----------------------------------------------------------
    @safe("DND hours")
    def set_dnd_hours(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        cur_start = self.prefs.get(sid, "dnd_start", "22:00")
        cur_end   = self.prefs.get(sid, "dnd_end", "07:00")
        start = Prompt.hhmm(self.ctx.parent, "DND start",
                            "Start (HH:MM):", initial=cur_start)
        if start is None:
            return
        end = Prompt.hhmm(self.ctx.parent, "DND end",
                          "End (HH:MM):", initial=cur_end)
        if end is None:
            return
        try:
            self.prefs.set(sid, "dnd_start", start)
            self.prefs.set(sid, "dnd_end", end)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.dnd", "prefs", sid, f"{start}-{end}")
        messagebox.showinfo("Saved", "Do-not-disturb hours updated.",
                            parent=self.ctx.parent)


# ===========================================================================
# PlanningService — features #23–#28
# ===========================================================================

class PlanningService:
    """Goals, budgets, term forecast, ICS export, recovery, wellbeing check-in."""

    def __init__(self, ctx: StudentContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #23 -----------------------------------------------------------
    @safe("Attendance goals")
    def set_per_module_goal(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        pct = simpledialog.askfloat("Target", "Target %:",
                                    parent=self.ctx.parent,
                                    minvalue=0, maxvalue=100, initialvalue=90)
        if pct is None:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_student_goals
                   (student_id, module_code, target_pct) VALUES (?,?,?)""",
                (sid, mcode, pct))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.goal", "abs_tracker_student_goals", sid,
              f"{mcode} {pct}")
        messagebox.showinfo("Saved", f"Goal saved: {mlabel} = {pct}%",
                            parent=self.ctx.parent)

    # --- #24 -----------------------------------------------------------
    @safe("Attendance budget")
    def show_attendance_budget(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        def_pct = float(_get_setting(self.ctx.db, "default_min_pct", 80) or 80)
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.module_code,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS p,
                          COUNT(*) AS n,
                          COALESCE(p.min_percent, ?) AS thr
                   FROM attendance a
                   LEFT JOIN abs_tracker_module_policy p
                          ON p.module_code = a.module_code
                   WHERE a.student_id=?
                   GROUP BY a.module_code""", (def_pct, sid)).fetchall()
        except sqlite3.Error:
            logger.exception("budget fetch failed")
            rows = []
        out = []
        for mc, p, n, thr in rows:
            if not n:
                continue
            k = 0
            while (p / (n + k + 1)) * 100 >= thr and k < 500:
                k += 1
            out.append((mc, f"{p / n * 100:.1f}%", f"{thr:.0f}%", k))
        _show_table(self.ctx.parent, "Attendance budget",
                    ("module", "current", "threshold", "can miss"), out)

    # --- #25 -----------------------------------------------------------
    @safe("Term forecast")
    def show_term_forecast(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT module_code,
                          SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                            *1.0/NULLIF(COUNT(*),0)*100,
                          COUNT(*)
                   FROM attendance WHERE student_id=?
                   GROUP BY module_code""", (sid,)).fetchall()
            sem = self.ctx.db.cur.execute(
                "SELECT start_date, end_date FROM semesters "
                "ORDER BY start_date DESC LIMIT 1").fetchone()
        except sqlite3.Error:
            logger.exception("term forecast fetch failed")
            rows, sem = [], None
        est_weeks = 12
        if sem and sem[0] and sem[1]:
            try:
                est_weeks = max(1, (datetime.fromisoformat(sem[1])
                                    - datetime.fromisoformat(sem[0])).days // 7)
            except ValueError:
                logger.debug("semester dates unparseable", exc_info=True)
        out = [(mc, f"{(pct or 0):.1f}%", n, est_weeks, f"{(pct or 0):.1f}%")
               for mc, pct, n in rows]
        _show_table(self.ctx.parent, "Term forecast (current rate)",
                    ("module", "now", "sessions", "est weeks", "projected"), out)

    # --- #26 -----------------------------------------------------------
    @safe("Calendar sync")
    def export_calendar_ics(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, module_code, status FROM attendance
                   WHERE student_id=? ORDER BY date""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("ics fetch failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Nothing", "No attendance rows to export.",
                                parent=self.ctx.parent)
            return
        path = filedialog.asksaveasfilename(
            parent=self.ctx.parent, defaultextension=".ics",
            initialfile=f"attendance_{sid}.ics")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
                         "PRODID:-//AbsenceTracker//EN\r\n")
                for d, mc, st in rows:
                    try:
                        dt = datetime.strptime(d, "%Y-%m-%d").strftime("%Y%m%d")
                    except ValueError:
                        continue
                    fh.write(f"BEGIN:VEVENT\r\nUID:{sid}-{mc}-{d}@abs\r\n"
                             f"DTSTART;VALUE=DATE:{dt}\r\nDTEND;VALUE=DATE:{dt}\r\n"
                             f"SUMMARY:{mc} — {st}\r\nEND:VEVENT\r\n")
                fh.write("END:VCALENDAR\r\n")
        except OSError as e:
            messagebox.showerror("Write failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.ics", "attendance", sid, path)
        messagebox.showinfo("Exported", f"ICS written:\n{path}",
                            parent=self.ctx.parent)

    # --- #27 -----------------------------------------------------------
    @safe("Recovery plan")
    def show_recovery_plan(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, module_code, COALESCE(reason,'')
                   FROM attendance
                   WHERE student_id=? AND status IN ('absent','late')
                   ORDER BY date DESC LIMIT 10""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("recovery fetch failed")
            rows = []
        suggestions = [
            (d, mc,
             "Request notes + review recording; book office hours this week.")
            for d, mc, _r in rows
        ]
        _show_table(self.ctx.parent, "Recovery plan",
                    ("date", "module", "suggested action"),
                    suggestions, widths=[100, 120, 620])

    # --- #28 -----------------------------------------------------------
    @safe("Wellbeing check-in")
    def log_wellbeing_checkin(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        abs_id = simpledialog.askinteger("Attendance id",
                                         "Attendance row id (from My Absences):",
                                         parent=self.ctx.parent)
        if abs_id is None:
            return
        note = Prompt.non_empty(self.ctx.parent, "Note",
                                "Private note to self:", min_len=1)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_wellbeing_flags
                   (student_id, attendance_id, note) VALUES (?,?,?)""",
                (sid, abs_id, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.wellbeing",
              "abs_tracker_wellbeing_flags", sid, str(abs_id))
        messagebox.showinfo("Saved", "Check-in saved.",
                            parent=self.ctx.parent)


# ===========================================================================
# SupportService — features #29–#35
# ===========================================================================

class SupportService:
    """Notes, office hours, study buddies, recordings, wellbeing, advising."""

    def __init__(self, ctx: StudentContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #29 -----------------------------------------------------------
    @safe("Request notes")
    def request_classmate_notes(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, _ = picked
        d = Prompt.iso_date(self.ctx.parent, "Date", "Session date (YYYY-MM-DD):")
        if not d:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_note_requests
                   (requester_id, module_code, date) VALUES (?,?,?)""",
                (sid, mcode, d))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.note_request", "abs_tracker_note_requests",
              sid, f"{mcode} {d}")
        messagebox.showinfo("Requested",
                            "Classmates will see your request on the peer board.",
                            parent=self.ctx.parent)

    # --- #30 -----------------------------------------------------------
    @safe("Book office hours")
    def book_office_hours(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS office_hour_bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, module_code TEXT,
                    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending')""")
            self.ctx.db.cur.execute(
                "INSERT INTO office_hour_bookings (student_id, module_code) VALUES (?,?)",
                (sid, mcode))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.office_hours", "office_hour_bookings",
              sid, mcode)
        messagebox.showinfo("Requested",
                            f"Office-hours request logged for {mlabel}.",
                            parent=self.ctx.parent)

    # --- #31 -----------------------------------------------------------
    @safe("Study buddy")
    def join_study_buddy_pool(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        try:
            self.ctx.db.cur.execute(
                """INSERT OR IGNORE INTO abs_tracker_study_buddies
                   (student_id, module_code) VALUES (?,?)""", (sid, mcode))
            self.ctx.db.conn.commit()
            others = self.ctx.db.cur.execute(
                """SELECT b.student_id,
                          TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,''))
                   FROM abs_tracker_study_buddies b
                   LEFT JOIN students s ON s.student_id = b.student_id
                   WHERE b.module_code=? AND b.student_id<>?""",
                (mcode, sid)).fetchall()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.study_buddy", "abs_tracker_study_buddies",
              sid, mcode)
        _show_table(self.ctx.parent, f"Study buddies for {mlabel}",
                    ("student_id", "name"), others, widths=[140, 320])

    # --- #32 -----------------------------------------------------------
    @safe("Recorded lectures")
    def show_recorded_lectures(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS virtual_recordings (
                    id INTEGER PRIMARY KEY,
                    module_code TEXT, date TEXT, url TEXT, title TEXT)""")
            rows = self.ctx.db.cur.execute(
                """SELECT a.date, a.module_code,
                          COALESCE(vr.title,''), COALESCE(vr.url,'')
                   FROM attendance a
                   LEFT JOIN virtual_recordings vr
                          ON vr.module_code = a.module_code AND vr.date = a.date
                   WHERE a.student_id=? AND a.status IN ('absent','excused')
                   ORDER BY a.date DESC LIMIT 30""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("recordings fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Recordings for my missed sessions",
                    ("date", "module", "title", "url"), rows,
                    widths=[100, 110, 300, 340])

    # --- #33 -----------------------------------------------------------
    @safe("Wellbeing flag")
    def submit_wellbeing_flag(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        note = Prompt.non_empty(
            self.ctx.parent, "Confidential note",
            "Brief note (visible to wellbeing staff only):", min_len=3)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_wellbeing_flags
                   (student_id, attendance_id, note) VALUES (?, NULL, ?)""",
                (sid, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.wellbeing_flag",
              "abs_tracker_wellbeing_flags", sid, "(redacted)")
        messagebox.showinfo("Flagged",
                            "Thanks — wellbeing staff will review your flag.",
                            parent=self.ctx.parent)

    # --- #34 -----------------------------------------------------------
    @safe("Support resources")
    def show_support_resources(self) -> None:
        resources = [
            ("Counselling & Wellbeing", "Book: /student-support/counselling"),
            ("Disability Services",      "Contact: disability@university.edu"),
            ("Academic Advising",        "Portal: /advising"),
            ("Tutoring",                 "Find a tutor: /tutoring"),
            ("Financial Hardship",       "Apply: /financial-aid/hardship"),
            ("Chaplaincy",               "Quiet space: Campus centre rm 12"),
        ]
        _show_table(self.ctx.parent, "Support resources",
                    ("service", "how"), resources, widths=[240, 520])

    # --- #35 -----------------------------------------------------------
    @safe("Self-refer to advising")
    def self_refer_to_advising(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        topic = Prompt.non_empty(self.ctx.parent, "Topic",
                                 "What's it about?", min_len=3)
        if not topic:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS advising_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, topic TEXT,
                    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending')""")
            self.ctx.db.cur.execute(
                "INSERT INTO advising_appointments (student_id, topic) VALUES (?,?)",
                (sid, topic))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.advising", "advising_appointments",
              sid, topic[:120])
        messagebox.showinfo("Submitted", "Advising request submitted.",
                            parent=self.ctx.parent)


# ===========================================================================
# SocialService — features #36–#39
# ===========================================================================

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
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS study_group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER, student_id TEXT,
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

class AppealsService:
    """Disputes against attendance records and appeals on rejected requests."""

    def __init__(self, ctx: StudentContext) -> None:
        self.ctx = ctx

    # --- #40 -----------------------------------------------------------
    @safe("Dispute record")
    def dispute_attendance_record(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        aid = simpledialog.askinteger("Attendance id",
                                      "Row id (from My Absences):",
                                      parent=self.ctx.parent)
        if aid is None:
            return
        reason = Prompt.non_empty(
            self.ctx.parent, "Reason",
            "Why do you believe this is wrong?", min_len=10)
        if not reason:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_attendance_disputes
                   (student_id, attendance_id, reason) VALUES (?,?,?)""",
                (sid, aid, reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.dispute",
              "abs_tracker_attendance_disputes", sid, f"aid={aid}")
        messagebox.showinfo("Submitted", "Dispute raised.",
                            parent=self.ctx.parent)

    # --- #41 -----------------------------------------------------------
    @safe("Dispute history")
    def show_dispute_history(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, attendance_id, reason, status, created_at,
                          COALESCE(outcome,''), COALESCE(resolved_at,'')
                   FROM abs_tracker_attendance_disputes
                   WHERE student_id=? ORDER BY created_at DESC""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("dispute history fetch failed")
            rows = []
        _show_table(self.ctx.parent, "My disputes",
                    ("id", "attendance id", "reason", "status",
                     "created", "outcome", "resolved"), rows,
                    widths=[60, 120, 260, 100, 150, 140, 150])

    # --- #42 -----------------------------------------------------------
    @safe("Appeal")
    def appeal_rejected_request(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, date, module_code FROM absence_requests
                   WHERE student_id=? AND status='rejected'""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("rejected fetch failed")
            messagebox.showerror("Error", "Could not load rejected requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("None", "No rejected requests to appeal.",
                                parent=self.ctx.parent)
            return
        m = {f"#{r[0]} {r[1]} {r[2]}": r[0] for r in rows}
        pick = _combo_dialog(self.ctx.parent, "Appeal",
                             "Which request?", list(m.keys()))
        if not pick:
            return
        reason = Prompt.non_empty(self.ctx.parent, "Grounds",
                                  "Grounds for appeal:", min_len=10)
        if not reason:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_appeals
                   (student_id, request_id, reason) VALUES (?,?,?)""",
                (sid, m[pick], reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.appeal", "abs_tracker_appeals",
              sid, f"req={m[pick]}")
        messagebox.showinfo("Submitted", "Appeal filed.",
                            parent=self.ctx.parent)


# ===========================================================================
# IntegrationsService — features #43–#47
# ===========================================================================

class IntegrationsService:
    """Timetable, grade impact, assignments, library search, exam-day check."""

    def __init__(self, ctx: StudentContext) -> None:
        self.ctx = ctx

    # --- #43 -----------------------------------------------------------
    @safe("My timetable")
    def show_my_timetable(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ms.module_code, ms.day_of_week, ms.start_time,
                          ms.end_time, ms.room_id, ms.semester
                   FROM module_schedule ms
                   JOIN student_modules sm ON sm.module_code = ms.module_code
                   WHERE sm.student_id=?
                   ORDER BY ms.day_of_week, ms.start_time""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("timetable fetch failed")
            rows = []
        _show_table(self.ctx.parent, "My timetable",
                    ("module", "day", "start", "end", "room", "semester"), rows)

    # --- #44 -----------------------------------------------------------
    @safe("Grade impact")
    def show_grade_vs_attendance(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS student_grades (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT, module_code TEXT, grade TEXT)""")
            rows = self.ctx.db.cur.execute(
                """SELECT m.module_code,
                          COALESCE((SELECT grade FROM student_grades
                                    WHERE student_id=? AND module_code=m.module_code
                                    ORDER BY id DESC LIMIT 1), '—') AS grade,
                          COALESCE((SELECT
                             SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100
                             FROM attendance
                             WHERE student_id=? AND module_code=m.module_code), 0)
                          AS pct
                   FROM student_modules sm
                   JOIN modules m ON m.module_code=sm.module_code
                   WHERE sm.student_id=?""",
                (sid, sid, sid)).fetchall()
        except sqlite3.Error:
            logger.exception("grade impact fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Grades vs attendance",
                    ("module", "grade", "attendance %"),
                    [(mc, g, f"{p:.1f}") for mc, g, p in rows])

    # --- #45 -----------------------------------------------------------
    @safe("My assignments")
    def show_my_assignments(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY, module_code TEXT, title TEXT,
                    due_date TEXT, status TEXT)""")
            rows = self.ctx.db.cur.execute(
                """SELECT a.module_code, a.title, a.due_date,
                          COALESCE(a.status,'')
                   FROM assignments a
                   JOIN student_modules sm ON sm.module_code = a.module_code
                   WHERE sm.student_id=?
                   ORDER BY a.due_date""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("assignments fetch failed")
            rows = []
        _show_table(self.ctx.parent, "My assignments",
                    ("module", "title", "due", "status"), rows,
                    widths=[110, 380, 110, 120])

    # --- #46 -----------------------------------------------------------
    @safe("Library resources")
    def search_library(self) -> None:
        q = Prompt.non_empty(self.ctx.parent, "Library search",
                             "Search term:", min_len=2)
        if not q:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY,
                    title TEXT, author TEXT, shelf TEXT)""")
            like = f"%{q}%"
            rows = self.ctx.db.cur.execute(
                """SELECT title, COALESCE(author,''), COALESCE(shelf,'')
                   FROM books WHERE title LIKE ? OR author LIKE ? LIMIT 50""",
                (like, like)).fetchall()
        except sqlite3.Error:
            logger.exception("library search failed")
            rows = []
        _show_table(self.ctx.parent, f"Library — '{q}'",
                    ("title", "author", "shelf"), rows)

    # --- #47 -----------------------------------------------------------
    @safe("Exam-day check")
    def show_exam_day_check(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT m.module_code, e.date, e.name
                   FROM academic_calendar_events e
                   JOIN student_modules sm ON 1=1
                   JOIN modules m ON m.module_code = sm.module_code
                   WHERE sm.student_id=? AND e.event_type LIKE '%exam%'
                     AND e.date >= date('now')
                   ORDER BY e.date""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("exam check fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Upcoming exam dates (must attend)",
                    ("module", "date", "event"), rows, widths=[120, 110, 500])


# ===========================================================================
# CustomisationService — features #48–#50
# ===========================================================================

class CustomisationService:
    """Accessibility, language, dashboard layout."""

    def __init__(self, ctx: StudentContext, prefs: StudentPrefs) -> None:
        self.ctx = ctx
        self.prefs = prefs

    # --- #48 -----------------------------------------------------------
    @safe("Accessibility mode")
    def toggle_accessibility_mode(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        on = self.prefs.get(sid, "a11y", "0") != "1"
        try:
            self.prefs.set(sid, "a11y", "1" if on else "0")
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        try:
            style = ttk.Style()
            if on:
                style.configure("Treeview", rowheight=34, font=("Arial", 13))
                style.configure("Treeview.Heading", font=("Arial", 13, "bold"))
                self.ctx.parent.option_add("*Font", "Arial 13")
            else:
                style.configure("Treeview", rowheight=26, font=("Arial", 10))
                style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
                self.ctx.parent.option_add("*Font", "Arial 10")
        except tk.TclError:
            logger.exception("a11y style apply failed")
        audit(self.ctx, "student.a11y", "prefs", sid, "on" if on else "off")
        messagebox.showinfo("Accessibility",
                            f"Accessibility mode is now {'ON' if on else 'OFF'}.",
                            parent=self.ctx.parent)

    # --- #49 -----------------------------------------------------------
    @safe("Language")
    def set_language(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        lang = _combo_dialog(self.ctx.parent, "Language", "Language:",
                             ["en", "fr", "es", "de", "zh", "ar"])
        if not lang:
            return
        try:
            self.prefs.set(sid, "language", lang)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.language", "prefs", sid, lang)
        messagebox.showinfo("Saved",
                            f"Language set to '{lang}'. Restart to apply everywhere.",
                            parent=self.ctx.parent)

    # --- #50 -----------------------------------------------------------
    @safe("Dashboard layout")
    def edit_dashboard_layout(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        default = ("📚 My Modules,📋 My Absences,📤 Submit Request,"
                   "📨 My Requests,📊 My Stats,🧑‍🎓 Student Tools (50)")
        current = self.prefs.get(sid, "dashboard_tabs", default)
        new = simpledialog.askstring(
            "Tabs order",
            "Comma-separated tab names in desired order:",
            parent=self.ctx.parent, initialvalue=current)
        if new is None:
            return
        try:
            self.prefs.set(sid, "dashboard_tabs", new)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.layout", "prefs", sid, new)
        messagebox.showinfo("Saved",
                            "Layout saved. It'll take effect next time you open the tracker.",
                            parent=self.ctx.parent)


# ===========================================================================
# Service container + feature registry
# ===========================================================================

@dataclass
class StudentServices:
    """Aggregates every service the Student Tools tab needs."""
    visibility: AttendanceVisibilityService
    requests: RequestService
    notifications: NotificationService
    planning: PlanningService
    support: SupportService
    social: SocialService
    appeals: AppealsService
    integrations: IntegrationsService
    customisation: CustomisationService

    @classmethod
    def for_context(cls, ctx: StudentContext) -> "StudentServices":
        prefs = StudentPrefs(ctx.db)
        picker = ModulePicker(ctx)
        return cls(
            visibility    = AttendanceVisibilityService(ctx, prefs),
            requests      = RequestService(ctx, prefs, picker),
            notifications = NotificationService(ctx, prefs),
            planning      = PlanningService(ctx, picker),
            support       = SupportService(ctx, picker),
            social        = SocialService(ctx, picker),
            appeals       = AppealsService(ctx),
            integrations  = IntegrationsService(ctx),
            customisation = CustomisationService(ctx, prefs),
        )


@dataclass(frozen=True)
class FeatureSpec:
    number: int
    category: str
    label: str
    method: Callable[[StudentServices], Callable[[], None]]


def _build_feature_registry() -> list[FeatureSpec]:
    """One row per student feature; method picks the bound method off StudentServices."""
    return [
        # Visibility
        FeatureSpec( 1, "Visibility", "Calendar view",
                    lambda s: s.visibility.show_calendar),
        FeatureSpec( 2, "Visibility", "Attendance gauges",
                    lambda s: s.visibility.show_gauges),
        FeatureSpec( 3, "Visibility", "Streak tracker",
                    lambda s: s.visibility.show_streak),
        FeatureSpec( 4, "Visibility", "Personal timeline",
                    lambda s: s.visibility.show_timeline),
        FeatureSpec( 5, "Visibility", "Export my data (CSV/JSON)",
                    lambda s: s.visibility.export_my_data),
        FeatureSpec( 6, "Visibility", "Compare to module average",
                    lambda s: s.visibility.compare_to_module_average),
        FeatureSpec( 7, "Visibility", "Absence-budget projection",
                    lambda s: s.visibility.project_absence_budget),
        FeatureSpec( 8, "Visibility", "Personal heatmap",
                    lambda s: s.visibility.show_personal_heatmap),

        # Requests
        FeatureSpec( 9, "Requests", "Quick-submit from template",
                    lambda s: s.requests.quick_submit_from_template),
        FeatureSpec(10, "Requests", "Attach evidence",
                    lambda s: s.requests.attach_evidence),
        FeatureSpec(11, "Requests", "Status tracker",
                    lambda s: s.requests.show_status_tracker),
        FeatureSpec(12, "Requests", "Withdraw pending",
                    lambda s: s.requests.withdraw_pending),
        FeatureSpec(13, "Requests", "Resubmit rejected",
                    lambda s: s.requests.resubmit_rejected),
        FeatureSpec(14, "Requests", "Bulk multi-day request",
                    lambda s: s.requests.bulk_multi_day_request),
        FeatureSpec(15, "Requests", "Save draft",
                    lambda s: s.requests.save_draft),
        FeatureSpec(16, "Requests", "Export request history",
                    lambda s: s.requests.export_request_history),

        # Reminders
        FeatureSpec(17, "Reminders", "Class reminder minutes",
                    lambda s: s.notifications.set_class_reminder),
        FeatureSpec(18, "Reminders", "Low-attendance self-alert",
                    lambda s: s.notifications.set_low_attendance_alert),
        FeatureSpec(19, "Reminders", "Upcoming deadlines",
                    lambda s: s.notifications.show_upcoming_deadlines),
        FeatureSpec(20, "Reminders", "Parent-notification log",
                    lambda s: s.notifications.show_parent_notifications_log),
        FeatureSpec(21, "Reminders", "Channel preferences",
                    lambda s: s.notifications.edit_channel_preferences),
        FeatureSpec(22, "Reminders", "Do-not-disturb hours",
                    lambda s: s.notifications.set_dnd_hours),

        # Planning
        FeatureSpec(23, "Planning", "Per-module goals",
                    lambda s: s.planning.set_per_module_goal),
        FeatureSpec(24, "Planning", "Attendance budget",
                    lambda s: s.planning.show_attendance_budget),
        FeatureSpec(25, "Planning", "Term forecast",
                    lambda s: s.planning.show_term_forecast),
        FeatureSpec(26, "Planning", "Calendar sync (ICS)",
                    lambda s: s.planning.export_calendar_ics),
        FeatureSpec(27, "Planning", "Recovery planner",
                    lambda s: s.planning.show_recovery_plan),
        FeatureSpec(28, "Planning", "Wellbeing check-in",
                    lambda s: s.planning.log_wellbeing_checkin),

        # Support
        FeatureSpec(29, "Support", "Request notes from classmates",
                    lambda s: s.support.request_classmate_notes),
        FeatureSpec(30, "Support", "Book office hours",
                    lambda s: s.support.book_office_hours),
        FeatureSpec(31, "Support", "Study buddy matchmaker",
                    lambda s: s.support.join_study_buddy_pool),
        FeatureSpec(32, "Support", "Recorded lectures",
                    lambda s: s.support.show_recorded_lectures),
        FeatureSpec(33, "Support", "Confidential wellbeing flag",
                    lambda s: s.support.submit_wellbeing_flag),
        FeatureSpec(34, "Support", "Support resources",
                    lambda s: s.support.show_support_resources),
        FeatureSpec(35, "Support", "Self-refer to advising",
                    lambda s: s.support.self_refer_to_advising),

        # Social
        FeatureSpec(36, "Social", "Find study group",
                    lambda s: s.social.find_or_create_study_group),
        FeatureSpec(37, "Social", "Note-share marketplace",
                    lambda s: s.social.share_or_browse_notes),
        FeatureSpec(38, "Social", "Attendance badges",
                    lambda s: s.social.claim_attendance_badges),
        FeatureSpec(39, "Social", "Weekly digest",
                    lambda s: s.social.show_weekly_digest),

        # Appeals
        FeatureSpec(40, "Appeals", "Dispute a record",
                    lambda s: s.appeals.dispute_attendance_record),
        FeatureSpec(41, "Appeals", "My dispute history",
                    lambda s: s.appeals.show_dispute_history),
        FeatureSpec(42, "Appeals", "Appeal a rejected request",
                    lambda s: s.appeals.appeal_rejected_request),

        # Integrations
        FeatureSpec(43, "Integrations", "My timetable",
                    lambda s: s.integrations.show_my_timetable),
        FeatureSpec(44, "Integrations", "Grade vs attendance impact",
                    lambda s: s.integrations.show_grade_vs_attendance),
        FeatureSpec(45, "Integrations", "My assignments",
                    lambda s: s.integrations.show_my_assignments),
        FeatureSpec(46, "Integrations", "Library resources",
                    lambda s: s.integrations.search_library),
        FeatureSpec(47, "Integrations", "Exam-day check",
                    lambda s: s.integrations.show_exam_day_check),

        # Accessibility
        FeatureSpec(48, "Accessibility", "Accessibility mode (toggle)",
                    lambda s: s.customisation.toggle_accessibility_mode),
        FeatureSpec(49, "Accessibility", "Language",
                    lambda s: s.customisation.set_language),
        FeatureSpec(50, "Accessibility", "Dashboard layout",
                    lambda s: s.customisation.edit_dashboard_layout),

        # Bonus
        FeatureSpec(51, "Requests", "Request time off (date picker)",
                    lambda s: s.requests.request_time_off),
    ]


FEATURES: list[FeatureSpec] = _build_feature_registry()


# ===========================================================================
# Tab renderer
# ===========================================================================

def build_student_tab(notebook: ttk.Notebook, ctx: StudentContext) -> None:
    """Render all 50 student features into a dedicated notebook tab."""
    try:
        ensure_support_tables(ctx.db)
        ensure_student_tables(ctx.db)
    except sqlite3.Error:
        logger.exception("could not ensure student tables")
        messagebox.showerror(
            "Student Tools",
            "Could not initialise student-tools tables. See log.",
            parent=ctx.parent)
        return

    services = StudentServices.for_context(ctx)

    frame = ttk.Frame(notebook)
    notebook.add(frame, text="🧑‍🎓 Student Tools (50)")

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
                bg="#0ea5e9", fg="white", activebackground="#0284c7",
                relief="flat", cursor="hand2",
                width=32, anchor="w", padx=8, pady=6,
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="w")

    logger.info("student tools tab built (%d features)", len(FEATURES))


# ===========================================================================
# Backwards-compat: keep module-level callable aliases for any external caller
# that imported the old `stu_NN_*` names directly. These thin wrappers build a
# transient StudentServices and invoke the corresponding method.
# ===========================================================================

def _wrap(method_picker: Callable[[StudentServices], Callable[[], None]]
          ) -> Callable[[StudentContext], None]:
    def runner(ctx: StudentContext) -> None:
        services = StudentServices.for_context(ctx)
        method_picker(services)()
    return runner


_LEGACY_ALIASES: dict[str, Callable] = {
    "stu_01_calendar":             _wrap(lambda s: s.visibility.show_calendar),
    "stu_02_gauge":                _wrap(lambda s: s.visibility.show_gauges),
    "stu_03_streak":               _wrap(lambda s: s.visibility.show_streak),
    "stu_04_timeline":             _wrap(lambda s: s.visibility.show_timeline),
    "stu_05_export_my_data":       _wrap(lambda s: s.visibility.export_my_data),
    "stu_06_compare_module_avg":   _wrap(lambda s: s.visibility.compare_to_module_average),
    "stu_07_projection":           _wrap(lambda s: s.visibility.project_absence_budget),
    "stu_08_personal_heatmap":     _wrap(lambda s: s.visibility.show_personal_heatmap),
    "stu_09_quick_submit":         _wrap(lambda s: s.requests.quick_submit_from_template),
    "stu_10_attach_evidence":      _wrap(lambda s: s.requests.attach_evidence),
    "stu_11_status_tracker":       _wrap(lambda s: s.requests.show_status_tracker),
    "stu_12_withdraw":             _wrap(lambda s: s.requests.withdraw_pending),
    "stu_13_resubmit":             _wrap(lambda s: s.requests.resubmit_rejected),
    "stu_14_bulk_request":         _wrap(lambda s: s.requests.bulk_multi_day_request),
    "stu_15_save_draft":           _wrap(lambda s: s.requests.save_draft),
    "stu_16_history_export":       _wrap(lambda s: s.requests.export_request_history),
    "stu_17_class_reminder":       _wrap(lambda s: s.notifications.set_class_reminder),
    "stu_18_low_attendance_alert": _wrap(lambda s: s.notifications.set_low_attendance_alert),
    "stu_19_deadline_alerts":      _wrap(lambda s: s.notifications.show_upcoming_deadlines),
    "stu_20_parent_notif_log":     _wrap(lambda s: s.notifications.show_parent_notifications_log),
    "stu_21_notification_prefs":   _wrap(lambda s: s.notifications.edit_channel_preferences),
    "stu_22_dnd_hours":            _wrap(lambda s: s.notifications.set_dnd_hours),
    "stu_23_attendance_goals":     _wrap(lambda s: s.planning.set_per_module_goal),
    "stu_24_attendance_budget":    _wrap(lambda s: s.planning.show_attendance_budget),
    "stu_25_term_forecast":        _wrap(lambda s: s.planning.show_term_forecast),
    "stu_26_calendar_sync":        _wrap(lambda s: s.planning.export_calendar_ics),
    "stu_27_recovery_plan":        _wrap(lambda s: s.planning.show_recovery_plan),
    "stu_28_wellbeing_checkin":    _wrap(lambda s: s.planning.log_wellbeing_checkin),
    "stu_29_request_notes":        _wrap(lambda s: s.support.request_classmate_notes),
    "stu_30_book_office_hours":    _wrap(lambda s: s.support.book_office_hours),
    "stu_31_study_buddy":          _wrap(lambda s: s.support.join_study_buddy_pool),
    "stu_32_recorded_lectures":    _wrap(lambda s: s.support.show_recorded_lectures),
    "stu_33_wellbeing_flag":       _wrap(lambda s: s.support.submit_wellbeing_flag),
    "stu_34_support_resources":    _wrap(lambda s: s.support.show_support_resources),
    "stu_35_self_refer_advising":  _wrap(lambda s: s.support.self_refer_to_advising),
    "stu_36_find_study_group":     _wrap(lambda s: s.social.find_or_create_study_group),
    "stu_37_note_share":           _wrap(lambda s: s.social.share_or_browse_notes),
    "stu_38_attendance_badge":     _wrap(lambda s: s.social.claim_attendance_badges),
    "stu_39_weekly_digest":        _wrap(lambda s: s.social.show_weekly_digest),
    "stu_40_dispute_record":       _wrap(lambda s: s.appeals.dispute_attendance_record),
    "stu_41_dispute_history":      _wrap(lambda s: s.appeals.show_dispute_history),
    "stu_42_appeal_request":       _wrap(lambda s: s.appeals.appeal_rejected_request),
    "stu_43_my_timetable":         _wrap(lambda s: s.integrations.show_my_timetable),
    "stu_44_grade_impact":         _wrap(lambda s: s.integrations.show_grade_vs_attendance),
    "stu_45_my_assignments":       _wrap(lambda s: s.integrations.show_my_assignments),
    "stu_46_library_resources":    _wrap(lambda s: s.integrations.search_library),
    "stu_47_exam_day_check":       _wrap(lambda s: s.integrations.show_exam_day_check),
    "stu_48_accessibility_mode":   _wrap(lambda s: s.customisation.toggle_accessibility_mode),
    "stu_49_language":             _wrap(lambda s: s.customisation.set_language),
    "stu_50_dashboard_layout":     _wrap(lambda s: s.customisation.edit_dashboard_layout),
    "stu_51_request_time_off":     _wrap(lambda s: s.requests.request_time_off),
}
globals().update(_LEGACY_ALIASES)
