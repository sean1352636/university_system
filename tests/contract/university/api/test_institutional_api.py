
import pytest

pytest.skip(
    "The university API routes (systems/university/shell/api) were removed "
    "so they can be rebuilt module by module. This file specifies the "
    "security/contract behaviour those routes must keep — re-enable it when "
    "the matching module is rebuilt. Backup of the removed tree: "
    "var/backups/maintenance/api-removal-20260908_204628/api-trees.tar.gz",
    allow_module_level=True,
)

from flask import Flask
import pytest

from education_system.platform.delivery.api import auth as shared_auth
from education_system.systems.university.shell.api.routes import institutional_routes


@pytest.fixture
def app():
    shared_auth._JWT_SECRET = "institutional-contract-secret-32-bytes"
    application = Flask(__name__)
    application.register_blueprint(
        institutional_routes.institutional_bp,
        url_prefix="/api/v1/university/institutional",
    )
    return application


@pytest.fixture
def staff_headers():
    token = shared_auth.generate_token(
        7,
        "university.staff",
        [{"system_key": "university", "role": "staff"}],
    )
    return {"Authorization": f"Bearer {token}"}


def test_every_institutional_workspace_requires_authentication(app):
    client = app.test_client()
    for path in ("cases", "connectors", "timetables", "pgr", "programmes"):
        response = client.get(f"/api/v1/university/institutional/{path}")
        assert response.status_code == 401


def test_shared_login_token_can_create_a_pgr_project(
    app, staff_headers, monkeypatch
):
    captured = {}

    def create_project(student_id, title, abstract, **kwargs):
        captured.update({
            "student_id": student_id,
            "title": title,
            "abstract": abstract,
            **kwargs,
        })
        return 42

    monkeypatch.setattr(institutional_routes.pgr, "create_project", create_project)
    response = app.test_client().post(
        "/api/v1/university/institutional/pgr",
        headers=staff_headers,
        json={
            "student_id": "S100",
            "proposal_title": "Reliable distributed enrolment",
            "abstract": "Research into transactional education platforms.",
            "department": "Computing",
        },
    )
    assert response.status_code == 201
    assert response.get_json() == {"project_id": 42}
    assert captured["created_by"] == "university.staff"


def test_non_university_token_is_rejected(app):
    token = shared_auth.generate_token(
        8,
        "school.staff",
        [{"system_key": "secondary", "role": "staff"}],
    )
    response = app.test_client().get(
        "/api/v1/university/institutional/pgr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
