"""Tests for LMS CourseContentService."""
import pytest
import sqlite3


@pytest.fixture
def lms_db(tmp_path):
    db = str(tmp_path / "test_lms.db")
    conn = sqlite3.connect(db)
    from education_system.platform.features.lms.schema import create_lms_tables
    create_lms_tables(conn)
    conn.close()
    return db


@pytest.fixture
def course_id(lms_db):
    from education_system.platform.features.lms.course_management_service import CourseManagementService
    return CourseManagementService(lms_db).create_course("CS101", "inst1")


class TestModules:
    def test_create_and_list_modules(self, lms_db, course_id):
        from education_system.platform.features.lms.course_content_service import CourseContentService
        svc = CourseContentService(lms_db)
        m1 = svc.create_module(course_id, "Module 1", order_index=0)
        m2 = svc.create_module(course_id, "Module 2", order_index=1)
        modules = svc.list_modules(course_id)
        assert len(modules) == 2
        assert modules[0]["title"] == "Module 1"
        assert modules[1]["title"] == "Module 2"

    def test_publish_unpublish_module(self, lms_db, course_id):
        from education_system.platform.features.lms.course_content_service import CourseContentService
        svc = CourseContentService(lms_db)
        mid = svc.create_module(course_id, "Module 1")
        modules = svc.list_modules(course_id)
        assert modules[0]["published"] == 0
        svc.publish_module(mid)
        assert svc.list_modules(course_id)[0]["published"] == 1
        svc.unpublish_module(mid)
        assert svc.list_modules(course_id)[0]["published"] == 0


class TestLessons:
    def test_create_and_list_lessons(self, lms_db, course_id):
        from education_system.platform.features.lms.course_content_service import CourseContentService
        svc = CourseContentService(lms_db)
        mid = svc.create_module(course_id, "Module 1")
        svc.create_lesson(mid, "Lesson 1", content_type="text", content="Hello", order_index=0)
        svc.create_lesson(mid, "Lesson 2", content_type="video", order_index=1, duration_mins=30)
        lessons = svc.list_lessons(mid)
        assert len(lessons) == 2
        assert lessons[0]["title"] == "Lesson 1"

    def test_get_lesson(self, lms_db, course_id):
        from education_system.platform.features.lms.course_content_service import CourseContentService
        svc = CourseContentService(lms_db)
        mid = svc.create_module(course_id, "Module 1")
        lid = svc.create_lesson(mid, "Lesson 1", content="Some content")
        lesson = svc.get_lesson(lid)
        assert lesson["title"] == "Lesson 1"
        assert lesson["content"] == "Some content"

    def test_update_lesson(self, lms_db, course_id):
        from education_system.platform.features.lms.course_content_service import CourseContentService
        svc = CourseContentService(lms_db)
        mid = svc.create_module(course_id, "Module 1")
        lid = svc.create_lesson(mid, "Lesson 1", content="Old")
        svc.update_lesson(lid, content="New", title="Lesson 1 Updated")
        lesson = svc.get_lesson(lid)
        assert lesson["content"] == "New"
        assert lesson["title"] == "Lesson 1 Updated"

    def test_delete_lesson(self, lms_db, course_id):
        from education_system.platform.features.lms.course_content_service import CourseContentService
        svc = CourseContentService(lms_db)
        mid = svc.create_module(course_id, "Module 1")
        lid = svc.create_lesson(mid, "Lesson 1")
        svc.delete_lesson(lid)
        assert svc.get_lesson(lid) is None

    def test_reorder_lessons(self, lms_db, course_id):
        from education_system.platform.features.lms.course_content_service import CourseContentService
        svc = CourseContentService(lms_db)
        mid = svc.create_module(course_id, "Module 1")
        l1 = svc.create_lesson(mid, "Lesson A", order_index=0)
        l2 = svc.create_lesson(mid, "Lesson B", order_index=1)
        l3 = svc.create_lesson(mid, "Lesson C", order_index=2)
        svc.reorder_lessons(mid, [l3, l1, l2])
        lessons = svc.list_lessons(mid)
        assert lessons[0]["title"] == "Lesson C"
        assert lessons[1]["title"] == "Lesson A"
        assert lessons[2]["title"] == "Lesson B"
