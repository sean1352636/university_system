"""Tests for the primary school progress tracking service."""

import pytest


class TestProgressService:
    """Tests for ProgressService."""

    def test_record_progress(self, progress_service, sample_pupil, sample_subject):
        """Test recording academic progress."""
        result = progress_service.record_progress(
            pupil_id=sample_pupil["pupil_id"],
            subject_code=sample_subject["subject_code"],
            term="Autumn",
            academic_year="2025-2026",
            current_level="Expected",
        )
        assert result is not None

    def test_get_pupil_progress(self, progress_service, sample_pupil, sample_subject):
        """Test getting progress for a pupil."""
        progress_service.record_progress(
            pupil_id=sample_pupil["pupil_id"],
            subject_code=sample_subject["subject_code"],
            term="Autumn",
            academic_year="2025-2026",
            current_level="Developing",
        )
        results = progress_service.get_progress(pupil_id=sample_pupil["pupil_id"])
        assert isinstance(results, list)

    def test_get_progress_by_year(self, progress_service, sample_pupil, sample_subject, sample_subject_maths):
        """Test getting progress across subjects for an academic year."""
        for subj in [sample_subject, sample_subject_maths]:
            progress_service.record_progress(
                pupil_id=sample_pupil["pupil_id"],
                subject_code=subj["subject_code"],
                term="Spring",
                academic_year="2025-2026",
                current_level="Expected",
            )
        results = progress_service.get_progress(
            pupil_id=sample_pupil["pupil_id"], academic_year="2025-2026"
        )
        assert isinstance(results, list)
