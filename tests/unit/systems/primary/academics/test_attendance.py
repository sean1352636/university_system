"""Daily AM/PM attendance marks (domain.academics.attendance.attendance)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.attendance import attendance as A
from education_system.systems.primary.domain.learners.pupils import pupils as P

DAY = "2025-09-08"      # a Monday
NEXT = "2025-09-09"


def _pupil(first="Ada"):
    return P.create_pupil({"first_name": first, "last_name": "Test", "year_group": "2",
                           "date_of_birth": "2019-01-01"}).pupil_id


# ── empty database ──

def test_empty_db():
    assert A.list_for_date(DAY) == []
    assert A.list_records() == []
    assert A.get_record(1) is None
    assert A.get_for("P0000001", DAY, "am") is None
    assert A.delete_record(1) is False
    assert A.list_for_pupil("P0000001") == []


def test_daily_summary_empty_day():
    out = A.daily_summary(DAY)
    assert out["date"] == DAY
    for sess in ("AM", "PM"):
        assert out["sessions"][sess] == {"total": 0, "present": 0,
                                         "authorised_absent": 0,
                                         "unauthorised_absent": 0, "other": 0,
                                         "marks": {}}


def test_pupil_summary_no_records():
    s = A.pupil_summary("P0000001")
    assert (s["total_sessions"], s["attendance_pct"], s["records"]) == (0, 0.0, [])


# ── record_mark ──

def test_record_mark_inserts_and_reads_back():
    pid = _pupil()
    rec = A.record_mark(pid, DAY, "am", "/", notes=" on time ")
    assert (rec.pupil_id, rec.date, rec.session, rec.mark, rec.notes) == (
        pid, DAY, "AM", "/", "on time")
    assert rec.label == "Present (AM)"
    assert rec.category == "present"
    assert rec.is_attending and rec.is_possible
    assert A.get_record(rec.record_id) == rec
    assert A.get_for(pid, DAY, "am") == rec


def test_record_mark_same_session_updates_in_place():
    pid = _pupil()
    first = A.record_mark(pid, DAY, "AM", "/")
    second = A.record_mark(pid, DAY, "AM", "I", "flu")
    assert second.record_id == first.record_id
    assert (second.mark, second.notes, second.category) == ("I", "flu", "auth_absent")
    assert len(A.list_for_date(DAY)) == 1


def test_record_properties_per_category():
    pid = _pupil()
    late = A.record_mark(pid, DAY, "AM", "L")
    assert late.is_attending and late.category == "late"
    x = A.record_mark(pid, DAY, "PM", "X")
    assert x.is_possible is False and x.is_attending is False
    u = A.record_mark(pid, NEXT, "AM", "U")
    assert u.category == "unauth_absent" and not u.is_attending


def test_record_mark_validation():
    pid = _pupil()
    with pytest.raises(A.ValidationError, match="Pupil ID is required"):
        A.record_mark(" ", DAY, "AM", "/")
    with pytest.raises(A.ValidationError, match="No pupil with id NOPE"):
        A.record_mark("NOPE", DAY, "AM", "/")
    with pytest.raises(A.ValidationError, match="Date is required"):
        A.record_mark(pid, "", "AM", "/")
    with pytest.raises(A.ValidationError, match="Date must be YYYY-MM-DD"):
        A.record_mark(pid, "08/09/2025", "AM", "/")
    with pytest.raises(A.ValidationError, match="not a real date"):
        A.record_mark(pid, "2025-02-30", "AM", "/")
    with pytest.raises(A.ValidationError, match="Session must be one of AM, PM"):
        A.record_mark(pid, DAY, "EVE", "/")
    with pytest.raises(A.ValidationError, match="Mark is required"):
        A.record_mark(pid, DAY, "AM", "")
    with pytest.raises(A.ValidationError, match="Mark must be one of"):
        A.record_mark(pid, DAY, "AM", "Z")
    assert A.list_records() == []


# ── bulk ──

def test_bulk_record_keeps_good_rows_when_one_fails():
    a, b = _pupil("Ada"), _pupil("Bea")
    out = A.bulk_record(DAY, "pm", {a: "\\", b: "Q", "GHOST": "/"})
    assert isinstance(out[a], A.AttendanceRecord) and out[a].session == "PM"
    assert "Mark must be one of" in out[b]
    assert out["GHOST"] == "No pupil with id GHOST"
    assert [r.pupil_id for r in A.list_for_date(DAY)] == [a]


def test_bulk_record_validates_date_and_session_first():
    with pytest.raises(A.ValidationError, match="Session must be one of"):
        A.bulk_record(DAY, "XX", {})
    with pytest.raises(A.ValidationError, match="Date must be YYYY-MM-DD"):
        A.bulk_record("today", "AM", {})


# ── listing ──

def test_list_for_date_session_filter_and_order():
    a, b = sorted([_pupil("Ada"), _pupil("Bea")])
    A.record_mark(b, DAY, "PM", "\\")
    A.record_mark(a, DAY, "PM", "\\")
    A.record_mark(a, DAY, "AM", "/")
    A.record_mark(a, NEXT, "AM", "/")
    assert [(r.pupil_id, r.session) for r in A.list_for_date(DAY)] == [
        (a, "AM"), (a, "PM"), (b, "PM")]
    assert [r.pupil_id for r in A.list_for_date(DAY, session="am")] == [a]


def test_list_records_filters_newest_first():
    a, b = _pupil("Ada"), _pupil("Bea")
    A.record_mark(a, "2025-09-08", "AM", "/")
    A.record_mark(a, "2025-09-10", "AM", "/")
    A.record_mark(b, "2025-09-09", "AM", "/")
    assert [r.date for r in A.list_records()] == ["2025-09-10", "2025-09-09", "2025-09-08"]
    assert [r.date for r in A.list_records(date="2025-09-09")] == ["2025-09-09"]
    assert [r.date for r in A.list_records(date_from="2025-09-09",
                                           date_to="2025-09-09")] == ["2025-09-09"]
    assert [r.date for r in A.list_records(pupil_id=f" {a} ")] == ["2025-09-10",
                                                                   "2025-09-08"]
    with pytest.raises(A.ValidationError, match="From date must be YYYY-MM-DD"):
        A.list_records(date_from="yesterday")


def test_list_for_pupil_range_and_required_id():
    a = _pupil()
    A.record_mark(a, "2025-09-08", "AM", "/")
    A.record_mark(a, "2025-09-08", "PM", "\\")
    A.record_mark(a, "2025-09-12", "AM", "I")
    assert [(r.date, r.session) for r in A.list_for_pupil(a)] == [
        ("2025-09-12", "AM"), ("2025-09-08", "AM"), ("2025-09-08", "PM")]
    assert len(A.list_for_pupil(a, date_to="2025-09-10")) == 2
    assert len(A.list_for_pupil(a, date_from="2025-09-10")) == 1
    with pytest.raises(A.ValidationError, match="Pupil ID is required"):
        A.list_for_pupil("")
    with pytest.raises(A.ValidationError, match="To date"):
        A.list_for_pupil(a, date_to="2025-13-01")


def test_delete_record():
    rec = A.record_mark(_pupil(), DAY, "AM", "/")
    assert A.delete_record(rec.record_id) is True
    assert A.get_record(rec.record_id) is None


# ── summaries ──

def test_daily_summary_counts_by_category():
    pids = [_pupil(n) for n in ("Ada", "Bea", "Cy", "Di", "Ed", "Fi")]
    for pid, mark in zip(pids, ["/", "L", "I", "O", "E", "X"]):
        A.record_mark(pid, DAY, "AM", mark)
    A.record_mark(pids[0], DAY, "PM", "\\")
    s = A.daily_summary(DAY)["sessions"]
    assert s["AM"] == {"total": 6, "present": 2, "authorised_absent": 1,
                       "unauthorised_absent": 1, "other": 2,
                       "marks": {"/": 1, "L": 1, "I": 1, "O": 1, "E": 1, "X": 1}}
    assert s["PM"]["total"] == 1 and s["PM"]["present"] == 1


def test_pupil_summary_percentage():
    pid = _pupil()
    for date, sess, mark in [("2025-09-08", "AM", "/"), ("2025-09-08", "PM", "\\"),
                             ("2025-09-09", "AM", "L"), ("2025-09-09", "PM", "I"),
                             ("2025-09-10", "AM", "O"), ("2025-09-10", "PM", "U"),
                             ("2025-09-11", "AM", "E")]:
        A.record_mark(pid, date, sess, mark)
    s = A.pupil_summary(f" {pid} ")
    assert s["pupil_id"] == pid
    assert (s["total_sessions"], s["present"], s["authorised_absent"],
            s["unauthorised_absent"], s["other"]) == (7, 3, 1, 2, 1)
    assert s["attendance_pct"] == round(100 * 3 / 7, 2)      # 42.86
    assert len(s["records"]) == 7


def test_pupil_summary_date_range():
    pid = _pupil()
    A.record_mark(pid, "2025-09-08", "AM", "O")
    A.record_mark(pid, "2025-09-09", "AM", "/")
    s = A.pupil_summary(pid, date_from="2025-09-09")
    assert (s["total_sessions"], s["attendance_pct"]) == (1, 100.0)


def test_not_required_sessions_are_left_out_of_the_percentage():
    """'X' is not a possible session (``is_possible`` is False), so it must not
    count against the pupil: one present + one X = 100 %, not 50 %."""
    pid = _pupil()
    A.record_mark(pid, DAY, "AM", "/")
    A.record_mark(pid, DAY, "PM", "X")
    assert A.pupil_summary(pid)["attendance_pct"] == 100.0
