"""Tests for the attendance calendar.

The two properties that matter: an unconfigured calendar behaves like
plain Monday-to-Friday, and a Year 13 study-leave day does not close the
college for Year 12.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
)


def next_weekday(target: int) -> _dt.date:
    today = _dt.date.today()
    return today + _dt.timedelta(days=(target - today.weekday()) % 7)


# ── 1. Unconfigured ────────────────────────────────────────────────

class TestNoCalendar:

    def test_weekdays_are_open(self, attdb):
        assert calendar.is_open(attdb.monday) is True

    def test_weekends_are_not(self, attdb):
        saturday = next_weekday(5).isoformat()
        assert calendar.is_open(saturday) is False

    def test_everything_counts_as_term_time(self, attdb):
        # A college that has not built its calendar should not suddenly
        # be told it is permanently on holiday.
        assert calendar.in_term("2030-08-15") is True

    def test_teaching_days_are_the_weekdays(self, attdb):
        monday = _dt.date.fromisoformat(attdb.monday)
        week = calendar.teaching_days(
            attdb.monday, (monday + _dt.timedelta(days=6)).isoformat())
        assert len(week) == 5

    def test_a_full_day_is_two_sessions(self, attdb):
        assert calendar.teaching_sessions(attdb.monday, attdb.monday) == 2


# ── 2. Terms ───────────────────────────────────────────────────────

class TestTerms:

    def test_a_term_can_be_recorded(self, attdb):
        term = calendar.add_term("Autumn", "2026-09-01", "2026-12-18",
                                 academic_year="2026/27")
        assert term.covers("2026-10-01") is True
        assert term.covers("2026-08-01") is False

    def test_a_term_cannot_end_before_it_starts(self, attdb):
        with pytest.raises(core.ValidationError, match="cannot end before"):
            calendar.add_term("Broken", "2026-12-01", "2026-09-01")

    def test_a_name_is_required(self, attdb):
        with pytest.raises(core.ValidationError, match="name is required"):
            calendar.add_term("  ", "2026-09-01", "2026-12-18")

    def test_dates_outside_every_term_are_closed(self, attdb):
        calendar.add_term("Autumn", "2026-09-01", "2026-12-18")
        assert calendar.is_open("2026-12-28") is False

    def test_the_term_containing_a_date_is_findable(self, attdb):
        calendar.add_term("Autumn", "2026-09-01", "2026-12-18")
        assert calendar.term_for("2026-10-01").name == "Autumn"

    def test_re_adding_a_term_updates_its_dates(self, attdb):
        calendar.add_term("Autumn", "2026-09-01", "2026-12-18",
                          academic_year="2026/27")
        calendar.add_term("Autumn", "2026-09-05", "2026-12-20",
                          academic_year="2026/27")
        assert len(calendar.list_terms()) == 1
        assert calendar.term_for("2026-12-19") is not None


# ── 3. Non-teaching days ───────────────────────────────────────────

class TestNonTeachingDays:

    def test_a_closure_closes_the_day(self, attdb):
        calendar.add_day(attdb.monday, kind=calendar.INSET, name="INSET")
        assert calendar.is_open(attdb.monday) is False

    def test_the_reason_is_reported(self, attdb):
        calendar.add_day(attdb.monday, kind=calendar.INSET, name="Training")
        status = calendar.day_status(attdb.monday)
        assert "INSET" in status.reason

    def test_a_half_day_leaves_one_session(self, attdb):
        calendar.add_day(attdb.monday, kind=calendar.CLOSURE,
                         half=calendar.PM)
        status = calendar.day_status(attdb.monday)
        assert status.open is True
        assert status.sessions == (calendar.AM,)
        assert status.half_day is True

    def test_a_range_marks_weekdays_only(self, attdb):
        monday = _dt.date.fromisoformat(attdb.monday)
        added = calendar.add_range(
            attdb.monday, (monday + _dt.timedelta(days=6)).isoformat(),
            kind=calendar.HALF_TERM, name="October half term")
        assert added == 5

    def test_a_range_can_be_cleared(self, attdb):
        monday = _dt.date.fromisoformat(attdb.monday)
        end = (monday + _dt.timedelta(days=4)).isoformat()
        calendar.add_range(attdb.monday, end, kind=calendar.HALF_TERM)
        assert calendar.clear_range(attdb.monday, end) == 5
        assert calendar.is_open(attdb.monday) is True

    def test_an_unknown_kind_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Kind must be"):
            calendar.add_day(attdb.monday, kind="Snow day-ish")

    def test_an_unknown_half_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Half must be"):
            calendar.add_day(attdb.monday, half="EVENING")

    def test_an_exam_period_is_still_teaching(self, attdb):
        # Learners still have lessons around their papers.
        calendar.add_day(attdb.monday, kind=calendar.EXAM_PERIOD)
        assert calendar.is_open(attdb.monday) is True

    def test_fixed_bank_holidays_can_be_seeded(self, attdb):
        assert calendar.seed_bank_holidays(2027) == 3
        assert calendar.is_open("2027-12-27") is False


# ── 4. Study leave, per year group ─────────────────────────────────

class TestStudyLeave:

    def test_study_leave_closes_the_day_for_that_year(self, attdb):
        calendar.add_day(attdb.monday, kind=calendar.STUDY_LEAVE,
                         year_group=13)
        assert calendar.is_open(attdb.monday, year_group=13) is False

    def test_other_years_carry_on(self, attdb):
        calendar.add_day(attdb.monday, kind=calendar.STUDY_LEAVE,
                         year_group=13)
        assert calendar.is_open(attdb.monday, year_group=12) is True

    def test_the_college_as_a_whole_stays_open(self, attdb):
        # A Year 13 study-leave day does not close the college.
        calendar.add_day(attdb.monday, kind=calendar.STUDY_LEAVE,
                         year_group=13)
        assert calendar.is_open(attdb.monday) is True

    def test_teaching_days_respect_the_year_group(self, attdb):
        calendar.add_day(attdb.monday, kind=calendar.STUDY_LEAVE,
                         year_group=13)
        days = calendar.teaching_days(attdb.monday, attdb.monday,
                                      year_group=13)
        assert days == []

    def test_a_bad_year_group_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Year group must be"):
            calendar.add_day(attdb.monday, year_group=99)


# ── 5. Counting and applying ───────────────────────────────────────

class TestCounting:

    def test_a_summary_counts_the_window(self, attdb):
        monday = _dt.date.fromisoformat(attdb.monday)
        friday = (monday + _dt.timedelta(days=4)).isoformat()
        calendar.add_day(attdb.monday, kind=calendar.INSET)
        summary = calendar.summary(attdb.monday, friday)
        assert summary.weekdays == 5
        assert summary.teaching_days == 4
        assert summary.closed_days == 1

    def test_half_days_reduce_the_session_count(self, attdb):
        calendar.add_day(attdb.monday, kind=calendar.CLOSURE,
                         half=calendar.PM)
        summary = calendar.summary(attdb.monday, attdb.monday)
        assert summary.sessions == 1

    def test_the_next_teaching_day_skips_closures(self, attdb):
        monday = _dt.date.fromisoformat(attdb.monday)
        tuesday = (monday + _dt.timedelta(days=1)).isoformat()
        calendar.add_day(tuesday, kind=calendar.INSET)
        assert calendar.next_teaching_day(attdb.monday) == \
            (monday + _dt.timedelta(days=2)).isoformat()

    def test_a_backwards_range_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="on or before"):
            calendar.teaching_days(attdb.next_monday, attdb.monday)

    def test_applying_a_closure_codes_the_lessons(self, attdb):
        # Otherwise a snow day becomes a day of unmarked lessons that
        # counts against the college.
        calendar.add_day(attdb.monday, kind=calendar.CLOSURE,
                         name="Burst pipe")
        written = calendar.apply_closure(attdb.monday, actor="head")
        assert written == 3
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == calendar.CLOSURE_CODE

    def test_applying_a_closure_to_an_open_day_is_refused(self, attdb):
        with pytest.raises(core.ValidationError, match="not marked as a "
                                                       "closure"):
            calendar.apply_closure(attdb.monday)
