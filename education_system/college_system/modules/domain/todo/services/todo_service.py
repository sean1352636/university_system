"""To-Do list management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import TodoError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class TodoService:
    """Service for managing to-do items."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_item(self, user_id: int, title: str, description: str | None = None,
                    priority: str = "medium", due_date: str | None = None) -> dict:
        """Create a new to-do item."""
        if not title or not title.strip():
            raise TodoError("Title is required.")
        if priority not in ("low", "medium", "high"):
            raise TodoError("Priority must be low, medium or high.")

        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO todo_items (user_id, title, description, priority, due_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, title.strip(), description, priority, due_date),
            )
            conn.commit()
            item_id = cursor.lastrowid
            logger.info("Todo item created: id=%d user=%d", item_id, user_id)
            return self.get_item(item_id, user_id)
        except TodoError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TodoError(f"Failed to create item: {e}") from e
        finally:
            conn.close()

    def list_items(self, user_id: int, show_completed: bool = False) -> list[dict]:
        """List to-do items for a user."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM todo_items WHERE user_id = ?"
            params: list = [user_id]
            if not show_completed:
                sql += " AND is_completed = 0"
            sql += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_item(self, item_id: int, user_id: int) -> dict:
        """Get a single to-do item (verify ownership)."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM todo_items WHERE id = ? AND user_id = ?",
                (item_id, user_id),
            ).fetchone()
            if not row:
                raise TodoError("Item not found.")
            return dict(row)
        finally:
            conn.close()

    def update_item(self, item_id: int, user_id: int, **kwargs) -> dict:
        """Update a to-do item."""
        set_parts: list[str] = []
        vals: list = []
        for col in ("description", "due_date", "priority", "title"):
            if col in kwargs and kwargs[col] is not None:
                set_parts.append(f"{col} = ?")
                vals.append(kwargs[col])
        if not set_parts:
            raise TodoError("No valid fields to update.")
        if "priority" in kwargs and kwargs["priority"] not in ("low", "medium", "high"):
            raise TodoError("Priority must be low, medium or high.")

        # Verify ownership
        self.get_item(item_id, user_id)

        conn = self._conn()
        try:
            sets = ", ".join(set_parts)
            vals.extend([datetime.now().isoformat(), item_id, user_id])
            conn.execute(
                f"UPDATE todo_items SET {sets}, updated_at = ? WHERE id = ? AND user_id = ?",
                vals,
            )
            conn.commit()
            logger.info("Todo item updated: id=%d", item_id)
            return self.get_item(item_id, user_id)
        except TodoError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TodoError(f"Failed to update item: {e}") from e
        finally:
            conn.close()

    def toggle_complete(self, item_id: int, user_id: int) -> dict:
        """Toggle the completed status of an item."""
        item = self.get_item(item_id, user_id)
        new_status = 0 if item["is_completed"] else 1

        conn = self._conn()
        try:
            conn.execute(
                "UPDATE todo_items SET is_completed = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (new_status, datetime.now().isoformat(), item_id, user_id),
            )
            conn.commit()
            return self.get_item(item_id, user_id)
        except Exception as e:
            conn.rollback()
            raise TodoError(f"Failed to toggle item: {e}") from e
        finally:
            conn.close()

    def delete_item(self, item_id: int, user_id: int) -> bool:
        """Delete a to-do item (verify ownership)."""
        self.get_item(item_id, user_id)

        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM todo_items WHERE id = ? AND user_id = ?",
                (item_id, user_id),
            )
            conn.commit()
            logger.info("Todo item deleted: id=%d", item_id)
            return True
        except Exception as e:
            conn.rollback()
            raise TodoError(f"Failed to delete item: {e}") from e
        finally:
            conn.close()
