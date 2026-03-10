"""Staff Onboarding service layer."""

from datetime import datetime
from education_system.college_system.core.exceptions import OnboardingError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class OnboardingService:
    """Staff Onboarding management service.

    Manages onboarding checklists, tasks, and probation reviews
    for new staff members.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Checklists ──────────────────────────────────────────────

    def list_checklists(self, status: str | None = None) -> list[dict]:
        """List all onboarding checklists, optionally filtered by status."""
        conn = self._conn()
        try:
            sql = (
                "SELECT c.*, s.first_name || ' ' || s.last_name AS staff_name "
                "FROM onboarding_checklists c "
                "LEFT JOIN staff s ON c.staff_id = s.id "
                "WHERE 1=1"
            )
            params: list = []
            if status is not None:
                sql += " AND c.overall_status = ?"
                params.append(status)
            sql += " ORDER BY c.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_checklist(self, checklist_id: int) -> dict | None:
        """Get a single checklist by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT c.*, s.first_name || ' ' || s.last_name AS staff_name "
                "FROM onboarding_checklists c "
                "LEFT JOIN staff s ON c.staff_id = s.id "
                "WHERE c.id = ?",
                (checklist_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_checklist(self, staff_id: int, **kwargs) -> dict:
        """Create a new onboarding checklist for a staff member."""
        now = datetime.utcnow().isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO onboarding_checklists
                   (staff_id, start_date, mentor_id, probation_end_date,
                    probation_outcome, overall_status, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    staff_id,
                    kwargs.get("start_date", now[:10]),
                    kwargs.get("mentor_id"),
                    kwargs.get("probation_end_date"),
                    kwargs.get("probation_outcome"),
                    kwargs.get("overall_status", "in_progress"),
                    kwargs.get("notes"),
                    now,
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM onboarding_checklists WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Checklist created: id=%d staff_id=%d", row["id"], staff_id)
            return dict(row)
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to create checklist: {e}") from e
        finally:
            conn.close()

    def update_checklist(self, checklist_id: int, **kwargs) -> dict:
        """Update an existing checklist."""
        allowed = {
            "staff_id", "start_date", "mentor_id", "probation_end_date",
            "probation_outcome", "overall_status", "notes",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise OnboardingError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [checklist_id]
        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE onboarding_checklists SET {set_clause} WHERE id = ?", params
            )
            conn.commit()
            logger.info("Checklist updated: id=%d", checklist_id)
            row = conn.execute(
                "SELECT * FROM onboarding_checklists WHERE id = ?", (checklist_id,)
            ).fetchone()
            return dict(row) if row else {}
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to update checklist: {e}") from e
        finally:
            conn.close()

    def delete_checklist(self, checklist_id: int) -> bool:
        """Delete a checklist and cascade-delete its tasks and reviews."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM onboarding_checklists WHERE id = ?", (checklist_id,)
            ).fetchone()
            if not existing:
                raise OnboardingError("Checklist not found.")
            conn.execute(
                "DELETE FROM onboarding_tasks WHERE checklist_id = ?", (checklist_id,)
            )
            conn.execute(
                "DELETE FROM probation_reviews WHERE checklist_id = ?", (checklist_id,)
            )
            conn.execute(
                "DELETE FROM onboarding_checklists WHERE id = ?", (checklist_id,)
            )
            conn.commit()
            logger.info("Checklist deleted (cascade): id=%d", checklist_id)
            return True
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to delete checklist: {e}") from e
        finally:
            conn.close()

    def complete_checklist(self, checklist_id: int, outcome: str = "completed") -> dict:
        """Mark a checklist as completed with a given outcome."""
        if outcome not in ("completed", "extended", "failed"):
            raise OnboardingError(
                f"Invalid outcome '{outcome}'. Must be completed, extended, or failed."
            )
        conn = self._conn()
        try:
            now = datetime.utcnow().isoformat()
            conn.execute(
                "UPDATE onboarding_checklists SET overall_status = ?, "
                "probation_outcome = ?, updated_at = ? WHERE id = ?",
                (outcome, outcome, now, checklist_id),
            )
            conn.commit()
            logger.info("Checklist completed: id=%d outcome=%s", checklist_id, outcome)
            row = conn.execute(
                "SELECT * FROM onboarding_checklists WHERE id = ?", (checklist_id,)
            ).fetchone()
            return dict(row) if row else {}
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to complete checklist: {e}") from e
        finally:
            conn.close()

    # ── Tasks ───────────────────────────────────────────────────

    def list_tasks(
        self,
        checklist_id: int | None = None,
        category: str | None = None,
        completed: int | None = None,
    ) -> list[dict]:
        """List tasks with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM onboarding_tasks WHERE 1=1"
            params: list = []
            if checklist_id is not None:
                sql += " AND checklist_id = ?"
                params.append(checklist_id)
            if category is not None:
                sql += " AND category = ?"
                params.append(category)
            if completed is not None:
                sql += " AND completed = ?"
                params.append(completed)
            sql += " ORDER BY due_date ASC, id ASC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_task(self, task_id: int) -> dict | None:
        """Get a single task by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM onboarding_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_task(self, checklist_id: int, task_name: str, **kwargs) -> dict:
        """Create a new onboarding task."""
        if not task_name or not task_name.strip():
            raise OnboardingError("task_name is required.")
        now = datetime.utcnow().isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO onboarding_tasks
                   (checklist_id, task_name, category, assigned_to,
                    due_date, completed, completed_date, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    checklist_id,
                    task_name.strip(),
                    kwargs.get("category", "general"),
                    kwargs.get("assigned_to"),
                    kwargs.get("due_date"),
                    kwargs.get("completed", 0),
                    kwargs.get("completed_date"),
                    kwargs.get("notes"),
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM onboarding_tasks WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Task created: id=%d checklist=%d", row["id"], checklist_id)
            return dict(row)
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to create task: {e}") from e
        finally:
            conn.close()

    def update_task(self, task_id: int, **kwargs) -> dict:
        """Update an existing task."""
        allowed = {
            "checklist_id", "task_name", "category", "assigned_to",
            "due_date", "completed", "completed_date", "notes",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise OnboardingError("No valid fields to update.")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [task_id]
        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE onboarding_tasks SET {set_clause} WHERE id = ?", params
            )
            conn.commit()
            logger.info("Task updated: id=%d", task_id)
            row = conn.execute(
                "SELECT * FROM onboarding_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else {}
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to update task: {e}") from e
        finally:
            conn.close()

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM onboarding_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not existing:
                raise OnboardingError("Task not found.")
            conn.execute("DELETE FROM onboarding_tasks WHERE id = ?", (task_id,))
            conn.commit()
            logger.info("Task deleted: id=%d", task_id)
            return True
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to delete task: {e}") from e
        finally:
            conn.close()

    def complete_task(self, task_id: int) -> dict:
        """Mark a task as completed."""
        now = datetime.utcnow().isoformat()
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE onboarding_tasks SET completed = 1, completed_date = ? "
                "WHERE id = ?",
                (now, task_id),
            )
            conn.commit()
            logger.info("Task completed: id=%d", task_id)
            row = conn.execute(
                "SELECT * FROM onboarding_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to complete task: {e}") from e
        finally:
            conn.close()

    def get_pending_tasks(self) -> list[dict]:
        """Get all incomplete tasks across all checklists."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT t.*, c.staff_id, c.overall_status AS checklist_status "
                "FROM onboarding_tasks t "
                "JOIN onboarding_checklists c ON t.checklist_id = c.id "
                "WHERE t.completed = 0 "
                "ORDER BY t.due_date ASC, t.id ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Probation Reviews ───────────────────────────────────────

    def list_reviews(self, checklist_id: int | None = None) -> list[dict]:
        """List probation reviews, optionally filtered by checklist."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM probation_reviews WHERE 1=1"
            params: list = []
            if checklist_id is not None:
                sql += " AND checklist_id = ?"
                params.append(checklist_id)
            sql += " ORDER BY review_date DESC, id DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_review(self, review_id: int) -> dict | None:
        """Get a single review by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM probation_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_review(self, checklist_id: int, review_date: str, **kwargs) -> dict:
        """Create a new probation review."""
        if not review_date or not review_date.strip():
            raise OnboardingError("review_date is required.")
        now = datetime.utcnow().isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO probation_reviews
                   (checklist_id, review_date, reviewer_id, review_number,
                    performance_rating, areas_of_strength, areas_for_development,
                    targets, recommendation, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    checklist_id,
                    review_date.strip(),
                    kwargs.get("reviewer_id"),
                    kwargs.get("review_number", 1),
                    kwargs.get("performance_rating"),
                    kwargs.get("areas_of_strength"),
                    kwargs.get("areas_for_development"),
                    kwargs.get("targets"),
                    kwargs.get("recommendation", "continue"),
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM probation_reviews WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info(
                "Review created: id=%d checklist=%d", row["id"], checklist_id
            )
            return dict(row)
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to create review: {e}") from e
        finally:
            conn.close()

    def update_review(self, review_id: int, **kwargs) -> dict:
        """Update an existing probation review."""
        allowed = {
            "checklist_id", "review_date", "reviewer_id", "review_number",
            "performance_rating", "areas_of_strength", "areas_for_development",
            "targets", "recommendation",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise OnboardingError("No valid fields to update.")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [review_id]
        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE probation_reviews SET {set_clause} WHERE id = ?", params
            )
            conn.commit()
            logger.info("Review updated: id=%d", review_id)
            row = conn.execute(
                "SELECT * FROM probation_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            return dict(row) if row else {}
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to update review: {e}") from e
        finally:
            conn.close()

    def delete_review(self, review_id: int) -> bool:
        """Delete a probation review."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM probation_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            if not existing:
                raise OnboardingError("Review not found.")
            conn.execute("DELETE FROM probation_reviews WHERE id = ?", (review_id,))
            conn.commit()
            logger.info("Review deleted: id=%d", review_id)
            return True
        except OnboardingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise OnboardingError(f"Failed to delete review: {e}") from e
        finally:
            conn.close()

    # ── Statistics ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get aggregate onboarding statistics."""
        conn = self._conn()
        try:
            # Checklist counts
            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM onboarding_checklists"
            ).fetchone()["cnt"]
            in_progress = conn.execute(
                "SELECT COUNT(*) AS cnt FROM onboarding_checklists "
                "WHERE overall_status = 'in_progress'"
            ).fetchone()["cnt"]
            completed = conn.execute(
                "SELECT COUNT(*) AS cnt FROM onboarding_checklists "
                "WHERE overall_status = 'completed'"
            ).fetchone()["cnt"]
            failed = conn.execute(
                "SELECT COUNT(*) AS cnt FROM onboarding_checklists "
                "WHERE overall_status = 'failed'"
            ).fetchone()["cnt"]

            # Task counts
            total_tasks = conn.execute(
                "SELECT COUNT(*) AS cnt FROM onboarding_tasks"
            ).fetchone()["cnt"]
            tasks_completed = conn.execute(
                "SELECT COUNT(*) AS cnt FROM onboarding_tasks WHERE completed = 1"
            ).fetchone()["cnt"]
            tasks_pending = total_tasks - tasks_completed
            completion_rate = (
                round((tasks_completed / total_tasks) * 100, 1)
                if total_tasks > 0
                else 0.0
            )

            # Review counts
            total_reviews = conn.execute(
                "SELECT COUNT(*) AS cnt FROM probation_reviews"
            ).fetchone()["cnt"]

            # Reviews by recommendation
            rec_rows = conn.execute(
                "SELECT recommendation, COUNT(*) AS cnt FROM probation_reviews "
                "GROUP BY recommendation"
            ).fetchall()
            by_recommendation = {r["recommendation"]: r["cnt"] for r in rec_rows}

            return {
                "total_checklists": total,
                "in_progress": in_progress,
                "completed": completed,
                "failed": failed,
                "total_tasks": total_tasks,
                "tasks_completed": tasks_completed,
                "tasks_pending": tasks_pending,
                "completion_rate": completion_rate,
                "total_reviews": total_reviews,
                "by_recommendation": by_recommendation,
            }
        finally:
            conn.close()
