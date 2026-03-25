"""Tests for LessonPlanService."""

import pytest
from education_system.college_system.core.exceptions import LessonPlanError, ValidationError


class TestLessonPlanService:
    """Test suite for LessonPlanService."""

    def test_create_plan(self, lesson_plans_service):
        item = lesson_plans_service.create_plan(course_id=1, teacher_id=1, lesson_date="test_lesson_date", topic="test_topic")
        assert item["id"] is not None

    def test_get_plan(self, lesson_plans_service):
        item = lesson_plans_service.create_plan(course_id=1, teacher_id=1, lesson_date="test_lesson_date", topic="test_topic")
        found = lesson_plans_service.get_plan(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_plans(self, lesson_plans_service):
        lesson_plans_service.create_plan(course_id=1, teacher_id=1, lesson_date="test_lesson_date", topic="test_topic")
        items = lesson_plans_service.list_plans()
        assert len(items) >= 1

    def test_update_plan(self, lesson_plans_service):
        item = lesson_plans_service.create_plan(course_id=1, teacher_id=1, lesson_date="test_lesson_date", topic="test_topic")
        updated = lesson_plans_service.update_plan(item["id"], lesson_date="updated_value")
        assert updated["lesson_date"] == "updated_value"

    def test_delete_plan(self, lesson_plans_service):
        item = lesson_plans_service.create_plan(course_id=1, teacher_id=1, lesson_date="test_lesson_date", topic="test_topic")
        result = lesson_plans_service.delete_plan(item["id"])
        assert result is True
        assert lesson_plans_service.get_plan(item["id"]) is None

    def test_count_plans(self, lesson_plans_service):
        lesson_plans_service.create_plan(course_id=1, teacher_id=1, lesson_date="test_lesson_date", topic="test_topic")
        count = lesson_plans_service.count_plans()
        assert count >= 1

    def test_delete_nonexistent_raises(self, lesson_plans_service):
        with pytest.raises(LessonPlanError):
            lesson_plans_service.delete_plan(99999)
