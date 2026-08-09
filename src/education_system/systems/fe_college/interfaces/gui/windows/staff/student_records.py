"""Learner records as a lecturer sees them.

Scoped to the learners a member of staff actually teaches or tutors — the
admin directory shows everyone, this shows yours. The actions here are the
pastoral ones: set a target, record a tutorial, log behaviour, make a referral.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from tkinter import ttk

from education_system.systems.fe_college.config import (
    BEHAVIOUR_TYPES,
    REFERRAL_TYPES,
)
from education_system.systems.fe_college.domain.pastoral.behaviour import (
    BehaviourRecord,
    disciplinary_stage,
)
from education_system.systems.fe_college.domain.pastoral.referrals import (
    URGENCIES,
    Referral,
)
from education_system.systems.fe_college.domain.pastoral.tutorials import (
    TUTORIAL_TYPES,
    Tutorial,
    is_tutorial_overdue,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    pastoral_repository as pastoral_repo,
)
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Learner records"


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
            "The learners you teach or tutor, with their attendance, targets "
            "and pastoral history.",
            actions=[("↻ Refresh", self.refresh)],
        )

        if not self.ctl.staff_id:
            w.empty_state(parent, "Your account is not linked to a staff record, "
                                  "so no learners are attached to you.")
            return

        self.filters = w.FilterBar(
            parent, self.refresh,
            search_label="Name / ID",
            filters=[
                ("course_id", "Course", [c.course_id for c in self.ctl.my_courses()]),
            ],
        )

        self.table = w.DataTable(parent, [
            ("id", "ID", 90),
            ("name", "Name", 190),
            ("group", "Group", 85),
            ("attendance", "Attendance", 95, "e"),
            ("band", "Band", 105),
            ("targets", "Open targets", 95, "e"),
            ("tutorial", "Last tutorial", 105),
            ("stage", "Behaviour stage", 175),
        ], on_double_click=lambda _s: self.view())

        w.button_bar(parent, [
            ("View record", self.view),
            ("Set a target", self.set_target),
            ("Record a tutorial", self.record_tutorial),
            ("Log behaviour", self.log_behaviour),
            ("Make a referral", self.make_referral),
        ])
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            learners = self.ctl.my_learners()
            query = self.filters.query.lower()
            course_id = self.filters.values().get("course_id")
            if course_id:
                on_course = {
                    s.student_id
                    for s in self.ctl.students.search(course_id=course_id)
                }
                learners = [s for s in learners if s.student_id in on_course]
            if query:
                learners = [
                    s for s in learners
                    if query in s.full_name.lower() or query in s.student_id.lower()
                ]

            rates = {s.student_id: summary
                     for s, summary in self.ctl.attendance.by_student()}
            last_tutorials = pastoral_repo.last_tutorial_dates()
        except Exception as exc:
            logger.exception("Could not load FE College learner records")
            w.error(self.host, TITLE, f"Could not load learners: {exc}")
            return

        rows = []
        for learner in learners:
            summary = rates.get(learner.student_id)
            band = summary.band if summary else "no data"
            targets = self.ctl.students.profile(learner.student_id)
            open_targets = (
                sum(1 for t in targets.targets if t.is_open) if targets else 0
            )
            last = last_tutorials.get(learner.student_id)
            behaviour = pastoral_repo.list_behaviour(student_id=learner.student_id)
            rows.append({
                "id": learner.student_id,
                "name": learner.full_name,
                "group": learner.tutor_group or "—",
                "attendance": w.pct(summary.attendance_pct) if summary else "—",
                "band": band,
                "targets": open_targets,
                "tutorial": w.when(last) + (" ⚠" if is_tutorial_overdue(last) else ""),
                "stage": disciplinary_stage(behaviour),
                "_tone": w.tone_for(band),
                "_obj": learner,
            })
        self.table.set_rows(rows)
        self.filters.set_count(len(rows), "learner")
        self.host.set_status(f"{len(rows)} learner(s) attached to you")

    # ── Actions ────────────────────────────────────────────────────────────

    def view(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        profile = self.ctl.students.profile(learner.student_id)
        if profile is None:
            self.refresh()
            return
        tutorials = pastoral_repo.list_tutorials(student_id=learner.student_id)
        behaviour = pastoral_repo.list_behaviour(student_id=learner.student_id)
        referrals = pastoral_repo.list_referrals(student_id=learner.student_id)

        lines = [
            f"{learner.full_name}  ({learner.student_id})",
            "=" * 64,
            f"Tutor group : {learner.tutor_group or '—'}",
            f"Attendance  : {w.pct(profile.attendance.attendance_pct)} "
            f"({profile.attendance.band}) · punctuality "
            f"{w.pct(profile.attendance.punctuality_pct)}",
            f"Behaviour   : {disciplinary_stage(behaviour)}",
            "",
            "Courses",
            "-" * 64,
        ]
        lines += [
            f"  {e.course_id:<12} {e.status}" for e in profile.enrolments if e.is_active
        ] or ["  None"]

        lines += ["", "Targets", "-" * 64]
        lines += [
            f"  [{t.status}] {t.description}"
            + (f" (due {w.when(t.due_date)})" if t.due_date else "")
            for t in profile.targets
        ] or ["  None"]

        lines += ["", "Tutorials", "-" * 64]
        lines += [
            f"  {w.when(t.held_on or t.scheduled_for)} {t.tutorial_type} — {t.status}"
            + (f"\n      {t.notes}" if t.notes else "")
            for t in tutorials[:8]
        ] or ["  None recorded"]

        lines += ["", "Behaviour", "-" * 64]
        lines += [
            f"  {w.when(b.logged_on)} [{b.behaviour_type}] {b.summary}"
            for b in behaviour[:10]
        ] or ["  None recorded"]

        lines += ["", "Referrals", "-" * 64]
        lines += [
            f"  {w.when(r.referred_on)} {r.referral_type} — {r.status}"
            + ("  BREACHING RESPONSE TARGET" if r.is_breaching() else "")
            for r in referrals
        ] or ["  None"]

        if profile.support:
            lines += ["", "Learning support", "-" * 64]
            lines += [f"  {p.support_type} — {p.status}" for p in profile.support]

        w.show_text(self.host, learner.display_name, "\n".join(lines))

    def set_target(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        courses = [""] + [c.course_id for c in self.ctl.my_courses()]
        result = w.ask(self.host, f"Target — {learner.full_name}", [
            ("description", "Target", "text"),
            ("course_id", "Course", "choice", courses),
            ("due_date", "Due by", "date"),
        ], initial={"due_date": (date.today() + timedelta(weeks=4)).isoformat()})
        if result is None:
            return
        try:
            self.ctl.students.set_target(
                learner.student_id, result["description"],
                set_by=self.ctl.staff_id,
                due_date=result["due_date"],
                course_id=result["course_id"],
            )
        except ValidationError as exc:
            w.error(self.host, "Set a target", str(exc))
            return
        self.refresh()

    def record_tutorial(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        result = w.ask(self.host, f"Tutorial — {learner.full_name}", [
            ("tutorial_type", "Type", "choice", list(TUTORIAL_TYPES)),
            ("held_on", "Held on", "date"),
            ("attendance_discussed", "Attendance discussed", "bool"),
            ("progress_discussed", "Progress discussed", "bool"),
            ("targets_set", "Targets agreed", "text"),
            ("notes", "What was discussed", "multiline"),
        ], initial={
            "tutorial_type": TUTORIAL_TYPES[0],
            "held_on": date.today().isoformat(),
            "attendance_discussed": True,
            "progress_discussed": True,
        })
        if result is None:
            return
        try:
            pastoral_repo.add_tutorial(Tutorial(
                tutorial_id=None,
                student_id=learner.student_id,
                tutor_id=self.ctl.staff_id,
                tutorial_type=result["tutorial_type"],
                status="held",
                scheduled_for=result["held_on"],
                held_on=result["held_on"],
                attendance_discussed=result["attendance_discussed"],
                progress_discussed=result["progress_discussed"],
                targets_set=result["targets_set"],
                notes=result["notes"],
            ))
        except ValidationError as exc:
            w.error(self.host, "Record a tutorial", str(exc))
            return
        self.refresh()

    def log_behaviour(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        courses = [""] + [c.course_id for c in self.ctl.my_courses()]
        result = w.ask(self.host, f"Behaviour — {learner.full_name}", [
            ("behaviour_type", "Type", "choice", list(BEHAVIOUR_TYPES)),
            ("summary", "Summary", "text"),
            ("course_id", "Course", "choice", courses),
            ("detail", "Detail", "multiline"),
            ("action_taken", "Action taken", "text"),
            ("parent_informed", "Parent / carer informed", "bool"),
        ], initial={"behaviour_type": BEHAVIOUR_TYPES[0]})
        if result is None:
            return
        try:
            pastoral_repo.add_behaviour(BehaviourRecord(
                record_id=None,
                student_id=learner.student_id,
                behaviour_type=result["behaviour_type"],
                summary=result["summary"],
                logged_by=self.ctl.staff_id,
                logged_on=date.today(),
                course_id=result["course_id"],
                detail=result["detail"],
                action_taken=result["action_taken"],
                parent_informed=result["parent_informed"],
            ))
        except ValidationError as exc:
            w.error(self.host, "Log behaviour", str(exc))
            return
        self.refresh()

    def make_referral(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        result = w.ask(self.host, f"Referral — {learner.full_name}", [
            ("referral_type", "Refer to", "choice", list(REFERRAL_TYPES)),
            ("urgency", "Urgency", "choice", list(URGENCIES)),
            ("reason", "Reason", "multiline"),
        ], initial={"referral_type": REFERRAL_TYPES[1], "urgency": "routine"})
        if result is None:
            return
        try:
            referral = pastoral_repo.add_referral(Referral(
                referral_id=None,
                student_id=learner.student_id,
                referral_type=result["referral_type"],
                reason=result["reason"],
                status="open",
                urgency=result["urgency"],
                referred_by=self.ctl.staff_id,
                referred_on=date.today(),
            ))
        except ValidationError as exc:
            w.error(self.host, "Make a referral", str(exc))
            return
        w.info(
            self.host, "Referral made",
            f"{result['referral_type']} referral raised for "
            f"{learner.full_name}.\n\nResponse due by "
            f"{w.when(referral.response_due)}.",
        )
        self.refresh()


__all__ = ["TITLE", "Screen", "open_window"]
