"""Tests for LettingsService."""

import pytest


class TestLettingsService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.lettings.services.lettings_service import LettingsService
        return LettingsService(db_path)

    def test_create_booking(self, service):
        booking = service.create_booking(
            hirer_name="Local FC", facility="Sports Hall",
            booking_date="2026-05-10",
            start_time="18:00", end_time="20:00",
        )
        assert booking is not None

    def test_list_bookings(self, service):
        service.create_booking("Org A", "Hall", "2026-05-10", "09:00", "12:00")
        service.create_booking("Org B", "Field", "2026-05-11", "14:00", "16:00")
        bookings = service.list_bookings()
        assert len(bookings) >= 2

    def test_get_booking(self, service):
        booking = service.create_booking("Test", "Room 1", "2026-05-10", "10:00", "11:00")
        found = service.get_booking(booking["id"])
        assert found["hirer_name"] == "Test"

    def test_update_booking(self, service):
        booking = service.create_booking("Hirer", "Hall", "2026-05-10", "09:00", "10:00")
        updated = service.update_booking(booking["id"], facility="Main Hall")
        assert updated is not None

    def test_delete_booking(self, service):
        booking = service.create_booking("Temp", "Room", "2026-05-10", "09:00", "10:00")
        result = service.delete_booking(booking["id"])
        assert result is True

    def test_confirm_booking(self, service):
        booking = service.create_booking("Club", "Gym", "2026-05-10", "18:00", "20:00")
        confirmed = service.confirm_booking(booking["id"])
        assert confirmed["status"] in ("confirmed", "approved")

    def test_cancel_booking(self, service):
        booking = service.create_booking("Club", "Gym", "2026-05-10", "18:00", "20:00")
        cancelled = service.cancel_booking(booking["id"])
        assert cancelled["status"] == "cancelled"

    def test_create_contract(self, service):
        contract = service.create_contract(hirer_name="Weekly Club")
        assert contract is not None

    def test_list_contracts(self, service):
        service.create_contract(hirer_name="Org A")
        contracts = service.list_contracts()
        assert len(contracts) >= 1

    def test_sign_contract(self, service):
        contract = service.create_contract(hirer_name="Signer")
        signed = service.sign_contract(contract["id"], signed_date="2026-04-01")
        assert signed is not None

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
