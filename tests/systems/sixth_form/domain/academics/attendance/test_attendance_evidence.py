"""Tests for absence evidence and its deadlines.

The half that changes behaviour is section 3: a college that asks for
evidence and never checks has an authorisation policy in name only.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
    attendance_evidence as evidence,
    attendance_thresholds as thresholds,
)


@pytest.fixture
def absence(attdb):
    """One authorised absence, coded and ready to need evidence."""
    core.save_register(attdb.slot, attdb.prev_monday,
                       {attdb.s1: {"code": "I"}})
    record = core.get_record_for(attdb.slot, attdb.s1, attdb.prev_monday)
    assert record is not None
    return record


# ── 1. Recording evidence ──────────────────────────────────────────

class TestEvidence:

    def test_sighted_evidence_can_be_logged_without_a_file(self, attdb):
        # Most of it is a card handed over the counter and given back.
        item = evidence.record_evidence(attdb.s1,
                                        kind=evidence.APPOINTMENT_CARD,
                                        custody=evidence.SIGHTED,
                                        received_by="reception")
        assert item.custody == evidence.SIGHTED
        assert item.has_file is False

    def test_storing_a_document_marks_it_held(self, attdb, tmp_path,
                                              monkeypatch):
        monkeypatch.setattr(evidence, "EVIDENCE_DIR", tmp_path / "evidence")
        item = evidence.record_evidence(attdb.s1, kind=evidence.FIT_NOTE,
                                        file_name="note.pdf",
                                        file_bytes=b"%PDF-1.4 fake")
        assert item.custody == evidence.HELD
        assert item.has_file is True

    def test_a_stored_document_needs_a_name(self, attdb):
        with pytest.raises(core.ValidationError, match="needs a file name"):
            evidence.record_evidence(attdb.s1, file_bytes=b"data")

    def test_attaching_to_a_record_infers_the_dates(self, attdb, absence):
        item = evidence.record_evidence(attdb.s1,
                                        record_id=absence.record_id)
        assert item.covers_from == absence.date
        assert item.covers_to == absence.date

    def test_evidence_covering_a_span_is_matched_across_it(self, attdb):
        monday = _dt.date.fromisoformat(attdb.prev_monday)
        evidence.record_evidence(
            attdb.s1, kind=evidence.FIT_NOTE, covers_from=attdb.prev_monday,
            covers_to=(monday + _dt.timedelta(days=13)).isoformat())
        middle = (monday + _dt.timedelta(days=5)).isoformat()
        assert evidence.evidence_for_date(attdb.s1, middle)

    def test_evidence_outside_its_span_does_not_match(self, attdb):
        evidence.record_evidence(attdb.s1, covers_from=attdb.prev_monday,
                                 covers_to=attdb.prev_monday)
        assert evidence.evidence_for_date(attdb.s1, attdb.monday) == []

    def test_an_unknown_learner_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No student"):
            evidence.record_evidence("NOPE")

    def test_an_unknown_kind_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Kind must be"):
            evidence.record_evidence(attdb.s1, kind="A vibe")

    def test_withdrawn_evidence_stops_counting(self, attdb):
        item = evidence.record_evidence(attdb.s1,
                                        covers_from=attdb.prev_monday,
                                        covers_to=attdb.prev_monday)
        evidence.withdraw_evidence(item.evidence_id,
                                   reason="Not genuine", actor="head")
        assert evidence.evidence_for_date(attdb.s1, attdb.prev_monday) == []

    def test_withdrawing_needs_a_reason(self, attdb):
        item = evidence.record_evidence(attdb.s1)
        with pytest.raises(core.ValidationError, match="reason is required"):
            evidence.withdraw_evidence(item.evidence_id, reason="  ")


# ── 2. Requirements ────────────────────────────────────────────────

class TestRequirements:

    def test_a_requirement_gets_a_deadline(self, attdb, absence):
        requirement = evidence.require_evidence(absence.record_id,
                                                raised_by="office")
        assert requirement.state == evidence.AWAITING
        assert requirement.due_on > absence.date

    def test_the_deadline_follows_the_threshold(self, attdb, absence):
        thresholds.set_threshold(thresholds.EVIDENCE_DAYS, 2.0)
        requirement = evidence.require_evidence(absence.record_id)
        expected = (_dt.date.fromisoformat(absence.date)
                    + _dt.timedelta(days=2)).isoformat()
        assert requirement.due_on == expected

    def test_asking_twice_does_not_make_two_deadlines(self, attdb, absence):
        evidence.require_evidence(absence.record_id)
        evidence.require_evidence(absence.record_id)
        assert len(evidence.list_requirements()) == 1

    def test_a_reason_flagged_for_evidence_raises_one(self, attdb):
        reason = codes.reason_by_name("Medical appointment")
        assert reason.requires_evidence is True
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "M",
                                       "reason_id": reason.reason_id}})
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        assert evidence.raise_for_reason(record.record_id) is not None

    def test_a_reason_not_flagged_raises_nothing(self, attdb):
        reason = codes.reason_by_name("Illness")
        assert reason.requires_evidence is False
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "I",
                                       "reason_id": reason.reason_id}})
        record = core.get_record_for(attdb.slot, attdb.s1,
                                     attdb.prev_monday)
        assert evidence.raise_for_reason(record.record_id) is None

    def test_an_unknown_record_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No attendance "
                                                       "record"):
            evidence.require_evidence(9999)

    def test_outstanding_requirements_carry_names(self, attdb, absence):
        evidence.require_evidence(absence.record_id)
        assert evidence.outstanding()[0].student_name == "Ada Test"

    def test_satisfying_closes_it(self, attdb, absence):
        requirement = evidence.require_evidence(absence.record_id)
        item = evidence.record_evidence(attdb.s1,
                                        record_id=absence.record_id)
        out = evidence.satisfy(requirement.requirement_id,
                               evidence_id=item.evidence_id,
                               settled_by="office")
        assert out.state == evidence.RECEIVED

    def test_waiving_closes_it_with_a_reason(self, attdb, absence):
        requirement = evidence.require_evidence(absence.record_id)
        out = evidence.waive(requirement.requirement_id,
                             reason="Circumstances known",
                             settled_by="head")
        assert out.state == evidence.WAIVED
        assert out.note == "Circumstances known"

    def test_waiving_needs_a_reason(self, attdb, absence):
        requirement = evidence.require_evidence(absence.record_id)
        with pytest.raises(core.ValidationError, match="reason is required"):
            evidence.waive(requirement.requirement_id, reason="  ")


# ── 3. Enforcement ─────────────────────────────────────────────────

class TestEnforcement:

    @pytest.fixture
    def overdue(self, attdb, absence):
        """A requirement whose deadline has already passed."""
        yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        return evidence.require_evidence(absence.record_id,
                                         due_on=yesterday)

    def test_an_overdue_requirement_is_listed(self, attdb, overdue):
        assert [r.requirement_id for r in evidence.overdue()] == \
            [overdue.requirement_id]
        assert overdue.is_overdue() is True

    def test_a_dry_run_changes_nothing(self, attdb, absence, overdue):
        result = evidence.enforce_overdue(dry_run=True)
        assert result.checked == 1
        assert result.recoded == 0
        assert core.get_record(absence.record_id).code == "I"

    def test_enforcement_recodes_the_mark(self, attdb, absence, overdue):
        result = evidence.enforce_overdue(dry_run=False, actor="office")
        assert result.recoded == 1
        assert core.get_record(absence.record_id).code == evidence.UNMET_CODE

    def test_the_requirement_is_marked_expired(self, attdb, overdue):
        evidence.enforce_overdue(dry_run=False)
        out = evidence.get_requirement(overdue.requirement_id)
        assert out.state == evidence.EXPIRED

    def test_late_evidence_on_file_saves_the_mark(self, attdb, absence,
                                                  overdue):
        # Evidence that arrived without being linked still counts.
        evidence.record_evidence(attdb.s1, covers_from=absence.date,
                                 covers_to=absence.date)
        result = evidence.enforce_overdue(dry_run=False)
        assert result.recoded == 0
        assert core.get_record(absence.record_id).code == "I"

    def test_a_requirement_inside_its_deadline_is_untouched(self, attdb,
                                                            absence):
        evidence.require_evidence(absence.record_id)
        assert evidence.enforce_overdue(dry_run=False).checked == 0

    def test_the_chase_list_warns_before_the_deadline(self, attdb, absence):
        tomorrow = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
        evidence.require_evidence(absence.record_id, due_on=tomorrow)
        assert len(evidence.chase_list(days_ahead=2)) == 1
        assert evidence.chase_list(days_ahead=0) == []
