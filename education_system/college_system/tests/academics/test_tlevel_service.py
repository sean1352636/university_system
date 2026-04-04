"""Tests for TLevelService."""

import pytest


class TestTLevelService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.tlevel.services.tlevel_service import TLevelService
        return TLevelService(db_path)

    @pytest.fixture
    def sample_route(self, service):
        return service.create_route(
            route_name="Digital Production, Design and Development",
            pathway="Software Development",
            awarding_body="Pearson",
        )

    def test_create_route(self, service):
        route = service.create_route(
            route_name="Health", pathway="Physiotherapy",
            awarding_body="NCFE", glh_total=1800,
            industry_placement_hours=315,
        )
        assert route is not None

    def test_list_routes(self, service):
        service.create_route(route_name="Education", pathway="Teaching")
        routes = service.list_routes()
        assert len(routes) >= 1

    def test_enroll_student(self, service, sample_route):
        route_id = sample_route if isinstance(sample_route, int) else sample_route.get("id", sample_route)
        enrollment = service.enroll_student(
            student_id=1, route_id=route_id,
            academic_year="2025/26",
            occupational_specialism="Software Design",
        )
        assert enrollment is not None

    def test_list_enrollments(self, service, sample_route):
        route_id = sample_route if isinstance(sample_route, int) else sample_route.get("id", sample_route)
        service.enroll_student(student_id=1, route_id=route_id)
        enrollments = service.list_enrollments(route_id=route_id)
        assert len(enrollments) >= 1

    def test_get_enrollment(self, service, sample_route):
        route_id = sample_route if isinstance(sample_route, int) else sample_route.get("id", sample_route)
        enr = service.enroll_student(student_id=1, route_id=route_id)
        enr_id = enr if isinstance(enr, int) else enr.get("id", enr)
        found = service.get_enrollment(enr_id)
        assert found is not None

    def test_log_placement(self, service, sample_route):
        route_id = sample_route if isinstance(sample_route, int) else sample_route.get("id", sample_route)
        enr = service.enroll_student(student_id=1, route_id=route_id)
        enr_id = enr if isinstance(enr, int) else enr.get("id", enr)
        log = service.log_placement(
            enrollment_id=enr_id, log_date="2026-03-15",
            hours=7.5, activity="Software testing",
            supervisor_feedback="Good progress",
        )
        assert log is not None

    def test_list_placement_logs(self, service, sample_route):
        route_id = sample_route if isinstance(sample_route, int) else sample_route.get("id", sample_route)
        enr = service.enroll_student(student_id=1, route_id=route_id)
        enr_id = enr if isinstance(enr, int) else enr.get("id", enr)
        service.log_placement(enr_id, "2026-03-15", 7.5)
        service.log_placement(enr_id, "2026-03-16", 7.0)
        logs = service.list_placement_logs(enr_id)
        assert len(logs) >= 2
