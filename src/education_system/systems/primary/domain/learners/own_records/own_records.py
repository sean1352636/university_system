"""The one read layer behind the student and parent screens (GUI and CLI).

Every function takes the signed-in ``auth`` and re-checks identity through
:data:`GATE` before reading anything. A student's pupil comes from the session
only; a parent's chosen child must be one of their own links, and is checked
again on every read and write.

The rows returned here carry only what the role matrix in
``docs/primary/security/SECURITY.md`` allows. Staff notes, comments, medical and
SEND detail, safeguarding records and other pupils' names are left out here, so
no screen can show them by accident.

Students read: timetable, homework, reading log.
Parents read: attendance, assessment, published reports.
Parents write: consent answers, and booking a parents' evening slot. Both go
through the existing domain services and are recorded in the activity feed,
which is what Audit Reports reads.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from education_system.platform.cross_system.own_record_access import (
    NoRecordLink,
    OwnRecordError,
    OwnRecordGate,
    RecordRefused,
)
from education_system.systems.primary.domain.learners.pupils import pupils

logger = logging.getLogger(__name__)

SYSTEM_KEY = "primary"

GATE = OwnRecordGate(
    SYSTEM_KEY,
    get_pupil=lambda pupil_id: pupils.get_pupil(pupil_id),
    pupil_for_journey=lambda journey_id: pupils.find_by_journey(journey_id),
    on_roll=pupils.ON_ROLL,
)

#: What a parent can answer on the school's consent records. These are the
#: purposes the security guide says parents consent to, by the names the GDPR
#: module stores; the rest of its list is not for parents to answer.
PARENT_CONSENT_PURPOSES: tuple[str, ...] = (
    "Photography / Video", "Trips & Visits", "Third-Party Sharing",
)

BOOKABLE_EVENT_STATUS = "Open for Booking"
#: The parents' evening year group every family can book.
ALL_YEARS_EVENT = "Whole School"
_KEY_STAGE_YEARS = {"KS1": ("1", "2"), "KS2": ("3", "4", "5", "6")}


def _evening_is_for(event_year: str | None, pupil_year: str | None) -> bool:
    """Is a parents' evening for this child's year? Evenings are for the
    whole school, one year ("Reception", "Year 1"…"Year 6") or a key stage."""
    yg = (event_year or ALL_YEARS_EVENT).strip()
    if yg == ALL_YEARS_EVENT:
        return True
    year = (pupil_year or "").strip()
    if yg in _KEY_STAGE_YEARS:
        return year in _KEY_STAGE_YEARS[yg]
    return yg == ("Reception" if year == "R" else f"Year {year}")


# ── Who is looking ─────────────────────────────────────────────────

@dataclass(frozen=True)
class Child:
    pupil_id: str
    name: str
    year_group: str
    class_name: str | None


def _child(pupil: Any) -> Child:
    return Child(pupil_id=pupil.pupil_id, name=pupil.full_name,
                 year_group=pupil.year_group, class_name=pupil.class_name)


def my_pupil(auth: Any) -> Child:
    """The pupil this student's session belongs to."""
    return _child(GATE.student(auth))


def my_children(auth: Any) -> list[Child]:
    """This parent's own linked children, for them to choose between."""
    return [_child(p) for p in GATE.children(auth)]


# ── Student: timetable ─────────────────────────────────────────────

@dataclass(frozen=True)
class TimetableRow:
    day: str
    period: int
    start_time: str | None
    end_time: str | None
    subject: str
    room: str | None
    teacher: str | None


def _for_my_class(row_form: str | None, class_name: str | None) -> bool:
    """A row set for the whole year, or for this pupil's own class."""
    return not row_form or row_form == class_name


