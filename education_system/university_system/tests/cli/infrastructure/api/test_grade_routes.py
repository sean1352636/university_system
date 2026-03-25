"""Comprehensive tests for grade_routes: list, record, update."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from flask import Flask

from education_system.shared.api.university.auth import _blacklisted_tokens
from education_system.shared.api.university.errors import register_error_handlers
from education_system.shared.api.university.routes.grade_routes import grade_bp, _row_to_dict

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

_SECRET = "grade-test-secret"
_API_CONFIG = {
    "jwt": {
        "secret_key": _SECRET,
        "access_token_expires_minutes": 30,
        "refresh_token_expires_days": 7,
        "algorithm": "HS256",
    },
    "rate_limiting": {"enabled": False},
}


def _token(sub="teacher", user_id=1, role="instructor"):
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


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["API_CONFIG"] = _API_CONFIG
    register_error_handlers(app)
    app.register_blueprint(grade_bp)
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
# _row_to_dict
# ---------------------------------------------------------------------------

class TestRowToDict:

    def test_converts_row(self):
        row = _FakeRow({"grade_id": 1, "score": 95})
        d = _row_to_dict(row)
        assert d == {"grade_id": 1, "score": 95}

    def test_none_returns_empty_dict(self):
        assert _row_to_dict(None) == {}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestGradeAuth:

    def test_list_requires_token(self, client):
        assert client.get("/api/grades").status_code == 401

    def test_create_requires_token(self, client):
        assert client.post("/api/grades", json={}).status_code == 401

    def test_update_requires_token(self, client):
        assert client.put("/api/grades/1", json={}).status_code == 401


# ---------------------------------------------------------------------------
# List grades
# ---------------------------------------------------------------------------

class TestListGrades:

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    def test_list_all(self, mock_conn, mock_log, client):
        row = _FakeRow({"grade_id": 1, "student_id": "S1", "score": 90})
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/grades", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["items"][0]["score"] == 90

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    def test_list_filter_by_student(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/grades?student_id=S1", headers=_headers())
        assert resp.status_code == 200
        # Verify the SQL contained WHERE clause with student_id
        call_args = conn.execute.call_args
        assert "student_id = ?" in call_args[0][0]

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    def test_list_filter_by_assessment(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/grades?assessment_id=A1", headers=_headers())
        assert resp.status_code == 200
        call_args = conn.execute.call_args
        assert "assessment_id = ?" in call_args[0][0]

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    def test_list_filter_both(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/grades?student_id=S1&assessment_id=A1", headers=_headers())
        assert resp.status_code == 200
        call_args = conn.execute.call_args
        sql = call_args[0][0]
        assert "student_id = ?" in sql
        assert "assessment_id = ?" in sql

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    def test_list_empty(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/grades", headers=_headers())
        data = resp.get_json()
        assert data["items"] == []
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# Record (create) grade
# ---------------------------------------------------------------------------

class TestRecordGrade:

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    @patch("shared.api.university.routes.grade_routes.transaction")
    def test_create_with_score(self, mock_tx, mock_conn, mock_log, client):
        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        new_row = _FakeRow({"grade_id": 10, "student_id": "S1", "score": 85, "letter_grade": ""})
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = new_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/grades",
            json={"student_id": "S1", "score": 85},
            headers=_headers(),
        )
        assert resp.status_code == 201
        assert resp.get_json()["grade_id"] == 10

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    @patch("shared.api.university.routes.grade_routes.transaction")
    def test_create_with_letter_grade(self, mock_tx, mock_conn, mock_log, client):
        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        new_row = _FakeRow({"grade_id": 11, "student_id": "S2", "score": None, "letter_grade": "A"})
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = new_row
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/grades",
            json={"student_id": "S2", "letter_grade": "A"},
            headers=_headers(),
        )
        assert resp.status_code == 201

    def test_create_missing_student_id(self, client):
        resp = client.post(
            "/api/grades",
            json={"score": 85},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_no_score_or_letter(self, client):
        resp = client.post(
            "/api/grades",
            json={"student_id": "S1"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_create_empty_body(self, client):
        resp = client.post("/api/grades", json={}, headers=_headers())
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Update grade
# ---------------------------------------------------------------------------

class TestUpdateGrade:

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    @patch("shared.api.university.routes.grade_routes.transaction")
    def test_update_score(self, mock_tx, mock_conn, mock_log, client):
        existing = _FakeRow({"grade_id": 1, "student_id": "S1", "score": 80})
        updated = _FakeRow({"grade_id": 1, "student_id": "S1", "score": 95})
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [existing, updated]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/grades/1",
            json={"score": 95},
            headers=_headers(),
        )
        assert resp.status_code == 200
        assert resp.get_json()["score"] == 95

    @patch("shared.api.university.routes.grade_routes.get_connection")
    def test_update_nonexistent(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/grades/999",
            json={"score": 90},
            headers=_headers(),
        )
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        resp = client.put("/api/grades/1", json={}, headers=_headers())
        assert resp.status_code == 400

    @patch("shared.api.university.routes.grade_routes.get_connection")
    def test_update_no_valid_fields(self, mock_conn, client):
        existing = _FakeRow({"grade_id": 1, "student_id": "S1", "score": 80})
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = existing
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/grades/1",
            json={"student_id": "X"},  # student_id not in allowed fields
            headers=_headers(),
        )
        assert resp.status_code == 400

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    @patch("shared.api.university.routes.grade_routes.transaction")
    def test_update_comments(self, mock_tx, mock_conn, mock_log, client):
        existing = _FakeRow({"grade_id": 1, "student_id": "S1", "score": 80, "comments": ""})
        updated = _FakeRow({"grade_id": 1, "student_id": "S1", "score": 80, "comments": "Well done"})
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [existing, updated]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/grades/1",
            json={"comments": "Well done"},
            headers=_headers(),
        )
        assert resp.status_code == 200
        assert resp.get_json()["comments"] == "Well done"

    @patch("shared.api.university.routes.grade_routes.log_activity")
    @patch("shared.api.university.routes.grade_routes.get_connection")
    @patch("shared.api.university.routes.grade_routes.transaction")
    def test_update_letter_grade(self, mock_tx, mock_conn, mock_log, client):
        existing = _FakeRow({"grade_id": 1, "letter_grade": "B"})
        updated = _FakeRow({"grade_id": 1, "letter_grade": "A+"})
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [existing, updated]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.put(
            "/api/grades/1",
            json={"letter_grade": "A+"},
            headers=_headers(),
        )
        assert resp.status_code == 200
        assert resp.get_json()["letter_grade"] == "A+"
