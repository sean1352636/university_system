"""Own-record screens for students and parents: who can read what.

Everything runs against a temporary primary.db and auth.db with invented rows.
The read layer's module paths are redirected before anything opens a database.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from education_system.platform.cross_system.own_record_access import (
    NoRecordLink,
    OwnRecordError,
    RecordRefused,
)
from education_system.platform.identity.auth import db as auth_db
from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.platform.services.parent_child_link import ParentChildLinkService
from education_system.systems.primary import cli_main, gui_main
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.academics.attendance import attendance as attendance_data
from education_system.systems.primary.domain.academics.classes import classes as classes_data
from education_system.systems.primary.domain.academics.homework import homework as homework_data
from education_system.systems.primary.domain.academics.subjects import subjects as subjects_data
from education_system.systems.primary.domain.academics.timetable import timetable as timetable_data
from education_system.systems.primary.domain.assessment import assessment as assessment_data
from education_system.systems.primary.domain.assessment.reading_levels import reading_levels
from education_system.systems.primary.domain.finance.trips import trips as trips_data
from education_system.systems.primary.domain.governance.gdpr import gdpr
from education_system.systems.primary.domain.learners.own_records import own_records as data
from education_system.systems.primary.domain.learners.pupils import pupils
from education_system.systems.primary.domain.operations.communications.activity_feed import (
    activity_feed,
)
from education_system.systems.primary.domain.operations.communications.parents_evenings import (
    parents_evenings as evenings,
)
from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
    pupil_reports as reports_data,
)
from education_system.systems.primary.domain.staff import staff as staff_data
from education_system.systems.primary.domain.staff.class_teachers import class_teachers


def build_world(tmp_path, monkeypatch) -> SimpleNamespace:
    """Two families, two teachers and every kind of record, all invented."""
    db = tmp_path / "primary.db"
    prefix = "education_system.systems.primary.domain."
    for name, module in list(sys.modules.items()):
        if not name.startswith(prefix) or module is None:
            continue
        if hasattr(module, "DB_PATH"):
            monkeypatch.setattr(module, "DB_PATH", db)
        if hasattr(module, "_DB_READY"):
            monkeypatch.setattr(module, "_DB_READY", False)
    monkeypatch.setattr(pupils, "_DATA_DIR", tmp_path)

    auth_file = tmp_path / "auth.db"
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", auth_file)
    initialise_auth_db(str(auth_file))

    w = SimpleNamespace(tmp_path=tmp_path, db=db, auth_file=auth_file)
    w.mine = pupils.create_pupil({"first_name": "Ann", "last_name": "Mine", "year_group": "3",
                                  "class_name": "3A", "medical_notes": "secret-medical",
                                  "send_status": "yes"})
    w.other = pupils.create_pupil({"first_name": "Otto", "last_name": "Other",
                                   "year_group": "3", "class_name": "3B"})
    w.left = pupils.create_pupil({"first_name": "Lee", "last_name": "Left", "year_group": "3",
                                  "class_name": "3A"})
    pupils.set_roll_status(w.left.pupil_id, pupils.ROLL_STATUSES[2])

    def account(username, role, *, email=None, journey=None):
        conn = auth_db.connect()
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, display_name, email, is_active, "
                "journey_id) VALUES (?, 'x', ?, ?, 1, ?)",
                (username, username.title(), email, journey))
            uid = cur.lastrowid
            conn.execute("INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                         (uid, "primary", role))
            conn.commit()
        finally:
            conn.close()
        return SimpleNamespace(current_user={
            "id": uid, "user_id": uid, "username": username, "display_name": username,
            "systems": [{"system_key": "primary", "role": role}]})

    w.account = account
    w.student = account(w.mine.pupil_id, "student")
    w.other_student = account(w.other.email, "student")
    w.unlinked_student = account("student3", "student")
    w.parent = account("parent.mine", "parent")
    w.other_parent = account("parent.other", "parent")
    w.unlinked_parent = account("parent3", "parent")
    w.admin = account("office", "admin")
    w.teacher = account("teach", "teacher")
    links = ParentChildLinkService(str(auth_file))
    links.link_child(w.parent.current_user["id"], w.mine.pupil_id, "primary")
    links.link_child(w.other_parent.current_user["id"], w.other.pupil_id, "primary")

    w.teacher_a = staff_data.create_staff({"first_name": "Tia", "last_name": "Teach",
                                           "email": "tia@school.example"})
    w.teacher_b = staff_data.create_staff({"first_name": "Ben", "last_name": "Teach",
                                           "email": "ben@school.example"})
    for name, member in (("3A", w.teacher_a), ("3B", w.teacher_b)):
        made = classes_data.create({"name": name, "year_group": "3"})
        class_teachers.create({"class_id": made.class_id, "staff_name": member.full_name,
                               "staff_id": member.staff_id, "academic_year": "2026-27",
                               "role": "Class Teacher", "is_primary": True})

    subject = subjects_data.create({"code": "MAT", "name": "Maths", "key_stage": "KS2"})
    w.subject_id = subject.subject_id
    timetable_data.create_slot({"year_group": "3", "form_group": "3A",
                                "subject_id": w.subject_id, "day_of_week": "Mon", "period": 1,
                                "teacher": "Ms Teach", "notes": "secret-slot-note"})
    timetable_data.create_slot({"year_group": "3", "form_group": "3B",
                                "subject_id": w.subject_id, "day_of_week": "Tue", "period": 2,
                                "room": "other-class-room"})
    due = (date.today() + timedelta(days=7)).isoformat()
    set_work = homework_data.create_assignment({
        "title": "Times tables", "subject_id": w.subject_id, "year_group": "3",
        "form_group": "3A", "due_date": due, "status": "Set",
        "notes": "secret-homework-note", "instructions": "Learn them"})
    homework_data.create_assignment({"title": "Unreleased draft", "subject_id": w.subject_id,
                                     "year_group": "3", "due_date": due, "status": "Draft"})
    homework_data.create_assignment({"title": "Other class work", "subject_id": w.subject_id,
                                     "year_group": "3", "form_group": "3B", "due_date": due,
                                     "status": "Set"})
    homework_data.upsert_submission(set_work.assignment_id, w.mine.pupil_id, {
        "status": "Graded", "grade": "A", "mark_pct": 90, "feedback": "Well done"})
    reading_levels.record_assessment(w.mine.pupil_id, {
        "band": "Blue", "status": "secure", "assessed_on": "2026-10-01",
        "book_title": "My Book", "notes": "secret-reading-note"})
    reading_levels.record_assessment(w.other.pupil_id, {
        "band": "Red", "status": "working", "assessed_on": "2026-10-02",
        "book_title": "Other Book"})
    attendance_data.record_mark(w.mine.pupil_id, "2026-10-05", "AM", "/", notes="secret-att-note")
    attendance_data.record_mark(w.other.pupil_id, "2026-10-05", "AM", "O")
    assessment_data.create({"pupil_id": w.mine.pupil_id, "academic_year": "2026-27",
                            "term": "Autumn", "subject": "Maths", "grade": "EXS",
                            "comment": "secret-assess-comment"})
    published = reports_data.create({"pupil_id": w.mine.pupil_id, "academic_year": "2026-27",
                                     "term": "Autumn", "headline": "Good term",
                                     "notes": "secret-report-note"})
    reports_data.publish(published.report_id)
    reports_data.create({"pupil_id": w.mine.pupil_id, "academic_year": "2026-27",
                         "term": "Spring", "headline": "Draft headline"})
    trip = trips_data.create_trip({"name": "Zoo", "start_date": due,
                                   "status": "Open for Booking", "notes": "secret-trip-note"})
    w.my_booking = trips_data.create_booking(trip.trip_id, {
        "student_id": w.mine.pupil_id, "medical_note": "secret-trip-medical"})
    w.other_booking = trips_data.create_booking(trip.trip_id, {"student_id": w.other.pupil_id})
    w.evening = evenings.create_event({
        "name": "Autumn evening", "event_date": due, "start_time": "16:00",
        "end_time": "17:00", "slot_minutes": 10, "status": "Open for Booking"})
    w.closed_evening = evenings.create_event({
        "name": "Not open", "event_date": due, "start_time": "16:00", "end_time": "17:00",
        "slot_minutes": 10, "status": "Scheduled"})
    return w


@pytest.fixture
def world(tmp_path, monkeypatch):
    return build_world(tmp_path, monkeypatch)


# ── Who is who ─────────────────────────────────────────────────────

def test_student_login_maps_to_their_pupil_by_exact_id_or_school_email(world):
    assert data.my_pupil(world.student).pupil_id == world.mine.pupil_id
    assert data.my_pupil(world.other_student).pupil_id == world.other.pupil_id


def test_unlinked_student_sees_nothing(world):
    for read in (data.my_pupil, data.timetable, data.homework, data.reading_log):
        with pytest.raises(NoRecordLink):
            read(world.unlinked_student)


def test_a_name_never_links_a_login(world):
    by_name = world.account("Ann Mine", "student")
    with pytest.raises(NoRecordLink):
        data.my_pupil(by_name)


def test_partial_id_does_not_link_a_login(world):
    partial = world.account(world.mine.pupil_id[:-1], "student")
    with pytest.raises(NoRecordLink):
        data.my_pupil(partial)


def test_login_matching_two_pupils_sees_nothing(world):
    conn = auth_db.connect()
    try:
        conn.execute(
            "INSERT INTO student_journey (journey_id, primary_student_id, legal_first_name, "
            "legal_last_name, current_system, status) VALUES ('j-clash', ?, 'X', 'Y', "
            "'primary', 'active')", (world.other.pupil_id,))
        conn.commit()
    finally:
        conn.close()
    clash = world.account(world.mine.pupil_id.lower(), "student", journey="j-clash")
    with pytest.raises(NoRecordLink, match="more than one"):
        data.my_pupil(clash)


def test_learner_link_alone_maps_to_one_pupil(world):
    conn = auth_db.connect()
    try:
        conn.execute(
            "INSERT INTO student_journey (journey_id, primary_student_id, legal_first_name, "
            "legal_last_name, current_system, status) VALUES ('j-one', ?, 'X', 'Y', "
            "'primary', 'active')", (world.mine.pupil_id,))
        conn.commit()
    finally:
        conn.close()
    linked = world.account("friendly.name", "student", journey="j-one")
    assert data.my_pupil(linked).pupil_id == world.mine.pupil_id


def test_student_who_has_left_sees_nothing(world):
    login = world.account(world.left.pupil_id, "student")
    with pytest.raises(NoRecordLink, match="on roll"):
        data.timetable(login)


def test_no_session_or_a_forged_session_sees_nothing(world):
    for auth in (SimpleNamespace(current_user=None), SimpleNamespace(),
                 SimpleNamespace(current_user={"username": world.mine.pupil_id})):
        with pytest.raises(OwnRecordError):
            data.my_pupil(auth)
    # The right id with someone else's username.
    forged = SimpleNamespace(current_user={
        "id": world.unlinked_student.current_user["id"], "username": world.mine.pupil_id})
    with pytest.raises(RecordRefused):
        data.my_pupil(forged)


def test_deactivated_account_is_refused_at_once(world):
    assert data.timetable(world.student)
    conn = auth_db.connect()
    try:
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?",
                     (world.student.current_user["id"],))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(RecordRefused):
        data.timetable(world.student)


def test_role_comes_from_the_database_not_the_session(world):
    claims_parent = SimpleNamespace(current_user={
        **world.student.current_user,
        "systems": [{"system_key": "primary", "role": "parent"}]})
    with pytest.raises(RecordRefused):
        data.my_children(claims_parent)


def test_staff_and_admin_have_no_own_records(world):
    for auth in (world.admin, world.teacher):
        with pytest.raises(RecordRefused):
            data.timetable(auth)
        with pytest.raises(RecordRefused):
            data.attendance(auth, world.mine.pupil_id)


# ── One pupil cannot reach another ─────────────────────────────────

def test_student_cannot_pass_another_pupils_id(world):
    for read in (data.timetable, data.homework, data.reading_log):
        with pytest.raises(RecordRefused):
            read(world.student, world.other.pupil_id)


def test_student_cannot_use_the_parent_reads(world):
    for read in (data.attendance, data.assessment, data.reports, data.consent_answers):
        with pytest.raises(RecordRefused):
            read(world.student, world.mine.pupil_id)


def test_student_timetable_is_their_class_only(world):
    rows = data.timetable(world.student)
    assert [r.day for r in rows] == ["Mon"]
    assert "other-class-room" not in repr(rows)


def test_student_homework_is_theirs_and_set(world):
    rows = data.homework(world.student)
    assert [r.title for r in rows] == ["Times tables"]
    assert rows[0].grade == "A" and rows[0].feedback == "Well done"
    assert data.homework(world.other_student)[0].title == "Other class work"


def test_reading_log_is_their_own(world):
    current, history = data.reading_log(world.student)
    assert current.band == "Blue" and [h.book_title for h in history] == ["My Book"]
    assert "Other Book" not in repr(data.reading_log(world.student))


# ── A parent cannot reach another family ───────────────────────────

def test_parent_sees_only_their_own_children(world):
    assert [c.pupil_id for c in data.my_children(world.parent)] == [world.mine.pupil_id]


def test_parent_cannot_reach_another_familys_child(world):
    for read in (data.attendance, data.assessment, data.reports, data.consent_answers,
                 data.trip_consents, data.evening_options, data.evening_bookings,
                 data.evening_teachers):
        with pytest.raises(RecordRefused):
            read(world.parent, world.other.pupil_id)


def test_unlinked_parent_sees_nothing(world):
    assert data.my_children(world.unlinked_parent) == []
    with pytest.raises(NoRecordLink):
        data.attendance(world.unlinked_parent, world.mine.pupil_id)


def test_ended_link_takes_effect_on_the_next_read(world):
    assert data.attendance(world.parent, world.mine.pupil_id)
    ParentChildLinkService(str(world.auth_file)).unlink_child(
        world.parent.current_user["id"], world.mine.pupil_id, "primary")
    with pytest.raises(OwnRecordError):
        data.attendance(world.parent, world.mine.pupil_id)


def test_missing_links_table_is_nobody_linked_and_is_not_created(world):
    conn = sqlite3.connect(world.auth_file)
    conn.execute("DROP TABLE parent_child_links")
    conn.commit()
    conn.close()
    assert data.my_children(world.parent) == []
    conn = sqlite3.connect(world.auth_file)
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'parent_child_links'"
                        ).fetchone() is None
    conn.close()


def test_link_in_another_system_does_not_count(world):
    ParentChildLinkService(str(world.auth_file)).link_child(
        world.unlinked_parent.current_user["id"], world.mine.pupil_id, "secondary")
    assert data.my_children(world.unlinked_parent) == []


def test_only_the_childs_own_marks_are_returned(world):
    s = data.attendance(world.parent, world.mine.pupil_id)
    assert s.total_sessions == 1 and s.present == 1
    assert [m.date for m in s.marks] == ["2026-10-05"]


def test_draft_reports_are_never_shown(world):
    rows = data.reports(world.parent, world.mine.pupil_id)
    assert [r.headline for r in rows] == ["Good term"]


# ── What is left out ───────────────────────────────────────────────

def test_no_staff_notes_medical_or_send_detail_reach_any_screen(world):
    seen = repr((
        data.my_pupil(world.student), data.timetable(world.student),
        data.homework(world.student), data.reading_log(world.student),
        data.my_children(world.parent),
        data.attendance(world.parent, world.mine.pupil_id),
        data.assessment(world.parent, world.mine.pupil_id),
        data.reports(world.parent, world.mine.pupil_id),
        data.consent_answers(world.parent, world.mine.pupil_id),
        data.trip_consents(world.parent, world.mine.pupil_id),
    ))
    assert "secret" not in seen
    assert "Otto" not in seen


def test_free_slots_name_nobody(world):
    pid = world.other.pupil_id
    data.book_evening(world.other_parent, pid, world.evening.event_id,
                      world.teacher_b.staff_id, "16:00")
    slots = data.evening_slots(world.other_parent, pid, world.evening.event_id,
                               world.teacher_b.staff_id)
    assert "16:00" not in slots
    assert all(isinstance(s, str) for s in slots)


# ── Writes ─────────────────────────────────────────────────────────

def _feed_actions(pupil_id):
    return [e.action for e in activity_feed.events_for_entity("student", pupil_id)]


def test_parent_answers_a_consent_form_with_history_and_audit(world):
    pid = world.mine.pupil_id
    answers = {a.purpose: a.answer for a in data.consent_answers(world.parent, pid)}
    assert answers["Photography / Video"] == "Not answered"

    data.answer_consent(world.parent, pid, "Photography / Video", True)
    assert {a.purpose: a.answer for a in data.consent_answers(world.parent, pid)
            }["Photography / Video"] == "Given"
    data.answer_consent(world.parent, pid, "Photography / Video", False)
    assert {a.purpose: a.answer for a in data.consent_answers(world.parent, pid)
            }["Photography / Video"] == "Not given"

    rows = gdpr.list_consents(subject_ref=pid, purpose="Photography / Video")
    assert len(rows) == 2 and not any(r.is_active for r in rows)
    assert _feed_actions(pid).count("parent_consent_answered") == 2
    assert all(r.source == "Parent account parent.mine" for r in rows)


def test_parent_cannot_answer_for_another_child_or_an_unlisted_form(world):
    with pytest.raises(RecordRefused):
        data.answer_consent(world.parent, world.other.pupil_id, "Photography / Video", True)
    with pytest.raises(RecordRefused):
        data.answer_consent(world.parent, world.mine.pupil_id, "Marketing", True)
    assert gdpr.list_consents(subject_ref=world.other.pupil_id) == []
    assert gdpr.list_consents(subject_ref=world.mine.pupil_id) == []


def test_parent_answers_trip_consent_for_own_booking_only(world):
    pid = world.mine.pupil_id
    saved = data.answer_trip_consent(world.parent, pid, world.my_booking.booking_id, True)
    assert saved.consent_received is True
    assert trips_data.get_booking(world.my_booking.booking_id).consent_received is True
    assert "parent_trip_consent_answered" in _feed_actions(pid)

    with pytest.raises(RecordRefused):
        data.answer_trip_consent(world.parent, pid, world.other_booking.booking_id, True)
    assert trips_data.get_booking(world.other_booking.booking_id).consent_received is False


def test_parent_books_a_slot_with_their_childs_teacher(world):
    pid = world.mine.pupil_id
    options = data.evening_options(world.parent, pid)
    assert [e.name for e in options] == ["Autumn evening"]
    teachers = data.evening_teachers(world.parent, pid)
    assert [t.staff_id for t in teachers] == [world.teacher_a.staff_id]

    saved = data.book_evening(world.parent, pid, world.evening.event_id,
                              world.teacher_a.staff_id, "16:10")
    assert saved.slot_time == "16:10" and saved.status == "Booked"
    assert [b.slot_time for b in data.evening_bookings(world.parent, pid)] == ["16:10"]
    assert "parent_evening_booked" in _feed_actions(pid)


def test_booking_refuses_other_teachers_closed_events_taken_slots_and_doubles(world):
    pid = world.mine.pupil_id
    event = world.evening.event_id
    with pytest.raises(RecordRefused):
        data.book_evening(world.parent, pid, event, world.teacher_b.staff_id, "16:10")
    with pytest.raises(RecordRefused):
        data.book_evening(world.parent, pid, world.closed_evening.event_id,
                          world.teacher_a.staff_id, "16:10")
    with pytest.raises(RecordRefused):
        data.book_evening(world.parent, world.other.pupil_id, event,
                          world.teacher_b.staff_id, "16:10")
    with pytest.raises(RecordRefused):
        data.book_evening(world.parent, pid, event, world.teacher_a.staff_id, "99:99")
    data.book_evening(world.parent, pid, event, world.teacher_a.staff_id, "16:10")
    with pytest.raises(RecordRefused, match="already have a booking"):
        data.book_evening(world.parent, pid, event, world.teacher_a.staff_id, "16:20")


def test_students_cannot_write(world):
    pid = world.mine.pupil_id
    with pytest.raises(RecordRefused):
        data.answer_consent(world.student, pid, "Photography / Video", True)
    with pytest.raises(RecordRefused):
        data.book_evening(world.student, pid, world.evening.event_id,
                          world.teacher_a.staff_id, "16:10")


# ── Linking a parent ───────────────────────────────────────────────

def test_only_an_admin_can_link_a_parent_login(world):
    pid = world.mine.pupil_id
    for auth in (world.teacher, world.parent, world.student):
        with pytest.raises(RecordRefused):
            data.link_parent_login(auth, "parent3", pid)
    child = data.link_parent_login(world.admin, "parent3", pid)
    assert child.pupil_id == pid
    assert [c.pupil_id for c in data.my_children(world.unlinked_parent)] == [pid]
    assert [c.pupil_id for c in data.linked_children_of(world.admin, "parent3")] == [pid]

    conn = auth_db.connect()
    try:
        audited = conn.execute(
            "SELECT COUNT(*) FROM security_audit_log WHERE event_type = 'identity.parent_linked' "
            "AND username = 'office'").fetchone()[0]
    finally:
        conn.close()
    assert audited == 1
    assert data.unlink_parent_login(world.admin, "parent3", pid) is True
    assert data.my_children(world.unlinked_parent) == []


def test_link_refuses_a_login_that_is_not_a_parent_here_and_an_unknown_pupil(world):
    with pytest.raises(ValueError):
        data.link_parent_login(world.admin, "teach", world.mine.pupil_id)
    with pytest.raises(ValueError):
        data.link_parent_login(world.admin, "parent%", world.mine.pupil_id)
    with pytest.raises(ValueError):
        data.link_parent_login(world.admin, "parent3", "P%")


# ── Menus ──────────────────────────────────────────────────────────

def _principal(role):
    return access.from_auth(SimpleNamespace(current_user={
        "username": "someone", "systems": [{"system_key": "primary", "role": role}]}))


def test_screens_open_for_their_own_role_only():
    student = access.POLICY.own_labels_for("student")
    parent = access.POLICY.own_labels_for("parent")
    assert student == {"My Timetable", "My Homework", "My Reading Log"}
    assert parent == {"Child Attendance", "Child Assessment", "Child Reports", "Consent Forms",
                      "Parents' Evening Booking"}
    for label in student:
        assert _principal("student").can_open(label)
        assert not _principal("parent").can_open(label)
    for label in parent:
        assert _principal("parent").can_open(label)
        assert not _principal("student").can_open(label)
    for role in ("admin", "teacher", "staff", "", "alumni"):
        for label in student | parent:
            assert not _principal(role).can_open(label)


def test_admin_and_teacher_menus_are_untouched():
    admin = _principal("admin")
    assert admin.visible_menu(gui_main.NAV_CATEGORIES) == list(gui_main.NAV_CATEGORIES)
    assert admin.visible_menu(cli_main.CATEGORIES, labels_only=True) == list(cli_main.CATEGORIES)
    teacher = _principal("teacher")
    assert teacher.visible_menu(gui_main.NAV_CATEGORIES) == teacher.filter_menu(
        gui_main.NAV_CATEGORIES)
    assert teacher.visible_menu(cli_main.CATEGORIES, labels_only=True) == teacher.filter_menu(
        cli_main.CATEGORIES)
    every_label = {i if isinstance(i, str) else i[0] for _c, items in gui_main.NAV_CATEGORIES
                   for i in items}
    assert not every_label & access.POLICY.own_labels


def test_learner_menus_show_their_screens_then_their_account():
    student = _principal("student").visible_menu(gui_main.NAV_CATEGORIES)
    assert [name for name, _ in student] == ["My School", "System"]
    parent = _principal("parent").visible_menu(cli_main.CATEGORIES, labels_only=True)
    assert [name for name, _ in parent] == ["My Child", "System"]
    assert all(isinstance(i, str) for _n, items in parent for i in items)


def test_every_own_handler_exists_on_the_window():
    for handler in access.POLICY.own_handlers():
        assert callable(getattr(gui_main.PrimarySchoolMainGUI, handler))


def test_cli_screens_print_the_message_and_no_records_when_unlinked(world, capsys, monkeypatch):
    from education_system.systems.primary.interfaces.cli.learners.own_records import (
        own_records_cli,
    )
    monkeypatch.setattr("builtins.input", lambda _m="": "")
    for label in access.POLICY.own_labels_for("student"):
        assert own_records_cli.dispatch(label, auth=world.unlinked_student)
    for label in access.POLICY.own_labels_for("parent"):
        assert own_records_cli.dispatch(label, auth=world.unlinked_parent)
    out = capsys.readouterr().out
    assert "not linked" in out
    assert "Maths" not in out and world.mine.pupil_id not in out


def test_cli_parent_contacts_offers_linking_to_admins_only(world):
    from education_system.systems.primary.interfaces.cli.operations.communications.parent_contacts import (
        parent_contacts_cli,
    )
    def labels(auth):
        return [label for label, _h in parent_contacts_cli._menu_for(auth)]

    assert "Link Parent Login" in labels(world.admin)
    assert "Link Parent Login" not in labels(world.teacher)
    assert "Link Parent Login" not in labels(None)
