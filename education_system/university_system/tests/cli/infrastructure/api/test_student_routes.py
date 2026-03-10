"""Comprehensive tests for student_routes: CRUD with pagination, search, filters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from flask import Flask

from education_system.university_system.api.auth import _blacklisted_tokens
from education_system.university_system.api.errors import register_error_handlers
from education_system.university_system.api.routes.student_routes import student_bp, _student_to_dict

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

_SECRET = "student-test-secret"
_API_CONFIG = {
    "jwt": {
        "secret_key": _SECRET,
        "access_token_expires_minutes": 30,
        "refresh_token_expires_days": 7,
        "algorithm": "HS256",
    },
    "rate_limiting": {"enabled": False},
}


def _token(sub="tester", user_id=1, role="admin"):
    payload = {
        "sub": sub,
        "user_id": user_id,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, _SECRET, algorithm="HS256")


def _headers(token=None):
    return {"Authorization": f"Bearer {token or _token()}"}


# ---------------------------------------------------------------------------
# Fake Student object
# ---------------------------------------------------------------------------

class _FakeStudent:
    def __init__(self, **kw):
        self.student_id = kw.get("student_id", "STU001")
        self.first_name = kw.get("first_name", "Jane")
        self.middle_name = kw.get("middle_name", None)
        self.last_name = kw.get("last_name", "Doe")
        self.full_name = kw.get("full_name", "Jane Doe")
        self.email_address = kw.get("email_address", "jane@uni.edu")
        self.title = kw.get("title", "Ms")
        self.gender = kw.get("gender", "Female")
        self.dob = kw.get("dob", "2000-01-01")
        self.age = kw.get("age", 26)
        self.course = kw.get("course", "CS101")
        self.status = kw.get("status", "Active")
        self.enrollment_date = kw.get("enrollment_date", "2024-09-01")
        self.registration_datetime = kw.get("registration_datetime", "2024-08-15 10:00:00")


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["API_CONFIG"] = _API_CONFIG
    register_error_handlers(app)
    app.register_blueprint(student_bp)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clear():
    _blacklisted_tokens.clear()
    yield
    _blacklisted_tokens.clear()


# ---------------------------------------------------------------------------
# _student_to_dict
# ---------------------------------------------------------------------------

class TestStudentToDict:

    def test_converts_all_fields(self):
        s = _FakeStudent()
        d = _student_to_dict(s)
        assert d["student_id"] == "STU001"
        assert d["first_name"] == "Jane"
        assert d["last_name"] == "Doe"
        assert d["email_address"] == "jane@uni.edu"
        assert d["status"] == "Active"
        assert d["course"] == "CS101"
        assert "full_name" in d
        assert "registration_datetime" in d

    def test_handles_none_middle_name(self):
        s = _FakeStudent(middle_name=None)
        d = _student_to_dict(s)
        assert d["middle_name"] is None


# ---------------------------------------------------------------------------
# Authentication requirements
# ---------------------------------------------------------------------------

class TestStudentAuth:

    def test_list_requires_token(self, client):
        resp = client.get("/api/students")
        assert resp.status_code == 401

    def test_get_requires_token(self, client):
        resp = client.get("/api/students/STU001")
        assert resp.status_code == 401

    def test_create_requires_token(self, client):
        resp = client.post("/api/students", json={"student_id": "X"})
        assert resp.status_code == 401

    def test_update_requires_token(self, client):
        resp = client.put("/api/students/STU001", json={"first_name": "Z"})
        assert resp.status_code == 401

    def test_delete_requires_token(self, client):
        resp = client.delete("/api/students/STU001")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List students
# ---------------------------------------------------------------------------

class TestListStudents:

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_list_paginated(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.get_all.return_value = [_FakeStudent()]
        repo.count.return_value = 1
        mock_repo_fn.return_value = repo

        resp = client.get("/api/students", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert "pagination" in data
        assert data["pagination"]["total"] == 1

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_list_with_search(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.search.return_value = [_FakeStudent()]
        mock_repo_fn.return_value = repo

        resp = client.get("/api/students?search=Jane", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        repo.search.assert_called_once_with("Jane")

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_list_with_status_filter(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.find_by_status.return_value = []
        mock_repo_fn.return_value = repo

        resp = client.get("/api/students?status=Inactive", headers=_headers())
        assert resp.status_code == 200
        repo.find_by_status.assert_called_once_with("Inactive")

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_list_with_course_filter(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.find_by_course.return_value = [_FakeStudent(), _FakeStudent(student_id="STU002")]
        mock_repo_fn.return_value = repo

        resp = client.get("/api/students?course=CS101", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 2
        repo.find_by_course.assert_called_once_with("CS101")

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_list_empty(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.get_all.return_value = []
        repo.count.return_value = 0
        mock_repo_fn.return_value = repo

        resp = client.get("/api/students", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["items"] == []

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_list_pagination_params(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.get_all.return_value = []
        repo.count.return_value = 50
        mock_repo_fn.return_value = repo

        resp = client.get("/api/students?page=2&per_page=10", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 10
        repo.get_all.assert_called_once_with(limit=10, offset=10)


# ---------------------------------------------------------------------------
# Get single student
# ---------------------------------------------------------------------------

class TestGetStudent:

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_get_existing_student(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.get_by_id.return_value = _FakeStudent(student_id="STU001")
        mock_repo_fn.return_value = repo

        resp = client.get("/api/students/STU001", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["student_id"] == "STU001"

    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_get_nonexistent_student(self, mock_repo_fn, client):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        mock_repo_fn.return_value = repo

        resp = client.get("/api/students/NOEXIST", headers=_headers())
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create student
# ---------------------------------------------------------------------------

class TestCreateStudent:

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_create_success(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        saved = _FakeStudent(student_id="STU010", first_name="John", last_name="Smith")
        repo.save.return_value = saved
        mock_repo_fn.return_value = repo

        resp = client.post(
            "/api/students",
            json={"student_id": "STU010", "first_name": "John", "last_name": "Smith"},
            headers=_headers(),
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["student_id"] == "STU010"

    def test_create_missing_required_fields(self, client):
        resp = client.post(
            "/api/students",
            json={"first_name": "John"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_missing_student_id(self, client):
        resp = client.post(
            "/api/students",
            json={"first_name": "John", "last_name": "Smith"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_missing_first_name(self, client):
        resp = client.post(
            "/api/students",
            json={"student_id": "X", "last_name": "Smith"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_missing_last_name(self, client):
        resp = client.post(
            "/api/students",
            json={"student_id": "X", "first_name": "John"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_create_with_optional_fields(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.save.return_value = _FakeStudent(
            student_id="STU011", first_name="Alice", last_name="Lee",
            email_address="alice@uni.edu", status="Active"
        )
        mock_repo_fn.return_value = repo

        resp = client.post(
            "/api/students",
            json={
                "student_id": "STU011",
                "first_name": "Alice",
                "last_name": "Lee",
                "email_address": "alice@uni.edu",
                "status": "Active",
            },
            headers=_headers(),
        )
        assert resp.status_code == 201

    def test_create_invalid_email(self, client):
        resp = client.post(
            "/api/students",
            json={
                "student_id": "STU012",
                "first_name": "Bad",
                "last_name": "Email",
                "email_address": "not-an-email",
            },
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_empty_body(self, client):
        resp = client.post("/api/students", json={}, headers=_headers())
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Update student
# ---------------------------------------------------------------------------

class TestUpdateStudent:

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_update_success(self, mock_repo_fn, mock_log, client):
        existing = _FakeStudent(student_id="STU001")
        repo = MagicMock()
        repo.get_by_id.return_value = existing
        repo.save.return_value = _FakeStudent(student_id="STU001", first_name="Updated")
        mock_repo_fn.return_value = repo

        resp = client.put(
            "/api/students/STU001",
            json={"first_name": "Updated"},
            headers=_headers(),
        )
        assert resp.status_code == 200
        assert resp.get_json()["first_name"] == "Updated"

    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_update_nonexistent(self, mock_repo_fn, client):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        mock_repo_fn.return_value = repo

        resp = client.put(
            "/api/students/NOEXIST",
            json={"first_name": "X"},
            headers=_headers(),
        )
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        resp = client.put(
            "/api/students/STU001",
            json={},
            headers=_headers(),
        )
        assert resp.status_code == 400

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_update_multiple_fields(self, mock_repo_fn, mock_log, client):
        existing = _FakeStudent(student_id="STU001")
        repo = MagicMock()
        repo.get_by_id.return_value = existing
        repo.save.return_value = existing
        mock_repo_fn.return_value = repo

        resp = client.put(
            "/api/students/STU001",
            json={"first_name": "New", "last_name": "Name", "status": "Inactive"},
            headers=_headers(),
        )
        assert resp.status_code == 200
        # Verify setattr was called on the student object
        assert existing.first_name == "New"
        assert existing.last_name == "Name"
        assert existing.status == "Inactive"

    def test_update_invalid_email(self, client):
        resp = client.put(
            "/api/students/STU001",
            json={"email_address": "bad-email"},
            headers=_headers(),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete student
# ---------------------------------------------------------------------------

class TestDeleteStudent:

    @patch("university_system.api.routes.student_routes.log_activity")
    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_delete_success(self, mock_repo_fn, mock_log, client):
        repo = MagicMock()
        repo.exists.return_value = True
        mock_repo_fn.return_value = repo

        resp = client.delete("/api/students/STU001", headers=_headers())
        assert resp.status_code == 200
        assert "deleted" in resp.get_json()["message"].lower()
        repo.delete.assert_called_once_with("STU001")

    @patch("university_system.api.routes.student_routes.get_student_repository")
    def test_delete_nonexistent(self, mock_repo_fn, client):
        repo = MagicMock()
        repo.exists.return_value = False
        mock_repo_fn.return_value = repo

        resp = client.delete("/api/students/NOEXIST", headers=_headers())
        assert resp.status_code == 404
