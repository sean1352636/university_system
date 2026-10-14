"""Tests for the barber-shop core service managers."""

import pytest


# ── ServiceManager ───────────────────────────────────────────────────

class TestServiceManager:
    def test_add_and_get(self, barber):
        sid = barber.ServiceManager.add_service("Fade", "fade", 18.0, 40, "Fade cut")
        row = barber.ServiceManager.get_service(sid)
        assert row["name"] == "Fade"
        assert row["price"] == 18.0

    def test_get_missing_returns_none(self, barber):
        assert barber.ServiceManager.get_service(999) is None

    def test_get_all_available_only(self, barber):
        a = barber.ServiceManager.add_service("A", "haircut", 10.0)
        barber.ServiceManager.add_service("B", "haircut", 12.0)
        barber.ServiceManager.update_service(a, is_available=0)
        names = [s["name"] for s in barber.ServiceManager.get_all_services(available_only=True)]
        assert names == ["B"]
        all_names = {s["name"] for s in barber.ServiceManager.get_all_services(available_only=False)}
        assert all_names == {"A", "B"}

    def test_update_unknown_fields_is_false(self, barber):
        sid = barber.ServiceManager.add_service("A", "haircut", 10.0)
        assert barber.ServiceManager.update_service(sid, bogus="x") is False

    def test_update_price(self, barber):
        sid = barber.ServiceManager.add_service("A", "haircut", 10.0)
        assert barber.ServiceManager.update_service(sid, price=25.0) is True
        assert barber.ServiceManager.get_service(sid)["price"] == 25.0


# ── StaffManager ─────────────────────────────────────────────────────

class TestStaffManager:
    def test_add_and_get(self, barber):
        sid = barber.StaffManager.add_staff("Alex", employee_id="E1", specialties="fades")
        row = barber.StaffManager.get_staff(sid)
        assert row["name"] == "Alex"
        assert row["is_active"] == 1

    def test_get_all_active_only(self, barber):
        barber.StaffManager.add_staff("Active", employee_id="E1")
        row_id = barber.StaffManager.add_staff("Inactive", employee_id="E2")
        with barber.transaction() as conn:
            conn.execute("UPDATE barber_staff SET is_active = 0 WHERE staff_id = ?", (row_id,))
        names = [s["name"] for s in barber.StaffManager.get_all_staff(active_only=True)]
        assert names == ["Active"]

    def test_availability_excludes_booked_slots(self, seeded):
        barber, service_id, staff_id = seeded
        barber.AppointmentManager.book_appointment(
            "C1", "Cust", service_id, "2026-08-01", "09:00", staff_id=staff_id
        )
        free = barber.StaffManager.get_staff_availability(staff_id, "2026-08-01")
        assert "09:00" not in free
        assert "09:30" in free


# ── AppointmentManager ───────────────────────────────────────────────

