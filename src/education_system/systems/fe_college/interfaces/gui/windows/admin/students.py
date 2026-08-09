"""Admin learner directory — the register of everyone on roll.

Search and filter, then act: view a full profile, add or edit a learner, enrol
them onto a course, withdraw them, or remove the record entirely.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.config import (
    LEARNER_TYPES,
    MODES_OF_STUDY,
    STUDENT_STATUSES,
)
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
)
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Learners"


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
            "Everyone on roll, plus applicants who have not yet enrolled.",
            actions=[
                ("+ New learner", self.new),
                ("↻ Refresh", self.refresh),
            ],
        )

        courses = [c.course_id for c in self.ctl.courses.list_all()]
        self.filters = w.FilterBar(
            parent, self.refresh,
            search_label="Name / ID / ULN",
            filters=[
                ("status", "Status", STUDENT_STATUSES),
                ("course_id", "Course", courses),
                ("tutor_group", "Tutor group", self.ctl.students.tutor_groups()),
                ("learner_type", "Learner type", LEARNER_TYPES),
            ],
        )

        self.table = w.DataTable(parent, [
            ("id", "ID", 90),
            ("name", "Name", 190),
            ("age", "Age", 45, "e"),
            ("type", "Learner type", 160),
            ("mode", "Mode", 90),
            ("group", "Group", 80),
            ("status", "Status", 90),
            ("attendance", "Attendance", 90, "e"),
            ("email", "Email", 230),
        ], on_double_click=lambda _s: self.view())

        w.button_bar(parent, [
            ("View profile", self.view),
            ("Edit", self.edit),
            ("Enrol on course", self.enrol),
            ("Withdraw", self.withdraw),
            ("Delete", self.delete),
        ])
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            learners = self.ctl.students.search(
                query=self.filters.query, **self.filters.values()
            )
            rates = {
                s.student_id: summary
                for s, summary in self.ctl.attendance.by_student()
            }
        except Exception as exc:
            logger.exception("Could not list FE College learners")
            w.error(self.host, TITLE, f"Could not load learners: {exc}")
            return

        rows = []
        for learner in learners:
            summary = rates.get(learner.student_id)
            band = summary.band if summary else "no data"
            rows.append({
                "id": learner.student_id,
                "name": learner.full_name,
                "age": learner.age if learner.age is not None else "—",
                "type": learner.learner_type,
                "mode": learner.mode_of_study,
                "group": learner.tutor_group or "—",
                "status": learner.status,
                "attendance": w.pct(summary.attendance_pct) if summary else "—",
                "email": learner.email or "—",
                "_tone": w.tone_for(band) if summary else "plain",
                "_obj": learner,
            })
        self.table.set_rows(rows)
        self.filters.set_count(len(rows), "learner")
        self.host.set_status(f"{len(rows)} learner(s)")

    # ── Actions ────────────────────────────────────────────────────────────

    def view(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        profile = self.ctl.students.profile(learner.student_id)
        if profile is None:
            w.error(self.host, TITLE, "That learner no longer exists.")
            self.refresh()
            return
        w.show_text(self.host, f"{learner.display_name}", _profile_text(profile))

    def new(self) -> None:
        result = w.ask(
            self.host, "New learner", _FIELDS,
            initial={
                "student_id": self.ctl.students.next_reference(),
                "learner_type": LEARNER_TYPES[0],
                "mode_of_study": MODES_OF_STUDY[0],
                "status": "applicant",
                "start_date": date.today().isoformat(),
            },
            submit_label="Create",
        )
        if result is None:
            return
        try:
            created = self.ctl.students.create(_to_student(result))
        except ValidationError as exc:
            w.error(self.host, "New learner", str(exc))
            return
        self.refresh()
        self.host.set_status(f"Created {created.display_name}")

    def edit(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        result = w.ask(
            self.host, f"Edit {learner.display_name}", _FIELDS,
            initial=_from_student(learner), submit_label="Save",
        )
        if result is None:
            return
        try:
            updated = _to_student(result)
            updated.created_at = learner.created_at
            self.ctl.students.update(updated)
        except ValidationError as exc:
            w.error(self.host, "Edit learner", str(exc))
            return
        self.refresh()
        self.host.set_status(f"Saved {learner.display_name}")

    def enrol(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        courses = self.ctl.courses.enrollable()
        if not courses:
            w.info(self.host, "Enrol", "No courses are currently accepting enrolments.")
            return
        options = [f"{c.course_id} — {c.title}" for c in courses]
        result = w.ask(self.host, f"Enrol {learner.full_name}", [
            ("course", "Course", "choice", options),
            ("main_aim", "Main learning aim", "bool"),
            ("override", "Admit despite entry requirements", "bool"),
        ], initial={"main_aim": True})
        if result is None:
            return

        course_id = result["course"].split(" — ")[0]
        try:
            outcome = self.ctl.enrolments.enrol(
                learner.student_id, course_id,
                is_main_aim=result["main_aim"],
                override_eligibility=result["override"],
            )
        except ValidationError as exc:
            w.error(self.host, "Enrol", str(exc))
            return

        if not outcome.enrolled:
            w.warn(
                self.host, "Not eligible",
                f"{learner.full_name} does not meet the entry requirements for "
                f"{course_id}:\n\n• " + "\n• ".join(outcome.actions)
                + "\n\nRe-run with 'Admit despite entry requirements' to override.",
            )
            return

        message = f"{learner.full_name} enrolled on {course_id}."
        if outcome.actions:
            message += "\n\nStill to do:\n• " + "\n• ".join(outcome.actions)
        w.info(self.host, "Enrolled", message)
        self.refresh()

    def withdraw(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        enrolments = [
            e for e in self.ctl.students.profile(learner.student_id).enrolments
            if e.is_active
        ]
        if not enrolments:
            w.info(self.host, "Withdraw", f"{learner.full_name} has no active enrolments.")
            return

        options = [f"{e.enrolment_id} — {e.course_id} ({e.academic_year})" for e in enrolments]
        result = w.ask(self.host, f"Withdraw {learner.full_name}", [
            ("enrolment", "Enrolment", "choice", options),
            ("reason", "Reason", "choice", list(self.ctl.enrolments.withdrawal_reasons())),
        ])
        if result is None:
            return
        try:
            self.ctl.enrolments.withdraw(
                int(result["enrolment"].split(" — ")[0]), result["reason"]
            )
        except ValidationError as exc:
            w.error(self.host, "Withdraw", str(exc))
            return
        self.refresh()
        self.host.set_status(f"Withdrew {learner.full_name}")

    def delete(self) -> None:
        learner = self.table.require_selection("a learner")
        if learner is None:
            return
        if not w.confirm(
            self.host, "Delete learner",
            f"Permanently delete {learner.display_name}?\n\n"
            "Their enrolments, attendance, grades, fees and pastoral records "
            "go with them. This cannot be undone — withdrawing keeps the "
            "history instead.",
        ):
            return
        self.ctl.students.delete(learner.student_id)
        self.refresh()
        self.host.set_status(f"Deleted {learner.display_name}")


# ── Form plumbing ───────────────────────────────────────────────────────────

_FIELDS = (
    ("student_id", "Student ID", "text"),
    ("first_name", "First name", "text"),
    ("last_name", "Last name", "text"),
    ("date_of_birth", "Date of birth", "date"),
    ("uln", "ULN (10 digits)", "text"),
    ("email", "Email", "text"),
    ("phone", "Phone", "text"),
    ("postcode", "Postcode", "text"),
    ("learner_type", "Learner type", "choice", LEARNER_TYPES),
    ("mode_of_study", "Mode of study", "choice", MODES_OF_STUDY),
    ("status", "Status", "choice", STUDENT_STATUSES),
    ("tutor_group", "Tutor group", "text"),
    ("personal_tutor", "Personal tutor (staff ID)", "text"),
    ("start_date", "Start date", "date"),
    ("prior_attainment", "Prior attainment", "text"),
    ("has_ehcp", "Has an EHC Plan", "bool"),
    ("emergency_contact_name", "Emergency contact", "text"),
    ("emergency_contact_phone", "Emergency phone", "text"),
    ("notes", "Notes", "multiline"),
)


def _from_student(s: Student) -> dict:
    return {
        "student_id": s.student_id,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "date_of_birth": w.when(s.date_of_birth, ""),
        "uln": s.uln,
        "email": s.email,
        "phone": s.phone,
        "postcode": s.postcode,
        "learner_type": s.learner_type,
        "mode_of_study": s.mode_of_study,
        "status": s.status,
        "tutor_group": s.tutor_group,
        "personal_tutor": s.personal_tutor,
        "start_date": w.when(s.start_date, ""),
        "prior_attainment": s.prior_attainment,
        "has_ehcp": s.has_ehcp,
        "emergency_contact_name": s.emergency_contact_name,
        "emergency_contact_phone": s.emergency_contact_phone,
        "notes": s.notes,
    }


def _to_student(d: dict) -> Student:
    return Student(
        student_id=d["student_id"],
        first_name=d["first_name"],
        last_name=d["last_name"],
        date_of_birth=d["date_of_birth"],
        uln=d["uln"],
        email=d["email"],
        phone=d["phone"],
        postcode=d["postcode"],
        learner_type=d["learner_type"],
        mode_of_study=d["mode_of_study"],
        status=d["status"],
        tutor_group=d["tutor_group"],
        personal_tutor=d["personal_tutor"],
        start_date=d["start_date"],
        prior_attainment=d["prior_attainment"],
        has_ehcp=d["has_ehcp"],
        emergency_contact_name=d["emergency_contact_name"],
        emergency_contact_phone=d["emergency_contact_phone"],
        notes=d["notes"],
    )


def _profile_text(profile) -> str:
    s = profile.student
    lines = [
        f"{s.full_name}  ({s.student_id})",
        "=" * 64,
        f"Date of birth   : {w.when(s.date_of_birth)}   (age {s.age if s.age is not None else '—'})",
        f"ULN             : {s.uln or '—'}",
        f"Email / phone   : {s.email or '—'} / {s.phone or '—'}",
        f"Learner type    : {s.learner_type} · {s.mode_of_study}",
        f"Status          : {s.status}",
        f"Tutor group     : {s.tutor_group or '—'}   Personal tutor: {s.personal_tutor or '—'}",
        f"Started         : {w.when(s.start_date)}",
        f"Prior attainment: {s.prior_attainment or '—'}",
        f"EHC Plan        : {w.yes_no(s.has_ehcp)}",
        f"Emergency       : {s.emergency_contact_name or '—'} {s.emergency_contact_phone or ''}".rstrip(),
        "",
        "Attendance",
        "-" * 64,
        f"  {w.pct(profile.attendance.attendance_pct)} across {profile.attendance.total} "
        f"session(s) — {profile.attendance.band}",
        f"  punctuality {w.pct(profile.attendance.punctuality_pct)} · "
        f"{profile.attendance.unauthorised} unauthorised absence(s)",
        "",
        "Enrolments",
        "-" * 64,
    ]
    if profile.enrolments:
        for e in profile.enrolments:
            aim = "main aim" if e.is_main_aim else "additional"
            grade = f" · grade {e.final_grade}" if e.final_grade else ""
            lines.append(
                f"  {e.course_id:<12} {e.academic_year:<9} {e.status:<11} ({aim}){grade}"
            )
            if e.withdrawal_reason:
                lines.append(f"               withdrawn: {e.withdrawal_reason}")
    else:
        lines.append("  None")

    lines += ["", "Targets", "-" * 64]
    open_targets = [t for t in profile.targets if t.is_open]
    if open_targets:
        for t in open_targets:
            due = f" (due {w.when(t.due_date)})" if t.due_date else ""
            flag = "  OVERDUE" if t.is_overdue() else ""
            lines.append(f"  [{t.status}] {t.description}{due}{flag}")
    else:
        lines.append("  No open targets")

    lines += ["", "Learning support", "-" * 64]
    if profile.support:
        for p in profile.support:
            lines.append(
                f"  {p.support_type} — {p.status}"
                + (f" ({p.hours_per_week}h/week)" if p.hours_per_week else "")
            )
    else:
        lines.append("  None recorded")

    lines += ["", "Finance", "-" * 64,
              f"  Balance: {w.money(profile.balance)}"]

    if profile.warnings:
        lines += ["", "Study programme warnings", "-" * 64]
        lines += [f"  • {warning}" for warning in profile.warnings]
    if s.notes:
        lines += ["", "Notes", "-" * 64, f"  {s.notes}"]
    return "\n".join(lines)


__all__ = ["TITLE", "Screen", "open_window"]
