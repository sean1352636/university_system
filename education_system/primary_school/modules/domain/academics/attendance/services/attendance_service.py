"""Attendance management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import AttendanceError
import traceback

logger = logging.getLogger(__name__)


class AttendanceService:
    """CRUD operations for attendance records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_attendance(self, pupil_id, date, session="AM", status="/",
                          note=None, recorded_by=None):
        if not pupil_id:
            raise AttendanceError("Pupil ID is required")
        if not date:
            raise AttendanceError("Date is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO attendance_records (
                    pupil_id, date, session, status, note, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (pupil_id, date, session, status, note, recorded_by),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info("Recorded attendance %d for pupil %s on %s (%s)",
                        record_id, pupil_id, date, session)
            return {"record_id": record_id, "pupil_id": pupil_id,
                    "date": date, "status": status}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AttendanceError(f"Failed to record attendance: {e}") from e
        finally:
            conn.close()

    def get_attendance(self, pupil_id=None, date=None, class_name=None,
                       session=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            if class_name is not None:
                sql = """SELECT ar.* FROM attendance_records ar
                         JOIN pupils p ON ar.pupil_id = p.pupil_id
                         WHERE 1=1"""
            else:
                sql = "SELECT * FROM attendance_records WHERE 1=1"
            params = []
            if pupil_id is not None:
                sql += " AND ar.pupil_id = ?" if class_name else " AND pupil_id = ?"
                params.append(pupil_id)
            if date is not None:
                sql += " AND ar.date = ?" if class_name else " AND date = ?"
                params.append(date)
            if class_name is not None:
                sql += " AND p.class_name = ?"
                params.append(class_name)
            if session is not None:
                sql += " AND ar.session = ?" if class_name else " AND session = ?"
                params.append(session)
            sql += " ORDER BY date DESC, session"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_attendance(self, record_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"status", "note", "recorded_by"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(record_id)
            cursor.execute(
                f"UPDATE attendance_records SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated attendance record: %d", record_id)
            cursor.execute("SELECT * FROM attendance_records WHERE id = ?",
                           (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AttendanceError(f"Failed to update attendance: {e}") from e
        finally:
            conn.close()

    def get_pupil_attendance_summary(self, pupil_id):
        """Return counts of present, absent, and late marks for a pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT
                       COUNT(*) AS total,
                       SUM(CASE WHEN status = '/' OR status = '\\' THEN 1 ELSE 0 END) AS present,
                       SUM(CASE WHEN status IN ('N', 'O') THEN 1 ELSE 0 END) AS absent_unauthorised,
                       SUM(CASE WHEN status IN ('I', 'M', 'C', 'E', 'H', 'R', 'S', 'T') THEN 1 ELSE 0 END) AS absent_authorised,
                       SUM(CASE WHEN status = 'L' THEN 1 ELSE 0 END) AS late,
                       SUM(CASE WHEN status = 'U' THEN 1 ELSE 0 END) AS late_after_register
                   FROM attendance_records WHERE pupil_id = ?""",
                (pupil_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_class_register(self, class_name, date):
        """Return the attendance register for a class on a given date."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT p.pupil_id, p.first_name, p.last_name,
                          ar.session, ar.status, ar.note, ar.id AS record_id
                   FROM pupils p
                   LEFT JOIN attendance_records ar
                       ON p.pupil_id = ar.pupil_id AND ar.date = ?
                   WHERE p.class_name = ?
                   ORDER BY p.last_name, p.first_name, ar.session""",
                (date, class_name),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
