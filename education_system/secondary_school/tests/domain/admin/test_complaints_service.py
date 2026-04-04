"""Tests for ComplaintsService."""
import pytest
from education_system.secondary_school.modules.domain.admin.complaints.services.complaints_service import ComplaintsService


@pytest.fixture
def complaints_service(db_path):
    return ComplaintsService(db_path)


class TestComplaintsCRUD:
    def test_create(self, complaints_service):
        r = complaints_service.create(subject="Noise complaint", description="Too loud in corridor",
                                       complainant_id="STF001", category="environment")
        assert r["subject"] == "Noise complaint"
        assert r["description"] == "Too loud in corridor"
        assert r["status"] == "open"
        assert r["priority"] == "normal"

    def test_list_all(self, complaints_service):
        complaints_service.create(subject="Complaint 1", description="Details 1")
        complaints_service.create(subject="Complaint 2", description="Details 2")
        result = complaints_service.list_all()
        assert len(result) >= 2

    def test_get(self, complaints_service):
        r = complaints_service.create(subject="Noise complaint", description="Too loud in corridor")
        found = complaints_service.get(r["id"])
        assert found is not None
        assert found["subject"] == "Noise complaint"
        assert found["description"] == "Too loud in corridor"

    def test_update(self, complaints_service):
        r = complaints_service.create(subject="Noise complaint", description="Too loud in corridor")
        updated = complaints_service.update(r["id"], status="resolved", priority="high")
        assert updated["status"] == "resolved"
        assert updated["priority"] == "high"

    def test_delete(self, complaints_service):
        r = complaints_service.create(subject="Noise complaint", description="Too loud in corridor")
        complaints_service.delete(r["id"])
        assert complaints_service.get(r["id"]) is None
