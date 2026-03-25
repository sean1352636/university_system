"""Parent portal service."""

from education_system.college_system.core.exceptions import ParentPortalError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class ParentService:
    """Service for parent portal features."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def link_parent(self, parent_user_id: int, student_id: int,
                    relationship: str = "parent") -> dict:
        """Link a parent user to a student."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO parent_links (parent_user_id, student_id, relationship)
                   VALUES (?, ?, ?)""",
                (parent_user_id, student_id, relationship),
            )
            conn.commit()
            logger.info("Parent link created: parent=%d student=%d",
                        parent_user_id, student_id)
            return {"parent_user_id": parent_user_id, "student_id": student_id,
                    "relationship": relationship}
        except Exception as e:
            conn.rollback()
            raise ParentPortalError(f"Failed to link parent: {e}") from e
        finally:
            conn.close()

    def get_linked_students(self, parent_user_id: int) -> list[dict]:
        """Get students linked to a parent."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.*, pl.relationship
                   FROM students s
                   JOIN parent_links pl ON s.id = pl.student_id
                   WHERE pl.parent_user_id = ?
                   ORDER BY s.last_name, s.first_name""",
                (parent_user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def unlink_parent(self, parent_user_id: int, student_id: int) -> bool:
        """Remove a parent-student link."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM parent_links WHERE parent_user_id = ? AND student_id = ?",
                (parent_user_id, student_id),
            )
            conn.commit()
            if result.rowcount == 0:
                raise ParentPortalError("Link not found.")
            logger.info("Parent link removed: parent=%d student=%d",
                        parent_user_id, student_id)
            return True
        except ParentPortalError:
            raise
        except Exception as e:
            conn.rollback()
            raise ParentPortalError(f"Failed to unlink parent: {e}") from e
        finally:
            conn.close()

    def _verify_link(self, conn, parent_user_id: int, student_id: int):
        """Verify a parent is linked to a student."""
        link = conn.execute(
            "SELECT id FROM parent_links WHERE parent_user_id = ? AND student_id = ?",
            (parent_user_id, student_id),
        ).fetchone()
        if not link:
            raise ParentPortalError("You are not linked to this student.")

    def get_child_grades(self, parent_user_id: int,
                         student_id: int) -> list[dict]:
        """Get grades for a linked child."""
        conn = self._conn()
        try:
            self._verify_link(conn, parent_user_id, student_id)
            rows = conn.execute(
                """SELECT g.*, c.course_code, c.title as course_title
                   FROM grades g
                   JOIN courses c ON g.course_id = c.id
                   WHERE g.student_id = ?
                   ORDER BY c.course_code""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_child_attendance(self, parent_user_id: int,
                             student_id: int) -> list[dict]:
        """Get attendance summary per course for a linked child."""
        conn = self._conn()
        try:
            self._verify_link(conn, parent_user_id, student_id)

            # Get distinct courses the student is enrolled in
            courses = conn.execute(
                """SELECT DISTINCT c.id, c.course_code, c.title
                   FROM courses c
                   JOIN enrollments e ON c.id = e.course_id
                   WHERE e.student_id = ? AND e.status = 'enrolled'""",
                (student_id,),
            ).fetchall()

            summaries = []
            for course in courses:
                records = conn.execute(
                    """SELECT ar.status FROM attendance_records ar
                       JOIN attendance_sessions asess ON ar.session_id = asess.id
                       WHERE ar.student_id = ? AND asess.course_id = ?""",
                    (student_id, course["id"]),
                ).fetchall()

                total = len(records)
                present = sum(1 for r in records if r["status"] == "present")
                late = sum(1 for r in records if r["status"] == "late")
                absent = sum(1 for r in records if r["status"] == "absent")
                excused = sum(1 for r in records if r["status"] == "excused")
                rate = round(((present + late) / total) * 100, 1) if total > 0 else 0.0

                summaries.append({
                    "course_code": course["course_code"],
                    "course_title": course["title"],
                    "total": total,
                    "present": present,
                    "late": late,
                    "absent": absent,
                    "excused": excused,
                    "rate": rate,
                })
            return summaries
        finally:
            conn.close()

    def get_child_timetable(self, parent_user_id: int,
                            student_id: int) -> list[dict]:
        """Get timetable for a linked child."""
        conn = self._conn()
        try:
            self._verify_link(conn, parent_user_id, student_id)
            rows = conn.execute(
                """SELECT ts.*, c.course_code, c.title as course_title
                   FROM timetable_slots ts
                   JOIN courses c ON ts.course_id = c.id
                   JOIN enrollments e ON c.id = e.course_id
                   WHERE e.student_id = ? AND e.status = 'enrolled'
                   ORDER BY CASE ts.day_of_week
                       WHEN 'Mon' THEN 1 WHEN 'Tue' THEN 2
                       WHEN 'Wed' THEN 3 WHEN 'Thu' THEN 4
                       WHEN 'Fri' THEN 5 END, ts.start_time""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all_parents(self) -> list[dict]:
        """List all parent-role users (admin use)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, username, email FROM users WHERE role = 'parent' AND is_active = 1"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_link(self, link_id: int) -> bool:
        """Delete a parent-student link by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM parent_links WHERE id = ?", (link_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise ParentPortalError(f"Link {link_id} not found.")
            logger.info("Parent link deleted: id=%d", link_id)
            return True
        except ParentPortalError:
            raise
        except Exception as e:
            conn.rollback()
            raise ParentPortalError(f"Failed to delete link: {e}") from e
        finally:
            conn.close()

    def admin_link_parent(self, parent_user_id: int, student_id: int,
                          relationship: str = "parent") -> dict:
        """Admin creates a parent-student link."""
        return self.link_parent(parent_user_id, student_id, relationship)
