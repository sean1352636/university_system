"""Tests for statutory mark codes, absence reasons and data sources.

Covers the code vocabulary and how it counts, the status/code
reconciliation that lets callers give either one, the editable absence
reason list, the data-source stamp, and the backfill and reporting
helpers.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
)


# ── 1. The vocabulary ──────────────────────────────────────────────

class TestVocabulary:

    def test_every_code_is_unique_and_indexed(self):
        assert len(codes.CODE_INDEX) == len(codes.MARK_CODES)
        assert set(codes.CODES) == set(codes.CODE_INDEX)

    def test_every_code_has_a_known_meaning_and_status(self):
        for mark in codes.MARK_CODES:
            assert mark.meaning in codes.MEANINGS
            assert mark.status in core.STATUSES

    def test_present_and_approved_count_as_attending(self):
        assert codes.counts_as_present("/")
        assert codes.counts_as_present("L")
        assert codes.counts_as_present("W")     # work experience
        assert not codes.counts_as_present("I")
        assert not codes.counts_as_present("O")

    def test_not_counted_codes_leave_the_denominator(self):
        assert not codes.counts_toward_possible("X")
        assert not codes.counts_toward_possible("Y")
        assert codes.counts_toward_possible("O")

    def test_a_missing_code_still_counts_toward_possible(self):
        # A session nobody coded is still a session that should have
        # happened — dropping it would flatter the percentage.
        assert codes.counts_toward_possible(None)
        assert codes.counts_toward_possible("")

    def test_authorised_and_unauthorised_are_told_apart(self):
        assert codes.is_authorised_absence("I")
        assert not codes.is_unauthorised_absence("I")
        assert codes.is_unauthorised_absence("O")
        assert codes.is_absence("I") and codes.is_absence("O")
        assert not codes.is_absence("/")

    def test_late_after_register_closed_is_unauthorised_but_reads_as_late(self):
        # `U` is the awkward one: pastorally a lateness, statutorily an
        # unauthorised absence. Both facts have to survive.
        mark = codes.CODE_INDEX["U"]
        assert mark.status == "Late"
        assert mark.meaning == codes.UNAUTHORISED
        assert not codes.counts_as_present("U")

    def test_offsite_codes_are_flagged(self):
        for code in ("B", "D", "V", "W"):
            assert codes.implies_offsite(code)
        assert not codes.implies_offsite("I")
        assert not codes.implies_offsite(None)

    def test_unknown_code_is_rejected(self):
        with pytest.raises(core.ValidationError, match="Unknown mark code"):
            codes.validate_code("Q")

    def test_blank_code_is_rejected(self):
        with pytest.raises(core.ValidationError, match="required"):
            codes.validate_code("")

    def test_codes_for_meaning_partitions_the_vocabulary(self):
        total = sum(len(codes.codes_for_meaning(m)) for m in codes.MEANINGS)
        assert total == len(codes.MARK_CODES)

    def test_describe_mentions_how_it_counts(self):
        assert "Authorised" in codes.describe("I")

    def test_uncoded_absence_defaults_to_no_reason_given(self):
        # Never O — the system must not decide an absence was
        # unauthorised just because nobody coded it.
        assert codes.default_code_for_status("Absent") == "N"
        assert codes.status_for_code("N") == "Absent"


# ── 2. Status / code reconciliation ────────────────────────────────

class TestResolveMarks:

    def test_status_only_gets_a_default_code(self, attdb):
        status, code, _ = core.resolve_marks({"status": "Present"})
        assert (status, code) == ("Present", "/")

    def test_code_only_derives_the_status(self, attdb):
        status, code, _ = core.resolve_marks({"code": "V"})
        assert (status, code) == ("Present", "V")

    def test_both_given_are_taken_as_given(self, attdb):
        # Deliberately allowed to disagree: a college may run a grace
        # period where L is recorded against Present.
        status, code, _ = core.resolve_marks(
            {"status": "Present", "code": "L"})
        assert (status, code) == ("Present", "L")

    def test_session_is_derived_from_the_slot(self, attdb):
        _, _, morning = core.resolve_marks({"status": "Present"},
                                           slot_id=attdb.slot)
        _, _, afternoon = core.resolve_marks({"status": "Present"},
                                             slot_id=attdb.pm_slot)
        assert (morning, afternoon) == ("AM", "PM")

    def test_neither_given_falls_back(self, attdb):
        status, code, _ = core.resolve_marks(
            {}, fallback_status="Late", fallback_code="L")
        assert (status, code) == ("Late", "L")


# ── 3. Codes on saved rows ─────────────────────────────────────────

class TestCodesOnRecords:

    def test_saving_a_status_fills_in_the_code(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Absent"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == "N"
        assert record.status == "Absent"

    def test_saving_a_code_fills_in_the_status(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "I"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.status == "Authorised"
        assert record.code == "I"

    def test_an_offsite_code_sets_the_offsite_flag_by_itself(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "W"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.is_offsite is True

    def test_a_location_alone_implies_offsite(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present", "offsite_location": "Acme Ltd"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.is_offsite is True
        assert record.offsite_location == "Acme Ltd"

    def test_clearing_offsite_drops_the_stale_location(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"code": "W", "offsite_location": "Acme Ltd"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        core.update_record(record.record_id,
                           {"code": "/", "is_offsite": False})
        after = core.get_record(record.record_id)
        assert after.is_offsite is False
        assert after.offsite_location is None

    def test_session_is_stamped_on_save(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        core.save_register(attdb.pm_slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        morning = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        afternoon = core.get_record_for(attdb.pm_slot, attdb.s1, attdb.monday)
        assert (morning.session, afternoon.session) == ("AM", "PM")

    def test_a_bad_code_rejects_the_whole_save(self, attdb):
        with pytest.raises(core.ValidationError):
            core.save_register(attdb.slot, attdb.monday, {
                attdb.s1: {"status": "Present"},
                attdb.s2: {"code": "Q"}})
        # Nothing was written — validation runs before any DB write.
        assert core.list_records(slot_id=attdb.slot, date=attdb.monday) == []

    def test_records_can_be_filtered_by_code(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"code": "I"},
            attdb.s2: {"code": "O"},
            attdb.s3: {"code": "I"}})
        assert len(core.list_records(code="I")) == 2
        assert len(core.list_records(code="O")) == 1


# ── 4. Data sources ────────────────────────────────────────────────

class TestDataSources:

    def test_default_source_is_manual(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.data_source == "manual"

    def test_source_is_stored_and_filterable(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present", "data_source": "kiosk"},
            attdb.s2: {"status": "Present"}})
        kiosk = core.list_records(data_source="kiosk")
        assert [r.student_id for r in kiosk] == [attdb.s1]

    def test_unknown_source_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Data source"):
            core.save_register(attdb.slot, attdb.monday, {
                attdb.s1: {"status": "Present", "data_source": "carrier-pigeon"}})

    def test_source_is_case_insensitive(self):
        assert codes.validate_source("KIOSK") == "kiosk"

    def test_source_breakdown_counts_each(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present", "data_source": "kiosk"},
            attdb.s2: {"status": "Present", "data_source": "kiosk"},
            attdb.s3: {"status": "Present"}})
        assert codes.source_breakdown() == {"kiosk": 2, "manual": 1}

    def test_a_partial_update_does_not_reset_the_source(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present", "data_source": "kiosk"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        core.update_record(record.record_id, {"notes": "checked"})
        assert core.get_record(record.record_id).data_source == "kiosk"


# ── 5. Absence reasons ─────────────────────────────────────────────

class TestAbsenceReasons:

    def test_the_shipped_list_is_seeded(self, attdb):
        names = {r.name for r in codes.list_reasons()}
        assert "Illness" in names
        assert "Medical appointment" in names

    def test_seeding_twice_adds_nothing(self, attdb):
        before = len(codes.list_reasons())
        assert codes.seed_reasons() == 0
        assert len(codes.list_reasons()) == before

    def test_seeded_reasons_suggest_a_code(self, attdb):
        illness = codes.reason_by_name("Illness")
        assert codes.suggest_code(illness.reason_id) == "I"

    def test_a_reason_can_be_added(self, attdb):
        reason = codes.create_reason({
            "name": "Driving test", "category": "Personal",
            "default_code": "C", "requires_evidence": True})
        assert reason.requires_evidence is True
        assert reason.label.endswith("(evidence required)")

    def test_duplicate_names_are_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="already exists"):
            codes.create_reason({"name": "Illness", "category": "Medical"})

    def test_a_bad_category_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Category"):
            codes.create_reason({"name": "Nonsense", "category": "Vibes"})

    def test_a_bad_default_code_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Unknown mark code"):
            codes.create_reason({"name": "Nonsense", "default_code": "Q"})

    def test_archiving_hides_without_deleting(self, attdb):
        reason = codes.reason_by_name("Truancy")
        codes.archive_reason(reason.reason_id)
        assert reason.name not in {r.name for r in codes.list_reasons()}
        assert reason.name in {
            r.name for r in codes.list_reasons(active_only=False)}
        assert codes.get_reason(reason.reason_id) is not None

    def test_an_archived_reason_cannot_be_used_on_a_new_mark(self, attdb):
        reason = codes.reason_by_name("Truancy")
        codes.archive_reason(reason.reason_id)
        with pytest.raises(core.ValidationError, match="archived"):
            core.save_register(attdb.slot, attdb.monday, {
                attdb.s1: {"code": "O", "reason_id": reason.reason_id}})

    def test_archiving_leaves_existing_rows_pointing_at_it(self, attdb):
        reason = codes.reason_by_name("Illness")
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"code": "I", "reason_id": reason.reason_id}})
        codes.archive_reason(reason.reason_id)
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.reason_id == reason.reason_id

    def test_restore_brings_it_back(self, attdb):
        reason = codes.reason_by_name("Truancy")
        codes.archive_reason(reason.reason_id)
        codes.restore_reason(reason.reason_id)
        assert reason.name in {r.name for r in codes.list_reasons()}

    def test_usage_counts_live_rows_only(self, attdb):
        reason = codes.reason_by_name("Illness")
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"code": "I", "reason_id": reason.reason_id},
            attdb.s2: {"code": "I", "reason_id": reason.reason_id}})
        assert codes.reason_usage(reason.reason_id) == 2

    def test_an_unknown_reason_id_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No absence reason"):
            codes.validate_reason_id(9999)

    def test_reasons_can_be_filtered_by_category(self, attdb):
        medical = codes.list_reasons(category="Medical")
        assert medical
        assert all(r.category == "Medical" for r in medical)


# ── 6. Recoding and backfill ───────────────────────────────────────

class TestRecoding:

    def test_set_code_rederives_the_status(self, attdb, one_absence):
        out = codes.set_code(one_absence.record_id, "I", actor="jsmith")
        assert (out.code, out.status) == ("I", "Authorised")

    def test_set_code_can_attach_a_reason(self, attdb, one_absence):
        reason = codes.reason_by_name("Illness")
        out = codes.set_code(one_absence.record_id, "I",
                             reason_id=reason.reason_id)
        assert out.reason_id == reason.reason_id

    def test_backfill_codes_only_touches_uncoded_rows(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"status": "Present"},
            attdb.s2: {"code": "I"}})
        # Simulate a legacy row by clearing the code the save filled in.
        import sqlite3
        conn = sqlite3.connect(attdb.db)
        conn.execute("UPDATE attendance_records SET code = NULL "
                     "WHERE student_id = ?", (attdb.s1,))
        conn.commit()
        conn.close()

        assert codes.uncoded_count() == 1
        assert codes.backfill_codes() == 1
        assert codes.uncoded_count() == 0
        assert core.get_record_for(
            attdb.slot, attdb.s2, attdb.monday).code == "I"

    def test_backfill_is_safe_to_rerun(self, attdb):
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        assert codes.backfill_codes() == 0


# ── 7. Reporting ───────────────────────────────────────────────────

class TestReporting:

    @pytest.fixture
    def marked(self, attdb):
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"code": "/"},
            attdb.s2: {"code": "I"},
            attdb.s3: {"code": "O"}})
        return attdb

    def test_code_breakdown_counts_each_code(self, marked):
        rows = {r.code: r.count for r in codes.code_breakdown()}
        assert rows == {"/": 1, "I": 1, "O": 1}

    def test_code_breakdown_labels_uncoded_rows(self, attdb):
        import sqlite3
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        conn = sqlite3.connect(attdb.db)
        conn.execute("UPDATE attendance_records SET code = NULL")
        conn.commit()
        conn.close()
        row = codes.code_breakdown()[0]
        assert row.code == ""
        assert row.label == "(no code)"

    def test_meaning_breakdown_rolls_codes_up(self, marked):
        meanings = codes.meaning_breakdown()
        assert meanings[codes.PRESENT] == 1
        assert meanings[codes.AUTHORISED] == 1
        assert meanings[codes.UNAUTHORISED] == 1

    def test_breakdown_respects_the_date_window(self, marked):
        assert codes.code_breakdown(date_from=marked.tuesday) == []

    def test_breakdown_can_be_scoped_to_a_group(self, marked):
        assert sum(r.count for r in
                   codes.code_breakdown(group_id=marked.group)) == 3
        assert codes.code_breakdown(group_id=2) == []


# ── 8. Interaction with the register lifecycle ─────────────────────

class TestRegisterInteraction:

    def test_copy_forward_carries_the_code(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_register as reg,
        )
        illness = codes.reason_by_name("Illness")
        core.save_register(attdb.slot, attdb.prev_monday, {
            attdb.s1: {"code": "I", "reason_id": illness.reason_id}})
        reg.copy_previous_register(attdb.slot, attdb.monday)
        copied = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        # An ongoing illness must stay an illness, not decay to N.
        assert copied.code == "I"
        assert copied.reason_id == illness.reason_id

    def test_copy_forward_does_not_inherit_an_authorisation(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_authorisation as authz,
            attendance_register as reg,
        )
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Absent"}})
        prior = core.get_record_for(attdb.slot, attdb.s1, attdb.prev_monday)
        authz.authorise(prior.record_id, authorised_by="jsmith")
        reg.copy_previous_register(attdb.slot, attdb.monday)
        copied = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert copied.authorised_by is None

    def test_bulk_marking_present_clears_a_stale_absence_code(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_register as reg,
        )
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "I"}})
        reg.mark_all(attdb.slot, attdb.monday, "Present",
                     student_ids=[attdb.s1])
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == "/"

    def test_undo_restores_the_code_and_the_reason(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_register as reg,
        )
        illness = codes.reason_by_name("Illness")
        core.save_register(attdb.slot, attdb.monday, {
            attdb.s1: {"code": "I", "reason_id": illness.reason_id}})
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"code": "O"}})
        reg.undo_last_save(attdb.slot, attdb.monday)
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        assert record.code == "I"
        assert record.reason_id == illness.reason_id

    def test_undo_restores_a_void(self, attdb):
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance_audit as audit,
            attendance_register as reg,
        )
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Absent"}})
        record = core.get_record_for(attdb.slot, attdb.s1, attdb.monday)
        audit.void_record(record.record_id, reason="Wrong learner")
        # Re-marking un-voids; undoing that save must put the void back.
        core.save_register(attdb.slot, attdb.monday,
                           {attdb.s1: {"status": "Present"}})
        reg.undo_last_save(attdb.slot, attdb.monday)
        assert core.get_record(record.record_id).voided is True
