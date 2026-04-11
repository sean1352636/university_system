"""T-Level Pathways service."""

from education_system.college_system.core.exceptions import TLevelError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class TLevelService:
    """T-Level Pathways service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_route(self, route_name: str, pathway: str | None = None,
                     awarding_body: str | None = None, glh_total: int = 1800,
                     industry_placement_hours: int = 315) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO tlevel_routes (route_name, pathway, awarding_body, glh_total, industry_placement_hours) VALUES (?, ?, ?, ?, ?)",
                (route_name, pathway, awarding_body, glh_total, industry_placement_hours),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM tlevel_routes WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise TLevelError(f"Failed to create route: {e}") from e
        finally:
            conn.close()

    def list_routes(self) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM tlevel_routes ORDER BY route_name").fetchall()]
        finally:
            conn.close()

    def enroll_student(self, student_id: int, route_id: int, academic_year: str | None = None,
                       occupational_specialism: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO tlevel_enrollments (student_id, route_id, academic_year, occupational_specialism)
                   VALUES (?, ?, ?, ?)""",
                (student_id, route_id, academic_year, occupational_specialism),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM tlevel_enrollments WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise TLevelError(f"Failed to enroll student: {e}") from e
        finally:
            conn.close()

    def list_enrollments(self, route_id: int | None = None, student_id: int | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT e.*, s.first_name, s.last_name, s.student_id as sid, r.route_name FROM tlevel_enrollments e JOIN students s ON e.student_id = s.id JOIN tlevel_routes r ON e.route_id = r.id WHERE 1=1"
            params: list = []
            if route_id:
                sql += " AND e.route_id = ?"
                params.append(route_id)
            if student_id:
                sql += " AND e.student_id = ?"
                params.append(student_id)
            sql += " ORDER BY e.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_enrollment(self, enrollment_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM tlevel_enrollments WHERE id = ?", (enrollment_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_enrollment(self, enrollment_id: int, **updates) -> dict:
        set_parts: list[str] = []
        vals: list = []
        for col in ("core_grade", "notes", "overall_grade", "placement_employer",
                    "placement_end_date", "placement_hours_completed",
                    "placement_start_date", "placement_status", "specialism_grade",
                    "status"):
            if col in updates and updates[col] is not None:
                set_parts.append(f"{col} = ?")
                vals.append(updates[col])
        conn = self._conn()
        try:
            sets = ", ".join(set_parts)
            vals.append(enrollment_id)
            conn.execute(f"UPDATE tlevel_enrollments SET {sets}, updated_at = datetime('now') WHERE id = ?", vals)
            conn.commit()
            return self.get_enrollment(enrollment_id)
        except Exception as e:
            conn.rollback()
            raise TLevelError(f"Failed to update enrollment: {e}") from e
        finally:
            conn.close()

    def log_placement(self, enrollment_id: int, log_date: str, hours: float,
                      activity: str | None = None, supervisor_feedback: str | None = None,
                      student_reflection: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO tlevel_placement_logs (enrollment_id, log_date, hours, activity, supervisor_feedback, student_reflection)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (enrollment_id, log_date, hours, activity, supervisor_feedback, student_reflection),
            )
            conn.commit()
            # Update hours completed
            total = conn.execute("SELECT SUM(hours) as t FROM tlevel_placement_logs WHERE enrollment_id = ?", (enrollment_id,)).fetchone()["t"] or 0
            conn.execute("UPDATE tlevel_enrollments SET placement_hours_completed = ? WHERE id = ?", (int(total), enrollment_id))
            conn.commit()
            row = conn.execute("SELECT * FROM tlevel_placement_logs WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise TLevelError(f"Failed to log placement: {e}") from e
        finally:
            conn.close()

    def list_placement_logs(self, enrollment_id: int) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tlevel_placement_logs WHERE enrollment_id = ? ORDER BY log_date DESC",
                (enrollment_id,)).fetchall()]
        finally:
            conn.close()

