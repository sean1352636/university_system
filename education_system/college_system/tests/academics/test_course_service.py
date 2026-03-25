"""Tests for CourseService — additional edge cases and CRUD coverage."""

import pytest

from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.exceptions import CourseError, ValidationError


class TestCourseCRUD:
    @pytest.fixture
    def svc(self, db_path):
        return CourseService(db_path)

    def test_create_course(self, svc):
        course = svc.create_course(
            course_code="TEST901", title="Intro to CS",
            guided_learning_hours=3, capacity=30,
            subject_area="Computer Science",
        )
        assert course["course_code"] == "TEST901"
        assert course["title"] == "Intro to CS"
        assert course["status"] == "active"

    def test_create_duplicate_course_raises(self, svc, sample_course):
        with pytest.raises(CourseError, match="already exists"):
            svc.create_course(course_code="TEST101", title="Duplicate")

    def test_create_course_invalid_code_raises(self, svc):
        with pytest.raises(ValidationError):
            svc.create_course(course_code="invalid", title="Bad Code")

    def test_get_course(self, svc, sample_course):
        found = svc.get_course(sample_course["id"])
        assert found is not None
        assert found["course_code"] == "TEST101"

    def test_get_course_not_found(self, svc):
        result = svc.get_course(99999)
        assert result is None

    def test_get_course_by_code(self, svc, sample_course):
        found = svc.get_course_by_code("TEST101")
        assert found is not None
        assert found["title"] == "Intro to Computer Science"

    def test_get_course_by_code_not_found(self, svc):
        result = svc.get_course_by_code("NONEXIST999")
        assert result is None

    def test_list_courses(self, svc):
        svc.create_course(course_code="TEST901", title="CS Intro")
        svc.create_course(course_code="TEST902", title="Calculus")
        courses = svc.list_courses()
        assert len(courses) >= 2

    def test_list_courses_search(self, svc):
        svc.create_course(course_code="UNIQ901", title="Unique Subject XYZ")
        results = svc.list_courses(search="Unique Subject")
        assert len(results) >= 1

    def test_list_courses_filter_status(self, svc, sample_course):
        active = svc.list_courses(status="active")
        assert all(c["status"] == "active" for c in active)

    def test_update_course(self, svc, sample_course):
        updated = svc.update_course(
            sample_course["id"], title="Updated CS", capacity=50,
        )
        assert updated["title"] == "Updated CS"
        assert updated["capacity"] == 50

    def test_update_course_no_valid_fields(self, svc, sample_course):
        with pytest.raises(ValidationError, match="No valid fields"):
            svc.update_course(sample_course["id"], bad_field="nope")

    def test_delete_course(self, svc, sample_course):
        result = svc.delete_course(sample_course["id"])
        assert result is True
        deleted = svc.get_course(sample_course["id"])
        assert deleted is None

    def test_delete_course_not_found(self, svc):
        with pytest.raises(CourseError, match="not found"):
            svc.delete_course(99999)

    def test_count_courses(self, svc, sample_course):
        count = svc.count_courses()
        assert count >= 1

    def test_get_enrollment_count_empty(self, svc, sample_course):
        assert svc.get_enrollment_count(sample_course["id"]) == 0

    def test_get_enrollment_count(self, svc, sample_course, sample_student,
                                   enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        assert svc.get_enrollment_count(sample_course["id"]) == 1

    def test_get_roster(self, svc, sample_course, sample_student, enrollment_service):
        enrollment_service.enroll_student(sample_student["id"], sample_course["id"])
        roster = svc.get_roster(sample_course["id"])
        assert len(roster) == 1
        assert roster[0]["first_name"] == "John"

    def test_get_roster_empty(self, svc, sample_course):
        roster = svc.get_roster(sample_course["id"])
        assert roster == []


class TestCoursePrerequisites:
    @pytest.fixture
    def svc(self, db_path):
        return CourseService(db_path)

    def test_add_prerequisite(self, svc):
        c1 = svc.create_course(course_code="TEST901", title="Intro")
        c2 = svc.create_course(course_code="TEST902", title="Advanced")
        svc.add_prerequisite(c2["id"], c1["id"])
        prereqs = svc.get_prerequisites(c2["id"])
        assert len(prereqs) == 1
        assert prereqs[0]["course_code"] == "TEST901"

    def test_self_prerequisite_raises(self, svc, sample_course):
        with pytest.raises(CourseError, match="own prerequisite"):
            svc.add_prerequisite(sample_course["id"], sample_course["id"])

    def test_circular_prerequisite_raises(self, svc):
        c1 = svc.create_course(course_code="TEST901", title="A")
        c2 = svc.create_course(course_code="TEST902", title="B")
        svc.add_prerequisite(c2["id"], c1["id"])
        with pytest.raises(CourseError, match="Circular"):
            svc.add_prerequisite(c1["id"], c2["id"])

    def test_remove_prerequisite(self, svc):
        c1 = svc.create_course(course_code="TEST901", title="Intro")
        c2 = svc.create_course(course_code="TEST902", title="Advanced")
        svc.add_prerequisite(c2["id"], c1["id"])
        svc.remove_prerequisite(c2["id"], c1["id"])
        prereqs = svc.get_prerequisites(c2["id"])
        assert len(prereqs) == 0

    def test_multiple_prerequisites(self, svc):
        c1 = svc.create_course(course_code="TEST901", title="Prereq 1")
        c2 = svc.create_course(course_code="TEST902", title="Prereq 2")
        c3 = svc.create_course(course_code="TEST903", title="Advanced")
        svc.add_prerequisite(c3["id"], c1["id"])
        svc.add_prerequisite(c3["id"], c2["id"])
        prereqs = svc.get_prerequisites(c3["id"])
        assert len(prereqs) == 2
