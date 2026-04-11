"""Timetable management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import TimetableError
import traceback

logger = logging.getLogger(__name__)


class TimetableService:
    """CRUD operations for timetable slots."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_slot(self, class_name, subject_code, day_of_week, period,
                    start_time=None, end_time=None, room=None,
                    teacher_staff_id=None):
        if not class_name:
            raise TimetableError("Class name is required")
        if not subject_code:
            raise TimetableError("Subject code is required")
        if not day_of_week:
            raise TimetableError("Day of week is required")
        if not period:
            raise TimetableError("Period is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO timetable_slots (
                    class_name, subject_code, day_of_week, period,
                    start_time, end_time, room, teacher_staff_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (class_name, subject_code, day_of_week, period,
                 start_time, end_time, room, teacher_staff_id),
            )
            conn.commit()
            slot_id = cursor.lastrowid
            logger.info("Created timetable slot %d: %s %s %s P%s",
                        slot_id, class_name, subject_code, day_of_week, period)
            return {"slot_id": slot_id, "class_name": class_name,
                    "subject_code": subject_code, "day_of_week": day_of_week,
                    "period": period}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TimetableError(f"Failed to create timetable slot: {e}") from e
        finally:
            conn.close()

    def get_timetable(self, class_name=None, day_of_week=None,
                      teacher_staff_id=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM timetable_slots WHERE 1=1"
            params = []
            if class_name is not None:
                sql += " AND class_name = ?"
                params.append(class_name)
            if day_of_week is not None:
                sql += " AND day_of_week = ?"
                params.append(day_of_week)
            if teacher_staff_id is not None:
                sql += " AND teacher_staff_id = ?"
                params.append(teacher_staff_id)
            sql += " ORDER BY day_of_week, period"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_slot(self, slot_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            set_parts: list[str] = []
            values: list = []
            for col in ("class_name", "day_of_week", "end_time", "period",
                        "room", "start_time", "subject_code", "teacher_staff_id"):
                if col in kwargs:
                    set_parts.append(f"{col} = ?")
                    values.append(kwargs[col])
            if not set_parts:
                return None

            set_clause = ", ".join(set_parts)
            values.append(slot_id)
            cursor.execute(
                f"UPDATE timetable_slots SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            logger.info("Updated timetable slot: %d", slot_id)
            cursor.execute("SELECT * FROM timetable_slots WHERE id = ?",
                           (slot_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TimetableError(f"Failed to update timetable slot: {e}") from e
        finally:
            conn.close()

    def delete_slot(self, slot_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM timetable_slots WHERE id = ?", (slot_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted timetable slot: %d", slot_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TimetableError(f"Failed to delete timetable slot: {e}") from e
        finally:
            conn.close()
