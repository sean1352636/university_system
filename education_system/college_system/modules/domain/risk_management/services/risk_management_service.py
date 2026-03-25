"""Risk Management service — institutional risks and risk reviews."""

from education_system.college_system.core.exceptions import RiskManagementError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import escape_like
import logging

logger = logging.getLogger(__name__)

RISK_CATEGORIES = [
    "operational", "financial", "strategic", "compliance",
    "reputational", "health_and_safety", "safeguarding", "cyber",
]
RISK_STATUSES = ["open", "mitigated", "closed", "escalated", "monitoring"]


class RiskManagementService:
    """Service for managing institutional risks and risk reviews."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Risks ────────────────────────────────────────────────────────────

    def create_risk(self, risk_title: str, category: str = "operational",
                    description: str | None = None, likelihood: int = 3,
                    impact: int = 3, current_controls: str | None = None,
                    mitigation_strategy: str | None = None,
                    risk_owner: str | None = None, review_date: str | None = None,
                    status: str = "open", residual_likelihood: int | None = None,
                    residual_impact: int | None = None,
                    notes: str | None = None) -> dict:
        """Create a new institutional risk. risk_score is auto-calculated."""
        risk_score = likelihood * impact
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO institutional_risks
                   (risk_title, category, description, likelihood, impact,
                    risk_score, current_controls, mitigation_strategy,
                    risk_owner, review_date, status, residual_likelihood,
                    residual_impact, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (risk_title, category, description, likelihood, impact,
                 risk_score, current_controls, mitigation_strategy,
                 risk_owner, review_date, status, residual_likelihood,
                 residual_impact, notes),
            )
            conn.commit()
            logger.info("Risk created: title=%s score=%d", risk_title, risk_score)
            row = conn.execute(
                "SELECT * FROM institutional_risks WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise RiskManagementError(f"Failed to create risk: {e}") from e
        finally:
            conn.close()

    def list_risks(self, status: str | None = None, category: str | None = None,
                   search: str | None = None) -> list[dict]:
        """List risks with optional status/category filter and search."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM institutional_risks WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if category:
                sql += " AND category = ?"
                params.append(category)
            if search:
                sql += " AND (risk_title LIKE ? OR description LIKE ? OR risk_owner LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term])
            sql += " ORDER BY risk_score DESC, created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_risk(self, risk_id: int) -> dict | None:
        """Get a single risk by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM institutional_risks WHERE id = ?", (risk_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_risk(self, risk_id: int, **updates) -> dict:
        """Update a risk. Recalculates risk_score if likelihood or impact change."""
        allowed = {
            "risk_title", "category", "description", "likelihood", "impact",
            "current_controls", "mitigation_strategy", "risk_owner",
            "review_date", "status", "residual_likelihood", "residual_impact",
            "notes",
        }
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise RiskManagementError("No valid fields to update.")

        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT * FROM institutional_risks WHERE id = ?", (risk_id,)
            ).fetchone()
            if not existing:
                raise RiskManagementError("Risk not found.")

            # Recalculate risk_score
            likelihood = updates.get("likelihood", existing["likelihood"])
            impact = updates.get("impact", existing["impact"])
            updates["risk_score"] = int(likelihood) * int(impact)

            set_parts = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [risk_id]
            conn.execute(
                f"UPDATE institutional_risks SET {set_parts}, "
                f"updated_at = datetime('now') WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("Risk updated: id=%d score=%d", risk_id, updates["risk_score"])
            row = conn.execute(
                "SELECT * FROM institutional_risks WHERE id = ?", (risk_id,)
            ).fetchone()
            return dict(row)
        except RiskManagementError:
            raise
        except Exception as e:
            conn.rollback()
            raise RiskManagementError(f"Failed to update risk: {e}") from e
        finally:
            conn.close()

    def delete_risk(self, risk_id: int) -> bool:
        """Delete a risk and cascade-delete its reviews."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM institutional_risks WHERE id = ?", (risk_id,)
            ).fetchone()
            if not existing:
                raise RiskManagementError("Risk not found.")
            conn.execute("DELETE FROM risk_reviews WHERE risk_id = ?", (risk_id,))
            conn.execute("DELETE FROM institutional_risks WHERE id = ?", (risk_id,))
            conn.commit()
            logger.info("Risk deleted (with reviews): id=%d", risk_id)
            return True
        except RiskManagementError:
            raise
        except Exception as e:
            conn.rollback()
            raise RiskManagementError(f"Failed to delete risk: {e}") from e
        finally:
            conn.close()

    # ── Reviews ──────────────────────────────────────────────────────────

    def create_review(self, risk_id: int, review_date: str, reviewer: str | None = None,
                      previous_score: int | None = None, new_score: int | None = None,
                      commentary: str | None = None,
                      actions_taken: str | None = None) -> dict:
        """Create a review for a risk."""
        conn = self._conn()
        try:
            # Verify the risk exists
            risk = conn.execute(
                "SELECT id FROM institutional_risks WHERE id = ?", (risk_id,)
            ).fetchone()
            if not risk:
                raise RiskManagementError("Risk not found.")
            conn.execute(
                """INSERT INTO risk_reviews
                   (risk_id, review_date, reviewer, previous_score, new_score,
                    commentary, actions_taken)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (risk_id, review_date, reviewer, previous_score, new_score,
                 commentary, actions_taken),
            )
            conn.commit()
            logger.info("Review created for risk_id=%d", risk_id)
            row = conn.execute(
                "SELECT * FROM risk_reviews WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except RiskManagementError:
            raise
        except Exception as e:
            conn.rollback()
            raise RiskManagementError(f"Failed to create review: {e}") from e
        finally:
            conn.close()

    def list_reviews(self, risk_id: int) -> list[dict]:
        """List all reviews for a specific risk."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM risk_reviews WHERE risk_id = ? ORDER BY review_date DESC",
                (risk_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_review(self, review_id: int) -> bool:
        """Delete a single review."""
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM risk_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            if not existing:
                raise RiskManagementError("Review not found.")
            conn.execute("DELETE FROM risk_reviews WHERE id = ?", (review_id,))
            conn.commit()
            logger.info("Review deleted: id=%d", review_id)
            return True
        except RiskManagementError:
            raise
        except Exception as e:
            conn.rollback()
            raise RiskManagementError(f"Failed to delete review: {e}") from e
        finally:
            conn.close()

    # ── Statistics ────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get risk register statistics."""
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM institutional_risks"
            ).fetchone()[0]

            # By status
            by_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM institutional_risks GROUP BY status"
            ).fetchall():
                by_status[row["status"]] = row["cnt"]

            # By category
            by_category = {}
            for row in conn.execute(
                "SELECT category, COUNT(*) AS cnt FROM institutional_risks GROUP BY category"
            ).fetchall():
                by_category[row["category"]] = row["cnt"]

            # Avg risk score
            avg_row = conn.execute(
                "SELECT AVG(risk_score) AS avg_score FROM institutional_risks"
            ).fetchone()
            avg_score = round(avg_row["avg_score"], 1) if avg_row["avg_score"] else 0

            # High risks (score >= 15)
            high_risks = conn.execute(
                "SELECT COUNT(*) FROM institutional_risks WHERE risk_score >= 15"
            ).fetchone()[0]

            # Total reviews
            reviews_count = conn.execute(
                "SELECT COUNT(*) FROM risk_reviews"
            ).fetchone()[0]

            return {
                "total_risks": total,
                "by_status": by_status,
                "by_category": by_category,
                "avg_risk_score": avg_score,
                "high_risks": high_risks,
                "reviews_count": reviews_count,
            }
        finally:
            conn.close()
