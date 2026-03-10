"""Discussion Forums service."""

from datetime import datetime

from education_system.college_system.core.exceptions import ForumError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)

_THREAD_STATUSES = ("open", "closed", "resolved")


class ForumService:
    """Service for managing discussion forum categories, threads and posts."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Categories ──────────────────────────────────────────────────────

    def create_category(self, name: str, description: str = "",
                        sort_order: int = 0) -> dict:
        """Create a new forum category."""
        if not name or not name.strip():
            raise ForumError("Category name is required.")
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO forum_categories (name, description, sort_order)
                   VALUES (?, ?, ?)""",
                (name.strip(), description.strip(), sort_order),
            )
            conn.commit()
            cat_id = cursor.lastrowid
            logger.info("Forum category created: id=%d name=%s", cat_id, name)
            return self.get_category(cat_id)
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to create category: {e}") from e
        finally:
            conn.close()

    def list_categories(self, active_only: bool = False) -> list[dict]:
        """List all forum categories ordered by sort_order."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM forum_categories"
            params: list = []
            if active_only:
                sql += " WHERE is_active = 1"
            sql += " ORDER BY sort_order, name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_category(self, category_id: int) -> dict | None:
        """Get a single category by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM forum_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_category(self, category_id: int, **kwargs) -> dict:
        """Update category name, description, sort_order, or is_active."""
        allowed = {"name", "description", "sort_order", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ForumError("No valid fields to update.")
        if "name" in updates and not str(updates["name"]).strip():
            raise ForumError("Category name cannot be empty.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [category_id]
            conn.execute(
                f"UPDATE forum_categories SET {sets} WHERE id = ?", vals,
            )
            conn.commit()
            logger.info("Forum category updated: id=%d", category_id)
            return self.get_category(category_id)
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to update category: {e}") from e
        finally:
            conn.close()

    def delete_category(self, category_id: int) -> bool:
        """Delete a category (only if it has no threads)."""
        conn = self._conn()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM forum_threads WHERE category_id = ?",
                (category_id,),
            ).fetchone()[0]
            if count > 0:
                raise ForumError(
                    f"Cannot delete category: {count} thread(s) still exist. "
                    "Delete or move threads first."
                )
            conn.execute("DELETE FROM forum_categories WHERE id = ?", (category_id,))
            conn.commit()
            logger.info("Forum category deleted: id=%d", category_id)
            return True
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to delete category: {e}") from e
        finally:
            conn.close()

    # ── Threads ─────────────────────────────────────────────────────────

    def create_thread(self, category_id: int, title: str,
                      author_id: int) -> dict:
        """Create a new discussion thread."""
        if not title or not title.strip():
            raise ForumError("Thread title is required.")
        conn = self._conn()
        try:
            cat = conn.execute(
                "SELECT id FROM forum_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
            if not cat:
                raise ForumError("Category not found.")
            cursor = conn.execute(
                """INSERT INTO forum_threads
                   (category_id, title, author_id)
                   VALUES (?, ?, ?)""",
                (category_id, title.strip(), author_id),
            )
            conn.commit()
            thread_id = cursor.lastrowid
            logger.info("Forum thread created: id=%d title=%s", thread_id, title)
            return self.get_thread(thread_id)
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to create thread: {e}") from e
        finally:
            conn.close()

    def list_threads(self, category_id: int | None = None,
                     status: str | None = None,
                     search: str | None = None,
                     limit: int = 100) -> list[dict]:
        """List threads with optional filters, joined with user names."""
        conn = self._conn()
        try:
            conditions: list[str] = []
            params: list = []

            if category_id is not None:
                conditions.append("t.category_id = ?")
                params.append(category_id)
            if status:
                conditions.append("t.status = ?")
                params.append(status)
            if search:
                conditions.append("t.title LIKE ?")
                params.append(f"%{search}%")

            sql = """SELECT t.*, u.username AS author_name,
                            c.name AS category_name
                     FROM forum_threads t
                     JOIN users u ON t.author_id = u.id
                     JOIN forum_categories c ON t.category_id = c.id"""
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY t.is_pinned DESC, t.created_at DESC LIMIT ?"
            params.append(limit)

            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_thread(self, thread_id: int) -> dict | None:
        """Get a single thread with author name."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT t.*, u.username AS author_name,
                          c.name AS category_name
                   FROM forum_threads t
                   JOIN users u ON t.author_id = u.id
                   JOIN forum_categories c ON t.category_id = c.id
                   WHERE t.id = ?""",
                (thread_id,),
            ).fetchone()
            if not row:
                return None
            # Increment view count
            conn.execute(
                "UPDATE forum_threads SET view_count = view_count + 1 WHERE id = ?",
                (thread_id,),
            )
            conn.commit()
            return dict(row)
        finally:
            conn.close()

    def update_thread(self, thread_id: int, **kwargs) -> dict:
        """Update thread title or status."""
        allowed = {"title", "status", "category_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ForumError("No valid fields to update.")
        if "title" in updates and not str(updates["title"]).strip():
            raise ForumError("Thread title cannot be empty.")
        if "status" in updates and updates["status"] not in _THREAD_STATUSES:
            raise ForumError(
                f"Status must be one of: {', '.join(_THREAD_STATUSES)}"
            )
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [thread_id]
            conn.execute(
                f"UPDATE forum_threads SET {sets} WHERE id = ?", vals,
            )
            conn.commit()
            logger.info("Forum thread updated: id=%d", thread_id)
            return self.get_thread(thread_id)
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to update thread: {e}") from e
        finally:
            conn.close()

    def delete_thread(self, thread_id: int) -> bool:
        """Delete a thread and cascade-delete its posts."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM forum_posts WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM forum_threads WHERE id = ?", (thread_id,))
            conn.commit()
            logger.info("Forum thread deleted (cascade): id=%d", thread_id)
            return True
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to delete thread: {e}") from e
        finally:
            conn.close()

    def pin_thread(self, thread_id: int, pinned: bool = True) -> dict:
        """Pin or unpin a thread."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE forum_threads SET is_pinned = ? WHERE id = ?",
                (1 if pinned else 0, thread_id),
            )
            conn.commit()
            logger.info("Forum thread %s: id=%d",
                        "pinned" if pinned else "unpinned", thread_id)
            return self.get_thread(thread_id)
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to pin/unpin thread: {e}") from e
        finally:
            conn.close()

    def lock_thread(self, thread_id: int, locked: bool = True) -> dict:
        """Lock or unlock a thread."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE forum_threads SET is_locked = ? WHERE id = ?",
                (1 if locked else 0, thread_id),
            )
            conn.commit()
            logger.info("Forum thread %s: id=%d",
                        "locked" if locked else "unlocked", thread_id)
            return self.get_thread(thread_id)
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to lock/unlock thread: {e}") from e
        finally:
            conn.close()

    # ── Posts ───────────────────────────────────────────────────────────

    def create_post(self, thread_id: int, author_id: int,
                    content: str) -> dict:
        """Create a new post in a thread. Updates reply_count and last_reply_at."""
        if not content or not content.strip():
            raise ForumError("Post content is required.")
        conn = self._conn()
        try:
            thread = conn.execute(
                "SELECT id, is_locked FROM forum_threads WHERE id = ?",
                (thread_id,),
            ).fetchone()
            if not thread:
                raise ForumError("Thread not found.")
            if thread["is_locked"]:
                raise ForumError("Thread is locked. No new posts allowed.")

            now = datetime.now().isoformat()
            cursor = conn.execute(
                """INSERT INTO forum_posts (thread_id, author_id, content)
                   VALUES (?, ?, ?)""",
                (thread_id, author_id, content.strip()),
            )
            post_id = cursor.lastrowid

            # Update thread metadata
            conn.execute(
                """UPDATE forum_threads
                   SET reply_count = reply_count + 1, last_reply_at = ?
                   WHERE id = ?""",
                (now, thread_id),
            )
            conn.commit()
            logger.info("Forum post created: id=%d thread=%d", post_id, thread_id)

            row = conn.execute(
                """SELECT p.*, u.username AS author_name
                   FROM forum_posts p
                   JOIN users u ON p.author_id = u.id
                   WHERE p.id = ?""",
                (post_id,),
            ).fetchone()
            return dict(row) if row else {"id": post_id}
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to create post: {e}") from e
        finally:
            conn.close()

    def list_posts(self, thread_id: int) -> list[dict]:
        """List all posts in a thread with author names."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT p.*, u.username AS author_name
                   FROM forum_posts p
                   JOIN users u ON p.author_id = u.id
                   WHERE p.thread_id = ?
                   ORDER BY p.created_at""",
                (thread_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_post(self, post_id: int, content: str) -> dict:
        """Update post content and set edited_at timestamp."""
        if not content or not content.strip():
            raise ForumError("Post content is required.")
        conn = self._conn()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE forum_posts SET content = ?, edited_at = ? WHERE id = ?",
                (content.strip(), now, post_id),
            )
            conn.commit()
            logger.info("Forum post updated: id=%d", post_id)
            row = conn.execute(
                """SELECT p.*, u.username AS author_name
                   FROM forum_posts p
                   JOIN users u ON p.author_id = u.id
                   WHERE p.id = ?""",
                (post_id,),
            ).fetchone()
            return dict(row) if row else {}
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to update post: {e}") from e
        finally:
            conn.close()

    def delete_post(self, post_id: int) -> bool:
        """Delete a post and decrement the thread reply_count."""
        conn = self._conn()
        try:
            post = conn.execute(
                "SELECT thread_id FROM forum_posts WHERE id = ?", (post_id,),
            ).fetchone()
            if not post:
                raise ForumError("Post not found.")
            thread_id = post["thread_id"]

            conn.execute("DELETE FROM forum_posts WHERE id = ?", (post_id,))
            conn.execute(
                """UPDATE forum_threads
                   SET reply_count = MAX(reply_count - 1, 0)
                   WHERE id = ?""",
                (thread_id,),
            )
            conn.commit()
            logger.info("Forum post deleted: id=%d", post_id)
            return True
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to delete post: {e}") from e
        finally:
            conn.close()

    def mark_solution(self, post_id: int, is_solution: bool = True) -> dict:
        """Mark or unmark a post as the solution."""
        conn = self._conn()
        try:
            post = conn.execute(
                "SELECT thread_id FROM forum_posts WHERE id = ?", (post_id,),
            ).fetchone()
            if not post:
                raise ForumError("Post not found.")

            if is_solution:
                # Clear any existing solution in the same thread
                conn.execute(
                    "UPDATE forum_posts SET is_solution = 0 WHERE thread_id = ?",
                    (post["thread_id"],),
                )
            conn.execute(
                "UPDATE forum_posts SET is_solution = ? WHERE id = ?",
                (1 if is_solution else 0, post_id),
            )
            conn.commit()
            logger.info("Forum post %s as solution: id=%d",
                        "marked" if is_solution else "unmarked", post_id)

            row = conn.execute(
                """SELECT p.*, u.username AS author_name
                   FROM forum_posts p
                   JOIN users u ON p.author_id = u.id
                   WHERE p.id = ?""",
                (post_id,),
            ).fetchone()
            return dict(row) if row else {}
        except ForumError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ForumError(f"Failed to mark solution: {e}") from e
        finally:
            conn.close()

    # ── Statistics ──────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get forum statistics."""
        conn = self._conn()
        try:
            total_categories = conn.execute(
                "SELECT COUNT(*) FROM forum_categories"
            ).fetchone()[0]
            total_threads = conn.execute(
                "SELECT COUNT(*) FROM forum_threads"
            ).fetchone()[0]
            total_posts = conn.execute(
                "SELECT COUNT(*) FROM forum_posts"
            ).fetchone()[0]
            active_threads = conn.execute(
                "SELECT COUNT(*) FROM forum_threads WHERE status = 'open'"
            ).fetchone()[0]
            return {
                "total_categories": total_categories,
                "total_threads": total_threads,
                "total_posts": total_posts,
                "active_threads": active_threads,
            }
        finally:
            conn.close()
