"""
Staff / instructor features for the Absence Tracker.

Fifty staff-facing utilities, each wrapped with the shared ``@safe`` decorator
for uniform logging and error handling. Context carries the DB handle, parent
Tk window, and authenticated user dict (an instructor / staff user).
"""

from __future__ import annotations

import csv
import functools
import io
import json
import logging
import os
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Optional

from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables, logger as _admin_logger,
    pick_date, pick_date_range,
)

logger = logging.getLogger("absence_tracker.staff")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
    for h in _admin_logger.handlers:
        logger.addHandler(h)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Context + support tables
# ---------------------------------------------------------------------------
@dataclass
class StaffContext:
    db: Any
    parent: tk.Misc
    user: dict

    @property
    def uid(self) -> int:
        return int(self.user.get("id") or 0)


def ensure_staff_tables(db) -> None:
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _my_modules(ctx: StaffContext):
    return ctx.db.get_courses(staff_id=ctx.uid)


def _pick_my_module(ctx: StaffContext, prompt="Pick one of your modules"):
    mods = _my_modules(ctx)
    if not mods:
        messagebox.showinfo("No modules",
                            "You are not assigned to any modules.",
                            parent=ctx.parent)
        return None
    m = {f"{r[1]} - {r[2]}": r[0] for r in mods}
    pick = _combo_dialog(ctx.parent, prompt, "Module:", list(m.keys()))
    return m.get(pick) if pick else None


def _pref(db, uid, key, default=None):
    r = db.cur.execute(
        "SELECT value FROM abs_tracker_staff_prefs WHERE user_id=? AND key=?",
        (uid, key)).fetchone()
    return r[0] if r else default


def _set_pref(db, uid, key, value):
    db.cur.execute(
        """INSERT OR REPLACE INTO abs_tracker_staff_prefs (user_id, key, value)
           VALUES (?, ?, ?)""", (uid, key, str(value)))
    db.conn.commit()


# ===========================================================================
# 1–10  Roll-call & session management
# ===========================================================================

@safe("Today's classes")
def stf_01_today_dashboard(ctx: StaffContext):
    """List today's scheduled sessions for the caller."""
    today = datetime.today().strftime("%A")
    rows = ctx.db.cur.execute(
        """SELECT ms.module_code, ms.start_time, ms.end_time, ms.room_id
           FROM module_schedule ms WHERE ms.instructor_id=? AND ms.day_of_week=?
           ORDER BY ms.start_time""", (ctx.uid, today)).fetchall()
    _show_table(ctx.parent, f"Today — {today}",
                ("module", "start", "end", "room"), rows,
                widths=[140, 100, 100, 120])
    audit(ctx, "staff.today", "module_schedule", ctx.uid, today)


@safe("Generate sessions")
def stf_02_generate_sessions(ctx: StaffContext):
    """Preview session dates for a module from its schedule rows."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    start = simpledialog.askstring("From", "Start date (YYYY-MM-DD):",
                                   parent=ctx.parent,
                                   initialvalue=date.today().isoformat())
    end = simpledialog.askstring("To", "End date (YYYY-MM-DD):",
                                 parent=ctx.parent,
                                 initialvalue=(date.today() + timedelta(days=84)).isoformat())
    if not (start and end):
        return
    sched = ctx.db.cur.execute(
        "SELECT day_of_week, start_time FROM module_schedule WHERE module_code=?",
        (mc,)).fetchall()
    dow_map = {n: i for i, n in enumerate(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    out = []
    d = d0
    while d <= d1:
        for dow, t in sched:
            if d.weekday() == dow_map.get(dow, -1):
                out.append((d.isoformat(), mc, t))
        d += timedelta(days=1)
    _show_table(ctx.parent, f"Upcoming sessions — {mc} ({len(out)})",
                ("date", "module", "start"), out)


@safe("Session note")
def stf_03_session_note(ctx: StaffContext):
    """Attach a teaching note to a given session date."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    d = simpledialog.askstring("Date", "Date (YYYY-MM-DD):", parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    note = simpledialog.askstring("Note", "Note:", parent=ctx.parent)
    if not (d and note):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_session_notes
           (staff_id, module_code, date, note) VALUES (?,?,?,?)""",
        (ctx.uid, mc, d, note))
    ctx.db.conn.commit()
    audit(ctx, "staff.note", "abs_tracker_session_notes", ctx.uid, f"{mc} {d}")
    messagebox.showinfo("Saved", "Session note saved.", parent=ctx.parent)


@safe("Cancel session")
def stf_04_cancel_session(ctx: StaffContext):
    """Mark a whole session cancelled — marks every student 'excused'."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    d = simpledialog.askstring("Date", "Date (YYYY-MM-DD):", parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    reason = simpledialog.askstring("Reason", "Reason:", parent=ctx.parent) or "Cancelled"
    if not d:
        return
    ctx.db.cur.execute(
        """INSERT OR REPLACE INTO abs_tracker_session_status
           (module_code, date, status, set_by) VALUES (?, ?, 'cancelled', ?)""",
        (mc, d, ctx.uid))
    roster = ctx.db.get_course_students(mc)
    for sid, *_ in roster:
        ctx.db.record_absence(sid, mc, d, "excused", f"[cancelled] {reason}")
    ctx.db.conn.commit()
    audit(ctx, "staff.cancel_session", "attendance", mc,
          f"{d} n={len(roster)}")
    messagebox.showinfo("Cancelled",
                        f"Session on {d} cancelled; {len(roster)} students excused.",
                        parent=ctx.parent)


