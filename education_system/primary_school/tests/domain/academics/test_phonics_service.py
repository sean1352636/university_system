"""Tests for PhonicsService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import PhonicsError


class TestRecordResult:
    """Tests for recording phonics screening results."""

    def test_record_passing_result(self, phonics_service, sample_pupil_ks1):
        """Recording a score at or above 32 should mark as passed."""
        result = phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=35,
        )
        assert result["result_id"] is not None
        assert result["pupil_id"] == sample_pupil_ks1["pupil_id"]
        assert result["score"] == 35
        assert result["passed"] == 1

    def test_record_failing_result(self, phonics_service, sample_pupil_ks1):
        """Recording a score below 32 should mark as not passed."""
        result = phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=28,
        )
        assert result["passed"] == 0

    def test_record_exact_threshold(self, phonics_service, sample_pupil_ks1):
        """A score of exactly 32 should pass (>= threshold)."""
        result = phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=32,
        )
        assert result["passed"] == 1

    def test_record_resit(self, phonics_service, sample_pupil_ks1):
        """Recording a resit should persist the is_resit flag."""
        phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 2",
            score=34,
            is_resit=1,
        )
        results = phonics_service.get_results(
            pupil_id=sample_pupil_ks1["pupil_id"],
        )
        assert len(results) == 1
        assert results[0]["is_resit"] == 1

    def test_record_missing_pupil_id_raises(self, phonics_service):
        """Missing pupil ID should raise PhonicsError."""
        with pytest.raises(PhonicsError):
            phonics_service.record_result(
                pupil_id=None,
                academic_year="2025-2026",
                year_group="Year 1",
                score=35,
            )

    def test_record_missing_score_raises(self, phonics_service, sample_pupil_ks1):
        """Missing score should raise PhonicsError."""
        with pytest.raises(PhonicsError):
            phonics_service.record_result(
                pupil_id=sample_pupil_ks1["pupil_id"],
                academic_year="2025-2026",
                year_group="Year 1",
                score=None,
            )


class TestGetResults:
    """Tests for retrieving phonics results."""

    def test_get_by_pupil_id(self, phonics_service, sample_pupil_ks1):
        """Filtering by pupil ID should return only that pupil's results."""
        phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=36,
        )
        results = phonics_service.get_results(
            pupil_id=sample_pupil_ks1["pupil_id"],
        )
        assert len(results) == 1
        assert results[0]["pupil_id"] == sample_pupil_ks1["pupil_id"]

    def test_get_by_academic_year(self, phonics_service, sample_pupil_ks1):
        """Filtering by academic year should return matching results only."""
        phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=30,
        )
        phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2024-2025",
            year_group="Year 1",
            score=38,
        )
        results = phonics_service.get_results(academic_year="2025-2026")
        assert len(results) == 1
        assert results[0]["score"] == 30

    def test_get_empty_results(self, phonics_service):
        """Getting results from empty database should return empty list."""
        results = phonics_service.get_results()
        assert results == []


class TestUpdateResult:
    """Tests for updating phonics results."""

    def test_update_score_recalculates_passed(self, phonics_service, sample_pupil_ks1):
        """Updating score should recalculate the passed flag."""
        result = phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=28,
        )
        assert result["passed"] == 0

        updated = phonics_service.update_result(
            result["result_id"], score=35,
        )
        assert updated["score"] == 35
        assert updated["passed"] == 1

    def test_update_no_valid_fields(self, phonics_service, sample_pupil_ks1):
        """Updating with no valid fields should return None."""
        result = phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=33,
        )
        updated = phonics_service.update_result(
            result["result_id"], invalid_field="test",
        )
        assert updated is None


class TestDeleteResult:
    """Tests for deleting phonics results."""

    def test_delete_existing_result(self, phonics_service, sample_pupil_ks1):
        """Deleting an existing result should return True."""
        result = phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=36,
        )
        deleted = phonics_service.delete_result(result["result_id"])
        assert deleted is True

    def test_delete_nonexistent_result(self, phonics_service):
        """Deleting a non-existent result should return False."""
        deleted = phonics_service.delete_result(99999)
        assert deleted is False

    def test_delete_removes_from_database(self, phonics_service, sample_pupil_ks1):
        """Deleted result should no longer appear in get_results."""
        result = phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=40,
        )
        phonics_service.delete_result(result["result_id"])
        results = phonics_service.get_results(
            pupil_id=sample_pupil_ks1["pupil_id"],
        )
        assert results == []


class TestCohortSummary:
    """Tests for cohort summary statistics."""

    def test_cohort_summary_pass_rate(self, phonics_service, sample_pupil_ks1,
                                      sample_pupil_ks2):
        """Summary should calculate correct pass rate."""
        phonics_service.record_result(
            pupil_id=sample_pupil_ks1["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=35,
        )
        phonics_service.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025-2026",
            year_group="Year 1",
            score=25,
        )
        summary = phonics_service.get_cohort_summary(
            academic_year="2025-2026", year_group="Year 1",
        )
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["pass_rate"] == 50.0

    def test_cohort_summary_empty(self, phonics_service):
        """Summary for empty cohort should return zeroed statistics."""
        summary = phonics_service.get_cohort_summary(
            academic_year="2025-2026", year_group="Year 1",
        )
        assert summary["total"] == 0
        assert summary["pass_rate"] == 0
