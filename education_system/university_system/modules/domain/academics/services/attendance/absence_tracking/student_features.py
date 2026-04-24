"""
Student features for the Absence Tracker.

Fifty student-facing utilities. Each is wrapped with logging and error handling
via the shared ``@safe`` decorator so any failure is logged with a traceback
and surfaced as a friendly dialog rather than crashing the GUI.

Context carries the DB handle, parent Tk window, and authenticated user dict.
"""

from __future__ import annotations

import calendar
import csv
import functools
import io
import json
import logging
import os
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Optional

from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables, logger as _admin_logger,
    pick_date, pick_date_range,
)

logger = logging.getLogger("absence_tracker.student")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
    # Share the admin handlers where available (same file handler).
    for h in _admin_logger.handlers:
        logger.addHandler(h)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Context + support tables
# ---------------------------------------------------------------------------
@dataclass
class StudentContext:
    db: Any
    parent: tk.Misc
    user: dict

    @property
    def sid(self) -> Optional[str]:
        return self.user.get("student_id")


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


def _require_sid(ctx: StudentContext) -> Optional[str]:
    if not ctx.sid:
        messagebox.showerror(
            "Missing student_id",
            "Your user account is not linked to a student record.",
            parent=ctx.parent,
        )
        return None
    return ctx.sid


def _pref(db, sid, key, default=None):
    r = db.cur.execute(
        "SELECT value FROM abs_tracker_student_prefs WHERE student_id=? AND key=?",
        (sid, key)).fetchone()
    return r[0] if r else default


def _set_pref(db, sid, key, value):
    db.cur.execute(
        """INSERT OR REPLACE INTO abs_tracker_student_prefs (student_id, key, value)
           VALUES (?, ?, ?)""", (sid, key, str(value)))
    db.conn.commit()


# ===========================================================================
# 1–8  My attendance visibility
# ===========================================================================

@safe("Calendar")
def stu_01_calendar(ctx: StudentContext):
    """Month calendar view of my attendance."""
    sid = _require_sid(ctx)
    if not sid:
        return
    today = date.today()
    y = simpledialog.askinteger("Year", "Year:", parent=ctx.parent,
                                initialvalue=today.year) or today.year
    m = simpledialog.askinteger("Month", "Month (1-12):", parent=ctx.parent,
                                initialvalue=today.month) or today.month
    rows = ctx.db.cur.execute(
        """SELECT date, status FROM attendance
           WHERE student_id=? AND strftime('%Y-%m', date) = ?""",
        (sid, f"{y:04d}-{m:02d}")).fetchall()
    by_day = {d: s for d, s in rows}

    win = tk.Toplevel(ctx.parent)
    win.title(f"My attendance — {y}-{m:02d}")
    win.geometry("560x420")
    tk.Label(win, text=f"{calendar.month_name[m]} {y}",
             font=("Arial", 14, "bold")).pack(pady=10)

    grid = tk.Frame(win)
    grid.pack()
    for i, wd in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        tk.Label(grid, text=wd, width=8, font=("Arial", 10, "bold")).grid(row=0, column=i)

    colours = {"present": "#86efac", "absent": "#fca5a5",
               "late": "#fcd34d", "excused": "#bfdbfe"}
    cal = calendar.Calendar(firstweekday=0)
    for r, week in enumerate(cal.monthdatescalendar(y, m), start=1):
        for c, d in enumerate(week):
            key = d.isoformat()
            st = by_day.get(key, "")
            bg = colours.get(st, "#f3f4f6" if d.month == m else "#e5e7eb")
            tk.Label(grid, text=f"{d.day}\n{st or ''}", width=8, height=3,
                     bg=bg, relief="solid", borderwidth=1,
                     font=("Arial", 9)).grid(row=r, column=c, padx=1, pady=1)

    audit(ctx, "student.calendar", "attendance", sid, f"{y}-{m:02d}")


@safe("Attendance gauge")
def stu_02_gauge(ctx: StudentContext):
    """Traffic-light % per module."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT a.module_code,
                  COALESCE(m.module_name, a.module_code),
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100,
                  COUNT(*)
           FROM attendance a LEFT JOIN modules m ON m.module_code = a.module_code
           WHERE a.student_id=? GROUP BY a.module_code""", (sid,)).fetchall()
    win = tk.Toplevel(ctx.parent)
    win.title("Attendance gauge")
    win.geometry("640x480")
    for mc, name, pct, n in rows:
        pct = pct or 0
        col = "#16a34a" if pct >= 85 else "#f59e0b" if pct >= 70 else "#dc2626"
        row = tk.Frame(win); row.pack(fill="x", padx=10, pady=4)
        tk.Label(row, text=f"{mc} — {name}", width=40, anchor="w").pack(side="left")
        tk.Label(row, text=f"{pct:.1f}%", fg="white", bg=col,
                 width=10, font=("Arial", 11, "bold")).pack(side="left", padx=8)
        tk.Label(row, text=f"{n} sessions", fg="#6b7280").pack(side="left")
    if not rows:
        tk.Label(win, text="No attendance data yet.", fg="#6b7280").pack(pady=20)


@safe("Streak")
def stu_03_streak(ctx: StudentContext):
    """Current consecutive-present streak."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT date, status FROM attendance
           WHERE student_id=? ORDER BY date DESC""", (sid,)).fetchall()
    streak = 0
    for _d, st in rows:
        if st == "present":
            streak += 1
        else:
            break
    longest = 0
    cur = 0
    for _d, st in reversed(rows):
        if st == "present":
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    messagebox.showinfo("Streak",
                        f"Current present streak: {streak}\nLongest ever: {longest}",
                        parent=ctx.parent)


@safe("Timeline")
def stu_04_timeline(ctx: StudentContext):
    """Full scrollable absence timeline with status filter."""
    sid = _require_sid(ctx)
    if not sid:
        return
    stat = _combo_dialog(ctx.parent, "Filter", "Status:",
                         ["(all)", "present", "absent", "late", "excused"]) or "(all)"
    q = ("SELECT date, module_code, status, COALESCE(reason,'') "
         "FROM attendance WHERE student_id=?")
    p = [sid]
    if stat != "(all)":
        q += " AND status=?"; p.append(stat)
    q += " ORDER BY date DESC"
    rows = ctx.db.cur.execute(q, p).fetchall()
    _show_table(ctx.parent, f"My timeline ({len(rows)} rows)",
                ("date", "module", "status", "reason"), rows,
                widths=[110, 140, 90, 360])


