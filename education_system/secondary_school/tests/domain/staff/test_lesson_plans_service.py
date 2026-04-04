"""Tests for LessonPlansService."""
import pytest
from education_system.secondary_school.modules.domain.staff.lesson_plans.services.lesson_plans_service import LessonPlansService


@pytest.fixture
def lesson_plans_service(db_path):
    return LessonPlansService(db_path)


class TestLessonPlansCRUD:
    def test_create(self, lesson_plans_service):
        rid = lesson_plans_service.create(
            teacher_id="STF001", subject="Maths", class_name="9A",
            lesson_date="2026-03-25", topic="Quadratic Equations",
            objectives="Solve quadratics",
        )
        assert isinstance(rid, int)
        record = lesson_plans_service.get(rid)
        assert record["teacher_id"] == "STF001"
        assert record["subject"] == "Maths"
        assert record["class_name"] == "9A"
        assert record["topic"] == "Quadratic Equations"
        assert record["objectives"] == "Solve quadratics"
        assert record["shared"] == 0

    def test_list_all(self, lesson_plans_service):
        lesson_plans_service.create(teacher_id="STF001", topic="Algebra")
        lesson_plans_service.create(teacher_id="STF002", topic="Geometry")
        result = lesson_plans_service.list_all()
        assert len(result) >= 2

    def test_get(self, lesson_plans_service):
        rid = lesson_plans_service.create(
            teacher_id="STF003", topic="Trigonometry",
        )
        found = lesson_plans_service.get(rid)
        assert found is not None
        assert found["topic"] == "Trigonometry"

    def test_update(self, lesson_plans_service):
        rid = lesson_plans_service.create(
            teacher_id="STF001", topic="Algebra basics",
        )
        lesson_plans_service.update(rid, shared=1, activities="Worksheet + group work")
        updated = lesson_plans_service.get(rid)
        assert updated["shared"] == 1
        assert updated["activities"] == "Worksheet + group work"

    def test_delete(self, lesson_plans_service):
        rid = lesson_plans_service.create(
            teacher_id="STF004", topic="Temp lesson",
        )
        lesson_plans_service.delete(rid)
        assert lesson_plans_service.get(rid) is None
