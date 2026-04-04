"""Tests for AssessmentService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import AssessmentError


class TestRecordAssessment:
    """Tests for recording assessments."""

    def test_record_formative_assessment(self, assessment_service, sample_pupil,
                                         sample_subject):
        """Recording a formative assessment with a valid level should succeed."""
        result = assessment_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            subject_code=sample_subject["subject_code"],
            level="Expected",
            assessment_type="Formative",
            term="Autumn",
            academic_year="2025-2026",
            year_group="Reception",
        )
        assert result["assessment_id"] is not None
        assert result["pupil_id"] == sample_pupil["pupil_id"]
        assert result["subject_code"] == "ENG"
        assert result["level"] == "Expected"

    def test_record_summative_assessment(self, assessment_service, sample_pupil,
                                          sample_subject):
        """Recording a summative assessment should succeed."""
        result = assessment_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            subject_code=sample_subject["subject_code"],
            level="Greater Depth",
            assessment_type="Summative",
            term="Summer",
            academic_year="2025-2026",
        )
        assert result["level"] == "Greater Depth"

    def test_record_all_assessment_levels(self, assessment_service, sample_pupil,
                                           sample_subject):
        """All four assessment levels should be recordable."""
        levels = ["Emerging", "Developing", "Expected", "Greater Depth"]
        for level in levels:
            result = assessment_service.record_assessment(
                pupil_id=sample_pupil["pupil_id"],
                subject_code=sample_subject["subject_code"],
                level=level,
                term="Spring",
            )
            assert result["level"] == level

    def test_record_assessment_with_score(self, assessment_service, sample_pupil,
                                           sample_subject):
        """Recording an assessment with numeric score should persist."""
        result = assessment_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            subject_code=sample_subject["subject_code"],
            level="Expected",
            score=42,
            max_score=50,
        )
        records = assessment_service.get_assessments(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(records) == 1
        assert records[0]["score"] == 42
        assert records[0]["max_score"] == 50

    def test_record_assessment_with_comments(self, assessment_service, sample_pupil,
                                              sample_subject):
        """Recording an assessment with comments should persist."""
        assessment_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            subject_code=sample_subject["subject_code"],
            level="Developing",
            comments="Making good progress with phonics",
            assessed_by="Mrs Taylor",
        )
        records = assessment_service.get_assessments(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert records[0]["comments"] == "Making good progress with phonics"
        assert records[0]["assessed_by"] == "Mrs Taylor"

    def test_record_assessment_missing_pupil_id_raises(self, assessment_service,
                                                        sample_subject):
        """Missing pupil ID should raise AssessmentError."""
        with pytest.raises(AssessmentError):
            assessment_service.record_assessment(
                pupil_id=None,
                subject_code=sample_subject["subject_code"],
                level="Expected",
            )

    def test_record_assessment_missing_subject_raises(self, assessment_service,
                                                       sample_pupil):
        """Missing subject code should raise AssessmentError."""
        with pytest.raises(AssessmentError):
            assessment_service.record_assessment(
                pupil_id=sample_pupil["pupil_id"],
                subject_code=None,
                level="Expected",
            )

    def test_record_assessment_missing_level_raises(self, assessment_service,
                                                     sample_pupil, sample_subject):
        """Missing level should raise AssessmentError."""
        with pytest.raises(AssessmentError):
            assessment_service.record_assessment(
                pupil_id=sample_pupil["pupil_id"],
                subject_code=sample_subject["subject_code"],
                level=None,
            )


class TestGetAssessments:
    """Tests for retrieving assessments."""

    def test_get_by_pupil_id(self, assessment_service, sample_pupil, sample_subject):
        """Filtering by pupil ID should return only that pupil's assessments."""
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], sample_subject["subject_code"], "Expected",
        )
        records = assessment_service.get_assessments(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(records) == 1
        assert records[0]["pupil_id"] == sample_pupil["pupil_id"]

    def test_get_by_subject_code(self, assessment_service, sample_pupil,
                                  sample_subject, sample_subject_maths):
        """Filtering by subject code should return only matching assessments."""
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Expected",
        )
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], "MAT", "Developing",
        )
        eng = assessment_service.get_assessments(subject_code="ENG")
        mat = assessment_service.get_assessments(subject_code="MAT")
        assert len(eng) == 1
        assert len(mat) == 1
        assert eng[0]["level"] == "Expected"
        assert mat[0]["level"] == "Developing"

    def test_get_by_term(self, assessment_service, sample_pupil, sample_subject):
        """Filtering by term should work correctly."""
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Emerging", term="Autumn",
        )
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Developing", term="Spring",
        )
        autumn = assessment_service.get_assessments(term="Autumn")
        assert len(autumn) == 1
        assert autumn[0]["level"] == "Emerging"

    def test_get_by_academic_year(self, assessment_service, sample_pupil,
                                   sample_subject):
        """Filtering by academic year should work correctly."""
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Expected",
            academic_year="2025-2026",
        )
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Greater Depth",
            academic_year="2024-2025",
        )
        current = assessment_service.get_assessments(academic_year="2025-2026")
        assert len(current) == 1
        assert current[0]["level"] == "Expected"

    def test_get_no_filters_returns_all(self, assessment_service, sample_pupil,
                                         sample_subject):
        """Getting assessments with no filters should return all records."""
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Expected",
        )
        assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Developing",
        )
        records = assessment_service.get_assessments()
        assert len(records) == 2

    def test_get_empty_results(self, assessment_service):
        """Getting assessments from empty database should return empty list."""
        records = assessment_service.get_assessments()
        assert records == []