@safe("Substitute mode")
def stf_05_substitute_mode(ctx: StaffContext):
    """Take roll on behalf of another instructor."""
    staff = ctx.db.get_users("instructor") + ctx.db.get_users("staff")
    m = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in staff if r[0] != ctx.uid}
    if not m:
        messagebox.showinfo("No-one", "No other instructors.", parent=ctx.parent)
        return
    pick = _combo_dialog(ctx.parent, "Substitute for", "Instructor:", list(m.keys()))
    if not pick:
        return
    their_uid = m[pick]
    their_mods = ctx.db.get_courses(staff_id=their_uid)
    if not their_mods:
        messagebox.showinfo("No modules",
                            f"{pick} has no modules.", parent=ctx.parent)
        return
    mm = {f"{r[1]} - {r[2]}": r[0] for r in their_mods}
    mod_pick = _combo_dialog(ctx.parent, "Module", "Module:", list(mm.keys()))
    if not mod_pick:
        return
    d = simpledialog.askstring("Date", "Date:", parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    if not d:
        return
    roster = ctx.db.get_course_students(mm[mod_pick])
    for sid, *_ in roster:
        ctx.db.record_absence(sid, mm[mod_pick], d, "present",
                              f"[sub by {ctx.user.get('username')}]")
    audit(ctx, "staff.substitute", "attendance", their_uid,
          f"{mm[mod_pick]} {d} n={len(roster)}")
    messagebox.showinfo("Recorded",
                        f"Substituted for {pick}: {len(roster)} marked present.",
                        parent=ctx.parent)


@safe("All-present")
def stf_06_all_present_except(ctx: StaffContext):
    """Mark all present except a list of student ids."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    d = simpledialog.askstring("Date", "Date:", parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    excl = simpledialog.askstring(
        "Exclusions", "Student IDs absent (comma-separated):",
        parent=ctx.parent) or ""
    except_ids = {x.strip() for x in excl.split(",") if x.strip()}
    roster = ctx.db.get_course_students(mc)
    for sid, *_ in roster:
        status = "absent" if sid in except_ids else "present"
        ctx.db.record_absence(sid, mc, d, status, "quick roll")
    audit(ctx, "staff.all_present", "attendance", mc,
          f"{d} except={','.join(except_ids)}")
    messagebox.showinfo(
        "Saved",
        f"Marked {len(roster) - len(except_ids)} present, {len(except_ids)} absent.",
        parent=ctx.parent)


@safe("Late log")
def stf_07_late_log(ctx: StaffContext):
    """Quick-add a 'late' record for a student."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    roster = ctx.db.get_course_students(mc)
    rm = {f"{r[1]} ({r[0]})": r[0] for r in roster}
    pick = _combo_dialog(ctx.parent, "Late", "Student:", list(rm.keys()))
    mins = simpledialog.askinteger("Minutes late", "Minutes late:",
                                   parent=ctx.parent, minvalue=1, maxvalue=120)
    if not (pick and mins):
        return
    ctx.db.record_absence(rm[pick], mc, date.today().isoformat(),
                          "late", f"late {mins}m")
    audit(ctx, "staff.late", "attendance", rm[pick], f"{mc} {mins}m")
    messagebox.showinfo("Recorded", f"{pick}: late {mins}m.", parent=ctx.parent)


@safe("Early leave")
def stf_08_early_leave(ctx: StaffContext):
    """Record an early-leave partial attendance row."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    roster = ctx.db.get_course_students(mc)
    rm = {f"{r[1]} ({r[0]})": r[0] for r in roster}
    pick = _combo_dialog(ctx.parent, "Early-leave", "Student:", list(rm.keys()))
    note = simpledialog.askstring("Reason", "Reason:", parent=ctx.parent)
    if not (pick and note):
        return
    ctx.db.record_absence(rm[pick], mc, date.today().isoformat(),
                          "late", f"early-leave: {note}")
    audit(ctx, "staff.early_leave", "attendance", rm[pick], note[:80])
    messagebox.showinfo("Recorded", "Early-leave logged.", parent=ctx.parent)


@safe("QR code")
def stf_09_session_qr(ctx: StaffContext):
    """Generate a pseudo-QR code token students can self-check-in with."""
    import secrets
    mc = _pick_my_module(ctx)
    if not mc:
        return
    d = date.today().isoformat()
    code = secrets.token_hex(4).upper()
    ctx.db.cur.execute(
        """INSERT OR REPLACE INTO abs_tracker_session_qr
           (module_code, date, code) VALUES (?, ?, ?)""",
        (mc, d, code))
    ctx.db.conn.commit()
    audit(ctx, "staff.qr", "abs_tracker_session_qr", mc, code)
    messagebox.showinfo("QR code",
                        f"Share this self-check-in code with your class:\n\n"
                        f"Module: {mc}\nDate: {d}\nCode: {code}",
                        parent=ctx.parent)


@safe("Correct roll")
def stf_10_correct_roll(ctx: StaffContext):
    """Edit one of my just-taken attendance rows."""
    rid = simpledialog.askinteger("Row id", "Attendance row id to edit:",
                                  parent=ctx.parent)
    if rid is None:
        return
    row = ctx.db.cur.execute(
        "SELECT status, reason, module_code FROM attendance WHERE id=?",
        (rid,)).fetchone()
    if not row:
        messagebox.showerror("Not found", f"Row {rid} missing.",
                             parent=ctx.parent)
        return
    mine = {r[0] for r in _my_modules(ctx)}
    if row[2] not in mine:
        messagebox.showerror("Not yours",
                             "That row isn't on one of your modules.",
                             parent=ctx.parent)
        return
    new_status = simpledialog.askstring("Status", f"New status (was {row[0]}):",
                                        parent=ctx.parent) or row[0]
    new_reason = simpledialog.askstring("Reason", f"New reason (was {row[1] or ''}):",
                                        parent=ctx.parent) or row[1]
    ctx.db.cur.execute(
        "UPDATE attendance SET status=?, reason=? WHERE id=?",
        (new_status, new_reason, rid))
    ctx.db.conn.commit()
    audit(ctx, "staff.correct", "attendance", rid, f"{row[0]}→{new_status}")
    messagebox.showinfo("Updated", "Row updated.", parent=ctx.parent)


# ===========================================================================
# 11–15  Roster views & search
# ===========================================================================

@safe("Roster photos")
def stf_11_roster_with_photos(ctx: StaffContext):
    """Roster including any `photo_url` or emergency_contact hint column."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    rows = ctx.db.cur.execute(
        """SELECT s.student_id,
                  TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')),
                  COALESCE(s.email_address,''),
                  COALESCE(s.emergency_contact,'')
           FROM student_modules sm
           JOIN students s ON s.student_id = sm.student_id
           WHERE sm.module_code=?
           ORDER BY s.last_name""", (mc,)).fetchall()
    _show_table(ctx.parent, f"Roster — {mc}",
                ("student_id", "name", "email", "emergency contact"), rows,
                widths=[110, 240, 280, 260])


@safe("Search my students")
def stf_12_search_my_students(ctx: StaffContext):
    """Keyword search across students in my modules."""
    q = simpledialog.askstring("Search", "Keyword:", parent=ctx.parent)
    if not q:
        return
    like = f"%{q}%"
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        return
    placeholders = ",".join("?" * len(mine))
    rows = ctx.db.cur.execute(
        f"""SELECT DISTINCT s.student_id,
                   TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')),
                   s.email_address
            FROM students s JOIN student_modules sm ON sm.student_id = s.student_id
            WHERE sm.module_code IN ({placeholders})
              AND (s.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
                   OR s.email_address LIKE ?)""",
        (*mine, like, like, like, like)).fetchall()
    _show_table(ctx.parent, f"Matches for '{q}'",
                ("student_id", "name", "email"), rows,
                widths=[110, 260, 300])


@safe("Filter by risk")
def stf_13_filter_by_risk(ctx: StaffContext):
    """Show my students filtered by their latest risk level."""
    lvl = _combo_dialog(ctx.parent, "Risk", "Risk level:",
                        ["high", "medium", "low"])
    if not lvl:
        return
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        return
    ph = ",".join("?" * len(mine))
    rows = ctx.db.cur.execute(
        f"""SELECT DISTINCT s.student_id,
                   TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')),
                   r.risk_level, r.risk_score
            FROM student_risk_assessment r
            JOIN students s ON s.student_id = r.student_id
            JOIN student_modules sm ON sm.student_id = s.student_id
            WHERE sm.module_code IN ({ph}) AND r.risk_level=?
            ORDER BY r.risk_score DESC""", (*mine, lvl)).fetchall()
    _show_table(ctx.parent, f"{lvl.title()} risk in my modules",
                ("student", "name", "risk", "score"), rows)


