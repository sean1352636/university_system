"""Homework management service for the Primary School Management System."""

import logging
from datetime import date as date_type
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import HomeworkError
import traceback

logger = logging.getLogger(__name__)


class HomeworkService:
    """CRUD operations for homework and submissions."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_homework(self, title, class_name, due_date, subject_code=None,
                        description=None, set_by=None):
        if not title or not title.strip():
            raise HomeworkError("Title is required")
        if not class_name:
            raise HomeworkError("Class name is required")
        if not due_date:
            raise HomeworkError("Due date is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO homework (
                    title, class_name, due_date, subject_code, description,
                    set_by, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'Active')""",
                (title.strip(), class_name, due_date, subject_code,
                 description, set_by),
            )
            conn.commit()
            homework_id = cursor.lastrowid
            logger.info("Created homework %d: %s for %s", homework_id, title,
                        class_name)
            return {"homework_id": homework_id, "title": title,
                    "class_name": class_name, "due_date": due_date}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HomeworkError(f"Failed to create homework: {e}") from e
        finally:
            conn.close()

    def list_homework(self, class_name=None, subject_code=None,
                      status="Active"):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM homework WHERE 1=1"
            params = []
            if class_name is not None:
                sql += " AND class_name = ?"
                params.append(class_name)
            if subject_code is not None:
                sql += " AND subject_code = ?"
                params.append(subject_code)
            if status is not None:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY due_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_homework(self, homework_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM homework WHERE id = ?",
                           (homework_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_homework(self, homework_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"title", "class_name", "due_date", "subject_code",
                       "description", "set_by", "status"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(homework_id)
            cursor.execute(
                f"UPDATE homework SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            logger.info("Updated homework: %d", homework_id)
            return self.get_homework(homework_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HomeworkError(f"Failed to update homework: {e}") from e
        finally:
            conn.close()

    def delete_homework(self, homework_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM homework_submissions WHERE homework_id = ?",
                (homework_id,),
            )
            cursor.execute("DELETE FROM homework WHERE id = ?", (homework_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted homework: %d", homework_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HomeworkError(f"Failed to delete homework: {e}") from e
        finally:
            conn.close()

    def record_submission(self, homework_id, pupil_id, submitted_date=None,
                          status="Submitted"):
        if not homework_id:
            raise HomeworkError("Homework ID is required")
        if not pupil_id:
            raise HomeworkError("Pupil ID is required")

        if submitted_date is None:
            submitted_date = str(date_type.today())

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO homework_submissions (
                    homework_id, pupil_id, submitted_date, status
                ) VALUES (?, ?, ?, ?)""",
                (homework_id, pupil_id, submitted_date, status),
            )
            conn.commit()
            submission_id = cursor.lastrowid
            logger.info("Recorded submission %d: homework %d by pupil %s",
                        submission_id, homework_id, pupil_id)
            return {"submission_id": submission_id, "homework_id": homework_id,
                    "pupil_id": pupil_id, "status": status}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HomeworkError(f"Failed to record submission: {e}") from e
        finally:
            conn.close()

    def get_submissions(self, homework_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT hs.*, p.first_name, p.last_name
                   FROM homework_submissions hs
                   JOIN pupils p ON hs.pupil_id = p.pupil_id
                   WHERE hs.homework_id = ?
                   ORDER BY p.last_name, p.first_name""",
                (homework_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
