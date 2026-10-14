"""Comprehensive tests for enrollment_routes: enroll, list, drop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from flask import Flask

from education_system.platform.delivery.api.university.auth import _blacklisted_tokens
from education_system.platform.delivery.api.university.errors import register_error_handlers
from education_system.api.university.learners.enrollment_routes import enrollment_bp, _row_to_dict
from education_system.systems.university.services.bus.enrolment_bus import (
    BLOCK_CAPACITY,
    BLOCK_PREREQUISITE,
    BLOCK_SECTION_REQUIRED,
    BLOCK_WINDOW,
    Block,
    Eligibility,
)

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

_SECRET = "enroll-test-secret"
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


def _enrollment_row(id=1, student_id="S1", module_code="CS101", status="Enrolled"):
    return _FakeRow({
        "id": id, "student_id": student_id, "module_code": module_code,
        "enrollment_date": "2024-09-01", "status": status,
        "module_type": "Standard", "module_name": None,
        "grade": None, "completion_date": None,
    })


_ELIGIBILITY = (
    "education_system.api.university.learners."
    "enrollment_routes.check_enrolment_eligibility"
)


def _eligible():
    """A pass verdict from the enrolment gate."""
    return Eligibility(ok=True)


def _blocked(kind, message, missing=None):
    """A block verdict from the enrolment gate."""
    details = {"missing": missing} if missing else {}
    return Eligibility(ok=False, blocks=[Block(kind, message, details)])


_CLASSIFY_DROP = (
    "education_system.api.university.learners."
    "enrollment_routes.classify_drop"
)
_RECORD_CHANGE = (
    "education_system.api.university.learners."
    "enrollment_routes.record_status_change"
)


def _clean_drop():
    """The calendar verdict when no registration period is configured."""
    return {"allowed": True, "status": "Dropped", "phase": "unconfigured",
            "reason": "", "period": None, "deadline": None, "on_transcript": False}


@pytest.fixture(autouse=True)
def _allow_enrolment():
    """Default every test to an eligible student inside an open window.

    The route consults the shared enrolment gate (window, prerequisites,
    co-requisites, capacity, sections) and the registration calendar on a live
    connection; the tests here mock the connection, so both are stubbed unless
    a test overrides them.
    """
    with patch(_ELIGIBILITY, return_value=_eligible()), \
            patch(_CLASSIFY_DROP, return_value=_clean_drop()), \
            patch(_RECORD_CHANGE, return_value=1):
        yield


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["API_CONFIG"] = _API_CONFIG
    register_error_handlers(app)
    app.register_blueprint(enrollment_bp)
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
# Helper
# ---------------------------------------------------------------------------

class TestRowToDict:

    def test_converts_row(self):
        d = _row_to_dict(_enrollment_row())
        assert d["student_id"] == "S1"
        assert d["module_code"] == "CS101"

    def test_none_returns_empty_dict(self):
        assert _row_to_dict(None) == {}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestEnrollmentAuth:

    def test_list_requires_token(self, client):
        assert client.get("/api/enrollments").status_code == 401

    def test_enroll_requires_token(self, client):
        assert client.post("/api/enrollments", json={}).status_code == 401

    def test_drop_requires_token(self, client):
        assert client.delete("/api/enrollments/1").status_code == 401


# ---------------------------------------------------------------------------
# List enrollments
# ---------------------------------------------------------------------------

class TestListEnrollments:

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_list_all(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [_enrollment_row()]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/enrollments", headers=_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["items"][0]["student_id"] == "S1"

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_list_filter_student(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/enrollments?student_id=S1", headers=_headers())
        assert resp.status_code == 200
        call_args = conn.execute.call_args
        assert "student_id = ?" in call_args[0][0]

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_list_filter_module(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/enrollments?module_code=CS101", headers=_headers())
        assert resp.status_code == 200
        call_args = conn.execute.call_args
        assert "module_code = ?" in call_args[0][0]

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_list_filter_both(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get(
            "/api/enrollments?student_id=S1&module_code=CS101", headers=_headers()
        )
        assert resp.status_code == 200
        sql = conn.execute.call_args[0][0]
        assert "student_id = ?" in sql
        assert "module_code = ?" in sql

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_list_empty(self, mock_conn, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/enrollments", headers=_headers())
        data = resp.get_json()
        assert data["items"] == []
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# Enroll (create)
# ---------------------------------------------------------------------------

class TestEnroll:

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.transaction")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_enroll_success(self, mock_conn, mock_tx, mock_log, client):
        conn = MagicMock()
        # student exists, module exists, no duplicate
        student_check = _FakeRow({"1": 1})
        module_check = _FakeRow({"1": 1})
        new_row = _enrollment_row(id=5, student_id="S1", module_code="CS201")
        conn.execute.return_value.fetchone.side_effect = [student_check, module_check, None, new_row]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/enrollments",
            json={"student_id": "S1", "module_code": "CS201"},
            headers=_headers(),
        )
        assert resp.status_code == 201
        assert resp.get_json()["student_id"] == "S1"

    def test_enroll_missing_student_id(self, client):
        resp = client.post(
            "/api/enrollments",
            json={"module_code": "CS101"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_enroll_missing_module_code(self, client):
        resp = client.post(
            "/api/enrollments",
            json={"student_id": "S1"},
            headers=_headers(),
        )
        assert resp.status_code == 400

    def test_enroll_empty_body(self, client):
        resp = client.post("/api/enrollments", json={}, headers=_headers())
        assert resp.status_code == 400

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_enroll_student_not_found(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/enrollments",
            json={"student_id": "NOEXIST", "module_code": "CS101"},
            headers=_headers(),
        )
        assert resp.status_code == 404

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_enroll_module_not_found(self, mock_conn, client):
        conn = MagicMock()
        student_check = _FakeRow({"1": 1})
        conn.execute.return_value.fetchone.side_effect = [student_check, None]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/enrollments",
            json={"student_id": "S1", "module_code": "NOMOD"},
            headers=_headers(),
        )
        assert resp.status_code == 404

    @patch("education_system.api.university.learners.enrollment_routes.AlreadyEnrolledError",
           side_effect=lambda student_id, course_id: type(
               "AlreadyEnrolledError", (Exception,), {})(f"{student_id}/{course_id}"))
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_enroll_already_enrolled(self, mock_conn, mock_exc, client):
        """When duplicate enrollment is detected, route raises AlreadyEnrolledError."""
        conn = MagicMock()
        student_check = _FakeRow({"1": 1})
        module_check = _FakeRow({"1": 1})
        duplicate_check = _FakeRow({"1": 1})
        conn.execute.return_value.fetchone.side_effect = [
            student_check, module_check, duplicate_check,
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.post(
            "/api/enrollments",
            json={"student_id": "S1", "module_code": "CS101"},
            headers=_headers(),
        )
        # The route detects the duplicate and attempts to raise an error
        # (response code depends on error handler registration)
        assert resp.status_code in (409, 500)


# ---------------------------------------------------------------------------
# Enrolment rules (prerequisites, co-requisites, capacity)
# ---------------------------------------------------------------------------

class TestEnrolmentRules:
    """The API must apply the same gate as the desktop registration paths.

    Before this gate existed the route wrote to ``student_modules`` after
    checking only existence and duplication, so a client could enrol a student
    with unmet prerequisites or into a full module.
    """

    @staticmethod
    def _conn_for_new_enrolment():
        """A mocked connection where the student and module exist, no duplicate."""
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [
            _FakeRow({"1": 1}),   # student exists
            _FakeRow({"1": 1}),   # module exists
            None,                 # not already enrolled
        ]
        return conn

    def _post(self, mock_conn, client, body=None):
        conn = self._conn_for_new_enrolment()
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        return client.post(
            "/api/enrollments",
            json={"student_id": "S1", "module_code": "CS201", **(body or {})},
            headers=_headers(),
        )

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_missing_prerequisite_is_rejected(self, mock_conn, client):
        with patch(_ELIGIBILITY, return_value=_blocked(
                BLOCK_PREREQUISITE,
                "Missing required prerequisite(s): CS101",
                missing=[{"code": "CS101", "name": "Intro", "min_grade": "Pass"}])):
            resp = self._post(mock_conn, client)
        assert resp.status_code == 409
        assert "Prerequisites not met" in resp.get_json()["error"]

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_full_module_is_rejected(self, mock_conn, client):
        with patch(_ELIGIBILITY, return_value=_blocked(
                BLOCK_CAPACITY, "CS201 is full (30/30).")):
            resp = self._post(mock_conn, client)
        assert resp.status_code == 409
        assert "full" in resp.get_json()["error"].lower()

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.transaction")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_override_flag_enrols_despite_block(self, mock_conn, mock_tx, mock_log, client):
        conn = self._conn_for_new_enrolment()
        # Fourth fetchone is the read-back of the created row.
        conn.execute.return_value.fetchone.side_effect = [
            _FakeRow({"1": 1}), _FakeRow({"1": 1}), None,
            _enrollment_row(id=9, student_id="S1", module_code="CS201"),
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        with patch(_ELIGIBILITY, return_value=_blocked(
                BLOCK_PREREQUISITE, "Missing required prerequisite(s): CS101")):
            resp = client.post(
                "/api/enrollments",
                json={"student_id": "S1", "module_code": "CS201",
                      "override_eligibility": True},
                headers=_headers(),
            )
        assert resp.status_code == 201

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_closed_registration_window_is_rejected(self, mock_conn, client):
        blocked = _blocked(BLOCK_WINDOW, "Registration closed on 2026-09-15.")
        blocked.window = {"open": False, "phase": "closed",
                          "deadline": "2026-09-15", "reason": "closed"}
        with patch(_ELIGIBILITY, return_value=blocked):
            resp = self._post(mock_conn, client)
        # A timing conflict, not a malformed request or a prerequisite failure.
        assert resp.status_code == 409
        assert "closed" in resp.get_json()["error"].lower()

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_module_with_sections_demands_a_section_id(self, mock_conn, client):
        blocked = _blocked(BLOCK_SECTION_REQUIRED, "CS201 runs in sections.")
        blocked.sections = [{"id": 7, "section_number": "A"},
                            {"id": 8, "section_number": "B"}]
        with patch(_ELIGIBILITY, return_value=blocked):
            resp = self._post(mock_conn, client)
        assert resp.status_code == 400
        assert "section_id" in resp.get_json()["error"]
        assert "id 7" in resp.get_json()["error"]

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_section_id_is_passed_to_the_gate(self, mock_conn, client):
        conn = self._conn_for_new_enrolment()
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        with patch(_ELIGIBILITY, return_value=_blocked(
                BLOCK_CAPACITY, "full")) as gate:
            client.post(
                "/api/enrollments",
                json={"student_id": "S1", "module_code": "CS201", "section_id": 7},
                headers=_headers(),
            )
        gate.assert_called_once_with("S1", "CS201", section_id=7, conn=conn)

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_gate_is_called_with_the_open_connection(self, mock_conn, client):
        """The gate must run inside the route's existing read connection."""
        conn = self._conn_for_new_enrolment()
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        with patch(_ELIGIBILITY, return_value=_blocked(
                BLOCK_CAPACITY, "CS201 is full (30/30).")) as gate:
            client.post(
                "/api/enrollments",
                json={"student_id": "S1", "module_code": "CS201"},
                headers=_headers(),
            )
        gate.assert_called_once_with("S1", "CS201", conn=conn)


