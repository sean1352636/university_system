"""Tests for register-taking nudges.

The sweep is idempotent and self-clearing: a register that gets taken
closes its own nudge rather than being chased again.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_cover as cover,
    attendance_nudges as nudges,
    attendance_register as reg,
)


def tomorrow_of(date: str) -> str:
    return (_dt.date.fromisoformat(date) + _dt.timedelta(days=1)).isoformat()


# ── 1. Raising ─────────────────────────────────────────────────────

class TestSweep:

    def test_an_unmarked_past_register_raises_a_nudge(self, attdb):
        result = nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                              date_from=attdb.prev_monday,
                              date_to=attdb.prev_monday)
        assert result.raised >= 1
        assert nudges.open_count() >= 1

    def test_todays_register_is_not_chased_yet(self, attdb):
        result = nudges.sweep(today=attdb.prev_monday,
                              date_from=attdb.prev_monday,
                              date_to=attdb.prev_monday)
        assert result.raised == 0

    def test_a_submitted_register_raises_nothing(self, attdb):
        core.save_register(
            attdb.slot, attdb.prev_monday,
            {sid: {"status": "Present"} for sid in attdb.students})
        reg.submit_register(attdb.slot, attdb.prev_monday,
                            submitted_by="teacher")
        result = nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                              date_from=attdb.prev_monday,
                              date_to=attdb.prev_monday)
        open_slots = {n.slot_id for n in result.nudges}
        assert attdb.slot not in open_slots

    def test_a_register_taken_later_closes_its_nudge(self, attdb):
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday, date_to=attdb.prev_monday)
        assert nudges.open_count() >= 1
        core.save_register(
            attdb.slot, attdb.prev_monday,
            {sid: {"status": "Present"} for sid in attdb.students})
        reg.submit_register(attdb.slot, attdb.prev_monday,
                            submitted_by="teacher")
        core.save_register(
            attdb.pm_slot, attdb.prev_monday,
            {sid: {"status": "Present"} for sid in attdb.students})
        reg.submit_register(attdb.pm_slot, attdb.prev_monday,
                            submitted_by="teacher")
        result = nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                              date_from=attdb.prev_monday,
                              date_to=attdb.prev_monday)
        assert result.resolved >= 1
        assert nudges.open_count() == 0

    def test_sweeping_twice_does_not_duplicate(self, attdb):
        today = tomorrow_of(attdb.prev_monday)
        nudges.sweep(today=today, date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        before = nudges.open_count()
        second = nudges.sweep(today=today, date_from=attdb.prev_monday,
                              date_to=attdb.prev_monday)
        assert second.raised == 0
        assert nudges.open_count() == before

    def test_a_slot_with_an_empty_roster_is_not_chased(self, attdb):
        # Group 2 has no members, so there is no register to miss.
        result = nudges.sweep(today=tomorrow_of(attdb.tuesday),
                              date_from=attdb.tuesday,
                              date_to=attdb.tuesday)
        assert attdb.empty_slot not in {n.slot_id for n in result.nudges}


# ── 2. Stages ──────────────────────────────────────────────────────

class TestStages:

    @pytest.mark.parametrize("age,stage", [
        (0, nudges.TEACHER),
        (1, nudges.TEACHER),
        (2, nudges.TEACHER),
        (3, nudges.HEAD_OF_DEPARTMENT),
        (6, nudges.HEAD_OF_DEPARTMENT),
        (7, nudges.SLT),
        (20, nudges.SLT),
    ])
    def test_age_decides_the_stage(self, attdb, age, stage):
        assert nudges.stage_for(age) == stage

    def test_an_old_register_escalates_on_the_next_sweep(self, attdb):
        day_after = tomorrow_of(attdb.prev_monday)
        nudges.sweep(today=day_after, date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        assert nudges.list_nudges(state=nudges.OPEN)[0].stage == \
            nudges.TEACHER
        much_later = (_dt.date.fromisoformat(attdb.prev_monday)
                      + _dt.timedelta(days=21)).isoformat()
        result = nudges.sweep(today=much_later,
                              date_from=attdb.prev_monday,
                              date_to=attdb.prev_monday)
        assert result.escalated >= 1
        assert nudges.list_nudges(state=nudges.OPEN)[0].stage == nudges.SLT

    def test_the_owner_is_whoever_should_have_taken_it(self, attdb):
        from education_system.systems.sixth_form.domain.academics.class_groups \
            import class_groups as cg
        cg.update_group(attdb.group, {"course_id": 1, "group_name": "12A",
                                      "teacher": "Mr Patel"})
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        assert nudges.list_nudges(state=nudges.OPEN)[0].owner == "Mr Patel"

    def test_a_covered_lesson_chases_the_cover_teacher(self, attdb):
        # Chasing the absent teacher for a lesson somebody else covered
        # is how a chase list loses its credibility.
        from education_system.systems.sixth_form.domain.academics.class_groups \
            import class_groups as cg
        cg.update_group(attdb.group, {"course_id": 1, "group_name": "12A",
                                      "teacher": "Mr Patel"})
        cover.arrange(attdb.slot, attdb.prev_monday,
                      cover_teacher="Ms Okafor")
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        owner = nudges.nudge_for(attdb.slot, attdb.prev_monday).owner
        assert owner == "Ms Okafor"


# ── 3. Managing ────────────────────────────────────────────────────

class TestManaging:

    @pytest.fixture
    def nudge(self, attdb):
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        return nudges.nudge_for(attdb.slot, attdb.prev_monday)

    def test_a_nudge_can_be_resolved(self, attdb, nudge):
        out = nudges.resolve(nudge.nudge_id, note="Taken on paper")
        assert out.state == nudges.RESOLVED

    def test_a_nudge_can_be_dismissed_with_a_reason(self, attdb, nudge):
        out = nudges.dismiss(nudge.nudge_id, reason="Group was on a trip")
        assert out.state == nudges.DISMISSED

    def test_dismissing_needs_a_reason(self, attdb, nudge):
        with pytest.raises(core.ValidationError, match="reason is required"):
            nudges.dismiss(nudge.nudge_id, reason="  ")

    def test_a_dismissed_nudge_stays_dismissed(self, attdb, nudge):
        nudges.dismiss(nudge.nudge_id, reason="Lesson never ran")
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        assert nudges.get_nudge(nudge.nudge_id).state == nudges.DISMISSED

    def test_an_unknown_nudge_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No nudge"):
            nudges.resolve(9999)


# ── 4. Digests and reporting ───────────────────────────────────────

class TestReporting:

    def test_digests_group_by_person(self, attdb):
        from education_system.systems.sixth_form.domain.academics.class_groups \
            import class_groups as cg
        cg.update_group(attdb.group, {"course_id": 1, "group_name": "12A",
                                      "teacher": "Mr Patel"})
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        digests = nudges.digests()
        assert digests[0].owner == "Mr Patel"
        assert len(digests[0].nudges) == 2       # both Monday lessons

    def test_a_digest_body_lists_the_registers(self, attdb):
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        body = nudges.digests()[0].body()
        assert "outstanding" in body
        assert attdb.prev_monday in body

    def test_worst_offenders_are_counted(self, attdb):
        from education_system.systems.sixth_form.domain.academics.class_groups \
            import class_groups as cg
        cg.update_group(attdb.group, {"course_id": 1, "group_name": "12A",
                                      "teacher": "Mr Patel"})
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        rows = nudges.worst_offenders(minimum=1)
        assert rows[0][0] == "Mr Patel"

    def test_habitually_missing_slots_are_counted(self, attdb):
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        assert nudges.slot_offenders(minimum=1)

    def test_the_chase_sheet_is_printable(self, attdb):
        nudges.sweep(today=tomorrow_of(attdb.prev_monday),
                     date_from=attdb.prev_monday,
                     date_to=attdb.prev_monday)
        assert any(attdb.prev_monday in line
                   for line in nudges.chase_sheet())
