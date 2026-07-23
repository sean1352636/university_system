"""Behavioural service/data-layer tests for commerce/carrental.

``carrental_core`` imports ``transaction`` and ``get_db_connection`` from the
shared ``infrastructure.database.db`` module and calls them with no arguments,
so both resolve ``DEFAULT_DB_PATH`` at call time. We redirect every manager at
an isolated temp DB by monkeypatching that module global (per the repo's
service-test isolation convention) — the real ``student_records.db`` is never
touched.

The carrental tables are created by the module's own ``init_carrental_db``; the
unified ``transactions`` table is not owned by this module, so we create it by
hand. ``TransactionManager.record_payment`` fans out to the finance
``unified_payments.record_payment`` — which would use the real DB — so we stub
it to a recorder.
"""

import sqlite3
from contextlib import contextmanager

import pytest

MODULE = (
    "education_system.post_18.university_system.modules.domain."
    "commerce.carrental.services.carrental_core"
)
DB_MODULE = "education_system.post_18.university_system.infrastructure.database.db"
FINANCE_RECORD_PAYMENT = (
    "education_system.post_18.university_system.modules.domain.finance."
    "core.unified_payments.record_payment"
)

# Column set matching the real unified transactions table well enough for the
# INSERT/SELECT statements the module issues.
_TRANSACTIONS_DDL = """
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL,
        reference_id INTEGER,
        reference_type TEXT,
        customer_id TEXT,
        amount DECIMAL(10,2),
        transaction_type TEXT,
        payment_method TEXT,
        reference_number TEXT,
        status TEXT DEFAULT 'completed',
        notes TEXT,
        processed_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _drop_table(path, table):
    """Rename a table out from under the module to force a sqlite error branch."""
    conn = sqlite3.connect(path)
    conn.execute(f"ALTER TABLE {table} RENAME TO {table}_gone")  # nosec B608
    conn.commit()
    conn.close()


@pytest.fixture()
def carrental(tmp_path, monkeypatch):
    db_path = str(tmp_path / "carrental.db")
    monkeypatch.setattr(f"{DB_MODULE}.DEFAULT_DB_PATH", db_path)

    # Recorder for the finance mirror seam so record_payment never reaches the
    # real finance DB.
    mirror_calls = []

    def _fake_record_payment(**kwargs):
        mirror_calls.append(kwargs)
        return 12345

    monkeypatch.setattr(FINANCE_RECORD_PAYMENT, _fake_record_payment)

    import education_system.post_18.university_system.modules.domain.commerce.carrental.services.carrental_core as cc

    assert cc.init_carrental_db() is True

    # Create the unified transactions table (not owned by this module).
    conn = _connect(db_path)
    conn.executescript(_TRANSACTIONS_DDL)
    conn.commit()
    conn.close()

    # ``generate_rental_number`` derives its value from a second-resolution
    # timestamp, so two rentals created inside the same wall-clock second collide
    # on the UNIQUE ``rental_number`` column and the second create silently fails.
    # Several tests create multiple rentals back-to-back, which made them flaky.
    # Swap in a deterministic, monotonic generator that preserves the real
    # format (``RNT-`` + 14 chars); the untouched original stays reachable via
    # ``_ORIG_GEN`` so the format test still exercises the real implementation.
    cc._ORIG_GEN = cc.RentalManager.generate_rental_number
    _counter = {"n": 0}

    def _unique_rental_number():
        _counter["n"] += 1
        return f"RNT-{_counter['n']:014d}"

    monkeypatch.setattr(
        cc.RentalManager,
        "generate_rental_number",
        staticmethod(_unique_rental_number),
    )

    cc.DB_PATH = db_path
    cc.MIRROR_CALLS = mirror_calls
    return cc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_vehicle(cc, reg="AB12 CDE", daily_rate=40.0, **kwargs):
    return cc.VehicleManager.add_vehicle(
        reg, "Toyota", "Corolla", 2022, "economy", daily_rate, **kwargs
    )


def _create_rental(cc, vehicle_id, daily_rate=40.0, **kwargs):
    return cc.RentalManager.create_rental(
        vehicle_id,
        "CUST1",
        "Alice Driver",
        "LIC-123",
        "2026-06-01",
        "10:00",
        "2026-06-04",
        "10:00",
        daily_rate,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# init_carrental_db
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_all_tables(self, carrental):
        conn = _connect(carrental.DB_PATH)
        names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert {
            "carrental_vehicles",
            "carrental_rentals",
            "carrental_maintenance",
            "carrental_insurance",
        } <= names

    def test_idempotent(self, carrental):
        # Running again against the existing schema still succeeds (IF NOT EXISTS).
        assert carrental.init_carrental_db() is True

    def test_returns_false_on_error(self, carrental, monkeypatch):
        @contextmanager
        def _boom(*a, **k):
            raise sqlite3.OperationalError("disk gone")
            yield  # pragma: no cover

        monkeypatch.setattr(f"{MODULE}.transaction", _boom)
        assert carrental.init_carrental_db() is False

    def test_module_constants(self, carrental):
        assert "economy" in carrental.VEHICLE_CATEGORIES
        assert "reserved" in carrental.RENTAL_STATUSES
        assert "available" in carrental.VEHICLE_STATUSES


# ---------------------------------------------------------------------------
# VehicleManager
# ---------------------------------------------------------------------------


class TestVehicleManager:
    def test_add_vehicle_minimal(self, carrental):
        vid = _add_vehicle(carrental)
        assert isinstance(vid, int)
        v = carrental.VehicleManager.get_vehicle(vid)
        assert v["make"] == "Toyota"
        assert v["seats"] == 5  # default
        assert v["transmission"] == "automatic"
        assert v["status"] == "available"

    def test_add_vehicle_with_kwargs(self, carrental):
        vid = _add_vehicle(
            carrental,
            reg="ZZ99 ZZZ",
            color="red",
            seats=2,
            transmission="manual",
            fuel_type="electric",
            mileage=100,
            features="GPS",
            insurance_info="policy-x",
        )
        v = carrental.VehicleManager.get_vehicle(vid)
        assert v["color"] == "red"
        assert v["seats"] == 2
        assert v["transmission"] == "manual"
        assert v["fuel_type"] == "electric"
        assert v["mileage"] == 100
        assert v["features"] == "GPS"
        assert v["insurance_info"] == "policy-x"

    def test_add_vehicle_duplicate_registration_returns_none(self, carrental):
        assert _add_vehicle(carrental, reg="DUP1 XXX") is not None
        assert _add_vehicle(carrental, reg="DUP1 XXX") is None

    def test_update_vehicle_success(self, carrental):
        vid = _add_vehicle(carrental)
        assert carrental.VehicleManager.update_vehicle(
            vid, daily_rate=55.0, color="blue"
        ) is True
        v = carrental.VehicleManager.get_vehicle(vid)
        assert v["daily_rate"] == 55.0
        assert v["color"] == "blue"

    def test_update_vehicle_ignores_none_values(self, carrental):
        vid = _add_vehicle(carrental, color="green")
        assert carrental.VehicleManager.update_vehicle(
            vid, color=None, mileage=999
        ) is True
        v = carrental.VehicleManager.get_vehicle(vid)
        assert v["color"] == "green"  # None was skipped
        assert v["mileage"] == 999

    def test_update_vehicle_no_updates_returns_false(self, carrental):
        vid = _add_vehicle(carrental)
        assert carrental.VehicleManager.update_vehicle(vid, color=None) is False

    def test_update_vehicle_bad_column_returns_false(self, carrental):
        vid = _add_vehicle(carrental)
        # Invalid identifier format trips validate_identifier -> caught -> False.
        assert carrental.VehicleManager.update_vehicle(
            vid, **{"bad column": "x"}
        ) is False

    def test_get_vehicle_not_found(self, carrental):
        assert carrental.VehicleManager.get_vehicle(999999) is None

    def test_get_vehicle_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_vehicles")
        assert carrental.VehicleManager.get_vehicle(1) is None

    def test_get_available_vehicles_no_filter(self, carrental):
        _add_vehicle(carrental, reg="AV1 AAA")
        _add_vehicle(carrental, reg="AV2 BBB", daily_rate=50.0)
        rows = carrental.VehicleManager.get_available_vehicles()
        assert len(rows) == 2
        assert all(r["status"] == "available" for r in rows)

    def test_get_available_vehicles_category_filter(self, carrental):
        _add_vehicle(carrental, reg="EC1 AAA")  # economy
        luxvid = carrental.VehicleManager.add_vehicle(
            "LX1 AAA", "BMW", "7", 2023, "luxury", 200.0
        )
        rows = carrental.VehicleManager.get_available_vehicles(category="luxury")
        assert len(rows) == 1
        assert rows[0]["vehicle_id"] == luxvid

    def test_get_available_vehicles_excludes_rented(self, carrental):
        vid = _add_vehicle(carrental)
        carrental.VehicleManager.update_vehicle_status(vid, "rented")
        assert carrental.VehicleManager.get_available_vehicles() == []

    def test_get_available_vehicles_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_vehicles")
        assert carrental.VehicleManager.get_available_vehicles() == []

    def test_get_all_vehicles(self, carrental):
        _add_vehicle(carrental, reg="A1 AAA")
        _add_vehicle(carrental, reg="A2 BBB")
        assert len(carrental.VehicleManager.get_all_vehicles()) == 2

    def test_get_all_vehicles_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_vehicles")
        assert carrental.VehicleManager.get_all_vehicles() == []

    def test_update_vehicle_status_success(self, carrental):
        vid = _add_vehicle(carrental)
        assert carrental.VehicleManager.update_vehicle_status(vid, "maintenance") is True
        assert carrental.VehicleManager.get_vehicle(vid)["status"] == "maintenance"

    def test_update_vehicle_status_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_vehicles")
        assert carrental.VehicleManager.update_vehicle_status(1, "available") is False


# ---------------------------------------------------------------------------
# RentalManager
# ---------------------------------------------------------------------------


class TestRentalManager:
    def test_generate_rental_number_format(self, carrental):
        # Exercise the real (unpatched) implementation, kept on the fixture.
        num = carrental._ORIG_GEN()
        assert num.startswith("RNT-")
        assert len(num) == len("RNT-20260101120000")

    def test_create_rental_success_and_marks_vehicle_rented(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        assert isinstance(rid, int)
        rental = carrental.RentalManager.get_rental(rid)
        assert rental["status"] == "reserved"
        assert rental["total_days"] == 3
        assert rental["subtotal"] == 120.0  # 40 * 3
        assert rental["total_amount"] == 120.0
        # Vehicle flipped to rented.
        assert carrental.VehicleManager.get_vehicle(vid)["status"] == "rented"

    def test_create_rental_with_insurance_and_kwargs(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(
            carrental,
            vid,
            insurance_fee=30.0,
            deposit_amount=100.0,
            customer_email="a@b.com",
            customer_phone="555",
            pickup_location="Depot A",
            return_location="Depot B",
            created_by="staff1",
        )
        r = carrental.RentalManager.get_rental(rid)
        assert r["insurance_fee"] == 30.0
        assert r["total_amount"] == 150.0  # 120 + 30
        assert r["deposit_amount"] == 100.0
        assert r["customer_email"] == "a@b.com"
        assert r["pickup_location"] == "Depot A"
        assert r["created_by"] == "staff1"

    def test_create_rental_same_day_minimum_one_day(self, carrental):
        vid = _add_vehicle(carrental)
        rid = carrental.RentalManager.create_rental(
            vid, "C", "N", "L", "2026-06-01", "10:00", "2026-06-01", "18:00", 40.0
        )
        r = carrental.RentalManager.get_rental(rid)
        assert r["total_days"] == 1  # max(1, 0)
        assert r["subtotal"] == 40.0

    def test_create_rental_bad_date_returns_none(self, carrental):
        vid = _add_vehicle(carrental)
        rid = carrental.RentalManager.create_rental(
            vid, "C", "N", "L", "not-a-date", "10:00", "2026-06-04", "10:00", 40.0
        )
        assert rid is None
        # Vehicle left available since the insert never ran.
        assert carrental.VehicleManager.get_vehicle(vid)["status"] == "available"

    def test_get_rental_not_found(self, carrental):
        assert carrental.RentalManager.get_rental(424242) is None

    def test_get_rental_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_rentals")
        assert carrental.RentalManager.get_rental(1) is None

    def test_get_rentals_by_status_filtered(self, carrental):
        v1 = _add_vehicle(carrental, reg="R1 AAA")
        v2 = _add_vehicle(carrental, reg="R2 BBB")
        r1 = _create_rental(carrental, v1)
        _create_rental(carrental, v2)
        carrental.RentalManager.cancel_rental(r1, "changed mind")
        reserved = carrental.RentalManager.get_rentals_by_status("reserved")
        cancelled = carrental.RentalManager.get_rentals_by_status("cancelled")
        assert len(reserved) == 1
        assert len(cancelled) == 1
        assert cancelled[0]["rental_id"] == r1

    def test_get_rentals_by_status_all(self, carrental):
        v1 = _add_vehicle(carrental, reg="R1 AAA")
        v2 = _add_vehicle(carrental, reg="R2 BBB")
        _create_rental(carrental, v1)
        _create_rental(carrental, v2)
        assert len(carrental.RentalManager.get_rentals_by_status()) == 2

    def test_get_rentals_by_status_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_rentals")
        assert carrental.RentalManager.get_rentals_by_status() == []

    def test_start_rental_success(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        assert carrental.RentalManager.start_rental(
            rid, 10000, "full", "no damage"
        ) is True
        r = carrental.RentalManager.get_rental(rid)
        assert r["status"] == "active"
        assert r["pickup_mileage"] == 10000
        assert r["fuel_level_pickup"] == "full"
        assert r["condition_notes"] == "no damage"

    def test_start_rental_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_rentals")
        assert carrental.RentalManager.start_rental(1, 1, "full") is False

    def test_complete_rental_success(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)  # total_amount 120
        carrental.RentalManager.start_rental(rid, 10000, "full")
        assert carrental.RentalManager.complete_rental(
            rid, 10500, "half", late_fee=20.0, damage_fee=15.0, fuel_fee=5.0
        ) is True
        r = carrental.RentalManager.get_rental(rid)
        assert r["status"] == "completed"
        assert r["return_mileage"] == 10500
        assert r["late_fee"] == 20.0
        assert r["damage_fee"] == 15.0
        assert r["fuel_fee"] == 5.0
        assert r["total_amount"] == 160.0  # 120 + 20 + 15 + 5
        assert r["actual_return_date"] is not None
        # Vehicle back to available with updated mileage.
        v = carrental.VehicleManager.get_vehicle(vid)
        assert v["status"] == "available"
        assert v["mileage"] == 10500

    def test_complete_rental_not_found_returns_false(self, carrental):
        assert carrental.RentalManager.complete_rental(999, 1, "full") is False

    def test_complete_rental_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_rentals")
        assert carrental.RentalManager.complete_rental(1, 1, "full") is False

    def test_cancel_rental_success_frees_vehicle(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        assert carrental.VehicleManager.get_vehicle(vid)["status"] == "rented"
        assert carrental.RentalManager.cancel_rental(rid, "customer request") is True
        r = carrental.RentalManager.get_rental(rid)
        assert r["status"] == "cancelled"
        assert r["condition_notes"] == "customer request"
        assert carrental.VehicleManager.get_vehicle(vid)["status"] == "available"

    def test_cancel_rental_not_found_returns_false(self, carrental):
        assert carrental.RentalManager.cancel_rental(999) is False

    def test_cancel_rental_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_rentals")
        assert carrental.RentalManager.cancel_rental(1) is False


# ---------------------------------------------------------------------------
# TransactionManager
# ---------------------------------------------------------------------------


class TestTransactionManager:
    def test_record_payment_success(self, carrental, monkeypatch):
        import random

        monkeypatch.setattr(random, "randint", lambda a, b: 4242)
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        tid = carrental.TransactionManager.record_payment(
            rid, "CUST1", 120.0, "card", processed_by="staff1"
        )
        assert isinstance(tid, int)
        # Rental marked paid.
        r = carrental.RentalManager.get_rental(rid)
        assert r["payment_status"] == "paid"
        assert r["payment_method"] == "card"
        # Transaction row written with deterministic ref.
        txns = carrental.TransactionManager.get_transactions(rid)
        assert len(txns) == 1
        assert txns[0]["transaction_type"] == "payment"
        assert txns[0]["reference_number"] == "PAY-" + \
            __import__("datetime").datetime.now().strftime("%Y%m%d") + "-4242"
        # Finance mirror invoked.
        assert len(carrental.MIRROR_CALLS) == 1
        assert carrental.MIRROR_CALLS[0]["source_type"] == "carrental"
        assert carrental.MIRROR_CALLS[0]["amount"] == 120.0

    def test_record_payment_mirror_failure_still_succeeds(self, carrental, monkeypatch):
        def _boom(**kwargs):
            raise RuntimeError("finance down")

        monkeypatch.setattr(FINANCE_RECORD_PAYMENT, _boom)
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        tid = carrental.TransactionManager.record_payment(rid, "CUST1", 50.0, "cash")
        assert isinstance(tid, int)
        assert carrental.RentalManager.get_rental(rid)["payment_status"] == "paid"

    def test_record_payment_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "transactions")
        assert carrental.TransactionManager.record_payment(1, "C", 10.0, "card") is None

    def test_record_refund_success(self, carrental, monkeypatch):
        import random

        monkeypatch.setattr(random, "randint", lambda a, b: 7777)
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        tid = carrental.TransactionManager.record_refund(
            rid, "CUST1", 40.0, "overcharge", processed_by="staff1"
        )
        assert isinstance(tid, int)
        txns = carrental.TransactionManager.get_transactions(rid)
        assert len(txns) == 1
        assert txns[0]["transaction_type"] == "refund"
        assert txns[0]["notes"] == "overcharge"
        assert txns[0]["reference_number"].startswith("REF-")

    def test_record_refund_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "transactions")
        assert carrental.TransactionManager.record_refund(1, "C", 10.0, "x") is None

    def test_get_transactions_all(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        carrental.TransactionManager.record_payment(rid, "CUST1", 120.0, "card")
        carrental.TransactionManager.record_refund(rid, "CUST1", 20.0, "goodwill")
        assert len(carrental.TransactionManager.get_transactions()) == 2

    def test_get_transactions_filtered_by_rental(self, carrental):
        v1 = _add_vehicle(carrental, reg="T1 AAA")
        v2 = _add_vehicle(carrental, reg="T2 BBB")
        r1 = _create_rental(carrental, v1)
        r2 = _create_rental(carrental, v2)
        carrental.TransactionManager.record_payment(r1, "C", 10.0, "card")
        carrental.TransactionManager.record_payment(r2, "C", 20.0, "card")
        assert len(carrental.TransactionManager.get_transactions(r1)) == 1

    def test_get_transactions_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "transactions")
        assert carrental.TransactionManager.get_transactions() == []


# ---------------------------------------------------------------------------
# ReportManager
# ---------------------------------------------------------------------------


class TestReportManager:
    def test_fleet_summary_counts(self, carrental):
        v1 = _add_vehicle(carrental, reg="F1 AAA")
        _add_vehicle(carrental, reg="F2 BBB")
        v3 = _add_vehicle(carrental, reg="F3 CCC")
        carrental.VehicleManager.update_vehicle_status(v1, "rented")
        carrental.VehicleManager.update_vehicle_status(v3, "maintenance")
        summary = carrental.ReportManager.get_fleet_summary()
        assert summary["total_vehicles"] == 3
        assert summary["available"] == 1
        assert summary["rented"] == 1
        assert summary["maintenance"] == 1

    def test_fleet_summary_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_vehicles")
        assert carrental.ReportManager.get_fleet_summary() == {}

    def test_revenue_report_no_dates(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)  # 120
        carrental.TransactionManager.record_payment(rid, "CUST1", 120.0, "card")
        report = carrental.ReportManager.get_revenue_report()
        assert report["total_rentals"] == 1
        assert report["total_revenue"] == 120.0
        assert report["completed_rentals"] == 0  # still 'reserved'

    def test_revenue_report_with_dates(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        carrental.TransactionManager.record_payment(rid, "CUST1", 120.0, "card")
        report = carrental.ReportManager.get_revenue_report("2000-01-01", "2100-01-01")
        assert report["total_rentals"] == 1
        assert report["total_revenue"] == 120.0

    def test_revenue_report_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_rentals")
        assert carrental.ReportManager.get_revenue_report() == {}

    def test_popular_vehicles(self, carrental):
        v1 = _add_vehicle(carrental, reg="P1 AAA")
        v2 = _add_vehicle(carrental, reg="P2 BBB")
        # v1 gets two rentals, v2 gets one.
        _create_rental(carrental, v1)
        carrental.VehicleManager.update_vehicle_status(v1, "available")
        _create_rental(carrental, v1)
        _create_rental(carrental, v2)
        popular = carrental.ReportManager.get_popular_vehicles(limit=10)
        assert popular[0]["vehicle_id"] == v1
        assert popular[0]["rental_count"] == 2

    def test_popular_vehicles_error_branch(self, carrental):
        _drop_table(carrental.DB_PATH, "carrental_vehicles")
        assert carrental.ReportManager.get_popular_vehicles() == []

    def test_generate_admin_report_content(self, carrental):
        vid = _add_vehicle(carrental)
        rid = _create_rental(carrental, vid)
        carrental.TransactionManager.record_payment(rid, "CUST1", 120.0, "card")
        report = carrental.ReportManager.generate_admin_report()
        assert "CAR RENTAL SYSTEM" in report
        assert "FLEET SUMMARY" in report
        assert "Toyota Corolla" in report

    def test_generate_admin_report_error_branch(self, carrental, monkeypatch):
        def _boom():
            raise RuntimeError("kaboom")

        monkeypatch.setattr(carrental.ReportManager, "get_fleet_summary", _boom)
        assert carrental.ReportManager.generate_admin_report() == "Error generating report"