@safe("Export my data")
def stu_05_export_my_data(ctx: StudentContext):
    """Export my attendance to CSV."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.get_absences(student_id=sid)
    hdr = ("id", "student", "module_code", "module_name", "date", "status", "reason")
    path = _export_rows_to_csv(rows, hdr, ctx.parent)
    if path:
        audit(ctx, "student.export", "attendance", sid, path)
        messagebox.showinfo("Saved", f"Wrote {len(rows)} rows to:\n{path}",
                            parent=ctx.parent)


@safe("Compare to module")
def stu_06_compare_module_avg(ctx: StudentContext):
    """Compare my % to module average."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT a.module_code,
                  SUM(CASE WHEN a.status='present' AND a.student_id=? THEN 1 ELSE 0 END)*1.0
                    / NULLIF(SUM(CASE WHEN a.student_id=? THEN 1 ELSE 0 END),0) * 100 AS mine,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*) * 100 AS avg
           FROM attendance a GROUP BY a.module_code
           HAVING SUM(CASE WHEN a.student_id=? THEN 1 ELSE 0 END) > 0""",
        (sid, sid, sid)).fetchall()
    _show_table(ctx.parent, "Me vs module average",
                ("module", "my %", "module avg %"),
                [(m, f"{(x or 0):.1f}", f"{(y or 0):.1f}") for m, x, y in rows])


@safe("Projection")
def stu_07_projection(ctx: StudentContext):
    """How many more absences before I drop below a threshold?"""
    sid = _require_sid(ctx)
    if not sid:
        return
    threshold = simpledialog.askfloat("Threshold", "Stay above what %?",
                                      parent=ctx.parent, initialvalue=80) or 80
    rows = ctx.db.cur.execute(
        """SELECT module_code,
                  SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) AS p,
                  COUNT(*) AS n
           FROM attendance WHERE student_id=? GROUP BY module_code""", (sid,)).fetchall()
    out = []
    for mc, p, n in rows:
        if n == 0:
            continue
        # current pct = p/n*100 ; allow k more absences: p/(n+k) >= threshold/100
        k = 0
        while (p / (n + k + 1)) * 100 >= threshold and k < 500:
            k += 1
        out.append((mc, f"{p/n*100:.1f}%", k))
    _show_table(ctx.parent, f"Absence budget (keep ≥ {threshold:.0f}%)",
                ("module", "current %", "can miss"), out)


@safe("Personal heatmap")
def stu_08_personal_heatmap(ctx: StudentContext):
    """My absences by day-of-week."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT CASE strftime('%w', date)
                    WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon'
                    WHEN '2' THEN 'Tue' WHEN '3' THEN 'Wed'
                    WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
                    ELSE 'Sat' END, COUNT(*)
           FROM attendance WHERE student_id=? AND status='absent'
           GROUP BY 1""", (sid,)).fetchall()
    _show_table(ctx.parent, "My absences by day-of-week",
                ("day", "absences"), rows, widths=[140, 140])


# ===========================================================================
# 9–16  Requests & submissions
# ===========================================================================

@safe("Quick-submit")
def stu_09_quick_submit(ctx: StudentContext):
    """Submit a request using a saved template."""
    sid = _require_sid(ctx)
    if not sid:
        return
    templates = ctx.db.cur.execute(
        "SELECT name, body FROM abs_tracker_request_templates ORDER BY name").fetchall()
    if not templates:
        messagebox.showinfo("No templates",
                            "Ask an admin to create request templates first.",
                            parent=ctx.parent)
        return
    tmap = {r[0]: r[1] for r in templates}
    tpl = _combo_dialog(ctx.parent, "Template", "Pick template:", list(tmap.keys()))
    if not tpl:
        return
    # Pick module from my enrolments
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    if not pick:
        return
    d = simpledialog.askstring("Date", "Date (YYYY-MM-DD):",
                               parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    if not d:
        return
    ctx.db.submit_request(sid, mmap[pick], d, tmap[tpl])
    audit(ctx, "student.quick_submit", "absence_requests", sid, tpl)
    messagebox.showinfo("Submitted", "Request submitted.", parent=ctx.parent)


@safe("Attach evidence")
def stu_10_attach_evidence(ctx: StudentContext):
    """Attach a file to one of my requests."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        "SELECT id, date, module_code FROM absence_requests WHERE student_id=? ORDER BY id DESC",
        (sid,)).fetchall()
    if not rows:
        messagebox.showinfo("No requests", "You have no requests.", parent=ctx.parent)
        return
    m = {f"#{r[0]} {r[1]} {r[2]}": r[0] for r in rows}
    pick = _combo_dialog(ctx.parent, "Request", "Pick request:", list(m.keys()))
    if not pick:
        return
    path = filedialog.askopenfilename(parent=ctx.parent)
    if not path:
        return
    ctx.db.cur.execute(
        "INSERT INTO abs_tracker_request_attachments (request_id, file_path) VALUES (?, ?)",
        (m[pick], path))
    ctx.db.conn.commit()
    audit(ctx, "student.attach", "absence_requests", m[pick], path)
    messagebox.showinfo("Attached", f"Attached:\n{path}", parent=ctx.parent)


@safe("Status tracker")
def stu_11_status_tracker(ctx: StudentContext):
    """My requests with status and timeline."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT id, date, module_code, status, submitted_at, substr(reason,1,60)
           FROM absence_requests WHERE student_id=?
           ORDER BY submitted_at DESC""", (sid,)).fetchall()
    _show_table(ctx.parent, "My request statuses",
                ("id", "date", "module", "status", "submitted", "reason"), rows,
                widths=[60, 100, 110, 90, 150, 360])


@safe("Withdraw")
def stu_12_withdraw(ctx: StudentContext):
    """Withdraw one of my pending requests."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT id, date, module_code FROM absence_requests
           WHERE student_id=? AND status='pending' ORDER BY submitted_at DESC""",
        (sid,)).fetchall()
    if not rows:
        messagebox.showinfo("No pending", "Nothing to withdraw.", parent=ctx.parent)
        return
    m = {f"#{r[0]} {r[1]} {r[2]}": r[0] for r in rows}
    pick = _combo_dialog(ctx.parent, "Withdraw", "Which?", list(m.keys()))
    if not pick:
        return
    ctx.db.cur.execute(
        "UPDATE absence_requests SET status='rejected', reason=reason||' [withdrawn]'"
        " WHERE id=?", (m[pick],))
    ctx.db.conn.commit()
    audit(ctx, "student.withdraw", "absence_requests", m[pick], "")
    messagebox.showinfo("Withdrawn", "Request withdrawn.", parent=ctx.parent)


