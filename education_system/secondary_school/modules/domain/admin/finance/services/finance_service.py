"""Finance management service."""

import logging
from education_system.secondary_school.core.exceptions import FinanceError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

TRANSACTION_TYPES = ("income", "expense")
INCOME_CATEGORIES = (
    "tuition_fees", "government_funding", "pupil_premium", "donations",
    "fundraising", "lettings", "catering", "trips", "other_income",
)
EXPENSE_CATEGORIES = (
    "salaries", "supplies", "utilities", "maintenance", "equipment",
    "catering", "transport", "training", "insurance", "trips",
    "exams", "resources", "it_services", "other_expense",
)
ALL_CATEGORIES = INCOME_CATEGORIES + EXPENSE_CATEGORIES


class FinanceService:
    """Manage school finances — transactions and budgets."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Transactions ──

    def add_transaction(self, transaction_type: str, category: str,
                        amount: float, description: str | None = None,
                        reference: str | None = None,
                        student_id: int | None = None,
                        staff_hr_id: int | None = None,
                        date: str | None = None,
                        recorded_by: str | None = None) -> dict:
        if transaction_type not in TRANSACTION_TYPES:
            raise FinanceError(f"Invalid type: {transaction_type}")
        if amount <= 0:
            raise FinanceError("Amount must be greater than zero.")
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO finance_transactions
                   (transaction_type, category, description, amount, reference,
                    student_id, staff_hr_id, date, recorded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, date('now')), ?)""",
                (transaction_type, category, description, amount, reference,
                 student_id, staff_hr_id, date, recorded_by),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM finance_transactions WHERE id = ?",
                               (cursor.lastrowid,)).fetchone()
            return dict(row)
        except FinanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to add transaction: {e}") from e
        finally:
            conn.close()

    def list_transactions(self, transaction_type: str | None = None,
                          category: str | None = None,
                          limit: int = 500) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM finance_transactions WHERE 1=1"
            params: list = []
            if transaction_type:
                sql += " AND transaction_type = ?"
                params.append(transaction_type)
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += f" ORDER BY date DESC, id DESC LIMIT {limit}"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_transaction(self, txn_id: int):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM finance_transactions WHERE id = ?", (txn_id,))
            conn.commit()
        finally:
            conn.close()

    def get_summary(self) -> dict:
        """Get total income, expenses, and balance."""
        conn = self._conn()
        try:
            inc = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM finance_transactions WHERE transaction_type = 'income'"
            ).fetchone()
            exp = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM finance_transactions WHERE transaction_type = 'expense'"
            ).fetchone()
            total_income = inc["total"]
            total_expense = exp["total"]
            return {
                "total_income": total_income,
                "total_expense": total_expense,
                "balance": total_income - total_expense,
            }
        finally:
            conn.close()

    # ── Budgets ──

    def set_budget(self, department: str, allocated: float,
                   academic_year: str = "2025/2026",
                   notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM finance_budgets WHERE department = ? AND academic_year = ?",
                (department, academic_year),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE finance_budgets SET allocated = ?, notes = ? WHERE id = ?",
                    (allocated, notes, existing["id"]),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM finance_budgets WHERE id = ?",
                                   (existing["id"],)).fetchone()
            else:
                cursor = conn.execute(
                    """INSERT INTO finance_budgets (department, academic_year, allocated, notes)
                       VALUES (?, ?, ?, ?)""",
                    (department, academic_year, allocated, notes),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM finance_budgets WHERE id = ?",
                                   (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to set budget: {e}") from e
        finally:
            conn.close()

    def list_budgets(self, academic_year: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM finance_budgets WHERE 1=1"
            params: list = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY department"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_budget_spent(self, budget_id: int, spent: float):
        conn = self._conn()
        try:
            conn.execute("UPDATE finance_budgets SET spent = ? WHERE id = ?", (spent, budget_id))
            conn.commit()
        finally:
            conn.close()

    def delete_budget(self, budget_id: int):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM finance_budgets WHERE id = ?", (budget_id,))
            conn.commit()
        finally:
            conn.close()
