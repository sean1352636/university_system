"""Tests for cover registers.

Covers arranging and allocating cover, who is allowed to mark a covered
register, the cover sheet the office prints, and the load counts that
say whether cover is being shared fairly.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_cover as cover,
    attendance_register as reg,
)


@pytest.fixture
def taught(attdb):
    """The Monday-morning slot, with a named teacher on its group."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    cg.update_group(attdb.group, {"course_id": 1, "group_name": "12A",
                                  "teacher": "Mr Patel"})
    return attdb


# ── 1. Arranging ───────────────────────────────────────────────────

class TestArrange:

    def test_cover_can_be_arranged(self, attdb):
        arranged = cover.arrange(attdb.slot, attdb.monday,
                                 absent_teacher="Mr Patel",
                                 reason="Illness")
        assert arranged.state == cover.UNALLOCATED
        assert arranged.reason == "Illness"

    def test_naming_a_cover_teacher_allocates_it(self, attdb):
        arranged = cover.arrange(attdb.slot, attdb.monday,
                                 absent_teacher="Mr Patel",
                                 cover_teacher="Ms Okafor")
        assert arranged.state == cover.ALLOCATED
        assert arranged.is_allocated is True

    def test_the_absent_teacher_defaults_to_the_timetable(self, taught):
        arranged = cover.arrange(taught.slot, taught.monday)
        assert arranged.absent_teacher == "Mr Patel"

    def test_nobody_covers_their_own_lesson(self, attdb):
        with pytest.raises(core.ValidationError, match="their own lesson"):
            cover.arrange(attdb.slot, attdb.monday,
                          absent_teacher="Mr Patel",
                          cover_teacher="mr patel")

    def test_re_arranging_updates_rather_than_duplicates(self, attdb):
        first = cover.arrange(attdb.slot, attdb.monday, reason="Illness")
        second = cover.arrange(attdb.slot, attdb.monday, reason="Trip")
        assert first.cover_id == second.cover_id
        assert second.reason == "Trip"
        assert len(cover.list_cover(date=attdb.monday)) == 1

    def test_an_unknown_reason_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Reason must be"):
            cover.arrange(attdb.slot, attdb.monday, reason="Hungover")

    def test_a_missing_slot_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No slot"):
            cover.arrange(9999, attdb.monday)


# ── 2. Allocating and cancelling ───────────────────────────────────

class TestAllocate:

    def test_an_unallocated_lesson_can_be_given_a_name(self, attdb):
        arranged = cover.arrange(attdb.slot, attdb.monday,
                                 absent_teacher="Mr Patel")
        allocated = cover.allocate(arranged.cover_id, "Ms Okafor")
        assert allocated.cover_teacher == "Ms Okafor"
        assert allocated.allocated_at is not None

    def test_unallocated_lessons_are_listed(self, attdb):
        cover.arrange(attdb.slot, attdb.monday, absent_teacher="Mr Patel")
        assert len(cover.unallocated(date_from=attdb.monday)) == 1

    def test_allocating_clears_it_from_the_list(self, attdb):
        arranged = cover.arrange(attdb.slot, attdb.monday,
                                 absent_teacher="Mr Patel")
        cover.allocate(arranged.cover_id, "Ms Okafor")
        assert cover.unallocated(date_from=attdb.monday) == []

    def test_a_cancelled_arrangement_cannot_be_allocated(self, attdb):
        arranged = cover.arrange(attdb.slot, attdb.monday)
        cover.cancel(arranged.cover_id, reason="Came in after all")
        with pytest.raises(core.ValidationError, match="cancelled"):
            cover.allocate(arranged.cover_id, "Ms Okafor")

    def test_cancelling_ends_the_arrangement(self, attdb):
        arranged = cover.arrange(attdb.slot, attdb.monday)
        cancelled = cover.cancel(arranged.cover_id, reason="False alarm")
        assert cancelled.state == cover.CANCELLED
        assert cancelled.is_live is False
        assert cover.is_covered(attdb.slot, attdb.monday) is False

    def test_cancelled_rows_are_hidden_by_default(self, attdb):
        arranged = cover.arrange(attdb.slot, attdb.monday)
        cover.cancel(arranged.cover_id, reason="False alarm")
        assert cover.list_cover(date=attdb.monday) == []
        assert cover.list_cover(date=attdb.monday, include_cancelled=True)


# ── 3. Who may mark ────────────────────────────────────────────────