@safe("Groups")
def stf_14_groups(ctx: StaffContext):
    """Manage tutorial / lab groups for a module."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    win = tk.Toplevel(ctx.parent)
    win.title(f"Groups — {mc}")
    win.geometry("640x420")
    tree = ttk.Treeview(win, columns=("id", "name", "members"), show="headings")
    for c, w in zip(("id", "name", "members"), (60, 220, 360)):
        tree.heading(c, text=c)
        tree.column(c, width=w)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh():
        for i in tree.get_children():
            tree.delete(i)
        for gid, name in ctx.db.cur.execute(
                "SELECT id, name FROM abs_tracker_groups WHERE module_code=?", (mc,)):
            cnt = ctx.db.cur.execute(
                "SELECT COUNT(*) FROM abs_tracker_group_members WHERE group_id=?",
                (gid,)).fetchone()[0]
            tree.insert("", "end", values=(gid, name, f"{cnt} members"))

    def add_group():
        name = simpledialog.askstring("Group", "Group name:", parent=win)
        if not name:
            return
        ctx.db.cur.execute(
            "INSERT OR IGNORE INTO abs_tracker_groups (module_code, name) VALUES (?,?)",
            (mc, name))
        ctx.db.conn.commit()
        audit(ctx, "staff.group_add", "abs_tracker_groups", mc, name)
        refresh()

    def add_member():
        sel = tree.selection()
        if not sel:
            return
        gid = tree.item(sel[0])["values"][0]
        sid = simpledialog.askstring("Student", "Student ID:", parent=win)
        if not sid:
            return
        ctx.db.cur.execute(
            "INSERT OR IGNORE INTO abs_tracker_group_members (group_id, student_id) VALUES (?,?)",
            (gid, sid))
        ctx.db.conn.commit()
        refresh()

    bar = tk.Frame(win); bar.pack(fill="x", pady=6)
    tk.Button(bar, text="➕ Group", command=add_group, bg="#16a34a", fg="white",
              relief="flat").pack(side="left", padx=6)
    tk.Button(bar, text="➕ Member", command=add_member, bg="#2563eb", fg="white",
              relief="flat").pack(side="left", padx=6)
    refresh()


@safe("Roster export")
def stf_15_roster_export(ctx: StaffContext):
    """Export a roster to CSV."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    rows = ctx.db.get_course_students(mc)
    path = _export_rows_to_csv(
        rows, ("student_id", "name", "username", "email"), ctx.parent)
    if path:
        audit(ctx, "staff.roster_export", "students", mc, path)
        messagebox.showinfo("Exported", f"{len(rows)} students → {path}",
                            parent=ctx.parent)


# ===========================================================================
# 16–21  Request handling
# ===========================================================================

@safe("Triage queue")
def stf_16_triage_queue(ctx: StaffContext):
    """Show all pending requests across my modules."""
    rows = ctx.db.cur.execute(
        """SELECT r.id, r.student_id, r.module_code, r.date, r.reason,
                  r.submitted_at
           FROM absence_requests r
           JOIN instructor_modules im ON im.module_code = r.module_code
           WHERE r.status='pending' AND im.instructor_id=?
           ORDER BY r.submitted_at""", (ctx.uid,)).fetchall()
    _show_table(ctx.parent, f"Pending triage ({len(rows)})",
                ("id", "student", "module", "date", "reason", "submitted"), rows,
                widths=[60, 120, 110, 100, 320, 160])


@safe("Preview evidence")
def stf_17_preview_evidence(ctx: StaffContext):
    """Show file attachments on a given request."""
    rid = simpledialog.askinteger("Request", "Request id:", parent=ctx.parent)
    if rid is None:
        return
    rows = ctx.db.cur.execute(
        "SELECT file_path, uploaded_at FROM abs_tracker_request_attachments WHERE request_id=?",
        (rid,)).fetchall()
    _show_table(ctx.parent, f"Evidence for request {rid}",
                ("path", "uploaded_at"), rows, widths=[560, 200])


@safe("Staff comment on decision")
def stf_18_decision_comment(ctx: StaffContext):
    """Attach a staff comment to a request and set its decision."""
    rid = simpledialog.askinteger("Request", "Request id:", parent=ctx.parent)
    if rid is None:
        return
    decision = _combo_dialog(ctx.parent, "Decision", "Decision:",
                             ["approved", "rejected"])
    comment = simpledialog.askstring("Comment", "Staff comment:",
                                     parent=ctx.parent)
    if not (decision and comment):
        return
    ctx.db.update_request(rid, decision)
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_request_comments (request_id, author, body)
           VALUES (?, ?, ?)""",
        (rid, ctx.user.get("username"), comment))
    ctx.db.conn.commit()
    audit(ctx, "staff.decision_comment", "absence_requests", rid,
          f"{decision}: {comment[:120]}")
    messagebox.showinfo("Done", f"Request {decision}.", parent=ctx.parent)


@safe("Approve with modification")
def stf_19_approve_with_mod(ctx: StaffContext):
    """Approve a request, overriding the date or status."""
    rid = simpledialog.askinteger("Request", "Request id:", parent=ctx.parent)
    if rid is None:
        return
    req = ctx.db.cur.execute(
        """SELECT student_id, module_code, date, reason
           FROM absence_requests WHERE id=?""", (rid,)).fetchone()
    if not req:
        messagebox.showerror("Missing", "No such request.", parent=ctx.parent)
        return
    sid, mc, orig_date, reason = req
    new_date = simpledialog.askstring("Date", f"Date (was {orig_date}):",
                                      parent=ctx.parent,
                                      initialvalue=orig_date) or orig_date
    new_status = _combo_dialog(ctx.parent, "Status", "Record as:",
                               ["excused", "absent", "late", "present"]) or "excused"
    ctx.db.update_request(rid, "approved")
    ctx.db.record_absence(sid, mc, new_date, new_status,
                          f"[Approved w/ mod] {reason}")
    audit(ctx, "staff.approve_mod", "absence_requests", rid,
          f"{orig_date}→{new_date} {new_status}")
    messagebox.showinfo("Approved",
                        f"Approved; recorded as {new_status} on {new_date}.",
                        parent=ctx.parent)


@safe("SLA dashboard")
def stf_20_sla_dashboard(ctx: StaffContext):
    """Show pending requests grouped by age (SLA buckets)."""
    rows = ctx.db.cur.execute(
        """SELECT r.id, r.student_id, r.module_code, r.submitted_at,
                  CAST((julianday('now') - julianday(r.submitted_at)) AS INT)
           FROM absence_requests r
           JOIN instructor_modules im ON im.module_code = r.module_code
           WHERE r.status='pending' AND im.instructor_id=?
           ORDER BY 5 DESC""", (ctx.uid,)).fetchall()
    enriched = [(r[0], r[1], r[2], r[3], r[4],
                 "BREACH" if r[4] >= 3 else "WARN" if r[4] >= 2 else "OK")
                for r in rows]
    _show_table(ctx.parent, "Request SLA (target 3 days)",
                ("id", "student", "module", "submitted", "age", "status"), enriched)


@safe("Route to dept head")
def stf_21_route_to_dept(ctx: StaffContext):
    """Route a difficult request to a department head."""
    rid = simpledialog.askinteger("Request", "Request id:", parent=ctx.parent)
    admins = ctx.db.get_users("admin")
    if not admins:
        messagebox.showinfo("No admin", "No admin user to route to.",
                            parent=ctx.parent)
        return
    m = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in admins}
    pick = _combo_dialog(ctx.parent, "Route to", "Route to:", list(m.keys()))
    reason = simpledialog.askstring("Reason", "Why escalate?", parent=ctx.parent)
    if not (rid and pick and reason):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_request_route
           (request_id, routed_to, reason) VALUES (?,?,?)""",
        (rid, m[pick], reason))
    ctx.db.conn.commit()
    audit(ctx, "staff.route", "absence_requests", rid, f"→{m[pick]}: {reason[:80]}")
    messagebox.showinfo("Routed", f"Routed to {pick}.", parent=ctx.parent)


