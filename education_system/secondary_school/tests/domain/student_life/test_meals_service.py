"""Tests for MealsService."""
import pytest

from education_system.secondary_school.modules.domain.student_life.meals.services.meals_service import MealsService


@pytest.fixture
def meals_service(db_path):
    return MealsService(db_path)


class TestRegistrations:
    def test_register_student(self, meals_service, sample_student):
        meals_service.register_student(
            student_id=sample_student["id"],
            meal_preference="vegetarian",
        )
        regs = meals_service.list_registrations()
        assert len(regs) == 1
        assert regs[0]["meal_preference"] == "vegetarian"

    def test_register_student_fsm(self, meals_service, sample_student):
        meals_service.register_student(
            student_id=sample_student["id"],
            free_school_meals=True,
        )
        regs = meals_service.list_registrations()
        assert regs[0]["free_school_meals"] == 1

    def test_list_registrations(self, meals_service, sample_student, sample_student_ks4):
        meals_service.register_student(sample_student["id"])
        meals_service.register_student(sample_student_ks4["id"])
        regs = meals_service.list_registrations()
        assert len(regs) == 2

    def test_list_registrations_fsm_only(self, meals_service, sample_student, sample_student_ks4):
        meals_service.register_student(sample_student["id"], free_school_meals=True)
        meals_service.register_student(sample_student_ks4["id"], free_school_meals=False)
        regs = meals_service.list_registrations(fsm_only=True)
        assert len(regs) == 1

    def test_fsm_count(self, meals_service, sample_student, sample_student_ks4):
        meals_service.register_student(sample_student["id"], free_school_meals=True)
        meals_service.register_student(sample_student_ks4["id"], free_school_meals=True)
        assert meals_service.fsm_count() == 2


class TestBookings:
    def test_book_meal(self, meals_service, sample_student):
        meals_service.book_meal(
            student_id=sample_student["id"],
            date="2026-03-20", meal_type="lunch",
            menu_choice="Pasta",
        )
        bookings = meals_service.list_bookings(date="2026-03-20")
        assert len(bookings) == 1
        assert bookings[0]["menu_choice"] == "Pasta"

    def test_list_bookings_by_date(self, meals_service, sample_student):
        meals_service.book_meal(sample_student["id"], "2026-03-20")
        meals_service.book_meal(sample_student["id"], "2026-03-21")
        bookings = meals_service.list_bookings(date="2026-03-20")
        assert len(bookings) == 1

    def test_cancel_booking(self, meals_service, sample_student):
        meals_service.book_meal(sample_student["id"], "2026-03-20")
        bookings = meals_service.list_bookings(date="2026-03-20")
        meals_service.cancel_booking(bookings[0]["id"])
        # Cancelled booking still exists but with status 'cancelled'
        all_bookings = meals_service.list_bookings(date="2026-03-20")
        assert all_bookings[0]["status"] == "cancelled"