def timetable(auth: Any, pupil_id: str | None = None) -> list[TimetableRow]:
    from education_system.systems.primary.domain.academics.timetable import (
        timetable as data,
    )
    pupil = GATE.student(auth, pupil_id)
    return [
        TimetableRow(day=s.day_of_week, period=s.period, start_time=s.start_time,
                     end_time=s.end_time, subject=s.subject_name or s.subject_code or "",
                     room=s.room, teacher=s.teacher)
        for s in data.list_slots(year_group=pupil.year_group)
        if _for_my_class(s.form_group, pupil.class_name)
    ]


# ── Student: homework ──────────────────────────────────────────────

@dataclass(frozen=True)
class HomeworkRow:
    title: str
    subject: str
    set_date: str
    due_date: str
    instructions: str | None
    status: str
    grade: str | None
    mark_pct: float | None
    feedback: str | None


def homework(auth: Any, pupil_id: str | None = None) -> list[HomeworkRow]:
    """Homework that has been set for this pupil's year and class."""
    from education_system.systems.primary.domain.academics.homework import (
        homework as data,
    )
    pupil = GATE.student(auth, pupil_id)
    mine = {s.assignment_id: s for s in data.list_for_pupil(pupil.pupil_id)}
    rows = []
    for a in data.list_assignments(year_group=pupil.year_group):
        if a.status == "Draft" or not _for_my_class(a.form_group, pupil.class_name):
            continue
        sub = mine.get(a.assignment_id)
        rows.append(HomeworkRow(
            title=a.title, subject=a.subject_name or a.subject_code or "",
            set_date=a.set_date, due_date=a.due_date, instructions=a.instructions,
            status=sub.status if sub else "Pending",
            grade=sub.grade if sub else None,
            mark_pct=sub.mark_pct if sub else None,
            feedback=sub.feedback if sub else None))
    return rows


# ── Student: reading log ───────────────────────────────────────────

@dataclass(frozen=True)
class ReadingRow:
    assessed_on: str | None
    band: str
    status: str
    book_title: str | None


def reading_log(auth: Any, pupil_id: str | None = None
                ) -> tuple[ReadingRow | None, list[ReadingRow]]:
    """(current book band, history), newest first. Staff notes are left out."""
    from education_system.systems.primary.domain.assessment.reading_levels import (
        reading_levels as data,
    )
    pupil = GATE.student(auth, pupil_id)
    current = data.get_record(pupil.pupil_id)
    return (
        ReadingRow(current.last_assessed, current.band, current.status,
                   current.book_title) if current else None,
        [ReadingRow(h.assessed_on, h.band, h.status, h.book_title)
         for h in data.list_history(pupil.pupil_id)],
    )


# ── Parent: attendance ─────────────────────────────────────────────

@dataclass(frozen=True)
class AttendanceMark:
    date: str
    session: str
    mark: str


@dataclass(frozen=True)
class AttendanceSummary:
    total_sessions: int
    present: int
    authorised_absent: int
    unauthorised_absent: int
    attendance_pct: float
    marks: tuple[AttendanceMark, ...]


def attendance(auth: Any, pupil_id: str) -> AttendanceSummary:
    from education_system.systems.primary.domain.academics.attendance import (
        attendance as data,
    )
    pupil = GATE.child(auth, pupil_id)
    s = data.pupil_summary(pupil.pupil_id)
    return AttendanceSummary(
        total_sessions=s["total_sessions"], present=s["present"],
        authorised_absent=s["authorised_absent"],
        unauthorised_absent=s["unauthorised_absent"],
        attendance_pct=s["attendance_pct"],
        marks=tuple(AttendanceMark(r.date, r.session, r.label) for r in s["records"]))


# ── Parent: assessment ─────────────────────────────────────────────

@dataclass(frozen=True)
class AssessmentRow:
    academic_year: str
    term: str
    subject: str
    grade: str
    score: float | None
    assessed_on: str | None


def assessment(auth: Any, pupil_id: str) -> list[AssessmentRow]:
    from education_system.systems.primary.domain.assessment import assessment as data

    pupil = GATE.child(auth, pupil_id)
    return [AssessmentRow(r.academic_year, r.term, r.subject, r.grade, r.score,
                          r.assessed_on)
            for r in data.list_for_pupil(pupil.pupil_id)]


