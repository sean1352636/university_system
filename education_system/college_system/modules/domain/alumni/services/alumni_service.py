"""Alumni Network service for managing alumni records, events, and surveys."""

from education_system.college_system.core.exceptions import AlumniError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import escape_like
import logging

logger = logging.getLogger(__name__)


class AlumniService:
    """Alumni Network service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ---- Alumni Records ----

    def create_record(self, first_name: str, last_name: str, *,
                      student_id: int = None, email: str = None,
                      phone: str = None, graduation_year: str = None,
                      courses_studied: str = None, current_employer: str = None,
                      current_role: str = None, further_education: str = None,
                      university_attended: str = None, degree_achieved: str = None,
                      willing_to_mentor: int = 0, willing_to_speak: int = 0,
                      consent_to_contact: int = 1, notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO alumni_records
                   (student_id, first_name, last_name, email, phone,
                    graduation_year, courses_studied, current_employer,
                    current_role, further_education, university_attended,
                    degree_achieved, willing_to_mentor, willing_to_speak,
                    consent_to_contact, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, first_name, last_name, email, phone,
                 graduation_year, courses_studied, current_employer,
                 current_role, further_education, university_attended,
                 degree_achieved, willing_to_mentor, willing_to_speak,
                 consent_to_contact, notes))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM alumni_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise AlumniError(f"Failed to create alumni record: {e}") from e
        finally:
            conn.close()

    def list_records(self, *, graduation_year: str = None,
                     willing_to_mentor: int = None,
                     willing_to_speak: int = None,
                     search: str = None,
                     limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM alumni_records WHERE 1=1"
            params: list = []
            if graduation_year:
                sql += " AND graduation_year = ?"
                params.append(graduation_year)
            if willing_to_mentor is not None:
                sql += " AND willing_to_mentor = ?"
                params.append(willing_to_mentor)
            if willing_to_speak is not None:
                sql += " AND willing_to_speak = ?"
                params.append(willing_to_speak)
            if search:
                sql += " AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR current_employer LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term, term])
            sql += " ORDER BY last_name, first_name LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_record(self, record_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM alumni_records WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_record(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "first_name", "last_name", "email", "phone",
                "graduation_year", "courses_studied", "current_employer",
                "current_role", "further_education", "university_attended",
                "degree_achieved", "willing_to_mentor", "willing_to_speak",
                "consent_to_contact", "last_contacted", "notes",
            }
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise AlumniError("No valid fields to update.")
            params.append(record_id)
            conn.execute(
                f"UPDATE alumni_records SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_record(record_id)
        except AlumniError:
            raise
        except Exception as e:
            conn.rollback()
            raise AlumniError(f"Failed to update alumni record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, record_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM alumni_surveys WHERE alumni_id = ?", (record_id,))
            conn.execute("DELETE FROM alumni_records WHERE id = ?", (record_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise AlumniError(f"Failed to delete alumni record: {e}") from e
        finally:
            conn.close()

    # ---- Alumni Events ----

    def create_event(self, event_name: str, event_date: str, *,
                     event_type: str = "reunion", description: str = None,
                     location: str = None, status: str = "planned") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO alumni_events
                   (event_name, event_date, event_type, description, location, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_name, event_date, event_type, description, location, status))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM alumni_events WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise AlumniError(f"Failed to create event: {e}") from e
        finally:
            conn.close()

    def list_events(self, *, event_type: str = None,
                    status: str = None, limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM alumni_events WHERE 1=1"
            params: list = []
            if event_type:
                sql += " AND event_type = ?"
                params.append(event_type)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY event_date DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_event(self, event_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM alumni_events WHERE id = ?", (event_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_event(self, event_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"event_name", "event_date", "event_type",
                        "description", "location", "attendee_count", "status"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise AlumniError("No valid fields to update.")
            params.append(event_id)
            conn.execute(
                f"UPDATE alumni_events SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_event(event_id)
        except AlumniError:
            raise
        except Exception as e:
            conn.rollback()
            raise AlumniError(f"Failed to update event: {e}") from e
        finally:
            conn.close()

    def delete_event(self, event_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM alumni_events WHERE id = ?", (event_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise AlumniError(f"Failed to delete event: {e}") from e
        finally:
            conn.close()

    # ---- Alumni Surveys ----

    def create_survey(self, alumni_id: int, *,
                      survey_year: str = None, employment_status: str = None,
                      satisfaction_rating: int = None,
                      would_recommend: int = 1,
                      feedback: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO alumni_surveys
                   (alumni_id, survey_year, employment_status,
                    satisfaction_rating, would_recommend, feedback)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (alumni_id, survey_year, employment_status,
                 satisfaction_rating, would_recommend, feedback))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM alumni_surveys WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise AlumniError(f"Failed to create survey: {e}") from e
        finally:
            conn.close()

    def list_surveys(self, alumni_id: int = None, *,
                     survey_year: str = None, limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT s.*, a.first_name, a.last_name
                     FROM alumni_surveys s
                     LEFT JOIN alumni_records a ON s.alumni_id = a.id
                     WHERE 1=1"""
            params: list = []
            if alumni_id:
                sql += " AND s.alumni_id = ?"
                params.append(alumni_id)
            if survey_year:
                sql += " AND s.survey_year = ?"
                params.append(survey_year)
            sql += " ORDER BY s.created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_survey(self, survey_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM alumni_surveys WHERE id = ?", (survey_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise AlumniError(f"Failed to delete survey: {e}") from e
        finally:
            conn.close()

    # ---- Statistics ----

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM alumni_records").fetchone()[0]
            mentors = conn.execute(
                "SELECT COUNT(*) FROM alumni_records WHERE willing_to_mentor = 1"
            ).fetchone()[0]
            speakers = conn.execute(
                "SELECT COUNT(*) FROM alumni_records WHERE willing_to_speak = 1"
            ).fetchone()[0]
            at_uni = conn.execute(
                "SELECT COUNT(*) FROM alumni_records WHERE university_attended IS NOT NULL AND university_attended != ''"
            ).fetchone()[0]
            employed = conn.execute(
                "SELECT COUNT(*) FROM alumni_records WHERE current_employer IS NOT NULL AND current_employer != ''"
            ).fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM alumni_events").fetchone()[0]
            surveys = conn.execute("SELECT COUNT(*) FROM alumni_surveys").fetchone()[0]
            avg_sat = conn.execute(
                "SELECT AVG(satisfaction_rating) FROM alumni_surveys WHERE satisfaction_rating IS NOT NULL"
            ).fetchone()[0]
            return {
                "total_alumni": total,
                "willing_to_mentor": mentors,
                "willing_to_speak": speakers,
                "at_university": at_uni,
                "employed": employed,
                "total_events": events,
                "total_surveys": surveys,
                "avg_satisfaction": round(avg_sat, 1) if avg_sat else None,
            }
        finally:
            conn.close()
