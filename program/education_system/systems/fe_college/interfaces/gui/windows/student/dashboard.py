"""Learner dashboard — everything that needs the learner's attention.

Written from the learner's point of view rather than the college's: what is
due, how am I doing, and is anything wrong. Attendance is shown against the
college's target because that is the number their bursary and their tutorial
conversations hang on.
"""

from __future__ import annotations

import logging
from datetime import datetime
from tkinter import ttk

from education_system.systems.fe_college.config import ATTENDANCE_TARGET_PCT
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "My dashboard"


def open_window(host) -> None:
    host.clear_content()
    ctl = host.ctl
    parent = host.content_frame

    now = datetime.now()
    w.page_header(
        parent,
        f"Hello, {ctl.identity.display_name}",
        f"{ctl.college_name} · {now.strftime('%A %d %B %Y')}",
        actions=[("↻ Refresh", lambda: open_window(host))],
    )

    if not ctl.student_id:
        w.empty_state(
            parent,
            "Your account is not linked to a learner record, so there is "
            "nothing to show yet.\n\nRecords are matched by student ID or "
            "email — ask college administration to check your account.",
        )
        host.set_status("No learner record linked to this account")
        return

    try:
        stats = ctl.reports.student_stats(ctl.student_id)
    except Exception:
        logger.exception("Could not load the FE College learner dashboard")
        w.empty_state(parent, "Your dashboard is unavailable — see the log.")
        return

    attendance_tone = w.tone_for(stats.attendance.band)
    w.kpi_row(parent, [
        ("My attendance", w.pct(stats.attendance.attendance_pct),
         f"target {ATTENDANCE_TARGET_PCT:.0f}% · {stats.attendance.band}",
         attendance_tone),
        ("Work due", str(stats.assignments_due),
         f"{stats.assignments_overdue} overdue",
         "bad" if stats.assignments_overdue else
         "warn" if stats.assignments_due else "good"),
        ("Grades so far", str(stats.grades_awarded),
         f"{w.pct(stats.pass_rate)} passed" if stats.pass_rate is not None else "none yet",
         "good" if (stats.pass_rate or 0) >= 90 else "plain"),
        ("Credits", f"{stats.credits_achieved}/{stats.credits_required}"
         if stats.credits_required else "—",
         "towards your qualification", "plain"),
        ("Balance", w.money(stats.balance),
         "owed to the college" if stats.balance > 0 else "nothing owed",
         "warn" if stats.balance > 0 else "good"),
    ])

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=1, uniform="d")
    body.columnconfigure(1, weight=1, uniform="d")
    body.rowconfigure(0, weight=1)

    left = ttk.Frame(body)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    _today_panel(left, ctl, now)
    _due_panel(left, ctl, host)

    right = ttk.Frame(body)
    right.grid(row=0, column=1, sticky="nsew")
    _targets_panel(right, ctl)
    _actions_panel(right, host)

    if stats.attendance.attendance_pct is not None and \
            stats.attendance.attendance_pct < ATTENDANCE_TARGET_PCT:
        ttk.Label(
            parent,
            text=(
                f"Your attendance is {w.pct(stats.attendance.attendance_pct)}, "
                f"below the {ATTENDANCE_TARGET_PCT:.0f}% the college expects. "
                "Talk to your personal tutor if something is getting in the way."
            ),
            foreground=w.TONE["warn"], wraplength=1000, justify="left",
        ).pack(anchor="w", pady=(10, 0))

    host.set_status(
        f"Attendance {w.pct(stats.attendance.attendance_pct)} · "
        f"{stats.assignments_due} piece(s) of work due"
    )


def _today_panel(parent, ctl, now) -> None:
    panel = ttk.LabelFrame(parent, text=f"Today — {now.strftime('%A')}", padding=8)
    panel.pack(fill="both", expand=True, pady=(0, 10))
    timetable = ctl.timetable.for_student(ctl.student_id)
    today = now.strftime("%A")

    rows = []
    for code, start, end in ctl.timetable.periods():
        for cell in timetable.at(today, code):
            rows.append({
                "time": f"{start}-{end}",
                "course": cell.course_title,
                "room": cell.room_name or "—",
                "teacher": cell.teacher_name or "—",
            })
    if not rows:
        w.empty_state(panel, f"You have no classes on {today}.")
        return

    table = w.DataTable(panel, [
        ("time", "Time", 100),
        ("course", "Class", 230),
        ("room", "Room", 140),
        ("teacher", "Teacher", 150),
    ], height=8)
    table.set_rows(rows)


def _due_panel(parent, ctl, host) -> None:
    panel = ttk.LabelFrame(parent, text="Work due", padding=8)
    panel.pack(fill="both", expand=True)

    submissions = {
        s.assignment_id: s for s in ctl.assessment.submissions_for(ctl.student_id)
    }
    assignments = [
        a for a in ctl.assessment.list_assignments(student_id=ctl.student_id)
        if a.status == "issued"
    ]
    outstanding = [
        a for a in assignments
        if a.assignment_id not in submissions
        or submissions[a.assignment_id].status in ("not_submitted", "referred")
    ]
    if not outstanding:
        w.empty_state(panel, "Nothing outstanding — you are up to date.")
        return

    table = w.DataTable(panel, [
        ("title", "Assignment", 250),
        ("course", "Course", 95),
        ("due", "Due", 100),
        ("days", "Days left", 80, "e"),
        ("status", "Status", 110),
    ], height=8)
    table.set_rows([
        {
            "title": a.title,
            "course": a.course_id,
            "due": w.when(a.due_date),
            "days": a.days_remaining() if a.days_remaining() is not None else "—",
            "status": (
                "referred — resubmit"
                if a.assignment_id in submissions
                and submissions[a.assignment_id].status == "referred"
                else "not handed in"
            ),
            "_tone": "bad" if a.is_overdue() else "warn",
        }
        for a in sorted(outstanding, key=lambda a: (a.due_date is None, a.due_date))
    ])
    ttk.Button(panel, text="Go to my assignments →",
               command=lambda: host.open_screen("assignments")).pack(
        anchor="e", pady=(6, 0))


def _targets_panel(parent, ctl) -> None:
    panel = ttk.LabelFrame(parent, text="My targets", padding=8)
    panel.pack(fill="both", expand=True, pady=(0, 10))
    profile = ctl.students.profile(ctl.student_id)
    targets = [t for t in profile.targets if t.is_open] if profile else []
    if not targets:
        w.empty_state(panel, "No open targets.")
        return

    table = w.DataTable(panel, [
        ("target", "Target", 280),
        ("due", "Due", 100),
        ("status", "Status", 100),
    ], height=8)
    table.set_rows([
        {
            "target": t.description,
            "due": w.when(t.due_date),
            "status": "overdue" if t.is_overdue() else t.status,
            "_tone": "bad" if t.is_overdue() else "plain",
        }
        for t in targets
    ])


def _actions_panel(parent, host) -> None:
    panel = ttk.LabelFrame(parent, text="Go to", padding=8)
    panel.pack(fill="x")
    actions = [
        ("My courses", "courses"),
        ("My timetable", "timetable"),
        ("My attendance", "attendance"),
        ("My assignments", "assignments"),
        ("My results", "results"),
        ("Get support", "support"),
    ]
    for i, (label, screen) in enumerate(actions):
        ttk.Button(panel, text=label,
                   command=lambda s=screen: host.open_screen(s)).grid(
            row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
    panel.columnconfigure(0, weight=1, uniform="qa")
    panel.columnconfigure(1, weight=1, uniform="qa")


__all__ = ["TITLE", "open_window"]
