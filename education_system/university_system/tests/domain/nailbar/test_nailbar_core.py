"""Tests for Nail Bar/Salon Core Services."""

import pytest
import sqlite3
import tempfile
import os
from contextlib import contextmanager
from unittest.mock import patch

MODULE = "education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core"


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.remove(path)


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_tables(conn):
    """Create nailbar tables plus the unified transactions and payments tables."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS nailbar_treatments (
            treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER DEFAULT 45,
            price DECIMAL(10,2) NOT NULL,
            is_available INTEGER DEFAULT 1,
            requires_appointment INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS nailbar_technicians (
            technician_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            employee_id TEXT UNIQUE,
            specialties TEXT,
            phone TEXT,
            email TEXT,
            certification TEXT,
            is_active INTEGER DEFAULT 1,
            hire_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS nailbar_appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_reference TEXT UNIQUE NOT NULL,
            customer_id TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT,
            customer_phone TEXT,
            technician_id INTEGER,
            technician_name TEXT,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            status TEXT DEFAULT 'booked',
            total_amount DECIMAL(10,2) DEFAULT 0.00,
            payment_status TEXT DEFAULT 'pending',
            payment_method TEXT,
            special_requests TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (technician_id) REFERENCES nailbar_technicians(technician_id)
        );
        CREATE TABLE IF NOT EXISTS nailbar_appointment_treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            treatment_id INTEGER NOT NULL,
            treatment_name TEXT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            duration_minutes INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (appointment_id) REFERENCES nailbar_appointments(appointment_id),
            FOREIGN KEY (treatment_id) REFERENCES nailbar_treatments(treatment_id)
        );
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            reference_id INTEGER,
            reference_type TEXT,
            customer_id TEXT,
            amount DECIMAL(10,2),
            payment_method TEXT,
            tip_amount DECIMAL(10,2) DEFAULT 0,
            reference_number TEXT,
            processed_by TEXT,
            receipt_sent INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            amount DECIMAL(10,2),
            payment_method TEXT,
            payment_date TEXT,
            status TEXT,
            notes TEXT,
            created_by TEXT
        );
        CREATE TABLE IF NOT EXISTS nailbar_customer_preferences (
            preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL UNIQUE,
            preferred_technician_id INTEGER,
            favorite_colors TEXT,
            nail_type TEXT,
            allergies TEXT,
            last_visit TEXT,
            visit_count INTEGER DEFAULT 0,
            loyalty_points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


@contextmanager
def _fake_transaction(path):
    """Mimic the real transaction() context manager."""
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _fake_get_db(path):
    """Mimic get_db_connection() context manager."""
    conn = _connect(path)
    try:
        yield conn
    finally:
        conn.close()


# ── helpers ──────────────────────────────────────────────────────────────

def _seed_treatment(path, name="Gel Manicure", category="gel_nails", price=32.0,
                    duration=45, desc="Gel polish"):
    conn = _connect(path)
    cur = conn.execute(
        "INSERT INTO nailbar_treatments (name,category,description,duration_minutes,price) VALUES (?,?,?,?,?)",
        (name, category, desc, duration, price),
    )
    tid = cur.lastrowid
    conn.commit()
    conn.close()
    return tid


def _seed_technician(path, name="Alice", employee_id="EMP001"):
    conn = _connect(path)
    cur = conn.execute(
        "INSERT INTO nailbar_technicians (name,employee_id,hire_date) VALUES (?,?,date('now'))",
        (name, employee_id),
    )
    tid = cur.lastrowid
    conn.commit()
    conn.close()
    return tid


# ── TreatmentManager ────────────────────────────────────────────────────

class TestTreatmentManager:

    def test_add_treatment(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TreatmentManager
            tid = TreatmentManager.add_treatment("Classic Mani", "manicure", 18.0, 30, "Basic")
        assert isinstance(tid, int) and tid > 0

    def test_get_treatment(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        tid = _seed_treatment(temp_db)

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TreatmentManager
            result = TreatmentManager.get_treatment(tid)
        assert result is not None
        assert result["name"] == "Gel Manicure"

    def test_get_treatment_not_found(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TreatmentManager
            assert TreatmentManager.get_treatment(999) is None

    def test_get_all_treatments_by_category(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        _seed_treatment(temp_db, "Gel Mani", "gel_nails", 32)
        _seed_treatment(temp_db, "Classic Pedi", "pedicure", 25)

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TreatmentManager
            gels = TreatmentManager.get_all_treatments(category="gel_nails")
        assert len(gels) == 1
        assert gels[0]["category"] == "gel_nails"

    def test_get_all_treatments_available_only(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.execute(
            "INSERT INTO nailbar_treatments (name,category,price,is_available) VALUES (?,?,?,?)",
            ("Hidden", "manicure", 10, 0),
        )
        conn.commit()
        conn.close()

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TreatmentManager
            results = TreatmentManager.get_all_treatments(available_only=True)
        assert len(results) == 0

    def test_update_treatment(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        tid = _seed_treatment(temp_db, price=20)

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TreatmentManager
            assert TreatmentManager.update_treatment(tid, price=25.0) is True

        conn = _connect(temp_db)
        row = conn.execute("SELECT price FROM nailbar_treatments WHERE treatment_id=?", (tid,)).fetchone()
        conn.close()
        assert float(row["price"]) == 25.0

    def test_update_treatment_no_fields(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TreatmentManager
            assert TreatmentManager.update_treatment(1, unknown_field="x") is False


# ── TechnicianManager ───────────────────────────────────────────────────

class TestTechnicianManager:

    def test_add_technician(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TechnicianManager
            tid = TechnicianManager.add_technician("Bob", "EMP002", "gel_nails", "07700900000", "bob@test.com", "NVQ3")
        assert isinstance(tid, int) and tid > 0

    def test_get_technician(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        tid = _seed_technician(temp_db, "Carol", "EMP003")

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TechnicianManager
            result = TechnicianManager.get_technician(tid)
        assert result["name"] == "Carol"

    def test_get_all_technicians_active_only(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        _seed_technician(temp_db, "Active Tech", "E01")
        conn2 = _connect(temp_db)
        conn2.execute("INSERT INTO nailbar_technicians (name,employee_id,is_active) VALUES ('Inactive','E02',0)")
        conn2.commit()
        conn2.close()

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TechnicianManager
            results = TechnicianManager.get_all_technicians(active_only=True)
        assert len(results) == 1

    def test_get_technician_availability(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        tech_id = _seed_technician(temp_db)

        # Book the 09:00 slot
        conn = _connect(temp_db)
        conn.execute(
            "INSERT INTO nailbar_appointments (booking_reference,customer_id,customer_name,"
            "appointment_date,appointment_time,technician_id,status) VALUES (?,?,?,?,?,?,?)",
            ("NB-TEST-001", "C1", "Test", "2026-04-10", "09:00", tech_id, "booked"),
        )
        conn.commit()
        conn.close()

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TechnicianManager
            slots = TechnicianManager.get_technician_availability(tech_id, "2026-04-10")
        assert "09:00" not in slots
        assert "09:30" in slots


# ── AppointmentManager ──────────────────────────────────────────────────

class TestAppointmentManager:

    def _create_appointment(self, temp_db):
        """Helper: seed treatment + technician then create appointment."""
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()
        tid = _seed_treatment(temp_db, "Gel Mani", "gel_nails", 32)
        tech = _seed_technician(temp_db)

        with (
            patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)),
            patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)),
        ):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            appt_id, ref = AppointmentManager.create_appointment(
                "CUST01", "Jane Doe", "2026-04-10", "10:00",
                treatment_ids=[tid], technician_id=tech,
                customer_email="jane@test.com", special_requests="Extra glitter",
            )
        return appt_id, ref, tid, tech

    def test_create_appointment(self, temp_db):
        appt_id, ref, _, _ = self._create_appointment(temp_db)
        assert appt_id > 0
        assert ref.startswith("NB-")

    def test_get_appointment_with_treatments(self, temp_db):
        appt_id, _, _, _ = self._create_appointment(temp_db)

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment(appt_id)
        assert appt is not None
        assert appt["customer_name"] == "Jane Doe"
        assert len(appt["treatments"]) == 1

    def test_get_appointment_by_reference(self, temp_db):
        appt_id, ref, _, _ = self._create_appointment(temp_db)

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(ref)
        assert appt is not None
        assert appt["appointment_id"] == appt_id

    def test_update_status(self, temp_db):
        appt_id, _, _, _ = self._create_appointment(temp_db)

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            assert AppointmentManager.update_status(appt_id, "confirmed") is True

        conn = _connect(temp_db)
        row = conn.execute("SELECT status FROM nailbar_appointments WHERE appointment_id=?", (appt_id,)).fetchone()
        conn.close()
        assert row["status"] == "confirmed"

    def test_update_status_invalid(self, temp_db):
        from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
        assert AppointmentManager.update_status(1, "invalid_status") is False

    def test_cancel_appointment(self, temp_db):
        appt_id, _, _, _ = self._create_appointment(temp_db)

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            assert AppointmentManager.cancel_appointment(appt_id, "Changed mind") is True

        conn = _connect(temp_db)
        row = conn.execute("SELECT status,notes FROM nailbar_appointments WHERE appointment_id=?", (appt_id,)).fetchone()
        conn.close()
        assert row["status"] == "cancelled"

    def test_reschedule_appointment(self, temp_db):
        appt_id, _, _, _ = self._create_appointment(temp_db)

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            assert AppointmentManager.reschedule_appointment(appt_id, "2026-04-12", "14:00") is True

        conn = _connect(temp_db)
        row = conn.execute("SELECT appointment_date,appointment_time FROM nailbar_appointments WHERE appointment_id=?", (appt_id,)).fetchone()
        conn.close()
        assert row["appointment_date"] == "2026-04-12"
        assert row["appointment_time"] == "14:00"

    def test_get_appointments_by_date(self, temp_db):
        self._create_appointment(temp_db)

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            results = AppointmentManager.get_appointments_by_date("2026-04-10")
        assert len(results) == 1

    def test_get_customer_appointments(self, temp_db):
        self._create_appointment(temp_db)

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            results = AppointmentManager.get_customer_appointments("CUST01")
        assert len(results) == 1


# ── TransactionManager ──────────────────────────────────────────────────

class TestTransactionManager:

    def _setup_paid_appointment(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.execute(
            "INSERT INTO nailbar_appointments (booking_reference,customer_id,customer_name,"
            "appointment_date,appointment_time,total_amount) VALUES (?,?,?,?,?,?)",
            ("NB-PAY-001", "C1", "Payer", "2026-04-10", "11:00", 50.0),
        )
        conn.commit()
        appt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return appt_id

    def test_process_payment(self, temp_db):
        appt_id = self._setup_paid_appointment(temp_db)

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TransactionManager
            txn_id = TransactionManager.process_payment(appt_id, 50.0, "card", "C1", tip_amount=5.0)
        assert isinstance(txn_id, int) and txn_id > 0

        conn = _connect(temp_db)
        row = conn.execute("SELECT payment_status FROM nailbar_appointments WHERE appointment_id=?", (appt_id,)).fetchone()
        conn.close()
        assert row["payment_status"] == "paid"

    def test_get_transaction(self, temp_db):
        appt_id = self._setup_paid_appointment(temp_db)

        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TransactionManager
            txn_id = TransactionManager.process_payment(appt_id, 50.0, "cash", "C1")

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TransactionManager
            txn = TransactionManager.get_transaction(txn_id)
        assert txn is not None
        assert float(txn["amount"]) == 50.0

    def test_get_daily_revenue_empty(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import TransactionManager
            rev = TransactionManager.get_daily_revenue("2026-04-10")
        assert rev["transaction_count"] == 0
        assert rev["total_revenue"] == 0


# ── ReportManager ────────────────────────────────────────────────────────

class TestReportManager:

    def test_generate_sales_report_empty(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import ReportManager
            report = ReportManager.generate_sales_report("2026-04-01", "2026-04-30")
        assert "period" in report
        assert report["period"]["start"] == "2026-04-01"

    def test_generate_admin_report(self, temp_db):
        conn = _connect(temp_db)
        _init_tables(conn)
        conn.close()

        with (
            patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)),
            patch(f"{MODULE}.get_db_connection", lambda **kw: _fake_get_db(temp_db)),
        ):
            from education_system.university_system.modules.domain.commerce.nailbar.services.nailbar_core import ReportManager
            text = ReportManager.generate_admin_report()
        assert "NAIL BAR" in text
        assert "WEEKLY SUMMARY" in text
