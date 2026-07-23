"""Smoke test for the Sixth Form College system.

Confirms the package imports and its REST API blueprints register onto a Flask
app. (Path handling and richer API behaviour are covered by this system's
existing test_paths.py / test_api.py.) Write-free.
"""

from flask import Flask


# The sixth-form routes module exports individual blueprints (no ALL_BLUEPRINTS
# tuple); this mirrors how unified_server mounts them under /api/v1/sixthform/.
def _blueprints():
    from education_system.shared.api.sixthform.routes import (
        academic_year_bp, students_bp, academics_bp, assessment_bp, finance_bp,
        governance_bp, pastoral_bp, progression_bp, reports_bp, staff_comms_bp,
        student_services_bp, advanced_search_bp,
    )
    return [
        academic_year_bp, students_bp, academics_bp, assessment_bp, finance_bp,
        governance_bp, pastoral_bp, progression_bp, reports_bp, staff_comms_bp,
        student_services_bp, advanced_search_bp,
    ]


def test_package_and_cli_import():
    import education_system.post_16.sixthform_system  # noqa: F401
    import education_system.post_16.sixthform_system.cli_main  # noqa: F401


def test_api_blueprints_register():
    app = Flask(__name__)
    for bp in _blueprints():
        app.register_blueprint(bp)
    rules = [r.rule for r in app.url_map.iter_rules()]

    assert len(rules) > 20
    assert any(r.startswith("/api/") for r in rules)


def test_protected_endpoint_requires_auth():
    app = Flask(__name__)
    for bp in _blueprints():
        app.register_blueprint(bp)
    resp = app.test_client().get("/api/sixthform/academic-year/")
    assert resp.status_code in (401, 403), resp.status_code
