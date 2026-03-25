"""Tests for TripsService."""
import pytest

from education_system.secondary_school.modules.domain.student_life.trips.services.trips_service import TripsService


@pytest.fixture
def trips_service(db_path):
    return TripsService(db_path)


class TestTrips:
    def test_create_trip(self, trips_service):
        trip = trips_service.create_trip(
            title="Science Museum Visit", date="2026-05-15",
            destination="Science Museum, London",
            lead_teacher="Dr Clarke", max_students=30,
            cost_per_student=12.50,
        )
        assert trip["title"] == "Science Museum Visit"
        assert trip["status"] == "planned"
        assert trip["cost_per_student"] == 12.50

    def test_list_trips(self, trips_service):
        trips_service.create_trip("Trip A", "2026-05-10")
        trips_service.create_trip("Trip B", "2026-06-01")
        result = trips_service.list_trips()
        assert len(result) == 2

    def test_update_status(self, trips_service):
        trip = trips_service.create_trip("Trip", "2026-05-10")
        trips_service.update_status(trip["id"], "approved")
        trips = trips_service.list_trips()
        assert trips[0]["status"] == "approved"

    def test_mark_risk_assessment(self, trips_service):
        trip = trips_service.create_trip("Trip", "2026-05-10")
        trips_service.mark_risk_assessment(trip["id"])
        trips = trips_service.list_trips()
        assert trips[0]["risk_assessment_done"] == 1

    def test_delete_trip(self, trips_service):
        trip = trips_service.create_trip("Temp Trip", "2026-05-10")
        trips_service.delete_trip(trip["id"])
        result = trips_service.list_trips()
        assert len(result) == 0


class TestTripStudents:
    def test_add_student(self, trips_service, sample_student):
        trip = trips_service.create_trip("Trip", "2026-05-10")
        trips_service.add_student(trip["id"], sample_student["id"],
                                  emergency_contact="Mrs Doe", emergency_phone="07700900001")
        students = trips_service.list_trip_students(trip["id"])
        assert len(students) == 1
        assert students[0]["first_name"] == "John"

    def test_list_trip_students(self, trips_service, sample_student, sample_student_ks4):
        trip = trips_service.create_trip("Trip", "2026-05-10")
        trips_service.add_student(trip["id"], sample_student["id"])
        trips_service.add_student(trip["id"], sample_student_ks4["id"])
        students = trips_service.list_trip_students(trip["id"])
        assert len(students) == 2

    def test_update_consent(self, trips_service, sample_student):
        trip = trips_service.create_trip("Trip", "2026-05-10")
        trips_service.add_student(trip["id"], sample_student["id"])
        students = trips_service.list_trip_students(trip["id"])
        trips_service.update_consent(students[0]["id"], consent=True)
        updated = trips_service.list_trip_students(trip["id"])
        assert updated[0]["consent_received"] == 1

    def test_update_payment(self, trips_service, sample_student):
        trip = trips_service.create_trip("Trip", "2026-05-10", cost_per_student=10.0)
        trips_service.add_student(trip["id"], sample_student["id"])
        students = trips_service.list_trip_students(trip["id"])
        trips_service.update_payment(students[0]["id"], paid=True)
        updated = trips_service.list_trip_students(trip["id"])
        assert updated[0]["paid"] == 1

    def test_remove_student(self, trips_service, sample_student):
        trip = trips_service.create_trip("Trip", "2026-05-10")
        trips_service.add_student(trip["id"], sample_student["id"])
        students = trips_service.list_trip_students(trip["id"])
        trips_service.remove_student(students[0]["id"])
        assert trips_service.list_trip_students(trip["id"]) == []