@safe("Resubmit")
def stu_13_resubmit(ctx: StudentContext):
    """Resubmit a previously rejected request with a new reason."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT id, date, module_code, reason FROM absence_requests
           WHERE student_id=? AND status='rejected'
           ORDER BY submitted_at DESC""", (sid,)).fetchall()
    if not rows:
        messagebox.showinfo("None", "No rejected requests.", parent=ctx.parent)
        return
    m = {f"#{r[0]} {r[1]} {r[2]}": r for r in rows}
    pick = _combo_dialog(ctx.parent, "Resubmit", "Which?", list(m.keys()))
    if not pick:
        return
    rid, d, mc, old = m[pick]
    new = simpledialog.askstring("New reason", f"(was: {old})", parent=ctx.parent)
    if not new:
        return
    ctx.db.submit_request(sid, mc, d, new + " [resubmitted]")
    audit(ctx, "student.resubmit", "absence_requests", rid, new[:80])
    messagebox.showinfo("Submitted", "Resubmitted.", parent=ctx.parent)


@safe("Bulk request")
def stu_14_bulk_request(ctx: StudentContext):
    """Submit a request covering multiple consecutive dates (e.g. sickness week)."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    if not pick:
        return
    start = simpledialog.askstring("Start", "Start (YYYY-MM-DD):",
                                   parent=ctx.parent,
                                   initialvalue=date.today().isoformat())
    days = simpledialog.askinteger("Days", "How many consecutive days?",
                                   parent=ctx.parent, minvalue=1, maxvalue=30)
    reason = simpledialog.askstring("Reason", "Reason:", parent=ctx.parent)
    if not (start and days and reason):
        return
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    for k in range(days):
        ctx.db.submit_request(sid, mmap[pick],
                              (d0 + timedelta(days=k)).isoformat(),
                              reason)
    audit(ctx, "student.bulk_request", "absence_requests", sid,
          f"{mmap[pick]} {start} x{days}")
    messagebox.showinfo("Submitted", f"Submitted {days} request(s).",
                        parent=ctx.parent)


@safe("Save draft")
def stu_15_save_draft(ctx: StudentContext):
    """Save a request draft for later."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    d = simpledialog.askstring("Date", "Date (YYYY-MM-DD):",
                               parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    reason = simpledialog.askstring("Reason", "Reason:", parent=ctx.parent) or ""
    if not (pick and d):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_student_drafts
           (student_id, module_code, date, reason) VALUES (?,?,?,?)""",
        (sid, mmap[pick], d, reason))
    ctx.db.conn.commit()
    audit(ctx, "student.draft", "abs_tracker_student_drafts", sid, mmap[pick])
    messagebox.showinfo("Saved", "Draft saved.", parent=ctx.parent)


@safe("Request history export")
def stu_16_history_export(ctx: StudentContext):
    """Export my full request history to CSV."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT id, date, module_code, status, submitted_at, reason
           FROM absence_requests WHERE student_id=? ORDER BY submitted_at DESC""",
        (sid,)).fetchall()
    path = _export_rows_to_csv(
        rows, ("id", "date", "module", "status", "submitted", "reason"), ctx.parent)
    if path:
        audit(ctx, "student.history_export", "absence_requests", sid, path)
        messagebox.showinfo("Saved", f"Exported to:\n{path}", parent=ctx.parent)


# ===========================================================================
# 17–22  Notifications & reminders
# ===========================================================================

@safe("Class reminder")
def stu_17_class_reminder(ctx: StudentContext):
    """Set a reminder window before scheduled classes."""
    sid = _require_sid(ctx)
    if not sid:
        return
    mins = simpledialog.askinteger(
        "Minutes",
        f"Remind me how many minutes before class? (current {_pref(ctx.db, sid, 'reminder_mins', '0')})",
        parent=ctx.parent, minvalue=0, maxvalue=240)
    if mins is None:
        return
    _set_pref(ctx.db, sid, "reminder_mins", mins)
    audit(ctx, "student.reminder", "prefs", sid, f"mins={mins}")
    messagebox.showinfo("Saved", f"Reminder = {mins} min before class.",
                        parent=ctx.parent)


@safe("Low-attendance alert")
def stu_18_low_attendance_alert(ctx: StudentContext):
    """Set my own low-attendance threshold."""
    sid = _require_sid(ctx)
    if not sid:
        return
    pct = simpledialog.askfloat(
        "Threshold",
        f"Alert me if I drop below %? (current {_pref(ctx.db, sid, 'self_threshold', '80')})",
        parent=ctx.parent, minvalue=0, maxvalue=100)
    if pct is None:
        return
    _set_pref(ctx.db, sid, "self_threshold", pct)
    # Fire immediately if already below
    row = ctx.db.cur.execute(
        """SELECT SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100
           FROM attendance WHERE student_id=?""", (sid,)).fetchone()
    current = row[0] if row and row[0] is not None else None
    msg = f"Self-threshold saved: {pct}%"
    if current is not None and current < pct:
        msg += f"\n⚠ Already below: {current:.1f}%"
    audit(ctx, "student.self_threshold", "prefs", sid, str(pct))
    messagebox.showinfo("Saved", msg, parent=ctx.parent)


@safe("Deadline alerts")
def stu_19_deadline_alerts(ctx: StudentContext):
    """Upcoming academic deadlines pulled from academic_calendar_events."""
    rows = ctx.db.cur.execute(
        """SELECT date, name, event_type FROM academic_calendar_events
           WHERE date >= date('now') ORDER BY date LIMIT 30""").fetchall()
    _show_table(ctx.parent, "Upcoming deadlines",
                ("date", "name", "type"), rows, widths=[110, 500, 160])


@safe("Parent notifications log")
def stu_20_parent_notif_log(ctx: StudentContext):
    """See notifications that have been sent to my parents about me."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT created_date, notification_type, notification_content, read_status
           FROM parent_notifications WHERE student_id=?
           ORDER BY created_date DESC""", (sid,)).fetchall()
    _show_table(ctx.parent, "Notifications sent about me",
                ("when", "type", "content", "read?"), rows,
                widths=[160, 140, 450, 80])


@safe("Notification preferences")
def stu_21_notification_prefs(ctx: StudentContext):
    """Choose notification channels (email/in-app/SMS)."""
    sid = _require_sid(ctx)
    if not sid:
        return
    win = tk.Toplevel(ctx.parent)
    win.title("Notification channels")
    win.geometry("320x220")
    vars_ = {}
    for key, label in [("notif_email", "Email"),
                       ("notif_inapp", "In-app"),
                       ("notif_sms", "SMS")]:
        v = tk.IntVar(value=int(_pref(ctx.db, sid, key, "1")))
        vars_[key] = v
        tk.Checkbutton(win, text=label, variable=v).pack(anchor="w", padx=20, pady=4)

    def save():
        for k, v in vars_.items():
            _set_pref(ctx.db, sid, k, v.get())
        audit(ctx, "student.notif_prefs", "prefs", sid,
              json.dumps({k: v.get() for k, v in vars_.items()}))
        messagebox.showinfo("Saved", "Preferences updated.", parent=win)
        win.destroy()

    tk.Button(win, text="Save", command=save, bg="#2563eb", fg="white",
              relief="flat", padx=20, pady=6).pack(pady=10)


@safe("DND hours")
def stu_22_dnd_hours(ctx: StudentContext):
    """Do-not-disturb hours for reminders."""
    sid = _require_sid(ctx)
    if not sid:
        return
    start = simpledialog.askstring(
        "DND start", f"Start (HH:MM, current {_pref(ctx.db, sid, 'dnd_start', '22:00')}):",
        parent=ctx.parent)
    end = simpledialog.askstring(
        "DND end", f"End (HH:MM, current {_pref(ctx.db, sid, 'dnd_end', '07:00')}):",
        parent=ctx.parent)
    if start: _set_pref(ctx.db, sid, "dnd_start", start)
    if end:   _set_pref(ctx.db, sid, "dnd_end", end)
    audit(ctx, "student.dnd", "prefs", sid, f"{start}-{end}")
    messagebox.showinfo("Saved", "Do-not-disturb hours updated.", parent=ctx.parent)


# ===========================================================================
# 23–28  Planning & goals
# ===========================================================================

@safe("Attendance goals")
def stu_23_attendance_goals(ctx: StudentContext):
    """Set a target attendance % per module."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    if not pick:
        return
    pct = simpledialog.askfloat("Target", "Target %:", parent=ctx.parent,
                                minvalue=0, maxvalue=100, initialvalue=90)
    if pct is None:
        return
    ctx.db.cur.execute(
        """INSERT OR REPLACE INTO abs_tracker_student_goals
           (student_id, module_code, target_pct) VALUES (?,?,?)""",
        (sid, mmap[pick], pct))
    ctx.db.conn.commit()
    audit(ctx, "student.goal", "abs_tracker_student_goals", sid,
          f"{mmap[pick]} {pct}")
    messagebox.showinfo("Saved", f"Goal saved: {mmap[pick]} = {pct}%",
                        parent=ctx.parent)


