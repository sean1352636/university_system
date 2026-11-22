"""Parents' evenings (modules.communication.domain.parents_evenings)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.communication.domain import parents_evenings as PE
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
BOB = Principal(username="bob", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Maths"), ("bob", "Bob English"), ("cat", "Cat Science"))]
TODAY = dt.date.today().isoformat()


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: LOGINS)
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=9, form="9A", **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Kid{_n}", "legal_last_name": f"Family{_n:03d}",
        "date_of_birth": "2012-01-15", "gender": "Female", "year_group": year,
        "form_group": form, "admission_date": "2023-09-01", **extra}, actor=ADMIN)


@pytest.fixture
def school():
    ava, ben, cal = _pupil(), _pupil(form="9B"), _pupil()
    # Ava and Ben are siblings (same mum); Cal has no e-mail contact.
    for p in (ava, ben):
        C.add_contact(p.pupil_id, {"full_name": "Mum Family", "relationship": "Mother",
                                   "email": "mum@home.org"}, actor=ADMIN)
    C.add_contact(cal.pupil_id, {"full_name": "Dad Cal", "relationship": "Father",
                                 "phone": "01234 567890"}, actor=ADMIN)
    maths = S.create({"code": "MATH", "name": "Maths", "is_core": True}, actor=ADMIN)
    eng = S.create({"code": "ENG", "name": "English", "is_core": True}, actor=ADMIN)
    ma = TG.create({"code": "9x/Ma1", "subject_id": maths.subject_id, "year_group": 9,
                    "teacher_username": "ann"}, actor=ADMIN)
    en = TG.create({"code": "9x/En1", "subject_id": eng.subject_id, "year_group": 9,
                    "teacher_username": "bob"}, actor=ADMIN)
    TG.create({"code": "8x/Ma1", "subject_id": maths.subject_id, "year_group": 8,
               "teacher_username": "cat"}, actor=ADMIN)
    TG.add_pupils([ava.pupil_id, ben.pupil_id, cal.pupil_id], ma.group_id, actor=ADMIN)
    TG.add_pupils([ava.pupil_id, ben.pupil_id], en.group_id, actor=ADMIN)
    return {"ava": ava, "ben": ben, "cal": cal}


def _event(**extra):
    return PE.create_event({"name": "Year 9 evening", "event_date": TODAY, "year_group": "9",
                            "location": "Main hall", "start_time": "16:00",
                            "end_time": "17:00", "slot_minutes": 10,
                            "break_slots": "16:30", **extra}, actor=ADMIN)


def test_event_rules_slots_and_teachers_from_teaching_groups(school):
    e = _event()
    assert e.year_label == "Year 9" and e.status == "Scheduled"
    assert PE.event_slots(e) == ["16:00", "16:10", "16:20", "16:40", "16:50"]
    assert [t.teacher_key for t in PE.list_teachers(e.event_id)] == ["ann", "bob"]
    assert PE.get_teacher(e.event_id, "ann").groups == "9x/Ma1"
    with pytest.raises(PE.ValidationError) as ex:
        PE.create_event({"name": "", "event_date": "x", "start_time": "18:00",
                         "end_time": "17:00", "slot_minutes": 99, "mode": "Online"},
                        actor=ADMIN)
    text = " ".join(ex.value.problems)
    for bit in ("Name is required", "Date must be", "Slot length", "End time must be after",
                "meeting link"):
        assert bit in text
    with pytest.raises(PE.ValidationError) as ex:
        _event(break_slots="16:05")
    assert "isn't one of the slots" in " ".join(ex.value.problems)
    with pytest.raises(PE.PermissionDenied):
        _event_as = PE.create_event({"name": "x"}, actor=ANN)  # noqa: F841
    added = PE.add_teacher(e.event_id, actor=ADMIN, username="cat", room="H1")
    assert added.source == "added" and added.teacher_name == "Cat Science"
    assert PE.sync_teachers(e.event_id, actor=ADMIN)["teachers"] == 3   # hand-added kept
    assert [x["teacher"].teacher_key for x in PE.teachers_for_pupil(
        e.event_id, school["cal"].pupil_id)] == ["ann"]


def test_no_double_booking_of_teacher_pupil_or_family(school):
    e = PE.set_event_status(_event().event_id, "Open for Booking", actor=ADMIN)
    ava, ben, cal = school["ava"], school["ben"], school["cal"]
    b = PE.book(e.event_id, ava.pupil_id, "ann", "16:00", actor=ADMIN, parent_name="Mum")
    assert b.status == "Booked" and b.teacher_name == "Ann Maths"
    for args, bit in (((cal.pupil_id, "ann", "16:00"), "already has"),
                      ((ava.pupil_id, "ann", "16:10"), "already has an appointment with"),
                      ((ben.pupil_id, "bob", "16:00"), "family is already booked"),
                      ((ava.pupil_id, "bob", "16:30"), "is a break"),
                      ((ava.pupil_id, "bob", "16:05"), "isn't a slot")):
        with pytest.raises(PE.ValidationError) as ex:
            PE.book(e.event_id, *args, actor=ADMIN)
        assert bit in " ".join(ex.value.problems), bit
    assert [p.pupil_id for p in PE.siblings(ava.pupil_id)] == [ben.pupil_id]
    assert "16:00" not in PE.free_slots(e.event_id, "bob", pupil_id=ben.pupil_id)
    # A teacher books their own appointments only, and only with pupils they teach.
    with pytest.raises(PE.PermissionDenied):
        PE.book(e.event_id, cal.pupil_id, "bob", "16:10", actor=ANN)
    with pytest.raises(PE.ValidationError) as ex:
        PE.book(e.event_id, cal.pupil_id, "bob", "16:10", actor=BOB)
    assert "doesn't teach" in " ".join(ex.value.problems)
    own = PE.book(e.event_id, cal.pupil_id, "ann", "16:10", actor=ANN)
    # Cancelling frees the slot; a teacher's break can't cover a booking.
    with pytest.raises(PE.ValidationError):
        PE.update_teacher(e.event_id, "ann", {"breaks": "16:10"}, actor=ANN)
    PE.cancel_booking(own.booking_id, actor=ANN)
    assert "16:10" in PE.free_slots(e.event_id, "ann")
    PE.update_teacher(e.event_id, "ann", {"breaks": "16:50", "room": "M2"}, actor=ANN)
    with pytest.raises(PE.PermissionDenied):
        PE.update_teacher(e.event_id, "ann", {"room": "x"}, actor=BOB)
    sched = PE.teacher_schedule(e.event_id, "ann")
    assert [x["kind"] for x in sched] == ["booked", "free", "free", "break", "free", "break"]
    assert "Kid" in PE.teacher_schedule_text(e.event_id, "ann")
    # Changing the times can't strand a booking.
    with pytest.raises(PE.ValidationError) as ex:
        PE.update_event(e.event_id, {"start_time": "16:30"}, actor=ADMIN)
    assert "outside the new slots" in " ".join(ex.value.problems)


def test_family_books_through_the_portal(school):
    ava, cal = school["ava"], school["cal"]
    mum = Principal(username=PA.links_for_pupil(ava.pupil_id)[0].username, role="parent")
    e = _event()
    with pytest.raises(PE.ValidationError) as ex:
        PE.book_for_family(mum, e.event_id, ava.pupil_id, "bob", "16:00")
    assert "Booking isn't open" in " ".join(ex.value.problems)
    PE.set_event_status(e.event_id, "Open for Booking", actor=ADMIN)
    with pytest.raises(PE.PermissionDenied):
        PE.book_for_family(mum, e.event_id, cal.pupil_id, "ann", "16:00")   # not her child
    b = PE.book_for_family(mum, e.event_id, ava.pupil_id, "bob", "16:00")
    assert b.booked_via == "portal" and b.booked_by == mum.username
    over = PE.family_overview(mum, ava.pupil_id)
    rows = {r["teacher_key"]: r for r in over[0]["teachers"]}
    assert rows["bob"]["booking"].booking_id == b.booking_id
    assert "16:00" not in rows["ann"]["free"]      # mum is with Bob then
    with pytest.raises(PE.ValidationError):
        PE.book_for_family(mum, e.event_id, school["ben"].pupil_id, "ann", "16:00")
    assert PE.cancel_for_family(mum, b.booking_id).status == "Cancelled"


def test_attendance_notes_emails_rates_and_export(school, tmp_path):
    ava, ben, cal = school["ava"], school["ben"], school["cal"]
    e = PE.set_event_status(_event().event_id, "Open for Booking", actor=ADMIN)
    inv = PE.send_invitations(e.event_id, actor=ADMIN)
    assert inv["emails"] == 1 and [p.pupil_id for p in inv["no_email"]] == [cal.pupil_id]
    with database.connect() as conn:
        body = conn.execute("SELECT body FROM email_recipients WHERE message_id = ?",
                            (inv["message_id"],)).fetchone()[0]
    assert f"{ava.legal_first_name} and {ben.legal_first_name}" in body
    a1 = PE.book(e.event_id, ava.pupil_id, "ann", "16:00", actor=ADMIN)
    PE.book(e.event_id, ben.pupil_id, "bob", "16:10", actor=ADMIN)
    PE.book(e.event_id, cal.pupil_id, "ann", "16:20", actor=ADMIN)
    sent = PE.email_schedules(e.event_id, actor=ADMIN)
    assert sent["emails"] == 1
    with database.connect() as conn:
        body = conn.execute("SELECT body FROM email_recipients WHERE message_id = ?",
                            (sent["message_id"],)).fetchone()[0]
    assert "16:00  Ann Maths" in body and "16:10  Bob English" in body   # siblings together
    done = PE.record_attendance(a1.booking_id, True, actor=ANN, teacher_notes="Going well")
    assert done.status == "Attended" and done.teacher_notes == "Going well"
    with pytest.raises(PE.PermissionDenied):
        PE.record_attendance(a1.booking_id, False, actor=BOB)
    rates = {r["group"]: r for r in PE.booking_rates(e.event_id, by="teacher")}
    assert rates["Ann Maths"]["pupils"] == 3 and rates["Ann Maths"]["booked"] == 2
    assert rates["Ann Maths"]["attended"] == 1
    forms = {r["group"]: r for r in PE.booking_rates(e.event_id, by="form")}
    assert forms["9A"]["rate"] == 100 and forms["9B"]["booked"] == 1
    s = PE.summarize_event(e.event_id)
    assert s.bookings == 3 and s.pupils_booked == 3 and s.capacity == 10
    assert PE.summary().total_bookings == 3
    with pytest.raises(PE.ValidationError):
        PE.delete_event(e.event_id, actor=ADMIN)       # attendance recorded
    out = tmp_path / "pe.csv"
    assert PE.export_csv(out, actor=ADMIN, event_id=e.event_id) == 3
    assert list(csv.reader(out.open()))[0][0] == "id"
    assert PE.export_schedule_csv(e.event_id, tmp_path / "ann.csv", actor=ANN,
                                  teacher_key="ann") == 6
    assert any(h["action"] == "book" for h in PE.history(e.event_id))
    with pytest.raises(PE.PermissionDenied):
        PE.export_csv(out, actor=Principal(username="kid", role="student"))
