"""Tests for the PayrollService in the Primary School system."""

import pytest


@pytest.fixture
def staff_id(hr_service):
    """Create a staff member and return their integer PK."""
    created = hr_service.create_staff(
        first_name="Payroll",
        last_name="Test",
        email="payroll.test@school.local",
        role="Teacher",
        department="Year 3",
    )
    full = hr_service.get_staff(created["staff_id"])
    return full["id"]


@pytest.fixture
def second_staff_id(hr_service):
    """Create a second staff member and return their integer PK."""
    created = hr_service.create_staff(
        first_name="Second",
        last_name="Staff",
        email="second.staff@school.local",
        role="Teacher",
        department="Year 4",
    )
    full = hr_service.get_staff(created["staff_id"])
    return full["id"]


class TestCreate:
    """Tests for creating payroll records."""

    def test_create_returns_id(self, payroll_service, staff_id):
        """Creating a payroll record returns a positive integer ID."""
        record_id = payroll_service.create(
            staff_id=staff_id,
            pay_period="2026-03",
            gross_pay=3200.00,
            tax=480.00,
            ni_contribution=256.00,
            pension=160.00,
            other_deductions=0.00,
            net_pay=2304.00,
            status="draft",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_persists(self, payroll_service, staff_id):
        """Created record can be retrieved by ID."""
        record_id = payroll_service.create(
            staff_id=staff_id,
            pay_period="2026-04",
            gross_pay=2800.00,
            tax=420.00,
            ni_contribution=224.00,
            pension=140.00,
            other_deductions=50.00,
            net_pay=1966.00,
            status="draft",
        )
        fetched = payroll_service.get(record_id)
        assert fetched is not None
        assert fetched["staff_id"] == staff_id
        assert fetched["gross_pay"] == 2800.00

    def test_create_multiple(self, payroll_service, staff_id):
        """Multiple records receive distinct IDs."""
        id1 = payroll_service.create(
            staff_id=staff_id, pay_period="2026-01",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        id2 = payroll_service.create(
            staff_id=staff_id, pay_period="2026-02",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        assert id1 != id2


class TestListAll:
    """Tests for listing payroll records."""

    def test_list_all_empty_db(self, payroll_service):
        """Listing on an empty database returns an empty list."""
        assert payroll_service.list_all() == []

    def test_list_all_returns_records(self, payroll_service, staff_id, second_staff_id):
        """All created records appear in the list."""
        payroll_service.create(
            staff_id=staff_id, pay_period="2026-01",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        payroll_service.create(
            staff_id=second_staff_id, pay_period="2026-01",
            gross_pay=2500, tax=375, ni_contribution=200,
            pension=125, other_deductions=0, net_pay=1800, status="draft",
        )
        results = payroll_service.list_all()
        assert len(results) == 2

    def test_list_all_with_filter(self, payroll_service, staff_id, second_staff_id):
        """Filtering by staff_id returns only matching records."""
        payroll_service.create(
            staff_id=staff_id, pay_period="2026-03",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        payroll_service.create(
            staff_id=second_staff_id, pay_period="2026-03",
            gross_pay=2500, tax=375, ni_contribution=200,
            pension=125, other_deductions=0, net_pay=1800, status="draft",
        )
        results = payroll_service.list_all(staff_id=staff_id)
        assert len(results) == 1
        assert results[0]["staff_id"] == staff_id


class TestGet:
    """Tests for retrieving a single payroll record."""

    def test_get_nonexistent_returns_none(self, payroll_service):
        """Fetching a non-existent ID returns None."""
        assert payroll_service.get(99999) is None


class TestUpdate:
    """Tests for updating payroll records."""

    def test_update_returns_true(self, payroll_service, staff_id):
        """Updating a record returns True."""
        record_id = payroll_service.create(
            staff_id=staff_id, pay_period="2026-01",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        result = payroll_service.update(record_id, status="pending_approval")
        assert result is True

    def test_update_persists(self, payroll_service, staff_id):
        """Updated fields are reflected on retrieval."""
        record_id = payroll_service.create(
            staff_id=staff_id, pay_period="2026-02",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        payroll_service.update(record_id, net_pay=2500.00, status="approved")
        fetched = payroll_service.get(record_id)
        assert fetched["net_pay"] == 2500.00
        assert fetched["status"] == "approved"

    def test_update_empty_kwargs_returns_false(self, payroll_service, staff_id):
        """Passing no fields returns False."""
        record_id = payroll_service.create(
            staff_id=staff_id, pay_period="2026-03",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        result = payroll_service.update(record_id)
        assert result is False


class TestDelete:
    """Tests for deleting payroll records."""

    def test_delete_existing(self, payroll_service, staff_id):
        """Deleting an existing record returns True and removes it."""
        record_id = payroll_service.create(
            staff_id=staff_id, pay_period="2026-01",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        assert payroll_service.delete(record_id) is True
        assert payroll_service.get(record_id) is None

    def test_delete_does_not_affect_others(self, payroll_service, staff_id, second_staff_id):
        """Deleting one record leaves other records intact."""
        id1 = payroll_service.create(
            staff_id=staff_id, pay_period="2026-01",
            gross_pay=3000, tax=450, ni_contribution=240,
            pension=150, other_deductions=0, net_pay=2160, status="draft",
        )
        id2 = payroll_service.create(
            staff_id=second_staff_id, pay_period="2026-01",
            gross_pay=2500, tax=375, ni_contribution=200,
            pension=125, other_deductions=0, net_pay=1800, status="draft",
        )
        payroll_service.delete(id2)
        remaining = payroll_service.list_all()
        assert len(remaining) == 1
        assert remaining[0]["id"] == id1
