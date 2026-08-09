"""Admin dashboard — the whole college on one screen.

Ordered by what a principal acts on: the headline numbers, then the two lists
that generate work (courses recruiting badly, learners whose attendance has
slipped), then everything outstanding.
"""

from __future__ import annotations

import logging
from datetime import datetime
from tkinter import ttk

from education_system.systems.fe_college.config import ATTENDANCE_TARGET_PCT
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Dashboard"


def open_window(host) -> None:
    """Render the admin dashboard into ``host``'s content pane."""
    host.clear_content()
    ctl = host.ctl
    parent = host.content_frame

    now = datetime.now()
    greeting = (
        "Good morning" if now.hour < 12
        else "Good afternoon" if now.hour < 18 else "Good evening"
    )
    w.page_header(
        parent,
        f"{greeting}, {ctl.identity.display_name}",
        f"{ctl.college_name} · {now.strftime('%A %d %B %Y · %H:%M')}",
        actions=[("↻ Refresh", lambda: open_window(host))],
    )

    try:
        stats = ctl.reports.college_stats()
    except Exception:
        logger.exception("Could not load FE College dashboard stats")
        w.empty_state(parent, "Dashboard data is unavailable — see the log for details.")
        host.set_status("Dashboard unavailable")
        return

    _kpis(parent, stats)

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)
    body.columnconfigure(0, weight=3, uniform="dash")
    body.columnconfigure(1, weight=2, uniform="dash")
    body.rowconfigure(0, weight=1)

    left = ttk.Frame(body)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    _attendance_panel(left, ctl, host)
    _viability_panel(left, ctl, host)

    right = ttk.Frame(body)
    right.grid(row=0, column=1, sticky="nsew")
    _outstanding_panel(right, stats)
    _finance_panel(right, stats)
    _quick_actions(right, host)

    host.set_status(
        f"{stats.learners_on_roll} learners · attendance {w.pct(stats.attendance_pct)} "
        f"({stats.attendance_band})"
    )


def _kpis(parent, stats) -> None:
    w.kpi_row(parent, [
        ("Learners on roll", str(stats.learners_on_roll),
         f"{stats.applicants} applicant(s) waiting", "plain"),
        ("Attendance", w.pct(stats.attendance_pct),
         f"target {ATTENDANCE_TARGET_PCT:.0f}% · {stats.attendance_band}",
         w.tone_for(stats.attendance_band)),
        ("At risk", str(stats.learners_at_risk),
         "below 75% attendance", "bad" if stats.learners_at_risk else "good"),
        ("Courses running", str(stats.courses_running),
         f"{stats.courses_at_risk} recruiting badly",
         "warn" if stats.courses_at_risk else "good"),
        ("Fees outstanding", w.money(stats.fees_outstanding),
         f"{w.pct(stats.fees_collected_pct)} collected",
         "warn" if stats.fees_outstanding > 0 else "good"),
    ])


def _attendance_panel(parent, ctl, host) -> None:
    panel = ttk.LabelFrame(parent, text="Attendance by course", padding=8)
    panel.pack(fill="both", expand=True, pady=(0, 10))
    rows = ctl.reports.attendance_report()
    if not rows:
        w.empty_state(panel, "No registers have been taken yet.")
        return

    table = w.DataTable(panel, [
        ("course", "Course", 90),
        ("title", "Title", 240),
        ("attendance", "Attendance", 90, "e"),
        ("punctuality", "Punctuality", 90, "e"),
        ("unauth", "Unauth.", 70, "e"),
        ("band", "Band", 110),
    ], height=8)
    table.set_rows([
        {
            "course": r["course_id"],
            "title": r["title"],
            "attendance": w.pct(r["attendance_pct"]),
            "punctuality": w.pct(r["punctuality_pct"]),
            "unauth": r["unauthorised"],
            "band": r["band"],
            "_tone": w.tone_for(r["band"]),
        }
        for r in rows
    ])


def _viability_panel(parent, ctl, host) -> None:
    panel = ttk.LabelFrame(parent, text="Recruitment", padding=8)
    panel.pack(fill="both", expand=True)
    rows = ctl.reports.viability_report()
    if not rows:
        w.empty_state(panel, "No courses have been set up yet.")
        return

    table = w.DataTable(panel, [
        ("course", "Course", 90),
        ("title", "Title", 240),
        ("enrolled", "On", 50, "e"),
        ("capacity", "Cap", 50, "e"),
        ("fill", "Filled", 80, "e"),
        ("viability", "Viability", 110),
    ], height=8)
    table.set_rows([
        {
            "course": r["course_id"],
            "title": r["title"],
            "enrolled": r["enrolled"],
            "capacity": r["capacity"] or "—",
            "fill": w.pct(r["fill_pct"]),
            "viability": r["viability"],
            "_tone": w.tone_for(r["viability"]),
        }
        for r in rows[:12]
    ])


def _outstanding_panel(parent, stats) -> None:
    w.kv_panel(parent, "Outstanding", [
        ("Work waiting to be marked", str(stats.marking_outstanding),
         "warn" if stats.marking_outstanding else "good"),
        ("Open referrals", str(stats.open_referrals),
         "warn" if stats.open_referrals else "good"),
        ("Safeguarding referrals open", str(stats.safeguarding_open),
         "bad" if stats.safeguarding_open else "good"),
        ("Tutorials overdue", str(stats.tutorials_overdue),
         "warn" if stats.tutorials_overdue else "good"),
    ]).pack(fill="x", pady=(0, 10))


def _finance_panel(parent, stats) -> None:
    w.kv_panel(parent, "Finance & staffing", [
        ("Fees charged", w.money(stats.fees_charged)),
        ("Outstanding", w.money(stats.fees_outstanding),
         "warn" if stats.fees_outstanding else "good"),
        ("Bursaries awarded", w.money(stats.bursary_awarded)),
        ("Staff", str(stats.staff_total)),
        ("Of whom teaching", str(stats.teaching_staff)),
    ]).pack(fill="x", pady=(0, 10))


def _quick_actions(parent, host) -> None:
    panel = ttk.LabelFrame(parent, text="Quick actions", padding=8)
    panel.pack(fill="x")
    actions = [
        ("Learners", "students"),
        ("Courses", "courses"),
        ("Timetable", "timetables"),
        ("Staff", "staff"),
        ("Finance", "finance"),
        ("Reports", "reports"),
    ]
    for i, (label, screen) in enumerate(actions):
        ttk.Button(panel, text=label,
                   command=lambda s=screen: host.open_screen(s)).grid(
            row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
    panel.columnconfigure(0, weight=1, uniform="qa")
    panel.columnconfigure(1, weight=1, uniform="qa")


__all__ = ["TITLE", "open_window"]
