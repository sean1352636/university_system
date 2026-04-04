"""Tests for LMS DiscussionService."""
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


@pytest.fixture
def course_id(lms_db):
    from education_system.shared.lms.course_management_service import CourseManagementService
    return CourseManagementService(lms_db).create_course("CS101", "inst1")


class TestForums:
    def test_create_and_list_forums(self, lms_db, course_id):
        from education_system.shared.lms.discussion_service import DiscussionService
        svc = DiscussionService(lms_db)
        svc.create_forum(course_id, "General Discussion", description="Talk about anything")
        svc.create_forum(course_id, "Announcements", is_pinned=True)
        forums = svc.list_forums(course_id)
        assert len(forums) == 2
        # Pinned forum should come first
        assert forums[0]["topic"] == "Announcements"
        assert forums[0]["is_pinned"] == 1

    def test_forum_with_created_by(self, lms_db, course_id):
        from education_system.shared.lms.discussion_service import DiscussionService
        svc = DiscussionService(lms_db)
        fid = svc.create_forum(course_id, "Q&A", created_by="inst1")
        forums = svc.list_forums(course_id)
        assert forums[0]["created_by"] == "inst1"


class TestPosts:
    def test_add_and_get_posts(self, lms_db, course_id):
        from education_system.shared.lms.discussion_service import DiscussionService
        svc = DiscussionService(lms_db)
        fid = svc.create_forum(course_id, "General")
        p1 = svc.add_post(fid, "stu1", "Hello everyone!")
        p2 = svc.add_post(fid, "stu2", "Welcome!")
        posts = svc.get_forum_posts(fid)
        assert len(posts) == 2
        assert posts[0]["content"] == "Hello everyone!"
        assert posts[0]["user_id"] == "stu1"

    def test_reply_to_post(self, lms_db, course_id):
        from education_system.shared.lms.discussion_service import DiscussionService
        svc = DiscussionService(lms_db)
        fid = svc.create_forum(course_id, "General")
        parent = svc.add_post(fid, "stu1", "Question about homework")
        reply = svc.add_post(fid, "inst1", "Here is the answer", parent_post_id=parent)
        posts = svc.get_forum_posts(fid)
        assert posts[1]["parent_post_id"] == parent

    def test_like_post(self, lms_db, course_id):
        from education_system.shared.lms.discussion_service import DiscussionService
        svc = DiscussionService(lms_db)
        fid = svc.create_forum(course_id, "General")
        pid = svc.add_post(fid, "stu1", "Great insight!")
        svc.like_post(pid)
        svc.like_post(pid)
        posts = svc.get_forum_posts(fid)
        assert posts[0]["likes_count"] == 2

    def test_empty_forum_posts(self, lms_db, course_id):
        from education_system.shared.lms.discussion_service import DiscussionService
        svc = DiscussionService(lms_db)
        fid = svc.create_forum(course_id, "Empty Forum")
        assert svc.get_forum_posts(fid) == []
