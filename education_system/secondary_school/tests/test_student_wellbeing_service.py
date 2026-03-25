"""Tests for StudentWellbeingService."""
import pytest
from education_system.secondary_school.modules.domain.pastoral_care.student_wellbeing.services.student_wellbeing_service import StudentWellbeingService


@pytest.fixture
def student_wellbeing_service(db_path):
    return StudentWellbeingService(db_path)


class TestStudentWellbeingCRUD:
    def test_create(self, student_wellbeing_service):
        rid = student_wellbeing_service.create(
            student_id="SEC0001", referred_by="Mr Jones",
            concern_type="anxiety",
            description="Showing signs of anxiety in class",
        )
        assert isinstance(rid, int)
        record = student_wellbeing_service.get(rid)
        assert record["student_id"] == "SEC0001"
        assert record["referred_by"] == "Mr Jones"
        assert record["concern_type"] == "anxiety"
        assert record["risk_level"] == "Low"
        assert record["status"] == "Open"

    def test_list_all(self, student_wellbeing_service):
        student_wellbeing_service.create(
            student_id="SEC0001", referred_by="Ms Smith",
            concern_type="attendance", description="Frequent absences",
        )
        student_wellbeing_service.create(
            student_id="SEC0002", referred_by="Mr Jones",
            concern_type="social", description="Isolated in class",
        )
        result = student_wellbeing_service.list_all()
        assert len(result) >= 2

    def test_get(self, student_wellbeing_service):
        rid = student_wellbeing_service.create(
            student_id="SEC0003", referred_by="Mrs Brown",
            concern_type="bereavement", description="Recent family loss",
        )
        found = student_wellbeing_service.get(rid)
        assert found is not None
        assert found["concern_type"] == "bereavement"

    def test_update(self, student_wellbeing_service):
        rid = student_wellbeing_service.create(
            student_id="SEC0001", referred_by="Mr Jones",
            concern_type="anxiety", description="Anxious behaviour",
        )
        student_wellbeing_service.update(rid, status="In Progress", risk_level="Medium")
        updated = student_wellbeing_service.get(rid)
        assert updated["status"] == "In Progress"
        assert updated["risk_level"] == "Medium"

    def test_delete(self, student_wellbeing_service):
        rid = student_wellbeing_service.create(
            student_id="SEC0004", referred_by="Ms Green",
            concern_type="self-harm", description="Reported concern",
        )
        student_wellbeing_service.delete(rid)
        assert student_wellbeing_service.get(rid) is None
