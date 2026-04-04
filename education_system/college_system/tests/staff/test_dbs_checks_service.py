"""Tests for DBSCheckService."""

import pytest


class TestDBSCheckService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.dbs_checks.services.dbs_checks_service import DBSCheckService
        return DBSCheckService(db_path)

    def test_create_check(self, service):
        check = service.create_check(
            staff_id=1, check_type="enhanced",
            certificate_number="DBS123456",
            issue_date="2025-01-15", expiry_date="2028-01-15",
        )
        assert check is not None

    def test_list_checks(self, service):
        service.create_check(staff_id=1, certificate_number="A001")
        service.create_check(staff_id=2, certificate_number="A002")
        checks = service.list_checks()
        assert len(checks) >= 2

    def test_get_check(self, service):
        check = service.create_check(staff_id=1, certificate_number="GET001")
        found = service.get_check(check["id"])
        assert found is not None

    def test_update_check(self, service):
        check = service.create_check(staff_id=1, certificate_number="UPD001")
        updated = service.update_check(check["id"], status="expired")
        assert updated is not None

    def test_delete_check(self, service):
        check = service.create_check(staff_id=1, certificate_number="DEL001")
        result = service.delete_check(check["id"])
        assert result is True

    def test_get_expiring(self, service):
        service.create_check(
            staff_id=1, certificate_number="EXP001",
            issue_date="2023-01-01", expiry_date="2026-05-01",
        )
        expiring = service.get_expiring(within_days=90)
        assert isinstance(expiring, list)

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