# ===========================================================================
# 22–28  Analytics & insights
# ===========================================================================

@safe("Heatmap")
def stf_22_my_heatmap(ctx: StaffContext):
    """My-module absences by day × week."""
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        return
    ph = ",".join("?" * len(mine))
    rows = ctx.db.cur.execute(
        f"""SELECT strftime('%Y-%W', date) AS week,
                   CASE strftime('%w', date) WHEN '1' THEN 'Mon'
                        WHEN '2' THEN 'Tue' WHEN '3' THEN 'Wed'
                        WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri' END AS dow,
                   SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) AS absences
            FROM attendance WHERE module_code IN ({ph})
            GROUP BY week, dow ORDER BY week DESC""", mine).fetchall()
    _show_table(ctx.parent, "My modules — heatmap",
                ("week", "day", "absences"), rows)


@safe("Drop-off")
def stf_23_dropoff(ctx: StaffContext):
    """Students whose attendance dropped >20% in the last 4 weeks."""
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        return
    ph = ",".join("?" * len(mine))
    now_cut = (date.today() - timedelta(days=28)).isoformat()
    rows = ctx.db.cur.execute(
        f"""SELECT student_id,
                   SUM(CASE WHEN status='present' AND date >= ? THEN 1 ELSE 0 END)*1.0 /
                      NULLIF(SUM(CASE WHEN date >= ? THEN 1 ELSE 0 END),0) * 100 AS recent,
                   SUM(CASE WHEN status='present' AND date < ?  THEN 1 ELSE 0 END)*1.0 /
                      NULLIF(SUM(CASE WHEN date < ?  THEN 1 ELSE 0 END),0) * 100 AS prior
            FROM attendance WHERE module_code IN ({ph})
            GROUP BY student_id HAVING prior - recent > 20
            ORDER BY (prior - recent) DESC""",
        (now_cut, now_cut, now_cut, now_cut, *mine)).fetchall()
    _show_table(ctx.parent, "Drop-off (>20%)",
                ("student", "recent %", "prior %"),
                [(s, f"{(r or 0):.1f}", f"{(p or 0):.1f}") for s, r, p in rows])


@safe("Compare my modules")
def stf_24_compare_my_modules(ctx: StaffContext):
    """Attendance % per module of mine."""
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        return
    ph = ",".join("?" * len(mine))
    rows = ctx.db.cur.execute(
        f"""SELECT module_code,
                   SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100,
                   COUNT(*)
            FROM attendance WHERE module_code IN ({ph})
            GROUP BY module_code ORDER BY 2 DESC""", mine).fetchall()
    _show_table(ctx.parent, "My modules compared",
                ("module", "%", "sessions"),
                [(m, f"{(p or 0):.1f}", n) for m, p, n in rows])


@safe("Historical cohort")
def stf_25_historical_cohort(ctx: StaffContext):
    """Compare this term's module attendance to last term."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    sems = ctx.db.cur.execute(
        "SELECT name, start_date, end_date FROM semesters ORDER BY start_date DESC LIMIT 2"
    ).fetchall()
    out = []
    for name, s, e in sems:
        r = ctx.db.cur.execute(
            """SELECT SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100
               FROM attendance WHERE module_code=? AND date BETWEEN ? AND ?""",
            (mc, s, e)).fetchone()
        out.append((name, s, e, f"{(r[0] or 0):.1f}"))
    _show_table(ctx.parent, f"{mc} — term compare",
                ("semester", "start", "end", "%"), out)


@safe("Module report")
def stf_26_module_report(ctx: StaffContext):
    """Export a full attendance dump for a module to CSV."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    rows = ctx.db.get_absences(course_id=mc)
    path = _export_rows_to_csv(
        rows, ("id", "student", "module_code", "module_name",
               "date", "status", "reason"), ctx.parent)
    if path:
        audit(ctx, "staff.module_report", "attendance", mc, path)
        messagebox.showinfo("Saved", f"Exported {len(rows)} rows → {path}",
                            parent=ctx.parent)


@safe("Student profile")
def stf_27_student_profile(ctx: StaffContext):
    """A single student's attendance + requests + risk."""
    sid = simpledialog.askstring("Student ID", "Student ID:", parent=ctx.parent)
    if not sid:
        return
    win = tk.Toplevel(ctx.parent)
    win.title(f"Profile — {sid}")
    win.geometry("920x620")
    nb = ttk.Notebook(win); nb.pack(fill="both", expand=True)
    for label, rows, cols in [
        ("Attendance",
         ctx.db.cur.execute(
            "SELECT date, module_code, status, COALESCE(reason,'') FROM attendance "
            "WHERE student_id=? ORDER BY date DESC", (sid,)).fetchall(),
         ("date", "module", "status", "reason")),
        ("Requests",
         ctx.db.cur.execute(
            "SELECT id, date, module_code, status, submitted_at FROM absence_requests "
            "WHERE student_id=? ORDER BY submitted_at DESC", (sid,)).fetchall(),
         ("id", "date", "module", "status", "submitted")),
        ("Risk",
         ctx.db.cur.execute(
            "SELECT assessment_date, risk_level, risk_score FROM student_risk_assessment "
            "WHERE student_id=? ORDER BY assessment_date DESC", (sid,)).fetchall(),
         ("date", "level", "score")),
    ]:
        tab = ttk.Frame(nb); nb.add(tab, text=label)
        tree = ttk.Treeview(tab, columns=cols, show="headings")
        for c in cols: tree.heading(c, text=c); tree.column(c, width=180)
        tree.pack(fill="both", expand=True)
        for r in rows: tree.insert("", "end", values=r)