@safe("Attendance budget")
def stu_24_attendance_budget(ctx: StudentContext):
    """How many more absences I can afford, per module."""
    sid = _require_sid(ctx)
    if not sid:
        return
    # Use per-module policy if set else default
    def_pct = float(_get_setting(ctx.db, "default_min_pct", 80) or 80)
    rows = ctx.db.cur.execute(
        """SELECT a.module_code,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS p,
                  COUNT(*) AS n,
                  COALESCE(p.min_percent, ?) AS thr
           FROM attendance a
           LEFT JOIN abs_tracker_module_policy p ON p.module_code = a.module_code
           WHERE a.student_id=? GROUP BY a.module_code""", (def_pct, sid)).fetchall()
    out = []
    for mc, p, n, thr in rows:
        k = 0
        while (p / (n + k + 1)) * 100 >= thr and k < 500:
            k += 1
        out.append((mc, f"{p/n*100:.1f}%", f"{thr:.0f}%", k))
    _show_table(ctx.parent, "Attendance budget",
                ("module", "current", "threshold", "can miss"), out)


@safe("Term forecast")
def stu_25_term_forecast(ctx: StudentContext):
    """Predict end-of-term attendance % given current rate."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT module_code,
                  SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100,
                  COUNT(*)
           FROM attendance WHERE student_id=? GROUP BY module_code""", (sid,)).fetchall()
    # Expected term length (heuristic): from soonest semester.end - semester.start / 7
    sem = ctx.db.cur.execute(
        "SELECT start_date, end_date FROM semesters ORDER BY start_date DESC LIMIT 1"
    ).fetchone()
    est_weeks = 12
    if sem and sem[0] and sem[1]:
        try:
            est_weeks = max(1, (datetime.fromisoformat(sem[1]) -
                                datetime.fromisoformat(sem[0])).days // 7)
        except Exception:
            pass
    out = []
    for mc, pct, n in rows:
        out.append((mc, f"{(pct or 0):.1f}%", n, est_weeks,
                    f"{(pct or 0):.1f}%"))
    _show_table(ctx.parent, "Term forecast (current rate)",
                ("module", "now", "sessions", "est weeks", "projected"), out)


@safe("Calendar sync")
def stu_26_calendar_sync(ctx: StudentContext):
    """Export my schedule + absences as ICS."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT date, module_code, status FROM attendance
           WHERE student_id=? ORDER BY date""", (sid,)).fetchall()
    if not rows:
        messagebox.showinfo("Nothing", "No attendance rows to export.",
                            parent=ctx.parent)
        return
    path = filedialog.asksaveasfilename(
        parent=ctx.parent, defaultextension=".ics",
        initialfile=f"attendance_{sid}.ics")
    if not path:
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//AbsenceTracker//EN\r\n")
        for d, mc, st in rows:
            try:
                dt = datetime.strptime(d, "%Y-%m-%d").strftime("%Y%m%d")
            except Exception:
                continue
            fh.write(f"BEGIN:VEVENT\r\nUID:{sid}-{mc}-{d}@abs\r\n"
                     f"DTSTART;VALUE=DATE:{dt}\r\nDTEND;VALUE=DATE:{dt}\r\n"
                     f"SUMMARY:{mc} — {st}\r\nEND:VEVENT\r\n")
        fh.write("END:VCALENDAR\r\n")
    audit(ctx, "student.ics", "attendance", sid, path)
    messagebox.showinfo("Exported", f"ICS written:\n{path}", parent=ctx.parent)


@safe("Recovery plan")
def stu_27_recovery_plan(ctx: StudentContext):
    """Suggest catch-up actions for my recent absences."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT date, module_code, COALESCE(reason,'') FROM attendance
           WHERE student_id=? AND status IN ('absent','late')
           ORDER BY date DESC LIMIT 10""", (sid,)).fetchall()
    suggestions = [
        (d, mc, "Request notes + review recording; book office hours this week.")
        for d, mc, _r in rows
    ]
    _show_table(ctx.parent, "Recovery plan",
                ("date", "module", "suggested action"), suggestions,
                widths=[100, 120, 620])


