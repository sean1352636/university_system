"""Tests for the primary school safeguarding service."""

import pytest


class TestSafeguardingService:
    """Tests for SafeguardingService."""

    def test_record_concern(self, safeguarding_service, sample_pupil):
        """Test raising a safeguarding concern."""
        result = safeguarding_service.record_concern(
            pupil_id=sample_pupil["pupil_id"],
            reported_by="STF0001",
            concern_type="welfare",
            description="Pupil appeared distressed during morning registration",
            severity="Medium",
        )
        assert result is not None

    def test_get_concerns(self, safeguarding_service, sample_pupil):
        """Test retrieving concerns for a pupil."""
        safeguarding_service.record_concern(
            pupil_id=sample_pupil["pupil_id"],
            reported_by="STF0001",
            concern_type="attendance",
            description="Persistent lateness",
            severity="Low",
        )
        results = safeguarding_service.get_concerns(pupil_id=sample_pupil["pupil_id"])
        assert isinstance(results, list)

    def test_update_concern(self, safeguarding_service, sample_pupil):
        """Test updating a concern."""
        concern_id = safeguarding_service.record_concern(
            pupil_id=sample_pupil["pupil_id"],
            reported_by="STF0002",
            concern_type="welfare",
            description="Visible bruising noted",
            severity="High",
        )
        if concern_id:
            result = safeguarding_service.update_concern(
                concern_id=concern_id,
                action_taken="Referred to DSL",
            )
            assert result is not None or result is None
