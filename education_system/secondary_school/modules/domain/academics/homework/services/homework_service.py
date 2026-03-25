"""Homework service."""

import logging
from datetime import datetime, date as date_type
from education_system.secondary_school.core.exceptions import HomeworkError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

SUBMISSION_STATUSES = ("pending", "submitted", "late", "marked", "missing")
VALID_STICKERS = ("gold_star", "well_done", "good_effort", "keep_trying")


class HomeworkService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_homework(self, subject_id, title, due_date, year_group=None,
                        description=None, set_by=None, max_marks=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO homework (subject_id, year_group, title, description, set_by, due_date, max_marks)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (subject_id, year_group, title, description, set_by, due_date, max_marks))
            conn.commit()
            row = conn.execute("SELECT * FROM homework WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise HomeworkError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_homework(self, subject_id=None, year_group=None, status=None):
        conn = self._conn()
        try:
            sql = """SELECT h.*, s.subject_code, s.title as subject_title
                     FROM homework h JOIN subjects s ON h.subject_id = s.id WHERE 1=1"""
            params = []
            if subject_id:
                sql += " AND h.subject_id = ?"
                params.append(subject_id)
            if year_group:
                sql += " AND h.year_group = ?"
                params.append(year_group)
            if status:
                sql += " AND h.status = ?"
                params.append(status)
            sql += " ORDER BY h.due_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_homework(self, hw_id):
        conn = self._conn()
        try:
            # Clean up feedback linked to submissions for this homework
            conn.execute(
                """DELETE FROM homework_feedback WHERE submission_id IN
                   (SELECT id FROM homework_submissions WHERE homework_id = ?)""",
                (hw_id,))
            conn.execute("DELETE FROM homework_submissions WHERE homework_id = ?", (hw_id,))
            conn.execute("DELETE FROM homework_rubrics WHERE homework_id = ?", (hw_id,))
            conn.execute("DELETE FROM homework_drafts WHERE homework_id = ?", (hw_id,))
            conn.execute("DELETE FROM homework WHERE id = ?", (hw_id,))
            conn.commit()
        finally:
            conn.close()

    def submit(self, homework_id, student_id):
        conn = self._conn()
        try:
            from datetime import datetime
            existing = conn.execute("SELECT id FROM homework_submissions WHERE homework_id = ? AND student_id = ?",
                                    (homework_id, student_id)).fetchone()
            if existing:
                conn.execute("UPDATE homework_submissions SET status = 'submitted', submitted_at = datetime('now') WHERE id = ?",
                             (existing["id"],))
            else:
                conn.execute("INSERT INTO homework_submissions (homework_id, student_id, submitted_at, status) VALUES (?, ?, datetime('now'), 'submitted')",
                             (homework_id, student_id))
            conn.commit()
        finally:
            conn.close()

    def mark_submission(self, homework_id, student_id, marks=None, feedback=None):
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM homework_submissions WHERE homework_id = ? AND student_id = ?",
                                    (homework_id, student_id)).fetchone()
            if existing:
                conn.execute("UPDATE homework_submissions SET marks = ?, feedback = ?, status = 'marked' WHERE id = ?",
                             (marks, feedback, existing["id"]))
            else:
                conn.execute("INSERT INTO homework_submissions (homework_id, student_id, marks, feedback, status) VALUES (?, ?, ?, ?, 'marked')",
                             (homework_id, student_id, marks, feedback))
            conn.commit()
        finally:
            conn.close()

    def get_submissions(self, homework_id):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT hs.*, s.student_id as sid, s.first_name, s.last_name
                   FROM homework_submissions hs JOIN students s ON hs.student_id = s.id
                   WHERE hs.homework_id = ? ORDER BY s.last_name""",
                (homework_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- Rubric support ----

    def add_rubric(self, homework_id, criteria, max_marks_per_criteria):
        """Add a rubric criterion to a homework assignment.

        Args:
            homework_id: ID of the homework.
            criteria: Description of the criterion being assessed.
            max_marks_per_criteria: Maximum marks available for this criterion.
        Returns:
            dict with the created rubric row.
        """
        if not criteria or not str(criteria).strip():
            raise HomeworkError("Criteria text is required")
        if max_marks_per_criteria is None or int(max_marks_per_criteria) < 0:
            raise HomeworkError("Max marks must be a non-negative integer")

        conn = self._conn()
        try:
            hw = conn.execute("SELECT id FROM homework WHERE id = ?", (homework_id,)).fetchone()
            if not hw:
                raise HomeworkError("Homework not found")
            cursor = conn.execute(
                "INSERT INTO homework_rubrics (homework_id, criteria, max_marks) VALUES (?, ?, ?)",
                (homework_id, str(criteria).strip(), int(max_marks_per_criteria)))
            conn.commit()
            row = conn.execute("SELECT * FROM homework_rubrics WHERE id = ?",
                               (cursor.lastrowid,)).fetchone()
            return dict(row)
        except HomeworkError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HomeworkError(f"Failed to add rubric: {e}") from e
        finally:
            conn.close()

    def get_rubric(self, homework_id):
        """Return all rubric criteria for a homework assignment."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM homework_rubrics WHERE homework_id = ? ORDER BY id",
                (homework_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- Submission with attachment ----

    def submit_with_attachment(self, homework_id, student_id, text=None, file_path=None):
        """Submit homework with optional text content and/or file attachment.

        Detects late submissions by comparing against the homework due date.
        """
        conn = self._conn()
        try:
            hw = conn.execute("SELECT * FROM homework WHERE id = ?", (homework_id,)).fetchone()
            if not hw:
                raise HomeworkError("Homework not found")

            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            is_late = 1 if now_str[:10] > hw["due_date"][:10] else 0
            status = "late" if is_late else "submitted"

            # Check for existing submission (update if exists)
            existing = conn.execute(
                "SELECT id FROM homework_submissions WHERE homework_id = ? AND student_id = ? AND resubmission_of IS NULL",
                (homework_id, student_id)).fetchone()
            if existing:
                conn.execute(
                    """UPDATE homework_submissions
                       SET feedback = COALESCE(?, feedback), file_path = COALESCE(?, file_path),
                           submitted_at = ?, is_late = ?, status = ?
                       WHERE id = ?""",
                    (text, file_path, now_str, is_late, status, existing["id"]))
            else:
                conn.execute(
                    """INSERT INTO homework_submissions
                       (homework_id, student_id, feedback, file_path, submitted_at, is_late, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (homework_id, student_id, text, file_path, now_str, is_late, status))
            conn.commit()
            logger.info("Submission (with attachment) for homework=%d student=%d late=%s",
                        homework_id, student_id, bool(is_late))
        except HomeworkError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HomeworkError(f"Submission failed: {e}") from e
        finally:
            conn.close()

    # ---- Detailed feedback ----

    def add_feedback(self, submission_id, feedback_text, marked_by):
        """Add detailed feedback to a submission (stored in homework_feedback table)."""
        if not feedback_text or not str(feedback_text).strip():
            raise HomeworkError("Feedback text is required")

        conn = self._conn()
        try:
            sub = conn.execute("SELECT id FROM homework_submissions WHERE id = ?",
                               (submission_id,)).fetchone()
            if not sub:
                raise HomeworkError("Submission not found")

            cursor = conn.execute(
                "INSERT INTO homework_feedback (submission_id, feedback_text, marked_by) VALUES (?, ?, ?)",
                (submission_id, str(feedback_text).strip(), marked_by))
            conn.commit()
            row = conn.execute("SELECT * FROM homework_feedback WHERE id = ?",
                               (cursor.lastrowid,)).fetchone()
            return dict(row)
        except HomeworkError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HomeworkError(f"Failed to add feedback: {e}") from e
        finally:
            conn.close()

    def get_detailed_feedback(self, submission_id):
        """Return all feedback entries for a submission, ordered chronologically."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM homework_feedback WHERE submission_id = ? ORDER BY created_at",
                (submission_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- Drafts ----

    def save_draft(self, homework_id, student_id, draft_text):
        """Save or update a draft for a homework assignment.

        Only one draft per student per homework is kept (upsert behaviour).
        """
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM homework_drafts WHERE homework_id = ? AND student_id = ?",
                (homework_id, student_id)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE homework_drafts SET draft_text = ?, saved_at = datetime('now') WHERE id = ?",
                    (draft_text, existing["id"]))
            else:
                conn.execute(
                    "INSERT INTO homework_drafts (homework_id, student_id, draft_text) VALUES (?, ?, ?)",
                    (homework_id, student_id, draft_text))
            conn.commit()
            logger.info("Draft saved: homework=%d student=%d", homework_id, student_id)
        except Exception as e:
            conn.rollback()
            raise HomeworkError(f"Failed to save draft: {e}") from e
        finally:
            conn.close()

    def get_draft(self, homework_id, student_id):
        """Retrieve the saved draft for a student's homework."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM homework_drafts WHERE homework_id = ? AND student_id = ?",
                (homework_id, student_id)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ---- Statistics ----

    def get_submission_stats(self, homework_id):
        """Return submission statistics for a homework assignment.

        Returns dict with: total_submissions, submitted_count, marked_count,
        late_count, avg_marks, pending_count.
        """
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT
                       COUNT(*) as total_submissions,
                       SUM(CASE WHEN status IN ('submitted', 'marked', 'late') THEN 1 ELSE 0 END) as submitted_count,
                       SUM(CASE WHEN status = 'marked' THEN 1 ELSE 0 END) as marked_count,
                       SUM(CASE WHEN is_late = 1 THEN 1 ELSE 0 END) as late_count,
                       AVG(CASE WHEN marks IS NOT NULL THEN marks END) as avg_marks,
                       SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count
                   FROM homework_submissions WHERE homework_id = ?""",
                (homework_id,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def list_late_submissions(self, homework_id=None):
        """List late submissions, optionally filtered by homework_id."""
        conn = self._conn()
        try:
            sql = """SELECT hs.*, h.title as homework_title, h.due_date,
                            s.student_id as sid, s.first_name, s.last_name
                     FROM homework_submissions hs
                     JOIN homework h ON hs.homework_id = h.id
                     JOIN students s ON hs.student_id = s.id
                     WHERE hs.is_late = 1"""
            params = []
            if homework_id is not None:
                sql += " AND hs.homework_id = ?"
                params.append(homework_id)
            sql += " ORDER BY hs.submitted_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- Deadline extension ----

    def extend_deadline(self, homework_id, new_due_date, reason):
        """Extend the due date for a homework assignment.

        Args:
            homework_id: ID of the homework.
            new_due_date: New due date string (YYYY-MM-DD).
            reason: Reason for the extension.
        """
        if not new_due_date:
            raise HomeworkError("New due date is required")

        conn = self._conn()
        try:
            hw = conn.execute("SELECT * FROM homework WHERE id = ?", (homework_id,)).fetchone()
            if not hw:
                raise HomeworkError("Homework not found")
            if new_due_date <= hw["due_date"][:10]:
                raise HomeworkError("New due date must be later than the current due date")

            conn.execute(
                "UPDATE homework SET due_date = ?, description = COALESCE(description, '') || ? WHERE id = ?",
                (new_due_date,
                 f"\n[Deadline extended to {new_due_date}: {reason}]",
                 homework_id))
            conn.commit()
            logger.info("Deadline extended: homework=%d new_due=%s reason=%s",
                        homework_id, new_due_date, reason)
            row = conn.execute("SELECT * FROM homework WHERE id = ?", (homework_id,)).fetchone()
            return dict(row)
        except HomeworkError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HomeworkError(f"Failed to extend deadline: {e}") from e
        finally:
            conn.close()

    # ---- Resubmission ----

    def resubmit(self, submission_id, text=None, file_path=None):
        """Create a resubmission linked to the original submission.

        The original submission is kept for audit; a new row is created
        with resubmission_of pointing to the original.
        """
        conn = self._conn()
        try:
            original = conn.execute(
                "SELECT * FROM homework_submissions WHERE id = ?",
                (submission_id,)).fetchone()
            if not original:
                raise HomeworkError("Original submission not found")

            hw = conn.execute("SELECT * FROM homework WHERE id = ?",
                              (original["homework_id"],)).fetchone()
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            is_late = 1 if now_str[:10] > hw["due_date"][:10] else 0
            status = "late" if is_late else "submitted"

            cursor = conn.execute(
                """INSERT INTO homework_submissions
                   (homework_id, student_id, feedback, file_path, submitted_at,
                    is_late, resubmission_of, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (original["homework_id"], original["student_id"],
                 text, file_path, now_str, is_late, submission_id, status))
            conn.commit()
            logger.info("Resubmission created: original=%d new=%d",
                        submission_id, cursor.lastrowid)
            row = conn.execute("SELECT * FROM homework_submissions WHERE id = ?",
                               (cursor.lastrowid,)).fetchone()
            return dict(row)
        except HomeworkError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HomeworkError(f"Resubmission failed: {e}") from e
        finally:
            conn.close()
