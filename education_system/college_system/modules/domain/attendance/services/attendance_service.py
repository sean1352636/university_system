"""Attendance management service."""

from datetime import datetime, date

from education_system.college_system.core.exceptions import AttendanceError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.database.constants import ATTENDANCE_STATUSES
from education_system.college_system.infrastructure.validation.validators import validate_date

import logging

logger = logging.getLogger(__name__)


class AttendanceService:
    """Service for managing attendance sessions and records."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_session(self, course_pk: int, session_date: str | None = None,
                       topic: str | None = None, created_by: str | None = None) -> dict:
        """Create a new attendance session for a course."""
        if session_date is None:
            session_date = date.today().isoformat()
        else:
            session_date = validate_date(session_date)

        conn = self._conn()
        try:
            # Verify course exists
            course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_pk,)).fetchone()
            if not course:
                raise AttendanceError("Course not found.")

            cursor = conn.execute(
                """INSERT INTO attendance_sessions (course_id, session_date, topic, created_by)
                   VALUES (?, ?, ?, ?)""",
                (course_pk, session_date, topic, created_by),
            )
            conn.commit()
            logger.info("Attendance session created: course=%d date=%s", course_pk, session_date)
            session_id = cursor.lastrowid

            return self.get_session(session_id)
        except AttendanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AttendanceError(f"Failed to create session: {e}") from e
        finally:
            conn.close()

    def get_session(self, session_id: int) -> dict | None:
        """Get an attendance session by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT a.*, c.course_code, c.title as course_title
                   FROM attendance_sessions a JOIN courses c ON a.course_id = c.id
                   WHERE a.id = ?""",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def record_attendance(self, session_id: int, student_pk: int,
                          status: str = "present", notes: str | None = None) -> dict:
        """Record attendance for a single student in a session."""
        if status not in ATTENDANCE_STATUSES:
            raise AttendanceError(
                f"Invalid status: {status}. Must be one of: {', '.join(ATTENDANCE_STATUSES)}"
            )

        conn = self._conn()
        try:
            # Verify session exists
            session = conn.execute(
                "SELECT * FROM attendance_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not session:
                raise AttendanceError("Attendance session not found.")

            # Verify student is enrolled in the course
            enrollment = conn.execute(
                "SELECT * FROM enrollments WHERE student_id = ? AND course_id = ? AND status = 'enrolled'",
                (student_pk, session["course_id"]),
            ).fetchone()
            if not enrollment:
                raise AttendanceError("Student is not enrolled in this course.")

            # Insert or update
            existing = conn.execute(
                "SELECT * FROM attendance_records WHERE session_id = ? AND student_id = ?",
                (session_id, student_pk),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE attendance_records SET status = ?, notes = ?, recorded_at = datetime('now') WHERE id = ?",
                    (status, notes, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO attendance_records (session_id, student_id, status, notes) VALUES (?, ?, ?, ?)",
                    (session_id, student_pk, status, notes),
                )

            conn.commit()
            logger.debug("Attendance recorded: session=%d student=%d status=%s", session_id, student_pk, status)
            return {"session_id": session_id, "student_pk": student_pk, "status": status}
        except AttendanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AttendanceError(f"Failed to record attendance: {e}") from e
        finally:
            conn.close()

    def bulk_record_attendance(self, session_id: int,
                               records: list[dict]) -> int:
        """Record attendance for multiple students at once.

        Each record is a dict with 'student_pk' and 'status' keys.
        Returns the number of records processed.
        """
        count = 0
        for record in records:
            self.record_attendance(
                session_id,
                record["student_pk"],
                record.get("status", "present"),
                record.get("notes"),
            )
            count += 1
        logger.info("Bulk attendance recorded: session=%d count=%d", session_id, count)
        return count

    def get_session_records(self, session_id: int,
                            limit: int = 0, offset: int = 0) -> list[dict]:
        """Get attendance records for a session, with optional pagination."""
        conn = self._conn()
        try:
            sql = """SELECT ar.*, s.student_id as sid, s.first_name, s.last_name
                   FROM attendance_records ar
                   JOIN students s ON ar.student_id = s.id
                   WHERE ar.session_id = ?
                   ORDER BY s.last_name, s.first_name"""
            params: list = [session_id]
            if limit > 0:
                sql += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def count_session_records(self, session_id: int) -> int:
        """Count total attendance records for a session."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM attendance_records WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def get_student_attendance(self, student_pk: int,
                               course_pk: int | None = None) -> list[dict]:
        """Get attendance records for a student, optionally filtered by course."""
        conn = self._conn()
        try:
            sql = """SELECT ar.*, a_s.session_date, a_s.topic,
                            c.course_code, c.title as course_title
                     FROM attendance_records ar
                     JOIN attendance_sessions a_s ON ar.session_id = a_s.id
                     JOIN courses c ON a_s.course_id = c.id
                     WHERE ar.student_id = ?"""
            params = [student_pk]

            if course_pk is not None:
                sql += " AND a_s.course_id = ?"
                params.append(course_pk)

            sql += " ORDER BY a_s.session_date DESC"

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_attendance_summary(self, student_pk: int,
                               course_pk: int) -> dict:
        """Get attendance summary for a student in a course."""
        records = self.get_student_attendance(student_pk, course_pk)

        total = len(records)
        if total == 0:
            return {
                "total_sessions": 0, "present": 0, "absent": 0,
                "late": 0, "excused": 0, "attendance_rate": 0.0,
            }

        counts = {s: 0 for s in ATTENDANCE_STATUSES}
        for r in records:
            counts[r["status"]] = counts.get(r["status"], 0) + 1

        attended = counts["present"] + counts["late"]
        rate = round((attended / total) * 100, 1) if total > 0 else 0.0

        return {
            "total_sessions": total,
            "present": counts["present"],
            "absent": counts["absent"],
            "late": counts["late"],
            "excused": counts["excused"],
            "attendance_rate": rate,
        }

    def get_course_sessions(self, course_pk: int) -> list[dict]:
        """Get all attendance sessions for a course."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM attendance_sessions
                   WHERE course_id = ?
                   ORDER BY session_date DESC""",
                (course_pk,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_course_attendance_report(self, course_pk: int) -> list[dict]:
        """Get attendance report for all students in a course."""
        conn = self._conn()
        try:
            students = conn.execute(
                """SELECT s.id, s.student_id, s.first_name, s.last_name
                   FROM students s JOIN enrollments e ON s.id = e.student_id
                   WHERE e.course_id = ? AND e.status = 'enrolled'
                   ORDER BY s.last_name""",
                (course_pk,),
            ).fetchall()

            report = []
            for s in students:
                summary = self.get_attendance_summary(s["id"], course_pk)
                report.append({
                    "student_id": s["student_id"],
                    "name": f"{s['first_name']} {s['last_name']}",
                    **summary,
                })
            return report
        finally:
            conn.close()

    def create_session_from_slot(self, timetable_slot_id: int,
                                  session_date: str | None = None,
                                  created_by: str | None = None) -> dict:
        """Create an attendance session linked to a timetable slot."""
        if session_date is None:
            session_date = date.today().isoformat()
        else:
            session_date = validate_date(session_date)

        conn = self._conn()
        try:
            slot = conn.execute(
                """SELECT ts.*, c.title as course_title
                   FROM timetable_slots ts JOIN courses c ON ts.course_id = c.id
                   WHERE ts.id = ?""",
                (timetable_slot_id,),
            ).fetchone()
            if not slot:
                raise AttendanceError("Timetable slot not found.")

            topic = f"{slot['course_title']} ({slot['start_time']}-{slot['end_time']})"
            cursor = conn.execute(
                """INSERT INTO attendance_sessions
                   (course_id, session_date, topic, created_by, timetable_slot_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (slot["course_id"], session_date, topic, created_by, timetable_slot_id),
            )
            conn.commit()
            session_id = cursor.lastrowid
            logger.info("Session created from slot %d: session=%d", timetable_slot_id, session_id)
            return self.get_session(session_id)
        except AttendanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AttendanceError(f"Failed to create session from slot: {e}") from e
        finally:
            conn.close()

    def generate_registers_for_date(self, target_date: str,
                                     created_by: str | None = None) -> list[dict]:
        """Auto-create attendance sessions for all timetable slots on a given date's day of week."""
        target_date = validate_date(target_date)
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_of_week = day_names[dt.weekday()]

        conn = self._conn()
        try:
            slots = conn.execute(
                """SELECT ts.id FROM timetable_slots ts
                   JOIN courses c ON ts.course_id = c.id
                   WHERE ts.day_of_week = ? AND c.status = 'active'""",
                (day_of_week,),
            ).fetchall()

            sessions = []
            for slot in slots:
                existing = conn.execute(
                    """SELECT id FROM attendance_sessions
                       WHERE timetable_slot_id = ? AND session_date = ?""",
                    (slot["id"], target_date),
                ).fetchone()
                if existing:
                    continue
                sessions.append(
                    self.create_session_from_slot(slot["id"], target_date, created_by)
                )

            logger.info("Generated %d registers for %s (%s)", len(sessions), target_date, day_of_week)
            return sessions
        finally:
            conn.close()

    def get_session_by_slot(self, slot_id: int, session_date: str) -> dict | None:
        """Find a session linked to a specific timetable slot on a given date."""
        session_date = validate_date(session_date)
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT a.*, c.course_code, c.title as course_title
                   FROM attendance_sessions a JOIN courses c ON a.course_id = c.id
                   WHERE a.timetable_slot_id = ? AND a.session_date = ?""",
                (slot_id, session_date),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_attendance(self, record_id: int) -> bool:
        """Delete an attendance record by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM attendance_records WHERE id = ?", (record_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise AttendanceError(f"Attendance record {record_id} not found.")
            logger.info("Attendance record deleted: id=%d", record_id)
            return True
        except AttendanceError:
            raise
        except Exception as e:
            conn.rollback()
            raise AttendanceError(f"Failed to delete attendance record: {e}") from e
        finally:
            conn.close()

    def pre_populate_register(self, session_id: int) -> int:
        """Pre-populate a session with absent records for all enrolled students."""
        conn = self._conn()
        try:
            session = conn.execute(
                "SELECT * FROM attendance_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not session:
                raise AttendanceError("Session not found.")

            students = conn.execute(
                """SELECT s.id FROM students s
                   JOIN enrollments e ON s.id = e.student_id
                   WHERE e.course_id = ? AND e.status = 'enrolled'""",
                (session["course_id"],),
            ).fetchall()

            count = 0
            for s in students:
                existing = conn.execute(
                    "SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?",
                    (session_id, s["id"]),
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO attendance_records (session_id, student_id, status) VALUES (?, ?, 'absent')",
                        (session_id, s["id"]),
                    )
                    count += 1

            conn.commit()
            logger.info("Pre-populated %d absent records for session %d", count, session_id)
            return count
        except AttendanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AttendanceError(f"Failed to pre-populate register: {e}") from e
        finally:
            conn.close()
