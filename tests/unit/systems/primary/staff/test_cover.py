"""Cover arrangements (systems.primary.domain.staff.cover.cover)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.subjects import subjects as SJ
from education_system.systems.primary.domain.academics.timetable import timetable as TT
from education_system.systems.primary.domain.staff.cover import cover as CV

MON = "2026-11-09"   # a Monday
TUE = "2026-11-10"
SAT = "2026-11-14"


def _cover(date=MON, period=1, absent="Mr Absent", **extra):
    # The clash check reads timetable_slots; create it so the other rules can
    # be tested (see test_fresh_database_cover_teacher_on_weekday).
    TT.init_db()
    return CV.create({"date": date, "period": period, "absent_teacher": absent, **extra})


def _subject(code="MAT", name="Maths"):
    return SJ.create({"code": code, "name": name, "key_stage": "KS2"})


# ── Create ───────────────────────────────────────────────────────────

def test_create_defaults_and_subject_join():
    sj = _subject()
    c = _cover(year_group="4", form_group=" 4B ", subject_id=str(sj.subject_id), room=" R1 ",
               reason=" Ill ", notes=" n ")
    assert (c.date, c.period, c.absent_teacher, c.cover_teacher) == (MON, 1, "Mr Absent", None)
    assert (c.status, c.year_group, c.form_group, c.room) == ("Pending", "4", "4B", "R1")
    assert (c.subject_id, c.subject_code, c.subject_name) == (sj.subject_id, "MAT", "Maths")
    assert (c.reason, c.notes) == ("Ill", "n")
    assert CV.get(c.cover_id) == c
    assert CV.get(999) is None


@pytest.mark.parametrize("bad, msg", [
    ({"date": ""}, "Date is required"),
    ({"date": "09/11/2026"}, "Date must be YYYY-MM-DD"),
    ({"date": "2026-02-30"}, "not a real date"),
    ({"period": ""}, "Period is required"),
    ({"period": "one"}, "Period must be a number"),
    ({"period": 0}, "Period must be between 1 and 8"),
    ({"period": 9}, "Period must be between 1 and 8"),
    ({"absent_teacher": " "}, "Absent teacher is required"),
    ({"cover_teacher": "mr absent"}, "cannot be the same as the absent teacher"),
    ({"year_group": "7"}, "Year group must be one of"),
    ({"subject_id": "x"}, "Subject ID must be a number"),
    ({"subject_id": 404}, "No subject #404"),
    ({"status": "Done"}, "Status must be one of"),
])
def test_create_refusals(bad, msg):
    data = {"date": MON, "period": 1, "absent_teacher": "Mr Absent", **bad}
    TT.init_db()
    with pytest.raises(CV.ValidationError, match=msg):
        CV.create(data)
    assert CV.list_arrangements() == []


def test_reception_is_a_valid_year_group():
    assert _cover(year_group="R").year_group == "R"


# ── Clashes ──────────────────────────────────────────────────────────

def test_cover_teacher_cannot_cover_two_lessons_at_once():
    _cover(cover_teacher="Ms Cover", status="Assigned")
    with pytest.raises(CV.ValidationError, match="Cover clash: Ms Cover already covers period 1"):
        _cover(absent="Mrs Other", cover_teacher="Ms Cover")
    # different period or different day is fine
    assert _cover(period=2, absent="Mrs Other", cover_teacher="Ms Cover").period == 2
    assert _cover(date=TUE, absent="Mrs Other", cover_teacher="Ms Cover").date == TUE


def test_cancelled_cover_does_not_clash():
    first = _cover(cover_teacher="Ms Cover")
    CV.set_status(first.cover_id, "Cancelled")
    assert _cover(absent="Mrs Other", cover_teacher="Ms Cover").cover_teacher == "Ms Cover"
    # and a cancelled new row is never checked
    assert _cover(absent="Mr Third", cover_teacher="Ms Cover",
                  status="Cancelled").status == "Cancelled"


def test_timetabled_lesson_clashes_on_that_weekday_only():
    sj = _subject()
    slot = TT.create_slot({"year_group": "3", "form_group": "3A", "subject_id": sj.subject_id,
                           "day_of_week": "Mon", "period": 2, "teacher": "Ms Busy"})
    with pytest.raises(CV.ValidationError,
                       match=f"already teaches period 2 on Mon .*#{slot.slot_id}"):
        _cover(period=2, cover_teacher="Ms Busy")
    assert _cover(date=TUE, period=2, cover_teacher="Ms Busy").cover_teacher == "Ms Busy"
    assert _cover(period=3, cover_teacher="Ms Busy").period == 3


def test_weekend_skips_timetable_check():
    sj = _subject()
    TT.create_slot({"year_group": "3", "subject_id": sj.subject_id, "day_of_week": "Mon",
                    "period": 1, "teacher": "Ms Busy"})
    assert _cover(date=SAT, cover_teacher="Ms Busy").date == SAT


# ── Update / assign / status / delete ────────────────────────────────

def test_update_merges_and_excludes_itself_from_clash():
    c = _cover(cover_teacher="Ms Cover", room="R1")
    out = CV.update(c.cover_id, {"notes": "bring books"})
    assert (out.notes, out.room, out.cover_teacher) == ("bring books", "R1", "Ms Cover")
    with pytest.raises(CV.ValidationError, match="No cover arrangement #999"):
        CV.update(999, {"notes": "x"})
    with pytest.raises(CV.ValidationError, match="Period must be between"):
        CV.update(c.cover_id, {"period": 12})


def test_update_into_a_clash_refused():
    _cover(cover_teacher="Ms Cover")
    other = _cover(period=2, absent="Mrs Other", cover_teacher="Ms Cover")
    with pytest.raises(CV.ValidationError, match="Cover clash"):
        CV.update(other.cover_id, {"period": 1})
    assert CV.get(other.cover_id).period == 2


def test_assign_sets_teacher_and_status():
    c = _cover()
    out = CV.assign(c.cover_id, "  Ms Cover ")
    assert (out.cover_teacher, out.status) == ("Ms Cover", "Assigned")
    with pytest.raises(CV.ValidationError, match="Cover teacher is required"):
        CV.assign(c.cover_id, " ")
    with pytest.raises(CV.ValidationError, match="cannot be the same"):
        CV.assign(c.cover_id, "Mr Absent")


def test_set_status_workflow_and_unknown_status():
    c = _cover(cover_teacher="Ms Cover")
    for status in ("Assigned", "Confirmed", "Completed"):
        assert CV.set_status(c.cover_id, status).status == status
    with pytest.raises(CV.ValidationError, match="Status must be one of"):
        CV.set_status(c.cover_id, "Lost")


def test_delete():
    c = _cover()
    assert CV.delete(c.cover_id) is True
    assert CV.get(c.cover_id) is None
    assert CV.delete(c.cover_id) is False


# ── Listing + figures ────────────────────────────────────────────────

def test_list_filters_and_order():
    a = _cover(date=MON, period=2, cover_teacher="Ms Cover")
    b = _cover(date=MON, period=1, absent="Mrs Other", status="Confirmed")
    c = _cover(date=TUE, period=1, cover_teacher="Mr Spare")
    ids = lambda rows: [r.cover_id for r in rows]  # noqa: E731
    assert ids(CV.list_arrangements()) == [c.cover_id, b.cover_id, a.cover_id]
    assert ids(CV.list_arrangements(date=MON)) == [b.cover_id, a.cover_id]
    assert ids(CV.list_arrangements(date_from=TUE)) == [c.cover_id]
    assert ids(CV.list_arrangements(date_to=MON)) == [b.cover_id, a.cover_id]
    assert ids(CV.list_arrangements(teacher="Mrs Other")) == [b.cover_id]
    assert ids(CV.list_arrangements(cover_teacher="Mr Spare")) == [c.cover_id]
    assert ids(CV.list_arrangements(status="Confirmed")) == [b.cover_id]
    with pytest.raises(CV.ValidationError, match="Status filter"):
        CV.list_arrangements(status="Nope")
    with pytest.raises(CV.ValidationError, match="From date must be YYYY-MM-DD"):
        CV.list_arrangements(date_from="soon")


def test_status_counts():
    assert CV.status_counts() == {s: 0 for s in CV.STATUSES}
    _cover(date=MON)
    _cover(date=MON, period=2, status="Confirmed")
    _cover(date=TUE, status="Confirmed")
    assert CV.status_counts() == {"Pending": 1, "Assigned": 0, "Confirmed": 2,
                                  "Completed": 0, "Cancelled": 0}
    assert CV.status_counts(date_from=TUE)["Confirmed"] == 1
    assert CV.status_counts(date_to=MON) == {"Pending": 1, "Assigned": 0, "Confirmed": 1,
                                             "Completed": 0, "Cancelled": 0}


def test_daily_load():
    _cover(period=1, cover_teacher="Ms Cover", status="Assigned")
    _cover(period=2, absent="Mrs Other", cover_teacher="Ms Cover", status="Confirmed")
    _cover(period=3)                                    # unassigned
    _cover(period=4, absent="Mr Gone", status="Cancelled")   # cancelled, not unassigned
    _cover(period=5, absent="Mr X", cover_teacher="Mr Spare", status="Cancelled")
    _cover(date=TUE, cover_teacher="Ms Cover")
    load = CV.daily_load(MON)
    assert load["date"] == MON and load["total"] == 5
    assert load["unassigned"] == 1
    assert load["by_cover"] == {"Ms Cover": 2}
    assert load["by_status"] == {"Pending": 1, "Assigned": 1, "Confirmed": 1,
                                 "Completed": 0, "Cancelled": 2}
    assert len(load["records"]) == 5
    empty = CV.daily_load("2026-12-25")
    assert (empty["total"], empty["unassigned"], empty["by_cover"]) == (0, 0, {})


def test_daily_load_rejects_bad_date():
    with pytest.raises(CV.ValidationError, match="Date must be YYYY-MM-DD"):
        CV.daily_load("Monday")


# ── Fresh database ───────────────────────────────────────────────────

def test_fresh_database_cover_teacher_on_weekday():
    """Cover must work before anyone has opened the timetable: init_db sets
    up subjects but not timetable_slots, which the clash check reads."""
    c = CV.create({"date": MON, "period": 1, "absent_teacher": "Mr Absent",
                   "cover_teacher": "Ms Cover"})
    assert (c.cover_teacher, c.status) == ("Ms Cover", "Pending")
