"""Finance management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import FinanceError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class FinanceService:
    """CRUD operations for financial transactions and budgets."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Transactions ─────────────────────────────────────────────────────

    def record_transaction(self, transaction_type, description, amount,
                           category=None, pupil_id=None, payment_method=None,
                           reference=None, recorded_by=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO finance_transactions (
                    transaction_type, description, amount, category,
                    pupil_id, payment_method, reference, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    transaction_type, description, amount, category,
                    pupil_id, payment_method, reference, recorded_by,
                ),
            )
            conn.commit()
            txn_id = cursor.lastrowid
            logger.info(
                "Recorded transaction: %s %.2f (id=%s)",
                transaction_type, amount, txn_id,
            )
            return {
                "id": txn_id,
                "transaction_type": transaction_type,
                "amount": amount,
            }
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise FinanceError(f"Failed to record transaction: {e}") from e
        finally:
            conn.close()

    def get_transactions(self, category=None, pupil_id=None,
                         date_from=None, date_to=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM finance_transactions WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if date_from:
                sql += " AND created_at >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND created_at <= ?"
                params.append(date_to)
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_transaction(self, txn_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "transaction_type", "description", "amount", "category",
                "pupil_id", "payment_method", "reference", "recorded_by",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(txn_id)
            cursor.execute(
                f"UPDATE finance_transactions SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated transaction id=%s", txn_id)
            cursor.execute(
                "SELECT * FROM finance_transactions WHERE id = ?", (txn_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise FinanceError(f"Failed to update transaction: {e}") from e
        finally:
            conn.close()

    # ── Budgets ──────────────────────────────────────────────────────────

    def create_budget(self, budget_name, allocated_amount, category=None,
                      academic_year=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO finance_budgets (budget_name, allocated_amount, category, academic_year)
                VALUES (?, ?, ?, ?)""",
                (budget_name, allocated_amount, category, academic_year),
            )
            conn.commit()
            budget_id = cursor.lastrowid
            logger.info("Created budget: %s (id=%s)", budget_name, budget_id)
            return {
                "id": budget_id,
                "budget_name": budget_name,
                "allocated_amount": allocated_amount,
            }
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise FinanceError(f"Failed to create budget: {e}") from e
        finally:
            conn.close()

    def get_budgets(self, academic_year=None, status="Active"):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM finance_budgets WHERE 1=1"
            params = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY budget_name"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_budget(self, budget_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "budget_name", "allocated_amount", "spent_amount",
                "category", "academic_year", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(budget_id)
            cursor.execute(
                f"UPDATE finance_budgets SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated budget id=%s", budget_id)
            cursor.execute("SELECT * FROM finance_budgets WHERE id = ?", (budget_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise FinanceError(f"Failed to update budget: {e}") from e
        finally:
            conn.close()
