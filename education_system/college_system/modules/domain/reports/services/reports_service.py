"""Reports service for managing progress reports and report entries."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import ReportsError


class ReportsService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Progress Reports ---

    def create_report(self, title: str, report_type: str = "interim",
                       academic_year: str = None, term: str = None,
                       due_date: str = None, created_by: int = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO progress_reports
                   (title, report_type, academic_year, term, due_date, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, report_type, academic_year, term, due_date, created_by),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM progress_reports WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ReportsError(f"Failed to create report: {e}")
        finally:
            conn.close()

    def list_reports(self, status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM progress_reports WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM progress_reports ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_report(self, report_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM progress_reports WHERE id = ?", (report_id,)
            ).fetchone()
            if not row:
                raise ReportsError(f"Report {report_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_report_status(self, report_id: int, status: str) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE progress_reports SET status = ? WHERE id = ?",
                (status, report_id),
            )
            conn.commit()
            return self.get_report(report_id)
        except ReportsError:
            raise
        except Exception as e:
            raise ReportsError(f"Failed to update report: {e}")
        finally:
            conn.close()

    # --- Report Entries ---

    def add_entry(self, report_id: int, student_id: int, course_id: int,
                   teacher_id: int, current_grade: str = None,
                   target_grade: str = None, effort_grade: str = None,
                   attendance_pct: float = None, comment: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO report_entries
                   (report_id, student_id, course_id, teacher_id,
                    current_grade, target_grade, effort_grade, attendance_pct, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (report_id, student_id, course_id, teacher_id,
                 current_grade, target_grade, effort_grade, attendance_pct, comment),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM report_entries WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise ReportsError(f"Failed to add report entry: {e}")
        finally:
            conn.close()

    def list_entries(self, report_id: int, student_id: int = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT re.*, s.first_name, s.last_name, c.course_name
                       FROM report_entries re
                       LEFT JOIN students s ON re.student_id = s.id
                       LEFT JOIN courses c ON re.course_id = c.id
                       WHERE re.report_id = ?"""
            params = [report_id]
            if student_id:
                query += " AND re.student_id = ?"
                params.append(student_id)
            query += " ORDER BY s.last_name, c.course_name"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_entry(self, entry_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"current_grade", "target_grade", "effort_grade",
                        "attendance_pct", "comment"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise ReportsError("No valid fields to update")
            params.append(entry_id)
            conn.execute(f"UPDATE report_entries SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM report_entries WHERE id = ?", (entry_id,)).fetchone()
            return dict(row) if row else {}
        except ReportsError:
            raise
        except Exception as e:
            raise ReportsError(f"Failed to update entry: {e}")
        finally:
            conn.close()

    def get_student_report(self, report_id: int, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT re.*, c.course_name FROM report_entries re
                   LEFT JOIN courses c ON re.course_id = c.id
                   WHERE re.report_id = ? AND re.student_id = ?
                   ORDER BY c.course_name""",
                (report_id, student_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
