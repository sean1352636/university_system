"""Finance management service — fees, invoices, payments, payroll."""

from education_system.college_system.core.exceptions import FinanceError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class FinanceService:
    """Service for managing fees, invoices, payments, and payroll."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # -- Fee Items --

    def create_fee_item(self, title: str, fee_type: str = "tuition",
                        amount: float = 0, academic_year: str | None = None,
                        mandatory: bool = True) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO fee_items (title, fee_type, amount, academic_year, mandatory)
                   VALUES (?, ?, ?, ?, ?)""",
                (title, fee_type, amount, academic_year, 1 if mandatory else 0),
            )
            conn.commit()
            logger.info("Fee item created: title=%s amount=%.2f", title, amount)
            row = conn.execute("SELECT * FROM fee_items WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to create fee item: {e}") from e
        finally:
            conn.close()

    def list_fee_items(self, fee_type: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            if fee_type:
                rows = conn.execute(
                    "SELECT * FROM fee_items WHERE fee_type = ? ORDER BY title", (fee_type,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM fee_items ORDER BY title").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_fee_item(self, fee_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM fee_items WHERE id = ?", (fee_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_fee_item(self, fee_id: int, **updates) -> dict:
        allowed = {"title", "fee_type", "amount", "academic_year", "mandatory"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise FinanceError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM fee_items WHERE id = ?", (fee_id,)).fetchone()
            if not existing:
                raise FinanceError("Fee item not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE fee_items SET {set_parts} WHERE id = ?",  # nosec B608
                         (*updates.values(), fee_id))
            conn.commit()
            logger.info("Fee item updated: id=%d", fee_id)
            row = conn.execute("SELECT * FROM fee_items WHERE id = ?", (fee_id,)).fetchone()
            return dict(row)
        except FinanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to update fee item: {e}") from e
        finally:
            conn.close()

    # -- Invoices --

    def create_invoice(self, student_id: int, fee_item_id: int,
                       amount: float | None = None, due_date: str | None = None) -> dict:
        conn = self._conn()
        try:
            if amount is None:
                fee = conn.execute("SELECT amount FROM fee_items WHERE id = ?", (fee_item_id,)).fetchone()
                if not fee:
                    raise FinanceError("Fee item not found.")
                amount = fee["amount"]
            conn.execute(
                """INSERT INTO invoices (student_id, fee_item_id, amount, due_date)
                   VALUES (?, ?, ?, ?)""",
                (student_id, fee_item_id, amount, due_date),
            )
            conn.commit()
            logger.info("Invoice created: student=%d fee=%d amount=%.2f", student_id, fee_item_id, amount)
            row = conn.execute("SELECT * FROM invoices WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except FinanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to create invoice: {e}") from e
        finally:
            conn.close()

    def list_invoices(self, student_id: int | None = None,
                      status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM invoices WHERE 1=1"
            params: list = []
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_invoice(self, invoice_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_invoice_status(self, invoice_id: int, status: str) -> dict:
        valid = ("pending", "paid", "overdue", "cancelled", "partial")
        if status not in valid:
            raise FinanceError(f"Invalid status. Must be one of: {', '.join(valid)}")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not existing:
                raise FinanceError("Invoice not found.")
            conn.execute("UPDATE invoices SET status = ? WHERE id = ?", (status, invoice_id))
            conn.commit()
            logger.info("Invoice status updated: id=%d status=%s", invoice_id, status)
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            return dict(row)
        except FinanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to update invoice: {e}") from e
        finally:
            conn.close()

    def get_student_balance(self, student_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COALESCE(SUM(amount), 0) as total_invoiced,
                          COALESCE(SUM(paid_amount), 0) as total_paid
                   FROM invoices WHERE student_id = ? AND status != 'cancelled'""",
                (student_id,),
            ).fetchone()
            total = row["total_invoiced"]
            paid = row["total_paid"]
            return {
                "student_id": student_id,
                "total_invoiced": total,
                "total_paid": paid,
                "balance_due": round(total - paid, 2),
            }
        finally:
            conn.close()

    def get_overdue_invoices(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT i.*, s.first_name, s.last_name, s.student_id as sid
                   FROM invoices i
                   JOIN students s ON i.student_id = s.id
                   WHERE i.status IN ('pending', 'partial', 'overdue')
                   AND i.due_date < date('now')
                   ORDER BY i.due_date"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # -- Payments --

    def record_payment(self, invoice_id: int, amount: float,
                       payment_method: str = "cash", reference: str | None = None,
                       recorded_by: int = 1) -> dict:
        conn = self._conn()
        try:
            invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not invoice:
                raise FinanceError("Invoice not found.")
            conn.execute(
                """INSERT INTO payments (invoice_id, amount, payment_method, reference, recorded_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (invoice_id, amount, payment_method, reference, recorded_by),
            )
            new_paid = invoice["paid_amount"] + amount
            new_status = "paid" if new_paid >= invoice["amount"] else "partial"
            conn.execute(
                "UPDATE invoices SET paid_amount = ?, status = ?, paid_date = date('now') WHERE id = ?",
                (new_paid, new_status, invoice_id),
            )
            conn.commit()
            logger.info("Payment recorded: invoice=%d amount=%.2f method=%s", invoice_id, amount, payment_method)
            row = conn.execute("SELECT * FROM payments WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except FinanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to record payment: {e}") from e
        finally:
            conn.close()

    def list_payments(self, invoice_id: int | None = None) -> list[dict]:
        conn = self._conn()
        try:
            if invoice_id:
                rows = conn.execute(
                    "SELECT * FROM payments WHERE invoice_id = ? ORDER BY created_at DESC",
                    (invoice_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM payments ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_payment(self, payment_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # -- Payroll --

    def create_payroll_record(self, staff_id: int, pay_period: str,
                              gross_pay: float, deductions: float = 0,
                              payment_date: str | None = None) -> dict:
        net_pay = gross_pay - deductions
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO payroll_records (staff_id, pay_period, gross_pay, deductions, net_pay, payment_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (staff_id, pay_period, gross_pay, deductions, net_pay, payment_date),
            )
            conn.commit()
            logger.info("Payroll record created: staff=%d period=%s", staff_id, pay_period)
            row = conn.execute("SELECT * FROM payroll_records WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to create payroll record: {e}") from e
        finally:
            conn.close()

    def list_payroll(self, staff_id: int | None = None,
                     status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM payroll_records WHERE 1=1"
            params: list = []
            if staff_id:
                sql += " AND staff_id = ?"
                params.append(staff_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY pay_period DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_payroll_status(self, payroll_id: int, status: str) -> dict:
        valid = ("pending", "processed", "paid")
        if status not in valid:
            raise FinanceError(f"Invalid status. Must be one of: {', '.join(valid)}")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM payroll_records WHERE id = ?", (payroll_id,)).fetchone()
            if not existing:
                raise FinanceError("Payroll record not found.")
            conn.execute("UPDATE payroll_records SET status = ? WHERE id = ?", (status, payroll_id))
            conn.commit()
            logger.info("Payroll status updated: id=%d status=%s", payroll_id, status)
            row = conn.execute("SELECT * FROM payroll_records WHERE id = ?", (payroll_id,)).fetchone()
            return dict(row)
        except FinanceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FinanceError(f"Failed to update payroll: {e}") from e
        finally:
            conn.close()

    def get_payroll_summary(self, pay_period: str) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) as record_count,
                          COALESCE(SUM(gross_pay), 0) as total_gross,
                          COALESCE(SUM(deductions), 0) as total_deductions,
                          COALESCE(SUM(net_pay), 0) as total_net
                   FROM payroll_records WHERE pay_period = ?""",
                (pay_period,),
            ).fetchone()
            return dict(row)
        finally:
            conn.close()
