"""Tests for TransportService."""
import pytest

from education_system.secondary_school.modules.domain.student_life.transport.services.transport_service import TransportService


@pytest.fixture
def transport_service(db_path):
    return TransportService(db_path)


class TestRoutes:
    def test_create_route(self, transport_service):
        route = transport_service.create_route(
            route_name="Route 1", operator="ABC Buses",
            vehicle_type="bus", capacity=50,
            departure_time="07:45", return_time="15:30",
        )
        assert route["route_name"] == "Route 1"
        assert route["vehicle_type"] == "bus"
        assert route["status"] == "active"

    def test_list_routes(self, transport_service):
        transport_service.create_route("Route A")
        transport_service.create_route("Route B")
        result = transport_service.list_routes()
        assert len(result) == 2

    def test_delete_route(self, transport_service):
        route = transport_service.create_route("Route X")
        transport_service.delete_route(route["id"])
        result = transport_service.list_routes()
        assert len(result) == 0


class TestStops:
    def test_add_stop(self, transport_service):
        route = transport_service.create_route("Route 1")
        transport_service.add_stop(route["id"], "High Street", pickup_time="07:50")
        stops = transport_service.list_stops(route["id"])
        assert len(stops) == 1
        assert stops[0]["stop_name"] == "High Street"

    def test_list_stops(self, transport_service):
        route = transport_service.create_route("Route 1")
        transport_service.add_stop(route["id"], "Stop A", sort_order=1)
        transport_service.add_stop(route["id"], "Stop B", sort_order=2)
        stops = transport_service.list_stops(route["id"])
        assert len(stops) == 2
        assert stops[0]["stop_name"] == "Stop A"


class TestRouteStudents:
    def test_assign_student(self, transport_service, sample_student):
        route = transport_service.create_route("Route 1")
        transport_service.assign_student(route["id"], sample_student["id"])
        students = transport_service.list_route_students(route["id"])
        assert len(students) == 1
        assert students[0]["first_name"] == "John"

    def test_list_route_students(self, transport_service, sample_student, sample_student_ks4):
        route = transport_service.create_route("Route 1")
        transport_service.assign_student(route["id"], sample_student["id"])
        transport_service.assign_student(route["id"], sample_student_ks4["id"])
        students = transport_service.list_route_students(route["id"])
        assert len(students) == 2

    def test_remove_student(self, transport_service, sample_student):
        route = transport_service.create_route("Route 1")
        transport_service.assign_student(route["id"], sample_student["id"])
        students = transport_service.list_route_students(route["id"])
        transport_service.remove_student(students[0]["id"])
        assert transport_service.list_route_students(route["id"]) == []

    def test_student_count(self, transport_service, sample_student, sample_student_ks4):
        route = transport_service.create_route("Route 1")
        assert transport_service.student_count(route["id"]) == 0
        transport_service.assign_student(route["id"], sample_student["id"])
        transport_service.assign_student(route["id"], sample_student_ks4["id"])
        assert transport_service.student_count(route["id"]) == 2
