"""Tests for attendance mark appeals.

The upheld rate is the number that matters: a teaching group with a
quarter of its marks successfully appealed has a marking problem, not
a discipline one.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_appeals as appeals,
)


@pytest.fixture
def disputed(attdb):
    """One unexplained absence a learner says is wrong."""
    core.save_register(attdb.slot, attdb.prev_monday,
                       {attdb.s1: {"code": "O"}})
    record = core.get_record_for(attdb.slot, attdb.s1, attdb.prev_monday)
    assert record is not None
    return record


# ── 1. Lodging ─────────────────────────────────────────────────────

class TestLodging:

    def test_an_appeal_can_be_lodged(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id,
                               grounds=appeals.WAS_PRESENT,
                               statement="I was in the room")
        assert appeal.state == appeals.SUBMITTED
        assert appeal.disputed_code == "O"

    def test_it_defaults_to_the_learner_as_submitter(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        assert appeal.submitted_by == attdb.s1

    def test_an_unknown_record_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No attendance "
                                                       "record"):
            appeals.lodge(9999)

    def test_unknown_grounds_are_rejected(self, attdb, disputed):
        with pytest.raises(core.ValidationError, match="Grounds must be"):
            appeals.lodge(disputed.record_id, grounds="Vibes")

    def test_a_mark_older_than_the_window_cannot_be_appealed(self, attdb):
        # A mark disputed months later cannot be checked against
        # anybody's memory.
        core.save_register(attdb.slot, attdb.ancient,
                           {attdb.s1: {"code": "O"}}, allow_retro=True)
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.ancient)
        with pytest.raises(core.ValidationError, match="appeals close"):
            appeals.lodge(record.record_id)

    def test_a_second_open_appeal_is_refused(self, attdb, disputed):
        appeals.lodge(disputed.record_id)
        with pytest.raises(core.ValidationError, match="already"):
            appeals.lodge(disputed.record_id)

    def test_a_voided_mark_cannot_be_appealed(self, attdb, disputed):
        from education_system.systems.sixth_form.domain.academics.attendance \
            import attendance_audit as audit
        audit.void_record(disputed.record_id, reason="Wrong learner")
        with pytest.raises(core.ValidationError, match="nothing to appeal"):
            appeals.lodge(disputed.record_id)

    def test_an_appeal_can_be_reassigned(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        out = appeals.assign(appeal.appeal_id, to="Mrs Rees")
        assert out.assigned_to == "Mrs Rees"
        assert out.state == appeals.UNDER_REVIEW

    def test_assigning_to_nobody_is_rejected(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        with pytest.raises(core.ValidationError, match="assigned to "
                                                       "somebody"):
            appeals.assign(appeal.appeal_id, to="  ")


# ── 2. Deciding ────────────────────────────────────────────────────

class TestDeciding:

    def test_upholding_recodes_the_mark(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id,
                               grounds=appeals.WAS_PRESENT)
        out = appeals.uphold(appeal.appeal_id, decided_by="Mr Patel")
        assert out.state == appeals.UPHELD
        assert core.get_record(disputed.record_id).code == "/"

    def test_the_outcome_code_follows_the_grounds(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id,
                               grounds=appeals.WAS_LATE_NOT_ABSENT)
        out = appeals.uphold(appeal.appeal_id, decided_by="Mr Patel")
        assert out.outcome_code == "L"

    def test_the_code_can_be_overridden(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        out = appeals.uphold(appeal.appeal_id, decided_by="Mr Patel",
                             code="I")
        assert out.outcome_code == "I"

    def test_upholding_writes_to_the_amendment_trail(self, attdb, disputed):
        from education_system.systems.sixth_form.domain.academics.attendance \
            import attendance_audit as audit
        appeal = appeals.lodge(disputed.record_id)
        appeals.uphold(appeal.appeal_id, decided_by="Mr Patel")
        trail = audit.list_amendments(student_id=attdb.s1)
        assert any("Appeal upheld" in (e.reason or "") for e in trail)

    def test_upholding_needs_a_named_decider(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        with pytest.raises(core.ValidationError, match="decided by "
                                                       "somebody named"):
            appeals.uphold(appeal.appeal_id, decided_by="  ")

    def test_rejecting_leaves_the_mark_alone(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        appeals.reject(appeal.appeal_id, decided_by="Mr Patel",
                       reason="Register and seating plan agree")
        assert core.get_record(disputed.record_id).code == "O"

    def test_rejecting_needs_a_reason(self, attdb, disputed):
        # An appeal turned down without one looks like one nobody read.
        appeal = appeals.lodge(disputed.record_id)
        with pytest.raises(core.ValidationError, match="reason is required"):
            appeals.reject(appeal.appeal_id, decided_by="Mr Patel",
                           reason="  ")

    def test_a_decided_appeal_cannot_be_decided_again(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        appeals.uphold(appeal.appeal_id, decided_by="Mr Patel")
        with pytest.raises(core.ValidationError, match="already"):
            appeals.reject(appeal.appeal_id, decided_by="Mr Patel",
                           reason="Changed my mind")

    def test_an_appeal_can_be_withdrawn(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        out = appeals.withdraw(appeal.appeal_id, reason="Fair enough")
        assert out.state == appeals.WITHDRAWN


# ── 3. Queue and statistics ────────────────────────────────────────

class TestReporting:

    def test_the_queue_holds_open_appeals(self, attdb, disputed):
        appeals.lodge(disputed.record_id)
        queue = appeals.queue()
        assert len(queue) == 1
        assert queue[0].student_name == "Ada Test"

    def test_a_decided_appeal_leaves_the_queue(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        appeals.uphold(appeal.appeal_id, decided_by="Mr Patel")
        assert appeals.queue() == []

    def test_statistics_count_outcomes(self, attdb, disputed):
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s2: {"code": "O"}})
        second = core.get_record_for(attdb.pm_slot, attdb.s2,
                                     attdb.prev_monday)
        first = appeals.lodge(disputed.record_id)
        other = appeals.lodge(second.record_id)
        appeals.uphold(first.appeal_id, decided_by="Mr Patel")
        appeals.reject(other.appeal_id, decided_by="Mr Patel",
                       reason="Register stands")
        stats = appeals.stats()
        assert (stats.total, stats.upheld, stats.rejected) == (2, 1, 1)
        assert stats.upheld_rate == 50.0

    def test_an_undecided_appeal_does_not_move_the_rate(self, attdb,
                                                        disputed):
        appeals.lodge(disputed.record_id)
        assert appeals.stats().upheld_rate is None

    def test_slots_attracting_appeals_are_listed(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        appeals.uphold(appeal.appeal_id, decided_by="Mr Patel")
        rows = appeals.by_slot(min_appeals=1)
        assert rows[0][0] == attdb.slot
        assert rows[0][1].upheld_rate == 100.0

    def test_an_appeal_is_findable_from_its_record(self, attdb, disputed):
        appeal = appeals.lodge(disputed.record_id)
        assert appeals.for_record(disputed.record_id).appeal_id == \
            appeal.appeal_id