@safe("Wellbeing check-in")
def stu_28_wellbeing_checkin(ctx: StudentContext):
    """Log a wellbeing note attached to an absence."""
    sid = _require_sid(ctx)
    if not sid:
        return
    abs_id = simpledialog.askinteger("Attendance id",
                                     "Attendance row id (from My Absences):",
                                     parent=ctx.parent)
    note = simpledialog.askstring("Note", "Private note to self:", parent=ctx.parent)
    if not (abs_id and note):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_wellbeing_flags (student_id, attendance_id, note)
           VALUES (?,?,?)""", (sid, abs_id, note))
    ctx.db.conn.commit()
    audit(ctx, "student.wellbeing", "abs_tracker_wellbeing_flags", sid, str(abs_id))
    messagebox.showinfo("Saved", "Check-in saved.", parent=ctx.parent)


# ===========================================================================
# 29–35  Academic & wellness support
# ===========================================================================

@safe("Request notes")
def stu_29_request_notes(ctx: StudentContext):
    """Ask classmates for notes from a missed session."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    d = simpledialog.askstring("Date", "Session date (YYYY-MM-DD):",
                               parent=ctx.parent)
    if not (pick and d):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_note_requests (requester_id, module_code, date)
           VALUES (?,?,?)""", (sid, mmap[pick], d))
    ctx.db.conn.commit()
    audit(ctx, "student.note_request", "abs_tracker_note_requests", sid,
          f"{mmap[pick]} {d}")
    messagebox.showinfo("Requested",
                        "Classmates will see your request on the peer board.",
                        parent=ctx.parent)


@safe("Book office hours")
def stu_30_book_office_hours(ctx: StudentContext):
    """Show instructor office hours; write an office_hour_bookings row."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    if not pick:
        return
    # office_hours table is central; fall back to creating a booking row
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS office_hour_bookings
        (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, module_code TEXT,
         requested_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'pending')""")
    ctx.db.cur.execute(
        "INSERT INTO office_hour_bookings (student_id, module_code) VALUES (?,?)",
        (sid, mmap[pick]))
    ctx.db.conn.commit()
    audit(ctx, "student.office_hours", "office_hour_bookings", sid, mmap[pick])
    messagebox.showinfo("Requested",
                        f"Office-hours request logged for {mmap[pick]}.",
                        parent=ctx.parent)


@safe("Study buddy")
def stu_31_study_buddy(ctx: StudentContext):
    """Opt into the study-buddy pool for a module and see matches."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    if not pick:
        return
    ctx.db.cur.execute(
        """INSERT OR IGNORE INTO abs_tracker_study_buddies
           (student_id, module_code) VALUES (?,?)""", (sid, mmap[pick]))
    ctx.db.conn.commit()
    others = ctx.db.cur.execute(
        """SELECT b.student_id,
                  TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,''))
           FROM abs_tracker_study_buddies b
           LEFT JOIN students s ON s.student_id = b.student_id
           WHERE b.module_code=? AND b.student_id<>?""", (mmap[pick], sid)).fetchall()
    audit(ctx, "student.study_buddy", "abs_tracker_study_buddies", sid, mmap[pick])
    _show_table(ctx.parent, f"Study buddies for {mmap[pick]}",
                ("student_id", "name"), others, widths=[140, 320])


@safe("Recorded lectures")
def stu_32_recorded_lectures(ctx: StudentContext):
    """Show virtual_recordings matching my missed dates."""
    sid = _require_sid(ctx)
    if not sid:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS virtual_recordings
        (id INTEGER PRIMARY KEY, module_code TEXT, date TEXT, url TEXT, title TEXT)""")
    rows = ctx.db.cur.execute(
        """SELECT a.date, a.module_code, COALESCE(vr.title,''), COALESCE(vr.url,'')
           FROM attendance a
           LEFT JOIN virtual_recordings vr
              ON vr.module_code = a.module_code AND vr.date = a.date
           WHERE a.student_id=? AND a.status IN ('absent','excused')
           ORDER BY a.date DESC LIMIT 30""", (sid,)).fetchall()
    _show_table(ctx.parent, "Recordings for my missed sessions",
                ("date", "module", "title", "url"), rows,
                widths=[100, 110, 300, 340])


@safe("Wellbeing flag")
def stu_33_wellbeing_flag(ctx: StudentContext):
    """Confidentially flag a wellbeing concern tied to an absence."""
    sid = _require_sid(ctx)
    if not sid:
        return
    note = simpledialog.askstring(
        "Confidential note",
        "Brief note (visible to wellbeing staff only):",
        parent=ctx.parent)
    if not note:
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_wellbeing_flags (student_id, attendance_id, note)
           VALUES (?, NULL, ?)""", (sid, note))
    ctx.db.conn.commit()
    audit(ctx, "student.wellbeing_flag", "abs_tracker_wellbeing_flags", sid, "(redacted)")
    messagebox.showinfo("Flagged",
                        "Thanks — wellbeing staff will review your flag.",
                        parent=ctx.parent)


@safe("Support resources")
def stu_34_support_resources(ctx: StudentContext):
    """Show support resource links."""
    resources = [
        ("Counselling & Wellbeing",  "Book: /student-support/counselling"),
        ("Disability Services",       "Contact: disability@university.edu"),
        ("Academic Advising",         "Portal: /advising"),
        ("Tutoring",                  "Find a tutor: /tutoring"),
        ("Financial Hardship",        "Apply: /financial-aid/hardship"),
        ("Chaplaincy",                "Quiet space: Campus centre rm 12"),
    ]
    _show_table(ctx.parent, "Support resources", ("service", "how"), resources,
                widths=[240, 520])


