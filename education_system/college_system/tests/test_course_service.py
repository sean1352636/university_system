"""Tests for CourseService."""

import pytest
from education_system.college_system.core.exceptions import CourseError, ValidationError


class TestCourseService:
    def test_create_course(self, course_service):
        course = course_service.create_course(
            course_code="TEST901", title="Intro to CS",
            guided_learning_hours=3, capacity=30, subject_area="CS",
        )
        assert course["course_code"] == "TEST901"
        assert course["title"] == "Intro to CS"
        assert course["credits"] == 3
        assert course["status"] == "active"

    def test_create_duplicate_course(self, course_service, sample_course):
        with pytest.raises(CourseError, match="already exists"):
            course_service.create_course(course_code="TEST101", title="Duplicate")

    def test_create_course_validates_code(self, course_service):
        with pytest.raises(ValidationError):
            course_service.create_course(course_code="invalid", title="Test")

    def test_get_course_by_code(self, course_service, sample_course):
        found = course_service.get_course_by_code("TEST101")
        assert found is not None
        assert found["title"] == "Intro to Computer Science"

    def test_list_courses(self, course_service):
        course_service.create_course(course_code="TEST901", title="CS Intro")
        course_service.create_course(course_code="TEST902", title="Calculus")
        courses = course_service.list_courses()
        # +20 seeded courses
        assert len(courses) == 22

    def test_update_course(self, course_service, sample_course):
        updated = course_service.update_course(
            sample_course["id"], title="Updated CS Intro", capacity=50,
        )
        assert updated["title"] == "Updated CS Intro"
        assert updated["capacity"] == 50

    def test_delete_course(self, course_service, sample_course):
        result = course_service.delete_course(sample_course["id"])
        assert result is True
        course = course_service.get_course(sample_course["id"])
        assert course["status"] == "inactive"

    def test_add_prerequisite(self, course_service):
        c1 = course_service.create_course(course_code="TEST901", title="Intro")
        c2 = course_service.create_course(course_code="TEST902", title="Advanced")
        course_service.add_prerequisite(c2["id"], c1["id"])
        prereqs = course_service.get_prerequisites(c2["id"])
        assert len(prereqs) == 1
        assert prereqs[0]["course_code"] == "TEST901"

    def test_circular_prerequisite_detection(self, course_service):
        c1 = course_service.create_course(course_code="TEST901", title="Intro")
        c2 = course_service.create_course(course_code="TEST902", title="Advanced")
        course_service.add_prerequisite(c2["id"], c1["id"])
        with pytest.raises(CourseError, match="Circular"):
            course_service.add_prerequisite(c1["id"], c2["id"])

    def test_self_prerequisite(self, course_service, sample_course):
        with pytest.raises(CourseError, match="own prerequisite"):
            course_service.add_prerequisite(sample_course["id"], sample_course["id"])

    def test_count_courses(self, course_service, sample_course):
        # 20 seeded + 1 sample_course
        assert course_service.count_courses() == 21
