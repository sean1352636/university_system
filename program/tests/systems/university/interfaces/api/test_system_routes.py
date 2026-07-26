"""Comprehensive tests for system_routes: /, /api, /api/, /api/health, /api/version."""

import json

import pytest
from flask import Flask

from education_system.platform.delivery.api.university.routes.system_routes import system_bp


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.register_blueprint(system_bp)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------- Index routes ----------

class TestIndexRoute:
    def test_root_redirects(self, client):
        resp = client.get("/")
        assert resp.status_code in (200, 302)

    def test_api_returns_json(self, client):
        resp = client.get("/api")
        data = resp.get_json()
        assert data["name"] == "University Management System API"
        assert "version" in data
        assert "endpoints" in data

    def test_api_path_returns_200(self, client):
        resp = client.get("/api")
        assert resp.status_code == 200

    def test_api_slash_returns_200(self, client):
        resp = client.get("/api/")
        assert resp.status_code == 200

    def test_index_contains_expected_endpoints(self, client):
        data = client.get("/api").get_json()
        endpoints = data["endpoints"]
        assert "health" in endpoints
        assert "version" in endpoints
        assert "auth" in endpoints
        assert "students" in endpoints
        assert "courses" in endpoints
        assert "finance" in endpoints

    def test_index_version_matches(self, client):
        data = client.get("/api").get_json()
        assert data["version"] == "5.46.3"


# ---------- Health endpoint ----------

class TestHealthRoute:
    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_status_is_healthy(self, client):
        data = client.get("/api/health").get_json()
        assert data["status"] == "healthy"

    def test_health_contains_timestamp(self, client):
        data = client.get("/api/health").get_json()
        assert "timestamp" in data
        # Timestamp should be ISO-8601 with UTC timezone indicator
        assert "T" in data["timestamp"]

    def test_health_post_not_allowed(self, client):
        resp = client.post("/api/health")
        assert resp.status_code == 405


# ---------- Version endpoint ----------

class TestVersionRoute:
    def test_version_returns_200(self, client):
        resp = client.get("/api/version")
        assert resp.status_code == 200

    def test_version_fields(self, client):
        data = client.get("/api/version").get_json()
        assert data["version"] == "5.46.3"
        assert data["api_version"] == "1.0"
        assert data["python_framework"] == "Flask"

    def test_version_post_not_allowed(self, client):
        resp = client.post("/api/version")
        assert resp.status_code == 405
