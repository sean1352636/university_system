"""Interview rooms, slots and bookings: past times, capacity, room and
panel clashes, double booking, and history kept on reschedule/cancel."""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    interviews as iv,
)

TOMORROW = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()


@pytest.fixture
def staff(admdb, sign_in):
    return sign_in("adm1")


@pytest.fixture
def room(staff):
    return iv.add_room("Room 12", capacity=2)


def _slot(room=None, start="10:00", end="10:30", panel=("mr.x",), **over):
    return iv.create_slot({"slot_date": TOMORROW, "start_time": start,
                           "end_time": end, "panel": list(panel),
                           "room_id": room.room_id if room else None, **over})


def test_rooms_are_listed_and_removed_softly(room):
    assert [r.name for r in iv.list_rooms()] == ["Room 12"]
    with pytest.raises(adm.ValidationError, match="already listed"):
        iv.add_room("room 12")
    assert iv.import_room_names(["Room 12", "Library", "TBC", ""]) == 1
    s = _slot(room)
    with pytest.raises(adm.ValidationError, match="upcoming"):
        iv.remove_room(room.room_id)
    iv.cancel_slot(s.slot_id, reason="not needed")
    assert iv.remove_room(room.room_id)
    assert "Room 12" not in [r.name for r in iv.list_rooms()]
    assert "Room 12" in [r.name for r in iv.list_rooms(active_only=False)]


def test_slot_rules(room):
    with pytest.raises(adm.ValidationError, match="past"):
        iv.create_slot({"slot_date": "2020-01-01", "start_time": "10:00",
                        "end_time": "10:30", "panel": ["a"]})
    with pytest.raises(adm.ValidationError, match="after the start"):
        _slot(start="11:00", end="10:00")
    with pytest.raises(adm.ValidationError, match="panel"):
        _slot(panel=())
    with pytest.raises(adm.ValidationError, match="holds 2"):
        _slot(room, capacity=3)
    _slot(room, panel=("mr.x", "ms.y"))
    with pytest.raises(adm.ValidationError, match="Room 12 is used"):
        _slot(room, start="10:15", end="10:45", panel=("mr.z",))
    with pytest.raises(adm.ValidationError, match="ms.y is on slot"):
        _slot(start="10:15", end="10:45", panel=("MS.Y",))
    assert _slot(room, start="10:30", end="11:00", panel=("ms.y",))


def test_booking_capacity_and_double_booking(room, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    b = adm.create_applicant(applicant_payload(first_name="Bo",
                                               email="bo@example.com"))
    s1 = _slot(room)
    s2 = _slot(room, start="11:00", end="11:30")
    adm.schedule_interview(a.applicant_id, slot_id=s1.slot_id)
    got = adm.get_applicant(a.applicant_id)
    assert (got.status, got.interview_date, got.interviewer) == (
        "Interview Scheduled", TOMORROW, "mr.x")
    with pytest.raises(adm.ValidationError, match="full"):
        iv.book(b.applicant_id, s1.slot_id)
    with pytest.raises(adm.ValidationError, match="already booked"):
        iv.book(a.applicant_id, s2.slot_id)
    with pytest.raises(adm.ValidationError, match="slot"):
        adm.reschedule_interview(a.applicant_id, new_date=TOMORROW)


def test_reschedule_and_cancel_keep_history(room, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    s1 = _slot(room)
    s2 = _slot(room, start="11:00", end="11:30")
    iv.book(a.applicant_id, s1.slot_id)
    adm.reschedule_interview(a.applicant_id, slot_id=s2.slot_id, reason="clash")
    assert [(h.slot_id, h.status) for h in iv.booking_history(a.applicant_id)] \
        == [(s2.slot_id, "Booked"), (s1.slot_id, "Rescheduled")]
    assert iv.get_slot(s1.slot_id).booked == 0
    adm.cancel_interview(a.applicant_id, reason="ill")
    assert adm.get_applicant(a.applicant_id).status == "Under Review"
    assert [h.status for h in iv.booking_history(a.applicant_id)] == [
        "Cancelled", "Rescheduled"]


def test_bare_dates_cannot_be_in_the_past(staff, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    with pytest.raises(adm.ValidationError, match="past"):
        adm.schedule_interview(a.applicant_id, interview_date="2020-01-01")
    adm.schedule_interview(a.applicant_id, interview_date=TOMORROW)
    with pytest.raises(adm.ValidationError, match="past"):
        adm.reschedule_interview(a.applicant_id, new_date="2020-01-01")


def test_attended_and_no_show_close_the_booking(room, applicant_payload):
    a = adm.create_applicant(applicant_payload())
    b = adm.create_applicant(applicant_payload(first_name="Bo",
                                               email="bo@example.com"))
    s = _slot(room, capacity=2)
    iv.book(a.applicant_id, s.slot_id)
    iv.book(b.applicant_id, s.slot_id)
    adm.record_interview(a.applicant_id, interview_notes="good")
    adm.mark_no_show(b.applicant_id)
    assert iv.booking_history(a.applicant_id)[0].status == "Attended"
    assert iv.booking_history(b.applicant_id)[0].status == "No-show"
    assert iv.active_booking(a.applicant_id) is None
