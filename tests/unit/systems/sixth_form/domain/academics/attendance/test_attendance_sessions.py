"""Tests for expected sessions and AM/PM statutory marks.

Covers expanding the timetable into expected lessons, the coverage gap
that the old summaries hid, the true percentage that follows from it,
and the AM/PM session marks plus the roll-up that derives them.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
    attendance_sessions as sessions,
)


def next_weekday(target: int) -> _dt.date:
    """The next date (today included) whose weekday matches ``target``.

    Defined here rather than imported from conftest: the test tree has
    no ``__init__.py`` and runs under ``--import-mode=importlib``, so a
    relative import has no package to resolve against.
    """
    today = _dt.date.today()
    return today + _dt.timedelta(days=(target - today.weekday()) % 7)


# ── 1. Which session a mark belongs to ─────────────────────────────

class TestSessionIdentification:

    @pytest.mark.parametrize("time,expected", [
        ("09:00", "AM"), ("11:30", "AM"), ("12:59", "AM"),
        ("13:00", "PM"), ("14:55", "PM"), ("15:50", "PM"),
    ])
    def test_the_cutoff_splits_the_day(self, time, expected):
        assert sessions.session_for_time(time) == expected

    def test_a_missing_time_defaults_to_morning(self):
        assert sessions.session_for_time(None) == "AM"
        assert sessions.session_for_time("") == "AM"

    def test_slots_are_placed_by_their_start_time(self, attdb):
        assert sessions.session_for_slot(attdb.slot) == "AM"
        assert sessions.session_for_slot(attdb.pm_slot) == "PM"

    def test_a_vanished_slot_does_not_break_a_write(self, attdb):
        # Called from a save path — refusing to mark because the slot's
        # times are missing would be a poor trade.
        assert sessions.session_for_slot(9999) == "AM"

    @pytest.mark.parametrize("raw,expected", [
        ("am", "AM"), ("PM", "PM"), ("lesson", "Lesson"),
    ])
    def test_session_names_are_normalised(self, raw, expected):
        assert sessions.validate_session(raw) == expected

    def test_an_unknown_session_is_rejected(self):
        with pytest.raises(core.ValidationError, match="Session must be"):
            sessions.validate_session("evening")

    def test_lesson_is_not_a_statutory_session(self, attdb):
        with pytest.raises(core.ValidationError, match="AM or PM"):
            sessions.mark_session(attdb.s1, attdb.monday, "Lesson", "/")


# ── 2. Expected lessons ────────────────────────────────────────────

class TestExpectedLessons:

    def test_a_single_week_expands_to_the_timetable(self, attdb):
        lessons = sessions.expected_lessons(
            group_id=attdb.group,
            date_from=attdb.monday, date_to=attdb.monday)
        # Group 1 has two Monday slots: period 1 and period 6.
        assert [lesson.slot_id for lesson in lessons] == [attdb.slot,
                                                          attdb.pm_slot]

    def test_lessons_carry_their_session(self, attdb):
        lessons = sessions.expected_lessons(
            group_id=attdb.group,
            date_from=attdb.monday, date_to=attdb.monday)
        assert [lesson.session for lesson in lessons] == ["AM", "PM"]

    def test_weekends_are_skipped(self, attdb):
        saturday = next_weekday(5).isoformat()
        sunday = next_weekday(6).isoformat()
        assert sessions.teaching_dates(saturday, sunday) == []

    def test_a_backwards_window_is_empty(self, attdb):
        assert sessions.teaching_dates(attdb.monday, attdb.prev_monday) == []

    def test_a_two_week_window_expects_twice_as_much(self, attdb):
        one = sessions.expected_count(
            group_id=attdb.group,
            date_from=attdb.monday, date_to=attdb.monday)
        two = sessions.expected_count(
            group_id=attdb.group,
            date_from=attdb.prev_monday, date_to=attdb.monday)
        assert two == one * 2

    def test_filtering_by_learner_uses_their_groups(self, attdb):
        lessons = sessions.expected_lessons(
            student_id=attdb.s1,
            date_from=attdb.monday, date_to=attdb.monday)
        assert {lesson.group_id for lesson in lessons} == {attdb.group}

    def test_a_learner_in_no_group_expects_nothing(self, attdb):
        assert sessions.expected_lessons(
            student_id="T9999",
            date_from=attdb.monday, date_to=attdb.monday) == []

    def test_sessions_expected_is_two_per_open_day(self, attdb):
        days = len(sessions.teaching_dates(attdb.prev_monday, attdb.monday))
        assert sessions.sessions_expected(
            date_from=attdb.prev_monday, date_to=attdb.monday) == days * 2

    def test_a_lesson_label_reads_usefully(self, attdb):
        lesson = sessions.expected_lessons(
            group_id=attdb.group,
            date_from=attdb.monday, date_to=attdb.monday)[0]
        assert "Mon" in lesson.label
        assert f"slot #{attdb.slot}" in lesson.label


# ── 3. Coverage gaps ───────────────────────────────────────────────

class TestCoverage:

    def test_an_unmarked_register_is_a_gap(self, attdb):
        missing = sessions.missing_marks(
            group_id=attdb.group,
            date_from=attdb.monday, date_to=attdb.monday)
        # Three learners × two Monday lessons, none of them marked.
        assert len(missing) == 6

    def test_marking_closes_the_gap(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present"},
            attdb.s2: {"status": "Present"},
            attdb.s3: {"status": "Present"}})
        missing = sessions.missing_marks(
            group_id=attdb.group,
            date_from=attdb.monday, date_to=attdb.monday)
        assert {gap.lesson.slot_id for gap in missing} == {attdb.pm_slot}

    def test_a_gap_names_the_learner(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present"},
            attdb.s2: {"status": "Present"}})
        missing = sessions.missing_marks(
            student_id=attdb.s3,
            date_from=attdb.monday, date_to=attdb.monday)
        assert all(gap.student_id == attdb.s3 for gap in missing)
        assert missing[0].student_name == "Grace Test"

    def test_coverage_reports_the_share_marked(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present"},
            attdb.s2: {"status": "Present"},
            attdb.s3: {"status": "Present"}})
        cover = sessions.coverage(group_id=attdb.group,
                                  date_from=attdb.monday,
                                  date_to=attdb.monday)
        assert cover.expected == 6
        assert cover.recorded == 3
        assert cover.missing == 3
        assert cover.percentage == 50.0

    def test_full_coverage_is_a_hundred_percent(self, attdb):
        for slot in (attdb.slot, attdb.pm_slot):
            core.save_register(slot, attdb.monday, {
                sid: {"status": "Present"} for sid in attdb.students})
        cover = sessions.coverage(group_id=attdb.group,
                                  date_from=attdb.monday,
                                  date_to=attdb.monday)
        assert cover.percentage == 100.0
        assert cover.missing == 0

    def test_empty_expectation_has_no_percentage(self, attdb):
        cover = sessions.coverage(group_id=2, date_from=attdb.monday,
                                  date_to=attdb.monday)
        assert cover.expected == 0
        assert cover.percentage is None

    def test_a_voided_mark_reopens_the_gap(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_audit as audit,
        )
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        audit.void_record(record.record_id, reason="Wrong learner")
        missing = sessions.missing_marks(
            student_id=attdb.s1,
            date_from=attdb.monday, date_to=attdb.monday)
        assert any(gap.lesson.slot_id == attdb.slot for gap in missing)


# ── 4. True percentage ─────────────────────────────────────────────

class TestTrueSummary:

    def test_unmarked_lessons_stay_in_the_denominator(self, attdb):
        # One of two Monday lessons marked present. The old figure says
        # 100%; against the timetable it is half that.
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        summary = sessions.true_summary(
            attdb.s1, date_from=attdb.monday, date_to=attdb.monday)
        assert summary.expected == 2
        assert summary.recorded == 1
        assert summary.unrecorded == 1
        assert summary.percentage == 50.0
        assert summary.recorded_percentage == 100.0

    def test_approved_activity_counts_as_attending(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "W"}})
        core.save_register(attdb.pm_slot, attdb.monday,
                           {attdb.s1: {"code": "/"}})
        summary = sessions.true_summary(
            attdb.s1, date_from=attdb.monday, date_to=attdb.monday)
        assert summary.approved == 1
        assert summary.present == 1
        assert summary.attending == 2
        assert summary.percentage == 100.0

    def test_not_counted_codes_leave_the_denominator(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "/"}})
        core.save_register(attdb.pm_slot, attdb.monday,
                           {attdb.s1: {"code": "Y"}})   # exceptional closure
        summary = sessions.true_summary(
            attdb.s1, date_from=attdb.monday, date_to=attdb.monday)
        assert summary.not_counted == 1
        assert summary.possible == 1
        assert summary.percentage == 100.0

    def test_authorised_and_unauthorised_are_split(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "I"}})
        core.save_register(attdb.pm_slot, attdb.monday,
                           {attdb.s1: {"code": "O"}})
        summary = sessions.true_summary(
            attdb.s1, date_from=attdb.monday, date_to=attdb.monday)
        assert (summary.authorised, summary.unauthorised) == (1, 1)
        assert summary.percentage == 0.0
        assert summary.unauthorised_percentage == 50.0

    def test_a_legacy_uncoded_row_still_counts(self, attdb):
        import sqlite3
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        conn = sqlite3.connect(attdb.db)
        conn.execute("UPDATE attendance_records SET code = NULL")
        conn.commit()
        conn.close()
        summary = sessions.true_summary(
            attdb.s1, date_from=attdb.monday, date_to=attdb.monday)
        assert summary.present == 1

    def test_no_timetable_means_no_percentage(self, attdb):
        summary = sessions.true_summary(
            "T9999", date_from=attdb.monday, date_to=attdb.monday)
        assert summary.expected == 0
        assert summary.percentage is None


# ── 5. AM/PM session marks ─────────────────────────────────────────

class TestSessionMarks:

    def test_a_mark_can_be_recorded_directly(self, attdb):
        mark = sessions.mark_session(attdb.s1, attdb.monday, "AM", "I",
                                     recorded_by="office")
        assert mark.code == "I"
        assert mark.status == "Authorised"
        assert mark.derived is False

    def test_remarking_replaces_rather_than_duplicates(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "I")
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "M")
        marks = sessions.list_session_marks(student_id=attdb.s1)
        assert len(marks) == 1
        assert marks[0].code == "M"

    def test_am_and_pm_are_separate(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "/")
        sessions.mark_session(attdb.s1, attdb.monday, "PM", "O")
        assert len(sessions.list_session_marks(student_id=attdb.s1)) == 2

    def test_a_bad_code_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Unknown mark code"):
            sessions.mark_session(attdb.s1, attdb.monday, "AM", "Q")

    def test_marks_can_be_deleted(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "/")
        assert sessions.delete_session_mark(attdb.s1, attdb.monday, "AM")
        assert sessions.get_session_mark(attdb.s1, attdb.monday,
                                         "AM") is None

    def test_listing_filters_by_session_and_window(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "/")
        sessions.mark_session(attdb.s1, attdb.prev_monday, "PM", "O")
        assert len(sessions.list_session_marks(session="AM")) == 1
        assert len(sessions.list_session_marks(
            date_from=attdb.monday)) == 1


# ── 6. Rolling lessons up ──────────────────────────────────────────

class TestRollUp:

    def test_a_present_morning_becomes_a_present_am_mark(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        marks = sessions.roll_up_day(attdb.s1, attdb.monday)
        assert [m.session for m in marks] == ["AM"]
        assert marks[0].code == "/"
        assert marks[0].derived is True

    def test_the_afternoon_gets_its_own_present_code(self, attdb):
        core.save_register(attdb.pm_slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        marks = sessions.roll_up_day(attdb.s1, attdb.monday)
        assert marks[0].session == "PM"
        assert marks[0].code == "\\"

    def test_present_for_any_of_it_means_present(self, attdb):
        # Two morning lessons would be needed to test this properly, so
        # use the one AM slot plus a PM slot and check each half
        # separately: absent PM, present AM.
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        core.save_register(attdb.pm_slot, attdb.monday,
                           {attdb.s1: {"code": "O"}})
        marks = {m.session: m.code
                 for m in sessions.roll_up_day(attdb.s1, attdb.monday)}
        assert marks == {"AM": "/", "PM": "O"}

    def test_an_authorised_session_keeps_its_specific_code(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "I"}})
        marks = sessions.roll_up_day(attdb.s1, attdb.monday)
        assert marks[0].code == "I"

    def test_a_session_with_no_lessons_is_left_alone(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        sessions.roll_up_day(attdb.s1, attdb.monday)
        assert sessions.get_session_mark(attdb.s1, attdb.monday,
                                         "PM") is None

    def test_a_day_with_no_marks_produces_nothing(self, attdb):
        assert sessions.roll_up_day(attdb.s1, attdb.monday) == []

    def test_a_manual_mark_survives_a_roll_up(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "M",
                              recorded_by="office")
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        assert sessions.roll_up_day(attdb.s1, attdb.monday) == []
        assert sessions.get_session_mark(
            attdb.s1, attdb.monday, "AM").code == "M"

    def test_overwrite_manual_forces_it(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "M")
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        marks = sessions.roll_up_day(attdb.s1, attdb.monday,
                                     overwrite_manual=True)
        assert marks[0].code == "/"

    def test_a_derived_mark_is_rewritten_on_rerun(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        sessions.roll_up_day(attdb.s1, attdb.monday)
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "O"}})
        sessions.roll_up_day(attdb.s1, attdb.monday)
        assert sessions.get_session_mark(
            attdb.s1, attdb.monday, "AM").code == "O"

    def test_range_roll_up_covers_every_learner(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            sid: {"status": "Present"} for sid in attdb.students})
        written = sessions.roll_up_range(
            date_from=attdb.monday, date_to=attdb.monday)
        assert written == 3

    def test_range_roll_up_is_idempotent(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        sessions.roll_up_range(date_from=attdb.monday, date_to=attdb.monday)
        sessions.roll_up_range(date_from=attdb.monday, date_to=attdb.monday)
        assert len(sessions.list_session_marks(student_id=attdb.s1)) == 1


# ── 7. Statutory summary ───────────────────────────────────────────

class TestSessionSummary:

    def test_attendance_is_counted_over_possible_sessions(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "/")
        sessions.mark_session(attdb.s1, attdb.monday, "PM", "O")
        summary = sessions.session_summary(attdb.s1)
        assert summary.possible == 2
        assert summary.attended == 1
        assert summary.unauthorised == 1
        assert summary.percentage == 50.0

    def test_not_counted_sessions_leave_the_denominator(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "/")
        sessions.mark_session(attdb.s1, attdb.monday, "PM", "X")
        summary = sessions.session_summary(attdb.s1)
        assert summary.possible == 1
        assert summary.not_counted == 1
        assert summary.percentage == 100.0

    def test_authorised_absence_still_counts_against_attendance(self, attdb):
        sessions.mark_session(attdb.s1, attdb.monday, "AM", "I")
        summary = sessions.session_summary(attdb.s1)
        assert summary.authorised == 1
        assert summary.absences == 1
        assert summary.percentage == 0.0
        assert summary.unauthorised_percentage == 0.0

    def test_below_ninety_is_persistent_absence(self, attdb):
        base = next_weekday(0)
        for i in range(10):
            date_s = (base - _dt.timedelta(days=7 * i)).isoformat()
            sessions.mark_session(attdb.s1, date_s, "AM",
                                  "/" if i else "O")
        summary = sessions.session_summary(attdb.s1)
        assert summary.percentage == 90.0
        assert summary.persistently_absent is False

        sessions.mark_session(
            attdb.s1, (base - _dt.timedelta(days=77)).isoformat(), "AM", "O")
        assert sessions.session_summary(attdb.s1).persistently_absent is True

    def test_no_marks_means_no_percentage(self, attdb):
        summary = sessions.session_summary(attdb.s1)
        assert summary.possible == 0
        assert summary.percentage is None
        assert summary.persistently_absent is False
