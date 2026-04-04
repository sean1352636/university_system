"""Tests for GDPRService."""
import pytest
from education_system.secondary_school.modules.domain.admin.gdpr.services.gdpr_service import GDPRService


@pytest.fixture
def gdpr_service(db_path):
    return GDPRService(db_path)


class TestGDPRCRUD:
    def test_create(self, gdpr_service):
        r = gdpr_service.create(requester_name="Jane Doe", request_type="data_access",
                                 requester_email="jane@test.com")
        assert r["requester_name"] == "Jane Doe"
        assert r["request_type"] == "data_access"
        assert r["requester_email"] == "jane@test.com"
        assert r["status"] == "pending"

    def test_list_all(self, gdpr_service):
        gdpr_service.create(requester_name="Jane Doe", request_type="data_access")
        gdpr_service.create(requester_name="John Smith", request_type="data_deletion")
        result = gdpr_service.list_all()
        assert len(result) >= 2

    def test_get(self, gdpr_service):
        r = gdpr_service.create(requester_name="Jane Doe", request_type="data_access",
                                 requester_email="jane@test.com")
        found = gdpr_service.get(r["id"])
        assert found is not None
        assert found["requester_name"] == "Jane Doe"
        assert found["request_type"] == "data_access"

    def test_update(self, gdpr_service):
        r = gdpr_service.create(requester_name="Jane Doe", request_type="data_access")
        updated = gdpr_service.update(r["id"], status="completed", processed_by="admin")
        assert updated["status"] == "completed"
        assert updated["processed_by"] == "admin"

    def test_delete(self, gdpr_service):
        r = gdpr_service.create(requester_name="Jane Doe", request_type="data_access")
        gdpr_service.delete(r["id"])
        assert gdpr_service.get(r["id"]) is None
