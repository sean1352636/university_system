"""Homework management service for the Primary School Management System."""

import logging
from datetime import date as date_type
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import HomeworkError
from education_system.primary_school.core.sql_safety import validate_identifier
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

            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
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
            # Clean up feedback linked to submissions for this homework
            cursor.execute(
                """DELETE FROM homework_feedback WHERE submission_id IN
                   (SELECT id FROM homework_submissions WHERE homework_id = ?)""",
                (homework_id,),
            )
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

    # ---- Teacher feedback with stickers ----

    VALID_STICKERS = ("gold_star", "well_done", "good_effort", "keep_trying")

    def add_teacher_feedback(self, submission_id, feedback, sticker=None):
        """Add teacher feedback and an optional sticker to a submission.

        Args:
            submission_id: ID of the homework submission.
            feedback: Teacher's written feedback text.
            sticker: Optional motivational sticker - one of
                     gold_star, well_done, good_effort, keep_trying.
        Returns:
            dict with the feedback record.
        """
        if not feedback or not str(feedback).strip():
            raise HomeworkError("Feedback text is required")
        if sticker and sticker not in self.VALID_STICKERS:
            raise HomeworkError(
                f"Invalid sticker. Choose from: {', '.join(self.VALID_STICKERS)}")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            sub = cursor.execute(
                "SELECT id FROM homework_submissions WHERE id = ?",
                (submission_id,)).fetchone()
            if not sub:
                raise HomeworkError("Submission not found")

            # Check for existing feedback row to update
            existing = cursor.execute(
                "SELECT id FROM homework_feedback WHERE submission_id = ? AND teacher_feedback IS NOT NULL",
                (submission_id,)).fetchone()
            if existing:
                cursor.execute(
                    "UPDATE homework_feedback SET teacher_feedback = ?, sticker = ? WHERE id = ?",
                    (str(feedback).strip(), sticker, existing["id"]))
            else:
                cursor.execute(
                    """INSERT INTO homework_feedback
                       (submission_id, teacher_feedback, sticker)
                       VALUES (?, ?, ?)""",
                    (submission_id, str(feedback).strip(), sticker))

            # Also mark the submission as 'Marked'
            cursor.execute(
                "UPDATE homework_submissions SET status = 'Marked' WHERE id = ?",
                (submission_id,))
            conn.commit()
            fb_id = existing["id"] if existing else cursor.lastrowid
            row = cursor.execute(
                "SELECT * FROM homework_feedback WHERE id = ?",
                (fb_id,)).fetchone()
            logger.info("Teacher feedback added for submission %d", submission_id)
            return dict(row)
        except HomeworkError:
            conn.rollback()
            raise
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HomeworkError(f"Failed to add feedback: {e}") from e
        finally:
            conn.close()

    # ---- Parent comments ----

    def add_parent_comment(self, submission_id, comment, parent_id):
        """Add a parent comment to a homework submission.

        Args:
            submission_id: ID of the homework submission.
            comment: The parent's comment text.
            parent_id: Identifier of the parent leaving the comment.
        Returns:
            dict with the feedback record.
        """
        if not comment or not str(comment).strip():
            raise HomeworkError("Comment text is required")
        if not parent_id:
            raise HomeworkError("Parent ID is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            sub = cursor.execute(
                "SELECT id FROM homework_submissions WHERE id = ?",
                (submission_id,)).fetchone()
            if not sub:
                raise HomeworkError("Submission not found")

            # Check for existing feedback row to update parent comment
            existing = cursor.execute(
                "SELECT id FROM homework_feedback WHERE submission_id = ?",
                (submission_id,)).fetchone()
            if existing:
                cursor.execute(
                    "UPDATE homework_feedback SET parent_comment = ?, parent_id = ? WHERE id = ?",
                    (str(comment).strip(), parent_id, existing["id"]))
            else:
                cursor.execute(
                    """INSERT INTO homework_feedback
                       (submission_id, parent_comment, parent_id)
                       VALUES (?, ?, ?)""",
                    (submission_id, str(comment).strip(), parent_id))
            conn.commit()
            fb_id = existing["id"] if existing else cursor.lastrowid
            row = cursor.execute(
                "SELECT * FROM homework_feedback WHERE id = ?",
                (fb_id,)).fetchone()
            logger.info("Parent comment added for submission %d by %s",
                        submission_id, parent_id)
            return dict(row)
        except HomeworkError:
            conn.rollback()
            raise
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HomeworkError(f"Failed to add parent comment: {e}") from e
        finally:
            conn.close()

    # ---- Submission with feedback ----

    def get_submission_with_feedback(self, submission_id):
        """Return a submission joined with its feedback record (if any).

        Returns a single dict combining submission fields with feedback fields.
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT hs.*, p.first_name, p.last_name,
                          hf.teacher_feedback, hf.sticker,
                          hf.parent_comment, hf.parent_id
                   FROM homework_submissions hs
                   JOIN pupils p ON hs.pupil_id = p.pupil_id
                   LEFT JOIN homework_feedback hf ON hf.submission_id = hs.id
                   WHERE hs.id = ?""",
                (submission_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ---- Outstanding homework ----

    def list_outstanding(self, pupil_id):
        """List homework not yet submitted by the given pupil.

        Returns active homework where no submission exists for this pupil.
        """
        if not pupil_id:
            raise HomeworkError("Pupil ID is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT h.*
                   FROM homework h
                   WHERE h.status = 'Active'
                     AND NOT EXISTS (
                         SELECT 1 FROM homework_submissions hs
                         WHERE hs.homework_id = h.id AND hs.pupil_id = ?
                     )
                   ORDER BY h.due_date ASC""",
                (pupil_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
