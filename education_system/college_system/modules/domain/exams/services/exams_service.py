"""Exams service for managing exam entries, timetables, access, and results."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import ExamsError


class ExamsService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Exam Entries ---

    def create_entry(self, student_id: int, course_id: int, exam_board: str,
                      qualification: str, unit_code: str = None,
                      exam_series: str = None, entry_date: str = None,
                      tier: str = None, fee: float = 0,
                      status: str = "planned") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO exam_entries
                   (student_id, course_id, exam_board, qualification,
                    unit_code, exam_series, entry_date, tier, fee, status)
                   VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, date('now')), ?, ?, ?)""",
                (student_id, course_id, exam_board, qualification,
                 unit_code, exam_series, entry_date, tier, fee, status),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM exam_entries WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ExamsError(f"Failed to create exam entry: {e}")
        finally:
            conn.close()

    def list_entries(self, student_id: int = None, exam_series: str = None,
                      limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT ee.*, s.first_name, s.last_name FROM exam_entries ee
                       LEFT JOIN students s ON ee.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                query += " AND ee.student_id = ?"
                params.append(student_id)
            if exam_series:
                query += " AND ee.exam_series = ?"
                params.append(exam_series)
            query += " ORDER BY ee.id LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_entry_status(self, entry_id: int, status: str) -> dict:
        conn = self._conn()
        try:
            conn.execute("UPDATE exam_entries SET status = ? WHERE id = ?", (status, entry_id))
            conn.commit()
            row = conn.execute("SELECT * FROM exam_entries WHERE id = ?", (entry_id,)).fetchone()
            if not row:
                raise ExamsError(f"Entry {entry_id} not found")
            return dict(row)
        finally:
            conn.close()

    def delete_exam(self, exam_id: int) -> bool:
        """Delete an exam entry by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM exam_entries WHERE id = ?", (exam_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise ExamsError(f"Exam entry {exam_id} not found.")
            return True
        except ExamsError:
            raise
        except Exception as e:
            conn.rollback()
            raise ExamsError(f"Failed to delete exam entry: {e}")
        finally:
            conn.close()

    # --- Exam Timetable ---

    def create_timetable_slot(self, exam_entry_id: int, exam_date: str,
                                start_time: str, duration_minutes: int,
                                room: str = None, seat_number: str = None,
                                invigilator: str = None, notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO exam_timetable
                   (exam_entry_id, exam_date, start_time, duration_minutes,
                    room, seat_number, invigilator, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (exam_entry_id, exam_date, start_time, duration_minutes,
                 room, seat_number, invigilator, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM exam_timetable WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ExamsError(f"Failed to create timetable slot: {e}")
        finally:
            conn.close()

    def list_timetable(self, exam_date: str = None) -> list[dict]:
        conn = self._conn()
        try:
            if exam_date:
                rows = conn.execute(
                    "SELECT * FROM exam_timetable WHERE exam_date = ? ORDER BY start_time",
                    (exam_date,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM exam_timetable ORDER BY exam_date, start_time"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # --- Results ---

    def record_result(self, student_id: int, course_id: int, exam_board: str,
                       qualification: str, grade: str,
                       unit_code: str = None, ums_score: int = None,
                       raw_mark: int = None, max_mark: int = None,
                       series: str = None, result_date: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO exam_results
                   (student_id, course_id, exam_board, qualification,
                    grade, unit_code, ums_score, raw_mark, max_mark,
                    series, result_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, course_id, exam_board, qualification,
                 grade, unit_code, ums_score, raw_mark, max_mark,
                 series, result_date),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM exam_results WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ExamsError(f"Failed to record result: {e}")
        finally:
            conn.close()

    def list_results(self, student_id: int = None, series: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT er.*, s.first_name, s.last_name FROM exam_results er
                       LEFT JOIN students s ON er.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                query += " AND er.student_id = ?"
                params.append(student_id)
            if series:
                query += " AND er.series = ?"
                params.append(series)
            query += " ORDER BY er.id"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_results(self, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM exam_results WHERE student_id = ?
                   ORDER BY result_date DESC""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
