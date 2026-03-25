"""Tests for PayrollService."""
import pytest
from education_system.secondary_school.modules.domain.admin.payroll.services.payroll_service import PayrollService


@pytest.fixture
def payroll_service(db_path):
    return PayrollService(db_path)


class TestPayrollCRUD:
    def test_create(self, payroll_service):
        r = payroll_service.create(staff_id="STF001", pay_period="March 2026",
                                    gross_pay=3500.0, net_pay=2800.0, tax=500.0)
        assert r["staff_id"] == "STF001"
        assert r["pay_period"] == "March 2026"
        assert r["gross_pay"] == 3500.0
        assert r["net_pay"] == 2800.0
        assert r["tax"] == 500.0
        assert r["status"] == "draft"

    def test_list_all(self, payroll_service):
        payroll_service.create(staff_id="STF001", pay_period="March 2026",
                                gross_pay=3500.0, net_pay=2800.0)
        payroll_service.create(staff_id="STF002", pay_period="March 2026",
                                gross_pay=4000.0, net_pay=3200.0)
        result = payroll_service.list_all()
        assert len(result) >= 2

    def test_get(self, payroll_service):
        r = payroll_service.create(staff_id="STF001", pay_period="March 2026",
                                    gross_pay=3500.0, net_pay=2800.0, tax=500.0)
        found = payroll_service.get(r["id"])
        assert found is not None
        assert found["staff_id"] == "STF001"
        assert found["gross_pay"] == 3500.0

    def test_update(self, payroll_service):
        r = payroll_service.create(staff_id="STF001", pay_period="March 2026",
                                    gross_pay=3500.0, net_pay=2800.0)
        updated = payroll_service.update(r["id"], status="approved",
                                          approved_by="Finance Manager")
        assert updated["status"] == "approved"
        assert updated["approved_by"] == "Finance Manager"

    def test_delete(self, payroll_service):
        r = payroll_service.create(staff_id="STF001", pay_period="March 2026",
                                    gross_pay=3500.0, net_pay=2800.0)
        payroll_service.delete(r["id"])
        assert payroll_service.get(r["id"]) is None
