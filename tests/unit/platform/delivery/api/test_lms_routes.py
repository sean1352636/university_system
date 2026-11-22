"""LMS connection routes: every route is gated, per system."""

from __future__ import annotations

import sqlite3

import pytest
from flask import Flask

from education_system.platform.delivery.api import lms_routes, registry
from education_system.platform.delivery.api.security import authentication

_SECRET = "lms-test-secret-with-enough-length-for-hs256"
_USERS = {
    "uni_admin": (1, [{"system_key": "university", "role": "admin"}]),
    "nursery_admin": (2, [{"system_key": "nursery", "role": "admin"}]),
    "uni_student": (3, [{"system_key": "university", "role": "student"}]),
    "super": (4, [{"system_key": key, "role": "admin"}
                  for key in ("university", "sixth_form", "secondary", "primary")]),
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    auth_db = tmp_path / "auth.db"
    conn = sqlite3.connect(auth_db)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, is_active INTEGER)")
    conn.executemany("INSERT INTO users VALUES (?, ?, 1)",
                     [(central, name) for name, (central, _s) in _USERS.items()])
    conn.commit()
    conn.close()
    monkeypatch.setattr(authentication, "_auth_db_path", str(auth_db))
    monkeypatch.setattr(authentication, "_JWT_SECRET", _SECRET)
    monkeypatch.setattr(lms_routes, "_sync_service", None)
    monkeypatch.setenv("LMS_DB_PATH", str(tmp_path / "lms.db"))
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(lms_routes.lms_bp, url_prefix="/api/v1/lms")
    service = lms_routes._service()
    assert service._db_path == str(tmp_path / "lms.db"), "not isolated from the live database"
    test_client = app.test_client()
    test_client.uni_id = service.add_connection(
        "university", "canvas", {"base_url": "https://canvas.example", "access_token": "TOKEN-MUST-NOT-LEAK"})
    test_client.nursery_id = service.add_connection(
        "nursery", "canvas", {"base_url": "https://canvas.example", "access_token": "TOKEN-MUST-NOT-LEAK"})
    return test_client


def _auth(username: str) -> dict:
    central, systems = _USERS[username]
    token = authentication.generate_token(central, username, systems)
    return {"Authorization": f"Bearer {token}"}


def test_it_is_in_the_platform_mount_table():
    assert ("education_system.platform.delivery.api.lms_routes", "lms_bp") in registry.PLATFORM


def test_the_blueprint_declares_the_prefix_the_app_factory_mounts():
    assert lms_routes.lms_bp.url_prefix == "/api/lms"


@pytest.mark.parametrize("method,path", [
    ("get", "/connections"), ("post", "/connections"), ("delete", "/connections/1"),
    ("post", "/connections/1/test"), ("post", "/connections/1/sync"), ("get", "/sync-log"),
    ("get", "/mappings/1")])
def test_every_route_needs_a_token(client, method, path):
    assert getattr(client, method)("/api/v1/lms" + path).status_code == 401


@pytest.mark.parametrize("method,path", [
    ("get", "/connections"), ("post", "/connections"), ("delete", "/connections/1"),
    ("post", "/connections/1/test"), ("post", "/connections/1/sync"), ("get", "/sync-log"),
    ("get", "/mappings/1")])
def test_a_student_is_refused_everything(client, method, path):
    response = getattr(client, method)("/api/v1/lms" + path, headers=_auth("uni_student"))
    assert response.status_code == 403


def test_listing_shows_only_the_systems_you_administer_and_no_credentials(client):
    response = client.get("/api/v1/lms/connections", headers=_auth("uni_admin"))
    assert [c["id"] for c in response.get_json()["connections"]] == [client.uni_id]
    assert "MUST-NOT-LEAK" not in response.get_data(as_text=True)
    both = client.get("/api/v1/lms/connections", headers=_auth("super")).get_json()
    assert both["count"] == 2


@pytest.mark.parametrize("method,suffix", [("delete", ""), ("post", "/test"), ("post", "/sync")])
def test_another_systems_connection_reads_as_missing(client, method, suffix):
    path = f"/api/v1/lms/connections/{client.uni_id}{suffix}"
    assert getattr(client, method)(path, headers=_auth("nursery_admin")).status_code == 404


def test_mappings_and_log_are_scoped_too(client):
    headers = _auth("nursery_admin")
    assert client.get(f"/api/v1/lms/mappings/{client.uni_id}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/lms/sync-log?connection_id={client.uni_id}", headers=headers).status_code == 404


def test_cannot_add_a_connection_to_a_system_you_do_not_administer(client):
    body = {"system_key": "university", "provider_type": "canvas",
            "config": {"base_url": "https://x.example", "access_token": "t"}}
    assert client.post("/api/v1/lms/connections", json=body, headers=_auth("nursery_admin")).status_code == 403
    assert client.post("/api/v1/lms/connections", json=body, headers=_auth("uni_admin")).status_code == 201


def test_administrator_removes_their_own(client):
    response = client.delete(f"/api/v1/lms/connections/{client.uni_id}", headers=_auth("uni_admin"))
    assert response.status_code == 200
    assert client.get("/api/v1/lms/connections", headers=_auth("uni_admin")).get_json()["count"] == 0


def test_errors_are_problem_json(client):
    response = client.delete("/api/v1/lms/connections/999", headers=_auth("uni_admin"))
    assert response.status_code == 404
    assert response.mimetype == "application/problem+json"
