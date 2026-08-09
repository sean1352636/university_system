"""LMS discussion forum service."""
import sqlite3
import logging

logger = logging.getLogger(__name__)


class DiscussionService:
    def __init__(self, db_path):
        self._db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_forum(self, course_id, topic, description="", created_by="", is_pinned=False):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO lms_discussion_forums (lms_course_id, topic, description, created_by, is_pinned) VALUES (?, ?, ?, ?, ?)",
                (course_id, topic, description, created_by, 1 if is_pinned else 0))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_forums(self, course_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lms_discussion_forums WHERE lms_course_id = ? ORDER BY is_pinned DESC, created_at DESC",
                (course_id,)).fetchall()]
        finally:
            conn.close()

    def add_post(self, forum_id, user_id, content, parent_post_id=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO lms_discussion_posts (forum_id, user_id, content, parent_post_id) VALUES (?, ?, ?, ?)",
                (forum_id, user_id, content, parent_post_id))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_forum_posts(self, forum_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lms_discussion_posts WHERE forum_id = ? ORDER BY created_at ASC",
                (forum_id,)).fetchall()]
        finally:
            conn.close()

    def like_post(self, post_id):
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE lms_discussion_posts SET likes_count = likes_count + 1 WHERE post_id = ?",
                (post_id,))
            conn.commit()
        finally:
            conn.close()
