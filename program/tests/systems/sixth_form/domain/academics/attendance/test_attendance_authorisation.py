"""Tests for absence authorisation and off-site placement.

Covers who signed an absence off and on what grounds, the decision
queue, bulk and range authorisation, withdrawal, and the off-site
placement register.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_audit as audit,
    attendance_authorisation as authz,
    attendance_codes as codes,
    attendance_register as reg,
)


# ── 1. Authorising ─────────────────────────────────────────────────

class TestAuthorise:

    def test_authorising_stamps_who_and_when(self, attdb, one_absence):
        out = authz.authorise(one_absence.record_id, authorised_by="jsmith")
        assert out.authorised_by == "jsmith"
        assert out.authorised_at is not None
        assert out.is_authorised is True

    def test_default_code_is_other_authorised_circumstances(
            self, attdb, one_absence):
        out = authz.authorise(one_absence.record_id, authorised_by="jsmith")
        assert out.code == "C"
        assert out.status == "Authorised"

    def test_the_reason_chooses_the_code(self, attdb, one_absence):
        illness = codes.reason_by_name("Illness")
        out = authz.authorise(one_absence.record_id, authorised_by="jsmith",
                              reason_id=illness.reason_id)
        assert out.code == "I"
        assert out.reason_id == illness.reason_id

    def test_a_reason_may_land_outside_the_authorised_bucket(
            self, attdb, one_absence):
        # Work experience is approved activity, not absence at all — the
        # reason's own code has to win over the authorised default.
        placement = codes.reason_by_name("Work experience")
        out = authz.authorise(one_absence.record_id, authorised_by="jsmith",
                              reason_id=placement.reason_id)
        assert out.code == "W"
        assert codes.counts_as_present(out.code)

    def test_an_explicit_code_overrides_the_reason(self, attdb, one_absence):
        illness = codes.reason_by_name("Illness")
        out = authz.authorise(one_absence.record_id, authorised_by="jsmith",
                              reason_id=illness.reason_id, code="M")
        assert out.code == "M"

    def test_grounds_are_recorded(self, attdb, one_absence):
        out = authz.authorise(one_absence.record_id, authorised_by="jsmith",
                              note="Hospital letter seen")
        assert out.authorisation_note == "Hospital letter seen"

    def test_an_unauthorised_code_cannot_be_authorised_into(
            self, attdb, one_absence):
        with pytest.raises(core.ValidationError,
                           match="not an authorised-absence code"):
            authz.authorise(one_absence.record_id, authorised_by="jsmith",
                            code="O")

    def test_an_authoriser_is_required(self, attdb, one_absence):
        with pytest.raises(core.ValidationError, match="needs an authoriser"):
            authz.authorise(one_absence.record_id, authorised_by="  ")

    def test_a_submitted_register_blocks_authorisation(
            self, attdb, one_absence):
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        with pytest.raises(core.ValidationError, match="submitted"):
            authz.authorise(one_absence.record_id, authorised_by="jsmith")

    def test_reopening_is_the_way_past_the_lock(self, attdb, one_absence):
        reg.submit_register(attdb.slot, attdb.monday, submitted_by="teacher")
        reg.reopen_register(attdb.slot, attdb.monday, reopened_by="head",
                            reason="Evidence arrived")
        out = authz.authorise(one_absence.record_id, authorised_by="jsmith")
        assert out.is_authorised

    def test_a_voided_record_cannot_be_authorised(self, attdb, one_absence):
        audit.void_record(one_absence.record_id, reason="Wrong learner")
        with pytest.raises(core.ValidationError, match="voided"):
            authz.authorise(one_absence.record_id, authorised_by="jsmith")

    def test_reauthorising_restamps(self, attdb, one_absence):
        authz.authorise(one_absence.record_id, authorised_by="jsmith")
        out = authz.authorise(one_absence.record_id, authorised_by="ahmed",
                              note="Reviewed")
        assert out.authorised_by == "ahmed"

    def test_authorising_writes_to_the_trail(self, attdb, one_absence):
        authz.authorise(one_absence.record_id, authorised_by="jsmith",
                        note="Hospital letter")
        trail = audit.list_amendments(record_id=one_absence.record_id,
                                      action="authorise")
        assert len(trail) == 1
        assert trail[0].new_value == "jsmith"


# ── 2. Withdrawing ─────────────────────────────────────────────────

class TestUnauthorise:

    def test_withdrawing_clears_the_stamp(self, attdb, one_absence):
        authz.authorise(one_absence.record_id, authorised_by="jsmith")
        out = authz.unauthorise(one_absence.record_id, actor="head",
                                reason="Evidence not produced")
        assert out.authorised_by is None
        assert out.authorised_at is None
        assert out.is_authorised is False

    def test_withdrawing_defaults_to_unauthorised(self, attdb, one_absence):
        authz.authorise(one_absence.record_id, authorised_by="jsmith")
        out = authz.unauthorise(one_absence.record_id, actor="head")
        assert out.code == "O"
        assert out.status == "Absent"

    def test_it_can_go_back_to_undecided_instead(self, attdb, one_absence):
        authz.authorise(one_absence.record_id, authorised_by="jsmith")
        out = authz.unauthorise(one_absence.record_id, actor="head", code="N")
        assert out.code == "N"

    def test_withdrawing_an_unauthorised_row_is_rejected(
            self, attdb, one_absence):
        with pytest.raises(core.ValidationError, match="not authorised"):
            authz.unauthorise(one_absence.record_id, actor="head")


# ── 3. The decision queue ──────────────────────────────────────────

class TestPendingQueue:

    def test_an_unexplained_absence_is_queued(self, attdb, one_absence):
        rows = authz.pending()
        assert [p.record_id for p in rows] == [one_absence.record_id]

    def test_an_authorised_absence_leaves_the_queue(self, attdb, one_absence):
        authz.authorise(one_absence.record_id, authorised_by="jsmith")
        assert authz.pending() == []

    def test_a_decided_no_also_leaves_the_queue(self, attdb, one_absence):
        # O means somebody decided; the decision was just "no".
        codes.set_code(one_absence.record_id, "O")
        assert authz.pending() == []

    def test_a_present_mark_is_never_queued(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        assert authz.pending() == []

    def test_the_queue_carries_names_and_waiting_time(
            self, attdb, one_absence):
        row = authz.pending()[0]
        assert row.student_name == "Ada Test"
        assert row.days_waiting >= 0
        assert one_absence.date in row.label

    def test_stale_filter_uses_the_threshold(self, attdb):
        old_date = "2020-01-06"          # a Monday, long past
        core.save_register(attdb.slot, old_date,
                           {attdb.s1: {"status": "Absent"}},
                           allow_retro=True)
        stale = authz.pending(stale_only=True)
        assert [p.record.date for p in stale] == [old_date]
        assert stale[0].stale is True

    def test_the_queue_can_be_scoped_to_a_group(self, attdb, one_absence):
        assert authz.pending_count(group_id=attdb.group) == 1
        assert authz.pending_count(group_id=2) == 0

    def test_the_queue_is_ordered_oldest_first(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Absent"}})
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Absent"}})
        dates = [p.record.date for p in authz.pending()]
        assert dates == sorted(dates)


# ── 4. Bulk and range ──────────────────────────────────────────────

class TestBulkAuthorise:

    def test_bulk_authorises_each_row(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Absent"},
            attdb.s2: {"status": "Absent"}})
        ids = [r.record_id for r in
               core.list_records(slot_id=attdb.slot, date=attdb.monday)]
        result = authz.bulk_authorise(ids, authorised_by="jsmith")
        assert result.authorised == 2
        assert result.skipped == 0

    def test_bulk_reports_failures_without_aborting(self, attdb, one_absence):
        result = authz.bulk_authorise(
            [one_absence.record_id, 9999], authorised_by="jsmith")
        assert result.authorised == 1
        assert result.skipped == 1
        assert "9999" in result.failures[0]
        assert "1 authorised" in result.message

    def test_range_covers_every_absence_in_the_window(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Absent"}})
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Absent"}})
        illness = codes.reason_by_name("Illness")
        result = authz.authorise_range(
            attdb.s1, date_from=attdb.prev_monday, date_to=attdb.monday,
            authorised_by="jsmith", reason_id=illness.reason_id)
        assert result.authorised == 2
        assert all(r.code == "I" for r in
                   core.list_records(student_id=attdb.s1))

    def test_range_leaves_present_marks_alone(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present"},
            attdb.s2: {"status": "Absent"}})
        result = authz.authorise_range(
            attdb.s1, date_from=attdb.monday, date_to=attdb.monday,
            authorised_by="jsmith")
        assert result.authorised == 0


# ── 5. Who is authorising ──────────────────────────────────────────

class TestAuthorisationOversight:

    def test_counts_by_staff_member(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Absent"},
            attdb.s2: {"status": "Absent"},
            attdb.s3: {"status": "Absent"}})
        records = core.list_records(slot_id=attdb.slot, date=attdb.monday)
        authz.authorise(records[0].record_id, authorised_by="jsmith")
        authz.authorise(records[1].record_id, authorised_by="jsmith")
        authz.authorise(records[2].record_id, authorised_by="ahmed")
        assert authz.authorised_by_staff() == {"jsmith": 2, "ahmed": 1}

    def test_unauthorised_rows_are_not_counted(self, attdb, one_absence):
        assert authz.authorised_by_staff() == {}


# ── 6. Off-site placement ──────────────────────────────────────────

class TestOffsite:

    def test_marking_off_site_records_the_location(self, attdb, one_absence):
        out = authz.set_offsite(one_absence.record_id,
                                location="Acme Ltd", actor="jsmith")
        assert out.is_offsite is True
        assert out.offsite_location == "Acme Ltd"

    def test_the_default_code_is_offsite_educational_activity(
            self, attdb, one_absence):
        out = authz.set_offsite(one_absence.record_id, location="Acme Ltd")
        assert out.code == "B"

    def test_a_known_placement_kind_picks_its_own_code(
            self, attdb, one_absence):
        out = authz.set_offsite(one_absence.record_id,
                                location="Work placement")
        assert out.code == "W"

    def test_an_offsite_learner_counts_as_attending(self, attdb, one_absence):
        out = authz.set_offsite(one_absence.record_id,
                                location="Work placement")
        assert codes.counts_as_present(out.code)
        assert out.status == "Present"

    def test_a_location_is_required(self, attdb, one_absence):
        with pytest.raises(core.ValidationError, match="needs a location"):
            authz.set_offsite(one_absence.record_id, location="   ")

    def test_an_overlong_location_is_rejected(self, attdb, one_absence):
        with pytest.raises(core.ValidationError, match="120 characters"):
            authz.set_offsite(one_absence.record_id, location="x" * 121)

    def test_clearing_puts_the_learner_back_in_the_room(
            self, attdb, one_absence):
        authz.set_offsite(one_absence.record_id, location="Acme Ltd")
        out = authz.clear_offsite(one_absence.record_id, actor="jsmith")
        assert out.is_offsite is False
        assert out.offsite_location is None
        assert out.code == "/"

    def test_clearing_a_non_placement_is_rejected(self, attdb, one_absence):
        with pytest.raises(core.ValidationError, match="not marked off site"):
            authz.clear_offsite(one_absence.record_id)

    def test_the_register_lists_placements(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Absent"},
            attdb.s2: {"status": "Absent"}})
        records = core.list_records(slot_id=attdb.slot, date=attdb.monday)
        authz.set_offsite(records[0].record_id, location="Acme Ltd")
        rows = authz.list_offsite()
        assert len(rows) == 1
        assert rows[0].location == "Acme Ltd"
        assert rows[0].student_name.endswith("Test")

    def test_breakdown_groups_by_location(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"code": "W", "offsite_location": "Acme Ltd"},
            attdb.s2: {"code": "W", "offsite_location": "Acme Ltd"},
            attdb.s3: {"code": "V", "offsite_location": "Tate Modern"}})
        assert authz.offsite_breakdown() == {"Acme Ltd": 2, "Tate Modern": 1}

    def test_placements_are_written_to_the_trail(self, attdb, one_absence):
        authz.set_offsite(one_absence.record_id, location="Acme Ltd")
        trail = audit.list_amendments(record_id=one_absence.record_id,
                                      action="offsite")
        assert trail[0].new_value == "Acme Ltd"

    def test_suggested_codes_cover_every_known_kind(self):
        for kind in authz.OFFSITE_KINDS:
            assert codes.get_code(authz.suggest_offsite_code(kind)) is not None
