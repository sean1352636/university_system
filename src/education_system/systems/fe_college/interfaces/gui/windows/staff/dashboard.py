"""Staff dashboard — a lecturer's own teaching at a glance.

Answers the three questions a lecturer opens the system for: what am I
teaching today, what is waiting to be marked, and which of my learners are
slipping.
"""

from __future__ import annotations

import logging
from datetime import datetime
from tkinter import ttk

from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "My teaching"


def open_window(host) -> None:
    host.clear_content()
    ctl = host.ctl
    parent = host.content_frame

    now = datetime.now()
    w.page_header(
        parent,
        f"Good {'morning' if now.hour < 12 else 'afternoon' if now.hour < 18 else 'evening'}, "
        f"{ctl.identity.display_name}",
        f"{ctl.college_name} · {now.strftime('%A %d %B %Y')}",
        actions=[("↻ Refresh", lambda: open_window(host))],
    )

    if not ctl.staff_id:
        _unlinked(parent, host)
        return

    try:
        stats = ctl.reports.staff_stats(ctl.staff_id)
    except Exception:
        logger.exception("Could not load FE College staff dashboard")
        w.empty_state(parent, "Dashboard data is unavailable — see the log.")
        return

    w.kpi_row(parent, [
        ("My learners", str(stats.learners),
         f"across {stats.courses} course(s)", "plain"),
        ("Their attendance", w.pct(stats.attendance.attendance_pct),
         stats.attendance.band, w.tone_for(stats.attendance.band)),
        ("At risk", str(stats.learners_at_risk),
         "below 75% attendance", "bad" if stats.learners_at_risk else "good"),
        ("To mark", str(stats.marking_outstanding),
         f"{stats.assignments_open} assignment(s) open",
         "warn" if stats.marking_outstanding else "good"),
        ("Sessions/week", str(stats.sessions_per_week),
         f"{stats.groups} class group(s)", "plain"),
    ])

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=1, uniform="d")
    body.columnconfigure(1, weight=1, uniform="d")
    body.rowconfigure(0, weight=1)

    left = ttk.Frame(body)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    _today_panel(left, ctl, now)
    _marking_panel(left, ctl, host)

    right = ttk.Frame(body)
    right.grid(row=0, column=1, sticky="nsew")
    _at_risk_panel(right, ctl)
    _actions_panel(right, host)

    host.set_status(
        f"{stats.learners} learner(s) · {stats.marking_outstanding} to mark"
    )


def _unlinked(parent, host) -> None:
    w.empty_state(
        parent,
        "Your account is not linked to a staff record, so there is nothing to "
        "show here yet.\n\nRecords are matched by email address. Ask an "
        "administrator to check the Users screen, or set your account's email "
        "to match your staff record.",
    )
    host.set_status("No staff record linked to this account")


def _today_panel(parent, ctl, now) -> None:
    panel = ttk.LabelFrame(parent, text=f"Today — {now.strftime('%A')}", padding=8)
    panel.pack(fill="both", expand=True, pady=(0, 10))
    timetable = ctl.timetable.for_staff(ctl.staff_id)
    today = now.strftime("%A")

    entries = []
    for code, start, end in ctl.timetable.periods():
        for cell in timetable.at(today, code):
            entries.append((f"{start}-{end}", cell))

    if not entries:
        w.empty_state(panel, f"Nothing timetabled for you on {today}.")
        return

    table = w.DataTable(panel, [
        ("time", "Time", 100),
        ("course", "Course", 220),
        ("group", "Group", 110),
        ("room", "Room", 150),
    ], height=8)
    table.set_rows([
        {
            "time": time_label,
            "course": cell.course_title,
            "group": cell.session.group_id or "—",
            "room": cell.room_name or "—",
        }
        for time_label, cell in entries
    ])


def _marking_panel(parent, ctl, host) -> None:
    panel = ttk.LabelFrame(parent, text="Waiting to be marked", padding=8)
    panel.pack(fill="both", expand=True)
    queue = ctl.assessment.marking_queue(ctl.staff_id)
    if not queue:
        w.empty_state(panel, "Nothing is waiting — the queue is clear.")
        return

    table = w.DataTable(panel, [
        ("student", "Learner", 170),
        ("assignment", "Assignment", 230),
        ("submitted", "Submitted", 100),
        ("late", "Late", 55),
    ], height=8)
    table.set_rows([
        {
            "student": row.student.full_name,
            "assignment": row.assignment.title,
            "submitted": w.when(row.submission.submitted_at),
            "late": w.yes_no(row.is_late),
            "_tone": "warn" if row.is_late else "plain",
        }
        for row in queue[:20]
    ])
    ttk.Button(panel, text=f"Mark all {len(queue)} →",
               command=lambda: host.open_screen("marking")).pack(anchor="e", pady=(6, 0))


def _at_risk_panel(parent, ctl) -> None:
    panel = ttk.LabelFrame(parent, text="Learners at risk", padding=8)
    panel.pack(fill="both", expand=True, pady=(0, 10))

    seen: dict[str, tuple] = {}
    for course in ctl.my_courses():
        for learner, summary in ctl.attendance.at_risk(course_id=course.course_id):
            seen[learner.student_id] = (learner, summary, course.course_id)

    if not seen:
        w.empty_state(panel, "No learner of yours is below 75% attendance.")
        return

    table = w.DataTable(panel, [
        ("student", "Learner", 170),
        ("course", "Course", 100),
        ("attendance", "Attendance", 95, "e"),
        ("unauth", "Unauth.", 70, "e"),
    ], height=10)
    table.set_rows([
        {
            "student": learner.full_name,
            "course": course_id,
            "attendance": w.pct(summary.attendance_pct),
            "unauth": summary.unauthorised,
            "_tone": w.tone_for(summary.band),
        }
        for learner, summary, course_id in sorted(
            seen.values(), key=lambda r: r[1].attendance_pct or 0
        )
    ])


def _actions_panel(parent, host) -> None:
    panel = ttk.LabelFrame(parent, text="Go to", padding=8)
    panel.pack(fill="x")
    actions = [
        ("Take a register", "registers"),
        ("Marking", "marking"),
        ("Assignments", "assignments"),
        ("My timetable", "timetable"),
        ("Lesson plans", "lesson_plans"),
        ("Learner records", "student_records"),
    ]
    for i, (label, screen) in enumerate(actions):
        ttk.Button(panel, text=label,
                   command=lambda s=screen: host.open_screen(s)).grid(
            row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
    panel.columnconfigure(0, weight=1, uniform="qa")
    panel.columnconfigure(1, weight=1, uniform="qa")


__all__ = ["TITLE", "open_window"]
