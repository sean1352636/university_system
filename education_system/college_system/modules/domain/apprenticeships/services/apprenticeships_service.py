"""Apprenticeships service."""

from education_system.college_system.core.exceptions import ApprenticeshipError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class ApprenticeshipService:
    """Apprenticeships service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_standard(self, standard_name: str, level: int, sector: str | None = None,
                        duration_months: int = 12, epa_provider: str | None = None,
                        off_the_job_hours: int = 0) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO apprenticeship_standards (standard_name, level, sector, duration_months, epa_provider, off_the_job_hours) VALUES (?, ?, ?, ?, ?, ?)",
                (standard_name, level, sector, duration_months, epa_provider, off_the_job_hours),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM apprenticeship_standards WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ApprenticeshipError(f"Failed to create standard: {e}") from e
        finally:
            conn.close()

    def list_standards(self) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM apprenticeship_standards ORDER BY standard_name").fetchall()]
        finally:
            conn.close()

    def enroll(self, student_id: int, standard_id: int, employer_name: str,
               employer_contact: str | None = None, start_date: str | None = None,
               expected_end_date: str | None = None, otj_hours_target: int = 0) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO apprenticeship_enrollments
                   (student_id, standard_id, employer_name, employer_contact, start_date, expected_end_date, otj_hours_target)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, standard_id, employer_name, employer_contact, start_date, expected_end_date, otj_hours_target),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM apprenticeship_enrollments WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ApprenticeshipError(f"Failed to enroll: {e}") from e
        finally:
            conn.close()

    def list_enrollments(self, standard_id: int | None = None, status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT e.*, s.first_name, s.last_name, s.student_id as sid, st.standard_name
                     FROM apprenticeship_enrollments e
                     JOIN students s ON e.student_id = s.id
                     JOIN apprenticeship_standards st ON e.standard_id = st.id WHERE 1=1"""
            params: list = []
            if standard_id:
                sql += " AND e.standard_id = ?"
                params.append(standard_id)
            if status:
                sql += " AND e.status = ?"
                params.append(status)
            sql += " ORDER BY e.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_enrollment(self, enrollment_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM apprenticeship_enrollments WHERE id = ?", (enrollment_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_enrollment(self, enrollment_id: int, **updates) -> dict:
        allowed = {"employer_name", "employer_contact", "expected_end_date", "epa_status",
                    "epa_grade", "gateway_met", "progress_review_date", "status", "notes"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [enrollment_id]
            conn.execute(f"UPDATE apprenticeship_enrollments SET {sets}, updated_at = datetime('now') WHERE id = ?", vals)
            conn.commit()
            return self.get_enrollment(enrollment_id)
        except Exception as e:
            conn.rollback()
            raise ApprenticeshipError(f"Failed to update: {e}") from e
        finally:
            conn.close()

    def log_otj(self, enrollment_id: int, log_date: str, hours: float,
                activity_type: str | None = None, description: str | None = None,
                evidence: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO apprenticeship_otj_log (enrollment_id, log_date, hours, activity_type, description, evidence) VALUES (?, ?, ?, ?, ?, ?)",
                (enrollment_id, log_date, hours, activity_type, description, evidence),
            )
            conn.commit()
            total = conn.execute("SELECT SUM(hours) as t FROM apprenticeship_otj_log WHERE enrollment_id = ?", (enrollment_id,)).fetchone()["t"] or 0
            conn.execute("UPDATE apprenticeship_enrollments SET otj_hours_completed = ? WHERE id = ?", (int(total), enrollment_id))
            conn.commit()
            row = conn.execute("SELECT * FROM apprenticeship_otj_log WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ApprenticeshipError(f"Failed to log OTJ: {e}") from e
        finally:
            conn.close()

    def list_otj_logs(self, enrollment_id: int) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM apprenticeship_otj_log WHERE enrollment_id = ? ORDER BY log_date DESC",
                (enrollment_id,)).fetchall()]
        finally:
            conn.close()

    def add_review(self, enrollment_id: int, review_date: str, reviewer_id: int | None = None,
                   employer_present: bool = False, progress_summary: str | None = None,
                   targets_set: str | None = None, concerns: str | None = None,
                   next_review_date: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO apprenticeship_reviews
                   (enrollment_id, review_date, reviewer_id, employer_present, progress_summary,
                    targets_set, concerns, next_review_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (enrollment_id, review_date, reviewer_id, int(employer_present),
                 progress_summary, targets_set, concerns, next_review_date),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM apprenticeship_reviews WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ApprenticeshipError(f"Failed to add review: {e}") from e
        finally:
            conn.close()

