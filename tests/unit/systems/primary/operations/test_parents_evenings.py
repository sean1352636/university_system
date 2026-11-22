"""Parents' evenings (domain.operations.communications.parents_evenings)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.communications.parents_evenings import (
    parents_evenings as PE,
)
from education_system.systems.primary.domain.staff import staff as S

TODAY = dt.date.today()


def _d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _pupil(first="Ada", last="Lovelace"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": "4",
                           "date_of_birth": "2017-05-05"})


def _staff(first="Tom", last="Teach"):
    return S.create_staff({"first_name": first, "last_name": last})


def _event(name="Autumn parents' evening", **extra):
    data = {"name": name, "event_date": "2026-11-20", "start_time": "16:00",
            "end_time": "17:00", "slot_minutes": 10}
    data.update(extra)
    return PE.create_event(data)


def _book(event, pupil, teacher, slot="16:00", **extra):
    return PE.create_booking(event.event_id, {"student_id": pupil.pupil_id,
                                              "staff_id": teacher.staff_id,
                                              "slot_time": slot, **extra})


# ── events ──────────────────────────────────────────────────────────

def test_empty_database():
    assert PE.list_events() == []
    assert PE.list_bookings() == []
    assert PE.get_event(1) is None and PE.get_booking(1) is None
    assert PE.list_bookings_with_detail() == []
    s = PE.summary()
    assert s.total_events == 0 and s.total_bookings == 0 and s.next_event is None


def test_create_event_defaults_and_fields():
    e = _event(location=" Hall ", notes=" bring reports ")
    assert PE.get_event(e.event_id) == e
    assert e.year_group == "Whole School"
    assert e.status == "Scheduled"
    assert e.location == "Hall" and e.notes == "bring reports"
    assert (e.start_time, e.end_time, e.slot_minutes) == ("16:00", "17:00", 10)


def test_slot_minutes_defaults_to_ten():
    e = PE.create_event({"name": "x", "event_date": "2026-11-20",
                         "start_time": "16:00", "end_time": "16:30"})
    assert e.slot_minutes == 10
    assert PE.event_slots(e) == ["16:00", "16:10", "16:20"]


def test_event_slots_across_the_hour():
    e = _event(start_time="15:45", end_time="16:30", slot_minutes=15)
    assert PE.event_slots(e) == ["15:45", "16:00", "16:15"]


@pytest.mark.parametrize("field,value,msg", [
    ("name", " ", "Name is required"),
    ("event_date", "", "Event date is required"),
    ("event_date", "20/11/2026", "Event date must be YYYY-MM-DD"),
    ("year_group", "Year 9", "Year group must be one of"),
    ("start_time", "4pm", "Start time must be HH:MM"),
    ("end_time", "24:00", "End time must be HH:MM"),
    ("slot_minutes", "ten", "Slot minutes must be a whole number"),
    ("slot_minutes", 61, "between 1 and 60"),
    ("status", "Postponed", "Status must be one of"),
])
def test_event_validation(field, value, msg):
    with pytest.raises(PE.ValidationError, match=msg):
        _event(**{field: value})


def test_end_must_be_after_start():
    with pytest.raises(PE.ValidationError, match="End time must be after start time"):
        _event(start_time="17:00", end_time="17:00")


def test_window_must_divide_into_slots():
    with pytest.raises(PE.ValidationError,
                       match=r"window \(60 min\) must be a multiple of the slot length \(7"):
        _event(slot_minutes=7)


def test_primary_year_groups_accepted():
    for yg in ("Reception", "Year 6", "KS1", "KS2"):
        assert _event(yg, year_group=yg).year_group == yg


def test_update_event_merges():
    e = _event()
    u = PE.update_event(e.event_id, {"location": "Library", "end_time": "18:00"})
    assert u.location == "Library" and u.end_time == "18:00"
    assert u.name == e.name
    assert PE.set_event_status(e.event_id, "Open for Booking").status == "Open for Booking"
    with pytest.raises(PE.ValidationError, match="Status must be one of"):
        PE.set_event_status(e.event_id, "Done")
    with pytest.raises(PE.ValidationError, match="No event with id 404"):
        PE.update_event(404, {})


def test_window_cannot_shrink_past_existing_bookings():
    e = _event()
    _book(e, _pupil(), _staff(), "16:50")
    with pytest.raises(PE.ValidationError, match="1 existing booking"):
        PE.update_event(e.event_id, {"end_time": "16:30"})
    with pytest.raises(PE.ValidationError, match="1 existing booking"):
        PE.update_event(e.event_id, {"start_time": "17:00", "end_time": "18:00"})
    assert PE.update_event(e.event_id, {"end_time": "17:30"}).end_time == "17:30"


def test_list_events_filters_and_order():
    a = _event("a", event_date="2026-10-01", year_group="KS1")
    b = _event("b", event_date="2026-12-01", status="Open for Booking")
    c = _event("c", event_date="2026-11-01", status="Completed", year_group="KS1")
    assert [e.name for e in PE.list_events()] == ["b", "c", "a"]

    def names(**kw):
        return {e.name for e in PE.list_events(**kw)}

    assert names(year_group="KS1") == {"a", "c"}
    assert names(status="Completed") == {"c"}
    assert names(open_only=True) == {"a", "b"}
    assert names(date_from="2026-11-01") == {"b", "c"}
    assert names(date_to="2026-11-01") == {"a", "c"}
    assert (a.name, b.name, c.name) == ("a", "b", "c")


def test_list_events_refuses_bad_filters():
    with pytest.raises(PE.ValidationError, match="Year group must be one of"):
        PE.list_events(year_group="Year 10")
    with pytest.raises(PE.ValidationError, match="Status must be one of"):
        PE.list_events(status="Live")
    with pytest.raises(PE.ValidationError, match="date_from must be YYYY-MM-DD"):
        PE.list_events(date_from="1 Nov")


def test_deleting_an_event_removes_its_bookings():
    e = _event()
    other = _event("other")
    t = _staff()
    p = _pupil()
    _book(e, p, t)
    keep = _book(other, p, t)
    assert PE.delete_event(e.event_id) is True
    assert PE.get_event(e.event_id) is None
    assert [b.booking_id for b in PE.list_bookings()] == [keep.booking_id]
    assert PE.delete_event(e.event_id) is False


# ── bookings ────────────────────────────────────────────────────────

def test_create_booking_reads_back():
    e = _event()
    p, t = _pupil(), _staff()
    b = PE.create_booking(e.event_id, {"student_id": f" {p.pupil_id} ",
                                       "staff_id": t.staff_id.lower(),
                                       "slot_time": "16:20", "parent_name": " Mrs L ",
                                       "notes": " reading "})
    assert PE.get_booking(b.booking_id) == b
    assert b.student_id == p.pupil_id
    assert b.staff_id == t.staff_id
    assert b.slot_time == "16:20"
    assert b.status == "Booked"
    assert b.parent_name == "Mrs L" and b.notes == "reading"


def test_booking_needs_existing_event_pupil_and_staff():
    e = _event()
    p, t = _pupil(), _staff()
    with pytest.raises(PE.ValidationError, match="No event with id 404"):
        PE.create_booking(404, {"student_id": p.pupil_id, "staff_id": t.staff_id,
                                "slot_time": "16:00"})
    with pytest.raises(PE.ValidationError, match="Student ID is required"):
        PE.create_booking(e.event_id, {"staff_id": t.staff_id, "slot_time": "16:00"})
    with pytest.raises(PE.ValidationError, match="No student with id 0000000"):
        PE.create_booking(e.event_id, {"student_id": "0000000", "staff_id": t.staff_id,
                                       "slot_time": "16:00"})
    with pytest.raises(PE.ValidationError, match="Staff ID is required"):
        PE.create_booking(e.event_id, {"student_id": p.pupil_id, "slot_time": "16:00"})
    with pytest.raises(PE.ValidationError, match="No staff with id T0000000"):
        PE.create_booking(e.event_id, {"student_id": p.pupil_id, "staff_id": "t0000000",
                                       "slot_time": "16:00"})


@pytest.mark.parametrize("slot,msg", [("15:50", "within event window"),
                                      ("17:00", "within event window"),
                                      ("16:05", "align to 10-minute boundaries"),
                                      ("4:00", "Slot time must be HH:MM")])
def test_slot_must_be_inside_and_on_the_grid(slot, msg):
    e = _event()
    with pytest.raises(PE.ValidationError, match=msg):
        _book(e, _pupil(), _staff(), slot)


def test_booking_status_must_be_known():
    with pytest.raises(PE.ValidationError, match="Status must be one of"):
        _book(_event(), _pupil(), _staff(), status="Late")


def test_teacher_cannot_be_double_booked_in_a_slot():
    e = _event()
    t = _staff()
    _book(e, _pupil(), t, "16:10")
    with pytest.raises(PE.ValidationError, match="slot is already taken"):
        _book(e, _pupil("Bob", "Smith"), t, "16:10")
    # the same slot with another teacher, or at another event, is fine
    assert _book(e, _pupil("Cat", "Jones"), _staff("Sue", "Two"), "16:10").slot_time == "16:10"
    assert _book(_event("other"), _pupil("Dan", "Four"), t, "16:10").slot_time == "16:10"


def test_update_booking_and_status():
    e = _event()
    t = _staff()
    b = _book(e, _pupil(), t)
    u = PE.update_booking(b.booking_id, {"slot_time": "16:30", "notes": "moved"})
    assert u.slot_time == "16:30" and u.notes == "moved"
    assert PE.set_booking_status(b.booking_id, "Attended").status == "Attended"
    with pytest.raises(PE.ValidationError, match="Status must be one of"):
        PE.set_booking_status(b.booking_id, "Late")
    with pytest.raises(PE.ValidationError, match="No booking with id 404"):
        PE.update_booking(404, {})


def test_update_booking_into_a_taken_slot_is_refused():
    e = _event()
    t = _staff()
    _book(e, _pupil(), t, "16:00")
    b = _book(e, _pupil("Bob", "Smith"), t, "16:10")
    with pytest.raises(PE.ValidationError, match="slot is already taken"):
        PE.update_booking(b.booking_id, {"slot_time": "16:00"})
    with pytest.raises(PE.ValidationError, match="align to"):
        PE.update_booking(b.booking_id, {"slot_time": "16:15"})


def test_delete_booking():
    b = _book(_event(), _pupil(), _staff())
    assert PE.delete_booking(b.booking_id) is True
    assert PE.get_booking(b.booking_id) is None
    assert PE.delete_booking(b.booking_id) is False


def test_deleting_pupil_or_staff_clears_their_bookings():
    e = _event()
    p, q = _pupil(), _pupil("Bob", "Smith")
    t, u = _staff(), _staff("Sue", "Two")
    _book(e, p, t, "16:00")
    keep = _book(e, q, u, "16:00")
    _book(e, q, t, "16:10")
    P.delete_pupil(p.pupil_id)
    S.delete_staff(t.staff_id)
    assert [b.booking_id for b in PE.list_bookings()] == [keep.booking_id]


def test_list_bookings_filters_and_order():
    e, f = _event(), _event("other")
    p, q = _pupil(), _pupil("Bob", "Smith")
    t, u = _staff(), _staff("Sue", "Two")
    b1 = _book(e, p, t, "16:20")
    b2 = _book(e, q, u, "16:00", status="Attended")
    b3 = _book(f, p, u, "16:10")
    assert [b.booking_id for b in PE.list_bookings()] == [b2.booking_id, b1.booking_id,
                                                          b3.booking_id]

    def ids(**kw):
        return {b.booking_id for b in PE.list_bookings(**kw)}

    assert ids(event_id=e.event_id) == {b1.booking_id, b2.booking_id}
    assert ids(student_id=p.pupil_id) == {b1.booking_id, b3.booking_id}
    assert ids(staff_id=u.staff_id.lower()) == {b2.booking_id, b3.booking_id}
    assert ids(status="Attended") == {b2.booking_id}
    assert ids(slot_time="16:10") == {b3.booking_id}
    with pytest.raises(PE.ValidationError, match="Status must be one of"):
        PE.list_bookings(status="Gone")
    with pytest.raises(PE.ValidationError, match="Slot time must be HH:MM"):
        PE.list_bookings(slot_time="4pm")


def test_list_bookings_with_detail_names_everyone():
    e = _event()
    p, t = _pupil(), _staff()
    b = _book(e, p, t)
    rows = PE.list_bookings_with_detail(event_id=e.event_id)
    assert len(rows) == 1
    r = rows[0]
    assert r.booking == b
    assert r.student_name == "Ada Lovelace"
    assert r.staff_name == "Tom Teach"
    assert (r.event_name, r.event_date) == (e.name, "2026-11-20")


# ── schedules ───────────────────────────────────────────────────────

def test_free_slots_and_schedules_ignore_cancelled():
    e = _event(end_time="16:40")
    p, q = _pupil(), _pupil("Bob", "Smith")
    t = _staff()
    _book(e, p, t, "16:00")
    c = _book(e, q, t, "16:20", status="Cancelled")
    assert PE.free_slots_for_staff(e.event_id, t.staff_id) == ["16:10", "16:20", "16:30"]
    assert [b.slot_time for b in PE.staff_schedule(e.event_id, t.staff_id)] == ["16:00"]
    assert PE.student_schedule(e.event_id, q.pupil_id) == []
    assert [b.slot_time for b in PE.student_schedule(e.event_id, p.pupil_id)] == ["16:00"]
    assert c.status == "Cancelled"
    with pytest.raises(PE.ValidationError, match="No event with id 404"):
        PE.free_slots_for_staff(404, t.staff_id)


def test_a_cancelled_slot_that_is_offered_as_free_can_be_booked_again():
    e = _event()
    t = _staff()
    b = _book(e, _pupil(), t, "16:20")
    PE.set_booking_status(b.booking_id, "Cancelled")
    assert "16:20" in PE.free_slots_for_staff(e.event_id, t.staff_id)
    again = _book(e, _pupil("Bob", "Smith"), t, "16:20")
    assert again.status == "Booked"


# ── summaries ───────────────────────────────────────────────────────

def test_summarize_event_counts_and_fill_rate():
    e = _event()                                  # 6 slots
    t, u = _staff(), _staff("Sue", "Two")
    p, q, r = _pupil(), _pupil("Bob", "Smith"), _pupil("Cat", "Jones")
    _book(e, p, t, "16:00")
    _book(e, q, t, "16:10", status="Attended")
    _book(e, r, u, "16:00", status="No-Show")
    _book(e, r, u, "16:10", status="Cancelled")
    s = PE.summarize_event(e.event_id)
    assert s.total_slots == 6
    assert (s.booked, s.attended, s.no_shows, s.cancelled) == (1, 1, 1, 1)
    assert s.distinct_students == 3
    assert s.distinct_staff == 2
    assert s.distinct_staff_total_slots == 12
    assert s.fill_rate == 25.0                    # 3 active / 12


def test_summarize_event_with_no_bookings_has_no_fill_rate():
    s = PE.summarize_event(_event().event_id)
    assert s.distinct_staff == 0 and s.distinct_staff_total_slots == 0
    assert s.fill_rate is None
    with pytest.raises(PE.ValidationError, match="No event with id 404"):
        PE.summarize_event(404)


def test_overall_summary():
    _event("past", event_date=_d(-10), status="Completed")
    soon = _event("soon", event_date=_d(3), status="Open for Booking")
    _event("later", event_date=_d(30))
    _event("cancelled", event_date=_d(1), status="Cancelled")
    _book(soon, _pupil(), _staff())
    s = PE.summary()
    assert s.total_events == 4
    assert s.upcoming_events == 2
    assert s.open_for_booking == 1
    assert s.completed == 1
    assert s.total_bookings == 1
    assert s.by_event_status["Scheduled"] == 1 and s.by_event_status["Cancelled"] == 1
    assert s.by_booking_status == {"Booked": 1, "Attended": 0, "No-Show": 0,
                                   "Cancelled": 0}
    assert s.next_event.name == "soon"
