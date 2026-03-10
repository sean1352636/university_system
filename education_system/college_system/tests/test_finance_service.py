"""Tests for FinanceService."""

import pytest

from education_system.college_system.modules.domain.finance.services.finance_service import FinanceService
from education_system.college_system.core.exceptions import FinanceError


class TestFinanceService:
    def test_create_fee_item(self, db_path):
        svc = FinanceService(db_path)
        fee = svc.create_fee_item("Tuition Fee", "tuition", 500.0)
        assert fee["title"] == "Tuition Fee"
        assert fee["amount"] == 500.0

    def test_list_fee_items(self, db_path):
        svc = FinanceService(db_path)
        svc.create_fee_item("Fee A", "tuition", 100)
        svc.create_fee_item("Fee B", "exam", 50)
        fees = svc.list_fee_items()
        assert len(fees) >= 2

    def test_create_invoice(self, db_path, sample_student):
        svc = FinanceService(db_path)
        fee = svc.create_fee_item("Test Fee", "tuition", 200)
        inv = svc.create_invoice(sample_student["id"], fee["id"])
        assert inv["amount"] == 200
        assert inv["status"] == "pending"

    def test_record_payment_updates_invoice(self, db_path, sample_student):
        svc = FinanceService(db_path)
        fee = svc.create_fee_item("Payment Test", "tuition", 100)
        inv = svc.create_invoice(sample_student["id"], fee["id"])

        svc.record_payment(inv["id"], 100.0, "cash")
        updated = svc.get_invoice(inv["id"])
        assert updated["status"] == "paid"
        assert updated["paid_amount"] == 100.0

    def test_partial_payment(self, db_path, sample_student):
        svc = FinanceService(db_path)
        fee = svc.create_fee_item("Partial Test", "tuition", 200)
        inv = svc.create_invoice(sample_student["id"], fee["id"])

        svc.record_payment(inv["id"], 50.0)
        updated = svc.get_invoice(inv["id"])
        assert updated["status"] == "partial"

    def test_student_balance(self, db_path, sample_student):
        svc = FinanceService(db_path)
        fee = svc.create_fee_item("Balance Test", "tuition", 300)
        svc.create_invoice(sample_student["id"], fee["id"])

        balance = svc.get_student_balance(sample_student["id"])
        assert balance["total_invoiced"] == 300
        assert balance["balance_due"] == 300

    def _create_staff(self, db_path, staff_id_str="STF001", first_name="Jane", last_name="Smith"):
        """Helper to create a staff record for payroll tests."""
        from education_system.college_system.infrastructure.database.db import connect
        conn = connect(db_path)
        try:
            conn.execute(
                "INSERT INTO staff (staff_id, first_name, last_name) VALUES (?, ?, ?)",
                (staff_id_str, first_name, last_name),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id FROM staff WHERE staff_id = ?", (staff_id_str,)
            ).fetchone()
            return row["id"]
        finally:
            conn.close()

    def test_payroll(self, db_path):
        svc = FinanceService(db_path)
        sid = self._create_staff(db_path, "STF_PAY1")
        record = svc.create_payroll_record(sid, "2025-01", 3000, 500)
        assert record["net_pay"] == 2500
        assert record["status"] == "pending"

        updated = svc.update_payroll_status(record["id"], "paid")
        assert updated["status"] == "paid"

    def test_payroll_summary(self, db_path):
        svc = FinanceService(db_path)
        sid1 = self._create_staff(db_path, "STF_SUM1")
        sid2 = self._create_staff(db_path, "STF_SUM2", first_name="Bob", last_name="Jones")
        svc.create_payroll_record(sid1, "2025-02", 3000, 500)
        svc.create_payroll_record(sid2, "2025-02", 2500, 400)

        summary = svc.get_payroll_summary("2025-02")
        assert summary["record_count"] == 2
        assert summary["total_gross"] == 5500