@safe("Correlation")
def stf_28_correlation(ctx: StaffContext):
    """Attendance vs grade for my modules' students."""
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS student_grades
        (id INTEGER PRIMARY KEY, student_id TEXT, module_code TEXT, grade TEXT)""")
    ph = ",".join("?" * len(mine))
    rows = ctx.db.cur.execute(
        f"""SELECT a.student_id, a.module_code,
                   SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100,
                   COALESCE((SELECT grade FROM student_grades g
                             WHERE g.student_id=a.student_id AND g.module_code=a.module_code
                             ORDER BY id DESC LIMIT 1),'')
            FROM attendance a WHERE a.module_code IN ({ph})
            GROUP BY a.student_id, a.module_code""", mine).fetchall()
    _show_table(ctx.parent, "Attendance vs grade",
                ("student", "module", "%", "grade"),
                [(s, m, f"{(p or 0):.1f}", g) for s, m, p, g in rows])


# ===========================================================================
# 29–34  Communication
# ===========================================================================

@safe("Email student")
def stf_29_email_student(ctx: StaffContext):
    """Queue an email to a student."""
    sid = simpledialog.askstring("Student ID", "Student ID:", parent=ctx.parent)
    subject = simpledialog.askstring("Subject", "Subject:", parent=ctx.parent)
    body = simpledialog.askstring("Body", "Body:", parent=ctx.parent)
    if not (sid and subject and body):
        return
    ctx.db.cur.execute(
        """INSERT INTO emails (recipient, subject, body, sent_at, status)
           SELECT email_address, ?, ?, CURRENT_TIMESTAMP, 'queued'
           FROM students WHERE student_id=?""",
        (subject, body, sid))
    ctx.db.conn.commit()
    audit(ctx, "staff.email", "emails", sid, subject[:80])
    messagebox.showinfo("Queued", "Email queued.", parent=ctx.parent)


@safe("Email at-risk list")
def stf_30_email_at_risk(ctx: StaffContext):
    """Send one email summarising the at-risk list to pastoral address."""
    to = simpledialog.askstring("Recipient", "Pastoral email:",
                                parent=ctx.parent) or "pastoral@university.edu"
    threshold = simpledialog.askfloat("Threshold", "Below %:",
                                      parent=ctx.parent, initialvalue=75) or 75
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        return
    ph = ",".join("?" * len(mine))
    rows = ctx.db.cur.execute(
        f"""SELECT student_id,
                   SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100
            FROM attendance WHERE module_code IN ({ph})
            GROUP BY student_id HAVING 2 < ?""",
        (*mine, threshold)).fetchall()
    body = f"At-risk students (<{threshold:.0f}%):\n" + \
           "\n".join(f"  {sid}: {p or 0:.1f}%" for sid, p in rows)
    ctx.db.cur.execute(
        """INSERT INTO emails (recipient, subject, body, sent_at, status)
           VALUES (?, 'At-risk attendance', ?, CURRENT_TIMESTAMP, 'queued')""",
        (to, body))
    ctx.db.conn.commit()
    audit(ctx, "staff.email_at_risk", "emails", to, f"n={len(rows)}")
    messagebox.showinfo("Queued", f"Emailed summary to {to}.", parent=ctx.parent)


@safe("Announcement")
def stf_31_announcement(ctx: StaffContext):
    """Create an announcement row for a module."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    msg = simpledialog.askstring("Announcement", "Message:", parent=ctx.parent)
    if not msg:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS announcements
        (id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT, content TEXT,
         author_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    ctx.db.cur.execute(
        "INSERT INTO announcements (module_code, content, author_id) VALUES (?,?,?)",
        (mc, msg, ctx.uid))
    ctx.db.conn.commit()
    audit(ctx, "staff.announce", "announcements", mc, msg[:80])
    messagebox.showinfo("Posted", "Announcement posted.", parent=ctx.parent)


@safe("Catch-up message")
def stf_32_catchup_message(ctx: StaffContext):
    """Bulk-message absent students with catch-up links."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    d = simpledialog.askstring("Date", "Session date:", parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    msg = simpledialog.askstring("Message", "Catch-up message:", parent=ctx.parent)
    if not (d and msg):
        return
    absent = ctx.db.cur.execute(
        """SELECT a.student_id, s.email_address FROM attendance a
           JOIN students s ON s.student_id = a.student_id
           WHERE a.module_code=? AND a.date=? AND a.status IN ('absent','late')""",
        (mc, d)).fetchall()
    for sid, email in absent:
        ctx.db.cur.execute(
            """INSERT INTO emails (recipient, subject, body, sent_at, status)
               VALUES (?, 'Catch up', ?, CURRENT_TIMESTAMP, 'queued')""",
            (email or sid, msg))
    ctx.db.conn.commit()
    audit(ctx, "staff.catchup", "emails", mc, f"{d} n={len(absent)}")
    messagebox.showinfo("Sent", f"Queued {len(absent)} email(s).",
                        parent=ctx.parent)


@safe("Parent outreach")
def stf_33_parent_outreach(ctx: StaffContext):
    """Notify parents of below-threshold students in my modules."""
    threshold = simpledialog.askfloat("Threshold", "Below %:",
                                      parent=ctx.parent, initialvalue=70) or 70
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        return
    ph = ",".join("?" * len(mine))
    low = ctx.db.cur.execute(
        f"""SELECT student_id,
                   SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100
            FROM attendance WHERE module_code IN ({ph})
            GROUP BY student_id HAVING 2 < ?""",
        (*mine, threshold)).fetchall()
    n = 0
    for sid, pct in low:
        parents = ctx.db.cur.execute(
            "SELECT parent_id FROM parent_student_links WHERE student_id=?",
            (sid,)).fetchall()
        for (pid,) in parents:
            ctx.db.cur.execute(
                """INSERT INTO parent_notifications
                   (parent_id, student_id, notification_type, notification_content,
                    created_date, read_status) VALUES (?,?,?,?,?,0)""",
                (str(pid), sid, "attendance_alert",
                 f"{sid} attendance {pct:.1f}% (below {threshold:.0f}%)",
                 datetime.now().isoformat(timespec="seconds")))
            n += 1
    ctx.db.conn.commit()
    audit(ctx, "staff.parent_outreach", "parent_notifications", "",
          f"n={n} threshold={threshold}")
    messagebox.showinfo("Sent", f"Notified {n} parent(s).", parent=ctx.parent)


@safe("Office hours")
def stf_34_office_hours(ctx: StaffContext):
    """Publish my office-hours slots."""
    slot = simpledialog.askstring("Slot",
                                  "Slot (e.g. 'Wed 14:00-15:00'):",
                                  parent=ctx.parent)
    if not slot:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS office_hours
        (id INTEGER PRIMARY KEY AUTOINCREMENT, staff_id INTEGER, slot TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    ctx.db.cur.execute(
        "INSERT INTO office_hours (staff_id, slot) VALUES (?,?)",
        (ctx.uid, slot))
    ctx.db.conn.commit()
    audit(ctx, "staff.office_hours", "office_hours", ctx.uid, slot)
    messagebox.showinfo("Published", f"Office hours: {slot}",
                        parent=ctx.parent)


# ===========================================================================
# 35–39  Pastoral / early warning
# ===========================================================================

@safe("Flag pastoral")
def stf_35_flag_pastoral(ctx: StaffContext):
    """Raise an early-warning flag for a student."""
    sid = simpledialog.askstring("Student", "Student ID:", parent=ctx.parent)
    note = simpledialog.askstring("Concern", "Concern:", parent=ctx.parent)
    if not (sid and note):
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS early_warning_notifications
        (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, author_id INTEGER,
         content TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    ctx.db.cur.execute(
        """INSERT INTO early_warning_notifications
           (student_id, author_id, content) VALUES (?,?,?)""",
        (sid, ctx.uid, note))
    ctx.db.conn.commit()
    audit(ctx, "staff.ew_flag", "early_warning_notifications", sid, note[:80])
    messagebox.showinfo("Flagged", "Pastoral team notified.", parent=ctx.parent)


@safe("Check-in log")
def stf_36_checkin_log(ctx: StaffContext):
    """Log a 1:1 check-in conversation."""
    sid = simpledialog.askstring("Student", "Student ID:", parent=ctx.parent)
    outcome = simpledialog.askstring("Notes", "Outcome / notes:", parent=ctx.parent)
    if not (sid and outcome):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_intervention_log
           (staff_id, student_id, action, outcome) VALUES (?,?,?,?)""",
        (ctx.uid, sid, "check-in", outcome))
    ctx.db.conn.commit()
    audit(ctx, "staff.checkin", "abs_tracker_intervention_log", sid, outcome[:80])
    messagebox.showinfo("Logged", "Check-in saved.", parent=ctx.parent)