# ── Parent: reports ────────────────────────────────────────────────

@dataclass(frozen=True)
class ReportRow:
    academic_year: str
    term: str
    published_on: str | None
    headline: str | None
    summary: str | None
    strengths: str | None
    next_steps: str | None
    attendance_pct: float | None
    behaviour: str | None


def reports(auth: Any, pupil_id: str) -> list[ReportRow]:
    """Published reports only: a draft is still the teacher's."""
    from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
        pupil_reports as data,
    )
    pupil = GATE.child(auth, pupil_id)
    return [ReportRow(r.academic_year, r.term, r.published_on, r.headline, r.summary,
                      r.strengths, r.next_steps, r.attendance_pct, r.behaviour)
            for r in data.list_for_pupil(pupil.pupil_id) if r.is_published]


# ── Writes: the audit line ─────────────────────────────────────────

def _audit(account: Any, action: str, summary: str, pupil_id: str) -> None:
    """Record a parent's write. The write has happened, so a logging failure
    must not report it as failed; it is logged loudly instead."""
    from education_system.systems.primary.domain.operations.communications.activity_feed import (
        activity_feed,
    )
    try:
        activity_feed.log(action, summary, actor=account.username,
                          actor_role=account.role, entity_type="student",
                          entity_id=pupil_id)
    except Exception:
        logger.exception("Could not audit %s by %s for pupil %s",
                         action, account.username, pupil_id)


# ── Parent: consent forms ──────────────────────────────────────────

@dataclass(frozen=True)
class ConsentAnswer:
    purpose: str
    answer: str
    answered_on: str | None


@dataclass(frozen=True)
class TripConsent:
    booking_id: int
    trip: str
    destination: str | None
    start_date: str
    end_date: str | None
    consent_received: bool


def consent_answers(auth: Any, pupil_id: str) -> list[ConsentAnswer]:
    """The current answer for each purpose a parent can answer."""
    from education_system.systems.primary.domain.governance.gdpr import gdpr

    pupil = GATE.child(auth, pupil_id)
    latest: dict[str, Any] = {}
    # Newest first, so the first row seen for a purpose is its current answer.
    for row in gdpr.list_consents(subject_ref=pupil.pupil_id):
        latest.setdefault(row.purpose, row)
    answers = []
    for purpose in PARENT_CONSENT_PURPOSES:
        row = latest.get(purpose)
        if row is None:
            answers.append(ConsentAnswer(purpose, "Not answered", None))
        elif row.is_active:
            answers.append(ConsentAnswer(purpose, "Given", row.granted_date))
        else:
            answers.append(ConsentAnswer(
                purpose, "Not given", row.withdrawn_date or row.granted_date))
    return answers


def answer_consent(auth: Any, pupil_id: str, purpose: str, give: bool) -> ConsentAnswer:
    """Record a parent's answer, keeping earlier answers as history."""
    from education_system.systems.primary.domain.governance.gdpr import gdpr

    account = GATE.account(auth)
    pupil = GATE.child(auth, pupil_id)
    if purpose not in PARENT_CONSENT_PURPOSES:
        raise RecordRefused("That is not a consent form a parent can answer here.")
    today = date.today().isoformat()
    for row in gdpr.list_consents(subject_ref=pupil.pupil_id, purpose=purpose,
                                  active_only=True):
        gdpr.withdraw_consent(row.consent_id, withdrawn_date=today)
    gdpr.create_consent({
        "subject_name": pupil.full_name,
        "subject_type": gdpr.DEFAULT_SUBJECT_TYPE,
        "subject_ref": pupil.pupil_id,
        "purpose": purpose,
        "granted": bool(give),
        "granted_date": today,
        "withdrawn_date": None if give else today,
        "source": f"Parent account {account.username}",
    })
    word = "given" if give else "not given"
    _audit(account, "parent_consent_answered", f"Consent {word}: {purpose}", pupil.pupil_id)
    return ConsentAnswer(purpose, "Given" if give else "Not given", today)