class TestAppointmentManager:
    def test_book_returns_id_and_number(self, seeded):
        barber, service_id, staff_id = seeded
        appt_id, number = barber.AppointmentManager.book_appointment(
            "C1", "Cust", service_id, "2026-08-01", "10:00", staff_id=staff_id
        )
        assert appt_id > 0
        assert number.startswith("BAR-")
        row = barber.AppointmentManager.get_appointment(appt_id)
        assert row["staff_name"] == "Dev Barber"
        assert row["service_name"] == "Standard Haircut"
        assert row["price"] == 15.0
        assert row["status"] == "scheduled"

    def test_book_unknown_service_raises(self, barber):
        with pytest.raises(ValueError):
            barber.AppointmentManager.book_appointment("C1", "Cust", 9999, "2026-08-01", "10:00")

    def test_get_by_number(self, seeded):
        barber, service_id, _ = seeded
        _, number = barber.AppointmentManager.book_appointment(
            "C1", "Cust", service_id, "2026-08-01", "10:00"
        )
        row = barber.AppointmentManager.get_appointment_by_number(number)
        assert row["appointment_number"] == number

    def test_update_status_valid_and_invalid(self, seeded):
        barber, service_id, _ = seeded
        appt_id, _ = barber.AppointmentManager.book_appointment(
            "C1", "Cust", service_id, "2026-08-01", "10:00"
        )
        assert barber.AppointmentManager.update_status(appt_id, "completed") is True
        assert barber.AppointmentManager.get_appointment(appt_id)["status"] == "completed"
        assert barber.AppointmentManager.update_status(appt_id, "not_a_status") is False

    def test_cancel_sets_status_and_reason(self, seeded):
        barber, service_id, _ = seeded
        appt_id, _ = barber.AppointmentManager.book_appointment(
            "C1", "Cust", service_id, "2026-08-01", "10:00"
        )
        assert barber.AppointmentManager.cancel_appointment(appt_id, reason="sick") is True
        row = barber.AppointmentManager.get_appointment(appt_id)
        assert row["status"] == "cancelled"
        assert row["notes"] == "sick"

    def test_reschedule_updates_date_time_and_staff(self, seeded):
        barber, service_id, staff_id = seeded
        appt_id, _ = barber.AppointmentManager.book_appointment(
            "C1", "Cust", service_id, "2026-08-01", "10:00"
        )
        assert barber.AppointmentManager.reschedule_appointment(
            appt_id, "2026-08-02", "11:00", new_staff_id=staff_id
        ) is True
        row = barber.AppointmentManager.get_appointment(appt_id)
        assert row["appointment_date"] == "2026-08-02"
        assert row["appointment_time"] == "11:00"
        assert row["staff_id"] == staff_id

    def test_get_by_date_and_customer(self, seeded):
        barber, service_id, _ = seeded
        barber.AppointmentManager.book_appointment("C1", "A", service_id, "2026-08-01", "09:00")
        barber.AppointmentManager.book_appointment("C2", "B", service_id, "2026-08-01", "10:00")
        barber.AppointmentManager.book_appointment("C1", "A", service_id, "2026-08-05", "09:00")
        assert len(barber.AppointmentManager.get_appointments_by_date("2026-08-01")) == 2
        assert len(barber.AppointmentManager.get_customer_appointments("C1")) == 2


# ── TransactionManager ───────────────────────────────────────────────

class TestTransactionManager:
    def _book(self, barber, service_id, staff_id):
        appt_id, _ = barber.AppointmentManager.book_appointment(
            "C1", "Cust", service_id, "2026-08-01", "10:00", staff_id=staff_id
        )
        return appt_id

    def test_process_payment_records_and_marks_paid(self, seeded):
        barber, service_id, staff_id = seeded
        appt_id = self._book(barber, service_id, staff_id)
        txn_id = barber.TransactionManager.process_payment(
            appt_id, 15.0, "card", "C1", tip_amount=3.0, processed_by="admin"
        )
        assert txn_id > 0
        txn = barber.TransactionManager.get_transaction(txn_id)
        assert txn["amount"] == 15.0
        assert txn["tip_amount"] == 3.0
        assert txn["source_type"] == "barber"
        # Appointment flips to paid.
        assert barber.AppointmentManager.get_appointment(appt_id)["payment_status"] == "paid"

    def test_get_transaction_missing_returns_none(self, barber):
        assert barber.TransactionManager.get_transaction(999) is None

    def test_mark_receipt_sent(self, seeded):
        barber, service_id, staff_id = seeded
        appt_id = self._book(barber, service_id, staff_id)
        txn_id = barber.TransactionManager.process_payment(appt_id, 15.0, "cash", "C1")
        assert barber.TransactionManager.mark_receipt_sent(txn_id) is True
        assert barber.TransactionManager.get_transaction(txn_id)["receipt_sent"] == 1

    def test_daily_revenue_aggregates_completed(self, seeded):
        barber, service_id, staff_id = seeded
        appt_id = self._book(barber, service_id, staff_id)
        barber.TransactionManager.process_payment(appt_id, 15.0, "card", "C1", tip_amount=5.0)
        today = _today()
        rev = barber.TransactionManager.get_daily_revenue(today)
        # Rows default to status 'completed', so they count immediately.
        assert rev["transaction_count"] == 1
        assert rev["service_revenue"] == 15.0
        assert rev["tips"] == 5.0
        assert rev["total_revenue"] == 20.0

    def test_daily_revenue_empty_day(self, barber):
        rev = barber.TransactionManager.get_daily_revenue("1999-01-01")
        assert rev["transaction_count"] == 0
        assert rev["total_revenue"] == 0


# ── CustomerManager ──────────────────────────────────────────────────