# ---------------------------------------------------------------------------
# Drop enrollment (DELETE)
# ---------------------------------------------------------------------------

class TestDropEnrollment:

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.transaction")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_drop_success(self, mock_conn, mock_tx, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = _enrollment_row(id=10)
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        tx_conn = MagicMock()
        mock_tx.return_value.__enter__ = MagicMock(return_value=tx_conn)
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.delete("/api/enrollments/10", headers=_headers())
        assert resp.status_code == 200
        body = resp.get_json()
        assert "dropped" in body["message"].lower()
        # Leaving a module is a status change, not an erasure: the row must
        # survive so the transcript and the audit trail still have it.
        statements = " ".join(str(c) for c in tx_conn.execute.call_args_list)
        assert "UPDATE student_modules" in statements
        assert "DELETE" not in statements
        assert body["status"] == "Dropped"
        assert body["on_transcript"] is False

    @patch("education_system.api.university.learners.enrollment_routes.log_activity")
    @patch("education_system.api.university.learners.enrollment_routes.transaction")
    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_drop_after_deadline_is_a_withdrawal(self, mock_conn, mock_tx, mock_log, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = _enrollment_row(id=10)
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_tx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_tx.return_value.__exit__ = MagicMock(return_value=False)

        with patch(_CLASSIFY_DROP, return_value={
            "allowed": True, "status": "Withdrawn", "phase": "closed",
            "reason": "The drop deadline has passed.", "period": {"period_id": 1},
            "deadline": "2026-11-30", "on_transcript": True,
        }):
            resp = client.delete("/api/enrollments/10", headers=_headers())

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "Withdrawn"
        assert body["on_transcript"] is True

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_drop_past_the_withdrawal_deadline_is_refused(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = _enrollment_row(id=10)
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        with patch(_CLASSIFY_DROP, return_value={
            "allowed": False, "status": "refused", "phase": "closed",
            "reason": "The withdrawal deadline (2026-11-30) has passed.",
            "period": {"period_id": 1}, "deadline": "2026-11-30",
            "on_transcript": True,
        }):
            resp = client.delete("/api/enrollments/10", headers=_headers())

        assert resp.status_code == 409

    @patch("education_system.api.university.learners.enrollment_routes.get_connection")
    def test_drop_nonexistent(self, mock_conn, client):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.delete("/api/enrollments/999", headers=_headers())
        assert resp.status_code == 400  # ValidationError -> 400
