"""
Tests for university_system/api/errors.py

Covers _error_response() JSON builder and register_error_handlers() which maps
domain exceptions and HTTP error codes to consistent JSON error responses.
"""

import os
import sys

import pytest
from flask import Flask

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from education_system.shared.api.university.errors import _error_response, register_error_handlers
from education_system.university_system.core.exceptions import (
    AlreadyEnrolledError,
    AuthenticationError,
    CourseFullError,
    CourseNotFoundError,
    DatabaseError,
    DuplicateStudentError,
    EnrollmentError,
    FinanceError,
    GradeNotFoundError,
    InsufficientFundsError,
    InvalidCredentialsError,
    PaymentError,
    PermissionDeniedError,
    StudentNotFoundError,
    TransactionFailedError,
    ValidationError,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def app():
    """Create a minimal Flask app with error handlers registered."""
    application = Flask(__name__)
    application.config["TESTING"] = True
    application.config["PROPAGATE_EXCEPTIONS"] = False
    application.config["TRAP_HTTP_EXCEPTIONS"] = False
    register_error_handlers(application)

    # Routes that raise each exception type for testing
    @application.route("/raise/validation-error")
    def raise_validation_error():
        raise ValidationError("bad input")

    @application.route("/raise/invalid-credentials")
    def raise_invalid_credentials():
        raise InvalidCredentialsError("wrong password")

    @application.route("/raise/authentication-error")
    def raise_authentication_error():
        raise AuthenticationError("not authenticated")

    @application.route("/raise/permission-denied")
    def raise_permission_denied():
        raise PermissionDeniedError("access denied")

    @application.route("/raise/student-not-found")
    def raise_student_not_found():
        raise StudentNotFoundError("S001")

    @application.route("/raise/course-not-found")
    def raise_course_not_found():
        raise CourseNotFoundError("CS101")

    @application.route("/raise/grade-not-found")
    def raise_grade_not_found():
        raise GradeNotFoundError("Grade record not found")

    @application.route("/raise/duplicate-student")
    def raise_duplicate_student():
        raise DuplicateStudentError("S001")

    @application.route("/raise/already-enrolled")
    def raise_already_enrolled():
        raise AlreadyEnrolledError("S001", "CS101")

    @application.route("/raise/course-full")
    def raise_course_full():
        raise CourseFullError("CS101")

    @application.route("/raise/enrollment-error")
    def raise_enrollment_error():
        raise EnrollmentError("enrollment failed")

    @application.route("/raise/insufficient-funds")
    def raise_insufficient_funds():
        raise InsufficientFundsError(required=500.0, available=100.0)

    @application.route("/raise/payment-error")
    def raise_payment_error():
        raise PaymentError("payment declined")

    @application.route("/raise/transaction-failed")
    def raise_transaction_failed():
        raise TransactionFailedError("transaction rolled back")

    @application.route("/raise/finance-error")
    def raise_finance_error():
        raise FinanceError("finance issue")

    @application.route("/raise/database-error")
    def raise_database_error():
        raise DatabaseError("db unavailable")

    return application


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


# ============================================================================
# _error_response tests
# ============================================================================


class TestErrorResponse:
    """Tests for the _error_response() helper."""

    def test_returns_tuple_with_status(self, app):
        """_error_response returns (response, status_code) tuple."""
        with app.app_context():
            resp, status = _error_response("something broke", 500)
            assert status == 500

    def test_response_body_contains_error_and_status(self, app):
        """Response JSON contains 'error' and 'status' keys."""
        with app.app_context():
            resp, status = _error_response("not found", 404)
            data = resp.get_json()
            assert data["error"] == "not found"
            assert data["status"] == 404

    def test_different_messages_and_codes(self, app):
        """Various message/status combinations work correctly."""
        with app.app_context():
            for msg, code in [("bad", 400), ("denied", 403), ("gone", 410)]:
                resp, status = _error_response(msg, code)
                data = resp.get_json()
                assert data["error"] == msg
                assert data["status"] == code
                assert status == code


# ============================================================================
# Domain exception handler tests
# ============================================================================


class TestValidationErrorHandler:
    """ValidationError should map to 400."""

    def test_status_code(self, client):
        resp = client.get("/raise/validation-error")
        assert resp.status_code == 400

    def test_response_body(self, client):
        resp = client.get("/raise/validation-error")
        data = resp.get_json()
        assert data["status"] == 400
        assert "bad input" in data["error"]


class TestInvalidCredentialsErrorHandler:
    """InvalidCredentialsError should map to 401."""

    def test_status_code(self, client):
        resp = client.get("/raise/invalid-credentials")
        assert resp.status_code == 401

    def test_response_body(self, client):
        resp = client.get("/raise/invalid-credentials")
        data = resp.get_json()
        assert data["status"] == 401


class TestAuthenticationErrorHandler:
    """AuthenticationError should map to 401."""

    def test_status_code(self, client):
        resp = client.get("/raise/authentication-error")
        assert resp.status_code == 401

    def test_response_body(self, client):
        resp = client.get("/raise/authentication-error")
        data = resp.get_json()
        assert data["status"] == 401
        assert "not authenticated" in data["error"]


class TestPermissionDeniedErrorHandler:
    """PermissionDeniedError should map to 403."""

    def test_status_code(self, client):
        resp = client.get("/raise/permission-denied")
        assert resp.status_code == 403

    def test_response_body(self, client):
        resp = client.get("/raise/permission-denied")
        data = resp.get_json()
        assert data["status"] == 403


class TestStudentNotFoundErrorHandler:
    """StudentNotFoundError should map to 404."""

    def test_status_code(self, client):
        resp = client.get("/raise/student-not-found")
        assert resp.status_code == 404

    def test_response_body(self, client):
        resp = client.get("/raise/student-not-found")
        data = resp.get_json()
        assert data["status"] == 404
        assert "S001" in data["error"]


class TestCourseNotFoundErrorHandler:
    """CourseNotFoundError should map to 404."""

    def test_status_code(self, client):
        resp = client.get("/raise/course-not-found")
        assert resp.status_code == 404

    def test_response_body(self, client):
        resp = client.get("/raise/course-not-found")
        data = resp.get_json()
        assert data["status"] == 404
        assert "CS101" in data["error"]


class TestGradeNotFoundErrorHandler:
    """GradeNotFoundError should map to 404."""

    def test_status_code(self, client):
        resp = client.get("/raise/grade-not-found")
        assert resp.status_code == 404

    def test_response_body(self, client):
        resp = client.get("/raise/grade-not-found")
        data = resp.get_json()
        assert data["status"] == 404


class TestDuplicateStudentErrorHandler:
    """DuplicateStudentError should map to 409."""

    def test_status_code(self, client):
        resp = client.get("/raise/duplicate-student")
        assert resp.status_code == 409

    def test_response_body(self, client):
        resp = client.get("/raise/duplicate-student")
        data = resp.get_json()
        assert data["status"] == 409
        assert "S001" in data["error"]


class TestAlreadyEnrolledErrorHandler:
    """AlreadyEnrolledError should map to 409."""

    def test_status_code(self, client):
        resp = client.get("/raise/already-enrolled")
        assert resp.status_code == 409

    def test_response_body(self, client):
        resp = client.get("/raise/already-enrolled")
        data = resp.get_json()
        assert data["status"] == 409
        assert "S001" in data["error"]
        assert "CS101" in data["error"]


class TestCourseFullErrorHandler:
    """CourseFullError should map to 409."""

    def test_status_code(self, client):
        resp = client.get("/raise/course-full")
        assert resp.status_code == 409

    def test_response_body(self, client):
        resp = client.get("/raise/course-full")
        data = resp.get_json()
        assert data["status"] == 409
        assert "CS101" in data["error"]


class TestEnrollmentErrorHandler:
    """EnrollmentError should map to 400."""

    def test_status_code(self, client):
        resp = client.get("/raise/enrollment-error")
        assert resp.status_code == 400

    def test_response_body(self, client):
        resp = client.get("/raise/enrollment-error")
        data = resp.get_json()
        assert data["status"] == 400
        assert "enrollment failed" in data["error"]


class TestInsufficientFundsErrorHandler:
    """InsufficientFundsError should map to 402."""

    def test_status_code(self, client):
        resp = client.get("/raise/insufficient-funds")
        assert resp.status_code == 402

    def test_response_body(self, client):
        resp = client.get("/raise/insufficient-funds")
        data = resp.get_json()
        assert data["status"] == 402
        assert "Insufficient funds" in data["error"]


class TestPaymentErrorHandler:
    """PaymentError should map to 400."""

    def test_status_code(self, client):
        resp = client.get("/raise/payment-error")
        assert resp.status_code == 400

    def test_response_body(self, client):
        resp = client.get("/raise/payment-error")
        data = resp.get_json()
        assert data["status"] == 400
        assert "payment declined" in data["error"]


class TestTransactionFailedErrorHandler:
    """TransactionFailedError should map to 500."""

    def test_status_code(self, client):
        resp = client.get("/raise/transaction-failed")
        assert resp.status_code == 500

    def test_response_body(self, client):
        resp = client.get("/raise/transaction-failed")
        data = resp.get_json()
        assert data["status"] == 500
        assert "transaction rolled back" in data["error"]


class TestFinanceErrorHandler:
    """FinanceError should map to 400."""

    def test_status_code(self, client):
        resp = client.get("/raise/finance-error")
        assert resp.status_code == 400

    def test_response_body(self, client):
        resp = client.get("/raise/finance-error")
        data = resp.get_json()
        assert data["status"] == 400
        assert "finance issue" in data["error"]


class TestDatabaseErrorHandler:
    """DatabaseError should map to 503."""

    def test_status_code(self, client):
        resp = client.get("/raise/database-error")
        assert resp.status_code == 503

    def test_response_body(self, client):
        resp = client.get("/raise/database-error")
        data = resp.get_json()
        assert data["status"] == 503
        assert "db unavailable" in data["error"]


# ============================================================================
# HTTP error handler tests
# ============================================================================


class TestHTTP404Handler:
    """Built-in 404 handler returns JSON."""

    def test_status_code(self, client):
        resp = client.get("/this/route/does/not/exist")
        assert resp.status_code == 404

    def test_response_body(self, client):
        resp = client.get("/this/route/does/not/exist")
        data = resp.get_json()
        assert data["error"] == "Resource not found"
        assert data["status"] == 404


class TestHTTP405Handler:
    """Built-in 405 handler returns JSON."""

    def test_status_code(self, client):
        # POST to a GET-only route triggers 405
        resp = client.post("/raise/validation-error")
        assert resp.status_code == 405

    def test_response_body(self, client):
        resp = client.post("/raise/validation-error")
        data = resp.get_json()
        assert data["error"] == "Method not allowed"
        assert data["status"] == 405


class TestHTTP500Handler:
    """Built-in 500 handler returns JSON."""

    def test_status_code(self, app):
        @app.route("/raise/unhandled")
        def raise_unhandled():
            raise RuntimeError("unexpected crash")

        client = app.test_client()
        resp = client.get("/raise/unhandled")
        assert resp.status_code == 500

    def test_response_body(self, app):
        @app.route("/raise/unhandled-body")
        def raise_unhandled_body():
            raise RuntimeError("unexpected crash")

        client = app.test_client()
        resp = client.get("/raise/unhandled-body")
        data = resp.get_json()
        assert data["error"] == "Internal server error"
        assert data["status"] == 500


# ============================================================================
# Consistency tests
# ============================================================================


class TestResponseConsistency:
    """All error responses share the same JSON structure."""

    def test_all_responses_have_error_and_status_keys(self, client):
        """Every registered handler returns both 'error' and 'status' keys."""
        routes = [
            "/raise/validation-error",
            "/raise/invalid-credentials",
            "/raise/authentication-error",
            "/raise/permission-denied",
            "/raise/student-not-found",
            "/raise/course-not-found",
            "/raise/grade-not-found",
            "/raise/duplicate-student",
            "/raise/already-enrolled",
            "/raise/course-full",
            "/raise/enrollment-error",
            "/raise/insufficient-funds",
            "/raise/payment-error",
            "/raise/transaction-failed",
            "/raise/finance-error",
            "/raise/database-error",
        ]
        for route in routes:
            resp = client.get(route)
            data = resp.get_json()
            assert "error" in data, f"Missing 'error' key for {route}"
            assert "status" in data, f"Missing 'status' key for {route}"
            assert data["status"] == resp.status_code, (
                f"Status mismatch for {route}: JSON={data['status']}, HTTP={resp.status_code}"
            )

    def test_content_type_is_json(self, client):
        """All error responses are served as application/json."""
        resp = client.get("/raise/validation-error")
        assert resp.content_type.startswith("application/json")

        resp = client.get("/this/route/does/not/exist")
        assert resp.content_type.startswith("application/json")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