def trip_consents(auth: Any, pupil_id: str) -> list[TripConsent]:
    """Trips this child is booked on that have not finished or been cancelled."""
    from education_system.systems.primary.domain.finance.trips import trips as data

    pupil = GATE.child(auth, pupil_id)
    rows = []
    for booking in data.list_bookings(student_id=pupil.pupil_id, active_only=True):
        trip = data.get_trip(booking.trip_id)
        if trip is None or trip.status in ("Completed", "Cancelled"):
            continue
        rows.append(TripConsent(booking.booking_id, trip.name, trip.destination,
                                trip.start_date, trip.end_date,
                                booking.consent_received))
    return rows


def answer_trip_consent(auth: Any, pupil_id: str, booking_id: int, give: bool) -> TripConsent:
    """Answer the consent form for one of this child's own trip bookings."""
    from education_system.systems.primary.domain.finance.trips import trips as data

    account = GATE.account(auth)
    pupil = GATE.child(auth, pupil_id)
    allowed = {t.booking_id: t for t in trip_consents(auth, pupil.pupil_id)}
    if booking_id not in allowed:
        logger.warning("Refused trip booking %s for parent login %s",
                       booking_id, account.username)
        raise RecordRefused("That trip booking is not open for your child.")
    word = "Given" if give else "Declined"
    data.update_booking(booking_id, {
        "consent_received": bool(give),
        "consent_note": (f"{word} by parent account {account.username} "
                         f"on {date.today().isoformat()}"),
    })
    _audit(account, "parent_trip_consent_answered",
           f"Trip consent {word.lower()}: booking {booking_id}", pupil.pupil_id)
    return next(t for t in trip_consents(auth, pupil.pupil_id)
                if t.booking_id == booking_id)


# ── Parent: parents' evening ───────────────────────────────────────

@dataclass(frozen=True)
class EveningOption:
    event_id: int
    name: str
    event_date: str
    location: str | None
    start_time: str
    end_time: str


@dataclass(frozen=True)
class TeacherOption:
    staff_id: str
    name: str


@dataclass(frozen=True)
class EveningBooking:
    event: str
    event_date: str
    slot_time: str
    teacher: str
    status: str


def _bookable(event: Any, pupil: Any) -> bool:
    return (event.status == BOOKABLE_EVENT_STATUS
            and _evening_is_for(event.year_group, getattr(pupil, "year_group", None))
            and event.event_date >= date.today().isoformat())


def evening_options(auth: Any, pupil_id: str) -> list[EveningOption]:
    """Evenings open for booking that this child's parents can use."""
    from education_system.systems.primary.domain.operations.communications.parents_evenings import (
        parents_evenings as data,
    )
    pupil = GATE.child(auth, pupil_id)
    events = [e for e in data.list_events() if _bookable(e, pupil)]
    events.sort(key=lambda e: (e.event_date, e.start_time))
    return [EveningOption(e.event_id, e.name, e.event_date, e.location, e.start_time,
                          e.end_time) for e in events]


def _class_teachers(pupil: Any) -> list[TeacherOption]:
    """The class teachers of this child's class in the latest academic year.

    ``class_teacher_assignments`` is the only record tying a pupil's class to a
    staff id. No assignment with a staff id means nobody to offer.
    """
    from education_system.systems.primary.domain.academics.classes import classes
    from education_system.systems.primary.domain.staff import staff as staff_data
    from education_system.systems.primary.domain.staff.class_teachers import class_teachers

    school_class = classes.get_by_name(pupil.class_name) if pupil.class_name else None
    if school_class is None:
        return []
    assignments = class_teachers.list_for_class(school_class.class_id)
    if not assignments:
        return []
    latest = assignments[0].academic_year
    today = date.today().isoformat()
    options: dict[str, TeacherOption] = {}
    for a in assignments:
        if (a.academic_year != latest or not a.staff_id
                or not (a.is_primary or a.role == "Class Teacher")
                or (a.end_date and a.end_date < today)):
            continue
        member = staff_data.get_staff(a.staff_id)
        if member is not None:
            options[member.staff_id] = TeacherOption(member.staff_id, member.full_name)
    return list(options.values())