@safe("Escalate safeguarding")
def stf_37_escalate_safeguarding(ctx: StaffContext):
    """Create a safeguarding incident row."""
    sid = simpledialog.askstring("Student", "Student ID:", parent=ctx.parent)
    desc = simpledialog.askstring("Details", "Details:", parent=ctx.parent)
    if not (sid and desc):
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS incidents
        (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, category TEXT,
         details TEXT, raised_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    ctx.db.cur.execute(
        """INSERT INTO incidents (student_id, category, details, raised_by)
           VALUES (?, 'safeguarding', ?, ?)""", (sid, desc, ctx.uid))
    ctx.db.conn.commit()
    audit(ctx, "staff.safeguard", "incidents", sid, "(redacted)")
    messagebox.showinfo("Escalated",
                        "Safeguarding team has been notified.",
                        parent=ctx.parent)


@safe("Meeting scheduler")
def stf_38_meeting_scheduler(ctx: StaffContext):
    """Schedule a meeting with a student."""
    sid = simpledialog.askstring("Student", "Student ID:", parent=ctx.parent)
    when = simpledialog.askstring("When", "Meeting time (YYYY-MM-DD HH:MM):",
                                  parent=ctx.parent)
    if not (sid and when):
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS parent_conferences
        (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, staff_id INTEGER,
         scheduled_for TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    ctx.db.cur.execute(
        """INSERT INTO parent_conferences (student_id, staff_id, scheduled_for)
           VALUES (?,?,?)""", (sid, ctx.uid, when))
    ctx.db.conn.commit()
    audit(ctx, "staff.meeting", "parent_conferences", sid, when)
    messagebox.showinfo("Scheduled", f"Meeting {when} with {sid}.",
                        parent=ctx.parent)


@safe("Intervention tracker")
def stf_39_intervention_tracker(ctx: StaffContext):
    """Browse all interventions I've logged."""
    rows = ctx.db.cur.execute(
        """SELECT created_at, student_id, action, outcome
           FROM abs_tracker_intervention_log
           WHERE staff_id=? ORDER BY created_at DESC""", (ctx.uid,)).fetchall()
    _show_table(ctx.parent, "My interventions",
                ("when", "student", "action", "outcome"), rows,
                widths=[160, 120, 140, 420])


# ===========================================================================
# 40–42  Assessment integration
# ===========================================================================

@safe("Assignment link")
def stf_40_assignment_link(ctx: StaffContext):
    """Flag students missing class ahead of assignment deadlines."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    ctx.db.cur.execute("""CREATE TABLE IF NOT EXISTS assignments
        (id INTEGER PRIMARY KEY, module_code TEXT, title TEXT, due_date TEXT)""")
    rows = ctx.db.cur.execute(
        """SELECT a.student_id, ass.title, ass.due_date,
                  SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END)
           FROM attendance a
           JOIN assignments ass ON ass.module_code = a.module_code
             AND ass.due_date >= date('now')
           WHERE a.module_code=? AND a.date BETWEEN date(ass.due_date,'-14 days')
                                               AND ass.due_date
           GROUP BY a.student_id, ass.id HAVING 4 >= 2
           ORDER BY ass.due_date""", (mc,)).fetchall()
    _show_table(ctx.parent, "Pre-deadline absence risk",
                ("student", "assignment", "due", "absences in 14d"), rows)


@safe("Exam eligibility")
def stf_41_exam_eligibility(ctx: StaffContext):
    """List students below policy threshold for upcoming exams."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    thr_row = ctx.db.cur.execute(
        "SELECT min_percent FROM abs_tracker_module_policy WHERE module_code=?",
        (mc,)).fetchone()
    thr = thr_row[0] if thr_row else float(
        _get_setting(ctx.db, "default_min_pct", 80) or 80)
    rows = ctx.db.cur.execute(
        """SELECT a.student_id,
                  SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)*1.0/COUNT(*)*100
           FROM attendance a WHERE a.module_code=?
           GROUP BY a.student_id HAVING 2 < ?""", (mc, thr)).fetchall()
    _show_table(ctx.parent, f"Ineligible (<{thr:.0f}%) — {mc}",
                ("student", "%"), [(s, f"{(p or 0):.1f}") for s, p in rows])


@safe("Lab safety")
def stf_42_lab_safety(ctx: StaffContext):
    """Show students missing mandatory safety briefings for my labs."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    rows = ctx.db.cur.execute(
        """SELECT sm.student_id
           FROM student_modules sm
           WHERE sm.module_code=?
             AND sm.student_id NOT IN (
                 SELECT DISTINCT student_id FROM attendance
                 WHERE module_code=? AND COALESCE(reason,'') LIKE '%safety%'
                   AND status='present')""", (mc, mc)).fetchall()
    _show_table(ctx.parent, f"{mc} — missed safety briefing",
                ("student",), rows, widths=[180])


# ===========================================================================
# 43–45  Collaboration
# ===========================================================================

@safe("Co-teacher")
def stf_43_co_teacher(ctx: StaffContext):
    """Grant roll-taking rights to a co-instructor on a module."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    staff = ctx.db.get_users("instructor") + ctx.db.get_users("staff")
    m = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in staff if r[0] != ctx.uid}
    pick = _combo_dialog(ctx.parent, "Co-teacher", "Grant to:", list(m.keys()))
    if not pick:
        return
    ctx.db.cur.execute(
        "INSERT OR IGNORE INTO abs_tracker_co_teachers (module_code, user_id) VALUES (?,?)",
        (mc, m[pick]))
    # Mirror into instructor_modules so the rest of the tracker respects it
    ctx.db.cur.execute(
        "INSERT OR IGNORE INTO instructor_modules (instructor_id, module_code) VALUES (?,?)",
        (m[pick], mc))
    ctx.db.conn.commit()
    audit(ctx, "staff.co_teacher", "abs_tracker_co_teachers", mc, str(m[pick]))
    messagebox.showinfo("Granted", f"{pick} can now take roll on {mc}.",
                        parent=ctx.parent)


@safe("TA handoff")
def stf_44_ta_handoff(ctx: StaffContext):
    """Leave a handoff note for a teaching assistant."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    tas = ctx.db.get_users("staff") + ctx.db.get_users("instructor")
    m = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in tas if r[0] != ctx.uid}
    pick = _combo_dialog(ctx.parent, "TA", "TA:", list(m.keys()))
    note = simpledialog.askstring("Handoff", "Note to TA:", parent=ctx.parent)
    if not (pick and note):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_ta_handoff
           (staff_id, ta_id, module_code, note) VALUES (?,?,?,?)""",
        (ctx.uid, m[pick], mc, note))
    ctx.db.conn.commit()
    audit(ctx, "staff.ta_handoff", "abs_tracker_ta_handoff", mc, note[:80])
    messagebox.showinfo("Saved", "TA handoff saved.", parent=ctx.parent)


