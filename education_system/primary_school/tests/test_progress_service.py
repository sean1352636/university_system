"""Tests for the primary school progress tracking service."""

import pytest


class TestProgressService:
    """Tests for ProgressService."""

    def test_record_progress(self, progress_service):
        """Test recording academic progress."""
        result = progress_service.record_progress(
            pupil_id="PRI0001",
            subject="Mathematics",
            level="expected",
            term="Autumn",
            academic_year="2025-2026",
        )
        assert result is not None

    def test_get_pupil_progress(self, progress_service):
        """Test getting progress for a pupil."""
        progress_service.record_progress(
            pupil_id="PRI0002",
            subject="English",
            level="developing",
            term="Autumn",
            academic_year="2025-2026",
        )
        results = progress_service.get_progress("PRI0002")
        assert isinstance(results, list)

    def test_get_progress_summary(self, progress_service):
        """Test getting progress summary across subjects."""
        for subj in ["Mathematics", "English", "Science"]:
            progress_service.record_progress(
                pupil_id="PRI0003",
                subject=subj,
                level="expected",
                term="Spring",
                academic_year="2025-2026",
            )
        summary = progress_service.get_summary("PRI0003")
        assert isinstance(summary, (dict, list))
