"""A learner's own attendance — the headline rate and the marks behind it.

Showing the individual marks matters: "88%" is an argument, but a dated list of
which sessions were missed is a conversation. The per-course breakdown is there
because attendance is rarely bad everywhere — it is usually one subject.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.fe_college.config import (
    ATTENDANCE_AT_RISK_PCT,
    ATTENDANCE_TARGET_PCT,
)
from education_system.systems.fe_college.domain.students.attendance import MARK_LABELS
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "My attendance"


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            f"The college expects {ATTENDANCE_TARGET_PCT:.0f}%. Below "
            f"{ATTENDANCE_AT_RISK_PCT:.0f}% your tutor will get in touch.",
            actions=[("↻ Refresh", self.refresh)],
        )

        if not self.ctl.student_id:
            w.empty_state(parent, "Your account is not linked to a learner record.")
            return

        self.holder = ttk.Frame(parent)
        self.holder.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self) -> None:
        w.clear(self.holder)
        try:
            overall = self.ctl.attendance.for_student(self.ctl.student_id)
            profile = self.ctl.students.profile(self.ctl.student_id)
            recent = self._recent_marks()
        except Exception as exc:
            logger.exception("Could not load FE College learner attendance")
            w.error(self.host, TITLE, f"Could not load your attendance: {exc}")
            return

        if overall.total == 0:
            w.empty_state(
                self.holder,
                "No registers have been taken for your classes yet.",
            )
            self.host.set_status("No attendance recorded yet")
            return

        w.kpi_row(self.holder, [
            ("Attendance", w.pct(overall.attendance_pct), overall.band,
             w.tone_for(overall.band)),
            ("Punctuality", w.pct(overall.punctuality_pct),
             f"{overall.late} late arrival(s)",
             "warn" if overall.late else "good"),
            ("Sessions attended", f"{overall.attended}/{overall.total - overall.excused}",
             f"{overall.excused} excused", "plain"),
            ("Unauthorised", str(overall.unauthorised),
             "absences without a reason",
             "bad" if overall.unauthorised else "good"),
        ])

        body = ttk.Frame(self.holder)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1, uniform="a")
        body.columnconfigure(1, weight=1, uniform="a")
        body.rowconfigure(0, weight=1)

        self._by_course(body, profile)
        self._recent_panel(body, recent)

        self.host.set_status(
            f"Attendance {w.pct(overall.attendance_pct)} ({overall.band})"
        )

    def _recent_marks(self):
        from education_system.systems.fe_college.infrastructure.persistence.repositories import (
            attendance_repository,
        )
        return attendance_repository.list_marks(
            student_id=self.ctl.student_id, limit=60
        )

    def _by_course(self, parent, profile) -> None:
        panel = ttk.LabelFrame(parent, text="By course", padding=8)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        rows = []
        for enrolment in (profile.enrolments if profile else []):
            if not enrolment.is_active:
                continue
            summary = self.ctl.attendance.for_student(
                self.ctl.student_id, course_id=enrolment.course_id
            )
            course = self.ctl.courses.get(enrolment.course_id)
            rows.append({
                "course": enrolment.course_id,
                "title": course.title if course else enrolment.course_id,
                "attendance": w.pct(summary.attendance_pct),
                "sessions": summary.total,
                "missed": summary.absent,
                "band": summary.band,
                "_tone": w.tone_for(summary.band),
            })
        if not rows:
            w.empty_state(panel, "No courses with registers yet.")
            return

        table = w.DataTable(panel, [
            ("course", "Course", 100),
            ("title", "Title", 210),
            ("attendance", "Attendance", 95, "e"),
            ("sessions", "Sessions", 75, "e"),
            ("missed", "Missed", 65, "e"),
            ("band", "Band", 110),
        ], height=10)
        table.set_rows(rows)

    def _recent_panel(self, parent, marks) -> None:
        panel = ttk.LabelFrame(parent, text="Recent sessions", padding=8)
        panel.grid(row=0, column=1, sticky="nsew")
        if not marks:
            w.empty_state(panel, "No marks recorded.")
            return

        table = w.DataTable(panel, [
            ("date", "Date", 100),
            ("course", "Course", 100),
            ("period", "Period", 70),
            ("mark", "Mark", 165),
            ("note", "Note", 180),
        ], height=16)
        table.set_rows([
            {
                "date": w.when(m.session_date),
                "course": m.course_id,
                "period": m.period or "—",
                "mark": (
                    f"{MARK_LABELS.get(m.mark, m.mark)}"
                    + (f" ({m.minutes_late} min)" if m.minutes_late else "")
                ),
                "note": m.note or "—",
                "_tone": (
                    "good" if m.mark == "present"
                    else "warn" if m.mark in ("late", "authorised", "excused")
                    else "bad"
                ),
            }
            for m in marks
        ])


__all__ = ["TITLE", "Screen", "open_window"]
