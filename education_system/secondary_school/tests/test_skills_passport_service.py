"""Tests for SkillsPassportService."""
import pytest
from education_system.secondary_school.modules.domain.student_life.skills_passport.services.skills_passport_service import SkillsPassportService


@pytest.fixture
def skills_passport_service(db_path):
    return SkillsPassportService(db_path)


class TestSkillsPassportCRUD:
    def test_create(self, skills_passport_service):
        r = skills_passport_service.create(student_id="SEC0001", skill_name="Public Speaking",
                                            category="communication", level="intermediate")
        assert r["student_id"] == "SEC0001"
        assert r["skill_name"] == "Public Speaking"
        assert r["category"] == "communication"
        assert r["level"] == "intermediate"

    def test_list_all(self, skills_passport_service):
        skills_passport_service.create(student_id="SEC0001", skill_name="Public Speaking")
        skills_passport_service.create(student_id="SEC0001", skill_name="Teamwork")
        result = skills_passport_service.list_all()
        assert len(result) >= 2

    def test_get(self, skills_passport_service):
        r = skills_passport_service.create(student_id="SEC0001", skill_name="Public Speaking",
                                            category="communication", level="intermediate")
        found = skills_passport_service.get(r["id"])
        assert found is not None
        assert found["student_id"] == "SEC0001"
        assert found["skill_name"] == "Public Speaking"

    def test_update(self, skills_passport_service):
        r = skills_passport_service.create(student_id="SEC0001", skill_name="Public Speaking",
                                            level="intermediate")
        updated = skills_passport_service.update(r["id"], level="advanced",
                                                  endorsed_by="Mrs Smith")
        assert updated["level"] == "advanced"
        assert updated["endorsed_by"] == "Mrs Smith"

    def test_delete(self, skills_passport_service):
        r = skills_passport_service.create(student_id="SEC0001", skill_name="Public Speaking")
        skills_passport_service.delete(r["id"])
        assert skills_passport_service.get(r["id"]) is None
