"""Student Wellbeing service layer."""

from education_system.college_system.core.exceptions import StudentWellbeingError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class StudentWellbeingService:
    """Service for managing wellbeing referrals, logs, and counselling sessions."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        conn = connect(self._db_path)
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        return conn

    # ================================================================
    # Referrals
    # ================================================================

    def list_referrals(self, status: str | None = None,
                       risk_level: str | None = None,
                       concern_category: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT r.*, s.first_name, s.last_name
                     FROM wellbeing_referrals r
                     LEFT JOIN students s ON r.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if status:
                sql += " AND r.status = ?"
                params.append(status)
            if risk_level:
                sql += " AND r.risk_level = ?"
                params.append(risk_level)
            if concern_category:
                sql += " AND r.concern_category = ?"
                params.append(concern_category)
            sql += " ORDER BY r.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_referral(self, referral_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT r.*, s.first_name, s.last_name
                   FROM wellbeing_referrals r
                   LEFT JOIN students s ON r.student_id = s.id
                   WHERE r.id = ?""", (referral_id,)
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_referral(self, student_id: int, concern_details: str, **kwargs) -> dict:
        allowed = {"referred_by", "referral_type", "concern_category",
                    "risk_level", "service_referred_to", "external_agency",
                    "consent_obtained", "appointment_date", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        fields["student_id"] = student_id
        fields["concern_details"] = concern_details
        conn = self._conn()
        try:
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO wellbeing_referrals ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            logger.info("Referral created: student=%d", student_id)
            row = conn.execute(
                "SELECT * FROM wellbeing_referrals WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to create referral: {e}") from e
        finally:
            conn.close()

    def update_referral(self, referral_id: int, **kwargs) -> dict:
        allowed = {"referral_type", "concern_category", "concern_details",
                    "risk_level", "service_referred_to", "external_agency",
                    "consent_obtained", "appointment_date", "outcome", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudentWellbeingError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM wellbeing_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            if not existing:
                raise StudentWellbeingError("Referral not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE wellbeing_referrals SET {set_parts}, updated_at = datetime('now') WHERE id = ?",
                (*updates.values(), referral_id),
            )
            conn.commit()
            logger.info("Referral updated: id=%d", referral_id)
            row = conn.execute(
                "SELECT * FROM wellbeing_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            return row
        except StudentWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to update referral: {e}") from e
        finally:
            conn.close()

    def delete_referral(self, referral_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM wellbeing_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            if not existing:
                raise StudentWellbeingError("Referral not found.")
            conn.execute("DELETE FROM wellbeing_referrals WHERE id = ?", (referral_id,))
            conn.commit()
            logger.info("Referral deleted: id=%d", referral_id)
            return True
        except StudentWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to delete referral: {e}") from e
        finally:
            conn.close()

    def resolve_referral(self, referral_id: int, outcome: str) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM wellbeing_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            if not existing:
                raise StudentWellbeingError("Referral not found.")
            conn.execute(
                """UPDATE wellbeing_referrals
                   SET status = 'resolved', outcome = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (outcome, referral_id),
            )
            conn.commit()
            logger.info("Referral resolved: id=%d", referral_id)
            row = conn.execute(
                "SELECT * FROM wellbeing_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            return row
        except StudentWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to resolve referral: {e}") from e
        finally:
            conn.close()

    # ================================================================
    # Wellbeing Logs
    # ================================================================

    def list_logs(self, student_id: int | None = None,
                  follow_up_needed: int | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT l.*, s.first_name, s.last_name
                     FROM wellbeing_logs l
                     LEFT JOIN students s ON l.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if student_id:
                sql += " AND l.student_id = ?"
                params.append(student_id)
            if follow_up_needed is not None:
                sql += " AND l.follow_up_needed = ?"
                params.append(follow_up_needed)
            sql += " ORDER BY l.log_date DESC, l.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_log(self, log_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT l.*, s.first_name, s.last_name
                   FROM wellbeing_logs l
                   LEFT JOIN students s ON l.student_id = s.id
                   WHERE l.id = ?""", (log_id,)
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_log(self, student_id: int, **kwargs) -> dict:
        allowed = {"logged_by", "log_date", "mood_rating", "anxiety_level",
                    "sleep_quality", "notes", "follow_up_needed"}
        fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        fields["student_id"] = student_id
        conn = self._conn()
        try:
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO wellbeing_logs ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            logger.info("Wellbeing log created: student=%d", student_id)
            row = conn.execute(
                "SELECT * FROM wellbeing_logs WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to create log: {e}") from e
        finally:
            conn.close()

    def update_log(self, log_id: int, **kwargs) -> dict:
        allowed = {"mood_rating", "anxiety_level", "sleep_quality",
                    "notes", "follow_up_needed", "log_date"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudentWellbeingError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM wellbeing_logs WHERE id = ?", (log_id,)
            ).fetchone()
            if not existing:
                raise StudentWellbeingError("Wellbeing log not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE wellbeing_logs SET {set_parts} WHERE id = ?",
                (*updates.values(), log_id),
            )
            conn.commit()
            logger.info("Wellbeing log updated: id=%d", log_id)
            row = conn.execute(
                "SELECT * FROM wellbeing_logs WHERE id = ?", (log_id,)
            ).fetchone()
            return row
        except StudentWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to update log: {e}") from e
        finally:
            conn.close()

    def delete_log(self, log_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM wellbeing_logs WHERE id = ?", (log_id,)
            ).fetchone()
            if not existing:
                raise StudentWellbeingError("Wellbeing log not found.")
            conn.execute("DELETE FROM wellbeing_logs WHERE id = ?", (log_id,))
            conn.commit()
            logger.info("Wellbeing log deleted: id=%d", log_id)
            return True
        except StudentWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to delete log: {e}") from e
        finally:
            conn.close()

    # ================================================================
    # Counselling Sessions
    # ================================================================

    def list_sessions(self, student_id: int | None = None,
                      status: str | None = None,
                      session_type: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT cs.*, s.first_name, s.last_name
                     FROM counselling_sessions cs
                     LEFT JOIN students s ON cs.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if student_id:
                sql += " AND cs.student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND cs.status = ?"
                params.append(status)
            if session_type:
                sql += " AND cs.session_type = ?"
                params.append(session_type)
            sql += " ORDER BY cs.session_date DESC, cs.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_session(self, session_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT cs.*, s.first_name, s.last_name
                   FROM counselling_sessions cs
                   LEFT JOIN students s ON cs.student_id = s.id
                   WHERE cs.id = ?""", (session_id,)
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_session(self, student_id: int, session_date: str, **kwargs) -> dict:
        allowed = {"counsellor_id", "session_number", "session_type",
                    "presenting_issues", "session_notes", "risk_assessment",
                    "next_appointment", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        fields["student_id"] = student_id
        fields["session_date"] = session_date
        conn = self._conn()
        try:
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO counselling_sessions ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            logger.info("Counselling session created: student=%d date=%s", student_id, session_date)
            row = conn.execute(
                "SELECT * FROM counselling_sessions WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to create session: {e}") from e
        finally:
            conn.close()

    def update_session(self, session_id: int, **kwargs) -> dict:
        allowed = {"counsellor_id", "session_date", "session_number",
                    "session_type", "presenting_issues", "session_notes",
                    "risk_assessment", "next_appointment", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudentWellbeingError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM counselling_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not existing:
                raise StudentWellbeingError("Counselling session not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE counselling_sessions SET {set_parts} WHERE id = ?",
                (*updates.values(), session_id),
            )
            conn.commit()
            logger.info("Counselling session updated: id=%d", session_id)
            row = conn.execute(
                "SELECT * FROM counselling_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return row
        except StudentWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to update session: {e}") from e
        finally:
            conn.close()

    def delete_session(self, session_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM counselling_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not existing:
                raise StudentWellbeingError("Counselling session not found.")
            conn.execute("DELETE FROM counselling_sessions WHERE id = ?", (session_id,))
            conn.commit()
            logger.info("Counselling session deleted: id=%d", session_id)
            return True
        except StudentWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentWellbeingError(f"Failed to delete session: {e}") from e
        finally:
            conn.close()

    # ================================================================
    # Reporting
    # ================================================================

    def get_student_wellbeing(self, student_id: int) -> dict:
        """Return all referrals, logs, and sessions for a student."""
        conn = self._conn()
        try:
            referrals = conn.execute(
                "SELECT * FROM wellbeing_referrals WHERE student_id = ? ORDER BY created_at DESC",
                (student_id,),
            ).fetchall()
            logs = conn.execute(
                "SELECT * FROM wellbeing_logs WHERE student_id = ? ORDER BY log_date DESC",
                (student_id,),
            ).fetchall()
            sessions = conn.execute(
                "SELECT * FROM counselling_sessions WHERE student_id = ? ORDER BY session_date DESC",
                (student_id,),
            ).fetchall()
            student = conn.execute(
                "SELECT first_name, last_name FROM students WHERE id = ?",
                (student_id,),
            ).fetchone()
            name = f"{student['first_name']} {student['last_name']}" if student else "Unknown"
            return {
                "student_id": student_id,
                "student_name": name,
                "referrals": referrals,
                "total_referrals": len(referrals),
                "open_referrals": sum(1 for r in referrals if r["status"] in ("open", "in_progress")),
                "logs": logs,
                "total_logs": len(logs),
                "sessions": sessions,
                "total_sessions": len(sessions),
            }
        finally:
            conn.close()

    def get_high_risk_students(self) -> list[dict]:
        """Return open referrals with high or critical risk level."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT r.*, s.first_name, s.last_name
                   FROM wellbeing_referrals r
                   LEFT JOIN students s ON r.student_id = s.id
                   WHERE r.risk_level IN ('high', 'critical')
                   AND r.status IN ('open', 'in_progress')
                   ORDER BY CASE r.risk_level WHEN 'critical' THEN 0 ELSE 1 END,
                            r.created_at DESC"""
            ).fetchall()
            return rows
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """Return comprehensive wellbeing statistics."""
        conn = self._conn()
        try:
            # Referral stats
            total_referrals = conn.execute(
                "SELECT COUNT(*) as cnt FROM wellbeing_referrals"
            ).fetchone()["cnt"]
            open_referrals = conn.execute(
                "SELECT COUNT(*) as cnt FROM wellbeing_referrals WHERE status = 'open'"
            ).fetchone()["cnt"]

            by_status_rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM wellbeing_referrals GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in by_status_rows}

            by_risk_rows = conn.execute(
                "SELECT risk_level, COUNT(*) as cnt FROM wellbeing_referrals GROUP BY risk_level"
            ).fetchall()
            by_risk_level = {r["risk_level"]: r["cnt"] for r in by_risk_rows}

            by_cat_rows = conn.execute(
                "SELECT concern_category, COUNT(*) as cnt FROM wellbeing_referrals WHERE concern_category IS NOT NULL GROUP BY concern_category"
            ).fetchall()
            by_category = {r["concern_category"]: r["cnt"] for r in by_cat_rows}

            high_risk_count = conn.execute(
                """SELECT COUNT(*) as cnt FROM wellbeing_referrals
                   WHERE risk_level IN ('high', 'critical')
                   AND status IN ('open', 'in_progress')"""
            ).fetchone()["cnt"]

            # Log stats
            total_logs = conn.execute(
                "SELECT COUNT(*) as cnt FROM wellbeing_logs"
            ).fetchone()["cnt"]
            follow_ups_needed = conn.execute(
                "SELECT COUNT(*) as cnt FROM wellbeing_logs WHERE follow_up_needed = 1"
            ).fetchone()["cnt"]
            avg_mood_row = conn.execute(
                "SELECT AVG(mood_rating) as avg_mood FROM wellbeing_logs WHERE mood_rating IS NOT NULL"
            ).fetchone()
            avg_mood = round(avg_mood_row["avg_mood"], 1) if avg_mood_row["avg_mood"] else 0.0

            # Session stats
            total_sessions = conn.execute(
                "SELECT COUNT(*) as cnt FROM counselling_sessions"
            ).fetchone()["cnt"]
            by_type_rows = conn.execute(
                "SELECT session_type, COUNT(*) as cnt FROM counselling_sessions GROUP BY session_type"
            ).fetchall()
            by_session_type = {r["session_type"]: r["cnt"] for r in by_type_rows}

            return {
                "total_referrals": total_referrals,
                "open_referrals": open_referrals,
                "by_status": by_status,
                "by_risk_level": by_risk_level,
                "by_category": by_category,
                "high_risk_count": high_risk_count,
                "total_logs": total_logs,
                "follow_ups_needed": follow_ups_needed,
                "total_sessions": total_sessions,
                "by_session_type": by_session_type,
                "avg_mood": avg_mood,
            }
        finally:
            conn.close()
