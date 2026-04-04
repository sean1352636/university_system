"""Tests for SATsService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import SATsError


class TestRecordResult:
    """Tests for recording SATs results."""

    def test_record_ks1_result(self, sats_service, sample_pupil_ks1):
        """Recording a KS1 SATs result should succeed."""
        result = sats_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS1",
            subject="Reading",
            raw_score=28,
            scaled_score=105,
            outcome="Expected",
        )
        assert result["result_id"] is not None
        assert result["pupil_id"] == sample_pupil_ks1["pupil_id"]
        assert result["subject"] == "Reading"
        assert result["key_stage"] == "KS1"

    def test_record_ks2_result(self, sats_service, sample_pupil_ks2):
        """Recording a KS2 SATs result should succeed."""
        result = sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Mathematics",
            raw_score=95,
            scaled_score=110,
            outcome="Greater Depth",
        )
        assert result["subject"] == "Mathematics"
        assert result["key_stage"] == "KS2"

    def test_record_below_expected(self, sats_service, sample_pupil_ks2):
        """Recording a below-expected outcome should persist."""
        sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Reading",
            outcome="Below Expected",
        )
        results = sats_service.get_results(
            pupil_id=sample_pupil_ks2["pupil_id"],
        )
        assert len(results) == 1
        assert results[0]["outcome"] == "Below Expected"

    def test_record_with_teacher_assessment(self, sats_service, sample_pupil_ks1):
        """Teacher assessment should persist alongside SATs result."""
        sats_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS1",
            subject="Writing",
            outcome="Expected",
            teacher_assessment="Expected",
            assessment_date="2026-05-15",
        )
        results = sats_service.get_results(
            pupil_id=sample_pupil_ks1["pupil_id"],
        )
        assert results[0]["teacher_assessment"] == "Expected"
        assert results[0]["assessment_date"] == "2026-05-15"

    def test_record_missing_pupil_id_raises(self, sats_service):
        """Missing pupil ID should raise SATsError."""
        with pytest.raises(SATsError):
            sats_service.record_result(
                pupil_id=None,
                academic_year="2025-2026",
                key_stage="KS2",
                subject="Reading",
            )

    def test_record_missing_subject_raises(self, sats_service, sample_pupil_ks2):
        """Missing subject should raise SATsError."""
        with pytest.raises(SATsError):
            sats_service.record_result(
                pupil_id=sample_pupil_ks2["pupil_id"],
                academic_year="2025-2026",
                key_stage="KS2",
                subject=None,
            )

    def test_record_missing_key_stage_raises(self, sats_service, sample_pupil_ks2):
        """Missing key stage should raise SATsError."""
        with pytest.raises(SATsError):
            sats_service.record_result(
                pupil_id=sample_pupil_ks2["pupil_id"],
                academic_year="2025-2026",
                key_stage=None,
                subject="Reading",
            )


class TestGetResults:
    """Tests for retrieving SATs results."""

    def test_get_by_pupil_id(self, sats_service, sample_pupil_ks2):
        """Filtering by pupil ID should return only that pupil's results."""
        sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Reading",
        )
        results = sats_service.get_results(
            pupil_id=sample_pupil_ks2["pupil_id"],
        )
        assert len(results) == 1
        assert results[0]["pupil_id"] == sample_pupil_ks2["pupil_id"]

    def test_get_by_key_stage(self, sats_service, sample_pupil_ks1,
                               sample_pupil_ks2):
        """Filtering by key stage should return matching results only."""
        sats_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS1",
            subject="Reading",
        )
        sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Reading",
        )
        results = sats_service.get_results(key_stage="KS1")
        assert len(results) == 1
        assert results[0]["key_stage"] == "KS1"

    def test_get_empty_results(self, sats_service):
        """Getting results from empty database should return empty list."""
        results = sats_service.get_results()
        assert results == []


class TestUpdateResult:
    """Tests for updating SATs results."""

    def test_update_scaled_score(self, sats_service, sample_pupil_ks2):
        """Updating scaled score should persist."""
        result = sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Mathematics",
            scaled_score=100,
        )
        updated = sats_service.update_result(
            result["result_id"], scaled_score=108,
        )
        assert updated["scaled_score"] == 108

    def test_update_outcome(self, sats_service, sample_pupil_ks2):
        """Updating outcome level should persist."""
        result = sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Reading",
            outcome="Expected",
        )
        updated = sats_service.update_result(
            result["result_id"], outcome="Greater Depth",
        )
        assert updated["outcome"] == "Greater Depth"

    def test_update_no_valid_fields(self, sats_service, sample_pupil_ks2):
        """Updating with no valid fields should return None."""
        result = sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Reading",
        )
        updated = sats_service.update_result(
            result["result_id"], invalid_field="test",
        )
        assert updated is None


class TestDeleteResult:
    """Tests for deleting SATs results."""

    def test_delete_existing_result(self, sats_service, sample_pupil_ks2):
        """Deleting an existing result should return True."""
        result = sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Reading",
        )
        deleted = sats_service.delete_result(result["result_id"])
        assert deleted is True

    def test_delete_nonexistent_result(self, sats_service):
        """Deleting a non-existent result should return False."""
        deleted = sats_service.delete_result(99999)
        assert deleted is False

    def test_delete_removes_from_database(self, sats_service, sample_pupil_ks2):
        """Deleted result should no longer appear in get_results."""
        result = sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Maths",
        )
        sats_service.delete_result(result["result_id"])
        results = sats_service.get_results(
            pupil_id=sample_pupil_ks2["pupil_id"],
        )
        assert results == []


class TestCohortSummary:
    """Tests for cohort summary statistics."""

    def test_cohort_summary_distribution(self, sats_service, sample_pupil_ks1,
                                         sample_pupil_ks2):
        """Summary should return outcome distribution per subject."""
        sats_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Reading",
            outcome="Expected",
        )
        sats_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            key_stage="KS2",
            subject="Reading",
            outcome="Greater Depth",
        )
        summary = sats_service.get_cohort_summary(
            academic_year="2025-2026", key_stage="KS2",
        )
        assert "Reading" in summary
        assert summary["Reading"]["total"] == 2
        assert "Expected" in summary["Reading"]["outcomes"]
        assert "Greater Depth" in summary["Reading"]["outcomes"]
        assert summary["Reading"]["outcomes"]["Expected"]["percentage"] == 50.0

    def test_cohort_summary_empty(self, sats_service):
        """Summary for empty cohort should return empty dict."""
        summary = sats_service.get_cohort_summary(
            academic_year="2025-2026", key_stage="KS2",
        )
        assert summary == {}