def evening_teachers(auth: Any, pupil_id: str) -> list[TeacherOption]:
    return _class_teachers(GATE.child(auth, pupil_id))


def _open_slots(event: Any, staff_id: str) -> list[str]:
    """Slots with no booking row at all.

    The table's unique index also counts cancelled rows, so a cancelled slot
    cannot be rebooked; ``free_slots_for_staff`` would offer one that then fails.
    """
    from education_system.systems.primary.domain.operations.communications.parents_evenings import (
        parents_evenings as data,
    )
    taken = {b.slot_time for b in data.list_bookings(event_id=event.event_id,
                                                     staff_id=staff_id)}
    return [s for s in data.event_slots(event) if s not in taken]


def _checked_evening(auth: Any, pupil_id: str, event_id: int, staff_id: str) -> tuple:
    """(pupil, event, staff id), or refuse: every part must be this child's."""
    from education_system.systems.primary.domain.operations.communications.parents_evenings import (
        parents_evenings as data,
    )
    pupil = GATE.child(auth, pupil_id)
    event = data.get_event(event_id)
    if event is None or not _bookable(event, pupil):
        raise RecordRefused("That parents' evening is not open for booking.")
    if staff_id not in {t.staff_id for t in _class_teachers(pupil)}:
        raise RecordRefused("You can book only with your child's class teacher.")
    return pupil, event, staff_id


def evening_slots(auth: Any, pupil_id: str, event_id: int, staff_id: str) -> list[str]:
    """Free times only: nothing here says who holds the others."""
    _pupil, event, staff_id = _checked_evening(auth, pupil_id, event_id, staff_id)
    return _open_slots(event, staff_id)


def evening_bookings(auth: Any, pupil_id: str) -> list[EveningBooking]:
    """This child's own bookings."""
    from education_system.systems.primary.domain.operations.communications.parents_evenings import (
        parents_evenings as data,
    )
    from education_system.systems.primary.domain.staff import staff as staff_data

    pupil = GATE.child(auth, pupil_id)
    rows = []
    for b in data.list_bookings(student_id=pupil.pupil_id):
        event = data.get_event(b.event_id)
        member = staff_data.get_staff(b.staff_id)
        rows.append(EveningBooking(
            event=event.name if event else "", event_date=event.event_date if event else "",
            slot_time=b.slot_time, teacher=member.full_name if member else "",
            status=b.status))
    return rows


def book_evening(auth: Any, pupil_id: str, event_id: int, staff_id: str,
                 slot_time: str) -> EveningBooking:
    """Book one slot. A child holds one live booking per teacher per evening."""
    from education_system.systems.primary.domain.operations.communications.parents_evenings import (
        parents_evenings as data,
    )
    account = GATE.account(auth)
    pupil, event, staff_id = _checked_evening(auth, pupil_id, event_id, staff_id)
    if any(b.staff_id == staff_id
           for b in data.student_schedule(event.event_id, pupil.pupil_id)):
        raise RecordRefused(
            "You already have a booking with this teacher at this evening. "
            "To change it, please contact the school office.")
    if slot_time not in _open_slots(event, staff_id):
        raise RecordRefused("That slot is not free. Please choose another.")
    booking = data.create_booking(event.event_id, {
        "student_id": pupil.pupil_id,
        "staff_id": staff_id,
        "slot_time": slot_time,
        "status": data.DEFAULT_BOOKING_STATUS,
        "parent_name": account.display_name,
    })
    _audit(account, "parent_evening_booked",
           f"Parents' evening booking {booking.booking_id} at {slot_time}", pupil.pupil_id)
    from education_system.systems.primary.domain.staff import staff as staff_data
    member = staff_data.get_staff(staff_id)
    return EveningBooking(event.name, event.event_date, slot_time,
                          member.full_name if member else "", booking.status)