@safe("Self-refer to advising")
def stu_35_self_refer_advising(ctx: StudentContext):
    """Create an advising_appointments row from the tracker."""
    sid = _require_sid(ctx)
    if not sid:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS advising_appointments
        (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, topic TEXT,
         requested_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'pending')""")
    topic = simpledialog.askstring("Topic", "What's it about?", parent=ctx.parent)
    if not topic:
        return
    ctx.db.cur.execute(
        "INSERT INTO advising_appointments (student_id, topic) VALUES (?,?)",
        (sid, topic))
    ctx.db.conn.commit()
    audit(ctx, "student.advising", "advising_appointments", sid, topic[:120])
    messagebox.showinfo("Submitted",
                        "Advising request submitted.", parent=ctx.parent)


# ===========================================================================
# 36–39  Social / peer
# ===========================================================================

@safe("Find study group")
def stu_36_find_study_group(ctx: StudentContext):
    """Find or create a study group for a module I'm enrolled in."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    if not pick:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS study_groups
        (id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT, name TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS study_group_members
        (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, student_id TEXT,
         UNIQUE(group_id, student_id))""")
    rows = ctx.db.cur.execute(
        "SELECT id, name FROM study_groups WHERE module_code=?", (mmap[pick],)).fetchall()
    if not rows:
        ctx.db.cur.execute(
            "INSERT INTO study_groups (module_code, name) VALUES (?,?)",
            (mmap[pick], f"{mmap[pick]} Study Group"))
        gid = ctx.db.cur.lastrowid
    else:
        gid = rows[0][0]
    ctx.db.cur.execute(
        "INSERT OR IGNORE INTO study_group_members (group_id, student_id) VALUES (?,?)",
        (gid, sid))
    ctx.db.conn.commit()
    audit(ctx, "student.study_group", "study_group_members", sid,
          f"gid={gid} {mmap[pick]}")
    messagebox.showinfo("Joined", f"Joined study group #{gid}.", parent=ctx.parent)


@safe("Note share")
def stu_37_note_share(ctx: StudentContext):
    """Upload or browse shared notes for a module."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    if not pick:
        return
    action = _combo_dialog(ctx.parent, "Action", "Do what?", ["upload", "browse"])
    if action == "upload":
        title = simpledialog.askstring("Title", "Notes title:", parent=ctx.parent)
        d = simpledialog.askstring("Date", "Session date:", parent=ctx.parent,
                                   initialvalue=date.today().isoformat())
        path = filedialog.askopenfilename(parent=ctx.parent)
        if not (title and d and path):
            return
        ctx.db.cur.execute(
            """INSERT INTO abs_tracker_note_share
               (owner_id, module_code, date, file_path, title) VALUES (?,?,?,?,?)""",
            (sid, mmap[pick], d, path, title))
        ctx.db.conn.commit()
        audit(ctx, "student.note_upload", "abs_tracker_note_share", sid, title)
        messagebox.showinfo("Uploaded", "Notes shared.", parent=ctx.parent)
    elif action == "browse":
        rows = ctx.db.cur.execute(
            """SELECT date, title, owner_id, file_path FROM abs_tracker_note_share
               WHERE module_code=? ORDER BY date DESC""", (mmap[pick],)).fetchall()
        _show_table(ctx.parent, f"Shared notes — {mmap[pick]}",
                    ("date", "title", "owner", "path"), rows,
                    widths=[100, 260, 140, 360])


@safe("Attendance badge")
def stu_38_attendance_badge(ctx: StudentContext):
    """Award a badge for good attendance streaks."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        "SELECT date, status FROM attendance WHERE student_id=? ORDER BY date",
        (sid,)).fetchall()
    longest = cur = 0
    for _d, st in rows:
        if st == "present":
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    badges = []
    for thresh, badge in [(5, "5-day streak"), (10, "10-day streak"),
                          (20, "20-day streak"), (30, "perfect month")]:
        if longest >= thresh:
            badges.append(badge)
            ctx.db.cur.execute(
                "INSERT OR IGNORE INTO abs_tracker_student_badges (student_id, badge) VALUES (?,?)",
                (sid, badge))
    ctx.db.conn.commit()
    audit(ctx, "student.badges", "abs_tracker_student_badges", sid,
          ",".join(badges))
    messagebox.showinfo("Badges",
                        "You earned:\n" + "\n".join(badges) if badges
                        else "No streak badges yet — keep showing up!",
                        parent=ctx.parent)


@safe("Weekly digest")
def stu_39_weekly_digest(ctx: StudentContext):
    """Show a digest of the last 7 days."""
    sid = _require_sid(ctx)
    if not sid:
        return
    since = (date.today() - timedelta(days=7)).isoformat()
    rows = ctx.db.cur.execute(
        """SELECT date, module_code, status FROM attendance
           WHERE student_id=? AND date >= ? ORDER BY date DESC""",
        (sid, since)).fetchall()
    present = sum(1 for r in rows if r[2] == "present")
    absent = sum(1 for r in rows if r[2] == "absent")
    late = sum(1 for r in rows if r[2] == "late")
    win = tk.Toplevel(ctx.parent)
    win.title("Weekly digest")
    win.geometry("540x400")
    tk.Label(win, text=f"Last 7 days — {ctx.user['name']}",
             font=("Arial", 13, "bold")).pack(pady=8)
    tk.Label(win, text=f"Present: {present} | Absent: {absent} | Late: {late}",
             font=("Arial", 11)).pack(pady=4)
    lst = tk.Listbox(win)
    lst.pack(fill="both", expand=True, padx=10, pady=10)
    for d, mc, st in rows:
        lst.insert("end", f"{d}  {mc}  {st}")


# ===========================================================================
# 40–42  Appeals & corrections
# ===========================================================================

@safe("Dispute record")
def stu_40_dispute_record(ctx: StudentContext):
    """Raise a correction request on an attendance row."""
    sid = _require_sid(ctx)
    if not sid:
        return
    aid = simpledialog.askinteger("Attendance id",
                                  "Row id (from My Absences):",
                                  parent=ctx.parent)
    reason = simpledialog.askstring("Reason",
                                    "Why do you believe this is wrong?",
                                    parent=ctx.parent)
    if not (aid and reason):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_attendance_disputes
           (student_id, attendance_id, reason) VALUES (?,?,?)""",
        (sid, aid, reason))
    ctx.db.conn.commit()
    audit(ctx, "student.dispute", "abs_tracker_attendance_disputes", sid,
          f"aid={aid}")
    messagebox.showinfo("Submitted", "Dispute raised.", parent=ctx.parent)


@safe("Dispute history")
def stu_41_dispute_history(ctx: StudentContext):
    """View the history of my disputes."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT id, attendance_id, reason, status, created_at,
                  COALESCE(outcome,''), COALESCE(resolved_at,'')
           FROM abs_tracker_attendance_disputes
           WHERE student_id=? ORDER BY created_at DESC""", (sid,)).fetchall()
    _show_table(ctx.parent, "My disputes",
                ("id", "attendance id", "reason", "status", "created",
                 "outcome", "resolved"), rows,
                widths=[60, 120, 260, 100, 150, 140, 150])


