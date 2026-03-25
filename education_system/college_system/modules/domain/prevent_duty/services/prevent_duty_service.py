"""Prevent Duty service for referrals and training records."""

from education_system.college_system.core.exceptions import PreventDutyError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import escape_like
import logging

logger = logging.getLogger(__name__)


class PreventDutyService:
    """Prevent Duty service covering referrals and staff training."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Referrals ──────────────────────────────────────────────────

    def create_referral(self, subject_name: str, concern_details: str,
                        reported_by: int | None = None,
                        subject_type: str = "student",
                        subject_id: int | None = None,
                        concern_type: str | None = None,
                        risk_level: str = "low",
                        actions_taken: str | None = None) -> dict:
        """Create a new Prevent referral."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO prevent_referrals
                   (reported_by, subject_name, subject_type, subject_id,
                    concern_type, concern_details, risk_level, actions_taken)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (reported_by, subject_name, subject_type, subject_id,
                 concern_type, concern_details, risk_level, actions_taken),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM prevent_referrals WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Referral created: id=%d", row["id"])
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise PreventDutyError(f"Failed to create referral: {e}") from e
        finally:
            conn.close()

    def list_referrals(self, status: str | None = None,
                       risk_level: str | None = None,
                       concern_type: str | None = None,
                       search: str | None = None) -> list[dict]:
        """List referrals with optional filters and name search."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM prevent_referrals WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if risk_level:
                sql += " AND risk_level = ?"
                params.append(risk_level)
            if concern_type:
                sql += " AND concern_type = ?"
                params.append(concern_type)
            if search:
                sql += " AND subject_name LIKE ?"
                escaped = escape_like(search)
                params.append(f"%{escaped}%")
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_referral(self, referral_id: int) -> dict | None:
        """Get a single referral by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM prevent_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_referral(self, referral_id: int, **updates) -> dict:
        """Update referral fields."""
        allowed = {
            "subject_name", "subject_type", "subject_id", "concern_type",
            "concern_details", "risk_level", "channel_referral",
            "channel_reference", "actions_taken", "outcome", "status",
        }
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise PreventDutyError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [referral_id]
            conn.execute(
                f"UPDATE prevent_referrals SET {sets}, updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("Referral updated: id=%d", referral_id)
            row = conn.execute(
                "SELECT * FROM prevent_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            return dict(row) if row else {}
        except PreventDutyError:
            raise
        except Exception as e:
            conn.rollback()
            raise PreventDutyError(f"Failed to update referral: {e}") from e
        finally:
            conn.close()

    def delete_referral(self, referral_id: int) -> bool:
        """Delete a referral."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM prevent_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            if not existing:
                raise PreventDutyError("Referral not found.")
            conn.execute("DELETE FROM prevent_referrals WHERE id = ?", (referral_id,))
            conn.commit()
            logger.info("Referral deleted: id=%d", referral_id)
            return True
        except PreventDutyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PreventDutyError(f"Failed to delete referral: {e}") from e
        finally:
            conn.close()

    def escalate_to_channel(self, referral_id: int,
                            channel_reference: str | None = None) -> dict:
        """Escalate a referral to the Channel programme."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM prevent_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            if not existing:
                raise PreventDutyError("Referral not found.")
            conn.execute(
                """UPDATE prevent_referrals
                   SET channel_referral = 1, channel_reference = ?,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (channel_reference, referral_id),
            )
            conn.commit()
            logger.info("Referral escalated to Channel: id=%d", referral_id)
            row = conn.execute(
                "SELECT * FROM prevent_referrals WHERE id = ?", (referral_id,)
            ).fetchone()
            return dict(row)
        except PreventDutyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PreventDutyError(f"Failed to escalate referral: {e}") from e
        finally:
            conn.close()

    # ── Training ───────────────────────────────────────────────────

    def create_training(self, staff_id: int, training_type: str = "basic",
                        completed_date: str | None = None,
                        expiry_date: str | None = None,
                        certificate_ref: str | None = None,
                        status: str = "completed") -> dict:
        """Record a Prevent training completion."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO prevent_training
                   (staff_id, training_type, completed_date, expiry_date,
                    certificate_ref, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (staff_id, training_type, completed_date, expiry_date,
                 certificate_ref, status),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM prevent_training WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Training record created: id=%d", row["id"])
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise PreventDutyError(f"Failed to create training record: {e}") from e
        finally:
            conn.close()

    def list_training(self, status: str | None = None,
                      expiring: bool = False) -> list[dict]:
        """List training records, optionally filtering by status or expiring soon."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM prevent_training WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if expiring:
                sql += " AND expiry_date IS NOT NULL AND expiry_date <= date('now', '+90 days')"
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_training(self, training_id: int) -> dict | None:
        """Get a single training record by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM prevent_training WHERE id = ?", (training_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_training(self, training_id: int, **updates) -> dict:
        """Update a training record."""
        allowed = {
            "training_type", "completed_date", "expiry_date",
            "certificate_ref", "status",
        }
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise PreventDutyError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [training_id]
            conn.execute(
                f"UPDATE prevent_training SET {sets} WHERE id = ?", vals,
            )
            conn.commit()
            logger.info("Training record updated: id=%d", training_id)
            row = conn.execute(
                "SELECT * FROM prevent_training WHERE id = ?", (training_id,)
            ).fetchone()
            return dict(row) if row else {}
        except PreventDutyError:
            raise
        except Exception as e:
            conn.rollback()
            raise PreventDutyError(f"Failed to update training record: {e}") from e
        finally:
            conn.close()

    def delete_training(self, training_id: int) -> bool:
        """Delete a training record."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM prevent_training WHERE id = ?", (training_id,)
            ).fetchone()
            if not existing:
                raise PreventDutyError("Training record not found.")
            conn.execute("DELETE FROM prevent_training WHERE id = ?", (training_id,))
            conn.commit()
            logger.info("Training record deleted: id=%d", training_id)
            return True
        except PreventDutyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PreventDutyError(f"Failed to delete training record: {e}") from e
        finally:
            conn.close()

    def get_expiring_training(self, within_days: int = 30) -> list[dict]:
        """Get training records expiring within N days."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM prevent_training
                   WHERE expiry_date IS NOT NULL
                     AND expiry_date <= date('now', '+' || ? || ' days')
                   ORDER BY expiry_date ASC""",
                (within_days,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Statistics ─────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return summary statistics for referrals and training."""
        conn = self._conn()
        try:
            stats: dict = {}

            # Referral totals
            row = conn.execute("SELECT COUNT(*) AS cnt FROM prevent_referrals").fetchone()
            stats["total_referrals"] = row["cnt"]
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM prevent_referrals WHERE status = 'open'"
            ).fetchone()
            stats["open_referrals"] = row["cnt"]
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM prevent_referrals WHERE status = 'closed'"
            ).fetchone()
            stats["closed_referrals"] = row["cnt"]
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM prevent_referrals WHERE channel_referral = 1"
            ).fetchone()
            stats["channel_referrals"] = row["cnt"]

            # By risk level
            risk_rows = conn.execute(
                "SELECT risk_level, COUNT(*) AS cnt FROM prevent_referrals GROUP BY risk_level"
            ).fetchall()
            stats["by_risk_level"] = {r["risk_level"]: r["cnt"] for r in risk_rows}

            # Training totals
            row = conn.execute("SELECT COUNT(*) AS cnt FROM prevent_training").fetchone()
            stats["total_training"] = row["cnt"]
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM prevent_training WHERE status = 'completed'"
            ).fetchone()
            stats["completed_training"] = row["cnt"]
            row = conn.execute(
                """SELECT COUNT(*) AS cnt FROM prevent_training
                   WHERE expiry_date IS NOT NULL
                     AND expiry_date <= date('now', '+30 days')"""
            ).fetchone()
            stats["expiring_soon"] = row["cnt"]

            return stats
        finally:
            conn.close()