# ── Admin: linking a parent's login to their child ─────────────────

def _require_admin(auth: Any) -> Any:
    from education_system.systems.primary.domain import access

    principal = access.from_auth(auth)
    if not principal.is_admin:
        raise RecordRefused("Only an administrator can link a parent's login.")
    return principal


def _parent_account(username: str) -> Any:
    """The account with exactly this username, if it is a parent here."""
    from education_system.platform.identity.auth import db as auth_db

    conn = auth_db.connect()
    try:
        row = conn.execute(
            "SELECT u.id, u.username FROM users u JOIN user_systems s ON s.user_id = u.id "
            "WHERE u.username = ? AND u.is_active = 1 AND s.system_key = ? "
            "AND s.role = 'parent'", ((username or "").strip(), SYSTEM_KEY)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"No active parent account with the username {username!r} here.")
    return row


def _audit_link(event_type: str, actor: str, parent: Any, pupil_id: str) -> None:
    import json

    from education_system.platform.identity.auth import db as auth_db

    conn = auth_db.connect()
    try:
        conn.execute(
            "INSERT INTO security_audit_log (event_type, username, user_id, detail) "
            "VALUES (?, ?, ?, ?)",
            (event_type, actor, int(parent["id"]),
             json.dumps({"system": SYSTEM_KEY, "pupil_id": pupil_id,
                         "account": parent["username"]})))
        conn.commit()
    finally:
        conn.close()


def linked_children_of(auth: Any, parent_username: str) -> list[Child]:
    """Admin view: who this parent login is linked to."""
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.services.parent_child_link import active_child_ids

    _require_admin(auth)
    parent = _parent_account(parent_username)
    pupils_found = (pupils.get_pupil(i) for i in active_child_ids(
        str(auth_db.PLATFORM_AUTH_DB_FILE), int(parent["id"]), SYSTEM_KEY))
    return [_child(p) for p in pupils_found if p is not None]


def link_parent_login(auth: Any, parent_username: str, pupil_id: str) -> Child:
    """Admin: link a parent's login to a child, by exact username and pupil id."""
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.services.parent_child_link import ParentChildLinkService

    principal = _require_admin(auth)
    parent = _parent_account(parent_username)
    pupil = pupils.get_pupil((pupil_id or "").strip())
    if pupil is None:
        raise ValueError(f"No pupil with the id {pupil_id!r}.")
    ParentChildLinkService(str(auth_db.PLATFORM_AUTH_DB_FILE)).link_child(
        int(parent["id"]), pupil.pupil_id, SYSTEM_KEY)
    _audit_link("identity.parent_linked", principal.username, parent, pupil.pupil_id)
    return _child(pupil)


def unlink_parent_login(auth: Any, parent_username: str, pupil_id: str) -> bool:
    """Admin: end a parent's link to a child. True if a link was ended."""
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.services.parent_child_link import ParentChildLinkService

    principal = _require_admin(auth)
    parent = _parent_account(parent_username)
    pupil_id = (pupil_id or "").strip()
    ended = ParentChildLinkService(str(auth_db.PLATFORM_AUTH_DB_FILE)).unlink_child(
        int(parent["id"]), pupil_id, SYSTEM_KEY)
    if ended:
        _audit_link("identity.parent_unlinked", principal.username, parent, pupil_id)
    return ended


__all__ = [
    "GATE", "NoRecordLink", "OwnRecordError", "RecordRefused",
    "PARENT_CONSENT_PURPOSES",
    "my_pupil", "my_children",
    "timetable", "homework", "reading_log",
    "attendance", "assessment", "reports",
    "consent_answers", "answer_consent", "trip_consents", "answer_trip_consent",
    "evening_options", "evening_teachers", "evening_slots", "evening_bookings", "book_evening",
    "linked_children_of", "link_parent_login", "unlink_parent_login",
]