@safe("Appeal")
def stu_42_appeal_request(ctx: StudentContext):
    """Appeal a rejected request."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT id, date, module_code FROM absence_requests
           WHERE student_id=? AND status='rejected'""", (sid,)).fetchall()
    if not rows:
        messagebox.showinfo("None", "No rejected requests to appeal.",
                            parent=ctx.parent)
        return
    m = {f"#{r[0]} {r[1]} {r[2]}": r[0] for r in rows}
    pick = _combo_dialog(ctx.parent, "Appeal", "Which request?", list(m.keys()))
    reason = simpledialog.askstring("Grounds", "Grounds for appeal:",
                                    parent=ctx.parent)
    if not (pick and reason):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_appeals (student_id, request_id, reason)
           VALUES (?,?,?)""", (sid, m[pick], reason))
    ctx.db.conn.commit()
    audit(ctx, "student.appeal", "abs_tracker_appeals", sid, f"req={m[pick]}")
    messagebox.showinfo("Submitted", "Appeal filed.", parent=ctx.parent)


# ===========================================================================
# 43–47  Integrations
# ===========================================================================

@safe("My timetable")
def stu_43_my_timetable(ctx: StudentContext):
    """Next scheduled classes from module_schedule for my enrolments."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
                  ms.room_id, ms.semester
           FROM module_schedule ms
           JOIN student_modules sm ON sm.module_code = ms.module_code
           WHERE sm.student_id=? ORDER BY ms.day_of_week, ms.start_time""",
        (sid,)).fetchall()
    _show_table(ctx.parent, "My timetable",
                ("module", "day", "start", "end", "room", "semester"), rows)


@safe("Grade impact")
def stu_44_grade_impact(ctx: StudentContext):
    """Current grade per module + attendance %, flagged if below policy."""
    sid = _require_sid(ctx)
    if not sid:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS student_grades
        (id INTEGER PRIMARY KEY, student_id TEXT, module_code TEXT, grade TEXT)""")
    rows = ctx.db.cur.execute(
        """SELECT m.module_code,
                  COALESCE((SELECT grade FROM student_grades
                            WHERE student_id=? AND module_code=m.module_code
                            ORDER BY id DESC LIMIT 1), '—') AS grade,
                  COALESCE((SELECT
                     SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100
                     FROM attendance WHERE student_id=? AND module_code=m.module_code), 0) AS pct
           FROM student_modules sm JOIN modules m ON m.module_code=sm.module_code
           WHERE sm.student_id=?""",
        (sid, sid, sid)).fetchall()
    _show_table(ctx.parent, "Grades vs attendance",
                ("module", "grade", "attendance %"),
                [(mc, g, f"{p:.1f}") for mc, g, p in rows])


@safe("My assignments")
def stu_45_my_assignments(ctx: StudentContext):
    """Upcoming assignments for modules I'm enrolled in."""
    sid = _require_sid(ctx)
    if not sid:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS assignments
        (id INTEGER PRIMARY KEY, module_code TEXT, title TEXT, due_date TEXT, status TEXT)""")
    rows = ctx.db.cur.execute(
        """SELECT a.module_code, a.title, a.due_date, COALESCE(a.status,'')
           FROM assignments a
           JOIN student_modules sm ON sm.module_code = a.module_code
           WHERE sm.student_id=?
           ORDER BY a.due_date""", (sid,)).fetchall()
    _show_table(ctx.parent, "My assignments",
                ("module", "title", "due", "status"), rows,
                widths=[110, 380, 110, 120])


@safe("Library resources")
def stu_46_library_resources(ctx: StudentContext):
    """Search the library catalogue for recovery materials."""
    q = simpledialog.askstring("Library search", "Search term:",
                               parent=ctx.parent)
    if not q:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS books
        (id INTEGER PRIMARY KEY, title TEXT, author TEXT, shelf TEXT)""")
    like = f"%{q}%"
    rows = ctx.db.cur.execute(
        """SELECT title, COALESCE(author,''), COALESCE(shelf,'')
           FROM books WHERE title LIKE ? OR author LIKE ? LIMIT 50""",
        (like, like)).fetchall()
    _show_table(ctx.parent, f"Library — '{q}'",
                ("title", "author", "shelf"), rows)


@safe("Exam-day check")
def stu_47_exam_day_check(ctx: StudentContext):
    """Flag exam-day attendance for modules I'm enrolled in."""
    sid = _require_sid(ctx)
    if not sid:
        return
    rows = ctx.db.cur.execute(
        """SELECT m.module_code, e.date, e.name
           FROM academic_calendar_events e
           JOIN student_modules sm ON 1=1
           JOIN modules m ON m.module_code = sm.module_code
           WHERE sm.student_id=? AND e.event_type LIKE '%exam%'
             AND e.date >= date('now')
           ORDER BY e.date""", (sid,)).fetchall()
    _show_table(ctx.parent, "Upcoming exam dates (must attend)",
                ("module", "date", "event"), rows, widths=[120, 110, 500])


# ===========================================================================
# 48–50  Accessibility & customisation
# ===========================================================================

@safe("Accessibility mode")
def stu_48_accessibility_mode(ctx: StudentContext):
    """Toggle large-text / high-contrast on this session."""
    sid = _require_sid(ctx)
    if not sid:
        return
    on = _pref(ctx.db, sid, "a11y", "0") == "1"
    on = not on
    _set_pref(ctx.db, sid, "a11y", "1" if on else "0")
    try:
        style = ttk.Style()
        if on:
            style.configure("Treeview", rowheight=34, font=("Arial", 13))
            style.configure("Treeview.Heading", font=("Arial", 13, "bold"))
            ctx.parent.option_add("*Font", "Arial 13")
        else:
            style.configure("Treeview", rowheight=26, font=("Arial", 10))
            style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
            ctx.parent.option_add("*Font", "Arial 10")
    except Exception:
        logger.exception("a11y apply failed")
    audit(ctx, "student.a11y", "prefs", sid, "on" if on else "off")
    messagebox.showinfo("Accessibility",
                        f"Accessibility mode is now {'ON' if on else 'OFF'}.",
                        parent=ctx.parent)


@safe("Language")
def stu_49_language(ctx: StudentContext):
    """Pick UI language (stored as pref — main system reads this)."""
    sid = _require_sid(ctx)
    if not sid:
        return
    lang = _combo_dialog(ctx.parent, "Language", "Language:",
                        ["en", "fr", "es", "de", "zh", "ar"])
    if not lang:
        return
    _set_pref(ctx.db, sid, "language", lang)
    audit(ctx, "student.language", "prefs", sid, lang)
    messagebox.showinfo("Saved",
                        f"Language set to '{lang}'. Restart to apply everywhere.",
                        parent=ctx.parent)


@safe("Dashboard layout")
def stu_50_dashboard_layout(ctx: StudentContext):
    """Reorder / hide tabs — saved per student."""
    sid = _require_sid(ctx)
    if not sid:
        return
    current = _pref(ctx.db, sid, "dashboard_tabs",
                    "📚 My Modules,📋 My Absences,📤 Submit Request,"
                    "📨 My Requests,📊 My Stats,🧑‍🎓 Student Tools (50)")
    new = simpledialog.askstring(
        "Tabs order",
        "Comma-separated tab names in desired order:",
        parent=ctx.parent, initialvalue=current)
    if new is None:
        return
    _set_pref(ctx.db, sid, "dashboard_tabs", new)
    audit(ctx, "student.layout", "prefs", sid, new)
    messagebox.showinfo("Saved",
                        "Layout saved. It'll take effect next time you open the tracker.",
                        parent=ctx.parent)


# ===========================================================================
# 51  Request time off (date-picker)
# ===========================================================================

