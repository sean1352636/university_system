"""
Tests for Cafe System CLI enhancements — suppliers, reservations, loyalty points,
and staff scheduling.

Tests cover the database-layer functions introduced in the cafe enhancements.
Uses in-memory SQLite so no real DB is touched.
"""

import pytest
from unittest.mock import patch, MagicMock
from education_system.post_18.university_system.infrastructure.database.db import sqlite3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MODULE = "education_system.post_18.university_system.modules.services.cli.cafe_system_cli"


def _make_cafe_db():
    """Create an in-memory SQLite DB with all cafe enhancement tables."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'cafe',
            source_product_id INTEGER,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            is_alcoholic INTEGER DEFAULT 0,
            is_available INTEGER DEFAULT 1,
            stock_quantity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cafe_suppliers (
            supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            payment_terms TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cafe_supplier_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            cost_per_unit REAL,
            notes TEXT,
            FOREIGN KEY (supplier_id) REFERENCES cafe_suppliers(supplier_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cafe_reservations (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            student_id TEXT,
            reservation_date DATE NOT NULL,
            reservation_time TIME NOT NULL,
            party_size INTEGER NOT NULL,
            status TEXT DEFAULT 'confirmed',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cafe_loyalty (
            loyalty_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cafe_loyalty_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            points_change INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES cafe_loyalty(student_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cafe_staff_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_name TEXT NOT NULL,
            position TEXT NOT NULL DEFAULT 'barista',
            day_of_week TEXT NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _NoCloseConn:
    """Wrapper that proxies everything to a real connection but ignores close()."""

    def __init__(self, real_conn):
        self._real = real_conn

    def close(self):
        pass  # no-op so the connection survives reuse across function calls

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture
def mem_conn():
    """Provide a fresh in-memory cafe DB for each test."""
    real_conn = _make_cafe_db()
    wrapper = _NoCloseConn(real_conn)
    yield wrapper
    real_conn.close()


@pytest.fixture
def _patch_db(mem_conn):
    """Patch get_db_connection so every cafe function uses mem_conn."""
    with patch(f"{MODULE}.get_db_connection", return_value=mem_conn):
        yield mem_conn


@pytest.fixture
def _patch_db_and_logger(mem_conn):
    """Patch DB connection and silence activity logger."""
    with patch(f"{MODULE}.get_db_connection", return_value=mem_conn), \
         patch(f"{MODULE}.ACTIVITY_LOGGER_AVAILABLE", False):
        yield mem_conn


# ---------------------------------------------------------------------------
# Tests — Supplier Management
# ---------------------------------------------------------------------------

class TestSupplierManagement:
    """Tests for supplier CRUD operations."""

    def test_add_supplier_returns_id(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import add_supplier

        sid = add_supplier("Bean World", "Alice", "alice@beans.com", "555-0101", "1 Bean St", "Net 30")
        assert sid is not None
        assert isinstance(sid, int)
        assert sid > 0

    def test_get_all_suppliers_returns_added(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            add_supplier, get_all_suppliers,
        )

        add_supplier("Bean World", "Alice", "alice@beans.com", "555-0101", "1 Bean St", "Net 30")
        add_supplier("Milk Co", "Bob", "bob@milk.com", "555-0202", "2 Dairy Ln", "Net 15")

        suppliers = get_all_suppliers()
        assert len(suppliers) == 2
        names = [s[1] for s in suppliers]
        assert "Bean World" in names
        assert "Milk Co" in names

    def test_update_supplier(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            add_supplier, update_supplier, get_supplier,
        )

        sid = add_supplier("Old Name", "C", "c@x.com", "555", "Addr", "Net 7")
        result = update_supplier(sid, "New Name", "D", "d@x.com", "666", "New Addr", "Net 60")
        assert result is True

        updated = get_supplier(sid)
        assert updated is not None
        assert updated[1] == "New Name"
        assert updated[2] == "D"

    def test_delete_supplier(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            add_supplier, delete_supplier, get_all_suppliers,
        )

        sid = add_supplier("Temp Supplier", "E", "e@x.com", "777", "Addr", "COD")
        assert delete_supplier(sid) is True
        assert len(get_all_suppliers()) == 0

    def test_link_supplier_to_product(self, _patch_db_and_logger, mem_conn):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            add_supplier, link_supplier_to_product, get_supplier_products,
        )

        # Insert a product first
        cur = mem_conn.cursor()
        cur.execute(
            "INSERT INTO products (source_type, name, category, description, price, is_available, stock_quantity) "
            "VALUES ('cafe', 'Espresso', 'Hot Drinks', 'Classic', 2.50, 1, 100)"
        )
        mem_conn.commit()
        product_id = cur.lastrowid

        sid = add_supplier("Bean World", "Alice", "a@b.com", "555", "Addr", "Net 30")
        assert link_supplier_to_product(sid, product_id, cost_per_unit=1.20, notes="Primary") is True

        products = get_supplier_products(sid)
        assert len(products) == 1
        assert products[0][1] == "Espresso"
        assert products[0][3] == 1.20


# ---------------------------------------------------------------------------
# Tests — Reservations
# ---------------------------------------------------------------------------

class TestReservations:
    """Tests for reservation CRUD operations."""

    def test_create_reservation_returns_id(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import create_reservation

        rid = create_reservation("Jane Doe", "STU0042", "2026-04-01", "12:30", 4, "Birthday lunch")
        assert rid is not None
        assert isinstance(rid, int)

    def test_view_reservations_all(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            create_reservation, get_all_reservations,
        )

        create_reservation("Jane", "STU0042", "2026-04-01", "12:30", 4)
        create_reservation("Bob", "STU0099", "2026-04-02", "13:00", 2)

        reservations = get_all_reservations(filter_type="all")
        assert len(reservations) == 2

    def test_update_reservation(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            create_reservation, update_reservation_details, get_reservation,
        )

        rid = create_reservation("Jane", "STU0042", "2026-04-01", "12:30", 4)
        result = update_reservation_details(rid, "Jane Updated", "2026-04-05", "14:00", 6, "Changed date")
        assert result is True

        updated = get_reservation(rid)
        assert updated[1] == "Jane Updated"
        assert updated[3] == "2026-04-05"
        assert updated[5] == 6

    def test_cancel_reservation(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            create_reservation, cancel_reservation, get_reservation,
        )

        rid = create_reservation("Jane", "STU0042", "2026-04-01", "12:30", 4)
        assert cancel_reservation(rid) is True

        cancelled = get_reservation(rid)
        assert cancelled[6] == "cancelled"


# ---------------------------------------------------------------------------
# Tests — Loyalty Points
# ---------------------------------------------------------------------------

class TestLoyaltyPoints:
    """Tests for loyalty account and points operations."""

    def test_get_or_create_loyalty_account_creates_new(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import get_or_create_loyalty_account

        account = get_or_create_loyalty_account("STU0042", "Jane Doe")
        assert account is not None
        assert account[1] == "STU0042"
        assert account[2] == "Jane Doe"
        assert account[3] == 0  # initial points

    def test_get_or_create_loyalty_account_returns_existing(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            get_or_create_loyalty_account, add_loyalty_points,
        )

        get_or_create_loyalty_account("STU0042", "Jane Doe")
        add_loyalty_points("STU0042", 50, "Welcome bonus")

        # Should return existing account with updated points
        account = get_or_create_loyalty_account("STU0042", "Jane Doe")
        assert account[3] == 50

    def test_add_loyalty_points(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            get_or_create_loyalty_account, add_loyalty_points, get_loyalty_account,
        )

        get_or_create_loyalty_account("STU0042", "Jane Doe")
        result = add_loyalty_points("STU0042", 100, "Purchase reward")
        assert result is True

        account = get_loyalty_account("STU0042")
        assert account[3] == 100

    def test_redeem_loyalty_points_success(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            get_or_create_loyalty_account, add_loyalty_points,
            redeem_loyalty_points, get_loyalty_account,
        )

        get_or_create_loyalty_account("STU0042", "Jane Doe")
        add_loyalty_points("STU0042", 200, "Accumulated")

        result = redeem_loyalty_points("STU0042", 75, "Free coffee")
        assert result is True

        account = get_loyalty_account("STU0042")
        assert account[3] == 125

    def test_redeem_loyalty_points_insufficient_balance(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            get_or_create_loyalty_account, add_loyalty_points, redeem_loyalty_points,
        )

        get_or_create_loyalty_account("STU0042", "Jane Doe")
        add_loyalty_points("STU0042", 10, "Small bonus")

        result = redeem_loyalty_points("STU0042", 50, "Too many points")
        assert result is False

    def test_view_loyalty_history(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            get_or_create_loyalty_account, add_loyalty_points,
            redeem_loyalty_points, get_loyalty_log,
        )

        get_or_create_loyalty_account("STU0042", "Jane Doe")
        add_loyalty_points("STU0042", 100, "Purchase")
        add_loyalty_points("STU0042", 50, "Bonus")
        redeem_loyalty_points("STU0042", 30, "Free pastry")

        log = get_loyalty_log("STU0042")
        assert len(log) == 3
        # Most recent first
        types = [entry[2] for entry in log]
        assert "redeemed" in types
        assert "added" in types


# ---------------------------------------------------------------------------
# Tests — Staff Scheduling
# ---------------------------------------------------------------------------

class TestStaffScheduling:
    """Tests for staff schedule management."""

    def test_add_staff_schedule(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import add_staff_schedule

        result = add_staff_schedule("Alice Smith", "barista", "Monday", "08:00", "14:00", "Morning shift")
        assert result is True

    def test_get_all_staff_schedules(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            add_staff_schedule, get_all_staff_schedules,
        )

        add_staff_schedule("Alice Smith", "barista", "Monday", "08:00", "14:00")
        add_staff_schedule("Bob Jones", "cashier", "Tuesday", "09:00", "17:00")
        add_staff_schedule("Alice Smith", "barista", "Wednesday", "08:00", "14:00")

        schedules = get_all_staff_schedules()
        assert len(schedules) == 3
        # Should be ordered by day of week then start time
        days = [s[3] for s in schedules]
        assert days == ["Monday", "Tuesday", "Wednesday"]

    def test_get_staff_schedule_by_name(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            add_staff_schedule, get_staff_schedule_by_name,
        )

        add_staff_schedule("Alice Smith", "barista", "Monday", "08:00", "14:00")
        add_staff_schedule("Bob Jones", "cashier", "Monday", "14:00", "20:00")
        add_staff_schedule("Alice Smith", "barista", "Friday", "08:00", "14:00")

        alice_schedules = get_staff_schedule_by_name("Alice")
        assert len(alice_schedules) == 2
        assert all("Alice" in s[1] for s in alice_schedules)

    def test_update_schedule_entry(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            add_staff_schedule, get_all_staff_schedules, update_staff_schedule_entry,
        )

        add_staff_schedule("Alice Smith", "barista", "Monday", "08:00", "14:00", "Morning")

        schedules = get_all_staff_schedules()
        schedule_id = schedules[0][0]

        result = update_staff_schedule_entry(schedule_id, "Tuesday", "09:00", "15:00", "Shifted")
        assert result is True

        updated = get_all_staff_schedules()
        assert updated[0][3] == "Tuesday"
        assert updated[0][4] == "09:00"
        assert updated[0][5] == "15:00"
        assert updated[0][6] == "Shifted"

    def test_delete_schedule_entry(self, _patch_db_and_logger):
        from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import (
            add_staff_schedule, get_all_staff_schedules, delete_staff_schedule_entry,
        )

        add_staff_schedule("Alice Smith", "barista", "Monday", "08:00", "14:00")
        add_staff_schedule("Bob Jones", "cashier", "Tuesday", "09:00", "17:00")

        schedules = get_all_staff_schedules()
        assert len(schedules) == 2

        result = delete_staff_schedule_entry(schedules[0][0])
        assert result is True

        remaining = get_all_staff_schedules()
        assert len(remaining) == 1
        assert remaining[0][1] == "Bob Jones"


# ---------------------------------------------------------------------------
# Tests — Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge-case and error-handling tests."""

    def test_add_supplier_with_no_db_returns_none(self):
        """When get_db_connection returns None, add_supplier should return None."""
        with patch(f"{MODULE}.get_db_connection", return_value=None), \
             patch(f"{MODULE}.ACTIVITY_LOGGER_AVAILABLE", False):
            from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import add_supplier
            result = add_supplier("X", "Y", "z@z.com", "111", "Addr", "COD")
            assert result is None

    def test_create_reservation_with_no_db_returns_none(self):
        """When get_db_connection returns None, create_reservation should return None."""
        with patch(f"{MODULE}.get_db_connection", return_value=None), \
             patch(f"{MODULE}.ACTIVITY_LOGGER_AVAILABLE", False):
            from education_system.post_18.university_system.modules.services.cli.cafe_system_cli import create_reservation
            result = create_reservation("Jane", "STU001", "2026-04-01", "12:00", 2)
            assert result is None
