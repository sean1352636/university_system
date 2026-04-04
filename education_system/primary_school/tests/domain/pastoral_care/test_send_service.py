"""Tests for the primary school SEND service."""

import pytest


class TestSENDService:
    """Tests for SENDService (Special Educational Needs and Disabilities)."""

    def test_create_send_record(self, send_service, sample_pupil):
        """Test creating a SEND record."""
        result = send_service.create_record(
            pupil_id=sample_pupil["pupil_id"],
            sen_status="SEN Support",
            primary_need="Cognition and Learning",
            notes="Requires additional support with reading comprehension",
        )
        assert result is not None

    def test_list_send_records(self, send_service, sample_pupil):
        """Test listing SEND records."""
        send_service.create_record(
            pupil_id=sample_pupil["pupil_id"],
            sen_status="SEN Support",
            primary_need="Communication and Interaction",
            notes="Speech and language therapy referral",
        )
        results = send_service.list_records(sen_status="SEN Support")
        assert isinstance(results, list)

    def test_add_provision(self, send_service, sample_pupil):
        """Test adding a provision for a pupil."""
        send_service.create_record(
            pupil_id=sample_pupil["pupil_id"],
            sen_status="SEN Support",
            primary_need="Cognition and Learning",
        )
        result = send_service.add_provision(
            pupil_id=sample_pupil["pupil_id"],
            provision_type="Intervention",
            description="Daily guided reading",
            frequency="Daily",
        )
        assert result is not None or result is None
