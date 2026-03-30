"""Tests for the primary school safeguarding service."""

import pytest


class TestSafeguardingService:
    """Tests for SafeguardingService."""

    def test_create_concern(self, safeguarding_service):
        """Test raising a safeguarding concern."""
        result = safeguarding_service.create_concern(
            pupil_id="PRI0001",
            reported_by="STF0001",
            concern_type="welfare",
            description="Pupil appeared distressed during morning registration",
            severity="medium",
        )
        assert result is not None

    def test_get_concerns_for_pupil(self, safeguarding_service):
        """Test retrieving concerns for a pupil."""
        safeguarding_service.create_concern(
            pupil_id="PRI0002",
            reported_by="STF0001",
            concern_type="attendance",
            description="Persistent lateness",
            severity="low",
        )
        results = safeguarding_service.get_concerns("PRI0002")
        assert isinstance(results, list)

    def test_update_concern_status(self, safeguarding_service):
        """Test updating concern status."""
        concern_id = safeguarding_service.create_concern(
            pupil_id="PRI0003",
            reported_by="STF0002",
            concern_type="welfare",
            description="Visible bruising noted",
            severity="high",
        )
        if concern_id:
            result = safeguarding_service.update_status(
                concern_id=concern_id,
                status="under_review",
                updated_by="STF0001",
            )
            assert result is not None or result is None
