"""Expense Claims service."""

from education_system.college_system.core.exceptions import ExpenseClaimError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class ExpenseClaimService:
    """Expense Claims service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ---- Claims ----

    def create_claim(self, claimant_id: int, description: str, amount: float,
                     **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {
                "claimant_id": claimant_id,
                "description": description,
                "amount": amount,
            }
            allowed = {
                "claim_date", "category", "mileage", "mileage_rate",
                "receipt_path", "notes", "status",
            }
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO expense_claims ({cols}) VALUES ({placeholders})", vals
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM expense_claims WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise ExpenseClaimError(f"Failed to create claim: {e}") from e
        finally:
            conn.close()

    def list_claims(self, claimant_id: int = None, category: str = None,
                    status: str = None, search: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT ec.*,
                              s.first_name, s.last_name
                       FROM expense_claims ec
                       LEFT JOIN staff s ON ec.claimant_id = s.id
                       WHERE 1=1"""
            params: list = []
            if claimant_id is not None:
                query += " AND ec.claimant_id = ?"
                params.append(claimant_id)
            if category:
                query += " AND ec.category = ?"
                params.append(category)
            if status:
                query += " AND ec.status = ?"
                params.append(status)
            if search:
                query += (" AND (s.first_name LIKE ? OR s.last_name LIKE ?"
                          " OR ec.description LIKE ? OR ec.notes LIKE ?)")
                term = f"%{search}%"
                params.extend([term, term, term, term])
            query += " ORDER BY ec.claim_date DESC, ec.id DESC"
            return [dict(r) for r in conn.execute(query, params).fetchall()]
        finally:
            conn.close()

    def get_claim(self, claim_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT ec.*, s.first_name, s.last_name
                   FROM expense_claims ec
                   LEFT JOIN staff s ON ec.claimant_id = s.id
                   WHERE ec.id = ?""",
                (claim_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_claim(self, claim_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "claimant_id", "claim_date", "description", "category",
                "amount", "mileage", "mileage_rate", "receipt_path",
                "notes", "status",
            }
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise ExpenseClaimError("No valid fields to update.")
            parts.append("updated_at = datetime('now')")
            params.append(claim_id)
            conn.execute(
                f"UPDATE expense_claims SET {', '.join(parts)} WHERE id = ?", params
            )
            conn.commit()
            return self.get_claim(claim_id)
        except ExpenseClaimError:
            raise
        except Exception as e:
            conn.rollback()
            raise ExpenseClaimError(f"Failed to update claim: {e}") from e
        finally:
            conn.close()

    def delete_claim(self, claim_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM expense_claims WHERE id = ?", (claim_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise ExpenseClaimError(f"Failed to delete claim: {e}") from e
        finally:
            conn.close()

    # ---- Workflow ----

    def approve_claim(self, claim_id: int, approved_by: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE expense_claims
                   SET status = 'approved', approved_by = ?,
                       approved_date = datetime('now'),
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (approved_by, claim_id),
            )
            conn.commit()
            return self.get_claim(claim_id)
        except Exception as e:
            conn.rollback()
            raise ExpenseClaimError(f"Failed to approve claim: {e}") from e
        finally:
            conn.close()

    def reject_claim(self, claim_id: int, notes: str = None) -> dict:
        conn = self._conn()
        try:
            if notes:
                conn.execute(
                    """UPDATE expense_claims
                       SET status = 'rejected', notes = ?,
                           updated_at = datetime('now')
                       WHERE id = ?""",
                    (notes, claim_id),
                )
            else:
                conn.execute(
                    """UPDATE expense_claims
                       SET status = 'rejected',
                           updated_at = datetime('now')
                       WHERE id = ?""",
                    (claim_id,),
                )
            conn.commit()
            return self.get_claim(claim_id)
        except Exception as e:
            conn.rollback()
            raise ExpenseClaimError(f"Failed to reject claim: {e}") from e
        finally:
            conn.close()

    def mark_paid(self, claim_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE expense_claims
                   SET paid = 1, paid_date = datetime('now'),
                       status = 'paid', updated_at = datetime('now')
                   WHERE id = ?""",
                (claim_id,),
            )
            conn.commit()
            return self.get_claim(claim_id)
        except Exception as e:
            conn.rollback()
            raise ExpenseClaimError(f"Failed to mark claim as paid: {e}") from e
        finally:
            conn.close()

    # ---- Statistics ----

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM expense_claims"
            ).fetchone()["cnt"]

            # By status
            status_rows = conn.execute(
                """SELECT status, COUNT(*) as cnt
                   FROM expense_claims
                   GROUP BY status
                   ORDER BY cnt DESC"""
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            # By category
            cat_rows = conn.execute(
                """SELECT category, COUNT(*) as cnt,
                          COALESCE(SUM(amount), 0) as total_amount
                   FROM expense_claims
                   GROUP BY category
                   ORDER BY cnt DESC"""
            ).fetchall()
            by_category = [dict(r) for r in cat_rows]

            # Totals
            amount_row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM expense_claims"
            ).fetchone()
            total_amount = amount_row["total"]

            paid_row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM expense_claims WHERE paid = 1"
            ).fetchone()
            total_paid = paid_row["total"]

            pending_row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM expense_claims WHERE status = 'submitted'"
            ).fetchone()
            total_pending = pending_row["total"]

            mileage_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM expense_claims WHERE mileage IS NOT NULL AND mileage > 0"
            ).fetchone()
            total_mileage_claims = mileage_row["cnt"]

            return {
                "total_claims": total,
                "by_status": by_status,
                "by_category": by_category,
                "total_amount": total_amount,
                "total_paid": total_paid,
                "total_pending": total_pending,
                "total_mileage_claims": total_mileage_claims,
            }
        finally:
            conn.close()
