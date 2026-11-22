"""Learner use cases — the operations the interfaces actually invoke.

Services compose repositories and domain rules into whole operations. They are
the layer the GUI and the CLI share: everything a screen needs is one call
here, so the two interfaces can never drift into implementing the same rule
differently.

The learner lifecycle is also announced to the rest of the platform from
here — a new learner joins the cross-system identity registry, and a start,
withdrawal or completion is published on the durable bus — so that an FE
learner has the same journey, history and events as a learner in any other
system. Those calls are best-effort: the college's own record is written
first and stands whatever the platform does.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from education_system.systems.fe_college.config import ACADEMIC_YEAR
from education_system.systems.fe_college.domain.students.attendance import (
    AttendanceSummary,
)
from education_system.systems.fe_college.domain.students.enrolment import (
    Enrolment,
    check_study_programme,
)
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
    next_student_id,
)
from education_system.systems.fe_college.domain.students.support import SupportPlan
from education_system.systems.fe_college.domain.students.targets import Target
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    attendance_repository as attendance_repo,
    course_repository as course_repo,
    finance_repository as finance_repo,
    pastoral_repository as pastoral_repo,
    student_repository as repo,
)

logger = logging.getLogger(__name__)

SYSTEM = "fe_college"
_SOURCE_MODULE = "fe_college.services.student_service"


@dataclass(frozen=True)
class StudentProfile:
    """Everything the learner profile screen shows, gathered in one call."""

    student: Student
    enrolments: list[Enrolment]
    attendance: AttendanceSummary
    targets: list[Target]
    support: list[SupportPlan]
    balance: float
    warnings: list[str]

    @property
    def main_aim(self) -> Enrolment | None:
        return next((e for e in self.enrolments if e.is_active and e.is_main_aim), None)

    @property
    def course_titles(self) -> list[str]:
        return [e.course_id for e in self.enrolments if e.is_active]


# ── Queries ─────────────────────────────────────────────────────────────────

def get(student_id: str) -> Student | None:
    return repo.get(student_id)


def search(query: str = "", **filters) -> list[Student]:
    """Search learners by name, ID, email or ULN, with optional filters."""
    return repo.list_students(query=query, **filters)


def list_active() -> list[Student]:
    return repo.list_students(status="enrolled")


def profile(student_id: str) -> StudentProfile | None:
    """Assemble a learner's full profile.

    Held in one connection: the profile screen needs six different slices of
    the database and opening six connections to draw one page is wasteful.
    """
    with session():
        student = repo.get(student_id)
        if student is None:
            return None
        enrolments = repo.list_enrolments(student_id=student_id)
        return StudentProfile(
            student=student,
            enrolments=enrolments,
            attendance=attendance_repo.summary_for_student(student_id),
            targets=repo.list_targets(student_id=student_id),
            support=repo.list_support_plans(student_id=student_id),
            balance=finance_repo.account_for(student_id).balance,
            warnings=check_study_programme(enrolments),
        )


def next_reference() -> str:
    """The student ID that would be allocated to the next new learner."""
    return next_student_id(repo.all_student_ids())


def tutor_groups() -> list[str]:
    return repo.tutor_groups()


def counts() -> dict[str, int]:
    return repo.count_by_status()


# ── Cross-system hooks (best-effort; never fail the college's own write) ────

def _iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _journey_id(student_id: str) -> str | None:
    try:
        from education_system.platform.cross_system import identity_service
        row = identity_service.find_by_student(SYSTEM, str(student_id))
        return row["journey_id"] if row else None
    except Exception:
        logger.debug("Journey lookup failed for %s", student_id, exc_info=True)
        return None


def _publish(event_attr: str, student_id: str, *, key: str,
             **payload: Any) -> None:
    """Publish a lifecycle event for a learner with a journey."""
    try:
        from education_system.platform.integrations.external import (
            cross_system_bus as bus,
        )
        jid = _journey_id(student_id)
        if jid is None:
            return
        bus.publish_cross_system(
            getattr(bus, event_attr), source_system=SYSTEM,
            source_module=_SOURCE_MODULE, journey_id=jid,
            idempotency_key=key, local_student_id=str(student_id), **payload)
    except Exception:
        logger.warning("Could not publish %s for learner %s (record saved)",
                       event_attr, student_id, exc_info=True)


def _register_journey(student: Student) -> None:
    """Join a new learner to the cross-system identity registry.

    Every other system did this on create; FE did not, so an FE learner had
    no journey until a transfer happened to mint one. Also announces
    ``journey.registered`` (deduplicated against the registry's own).
    """
    try:
        from education_system.platform.cross_system import person
        from education_system.systems.fe_college.infrastructure.persistence import (
            db_path,
        )
        person.register_local_learner(
            SYSTEM, student_id=student.student_id,
            first_name=student.first_name, last_name=student.last_name,
            date_of_birth=_iso(student.date_of_birth),
            start_date=_iso(student.start_date),
            source_module=_SOURCE_MODULE, system_db_path=str(db_path()))
    except Exception:
        logger.debug("Journey registration skipped for %s",
                     student.student_id, exc_info=True)


def _sync_login_links(student: Student, *, previous_email: str | None = None) -> None:
    """Link the learner's own login(s) to their platform learner record.

    FE pairs a login with a learner by student id, then by email, so both
    are re-checked — and a previous email too, so a link made on the old
    address is taken off. Best-effort, never raises.
    """
    from education_system.platform.cross_system import login_links

    login_links.try_sync_username(student.student_id)
    addresses = {a.strip().lower() for a in (student.email, previous_email)
                 if a and a.strip()}
    for address in sorted(addresses):
        login_links.try_sync_email(address)


def _set_programme(student_id: str, title: str | None, *,
                   start: Any = None, replace: bool = False) -> None:
    """Record the learner's main programme on their platform enrolment."""
    if not title:
        return
    try:
        from education_system.platform.cross_system import enrolments
        jid = _journey_id(student_id)
        if jid is None:
            return
        current = enrolments.current_enrolment(jid, SYSTEM)
        if current is not None and replace and current.get("programme") != title:
            enrolments.update_enrolment(current["enrolment_id"], programme=title)
        else:
            enrolments.link_local_enrolment(
                journey_id=jid, system=SYSTEM, local_student_id=str(student_id),
                programme=title, start_date=_iso(start), source_system=SYSTEM)
    except Exception:
        logger.debug("Programme annotation failed for %s", student_id,
                     exc_info=True)


def _learner_left(student_id: str, *, reason: str, status: str,
                  on: Any = None, outcome: str | None = None) -> None:
    """Close the learner's platform enrolment (publishes enrolment.ended)."""
    try:
        from education_system.platform.cross_system import enrolments
        enrolments.end_local_enrolment(
            SYSTEM, str(student_id), reason=reason, status=status,
            end_date=_iso(on), outcome=outcome)
    except Exception:
        logger.debug("Could not close platform enrolment for %s", student_id,
                     exc_info=True)


def record_completion(enrolment: Enrolment, course: Any = None, *,
                      passed: bool = False) -> None:
    """Announce a completed course: programme.completed, and the award.

    Called by :func:`enrolment_service.complete` after the college's own
    row is saved. A passing grade is recorded as a qualification (which
    publishes ``qualification.awarded``) under the same lineage reference
    the platform's qualification projection uses, so the two never
    duplicate. When no active course remains the learner's platform
    enrolment is closed as completed.
    """
    sid = str(enrolment.student_id)
    title = getattr(course, "title", None) or str(enrolment.course_id)
    _publish(
        "EVENT_PROGRAMME_COMPLETED", sid,
        key=f"programme.completed:{SYSTEM}:{enrolment.enrolment_id}",
        enrolment_id=enrolment.enrolment_id, course_id=enrolment.course_id,
        programme=title, final_grade=enrolment.final_grade or None,
        is_main_aim=bool(enrolment.is_main_aim),
        end_date=_iso(enrolment.end_date))
    if passed and enrolment.final_grade:
        try:
            from education_system.platform.cross_system import qualifications
            jid = _journey_id(sid)
            if jid:
                qualifications.record_qualification(
                    jid, source_system=SYSTEM, title=title,
                    level=getattr(course, "level", None),
                    grade=enrolment.final_grade,
                    awarded_on=_iso(enrolment.end_date),
                    source_ref=f"fe_college:enrolments:{enrolment.enrolment_id}",
                    qualification_type=getattr(course, "qualification_type", None),
                    awarding_body=getattr(course, "awarding_body", None),
                    recorded_by=_SOURCE_MODULE)
        except Exception:
            logger.warning("Could not record qualification for enrolment %s",
                           enrolment.enrolment_id, exc_info=True)
    try:
        still_active = repo.list_enrolments(student_id=sid, status="active")
    except Exception:
        still_active = [enrolment]
    if not still_active:
        _learner_left(sid, reason="completed programme", status="completed",
                      on=enrolment.end_date,
                      outcome=enrolment.final_grade or None)


# ── Commands ────────────────────────────────────────────────────────────────

class DuplicateLearner(ValidationError):
    """The new learner looks like somebody already on record.

    Raised only when the caller asks for the check. ``matches`` holds the
    existing learners, so a form can show them and let staff save anyway
    (twins share a surname and a birthday).
    """

    def __init__(self, matches: list[Student]) -> None:
        self.matches = matches
        names = "; ".join(
            f"{m.display_name}, born {m.date_of_birth or 'unknown'}, {m.status}" for m in matches)
        super().__init__(f"This looks like a learner already on record: {names}")


def find_possible_duplicates(student: Student) -> list[Student]:
    return repo.find_possible_duplicates(student)


def create(student: Student, *, check_duplicate: bool = False) -> Student:
    """Register a new learner (an applicant until they are enrolled).

    With *check_duplicate*, a learner matching someone already on record
    (same name and date of birth, or same email) is refused with
    :class:`DuplicateLearner`; call again without it to save anyway. The
    forms ask for the check. Handovers from other systems don't come
    through here; they match on the learner journey.
    """
    if check_duplicate:
        matches = repo.find_possible_duplicates(student)
        if matches:
            raise DuplicateLearner(matches)
    created = repo.create(student)
    _register_journey(created)
    _sync_login_links(created)
    return created


def update(student: Student) -> Student:
    before = repo.get(student.student_id)
    updated = repo.update(student)
    if before is not None and (
            (before.email or "").strip().lower() != (updated.email or "").strip().lower()):
        _sync_login_links(updated, previous_email=before.email)
    return updated


def delete(student_id: str) -> bool:
    return repo.delete(student_id)


def enrol(student_id: str, course_id: str, *,
          academic_year: str = ACADEMIC_YEAR,
          is_main_aim: bool = True,
          funding_source: str = "",
          start_date: date | None = None) -> Enrolment:
    """Enrol a learner onto a course, enforcing the course's own rules.

    Checks that would otherwise be spread across the two interfaces live here:
    the course must exist and be accepting enrolments, and enrolling a learner
    promotes them from applicant to enrolled in the same transaction.
    """
    with session():
        student = repo.get(student_id)
        if student is None:
            raise ValidationError(f"No learner with ID {student_id}")
        course = course_repo.get(course_id)
        if course is None:
            raise ValidationError(f"No course with code {course_id}")
        if course.status in ("cancelled", "archived"):
            raise ValidationError(f"{course.title} is {course.status} and cannot take enrolments")
        if course.is_full:
            raise ValidationError(
                f"{course.title} is full ({course.enrolled}/{course.capacity})"
            )

        enrolment = repo.add_enrolment(Enrolment(
            enrolment_id=None,
            student_id=student_id,
            course_id=course_id,
            academic_year=academic_year,
            status="active",
            is_main_aim=is_main_aim,
            start_date=start_date or course.start_date or date.today(),
            expected_end_date=course.end_date,
            funding_source=funding_source,
        ))
        started = student.status == "applicant"
        if started:
            repo.set_status(student_id, "enrolled")
    if is_main_aim:
        _set_programme(student_id, course.title, start=enrolment.start_date)
    if started:
        _publish("EVENT_LEARNER_UPDATED", student_id,
                 key=f"learner.updated:{SYSTEM}:{student_id}:enrolled",
                 scope="status", status="enrolled", course_id=course_id,
                 programme=course.title)
    return enrolment


def withdraw(enrolment_id: int, reason: str, on: date | None = None) -> None:
    """Withdraw a learner from one course.

    If it was their last active enrolment they leave the college, so their
    learner record is withdrawn too — otherwise they stay on roll for the
    courses they are still taking.
    """
    with session():
        enrolment = repo.get_enrolment(enrolment_id)
        if enrolment is None:
            raise ValidationError(f"No enrolment with ID {enrolment_id}")
        repo.withdraw_enrolment(enrolment_id, reason, on)
        remaining = [
            e for e in repo.list_enrolments(student_id=enrolment.student_id, status="active")
            if e.enrolment_id != enrolment_id
        ]
        left = not remaining
        if left:
            repo.set_status(enrolment.student_id, "withdrawn", on or date.today())
    if left:
        when = on or date.today()
        _publish("EVENT_STUDENT_WITHDRAWN", enrolment.student_id,
                 key=f"student.withdrawn:{SYSTEM}:{enrolment.student_id}:{when}",
                 reason=reason, withdrawal_date=_iso(when),
                 enrolment_id=enrolment_id)
        _learner_left(enrolment.student_id, reason=reason, status="withdrawn",
                      on=when)


def transfer(enrolment_id: int, new_course_id: str, *,
             reason: str = "Transferred to another course") -> Enrolment:
    """Move a learner from one course to another, keeping the audit trail.

    The old enrolment is withdrawn rather than edited, so the college can still
    show what the learner originally started.
    """
    with session():
        enrolment = repo.get_enrolment(enrolment_id)
        if enrolment is None:
            raise ValidationError(f"No enrolment with ID {enrolment_id}")
        if enrolment.course_id == new_course_id:
            raise ValidationError("The learner is already on that course")
        repo.withdraw_enrolment(enrolment_id, reason)
        new = repo.add_enrolment(Enrolment(
            enrolment_id=None,
            student_id=enrolment.student_id,
            course_id=new_course_id,
            academic_year=enrolment.academic_year,
            status="active",
            is_main_aim=enrolment.is_main_aim,
            start_date=date.today(),
            funding_source=enrolment.funding_source,
        ))
        repo.set_status(enrolment.student_id, "enrolled")
        new_course = course_repo.get(new_course_id)
    if enrolment.is_main_aim and new_course is not None:
        # A change of main programme is a learner update the platform sees
        # (enrolments publishes learner.updated when the programme changes).
        _set_programme(enrolment.student_id, new_course.title, replace=True)
    return new


def set_target(student_id: str, description: str, *, set_by: str,
               due_date: date | None = None, course_id: str = "") -> Target:
    return repo.add_target(Target(
        target_id=None,
        student_id=student_id,
        description=description,
        status="set",
        course_id=course_id,
        set_by=set_by,
        set_date=date.today(),
        due_date=due_date,
    ))


def complete_target(target_id: int, note: str = "") -> Target:
    with session():
        targets = [t for t in repo.list_targets() if t.target_id == target_id]
        if not targets:
            raise ValidationError(f"No target with ID {target_id}")
        target = targets[0]
        target.status = "achieved"
        target.completed_date = date.today()
        if note:
            target.review_note = note
        return repo.update_target(target)


def add_support(plan: SupportPlan) -> SupportPlan:
    return repo.add_support_plan(plan)


def at_risk(threshold_pct: float = 75.0) -> list[tuple[Student, AttendanceSummary]]:
    """Learners whose attendance has fallen below ``threshold_pct``.

    Ordered worst-first, because that is the order the pastoral team works it.
    """
    with session():
        summaries = attendance_repo.summaries_by_student()
        learners = {s.student_id: s for s in repo.list_students(status="enrolled")}
    rows = [
        (learners[sid], summary)
        for sid, summary in summaries.items()
        if sid in learners
        and summary.attendance_pct is not None
        and summary.attendance_pct < threshold_pct
    ]
    return sorted(rows, key=lambda r: r[1].attendance_pct or 0)


def tutorial_overdue() -> list[Student]:
    """Enrolled learners past due an individual tutorial review."""
    from education_system.systems.fe_college.domain.pastoral.tutorials import (
        is_tutorial_overdue,
    )

    with session():
        last = pastoral_repo.last_tutorial_dates()
        learners = repo.list_students(status="enrolled")
    return [s for s in learners if is_tutorial_overdue(last.get(s.student_id))]


__all__ = [
    "StudentProfile",
    "add_support",
    "at_risk",
    "complete_target",
    "counts",
    "create",
    "delete",
    "enrol",
    "get",
    "list_active",
    "next_reference",
    "profile",
    "record_completion",
    "search",
    "set_target",
    "transfer",
    "tutor_groups",
    "tutorial_overdue",
    "update",
    "withdraw",
]
