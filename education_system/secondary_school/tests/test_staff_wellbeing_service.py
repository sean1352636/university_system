"""Tests for StaffWellbeingService."""
import pytest
from education_system.secondary_school.modules.domain.staff.staff_wellbeing.services.staff_wellbeing_service import StaffWellbeingService


@pytest.fixture
def staff_wellbeing_service(db_path):
    return StaffWellbeingService(db_path)


class TestStaffWellbeingCRUD:
    def test_create(self, staff_wellbeing_service):
        rid = staff_wellbeing_service.create(title="Term 2 Survey", description="Staff satisfaction", created_by="admin")
        assert isinstance(rid, int)
        record = staff_wellbeing_service.get(rid)
        assert record["title"] == "Term 2 Survey"
        assert record["status"] == "draft"

    def test_list_all(self, staff_wellbeing_service):
        staff_wellbeing_service.create(title="Survey A")
        staff_wellbeing_service.create(title="Survey B")
        result = staff_wellbeing_service.list_all()
        assert len(result) >= 2

    def test_get(self, staff_wellbeing_service):
        rid = staff_wellbeing_service.create(title="Survey")
        found = staff_wellbeing_service.get(rid)
        assert found is not None
        assert found["title"] == "Survey"

    def test_update(self, staff_wellbeing_service):
        rid = staff_wellbeing_service.create(title="Draft Survey")
        staff_wellbeing_service.update(rid, status="active", title="Live Survey")
        updated = staff_wellbeing_service.get(rid)
        assert updated["status"] == "active"
        assert updated["title"] == "Live Survey"

    def test_delete(self, staff_wellbeing_service):
        rid = staff_wellbeing_service.create(title="Temp")
        staff_wellbeing_service.delete(rid)
        assert staff_wellbeing_service.get(rid) is None
