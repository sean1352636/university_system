"""Tests for non-lesson registers.

Tutorials, assemblies, enrichment and supervised study: their own
roster, their own marks, the shared code vocabulary, and the ``required``
flag that decides whether missing one counts against a learner.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_activities as activities,
    attendance_weeks as weeks,
)


@pytest.fixture
def tutorial(attdb):
    """A required Monday tutorial with the whole of 12A on it."""
    activity = activities.create_activity({
        "name": "12A Tutorial", "kind": "Tutorial", "day": 1, "period": 1,
        "room": "R4", "staff": "Mr Patel",
    })
    activities.enrol_class_group(activity.activity_id, attdb.group)
    return activity


# ── 1. Setting one up ──────────────────────────────────────────────

class TestActivities:

    def test_an_activity_can_be_created(self, attdb):
        activity = activities.create_activity({"name": "Choir",
                                               "kind": "Enrichment"})
        assert activity.activity_id > 0
        assert activity.kind == "Enrichment"

    def test_pastoral_kinds_are_required_by_default(self, attdb):
        activity = activities.create_activity({"name": "Assembly",
                                               "kind": "Assembly"})
        assert activity.required is True

    def test_voluntary_kinds_are_not(self, attdb):
        # Reporting somebody as a 62% attender because they stopped
        # going to badminton helps nobody.
        activity = activities.create_activity({"name": "Badminton",
                                               "kind": "Sport"})
        assert activity.required is False

    def test_required_can_be_overridden(self, attdb):
        activity = activities.create_activity({"name": "Choir",
                                               "kind": "Enrichment",
                                               "required": True})
        assert activity.required is True

    def test_names_are_unique(self, attdb):
        activities.create_activity({"name": "Choir"})
        with pytest.raises(core.ValidationError, match="already exists"):
            activities.create_activity({"name": "Choir"})

    def test_a_name_is_required(self, attdb):
        with pytest.raises(core.ValidationError, match="name is required"):
            activities.create_activity({"name": "  "})

    def test_an_unknown_kind_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Kind must be"):
            activities.create_activity({"name": "Thing", "kind": "Jousting"})

    def test_a_bad_day_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Day must be"):
            activities.create_activity({"name": "Weekend club", "day": 6})

    def test_an_end_before_a_start_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="on or after"):
            activities.create_activity({"name": "Short course",
                                        "start_date": "2026-03-01",
                                        "end_date": "2026-02-01"})

    def test_archiving_hides_it_without_losing_it(self, attdb, tutorial):
        activities.archive_activity(tutorial.activity_id)
        assert activities.list_activities() == []
        assert activities.list_activities(active_only=False)

    def test_an_activity_can_be_updated(self, attdb, tutorial):
        out = activities.update_activity(tutorial.activity_id,
                                         {"room": "R9"})
        assert out.room == "R9"


# ── 2. Roster ──────────────────────────────────────────────────────

class TestRoster:

    def test_a_class_group_can_be_enrolled(self, attdb, tutorial):
        assert activities.count_members(tutorial.activity_id) == 3

    def test_a_learner_can_be_added(self, attdb):
        activity = activities.create_activity({"name": "Choir"})
        assert activities.add_member(activity.activity_id, attdb.s1) is True
        assert activities.list_members(activity.activity_id) == [attdb.s1]

    def test_an_unknown_learner_is_rejected(self, attdb):
        activity = activities.create_activity({"name": "Choir"})
        with pytest.raises(core.ValidationError, match="No student"):
            activities.add_member(activity.activity_id, "NOPE")

    def test_adding_twice_is_harmless(self, attdb):
        activity = activities.create_activity({"name": "Choir"})
        activities.add_member(activity.activity_id, attdb.s1)
        activities.add_member(activity.activity_id, attdb.s1)
        assert activities.count_members(activity.activity_id) == 1

    def test_removing_dates_them_out_rather_than_deleting(self, attdb,
                                                          tutorial):
        activities.remove_member(tutorial.activity_id, attdb.s1,
                                 left_on=attdb.monday)
        assert attdb.s1 not in activities.list_members(tutorial.activity_id)
        # Still on the roster as at an earlier date, so their old marks
        # continue to make sense.
        earlier = (_dt.date.fromisoformat(attdb.monday)
                   - _dt.timedelta(days=7)).isoformat()
        assert attdb.s1 in activities.list_members(tutorial.activity_id,
                                                   on=earlier)

    def test_a_learners_activities_are_listed(self, attdb, tutorial):
        assert [a.activity_id for a in
                activities.activities_for_student(attdb.s1)] == \
            [tutorial.activity_id]


# ── 3. When it meets ───────────────────────────────────────────────

class TestMeeting:

    def test_it_meets_on_its_weekday(self, attdb, tutorial):
        assert activities.meets_on(tutorial.activity_id, attdb.monday) is True

    def test_it_does_not_meet_on_other_days(self, attdb, tutorial):
        assert activities.meets_on(tutorial.activity_id,
                                   attdb.tuesday) is False

    def test_an_archived_activity_never_meets(self, attdb, tutorial):
        activities.archive_activity(tutorial.activity_id)
        assert activities.meets_on(tutorial.activity_id, attdb.monday) is False

    def test_a_date_range_bounds_it(self, attdb, tutorial):
        activities.update_activity(tutorial.activity_id,
                                   {"start_date": attdb.next_monday})
        assert activities.meets_on(tutorial.activity_id, attdb.monday) is False
        assert activities.meets_on(tutorial.activity_id,
                                   attdb.next_monday) is True

    def test_a_fortnightly_activity_skips_its_off_week(self, attdb, tutorial):
        weeks.set_pattern(cycle_weeks=2, anchor_date=attdb.monday)
        activities.update_activity(tutorial.activity_id, {"week": "A"})
        assert activities.meets_on(tutorial.activity_id, attdb.monday) is True
        assert activities.meets_on(tutorial.activity_id,
                                   attdb.next_monday) is False

    def test_meeting_dates_are_listed(self, attdb, tutorial):
        dates = activities.meeting_dates(tutorial.activity_id,
                                         attdb.monday, attdb.next_monday)
        assert attdb.monday in dates
        assert attdb.tuesday not in dates

    def test_todays_activities_are_listed(self, attdb, tutorial):
        assert [a.activity_id for a in
                activities.today_activities(attdb.monday)] == \
            [tutorial.activity_id]


# ── 4. Marking ─────────────────────────────────────────────────────

class TestMarking:

    def test_the_register_shows_the_roster(self, attdb, tutorial):
        entries = activities.register_view(tutorial.activity_id,
                                           attdb.monday)
        assert [e.student_id for e in entries] == attdb.students
        assert all(e.mark is None for e in entries)

    def test_marks_can_be_saved(self, attdb, tutorial):
        written = activities.save_register(
            tutorial.activity_id, attdb.monday,
            {attdb.s1: {"code": "/"}, attdb.s2: {"code": "N"}})
        assert written == 2
        entries = {e.student_id: e for e in
                   activities.register_view(tutorial.activity_id,
                                            attdb.monday)}
        assert entries[attdb.s1].mark.code == "/"
        assert entries[attdb.s2].mark.attending is False

    def test_a_status_works_instead_of_a_code(self, attdb, tutorial):
        activities.save_register(tutorial.activity_id, attdb.monday,
                                 {attdb.s1: {"status": "Absent"}})
        mark = activities.list_marks(activity_id=tutorial.activity_id)[0]
        assert mark.status == "Absent"

    def test_somebody_off_the_roster_is_rejected(self, attdb):
        activity = activities.create_activity({"name": "Choir"})
        activities.add_member(activity.activity_id, attdb.s1)
        with pytest.raises(core.ValidationError, match="not on the roster"):
            activities.save_register(activity.activity_id, attdb.monday,
                                     {attdb.s2: {"code": "/"}})

    def test_saving_again_updates_rather_than_duplicates(self, attdb,
                                                          tutorial):
        activities.save_register(tutorial.activity_id, attdb.monday,
                                 {attdb.s1: {"code": "/"}})
        activities.save_register(tutorial.activity_id, attdb.monday,
                                 {attdb.s1: {"code": "I"}})
        marks = activities.list_marks(activity_id=tutorial.activity_id,
                                      date=attdb.monday)
        assert len(marks) == 1
        assert marks[0].code == "I"

    def test_mark_all_covers_the_roster(self, attdb, tutorial):
        assert activities.mark_all(tutorial.activity_id, attdb.monday,
                                   "/") == 3

    def test_mark_all_can_be_narrowed(self, attdb, tutorial):
        assert activities.mark_all(tutorial.activity_id, attdb.monday, "/",
                                   student_ids=[attdb.s1]) == 1

    def test_a_mark_can_be_deleted(self, attdb, tutorial):
        activities.save_register(tutorial.activity_id, attdb.monday,
                                 {attdb.s1: {"code": "/"}})
        assert activities.delete_mark(tutorial.activity_id, attdb.s1,
                                      attdb.monday) is True


# ── 5. Summaries and gaps ──────────────────────────────────────────

class TestSummaries:

    def test_an_activity_summary_counts_meanings(self, attdb, tutorial):
        activities.save_register(tutorial.activity_id, attdb.monday, {
            attdb.s1: {"code": "/"}, attdb.s2: {"code": "I"},
            attdb.s3: {"code": "O"}})
        summary = activities.summary_for_activity(tutorial.activity_id)
        assert (summary.attending, summary.authorised,
                summary.unauthorised) == (1, 1, 1)
        assert summary.percentage == pytest.approx(33.3, abs=0.1)

    def test_not_counted_codes_leave_the_denominator(self, attdb, tutorial):
        activities.save_register(tutorial.activity_id, attdb.monday, {
            attdb.s1: {"code": "/"}, attdb.s2: {"code": "Y"}})
        summary = activities.summary_for_activity(tutorial.activity_id)
        assert summary.possible == 1
        assert summary.percentage == 100.0

    def test_a_learner_summary_counts_required_activities_only(self, attdb,
                                                                tutorial):
        club = activities.create_activity({"name": "Badminton",
                                           "kind": "Sport"})
        activities.add_member(club.activity_id, attdb.s1)
        activities.save_register(tutorial.activity_id, attdb.monday,
                                 {attdb.s1: {"code": "/"}})
        activities.save_register(club.activity_id, attdb.monday,
                                 {attdb.s1: {"code": "O"}})
        required_only = activities.summary_for_student(attdb.s1)
        assert required_only.sessions == 1
        assert required_only.percentage == 100.0
        everything = activities.summary_for_student(attdb.s1,
                                                    required_only=False)
        assert everything.sessions == 2

    def test_per_student_summaries_are_produced(self, attdb, tutorial):
        activities.mark_all(tutorial.activity_id, attdb.monday, "/")
        per = activities.per_student_summary(tutorial.activity_id)
        assert set(per) == set(attdb.students)

    def test_an_unmarked_meeting_is_reported(self, attdb, tutorial):
        missing = activities.missing_registers(date_from=attdb.monday,
                                                date_to=attdb.monday)
        assert [m.activity.activity_id for m in missing] == \
            [tutorial.activity_id]
        assert missing[0].expected == 3

    def test_a_marked_meeting_is_not(self, attdb, tutorial):
        activities.mark_all(tutorial.activity_id, attdb.monday, "/")
        assert activities.missing_registers(date_from=attdb.monday,
                                            date_to=attdb.monday) == []

    def test_a_partly_marked_meeting_still_counts_as_missing(self, attdb,
                                                              tutorial):
        activities.save_register(tutorial.activity_id, attdb.monday,
                                 {attdb.s1: {"code": "/"}})
        missing = activities.missing_registers(date_from=attdb.monday,
                                                date_to=attdb.monday)
        assert missing[0].marked == 1
