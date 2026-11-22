"""Wraparound care (systems.primary.domain.operations.daily_care.wraparound.wraparound)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.daily_care.wraparound import (
    wraparound as W,
)

MON, TUE, WED = "2030-01-07", "2030-01-08", "2030-01-09"
SAT = "2030-01-12"


def _pupil(first="Ada", last="Lovelace", year="3"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year,
                           "date_of_birth": "2019-03-01"})


def _session(name="Breakfast Club", **extra):
    data = {"name": name, "session_type": "breakfast",
            "days_of_week": "Monday,Tuesday,Wednesday,Thursday,Friday"}
    data.update(extra)
    return W.create_session(data)


def _book(session, pupil, date=MON, **extra):
    return W.book({"session_id": session.session_id, "pupil_id": pupil.pupil_id,
                   "date": date, **extra})


# ── sessions ──

def test_create_session_stores_and_canonicalises():
    s = W.create_session({"name": "  Maple After School ", "session_type": " AFTER_SCHOOL ",
                          "days_of_week": ["mon", "Wed", "monday", "FRI"],
                          "start_time": "15:15", "end_time": "17:45", "capacity": "20",
                          "fee_pounds": "7.5", "notes": "  "})
    got = W.get_session(s.session_id)
    assert got == s
    assert (got.name, got.session_type, got.days_of_week) == \
        ("Maple After School", "after_school", "Monday,Wednesday,Friday")
    assert got.day_list == ["Monday", "Wednesday", "Friday"]
    assert (got.start_time, got.end_time, got.capacity, got.fee_pence) == \
        ("15:15", "17:45", 20, 750)
    assert got.fee_display == "£7.50"
    assert got.is_active and got.notes is None


def test_session_defaults():
    s = W.create_session({"name": "Free club", "session_type": "breakfast"})
    assert (s.days_of_week, s.capacity, s.fee_pence, s.is_active) == (None, None, 0, True)
    assert s.fee_display == "free" and s.day_list == []
    assert W.create_session({"name": "Pence", "session_type": "breakfast",
                             "fee_pence": 305}).fee_display == "£3.05"


@pytest.mark.parametrize("extra,message", [
    ({"name": " "}, "Session name is required"),
    ({"name": "x" * 81}, "80 characters or fewer"),
    ({"session_type": ""}, "Session type is required"),
    ({"session_type": "lunch"}, "Session type must be one of"),
    ({"days_of_week": "Saturday"}, "Day of week 'Saturday' must be one of"),
    ({"start_time": "7am"}, r"Start time must be HH:MM \(24-hour\)"),
    ({"end_time": "24:00"}, r"End time must be HH:MM \(24-hour\)"),
    ({"start_time": "08:00", "end_time": "08:00"}, "End time must be after start time"),
    ({"capacity": "lots"}, "Capacity must be an integer"),
    ({"capacity": 0}, "Capacity must be between 1 and 500"),
    ({"capacity": 501}, "Capacity must be between 1 and 500"),
    ({"fee_pounds": "cheap"}, "Fee must be a number"),
    ({"fee_pounds": 200.01}, "Fee must be between £0 and £200"),
    ({"fee_pence": "1.50"}, r"Fee \(pence\) must be an integer"),
    ({"fee_pence": -1}, "Fee must be between 0p and 20000p"),
    ({"fee_pence": 20001}, "Fee must be between 0p and 20000p"),
])
def test_session_validation(extra, message):
    with pytest.raises(W.ValidationError, match=message):
        _session(**extra)


def test_session_name_must_be_unique():
    _session("Club")
    with pytest.raises(W.ValidationError, match="A session named 'Club' already exists"):
        _session("Club")


def test_list_sessions_filter_and_order():
    a = _session("b breakfast")
    b = _session("A Breakfast")
    c = _session("After", session_type="after_school", is_active=False)
    assert [s.session_id for s in W.list_sessions()] == [c.session_id, b.session_id, a.session_id]
    assert [s.session_id for s in W.list_sessions(session_type="breakfast")] == \
        [b.session_id, a.session_id]
    assert c.session_id not in [s.session_id for s in W.list_sessions(active_only=True)]
    with pytest.raises(W.ValidationError, match="Type filter must be one of"):
        W.list_sessions(session_type="lunch")


def test_update_session_merges_and_checks():
    s = _session(capacity=10, fee_pence=500)
    out = W.update_session(s.session_id, {"capacity": 12})
    assert (out.capacity, out.fee_pence, out.name) == (12, 500, "Breakfast Club")
    assert W.update_session(s.session_id, {"fee_pounds": 4}).fee_pence == 400
    _session("Other")
    with pytest.raises(W.ValidationError, match="A session named 'Other' already exists"):
        W.update_session(s.session_id, {"name": "Other"})
    assert W.update_session(s.session_id, {"name": "Breakfast Club"}).name == "Breakfast Club"
    with pytest.raises(W.ValidationError, match="No session #99"):
        W.update_session(99, {})


def test_toggle_active():
    s = _session()
    assert W.toggle_session_active(s.session_id).is_active is False
    assert W.toggle_session_active(s.session_id).is_active is True
    with pytest.raises(W.ValidationError, match="No session #5"):
        W.toggle_session_active(5)


def test_delete_session_cascades_attendance():
    s, p = _session(), _pupil()
    a = _book(s, p)
    assert W.delete_session(s.session_id) is True
    assert W.get_attendance(a.attendance_id) is None
    assert W.delete_session(s.session_id) is False


# ── booking ──

def test_book_and_upsert():
    s, p = _session(), _pupil()
    a = _book(s, p, notes=" first ")
    assert (a.session_id, a.pupil_id, a.date, a.status, a.notes) == \
        (s.session_id, p.pupil_id, MON, "booked", "first")
    again = _book(s, p, status="ATTENDED")
    assert again.attendance_id == a.attendance_id
    assert (again.status, again.notes) == ("attended", None)
    assert W.counts()["attendance_rows"] == 1


@pytest.mark.parametrize("data,message", [
    ({"session_id": None}, "Session is required"),
    ({"session_id": "abc"}, "Session ID must be an integer"),
    ({"pupil_id": " "}, "Pupil ID is required"),
    ({"date": ""}, "Date is required"),
    ({"date": "07/01/2030"}, "Date must be YYYY-MM-DD"),
    ({"status": "maybe"}, "Status must be one of"),
])
def test_book_validation(data, message):
    s, p = _session(), _pupil()
    payload = {"session_id": s.session_id, "pupil_id": p.pupil_id, "date": MON}
    payload.update(data)
    with pytest.raises(W.ValidationError, match=message):
        W.book(payload)


def test_book_refuses_unknown_inactive_and_unknown_pupil():
    s, p = _session(), _pupil()
    with pytest.raises(W.ValidationError, match="No session #404"):
        W.book({"session_id": 404, "pupil_id": p.pupil_id, "date": MON})
    with pytest.raises(W.ValidationError, match="No pupil with id NOPE"):
        W.book({"session_id": s.session_id, "pupil_id": "NOPE", "date": MON})
    W.toggle_session_active(s.session_id)
    with pytest.raises(W.ValidationError, match="'Breakfast Club' is inactive"):
        _book(s, p)


def test_capacity_counts_only_booked_attended_late():
    s = _session(capacity=2)
    p1, p2, p3, p4 = (_pupil(f"P{i}", f"L{i}") for i in range(4))
    _book(s, p1, status="attended")
    _book(s, p2, status="absent")
    _book(s, p3, status="late")
    with pytest.raises(W.ValidationError, match="is full for 2030-01-07 \\(capacity 2\\)"):
        _book(s, p4)
    assert _book(s, p4, date=TUE).status == "booked"


def test_rebooking_an_absence_respects_capacity():
    s = _session(capacity=1)
    p1, p2 = _pupil("A", "One"), _pupil("B", "Two")
    _book(s, p1, status="absent")
    _book(s, p2)
    with pytest.raises(W.ValidationError, match="is full"):
        _book(s, p1, status="booked")


def test_cannot_book_a_day_the_session_does_not_run():
    s, p = _session(days_of_week="Monday,Wednesday"), _pupil()
    with pytest.raises(W.ValidationError):
        _book(s, p, date=TUE)
    with pytest.raises(W.ValidationError):
        _book(s, p, date=SAT)


def test_set_attendance_status():
    s, p = _session(), _pupil()
    a = _book(s, p)
    assert W.set_attendance_status(a.attendance_id, "late").status == "late"
    with pytest.raises(W.ValidationError, match="Status must be one of"):
        W.set_attendance_status(a.attendance_id, "Late")
    with pytest.raises(W.ValidationError, match="No attendance #77"):
        W.set_attendance_status(77, "late")


def test_delete_attendance():
    s, p = _session(), _pupil()
    a = _book(s, p)
    assert W.delete_attendance(a.attendance_id) is True
    assert W.delete_attendance(a.attendance_id) is False


def test_deleting_pupil_cascades_attendance():
    s, p = _session(), _pupil()
    a = _book(s, p)
    P.delete_pupil(p.pupil_id)
    assert W.get_attendance(a.attendance_id) is None


# ── listing / register ──

def test_list_attendance_filters_and_joins():
    s1 = _session("Breakfast")
    s2 = _session("After", session_type="after_school")
    p1, p2 = _pupil("Amy", "Zed"), _pupil("Bo", "Abel")
    a1 = _book(s1, p1, date=MON)
    a2 = _book(s2, p1, date=TUE, status="absent")
    a3 = _book(s1, p2, date=WED)
    rows = W.list_attendance()
    assert [r[0].attendance_id for r in rows] == [a3.attendance_id, a2.attendance_id,
                                                  a1.attendance_id]
    att, sess, pupil = rows[0]
    assert (sess.name, pupil.pupil_id) == ("Breakfast", p2.pupil_id)

    def ids(**kw):
        return [r[0].attendance_id for r in W.list_attendance(**kw)]

    assert ids(session_id=s1.session_id) == [a3.attendance_id, a1.attendance_id]
    assert ids(pupil_id=f" {p1.pupil_id} ") == [a2.attendance_id, a1.attendance_id]
    assert ids(status="absent") == [a2.attendance_id]
    assert ids(from_date=TUE, to_date=TUE) == [a2.attendance_id]
    with pytest.raises(W.ValidationError, match="Status filter must be one of"):
        W.list_attendance(status="x")
    with pytest.raises(W.ValidationError, match="from_date must be YYYY-MM-DD"):
        W.list_attendance(from_date="Monday")


def test_day_register_sorted_by_name():
    s = _session()
    zed, abel = _pupil("Amy", "Zed"), _pupil("Bo", "Abel")
    _book(s, zed)
    _book(s, abel)
    _book(s, abel, date=TUE)
    reg = W.day_register(s.session_id, MON)
    assert [p.last_name for _, p in reg] == ["Abel", "Zed"]
    assert W.day_register(s.session_id, WED) == []
    with pytest.raises(W.ValidationError, match="Date must be YYYY-MM-DD"):
        W.day_register(s.session_id, "today")
    with pytest.raises(W.ValidationError, match="No session #9"):
        W.day_register(9, MON)


# ── summaries ──

def test_session_summary():
    s = _session()
    p1, p2 = _pupil("A", "A"), _pupil("B", "B")
    _book(s, p1, date=MON, status="attended")
    _book(s, p1, date=TUE, status="late")
    _book(s, p2, date=TUE, status="absent")
    _book(s, p2, date=WED)
    out = W.session_summary(s.session_id)
    assert out == {"session_id": s.session_id, "total_rows": 4, "unique_pupils": 2,
                   "by_status": {"booked": 1, "attended": 1, "absent": 1, "late": 1}}
    tue = W.session_summary(s.session_id, from_date=TUE, to_date=TUE)
    assert tue["total_rows"] == 2 and tue["unique_pupils"] == 2
    assert tue["by_status"] == {"booked": 0, "attended": 0, "absent": 1, "late": 1}
    with pytest.raises(W.ValidationError, match="to_date must be YYYY-MM-DD"):
        W.session_summary(s.session_id, to_date="x")
    with pytest.raises(W.ValidationError, match="No session #3"):
        W.session_summary(3)


def test_counts():
    assert W.counts() == {"sessions": 0, "active_sessions": 0, "attendance_rows": 0}
    s = _session()
    _session("Off", is_active=False)
    _book(s, _pupil())
    assert W.counts() == {"sessions": 2, "active_sessions": 1, "attendance_rows": 1}
