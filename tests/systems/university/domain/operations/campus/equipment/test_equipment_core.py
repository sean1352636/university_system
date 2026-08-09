"""Tests for the Equipment Rental core service.

Exercises EquipmentManager (inventory CRUD), RentalManager (rental
lifecycle: create / checkout / return / cancel / extend), and
ReportManager (analytics). Each test gets an isolated SQLite file via
the ``equipment_db`` fixture, which monkeypatches DEFAULT_DB_PATH and
calls ``init_equipment_db``.

TransactionManager.record_payment is not covered here: it writes to the
unified ``transactions`` and ``payments`` tables and posts to the finance
ledger, none of which are created by ``init_equipment_db``. Testing it
would require standing up the finance schema, which is out of scope for a
focused unit test of the equipment core.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.domain.operations.campus.equipment.services.equipment_core import (
    EquipmentManager,
    RentalManager,
    ReportManager,
    init_equipment_db,
)


@pytest.fixture
def equipment_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "equipment_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    assert init_equipment_db() is True
    yield db_path


def _add_item(**overrides) -> int:
    defaults = dict(
        item_code="CAM-001",
        name="DSLR Camera",
        category="cameras",
        daily_rate=25.0,
    )
    defaults.update(overrides)
    code = defaults.pop("item_code")
    name = defaults.pop("name")
    category = defaults.pop("category")
    daily_rate = defaults.pop("daily_rate")
    return EquipmentManager.add_item(code, name, category, daily_rate, **defaults)


def _create_rental(item_id: int, **overrides) -> int:
    today = date.today()
    defaults = dict(
        item_id=item_id,
        borrower_id="S12345",
        borrower_name="Alice Student",
        checkout_date=today.isoformat(),
        checkout_time="09:00",
        due_date=(today + timedelta(days=3)).isoformat(),
        due_time="17:00",
        daily_rate=25.0,
        quantity=1,
    )
    defaults.update(overrides)
    return RentalManager.create_rental(**defaults)


class TestEquipmentManager:
    def test_add_item_returns_id_and_persists(self, equipment_db):
        item_id = _add_item(
            quantity_total=3,
            location="AV Store",
            deposit_required=50.0,
        )
        assert isinstance(item_id, int) and item_id > 0

        item = EquipmentManager.get_item(item_id)
        assert item is not None
        assert item["item_code"] == "CAM-001"
        assert item["name"] == "DSLR Camera"
        assert item["category"] == "cameras"
        assert item["daily_rate"] == pytest.approx(25.0)
        assert item["quantity_total"] == 3
        # quantity_available defaults to quantity_total when not given
        assert item["quantity_available"] == 3
        assert item["is_active"] == 1

    def test_get_item_missing_returns_none(self, equipment_db):
        assert EquipmentManager.get_item(999999) is None

    def test_update_item_changes_fields(self, equipment_db):
        item_id = _add_item()
        assert EquipmentManager.update_item(item_id, name="Updated Cam", daily_rate=40.0) is True

        item = EquipmentManager.get_item(item_id)
        assert item["name"] == "Updated Cam"
        assert item["daily_rate"] == pytest.approx(40.0)

    def test_update_item_with_no_fields_returns_false(self, equipment_db):
        item_id = _add_item()
        # All-None kwargs produce no updates -> False
        assert EquipmentManager.update_item(item_id, name=None, location=None) is False

    def test_get_all_and_available_items(self, equipment_db):
        a = _add_item(item_code="A-1", name="Alpha", category="tools")
        b = _add_item(item_code="B-1", name="Bravo", category="cameras", quantity_total=2)
        # Make one item unavailable.
        EquipmentManager.update_item(a, quantity_available=0)

        all_codes = {i["item_code"] for i in EquipmentManager.get_all_items()}
        assert all_codes == {"A-1", "B-1"}

        avail_codes = {i["item_code"] for i in EquipmentManager.get_available_items()}
        assert avail_codes == {"B-1"}

        # Category filter on available items.
        cam = EquipmentManager.get_available_items(category="cameras")
        assert {i["item_code"] for i in cam} == {"B-1"}
        assert EquipmentManager.get_available_items(category="tools") == []

    def test_update_availability_delta(self, equipment_db):
        item_id = _add_item(quantity_total=5, quantity_available=5)
        assert EquipmentManager.update_availability(item_id, -2) is True
        assert EquipmentManager.get_item(item_id)["quantity_available"] == 3
        assert EquipmentManager.update_availability(item_id, 1) is True
        assert EquipmentManager.get_item(item_id)["quantity_available"] == 4


class TestRentalManager:
    def test_generate_rental_number_format(self, equipment_db):
        num = RentalManager.generate_rental_number()
        assert num.startswith("EQR-")
        assert len(num) > len("EQR-")

    def test_create_rental_computes_totals_and_decrements_availability(self, equipment_db):
        item_id = _add_item(quantity_total=2, quantity_available=2)
        rental_id = _create_rental(item_id, deposit_amount=10.0)
        assert isinstance(rental_id, int) and rental_id > 0

        rental = RentalManager.get_rental(rental_id)
        assert rental is not None
        assert rental["status"] == "reserved"
        assert rental["total_days"] == 3
        assert rental["subtotal"] == pytest.approx(75.0)  # 25 * 3 * 1
        assert rental["total_amount"] == pytest.approx(85.0)  # subtotal + deposit
        # Joined item columns are present.
        assert rental["item_code"] == "CAM-001"
        assert rental["item_name"] == "DSLR Camera"

        # Availability decremented by quantity.
        assert EquipmentManager.get_item(item_id)["quantity_available"] == 1

    def test_create_rental_same_day_minimum_one_day(self, equipment_db):
        item_id = _add_item()
        today = date.today().isoformat()
        rental_id = _create_rental(item_id, checkout_date=today, due_date=today)
        rental = RentalManager.get_rental(rental_id)
        assert rental["total_days"] == 1
        assert rental["subtotal"] == pytest.approx(25.0)

    def test_get_rentals_by_status(self, equipment_db):
        item_id = _add_item(quantity_total=5, quantity_available=5)
        r1 = _create_rental(item_id)
        r2 = _create_rental(item_id)
        RentalManager.checkout_item(r1)

        reserved = RentalManager.get_rentals_by_status("reserved")
        assert {r["rental_id"] for r in reserved} == {r2}

        checked_out = RentalManager.get_rentals_by_status("checked_out")
        assert {r["rental_id"] for r in checked_out} == {r1}

        # No status -> all rentals.
        all_rentals = RentalManager.get_rentals_by_status()
        assert {r["rental_id"] for r in all_rentals} == {r1, r2}

    def test_checkout_item_sets_status_and_condition(self, equipment_db):
        item_id = _add_item()
        rental_id = _create_rental(item_id)
        assert RentalManager.checkout_item(rental_id, condition="excellent") is True

        rental = RentalManager.get_rental(rental_id)
        assert rental["status"] == "checked_out"
        assert rental["condition_checkout"] == "excellent"

    def test_return_item_restores_availability_and_adds_fees(self, equipment_db):
        item_id = _add_item(quantity_total=2, quantity_available=2)
        rental_id = _create_rental(item_id)
        RentalManager.checkout_item(rental_id)
        before_total = RentalManager.get_rental(rental_id)["total_amount"]

        assert RentalManager.return_item(
            rental_id, condition="good", late_fee=5.0, damage_fee=2.5
        ) is True

        rental = RentalManager.get_rental(rental_id)
        assert rental["status"] == "returned"
        assert rental["condition_return"] == "good"
        assert rental["late_fee"] == pytest.approx(5.0)
        assert rental["damage_fee"] == pytest.approx(2.5)
        assert rental["total_amount"] == pytest.approx(before_total + 7.5)
        assert rental["actual_return_date"]
        # Availability restored.
        assert EquipmentManager.get_item(item_id)["quantity_available"] == 2

    def test_return_missing_rental_returns_false(self, equipment_db):
        assert RentalManager.return_item(999999, condition="good") is False

    def test_cancel_rental_restores_availability(self, equipment_db):
        item_id = _add_item(quantity_total=3, quantity_available=3)
        rental_id = _create_rental(item_id, quantity=2)
        assert EquipmentManager.get_item(item_id)["quantity_available"] == 1

        assert RentalManager.cancel_rental(rental_id, reason="No longer needed") is True
        rental = RentalManager.get_rental(rental_id)
        assert rental["status"] == "cancelled"
        assert rental["notes"] == "No longer needed"
        assert EquipmentManager.get_item(item_id)["quantity_available"] == 3

    def test_cancel_missing_rental_returns_false(self, equipment_db):
        assert RentalManager.cancel_rental(999999) is False

    def test_extend_rental_recomputes_totals(self, equipment_db):
        item_id = _add_item()
        today = date.today()
        rental_id = _create_rental(
            item_id,
            checkout_date=today.isoformat(),
            due_date=(today + timedelta(days=2)).isoformat(),
        )
        assert RentalManager.get_rental(rental_id)["total_days"] == 2

        new_due = (today + timedelta(days=5)).isoformat()
        assert RentalManager.extend_rental(rental_id, new_due, "17:00") is True

        rental = RentalManager.get_rental(rental_id)
        assert rental["due_date"] == new_due
        assert rental["total_days"] == 5
        assert rental["subtotal"] == pytest.approx(125.0)  # 25 * 5

    def test_extend_missing_rental_returns_false(self, equipment_db):
        future = (date.today() + timedelta(days=5)).isoformat()
        assert RentalManager.extend_rental(999999, future, "17:00") is False


class TestReportManager:
    def test_inventory_summary_aggregates(self, equipment_db):
        i1 = _add_item(item_code="I-1", quantity_total=4, quantity_available=4)
        _add_item(item_code="I-2", quantity_total=2, quantity_available=2)
        # Rent out one unit of the first item.
        _create_rental(i1)

        summary = ReportManager.get_inventory_summary()
        assert summary["total_items"] == 2
        assert summary["total_quantity"] == 6
        assert summary["available_quantity"] == 5
        assert summary["rented_quantity"] == 1

    def test_get_overdue_rentals(self, equipment_db):
        item_id = _add_item(quantity_total=5, quantity_available=5)
        today = date.today()
        # Overdue: checked out and due in the past.
        overdue_id = _create_rental(
            item_id,
            checkout_date=(today - timedelta(days=10)).isoformat(),
            due_date=(today - timedelta(days=2)).isoformat(),
        )
        RentalManager.checkout_item(overdue_id)
        # Not overdue: due in the future, also checked out.
        future_id = _create_rental(
            item_id,
            due_date=(today + timedelta(days=5)).isoformat(),
        )
        RentalManager.checkout_item(future_id)

        overdue = ReportManager.get_overdue_rentals()
        assert {r["rental_id"] for r in overdue} == {overdue_id}

    def test_popular_items_ordered_by_rental_count(self, equipment_db):
        a = _add_item(item_code="POP-A", name="Popular", quantity_total=10, quantity_available=10)
        b = _add_item(item_code="POP-B", name="Quiet", quantity_total=10, quantity_available=10)
        for _ in range(3):
            _create_rental(a)
        _create_rental(b)

        popular = ReportManager.get_popular_items(limit=10)
        # Most-rented first.
        assert popular[0]["item_id"] == a
        counts = {p["item_id"]: p["rental_count"] for p in popular}
        assert counts[a] == 3
        assert counts[b] == 1

    def test_generate_admin_report_contains_sections(self, equipment_db):
        item_id = _add_item()
        _create_rental(item_id)
        report = ReportManager.generate_admin_report()
        assert "EQUIPMENT RENTAL SYSTEM - ADMIN REPORT" in report
        assert "INVENTORY SUMMARY" in report
        assert "REVENUE SUMMARY" in report
        assert "OVERDUE RENTALS" in report