@safe("Peer observation")
def stf_45_peer_observation(ctx: StaffContext):
    """Log a peer observation of a colleague's session."""
    staff = ctx.db.get_users("instructor") + ctx.db.get_users("staff")
    m = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in staff if r[0] != ctx.uid}
    pick = _combo_dialog(ctx.parent, "Observed", "Who did you observe?",
                         list(m.keys()))
    mc = simpledialog.askstring("Module", "Module code:", parent=ctx.parent)
    d = simpledialog.askstring("Date", "Date (YYYY-MM-DD):",
                               parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    notes = simpledialog.askstring("Notes", "Notes:", parent=ctx.parent)
    if not (pick and mc and d and notes):
        return
    ctx.db.cur.execute(
        """INSERT INTO abs_tracker_peer_observations
           (observer_id, subject_id, module_code, date, notes) VALUES (?,?,?,?,?)""",
        (ctx.uid, m[pick], mc, d, notes))
    ctx.db.conn.commit()
    audit(ctx, "staff.peer_obs", "abs_tracker_peer_observations", m[pick],
          f"{mc} {d}")
    messagebox.showinfo("Saved", "Peer observation recorded.",
                        parent=ctx.parent)


# ===========================================================================
# 46–48  Admin/config
# ===========================================================================

@safe("Module policy quick-edit")
def stf_46_policy_quick_edit(ctx: StaffContext):
    """Quickly edit the per-module policy for one of mine."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    pct = simpledialog.askfloat("Min %",
                                "Minimum attendance % (0-100):",
                                parent=ctx.parent, initialvalue=80,
                                minvalue=0, maxvalue=100)
    grace = simpledialog.askinteger("Grace",
                                    "Grace minutes for late→present:",
                                    parent=ctx.parent, initialvalue=5,
                                    minvalue=0, maxvalue=60)
    if pct is None:
        return
    ctx.db.cur.execute(
        """INSERT OR REPLACE INTO abs_tracker_module_policy
           (module_code, min_percent, late_as_absent, grace_minutes, notes)
           VALUES (?, ?, 0, ?, ?)""",
        (mc, pct, grace or 0, f"edited by {ctx.user.get('username')}"))
    ctx.db.conn.commit()
    audit(ctx, "staff.policy", "abs_tracker_module_policy", mc,
          f"pct={pct} grace={grace}")
    messagebox.showinfo("Saved", f"{mc}: ≥{pct}%, grace={grace}m",
                        parent=ctx.parent)


@safe("Excuse range")
def stf_47_excuse_range(ctx: StaffContext):
    """Mark a date range 'excused' for the whole module (e.g. field trip)."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    start = simpledialog.askstring("From", "Start (YYYY-MM-DD):",
                                   parent=ctx.parent)
    end = simpledialog.askstring("To", "End (YYYY-MM-DD):", parent=ctx.parent)
    reason = simpledialog.askstring("Reason", "Reason:", parent=ctx.parent) or "field trip"
    if not (start and end):
        return
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    roster = ctx.db.get_course_students(mc)
    n = 0
    d = d0
    while d <= d1:
        for sid, *_ in roster:
            ctx.db.record_absence(sid, mc, d.isoformat(), "excused", reason)
            n += 1
        d += timedelta(days=1)
    audit(ctx, "staff.excuse_range", "attendance", mc,
          f"{start}..{end} n={n}")
    messagebox.showinfo("Excused",
                        f"{n} rows written {start} → {end}.",
                        parent=ctx.parent)


@safe("Seating chart")
def stf_48_seating_chart(ctx: StaffContext):
    """Save a seating plan JSON for a session."""
    mc = _pick_my_module(ctx)
    if not mc:
        return
    d = simpledialog.askstring("Date", "Date (YYYY-MM-DD):", parent=ctx.parent,
                               initialvalue=date.today().isoformat())
    path = filedialog.askopenfilename(parent=ctx.parent,
                                      filetypes=[("JSON", "*.json"), ("All", "*.*")])
    if not (d and path):
        return
    try:
        layout = Path(path).read_text() if hasattr(Path(path), "read_text") \
                 else open(path).read()
    except Exception:
        with open(path) as fh:
            layout = fh.read()
    ctx.db.cur.execute(
        """INSERT OR REPLACE INTO abs_tracker_seating
           (module_code, date, layout_json) VALUES (?,?,?)""",
        (mc, d, layout))
    ctx.db.conn.commit()
    audit(ctx, "staff.seating", "abs_tracker_seating", mc, f"{d} {path}")
    messagebox.showinfo("Saved", "Seating plan saved.", parent=ctx.parent)


# ===========================================================================
# 49–50  Personal productivity
# ===========================================================================

@safe("My KPIs")
def stf_49_my_kpis(ctx: StaffContext):
    """Personal KPIs: sessions held, roll completion %, request response time."""
    mine = [r[0] for r in _my_modules(ctx)]
    if not mine:
        messagebox.showinfo("No modules", "No data.", parent=ctx.parent)
        return
    ph = ",".join("?" * len(mine))
    sessions = ctx.db.cur.execute(
        f"SELECT COUNT(DISTINCT date) FROM attendance WHERE module_code IN ({ph})",
        mine).fetchone()[0]
    rolls = ctx.db.cur.execute(
        f"SELECT COUNT(*) FROM attendance WHERE module_code IN ({ph})",
        mine).fetchone()[0]
    pending = ctx.db.cur.execute(
        f"""SELECT COUNT(*) FROM absence_requests WHERE module_code IN ({ph}) AND status='pending'""",
        mine).fetchone()[0]
    decided = ctx.db.cur.execute(
        f"""SELECT AVG(julianday('now') - julianday(submitted_at))
            FROM absence_requests WHERE module_code IN ({ph}) AND status<>'pending'""",
        mine).fetchone()[0] or 0
    _show_table(ctx.parent, "My KPIs",
                ("metric", "value"),
                [("sessions held", sessions),
                 ("attendance rows", rolls),
                 ("pending requests", pending),
                 ("avg decision time (days)", f"{decided:.1f}")],
                widths=[260, 200])


@safe("My to-do list")
def stf_50_todo(ctx: StaffContext):
    """Personal to-do list stored per user."""
    win = tk.Toplevel(ctx.parent)
    win.title("My to-do list")
    win.geometry("640x460")
    lst = ttk.Treeview(win, columns=("id", "task", "done", "when"), show="headings")
    for c, w in zip(("id", "task", "done", "when"), (60, 400, 70, 160)):
        lst.heading(c, text=c); lst.column(c, width=w)
    lst.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh():
        for i in lst.get_children():
            lst.delete(i)
        for row in ctx.db.cur.execute(
                """SELECT id, task, CASE done WHEN 1 THEN '✓' ELSE '' END,
                          COALESCE(done_at, created_at)
                   FROM abs_tracker_staff_tasks
                   WHERE staff_id=? ORDER BY done, created_at DESC""",
                (ctx.uid,)):
            lst.insert("", "end", values=row)

    def add():
        t = simpledialog.askstring("Task", "Task:", parent=win)
        if not t:
            return
        ctx.db.cur.execute(
            "INSERT INTO abs_tracker_staff_tasks (staff_id, task) VALUES (?,?)",
            (ctx.uid, t))
        ctx.db.conn.commit()
        refresh()

    def toggle():
        sel = lst.selection()
        if not sel:
            return
        tid = lst.item(sel[0])["values"][0]
        ctx.db.cur.execute(
            """UPDATE abs_tracker_staff_tasks
               SET done = 1 - done,
                   done_at = CASE WHEN done = 0 THEN CURRENT_TIMESTAMP ELSE NULL END
               WHERE id=?""", (tid,))
        ctx.db.conn.commit()
        refresh()

    bar = tk.Frame(win); bar.pack(fill="x", pady=6)
    tk.Button(bar, text="➕ Add", command=add, bg="#16a34a", fg="white",
              relief="flat", padx=10).pack(side="left", padx=6)
    tk.Button(bar, text="✓ Toggle", command=toggle, bg="#2563eb", fg="white",
              relief="flat", padx=10).pack(side="left", padx=6)
    refresh()


