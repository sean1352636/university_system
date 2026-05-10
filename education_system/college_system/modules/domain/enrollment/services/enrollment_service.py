"""Enrollment management service with auto-waitlist support."""

from datetime import datetime

from education_system.college_system.core.exceptions import EnrollmentError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class EnrollmentService:
    """Service for managing student enrollments and waitlists."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def enroll_student(self, student_pk: int, course_pk: int) -> dict:
        """Enroll a student in a course. Auto-waitlists if course is full.

        Returns dict with 'status' key: 'enrolled' or 'waitlisted'.
        """
        conn = self._conn()
        try:
            # Verify student exists
            student = conn.execute("SELECT * FROM students WHERE id = ?", (student_pk,)).fetchone()
            if not student:
                raise EnrollmentError("Student not found.")

            # Verify course exists and is active
            course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_pk,)).fetchone()
            if not course:
                raise EnrollmentError("Course not found.")
            if course["status"] != "active":
                raise EnrollmentError("Course is not active.")

            # Check if already enrolled
            existing = conn.execute(
                "SELECT * FROM enrollments WHERE student_id = ? AND course_id = ? AND status = 'enrolled'",
                (student_pk, course_pk),
            ).fetchone()
            if existing:
                raise EnrollmentError("Student is already enrolled in this course.")

            # Check already on waitlist
            on_waitlist = conn.execute(
                "SELECT * FROM waitlist WHERE student_id = ? AND course_id = ?",
                (student_pk, course_pk),
            ).fetchone()
            if on_waitlist:
                raise EnrollmentError("Student is already on the waitlist for this course.")

            # Check prerequisites
            prereqs = conn.execute(
                "SELECT prerequisite_id FROM prerequisites WHERE course_id = ?",
                (course_pk,),
            ).fetchall()

            for prereq in prereqs:
                grade = conn.execute(
                    """SELECT * FROM grades
                       WHERE student_id = ? AND course_id = ? AND letter_grade != 'U'""",
                    (student_pk, prereq["prerequisite_id"]),
                ).fetchone()
                if not grade:
                    prereq_course = conn.execute(
                        "SELECT course_code FROM courses WHERE id = ?",
                        (prereq["prerequisite_id"],),
                    ).fetchone()
                    code = prereq_course["course_code"] if prereq_course else "unknown"
                    raise EnrollmentError(f"Prerequisite not met: {code}")

            # Check capacity
            enrolled_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM enrollments WHERE course_id = ? AND status = 'enrolled'",
                (course_pk,),
            ).fetchone()["cnt"]

            if enrolled_count >= course["capacity"]:
                # Add to waitlist
                max_pos = conn.execute(
                    "SELECT COALESCE(MAX(position), 0) as max_pos FROM waitlist WHERE course_id = ?",
                    (course_pk,),
                ).fetchone()["max_pos"]

                position = max_pos + 1
                conn.execute(
                    "INSERT INTO waitlist (student_id, course_id, position) VALUES (?, ?, ?)",
                    (student_pk, course_pk, position),
                )
                conn.commit()
                logger.info("Student waitlisted: student_pk=%d course_pk=%d position=%d", student_pk, course_pk, position)
                return {
                    "status": "waitlisted",
                    "position": position,
                    "student_id": student["student_id"],
                    "course_code": course["course_code"],
                }

            # Enroll
            # Remove any previous dropped enrollment first
            conn.execute(
                "DELETE FROM enrollments WHERE student_id = ? AND course_id = ? AND status = 'dropped'",
                (student_pk, course_pk),
            )
            conn.execute(
                "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
                (student_pk, course_pk),
            )
            conn.commit()
            logger.info("Student enrolled: student_pk=%d course_pk=%d", student_pk, course_pk)

            # Notify student of enrollment
            try:
                if student["user_id"]:
                    from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService
                    nsvc = NotificationService(self._db_path)
                    nsvc.send(
                        student["user_id"],
                        f"Enrolled in {course['course_code']}",
                        f"You have been enrolled in {course['title']} ({course['course_code']}).",
                        type="success",
                    )
            except Exception:
                logger.warning("Failed to send enrollment notification to student user_id=%s", student["user_id"], exc_info=True)

            return {
                "status": "enrolled",
                "student_id": student["student_id"],
                "course_code": course["course_code"],
            }
        except EnrollmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise EnrollmentError(f"Enrollment failed: {e}") from e
        finally:
            conn.close()

    def drop_student(self, student_pk: int, course_pk: int) -> dict:
        """Drop a student from a course. Auto-promotes next waitlisted student."""
        conn = self._conn()
        try:
            enrollment = conn.execute(
                "SELECT * FROM enrollments WHERE student_id = ? AND course_id = ? AND status = 'enrolled'",
                (student_pk, course_pk),
            ).fetchone()

            if not enrollment:
                raise EnrollmentError("Student is not enrolled in this course.")

            conn.execute(
                """UPDATE enrollments SET status = 'dropped', dropped_at = datetime('now')
                   WHERE student_id = ? AND course_id = ? AND status = 'enrolled'""",
                (student_pk, course_pk),
            )

            # Auto-promote from waitlist
            promoted = self._promote_from_waitlist(conn, course_pk)

            conn.commit()
            logger.info("Student dropped: student_pk=%d course_pk=%d", student_pk, course_pk)

            result = {"status": "dropped", "student_pk": student_pk, "course_pk": course_pk}
            if promoted:
                result["promoted_student_pk"] = promoted
            return result
        except EnrollmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise EnrollmentError(f"Drop failed: {e}") from e
        finally:
            conn.close()

    def _promote_from_waitlist(self, conn, course_pk: int) -> int | None:
        """Promote the next student from the waitlist. Returns promoted student_pk or None."""
        next_student = conn.execute(
            "SELECT * FROM waitlist WHERE course_id = ? ORDER BY position LIMIT 1",
            (course_pk,),
        ).fetchone()

        if not next_student:
            return None

        student_pk = next_student["student_id"]

        # Remove from waitlist
        conn.execute(
            "DELETE FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_pk, course_pk),
        )

        # Re-number remaining waitlist positions
        remaining = conn.execute(
            "SELECT id FROM waitlist WHERE course_id = ? ORDER BY position",
            (course_pk,),
        ).fetchall()
        for i, row in enumerate(remaining, 1):
            conn.execute("UPDATE waitlist SET position = ? WHERE id = ?", (i, row["id"]))

        # Enroll the student
        conn.execute(
            "DELETE FROM enrollments WHERE student_id = ? AND course_id = ? AND status = 'dropped'",
            (student_pk, course_pk),
        )
        conn.execute(
            "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, 'enrolled')",
            (student_pk, course_pk),
        )
        logger.info("Student promoted from waitlist: student_pk=%d course_pk=%d", student_pk, course_pk)

        return student_pk

    def get_enrollment(self, student_pk: int, course_pk: int) -> dict | None:
        """Get enrollment info for a student in a course."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT e.*, s.student_id as sid, c.course_code
                   FROM enrollments e
                   JOIN students s ON e.student_id = s.id
                   JOIN courses c ON e.course_id = c.id
                   WHERE e.student_id = ? AND e.course_id = ?""",
                (student_pk, course_pk),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    _SEARCH_COLUMNS = (
        "s.student_id", "s.first_name", "s.last_name",
        "c.course_code", "c.title", "c.term",
    )

    @classmethod
    def _search_clause(cls, search: str | None) -> tuple[str, list]:
        """Return ``(sql_fragment, params)`` for a free-text search across
        student/course identifying columns. Empty/None search returns no-op."""
        if not search:
            return "", []
        term = f"%{search.strip()}%"
        ors = " OR ".join(f"{col} LIKE ?" for col in cls._SEARCH_COLUMNS)
        return f" AND ({ors})", [term] * len(cls._SEARCH_COLUMNS)

    def list_enrollments(self, student_pk: int | None = None,
                         course_pk: int | None = None,
                         status: str | None = None,
                         search: str | None = None,
                         limit: int = 100, offset: int = 0) -> list[dict]:
        """List enrollments with optional filters.

        ``search`` matches across student id/name and course code/title/term.
        """
        sql = """SELECT e.*, s.student_id as sid, s.first_name, s.last_name,
                        c.course_code, c.title
                 FROM enrollments e
                 JOIN students s ON e.student_id = s.id
                 JOIN courses c ON e.course_id = c.id
                 WHERE 1=1"""
        params: list = []

        if student_pk is not None:
            sql += " AND e.student_id = ?"
            params.append(student_pk)
        if course_pk is not None:
            sql += " AND e.course_id = ?"
            params.append(course_pk)
        if status:
            sql += " AND e.status = ?"
            params.append(status)
        search_sql, search_params = self._search_clause(search)
        sql += search_sql
        params.extend(search_params)

        sql += " ORDER BY e.enrolled_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def count_enrollments(self, student_pk: int | None = None,
                          course_pk: int | None = None,
                          status: str | None = None,
                          search: str | None = None) -> int:
        """Count total enrollments with optional filters."""
        sql = """SELECT COUNT(*) as cnt
                 FROM enrollments e
                 JOIN students s ON e.student_id = s.id
                 JOIN courses c ON e.course_id = c.id
                 WHERE 1=1"""
        params: list = []
        if student_pk is not None:
            sql += " AND e.student_id = ?"
            params.append(student_pk)
        if course_pk is not None:
            sql += " AND e.course_id = ?"
            params.append(course_pk)
        if status:
            sql += " AND e.status = ?"
            params.append(status)
        search_sql, search_params = self._search_clause(search)
        sql += search_sql
        params.extend(search_params)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def promote_from_waitlist(self, course_pk: int) -> int | None:
        """Public wrapper around the internal waitlist promotion helper.

        Returns the promoted student's PK, or ``None`` if the waitlist for
        ``course_pk`` was empty. Commits the change.
        """
        conn = self._conn()
        try:
            promoted = self._promote_from_waitlist(conn, course_pk)
            conn.commit()
            return promoted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_waitlist(self, course_pk: int) -> list[dict]:
        """Get the waitlist for a course."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT w.*, s.student_id as sid, s.first_name, s.last_name
                   FROM waitlist w JOIN students s ON w.student_id = s.id
                   WHERE w.course_id = ?
                   ORDER BY w.position""",
                (course_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_enrollment(self, enrollment_id: int) -> bool:
        """Delete an enrollment record by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM enrollments WHERE id = ?", (enrollment_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise EnrollmentError(f"Enrollment {enrollment_id} not found.")
            logger.info("Enrollment deleted: id=%d", enrollment_id)
            return True
        except EnrollmentError:
            raise
        except Exception as e:
            conn.rollback()
            raise EnrollmentError(f"Failed to delete enrollment: {e}") from e
        finally:
            conn.close()

    def get_student_enrollments(self, student_pk: int) -> list[dict]:
        """Get all active enrollments for a student."""
        return self.list_enrollments(student_pk=student_pk, status="enrolled")