@safe("Request time off")
def stu_51_request_time_off(ctx: StudentContext):
    """Submit an absence request using dropdown date pickers (no manual typing)."""
    sid = _require_sid(ctx)
    if not sid:
        return
    modules = ctx.db.get_courses(student_id=sid)
    if not modules:
        messagebox.showinfo("No modules", "You aren't enrolled in any modules.",
                            parent=ctx.parent)
        return
    mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
    pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mmap.keys()))
    if not pick:
        return
    rng = pick_date_range(ctx.parent, "Time-off dates")
    if not rng:
        return
    start, end = rng
    reason = simpledialog.askstring("Reason", "Reason for time off:",
                                    parent=ctx.parent)
    if not reason:
        return
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    days = (d1 - d0).days + 1
    d = d0
    submitted = 0
    while d <= d1:
        ctx.db.submit_request(sid, mmap[pick], d.isoformat(), reason)
        submitted += 1
        d += timedelta(days=1)
    audit(ctx, "student.request_time_off", "absence_requests", sid,
          f"{mmap[pick]} {start}..{end} ({days}d)")
    messagebox.showinfo(
        "Submitted",
        f"{submitted} absence request(s) submitted for {start} → {end}.",
        parent=ctx.parent,
    )


# ---------------------------------------------------------------------------
# Registry + tab renderer
# ---------------------------------------------------------------------------
FEATURES: list[tuple[int, str, str, Callable]] = [
    (1,  "Visibility",    "Calendar view",                  stu_01_calendar),
    (2,  "Visibility",    "Attendance gauges",              stu_02_gauge),
    (3,  "Visibility",    "Streak tracker",                 stu_03_streak),
    (4,  "Visibility",    "Personal timeline",              stu_04_timeline),
    (5,  "Visibility",    "Export my data (CSV)",           stu_05_export_my_data),
    (6,  "Visibility",    "Compare to module average",      stu_06_compare_module_avg),
    (7,  "Visibility",    "Absence-budget projection",      stu_07_projection),
    (8,  "Visibility",    "Personal heatmap",               stu_08_personal_heatmap),

    (9,  "Requests",      "Quick-submit from template",     stu_09_quick_submit),
    (10, "Requests",      "Attach evidence",                stu_10_attach_evidence),
    (11, "Requests",      "Status tracker",                 stu_11_status_tracker),
    (12, "Requests",      "Withdraw pending",               stu_12_withdraw),
    (13, "Requests",      "Resubmit rejected",              stu_13_resubmit),
    (14, "Requests",      "Bulk multi-day request",         stu_14_bulk_request),
    (15, "Requests",      "Save draft",                     stu_15_save_draft),
    (16, "Requests",      "Export request history",         stu_16_history_export),

    (17, "Reminders",     "Class reminder minutes",         stu_17_class_reminder),
    (18, "Reminders",     "Low-attendance self-alert",      stu_18_low_attendance_alert),
    (19, "Reminders",     "Upcoming deadlines",             stu_19_deadline_alerts),
    (20, "Reminders",     "Parent-notification log",        stu_20_parent_notif_log),
    (21, "Reminders",     "Channel preferences",            stu_21_notification_prefs),
    (22, "Reminders",     "Do-not-disturb hours",           stu_22_dnd_hours),

    (23, "Planning",      "Per-module goals",               stu_23_attendance_goals),
    (24, "Planning",      "Attendance budget",              stu_24_attendance_budget),
    (25, "Planning",      "Term forecast",                  stu_25_term_forecast),
    (26, "Planning",      "Calendar sync (ICS)",            stu_26_calendar_sync),
    (27, "Planning",      "Recovery planner",               stu_27_recovery_plan),
    (28, "Planning",      "Wellbeing check-in",             stu_28_wellbeing_checkin),

    (29, "Support",       "Request notes from classmates",  stu_29_request_notes),
    (30, "Support",       "Book office hours",              stu_30_book_office_hours),
    (31, "Support",       "Study buddy matchmaker",         stu_31_study_buddy),
    (32, "Support",       "Recorded lectures",              stu_32_recorded_lectures),
    (33, "Support",       "Confidential wellbeing flag",    stu_33_wellbeing_flag),
    (34, "Support",       "Support resources",              stu_34_support_resources),
    (35, "Support",       "Self-refer to advising",         stu_35_self_refer_advising),

    (36, "Social",        "Find study group",               stu_36_find_study_group),
    (37, "Social",        "Note-share marketplace",         stu_37_note_share),
    (38, "Social",        "Attendance badges",              stu_38_attendance_badge),
    (39, "Social",        "Weekly digest",                  stu_39_weekly_digest),

    (40, "Appeals",       "Dispute a record",               stu_40_dispute_record),
    (41, "Appeals",       "My dispute history",             stu_41_dispute_history),
    (42, "Appeals",       "Appeal a rejected request",      stu_42_appeal_request),

    (43, "Integrations",  "My timetable",                   stu_43_my_timetable),
    (44, "Integrations",  "Grade vs attendance impact",     stu_44_grade_impact),
    (45, "Integrations",  "My assignments",                 stu_45_my_assignments),
    (46, "Integrations",  "Library resources",              stu_46_library_resources),
    (47, "Integrations",  "Exam-day check",                 stu_47_exam_day_check),

    (48, "Accessibility", "Accessibility mode (toggle)",    stu_48_accessibility_mode),
    (49, "Accessibility", "Language",                       stu_49_language),
    (50, "Accessibility", "Dashboard layout",               stu_50_dashboard_layout),

    (51, "Requests",      "Request time off (date picker)", stu_51_request_time_off),
]


def build_student_tab(notebook: ttk.Notebook, ctx: StudentContext) -> None:
    """Render all 50 student features into a dedicated tab."""
    ensure_support_tables(ctx.db)       # admin-side support tables (templates, etc.)
    ensure_student_tables(ctx.db)

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

    by_cat: dict[str, list[tuple[int, str, Callable]]] = {}
    for n, cat, label, fn in FEATURES:
        by_cat.setdefault(cat, []).append((n, label, fn))

    for cat, items in by_cat.items():
        box = tk.LabelFrame(inner, text=cat, padx=10, pady=8,
                            font=("Arial", 11, "bold"), bg="#f0f4f8",
                            fg="#1e3a5f")
        box.pack(fill="x", padx=12, pady=8)
        cols = 3
        for i, (num, label, fn) in enumerate(items):
            btn = tk.Button(
                box, text=f"{num:02d}. {label}",
                command=functools.partial(fn, ctx),
                bg="#0ea5e9", fg="white", activebackground="#0284c7",
                relief="flat", cursor="hand2",
                width=32, anchor="w", padx=8, pady=6,
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="w")

    logger.info("student tools tab built (%d features)", len(FEATURES))