class TestPermission:

    def test_the_usual_teacher_may_mark_their_own(self, taught):
        assert cover.can_mark(taught.slot, taught.monday, "Mr Patel") is True

    def test_a_stranger_may_not(self, taught):
        assert cover.can_mark(taught.slot, taught.monday, "Ms Okafor") is False

    def test_the_allocated_cover_teacher_may(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        assert cover.can_mark(taught.slot, taught.monday, "Ms Okafor") is True

    def test_the_usual_teacher_still_may_while_covered(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        assert cover.can_mark(taught.slot, taught.monday, "Mr Patel") is True

    def test_a_third_party_may_not_while_covered(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        assert cover.can_mark(taught.slot, taught.monday, "Mr Rees") is False

    def test_an_unallocated_lesson_is_open_to_anyone(self, taught):
        # Better a marked register than a hunt for the right signature.
        cover.arrange(taught.slot, taught.monday)
        assert cover.can_mark(taught.slot, taught.monday, "Mr Rees") is True

    def test_nobody_is_not_somebody(self, taught):
        assert cover.can_mark(taught.slot, taught.monday, None) is False

    def test_who_should_mark_names_the_cover_teacher(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        assert cover.who_should_mark(taught.slot, taught.monday) == "Ms Okafor"

    def test_who_should_mark_falls_back_to_the_usual_teacher(self, taught):
        assert cover.who_should_mark(taught.slot, taught.monday) == "Mr Patel"

    def test_asserting_explains_who_should(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        with pytest.raises(core.ValidationError, match="Ms Okafor is"):
            cover.assert_can_mark(taught.slot, taught.monday, "Mr Rees")


# ── 4. Saving a cover register ─────────────────────────────────────

class TestSaving:

    def test_the_cover_teacher_can_save(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        written = cover.save_cover_register(
            taught.slot, taught.monday,
            {taught.s1: {"status": "Present"}}, cover_teacher="Ms Okafor")
        assert written == 1

    def test_marks_are_stamped_as_cover(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        cover.save_cover_register(
            taught.slot, taught.monday,
            {taught.s1: {"status": "Present"}}, cover_teacher="Ms Okafor")
        record = core.get_record_for(taught.slot, taught.s1, taught.monday)
        assert record.data_source == cover.COVER_SOURCE

    def test_a_kiosk_source_in_the_payload_is_respected(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        cover.save_cover_register(
            taught.slot, taught.monday,
            {taught.s1: {"status": "Present", "data_source": "kiosk"}},
            cover_teacher="Ms Okafor")
        record = core.get_record_for(taught.slot, taught.s1, taught.monday)
        assert record.data_source == "kiosk"

    def test_the_wrong_person_cannot_save(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        with pytest.raises(core.ValidationError, match="not down to take"):
            cover.save_cover_register(
                taught.slot, taught.monday,
                {taught.s1: {"status": "Present"}}, cover_teacher="Mr Rees")

    def test_the_cover_teacher_signs_the_register_off(self, taught):
        cover.arrange(taught.slot, taught.monday, cover_teacher="Ms Okafor")
        cover.save_cover_register(
            taught.slot, taught.monday,
            {sid: {"status": "Present"} for sid in taught.students},
            cover_teacher="Ms Okafor")
        session = cover.submit_cover_register(
            taught.slot, taught.monday, cover_teacher="Ms Okafor")
        assert session.submitted_by == "Ms Okafor"
        assert reg.is_locked(taught.slot, taught.monday) is True


# ── 5. The cover sheet ─────────────────────────────────────────────

class TestSheet:

    def test_the_sheet_carries_the_timetable_detail(self, attdb):
        cover.arrange(attdb.slot, attdb.monday, absent_teacher="Mr Patel",
                      cover_teacher="Ms Okafor")
        row = cover.today_sheet(attdb.monday)[0]
        assert row.group_name == "12A"
        assert row.period == 1
        assert row.expected == 3

    def test_an_unmarked_covered_lesson_is_flagged(self, attdb):
        cover.arrange(attdb.slot, attdb.monday, cover_teacher="Ms Okafor")
        assert cover.unmarked_cover(date=attdb.monday)

    def test_a_fully_marked_one_is_not(self, attdb):
        cover.arrange(attdb.slot, attdb.monday, cover_teacher="Ms Okafor")
        cover.save_cover_register(
            attdb.slot, attdb.monday,
            {sid: {"status": "Present"} for sid in attdb.students},
            cover_teacher="Ms Okafor")
        assert cover.unmarked_cover(date=attdb.monday) == []

    def test_the_sheet_is_in_period_order(self, attdb):
        cover.arrange(attdb.pm_slot, attdb.monday, cover_teacher="Ms Okafor")
        cover.arrange(attdb.slot, attdb.monday, cover_teacher="Mr Rees")
        assert [row.period for row in cover.today_sheet(attdb.monday)] == [1, 6]


# ── 6. Load ────────────────────────────────────────────────────────

class TestLoad:

    def test_cover_is_counted_per_teacher(self, attdb):
        cover.arrange(attdb.slot, attdb.monday, cover_teacher="Ms Okafor")
        cover.arrange(attdb.pm_slot, attdb.monday, cover_teacher="Ms Okafor")
        load = cover.cover_load()
        assert load[0].teacher == "Ms Okafor"
        assert load[0].lessons == 2
        assert load[0].dates == 1

    def test_absence_is_counted_from_the_other_side(self, attdb):
        cover.arrange(attdb.slot, attdb.monday, absent_teacher="Mr Patel")
        assert cover.absence_load()[0].teacher == "Mr Patel"

    def test_reasons_are_broken_down(self, attdb):
        cover.arrange(attdb.slot, attdb.monday, reason="Illness")
        cover.arrange(attdb.pm_slot, attdb.monday, reason="Illness")
        assert cover.reason_breakdown()["Illness"] == 2

    def test_cancelled_cover_does_not_count(self, attdb):
        arranged = cover.arrange(attdb.slot, attdb.monday,
                                 cover_teacher="Ms Okafor")
        cover.cancel(arranged.cover_id, reason="Came in")
        assert cover.cover_load() == []

    def test_marks_taken_under_cover_are_countable(self, attdb):
        cover.arrange(attdb.slot, attdb.monday, cover_teacher="Ms Okafor")
        cover.save_cover_register(
            attdb.slot, attdb.monday,
            {attdb.s1: {"status": "Present"}}, cover_teacher="Ms Okafor")
        assert cover.marks_taken_under_cover() == 1
