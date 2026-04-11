"""Staff Recruitment service — job vacancies and applications."""

from education_system.college_system.core.exceptions import RecruitmentError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import escape_like
import logging

logger = logging.getLogger(__name__)


class RecruitmentService:
    """Service for managing job vacancies and applications."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Vacancies ──────────────────────────────────────────────────────

    def create_vacancy(self, job_title: str, department: str | None = None,
                       contract_type: str = "permanent", hours: str = "full-time",
                       salary_range: str | None = None, closing_date: str | None = None,
                       start_date: str | None = None, description: str | None = None,
                       person_spec: str | None = None,
                       hiring_manager_id: int | None = None,
                       status: str = "draft") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO job_vacancies
                   (job_title, department, contract_type, hours, salary_range,
                    closing_date, start_date, description, person_spec,
                    hiring_manager_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_title, department, contract_type, hours, salary_range,
                 closing_date, start_date, description, person_spec,
                 hiring_manager_id, status),
            )
            conn.commit()
            logger.info("Vacancy created: %s", job_title)
            row = conn.execute(
                "SELECT * FROM job_vacancies WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise RecruitmentError(f"Failed to create vacancy: {e}") from e
        finally:
            conn.close()

    def list_vacancies(self, status: str | None = None,
                       department: str | None = None,
                       contract_type: str | None = None,
                       search: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM job_vacancies WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if department:
                sql += " AND department = ?"
                params.append(department)
            if contract_type:
                sql += " AND contract_type = ?"
                params.append(contract_type)
            if search:
                sql += " AND (job_title LIKE ? OR description LIKE ?)"
                escaped = escape_like(search)
                params.extend([f"%{escaped}%", f"%{escaped}%"])
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_vacancy(self, vacancy_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM job_vacancies WHERE id = ?", (vacancy_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_vacancy(self, vacancy_id: int, **updates) -> dict:
        set_parts: list[str] = []
        vals: list = []
        for col in ("closing_date", "contract_type", "department", "description",
                    "hiring_manager_id", "hours", "job_title", "person_spec",
                    "salary_range", "start_date", "status"):
            if col in updates and updates[col] is not None:
                set_parts.append(f"{col} = ?")
                vals.append(updates[col])
        if not set_parts:
            raise RecruitmentError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM job_vacancies WHERE id = ?", (vacancy_id,)
            ).fetchone()
            if not existing:
                raise RecruitmentError("Vacancy not found.")
            set_clause = ", ".join(set_parts)
            vals.append(vacancy_id)
            conn.execute(
                f"UPDATE job_vacancies SET {set_clause}, updated_at = datetime('now') WHERE id = ?",  # nosec B608
                vals,
            )
            conn.commit()
            logger.info("Vacancy updated: id=%d", vacancy_id)
            row = conn.execute(
                "SELECT * FROM job_vacancies WHERE id = ?", (vacancy_id,)
            ).fetchone()
            return dict(row)
        except RecruitmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise RecruitmentError(f"Failed to update vacancy: {e}") from e
        finally:
            conn.close()

    def delete_vacancy(self, vacancy_id: int) -> bool:
        """Delete vacancy and cascade-delete its applications."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM job_vacancies WHERE id = ?", (vacancy_id,)
            ).fetchone()
            if not existing:
                raise RecruitmentError("Vacancy not found.")
            conn.execute(
                "DELETE FROM job_applications WHERE vacancy_id = ?", (vacancy_id,)
            )
            conn.execute(
                "DELETE FROM job_vacancies WHERE id = ?", (vacancy_id,)
            )
            conn.commit()
            logger.info("Vacancy deleted (cascaded): id=%d", vacancy_id)
            return True
        except RecruitmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise RecruitmentError(f"Failed to delete vacancy: {e}") from e
        finally:
            conn.close()

    def publish_vacancy(self, vacancy_id: int) -> dict:
        """Set vacancy status to 'open'."""
        return self.update_vacancy(vacancy_id, status="open")

    def close_vacancy(self, vacancy_id: int) -> dict:
        """Set vacancy status to 'closed'."""
        return self.update_vacancy(vacancy_id, status="closed")

    # ── Applications ───────────────────────────────────────────────────

    def create_application(self, vacancy_id: int, applicant_name: str,
                           email: str | None = None, phone: str | None = None,
                           cv_path: str | None = None,
                           cover_letter: str | None = None) -> dict:
        conn = self._conn()
        try:
            vac = conn.execute(
                "SELECT id FROM job_vacancies WHERE id = ?", (vacancy_id,)
            ).fetchone()
            if not vac:
                raise RecruitmentError("Vacancy not found.")
            conn.execute(
                """INSERT INTO job_applications
                   (vacancy_id, applicant_name, email, phone, cv_path, cover_letter)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (vacancy_id, applicant_name, email, phone, cv_path, cover_letter),
            )
            conn.commit()
            logger.info("Application created: %s for vacancy %d",
                        applicant_name, vacancy_id)
            row = conn.execute(
                "SELECT * FROM job_applications WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except RecruitmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise RecruitmentError(f"Failed to create application: {e}") from e
        finally:
            conn.close()

    def list_applications(self, vacancy_id: int | None = None,
                          status: str | None = None,
                          shortlisted: bool | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM job_applications WHERE 1=1"
            params: list = []
            if vacancy_id is not None:
                sql += " AND vacancy_id = ?"
                params.append(vacancy_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if shortlisted is not None:
                sql += " AND shortlisted = ?"
                params.append(1 if shortlisted else 0)
            sql += " ORDER BY application_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_application(self, application_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM job_applications WHERE id = ?", (application_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_application(self, application_id: int, **updates) -> dict:
        allowed = {"applicant_name", "email", "phone", "cv_path", "cover_letter",
                    "shortlisted", "interview_date", "interview_score",
                    "interview_notes", "references_received", "offer_made",
                    "offer_accepted", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise RecruitmentError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM job_applications WHERE id = ?", (application_id,)
            ).fetchone()
            if not existing:
                raise RecruitmentError("Application not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE job_applications SET {set_parts} WHERE id = ?",
                (*updates.values(), application_id),
            )
            conn.commit()
            logger.info("Application updated: id=%d", application_id)
            row = conn.execute(
                "SELECT * FROM job_applications WHERE id = ?", (application_id,)
            ).fetchone()
            return dict(row)
        except RecruitmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise RecruitmentError(f"Failed to update application: {e}") from e
        finally:
            conn.close()

    def delete_application(self, application_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM job_applications WHERE id = ?", (application_id,)
            ).fetchone()
            if not existing:
                raise RecruitmentError("Application not found.")
            conn.execute(
                "DELETE FROM job_applications WHERE id = ?", (application_id,)
            )
            conn.commit()
            logger.info("Application deleted: id=%d", application_id)
            return True
        except RecruitmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise RecruitmentError(f"Failed to delete application: {e}") from e
        finally:
            conn.close()

    def shortlist_application(self, application_id: int) -> dict:
        """Mark application as shortlisted and update status."""
        return self.update_application(application_id,
                                       shortlisted=1, status="shortlisted")

    def schedule_interview(self, application_id: int,
                           interview_date: str) -> dict:
        """Schedule an interview date and update status."""
        return self.update_application(application_id,
                                       interview_date=interview_date,
                                       status="interview_scheduled")

    def record_interview_score(self, application_id: int, score: float,
                               notes: str | None = None) -> dict:
        """Record interview score and optional notes."""
        updates = {"interview_score": score, "status": "interviewed"}
        if notes:
            updates["interview_notes"] = notes
        return self.update_application(application_id, **updates)

    def make_offer(self, application_id: int) -> dict:
        """Mark that an offer has been made."""
        return self.update_application(application_id,
                                       offer_made=1, status="offer_made")

    # ── Statistics ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            # Vacancy counts by status
            vac_rows = conn.execute(
                """SELECT status, COUNT(*) as cnt
                   FROM job_vacancies GROUP BY status"""
            ).fetchall()
            vacancies_by_status = {r["status"]: r["cnt"] for r in vac_rows}

            # Application totals
            app_row = conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN shortlisted = 1 THEN 1 ELSE 0 END) as shortlisted,
                          SUM(CASE WHEN offer_made = 1 THEN 1 ELSE 0 END) as offers_made,
                          SUM(CASE WHEN offer_accepted = 1 THEN 1 ELSE 0 END) as offers_accepted
                   FROM job_applications"""
            ).fetchone()

            return {
                "vacancies_by_status": vacancies_by_status,
                "total_vacancies": sum(vacancies_by_status.values()),
                "total_applications": app_row["total"],
                "shortlisted": app_row["shortlisted"],
                "offers_made": app_row["offers_made"],
                "offers_accepted": app_row["offers_accepted"],
            }
        finally:
            conn.close()
