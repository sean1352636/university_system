"""Comprehensive tests for course_routes: CRUD and waitlist."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from flask import Flask

from education_system.platform.delivery.api.university.auth import _blacklisted_tokens
from education_system.platform.delivery.api.university.errors import register_error_handlers
from education_system.platform.delivery.api.university.routes.course_routes import course_bp, _row_to_dict

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

_SECRET = "course-test-secret"
_API_CONFIG = {
    "jwt": {
        "secret_key": _SECRET,
        "access_token_expires_minutes": 30,
        "refresh_token_expires_days": 7,
        "algorithm": "HS256",
    },
    "rate_limiting": {"enabled": False},
}


def _token(sub="admin", user_id=1, role="admin"):
    payload = {
        "sub": sub, "user_id": user_id, "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, _SECRET, algorithm="HS256")


def _headers():
    return {"Authorization": f"Bearer {_token()}"}


class _FakeRow:
    def __init__(self, data: dict):
        self._data = data

    def keys(self):
        return self._data.keys()

    def __getitem__(self, key):
        return self._data[key]


def _course_row(course_id=1, course_code="CS101", course_name="Intro to CS",
                department="CS", credits=3, status="active"):
    return _FakeRow({
        "course_id": course_id, "course_code": course_code,
        "course_name": course_name, "description": "",
        "department": department, "credits": credits,
        "max_capacity": 30, "status": status,
        "created_at": "2024-01-01", "updated_at": "2024-01-01",
    })


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["API_CONFIG"] = _API_CONFIG
    register_error_handlers(app)
    app.register_blueprint(course_bp)
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
# Helper unit test
# ---------------------------------------------------------------------------

class TestRowToDict:

    def test_converts_row(self):
        d = _row_to_dict(_course_row())
        assert d["course_id"] == 1
        assert d["course_code"] == "CS101"

    def test_none_returns_empty_dict(self):
        assert _row_to_dict(None) == {}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestCourseAuth:

    def test_list_requires_token(self, client):
        assert client.get("/api/courses").status_code == 401

    def test_get_requires_token(self, client):
        assert client.get("/api/courses/1").status_code == 401

    def test_create_requires_token(self, client):
        assert client.post("/api/courses", json={}).status_code == 401

    def test_update_requires_token(self, client):
        assert client.put("/api/courses/1", json={}).status_code == 401

    def test_waitlist_requires_token(self, client):
        assert client.get("/api/courses/1/waitlist").status_code == 401


# ---------------------------------------------------------------------------
# List courses
# ---------------------------------------------------------------------------

class TestListCourses:

    @patch("education_system.platform.delivery.api.university.routes.course_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_list_paginated(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [_course_row()]
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: 1
        conn.execute.return_value.fetchone.return_value = count_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data
        assert "pagination" in data

    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_list_search(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [_course_row()]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses?search=CS", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1

    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_list_by_department(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses?department=Math", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0

    @patch("education_system.platform.delivery.api.university.routes.course_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_list_empty(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        count_row = MagicMock()
        count_row.__getitem__ = lambda self, i: 0
        conn.execute.return_value.fetchone.return_value = count_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses", headers=_headers())
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Get single course
# ---------------------------------------------------------------------------

class TestGetCourse:

    @patch("education_system.platform.delivery.api.university.routes.course_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_get_existing(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = _course_row(course_id=5)
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses/5", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["course_id"] == 5

    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_get_nonexistent(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses/999", headers=_headers())
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create course
# ---------------------------------------------------------------------------

class TestCreateCourse:

    @patch("education_system.platform.delivery.api.university.routes.course_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.transaction")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_create_success(self, mock_conn, mock_tx, mock_log, client):
        conn = MagicMock()
        # First call: check existing -> None
        # Second call: fetch newly created course (used by _get_course_or_404)
        new_row = _course_row(course_id=10, course_code="NEW101", course_name="New Course")
        conn.execute.return_value.fetchone.side_effect = [None, new_row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        last_id_row = MagicMock()
        last_id_row.__getitem__ = lambda self, i: 10
        tx_conn.execute.return_value.fetchone.return_value = last_id_row
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/courses",
            json={"course_code": "NEW101", "course_name": "New Course"},
            headers=_headers(),
        )
        assert resp.status_code == 201
        assert resp.get_json()["course_code"] == "NEW101"

    def test_create_missing_code(self, client):
        resp = client.post(
            "/api/courses",
            json={"course_name": "Test"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_missing_name(self, client):
        resp = client.post(
            "/api/courses",
            json={"course_code": "X"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_empty_body(self, client):
        resp = client.post("/api/courses", json={}, headers=_headers())
        assert resp.status_code == 400

    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_create_duplicate_code(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = _FakeRow({"1": 1})
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/courses",
            json={"course_code": "CS101", "course_name": "Dup"},
            headers=_headers(),
        )
        assert resp.status_code == 400
        assert "already exists" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Update course
# ---------------------------------------------------------------------------

class TestUpdateCourse:

    @patch("education_system.platform.delivery.api.university.routes.course_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.transaction")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_update_success(self, mock_conn, mock_tx, mock_log, client):
        existing = _course_row(course_id=1)
        updated = _course_row(course_id=1, course_name="Updated Name")
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [existing, updated]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/courses/1",
            json={"course_name": "Updated Name"},
            headers=_headers(),
        )
        assert resp.status_code == 200

    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_update_nonexistent(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/courses/999",
            json={"course_name": "X"},
            headers=_headers(),
        )
        assert resp.status_code == 404

    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_update_empty_body(self, mock_conn, client):
        existing = _course_row(course_id=1)
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = existing
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put("/api/courses/1", json={}, headers=_headers())
        assert resp.status_code == 400

    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_update_no_valid_fields(self, mock_conn, client):
        existing = _course_row(course_id=1)
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = existing
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/courses/1",
            json={"bogus": "field"},
            headers=_headers(),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Course waitlist
# ---------------------------------------------------------------------------

class TestCourseWaitlist:

    @patch("education_system.platform.delivery.api.university.routes.course_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_waitlist_success(self, mock_conn, mock_log, client):
        course_row = _course_row(course_id=1)
        waitlist_row = _FakeRow({
            "student_id": "S1", "course_id": 1, "position": 1,
            "first_name": "Jane", "last_name": "Doe",
        })
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = course_row
        conn.execute.return_value.fetchall.return_value = [waitlist_row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses/1/waitlist", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["course_id"] == 1
        assert len(data["waitlist"]) == 1

    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_waitlist_nonexistent_course(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses/999/waitlist", headers=_headers())
        assert resp.status_code == 404

    @patch("education_system.platform.delivery.api.university.routes.course_routes.log_activity")
    @patch("education_system.platform.delivery.api.university.routes.course_routes.get_connection")
    def test_waitlist_empty(self, mock_conn, mock_log, client):
        course_row = _course_row(course_id=2)
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = course_row
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/courses/2/waitlist", headers=_headers())
        assert resp.status_code == 200
        assert resp.get_json()["waitlist"] == []
