"""Destination tracking and NEET risk service."""

from education_system.college_system.core.exceptions import DestinationError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class DestinationService:
    """Service for managing student destinations and NEET risk assessment."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_destination(self, student_id: int, academic_year: str | None = None,
                           intended_destination: str | None = None,
                           destination_type: str = "unknown",
                           institution_name: str | None = None,
                           course_title: str | None = None,
                           notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO destinations
                   (student_id, academic_year, intended_destination, destination_type,
                    institution_name, course_title, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, academic_year, intended_destination, destination_type,
                 institution_name, course_title, notes),
            )
            conn.commit()
            logger.info("Destination created: student=%d type=%s", student_id, destination_type)
            row = conn.execute("SELECT * FROM destinations WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise DestinationError(f"Failed to create destination: {e}") from e
        finally:
            conn.close()

    def list_destinations(self, academic_year: str | None = None,
                          destination_type: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM destinations WHERE 1=1"
            params: list = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            if destination_type:
                sql += " AND destination_type = ?"
                params.append(destination_type)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_destination(self, dest_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_destination(self, dest_id: int, **updates) -> dict:
        set_parts: list[str] = []
        vals: list = []
        for col in ("confirmed_destination", "contact_made", "course_title",
                    "destination_type", "institution_name", "intended_destination",
                    "neet_risk", "notes"):
            if col in updates and updates[col] is not None:
                set_parts.append(f"{col} = ?")
                vals.append(updates[col])
        if not set_parts:
            raise DestinationError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM destinations WHERE id = ?", (dest_id,)).fetchone()
            if not existing:
                raise DestinationError("Destination not found.")
            set_clause = ", ".join(set_parts)
            vals.append(dest_id)
            conn.execute(
                f"UPDATE destinations SET {set_clause}, updated_at = datetime('now') WHERE id = ?",  # nosec B608
                vals,
            )
            conn.commit()
            logger.info("Destination updated: id=%d", dest_id)
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)).fetchone()
            return dict(row)
        except DestinationError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DestinationError(f"Failed to update destination: {e}") from e
        finally:
            conn.close()

    def confirm_destination(self, dest_id: int, confirmed_destination: str,
                            destination_type: str | None = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM destinations WHERE id = ?", (dest_id,)).fetchone()
            if not existing:
                raise DestinationError("Destination not found.")
            sql = "UPDATE destinations SET confirmed_destination = ?, updated_at = datetime('now')"
            params: list = [confirmed_destination]
            if destination_type:
                sql += ", destination_type = ?"
                params.append(destination_type)
            sql += " WHERE id = ?"
            params.append(dest_id)
            conn.execute(sql, params)
            conn.commit()
            logger.info("Destination confirmed: id=%d", dest_id)
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)).fetchone()
            return dict(row)
        except DestinationError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DestinationError(f"Failed to confirm destination: {e}") from e
        finally:
            conn.close()

    def flag_neet_risk(self, dest_id: int, risk: int = 1) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE destinations SET neet_risk = ?, updated_at = datetime('now') WHERE id = ?",
                (risk, dest_id),
            )
            conn.commit()
            logger.info("NEET risk flagged: id=%d risk=%d", dest_id, risk)
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise DestinationError(f"Failed to flag NEET risk: {e}") from e
        finally:
            conn.close()

    def get_neet_risk_students(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT d.*, s.first_name, s.last_name, s.student_id as sid
                   FROM destinations d
                   JOIN students s ON d.student_id = s.id
                   WHERE d.neet_risk = 1
                   ORDER BY s.last_name, s.first_name"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def calculate_neet_risk(self, student_id: int) -> dict:
        """Calculate NEET risk score (0-4) based on multiple factors."""
        conn = self._conn()
        try:
            score = 0
            reasons = []

            # Factor 1: No confirmed destination
            dest = conn.execute(
                "SELECT * FROM destinations WHERE student_id = ? ORDER BY created_at DESC LIMIT 1",
                (student_id,),
            ).fetchone()
            if not dest or not dest["confirmed_destination"]:
                score += 1
                reasons.append("No confirmed destination")

            # Factor 2: Has withdrawal record
            withdrawal = conn.execute(
                "SELECT id FROM withdrawals WHERE student_id = ?", (student_id,)
            ).fetchone()
            if withdrawal:
                score += 1
                reasons.append("Has withdrawal record")

            # Factor 3: Attendance below 85%
            att_row = conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN ar.status IN ('present', 'late') THEN 1 ELSE 0 END) as attended
                   FROM attendance_records ar
                   JOIN attendance_sessions asess ON ar.session_id = asess.id
                   WHERE ar.student_id = ?""",
                (student_id,),
            ).fetchone()
            if att_row and att_row["total"] > 0:
                rate = (att_row["attended"] / att_row["total"]) * 100
                if rate < 85:
                    score += 1
                    reasons.append(f"Attendance below 85% ({rate:.1f}%)")

            # Factor 4: No contact made
            if dest and not dest["contact_made"]:
                score += 1
                reasons.append("No contact made")

            return {
                "student_id": student_id,
                "risk_score": score,
                "max_score": 4,
                "reasons": reasons,
                "risk_level": "high" if score >= 3 else "medium" if score >= 2 else "low",
            }
        except Exception as e:
            raise DestinationError(f"Failed to calculate NEET risk: {e}") from e
        finally:
            conn.close()

    def record_contact(self, dest_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE destinations SET contact_made = 1, updated_at = datetime('now') WHERE id = ?",
                (dest_id,),
            )
            conn.commit()
            logger.info("Contact recorded: id=%d", dest_id)
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise DestinationError(f"Failed to record contact: {e}") from e
        finally:
            conn.close()

    def get_pending_followups(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT d.*, s.first_name, s.last_name, s.student_id as sid
                   FROM destinations d
                   JOIN students s ON d.student_id = s.id
                   WHERE d.contact_made = 0 AND d.confirmed_destination IS NULL
                   ORDER BY s.last_name, s.first_name"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_destination_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) as c FROM destinations").fetchone()["c"]
            confirmed = conn.execute(
                "SELECT COUNT(*) as c FROM destinations WHERE confirmed_destination IS NOT NULL"
            ).fetchone()["c"]
            neet_risk = conn.execute(
                "SELECT COUNT(*) as c FROM destinations WHERE neet_risk = 1"
            ).fetchone()["c"]
            by_type = conn.execute(
                """SELECT destination_type, COUNT(*) as count
                   FROM destinations GROUP BY destination_type ORDER BY count DESC"""
            ).fetchall()
            return {
                "total": total,
                "confirmed": confirmed,
                "unconfirmed": total - confirmed,
                "neet_risk": neet_risk,
                "by_type": [dict(r) for r in by_type],
            }
        finally:
            conn.close()
