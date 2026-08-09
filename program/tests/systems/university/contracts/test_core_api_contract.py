from __future__ import annotations

from education_system.platform.delivery.api.university.core_api import create_core_app


def test_core_api_exposes_complete_journey_and_protects_operations() -> None:
    app = create_core_app(validate_schema=False)
    app.config.update(TESTING=True)
    client = app.test_client()

    page = client.get("/portal/journey")
    assert page.status_code == 200
    assert b"Apply to the university" in page.data

    response = client.get("/api/operations/health")
    assert response.status_code in {401, 403}


def test_lifecycle_contract_routes_are_present() -> None:
    app = create_core_app(validate_schema=False)
    rules = {(rule.rule, tuple(sorted(rule.methods))) for rule in app.url_map.iter_rules()}
    paths = {rule for rule, _methods in rules}

    assert "/api/admissions/applications/<int:application_id>/readiness" in paths
    assert "/api/admissions/applications/<int:application_id>/enrol" in paths
    assert "/api/student-lifecycle/students/<student_id>/registrations" in paths
    assert "/api/student-lifecycle/students/<student_id>/module-selections" in paths
    assert "/api/operations/event-deliveries" in paths
