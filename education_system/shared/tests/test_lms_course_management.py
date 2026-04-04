"""Tests for LMS CourseManagementService."""
import pytest
import sqlite3


@pytest.fixture
def lms_db(tmp_path):
    db = str(tmp_path / "test_lms.db")
    conn = sqlite3.connect(db)
    from education_system.shared.lms.schema import create_lms_tables
    create_lms_tables(conn)
    conn.close()
    return db


class TestCourseLifecycle:
    def test_create_course(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        cid = svc.create_course("CS101", "inst1", description="Intro to CS",
                                start_date="2026-09-01", end_date="2026-12-20",
                                enrollment_limit=30)
        assert cid is not None
        details = svc.get_course_details(cid)
        assert details["module_code"] == "CS101"
        assert details["instructor_id"] == "inst1"
        assert details["enrollment_limit"] == 30

    def test_publish_course(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        cid = svc.create_course("CS102", "inst1")
        details = svc.get_course_details(cid)
        assert details["is_published"] == 0
        svc.publish_course(cid)
        details = svc.get_course_details(cid)
        assert details["is_published"] == 1

    def test_list_all_courses(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        svc.create_course("CS101", "inst1")
        svc.create_course("CS102", "inst2")
        courses = svc.list_all_courses()
        assert len(courses) == 2

    def test_get_instructor_courses(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        svc.create_course("CS101", "inst1")
        svc.create_course("CS102", "inst1")
        svc.create_course("CS103", "inst2")
        assert len(svc.get_instructor_courses("inst1")) == 2
        assert len(svc.get_instructor_courses("inst2")) == 1


class TestCourseContent:
    def test_add_and_get_content(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        cid = svc.create_course("CS101", "inst1")
        c1 = svc.add_content(cid, "lecture", "Week 1", content_order=1)
        c2 = svc.add_content(cid, "lab", "Lab 1", content_order=2)
        assert c1 is not None
        content = svc.get_course_content(cid)
        assert len(content) == 2
        assert content[0]["title"] == "Week 1"

    def test_add_video_lecture(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        cid = svc.create_course("CS101", "inst1")
        content_id = svc.add_content(cid, "video", "Lecture 1")
        vid = svc.add_video_lecture(content_id, "https://example.com/v1.mp4",
                                    duration_minutes=45, video_quality="1080p")
        assert vid is not None


class TestEnrollment:
    def test_enrol_and_get_enrolled(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        cid = svc.create_course("CS101", "inst1")
        svc.enrol_student(cid, "stu1")
        enrolled = svc.get_enrolled_courses("stu1")
        assert len(enrolled) == 1
        assert enrolled[0]["module_code"] == "CS101"

    def test_get_available_courses(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        c1 = svc.create_course("CS101", "inst1")
        c2 = svc.create_course("CS102", "inst1")
        svc.publish_course(c1)
        svc.publish_course(c2)
        svc.enrol_student(c1, "stu1")
        available = svc.get_available_courses("stu1")
        assert len(available) == 1
        assert available[0]["module_code"] == "CS102"

    def test_get_course_details_nonexistent(self, lms_db):
        from education_system.shared.lms.course_management_service import CourseManagementService
        svc = CourseManagementService(lms_db)
        assert svc.get_course_details(9999) is None
