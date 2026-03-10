"""Reading record service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import ReadingRecordError
import traceback

logger = logging.getLogger(__name__)


class ReadingRecordService:
    """CRUD operations for reading records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_reading(self, pupil_id, book_title=None, book_level=None,
                       pages_read=None, reading_date=None, read_with="Independent",
                       fluency=None, comprehension=None, comments=None,
                       recorded_by=None):
        if not pupil_id:
            raise ReadingRecordError("Pupil ID is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO reading_records (
                    pupil_id, book_title, book_level, pages_read, reading_date,
                    read_with, fluency, comprehension, comments, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pupil_id, book_title, book_level, pages_read, reading_date,
                 read_with, fluency, comprehension, comments, recorded_by),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info("Recorded reading %d for pupil %s: %s",
                        record_id, pupil_id, book_title or "(no title)")
            return {"record_id": record_id, "pupil_id": pupil_id,
                    "book_title": book_title}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ReadingRecordError(f"Failed to record reading: {e}") from e
        finally:
            conn.close()

    def get_records(self, pupil_id=None, date_from=None, date_to=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM reading_records WHERE 1=1"
            params = []
            if pupil_id is not None:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if date_from is not None:
                sql += " AND reading_date >= ?"
                params.append(date_from)
            if date_to is not None:
                sql += " AND reading_date <= ?"
                params.append(date_to)
            sql += " ORDER BY reading_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_record(self, record_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"book_title", "book_level", "pages_read", "reading_date",
                       "read_with", "fluency", "comprehension", "comments",
                       "recorded_by"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(record_id)
            cursor.execute(
                f"UPDATE reading_records SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            logger.info("Updated reading record: %d", record_id)
            cursor.execute("SELECT * FROM reading_records WHERE id = ?",
                           (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ReadingRecordError(f"Failed to update reading record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, record_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM reading_records WHERE id = ?", (record_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted reading record: %d", record_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ReadingRecordError(f"Failed to delete reading record: {e}") from e
        finally:
            conn.close()
