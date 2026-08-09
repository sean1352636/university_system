"""Tests for offline register capture and sync.

The interesting behaviour is all in section 3: what happens when the
server moved on while a device was away. Everything else is plumbing
around that.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_offline as offline,
    attendance_register as reg,
)


OLD_CAPTURE = "2000-01-01 00:00:00"


# ── 1. Bundles ─────────────────────────────────────────────────────

class TestBundle:

    def test_a_bundle_carries_the_roster(self, attdb):
        bundle = offline.pack_bundle(attdb.slot, attdb.monday)
        assert [s["student_id"] for s in bundle.students] == attdb.students

    def test_a_bundle_carries_the_digest(self, attdb):
        bundle = offline.pack_bundle(attdb.slot, attdb.monday)
        assert bundle.digest == reg.register_digest(attdb.slot, attdb.monday)

    def test_the_digest_moves_when_the_register_does(self, attdb):
        before = offline.pack_bundle(attdb.slot, attdb.monday).digest
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Absent"}})
        after = offline.pack_bundle(attdb.slot, attdb.monday).digest
        assert before != after

    def test_existing_marks_travel_with_it(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Absent"}})
        bundle = offline.pack_bundle(attdb.slot, attdb.monday)
        first = next(s for s in bundle.students
                     if s["student_id"] == attdb.s1)
        assert first["status"] == "Absent"

    def test_a_locked_register_says_so(self, attdb):
        core.save_register(
            attdb.slot, attdb.monday,
            {sid: {"status": "Present"} for sid in attdb.students})
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        assert offline.pack_bundle(attdb.slot, attdb.monday).locked is True

    def test_a_day_packs_every_lesson(self, attdb):
        bundles = offline.pack_day(date=attdb.monday)
        assert {b.slot_id for b in bundles} == {attdb.slot, attdb.pm_slot}

    def test_a_bundle_serialises(self, attdb):
        assert "digest" in offline.pack_bundle(attdb.slot, attdb.monday).to_json()


# ── 2. Queueing ────────────────────────────────────────────────────

class TestQueue:

    def test_a_batch_is_stored_without_writing_marks(self, attdb):
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1")
        assert offline.pending_count() == 1
        assert core.list_records(slot_id=attdb.slot) == []

    def test_the_same_uuid_is_stored_once(self, attdb):
        first = offline.queue_batch(attdb.slot, attdb.monday,
                                    {attdb.s1: {"status": "Absent"}},
                                    client_uuid="u1")
        second = offline.queue_batch(attdb.slot, attdb.monday,
                                     {attdb.s1: {"status": "Present"}},
                                     client_uuid="u1")
        assert first.queue_id == second.queue_id
        assert offline.pending_count() == 1

    def test_a_uuid_is_required(self, attdb):
        with pytest.raises(core.ValidationError, match="client_uuid"):
            offline.queue_batch(attdb.slot, attdb.monday,
                                {attdb.s1: {"status": "Absent"}},
                                client_uuid="")

    def test_an_empty_batch_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="at least one mark"):
            offline.queue_batch(attdb.slot, attdb.monday, {},
                                client_uuid="u1")

    def test_a_mark_without_a_status_or_code_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="status or a code"):
            offline.queue_batch(attdb.slot, attdb.monday,
                                {attdb.s1: {"notes": "hm"}},
                                client_uuid="u1")

    def test_an_unknown_slot_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No slot"):
            offline.queue_batch(9999, attdb.monday,
                                {attdb.s1: {"status": "Absent"}},
                                client_uuid="u1")

    def test_backlog_is_reported_per_device(self, attdb):
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1", device_name="tablet-2")
        backlog = offline.device_backlog()
        assert backlog[0].device_name == "tablet-2"
        assert backlog[0].pending == 1


# ── 3. Conflicts ───────────────────────────────────────────────────

class TestConflicts:

    @pytest.fixture
    def contested(self, attdb):
        """A device that captured before the office changed the mark."""
        stale_digest = reg.register_digest(attdb.slot, attdb.monday)
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "I"},
                            attdb.s2: {"status": "Present"}})
        return offline.queue_batch(
            attdb.slot, attdb.monday,
            {attdb.s1: {"status": "Absent"}, attdb.s3: {"status": "Present"}},
            client_uuid="u1", device_name="phone",
            base_digest=stale_digest, captured_at=OLD_CAPTURE)

    def test_a_changed_learner_is_a_conflict(self, attdb, contested):
        found = offline.detect_conflicts(contested)
        assert [c.student_id for c in found] == [attdb.s1]

    def test_an_untouched_learner_is_not(self, attdb, contested):
        found = offline.detect_conflicts(contested)
        assert attdb.s3 not in [c.student_id for c in found]

    def test_a_matching_digest_means_no_conflict(self, attdb):
        digest = reg.register_digest(attdb.slot, attdb.monday)
        batch = offline.queue_batch(attdb.slot, attdb.monday,
                                    {attdb.s1: {"status": "Absent"}},
                                    client_uuid="u1", base_digest=digest,
                                    captured_at=OLD_CAPTURE)
        assert offline.detect_conflicts(batch) == []

    def test_no_digest_means_the_device_is_trusted(self, attdb):
        # With nothing to compare against, inventing conflicts would
        # block honest registers.
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "I"}})
        batch = offline.queue_batch(attdb.slot, attdb.monday,
                                    {attdb.s1: {"status": "Absent"}},
                                    client_uuid="u1",
                                    captured_at=OLD_CAPTURE)
        assert offline.detect_conflicts(batch) == []

    def test_server_wins_keeps_the_office_mark(self, attdb, contested):
        result = offline.apply_batch(contested.queue_id,
                                     policy=offline.SERVER_WINS)
        assert result.state == offline.APPLIED
        assert result.skipped == 1
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == "I"

    def test_server_wins_still_applies_the_rest(self, attdb, contested):
        offline.apply_batch(contested.queue_id, policy=offline.SERVER_WINS)
        assert core.get_record_for(attdb.slot, attdb.s3, attdb.monday) \
            is not None

    def test_device_wins_overwrites(self, attdb, contested):
        result = offline.apply_batch(contested.queue_id,
                                     policy=offline.DEVICE_WINS)
        assert result.state == offline.APPLIED
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.status == "Absent"

    def test_hold_applies_nothing(self, attdb, contested):
        result = offline.apply_batch(contested.queue_id,
                                     policy=offline.HOLD)
        assert result.state == offline.CONFLICT
        assert core.get_record_for(attdb.slot, attdb.s3, attdb.monday) is None

    def test_a_held_batch_appears_in_the_conflict_list(self, attdb,
                                                       contested):
        offline.apply_batch(contested.queue_id, policy=offline.HOLD)
        assert [b.queue_id for b in offline.conflicts()] == \
            [contested.queue_id]

    def test_a_held_batch_can_be_resolved(self, attdb, contested):
        offline.apply_batch(contested.queue_id, policy=offline.HOLD)
        result = offline.resolve(contested.queue_id,
                                 policy=offline.DEVICE_WINS)
        assert result.state == offline.APPLIED
        assert core.get_record_for(attdb.slot, attdb.s1,
                                   attdb.monday).status == "Absent"

    def test_holding_again_is_not_a_resolution(self, attdb, contested):
        offline.apply_batch(contested.queue_id, policy=offline.HOLD)
        with pytest.raises(core.ValidationError, match="not holding it again"):
            offline.resolve(contested.queue_id, policy=offline.HOLD)


# ── 4. Sync ────────────────────────────────────────────────────────

class TestSync:

    def test_a_clean_batch_applies(self, attdb):
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1")
        report = offline.sync()
        assert report.applied == 1
        assert report.written == 1

    def test_marks_are_stamped_as_sync(self, attdb):
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1")
        offline.sync()
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.data_source == offline.SYNC_SOURCE

    def test_a_locked_register_rejects_the_batch(self, attdb):
        core.save_register(
            attdb.slot, attdb.monday,
            {sid: {"status": "Present"} for sid in attdb.students})
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1")
        report = offline.sync()
        assert report.rejected == 1
        assert core.get_record_for(attdb.slot, attdb.s1,
                                   attdb.monday).status == "Present"

    def test_a_closed_date_rejects_the_batch(self, attdb):
        offline.queue_batch(attdb.slot, attdb.ancient,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1")
        assert offline.sync().rejected == 1

    def test_allow_retro_gets_an_old_batch_in(self, attdb):
        offline.queue_batch(attdb.slot, attdb.ancient,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1")
        assert offline.sync(allow_retro=True).applied == 1

    def test_syncing_twice_does_not_reapply(self, attdb):
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1")
        offline.sync()
        assert offline.sync().processed == 0

    def test_batches_apply_in_capture_order(self, attdb):
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Present"}},
                            client_uuid="late",
                            captured_at="2030-01-01 10:00:00")
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="early",
                            captured_at="2030-01-01 09:00:00")
        offline.sync()
        # The later capture is applied last, so it wins.
        assert core.get_record_for(attdb.slot, attdb.s1,
                                   attdb.monday).status == "Present"


# ── 5. Housekeeping ────────────────────────────────────────────────

class TestHousekeeping:

    def test_a_batch_can_be_discarded(self, attdb):
        batch = offline.queue_batch(attdb.slot, attdb.monday,
                                    {attdb.s1: {"status": "Absent"}},
                                    client_uuid="u1")
        out = offline.discard(batch.queue_id, reason="Duplicate upload")
        assert out.state == offline.DISCARDED
        assert offline.sync().processed == 0

    def test_discarding_needs_a_reason(self, attdb):
        batch = offline.queue_batch(attdb.slot, attdb.monday,
                                    {attdb.s1: {"status": "Absent"}},
                                    client_uuid="u1")
        with pytest.raises(core.ValidationError, match="reason is required"):
            offline.discard(batch.queue_id, reason="  ")

    def test_an_applied_batch_cannot_be_discarded(self, attdb):
        batch = offline.queue_batch(attdb.slot, attdb.monday,
                                    {attdb.s1: {"status": "Absent"}},
                                    client_uuid="u1")
        offline.sync()
        with pytest.raises(core.ValidationError, match="already been applied"):
            offline.discard(batch.queue_id, reason="Changed my mind")

    def test_resolved_batches_can_be_purged(self, attdb):
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1",
                            captured_at="2020-01-01 09:00:00")
        offline.sync(allow_retro=True)
        assert offline.purge_resolved(before_date="2021-01-01",
                                      dry_run=True) == 1
        assert offline.purge_resolved(before_date="2021-01-01") == 1

    def test_stale_batches_are_listed(self, attdb):
        offline.queue_batch(attdb.slot, attdb.monday,
                            {attdb.s1: {"status": "Absent"}},
                            client_uuid="u1",
                            captured_at="2020-01-01 09:00:00")
        assert len(offline.stale_batches()) == 1

    def test_an_unknown_policy_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Policy must be"):
            offline.validate_policy("whatever-the-teacher-says")