# ===========================================================================
# 51  Request time off (date-picker)
# ===========================================================================

@safe("Request time off")
def stf_51_request_time_off(ctx: StaffContext):
    """File a staff leave request using dropdown date pickers (writes leave_requests)."""
    ctx.db.cur.execute(
        """INSERT OR IGNORE INTO leave_types
           (leave_type_id, name, requires_approval, is_active)
           VALUES (1,'Annual leave',1,1), (2,'Sick leave',1,1),
                  (3,'Personal',1,1), (4,'Bereavement',1,1),
                  (5,'Training',1,1)""")
    ctx.db.conn.commit()
    types = ctx.db.cur.execute(
        "SELECT leave_type_id, name FROM leave_types WHERE is_active=1 ORDER BY name"
    ).fetchall()
    tmap = {r[1]: r[0] for r in types}
    tpick = _combo_dialog(ctx.parent, "Leave type", "Type:", list(tmap.keys()))
    if not tpick:
        return
    rng = pick_date_range(ctx.parent, "Leave dates")
    if not rng:
        return
    start, end = rng
    reason = simpledialog.askstring("Reason", "Reason:", parent=ctx.parent) or ""
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    total = (d1 - d0).days + 1
    now = datetime.now().isoformat(timespec="seconds")
    ctx.db.cur.execute(
        """INSERT INTO leave_requests
           (user_id, leave_type_id, start_date, end_date, total_days, reason,
            status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (str(ctx.uid), tmap[tpick], start, end, total, reason, now, now))
    ctx.db.conn.commit()
    audit(ctx, "staff.request_time_off", "leave_requests", ctx.uid,
          f"{tpick} {start}..{end} ({total}d)")
    messagebox.showinfo(
        "Submitted",
        f"Leave request ({tpick}, {total} day{'s' if total != 1 else ''}) "
        f"submitted for {start} → {end}.",
        parent=ctx.parent,
    )


# ---------------------------------------------------------------------------
# Registry + tab renderer
# ---------------------------------------------------------------------------
FEATURES: list[tuple[int, str, str, Callable]] = [
    (1,  "Roll-call",      "Today's classes",                stf_01_today_dashboard),
    (2,  "Roll-call",      "Generate sessions",              stf_02_generate_sessions),
    (3,  "Roll-call",      "Session notes",                  stf_03_session_note),
    (4,  "Roll-call",      "Cancel session",                 stf_04_cancel_session),
    (5,  "Roll-call",      "Substitute mode",                stf_05_substitute_mode),
    (6,  "Roll-call",      "All-present (with excepts)",     stf_06_all_present_except),
    (7,  "Roll-call",      "Late log",                       stf_07_late_log),
    (8,  "Roll-call",      "Early-leave log",                stf_08_early_leave),
    (9,  "Roll-call",      "Session QR code",                stf_09_session_qr),
    (10, "Roll-call",      "Correct roll after session",     stf_10_correct_roll),

    (11, "Roster",         "Roster (+ contacts)",            stf_11_roster_with_photos),
    (12, "Roster",         "Search my students",             stf_12_search_my_students),
    (13, "Roster",         "Filter by risk",                 stf_13_filter_by_risk),
    (14, "Roster",         "Groups",                         stf_14_groups),
    (15, "Roster",         "Roster export",                  stf_15_roster_export),

    (16, "Requests",       "Triage queue",                   stf_16_triage_queue),
    (17, "Requests",       "Preview evidence",               stf_17_preview_evidence),
    (18, "Requests",       "Staff comment + decide",         stf_18_decision_comment),
    (19, "Requests",       "Approve with modification",      stf_19_approve_with_mod),
    (20, "Requests",       "SLA dashboard",                  stf_20_sla_dashboard),
    (21, "Requests",       "Route to dept head",             stf_21_route_to_dept),

    (22, "Analytics",      "My heatmap",                     stf_22_my_heatmap),
    (23, "Analytics",      "Drop-off detector",              stf_23_dropoff),
    (24, "Analytics",      "Compare my modules",             stf_24_compare_my_modules),
    (25, "Analytics",      "Historical cohort",              stf_25_historical_cohort),
    (26, "Analytics",      "Module report export",           stf_26_module_report),
    (27, "Analytics",      "Student profile",                stf_27_student_profile),
    (28, "Analytics",      "Attendance vs grade",            stf_28_correlation),

    (29, "Communication",  "Email student",                  stf_29_email_student),
    (30, "Communication",  "Email at-risk list",             stf_30_email_at_risk),
    (31, "Communication",  "Module announcement",            stf_31_announcement),
    (32, "Communication",  "Catch-up message (absent)",      stf_32_catchup_message),
    (33, "Communication",  "Parent outreach",                stf_33_parent_outreach),
    (34, "Communication",  "Publish office hours",           stf_34_office_hours),

    (35, "Pastoral",       "Flag pastoral",                  stf_35_flag_pastoral),
    (36, "Pastoral",       "Check-in log",                   stf_36_checkin_log),
    (37, "Pastoral",       "Escalate safeguarding",          stf_37_escalate_safeguarding),
    (38, "Pastoral",       "Meeting scheduler",              stf_38_meeting_scheduler),
    (39, "Pastoral",       "Intervention tracker",           stf_39_intervention_tracker),

    (40, "Assessment",     "Assignment ↔ absence",           stf_40_assignment_link),
    (41, "Assessment",     "Exam eligibility",               stf_41_exam_eligibility),
    (42, "Assessment",     "Lab safety briefing check",      stf_42_lab_safety),

    (43, "Collaboration",  "Co-teacher",                     stf_43_co_teacher),
    (44, "Collaboration",  "TA handoff note",                stf_44_ta_handoff),
    (45, "Collaboration",  "Peer observation",               stf_45_peer_observation),

    (46, "Config",         "Module policy quick-edit",       stf_46_policy_quick_edit),
    (47, "Config",         "Excuse date range",              stf_47_excuse_range),
    (48, "Config",         "Seating chart",                  stf_48_seating_chart),

    (49, "Productivity",   "My KPIs",                        stf_49_my_kpis),
    (50, "Productivity",   "My to-do list",                  stf_50_todo),

    (51, "Requests",       "Request time off (date picker)", stf_51_request_time_off),
]


# Compatibility: feature 48 uses pathlib.Path
from pathlib import Path  # noqa: E402


def build_staff_tab(notebook: ttk.Notebook, ctx: StaffContext) -> None:
    """Render all 50 staff features into a dedicated tab."""
    ensure_support_tables(ctx.db)
    ensure_staff_tables(ctx.db)

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
                bg="#7c3aed", fg="white", activebackground="#6d28d9",
                relief="flat", cursor="hand2",
                width=32, anchor="w", padx=8, pady=6,
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="w")

    logger.info("staff tools tab built (%d features)", len(FEATURES))
