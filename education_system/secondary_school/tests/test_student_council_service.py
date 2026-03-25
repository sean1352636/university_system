"""Tests for StudentCouncilService."""
import pytest
from education_system.secondary_school.modules.domain.student_life.student_council.services.student_council_service import StudentCouncilService


@pytest.fixture
def student_council_service(db_path):
    return StudentCouncilService(db_path)


class TestStudentCouncilCRUD:
    def test_create(self, student_council_service):
        rid = student_council_service.create(
            student_id="SEC0001", role="chair", year_group="11", term="Autumn",
        )
        assert isinstance(rid, int)
        record = student_council_service.get(rid)
        assert record["student_id"] == "SEC0001"
        assert record["role"] == "chair"
        assert record["year_group"] == "11"
        assert record["term"] == "Autumn"
        assert record["active"] == 1

    def test_list_all(self, student_council_service):
        student_council_service.create(student_id="SEC0001", role="chair")
        student_council_service.create(student_id="SEC0002", role="secretary")
        result = student_council_service.list_all()
        assert len(result) >= 2

    def test_get(self, student_council_service):
        rid = student_council_service.create(student_id="SEC0003", role="representative")
        found = student_council_service.get(rid)
        assert found is not None
        assert found["student_id"] == "SEC0003"

    def test_update(self, student_council_service):
        rid = student_council_service.create(student_id="SEC0001", role="representative")
        student_council_service.update(rid, role="vice_chair")
        updated = student_council_service.get(rid)
        assert updated["role"] == "vice_chair"

    def test_delete(self, student_council_service):
        rid = student_council_service.create(student_id="SEC0004")
        student_council_service.delete(rid)
        assert student_council_service.get(rid) is None
