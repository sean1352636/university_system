"""Academic year + calendar rules (domain.academic_year, domain.calendar_events)
on a scratch school DB."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
from education_system.systems.secondary.modules.curriculum.domain import calendar_events as CE
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")
OTHER = Principal(username="teacher2", role="teacher")
TODAY = dt.date(2026, 11, 3)
D = dt.date

SIX_TERMS = (
    ("Autumn 1", "2026-09-03", "2026-10-23"), ("Autumn 2", "2026-11-02", "2026-12-18"),
    ("Spring 1", "2027-01-05", "2027-02-12"), ("Spring 2", "2027-02-22", "2027-03-25"),
    ("Summer 1", "2027-04-12", "2027-05-28"), ("Summer 2", "2027-06-07", "2027-07-21"),
)


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _year(name="2026/27", terms=SIX_TERMS):
    y = AY.create_year(name, actor=ADMIN)
    for n, s, e in terms:
        AY.add_term(y.year_id, {"name": n, "start_date": s, "end_date": e}, actor=ADMIN)
    return y


# ── Years ────────────────────────────────────────────────────────────

def test_year_bounds_and_validation():
    y = AY.create_year("2026/27", actor=ADMIN)
    assert (y.start_date, y.end_date, y.status) == ("2026-09-01", "2027-08-31", "Planning")
    for bad in ("2026", "2026/28", "26/27", ""):
        with pytest.raises(AY.ValidationError):
            AY.create_year(bad, actor=ADMIN)
    with pytest.raises(AY.ValidationError, match="already exists"):
        AY.create_year("2026/27", actor=ADMIN)
    with pytest.raises(AY.PermissionDenied):
        AY.create_year("2027/28", actor=TEACHER)


def test_set_current_rules():
    old = _year("2025/26", (("Autumn", "2025-09-03", "2025-12-19"),))
    new = AY.create_year("2026/27", actor=ADMIN)
    with pytest.raises(AY.ValidationError, match="ended"):
        AY.set_current(old.year_id, actor=ADMIN, today=TODAY)
    with pytest.raises(AY.ValidationError, match="terms first"):
        AY.set_current(new.year_id, actor=ADMIN, today=TODAY)
    AY.add_term(new.year_id, {"name": "Autumn", "start_date": "2026-09-03",
                              "end_date": "2026-12-18"}, actor=ADMIN)
    # an Active older year gets archived when the new one is made current
    AY.set_current(old.year_id, actor=ADMIN, today=D(2025, 10, 1))
    y = AY.set_current(new.year_id, actor=ADMIN, today=TODAY)
    assert y.status == "Active" and AY.get_year(old.year_id).status == "Archived"
    assert AY.current_year(TODAY).year_id == new.year_id
    with pytest.raises(AY.ValidationError, match="already the current"):
        AY.set_current(new.year_id, actor=ADMIN, today=TODAY)
    far = _year("2028/29", (("Autumn", "2028-09-04", "2028-12-15"),))
    with pytest.raises(AY.ValidationError, match="3 months"):
        AY.set_current(far.year_id, actor=ADMIN, today=TODAY)
    with pytest.raises(AY.ValidationError, match="can't be deleted"):
        AY.delete_year(new.year_id, actor=ADMIN)


def test_archived_year_is_locked_until_reopened():
    y = _year("2025/26", (("Autumn", "2025-09-03", "2025-12-19"),))
    AY.update_year(y.year_id, actor=ADMIN, status="Archived")
    with pytest.raises(AY.ValidationError, match="archived"):
        AY.add_term(y.year_id, {"name": "Spring", "start_date": "2026-01-05",
                                "end_date": "2026-03-27"}, actor=ADMIN)
    AY.update_year(y.year_id, actor=ADMIN, status="Planning")
    AY.add_term(y.year_id, {"name": "Spring", "start_date": "2026-01-05",
                            "end_date": "2026-03-27"}, actor=ADMIN)


def test_delete_year_removes_terms_and_breaks():
    y = _year()
    AY.add_break(y.year_id, {"name": "INSET", "type": "INSET", "start_date": "2026-09-03"},
                 actor=ADMIN)
    AY.delete_year(y.year_id, actor=ADMIN)
    assert AY.list_terms() == [] and AY.list_breaks() == []


# ── Terms / breaks ───────────────────────────────────────────────────

@pytest.mark.parametrize("data, expect", [
    ({"name": "Winter", "start_date": "2026-09-03", "end_date": "2026-10-23"}, "one of"),
    ({"name": "Autumn", "start_date": "2026-08-20", "end_date": "2026-10-23"}, "inside"),
    ({"name": "Autumn", "start_date": "2026-10-23", "end_date": "2026-09-03"}, "before"),
    ({"name": "Autumn", "start_date": "", "end_date": "2026-10-23"}, "Start date"),
    ({"name": "Autumn 2", "start_date": "2026-10-20", "end_date": "2026-12-18"}, "Overlaps"),
    ({"name": "Autumn 1", "start_date": "2027-01-04", "end_date": "2027-02-01"},
     "already has"),
])
def test_term_validation(data, expect):
    y = _year(terms=SIX_TERMS[:1])
    with pytest.raises(AY.ValidationError) as e:
        AY.add_term(y.year_id, data, actor=ADMIN)
    assert any(expect.lower() in p.lower() for p in e.value.problems), e.value.problems


def test_teacher_cannot_change_terms():
    y = _year(terms=())
    with pytest.raises(AY.PermissionDenied):
        AY.add_term(y.year_id, {"name": "Autumn", "start_date": "2026-09-03",
                                "end_date": "2026-12-18"}, actor=TEACHER)


def test_break_single_day_and_validation():
    y = _year()
    b = AY.add_break(y.year_id, {"name": "Training", "type": "INSET",
                                 "start_date": "2026-09-03"}, actor=ADMIN)
    assert b.end_date == "2026-09-03"
    with pytest.raises(AY.ValidationError, match="Type"):
        AY.add_break(y.year_id, {"name": "x", "type": "Snow", "start_date": "2026-09-04"},
                     actor=ADMIN)
    with pytest.raises(AY.ValidationError, match="Overlaps"):
        AY.add_break(y.year_id, {"name": "Again", "type": "INSET", "start_date": "2026-09-03"},
                     actor=ADMIN)
    b = AY.update_break(b.break_id, {"notes": "Safeguarding"}, actor=ADMIN)
    assert b.notes == "Safeguarding" and b.type == "INSET"


# ── Day questions ────────────────────────────────────────────────────

def test_day_info():
    y = _year()
    AY.add_break(y.year_id, {"name": "Staff training", "type": "INSET",
                             "start_date": "2026-09-03"}, actor=ADMIN)
    AY.add_break(y.year_id, {"name": "Exams", "type": "Exam Period",
                             "start_date": "2027-05-10", "end_date": "2027-06-18"}, actor=ADMIN)
    inset = AY.day_info(D(2026, 9, 3))
    assert inset.is_staff_day and not inset.is_school_day and inset.label.startswith("INSET")
    first = AY.day_info(D(2026, 9, 4))
    assert first.is_school_day and first.term.name == "Autumn 1" and first.week == 1
    assert AY.day_info(D(2026, 9, 7)).week == 2  # next Monday
    assert AY.day_info(D(2026, 9, 5)).label == "Weekend"
    half_term = AY.day_info(D(2026, 10, 28))
    assert half_term.term is None and not half_term.is_school_day
    assert "between terms" in half_term.label
    exam = AY.day_info(D(2027, 5, 12))
    assert exam.is_school_day and exam.closure is None  # exam periods don't close school
    assert AY.day_info(D(2030, 1, 7)).label == "No academic year recorded"
    assert AY.school_days_between(D(2026, 9, 1), D(2026, 9, 11)) == 6


def test_check_year_counts_and_problems():
    y = _year(terms=(("Autumn", "2026-09-07", "2026-09-19"),))  # ends on a Saturday
    AY.add_break(y.year_id, {"name": "INSET", "type": "INSET", "start_date": "2026-09-07"},
                 actor=ADMIN)
    AY.add_break(y.year_id, {"name": "Closed", "type": "Other", "start_date": "2026-09-08"},
                 actor=ADMIN)
    c = AY.check_year(y.year_id)
    assert (c.pupil_days, c.staff_days, c.inset_days) == (8, 9, 1)
    assert c.errors == []
    text = " ".join(c.warnings)
    assert "Saturday" in text and "190" in text and "INSET" in text


def test_bank_holidays_added_only_on_school_days():
    y = _year()
    added = AY.add_bank_holidays(y.year_id, actor=ADMIN)
    # Christmas, New Year, Easter and the late-May/August ones fall in holidays.
    assert [(b.start_date, b.name) for b in added] == [("2027-05-03",
                                                        "Early May bank holiday")]
    assert AY.add_bank_holidays(y.year_id, actor=ADMIN) == []  # not twice
    assert not AY.day_info(D(2027, 5, 3)).is_school_day


def test_england_bank_holiday_dates():
    days = {d.isoformat() for d, _n in AY.england_bank_holidays(2027)}
    assert {"2027-03-26", "2027-03-29", "2027-05-03", "2027-05-31", "2027-08-30",
            "2027-12-27", "2027-12-28"} <= days


def test_copy_from_moves_by_whole_weeks():
    src = _year()
    AY.add_break(src.year_id, {"name": "INSET", "type": "INSET", "start_date": "2026-09-03"},
                 actor=ADMIN)
    AY.add_bank_holidays(src.year_id, actor=ADMIN)
    dst = AY.create_year("2027/28", actor=ADMIN)
    terms, breaks = AY.copy_from(dst.year_id, src.year_id, actor=ADMIN)
    assert (terms, breaks) == (6, 1)  # bank holiday not copied
    first = AY.list_terms(dst.year_id)[0]
    assert first.start_date == "2027-09-02"  # same weekday (Thursday), 52 weeks on
    assert D.fromisoformat(first.start_date).weekday() == D(2026, 9, 3).weekday()
    with pytest.raises(AY.ValidationError, match="empty year"):
        AY.copy_from(dst.year_id, src.year_id, actor=ADMIN)


def test_month_info_matches_day_info():
    _year()
    month = AY.month_info(2026, 10)
    assert len(month) == 31
    for d in (D(2026, 10, 1), D(2026, 10, 24), D(2026, 10, 28)):
        assert month[d].label == AY.day_info(d).label


# ── Events ───────────────────────────────────────────────────────────

def _event(**kw):
    data = {"title": "Year 7 assembly", "event_type": "Assembly", "start_date": "2026-11-05",
            "start_time": "08:50", "end_time": "9:20", "audience": "Year 7", **kw}
    return CE.create_event(data, actor=TEACHER)


@pytest.mark.parametrize("changes, expect", [
    ({"title": ""}, "Title"),
    ({"event_type": "Party"}, "Type"),
    ({"audience": "Year 12"}, "Audience"),
    ({"start_time": ""}, "start time"),
    ({"start_time": "25:00"}, "time like"),
    ({"end_time": "08:00"}, "after the start"),
    ({"end_date": "2026-11-01"}, "end date"),
    ({"capacity": "-1"}, "Capacity"),
    ({"cost": "lots"}, "Cost"),
    ({"status": "Cancelled"}, "can't start out"),
])
def test_event_validation(changes, expect):
    with pytest.raises(CE.ValidationError) as e:
        _event(**changes)
    assert any(expect.lower() in p.lower() for p in e.value.problems), e.value.problems


def test_event_normalises():
    ev = _event(cost="£5", capacity="30", all_day="no")
    assert (ev.end_date, ev.end_time, ev.cost, ev.capacity) == ("2026-11-05", "09:20", 5.0, 30)
    ev = _event(all_day=True, start_time="", end_time="")
    assert ev.all_day and ev.start_time is None
    assert ev.when == "2026-11-05 (all day)"


def test_event_permissions():
    ev = _event()
    CE.update_event(ev.event_id, {"location": "Hall"}, actor=TEACHER)
    with pytest.raises(CE.PermissionDenied):
        CE.update_event(ev.event_id, {"location": "Gym"}, actor=OTHER)
    with pytest.raises(CE.PermissionDenied):
        CE.delete_event(ev.event_id, actor=OTHER)
    CE.update_event(ev.event_id, {"location": "Gym"}, actor=ADMIN)
    with pytest.raises(CE.PermissionDenied):
        CE.create_event({"title": "x", "start_date": "2026-11-05", "all_day": True},
                        actor=Principal("pupil", "student"))


def test_event_status_rules():
    ev = _event()
    with pytest.raises(CE.ValidationError, match="Status / Cancel"):
        CE.update_event(ev.event_id, {"status": "Cancelled"}, actor=TEACHER)
    with pytest.raises(CE.ValidationError, match="why"):
        CE.cancel_event(ev.event_id, actor=TEACHER, reason="")
    with pytest.raises(CE.ValidationError, match="before it has started"):
        CE.complete_event(ev.event_id, actor=TEACHER, today=TODAY)
    ev = CE.cancel_event(ev.event_id, actor=TEACHER, reason="Hall flooded")
    assert ev.status == "Cancelled" and ev.status_reason == "Hall flooded"
    ev = CE.set_status(ev.event_id, "Scheduled", actor=TEACHER)
    assert CE.complete_event(ev.event_id, actor=TEACHER, today=D(2026, 11, 5)).status == \
        "Completed"


def test_lists_counts_warnings_summary():
    _year()
    a = _event()
    trip = _event(title="Museum trip", event_type="Trip", start_date="2026-11-06",
                  end_date="2026-11-08", all_day=True, audience="Year 9")
    gone = _event(title="Old", start_date="2026-11-06")
    CE.cancel_event(gone.event_id, actor=TEACHER, reason="x")
    assert [e.event_id for e in CE.list_events(start="2026-11-06", end="2026-11-06")] == [
        trip.event_id, gone.event_id]
    assert [e.event_id for e in CE.list_events(event_type="Trip")] == [trip.event_id]
    assert [e.event_id for e in CE.list_events(search="museum")] == [trip.event_id]
    counts = CE.counts_by_day(D(2026, 11, 1), D(2026, 11, 30))
    assert counts == {D(2026, 11, 5): 1, D(2026, 11, 6): 1, D(2026, 11, 7): 1,
                      D(2026, 11, 8): 1}
    warn = CE.warnings_for("2026-11-06", "2026-11-08")
    assert len(warn) == 2 and "Weekend" in warn[0]
    assert CE.warnings_for("2026-10-28") == ["Wed 28 Oct 2026: School holiday (between terms)"]
    assert CE.warnings_for(a.start_date) == []
    s = CE.summary(days=14, today=TODAY)
    assert s.total == 3 and len(s.upcoming) == 2 and s.by_status["Cancelled"] == 1
