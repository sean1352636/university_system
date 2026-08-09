"""Tests for emergency roll call.

Section 2 holds the property the whole module exists for: the list is
frozen when the alarm sounds, and a register edited during the
evacuation cannot remove a name from it.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
    attendance_rollcall as rollcall,
)


# ── 1. Who is on site ──────────────────────────────────────────────

class TestPresence:

    def test_a_marked_learner_is_in_a_lesson(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        found = {p.student_id: p for p in
                 rollcall.expected_on_site(date=attdb.monday,
                                           at_time="09:30")}
        assert found[attdb.s1].reason == rollcall.IN_LESSON
        assert found[attdb.s1].on_site is True

    def test_the_room_travels_with_them(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        found = {p.student_id: p for p in
                 rollcall.expected_on_site(date=attdb.monday,
                                           at_time="09:30")}
        assert found[attdb.s1].room == "R1"

    def test_an_absent_learner_is_not_on_site(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "O"}})
        found = {p.student_id: p for p in
                 rollcall.expected_on_site(date=attdb.monday,
                                           at_time="09:30")}
        assert found[attdb.s1].reason == rollcall.ABSENT
        assert found[attdb.s1].on_site is False

    def test_an_off_site_learner_is_accounted_for_elsewhere(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "V",
                                       "offsite_location": "Tate Modern"}})
        found = {p.student_id: p for p in
                 rollcall.expected_on_site(date=attdb.monday,
                                           at_time="09:30")}
        assert found[attdb.s1].reason == rollcall.OFF_SITE
        assert found[attdb.s1].on_site is False

    def test_somebody_who_went_home_is_not_at_the_assembly_point(self,
                                                                 attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        reg.record_departure(attdb.slot, attdb.monday, attdb.s1, "09:30")
        found = {p.student_id: p for p in
                 rollcall.expected_on_site(date=attdb.monday,
                                           at_time="09:45")}
        assert found[attdb.s1].reason == rollcall.LEFT_EARLY

    def test_an_unmarked_but_timetabled_learner_is_expected(self, attdb):
        # An unmarked register is not evidence that somebody is absent.
        found = {p.student_id: p for p in
                 rollcall.expected_on_site(date=attdb.monday,
                                           at_time="09:30")}
        assert found[attdb.s1].reason == rollcall.EXPECTED_UNMARKED
        assert found[attdb.s1].on_site is True

    def test_a_learner_with_no_lessons_is_not_expected(self, attdb):
        found = {p.student_id: p for p in
                 rollcall.expected_on_site(date=attdb.tuesday,
                                           at_time="09:30")}
        assert found[attdb.s1].reason == rollcall.NOT_TIMETABLED
        assert found[attdb.s1].on_site is False

    def test_the_on_site_list_is_just_the_people_expected_out(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"},
                            attdb.s2: {"code": "O"}})
        on_site = {p.student_id for p in
                   rollcall.on_site_list(date=attdb.monday,
                                         at_time="09:30")}
        assert attdb.s1 in on_site
        assert attdb.s2 not in on_site

    def test_the_head_count_groups_by_reason(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        counts = rollcall.head_count(date=attdb.monday)
        assert counts.get(rollcall.IN_LESSON) == 1


# ── 2. The frozen list ─────────────────────────────────────────────

class TestDrill:

    def test_starting_a_drill_freezes_the_list(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {sid: {"status": "Present"}
                            for sid in attdb.students})
        drill = rollcall.start_drill(date=attdb.monday, at_time="09:30",
                                     started_by="head")
        assert drill.expected == 3
        assert len(drill.snapshot) == 3

    def test_editing_a_register_does_not_shrink_the_list(self, attdb):
        # The one failure mode a roll call cannot have.
        core.save_register(attdb.slot, attdb.monday,
                           {sid: {"status": "Present"}
                            for sid in attdb.students})
        drill = rollcall.start_drill(date=attdb.monday, at_time="09:30")
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "O"}})
        assert rollcall.get_drill(drill.drill_id).expected == 3
        assert attdb.s1 in [p.student_id for p in
                            rollcall.status(drill.drill_id).missing]

    def test_two_drills_cannot_run_at_once(self, attdb):
        rollcall.start_drill(date=attdb.monday, at_time="09:30")
        with pytest.raises(core.ValidationError, match="still running"):
            rollcall.start_drill(date=attdb.monday, at_time="09:35")

    def test_an_unknown_kind_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Kind must be"):
            rollcall.start_drill(kind="Picnic", date=attdb.monday)

    def test_the_running_drill_is_findable(self, attdb):
        drill = rollcall.start_drill(date=attdb.monday, at_time="09:30")
        assert rollcall.current_drill().drill_id == drill.drill_id


# ── 3. Marshalling ─────────────────────────────────────────────────

class TestMarshalling:

    @pytest.fixture
    def running(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {sid: {"status": "Present"}
                            for sid in attdb.students})
        return rollcall.start_drill(date=attdb.monday, at_time="09:30",
                                    started_by="head",
                                    assembly_point="Car park")

    def test_everybody_starts_unaccounted_for(self, attdb, running):
        state = rollcall.status(running.drill_id)
        assert state.outstanding == 3
        assert state.complete is False

    def test_people_can_be_ticked_off(self, attdb, running):
        assert rollcall.account_for(running.drill_id,
                                    [attdb.s1, attdb.s2],
                                    marked_by="marshal") == 2
        state = rollcall.status(running.drill_id)
        assert state.counted == 2
        assert [p.student_id for p in state.missing] == [attdb.s3]

    def test_a_whole_group_can_be_ticked_off(self, attdb, running):
        assert rollcall.account_for_group(running.drill_id, attdb.group,
                                          marked_by="marshal") == 3
        assert rollcall.status(running.drill_id).complete is True

    def test_a_group_member_who_was_never_on_site_is_not_ticked(self, attdb):
        # Marking somebody accounted for who was never here reads as a
        # false all-clear.
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"},
                            attdb.s2: {"code": "O"},
                            attdb.s3: {"code": "O"}})
        drill = rollcall.start_drill(date=attdb.monday, at_time="09:30")
        assert rollcall.account_for_group(drill.drill_id, attdb.group) == 1

    def test_somebody_can_be_marked_missing_explicitly(self, attdb,
                                                        running):
        rollcall.account_for(running.drill_id, attdb.students)
        rollcall.mark_missing(running.drill_id, attdb.s2,
                              marked_by="marshal")
        assert [p.student_id for p in
                rollcall.unaccounted(running.drill_id)] == [attdb.s2]

    def test_somebody_found_off_site_can_be_excused(self, attdb, running):
        rollcall.excuse(running.drill_id, attdb.s1,
                        reason="Collected by parent at 09:15")
        state = rollcall.status(running.drill_id)
        assert attdb.s1 in state.excused
        assert attdb.s1 not in [p.student_id for p in state.missing]

    def test_an_empty_list_is_rejected(self, attdb, running):
        with pytest.raises(core.ValidationError, match="No students given"):
            rollcall.account_for(running.drill_id, [])

    def test_a_closed_drill_cannot_be_marked(self, attdb, running):
        rollcall.account_for(running.drill_id, attdb.students)
        rollcall.close_drill(running.drill_id, closed_by="head")
        with pytest.raises(core.ValidationError, match="reopen it"):
            rollcall.account_for(running.drill_id, [attdb.s1])

    def test_marks_are_logged(self, attdb, running):
        rollcall.account_for(running.drill_id, [attdb.s1],
                             marked_by="marshal")
        marks = rollcall.list_marks(running.drill_id)
        assert marks[0].marked_by == "marshal"


# ── 4. Closing ─────────────────────────────────────────────────────

class TestClosing:

    @pytest.fixture
    def running(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {sid: {"status": "Present"}
                            for sid in attdb.students})
        return rollcall.start_drill(date=attdb.monday, at_time="09:30",
                                    started_by="head")

    def test_closing_refuses_while_anybody_is_missing(self, attdb, running):
        rollcall.account_for(running.drill_id, [attdb.s1])
        with pytest.raises(core.ValidationError, match="unaccounted for"):
            rollcall.close_drill(running.drill_id, closed_by="head")

    def test_closing_works_once_everybody_is_out(self, attdb, running):
        rollcall.account_for(running.drill_id, attdb.students)
        out = rollcall.close_drill(running.drill_id, closed_by="head")
        assert out.state == rollcall.CLOSED
        assert out.duration_seconds is not None

    def test_closing_can_be_overridden_deliberately(self, attdb, running):
        out = rollcall.close_drill(running.drill_id, closed_by="head",
                                   allow_incomplete=True)
        assert out.state == rollcall.CLOSED

    def test_a_drill_can_be_abandoned(self, attdb, running):
        out = rollcall.abandon_drill(running.drill_id, reason="False alarm",
                                     actor="head")
        assert out.state == rollcall.ABANDONED

    def test_abandoning_needs_a_reason(self, attdb, running):
        with pytest.raises(core.ValidationError, match="reason is required"):
            rollcall.abandon_drill(running.drill_id, reason="  ")

    def test_a_closed_drill_can_be_reopened(self, attdb, running):
        rollcall.account_for(running.drill_id, attdb.students)
        rollcall.close_drill(running.drill_id, closed_by="head")
        out = rollcall.reopen_drill(running.drill_id,
                                    reason="One learner turned up")
        assert out.is_running is True


# ── 5. The write-up ────────────────────────────────────────────────

class TestReport:

    def test_the_report_names_who_was_missing(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {sid: {"status": "Present"}
                            for sid in attdb.students})
        drill = rollcall.start_drill(date=attdb.monday, at_time="09:30",
                                     started_by="head",
                                     assembly_point="Car park")
        rollcall.account_for(drill.drill_id, [attdb.s1, attdb.s2])
        rollcall.close_drill(drill.drill_id, closed_by="head",
                             allow_incomplete=True)
        report = rollcall.drill_report(drill.drill_id)
        assert report["expected"] == 3
        assert report["accounted"] == 2
        assert [m["student_id"] for m in report["missing"]] == [attdb.s3]
        assert report["assembly_point"] == "Car park"

    def test_history_excludes_a_running_drill(self, attdb):
        rollcall.start_drill(date=attdb.monday, at_time="09:30")
        assert rollcall.drill_history() == []

    def test_history_includes_a_closed_one(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {sid: {"status": "Present"}
                            for sid in attdb.students})
        drill = rollcall.start_drill(date=attdb.monday, at_time="09:30")
        rollcall.account_for(drill.drill_id, attdb.students)
        rollcall.close_drill(drill.drill_id, closed_by="head")
        assert len(rollcall.drill_history()) == 1