class TestCustomerManager:
    def test_create_and_get_profile(self, barber):
        barber.CustomerManager.create_profile("C1", "Sam", email="s@x.com", phone="123")
        row = barber.CustomerManager.get_profile("C1")
        assert row["name"] == "Sam"
        assert barber.CustomerManager.get_customer("C1")["email"] == "s@x.com"

    def test_create_profile_is_upsert(self, barber):
        barber.CustomerManager.create_profile("C1", "Old Name")
        barber.CustomerManager.create_profile("C1", "New Name")
        assert barber.CustomerManager.get_profile("C1")["name"] == "New Name"
        assert len(barber.CustomerManager.get_all_customers()) == 1

    def test_update_profile(self, barber):
        barber.CustomerManager.create_profile("C1", "Sam")
        assert barber.CustomerManager.update_profile("C1", phone="999") is True
        assert barber.CustomerManager.get_profile("C1")["phone"] == "999"
        assert barber.CustomerManager.update_profile("C1", bogus="x") is False

    def test_notes_roundtrip_newest_first(self, barber):
        barber.CustomerManager.create_profile("C1", "Sam")
        barber.CustomerManager.add_note("C1", "first note", "general", "admin")
        barber.CustomerManager.add_note("C1", "second note", "general", "admin")
        notes = barber.CustomerManager.get_notes("C1")
        assert len(notes) == 2
        assert {n["note"] for n in notes} == {"first note", "second note"}

    def test_search_customers(self, barber):
        barber.CustomerManager.create_profile("C1", "Alice Smith", email="alice@x.com")
        barber.CustomerManager.create_profile("C2", "Bob Jones", email="bob@x.com")
        found = barber.CustomerManager.search_customers("alice")
        assert len(found) == 1
        assert found[0]["customer_id"] == "C1"


# ── WaitlistManager ──────────────────────────────────────────────────

class TestWaitlistManager:
    def test_add_and_get(self, seeded):
        barber, service_id, _ = seeded
        wid = barber.WaitlistManager.add_to_waitlist(
            "C1", "Cust", "c@x.com", "123", "2026-08-01", "10:00", service_id
        )
        assert wid > 0
        entries = barber.WaitlistManager.get_waitlist(date="2026-08-01")
        assert len(entries) == 1
        assert entries[0]["customer_id"] == "C1"

    def test_notify_and_remove_change_status(self, seeded):
        barber, service_id, _ = seeded
        wid = barber.WaitlistManager.add_to_waitlist(
            "C1", "Cust", "c@x.com", "123", "2026-08-01", "10:00", service_id
        )
        assert barber.WaitlistManager.notify_waitlist(wid, "11:00") is True
        # No longer 'waiting', so it drops out of the active waitlist.
        assert barber.WaitlistManager.get_waitlist(date="2026-08-01") == []
        barber.WaitlistManager.remove_from_waitlist(wid, reason="booked")


# ── BlockedSlotManager ───────────────────────────────────────────────

class TestBlockedSlotManager:
    def test_block_get_unblock(self, seeded):
        barber, _, staff_id = seeded
        bid = barber.BlockedSlotManager.block_slot(
            staff_id, "2026-08-01", "12:00", "13:00", "lunch", "admin"
        )
        assert bid > 0
        slots = barber.BlockedSlotManager.get_blocked_slots(staff_id=staff_id, date="2026-08-01")
        assert len(slots) == 1
        assert slots[0]["reason"] == "lunch"
        assert barber.BlockedSlotManager.unblock_slot(bid) is True
        assert barber.BlockedSlotManager.get_blocked_slots(staff_id=staff_id) == []


# ── RecurringAppointmentManager ──────────────────────────────────────

class TestRecurringAppointmentManager:
    def test_create_get_cancel(self, seeded):
        barber, service_id, staff_id = seeded
        rid = barber.RecurringAppointmentManager.create_recurring(
            "C1", "Cust", "c@x.com", service_id, staff_id, 1, "10:00", "weekly", "2026-08-01"
        )
        assert rid > 0
        recs = barber.RecurringAppointmentManager.get_customer_recurring("C1")
        assert len(recs) == 1
        assert recs[0]["service_name"] == "Standard Haircut"
        assert barber.RecurringAppointmentManager.cancel_recurring(rid) is True
        # is_active flips to 0, so it drops from the active listing.
        assert barber.RecurringAppointmentManager.get_customer_recurring("C1") == []


def _today():
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d")
