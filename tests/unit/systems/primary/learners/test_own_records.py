"""Own records (domain.learners.own_records.own_records): gaps left by
``tests/unit/systems/primary/test_own_records.py``.

That file covers who may see what. This one checks the values the parent
screens show (attendance figures, assessment and report rows, consent dates),
which trips and evenings are offered, which teachers are offered, and the
admin link/unlink edges. Everything runs in the primary sandbox.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from education_system.platform.cross_system.own_record_access import RecordRefused
from education_system.platform.identity.auth import db as auth_db
from education_system.platform.services.parent_child_link import ParentChildLinkService
from education_system.systems.primary.domain.academics.attendance import attendance as AT
from education_system.systems.primary.domain.academics.classes import classes as CL
from education_system.systems.primary.domain.assessment import assessment as AS
from education_system.systems.primary.domain.finance.trips import trips as TR
from education_system.systems.primary.domain.learners.own_records import own_records as OR
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.communications.parents_evenings import (
    parents_evenings as PE,
)
from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
    pupil_reports as RP,
)
from education_system.systems.primary.domain.staff import staff as SF
from education_system.systems.primary.domain.staff.class_teachers import class_teachers as CT

TODAY = date.today()
SOON = (TODAY + timedelta(days=7)).isoformat()
LATER = (TODAY + timedelta(days=14)).isoformat()
PAST = (TODAY - timedelta(days=7)).isoformat()


def _account(username, role):
    conn = auth_db.connect()
    try:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, display_name, email, is_active) "
            "VALUES (?, 'x', ?, NULL, 1)", (username, username.title())).lastrowid
        conn.execute("INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                     (uid, "primary", role))
        conn.commit()
    finally:
        conn.close()
    return SimpleNamespace(current_user={
        "id": uid, "user_id": uid, "username": username, "display_name": username,
        "systems": [{"system_key": "primary", "role": role}]})


def _family(*children):
    parent = _account("parent.one", "parent")
    links = ParentChildLinkService(str(auth_db.PLATFORM_AUTH_DB_FILE))
    for child in children:
        links.link_child(parent.current_user["id"], child.pupil_id, "primary")
    return parent


def _pupil(first="Ann", year="3", cls="3A"):
    return P.create_pupil({"first_name": first, "last_name": "Mine", "year_group": year,
                           "class_name": cls})


def _audit_count(event_type):
    conn = auth_db.connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM security_audit_log WHERE event_type = ?",
                            (event_type,)).fetchone()[0]
    finally:
        conn.close()


# ── who is looking ───────────────────────────────────────────────────

def test_my_children_carries_name_year_and_class_for_each_linked_child():
    a = _pupil("Ann", "3", "3A")
    b = _pupil("Bob", "R", None)
    parent = _family(a, b)
    kids = {c.pupil_id: c for c in OR.my_children(parent)}
    assert kids[a.pupil_id] == OR.Child(a.pupil_id, "Ann Mine", "3", "3A")
    assert kids[b.pupil_id] == OR.Child(b.pupil_id, "Bob Mine", "R", None)


def test_my_pupil_returns_the_childs_details():
    a = _pupil()
    student = _account(a.pupil_id, "student")
    assert OR.my_pupil(student) == OR.Child(a.pupil_id, "Ann Mine", "3", "3A")


# ── parent reads: values ─────────────────────────────────────────────

def test_attendance_figures_are_computed_from_the_childs_marks():
    a = _pupil()
    parent = _family(a)
    for day, session, mark in (("2026-10-05", "AM", "/"), ("2026-10-05", "PM", "\\"),
                               ("2026-10-06", "AM", "L"), ("2026-10-06", "PM", "I"),
                               ("2026-10-07", "AM", "O"), ("2026-10-07", "PM", "X")):
        AT.record_mark(a.pupil_id, day, session, mark)
    s = OR.attendance(parent, a.pupil_id)
    assert s.total_sessions == 6
    assert (s.present, s.authorised_absent, s.unauthorised_absent) == (3, 1, 1)
    assert s.attendance_pct == 50.0                     # 3 of 6
    assert len(s.marks) == 6
    assert all(isinstance(m, OR.AttendanceMark) for m in s.marks)
    assert {(m.date, m.session) for m in s.marks} >= {("2026-10-05", "AM"),
                                                      ("2026-10-07", "PM")}


def test_attendance_with_no_marks_is_zero_not_an_error():
    a = _pupil()
    s = OR.attendance(_family(a), a.pupil_id)
    assert (s.total_sessions, s.present, s.attendance_pct, s.marks) == (0, 0, 0.0, ())


def test_assessment_rows_carry_year_term_subject_grade_score_and_date():
    a = _pupil()
    AS.create({"pupil_id": a.pupil_id, "academic_year": "2026-27", "term": "Autumn",
               "subject": "Maths", "grade": "EXS", "score": 72, "assessed_on": "2026-10-10"})
    rows = OR.assessment(_family(a), a.pupil_id)
    assert len(rows) == 1
    r = rows[0]
    assert (r.academic_year, r.term, r.subject, r.grade) == ("2026-27", "Autumn", "Maths", "EXS")
    assert r.score == 72.0 and r.assessed_on == "2026-10-10"


def test_assessment_with_nothing_recorded_is_empty():
    a = _pupil()
    assert OR.assessment(_family(a), a.pupil_id) == []


def test_published_report_shows_its_fields():
    a = _pupil()
    made = RP.create({"pupil_id": a.pupil_id, "academic_year": "2026-27", "term": "Autumn",
                      "headline": "Good term", "summary": "Settled", "strengths": "Reading",
                      "next_steps": "Times tables", "attendance_pct": 96.5,
                      "behaviour": "Excellent"})
    RP.publish(made.report_id, published_on="2026-12-15")
    [r] = OR.reports(_family(a), a.pupil_id)
    assert (r.academic_year, r.term, r.published_on) == ("2026-27", "Autumn", "2026-12-15")
    assert (r.headline, r.summary, r.strengths, r.next_steps) == (
        "Good term", "Settled", "Reading", "Times tables")
    assert r.attendance_pct == 96.5 and r.behaviour == "Excellent"


# ── consent ──────────────────────────────────────────────────────────

def test_consent_answers_list_every_parent_purpose_in_order():
    a = _pupil()
    answers = OR.consent_answers(_family(a), a.pupil_id)
    assert [x.purpose for x in answers] == list(OR.PARENT_CONSENT_PURPOSES)
    assert all(x.answer == "Not answered" and x.answered_on is None for x in answers)


def test_answer_consent_is_dated_today_and_only_touches_that_purpose():
    a = _pupil()
    parent = _family(a)
    saved = OR.answer_consent(parent, a.pupil_id, "Trips & Visits", True)
    assert saved == OR.ConsentAnswer("Trips & Visits", "Given", TODAY.isoformat())
    answers = {x.purpose: x for x in OR.consent_answers(parent, a.pupil_id)}
    assert answers["Trips & Visits"].answered_on == TODAY.isoformat()
    assert answers["Photography / Video"].answer == "Not answered"
    assert answers["Third-Party Sharing"].answer == "Not answered"


def test_declining_consent_dates_the_refusal():
    a = _pupil()
    parent = _family(a)
    saved = OR.answer_consent(parent, a.pupil_id, "Third-Party Sharing", False)
    assert saved == OR.ConsentAnswer("Third-Party Sharing", "Not given", TODAY.isoformat())
    answers = {x.purpose: x for x in OR.consent_answers(parent, a.pupil_id)}
    assert answers["Third-Party Sharing"].answer == "Not given"
    assert answers["Third-Party Sharing"].answered_on == TODAY.isoformat()


# ── trips ────────────────────────────────────────────────────────────

def test_finished_and_cancelled_trips_are_not_offered():
    a = _pupil()
    parent = _family(a)
    live = TR.create_trip({"name": "Zoo", "destination": "City Zoo", "start_date": SOON,
                           "end_date": SOON, "status": "Open for Booking"})
    done = TR.create_trip({"name": "Farm", "start_date": SOON, "status": "Completed"})
    off = TR.create_trip({"name": "Castle", "start_date": SOON, "status": "Cancelled"})
    for trip in (live, done, off):
        TR.create_booking(trip.trip_id, {"student_id": a.pupil_id})
    [t] = OR.trip_consents(parent, a.pupil_id)
    assert (t.trip, t.destination, t.start_date, t.end_date) == ("Zoo", "City Zoo", SOON, SOON)
    assert t.consent_received is False


def test_trip_consent_declined_is_recorded_as_not_received():
    a = _pupil()
    parent = _family(a)
    trip = TR.create_trip({"name": "Zoo", "start_date": SOON, "status": "Open for Booking"})
    booking = TR.create_booking(trip.trip_id, {"student_id": a.pupil_id})
    OR.answer_trip_consent(parent, a.pupil_id, booking.booking_id, True)
    saved = OR.answer_trip_consent(parent, a.pupil_id, booking.booking_id, False)
    assert saved.consent_received is False
    note = TR.get_booking(booking.booking_id).consent_note
    assert note.startswith("Declined by parent account parent.one on ")


# ── parents' evenings ────────────────────────────────────────────────

def _evening(name="Autumn evening", day=SOON, status="Open for Booking", year="Whole School",
             start="16:00"):
    return PE.create_event({"name": name, "event_date": day, "start_time": start,
                            "end_time": "17:00", "slot_minutes": 10, "status": status,
                            "year_group": year})


def _teacher(first, cls_name, *, year="2026-27", role="Class Teacher", primary=True,
             end=None, class_year="3"):
    member = SF.create_staff({"first_name": first, "last_name": "Teach",
                              "email": f"{first.lower()}@school.example"})
    made = CL.get_by_name(cls_name) or CL.create({"name": cls_name, "year_group": class_year})
    CT.create({"class_id": made.class_id, "staff_name": member.full_name,
               "staff_id": member.staff_id, "academic_year": year, "role": role,
               "is_primary": primary, "end_date": end})
    return member


def test_whole_school_evening_open_for_booking_is_offered():
    """A Whole School evening is the one every parent can book. Parents'
    evenings store "Whole School"; own_records only accepts "Both", a label
    the evenings module never writes, so no evening is ever offered."""
    a = _pupil()
    ev = _evening()
    options = OR.evening_options(_family(a), a.pupil_id)
    assert [o.event_id for o in options] == [ev.event_id]
    assert options[0] == OR.EveningOption(ev.event_id, "Autumn evening", SOON, None,
                                          "16:00", "17:00")


def test_whole_school_evenings_are_sorted_by_date_then_time():
    a = _pupil()
    late = _evening("Later", day=LATER)
    early = _evening("Sooner", day=SOON, start="16:30")
    first = _evening("Soonest", day=SOON, start="16:00")
    assert [o.event_id for o in OR.evening_options(_family(a), a.pupil_id)] == [
        first.event_id, early.event_id, late.event_id]


def test_closed_past_and_other_year_evenings_are_not_offered():
    a = _pupil()
    _evening("Scheduled", status="Scheduled")
    _evening("Past", day=PAST)
    _evening("Year 5 only", year="Year 5")
    assert OR.evening_options(_family(a), a.pupil_id) == []


def test_evening_teachers_are_this_years_live_class_teachers_only():
    a = _pupil(cls="3A")
    current = _teacher("Tia", "3A")
    _teacher("Old", "3A", year="2025-26")
    _teacher("Ta", "3A", role="Teaching Assistant", primary=False)
    _teacher("Gone", "3A", end=(TODAY - timedelta(days=1)).isoformat())
    _teacher("Ben", "3B")
    teachers = OR.evening_teachers(_family(a), a.pupil_id)
    assert teachers == [OR.TeacherOption(current.staff_id, "Tia Teach")]


def test_a_child_with_no_class_or_unknown_class_has_no_teachers():
    a = _pupil(cls=None)
    b = _pupil("Bob", cls="Nowhere")
    parent = _family(a, b)
    assert OR.evening_teachers(parent, a.pupil_id) == []
    assert OR.evening_teachers(parent, b.pupil_id) == []


def test_evening_slots_refuse_a_closed_evening():
    a = _pupil(cls="3A")
    tia = _teacher("Tia", "3A")
    closed = _evening(status="Scheduled")
    with pytest.raises(RecordRefused, match="not open for booking"):
        OR.evening_slots(_family(a), a.pupil_id, closed.event_id, tia.staff_id)


def test_evening_bookings_are_empty_before_booking():
    a = _pupil()
    assert OR.evening_bookings(_family(a), a.pupil_id) == []


# ── admin linking ────────────────────────────────────────────────────

def test_linked_children_of_is_admin_only():
    a = _pupil()
    _family(a)
    teacher = _account("teach", "teacher")
    with pytest.raises(RecordRefused, match="Only an administrator"):
        OR.linked_children_of(teacher, "parent.one")
    admin = _account("office", "admin")
    assert [c.pupil_id for c in OR.linked_children_of(admin, "parent.one")] == [a.pupil_id]


def test_linked_children_of_an_unlinked_parent_is_empty_and_unknown_is_refused():
    admin = _account("office", "admin")
    _account("parent.two", "parent")
    assert OR.linked_children_of(admin, "parent.two") == []
    with pytest.raises(ValueError, match="No active parent account"):
        OR.linked_children_of(admin, "nobody")


def test_unlinking_a_link_that_does_not_exist_is_false_and_not_audited():
    a = _pupil()
    admin = _account("office", "admin")
    _account("parent.two", "parent")
    assert OR.unlink_parent_login(admin, "parent.two", a.pupil_id) is False
    assert _audit_count("identity.parent_unlinked") == 0


def test_unlink_is_audited_once():
    a = _pupil()
    _family(a)
    admin = _account("office", "admin")
    assert OR.unlink_parent_login(admin, "parent.one", f" {a.pupil_id} ") is True
    assert _audit_count("identity.parent_unlinked") == 1
    assert OR.linked_children_of(admin, "parent.one") == []


def test_link_trims_the_pupil_id():
    a = _pupil()
    admin = _account("office", "admin")
    _account("parent.two", "parent")
    child = OR.link_parent_login(admin, " parent.two ", f"  {a.pupil_id}  ")
    assert child.pupil_id == a.pupil_id
    assert _audit_count("identity.parent_linked") == 1
