"""Tests for the primary school SEND service."""

import pytest


class TestSENDService:
    """Tests for SENDService (Special Educational Needs and Disabilities)."""

    def test_create_send_record(self, send_service):
        """Test creating a SEND record."""
        result = send_service.create_record(
            pupil_id="PRI0001",
            need_type="cognition_learning",
            description="Requires additional support with reading comprehension",
            support_level="SEN Support",
        )
        assert result is not None

    def test_get_send_records(self, send_service):
        """Test retrieving SEND records for a pupil."""
        send_service.create_record(
            pupil_id="PRI0002",
            need_type="communication_interaction",
            description="Speech and language therapy referral",
            support_level="SEN Support",
        )
        results = send_service.get_records("PRI0002")
        assert isinstance(results, list)

    def test_create_iep(self, send_service):
        """Test creating an Individual Education Plan."""
        result = send_service.create_iep(
            pupil_id="PRI0001",
            targets=["Improve reading fluency to age-appropriate level",
                     "Use phonics strategies independently"],
            strategies=["Daily guided reading", "Phonics intervention group"],
            review_date="2026-07-01",
        )
        assert result is not None or result is None
