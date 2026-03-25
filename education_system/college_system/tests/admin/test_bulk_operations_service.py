"""Tests for BulkOperationService."""

import pytest
from education_system.college_system.core.exceptions import BulkOperationError, ValidationError


class TestBulkOperationService:
    """Test suite for BulkOperationService."""

    def test_create_job(self, bulk_operations_service):
        item = bulk_operations_service.create_job(job_type="test_job_type", initiated_by=1)
        assert item["id"] is not None

    def test_get_job(self, bulk_operations_service):
        item = bulk_operations_service.create_job(job_type="test_job_type", initiated_by=1)
        found = bulk_operations_service.get_job(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_jobs(self, bulk_operations_service):
        bulk_operations_service.create_job(job_type="test_job_type", initiated_by=1)
        items = bulk_operations_service.list_jobs()
        assert len(items) >= 1

    def test_update_job(self, bulk_operations_service):
        item = bulk_operations_service.create_job(job_type="test_job_type", initiated_by=1)
        updated = bulk_operations_service.update_job(item["id"], job_type="updated_value")
        assert updated["job_type"] == "updated_value"

    def test_delete_job(self, bulk_operations_service):
        item = bulk_operations_service.create_job(job_type="test_job_type", initiated_by=1)
        result = bulk_operations_service.delete_job(item["id"])
        assert result is True
        assert bulk_operations_service.get_job(item["id"]) is None

    def test_count_jobs(self, bulk_operations_service):
        bulk_operations_service.create_job(job_type="test_job_type", initiated_by=1)
        count = bulk_operations_service.count_jobs()
        assert count >= 1

    def test_delete_nonexistent_raises(self, bulk_operations_service):
        with pytest.raises(BulkOperationError):
            bulk_operations_service.delete_job(99999)
