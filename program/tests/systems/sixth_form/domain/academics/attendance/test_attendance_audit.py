"""Tests for the attendance amendment trail and record voiding.

Covers what gets logged and what deliberately does not, the trail's
read side, soft-deleting a mark without losing it, restoring, and the
retention purge.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_audit as audit,
    attendance_codes as codes,
    attendance_register as reg,
)


# ── 1. What gets logged ────────────────────────────────────────────

class TestLogging:

    def test_a_new_row_is_not_an_amendment(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        assert audit.list_amendments() == []

    def test_a_targeted_edit_is_always_logged(self, attdb, one_absence):
        core.update_record(one_absence.record_id, {"notes": "Called home"},
                           actor="jsmith")
        trail = audit.list_amendments(record_id=one_absence.record_id)
        assert [e.field for e in trail] == ["notes"]
        assert trail[0].amended_by == "jsmith"

    def test_one_entry_per_changed_field(self, attdb, one_absence):
        core.update_record(one_absence.record_id,
                           {"code": "I", "notes": "Flu"}, actor="jsmith")
        fields = {e.field for e in
                  audit.list_amendments(record_id=one_absence.record_id)}
        assert fields == {"code", "status", "notes"}

    def test_an_unchanged_edit_logs_nothing(self, attdb, one_absence):
        core.update_record(one_absence.record_id,
                           {"status": one_absence.status}, actor="jsmith")
        assert audit.list_amendments(record_id=one_absence.record_id) == []

    def test_a_draft_register_save_is_not_logged(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Absent"}})
        # Before sign-off the undo buffer is the record, not the trail.
        assert audit.list_amendments() == []

    def test_a_post_submission_save_is_logged(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        reg.reopen_register(attdb.slot, attdb.monday, reopened_by="head",
                            reason="Marked the wrong learner")
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Absent"}}, actor="head")
        trail = audit.list_amendments(student_id=attdb.s1)
        assert {e.field for e in trail} == {"status", "code"}
        assert all(e.reason == "Amended after submission" for e in trail)

    def test_the_old_and_new_values_are_both_kept(self, attdb, one_absence):
        codes.set_code(one_absence.record_id, "I", actor="jsmith")
        entry = next(e for e in
                     audit.list_amendments(record_id=one_absence.record_id)
                     if e.field == "code")
        assert (entry.old_value, entry.new_value) == ("N", "I")

    def test_booleans_are_rendered_readably(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner",
                          actor="jsmith")
        entry = audit.list_amendments(action="void")[0]
        assert (entry.old_value, entry.new_value) == ("no", "yes")

    def test_recorded_at_is_not_tracked(self, attdb, one_absence):
        assert "recorded_at" not in audit.TRACKED_FIELDS

    def test_an_amendment_needs_a_subject(self, attdb):
        with pytest.raises(core.ValidationError, match="needs a slot"):
            audit.record_amendment(action="edit", student_id="T0001")

    def test_an_unknown_action_is_rejected(self, attdb, one_absence):
        with pytest.raises(core.ValidationError, match="Action must be"):
            audit.record_amendment(record=one_absence, action="fiddle")


# ── 2. Reading the trail ───────────────────────────────────────────

class TestReadingTheTrail:

    @pytest.fixture
    def amended(self, attdb, one_absence):
        codes.set_code(one_absence.record_id, "I", actor="jsmith")
        core.update_record(one_absence.record_id, {"notes": "Flu"},
                           actor="ahmed")
        return one_absence

    def test_list_is_newest_first(self, attdb, amended):
        trail = audit.list_amendments(record_id=amended.record_id)
        ids = [e.amendment_id for e in trail]
        assert ids == sorted(ids, reverse=True)

    def test_trail_for_a_record_is_oldest_first(self, attdb, amended):
        trail = audit.amendment_trail(amended.record_id)
        ids = [e.amendment_id for e in trail]
        assert ids == sorted(ids)

    def test_filter_by_actor(self, attdb, amended):
        assert all(e.amended_by == "ahmed"
                   for e in audit.list_amendments(actor="ahmed"))
        assert audit.list_amendments(actor="AHMED")

    def test_filter_by_group(self, attdb, amended):
        assert audit.list_amendments(group_id=attdb.group)
        assert audit.list_amendments(group_id=2) == []

    def test_dates_filter_on_the_lesson_not_the_edit(self, attdb, amended):
        assert audit.list_amendments(date_from=amended.date,
                                     date_to=amended.date)
        assert audit.list_amendments(date_from="2099-01-01") == []

    def test_limit_caps_the_result(self, attdb, amended):
        assert len(audit.list_amendments(limit=1)) == 1

    def test_summary_counts_by_action(self, attdb, amended):
        audit.void_record(amended.record_id, reason="Duplicate")
        counts = audit.amendment_summary()
        assert counts["void"] == 1
        assert counts["edit"] >= 1
        assert counts["purge"] == 0

    def test_most_amended_ranks_learners(self, attdb, amended):
        assert audit.most_amended(limit=5)[0][0] == attdb.s1

    def test_summary_is_readable(self, attdb, amended):
        entry = audit.list_amendments(record_id=amended.record_id)[0]
        assert "→" in entry.summary
        assert "ahmed" in entry.summary


# ── 3. Voiding ─────────────────────────────────────────────────────

class TestVoiding:

    def test_voiding_keeps_the_row(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner",
                          actor="jsmith")
        record = core.get_record(one_absence.record_id)
        assert record is not None
        assert record.voided is True
        assert record.void_reason == "Wrong learner"
        assert record.voided_by == "jsmith"

    def test_a_voided_row_drops_out_of_listings(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner")
        assert core.list_records(student_id=attdb.s1) == []
        assert len(core.list_records(student_id=attdb.s1,
                                     include_voided=True)) == 1

    def test_a_voided_row_drops_out_of_summaries(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present"},
            attdb.s2: {"status": "Absent"}})
        absent = core.get_record_for(attdb.slot, attdb.s2, attdb.monday)
        audit.void_record(absent.record_id, reason="Duplicate")
        summary = core.summary_for_group(attdb.group)
        assert summary.total == 1
        assert summary.absent == 0

    def test_a_voided_row_leaves_the_roster_unmarked(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner")
        entry = next(e for e in core.register_view(attdb.slot, attdb.monday)
                     if e.student_id == attdb.s1)
        assert entry.record is None

    def test_remarking_a_voided_student_revives_the_row(
            self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner")
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        record = core.get_record(one_absence.record_id)
        assert record.voided is False
        assert record.void_reason is None
        assert record.status == "Present"

    def test_a_reason_is_mandatory(self, attdb, one_absence):
        with pytest.raises(core.ValidationError, match="needs a reason"):
            audit.void_record(one_absence.record_id, reason="   ")

    def test_voiding_twice_is_rejected(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner")
        with pytest.raises(core.ValidationError, match="already voided"):
            audit.void_record(one_absence.record_id, reason="Again")

    def test_a_submitted_register_blocks_voiding(self, attdb, one_absence):
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        with pytest.raises(core.ValidationError, match="submitted"):
            audit.void_record(one_absence.record_id, reason="Wrong learner")

    def test_force_gets_past_a_submitted_register(self, attdb, one_absence):
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        result = audit.void_record(one_absence.record_id, reason="Duplicate",
                                   actor="head", force=True)
        assert result.action == "void"
        assert core.get_record(one_absence.record_id).voided is True

    def test_an_unknown_record_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No record"):
            audit.void_record(9999, reason="Nope")


# ── 4. Restoring ───────────────────────────────────────────────────

class TestRestoring:

    def test_restore_puts_it_back_in_the_counts(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner")
        audit.restore_record(one_absence.record_id, actor="head")
        record = core.get_record(one_absence.record_id)
        assert record.voided is False
        assert record.voided_by is None
        assert len(core.list_records(student_id=attdb.s1)) == 1

    def test_restoring_a_live_row_is_rejected(self, attdb, one_absence):
        with pytest.raises(core.ValidationError, match="not voided"):
            audit.restore_record(one_absence.record_id)

    def test_both_ends_are_in_the_trail(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner")
        audit.restore_record(one_absence.record_id)
        actions = [e.action for e in
                   audit.list_amendments(record_id=one_absence.record_id)]
        assert actions[:2] == ["restore", "void"]

    def test_listing_voided_rows(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner")
        rows = audit.list_voided()
        assert [r.record_id for r in rows] == [one_absence.record_id]
        assert audit.void_reason_for(one_absence.record_id) == "Wrong learner"


# ── 5. Retention purge ─────────────────────────────────────────────

class TestPurge:

    @pytest.fixture
    def old_void(self, attdb):
        # Six years back: past the retro-marking window, so the
        # backfill has to say so out loud.
        core.save_register(attdb.slot, "2020-01-06",
                           {attdb.s1: {"status": "Absent"}},
                           allow_retro=True)
        record = core.get_record_for(attdb.slot, attdb.s1, "2020-01-06")
        audit.void_record(record.record_id, reason="Ancient error")
        return record

    def test_dry_run_counts_without_deleting(self, attdb, old_void):
        result = audit.purge_voided(before_date="2021-01-01", dry_run=True)
        assert result.purged == 1
        assert core.get_record(old_void.record_id) is not None

    def test_purge_deletes_the_row(self, attdb, old_void):
        result = audit.purge_voided(before_date="2021-01-01", actor="head")
        assert result.purged == 1
        assert core.get_record(old_void.record_id) is None

    def test_the_trail_outlives_the_row(self, attdb, old_void):
        audit.purge_voided(before_date="2021-01-01", actor="head")
        entry = audit.list_amendments(action="purge")[0]
        assert entry.student_id == attdb.s1
        assert entry.record_id is None
        assert str(old_void.record_id) == entry.old_value

    def test_live_rows_are_never_purged(self, attdb):
        core.save_register(attdb.slot, "2020-01-06",
                           {attdb.s1: {"status": "Absent"}},
                           allow_retro=True)
        assert audit.purge_voided(before_date="2021-01-01").purged == 0
        assert core.list_records(student_id=attdb.s1)

    def test_the_cutoff_is_exclusive(self, attdb, old_void):
        assert audit.purge_voided(before_date="2020-01-06",
                                  dry_run=True).purged == 0
        assert audit.purge_voided(before_date="2020-01-07",
                                  dry_run=True).purged == 1

    def test_a_bad_cutoff_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError):
            audit.purge_voided(before_date="last Tuesday")
