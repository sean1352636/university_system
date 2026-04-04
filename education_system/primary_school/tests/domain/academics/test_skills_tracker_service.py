"""Tests for SkillsTrackerService in the Primary School Management System."""

import pytest


class TestRecordAssessment:
    """Tests for recording skill assessments."""

    def test_record_assessment(self, skills_tracker_service, sample_pupil):
        """Recording a skill assessment should return a valid ID."""
        result_id = skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="literacy",
            level="developing",
            term="Autumn",
            academic_year="2025-2026",
            assessed_by="Mrs Taylor",
        )
        assert result_id is not None
        assert isinstance(result_id, int)

    def test_record_all_levels(self, skills_tracker_service, sample_pupil):
        """All four assessment levels should be recordable."""
        levels = ["emerging", "developing", "expected", "greater_depth"]
        for level in levels:
            result_id = skills_tracker_service.record_assessment(
                pupil_id=sample_pupil["pupil_id"],
                skill_area="mathematics",
                level=level,
            )
            assert result_id is not None

    def test_record_with_notes(self, skills_tracker_service, sample_pupil):
        """Recording with notes should persist them."""
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="physical_development",
            level="expected",
            notes="Good fine motor control",
        )
        progress = skills_tracker_service.get_pupil_progress(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="physical_development",
        )
        assert len(progress) == 1
        assert progress[0]["notes"] == "Good fine motor control"

    def test_record_invalid_skill_area_raises(self, skills_tracker_service,
                                               sample_pupil):
        """An unknown skill area should raise ValueError."""
        with pytest.raises(ValueError):
            skills_tracker_service.record_assessment(
                pupil_id=sample_pupil["pupil_id"],
                skill_area="unknown_area",
                level="expected",
            )

    def test_record_invalid_level_raises(self, skills_tracker_service,
                                          sample_pupil):
        """An invalid level should raise ValueError."""
        with pytest.raises(ValueError):
            skills_tracker_service.record_assessment(
                pupil_id=sample_pupil["pupil_id"],
                skill_area="literacy",
                level="outstanding",
            )


class TestGetPupilProfile:
    """Tests for retrieving a pupil's skill profile."""

    def test_profile_returns_all_areas(self, skills_tracker_service, sample_pupil):
        """Profile should include an entry for every skill area."""
        profile = skills_tracker_service.get_pupil_profile(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert "literacy" in profile
        assert "mathematics" in profile
        assert "communication_language" in profile
        assert len(profile) == 9  # All SKILL_AREAS

    def test_profile_shows_latest_assessment(self, skills_tracker_service,
                                              sample_pupil):
        """Profile should show the most recent assessment for each area."""
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="literacy",
            level="emerging",
            term="Autumn",
            academic_year="2024-2025",
        )
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="literacy",
            level="developing",
            term="Spring",
            academic_year="2025-2026",
        )
        profile = skills_tracker_service.get_pupil_profile(
            pupil_id=sample_pupil["pupil_id"],
        )
        # The latest recorded assessment should appear in the profile
        assert profile["literacy"]["current_level"] in ("emerging", "developing")

    def test_profile_unassessed_area_is_none(self, skills_tracker_service,
                                              sample_pupil):
        """Skill areas with no assessments should have current_level None."""
        profile = skills_tracker_service.get_pupil_profile(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert profile["science"]["current_level"] is None
        assert profile["science"]["assessed_at"] is None


class TestGetPupilProgress:
    """Tests for retrieving a pupil's assessment history."""

    def test_progress_all_areas(self, skills_tracker_service, sample_pupil):
        """Getting progress without skill_area filter returns all records."""
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="literacy",
            level="emerging",
        )
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="mathematics",
            level="expected",
        )
        progress = skills_tracker_service.get_pupil_progress(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(progress) == 2

    def test_progress_filtered_by_skill(self, skills_tracker_service, sample_pupil):
        """Filtering by skill_area should return only matching records."""
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="literacy",
            level="emerging",
        )
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="mathematics",
            level="expected",
        )
        progress = skills_tracker_service.get_pupil_progress(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="literacy",
        )
        assert len(progress) == 1
        assert progress[0]["skill_area"] == "literacy"

    def test_progress_empty(self, skills_tracker_service, sample_pupil):
        """Progress for a pupil with no assessments should be empty."""
        progress = skills_tracker_service.get_pupil_progress(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert progress == []


class TestGetClassSummary:
    """Tests for class-level summary statistics."""

    def test_class_summary_counts(self, skills_tracker_service, sample_pupil,
                                   sample_pupil_ks1, sample_pupil_ks2):
        """Summary should count pupils at each level."""
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="literacy",
            level="emerging",
        )
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil_ks1["pupil_id"],
            skill_area="literacy",
            level="expected",
        )
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil_ks2["pupil_id"],
            skill_area="literacy",
            level="expected",
        )
        pupil_ids = [
            sample_pupil["pupil_id"],
            sample_pupil_ks1["pupil_id"],
            sample_pupil_ks2["pupil_id"],
        ]
        summary = skills_tracker_service.get_class_summary(
            pupil_ids=pupil_ids, skill_area="literacy",
        )
        assert summary["total_pupils"] == 3
        assert summary["level_counts"]["emerging"] == 1
        assert summary["level_counts"]["expected"] == 2
        assert summary["skill_area"] == "literacy"

    def test_class_summary_percentages(self, skills_tracker_service, sample_pupil,
                                        sample_pupil_ks1):
        """Summary should calculate correct percentages."""
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil["pupil_id"],
            skill_area="mathematics",
            level="developing",
        )
        skills_tracker_service.record_assessment(
            pupil_id=sample_pupil_ks1["pupil_id"],
            skill_area="mathematics",
            level="developing",
        )
        pupil_ids = [
            sample_pupil["pupil_id"],
            sample_pupil_ks1["pupil_id"],
        ]
        summary = skills_tracker_service.get_class_summary(
            pupil_ids=pupil_ids, skill_area="mathematics",
        )
        assert summary["level_percentages"]["developing"] == 100.0
        assert summary["level_percentages"]["emerging"] == 0

    def test_class_summary_empty(self, skills_tracker_service):
        """Summary with no pupils should return zero totals."""
        summary = skills_tracker_service.get_class_summary(
            pupil_ids=[], skill_area="literacy",
        )
        assert summary["total_pupils"] == 0
