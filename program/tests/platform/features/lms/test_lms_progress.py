"""Tests for LMS LearningProgressService."""
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
def course_with_lessons(lms_db):
    """Create a course with 2 modules and 3 lessons each (6 total)."""
    from education_system.platform.features.lms.course_management_service import CourseManagementService
    from education_system.platform.features.lms.course_content_service import CourseContentService
    cms = CourseManagementService(lms_db)
    ccs = CourseContentService(lms_db)
    cid = cms.create_course("CS101", "inst1")
    m1 = ccs.create_module(cid, "Module 1", order_index=0)
    m2 = ccs.create_module(cid, "Module 2", order_index=1)
    lessons = []
    for i in range(3):
        lessons.append(ccs.create_lesson(m1, f"M1 Lesson {i+1}", order_index=i))
    for i in range(3):
        lessons.append(ccs.create_lesson(m2, f"M2 Lesson {i+1}", order_index=i))
    return {"course_id": cid, "module1_id": m1, "module2_id": m2, "lesson_ids": lessons}


class TestMarkComplete:
    def test_mark_lesson_complete(self, lms_db, course_with_lessons):
        from education_system.platform.features.lms.learning_progress_service import LearningProgressService
        svc = LearningProgressService(lms_db)
        lid = course_with_lessons["lesson_ids"][0]
        svc.mark_lesson_complete("stu1", lid)
        progress = svc.get_student_progress("stu1", course_with_lessons["course_id"])
        assert progress["completed"] == 1
        assert progress["total"] == 6

    def test_mark_already_completed_is_idempotent(self, lms_db, course_with_lessons):
        from education_system.platform.features.lms.learning_progress_service import LearningProgressService
        svc = LearningProgressService(lms_db)
        lid = course_with_lessons["lesson_ids"][0]
        svc.mark_lesson_complete("stu1", lid)
        svc.mark_lesson_complete("stu1", lid)
        progress = svc.get_student_progress("stu1", course_with_lessons["course_id"])
        assert progress["completed"] == 1


class TestProgressTracking:
    def test_get_module_progress(self, lms_db, course_with_lessons):
        from education_system.platform.features.lms.learning_progress_service import LearningProgressService
        svc = LearningProgressService(lms_db)
        m1 = course_with_lessons["module1_id"]
        lessons = course_with_lessons["lesson_ids"]
        svc.mark_lesson_complete("stu1", lessons[0])
        svc.mark_lesson_complete("stu1", lessons[1])
        prog = svc.get_module_progress("stu1", m1)
        assert prog["completed"] == 2
        assert prog["total"] == 3
        assert prog["percentage"] == pytest.approx(66.7, abs=0.1)

    def test_get_next_lesson(self, lms_db, course_with_lessons):
        from education_system.platform.features.lms.learning_progress_service import LearningProgressService
        svc = LearningProgressService(lms_db)
        cid = course_with_lessons["course_id"]
        lessons = course_with_lessons["lesson_ids"]
        # Before any completion, next lesson should be the first
        nxt = svc.get_next_lesson("stu1", cid)
        assert nxt is not None
        assert nxt["id"] == lessons[0]
        # Complete first, next should be second
        svc.mark_lesson_complete("stu1", lessons[0])
        nxt = svc.get_next_lesson("stu1", cid)
        assert nxt["id"] == lessons[1]

    def test_all_complete_returns_none(self, lms_db, course_with_lessons):
        from education_system.platform.features.lms.learning_progress_service import LearningProgressService
        svc = LearningProgressService(lms_db)
        cid = course_with_lessons["course_id"]
        for lid in course_with_lessons["lesson_ids"]:
            svc.mark_lesson_complete("stu1", lid)
        assert svc.get_next_lesson("stu1", cid) is None

    def test_list_completed_lessons(self, lms_db, course_with_lessons):
        from education_system.platform.features.lms.learning_progress_service import LearningProgressService
        svc = LearningProgressService(lms_db)
        cid = course_with_lessons["course_id"]
        lessons = course_with_lessons["lesson_ids"]
        svc.mark_lesson_complete("stu1", lessons[0])
        svc.mark_lesson_complete("stu1", lessons[3])
        completed = svc.list_completed_lessons("stu1", cid)
        assert len(completed) == 2

    def test_course_completion_stats(self, lms_db, course_with_lessons):
        from education_system.platform.features.lms.learning_progress_service import LearningProgressService
        svc = LearningProgressService(lms_db)
        cid = course_with_lessons["course_id"]
        lessons = course_with_lessons["lesson_ids"]
        # Student 1 completes all
        for lid in lessons:
            svc.mark_lesson_complete("stu1", lid)
        # Student 2 completes half
        for lid in lessons[:3]:
            svc.mark_lesson_complete("stu2", lid)
        stats = svc.get_course_completion_stats(cid)
        assert stats["total_students"] == 2
        assert stats["fully_completed"] == 1
        assert stats["total_lessons"] == 6
        assert stats["avg_percentage"] == 75.0
