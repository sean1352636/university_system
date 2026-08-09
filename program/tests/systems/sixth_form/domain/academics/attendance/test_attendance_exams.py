"""Tests for exam room registers.

The distinction that matters is late-but-fine versus late-enough-to-
report, which is why arrival times get written down at all.

``populate_from_entries`` is not covered here: it reaches into
:mod:`exam_entries`, whose validator needs a seeded subject list and
exam board that this fixture does not build.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_exams as exams,
)


@pytest.fixture
def sitting(attdb):
    """A 09:00 paper with all three learners seated."""
    out = exams.create_sitting({
        "paper_code": "9MA0/01", "paper_title": "Pure Mathematics 1",
        "subject": "Mathematics", "exam_board": "Edexcel",
        "date": attdb.monday, "start_time": "09:00", "end_time": "11:00",
        "room": "Sports Hall", "series": "Summer",
    })
    for seat, student_id in enumerate(attdb.students, 1):
        exams.add_candidate(out.sitting_id, student_id, seat=str(seat),
                            candidate_no=f"100{seat}")
    return out


# ── 1. Scheduling ──────────────────────────────────────────────────

class TestSittings:

    def test_a_sitting_can_be_scheduled(self, attdb):
        out = exams.create_sitting({"paper_code": "9MA0/01",
                                    "date": attdb.monday,
                                    "start_time": "09:00"})
        assert out.sitting_id > 0
        assert out.state == exams.PLANNED

    def test_a_paper_code_is_required(self, attdb):
        with pytest.raises(core.ValidationError, match="Paper code"):
            exams.create_sitting({"date": attdb.monday,
                                  "start_time": "09:00"})

    def test_an_end_before_the_start_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="after the start"):
            exams.create_sitting({"paper_code": "9MA0/01",
                                  "date": attdb.monday,
                                  "start_time": "09:00",
                                  "end_time": "08:00"})

    def test_the_reportable_time_is_derived(self, attdb, sitting):
        assert sitting.very_late_after == "10:00"

    def test_sittings_are_listed_by_date(self, attdb, sitting):
        assert [s.sitting_id for s in
                exams.list_sittings(date=attdb.monday)] == [sitting.sitting_id]


# ── 2. Candidates and seating ──────────────────────────────────────

class TestCandidates:

    def test_candidates_are_seated(self, attdb, sitting):
        plan = exams.seating_plan(sitting.sitting_id)
        assert [c.seat for c in plan.rows] == ["1", "2", "3"]
        assert plan.unseated == []

    def test_a_seat_cannot_be_double_booked(self, attdb, sitting):
        with pytest.raises(core.ValidationError, match="already"):
            exams.add_candidate(sitting.sitting_id, attdb.s1, seat="2")

    def test_a_candidate_can_be_moved(self, attdb, sitting):
        exams.add_candidate(sitting.sitting_id, attdb.s1, seat="9")
        assert exams.get_candidate(sitting.sitting_id, attdb.s1).seat == "9"

    def test_an_unknown_learner_is_rejected(self, attdb, sitting):
        with pytest.raises(core.ValidationError, match="No student"):
            exams.add_candidate(sitting.sitting_id, "NOPE")

    def test_names_can_be_joined_on(self, attdb, sitting):
        candidates = exams.list_candidates(sitting.sitting_id,
                                           with_names=True)
        assert candidates[0].full_name == "Ada Test"

    def test_a_candidate_can_be_removed(self, attdb, sitting):
        assert exams.remove_candidate(sitting.sitting_id, attdb.s3) is True
        assert len(exams.list_candidates(sitting.sitting_id)) == 2


# ── 3. Marking ─────────────────────────────────────────────────────

class TestMarking:

    def test_an_unmarked_candidate_is_unmarked(self, attdb, sitting):
        assert exams.get_candidate(sitting.sitting_id,
                                   attdb.s1).marked is False

    def test_marking_all_present_fills_the_gaps(self, attdb, sitting):
        assert exams.mark_all_present(sitting.sitting_id) == 3
        assert exams.summary(sitting.sitting_id).present == 3

    def test_marking_all_present_leaves_existing_marks(self, attdb, sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.ABSENT)
        assert exams.mark_all_present(sitting.sitting_id) == 2
        assert exams.get_candidate(sitting.sitting_id,
                                   attdb.s1).state == exams.ABSENT

    @pytest.mark.parametrize("arrival,expected", [
        ("09:00", exams.PRESENT),
        ("09:20", exams.LATE),
        ("10:00", exams.LATE),
        ("10:01", exams.VERY_LATE),
        ("10:45", exams.VERY_LATE),
    ])
    def test_the_arrival_time_decides_the_state(self, attdb, sitting,
                                                arrival, expected):
        candidate = exams.record_arrival(sitting.sitting_id, attdb.s1,
                                         arrival)
        assert candidate.state == expected

    def test_a_very_late_candidate_is_reportable(self, attdb, sitting):
        # Past the hour it stops being an internal matter.
        candidate = exams.record_arrival(sitting.sitting_id, attdb.s1,
                                         "10:30")
        assert candidate.reportable is True
        assert candidate.minutes_late == 90

    def test_a_merely_late_candidate_is_not(self, attdb, sitting):
        candidate = exams.record_arrival(sitting.sitting_id, attdb.s1,
                                         "09:10")
        assert candidate.reportable is False

    def test_an_absence_gets_a_default_reason(self, attdb, sitting):
        candidate = exams.mark_candidate(sitting.sitting_id, attdb.s1,
                                         exams.ABSENT)
        assert candidate.absence_reason == "Unexplained"

    def test_an_absence_reason_can_be_decided_afterwards(self, attdb,
                                                          sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.ABSENT)
        candidate = exams.set_absence_reason(
            sitting.sitting_id, attdb.s1, "Illness (evidence received)")
        assert candidate.absence_reason == "Illness (evidence received)"

    def test_a_reason_does_not_apply_to_somebody_who_sat_it(self, attdb,
                                                             sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.PRESENT)
        with pytest.raises(core.ValidationError, match="does not apply"):
            exams.set_absence_reason(sitting.sitting_id, attdb.s1,
                                     "Unexplained")

    def test_an_unknown_state_is_rejected(self, attdb, sitting):
        with pytest.raises(core.ValidationError, match="State must be"):
            exams.mark_candidate(sitting.sitting_id, attdb.s1, "Wandering")

    def test_somebody_not_entered_cannot_be_marked(self, attdb, sitting):
        exams.remove_candidate(sitting.sitting_id, attdb.s3)
        with pytest.raises(core.ValidationError, match="not a candidate"):
            exams.mark_candidate(sitting.sitting_id, attdb.s3, exams.PRESENT)

    def test_marking_opens_the_sitting(self, attdb, sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.PRESENT)
        assert exams.get_sitting(sitting.sitting_id).state == exams.OPEN


# ── 4. Sign-off ────────────────────────────────────────────────────

class TestSignOff:

    def test_an_incomplete_register_cannot_be_signed(self, attdb, sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.PRESENT)
        with pytest.raises(core.ValidationError, match="still unmarked"):
            exams.sign_off(sitting.sitting_id, invigilator="J Smith")

    def test_a_complete_register_signs_off(self, attdb, sitting):
        exams.mark_all_present(sitting.sitting_id)
        out = exams.sign_off(sitting.sitting_id, invigilator="J Smith")
        assert out.is_signed_off is True
        assert out.signed_off_by == "J Smith"

    def test_an_override_allows_an_incomplete_one(self, attdb, sitting):
        out = exams.sign_off(sitting.sitting_id, invigilator="J Smith",
                             allow_incomplete=True)
        assert out.is_signed_off is True

    def test_an_invigilator_is_required(self, attdb, sitting):
        exams.mark_all_present(sitting.sitting_id)
        with pytest.raises(core.ValidationError, match="has to sign"):
            exams.sign_off(sitting.sitting_id, invigilator="  ")

    def test_a_signed_register_refuses_further_marking(self, attdb, sitting):
        exams.mark_all_present(sitting.sitting_id)
        exams.sign_off(sitting.sitting_id, invigilator="J Smith")
        with pytest.raises(core.ValidationError, match="signed off"):
            exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.ABSENT)

    def test_reopening_needs_a_reason(self, attdb, sitting):
        exams.mark_all_present(sitting.sitting_id)
        exams.sign_off(sitting.sitting_id, invigilator="J Smith")
        with pytest.raises(core.ValidationError, match="reason is required"):
            exams.reopen(sitting.sitting_id, reason="  ")

    def test_reopening_is_the_way_back_in(self, attdb, sitting):
        exams.mark_all_present(sitting.sitting_id)
        exams.sign_off(sitting.sitting_id, invigilator="J Smith")
        exams.reopen(sitting.sitting_id, reason="Miscounted seat 3",
                     actor="head")
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.ABSENT)
        assert exams.get_candidate(sitting.sitting_id,
                                   attdb.s1).state == exams.ABSENT

    def test_a_signed_register_cannot_be_deleted(self, attdb, sitting):
        exams.mark_all_present(sitting.sitting_id)
        exams.sign_off(sitting.sitting_id, invigilator="J Smith")
        with pytest.raises(core.ValidationError, match="retained document"):
            exams.delete_sitting(sitting.sitting_id)


# ── 5. Reporting ───────────────────────────────────────────────────

class TestReporting:

    def test_the_summary_counts_everything(self, attdb, sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.PRESENT)
        exams.record_arrival(sitting.sitting_id, attdb.s2, "10:30")
        exams.mark_candidate(sitting.sitting_id, attdb.s3, exams.ABSENT)
        summary = exams.summary(sitting.sitting_id)
        assert (summary.entered, summary.present, summary.very_late,
                summary.absent) == (3, 1, 1, 1)
        assert summary.sat == 2
        assert summary.complete is True

    def test_the_attendance_rate_excludes_withdrawals(self, attdb, sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.PRESENT)
        exams.mark_candidate(sitting.sitting_id, attdb.s2, exams.PRESENT)
        exams.mark_candidate(sitting.sitting_id, attdb.s3, exams.WITHDRAWN)
        assert exams.summary(sitting.sitting_id).attendance_rate == 100.0

    def test_absentees_are_listed_for_chasing(self, attdb, sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.ABSENT)
        rows = exams.absentees(date=attdb.monday)
        assert [c.student_id for _s, c in rows] == [attdb.s1]

    def test_reportable_candidates_are_listed(self, attdb, sitting):
        exams.record_arrival(sitting.sitting_id, attdb.s1, "10:30")
        exams.mark_candidate(sitting.sitting_id, attdb.s2, exams.REMOVED)
        rows = exams.reportable(date_from=attdb.monday, date_to=attdb.monday)
        assert {c.student_id for _s, c in rows} == {attdb.s1, attdb.s2}

    def test_a_candidates_history_is_readable(self, attdb, sitting):
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.PRESENT)
        history = exams.student_record(attdb.s1)
        assert history[0][0].paper_code == "9MA0/01"

    def test_unsigned_registers_are_chased(self, attdb, sitting):
        assert sitting.sitting_id in [s.sitting_id
                                      for s in exams.unsigned_registers()]

    def test_syncing_codes_the_lesson_register(self, attdb, sitting):
        exams.mark_all_present(sitting.sitting_id)
        written = exams.sync_to_register(sitting.sitting_id)
        assert written >= 1
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == "B"

    def test_syncing_leaves_absentees_for_a_person(self, attdb, sitting):
        # An exam absence is a conversation, not a data entry.
        exams.mark_candidate(sitting.sitting_id, attdb.s1, exams.ABSENT)
        exams.mark_candidate(sitting.sitting_id, attdb.s2, exams.PRESENT)
        exams.mark_candidate(sitting.sitting_id, attdb.s3, exams.PRESENT)
        exams.sync_to_register(sitting.sitting_id)
        assert core.get_record_for(attdb.slot, attdb.s1, attdb.monday) is None