class TestUpdateAssessment:
    """Tests for updating assessments."""

    def test_update_level(self, assessment_service, sample_pupil, sample_subject):
        """Updating an assessment level should persist."""
        result = assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Emerging",
        )
        updated = assessment_service.update_assessment(
            result["assessment_id"], level="Developing",
        )
        assert updated["level"] == "Developing"

    def test_update_score(self, assessment_service, sample_pupil, sample_subject):
        """Updating score fields should persist."""
        result = assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Expected",
        )
        updated = assessment_service.update_assessment(
            result["assessment_id"], score=35, max_score=40,
        )
        assert updated["score"] == 35
        assert updated["max_score"] == 40

    def test_update_no_valid_fields(self, assessment_service, sample_pupil,
                                     sample_subject):
        """Updating with no valid fields should return None."""
        result = assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Expected",
        )
        updated = assessment_service.update_assessment(
            result["assessment_id"], invalid_field="test",
        )
        assert updated is None


class TestDeleteAssessment:
    """Tests for deleting assessments."""

    def test_delete_existing_assessment(self, assessment_service, sample_pupil,
                                         sample_subject):
        """Deleting an existing assessment should return True."""
        result = assessment_service.record_assessment(
            sample_pupil["pupil_id"], "ENG", "Expected",
        )
        deleted = assessment_service.delete_assessment(result["assessment_id"])
        assert deleted is True

    def test_delete_nonexistent_assessment(self, assessment_service):
        """Deleting a non-existent assessment should return False."""
        deleted = assessment_service.delete_assessment(99999)
        assert deleted is False


class TestGetPupilSummary:
    """Tests for the pupil assessment summary."""

    def test_summary_returns_per_subject(self, assessment_service, sample_pupil,
                                         sample_subject, sample_subject_maths):
        """Summary should return assessments for each subject."""
        pid = sample_pupil["pupil_id"]
        assessment_service.record_assessment(pid, "ENG", "Expected")
        assessment_service.record_assessment(pid, "MAT", "Developing")

        summary = assessment_service.get_pupil_summary(pid)
        assert len(summary) == 2
        subject_codes = {s["subject_code"] for s in summary}
        assert "ENG" in subject_codes
        assert "MAT" in subject_codes

    def test_summary_empty(self, assessment_service, sample_pupil):
        """Summary for a pupil with no assessments should be empty."""
        summary = assessment_service.get_pupil_summary(sample_pupil["pupil_id"])
        assert summary == []
